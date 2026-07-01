"""Biro26 source definitions — register any read-only SELECT as an import source.

The SELECT is materialized as a view V_BIRO26_SRC_<name> that the YBIRO package
imports from (g_tbl_goods -> view). All access via the thick subprocess Biro26DB.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows, _result

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|"
    r"begin|declare|call|execute|exec|comment|rename|lock)\b", re.IGNORECASE)


_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def is_safe_select(sql: str) -> bool:
    if not sql or not sql.strip():
        return False
    # strip comments first so they cannot hide ';' or forbidden keywords,
    # and so a ';' inside a comment doesn't trigger a false multi-statement reject
    s = _COMMENTS.sub(" ", sql).strip().rstrip(";").strip()
    if not s or ";" in s:             # only a single statement
        return False
    low = s.lower()
    if not (low.startswith("select") or low.startswith("with")):
        return False
    if _FORBIDDEN.search(s):
        return False
    return True


def view_name_for(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return "V_BIRO26_SRC_" + slug


class Biro26Sources:
    @staticmethod
    def sample(sql: str, limit: int = 20) -> Dict[str, Any]:
        if not is_safe_select(sql):
            return {"success": False, "error": "only a single read-only SELECT is allowed"}
        inner = sql.strip().rstrip(";")
        r = Biro26DB().execute_query(
            f"SELECT * FROM ({inner}) WHERE ROWNUM <= :n", {"n": int(limit)})
        if not r.get("success"):
            return {"success": False, "error": r.get("message")}
        return {"success": True, "columns": list(r.get("columns", [])),
                "data": [list(row) for row in r.get("data", [])]}

    @staticmethod
    def list_sources() -> Dict[str, Any]:
        return _result(Biro26DB().execute_query(
            "SELECT id, name, view_name, md_path, "
            "TO_CHAR(created_at,'DD.MM.YYYY HH24:MI') created_at FROM YBIRO_SRC_DEF ORDER BY name"))

    @staticmethod
    def get_source(name: str) -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT id, name, view_name, md_path, select_sql FROM YBIRO_SRC_DEF WHERE name=:n",
            {"n": name}))
        return {"success": True, "data": rows[0]} if rows else {"success": False, "error": "not found"}

    @staticmethod
    def create_source(name: str, sql: str, md_path: Optional[str] = None) -> Dict[str, Any]:
        if not is_safe_select(sql):
            return {"success": False, "error": "only a single read-only SELECT is allowed"}
        from models.biro26_oracle_store import _is_ident
        if not _is_ident(name):
            return {"success": False, "error": "invalid source name (use letters/digits/_)"}
        view = view_name_for(name)
        inner = sql.strip().rstrip(";")
        db = Biro26DB()
        # wrap the body in a subquery: only something that parses as a SELECT
        # survives, so the SELECT can't morph the CREATE VIEW into other DDL/DML
        cv = db.execute_dml(f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM ({inner})")
        if not cv.get("success"):
            return {"success": False, "error": cv.get("message")}
        res = db.execute_script([
            {"sql": "DELETE FROM YBIRO_SRC_DEF WHERE name=:n", "params": {"n": name}, "kind": "dml"},
            {"sql": "INSERT INTO YBIRO_SRC_DEF(name, select_sql, view_name, md_path) "
                    "VALUES(:n, :s, :v, :m)",
             "params": {"n": name, "s": inner, "v": view, "m": md_path}, "kind": "dml"},
        ])
        if not res.get("success"):
            db.execute_dml(f"DROP VIEW {view}")  # avoid orphaned view on metadata failure
            return {"success": False, "error": res.get("message")}
        return {"success": True, "data": {"name": name, "view_name": view}}

    @staticmethod
    def drop_source(name: str) -> Dict[str, Any]:
        view = view_name_for(name)
        db = Biro26DB()
        db.execute_dml(f"DROP VIEW {view}")  # ignore if missing
        return db.execute_dml("DELETE FROM YBIRO_SRC_DEF WHERE name=:n", {"n": name})
