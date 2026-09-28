"""Biro26 — выгрузка кредитных документов в Google Sheets.

RO: sincronizare INTR-UN SINGUR SENS: Oracle -> Google Sheets (ERP ramine
    sursa adevarului). Doua foi: capetele documentelor si rindurile lor.
    Autentificare: cont de serviciu (JWT RS256 -> access token), fara OAuth
    interactiv, fara `gspread`/`google-api-python-client` — doar `requests`
    si `cryptography`, care sint deja in venv.
EN: one-way sync Oracle -> Google Sheets via a service account (JWT RS256);
    no external Google libraries, no interactive OAuth.

Реквизиты берутся из окружения (.env), а НЕ из репозитория:
    GSHEET_SA_JSON        путь к JSON-ключу сервисного аккаунта (проще всего)
  или по отдельности:
    GSHEET_SA_EMAIL, GSHEET_SA_PRIVATE_KEY
    GSHEET_SPREADSHEET_ID, GSHEET_SHEET_MASTER, GSHEET_SHEET_DETAIL

Описание подключения: docs/Biro26/GOOGLE_SHEETS_CREDITE.md
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Any, Dict, List, Optional

import requests

from models.biro26_credit import Biro26Credit

TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
API = "https://sheets.googleapis.com/v4/spreadsheets"
TIMEOUT = 45

MASTER_COLS = ["cod", "nrmanual", "datamanual", "order_nrmanual", "client_cod",
               "client_name", "nnp", "idnp", "phone", "adresa", "birth_date",
               "org_id", "org_name", "plan_name", "months", "avans", "amount",
               "credit_price", "monthly", "provider_code", "ext_ref",
               "api_status", "req_id", "lines", "created"]
DETAIL_COLS = ["nrdoc", "cod1", "sc", "codvechi", "denumirea", "um", "cant",
               "pret", "pret_credit", "suma", "txtcoment"]


def _b64(raw: bytes) -> str:
    """base64url без набивки — так требует JWT."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def config() -> Dict[str, str]:
    """RO: reqvizitele din mediu. Cheia JSON are prioritate — nu cere escaping."""
    cfg = {"spreadsheet_id": os.getenv("GSHEET_SPREADSHEET_ID", "").strip(),
           "master": os.getenv("GSHEET_SHEET_MASTER", "Credite").strip(),
           "detail": os.getenv("GSHEET_SHEET_DETAIL", "Credite_linii").strip(),
           "email": os.getenv("GSHEET_SA_EMAIL", "").strip(),
           "key": os.getenv("GSHEET_SA_PRIVATE_KEY", "")}
    path = os.getenv("GSHEET_SA_JSON", "").strip()
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                j = json.load(f)
            cfg["email"] = j.get("client_email") or cfg["email"]
            cfg["key"] = j.get("private_key") or cfg["key"]
        except Exception:                              # noqa: BLE001
            pass
    # RO: in .env cheia se scrie pe un rind, cu \n literal
    cfg["key"] = (cfg["key"] or "").replace("\\n", "\n").strip()
    return cfg


def _check(cfg: Dict[str, str]) -> Optional[str]:
    """RO: verifica reqvizitele INAINTE de a lovi reteaua — mesaj clar in loc de 400."""
    if not cfg["spreadsheet_id"]:
        return "GSHEET_SPREADSHEET_ID nu este setat"
    if not cfg["email"] or not cfg["key"]:
        return "contul de serviciu nu este configurat (GSHEET_SA_JSON sau GSHEET_SA_EMAIL + GSHEET_SA_PRIVATE_KEY)"
    if "BEGIN PRIVATE KEY" not in cfg["key"] or "END PRIVATE KEY" not in cfg["key"]:
        return "GSHEET_SA_PRIVATE_KEY nu arată ca o cheie PEM întreagă"
    # RO: o cheie RSA 2048 are ~1600+ caractere. Una scurtata cu «...» (cum vine
    #     dintr-un exemplu de documentatie) nu poate semna nimic — o prindem aici,
    #     ca eroarea sa fie de configurare, nu «invalid_grant» de la Google.
    if "..." in cfg["key"] or len(cfg["key"]) < 800:
        return "GSHEET_SA_PRIVATE_KEY pare trunchiată (exemplu, nu cheie reală)"
    return None


