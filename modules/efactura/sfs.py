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
# RO: valorile din ghidul SFS — roluri si statut XML (tabelele 6 si 24)
ROLE_SUPPLIER = 1        # furnizor
ROLE_BUYER = 2           # cumparator
ROLE_CARRIER = 3         # transportator
XML_UNSIGNED = 0         # nesemnat
XML_SIGNED = 1           # semnat
SIGN_FIRST = 1           # coada primei semnaturi
SIGN_SECOND = 2          # coada celei de a doua semnaturi

# RO: adresa mediului de PROBA al SFS si namespace-ul serviciului. Sint
#     proprietati ale SFS, nu setari ale unei firme — de aceea stau in cod:
#     pagina probei trebuie sa mearga la orice director, fara sa depinda de
#     ce a configurat cineva in back-office-ul unui anume magazin.
# EN: SFS test endpoint — a property of SFS, not of any tenant's settings.
# Adresele publicate de SFS (ghidul de integrare ERP, verificate 31.08.2026):
#   portal de test        https://preproductie.sfs.md
#   e-Factura de test     https://efactura-pre.sfs.md
#   API de test           https://apiefactura-pre.sfs.md   (acces pe lista de IP)
#   API real              https://efactura-api.sfs.md
ENDPOINT_PROD = "https://efactura-api.sfs.md/Service.svc"
ENDPOINT_TEST = "https://apiefactura-pre.sfs.md/Service.svc"
TEST_ENDPOINT = ENDPOINT_TEST          # RO: implicit — mediul de proba
DEFAULT_NAMESPACE = "http://tempuri.org/"
CONTRACT = "IService"                  # RO: SOAPAction e {ns}/IService/{metoda}

# RO: copiii lui <request> NU stau in tempuri, ci in namespace-ul
#     DataContract al serviciului, si in ORDINEA din XSD (intii membrii
#     clasei de baza, apoi cei derivati). Altfel WCF ii deserializeaza ca
#     null si apelul „reuseste" fara sa faca nimic.
NS_DC = "http://schemas.datacontract.org/2004/07/AX.EFactura.Model.ApiModel"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_ARRAYS = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"
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


