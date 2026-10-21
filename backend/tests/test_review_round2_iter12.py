"""Iteration 12: regression of store_invoice (try/except/else) and _parse_root after code-review round 2."""
import io
import os
import zipfile
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
BASE_URL = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
S = "/app/tests/samples"
A, B = "01234567890", "05555555555"


@pytest.fixture(scope="module")
def adm():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
    assert r.status_code == 200
    for v, n in ((A, "TEST_A srl"), (B, "TEST_B srl")):
        s.post(f"{API}/companies", json={"company_vat": v, "company_name": n})
    yield s
    for v in (A, B):
        items = s.get(f"{API}/invoices", params={"limit": 200}, headers={"X-Company-Vat": v}).json().get("items", [])
        for i in items:
            s.delete(f"{API}/invoices/{i['id']}", headers={"X-Company-Vat": v})
        s.delete(f"{API}/companies/{v}")


def up(s, name, data, vat):
    r = s.post(f"{API}/invoices/upload", files=[("files", (name, data))], headers={"X-Company-Vat": vat})
    assert r.status_code == 200, r.text
    return r.json()["results"]


def raw(n):
    with open(f"{S}/{n}", "rb") as f:
        return f.read()


def test_xml_ok_returns_id_then_duplicate(adm):
    r = up(adm, "IT01234567890_00001.xml", raw("IT01234567890_00001.xml"), A)
    assert all(x["status"] == "ok" for x in r), r
    assert isinstance(r[0]["id"], str) and len(r[0]["id"]) > 0
    g = adm.get(f"{API}/invoices/{r[0]['id']}", headers={"X-Company-Vat": A})
    assert g.status_code == 200 and g.json()["numero"] == r[0]["numero"]
    r2 = up(adm, "IT01234567890_00001.xml", raw("IT01234567890_00001.xml"), A)
    assert all(x["status"] == "duplicate" for x in r2), r2


def test_p7m_and_zip(adm):
    r = up(adm, "IT05555555555_A0002.xml.p7m", raw("IT05555555555_A0002.xml.p7m"), B)
    assert r and r[0]["status"] == "ok", r
    r = up(adm, "lotto.zip", raw("lotto.zip"), B)
    assert r and all(x["status"] in ("ok", "duplicate", "error") for x in r), r
    assert any(x["status"] == "ok" for x in r) or any(x["status"] == "duplicate" for x in r), r


def test_invalid_xml(adm):
    r = up(adm, "bad.xml", b"<FatturaElettronica><broken>", A)
    assert r[0]["status"] == "error" and "XML non valido" in r[0]["message"], r
    r = up(adm, "other.xml", b"<?xml version='1.0'?><Foo/>", A)
    assert r[0]["status"] == "error" and "FatturaElettronica" in r[0]["message"], r


def test_zip_with_bad_entry(adm):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("bad.xml", "<nope")
    r = up(adm, "bad.zip", buf.getvalue(), A)
    assert r and r[0]["status"] == "error", r


def test_detail_and_anagrafiche(adm):
    items = adm.get(f"{API}/invoices", params={"limit": 50}, headers={"X-Company-Vat": A}).json()["items"]
    assert items
    an = adm.get(f"{API}/anagrafiche", headers={"X-Company-Vat": A}).json()
    lst = an if isinstance(an, list) else an.get("items", [])
    assert lst
    d = adm.get(f"{API}/anagrafiche/{lst[0]['id']}", headers={"X-Company-Vat": A})
    assert d.status_code == 200
    st = adm.get(f"{API}/stats", headers={"X-Company-Vat": A}).json()
    assert len(st["mensile"]) == 12
