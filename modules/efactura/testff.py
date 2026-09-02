"""Factura fiscala de TEST — mini-modul universal.

RO: orice director isi poate emite o factura fiscala de proba, cu rechizitele
LUI, pe o suma mica, ca sa vada ca lantul „sistemul nostru → SIA e-Factura →
semnare” chiar merge, INAINTE sa treaca documentele reale prin el.

De ce exista limita de suma: o factura trimisa in e-Factura este un document
FISCAL adevarat, nu o simulare. Chiar si „de test”, ea ajunge in sistemul
SFS. De aceea suma e plafonata la 10 lei (minim 1 ban): daca proba ramine
uitata sau se semneaza din greseala, paguba e de citiva bani, nu de mii.
Limita se verifica pe SERVER, nu doar in formular.

Universal: modulul nu stie nimic despre Biro26. Primeste datele din formular
si intoarce XML-ul / rezultatul trimiterii, deci orice alt modul al
platformei il poate folosi — fie prin butonul-widget
(`/UNA.md/orasldev/efactura/widget.js`), fie prin API-ul intern.
EN: reusable test-invoice engine; server-side amount cap because an
e-Factura document is a real fiscal record, not a sandbox.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from modules.efactura import sfs
from modules.efactura.store import EfaStore

# RO: plafonul probei. 0,01 lei = un ban; 10 lei = pragul de sus.
MIN_TOTAL = 0.01
MAX_TOTAL = 10.00
MAX_LINES = 5


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return default


def validate(payload: Dict[str, Any]) -> Dict[str, List[str]]:
    """RO: verificarea formularului. Intoarce {cimp: [mesaje]}; gol = valid."""
    e: Dict[str, List[str]] = {}
    seller = payload.get("seller") or {}
    buyer = payload.get("buyer") or {}
    lines = payload.get("lines") or []

    if not str(seller.get("idno") or "").strip():
        e["seller.idno"] = ["IDNO-ul vinzatorului e obligatoriu"]
    if not str(seller.get("name") or "").strip():
        e["seller.name"] = ["Denumirea vinzatorului e obligatorie"]
    if not str(buyer.get("idno") or "").strip():
        e["buyer.idno"] = ["IDNO-ul cumparatorului e obligatoriu"]
    if not str(buyer.get("name") or "").strip():
        e["buyer.name"] = ["Denumirea cumparatorului e obligatorie"]

    if not isinstance(lines, list) or not (1 <= len(lines) <= MAX_LINES):
        e["lines"] = [f"Intre 1 si {MAX_LINES} pozitii"]
        return e

    total = 0.0
    for i, ln in enumerate(lines):
        name = str((ln or {}).get("name") or "").strip()
        qty = _f((ln or {}).get("qty"), 0)
        price = _f((ln or {}).get("price"), 0)
        if not name:
            e[f"lines.{i}.name"] = ["Denumirea marfii/serviciului e obligatorie"]
        if qty <= 0:
            e[f"lines.{i}.qty"] = ["Cantitatea trebuie sa fie > 0"]
        if price < 0:
            e[f"lines.{i}.price"] = ["Pretul nu poate fi negativ"]
        total += round(qty * price, 2)

    total = round(total, 2)
    if total < MIN_TOTAL:
        e["total"] = [f"Suma minima este {MIN_TOTAL:.2f} lei (un ban)"]
    elif total > MAX_TOTAL:
        e["total"] = [f"Proba e plafonata la {MAX_TOTAL:.2f} lei — "
                      f"suma calculata: {total:.2f} lei. "
                      "Factura ajunge in sistemul FISCAL real, de aceea limita."]
    return e


def build(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RO: formularul -> documentul in forma pe care o asteapta build_invoice_xml."""
    seller = payload.get("seller") or {}
    buyer = payload.get("buyer") or {}
    lines_in = payload.get("lines") or []
    tva_rate = _f(payload.get("tva_rate"), 20)

    items, total = [], 0.0
    for i, ln in enumerate(lines_in, 1):
        qty = _f(ln.get("qty"), 1)
        price = _f(ln.get("price"), 0)
        amount = round(qty * price, 2)
        total += amount
        items.append({
            "cod": str(ln.get("cod") or f"TEST-{i}")[:60],
            "name": str(ln.get("name") or "")[:400],
            # RO: serviciu sau marfa — unitatea o alege directorul
            "um": str(ln.get("um") or "buc.")[:20],
            "qty": qty, "price": price, "sum": amount,
        })
    total = round(total, 2)
    # RO: TVA inclus in pret (ca in contul de plata al magazinului)
    tva = round(total - total / (1 + tva_rate / 100), 2) if tva_rate else 0.0
    nr = str(payload.get("number") or "").strip() or (
        "TEST-" + datetime.datetime.now().strftime("%m%d%H%M"))
    return {
        "nrmanual": nr,
        "issue_date": (str(payload.get("date") or "").strip()
                       or datetime.date.today().isoformat()),
        "client_name": buyer.get("name"),
        "client_idno": buyer.get("idno"),
        "client_address": buyer.get("address"),
        # RO: banca cumparatorului, daca e data (exportul real o are mereu)
        "client_iban": buyer.get("iban"),
        "client_bank": buyer.get("bank_name"),
        "client_bank_code": buyer.get("bank_code"),
        "client_taxpayer_type": buyer.get("taxpayer_type"),
        "items": items,
        "total": total,
        "tva": tva,
        "total_fara_tva": round(total - tva, 2),
        "tva_rate": tva_rate,
        "_seller": {
            "idno": seller.get("idno"), "name": seller.get("name"),
            "address": seller.get("address"), "iban": seller.get("iban"),
            "bank_code": seller.get("bank_code"),
            # RO: XSD: BankAccount@BranchTitle = denumirea bancii
            "bank_name": seller.get("bank_name"),
            "cod_tva": seller.get("cod_tva"),
            "taxpayer_type": seller.get("taxpayer_type"),
        },
        "_seria": str(payload.get("seria") or "").strip(),
    }


