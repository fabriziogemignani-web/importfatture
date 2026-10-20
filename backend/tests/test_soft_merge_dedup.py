"""Soft-merge dedup (API side) + CORS. Requires `python soft_merge_repro.py seed` + backend restart beforehand."""
import json
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = BASE + "/api"
VAT, DUP = "01192570453", "01428910457"
STATE = "/tmp/soft_merge_ids.json"


def ids():
    if not os.path.exists(STATE):
        pytest.skip("seed state missing")
    d = json.load(open(STATE))
    return sorted([d["a1"], d["a2"]])


def xml(numero):
    x = open("/app/tests/samples/IT01234567890_00001.xml").read()
    x = x.replace("01234567890", VAT).replace("09876543210", DUP)
    return x.replace("<Numero>10</Numero>", f"<Numero>{numero}</Numero>").encode()


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    r = ses.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
    assert r.status_code == 200, r.text
    ses.headers["X-Company-Vat"] = VAT
    return ses


# Login / cookies
def test_login_cookies():
    r = requests.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]},
                      headers={"Origin": BASE})
    assert r.status_code == 200
    sc = r.headers.get("set-cookie", "")
    assert "access_token" in sc and "HttpOnly" in sc, sc
    assert r.headers.get("access-control-allow-origin") == BASE, r.headers
    assert r.headers.get("access-control-allow-credentials") == "true"


# CORS preflight
def test_cors_preflight():
    r = requests.options(f"{API}/auth/login", headers={"Origin": BASE, "Access-Control-Request-Method": "POST",
                                                        "Access-Control-Request-Headers": "content-type,x-company-vat"})
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") == BASE, dict(r.headers)
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_cors_foreign_origin_report():
    r = requests.options(f"{API}/auth/login", headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"})
    print("foreign origin preflight:", r.status_code, r.headers.get("access-control-allow-origin"), r.headers.get("access-control-allow-credentials"))


# Clienti list shows only kept record with combined totals
def test_clienti_one_row(s):
    keep, _ = ids()
    r = s.get(f"{API}/anagrafiche", params={"ruolo": "cliente"})
    assert r.status_code == 200
    rows = [a for a in r.json() if a["chiave"].startswith(DUP)]
    assert len(rows) == 1 and rows[0]["id"] == keep
    assert rows[0]["n_fatture"] == 2 and rows[0]["totale_fatture"] == 150.5


def test_fornitori_empty(s):
    r = s.get(f"{API}/anagrafiche", params={"ruolo": "fornitore"})
    assert r.status_code == 200 and r.json() == []


def test_search_does_not_show_merged(s):
    r = s.get(f"{API}/anagrafiche", params={"ruolo": "cliente", "q": "unita"})
    assert r.status_code == 200 and r.json() == []


def test_list_without_ruolo_report(s):
    _, dupe = ids()
    r = s.get(f"{API}/anagrafiche")
    assert r.status_code == 200
    print("no-ruolo list ids:", [a["id"] for a in r.json()], "merged visible:", any(a["id"] == dupe for a in r.json()))


def test_stats_counts(s):
    r = s.get(f"{API}/stats")
    assert r.status_code == 200
    d = r.json()
    assert d["n_clienti"] == 1 and d["n_fornitori"] == 0
    assert d["per_tipo"]["attiva"]["n"] == 2


def test_detail_kept(s):
    keep, _ = ids()
    r = s.get(f"{API}/anagrafiche/{keep}")
    assert r.status_code == 200
    assert r.json()["riepilogo"]["attiva"] == {"n": 2, "totale": 150.5}


def test_detail_merged_report(s):
    _, dupe = ids()
    r = s.get(f"{API}/anagrafiche/{dupe}")
    print("merged detail:", r.status_code, r.text[:300])


def test_invoices_list(s):
    keep, _ = ids()
    r = s.get(f"{API}/invoices", params={"tipo": "attiva"})
    assert r.status_code == 200 and r.json()["total"] == 2
    assert {i["controparte_id"] for i in r.json()["items"]} == {keep}
    r2 = s.get(f"{API}/invoices", params={"anagrafica_id": keep})
    assert r2.json()["total"] == 2


# New upload updates kept record, no new duplicate
def test_upload_updates_kept(s):
    keep, _ = ids()
    r = s.post(f"{API}/invoices/upload", files=[("files", ("SM3.xml", xml("TEST-SM3"), "application/xml"))])
    assert r.status_code == 200, r.text
    res = r.json()["results"][0]
    assert res["status"] == "ok", res
    inv = s.get(f"{API}/invoices/{res['id']}").json()
    assert inv["controparte_id"] == keep
    rows = [a for a in s.get(f"{API}/anagrafiche", params={"ruolo": "cliente"}).json() if a["chiave"].startswith(DUP)]
    assert len(rows) == 1 and rows[0]["id"] == keep and rows[0]["n_fatture"] == 3
    assert s.get(f"{API}/stats").json()["n_clienti"] == 1
