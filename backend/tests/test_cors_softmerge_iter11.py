"""Iter 11: CORS no-credentials-with-wildcard + soft-merge list/detail/delete cascade.
Requires `python soft_merge_repro.py seed` + backend restart beforehand (LOCAL DB)."""
import json
import os
import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = BASE + "/api"
VAT, DUP = "01192570453", "01428910457"
STATE = "/tmp/soft_merge_ids.json"
EVIL = "https://evil.example.com"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def ids():
    if not os.path.exists(STATE):
        pytest.skip("seed state missing")
    d = json.load(open(STATE))
    return sorted([d["a1"], d["a2"]])


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    r = ses.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
    assert r.status_code == 200, r.text
    ses.headers["X-Company-Vat"] = VAT
    return ses


# CORS: evil preflight must not get credentials
def test_cors_evil_preflight():
    r = requests.options(f"{API}/auth/login", headers={"Origin": EVIL, "Access-Control-Request-Method": "POST",
                                                        "Access-Control-Request-Headers": "content-type"})
    h = {k.lower(): v for k, v in r.headers.items()}
    print("evil preflight", r.status_code, h.get("access-control-allow-origin"), h.get("access-control-allow-credentials"))
    assert h.get("access-control-allow-credentials") != "true"
    assert h.get("access-control-allow-origin") != EVIL


# CORS: evil origin + cookie on /me must not get ACAO evil + creds
def test_cors_evil_me_with_cookie(s):
    cookies = "; ".join(f"{c.name}={c.value}" for c in s.cookies)
    r = requests.get(f"{API}/auth/me", headers={"Origin": EVIL, "Cookie": cookies})
    h = {k.lower(): v for k, v in r.headers.items()}
    print("evil /me", r.status_code, h.get("access-control-allow-origin"), h.get("access-control-allow-credentials"))
    assert r.status_code == 200
    # Starlette reflects origin for cookie-bearing requests when allow_all_origins, but without ACAC:true
    # browsers block reading credentialed responses -> safe. Must never be both.
    assert h.get("access-control-allow-credentials") != "true"


# Same-origin login still works with cookies
def test_login_cookies_same_origin():
    r = requests.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]},
                      headers={"Origin": BASE})
    assert r.status_code == 200
    sc = r.headers.get("set-cookie", "")
    assert "access_token" in sc and "HttpOnly" in sc
    me = requests.get(f"{API}/auth/me", cookies=r.cookies)
    assert me.status_code == 200 and me.json()["email"] == os.environ["ADMIN_EMAIL"]


# Soft-merge: list without ruolo returns only kept
def test_list_no_ruolo_only_kept(s):
    keep, dupe = ids()
    r = s.get(f"{API}/anagrafiche")
    assert r.status_code == 200
    got = [a["id"] for a in r.json()]
    assert got == [keep], got


def test_detail_merged_404(s):
    _, dupe = ids()
    r = s.get(f"{API}/anagrafiche/{dupe}")
    assert r.status_code == 404, r.text


def test_detail_kept_200(s):
    keep, _ = ids()
    r = s.get(f"{API}/anagrafiche/{keep}")
    assert r.status_code == 200
    assert r.json()["riepilogo"]["attiva"] == {"n": 2, "totale": 150.5}


# Delete all invoices of kept -> kept + merged sibling removed
def test_delete_cascade(s):
    keep, dupe = ids()
    items = s.get(f"{API}/invoices", params={"anagrafica_id": keep}).json()["items"]
    assert len(items) == 2
    r1 = s.delete(f"{API}/invoices/{items[0]['id']}")
    assert r1.status_code == 200
    assert s.get(f"{API}/anagrafiche/{keep}").status_code == 200
    assert db.anagrafiche.count_documents({"_id": ObjectId(dupe)}) == 1
    r2 = s.delete(f"{API}/invoices/{items[1]['id']}")
    assert r2.status_code == 200
    assert s.get(f"{API}/anagrafiche/{keep}").status_code == 404
    assert db.anagrafiche.count_documents({"company_vat": VAT}) == 0
    assert s.get(f"{API}/anagrafiche").json() == []
    assert s.get(f"{API}/stats").json()["n_clienti"] == 0
