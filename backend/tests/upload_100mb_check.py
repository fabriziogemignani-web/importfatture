"""Iteration 15: per-file 100MB upload limit via public URL (101MB junk + 1 valid xml in same request)."""
import os
import sys
import time

import requests

sys.path.insert(0, "/app/backend/tests")
from test_security_iter15 import API, ADMIN, VAT, xml  # noqa: E402

s = requests.Session()
assert s.post(f"{API}/auth/login", json=ADMIN).status_code == 200
s.headers["X-Company-Vat"] = VAT
s.post(f"{API}/companies", json={"company_vat": VAT, "company_name": "TEST_Sec Co"})
big = b"a" * (101 * 1024 * 1024)
t = time.time()
r = s.post(f"{API}/invoices/upload", files=[("files", ("huge.xml", big)), ("files", ("TEST_small.xml", xml("TEST_100MB_OK")))], timeout=280)
print(r.status_code, round(time.time() - t, 1), r.text[:600])
print("me after:", s.get(f"{API}/auth/me").status_code)
