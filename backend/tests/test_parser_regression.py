"""Regression tests for fattura_parser refactor (unit) + upload API end-to-end (xml, p7m, zip nested, errors)."""
import io
import os
import sys
import zipfile

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
from fattura_parser import extract_xml_files, parse_fattura, natural_key  # noqa: E402

load_dotenv("/app/backend/.env")
BASE_URL = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
S = "/app/tests/samples"
VAT = "01234567890"


def rd(n):
    with open(f"{S}/{n}", "rb") as f:
        return f.read()


def build_xml(bodies, ced_name="<Denominazione>TEST_X</Denominazione>"):
    b = "".join(bodies)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"><FatturaElettronicaHeader>
<DatiTrasmissione><CodiceDestinatario>0000000</CodiceDestinatario><PECDestinatario>a@pec.it</PECDestinatario></DatiTrasmissione>
<CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{VAT}</IdCodice></IdFiscaleIVA><Anagrafica>{ced_name}</Anagrafica></DatiAnagrafici></CedentePrestatore>
<CessionarioCommittente><DatiAnagrafici><CodiceFiscale>RSSMRA80A01H501U</CodiceFiscale><Anagrafica><Nome>Mario</Nome><Cognome>Rossi</Cognome></Anagrafica></DatiAnagrafici></CessionarioCommittente>
</FatturaElettronicaHeader>{b}</p:FatturaElettronica>""".encode()


def body(num, data, riep, total=None):
    t = f"<ImportoTotaleDocumento>{total}</ImportoTotaleDocumento>" if total else ""
    r = "".join(f"<DatiRiepilogo><AliquotaIVA>{a}</AliquotaIVA><ImponibileImporto>{i}</ImponibileImporto><Imposta>{p}</Imposta></DatiRiepilogo>" for a, i, p in riep)
    return f"<FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento><TipoDocumento>TD01</TipoDocumento><Data>{data}</Data><Numero>{num}</Numero>{t}<Causale>A</Causale><Causale>B</Causale></DatiGeneraliDocumento></DatiGenerali><DatiBeniServizi>{r}</DatiBeniServizi></FatturaElettronicaBody>"


# ---- Unit: parser ----
class TestParserUnit:
    def test_sample_xml_fields(self):
        invs, raw = parse_fattura(rd("IT01234567890_00001.xml"))
        assert len(invs) == 1 and "FatturaElettronica" in raw
        i = invs[0]
        assert i["numero"] == "10" and i["data"] == "2025-03-15" and i["anno"] == 2025
        assert i["tipo_documento"] == "TD01" and i["divisa"] == "EUR"
        assert i["imponibile"] == 1000.0 and i["imposta"] == 220.0 and i["totale"] == 1220.0
        assert i["causale"] == "Consulenza informatica marzo"
        assert i["righe"][0] == {"numero_linea": "1", "descrizione": "Consulenza sviluppo software", "quantita": "10.00",
                                 "unita_misura": "ore", "prezzo_unitario": 100.0, "prezzo_totale": 1000.0, "aliquota_iva": 22.0, "natura": ""}
        assert i["riepilogo"][0]["esigibilita"] == "I" and i["riepilogo"][0]["aliquota_iva"] == 22.0
        p = i["pagamenti"][0]
        assert p["condizioni"] == "TP02" and p["modalita"] == "MP05" and p["scadenza"] == "2025-04-15"
        assert p["importo"] == 1220.0 and p["iban"] == "IT60X0542811101000000123456"
        assert i["cedente"]["piva"] == VAT and i["cedente"]["denominazione"] == "TEST_Mia Azienda Srl"
        assert i["cedente"]["indirizzo"] == "Via Roma 1" and i["cedente"]["comune"] == "Milano" and "telefono" in i["cedente"]
        assert i["cessionario"]["piva"] == "09876543210" and i["cessionario"]["codice_destinatario"] == "ABC1234"
        assert i["trasmissione"]["progressivo_invio"] == "00001"
        assert i["numero_key"] == natural_key("10")

    def test_multi_body_bom_nome_cognome_no_total(self):
        x = b"\xef\xbb\xbf" + build_xml([body("A/1", "2024-01-02", [(22, 100, 22), (10, 50, 5)]), body("A/2", "2024-02-02", [(22, 10, 2.2)], "99.00")])
        invs, _ = parse_fattura(x)
        assert len(invs) == 2
        assert invs[0]["imponibile"] == 150.0 and invs[0]["imposta"] == 27.0 and invs[0]["totale"] == 177.0
        assert invs[1]["totale"] == 99.0 and invs[0]["causale"] == "A B"
        assert invs[0]["cessionario"]["denominazione"] == "Mario Rossi"
        assert invs[0]["cessionario"]["pec"] == "a@pec.it" and invs[0]["pagamenti"] == [] and invs[0]["righe"] == []

    @pytest.mark.parametrize("data,msg", [
        (b"<not xml", "XML non valido"),
        (b"<root/>", "non è una FatturaElettronica"),
        (b"<FatturaElettronica/>", "Header"),
    ])
    def test_errors(self, data, msg):
        with pytest.raises(ValueError, match=msg):
            parse_fattura(data)

    def test_no_body_and_missing_numero(self):
        with pytest.raises(ValueError, match="Nessun corpo"):
            parse_fattura(build_xml([]))
        with pytest.raises(ValueError, match="Numero o data"):
            parse_fattura(build_xml([body("", "2024-01-01", [])]))

    def test_p7m_decoding(self):
        out = list(extract_xml_files("x.xml.p7m", rd("IT05555555555_A0002.xml.p7m")))
        assert out[0][2] is None and parse_fattura(out[0][1])[0][0]["numero"]
        bad = list(extract_xml_files("bad.p7m", b"garbage"))
        assert bad[0][1] is None and "p7m" in bad[0][2]

    def test_zip_nested_hidden_and_bad(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            z.writestr("deep/a.xml", rd("IT01234567890_00001.xml"))
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as z:
            z.writestr("sub/inner.zip", inner.getvalue())
            z.writestr("b.xml.p7m", rd("IT05555555555_A0002.xml.p7m"))
            z.writestr("__MACOSX/._a.xml", b"junk")
            z.writestr("sub/.hidden.xml", b"junk")
            z.writestr("readme.txt", b"x")
        names = [n for n, _, e in extract_xml_files("o.zip", outer.getvalue()) if e is None]
        assert sorted(names) == ["o.zip/b.xml.p7m", "o.zip/sub/inner.zip/deep/a.xml"]
        assert list(extract_xml_files("bad.zip", b"nope"))[0][2] == "Archivio ZIP non valido"
        assert "Formato non supportato" in list(extract_xml_files("a.pdf", b""))[0][2]

    def test_sample_lotto_zip(self):
        res = list(extract_xml_files("lotto.zip", rd("lotto.zip")))
        assert len(res) == 3 and all(e is None for _, _, e in res)


# ---- API: upload end-to-end ----
@pytest.fixture(scope="module")
def adm():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
    assert r.status_code == 200
    s.post(f"{API}/companies", json={"company_vat": VAT, "company_name": "TEST_Parser Co"})
    s.headers["X-Company-Vat"] = VAT
    yield s
    for inv in s.get(f"{API}/invoices", params={"limit": 200}).json().get("items", []):
        s.delete(f"{API}/invoices/{inv['id']}")
    s.headers.pop("X-Company-Vat", None)
    s.delete(f"{API}/companies/{VAT}")


class TestUploadAPI:
    def test_upload_mixed(self, adm):
        files = [("files", (n, rd(n))) for n in ["IT01234567890_00001.xml", "lotto.zip"]]
        files += [("files", ("bad.zip", b"x")), ("files", ("bad.xml", b"<x")), ("files", ("other.xml", b"<root/>"))]
        r = adm.post(f"{API}/invoices/upload", files=files)
        assert r.status_code == 200
        res = r.json()["results"]
        by = {x["filename"]: x for x in res}
        assert by["IT01234567890_00001.xml"]["status"] == "ok" and by["IT01234567890_00001.xml"]["tipo"] == "attiva"
        assert by["bad.zip"]["status"] == "error" and "ZIP" in by["bad.zip"]["message"]
        assert by["bad.xml"]["status"] == "error" and "XML non valido" in by["bad.xml"]["message"]
        assert by["other.xml"]["status"] == "error" and "FatturaElettronica" in by["other.xml"]["message"]
        zipped = [x for x in res if x["filename"].startswith("lotto.zip/")]
        assert len(zipped) == 3
        print({x["filename"]: (x["status"], x.get("message")) for x in res})
        # Detail persisted correctly
        d = adm.get(f"{API}/invoices/{by['IT01234567890_00001.xml']['id']}").json()
        assert d["numero"] == "10" and d["anno"] == 2025 and d["totale"] == 1220.0
        assert len(d["righe"]) == 1 and len(d["riepilogo"]) == 1 and d["pagamenti"][0]["importo"] == 1220.0
        assert d["cedente"]["piva"] == VAT and d["cessionario"]["denominazione"] == "TEST_Cliente Alfa Spa"
        assert "_id" not in d and "<" in d["xml"]
        # Re-upload -> duplicate
        r2 = adm.post(f"{API}/invoices/upload", files=[("files", ("IT01234567890_00001.xml", rd("IT01234567890_00001.xml")))])
        assert r2.json()["results"][0]["status"] == "duplicate"
