"""Seed/cleanup helper for multi-P.IVA UI tests. Usage: python seed_multivat_ui.py seed|clean"""
import sys
import requests

with open("/app/frontend/.env") as f:
    BASE = [l.split("=", 1)[1].strip() for l in f if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = f"{BASE}/api"
S = "/app/tests/samples"
A, B, C = "01234567890", "05555555555", "09999999999"
PWD = "TestPass123!"


def adm():
    s = requests.Session()
    assert s.post(f"{API}/auth/login", json={"email": "fabrizio.gemignani@gmail.com", "password": "FattureXML2026"}).status_code == 200
    return s


def up(s, fn, vat):
    with open(f"{S}/{fn}", "rb") as f:
        return s.post(f"{API}/invoices/upload", files=[("files", (fn, f.read()))], headers={"X-Company-Vat": vat}).json()


def clean(s):
    for u in s.get(f"{API}/users").json():
        if u["email"].startswith("test_"):
            s.delete(f"{API}/users/{u['id']}")
    for c in s.get(f"{API}/companies").json():
        v = c["company_vat"]
        for i in s.get(f"{API}/invoices", params={"limit": 200}, headers={"X-Company-Vat": v}).json().get("items", []):
            s.delete(f"{API}/invoices/{i['id']}", headers={"X-Company-Vat": v})
        print("del company", v, s.delete(f"{API}/companies/{v}").status_code)


if __name__ == "__main__":
    s = adm()
    clean(s)
    if sys.argv[1] == "seed":
        for v, n in ((A, "TEST Alfa"), (B, "TEST Beta"), (C, "TEST Gamma")):
            s.post(f"{API}/companies", json={"company_vat": v, "company_name": n})
        print(s.post(f"{API}/users", json={"email": "test_multi@example.com", "name": "Multi", "role": "user", "password": PWD, "company_vats": [A, B]}).status_code)
        print(s.post(f"{API}/users", json={"email": "test_single@example.com", "name": "Single", "role": "user", "password": PWD, "company_vats": [C]}).status_code)
        print(up(s, "IT01234567890_00001.xml", A))
        print(up(s, "IT05555555555_A0001.xml", A))
        print(up(s, "IT05555555555_A0001.xml", B))
