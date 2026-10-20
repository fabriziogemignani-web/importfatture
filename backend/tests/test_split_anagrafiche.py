"""Split anagrafiche per ruolo: a counterpart that is both cliente and fornitore has 2 separate records."""
import os
import csv
import io
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
SAMPLES = "/app/tests/samples"
VAT, OTHER, CP = "01234567890", "07777777777", "05555555555"


def attiva(numero, totale_line=None):
    x = open(f"{SAMPLES}/IT01234567890_00001.xml").read().replace("09876543210", CP)
    return x.replace("<Numero>10</Numero>", f"<Numero>{numero}</Numero>").encode()


def up(s, files, vat=VAT):
    r = s.post(f"{API}/invoices/upload", files=[("files", f) for f in files], headers={"X-Company-Vat": vat})
    assert r.status_code == 200, r.text
    return r.json()["results"]


def cleanup(s):
    for v in (VAT, OTHER):
        h = {"X-Company-Vat": v}
        r = s.get(f"{API}/invoices", params={"limit": 200}, headers=h)
        if r.status_code == 200:
            for i in r.json()["items"]:
                s.delete(f"{API}/invoices/{i['id']}", headers=h)
        s.delete(f"{API}/companies/{v}")


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    r = ses.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
    assert r.status_code == 200
    cleanup(ses)
    for v, n in ((VAT, "TEST_Split Srl"), (OTHER, "TEST_Other Srl")):
        assert ses.post(f"{API}/companies", json={"company_vat": v, "company_name": n}).status_code in (200, 201)
    ses.headers["X-Company-Vat"] = VAT
    res = up(ses, [("A1.xml", attiva("TEST-A1"), "application/xml"),
                   ("IT05555555555_A0001.xml", open(f"{SAMPLES}/IT05555555555_A0001.xml", "rb").read(), "application/xml")])
    assert [r["status"] for r in res] == ["ok", "ok"], res
    assert {r["tipo"] for r in res} == {"attiva", "passiva"}
    yield ses
    cleanup(ses)


def recs(s):
    return [a for a in s.get(f"{API}/anagrafiche").json() if a.get("chiave") == CP]


def by_role(s, ruolo):
    r = s.get(f"{API}/anagrafiche", params={"ruolo": ruolo})
    assert r.status_code == 200
    return [a for a in r.json() if a.get("chiave") == CP]


class TestSplit:
    def test_two_distinct_records(self, s):
        rs = recs(s)
        assert len(rs) == 2, rs
        assert rs[0]["id"] != rs[1]["id"]
        assert sorted(a["ruolo"] for a in rs) == ["cliente", "fornitore"]
        for a in rs:
            assert a["ruoli"] == [a["ruolo"]]

    def test_role_lists(self, s):
        c, f = by_role(s, "cliente"), by_role(s, "fornitore")
        assert len(c) == 1 and len(f) == 1
        assert c[0]["id"] != f[0]["id"]
        assert c[0]["n_fatture"] == 1 and f[0]["n_fatture"] == 1

    def test_detail_riepilogo_only_own_tipo(self, s):
        c, f = by_role(s, "cliente")[0], by_role(s, "fornitore")[0]
        dc = s.get(f"{API}/anagrafiche/{c['id']}").json()
        df = s.get(f"{API}/anagrafiche/{f['id']}").json()
        assert dc["ruolo"] == "cliente" and list(dc["riepilogo"].keys()) == ["attiva"]
        assert df["ruolo"] == "fornitore" and list(df["riepilogo"].keys()) == ["passiva"]
        ic = s.get(f"{API}/invoices", params={"anagrafica_id": c["id"], "limit": 200}).json()["items"]
        ip = s.get(f"{API}/invoices", params={"anagrafica_id": f["id"], "limit": 200}).json()["items"]
        assert ic and all(i["tipo"] == "attiva" for i in ic)
        assert ip and all(i["tipo"] == "passiva" for i in ip)

    def test_more_uploads_no_duplicate_records(self, s):
        c0, f0 = by_role(s, "cliente")[0]["id"], by_role(s, "fornitore")[0]["id"]
        res = up(s, [("A2.xml", attiva("TEST-A2"), "application/xml"),
                     ("A3.xml", attiva("TEST-A3"), "application/xml")])
        assert all(r["status"] == "ok" for r in res), res
        # p7m passive from the same supplier
        res2 = up(s, [("IT05555555555_A0002.xml.p7m", open(f"{SAMPLES}/IT05555555555_A0002.xml.p7m", "rb").read(), "application/octet-stream")])
        print("p7m:", res2)
        rs = recs(s)
        assert len(rs) == 2
        c, f = by_role(s, "cliente")[0], by_role(s, "fornitore")[0]
        assert c["id"] == c0 and f["id"] == f0
        assert c["n_fatture"] == 3
        if res2 and res2[0]["status"] == "ok" and res2[0].get("tipo") == "passiva":
            assert f["n_fatture"] == 2

    def test_invoice_controparte_ids(self, s):
        c, f = by_role(s, "cliente")[0], by_role(s, "fornitore")[0]
        for i in s.get(f"{API}/invoices", params={"limit": 200}).json()["items"]:
            if i["controparte_piva"] == CP:
                assert i["controparte_id"] == (c["id"] if i["tipo"] == "attiva" else f["id"])

    def test_stats_counts(self, s):
        st = s.get(f"{API}/stats").json()
        assert st["n_clienti"] == 1 and st["n_fornitori"] == 1, st

    def test_csv_export_card(self, s):
        c, f = by_role(s, "cliente")[0], by_role(s, "fornitore")[0]
        for a, tipo in ((c, "attiva"), (f, "passiva")):
            r = s.get(f"{API}/invoices/export", params={"anagrafica_id": a["id"], "tipo": tipo})
            assert r.status_code == 200
            rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))[1:]
            assert rows and all(x[0] == tipo for x in rows)
            assert len(rows) == a["n_fatture"]
            # without tipo, export by id still only has that card's invoices
            r2 = s.get(f"{API}/invoices/export", params={"anagrafica_id": a["id"]})
            rows2 = list(csv.reader(io.StringIO(r2.content.decode("utf-8-sig")), delimiter=";"))[1:]
            assert all(x[0] == tipo for x in rows2)

    def test_isolation(self, s):
        c = by_role(s, "cliente")[0]
        h = {"X-Company-Vat": OTHER}
        assert s.get(f"{API}/anagrafiche", headers=h).json() == []
        assert s.get(f"{API}/anagrafiche/{c['id']}", headers=h).status_code == 404
        st = s.get(f"{API}/stats", headers=h).json()
        assert st["n_clienti"] == 0 and st["n_fornitori"] == 0

    def test_unique_index_exists(self):
        from pymongo import MongoClient
        db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        idx = db.anagrafiche.index_information()
        keys = [v["key"] for v in idx.values() if v.get("unique")]
        assert [("company_vat", 1), ("ruolo", 1), ("chiave", 1)] in keys, idx
