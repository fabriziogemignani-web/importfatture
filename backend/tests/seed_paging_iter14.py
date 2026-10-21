"""Iteration 14 helper: seed TEST data for paging-reset UI test. Usage: python seed_paging_iter14.py [cleanup]"""
import sys
sys.path.insert(0, "/app/backend/tests")
from test_doc_type_filter_iter13 import login, make_xml, API, HA, seed, A, B  # noqa


def cleanup(s):
    for v in (A, B):
        for _ in range(10):
            items = s.get(f"{API}/invoices", params={"limit": 200}, headers={"X-Company-Vat": v}).json().get("items", [])
            if not items:
                break
            for i in items:
                s.delete(f"{API}/invoices/{i['id']}", headers={"X-Company-Vat": v})
        s.delete(f"{API}/companies/{v}")
    # remove leftover TEST anagrafiche, if endpoint exists
    for path in ("anagrafiche",):
        try:
            r = s.get(f"{API}/{path}", headers=HA)
            print(path, r.status_code, str(r.text)[:200])
        except Exception as e:
            print(path, e)


s = login()
if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
    cleanup(s)
    print("cleaned")
else:
    print([x["status"] for x in seed(s)])
    files = [("files", (f"IT01234567890_P{n}.xml", make_xml("TD01", str(100 + n), "2025-07-01", "10.00").encode())) for n in range(55)]
    files += [("files", (f"IT01234567890_N{n}.xml", make_xml("TD04", str(300 + n), "2025-08-01", "5.00").encode())) for n in range(4)]
    r = s.post(f"{API}/invoices/upload", files=files, headers=HA)
    print(r.status_code, sum(1 for x in r.json()["results"] if x["status"] == "ok"))
