"""Reguli pure ale modulului e-Factura — fara baza de date, testabile oriunde.

RO: cifra de control a IDNO/IDNP (Republica Moldova): primele 12 cifre se
inmultesc cu ponderile 7,3,1 (repetate), suma modulo 10 trebuie sa fie a 13-a
cifra. Verificat 02.09.2026 pe raspunsurile reale ale SFS: clientul fictiv
«SRL TEST Casa Operator» (1026602001999) pica la cifra de control si a fost
respins de registru; IDNO-urile acceptate trec toate. Un IDNO care pica aici
nu are rost sa mai plece la SFS — refuzul e local si in romana.
EN: Moldovan IDNO/IDNP check digit (weights 7,3,1), used before calling SFS.
"""
from __future__ import annotations

from typing import Optional


def idno_valid(idno: str) -> bool:
    d = [int(c) for c in str(idno or "") if c.isdigit()]
    if len(d) != 13 or len(str(idno or "").strip()) != 13:
        return False
    s = sum(x * w for x, w in zip(d[:12], [7, 3, 1] * 4))
    return s % 10 == d[12]


def idno_error(idno: str, who: str = "clientul") -> Optional[str]:
    """RO: None daca e bun; altfel mesajul pentru operator."""
    v = str(idno or "").strip()
    if not v:
        return "%s nu are IDNO." % who.capitalize()
    if not idno_valid(v):
        return ("IDNO-ul %s (%s) nu trece cifra de control — verificați "
                "fișa clientului; SFS îl va respinge ca «isn't registered in "
                "the fiscal registry»." % (who, v))
    return None


# ── explicarea refuzurilor SFS (11.09.2026, documentul 431) ──────────────
# RO: SFS raspunde HTTP 200 si pune motivul in `ErrorMessage`, iar `Status=2`
#     inseamna doar «raspuns prelucrat», nu «acceptat». Ce conteaza pentru
#     operator e `TotalInvoicesPosted`: 0 din N = NIMIC nu a intrat in SIA
#     e-Factura, deci actiunea se poate repeta fara teama de dubluri (pe
#     03.09.2026 actiunea a fost apasata de 4 ori si au aparut 4 facturi —
#     acolo insa fiecare apasare REUSISE).
#     Unele mesaje sint ale lor, nu ale noastre: incarcarea atasamentului
#     (XML-ul facturii ajunge fisier in stocarea SFS) cade cu «Va rugam sa
#     incercati mai tarziu» — nu e nimic de corectat in document.
SFS_TRANSIENT = (
    "atasament", "ataşament", "atașament",       # incarcarea atasamentului
    "incercati mai tarziu", "incercaţi mai târziu", "încercați mai târziu",
    "try again later", "timeout", "time-out",
)


def sfs_transient(err: Optional[str]) -> bool:
    """RO: True daca refuzul e al serverului SFS, nu al documentului nostru."""
    t = (err or "").lower()
    return any(w in t for w in SFS_TRANSIENT)


def explain_sfs_error(err: Optional[str], parsed: Optional[dict] = None) -> str:
    """RO: mesajul pe care il vede operatorul in fereastra aplicatiei native.
    Pastreaza textul SFS si adauga ce trebuie sa stie: cine e de vina si daca
    se poate reincerca."""
    base = (err or "").strip()
    if not base:
        return ""
    p = parsed or {}
    try:
        posted = int(str(p.get("TotalInvoicesPosted") or 0).strip() or 0)
        total = int(str(p.get("TotalInvoices") or 0).strip() or 0)
    except (TypeError, ValueError):
        posted, total = 0, 0
    out = base
    if sfs_transient(base):
        out += " [eroare la SFS, nu in document]"
    if total and posted == 0:
        out += (" Nimic nu a intrat in SIA e-Factura (%d din %d) — "
                "actiunea se poate repeta." % (posted, total))
    elif posted:
        out += (" ATENTIE: %d din %d au INTRAT deja in SIA e-Factura — "
                "nu repetati actiunea, verificati pe portal." % (posted, total))
    return out
