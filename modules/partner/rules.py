"""Reguli pure ale modulului Partner API — fara importuri de BD.

RO: tot ce se poate testa fara wallet Oracle: parole (PBKDF2), generarea si
amprentarea token-urilor, formatul raspunsurilor in stilul Ultra B2B API,
maparea produsului ERP -> obiectul public al API-ului.
EN: pure, DB-free logic — password hashing, token fingerprints, Ultra-shaped
response mapping. Unit-tested without a wallet.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any, Dict, List, Optional

# RO: duratele de viata — identice cu Ultra B2B API V1
# EN: token lifetimes — same as Ultra's
ACCESS_TTL_S = 3600                 # access token: 1 ora
REFRESH_TTL_S = 30 * 86400          # refresh token: 30 de zile
PBKDF2_ITERATIONS = 200_000


# ── parole ─────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """RO: 'pbkdf2$<iteratii>$<sare>$<hash>' — totul intr-o singura coloana.
    EN: self-describing PBKDF2 string, one column."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iters, salt, digest = (stored or "").split("$", 3)
        if scheme != "pbkdf2":
            return False
        calc = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iters)).hex()
        return hmac.compare_digest(calc, digest)
    except (ValueError, AttributeError):
        return False


# ── token-uri ──────────────────────────────────────────────────────────
def new_token() -> str:
    """RO: token opac, ~64 de caractere URL-safe. EN: opaque bearer token."""
    return secrets.token_urlsafe(48)


def token_hash(token: str) -> str:
    """RO: in baza se tine DOAR amprenta SHA-256 — un dump al tabelei nu da
    acces la API. EN: only the SHA-256 fingerprint is stored."""
    return hashlib.sha256((token or "").encode()).hexdigest()


# ── forma raspunsurilor (stilul Ultra) ─────────────────────────────────
def error_body(message: str,
               errors: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
    """RO: formatul de eroare Ultra: {"message": ..., "errors": {...}}."""
    body: Dict[str, Any] = {"message": message}
    if errors:
        body["errors"] = errors
    return body


def map_product(row: Dict[str, Any]) -> Dict[str, Any]:
    """RO: rindul grilei ERP -> obiectul public al API-ului, cu ACEEASI
    structura ca la Ultra (ultra_code -> code, ultra_uuid -> uuid; restul
    cimpurilor poarta aceleasi nume, ca un client scris pentru Ultra sa se
    porteze printr-o redenumire).
    EN: ERP grid row -> public product object, Ultra-shaped."""
    g = row.get
    images = [u for u in [g("image")] if u]
    price = _num(g("retail1"))
    user_price = _num(g("angro"))
    return {
        "code": str(g("codvechi") or g("cod") or ""),
        "uuid": str(g("cod") or ""),
        "product_name": {"ro": g("denumirea") or "",
                         "ru": g("namerus") or g("denumirea") or ""},
        "description": g("denum_full") or None,
        "description_by_language": {"ro": g("denum_full"),
                                    "ru": g("denum_full_ru")},
        "quantity": int(g("avail_cant") or 0),
        "image_urls": images,
        "barcode": g("barcode"),
        "brand": ({"name": g("brand")} if g("brand") else None),
        "category": ({"name": {"ro": g("categorie") or g("grupa")},
                      "hierarchy": [x for x in (g("grupa"), g("categorie")) if x]}
                     if (g("grupa") or g("categorie")) else None),
        "user_price": user_price,
        "fixed_price": price,
        "price_d": None,
        "promo_b2b": None,
        "updated_at": None,
    }


def map_quantity(row: Dict[str, Any]) -> Dict[str, Any]:
    g = row.get
    return {
        "code": str(g("codvechi") or g("cod") or ""),
        "uuid": str(g("cod") or ""),
        "product_name": {"ro": g("denumirea") or ""},
        "quantity": int(g("avail_cant") or 0),
    }


def _num(v: Any) -> Optional[float]:
    try:
        f = float(str(v).replace(",", "."))
        return round(f, 2)
    except (TypeError, ValueError):
        return None


def validate_order(payload: Dict[str, Any]) -> Dict[str, List[str]]:
    """RO: validarea cererii POST /api/order (forma Ultra: delivery, payment,
    products[{code|uuid, quantity}]). Intoarce {cimp: [mesaje]} — gol = valid.
    EN: Ultra-shaped order validation; empty dict = valid."""
    errors: Dict[str, List[str]] = {}
    if payload.get("delivery") not in ("pickup", "delivery"):
        errors["delivery"] = ["must be one of: pickup, delivery"]
    if payload.get("payment") not in ("cash", "transfer", "card"):
        errors["payment"] = ["must be one of: cash, transfer, card"]
    products = payload.get("products")
    if not isinstance(products, list) or not (1 <= len(products) <= 1000):
        errors["products"] = ["must be a list of 1..1000 items"]
    else:
        for i, p in enumerate(products):
            if not isinstance(p, dict) or not (p.get("code") or p.get("uuid")):
                errors[f"products.{i}"] = ["code or uuid is required"]
                continue
            try:
                if int(p.get("quantity") or 0) < 1:
                    raise ValueError
            except (TypeError, ValueError):
                errors[f"products.{i}.quantity"] = ["must be an integer >= 1"]
    return errors
