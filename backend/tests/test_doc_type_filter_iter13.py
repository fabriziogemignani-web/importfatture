"""Iteration 13: TipoDocumento filter on /api/invoices, /api/invoices/export, /api/invoices/doc-types."""
import os
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
A, B = "01234567890", "05555555555"
TPL = open("/app/tests/samples/IT01234567890_00001.xml", encoding="utf-8").read()
# (TipoDocumento, Numero, Data, Totale)
SEED = [("TD01", "10", "2025-03-15", "1220.00"), ("TD01", "11", "2025-04-10", "500.00"),
        ("TD04", "12", "2025-05-20", "300.00"), ("TD05", "13", "2025-06-01", "100.00"),
        ("TD04", "1", "2026-01-10", "50.00")]
HA = {"X-Company-Vat": A}


def make_xml(td, num, data, tot):
    return (TPL.replace("<TipoDocumento>TD01</TipoDocumento>", f"<TipoDocumento>{td}</TipoDocumento>")
            .replace("<Data>2025-03-15</Data><Numero>10</Numero>", f"<Data>{data}</Data><Numero>{num}</Numero>")
            .replace("<ImportoTotaleDocumento>1220.00</ImportoTotaleDocumento>", f"<ImportoTotaleDocumento>{tot}</ImportoTotaleDocumento>"))


def login():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
    assert r.status_code == 200
    return s


def seed(s):
    for v, n in ((A, "TEST_A srl"), (B, "TEST_B srl")):
        s.post(f"{API}/companies", json={"company_vat": v, "company_name": n})
    files = [("files", (f"IT01234567890_T{td}{num}.xml", make_xml(td, num, d, t).encode())) for td, num, d, t in SEED]
    r = s.post(f"{API}/invoices/upload", files=files, headers=HA)
    assert r.status_code == 200, r.text
    return r.json()["results"]


def cleanup(s):
    for v in (A, B):
        items = s.get(f"{API}/invoices", params={"limit": 200}, headers={"X-Company-Vat": v}).json().get("items", [])
        for i in items:
            s.delete(f"{API}/invoices/{i['id']}", headers={"X-Company-Vat": v})
        s.delete(f"{API}/companies/{v}")


@pytest.fixture(scope="module")
def adm():
    s = login()
    res = seed(s)
    assert all(x["status"] in ("ok", "duplicate") for x in res), res
    yield s
    if os.environ.get("KEEP_SEED") != "1":
        cleanup(s)


def test_doc_types_2025(adm):
    r = adm.get(f"{API}/invoices/doc-types", params={"tipo": "attiva", "anno": 2025}, headers=HA)
    assert r.status_code == 200
    assert r.json() == [{"code": "TD01", "n": 2}, {"code": "TD04", "n": 1}, {"code": "TD05", "n": 1}]


def test_doc_types_2026_and_all(adm):
    assert adm.get(f"{API}/invoices/doc-types", params={"tipo": "attiva", "anno": 2026}, headers=HA).json() == [{"code": "TD04", "n": 1}]
    allt = adm.get(f"{API}/invoices/doc-types", params={"tipo": "attiva"}, headers=HA).json()
    assert {"code": "TD04", "n": 2} in allt


def test_doc_types_passive_empty(adm):
    assert adm.get(f"{API}/invoices/doc-types", params={"tipo": "passiva"}, headers=HA).json() == []


def test_doc_types_scoped_by_vat(adm):
    r = adm.get(f"{API}/invoices/doc-types", headers={"X-Company-Vat": B})
    assert r.status_code == 200 and r.json() == []


def test_list_filter_td04(adm):
    d = adm.get(f"{API}/invoices", params={"tipo": "attiva", "anno": 2025, "tipo_documento": "TD04"}, headers=HA).json()
    assert d["total"] == 1 and d["items"][0]["tipo_documento"] == "TD04" and d["items"][0]["numero"] == "12"
    assert d["somma_totale"] == 300.0


def test_list_filter_lowercase(adm):
    d = adm.get(f"{API}/invoices", params={"tipo": "attiva", "tipo_documento": "td04"}, headers=HA).json()
    assert d["total"] == 2 and all(i["tipo_documento"] == "TD04" for i in d["items"])


def test_list_filter_combined_with_search_and_order(adm):
    d = adm.get(f"{API}/invoices", params={"tipo": "attiva", "anno": 2025, "tipo_documento": "TD01", "order": "desc"}, headers=HA).json()
    assert [i["numero"] for i in d["items"]] == ["11", "10"]
    d = adm.get(f"{API}/invoices", params={"tipo": "attiva", "anno": 2025, "tipo_documento": "TD01", "q": "11"}, headers=HA).json()
    assert d["total"] >= 1 and all(i["tipo_documento"] == "TD01" for i in d["items"])
    d = adm.get(f"{API}/invoices", params={"tipo": "attiva", "anno": 2026, "tipo_documento": "TD01"}, headers=HA).json()
    assert d["total"] == 0 and d["somma_totale"] == 0


def test_list_other_vat_no_leak(adm):
    d = adm.get(f"{API}/invoices", params={"tipo_documento": "TD04"}, headers={"X-Company-Vat": B}).json()
    assert d["total"] == 0


def test_export_td04(adm):
    r = adm.get(f"{API}/invoices/export", params={"tipo": "attiva", "anno": 2025, "tipo_documento": "td04"}, headers=HA)
    assert r.status_code == 200
    lines = [l for l in r.content.decode("utf-8-sig").splitlines() if l.strip()]
    assert len(lines) == 2, lines
    assert ";TD04;" in lines[1]


def test_export_no_filter(adm):
    r = adm.get(f"{API}/invoices/export", params={"tipo": "attiva", "anno": 2025}, headers=HA)
    lines = [l for l in r.content.decode("utf-8-sig").splitlines() if l.strip()]
    assert len(lines) == 5
