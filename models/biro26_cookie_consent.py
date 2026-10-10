"""RO: consimtamintul pentru cookie-uri — partea de server (09.10.2026, noua lege
a datelor cu caracter personal).

Vizitatorul alege in bannerul din static/biro26/cookie-consent.js; alegerea sta in
cookie-ul `op_consent` = "v1.a0.f1.m0.<unix>" (a = analitice, f = functionale,
m = marketing). Serverul pune cookie-urile de atributie a reclamelor
(models/biro26_social.py: op_vid, op_attr) DOAR cind alegerea contine `m1`.
Fara acord — sau dupa retragerea lui — valorile existente se golesc: un ID gol nu mai
identifica pe nimeni, iar statistica de atributie nu se mai scrie.
Versiunea trebuie sa fie aceeasi ca CONSENT_VERSION din cookie-consent.js.
EN: server side of the cookie consent — attribution cookies only with marketing consent.
Documentatie: docs/Biro26/COOKIE_CONSIMTAMINT_2026-10-09.md
"""
from typing import Any, Dict, Optional

CONSENT_COOKIE = "op_consent"
CONSENT_VERSION = "v1"
MARKETING_COOKIES = ("op_vid", "op_attr")


def parse(value: Optional[str]) -> Dict[str, bool]:
    """RO: "v1.a1.f0.m1.1790000000" -> {"a": True, "f": False, "m": True}.
    Versiune necunoscuta sau gunoi -> totul False (nu exista acord)."""
    out = {"a": False, "f": False, "m": False}
    parts = str(value or "").split(".")
    if not parts or parts[0] != CONSENT_VERSION:
        return out
    for p in parts[1:4]:
        if len(p) == 2 and p[0] in out:
            out[p[0]] = p[1] == "1"
    return out


def marketing_allowed(req) -> bool:
    try:
        return parse(req.cookies.get(CONSENT_COOKIE))["m"]
    except Exception:                                        # noqa: BLE001
        return False


def wipe_marketing(req) -> Optional[Dict[str, Any]]:
    """RO: fara acord: golim cookie-urile de atributie care au apucat sa fie scrise
    (inainte de banner sau inainte de retragerea acordului). None = nimic de facut."""
    try:
        stale = {n: "" for n in MARKETING_COOKIES if req.cookies.get(n)}
    except Exception:                                        # noqa: BLE001
        return None
    return {"set_cookies": stale} if stale else None