def preview(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RO: XML-ul probei, FARA sa trimita nimic — merge si neconfigurat."""
    errors = validate(payload)
    if errors:
        return {"success": False, "error": "Validation failed.",
                "errors": errors}
    doc = build(payload)
    xml = sfs.build_invoice_xml(doc, doc["_seller"], seria=doc["_seria"],
                                number=doc["nrmanual"])
    return {"success": True, "data": {"xml": xml, "total": doc["total"],
                                      "number": doc["nrmanual"]}}


def send(payload: Dict[str, Any], src: str = "test") -> Dict[str, Any]:
    """RO: trimite proba in SIA e-Factura, cu rechizitele din formular.

    Documentul pleaca NEsemnat (`InvoicesXmlStatus = 0`): semnarea ramine la
    cei doi semnatari — in interfata web (regim semi) sau prin cozile
    `GetInvoicesForSigning` Order 1 si 2.
    """
    errors = validate(payload)
    if errors:
        return {"success": False, "error": "Validation failed.",
                "errors": errors}
    doc = build(payload)
    xml = sfs.build_invoice_xml(doc, doc["_seller"], seria=doc["_seria"],
                                number=doc["nrmanual"])
    # RO: NUMAI contul scris in formular — pagina probei nu se leaga de
    #     setarile vreunui magazin (vezi sfs.SfsClient.from_api).
    client = sfs.SfsClient.from_api(payload.get("api"), signer=1, src=src)
    if not client.configured():
        return {"success": False, "xml": xml, "error":
                "Completati contul API e-Factura (utilizator si parola) "
                "in pagina probei."}
    rid = "test-" + uuid.uuid4().hex[:16]
    r = client.post_invoices(xml, request_id=rid,
                             actor_role=sfs.ROLE_SUPPLIER,
                             xml_status=sfs.XML_UNSIGNED)
    EfaStore.log(None, "test_invoice",
                 f"src={src} nr={doc['nrmanual']} total={doc['total']} "
                 f"xml={xml[:800]}", src)
    if not r.get("success"):
        EfaStore.log(None, "test_error", str(r.get("error"))[:1200], src)
        return {"success": False, "error": r.get("error"), "xml": xml}
    parsed = r.get("parsed") or {}
    EfaStore.log(None, "test_reply", str(parsed)[:1200], src)
    return {"success": not parsed.get("ErrorMessage"),
            "data": {"number": doc["nrmanual"], "total": doc["total"],
                     "request_id": rid, "reply": parsed,
                     "error": parsed.get("ErrorMessage")},
            "xml": xml}


def _reach(endpoint: str) -> Dict[str, Any]:
    """RO: intii adresa, apoi contul. Daca gazda nu se rezolva sau portul e
    inchis, vina nu e a utilizatorului si a parolei — omul trebuie sa vada
    asta separat, nu ca «cont gresit»."""
    import socket
    from urllib.parse import urlsplit
    u = urlsplit(endpoint or "")
    host = u.hostname
    port = u.port or (443 if u.scheme == "https" else 80)
    if not host:
        return {"configured": False}
    try:
        socket.getaddrinfo(host, port)
    except OSError as e:
        return {"configured": True, "ok": False,
                "reply": "«%s» nu se rezolvă (DNS): %s. Unele medii ale SFS "
                         "sînt accesibile doar din rețeaua lor." % (host, e)}
    try:
        with socket.create_connection((host, port), timeout=6):
            pass
    except OSError as e:
        return {"configured": True, "ok": False,
                "reply": "%s:%s inaccesibil: %s" % (host, port, e)}
    return {"configured": True, "ok": True, "reply": "%s:%s accesibil" % (host, port)}


_EGRESS: Dict[str, str] = {}


def _egress_ip() -> str:
    """RO: adresa cu care ESTE VAZUT serverul in internet.

    SFS deschide accesul pe lista de IP, iar apelul catre e-Factura il face
    SERVERUL, nu calculatorul directorului — deci adresa care trebuie trimisa
    la `asistenta@sfs.md` este aceasta, nu cea a statiei de lucru. Se afla o
    singura data si se tine minte; daca nu se poate afla, nu strica nimic.
    EN: the server's outbound IP — that is what SFS must whitelist.
    """
    if "ip" not in _EGRESS:
        import urllib.request
        try:
            with urllib.request.urlopen("https://api.ipify.org",
                                        timeout=4) as r:
                _EGRESS["ip"] = r.read().decode("ascii", "replace").strip()[:45]
        except Exception:                                    # noqa: BLE001
            _EGRESS["ip"] = ""
    return _EGRESS["ip"]


def ping(api: Optional[Dict[str, Any]] = None,
         src: str = "test-page") -> Dict[str, Any]:
    """RO: verifica AMBELE conturi API date in formular, fara sa trimita
    nimic in sistem — asa directorul vede ca datele lui sint bune inainte
    de a emite proba. Prima linie e despre ADRESA, nu despre cont."""
    out = {"adresa": _reach(sfs.SfsClient.from_api(api).endpoint)}
    ip = _egress_ip()
    if ip:
        out["ip_server"] = {"configured": True, "ok": True,
                            "reply": "%s — această adresă trebuie deschisă "
                                     "la SFS (asistenta@sfs.md)" % ip}
    if out["adresa"].get("configured") and not out["adresa"].get("ok"):
        # RO: fara retea, apelurile SOAP ar da doar acelasi mesaj de trei ori
        return {"success": True, "data": out}
    for label, signer in (("prima_semnatura", 1), ("a_doua_semnatura", 2)):
        c = sfs.SfsClient.from_api(api, signer=signer, src=src)
        if not c.configured():
            out[label] = {"configured": False}
            continue
        r = c.test()
        out[label] = {"configured": True, "user": c.username,
                      "ok": bool(r.get("success")),
                      "reply": str(r.get("message") or r.get("error"))[:300]}
    return {"success": True, "data": out}


def signing_queues(api: Optional[Dict[str, Any]] = None,
                   src: str = "test-page") -> Dict[str, Any]:
    """RO: ce asteapta prima si a doua semnatura — pentru butonul din pagina
    de test: se vede imediat daca proba a ajuns in coada de semnare."""
    out = {}
    for label, signer, order in (("prima_semnatura", 1, sfs.SIGN_FIRST),
                                 ("a_doua_semnatura", 2, sfs.SIGN_SECOND)):
        c = sfs.SfsClient.from_api(api, signer=signer, src=src)
        if not c.configured():
            out[label] = {"configured": False}
            continue
        r = c.get_for_signing(order=order)
        invs = queue_invoices(r.get("raw", "")) if r.get("success") else []
        out[label] = {"configured": True, "ok": r.get("success"),
                      "count": len(invs), "invoices": invs[:20],
                      "reply": (("%d factură/facturi în așteptare" % len(invs))
                                if r.get("success") else str(r.get("error"))[:300])}
    return {"success": True, "data": out}


def queue_invoices(raw: str) -> List[Dict[str, Any]]:
    """RO: lista lizibila din raspunsul GetInvoicesForSigning.

    Structura (masurata 02.09.2026): Results/XmlInvoice cu Number, Seria,
    Status, InvoiceStatus si Xml (documentul, ca text). SFS NORMALIZEAZA ce
    a primit: Seria/Number vin goale pina la semnare (le da sistemul), iar
    Title/Address ale partilor sint inlocuite cu cele din registrul fiscal
    dupa IDNO — de aceea aratam ce e IN sistem, nu ce am trimis noi.
    """
    from xml.etree import ElementTree as ET
    out: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    for el in root.iter():
        if el.tag.split("}")[-1] != "XmlInvoice":
            continue
        rec: Dict[str, Any] = {}
        for ch in el:
            rec[ch.tag.split("}")[-1]] = (ch.text or "").strip()
        item = {"seria": rec.get("Seria", ""), "number": rec.get("Number", ""),
                "invoice_status": rec.get("InvoiceStatus", ""),
                "status": rec.get("Status", ""), "total": "", "buyer": "",
                "first_row": ""}
        try:
            doc = ET.fromstring(rec.get("Xml") or "")
            inf = doc.find("SupplierInfo") if doc.tag == "Document" else doc.find(".//SupplierInfo")
            if inf is not None:
                item["total"] = inf.findtext("Total") or ""
                b = inf.find("Buyer")
                item["buyer"] = (b.get("Title") if b is not None else "") or ""
                row = inf.find("Merchandises/Row")
                item["first_row"] = (row.get("Name") if row is not None else "") or ""
        except ET.ParseError:
            pass
        out.append(item)
    return out
