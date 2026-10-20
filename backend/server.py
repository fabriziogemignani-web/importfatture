from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import csv
import hashlib
import io
import secrets
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Annotated, List, Optional

import bcrypt
import jwt
from bson import ObjectId
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from fattura_parser import extract_xml_files, parse_fattura
from email_service import reset_email_html, send_email

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

app = FastAPI()
api = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

JWT_ALGORITHM = "HS256"

# ---------- Models ----------
PyObjectId = Annotated[str, BeforeValidator(str)]


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc):
        return cls.model_validate(doc) if doc else None

    def to_mongo(self):
        d = self.model_dump(by_alias=True, exclude_none=True)
        d.pop("_id", None)
        return d


class Invoice(BaseDocument):
    tipo: str
    anno: int
    numero: str
    data: str
    totale: float = 0


class Anagrafica(BaseDocument):
    chiave: str
    denominazione: str = ""
    ruoli: List[str] = []


class LoginIn(BaseModel):
    email: str
    password: str


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8)


class UserCreate(BaseModel):
    email: str
    name: str = ""
    role: str = Field(default="user", pattern="^(admin|user)$")
    password: str = Field(min_length=8)
    company_vats: List[str] = []


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    active: Optional[bool] = None
    company_vats: Optional[List[str]] = None


class PasswordIn(BaseModel):
    password: str = Field(min_length=8)


class SettingsIn(BaseModel):
    company_vat: str = ""
    company_name: str = ""


# ---------- Auth ----------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    return bcrypt.checkpw(p.encode(), h.encode())


def _token(payload: dict, delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": int(now.timestamp()), "exp": now + delta}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


def _session_valid(payload: dict, user: Optional[dict]) -> bool:
    return bool(user) and user.get("active", True) and payload.get("iat", 0) >= user.get("pwd_at", 0)


async def _set_password(oid: ObjectId, password: str):
    u = await db.users.find_one_and_update(
        {"_id": oid}, {"$set": {"password_hash": hash_password(password), "pwd_at": int(datetime.now(timezone.utc).timestamp())}})
    if u:
        await db.login_attempts.delete_many({"identifier": {"$regex": f":{re.escape(u['email'])}$"}})
    return u


def set_auth_cookies(response: Response, user_id: str, email: str):
    access = _token({"sub": user_id, "email": email, "type": "access"}, timedelta(minutes=15))
    refresh = _token({"sub": user_id, "type": "refresh"}, timedelta(days=7))
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=900, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=604800, path="/")


def _public_user(u: dict) -> dict:
    return {"id": str(u["_id"]), "email": u["email"], "name": u.get("name", ""), "role": u.get("role", "user"),
            "active": u.get("active", True), "company_vats": u.get("company_vats", []), "created_at": u.get("created_at")}


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    auth = request.headers.get("Authorization", "")
    if not token and auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        raise HTTPException(401, "Non autenticato")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sessione scaduta")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token non valido")
    if payload.get("type") != "access":
        raise HTTPException(401, "Token non valido")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not _session_valid(payload, user):
        raise HTTPException(401, "Utente non trovato o disattivato")
    return _public_user(user)


async def require_admin(user=Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Operazione riservata agli amministratori")
    return user


@api.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.strip().lower()
    fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ident = f"{fwd or (request.client.host if request.client else 'x')}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    now = datetime.now(timezone.utc)
    if att and att.get("count", 0) >= 5:
        locked = att["last"].replace(tzinfo=timezone.utc) if att["last"].tzinfo is None else att["last"]
        if now - locked < timedelta(minutes=15):
            raise HTTPException(429, "Troppi tentativi. Riprova tra 15 minuti.")
        await db.login_attempts.delete_one({"identifier": ident})
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        await db.login_attempts.update_one({"identifier": ident}, {"$inc": {"count": 1}, "$set": {"last": now}}, upsert=True)
        raise HTTPException(401, "Email o password non corretti")
    if not user.get("active", True):
        raise HTTPException(403, "Account disattivato. Contatta l'amministratore.")
    await db.login_attempts.delete_one({"identifier": ident})
    set_auth_cookies(response, str(user["_id"]), email)
    return _public_user(user)


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/", secure=True, samesite="none")
    response.delete_cookie("refresh_token", path="/", secure=True, samesite="none")
    return {"ok": True}


@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user


@api.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "Non autenticato")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Sessione scaduta")
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Token non valido")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not _session_valid(payload, user):
        raise HTTPException(401, "Utente non trovato o disattivato")
    set_auth_cookies(response, str(user["_id"]), user["email"])
    return _public_user(user)


