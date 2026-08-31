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
    s = EfaStore.settings()
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
        "items": items,
        "total": total,
        "tva": tva,
        "total_fara_tva": round(total - tva, 2),
        "tva_rate": tva_rate,
        "_seller": {
            "idno": seller.get("idno"), "name": seller.get("name"),
            "address": seller.get("address"), "iban": seller.get("iban"),
            "bank_code": seller.get("bank_code"),
        },
        "_seria": str(payload.get("seria") or s.get("seria") or "").strip(),
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
    # RO: contul API scris in formular are prioritate — proba pleaca sub
    #     semnatura directorului care o face, fara sa atinga setarile firmei.
    client = sfs.SfsClient.from_settings(signer=1, api=payload.get("api"))
    if not client.configured():
        return {"success": False, "xml": xml, "error":
                "Contul API e-Factura lipseste: completati utilizatorul si "
                "parola in pagina probei sau in Setari e-Factura."}
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


def ping(api: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RO: verifica AMBELE conturi API date in formular, fara sa trimita
    nimic in sistem — asa directorul vede ca datele lui sint bune inainte
    de a emite proba."""
    out = {}
    for label, signer in (("prima_semnatura", 1), ("a_doua_semnatura", 2)):
        c = sfs.SfsClient.from_settings(signer=signer, api=api)
        if not c.configured():
            out[label] = {"configured": False}
            continue
        r = c.test()
        out[label] = {"configured": True, "user": c.username,
                      "ok": bool(r.get("success")),
                      "reply": str(r.get("message") or r.get("error"))[:300]}
    return {"success": True, "data": out}


def signing_queues(api: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RO: ce asteapta prima si a doua semnatura — pentru butonul din pagina
    de test: se vede imediat daca proba a ajuns in coada de semnare."""
    out = {}
    for label, signer, order in (("prima_semnatura", 1, sfs.SIGN_FIRST),
                                 ("a_doua_semnatura", 2, sfs.SIGN_SECOND)):
        c = sfs.SfsClient.from_settings(signer=signer, api=api)
        if not c.configured():
            out[label] = {"configured": False}
            continue
        r = c.get_for_signing(order=order)
        out[label] = {"configured": True, "ok": r.get("success"),
                      "reply": str(r.get("parsed") or r.get("error"))[:300]}
    return {"success": True, "data": out}
