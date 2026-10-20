# Seed/cleanup for dual-role anagrafica (cliente+fornitore) UI test. Usage: python seed_dual_role.py seed|cleanup
import os, sys, requests
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
VAT = "01234567890"
S = "/app/tests/samples/"

def login():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
    r.raise_for_status()
    s.headers["X-Company-Vat"] = VAT
    return s

def seed():
    s = login()
    print(s.post(f"{BASE}/companies", json={"company_vat": VAT, "company_name": "TEST_Dual Srl"}).json())
    base = open(S + "IT01234567890_00001.xml").read().replace("09876543210", "05555555555")
    a1 = base.replace("<Numero>10</Numero>", "<Numero>TEST-A1</Numero>")
    a2 = base.replace("<Numero>10</Numero>", "<Numero>TEST-A2</Numero>")
    files = [("files", ("A1.xml", a1.encode(), "application/xml")), ("files", ("A2.xml", a2.encode(), "application/xml")),
             ("files", ("IT05555555555_A0001.xml", open(S + "IT05555555555_A0001.xml", "rb").read(), "application/xml"))]
    print(s.post(f"{BASE}/invoices/upload", files=files).json())
    for a in s.get(f"{BASE}/anagrafiche").json():
        print(a["id"], a["denominazione"], a["ruoli"])

def cleanup():
    s = login()
    for inv in s.get(f"{BASE}/invoices", params={"limit": 200}).json()["items"]:
        s.delete(f"{BASE}/invoices/{inv['id']}")
    print(s.delete(f"{BASE}/companies/{VAT}").json())

{"seed": seed, "cleanup": cleanup}[sys.argv[1]]()
