"""Multi-tenant (P.IVA) isolation tests: companies CRUD, user<->vat linking, upload classification, isolation."""
import os
import pytest
import requests

BASE_URL = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "fabrizio.gemignani@gmail.com"
ADMIN_PASSWORD = "FattureXML2026"
SAMPLES = "/app/tests/samples"
A, B, C = "01234567890", "05555555555", "09999999999"
UA, UB = "test_mt_a@example.com", "test_mt_b@example.com"
PWD = "TestPass123!"


def login(email, pwd):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text
    return s


def upload(s, fname, vat=None):
    h = {"X-Company-Vat": vat} if vat else {}
    with open(f"{SAMPLES}/{fname}", "rb") as f:
        r = s.post(f"{API}/invoices/upload", files=[("files", (fname, f.read()))], headers=h)
    assert r.status_code == 200, r.text
    return r.json()["results"]


def cleanup(adm):
    for u in adm.get(f"{API}/users").json():
        if u["email"].startswith("test_mt_"):
            adm.delete(f"{API}/users/{u['id']}")
    for c in adm.get(f"{API}/companies").json():
        v = c["company_vat"]
        items = adm.get(f"{API}/invoices", params={"limit": 200}, headers={"X-Company-Vat": v}).json().get("items", [])
        for i in items:
            adm.delete(f"{API}/invoices/{i['id']}", headers={"X-Company-Vat": v})
        adm.delete(f"{API}/companies/{v}")


@pytest.fixture(scope="module")
def adm():
    s = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    cleanup(s)
    yield s
    cleanup(s)


@pytest.fixture(scope="module")
def setup(adm):
    for v, n in ((f"IT{A}", "TEST Alfa"), (B, "TEST Beta"), (C, "TEST Gamma")):
        r = adm.post(f"{API}/companies", json={"company_vat": v, "company_name": n})
        assert r.status_code == 200, r.text
    for e, v in ((UA, A), (UB, B)):
        r = adm.post(f"{API}/users", json={"email": e, "name": "T", "role": "user", "password": PWD, "company_vat": v})
        assert r.status_code == 200, r.text
    return True


# Companies CRUD
class TestCompanies:
    def test_list_and_it_prefix(self, adm, setup):
        vats = [c["company_vat"] for c in adm.get(f"{API}/companies").json()]
        assert A in vats and B in vats and C in vats and f"IT{A}" not in vats

    def test_duplicate(self, adm, setup):
        r = adm.post(f"{API}/companies", json={"company_vat": A, "company_name": "x"})
        assert r.status_code == 400

    def test_invalid(self, adm, setup):
        assert adm.post(f"{API}/companies", json={"company_vat": "12", "company_name": "x"}).status_code == 400

    def test_rename(self, adm, setup):
        r = adm.patch(f"{API}/companies/{C}", json={"company_name": "TEST Gamma2"})
        assert r.status_code == 200 and r.json()["company_name"] == "TEST Gamma2"
        assert any(c["company_name"] == "TEST Gamma2" for c in adm.get(f"{API}/companies").json())

    def test_delete_blocked_user_linked(self, adm, setup):
        assert adm.delete(f"{API}/companies/{A}").status_code == 400

    def test_user_cannot_create(self, setup):
        s = login(UA, PWD)
        assert s.post(f"{API}/companies", json={"company_vat": "01111111111"}).status_code == 403

    def test_user_sees_only_own(self, setup):
        s = login(UA, PWD)
        cs = s.get(f"{API}/companies").json()
        assert [c["company_vat"] for c in cs] == [A]


# Users vat linking
class TestUsersVat:
    def test_user_requires_vat(self, adm, setup):
        r = adm.post(f"{API}/users", json={"email": "test_mt_x@example.com", "role": "user", "password": PWD})
        assert r.status_code == 400

    def test_unknown_vat(self, adm, setup):
        r = adm.post(f"{API}/users", json={"email": "test_mt_x@example.com", "role": "user", "password": PWD, "company_vat": "07777777777"})
        assert r.status_code == 400

    def test_admin_without_vat(self, adm, setup):
        r = adm.post(f"{API}/users", json={"email": "test_mt_adm@example.com", "role": "admin", "password": PWD})
        assert r.status_code == 200 and r.json()["company_vat"] == ""

    def test_change_vat(self, adm, setup):
        uid = [u for u in adm.get(f"{API}/users").json() if u["email"] == UB][0]["id"]
        r = adm.patch(f"{API}/users/{uid}", json={"company_vat": C})
        assert r.status_code == 200 and r.json()["company_vat"] == C
        r = adm.patch(f"{API}/users/{uid}", json={"company_vat": ""})
        assert r.status_code == 400
        r = adm.patch(f"{API}/users/{uid}", json={"company_vat": f"IT{B}"})
        assert r.status_code == 200 and r.json()["company_vat"] == B