def _access_token(cfg: Dict[str, str]) -> tuple[str, Optional[str]]:
    """RO: JWT semnat RS256 -> access token. (token, eroare)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    now = int(time.time())
    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64(json.dumps({
        "iss": cfg["email"], "scope": SCOPE, "aud": TOKEN_URL,
        "iat": now, "exp": now + 3600}).encode())
    signing_input = f"{header}.{claims}".encode()
    try:
        key = serialization.load_pem_private_key(cfg["key"].encode(), password=None)
        sig = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    except Exception as e:                             # noqa: BLE001
        return "", f"cheia privată nu poate fi citită: {e}"
    jwt = f"{header}.{claims}.{_b64(sig)}"
    try:
        r = requests.post(TOKEN_URL, timeout=TIMEOUT, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt})
    except requests.RequestException as e:
        return "", str(e)
    if r.status_code >= 400:
        return "", f"HTTP {r.status_code}: {(r.text or '')[:200]}"
    tok = (r.json() or {}).get("access_token") or ""
    return (tok, None) if tok else ("", "Google nu a returnat access_token")


def _cell(v: Any) -> Any:
    """RO: datele Oracle vin ISO ('2026-08-01T00:00:00') — in foaie se pune data."""
    if v is None:
        return ""
    if isinstance(v, str) and len(v) == 19 and v[10] == "T":
        return v[:10] if v.endswith("T00:00:00") else v.replace("T", " ")
    return v


def _write(tok: str, sid: str, sheet: str, rows: List[List[Any]]) -> Optional[str]:
    """RO: curata foaia si scrie totul din A1. Intoarce eroarea sau None."""
    h = {"Authorization": f"Bearer {tok}"}
    rng = f"{sheet}!A1:ZZ"
    try:
        c = requests.post(f"{API}/{sid}/values/{rng}:clear", headers=h, timeout=TIMEOUT)
        if c.status_code >= 400:
            return f"clear {sheet}: HTTP {c.status_code}: {(c.text or '')[:200]}"
        u = requests.put(f"{API}/{sid}/values/{sheet}!A1",
                         headers=h, timeout=TIMEOUT,
                         params={"valueInputOption": "RAW"},
                         json={"values": rows})
        if u.status_code >= 400:
            return f"update {sheet}: HTTP {u.status_code}: {(u.text or '')[:200]}"
    except requests.RequestException as e:
        return f"{sheet}: {e}"
    return None


class Biro26GSheets:
    """Выгрузка кредитных документов в Google Sheets."""

    @staticmethod
    def status() -> Dict[str, Any]:
        """RO: e configurata sincronizarea? Fara secrete in raspuns."""
        cfg = config()
        err = _check(cfg)
        return {"success": True, "data": {
            "configured": err is None, "reason": err,
            "spreadsheet_id": cfg["spreadsheet_id"],
            "sheets": [cfg["master"], cfg["detail"]],
            "account": cfg["email"]}}

    @staticmethod
    def sync() -> Dict[str, Any]:
        """RO: rescrie AMBELE foi din VMDB_CREDITE_M / VMDB_CREDITE_D."""
        cfg = config()
        err = _check(cfg)
        if err:
            return {"success": False, "error": err}
        docs = Biro26Credit.documents(limit=5000)
        if not docs.get("success"):
            return docs
        master = docs.get("data") or []
        tok, err = _access_token(cfg)
        if err:
            return {"success": False, "error": err}
        rows_m = [[c.upper() for c in MASTER_COLS]] + \
                 [[_cell(d.get(c)) for c in MASTER_COLS] for d in master]
        e = _write(tok, cfg["spreadsheet_id"], cfg["master"], rows_m)
        if e:
            return {"success": False, "error": e}
        rows_d: List[List[Any]] = [[c.upper() for c in DETAIL_COLS]]
        for d in master:
            lines = Biro26Credit.document_lines(d["cod"]).get("data") or []
            for ln in lines:
                ln["nrdoc"] = d["cod"]
                rows_d.append([_cell(ln.get(c)) for c in DETAIL_COLS])
        e = _write(tok, cfg["spreadsheet_id"], cfg["detail"], rows_d)
        if e:
            return {"success": False, "error": e}
        return {"success": True, "data": {"master": len(rows_m) - 1,
                                          "detail": len(rows_d) - 1,
                                          "spreadsheet_id": cfg["spreadsheet_id"]}}
