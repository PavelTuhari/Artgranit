"""Controllerul modulului Partner API: autentificare, throttle, validare.

RO: fiecare interogare Oracle trece printr-un subproces thick (~0,4 s), deci
token-ul verificat se tine 60 s intr-un cache in memorie — a doua cerere a
partenerului nu mai plateste drumul la baza. Limita de debit: 120 de cereri
pe minut per partener (numarata in memorie, per proces — suficient pentru
protectie, fara inca un drum la baza).
EN: token cache (60 s) + in-memory per-partner throttle (120 req/min).
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from flask import request

from modules.partner import rules
from modules.partner.store import PartnerStore

RATE_LIMIT_PER_MIN = 120
_token_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_rate: Dict[int, list] = {}


class PartnerController:

    # ── autentificare ──────────────────────────────────────────────────
    @staticmethod
    def auth_token(d: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        username = str(d.get("username") or d.get("email") or "").strip()
        password = str(d.get("password") or "")
        p = PartnerStore.partner_by_email(username)
        if not p or not rules.verify_password(password, p.get("pwd_hash") or ""):
            PartnerStore.log(None, "auth_fail", username[:100])
            return rules.error_body("Invalid credentials."), 401
        if str(p.get("enabled")) != "1":
            return rules.error_body("Account disabled."), 403
        pair = PartnerStore.tokens_issue(int(p["id"]))
        PartnerStore.log(int(p["id"]), "auth_ok", username[:100])
        return {
            "access_token": pair["access"],
            "refresh_token": pair["refresh"],
            "expires_in": rules.ACCESS_TTL_S,
            "token_type": "Bearer",
            "user_email": p["email"],
            "user_id": int(p["id"]),
        }, 200

    @staticmethod
    def auth_refresh(d: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        token = str(d.get("refresh_token") or "")
        row = PartnerStore.token_lookup(token, "refresh")
        if not row:
            return rules.error_body("Invalid or expired refresh token."), 401
        # RO: rotatie — refresh-ul folosit se revoca, iese pereche noua
        PartnerStore.token_revoke(token)
        pair = PartnerStore.tokens_issue(int(row["partner_id"]))
        return {
            "access_token": pair["access"],
            "refresh_token": pair["refresh"],
            "expires_in": rules.ACCESS_TTL_S,
            "token_type": "Bearer",
        }, 200

    @staticmethod
    def auth_revoke() -> Tuple[Dict[str, Any], int]:
        partner = PartnerController.current_partner()
        if not partner:
            return rules.error_body("Unauthenticated."), 401
        PartnerStore.tokens_revoke_all(int(partner["partner_id"]))
        _token_cache.clear()
        PartnerStore.log(int(partner["partner_id"]), "revoke")
        return {"message": "All tokens revoked."}, 200

    # ── garda cererilor API ────────────────────────────────────────────
    @staticmethod
    def current_partner() -> Optional[Dict[str, Any]]:
        """RO: partenerul din spatele cererii (Authorization: Bearer sau
        X-API-Token), cu cache de 60 s. EN: resolve the calling partner."""
        auth = request.headers.get("Authorization", "")
        token = (auth[7:].strip() if auth.startswith("Bearer ")
                 else request.headers.get("X-API-Token", "").strip())
        if not token:
            return None
        now = time.time()
        hit = _token_cache.get(token)
        if hit and hit[0] > now:
            return hit[1]
        row = PartnerStore.token_lookup(token, "access")
        if not row:
            return None
        partner = {"partner_id": int(row["partner_id"]),
                   "email": row["email"],
                   "univers_cod": int(row["univers_cod"])}
        _token_cache[token] = (now + 60, partner)
        if len(_token_cache) > 500:                # igiena memoriei
            for k in [k for k, v in _token_cache.items() if v[0] <= now]:
                _token_cache.pop(k, None)
        return partner

    @staticmethod
    def throttled(partner_id: int) -> bool:
        now = time.time()
        window = _rate.setdefault(partner_id, [])
        window[:] = [t for t in window if t > now - 60]
        if len(window) >= RATE_LIMIT_PER_MIN:
            return True
        window.append(now)
        return False
