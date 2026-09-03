"""BIRO26 — service (maintenance) functions for the back-office.

RO: Registru DINAMIC de functii de serviciu: lista vine din tabelul
    YBIRO_SERVICE_FUNCTIONS, deci o functie noua se adauga printr-un simplu
    INSERT, fara modificari de cod. Prima functie: exportul in CSV al
    cardurilor de marfa cu text stricat de charset-ul bazei (CL8MSWIN1251).
EN: DYNAMIC registry of service functions: the list comes from the
    YBIRO_SERVICE_FUNCTIONS table, so adding a new one is a plain INSERT with
    no code change. First function: CSV export of product cards whose text was
    mangled by the DB charset (CL8MSWIN1251).

Securitate / Security: se executa DOAR interogari SELECT stocate in registru
(administrate din baza), niciodata SQL primit de la client.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows, _result

# RO: doar SELECT, o singura instructiune / EN: SELECT only, single statement
_SELECT_ONLY = re.compile(r"^\s*select\s", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|"
    r"execute|begin|declare)\b", re.IGNORECASE)

_LANGS = ("ro", "ru", "en")


class Biro26Services:
    """RO: strat de acces pentru functiile de serviciu / EN: service-function access layer."""

    # ── registry ──

    @staticmethod
    def list_functions(lang: str = "ro") -> Dict[str, Any]:
        """RO: lista functiilor active (dinamica, din BD) / EN: active functions (dynamic)."""
        lang = lang if lang in _LANGS else "ro"
        res = Biro26DB().execute_query(
            "SELECT code, kind, ord, name_ro, name_ru, name_en, "
            "       descr_ro, descr_ru, descr_en, file_name "
            "FROM ybiro_service_functions WHERE enabled = 'Y' ORDER BY ord, code")
        if not res.get("success"):
            return _result(res)
        out: List[Dict[str, Any]] = []
        for r in _rows(res):
            # RO: _rows() intoarce DICTIONARE cu chei mici, nu tuple —
            #     indexarea numerica dadea KeyError: 0 si pagina «Servicii» era
            #     moarta (03.09.2026, ambele contururi).
            out.append({
                "code": r["code"],
                "kind": r["kind"],
                "ord": r["ord"],
                "name": r.get("name_" + lang) or r.get("name_ro"),
                "descr": r.get("descr_" + lang) or r.get("descr_ro"),
                "file_name": r.get("file_name"),
                # RO: numarul de randuri se cere separat (poate fi lent)
                # EN: row count is fetched separately (can be slow)
                "count_url": f"/api/biro26/services/{r['code']}/count",
                "csv_url": f"/api/biro26/services/{r['code']}/csv",
            })
        return {"success": True, "data": out}

    @staticmethod
    def _get_sql(code: str) -> Optional[Dict[str, Any]]:
        res = Biro26DB().execute_query(
            "SELECT src_sql, file_name, kind FROM ybiro_service_functions "
            "WHERE code = :c AND enabled = 'Y'", {"c": code})
        rows = _rows(res)
        if not rows:
            return None
        sql, file_name, kind = rows[0]["src_sql"], rows[0]["file_name"], rows[0]["kind"]
        if isinstance(sql, str) is False:          # CLOB-safe
            sql = str(sql)
        sql = sql.strip().rstrip(";")
        # RO: paza — doar SELECT / EN: guard — SELECT only
        if not _SELECT_ONLY.match(sql) or _FORBIDDEN.search(sql):
            return None
        return {"sql": sql, "file_name": file_name or code, "kind": kind}

    # ── actions ──

    @staticmethod
    def count(code: str) -> Dict[str, Any]:
        """RO: cite randuri va produce functia / EN: how many rows the function yields."""
        spec = Biro26Services._get_sql(code)
        if not spec:
            return {"success": False, "error": "unknown or unsafe function"}
        res = Biro26DB().execute_query(
            f"SELECT COUNT(*) CNT FROM ({spec['sql']})")
        rows = _rows(res)
        if not res.get("success"):
            return _result(res)
        return {"success": True, "data": {"code": code,
                                          "count": rows[0]["cnt"] if rows else 0}}

    @staticmethod
    def to_csv(code: str) -> Dict[str, Any]:
        """RO: executa functia si intoarce CSV (text) / EN: run and return CSV text."""
        spec = Biro26Services._get_sql(code)
        if not spec:
            return {"success": False, "error": "unknown or unsafe function"}
        res = Biro26DB().execute_query(spec["sql"])
        if not res.get("success"):
            return _result(res)
        buf = io.StringIO()
        # RO: ';' + BOM => Excel (RO/RU) deschide corect / EN: Excel-friendly
        writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL,
                            lineterminator="\r\n")
        cols = res.get("columns") or []
        if cols:
            writer.writerow(cols)
        # RO: _rows() da dictionare — iterat direct, ar scrie NUMELE
        #     coloanelor pe fiecare rind; valorile vin din tuplele brute,
        #     in ordinea lui `columns`.
        for row in res.get("data") or []:
            writer.writerow(["" if v is None else v for v in row])
        return {"success": True,
                "csv": buf.getvalue(),
                "file_name": f"{spec['file_name']}.csv"}