def _hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


@api.post("/auth/forgot-password")
async def forgot_password(body: ForgotIn):
    email = body.email.strip().lower()
    msg = {"ok": True, "message": "Se l'email è registrata riceverai un link per reimpostare la password."}
    user = await db.users.find_one({"email": email})
    if not user or not user.get("active", True):
        return msg
    now = datetime.now(timezone.utc)
    recent = await db.password_reset_tokens.count_documents({"user_id": str(user["_id"]), "created_at": {"$gt": now - timedelta(hours=1)}})
    if recent >= 3:
        return msg
    token = secrets.token_urlsafe(32)
    res = await db.password_reset_tokens.insert_one({"token_hash": _hash_token(token), "user_id": str(user["_id"]), "used": False,
                                                     "created_at": now, "expires_at": now + timedelta(hours=1)})
    link = f"{os.environ['APP_URL'].rstrip('/')}/reset-password?token={token}"
    try:
        await send_email(to=email, subject="Reimposta la tua password", html=reset_email_html(user.get("name", ""), link))
    except HTTPException as e:
        logger.error(f"Reset email not sent: {e.detail}")
        await db.password_reset_tokens.delete_one({"_id": res.inserted_id})
    return msg


@api.post("/auth/reset-password")
async def reset_password(body: ResetIn):
    rec = await db.password_reset_tokens.find_one({"token_hash": _hash_token(body.token)})
    now = datetime.now(timezone.utc)
    exp = rec["expires_at"].replace(tzinfo=timezone.utc) if rec and rec["expires_at"].tzinfo is None else (rec or {}).get("expires_at")
    if not rec or rec["used"] or exp < now:
        raise HTTPException(400, "Link non valido o scaduto. Richiedine uno nuovo.")
    await _set_password(ObjectId(rec["user_id"]), body.password)
    await db.password_reset_tokens.update_many({"user_id": rec["user_id"]}, {"$set": {"used": True}})
    return {"ok": True}


# ---------- Users (admin) ----------
async def _valid_user_vats(vats: List[str], role: str) -> List[str]:
    vats = list(dict.fromkeys(v for v in (norm_vat(x) for x in vats) if v))
    if vats and await db.companies.count_documents({"_id": {"$in": vats}}) != len(vats):
        raise HTTPException(400, "P.IVA non presente in archivio: creala prima nelle Impostazioni")
    if role == "user" and not vats:
        raise HTTPException(400, "Un utente deve essere collegato ad almeno una P.IVA")
    return vats

async def _other_active_admins(exclude_id: ObjectId) -> int:
    return await db.users.count_documents({"role": "admin", "active": {"$ne": False}, "_id": {"$ne": exclude_id}})


@api.get("/users")
async def list_users(admin=Depends(require_admin)):
    return [_public_user(u) async for u in db.users.find({}).sort("created_at", ASCENDING)]


@api.post("/users")
async def create_user(body: UserCreate, admin=Depends(require_admin)):
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "Email non valida")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Esiste già un utente con questa email")
    vats = await _valid_user_vats(body.company_vats, body.role)
    doc = {"email": email, "name": body.name.strip(), "role": body.role, "active": True, "company_vats": vats,
           "password_hash": hash_password(body.password), "created_at": datetime.now(timezone.utc)}
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _public_user(doc)


