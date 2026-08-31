"""Clientul SOAP al SIA „e-Factura” (SFS) + constructorul XML-ului facturii.

RO: serviciul SFS este SOAP/WCF (`basicHttpBinding`, securitate
`TransportWithMessageCredential`), deci autentificarea merge prin antetul
WS-Security `UsernameToken` peste HTTPS — exact ce descrie ghidul oficial
(efactura.sfs.md/Help). Nu folosim `zeep`: nu e in venv-ul productiei, iar
adaugarea unei dependinte pe conturul viu e un risc care nu se justifica
pentru cinci metode. Plicul SOAP il compunem direct — este stabil si vizibil
in jurnal, ceea ce ajuta cind SFS respinge un document.

ATENTIE la XSD: schema exacta a facturii se descarca din sectiunea *Help* a
e-Facturii, sub contul companiei. Pina atunci `build_invoice_xml` produce
structura descrisa in ghid; cimpurile se aliniaza la primul apel real, iar
XML-ul trimis se pastreaza in jurnal ca sa se vada exact ce a plecat.

EN: hand-rolled SOAP client (no zeep in the production venv) + invoice XML
builder; the exact XSD comes from the company's e-Factura Help section.
"""
from __future__ import annotations

import datetime
import re
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

TIMEOUT_S = 60
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_WSSE = ("http://docs.oasis-open.org/wss/2004/01/"
           "oasis-200401-wss-wssecurity-secext-1.0.xsd")
NS_PASS = ("http://docs.oasis-open.org/wss/2004/01/"
           "oasis-200401-wss-username-token-profile-1.0#PasswordText")


def _esc(v: Any) -> str:
    """RO: text sigur pentru XML (SFS respinge documentul la un & liber)."""
    s = "" if v is None else str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _num(v: Any, nd: int = 2) -> str:
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return f"{0:.{nd}f}"