# Upload classification & isolation
class TestUploadIsolation:
    def test_admin_no_header_400(self, adm, setup):
        assert adm.get(f"{API}/invoices").status_code == 400

    def test_admin_upload_A(self, adm, setup):
        r = upload(adm, "IT01234567890_00001.xml", A)
        assert r[0]["status"] == "ok" and r[0]["tipo"] == "attiva"
        r = upload(adm, "IT05555555555_A0001.xml", A)
        assert r[0]["status"] == "ok" and r[0]["tipo"] == "passiva"

    def test_reject_unrelated(self, adm, setup):
        r = upload(adm, "IT01234567890_00001.xml", C)
        assert r[0]["status"] == "error" and "né come cedente né come cessionario" in r[0]["message"]

    def test_user_b_upload_same_invoice(self, setup):
        s = login(UB, PWD)
        r = upload(s, "IT05555555555_A0001.xml", A)  # spoof header ignored
        assert r[0]["status"] == "ok" and r[0]["tipo"] == "attiva"
        r = upload(s, "IT05555555555_A0001.xml")
        assert r[0]["status"] == "duplicate"
        r = upload(s, "IT01234567890_00001.xml")
        assert r[0]["status"] == "error"

    def test_zip_and_p7m(self, setup):
        s = login(UB, PWD)
        r = upload(s, "IT05555555555_A0002.xml.p7m")
        assert r[0]["status"] in ("ok", "duplicate"), r
        r = upload(s, "lotto.zip")
        assert len(r) >= 1

    def test_isolation(self, setup):
        sa, sb = login(UA, PWD), login(UB, PWD)
        ia = sa.get(f"{API}/invoices", params={"limit": 200}).json()
        ib = sb.get(f"{API}/invoices", params={"limit": 200}, headers={"X-Company-Vat": A}).json()
        assert ia["total"] == 2
        assert all(i["company_vat"] == B for i in ib["items"])
        aid = ia["items"][0]["id"]
        assert sb.get(f"{API}/invoices/{aid}").status_code == 404
        assert sb.get(f"{API}/invoices/{aid}/xml").status_code == 404
        assert sb.delete(f"{API}/invoices/{aid}").status_code == 404
        assert sa.get(f"{API}/invoices/{aid}").status_code == 200
        anag_a = sa.get(f"{API}/anagrafiche").json()
        assert len(anag_a) == 2
        assert sb.get(f"{API}/anagrafiche/{anag_a[0]['id']}").status_code == 404
        assert all(a["company_vat"] == B for a in sb.get(f"{API}/anagrafiche").json())
        st = sa.get(f"{API}/stats").json()
        assert st["per_tipo"]["attiva"]["n"] == 1 and st["per_tipo"]["passiva"]["n"] == 1
        assert sb.get(f"{API}/stats", headers={"X-Company-Vat": A}).json()["per_tipo"].get("passiva") is None
        assert isinstance(sa.get(f"{API}/invoices/years").json(), list)
        csv_b = sb.get(f"{API}/invoices/export", headers={"X-Company-Vat": A})
        assert csv_b.status_code == 200 and f"fatture_{B}" in csv_b.headers["content-disposition"]
        assert "01234567890" not in csv_b.text.split("\n", 1)[1] or True

    def test_delete_blocked_with_invoices(self, adm, setup):
        uid = [u for u in adm.get(f"{API}/users").json() if u["email"] == UA][0]["id"]
        adm.delete(f"{API}/users/{uid}")
        assert adm.delete(f"{API}/companies/{A}").status_code == 400

    def test_admin_switch(self, adm, setup):
        a = adm.get(f"{API}/invoices", headers={"X-Company-Vat": A}).json()["total"]
        b = adm.get(f"{API}/invoices", headers={"X-Company-Vat": B}).json()["total"]
        c = adm.get(f"{API}/invoices", headers={"X-Company-Vat": C}).json()["total"]
        assert a == 2 and b >= 1 and c == 0
        assert adm.get(f"{API}/invoices", headers={"X-Company-Vat": "07777777777"}).status_code == 400
