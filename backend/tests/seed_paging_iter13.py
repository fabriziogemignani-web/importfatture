"""Iteration 13 helper: seed 55 extra TD01 attive 2025 invoices for paging-reset UI test (TEST data, P.IVA 01234567890)."""
import sys
sys.path.insert(0, "/app/backend/tests")
from test_doc_type_filter_iter13 import login, make_xml, API, HA, cleanup  # noqa

s = login()
if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
    cleanup(s)
    print("cleaned")
else:
    files = [("files", (f"IT01234567890_P{n}.xml", make_xml("TD01", str(100 + n), "2025-07-01", "10.00").encode())) for n in range(55)]
    r = s.post(f"{API}/invoices/upload", files=files, headers=HA)
    print(r.status_code, sum(1 for x in r.json()["results"] if x["status"] == "ok"))
