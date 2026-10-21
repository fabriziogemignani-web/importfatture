"""Iteration 16: CSRF header guard (X-Requested-With) on unsafe /api calls + unreadable ZIP members -> per-file error (no 500)."""
import hashlib
import io
import os
import secrets
import struct
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
BASE_URL = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
# per-xdist-worker VAT so parallel module fixtures don't tear down each other's company
VAT = "0123456780" + os.environ.get("PYTEST_XDIST_WORKER", "gw9")[-1]
ADMIN = {"email": "fabrizio.gemignani@gmail.com", "password": "FattureXML2026"}
XRW = {"X-Requested-With": "XMLHttpRequest"}
BAD_MSG = "File dell'archivio illeggibile, corrotto o protetto da password"
FORBID = "Richiesta non consentita"
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def xml(num, ced="TEST_Ced16"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"><FatturaElettronicaHeader>
<DatiTrasmissione><CodiceDestinatario>0000000</CodiceDestinatario></DatiTrasmissione>
<CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{VAT}</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>{ced}</Denominazione></Anagrafica></DatiAnagrafici></CedentePrestatore>
<CessionarioCommittente><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>07777777777</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>TEST_Ces16</Denominazione></Anagrafica></DatiAnagrafici></CessionarioCommittente>
</FatturaElettronicaHeader><FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento><TipoDocumento>TD01</TipoDocumento><Divisa>EUR</Divisa><Data>2025-06-01</Data><Numero>{num}</Numero><ImportoTotaleDocumento>122.00</ImportoTotaleDocumento></DatiGeneraliDocumento></DatiGenerali>
<DatiBeniServizi><DatiRiepilogo><AliquotaIVA>22.00</AliquotaIVA><ImponibileImporto>100.00</ImponibileImporto><Imposta>22.00</Imposta></DatiRiepilogo></DatiBeniServizi></FatturaElettronicaBody></p:FatturaElettronica>""".encode()


def stored_zip(entries):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_STORED) as z:
        for n, d in entries:
            z.writestr(n, d)
    return bytearray(b.getvalue())


def hdr_offsets(z, idx):
    """Return (local_header_offset, central_header_offset) for member idx."""
    zf = zipfile.ZipFile(io.BytesIO(bytes(z)))
    info = zf.infolist()[idx]
    cpos, n = 0, -1
    while n < idx:
        cpos = z.find(b"PK\x01\x02", cpos + (1 if n >= 0 else 0))
        n += 1
    return info.header_offset, cpos


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json=ADMIN)
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code} {r.text}")
    sess.headers["X-Company-Vat"] = VAT
    created = sess.post(f"{API}/companies", json={"company_vat": VAT, "company_name": "TEST_CSRF Co"}).status_code == 200
    yield sess
    mdb.invoices.delete_many({"company_vat": VAT})
    mdb.anagrafiche.delete_many({"company_vat": VAT})
    mdb.users.delete_many({"email": {"$regex": "^test_csrf16"}})
    mdb.companies.delete_many({"_id": {"$in": ["99887766554", "99887766555"]}})
    if created:
        sess.delete(f"{API}/companies/{VAT}")


def noxrw(s):
    """Copy of authenticated session without the CSRF header."""
    n = requests.Session()
    n.headers.pop("X-Requested-With", None)
    n.cookies.update(s.cookies)
    n.headers["X-Company-Vat"] = VAT
    return n


def up(sess, files):
    return sess.post(f"{API}/invoices/upload", files=[("files", (n, bytes(d), "application/octet-stream")) for n, d in files], timeout=120)


# ---- CSRF guard ----
class TestCsrfGuard:
    def test_login_without_header_403(self):
        n = requests.Session(); n.headers.pop("X-Requested-With", None)
        r = n.post(f"{API}/auth/login", json=ADMIN)
        assert r.status_code == 403 and r.json()["detail"] == FORBID
        assert "access_token" not in r.cookies

    def test_login_wrong_header_value_403(self):
        n = requests.Session(); n.headers["X-Requested-With"] = "fetch"
        assert n.post(f"{API}/auth/login", json=ADMIN).status_code == 403

    def test_login_with_header_200(self):
        r = requests.post(f"{API}/auth/login", json=ADMIN, headers=XRW)
        assert r.status_code == 200 and r.json()["email"] == ADMIN["email"]

    def test_get_without_header_ok(self, s):
        n = noxrw(s)
        assert n.get(f"{API}/auth/me").status_code == 200
        assert n.get(f"{API}/companies").status_code == 200
        assert n.get(f"{API}/invoices").status_code == 200

    def test_upload_without_header_403(self, s):
        r = up(noxrw(s), [("TEST_x.xml", xml("TEST_CSRFUP"))])
        assert r.status_code == 403 and r.json()["detail"] == FORBID
        assert mdb.invoices.count_documents({"numero": "TEST_CSRFUP"}) == 0

    def test_delete_invoice_without_header_403(self, s):
        r = up(s, [("TEST_d.xml", xml("TEST_CSRFDEL"))])
        iid = r.json()["results"][0]["id"]
        assert noxrw(s).delete(f"{API}/invoices/{iid}").status_code == 403
        assert s.get(f"{API}/invoices/{iid}").status_code == 200
        assert s.delete(f"{API}/invoices/{iid}").status_code == 200
        assert s.get(f"{API}/invoices/{iid}").status_code == 404

    def test_companies_without_header_403(self, s):
        n = noxrw(s)
        assert n.post(f"{API}/companies", json={"company_vat": "99887766554", "company_name": "TEST_x"}).status_code == 403
        assert mdb.companies.count_documents({"_id": "99887766554"}) == 0
        assert n.patch(f"{API}/companies/{VAT}", json={"company_vat": VAT, "company_name": "HACK"}).status_code == 403
        assert n.delete(f"{API}/companies/{VAT}").status_code == 403
        assert mdb.companies.find_one({"_id": VAT})["name"] == "TEST_CSRF Co"
        # with header: full CRUD works
        assert s.post(f"{API}/companies", json={"company_vat": "99887766555", "company_name": "TEST_c"}).status_code == 200
        assert s.patch(f"{API}/companies/99887766555", json={"company_vat": "99887766555", "company_name": "TEST_c2"}).json()["company_name"] == "TEST_c2"
        assert s.delete(f"{API}/companies/99887766555").status_code == 200

    def test_users_without_header_403(self, s):
        n = noxrw(s)
        body = {"email": "test_csrf16a@example.com", "name": "T", "password": "TestPass123!", "role": "user", "company_vats": [VAT]}
        assert n.post(f"{API}/users", json=body).status_code == 403
        assert mdb.users.count_documents({"email": "test_csrf16a@example.com"}) == 0
        r = s.post(f"{API}/users", json=body)
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        assert n.patch(f"{API}/users/{uid}", json={"name": "HACK"}).status_code == 403
        assert n.post(f"{API}/users/{uid}/password", json={"password": "Hacked123!"}).status_code == 403
        assert n.delete(f"{API}/users/{uid}").status_code == 403
        assert mdb.users.find_one({"email": "test_csrf16a@example.com"})["name"] == "T"
        assert s.patch(f"{API}/users/{uid}", json={"name": "T2"}).json()["name"] == "T2"
        assert s.post(f"{API}/users/{uid}/password", json={"password": "NewPass123!"}).status_code == 200
        lr = requests.post(f"{API}/auth/login", json={"email": "test_csrf16a@example.com", "password": "NewPass123!"}, headers=XRW)
        assert lr.status_code == 200
        assert s.delete(f"{API}/users/{uid}").status_code == 200

    def test_forgot_reset_need_header(self, s):
        n = requests.Session(); n.headers.pop("X-Requested-With", None)
        assert n.post(f"{API}/auth/forgot-password", json={"email": "test_csrf16_nobody@example.com"}).status_code == 403
        r = requests.post(f"{API}/auth/forgot-password", json={"email": "test_csrf16_nobody@example.com"}, headers=XRW)
        assert r.status_code == 200 and r.json()["ok"] is True
        # seed a user + token in DB
        body = {"email": "test_csrf16b@example.com", "name": "T", "password": "TestPass123!", "role": "user", "company_vats": [VAT]}
        uid = s.post(f"{API}/users", json=body).json()["id"]
        tok = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        mdb.password_reset_tokens.insert_one({"token_hash": hashlib.sha256(tok.encode()).hexdigest(), "user_id": uid, "used": False,
                                              "created_at": now, "expires_at": now + timedelta(hours=1)})
        assert n.post(f"{API}/auth/reset-password", json={"token": tok, "password": "Reset123!x"}).status_code == 403
        r = requests.post(f"{API}/auth/reset-password", json={"token": tok, "password": "Reset123!x"}, headers=XRW)
        assert r.status_code == 200, r.text
        assert requests.post(f"{API}/auth/login", json={"email": body["email"], "password": "Reset123!x"}, headers=XRW).status_code == 200
        s.delete(f"{API}/users/{uid}")

    def test_logout_refresh_need_header(self, s):
        n = noxrw(s)
        assert n.post(f"{API}/auth/refresh").status_code == 403
        assert n.post(f"{API}/auth/logout").status_code == 403

    def test_options_preflight_not_blocked(self):
        r = requests.options(f"{API}/auth/login", headers={"Origin": BASE_URL, "Access-Control-Request-Method": "POST",
                                                            "Access-Control-Request-Headers": "content-type,x-requested-with"})
        assert r.status_code == 200, r.status_code


# ---- Unreadable ZIP members ----
class TestBadZipMembers:
    def _check(self, s, z, name):
        r = up(s, [(name, z)])
        assert r.status_code == 200, r.text[:300]
        res = r.json()["results"]
        print(name, res)
        bad = [x for x in res if x["status"] == "error"]
        ok = [x for x in res if x["status"] == "ok"]
        assert len(bad) == 1 and bad[0]["message"] == BAD_MSG and bad[0]["filename"].endswith("bad.xml"), res
        assert len(ok) == 1 and ok[0]["filename"].endswith("good.xml"), res
        return res

    def test_corrupt_crc_member(self, s):
        z = stored_zip([("bad.xml", xml("TEST_Z_CRCBAD")), ("good.xml", xml("TEST_Z_CRCOK"))])
        i = z.find(b"TEST_Z_CRCBAD")
        z[i] = ord("X")
        self._check(s, z, "crc16.zip")
        assert mdb.invoices.count_documents({"numero": "TEST_Z_CRCOK"}) == 1

    def test_encrypted_member(self, s):
        z = stored_zip([("bad.xml", xml("TEST_Z_ENC")), ("good.xml", xml("TEST_Z_ENCOK"))])
        lh, ch = hdr_offsets(z, 0)
        z[lh + 6] |= 1
        z[ch + 8] |= 1
        self._check(s, z, "enc16.zip")

    def test_unsupported_compression(self, s):
        z = stored_zip([("bad.xml", xml("TEST_Z_CMP")), ("good.xml", xml("TEST_Z_CMPOK"))])
        lh, ch = hdr_offsets(z, 0)
        struct.pack_into("<H", z, lh + 8, 99)
        struct.pack_into("<H", z, ch + 10, 99)
        self._check(s, z, "cmp16.zip")

    def test_truncated_member_data(self, s):
        # deflated member whose compress_size is lied about (truncated stream)
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as zz:
            zz.writestr("good.xml", xml("TEST_Z_TRUOK"))
            zz.writestr("bad.xml", xml("TEST_Z_TRU") * 20)
        z = bytearray(b.getvalue())
        lh, ch = hdr_offsets(z, 1)
        orig = struct.unpack_from("<I", z, ch + 20)[0]
        struct.pack_into("<I", z, lh + 18, orig // 3)
        struct.pack_into("<I", z, ch + 20, orig // 3)
        r = up(s, [("tru16.zip", z)])
        assert r.status_code == 200, r.text[:300]
        res = r.json()["results"]
        print("TRUNC", res)
        assert any(x["status"] == "ok" and x["filename"].endswith("good.xml") for x in res), res
        assert any(x["status"] == "error" and x["filename"].endswith("bad.xml") for x in res), res

    def test_session_still_alive(self, s):
        assert s.get(f"{API}/auth/me").status_code == 200