@api.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate, admin=Depends(require_admin)):
    oid = _oid(user_id)
    changes = body.model_dump(exclude_none=True)
    current = await db.users.find_one({"_id": oid})
    if not current:
        raise HTTPException(404, "Utente non trovato")
    if "company_vats" in changes or "role" in changes:
        changes["company_vats"] = await _valid_user_vats(changes.get("company_vats", current.get("company_vats", [])),
                                                         changes.get("role", current.get("role", "user")))
    demoting = changes.get("role") == "user" or changes.get("active") is False
    if demoting and user_id == admin["id"]:
        raise HTTPException(400, "Non puoi rimuovere i tuoi permessi di amministratore")
    if demoting and not await _other_active_admins(oid):
        raise HTTPException(400, "Deve rimanere almeno un amministratore attivo")
    u = await db.users.find_one_and_update({"_id": oid}, {"$set": changes}, return_document=True)
    if not u:
        raise HTTPException(404, "Utente non trovato")
    return _public_user(u)


@api.post("/users/{user_id}/password")
async def set_user_password(user_id: str, body: PasswordIn, admin=Depends(require_admin)):
    if not await _set_password(_oid(user_id), body.password):
        raise HTTPException(404, "Utente non trovato")
    return {"ok": True}


@api.delete("/users/{user_id}")
async def delete_user(user_id: str, admin=Depends(require_admin)):
    oid = _oid(user_id)
    if user_id == admin["id"]:
        raise HTTPException(400, "Non puoi eliminare il tuo account")
    if not await _other_active_admins(oid):
        raise HTTPException(400, "Deve rimanere almeno un amministratore attivo")
    res = await db.users.delete_one({"_id": oid})
    if not res.deleted_count:
        raise HTTPException(404, "Utente non trovato")
    await db.password_reset_tokens.delete_many({"user_id": user_id})
    return {"ok": True}


# ---------- Settings ----------
def norm_vat(v: str) -> str:
    v = re.sub(r"[\s.\-]", "", (v or "")).upper()
    return v[2:] if re.match(r"^[A-Z]{2}\d", v) else v


async def get_tenant(request: Request, user=Depends(get_current_user)) -> str:
    header = norm_vat(request.headers.get("X-Company-Vat", ""))
    if user["role"] == "admin":
        vat = header or next(iter(user["company_vats"]), "")
        if not vat or not await db.companies.find_one({"_id": vat}):
            raise HTTPException(400, "Seleziona una P.IVA valida")
        return vat
    allowed = user["company_vats"]
    if header and header not in allowed:
        raise HTTPException(403, "Non hai accesso a questa P.IVA")
    vat = header or next(iter(allowed), "")
    if not vat or not await db.companies.find_one({"_id": vat}):
        raise HTTPException(403, "Nessuna P.IVA associata al tuo account. Contatta l'amministratore.")
    return vat


def _company(c: dict) -> dict:
    return {"company_vat": c["_id"], "company_name": c.get("name", "")}


@api.get("/companies")
async def list_companies(user=Depends(get_current_user)):
    query = {} if user["role"] == "admin" else {"_id": {"$in": user["company_vats"]}}
    return [_company(c) async for c in db.companies.find(query).sort("name", ASCENDING)]


@api.post("/companies")
async def create_company(body: SettingsIn, admin=Depends(require_admin)):
    vat = norm_vat(body.company_vat)
    if not re.match(r"^[A-Z0-9]{8,16}$", vat):
        raise HTTPException(400, "Inserisci una P.IVA valida")
    if await db.companies.find_one({"_id": vat}):
        raise HTTPException(400, "P.IVA già presente")
    doc = {"_id": vat, "name": body.company_name.strip(), "created_at": datetime.now(timezone.utc)}
    await db.companies.insert_one(doc)
    return _company(doc)


