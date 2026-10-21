"""Iteration 17: bounded streaming in fattura_parser._read_member (zip bomb with lying file_size) + API regression."""
import io
import os
import struct
import sys
import threading
import time
import tracemalloc
import zipfile

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from fattura_parser import extract_xml_files  # noqa: E402

load_dotenv("/app/backend/.env")
with open("/app/frontend/.env") as f:
    BASE_URL = [l.split("=", 1)[1].strip().rstrip("/") for l in f if l.startswith("REACT_APP_BACKEND_URL=")][0]
API = f"{BASE_URL}/api"
VAT = "01234567890"
ADMIN = {"email": "fabrizio.gemignani@gmail.com", "password": "FattureXML2026"}
BAD_MSG = "File dell'archivio illeggibile, corrotto o protetto da password"
BIG_MSG = "File troppo grande (max 20 MB)"
SAMPLES = "/app/tests/samples"
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def xml(num):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"><FatturaElettronicaHeader>
<CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{VAT}</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>TEST_Ced17</Denominazione></Anagrafica></DatiAnagrafici></CedentePrestatore>
<CessionarioCommittente><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>07777777777</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>TEST_Ces17</Denominazione></Anagrafica></DatiAnagrafici></CessionarioCommittente>
</FatturaElettronicaHeader><FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento><TipoDocumento>TD01</TipoDocumento><Divisa>EUR</Divisa><Data>2025-06-01</Data><Numero>{num}</Numero><ImportoTotaleDocumento>122.00</ImportoTotaleDocumento></DatiGeneraliDocumento></DatiGenerali>
<DatiBeniServizi><DatiRiepilogo><AliquotaIVA>22.00</AliquotaIVA><ImponibileImporto>100.00</ImponibileImporto><Imposta>22.00</Imposta></DatiRiepilogo></DatiBeniServizi></FatturaElettronicaBody></p:FatturaElettronica>""".encode()


def mkzip(entries, method=zipfile.ZIP_DEFLATED):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", method) as z:
        for n, d in entries:
            z.writestr(n, d)
    return bytearray(b.getvalue())


def lie(z, size=1000, idx=0):
    """Patch declared uncompressed size of member idx in local + central header."""
    lp = cp = -1
    for _ in range(idx + 1):
        lp = z.find(b"PK\x03\x04", lp + 1)
        cp = z.find(b"PK\x01\x02", cp + 1)
    struct.pack_into("<I", z, lp + 22, size)
    struct.pack_into("<I", z, cp + 24, size)
    return z


_BOMB = None


def bomb400():
    global _BOMB
    if _BOMB is None:
        _BOMB = bytes(lie(mkzip([("big.xml", b" " * (400 * 1024 * 1024)), ("ok.xml", xml("TEST_BOMBOK"))])))
    return _BOMB


def peak(name, data):
    tracemalloc.start()
    res = list(extract_xml_files(name, data))
    p = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return res, p / 1e6


# ---- parser-level memory bound ----
class TestParserMemory:
    def test_bomb_400mb_lying_1000(self):
        z = bomb400()
        assert len(z) < 1024 * 1024
        res, mb = peak("bomb.zip", z)
        print("peak MB", mb, res[0][:1], res[0][2])
        assert mb < 50, mb
        assert res[0][0] == "bomb.zip/big.xml" and res[0][1] is None and res[0][2] == BAD_MSG
        assert res[1][0] == "bomb.zip/ok.xml" and res[1][1] is not None

    def test_bomb_lying_19mb_declared(self):
        z = bytes(lie(mkzip([("big.xml", b" " * (400 * 1024 * 1024))]), size=19 * 1024 * 1024))
        res, mb = peak("b.zip", z)
        print("peak MB", mb, res)
        assert mb < 120 and res[0][2] in (BAD_MSG, BIG_MSG)

    def test_bomb_nested(self):
        inner = bytes(lie(mkzip([("big.xml", b" " * (200 * 1024 * 1024))])))
        outer = bytes(mkzip([("inner.zip", inner), ("ok.xml", xml("TEST_NESTOK"))]))
        res, mb = peak("o.zip", outer)
        print("peak MB", mb, [(n, e) for n, _, e in res])
        assert mb < 50 and res[0][2] == BAD_MSG and res[1][2] is None

    def test_bomb_stored_lying(self):
        z = bytes(lie(mkzip([("big.xml", b" " * (30 * 1024 * 1024)), ("ok.xml", xml("x"))], zipfile.ZIP_STORED)))
        res, mb = peak("s.zip", z)
        assert res[0][2] == BAD_MSG and res[1][2] is None

    def test_honest_25mb(self):
        z = bytes(mkzip([("big.xml", b" " * (25 * 1024 * 1024)), ("ok.xml", xml("x"))]))
        res, mb = peak("h.zip", z)
        assert res[0][2] == BIG_MSG and res[1][2] is None and mb < 50

    def test_total_17x19mb(self):
        z = bytes(mkzip([(f"m{i}.xml", b" " * (19 * 1024 * 1024)) for i in range(17)]))
        res = list(extract_xml_files("t.zip", z))
        assert any(e and "Archivio troppo grande" in e for _, _, e in res)
        assert sum(1 for _, d, _ in res if d is not None) == 15


# ---- API ----
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers["X-Requested-With"] = "XMLHttpRequest"
    r = sess.post(f"{API}/auth/login", json=ADMIN)
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    sess.headers["X-Company-Vat"] = VAT
    created = sess.post(f"{API}/companies", json={"company_vat": VAT, "company_name": "TEST_Iter17 Co"}).status_code == 200
    yield sess
    mdb.invoices.delete_many({"company_vat": VAT})
    mdb.anagrafiche.delete_many({"company_vat": VAT})
    if created:
        sess.delete(f"{API}/companies/{VAT}")
    mdb.companies.delete_many({"_id": VAT})


def up(s, files, timeout=180):
    r = s.post(f"{API}/invoices/upload", files=[("files", (n, bytes(d), "application/octet-stream")) for n, d in files], timeout=timeout)
    return r, [(x.get("filename") or x.get("name"), x.get("status"), x.get("message") or x.get("error") or "") for x in (r.json().get("results", []) if r.status_code == 200 else [])]


class TestApi:
    def test_bomb_upload_responsive(self, s):
        lat = []
        stop = threading.Event()

        def ping():
            while not stop.is_set():
                t = time.time()
                rr = s.get(f"{API}/auth/me", timeout=30)
                lat.append((rr.status_code, time.time() - t))
                time.sleep(0.3)
        th = threading.Thread(target=ping)
        th.start()
        r, res = up(s, [("bomb.zip", bomb400())])
        stop.set()
        th.join()
        print(res, "max latency", max(l for _, l in lat) if lat else None)
        assert r.status_code == 200, r.text[:300]
        assert any(st == "error" and BAD_MSG in m for _, st, m in res), res
        assert any(st == "ok" for _, st, _ in res), res
        assert all(c == 200 for c, _ in lat)

    def test_corrupt_members_siblings(self, s):
        ok = xml("TEST_SIB1")
        # corrupt CRC
        z1 = mkzip([("a.xml", xml("TEST_C1")), ("ok1.xml", ok)], zipfile.ZIP_STORED)
        cp = z1.find(b"PK\x01\x02")
        lp = z1.find(b"PK\x03\x04")
        z1[cp + 16] ^= 0xFF
        z1[lp + 14] ^= 0xFF
        # encrypted
        z2 = mkzip([("e.xml", b"<x/>"), ("ok2.xml", xml("TEST_SIB2"))], zipfile.ZIP_STORED)
        z2[z2.find(b"PK\x03\x04") + 6] |= 1
        z2[z2.find(b"PK\x01\x02") + 8] |= 1
        # unsupported method 99
        z3 = mkzip([("u.xml", b"<x/>"), ("ok3.xml", xml("TEST_SIB3"))], zipfile.ZIP_STORED)
        struct.pack_into("<H", z3, z3.find(b"PK\x03\x04") + 8, 99)
        struct.pack_into("<H", z3, z3.find(b"PK\x01\x02") + 10, 99)
        r, res = up(s, [("crc.zip", z1), ("enc.zip", z2), ("meth.zip", z3)])
        print(res)
        assert r.status_code == 200
        errs = [m for _, st, m in res if st == "error"]
        assert len(errs) == 3 and all(BAD_MSG in m for m in errs), res
        assert sum(1 for _, st, _ in res if st == "ok") == 3, res

    def test_truncated_member(self, s):
        z = mkzip([("ok.xml", xml("TEST_TR_OK")), ("t.xml", b"A" * 200000 + os.urandom(200000))])
        zf = zipfile.ZipFile(io.BytesIO(bytes(z)))
        info = zf.infolist()[1]
        start = info.header_offset + 30 + len(info.filename)
        z[start + 1000:start + info.compress_size] = b"\x00" * (info.compress_size - 1000)
        r, res = up(s, [("trunc.zip", z)])
        print(res)
        assert r.status_code == 200
        assert any(st == "error" for _, st, _ in res) and any(st == "ok" for _, st, _ in res), res

    def test_honest_25mb_api(self, s):
        r, res = up(s, [("h.zip", mkzip([("big.xml", b" " * (25 * 1024 * 1024)), ("ok.xml", xml("TEST_H25"))]))])
        assert r.status_code == 200 and any(BIG_MSG in m for _, _, m in res) and any(st == "ok" for _, st, _ in res), res

    def test_17x19_api(self, s):
        r, res = up(s, [("t.zip", mkzip([(f"m{i}.xml", b" " * (19 * 1024 * 1024)) for i in range(17)]))])
        assert r.status_code == 200 and any("Archivio troppo grande" in m for _, _, m in res), res

    def test_nesting(self, s):
        l3 = mkzip([("inv.xml", xml("TEST_N3_17"))])
        r, res = up(s, [("o.zip", mkzip([("l2.zip", mkzip([("l3.zip", l3)]))]))])
        assert r.status_code == 200 and res[0][1] == "ok", res
        l4 = mkzip([("inv.xml", xml("TEST_N4_17"))])
        r, res = up(s, [("o.zip", mkzip([("l2.zip", mkzip([("l3.zip", mkzip([("l4.zip", l4)]))]))]))])
        assert r.status_code == 200 and res[0][1] == "error" and "Troppi archivi ZIP annidati" in res[0][2], res

    def test_samples(self, s):
        names = ("IT01234567890_00001.xml", "IT05555555555_A0001.xml", "IT05555555555_A0002.xml.p7m", "lotto.zip")
        files = [(n, open(f"{SAMPLES}/{n}", "rb").read()) for n in names]
        r, res = up(s, files)
        print(res)
        assert r.status_code == 200
        assert not [x for x in res if x[1] == "error"], res
        assert sum(1 for _, st, _ in res if st in ("ok", "duplicate")) >= 5, res
        assert any(".p7m" in (n or "") and "lotto.zip/" in (n or "") for n, _, _ in res), res

    def test_alive(self, s):
        assert s.get(f"{API}/auth/me").status_code == 200
