"""Iteration 19: Dichiarazioni d'intento + plafond (CRUD, normalization, usage, anomalies, riepilogo, PDF, isolation).
Uses its own TEST company 09999999002 (created+deleted here). Reads (never modifies) the main agent's 09999999001 data."""
import os

import pytest
import requests

with open("/app/frontend/.env") as f:
    BASE_URL = [l.split("=", 1)[1].strip().rstrip("/") for l in f if l.startswith("REACT_APP_BACKEND_URL=")][0]
API = f"{BASE_URL}/api"
ADMIN = {"email": "fabrizio.gemignani@gmail.com", "password": "FattureXML2026"}
VAT1 = "09999999001"
VAT2 = "09999999002"
CLI = "09999999777"
P1 = "26010300000000001-000001"
P2 = "26010300000000002-000002"


def sess(vat):
    s = requests.Session()
    s.headers["X-Requested-With"] = "XMLHttpRequest"
    assert s.post(f"{API}/auth/login", json=ADMIN).status_code == 200
    s.headers["X-Company-Vat"] = vat
    return s


def xml(num, data, amount, prot=None, rdata="2026-02-01", natura="N3.5", ces=CLI, td="TD01"):
    adg = (f"<AltriDatiGestionali><TipoDato>INTENTO</TipoDato><RiferimentoTesto>{prot}</RiferimentoTesto>"
           f"<RiferimentoData>{rdata}</RiferimentoData></AltriDatiGestionali>") if prot else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica versione="FPR12" xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"><FatturaElettronicaHeader>
<CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{VAT2}</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>TEST_Ced</Denominazione></Anagrafica></DatiAnagrafici></CedentePrestatore>
<CessionarioCommittente><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{ces}</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>TEST_Ces_{ces}</Denominazione></Anagrafica></DatiAnagrafici></CessionarioCommittente>
</FatturaElettronicaHeader><FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento><TipoDocumento>{td}</TipoDocumento><Divisa>EUR</Divisa><Data>{data}</Data><Numero>{num}</Numero><ImportoTotaleDocumento>{amount}</ImportoTotaleDocumento></DatiGeneraliDocumento></DatiGenerali>
<DatiBeniServizi><DettaglioLinee><NumeroLinea>1</NumeroLinea><Descrizione>x</Descrizione><PrezzoUnitario>{amount}</PrezzoUnitario><PrezzoTotale>{amount}</PrezzoTotale><AliquotaIVA>0.00</AliquotaIVA><Natura>{natura}</Natura>{adg}</DettaglioLinee>
<DatiRiepilogo><AliquotaIVA>0.00</AliquotaIVA><Natura>{natura}</Natura><ImponibileImporto>{amount}</ImponibileImporto><Imposta>0.00</Imposta></DatiRiepilogo></DatiBeniServizi></FatturaElettronicaBody></p:FatturaElettronica>""".encode()


INVOICES = [
    ("A1", "2026-03-01", "5000.00", dict(prot=P1)),                       # ok
    ("A2", "2026-01-15", "100.00", dict(prot=P1)),                        # fuori_periodo (before ricevuta)
    ("A3", "2025-12-01", "100.00", dict(prot=P1)),                        # fuori_periodo (other year)
    ("A4", "2026-10-01", "100.00", dict(prot=P1)),                        # revocata
    ("A5", "2026-04-01", "100.00", dict(prot=P1, rdata="2026-02-05")),    # data_diversa
    ("A6", "2026-04-02", "100.00", dict(prot=P1, natura="N3.1")),         # natura_errata
    ("A7", "2026-04-03", "100.00", dict(prot=P1, ces="09999999888")),     # cliente_diverso
    ("A8", "2026-04-04", "100.00", dict(prot="26010399999999999-000009")),  # non_registrata
    ("A9", "2026-04-05", "100.00", dict(prot="ABC123")),                  # protocollo_non_valido
    ("A10", "2026-04-06", "100.00", dict()),                              # senza_protocollo
    ("B1", "2026-03-01", "800.00", dict(prot=P2, rdata="2026-02-01")),    # D2 80% -> attenzione
]


@pytest.fixture(scope="module")
def st():
    s = sess(VAT2)
    created_company = s.post(f"{API}/companies", json={"company_vat": VAT2, "company_name": "TEST_Intento2"}).status_code == 200
    state = {"s": s, "inv": [], "dich": [], "company": created_company}
    r = s.post(f"{API}/invoices/upload", files=[("files", (f"TEST_{n}.xml", xml(n, d, a, **kw), "text/xml")) for n, d, a, kw in INVOICES])
    assert r.status_code == 200, r.text
    res = r.json()["results"]
    state["inv"] = [x["id"] for x in res if x.get("id")]
    assert all(x.get("status") == "ok" for x in res), res
    yield state
    for d in state["dich"]:
        s.delete(f"{API}/dichiarazioni/{d}")
    for i in state["inv"]:
        s.delete(f"{API}/invoices/{i}")
    if created_company:
        print("company delete", s.delete(f"{API}/companies/{VAT2}").status_code)


def body(**kw):
    b = {"cliente_piva": CLI, "cliente_nome": "TEST_Ces", "protocollo": P1, "data": "2026-02-01", "anno": 2026, "plafond": 10000}
    b.update(kw)
    return b


# --- CRUD + validation
class TestCrud:
    def test_create_normalize_23digits(self, st):
        s = st["s"]
        r = s.post(f"{API}/dichiarazioni", json=body(protocollo=P1.replace("-", ""), data_revoca="2026-09-01", cliente_piva="IT 09999999777"))
        assert r.status_code == 200, r.text
        d = r.json()
        st["dich"].append(d["id"])
        assert d["protocollo"] == P1 and d["cliente_piva"] == CLI and "_id" not in d and "company_vat" not in d
        r = s.post(f"{API}/dichiarazioni", json=body(protocollo=P2.replace("-", "/"), plafond=1000, note="TEST_d2"))
        assert r.status_code == 200, r.text
        assert r.json()["protocollo"] == P2
        st["dich"].append(r.json()["id"])

    def test_duplicate_and_invalid(self, st):
        s = st["s"]
        assert s.post(f"{API}/dichiarazioni", json=body(protocollo=P1.replace("-", "/"))).status_code == 400
        assert s.post(f"{API}/dichiarazioni", json=body(protocollo="1234-56")).status_code == 400
        assert s.post(f"{API}/dichiarazioni", json=body(protocollo="26010300000000009-000001", plafond=0)).status_code == 422
        assert s.post(f"{API}/dichiarazioni", json=body(protocollo="26010300000000009-000001", plafond=-5)).status_code == 422
        r = s.post(f"{API}/dichiarazioni", json=body(protocollo="26010300000000009-000001", data_revoca="2026-01-01"))
        assert r.status_code == 400

    def test_no_csrf_header_rejected(self, st):
        s2 = requests.Session()
        s2.cookies.update(st["s"].cookies)
        s2.headers.pop("X-Requested-With", None)  # conftest adds it by default
        r = s2.post(f"{API}/dichiarazioni", json=body(protocollo="26010300000000009-000001"), headers={"X-Company-Vat": VAT2})
        if r.status_code == 200:
            st["dich"].append(r.json()["id"])
        assert r.status_code == 403


# --- usage + anomalies
class TestUsage:
    def test_list_usage_levels(self, st):
        r = st["s"].get(f"{API}/dichiarazioni", params={"anno": 2026})
        assert r.status_code == 200
        j = r.json()
        by = {d["protocollo"]: d for d in j["dichiarazioni"]}
        d1, d2 = by[P1], by[P2]
        print("D1", {k: d1[k] for k in ("utilizzato", "residuo", "percentuale", "livello", "n_fatture")})
        print("D2", {k: d2[k] for k in ("utilizzato", "residuo", "percentuale", "livello", "n_fatture")})
        assert "fatture" not in d1
        assert d2["utilizzato"] == 800 and d2["percentuale"] == 80.0 and d2["livello"] == "attenzione"
        assert d1["livello"] == "ok"
        codes = sorted(a["codice"] for a in j["anomalie"])
        print("codes", codes)
        for c in ("senza_protocollo", "non_registrata", "protocollo_non_valido", "cliente_diverso", "fuori_periodo",
                  "revocata", "data_diversa", "natura_errata"):
            assert c in codes, c
        # 2025 invoice anomaly filtered out of 2026
        assert not any(a["numero"] == "A3" for a in j["anomalie"])
        j25 = st["s"].get(f"{API}/dichiarazioni", params={"anno": 2025}).json()
        assert any(a["numero"] == "A3" and a["codice"] == "fuori_periodo" for a in j25["anomalie"])

    def test_detail_progressivo(self, st):
        r = st["s"].get(f"{API}/dichiarazioni/{st['dich'][0]}")
        assert r.status_code == 200
        d = r.json()
        prog = [(f["numero"], f["importo"], f["progressivo"]) for f in d["fatture"]]
        print("prog", prog)
        assert d["fatture"][-1]["progressivo"] == d["utilizzato"]
        assert st["s"].get(f"{API}/dichiarazioni/000000000000000000000000").status_code == 404
        assert st["s"].get(f"{API}/dichiarazioni/bad").status_code == 404

    def test_update_plafond_superato(self, st):
        s = st["s"]
        did = st["dich"][1]
        r = s.put(f"{API}/dichiarazioni/{did}", json=body(protocollo=P2, plafond=500))
        assert r.status_code == 200 and r.json()["plafond"] == 500
        j = s.get(f"{API}/dichiarazioni", params={"anno": 2026}).json()
        d2 = next(d for d in j["dichiarazioni"] if d["id"] == did)
        assert d2["livello"] == "superato" and d2["residuo"] == -300
        assert any(a["codice"] == "plafond_superato" and a["numero"] == "B1" for a in j["anomalie"])
        rr = s.get(f"{API}/dichiarazioni/riepilogo").json()
        print("riepilogo", rr)
        assert rr["superate"] >= 1 and rr["anomalie"] >= 9
        # PUT to existing protocol of other decl -> 400
        assert s.put(f"{API}/dichiarazioni/{did}", json=body(protocollo=P1)).status_code == 400
        assert s.put(f"{API}/dichiarazioni/{did}", json=body(protocollo="xx")).status_code == 400

    def test_vat1_seed_td04(self):
        s = sess(VAT1)
        j = s.get(f"{API}/dichiarazioni", params={"anno": 2026}).json()
        d = next(x for x in j["dichiarazioni"] if x["protocollo"] == "26010312345678901-000001")
        assert d["utilizzato"] == 11000 and d["livello"] == "superato"
        assert sorted(a["codice"] for a in j["anomalie"]) == ["plafond_superato", "senza_protocollo"]


# --- PDF attachments
class TestFiles:
    def test_pdf_flow(self, st):
        s, did = st["s"], st["dich"][0]
        pdf = b"%PDF-1.4\n%TEST\n"
        r = s.post(f"{API}/dichiarazioni/{did}/files/dichiarazione", files={"file": ("TEST d/ich.pdf", pdf, "application/pdf")})
        assert r.status_code == 200, r.text
        assert s.get(f"{API}/dichiarazioni/{did}").json()["files"].get("dichiarazione")
        g = s.get(f"{API}/dichiarazioni/{did}/files/dichiarazione")
        assert g.status_code == 200 and g.content == pdf and g.headers["content-type"] == "application/pdf"
        assert s.post(f"{API}/dichiarazioni/{did}/files/ricevuta", files={"file": ("x.pdf", b"NOTPDF", "application/pdf")}).status_code == 400
        big = b"%PDF" + b"0" * (5 * 1024 * 1024)
        assert s.post(f"{API}/dichiarazioni/{did}/files/ricevuta", files={"file": ("x.pdf", big, "application/pdf")}).status_code == 400
        assert s.post(f"{API}/dichiarazioni/{did}/files/altro", files={"file": ("x.pdf", pdf, "application/pdf")}).status_code == 404
        assert s.get(f"{API}/dichiarazioni/{did}/files/ricevuta").status_code == 404
        # isolation on file
        assert sess(VAT1).get(f"{API}/dichiarazioni/{did}/files/dichiarazione").status_code == 404
        assert s.delete(f"{API}/dichiarazioni/{did}/files/dichiarazione").status_code == 200
        assert s.get(f"{API}/dichiarazioni/{did}/files/dichiarazione").status_code == 404
        assert not s.get(f"{API}/dichiarazioni/{did}").json()["files"].get("dichiarazione")


# --- tenant isolation + delete
class TestIsolationDelete:
    def test_isolation(self, st):
        o = sess(VAT1)
        did = st["dich"][0]
        assert o.get(f"{API}/dichiarazioni/{did}").status_code == 404
        assert o.put(f"{API}/dichiarazioni/{did}", json=body()).status_code == 404
        assert o.delete(f"{API}/dichiarazioni/{did}").status_code == 404
        assert all(d["id"] != did for d in o.get(f"{API}/dichiarazioni").json()["dichiarazioni"])
        # same protocol allowed in other tenant? (unique per company) - check without creating in VAT1
        assert st["s"].get(f"{API}/dichiarazioni/{did}").status_code == 200

    def test_delete(self, st):
        s = st["s"]
        did = st["dich"].pop()
        assert s.delete(f"{API}/dichiarazioni/{did}").status_code == 200
        assert s.get(f"{API}/dichiarazioni/{did}").status_code == 404
        j = s.get(f"{API}/dichiarazioni", params={"anno": 2026}).json()
        assert any(a["codice"] == "non_registrata" and a["numero"] == "B1" for a in j["anomalie"])
