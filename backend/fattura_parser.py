import base64
import io
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET


def _decode_p7m(data: bytes) -> bytes:
    candidates = [data]
    try:
        candidates.append(base64.b64decode(data, validate=False))
    except Exception:
        pass
    for c in candidates:
        r = subprocess.run(
            ["openssl", "cms", "-verify", "-noverify", "-nosigs", "-inform", "DER", "-binary"],
            input=c, capture_output=True,
        )
        if r.returncode == 0 and b"<" in r.stdout:
            return r.stdout
    m = re.search(rb"<\?xml.*?FatturaElettronica>", data, re.S)
    if m:
        return m.group(0)
    raise ValueError("Impossibile estrarre l'XML dal file firmato .p7m")


def extract_xml_files(filename: str, data: bytes):
    """Yields (name, xml_bytes or None, error or None)."""
    low = filename.lower()
    if low.endswith(".zip"):
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            yield filename, None, "Archivio ZIP non valido"
            return
        for info in zf.infolist():
            if info.is_dir() or info.filename.startswith("__MACOSX") or "/." in "/" + info.filename:
                continue
            inner = info.filename.lower()
            if inner.endswith((".xml", ".p7m", ".zip")):
                yield from extract_xml_files(f"{filename}/{info.filename}", zf.read(info))
        return
    if low.endswith(".p7m"):
        try:
            yield filename, _decode_p7m(data), None
        except ValueError as e:
            yield filename, None, str(e)
        return
    if low.endswith(".xml"):
        yield filename, data, None
        return
    yield filename, None, "Formato non supportato (usa .xml, .p7m, .zip)"


def _t(el, path):
    if el is None:
        return ""
    f = el.find(path)
    return (f.text or "").strip() if f is not None and f.text else ""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _party(el, with_contacts=False):
    da = el.find("DatiAnagrafici") if el is not None else None
    piva_paese = _t(da, "IdFiscaleIVA/IdPaese")
    piva_cod = _t(da, "IdFiscaleIVA/IdCodice")
    nome = _t(da, "Anagrafica/Denominazione") or " ".join(
        x for x in [_t(da, "Anagrafica/Nome"), _t(da, "Anagrafica/Cognome")] if x
    )
    sede = el.find("Sede") if el is not None else None
    p = {
        "piva": piva_cod,
        "paese": piva_paese,
        "codice_fiscale": _t(da, "CodiceFiscale"),
        "denominazione": nome,
        "regime_fiscale": _t(da, "RegimeFiscale"),
        "indirizzo": " ".join(x for x in [_t(sede, "Indirizzo"), _t(sede, "NumeroCivico")] if x),
        "cap": _t(sede, "CAP"),
        "comune": _t(sede, "Comune"),
        "provincia": _t(sede, "Provincia"),
        "nazione": _t(sede, "Nazione"),
    }
    if with_contacts:
        p["telefono"] = _t(el, "Contatti/Telefono")
        p["email"] = _t(el, "Contatti/Email")
    return p


def natural_key(numero: str) -> str:
    return re.sub(r"\d+", lambda m: m.group(0).zfill(12), (numero or "").upper())


def parse_fattura(xml_bytes: bytes):
    """Returns (list_of_invoice_dicts, raw_xml_string)."""
    xml_bytes = xml_bytes.lstrip(b"\xef\xbb\xbf").strip()
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"XML non valido: {e}")
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    if root.tag != "FatturaElettronica":
        raise ValueError("Il file non è una FatturaElettronica")
    header = root.find("FatturaElettronicaHeader")
    if header is None:
        raise ValueError("Header della fattura mancante")
    dt = header.find("DatiTrasmissione")
    trasmissione = {
        "formato": _t(dt, "FormatoTrasmissione"),
        "codice_destinatario": _t(dt, "CodiceDestinatario"),
        "pec_destinatario": _t(dt, "PECDestinatario"),
        "progressivo_invio": _t(dt, "ProgressivoInvio"),
    }
    cedente = _party(header.find("CedentePrestatore"), with_contacts=True)
    cessionario = _party(header.find("CessionarioCommittente"))
    cessionario["codice_destinatario"] = trasmissione["codice_destinatario"]
    cessionario["pec"] = trasmissione["pec_destinatario"]

    invoices = []
    for body in root.findall("FatturaElettronicaBody"):
        dgd = body.find("DatiGenerali/DatiGeneraliDocumento")
        numero = _t(dgd, "Numero")
        data = _t(dgd, "Data")
        if not numero or not data:
            raise ValueError("Numero o data della fattura mancanti")
        righe = [
            {
                "numero_linea": _t(l, "NumeroLinea"),
                "descrizione": _t(l, "Descrizione"),
                "quantita": _t(l, "Quantita"),
                "unita_misura": _t(l, "UnitaMisura"),
                "prezzo_unitario": _num(_t(l, "PrezzoUnitario")),
                "prezzo_totale": _num(_t(l, "PrezzoTotale")),
                "aliquota_iva": _num(_t(l, "AliquotaIVA")),
                "natura": _t(l, "Natura"),
            }
            for l in body.findall("DatiBeniServizi/DettaglioLinee")
        ]
        riepilogo = [
            {
                "aliquota_iva": _num(_t(r, "AliquotaIVA")),
                "natura": _t(r, "Natura"),
                "imponibile": _num(_t(r, "ImponibileImporto")),
                "imposta": _num(_t(r, "Imposta")),
                "esigibilita": _t(r, "EsigibilitaIVA"),
                "riferimento_normativo": _t(r, "RiferimentoNormativo"),
            }
            for r in body.findall("DatiBeniServizi/DatiRiepilogo")
        ]
        pagamenti = []
        for dp in body.findall("DatiPagamento"):
            for d in dp.findall("DettaglioPagamento"):
                pagamenti.append({
                    "condizioni": _t(dp, "CondizioniPagamento"),
                    "modalita": _t(d, "ModalitaPagamento"),
                    "scadenza": _t(d, "DataScadenzaPagamento"),
                    "importo": _num(_t(d, "ImportoPagamento")),
                    "iban": _t(d, "IBAN"),
                    "istituto": _t(d, "IstitutoFinanziario"),
                })
        imponibile = round(sum(r["imponibile"] for r in riepilogo), 2)
        imposta = round(sum(r["imposta"] for r in riepilogo), 2)
        totale_doc = _t(dgd, "ImportoTotaleDocumento")
        totale = _num(totale_doc) if totale_doc else round(imponibile + imposta, 2)
        invoices.append({
            "numero": numero,
            "numero_key": natural_key(numero),
            "data": data,
            "anno": int(data[:4]) if data[:4].isdigit() else 0,
            "tipo_documento": _t(dgd, "TipoDocumento"),
            "divisa": _t(dgd, "Divisa") or "EUR",
            "causale": " ".join(c.text.strip() for c in dgd.findall("Causale") if c.text) if dgd is not None else "",
            "imponibile": imponibile,
            "imposta": imposta,
            "totale": totale,
            "righe": righe,
            "riepilogo": riepilogo,
            "pagamenti": pagamenti,
            "cedente": cedente,
            "cessionario": cessionario,
            "trasmissione": trasmissione,
        })
    if not invoices:
        raise ValueError("Nessun corpo fattura trovato")
    return invoices, xml_bytes.decode("utf-8", errors="replace")
