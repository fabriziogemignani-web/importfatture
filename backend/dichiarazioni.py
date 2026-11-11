import re
from datetime import datetime, timezone
from typing import Optional

from bson import Binary, ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from fattura_parser import parse_fattura

DATE_RX = r"^\d{4}-\d{2}-\d{2}$"
PROT_RX = re.compile(r"^(\d{17})[-/](\d{6})$")
MAX_PDF_BYTES = 5 * 1024 * 1024
FILE_KINDS = ("dichiarazione", "ricevuta")


class DichiarazioneIn(BaseModel):
    cliente_piva: str = Field(min_length=8, max_length=16)
    cliente_nome: str = Field(min_length=1, max_length=200)
    protocollo: str
    data: str = Field(pattern=DATE_RX)
    anno: int = Field(ge=2000, le=2100)
    plafond: float = Field(gt=0)
    data_revoca: Optional[str] = Field(default=None, pattern=DATE_RX)
    note: str = Field(default="", max_length=1000)


def norm_protocollo(p: str) -> Optional[str]:
    p = re.sub(r"\s", "", p or "")
    if re.fullmatch(r"\d{23}", p):
        p = f"{p[:17]}-{p[17:]}"
    m = PROT_RX.match(p)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def prot_key(p: str) -> str:
    return re.sub(r"\D", "", p or "")


def livello(perc: float) -> str:
    if perc > 100:
        return "superato"
    return "attenzione" if perc >= 80 else "ok"


def _sign(d: dict) -> int:
    return -1 if (d.get("tipo_documento") or "").upper() == "TD04" else 1


def _inv_ref(d: dict, importo: float) -> dict:
    return {"invoice_id": str(d["_id"]), "numero": d["numero"], "data": d["data"], "tipo_documento": d.get("tipo_documento", ""),
            "controparte_nome": d.get("controparte_nome", ""), "controparte_piva": d.get("controparte_piva", ""), "importo": importo}


def _public(d: dict) -> dict:
    out = {k: v for k, v in d.items() if k not in ("_id", "company_vat", "files")}
    out["id"] = str(d["_id"])
    out["files"] = {k: v["filename"] for k, v in (d.get("files") or {}).items()}
    for k in ("created_at", "updated_at"):
        if isinstance(out.get(k), datetime):
            out[k] = out[k].isoformat()
    return out


def _check_invoice(d: dict, ref: dict, decl: Optional[dict], anomalies: list) -> None:
    def flag(code, msg):
        anomalies.append({**_inv_ref(d, round(_sign(d) * ref["importo"], 2)), "codice": code, "messaggio": msg,
                          "protocollo": ref["protocollo"]})

    if not PROT_RX.match(ref["protocollo"]):
        flag("protocollo_non_valido", "Protocollo non conforme (17 cifre, trattino o barra, 6 cifre)")
    if not decl:
        flag("non_registrata", "Dichiarazione d'intento non registrata in archivio")
        return
    if decl["cliente_piva"] != d.get("controparte_piva"):
        flag("cliente_diverso", f"Protocollo intestato a {decl['cliente_nome']}, non al cliente della fattura")
    if int(d["data"][:4]) != decl["anno"]:
        flag("fuori_periodo", f"Fattura fuori dall'anno di validità ({decl['anno']})")
    elif d["data"] < decl["data"]:
        flag("fuori_periodo", "Fattura emessa prima della ricevuta della dichiarazione")
    if decl.get("data_revoca") and d["data"] >= decl["data_revoca"]:
        flag("revocata", "Fattura emessa dopo la revoca della dichiarazione")
    if ref.get("data") and ref["data"] != decl["data"]:
        flag("data_diversa", "Data della ricevuta in fattura diversa da quella registrata")
    if not d.get("n35"):
        flag("natura_errata", "Protocollo indicato ma nessuna riga con natura N3.5")


