"""Regulile pure ale CRM-ului — fara baza de date, testabile fara wallet.

RO: contractul XML al Contragenti (INTEGRATION.md §2) -> dict; validarea
IDNO (13 cifre + cifra de control 7,3,1 mod 10); cardul din parametrii
`return_to` (API_ru.md, «Возврат в вызывающую систему»); preseturile de
filtru ale Demo CRM («Toate / Adaugati azi / Cu adresa juridica»);
adresa de apel `/pick`.
EN: pure rules: Contragenti XML card parsing, IDNO check, return_to
parsing, list presets, pick URL.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

CARD_FIELDS = ("idno", "denumire", "inregistrare", "forma_juridica",
               "lichidata", "adresa", "administratori")
PRESETS = ("all", "today", "with_address")
LANGS = ("ro", "ru", "en")


def _num(s: Optional[str]) -> Optional[float]:
    """RO: «100,00» / «180,78» (virgula = separator decimal) -> float."""
    if s is None:
        return None
    t = str(s).strip().replace(" ", "").replace(",", ".")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def idno_valid(idno: Optional[str]) -> bool:
    """RO: IDNO = 13 cifre; ultima e cifra de control (ponderi 7,3,1 ciclic
    pe primele 12, suma mod 10)."""
    s = re.sub(r"\D", "", str(idno or ""))
    if len(s) != 13:
        return False
    w = (7, 3, 1)
    total = sum(int(c) * w[i % 3] for i, c in enumerate(s[:12]))
    return total % 10 == int(s[12])


def parse_card_xml(text: str) -> Dict[str, Any]:
    """RO: <counterparty> -> dict cu cheile din tabela de corespondenta a
    INTEGRATION.md. `founders`/`debts` goale = «fara date», nu eroare."""
    if not text or not text.strip():
        raise ValueError("XML gol")
    try:
        root = ET.fromstring(text.strip().encode("utf-8")
                             if isinstance(text, str) else text)
    except ET.ParseError as e:
        raise ValueError("XML invalid: %s" % e) from e
    if root.tag != "counterparty":
        raise ValueError("radacina asteptata <counterparty>, primita <%s>" % root.tag)

    def txt(tag: str) -> str:
        el = root.find(tag)
        return (el.text or "").strip() if el is not None else ""

    idno = re.sub(r"\D", "", txt("idno") or root.get("idno") or "")
    if not idno:
        raise ValueError("cardul nu are IDNO")
    founders = [{"name": (f.get("name") or "").strip(), "share": _num(f.get("share"))}
                for f in root.findall("founders/founder") if (f.get("name") or "").strip()]
    debts_el = root.find("debts")
    debts = [{"nr": int(d.get("nr")) if (d.get("nr") or "").isdigit() else None,
              "type": (d.get("type") or "").strip(), "sum": _num(d.get("sum"))}
             for d in root.findall("debts/debt")]
    return {
        "idno": idno,
        "denumire": txt("denumire"),
        "inregistrare": txt("inregistrare"),
        "forma_juridica": txt("forma_juridica"),
        "lichidata": txt("lichidata").lower() in ("da", "yes", "1", "true"),
        "adresa": txt("adresa"),
        "administratori": txt("administratori"),
        "founders": founders,
        "debts": debts,
        "currency": (debts_el.get("currency") if debts_el is not None else None) or "MDL",
        "details_text": txt("details_text"),
        "source": root.get("source") or "date.gov.md",
        "updated": root.get("updated") or "",
    }


def card_from_query(args: Dict[str, Any]) -> Dict[str, Any]:
    """RO: cardul scurt din redirect-ul `return_to` (`status=ok&idno=…`).
    Fara fondatori/datorii — acestea se iau cu `GET /card?idno=` din browser."""
    status = (args.get("status") or "").strip().lower()
    if status != "ok":
        raise ValueError({"cancelled": "Selectia a fost anulata",
                          "timeout": "Timpul de selectie a expirat"}.get(status, "Selectie fara rezultat"))
    idno = re.sub(r"\D", "", str(args.get("idno") or ""))
    if not idno:
        raise ValueError("redirect fara IDNO")
    return {
        "idno": idno,
        "denumire": (args.get("denumire") or "").strip(),
        "inregistrare": (args.get("inregistrare") or "").strip(),
        "forma_juridica": (args.get("forma_juridica") or "").strip(),
        "lichidata": (args.get("lichidata") or "").strip().lower() in ("da", "yes", "1", "true"),
        "adresa": (args.get("adresa") or "").strip(),
        "administratori": (args.get("administratori") or "").strip(),
        "founders": [], "debts": [], "currency": "MDL",
        "details_text": "", "source": "date.gov.md", "updated": "",
    }


def preset_where(preset: Optional[str]) -> str:
    """RO: preseturile listei din Demo CRM. Necunoscut -> toate."""
    p = (preset or "all").lower()
    if p == "today":
        return " AND TRUNC(c.CREATED) = TRUNC(SYSDATE)"
    if p == "with_address":
        return " AND c.ADDRESS IS NOT NULL"
    return ""


def pick_url(base: str, q: str = "", lang: str = "ro", return_to: str = "",
             state: str = "", timeout: int = 300) -> str:
    """RO: adresa `GET /pick` a Contragenti (API_ru.md §1)."""
    base = (base or "http://127.0.0.1:9393").rstrip("/")
    params = {"q": q or "", "lang": lang if lang in LANGS else "ro",
              "timeout": int(timeout)}
    if return_to:
        params["return_to"] = return_to
        if state:
            params["state"] = state[:120]
    return base + "/pick?" + urlencode(params)


def card_summary(card: Dict[str, Any]) -> str:
    """RO: o fraza pentru jurnal / linia de mesaje."""
    return "%s — %s%s" % (card.get("idno"), card.get("denumire") or "(fara denumire)",
                          ", lichidata" if card.get("lichidata") else "")
