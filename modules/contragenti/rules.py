"""Regulile pure ale puntii Contragenti -> una.md (fara baza de date).

RO: parsarea cardului XML (contractul din INTEGRATION.md), aducerea textului
la CL8MSWIN1251 (diacriticele romanesti -> ASCII, chirilicele ramin),
normalizarea denumirii pentru potrivire (fara forma juridica, fara
punctuatie) si maparea cardului pe cimpurile TMS_UNIVERS / TMS_ORG — aceeasi
mapare ca `tms_export.map_company` din Contragenti (GR1='E', CODVECHI=IDNO).
EN: pure rules: XML card, charset folding, name normalisation, TMS mapping.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, Optional
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sdk"))
import legal_forms  # noqa: E402  (copie MIT din repo-ul Contragenti)

_TRANSLIT = str.maketrans({"ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
                           "Ă": "A", "Â": "A", "Î": "I", "Ș": "S", "Ş": "S", "Ț": "T", "Ţ": "T",
                           "—": "-", "–": "-", "«": '"', "»": '"', "’": "'", "“": '"', "”": '"'})


def to_db_charset(text: Optional[str]) -> str:
    """RO: doar caractere reprezentabile in CP1251; restul se arunca, nu «?»."""
    if not text:
        return ""
    out = []
    for ch in str(text).translate(_TRANSLIT):
        try:
            ch.encode("cp1251")
            out.append(ch)
        except UnicodeEncodeError:
            continue
    return "".join(out).strip()


def cut(text: Optional[str], n: int) -> Optional[str]:
    s = to_db_charset(text)
    return s[:n] if s else None


def strip_role(admin: Optional[str]) -> str:
    """'TUHARI PAVEL [Administrator]' -> 'TUHARI PAVEL'."""
    s = to_db_charset(admin)
    i = s.find("[")
    return (s[:i] if i >= 0 else s).strip()


def idno_valid(idno: Optional[str]) -> bool:
    s = re.sub(r"\D", "", str(idno or ""))
    if len(s) != 13:
        return False
    w = (7, 3, 1)
    return sum(int(c) * w[i % 3] for i, c in enumerate(s[:12])) % 10 == int(s[12])


def norm_name(name: Optional[str]) -> str:
    """RO: cheia de potrivire dupa denumire: fara diacritice, fara forma
    juridica (SRL, SA, II, «Societatea cu raspundere limitata»…), fara
    ghilimele/punctuatie, spatii unice, majuscule.
    'Societatea cu Raspundere Limitata CONINFO' == 'CONINFO S.R.L.' == 'coninfo'."""
    if not name:
        return ""
    parsed = legal_forms.parse_name(to_db_charset(name))
    core = parsed.get("nume") or parsed.get("short") or name
    core = to_db_charset(core).upper()
    core = re.sub(r"[\"'«»„“”().,;:/\\_-]+", " ", core)
    return re.sub(r"\s+", " ", core).strip()


def name_token(name: Optional[str]) -> str:
    """RO: cel mai lung cuvint (>= 4 litere) — filtrul LIKE pentru candidati."""
    words = [w for w in re.split(r"[^A-Z0-9]+", norm_name(name)) if len(w) >= 4]
    return max(words, key=len) if words else norm_name(name)[:12]


def parse_card_xml(text: str) -> Dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("XML gol")
    try:
        root = ET.fromstring(text.strip().encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError as e:
        raise ValueError("XML invalid: %s" % e) from e
    if root.tag != "counterparty":
        raise ValueError("radacina asteptata <counterparty>, primita <%s>" % root.tag)

    def txt(tag):
        el = root.find(tag)
        return (el.text or "").strip() if el is not None else ""

    idno = re.sub(r"\D", "", txt("idno") or root.get("idno") or "")
    if not idno:
        raise ValueError("cardul nu are IDNO")
    return {"idno": idno, "denumire": txt("denumire"), "inregistrare": txt("inregistrare"),
            "forma_juridica": txt("forma_juridica"),
            "lichidata": txt("lichidata").lower() in ("da", "yes", "1", "true"),
            "adresa": txt("adresa"), "administratori": txt("administratori"),
            "source": root.get("source") or "date.gov.md", "updated": root.get("updated") or ""}


def card_from_fields(d: Dict[str, Any]) -> Dict[str, Any]:
    """RO: cardul scurt din `return_to` / postMessage (idno, denumire, adresa…)."""
    idno = re.sub(r"\D", "", str(d.get("idno") or ""))
    if not idno:
        raise ValueError("fara IDNO")
    return {"idno": idno, "denumire": (d.get("denumire") or d.get("name") or "").strip(),
            "inregistrare": (d.get("inregistrare") or "").strip(),
            "forma_juridica": (d.get("forma_juridica") or "").strip(),
            "lichidata": str(d.get("lichidata") or "").strip().lower() in ("da", "yes", "1", "true"),
            "adresa": (d.get("adresa") or d.get("address") or "").strip(),
            "administratori": (d.get("administratori") or "").strip(),
            "source": d.get("source") or "date.gov.md", "updated": d.get("updated") or ""}


def map_card(card: Dict[str, Any]) -> Dict[str, Any]:
    """RO: cimpurile TMS — ca `tms_export.map_company` din Contragenti."""
    original = cut(card.get("denumire"), 80)
    parsed = legal_forms.parse_name(card.get("denumire") or "")
    return {
        "univers": {"DENUMIREA": cut(parsed.get("short"), 80) or original,
                    "NAMERUS": original, "TIP": "O", "GR1": "E",
                    "CODVECHI": cut(card.get("idno"), 13)},
        "org": {"CODFISCAL": cut(card.get("idno"), 30), "ADRESS": cut(card.get("adresa"), 150),
                "DIRECTOR": cut(strip_role(card.get("administratori")), 25)},
        "forma": parsed.get("forma"), "nume": parsed.get("nume"),
    }


def card_summary(card: Dict[str, Any]) -> str:
    return "%s — %s%s" % (card.get("idno"), card.get("denumire") or "(fara denumire)",
                          ", lichidata" if card.get("lichidata") else "")