@api.patch("/companies/{vat}")
async def rename_company(vat: str, body: SettingsIn, admin=Depends(require_admin)):
    c = await db.companies.find_one_and_update({"_id": norm_vat(vat)}, {"$set": {"name": body.company_name.strip()}}, return_document=True)
    if not c:
        raise HTTPException(404, "P.IVA non trovata")
    return _company(c)


@api.delete("/companies/{vat}")
async def delete_company(vat: str, admin=Depends(require_admin)):
    vat = norm_vat(vat)
    if await db.invoices.count_documents({"company_vat": vat}, limit=1) or await db.users.count_documents({"company_vats": vat}, limit=1):
        raise HTTPException(400, "Impossibile eliminare: ci sono fatture o utenti collegati a questa P.IVA")
    res = await db.companies.delete_one({"_id": vat})
    if not res.deleted_count:
        raise HTTPException(404, "P.IVA non trovata")
    await db.anagrafiche.delete_many({"company_vat": vat})
    return {"ok": True}


# ---------- Upload ----------
async def upsert_anagrafica(party: dict, ruolo: str, company_vat: str) -> Optional[str]:
    chiave = norm_vat(party.get("piva")) or (party.get("codice_fiscale") or "").upper()
    if not chiave:
        return None
    fields = {k: v for k, v in party.items() if v}
    fields["chiave"] = chiave
    fields["updated_at"] = datetime.now(timezone.utc)
    fields["ruolo"] = ruolo
    fields["ruoli"] = [ruolo]
    doc = await db.anagrafiche.find_one_and_update(
        {"company_vat": company_vat, "ruolo": ruolo, "chiave": chiave},
        {"$set": fields, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True, return_document=True,
    )
    return str(doc["_id"])


async def split_anagrafiche() -> None:
    """One-off migration: one anagrafica per ruolo (cliente / fornitore)."""
    async for a in db.anagrafiche.find({"ruolo": {"$exists": False}}):
        ruoli = a.get("ruoli") or ["cliente"]
        await db.anagrafiche.update_one({"_id": a["_id"]}, {"$set": {"ruolo": ruoli[0], "ruoli": [ruoli[0]]}})
        for r in ruoli[1:]:
            copy = {k: v for k, v in a.items() if k != "_id"}
            copy.update(ruolo=r, ruoli=[r])
            new_id = (await db.anagrafiche.insert_one(copy)).inserted_id
            await db.invoices.update_many(
                {"company_vat": a.get("company_vat"), "controparte_id": str(a["_id"]),
                 "tipo": "attiva" if r == "cliente" else "passiva"},
                {"$set": {"controparte_id": str(new_id)}})


async def store_invoice(inv: dict, raw_xml: str, filename: str, company_vat: str) -> dict:
    ced, ces = inv["cedente"], inv["cessionario"]
    is_attiva = company_vat in (norm_vat(ced.get("piva")), (ced.get("codice_fiscale") or "").upper())
    is_passiva = company_vat in (norm_vat(ces.get("piva")), (ces.get("codice_fiscale") or "").upper())
    if not is_attiva and not is_passiva:
        return {"status": "error", "message": f"La P.IVA {company_vat} non compare né come cedente né come cessionario", "numero": inv["numero"]}
    tipo = "attiva" if is_attiva else "passiva"
    controparte = inv["cessionario"] if is_attiva else ced
    ruolo = "cliente" if is_attiva else "fornitore"
    dedup = f"{norm_vat(ced.get('piva')) or ced.get('codice_fiscale')}|{inv['tipo_documento']}|{inv['numero']}|{inv['data']}"
    if await db.invoices.find_one({"company_vat": company_vat, "dedup_key": dedup}, {"_id": 1}):
        return {"status": "duplicate", "message": "Fattura già presente in archivio", "numero": inv["numero"], "tipo": tipo}
    controparte_id = await upsert_anagrafica(controparte, ruolo, company_vat)
    doc = Invoice(
        company_vat=company_vat, tipo=tipo, anno=inv["anno"], numero=inv["numero"], data=inv["data"], totale=inv["totale"],
        **{k: v for k, v in inv.items() if k not in ("anno", "numero", "data", "totale")},
        controparte_id=controparte_id,
        controparte_nome=controparte.get("denominazione", ""),
        controparte_piva=norm_vat(controparte.get("piva")) or controparte.get("codice_fiscale", ""),
        filename=filename, xml=raw_xml, dedup_key=dedup,
        created_at=datetime.now(timezone.utc),
    )
    try:
        res = await db.invoices.insert_one(doc.to_mongo())
    except DuplicateKeyError:
        return {"status": "duplicate", "message": "Fattura già presente in archivio", "numero": inv["numero"], "tipo": tipo}
    return {"status": "ok", "message": f"Fattura {tipo} importata", "numero": inv["numero"], "tipo": tipo, "id": str(res.inserted_id)}


@api.post("/invoices/upload")
async def upload_invoices(files: List[UploadFile] = File(...), company_vat=Depends(get_tenant)):
    results = []
    for f in files:
        data = await f.read()
        for name, xml_bytes, err in extract_xml_files(f.filename or "file", data):
            if err:
                results.append({"filename": name, "status": "error", "message": err})
                continue
            try:
                invoices, raw = parse_fattura(xml_bytes)
            except ValueError as e:
                results.append({"filename": name, "status": "error", "message": str(e)})
                continue
            for inv in invoices:
                r = await store_invoice(inv, raw, name, company_vat)
                results.append({"filename": name, **r})
    return {"results": results}


# ---------- Invoices ----------
LIST_PROJECTION = {"xml": 0, "righe": 0, "riepilogo": 0, "pagamenti": 0, "trasmissione": 0}


def build_query(vat, tipo, anno, q, anagrafica_id):
    query = {"company_vat": vat}
    if tipo:
        query["tipo"] = tipo
    if anno:
        query["anno"] = anno
    if anagrafica_id:
        query["controparte_id"] = anagrafica_id
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [
            {"numero": rx}, {"controparte_nome": rx}, {"controparte_piva": rx},
            {"causale": rx}, {"righe.descrizione": rx}, {"filename": rx},
        ]
    return query


def sort_spec(order: str):
    d = DESCENDING if order == "desc" else ASCENDING
    return [("anno", DESCENDING), ("numero_key", d)]


@api.get("/invoices")
async def list_invoices(tipo: Optional[str] = None, anno: Optional[int] = None, q: Optional[str] = None,
                        anagrafica_id: Optional[str] = None, order: str = "asc", page: int = 1, limit: int = 50,
                        vat=Depends(get_tenant)):
    query = build_query(vat, tipo, anno, q, anagrafica_id)
    total = await db.invoices.count_documents(query)
    limit = max(1, min(limit, 200))
    cursor = db.invoices.find(query, LIST_PROJECTION).sort(sort_spec(order)).skip((max(page, 1) - 1) * limit).limit(limit)
    items = [Invoice.from_mongo(d).model_dump() async for d in cursor]
    agg = await db.invoices.aggregate([{"$match": query}, {"$group": {"_id": None, "totale": {"$sum": "$totale"}}}]).to_list(1)
    return {"items": items, "total": total, "page": page, "limit": limit, "somma_totale": round(agg[0]["totale"], 2) if agg else 0}


@api.get("/invoices/years")
async def invoice_years(tipo: Optional[str] = None, vat=Depends(get_tenant)):
    years = await db.invoices.distinct("anno", {"company_vat": vat, **({"tipo": tipo} if tipo else {})})
    return sorted(years, reverse=True)


def _fmt(n):
    return f"{n:.2f}".replace(".", ",")


@api.get("/invoices/export")
async def export_csv(tipo: Optional[str] = None, anno: Optional[int] = None, q: Optional[str] = None,
                     anagrafica_id: Optional[str] = None, order: str = "asc", vat=Depends(get_tenant)):
    query = build_query(vat, tipo, anno, q, anagrafica_id)
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Tipo", "Anno", "Numero", "Data", "Tipo documento", "Cliente/Fornitore", "P.IVA/CF", "Imponibile", "IVA", "Totale", "Divisa", "File"])
    async for d in db.invoices.find(query, LIST_PROJECTION).sort(sort_spec(order)):
        w.writerow([d["tipo"], d["anno"], d["numero"], d["data"], d.get("tipo_documento", ""), d.get("controparte_nome", ""),
                    d.get("controparte_piva", ""), _fmt(d.get("imponibile", 0)), _fmt(d.get("imposta", 0)), _fmt(d.get("totale", 0)),
                    d.get("divisa", ""), d.get("filename", "")])
    name = f"fatture_{vat}_{tipo or 'tutte'}_{anno or 'tutti-anni'}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _oid(id_: str) -> ObjectId:
    if not ObjectId.is_valid(id_):
        raise HTTPException(404, "Non trovato")
    return ObjectId(id_)


@api.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, vat=Depends(get_tenant)):
    d = await db.invoices.find_one({"_id": _oid(invoice_id), "company_vat": vat})
    if not d:
        raise HTTPException(404, "Fattura non trovata")
    return Invoice.from_mongo(d).model_dump()