class SfsClient:
    """RO: apeluri catre serviciul e-Factura. Fara credentiale intoarce un
    mesaj clar, nu o exceptie — modulul trebuie sa fie instalabil inainte ca
    firma sa primeasca utilizatorul API."""

    def __init__(self, endpoint: str, username: str, password: str,
                 namespace: str = "http://tempuri.org/"):
        self.endpoint = (endpoint or "").strip()
        self.username = (username or "").strip()
        self.password = password or ""
        self.ns = namespace or "http://tempuri.org/"

    @classmethod
    def from_settings(cls) -> "SfsClient":
        from modules.efactura.store import EfaStore
        s = EfaStore.settings()
        return cls(s.get("endpoint", ""), s.get("username", ""),
                   s.get("password", ""),
                   s.get("namespace", "http://tempuri.org/"))

    def configured(self) -> bool:
        return bool(self.endpoint and self.username and self.password)

    # ── transport ──────────────────────────────────────────────────────
    def _envelope(self, method: str, body_xml: str) -> str:
        """RO: plicul SOAP cu WS-Security UsernameToken (parola in clar peste
        HTTPS — asa cere `TransportWithMessageCredential`)."""
        return (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<soap:Envelope xmlns:soap="{NS_SOAP}">'
            '<soap:Header>'
            f'<wsse:Security xmlns:wsse="{NS_WSSE}" soap:mustUnderstand="1">'
            '<wsse:UsernameToken>'
            f'<wsse:Username>{_esc(self.username)}</wsse:Username>'
            f'<wsse:Password Type="{NS_PASS}">{_esc(self.password)}</wsse:Password>'
            '</wsse:UsernameToken></wsse:Security></soap:Header>'
            f'<soap:Body><{method} xmlns="{self.ns}">{body_xml}'
            f'</{method}></soap:Body></soap:Envelope>')

    def call(self, method: str, body_xml: str = "") -> Dict[str, Any]:
        if not self.configured():
            return {"success": False, "error":
                    "RO: integrarea e-Factura nu e configurata (endpoint / "
                    "utilizator API / parola) — completati-le in pagina "
                    "modulului / EN: e-Factura is not configured yet"}
        envelope = self._envelope(method, body_xml)
        req = urllib.request.Request(
            self.endpoint, data=envelope.encode("utf-8"), method="POST",
            headers={"Content-Type": "text/xml; charset=utf-8",
                     "SOAPAction": f"{self.ns.rstrip('/')}/{method}",
                     "User-Agent": "OfficePlus-eFactura/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read().decode("utf-8", "replace")
            return {"success": True, "raw": raw, "parsed": self._parse(raw)}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")[:2000]
            # RO: SOAP intoarce erorile cu status 500 si un <Fault> lizibil
            return {"success": False, "status": e.code,
                    "error": self._fault(raw) or raw[:400], "raw": raw}
        except Exception as e:                               # noqa: BLE001
            return {"success": False, "error": str(e)[:300]}

    @staticmethod
    def _fault(raw: str) -> Optional[str]:
        m = re.search(r"<(?:\w+:)?faultstring[^>]*>(.*?)</", raw, re.S)
        return m.group(1).strip()[:400] if m else None

    @staticmethod
    def _parse(raw: str) -> Dict[str, str]:
        """RO: aplatizam raspunsul in {tag: text} — ne trebuie doar citeva
        cimpuri (Status, RequestId, TotalInvoicesPosted, ErrorMessage)."""
        out: Dict[str, str] = {}
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return out
        for el in root.iter():
            tag = el.tag.split("}")[-1]
            if el.text and el.text.strip() and tag not in out:
                out[tag] = el.text.strip()
        return out

    # ── metodele folosite ──────────────────────────────────────────────
    def post_invoices(self, invoices_xml: str,
                      request_id: Optional[str] = None,
                      actor_role: str = "Supplier",
                      xml_status: str = "Draft") -> Dict[str, Any]:
        """RO: PostInvoices — trimite factura fiscala in e-Factura.
        Raspunsul contine Status, TotalInvoicesPosted, RequestId, ErrorMessage.
        """
        rid = request_id or uuid.uuid4().hex
        body = ("<request>"
                f"<RequestId>{_esc(rid)}</RequestId>"
                f"<InvoicesXml>{_esc(invoices_xml)}</InvoicesXml>"
                f"<ActorRole>{_esc(actor_role)}</ActorRole>"
                f"<InvoicesXmlStatus>{_esc(xml_status)}</InvoicesXmlStatus>"
                "</request>")
        r = self.call("PostInvoices", body)
        r["request_id"] = rid
        return r

    def get_accepted(self, since: str = "") -> Dict[str, Any]:
        return self.call("GetAcceptedInvoices",
                         f"<request><DateFrom>{_esc(since)}</DateFrom></request>")

    def get_rejected(self, since: str = "") -> Dict[str, Any]:
        return self.call("GetRejectedInvoices",
                         f"<request><DateFrom>{_esc(since)}</DateFrom></request>")

    def get_by_seria_number(self, seria: str, number: str) -> Dict[str, Any]:
        return self.call(
            "GetInvoicesBySeriaNumber",
            f"<request><Seria>{_esc(seria)}</Seria>"
            f"<Number>{_esc(number)}</Number></request>")

    def get_taxpayer(self, idno: str) -> Dict[str, Any]:
        return self.call("GetTaxpayersInfo",
                         f"<request><IDNO>{_esc(idno)}</IDNO></request>")

    def test(self) -> Dict[str, Any]:
        """RO: verificarea conexiunii pentru butonul din pagina modulului —
        un apel inofensiv (nu trimite nimic in sistem)."""
        if not self.configured():
            return {"success": False, "error":
                    "RO: completati endpoint, utilizator si parola / "
                    "EN: fill in endpoint, user and password"}
        r = self.call("GetLogs", "<request><Top>1</Top></request>")
        if r.get("success"):
            return {"success": True,
                    "message": "RO: conectat la SIA e-Factura / EN: connected",
                    "sample": str(r.get("parsed"))[:300]}
        return r


# ── XML-ul facturii ────────────────────────────────────────────────────
def build_invoice_xml(doc: Dict[str, Any], seller: Dict[str, Any],
                      seria: str = "", number: str = "") -> str:
    """RO: documentul nostru -> XML-ul facturii fiscale.

    Structura urmeaza ghidul SFS; denumirile exacte ale nodurilor se verifica
    la primul apel real fata de XSD-ul descarcat din e-Factura. XML-ul plecat
    se pastreaza in jurnal (EFA_LOG), deci alinierea se face pe date reale,
    nu pe presupuneri.
    EN: our document -> fiscal invoice XML; node names to be confirmed against
    the XSD downloaded from e-Factura.
    """
    d = doc
    items: List[Dict[str, Any]] = d.get("items") or []
    lines = []
    for i, it in enumerate(items, 1):
        lines.append(
            "<InvoiceLine>"
            f"<LineNumber>{i}</LineNumber>"
            f"<ProductCode>{_esc(it.get('cod'))}</ProductCode>"
            f"<ProductName>{_esc(it.get('name'))}</ProductName>"
            f"<UnitOfMeasure>{_esc(it.get('um') or 'buc.')}</UnitOfMeasure>"
            f"<Quantity>{_num(it.get('qty'), 3)}</Quantity>"
            f"<UnitPrice>{_num(it.get('price'))}</UnitPrice>"
            f"<Amount>{_num(it.get('sum'))}</Amount>"
            f"<VatRate>{_num(d.get('tva_rate', 20), 0)}</VatRate>"
            "</InvoiceLine>")
    today = datetime.date.today().strftime("%Y-%m-%d")
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<Invoices><Invoice>"
        f"<Seria>{_esc(seria)}</Seria>"
        f"<Number>{_esc(number or d.get('nrmanual'))}</Number>"
        f"<IssueDate>{_esc(d.get('issue_date') or today)}</IssueDate>"
        "<Supplier>"
        f"<IDNO>{_esc(seller.get('idno'))}</IDNO>"
        f"<Name>{_esc(seller.get('name'))}</Name>"
        f"<Address>{_esc(seller.get('address'))}</Address>"
        f"<BankAccount>{_esc(seller.get('iban'))}</BankAccount>"
        f"<BankCode>{_esc(seller.get('bank_code'))}</BankCode>"
        "</Supplier>"
        "<Buyer>"
        f"<IDNO>{_esc(d.get('client_idno'))}</IDNO>"
        f"<Name>{_esc(d.get('client_name'))}</Name>"
        f"<Address>{_esc(d.get('client_address'))}</Address>"
        "</Buyer>"
        f"<Lines>{''.join(lines)}</Lines>"
        f"<TotalWithoutVat>{_num(d.get('total_fara_tva'))}</TotalWithoutVat>"
        f"<TotalVat>{_num(d.get('tva'))}</TotalVat>"
        f"<TotalAmount>{_num(d.get('total'))}</TotalAmount>"
        "</Invoice></Invoices>")