def _request(fields: List[tuple]) -> str:
    """RO: <request> cu copiii in namespace-ul DataContract.

    `fields` — perechi (nume, xml_deja_construit_sau_text); ordinea din lista
    trebuie sa fie cea din XSD. Valoarea None trimite elementul ca nil.
    """
    out = []
    for name, val in fields:
        if val is None:
            out.append('<a:%s i:nil="true"/>' % name)
        else:
            out.append("<a:%s>%s</a:%s>" % (name, val, name))
    return ('<request xmlns:a="%s" xmlns:i="%s">%s</request>'
            % (NS_DC, NS_XSI, "".join(out)))


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
    def from_settings(cls, signer: int = 1,
                      api: Optional[Dict[str, Any]] = None) -> "SfsClient":
        """RO: clientul unuia dintre cei DOI semnatari.

        In practica factura fiscala se semneaza de doua persoane (director si
        contabil-sef), iar SIA e-Factura tine cozi separate pentru fiecare
        (`Order` 1 si 2). De aceea sint doua conturi API: `signer=1` —
        primul semnatar, `signer=2` — al doilea. Daca al doilea nu e
        configurat, se foloseste primul (firmele mici semneaza cu o singura
        persoana).
        Parametrul `api` sint credentialele scrise AD-HOC in formular (pagina
        probei): cind e dat un utilizator acolo, proba pleaca sub ACEL cont,
        iar setarile salvate nu se ating si nu se amesteca. Din setari se ia
        atunci doar adresa serviciului, daca omul nu a scris-o pe a lui.
        EN: one client per signer; `api` overrides the stored account for a
        single call without touching saved settings.
        """
        from modules.efactura.store import EfaStore
        s = EfaStore.settings()
        adhoc = {k: str(v).strip() for k, v in (api or {}).items()
                 if str(v or "").strip()}
        endpoint = adhoc.get("endpoint") or s.get("endpoint", "")
        ns = adhoc.get("namespace") or s.get("namespace",
                                             "http://tempuri.org/")
        if adhoc.get("username"):
            user, pwd = adhoc["username"], adhoc.get("password", "")
            if int(signer) == 2 and adhoc.get("username2"):
                user, pwd = adhoc["username2"], adhoc.get("password2", "")
            return cls(endpoint, user, pwd, ns)
        user, pwd = s.get("username", ""), s.get("password", "")
        if int(signer) == 2 and s.get("username2"):
            user, pwd = s.get("username2", ""), s.get("password2", "")
        return cls(endpoint, user, pwd, ns)

    @classmethod
    def from_api(cls, api: Optional[Dict[str, Any]] = None,
                 signer: int = 1) -> "SfsClient":
        """RO: clientul construit NUMAI din ce s-a scris in formular.

        Spre deosebire de `from_settings`, nu atinge deloc `EFA_SETTING`:
        proba merge sub contul omului care o face, pe adresa pe care a
        indicat-o el (implicit — mediul de proba al SFS). Asa pagina probei
        e universala: nu depinde de setarile unui magazin anume.
        EN: form-only client; never reads tenant settings.
        """
        a = {k: str(v).strip() for k, v in (api or {}).items()
             if str(v or "").strip()}
        user, pwd = a.get("username", ""), a.get("password", "")
        if int(signer) == 2 and a.get("username2"):
            user, pwd = a["username2"], a.get("password2", "")
        return cls(a.get("endpoint") or TEST_ENDPOINT, user, pwd,
                   a.get("namespace") or DEFAULT_NAMESPACE)

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
                     "SOAPAction":
                         f"{self.ns.rstrip('/')}/{CONTRACT}/{method}",
                     "User-Agent": "OfficePlus-eFactura/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read().decode("utf-8", "replace")
            return {"success": True, "raw": raw, "parsed": self._parse(raw)}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")[:2000]
            # RO: SOAP intoarce erorile cu status 500 si un <Fault> lizibil.
            #     Daca in loc de XML vine o PAGINA HTML, raspunde portalul /
            #     firewall-ul lor, nu serviciul: cel mai des inseamna ca IP-ul
            #     nostru nu e pe lista lor de acces (verificat 31.08.2026:
            #     GET pe ?wsdl merge, POST intoarce o pagina HTML 500).
            if raw.lstrip()[:9].lower().startswith(("<!doctype", "<html")):
                # RO: masurat 02.09.2026, dupa deschiderea accesului: POST gol
                #     -> 400, SOAP 1.2 -> 415 (raspunsuri ale WCF), dar ORICE
                #     fault SOAP (statut 500) vine inapoi ca pagina HTML a
                #     portalului. Deci: 403 = IP-ul nu e pe lista; 500 = o
                #     eroare SOAP mascata (cel mai des utilizator/parola API
                #     gresite sau cont creat pe alt mediu) — textul ei nu se
                #     poate citi de la SFS, doar apelul reusit intoarce SOAP.
                if e.code == 403:
                    msg = ("Accesul e restricționat (403): IP-ul de ieșire al "
                           "acestui server nu e pe lista SFS. Se cere la "
                           "asistenta@sfs.md, cu IP-ul serverului.")
                else:
                    msg = ("Serviciul a răspuns cu o eroare SOAP (status %s), "
                           "iar portalul SFS îi ascunde textul în spatele unei "
                           "pagini HTML. Cel mai des: utilizatorul sau parola "
                           "API greșite, ori contul creat pe alt mediu (de "
                           "probă vs real) decât adresa aleasă." % e.code)
                return {"success": False, "status": e.code, "raw": raw,
                        "error": msg}
            return {"success": False, "status": e.code,
                    "error": self._fault(raw) or raw[:400], "raw": raw}
        except Exception as e:                               # noqa: BLE001
            return {"success": False, "error": self._network_hint(e)}

    def _network_hint(self, exc: Exception) -> str:
        """RO: erorile de retea in limbaj omenesc.

        «urlopen error [Errno -2] Name or service not known» nu spune nimic
        unui director: problema nu e la contul lui, ci la ADRESA serviciului,
        care nu se rezolva de pe server. Mesajul trebuie sa spuna exact asta.
        EN: turn raw socket errors into an actionable sentence.
        """
        host = ""
        try:
            from urllib.parse import urlsplit
            host = urlsplit(self.endpoint).hostname or ""
        except Exception:                                    # noqa: BLE001
            pass
        txt = str(exc)
        low = txt.lower()
        if "name or service not known" in low or "nodename nor servname" in low \
                or "name resolution" in low or "getaddrinfo" in low:
            return ("Adresa serviciului nu se rezolvă din server (DNS): «%s». "
                    "Verificați adresa primită de la SFS — unele medii ale "
                    "SFS sînt accesibile doar din rețeaua lor (MConnect / "
                    "canal dedicat), nu din internet." % (host or self.endpoint))
        if "timed out" in low or "timeout" in low:
            return ("Serviciul «%s» nu a răspuns în %s s: adresa se rezolvă, "
                    "dar conexiunea nu trece (firewall sau rețea închisă)."
                    % (host or self.endpoint, TIMEOUT_S))
        if "connection refused" in low:
            return ("Conexiune refuzată de «%s»: gazda există, dar portul e "
                    "închis pentru noi." % (host or self.endpoint))
        if "certificate" in low or "ssl" in low:
            return "Problemă de certificat TLS la «%s»: %s" % (host, txt[:200])
        return txt[:300]

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
                      actor_role: int = ROLE_SUPPLIER,
                      xml_status: int = XML_UNSIGNED) -> Dict[str, Any]:
        """RO: PostInvoices — trimite factura fiscala in e-Factura.

        Structura e luata din WSDL-ul viu (`?wsdl` / `?xsd=xsd2`, verificat
        31.08.2026), nu din presupuneri: `PostInvocesRequest` mosteneste
        `ActorBaseRequest` -> `BaseRequest`, deci ordinea ceruta de
        DataContractSerializer este RequestId, ActorRole, Attachment,
        InvoicesXml, InvoicesXmlStatus.
        `ActorRole` si `InvoicesXmlStatus` sint NUMERE (rol 1/2/3;
        statut 0 = nesemnat, 1 = semnat).
        EN: field order and namespace taken from the live WSDL.
        """
        rid = request_id or uuid.uuid4().hex
        body = _request([
            ("RequestId", _esc(rid)),
            ("ActorRole", int(actor_role)),
            ("InvoicesXml", _esc(invoices_xml)),
            ("InvoicesXmlStatus", int(xml_status)),
        ])
        r = self.call("PostInvoices", body)
        r["request_id"] = rid
        return r

    def get_for_signing(self, order: int = SIGN_FIRST,
                        actor_role: int = ROLE_SUPPLIER) -> Dict[str, Any]:
        """RO: facturile care asteapta semnatura (`SignRequest`).

        `Order` = pozitia in lantul de semnare: 1 — factura NEsemnata
        (asteapta PRIMA semnatura); 2 — deja semnata cu prima (asteapta
        A DOUA). De aici si nevoia celor doua conturi API.
        EN: invoices awaiting signature; Order 1 = unsigned, 2 = first signed.
        """
        return self.call("GetInvoicesForSigning", _request([
            ("RequestId", uuid.uuid4().hex),
            ("ActorRole", int(actor_role)),
            ("Order", int(order)),
        ]))

    def get_accepted(self, actor_role: int = ROLE_SUPPLIER) -> Dict[str, Any]:
        """RO: `ActorBaseRequest` — doar rolul, fara interval de date."""
        return self.call("GetAcceptedInvoices", _request([
            ("RequestId", uuid.uuid4().hex), ("ActorRole", int(actor_role))]))

    def get_rejected(self, actor_role: int = ROLE_SUPPLIER) -> Dict[str, Any]:
        return self.call("GetRejectedInvoices", _request([
            ("RequestId", uuid.uuid4().hex), ("ActorRole", int(actor_role))]))

    def get_by_seria_number(self, seria: str, number: str) -> Dict[str, Any]:
        """RO: `InvoicesRequest` cere o LISTA de identificatori, nu doua
        cimpuri scalare (ArrayOfInvoiceIndentificator; in element intii
        Number, apoi Seria — ordine alfabetica, ca in XSD)."""
        item = ("<a:InvoiceIndentificator>"
                "<a:Number>%s</a:Number><a:Seria>%s</a:Seria>"
                "</a:InvoiceIndentificator>" % (_esc(number), _esc(seria)))
        return self.call("GetInvoicesBySeriaNumber", _request([
            ("RequestId", uuid.uuid4().hex), ("SeriaAndNumbers", item)]))

    def get_taxpayer(self, idno: str) -> Dict[str, Any]:
        """RO: `TaxpayersRequest` — lista de coduri fiscale; elementele
        listei stau in namespace-ul Arrays al WCF."""
        codes = ('<b:string xmlns:b="%s">%s</b:string>'
                 % (NS_ARRAYS, _esc(idno)))
        return self.call("GetTaxpayersInfo", _request([
            ("RequestId", uuid.uuid4().hex), ("FiscalCodes", codes)]))

    def test(self) -> Dict[str, Any]:
        """RO: verificarea conexiunii — metoda `Test` a serviciului, care
        exista chiar pentru asta si nu atinge nicio factura.

        Inainte se apela `GetLogs` cu `<Top>1</Top>`, un cimp care nu exista
        in contract (`LogsRequest` are From/To) — verificat in XSD.
        EN: uses the service's own `Test` operation.
        """
        if not self.configured():
            return {"success": False, "error":
                    "RO: completati adresa serviciului, utilizatorul si "
                    "parola / EN: fill in endpoint, user and password"}
        r = self.call("Test", "<message>ping</message>")
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
