"""Text pentru baza OfficePlus (CL8MSWIN1251) — un singur loc, fisier propriu.

RO: baza refuza diacriticele romanesti (trigger YBIRO_UNIVERS_CHK_DIACRITICE,
ORA-20077 «Text cu diacritice STRICATE in DENUMIREA», vazut pe 07.09.2026 la
«SOCIETATEA PE ACTIUNI DAAC HERMES» venita din registrul de stat). Aici se
transliterează inainte de orice scriere: a-breve/i-circumflex/s-virgula/
t-virgula -> a i s t; chirilicele ramin; ce nu incape in CP1251 se arunca.
EN: fold text to what CL8MSWIN1251 can store; Cyrillic preserved.
"""
from __future__ import annotations

from typing import Optional

_TRANSLIT = str.maketrans({"ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
                           "Ă": "A", "Â": "A", "Î": "I", "Ș": "S", "Ş": "S", "Ț": "T", "Ţ": "T",
                           "—": "-", "–": "-", "«": '"', "»": '"', "’": "'", "‘": "'", "“": '"', "”": '"', "…": "..."})


def to_db_charset(text: Optional[str]) -> str:
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
