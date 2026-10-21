"""Measure backend process RSS while 4 concurrent 400MB-lying-size bomb uploads run (manual check, iter17)."""
import subprocess
import sys
import threading
import time

sys.path.insert(0, "/app/backend/tests")
import requests  # noqa: E402
from test_zip_stream_iter17 import API, ADMIN, bomb400  # noqa: E402


def rss():
    pids = subprocess.run(["pgrep", "-f", "uvicorn"], capture_output=True, text=True).stdout.split()
    tot = 0
    for p in pids:
        try:
            for line in open(f"/proc/{p}/status"):
                if line.startswith("VmRSS"):
                    tot = max(tot, int(line.split()[1]))
        except OSError:
            pass
    return tot / 1024


s = requests.Session()
s.headers["X-Requested-With"] = "XMLHttpRequest"
s.post(f"{API}/auth/login", json=ADMIN)
s.headers["X-Company-Vat"] = "01234567890"
created = s.post(f"{API}/companies", json={"company_vat": "01234567890", "company_name": "TEST_RSS"}).status_code == 200
z = bomb400()
base = rss()
peak = [base]
stop = threading.Event()


def mon():
    while not stop.is_set():
        peak[0] = max(peak[0], rss())
        time.sleep(0.05)


codes = []
m = threading.Thread(target=mon)
m.start()
ts = [threading.Thread(target=lambda: codes.append((lambda r: (r.status_code, r.text[:150]))(s.post(f"{API}/invoices/upload", files=[("files", ("bomb.zip", z, "application/zip"))], timeout=120)))) for _ in range(4)]
[t.start() for t in ts]
[t.join() for t in ts]
stop.set()
m.join()
print("codes", codes, "base RSS MB", round(base), "peak RSS MB", round(peak[0]), "me", s.get(f"{API}/auth/me").status_code)
from test_zip_stream_iter17 import mdb  # noqa: E402
mdb.invoices.delete_many({"company_vat": "01234567890"})
mdb.anagrafiche.delete_many({"company_vat": "01234567890"})
if created:
    print("company delete", s.delete(f"{API}/companies/01234567890").status_code)
