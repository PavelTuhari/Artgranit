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
        # RO: de unde vine apelul — pentru jurnalul EFA_CALL (test-page/api/…)
        self.src = ""

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
                 signer: int = 1, src: str = "test-page") -> "SfsClient":
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
        c = cls(a.get("endpoint") or TEST_ENDPOINT, user, pwd,
                a.get("namespace") or DEFAULT_NAMESPACE)
        c.src = src or "test-page"          # RO: eticheta din jurnalul EFA_CALL
        return c

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
        r = self._send(method, envelope)
        # RO: fiecare apel, intreg, in jurnal (parola mascata) — vezi journal.py
        from modules.efactura import journal
        res, summ = journal.verdict(r.get("status"), r.get("raw", ""),
                                    r.get("parsed"), r.get("error"))
        journal.record(src=self.src, username=self.username,
                       endpoint=self.endpoint, method=method,
                       request_xml=envelope, response_raw=r.get("raw", ""),
                       status=r.get("status"), duration_ms=r.get("ms", 0),
                       result=res, summary=summ)
        r["result"], r["summary"] = res, summ
        return r

    def _send(self, method: str, envelope: str) -> Dict[str, Any]:
        """RO: transportul propriu-zis; intoarce si statutul HTTP si durata."""
        import time as _t
        t0 = _t.time()
        req = urllib.request.Request(
            self.endpoint, data=envelope.encode("utf-8"), method="POST",
            headers={"Content-Type": "text/xml; charset=utf-8",
                     "SOAPAction":
                         f"{self.ns.rstrip('/')}/{CONTRACT}/{method}",
                     "User-Agent": "OfficePlus-eFactura/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read().decode("utf-8", "replace")
                st = resp.status
            return {"success": True, "raw": raw, "parsed": self._parse(raw),
                    "status": st, "ms": int((_t.time() - t0) * 1000)}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")[:200000]
            ms = int((_t.time() - t0) * 1000)
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
                        "error": msg, "ms": ms}
            return {"success": False, "status": e.code, "raw": raw, "ms": ms,
                    "error": self._fault(raw) or raw[:400]}
        except Exception as e:                               # noqa: BLE001
            return {"success": False, "error": self._network_hint(e),
                    "status": None, "raw": "",
                    "ms": int((_t.time() - t0) * 1000)}

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
def _attr(v: Any) -> str:
    """RO: valoare de ATRIBUT — pe linga &,<,> trebuie mascate si ghilimelele."""
    return _esc(v).replace('"', "&quot;")


def _dt(v: Any) -> str:
    """RO: XSD cere xs:dateTime; primim 'YYYY-MM-DD' sau nimic (= azi).
    Ora si fusul orar — ca in exportul real din ghidul SFS
    (`2025-05-29T15:32:08+03:00`), nu miezul noptii fara fus."""
    v = str(v or "").strip()[:10] or datetime.date.today().isoformat()
    return v + datetime.datetime.now().strftime("T%H:%M:%S") + "+03:00"


def build_invoice_xml(doc: Dict[str, Any], seller: Dict[str, Any],
                      seria: str = "", number: str = "") -> str:
    """RO: documentul nostru -> XML-ul facturii fiscale, dupa XSD-ul OFICIAL.

    Structura vine din `TaxInvoiceSchema.xsd` (e-Factura -> Ajutor, copiat in
    docs/Partner/sfs/), nu din presupuneri: prima proba reala (02.09.2026) a
    fost respinsa cu «The 'Invoices' element is not declared…» pentru ca
    radacina si nodurile noastre erau inventate. Reguli din XSD:

      Documents / Document / SupplierInfo (fara namespace)
        Seria?, Number?, IssuedDate?, DeliveryDate (OBLIGATORIU, dateTime),
        Supplier @IDNO(obligatoriu) @Title @Address @TaxpayerType
          + BankAccount @Account @BranchTitle @BranchCode,
        Buyer  @IDNO(obligatoriu) @Title @Address @TaxpayerType,
        Total?, TotalTVA?,
        Merchandises / Row @Name @UnitOfMeasure @Quantity @UnitPriceWithoutTVA
          @TotalPriceWithoutTVA @TVA @TotalTVA @TotalPrice (toate obligatorii),
        CreationMotiv (OBLIGATORIU, int)
      — in EXACT aceasta ordine (xs:sequence).

    Preturile noastre includ TVA (ca in contul de plata al magazinului), iar
    XSD-ul cere si valorile FARA TVA: se calculeaza pe fiecare rind.
    TaxpayerType: 1 = juridic, 2 = persoana fizica, 3 = nerezident.
    CreationMotiv: 4 = Livrare / 5 = Non-livrare — SFS respinge orice alta
    valoare (masurat 02.09.2026); implicit 4.
    Total = suma cu TVA a facturii, TotalTVA = suma TVA — asa cum apar pe
    factura tiparita; ambele sint optionale la import, mediul de proba le
    valideaza.
    EN: invoice XML strictly following the official TaxInvoiceSchema.xsd.
    """
    d = doc
    items: List[Dict[str, Any]] = d.get("items") or []
    rate = float(d.get("tva_rate") or 0)
    k = 1 + rate / 100.0
    rows, total, total_tva = [], 0.0, 0.0
    for it in items:
        qty = float(it.get("qty") or 0)
        with_tva = float(it.get("sum") or 0)
        no_tva = round(with_tva / k, 2) if k else with_tva
        tva = round(with_tva - no_tva, 2)
        unit_no_tva = round(no_tva / qty, 2) if qty else 0.0
        total += with_tva
        total_tva += tva
        rows.append(
            "<Row"
            f' Code="{_attr(it.get("cod") or "")}"'
            f' Name="{_attr(it.get("name"))}"'
            f' UnitOfMeasure="{_attr(it.get("um") or "buc.")}"'
            f' Quantity="{_num(qty, 3)}"'
            f' UnitPriceWithoutTVA="{_num(unit_no_tva)}"'
            f' TotalPriceWithoutTVA="{_num(no_tva)}"'
            f' TVA="{_num(rate, 0)}"'
            f' TotalTVA="{_num(tva)}"'
            f' TotalPrice="{_num(with_tva)}"/>')

    def party(tag: str, p: Dict[str, Any], idno: Any, name: Any, addr: Any,
              with_bank: bool) -> str:
        # RO: TaxpayerType 1 = juridic, 2 = persoana fizica, 3 = nerezident.
        #     Daca nu e dat, se deduce: IDNO-urile firmelor incep cu 1,
        #     IDNP-urile persoanelor cu 2 (vazut pe contul A-88: cumparator
        #     persoana fizica cu IDNP 2003…, marcat gresit ca juridic).
        tt = p.get("taxpayer_type")
        if not tt:
            digits = "".join(ch for ch in str(idno or "") if ch.isdigit())
            tt = 2 if (len(digits) == 13 and digits.startswith("2")) else 1
        out = (f"<{tag} IDNO=\"{_attr(idno)}\" Title=\"{_attr(name)}\" "
               f"Address=\"{_attr(addr)}\" NResident=\"false\" "
               f"IsSupplierOnly=\"false\" "
               f"TaxpayerType=\"{int(tt)}\"")
        if p.get("cod_tva"):
            out += f' CodTVA="{_attr(p.get("cod_tva"))}"'
        acc = p.get("iban") or p.get("account")
        if with_bank and acc:
            out += (">"
                    f"<BankAccount Account=\"{_attr(acc)}\" "
                    f"BranchTitle=\"{_attr(p.get('bank_name') or p.get('bank') or '')}\" "
                    f"BranchCode=\"{_attr(p.get('bank_code') or '')}\"/>"
                    f"</{tag}>")
        else:
            out += "/>"
        return out

    buyer = {"iban": d.get("client_iban"), "bank_name": d.get("client_bank"),
             "bank_code": d.get("client_bank_code"),
             "taxpayer_type": d.get("client_taxpayer_type"),
             "cod_tva": d.get("client_cod_tva")}
    issue = d.get("issue_date") or d.get("date")
    head = ""
    if seria:
        head += f"<Seria>{_esc(seria)}</Seria>"
    if number:
        head += f"<Number>{_esc(number)}</Number>"
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<Documents><Document><SupplierInfo>"
        + head +
        f"<IssuedDate>{_dt(issue)}</IssuedDate>"
        f"<DeliveryDate>{_dt(d.get('delivery_date') or issue)}</DeliveryDate>"
        + party("Supplier", seller, seller.get("idno"), seller.get("name"),
                seller.get("address"), True)
        + party("Buyer", buyer, d.get("client_idno"), d.get("client_name"),
                d.get("client_address"), bool(buyer.get("iban")))
        # RO: nodurile pe care exportul real al SFS le are mereu, chiar goale
        #     (ghidul de integrare, §6): fara ele serverul lor a raspuns
        #     «Object reference not set to an instance of an object» (02.09.2026).
        + "<VehicleLogbook><Seria/><Number/></VehicleLogbook>"
        + "<Redirections/>"
        + f"<Total>{_num(round(total, 2))}</Total>"
        f"<TotalTVA>{_num(round(total_tva, 2))}</TotalTVA>"
        "<Merchandises>" + "".join(rows) + "</Merchandises>"
        # RO: SFS accepta DOAR 4 sau 5 («Motivul Crearii … trebue sa fie 4
        #     sau 5», raspuns real 02.09.2026): 4 = Livrare (exemplul din
        #     ghidul de integrare), 5 = Non-livrare (ghidul utilizatorului
        #     §4.2). Implicit 4; se poate da in document (`creation_motiv`).
        f"<CreationMotiv>{int(d.get('creation_motiv') or 4)}</CreationMotiv>"
        "</SupplierInfo></Document></Documents>")