@api.get("/invoices/{invoice_id}/xml")
async def get_invoice_xml(invoice_id: str, vat=Depends(get_tenant)):
    d = await db.invoices.find_one({"_id": _oid(invoice_id), "company_vat": vat}, {"xml": 1, "numero": 1, "filename": 1})
    if not d:
        raise HTTPException(404, "Fattura non trovata")
    fname = (d.get("filename") or f"fattura_{d['numero']}").split("/")[-1]
    fname = re.sub(r"\.p7m$", "", fname, flags=re.I)
    if not fname.lower().endswith(".xml"):
        fname += ".xml"
    return Response(d["xml"], media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@api.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, vat=Depends(get_tenant)):
    res = await db.invoices.delete_one({"_id": _oid(invoice_id), "company_vat": vat})
    if not res.deleted_count:
        raise HTTPException(404, "Fattura non trovata")
    return {"ok": True}


# ---------- Anagrafiche ----------
@api.get("/anagrafiche")
async def list_anagrafiche(ruolo: Optional[str] = None, q: Optional[str] = None, anno: Optional[int] = None,
                           vat=Depends(get_tenant)):
    query = {"company_vat": vat}
    if ruolo:
        query["ruoli"] = ruolo
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"denominazione": rx}, {"chiave": rx}, {"codice_fiscale": rx}, {"comune": rx}]
    docs = await db.anagrafiche.find(query).sort("denominazione", ASCENDING).to_list(2000)
    inv_match = {"company_vat": vat}
    if ruolo:
        inv_match["tipo"] = "attiva" if ruolo == "cliente" else "passiva"
    if anno:
        inv_match["anno"] = anno
    counts = {c["_id"]: c async for c in db.invoices.aggregate([
        {"$match": inv_match},
        {"$group": {"_id": "$controparte_id", "n": {"$sum": 1}, "totale": {"$sum": "$totale"}}}
    ])}
    out = []
    for d in docs:
        a = Anagrafica.from_mongo(d).model_dump()
        c = counts.get(a["id"], {})
        if anno and not c:
            continue
        a["n_fatture"] = c.get("n", 0)
        a["totale_fatture"] = round(c.get("totale", 0), 2)
        out.append(a)
    return out


