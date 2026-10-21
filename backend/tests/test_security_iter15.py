"""Iteration 15: security fixes SEC-001 (DoS upload/ZIP/XML limits), SEC-002 (CSV formula injection), SEC-003 (SameSite=Lax cookies) + sample regression."""
import csv
import io
import os
import sys
import time
import zipfile

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
BASE_URL = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
S = "/app/tests/samples"
VAT = "01234567890"
ADMIN = {"email": "fabrizio.gemignani@gmail.com", "password": "FattureXML2026"}


def rd(n):
    with open(f"{S}/{n}", "rb") as f:
        return f.read()


def xml(num, ces_name="Mario Rossi SRL", ced_name="TEST_Cedente", data="2025-05-10", imp="100.00", iva="22.00"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"><FatturaElettronicaHeader>
<DatiTrasmissione><CodiceDestinatario>0000000</CodiceDestinatario></DatiTrasmissione>
<CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{VAT}</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>{ced_name}</Denominazione></Anagrafica></DatiAnagrafici></CedentePrestatore>
<CessionarioCommittente><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>07777777777</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>{ces_name}</Denominazione></Anagrafica></DatiAnagrafici></CessionarioCommittente>
</FatturaElettronicaHeader><FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento><TipoDocumento>TD01</TipoDocumento><Divisa>EUR</Divisa><Data>{data}</Data><Numero>{num}</Numero><ImportoTotaleDocumento>122.00</ImportoTotaleDocumento></DatiGeneraliDocumento></DatiGenerali>
<DatiBeniServizi><DatiRiepilogo><AliquotaIVA>22.00</AliquotaIVA><ImponibileImporto>{imp}</ImponibileImporto><Imposta>{iva}</Imposta></DatiRiepilogo></DatiBeniServizi></FatturaElettronicaBody></p:FatturaElettronica>""".encode()


def mkzip(entries, method=zipfile.ZIP_DEFLATED):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", method) as z:
        for n, d in entries:
            z.writestr(n, d)
    return b.getvalue()


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json=ADMIN)
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    sess.login_resp = r
    sess.headers["X-Company-Vat"] = VAT
    created = sess.post(f"{API}/companies", json={"company_vat": VAT, "company_name": "TEST_Sec Co"}).status_code == 200
    yield sess
    m = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    m.invoices.delete_many({"company_vat": VAT})
    m.anagrafiche.delete_many({"company_vat": VAT})
    if created:
        sess.delete(f"{API}/companies/{VAT}")


def up(s, files, timeout=120):
    return s.post(f"{API}/invoices/upload", files=[("files", (n, d, "application/octet-stream")) for n, d in files], timeout=timeout)


def msgs(r):
    return [(x["filename"], x["status"], x.get("message", "")) for x in r.json()["results"]]


# ---- SEC-003 cookies ----
class TestCookies:
    @pytest.mark.xfail(reason="Emergent preview ingress rewrites SameSite=lax -> SameSite=None; Partitioned (backend on :8001 emits lax)", strict=False)
    def test_login_cookies_samesite_lax(self, s):
        raw = s.login_resp.headers.get("set-cookie", "")
        for name in ("access_token", "refresh_token"):
            part = [c for c in raw.split(", ") if c.startswith(name + "=")]
            assert part, raw
            low = part[0].lower()
            assert "samesite=lax" in low and "secure" in low and "httponly" in low, part[0]

    def test_me_works_with_cookie(self, s):
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 200 and r.json()["email"] == ADMIN["email"]


# ---- SEC-001 upload limits ----
class TestUploadLimits:
    def test_more_than_50_files_400(self, s):
        r = up(s, [(f"f{i}.xml", b"<x/>") for i in range(51)])
        assert r.status_code == 400 and "50" in r.json()["detail"]

    def test_exactly_50_files_ok(self, s):
        r = up(s, [(f"f{i}.xml", b"<x/>") for i in range(50)])
        assert r.status_code == 200 and len(r.json()["results"]) == 50

    def test_nested_3_levels_ok(self, s):
        l3 = mkzip([("inv.xml", xml("TEST_N3"))])
        l2 = mkzip([("l3.zip", l3)])
        outer = mkzip([("l2.zip", l2)])
        r = up(s, [("outer.zip", outer)])
        res = msgs(r)
        assert r.status_code == 200 and res[0][1] == "ok", res

    def test_nested_4_levels_rejected(self, s):
        l4 = mkzip([("inv.xml", xml("TEST_N4"))])
        l3 = mkzip([("l4.zip", l4)])
        l2 = mkzip([("l3.zip", l3)])
        outer = mkzip([("l2.zip", l2)])
        r = up(s, [("outer.zip", outer)])
        res = msgs(r)
        assert r.status_code == 200 and res[0][1] == "error" and "Troppi archivi ZIP annidati" in res[0][2], res

    def test_member_25mb_rejected(self, s):
        big = b"<?xml version='1.0'?><FatturaElettronica>" + b" " * (25 * 1024 * 1024) + b"</FatturaElettronica>"
        z = mkzip([("big.xml", big), ("ok.xml", xml("TEST_BIGOK"))])
        assert len(z) < 1024 * 1024
        t = time.time()
        r = up(s, [("bomb.zip", z)])
        res = msgs(r)
        assert r.status_code == 200, r.text
        assert any("File troppo grande (max 20 MB)" in m for _, _, m in res), res
        assert any(st == "ok" for _, st, _ in res), res
        assert time.time() - t < 30
        assert s.get(f"{API}/auth/me").status_code == 200

    def test_total_over_300mb_rejected(self, s):
        member = b" " * (19 * 1024 * 1024)
        z = mkzip([(f"m{i}.xml", member) for i in range(17)])
        r = up(s, [("total.zip", z)])
        res = msgs(r)
        assert r.status_code == 200 and any("Archivio troppo grande" in m for _, _, m in res), res

    def test_too_many_members(self, s):
        z = mkzip([(f"m{i}.xml", b"<x/>") for i in range(5001)])
        r = up(s, [("many.zip", z)])
        res = msgs(r)
        assert r.status_code == 200 and "Archivio troppo grande" in res[-1][2], res[-1]

    def test_billion_laughs(self, s):
        lol = b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">' + b"".join(
            f'<!ENTITY lol{i} "{("&lol" + (str(i - 1) if i > 1 else "") + ";") * 10}">'.encode() for i in range(1, 10)
        ) + b"]><FatturaElettronica>&lol9;</FatturaElettronica>"
        r = up(s, [("lol.xml", lol)])
        res = msgs(r)
        assert r.status_code == 200 and res[0][1] == "error" and "DTD/ENTITY" in res[0][2], res
        assert s.get(f"{API}/auth/me").status_code == 200

    def test_billion_laughs_utf16_no_crash(self, s):
        lol = ('<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE lolz [<!ENTITY lol "lol">' + "".join(
            f'<!ENTITY lol{i} "{("&lol" + (str(i - 1) if i > 1 else "") + ";") * 10}">' for i in range(1, 10)
        ) + "]><FatturaElettronica>&lol9;</FatturaElettronica>").encode("utf-16")
        t = time.time()
        r = up(s, [("lol16.xml", lol)])
        res = msgs(r)
        print("UTF16 result:", res)
        assert r.status_code == 200 and res[0][1] == "error", res
        assert time.time() - t < 30

    def test_encrypted_zip_member_no_500(self, s):
        # zip with encryption flag set on member -> zipfile raises RuntimeError on read
        z = bytearray(mkzip([("enc.xml", xml("TEST_ENC"))], zipfile.ZIP_STORED))
        # set general purpose bit 0 (encrypted) in local + central headers
        for sig in (b"PK\x03\x04", b"PK\x01\x02"):
            i = z.find(sig)
            off = i + (6 if sig == b"PK\x03\x04" else 8)
            z[off] |= 0x01
        r = up(s, [("enc.zip", bytes(z))])
        print("ENC:", r.status_code, r.text[:300])
        assert r.status_code == 200, r.text[:300]

    def test_corrupt_crc_zip_no_500(self, s):
        z = bytearray(mkzip([("c.xml", xml("TEST_CRC"))], zipfile.ZIP_STORED))
        i = z.find(b"TEST_CRC")
        z[i] = ord("X")
        r = up(s, [("crc.zip", bytes(z))])
        print("CRC:", r.status_code, r.text[:300])
        assert r.status_code == 200, r.text[:300]


# ---- SEC-002 CSV injection ----
class TestCsvInjection:
    def test_formula_prefixed(self, s):
        files = [
            ("TEST_h.xml", xml("TEST_CSV1", ces_name='=HYPERLINK("http://evil","x")')),
            ("TEST_p.xml", xml("TEST_CSV2", ces_name="+1+1")),
            ("TEST_a.xml", xml("TEST_CSV3", ces_name="@SUM(1)")),
            ("TEST_m.xml", xml("-TEST_CSV4", ces_name="-2+3")),
        ]
        r = up(s, files)
        assert all(st == "ok" for _, st, _ in msgs(r)), msgs(r)
        e = s.get(f"{API}/invoices/export", params={"tipo": "attiva"})
        assert e.status_code == 200
        rows = list(csv.reader(io.StringIO(e.content.decode("utf-8-sig")), delimiter=";"))
        by = {row[5]: row for row in rows[1:]}
        print(rows)
        assert "'=HYPERLINK(\"http://evil\",\"x\")" in by
        assert "'+1+1" in by and "'@SUM(1)" in by and "'-2+3" in by
        row = by["'+1+1"]
        assert row[7] == "100,00" and row[8] == "22,00" and row[9] == "122,00"
        assert by["'-2+3"][2] == "'-TEST_CSV4"
        assert by["'+1+1"][2] == "TEST_CSV2"
        # stored value unchanged
        lst = s.get(f"{API}/invoices", params={"tipo": "attiva", "q": "TEST_CSV2"}).json()["items"]
        assert lst[0]["controparte_nome"] == "+1+1"


# ---- Regression samples ----
class TestSamples:
    def test_samples_import(self, s):
        r = up(s, [(n, rd(n)) for n in ("IT01234567890_00001.xml", "IT05555555555_A0001.xml", "IT05555555555_A0002.xml.p7m", "lotto.zip")])
        res = msgs(r)
        print(res)
        assert r.status_code == 200
        assert sum(1 for _, st, _ in res if st == "ok") >= 5, res
        assert not [x for x in res if x[1] == "error"], res
