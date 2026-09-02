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