@api.get("/anagrafiche/{anag_id}")
async def get_anagrafica(anag_id: str, vat=Depends(get_tenant)):
    d = await db.anagrafiche.find_one({"_id": _oid(anag_id), "company_vat": vat})
    if not d:
        raise HTTPException(404, "Anagrafica non trovata")
    a = Anagrafica.from_mongo(d).model_dump()
    agg = await db.invoices.aggregate([
        {"$match": {"company_vat": vat, "controparte_id": anag_id}},
        {"$group": {"_id": "$tipo", "n": {"$sum": 1}, "totale": {"$sum": "$totale"}}},
    ]).to_list(10)
    a["riepilogo"] = {g["_id"]: {"n": g["n"], "totale": round(g["totale"], 2)} for g in agg}
    return a


# ---------- Stats ----------
@api.get("/stats")
async def stats(anno: Optional[int] = None, vat=Depends(get_tenant)):
    match = {"company_vat": vat, **({"anno": anno} if anno else {})}
    groups = await db.invoices.aggregate([
        {"$match": match},
        {"$group": {"_id": "$tipo", "n": {"$sum": 1}, "totale": {"$sum": "$totale"}, "imposta": {"$sum": "$imposta"}}},
    ]).to_list(10)
    per_tipo = {g["_id"]: {"n": g["n"], "totale": round(g["totale"], 2), "imposta": round(g["imposta"], 2)} for g in groups}
    monthly = await db.invoices.aggregate([
        {"$match": match},
        {"$group": {"_id": {"m": {"$substr": ["$data", 5, 2]}, "t": "$tipo"}, "totale": {"$sum": "$totale"}}},
    ]).to_list(100)
    months = [{"mese": f"{i:02d}", "attiva": 0, "passiva": 0} for i in range(1, 13)]
    for m in monthly:
        idx = int(m["_id"]["m"]) - 1 if m["_id"]["m"].isdigit() else -1
        if 0 <= idx < 12:
            months[idx][m["_id"]["t"]] = round(m["totale"], 2)
    recent = [Invoice.from_mongo(d).model_dump() async for d in
              db.invoices.find(match, LIST_PROJECTION).sort("created_at", DESCENDING).limit(6)]
    n_clienti = await db.anagrafiche.count_documents({"company_vat": vat, "ruoli": "cliente"})
    n_fornitori = await db.anagrafiche.count_documents({"company_vat": vat, "ruoli": "fornitore"})
    return {"per_tipo": per_tipo, "mensile": months, "recenti": recent, "n_clienti": n_clienti, "n_fornitori": n_fornitori}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ["FRONTEND_URL"].split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_tokens.create_index("token_hash")
    for coll, idx in ((db.invoices, "dedup_key_1"), (db.anagrafiche, "chiave_1"), (db.anagrafiche, "company_vat_1_chiave_1"),
                      (db.invoices, "tipo_1_anno_-1_numero_key_1")):
        if idx in await coll.index_information():
            await coll.drop_index(idx)
    await db.invoices.create_index([("company_vat", 1), ("dedup_key", 1)], unique=True)
    await db.invoices.create_index([("company_vat", 1), ("tipo", 1), ("anno", -1), ("numero_key", 1)])
    await db.invoices.create_index([("company_vat", 1), ("controparte_id", 1)])
    await split_anagrafiche()
    await db.anagrafiche.create_index([("company_vat", 1), ("ruolo", 1), ("chiave", 1)], unique=True)
    async for u in db.users.find({"company_vat": {"$exists": True}}):
        vats = u.get("company_vats") or ([u["company_vat"]] if u.get("company_vat") else [])
        await db.users.update_one({"_id": u["_id"]}, {"$set": {"company_vats": vats}, "$unset": {"company_vat": ""}})
    if "company_vat_1" in await db.users.index_information():
        await db.users.drop_index("company_vat_1")
    await db.users.create_index("company_vats")
    email = os.environ["ADMIN_EMAIL"].lower()
    pwd = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({"email": email, "password_hash": hash_password(pwd), "name": "Admin", "role": "admin",
                                   "created_at": datetime.now(timezone.utc)})
    await db.users.update_one({"email": email}, {"$set": {"role": "admin", "active": True}})


@app.on_event("shutdown")
async def shutdown():
    client.close()
