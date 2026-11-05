"""Iteration 18: bulk ZIP export for the accountant (GET /api/invoices/export-zip) + list dal/al + isolation + regression.
Run: pytest -n0 test_export_zip_iter18.py   (KEEP_DATA=1 keeps seeded data for UI tests; `python test_export_zip_iter18.py cleanup` removes it)."""
import csv
import io
import json
import os
import sys
import zipfile

import pytest
import requests

with open("/app/frontend/.env") as f:
    BASE_URL = [l.split("=", 1)[1].strip().rstrip("/") for l in f if l.startswith("REACT_APP_BACKEND_URL=")][0]
API = f"{BASE_URL}/api"
VAT = "01234567890"
VAT_B = "07777777777"
ADMIN = {"email": "fabrizio.gemignani@gmail.com", "password": "FattureXML2026"}
SAMPLES = "/app/tests/samples"
STATE = "/tmp/iter18_state.json"
USER_B = {"email": "test_iter18_userb@example.com", "password": "TestPass2026!", "name": "TEST_UserB"}


def xml(ced, ces, data, num, tot="122.00"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"><FatturaElettronicaHeader>
<CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{ced}</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>TEST_Ced_{ced}</Denominazione></Anagrafica></DatiAnagrafici></CedentePrestatore>
<CessionarioCommittente><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{ces}</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>TEST_Ces_{ces}</Denominazione></Anagrafica></DatiAnagrafici></CessionarioCommittente>
</FatturaElettronicaHeader><FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento><TipoDocumento>TD01</TipoDocumento><Divisa>EUR</Divisa><Data>{data}</Data><Numero>{num}</Numero><ImportoTotaleDocumento>{tot}</ImportoTotaleDocumento></DatiGeneraliDocumento></DatiGenerali>
<DatiBeniServizi><DatiRiepilogo><AliquotaIVA>22.00</AliquotaIVA><ImponibileImporto>100.00</ImponibileImporto><Imposta>22.00</Imposta></DatiRiepilogo></DatiBeniServizi></FatturaElettronicaBody></p:FatturaElettronica>""".encode()


# (filename, ced, ces, data, numero) generated invoices for company A
GEN = [
    ("TEST_dup.xml", VAT, "09999999999", "2026-10-31", "T1"),
    ("TEST_dup.xml", VAT, "09999999999", "2026-10-15", "T2"),
    ("TEST fattura (è).xml", "08888888888", VAT, "2026-10-01", "T3"),
    ("TEST_t4.xml", "08888888888", VAT, "2026-11-01", "T4"),
    ("TEST_t5.xml", VAT, "09999999999", "2026-09-30", "T5"),
    ("TEST_t6.xml", VAT, "09999999999", "2025-12-31", "T6"),
]


def admin_session(vat=VAT):
    s = requests.Session()
    s.headers["X-Requested-With"] = "XMLHttpRequest"
    r = s.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    s.headers["X-Company-Vat"] = vat
    return s


def upload(s, files):
    r = s.post(f"{API}/invoices/upload", files=[("files", (n, b, "application/octet-stream")) for n, b in files])
    assert r.status_code == 200, r.text
    return r.json()["results"]


def seed():
    s = admin_session()
    state = {"companies": [], "invoice_ids": {VAT: [], VAT_B: []}, "user_id": None}
    for v, n in ((VAT, "TEST_Company A"), (VAT_B, "TEST_Company B")):
        r = s.post(f"{API}/companies", json={"company_vat": v, "company_name": n})
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            state["companies"].append(v)
    files = [(n, open(f"{SAMPLES}/{n}", "rb").read()) for n in sorted(os.listdir(SAMPLES))]
    res = upload(s, files)
    res += upload(s, [(fn, xml(c, e, d, n)) for fn, c, e, d, n in GEN])
    state["invoice_ids"][VAT] = [r["id"] for r in res if r.get("status") == "ok"]
    sb = admin_session(VAT_B)
    resb = upload(sb, [("TEST_dup.xml", xml(VAT_B, "09999999999", "2026-10-10", "B1"))])
    state["invoice_ids"][VAT_B] = [r["id"] for r in resb if r.get("status") == "ok"]
    r = s.post(f"{API}/users", json={**USER_B, "role": "user", "company_vats": [VAT_B]})
    assert r.status_code == 200, r.text
    state["user_id"] = r.json().get("id")
    json.dump(state, open(STATE, "w"))
    return state, res, resb


def cleanup():
    if not os.path.exists(STATE):
        return
    st = json.load(open(STATE))
    for v, ids in st["invoice_ids"].items():
        s = admin_session(v)
        for i in ids:
            s.delete(f"{API}/invoices/{i}")
    s = admin_session()
    if st.get("user_id"):
        s.delete(f"{API}/users/{st['user_id']}")
    for v in st["companies"]:
        print("delete company", v, s.delete(f"{API}/companies/{v}").status_code)
    os.remove(STATE)


@pytest.fixture(scope="module")
def seeded():
    cleanup()
    data = seed()
    yield data
    if not os.environ.get("KEEP_DATA"):
        cleanup()


def adm_list_all():
    return admin_session().get(f"{API}/invoices", params={"limit": 200}).json()["items"]


@pytest.fixture
def adm(seeded):
    return admin_session()


def get_zip(s, **params):
    r = s.get(f"{API}/invoices/export-zip", params=params)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/zip")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    rows = list(csv.reader(io.StringIO(z.read("riepilogo.csv").decode("utf-8-sig")), delimiter=";"))
    return r, z, rows


# --- seeding sanity
def test_seed_imported(seeded):
    _, res, resb = seeded
    ok = [r for r in res if r["status"] == "ok"]
    assert len([r for r in ok if r["numero"].startswith("T")]) == 6, res
    assert all(r["status"] in ("ok", "duplicate") for r in res), res  # samples may pre-exist
    assert len(adm_list_all()) == 11
    assert resb[0]["status"] == "ok"


# --- list endpoint dal/al
def test_list_dal_al_inclusive(adm):
    r = adm.get(f"{API}/invoices", params={"dal": "2026-10-01", "al": "2026-10-31"}).json()
    assert r["total"] == 3
    assert sorted(i["numero"] for i in r["items"]) == ["T1", "T2", "T3"]
    a = adm.get(f"{API}/invoices", params={"tipo": "attiva", "dal": "2025-01-01", "al": "2025-12-31"}).json()
    assert a["total"] == 4
    assert adm.get(f"{API}/invoices", params={"dal": "2026/10/01"}).status_code == 422


# --- ZIP both types
def test_zip_both_types(adm):
    r, z, rows = get_zip(adm, dal="2026-10-01", al="2026-10-31")
    names = sorted(z.namelist())
    assert names == ["attive/TEST_dup.xml", "attive/TEST_dup_2.xml", "passive/TEST_fattura____.xml", "riepilogo.csv"], names
    assert rows[0][0] == "Tipo" and len(rows) == 4
    assert sorted(r_[2] for r_ in rows[1:]) == ["T1", "T2", "T3"]
    assert f'fatture_{VAT}_2026-10-01_2026-10-31.zip' in r.headers["content-disposition"]
    # content is original XML and matches numero
    for n in names[:-1]:
        assert b"<FatturaElettronica" in z.read(n) or b":FatturaElettronica" in z.read(n)


def test_zip_only_passive(adm):
    _, z, rows = get_zip(adm, dal="2026-01-01", al="2026-12-31", tipo="passiva")
    names = z.namelist()
    assert all(n.startswith("passive/") or n == "riepilogo.csv" for n in names), names
    assert len(names) == 5  # A0001, A0002(p7m), T3, T4 + csv
    assert all(r_[0] == "passiva" for r_ in rows[1:])
    # p7m-origin exported as .xml, parsed XML (not p7m envelope)
    assert "passive/IT05555555555_A0002.xml" in names
    assert b"FT/11" in z.read("passive/IT05555555555_A0002.xml")


def test_zip_only_attive_year(adm):
    _, z, rows = get_zip(adm, dal="2025-01-01", al="2025-12-31", tipo="attiva")
    assert len([n for n in z.namelist() if n.startswith("attive/")]) == 4
    assert sorted(r_[2] for r_ in rows[1:]) == sorted(["10", "9", "100", "T6"])


def test_zip_boundaries_single_day(adm):
    _, z, rows = get_zip(adm, dal="2026-10-31", al="2026-10-31")
    assert [r_[2] for r_ in rows[1:]] == ["T1"]


def test_zip_csv_matches_list_totals(adm):
    _, _, rows = get_zip(adm, dal="2026-01-01", al="2026-12-31")
    lst = adm.get(f"{API}/invoices", params={"dal": "2026-01-01", "al": "2026-12-31", "limit": 200}).json()
    assert len(rows) - 1 == lst["total"]
    tot = sum(float(r_[9].replace(",", ".")) for r_ in rows[1:])
    assert round(tot, 2) == lst["somma_totale"]


# --- errors
def test_zip_errors(adm):
    assert adm.get(f"{API}/invoices/export-zip", params={"dal": "2020-01-01", "al": "2020-12-31"}).status_code == 404
    assert adm.get(f"{API}/invoices/export-zip", params={"dal": "2026-13", "al": "2026-12-31"}).status_code == 422
    assert adm.get(f"{API}/invoices/export-zip", params={"dal": "2026-12-31", "al": "2026-01-01"}).status_code == 400
    assert adm.get(f"{API}/invoices/export-zip", params={"dal": "2026-01-01"}).status_code == 422
    assert adm.get(f"{API}/invoices/export-zip", params={"dal": "2026-01-01", "al": "2026-12-31", "tipo": "x"}).status_code == 422
    assert requests.get(f"{API}/invoices/export-zip", params={"dal": "2026-01-01", "al": "2026-12-31"}).status_code == 401


# --- isolation
def test_isolation_user_b(seeded):
    s = requests.Session()
    s.headers["X-Requested-With"] = "XMLHttpRequest"
    assert s.post(f"{API}/auth/login", json={"email": USER_B["email"], "password": USER_B["password"]}).status_code == 200
    _, z, rows = get_zip(s, dal="2026-10-01", al="2026-10-31")
    assert z.namelist() == ["attive/TEST_dup.xml", "riepilogo.csv"]
    assert [r_[2] for r_ in rows[1:]] == ["B1"]
    assert s.get(f"{API}/invoices/export-zip", params={"dal": "2025-01-01", "al": "2025-12-31"}).status_code == 404
    s.headers["X-Company-Vat"] = VAT
    assert s.get(f"{API}/invoices/export-zip", params={"dal": "2026-10-01", "al": "2026-10-31"}).status_code == 403


def test_admin_scoped_by_header(seeded):
    _, z, rows = get_zip(admin_session(VAT_B), dal="2026-10-01", al="2026-10-31")
    assert [r_[2] for r_ in rows[1:]] == ["B1"]


# --- regression
def test_regression_csv_export_and_list(adm):
    r = adm.get(f"{API}/invoices/export", params={"tipo": "attiva", "anno": 2025})
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert len(rows) == 5
    lst = adm.get(f"{API}/invoices", params={"tipo": "passiva"}).json()
    assert lst["total"] == 4


if __name__ == "__main__" and sys.argv[1:] == ["cleanup"]:
    cleanup()