def build_router(db, get_tenant, norm_vat) -> APIRouter:
    r = APIRouter(prefix="/dichiarazioni")

    async def backfill(vat: str) -> None:
        async for d in db.invoices.find({"company_vat": vat, "tipo": "attiva", "intenti_v": {"$exists": False}},
                                        {"xml": 1, "numero": 1, "data": 1}):
            n35, intenti = 0.0, []
            try:
                invs, _ = parse_fattura((d.get("xml") or "").encode("utf-8"))
                match = next((i for i in invs if i["numero"] == d["numero"] and i["data"] == d["data"]), invs[0])
                n35, intenti = match["n35"], match["intenti"]
            except (ValueError, IndexError):
                pass
            await db.invoices.update_one({"_id": d["_id"]}, {"$set": {"n35": n35, "intenti": intenti, "intenti_v": 1}})

    async def compute(vat: str, anno: Optional[int]):
        await backfill(vat)
        decls = await db.dichiarazioni.find({"company_vat": vat}).sort([("anno", -1), ("data", -1)]).to_list(5000)
        by_key = {prot_key(x["protocollo"]): x for x in decls}
        usage = {str(x["_id"]): [] for x in decls}
        anomalies: list = []
        cursor = db.invoices.find(
            {"company_vat": vat, "tipo": "attiva", "$or": [{"n35": {"$ne": 0}}, {"intenti.0": {"$exists": True}}]},
            {"numero": 1, "data": 1, "anno": 1, "tipo_documento": 1, "controparte_nome": 1, "controparte_piva": 1, "n35": 1, "intenti": 1},
        ).sort([("data", 1), ("numero_key", 1)])
        async for d in cursor:
            if not d.get("intenti"):
                anomalies.append({**_inv_ref(d, round(_sign(d) * d["n35"], 2)), "codice": "senza_protocollo", "protocollo": "",
                                  "messaggio": "Operazione N3.5 senza protocollo della dichiarazione d'intento"})
                continue
            for ref in d["intenti"]:
                decl = by_key.get(prot_key(ref["protocollo"]))
                _check_invoice(d, ref, decl, anomalies)
                if decl:
                    usage[str(decl["_id"])].append((d, round(_sign(d) * ref["importo"], 2)))
        out = []
        for x in decls:
            run, fatture = 0.0, []
            for d, imp in usage[str(x["_id"])]:
                run = round(run + imp, 2)
                fatture.append({**_inv_ref(d, imp), "progressivo": run})
                if imp > 0 and run > x["plafond"] + 0.005:
                    anomalies.append({**_inv_ref(d, imp), "codice": "plafond_superato", "protocollo": x["protocollo"],
                                      "messaggio": f"Plafond superato di {run - x['plafond']:.2f} €"})
            perc = round(run / x["plafond"] * 100, 1)
            out.append({**_public(x), "utilizzato": run, "residuo": round(x["plafond"] - run, 2), "percentuale": perc,
                        "livello": livello(perc), "n_fatture": len(fatture), "fatture": fatture})
        if anno:
            out = [x for x in out if x["anno"] == anno]
            anomalies = [a for a in anomalies if a["data"][:4] == str(anno)]
        anomalies.sort(key=lambda a: (a["data"], a["numero"]))
        return out, anomalies

    async def get_decl(vat: str, did: str) -> dict:
        d = ObjectId.is_valid(did) and await db.dichiarazioni.find_one({"_id": ObjectId(did), "company_vat": vat})
        if not d:
            raise HTTPException(404, "Dichiarazione non trovata")
        return d

    def clean(body: DichiarazioneIn) -> dict:
        prot = norm_protocollo(body.protocollo)
        if not prot:
            raise HTTPException(400, "Protocollo non valido: 17 cifre, trattino o barra, 6 cifre (es. 24010312345678901-000001)")
        if body.data_revoca and body.data_revoca < body.data:
            raise HTTPException(400, "La data di revoca non può precedere la data della ricevuta")
        return {**body.model_dump(), "protocollo": prot, "cliente_piva": norm_vat(body.cliente_piva),
                "cliente_nome": body.cliente_nome.strip(), "note": body.note.strip()}

    @r.get("")
    async def list_dichiarazioni(anno: Optional[int] = None, vat=Depends(get_tenant)):
        decls, anomalies = await compute(vat, anno)
        for x in decls:
            x.pop("fatture")
        return {"dichiarazioni": decls, "anomalie": anomalies}

    @r.get("/riepilogo")
    async def riepilogo(vat=Depends(get_tenant)):
        decls, anomalies = await compute(vat, datetime.now(timezone.utc).year)
        return {"attenzione": sum(x["livello"] == "attenzione" for x in decls),
                "superate": sum(x["livello"] == "superato" for x in decls), "anomalie": len(anomalies)}

    @r.post("")
    async def create(body: DichiarazioneIn, vat=Depends(get_tenant)):
        doc = {**clean(body), "company_vat": vat, "files": {}, "created_at": datetime.now(timezone.utc)}
        try:
            res = await db.dichiarazioni.insert_one(doc)
        except DuplicateKeyError:
            raise HTTPException(400, "Protocollo già registrato")
        doc["_id"] = res.inserted_id
        return _public(doc)

    @r.get("/{did}")
    async def detail(did: str, vat=Depends(get_tenant)):
        await get_decl(vat, did)
        decls, _ = await compute(vat, None)
        return next(x for x in decls if x["id"] == did)

    @r.put("/{did}")
    async def update(did: str, body: DichiarazioneIn, vat=Depends(get_tenant)):
        await get_decl(vat, did)
        try:
            d = await db.dichiarazioni.find_one_and_update(
                {"_id": ObjectId(did), "company_vat": vat},
                {"$set": {**clean(body), "updated_at": datetime.now(timezone.utc)}}, return_document=True)
        except DuplicateKeyError:
            raise HTTPException(400, "Protocollo già registrato")
        return _public(d)

    @r.delete("/{did}")
    async def delete(did: str, vat=Depends(get_tenant)):
        await get_decl(vat, did)
        await db.dichiarazioni.delete_one({"_id": ObjectId(did), "company_vat": vat})
        await db.dichiarazioni_files.delete_many({"dich_id": did, "company_vat": vat})
        return {"ok": True}

    def check_kind(kind: str) -> None:
        if kind not in FILE_KINDS:
            raise HTTPException(404, "Allegato non trovato")

    @r.post("/{did}/files/{kind}")
    async def upload_pdf(did: str, kind: str, file: UploadFile = File(...), vat=Depends(get_tenant)):
        check_kind(kind)
        await get_decl(vat, did)
        data = await file.read(MAX_PDF_BYTES + 1)
        if len(data) > MAX_PDF_BYTES:
            raise HTTPException(400, "PDF troppo grande (max 5 MB)")
        if not data.startswith(b"%PDF"):
            raise HTTPException(400, "Il file non è un PDF valido")
        name = re.sub(r"[^\w.\- ]", "_", (file.filename or f"{kind}.pdf").split("/")[-1])[:120]
        await db.dichiarazioni_files.update_one(
            {"dich_id": did, "company_vat": vat, "kind": kind},
            {"$set": {"filename": name, "data": Binary(data), "size": len(data), "uploaded_at": datetime.now(timezone.utc)}},
            upsert=True)
        await db.dichiarazioni.update_one({"_id": ObjectId(did)}, {"$set": {f"files.{kind}": {"filename": name}}})
        return {"ok": True, "filename": name}

    @r.get("/{did}/files/{kind}")
    async def download_pdf(did: str, kind: str, vat=Depends(get_tenant)):
        check_kind(kind)
        f = await db.dichiarazioni_files.find_one({"dich_id": did, "company_vat": vat, "kind": kind})
        if not f:
            raise HTTPException(404, "Allegato non trovato")
        return Response(bytes(f["data"]), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{f["filename"]}"'})

    @r.delete("/{did}/files/{kind}")
    async def delete_pdf(did: str, kind: str, vat=Depends(get_tenant)):
        check_kind(kind)
        await get_decl(vat, did)
        await db.dichiarazioni_files.delete_one({"dich_id": did, "company_vat": vat, "kind": kind})
        await db.dichiarazioni.update_one({"_id": ObjectId(did)}, {"$unset": {f"files.{kind}": ""}})
        return {"ok": True}

    return r


async def ensure_indexes(db) -> None:
    await db.dichiarazioni.create_index([("company_vat", ASCENDING), ("protocollo", ASCENDING)], unique=True)
    await db.dichiarazioni_files.create_index([("company_vat", ASCENDING), ("dich_id", ASCENDING), ("kind", ASCENDING)], unique=True)
