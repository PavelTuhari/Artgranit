"""Regulile pentru angajati — pure, fara baza de date.

RO: cerinta proprietarului (10.09.2026): angajatii ii inregistreaza
administratorul; in lista se vad data inregistrarii, dezactivarea contului,
parola standard cu recuperare, e-mailul si telefonul.

Utilizatorul REAL ramine cel al ERP-ului (nodul din arborele A$ADM/A$ADP),
deci regulile de aici respecta ce cere `a$util.login`:
  * `USERNAME` e cautat cu UPPER(...) -> numele trebuie sa fie unic
    indiferent de registru si fara spatii (altfel «duplicated» sau logare
    imposibila);
  * contul se blocheaza cu proprietatea `Enabled = false` — deci
    «dezactivare» inseamna exact ce intelege ERP-ul, nu un cimp propriu;
  * parola trece prin `a$util.set_passwd`, care are propriile verificari;
    de aceea parola standard generata aici e destul de lunga si mixta.
EN: pure rules for employee accounts backed by the UNA config tree.
"""
from __future__ import annotations

import re
import secrets
from typing import Any, Dict, List, Optional

# RO: numele de logare — litere latine, cifre, punct, minus, underscore.
#     Fara spatii si fara chirilica: baza e CL8MSWIN1251 si numele intra in
#     UPPER(...) din a$util.login.
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{2,49}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")
PHONE_RE = re.compile(r"^[+0-9][0-9 ()./-]{5,29}$")

# RO: alfabet fara caractere care se confunda la dictare (0/O, 1/l/I)
_PWD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
PWD_LEN = 10

ACTIONS = ("created", "updated", "enabled", "disabled", "password", "synced")


def gen_password(length: int = PWD_LEN) -> str:
    """RO: parola standard pentru un cont nou sau pentru recuperare.
    Se arata administratorului o singura data — in baza ramine doar ce scrie
    `a$util.set_passwd` (deschisa sau codificata, dupa setarile ERP-ului)."""
    n = max(8, int(length or PWD_LEN))
    return "".join(secrets.choice(_PWD_ALPHABET) for _ in range(n))


def check_username(name: Optional[str]) -> str:
    v = (name or "").strip()
    if not USERNAME_RE.match(v):
        raise ValueError("username: litere latine, cifre, . _ -, 3..50 semne, "
                         "incepe cu litera, fara spatii")
    return v


def check_optional(email: Optional[str], phone: Optional[str]) -> None:
    e = (email or "").strip()
    p = (phone or "").strip()
    if e and not EMAIL_RE.match(e):
        raise ValueError("email: adresa nu pare corecta")
    if p and not PHONE_RE.match(p):
        raise ValueError("phone: numar nu pare corect")


def check_password(pwd: Optional[str]) -> str:
    v = (pwd or "").strip()
    if len(v) < 6:
        raise ValueError("password: cel putin 6 semne")
    if len(v) > 60:
        raise ValueError("password: prea lunga")
    return v


def node_name(user_id: Optional[int], full_name: Optional[str], username: str) -> str:
    """RO: NAME0 al nodului, in formatul folosit deja in arbore:
    «51 Gherganova Janna» — numarul utilizatorului si numele."""
    who = (full_name or username or "").strip()
    return ("%s %s" % (user_id, who)).strip() if user_id else who


def sort_key(field: str) -> str:
    """RO: coloana de sortare a listei; necunoscut -> nume."""
    return {"username": "USERNAME", "full_name": "FULL_NAME", "user_id": "USER_ID",
            "reg_date": "REG_DATE", "enabled": "ENABLED"}.get(field or "", "USERNAME")


def summary(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    return {"total": len(rows),
            "active": sum(1 for r in rows if r.get("enabled")),
            "disabled": sum(1 for r in rows if not r.get("enabled")),
            "admins": sum(1 for r in rows if r.get("is_admin")),
            "with_email": sum(1 for r in rows if (r.get("email") or "").strip()),
            "with_phone": sum(1 for r in rows if (r.get("phone") or "").strip())}
