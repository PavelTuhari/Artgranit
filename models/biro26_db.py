"""Biro26 module — Oracle connection to the OfficePlus ERP DB.

Separate from the wallet-based DatabaseModel: thin mode, direct DSN.
Default target: officeplus@orange.una.md:4024/cloudbd.world.
NLS is forced on connect (ENGLISH/AMERICA) to avoid ORA-12705 from the
macOS en_MD locale and to make price parsing deterministic.

Contract mirrors models.database.DatabaseModel:
    {success, data, columns, rowcount, message}
"""
from __future__ import annotations

import oracledb
from typing import Any, Dict, List, Optional

from config import Config


class Biro26DB:
    """Context-manager connection to the OfficePlus ERP database."""

    def __init__(self):
        self.connection: Optional[oracledb.Connection] = None

    # -- NLS ----------------------------------------------------------
    def _nls_statements(self) -> List[str]:
        return [
            f"ALTER SESSION SET NLS_LANGUAGE='{Config.BIRO26_NLS_LANGUAGE}'",
            f"ALTER SESSION SET NLS_TERRITORY='{Config.BIRO26_NLS_TERRITORY}'",
            "ALTER SESSION SET NLS_NUMERIC_CHARACTERS='. '",
        ]

    # -- lifecycle ----------------------------------------------------
    def __enter__(self) -> "Biro26DB":
        self.connection = oracledb.connect(
            user=Config.BIRO26_DB_USER,
            password=Config.BIRO26_DB_PASSWORD,
            dsn=Config.BIRO26_DB_DSN,
        )
        with self.connection.cursor() as cur:
            for stmt in self._nls_statements():
                cur.execute(stmt)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            try:
                if exc_type:
                    self.connection.rollback()
            finally:
                self.connection.close()

    # -- queries ------------------------------------------------------
    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = {"success": False, "data": [], "columns": [], "rowcount": 0, "message": ""}
        try:
            with self.connection.cursor() as cur:
                cur.execute(sql, params or {})
                if cur.description:
                    result["columns"] = [d[0] for d in cur.description]
                    result["data"] = cur.fetchall()
                    result["rowcount"] = len(result["data"])
                result["success"] = True
        except Exception as e:
            result["message"] = str(e)
        return result

    def execute_dml(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            with self.connection.cursor() as cur:
                cur.execute(sql, params or {})
                rc = cur.rowcount
            self.connection.commit()
            return {"success": True, "rowcount": rc}
        except Exception as e:
            self.connection.rollback()
            return {"success": False, "rowcount": 0, "message": str(e)}

    def call_proc(self, plsql: str, params: Optional[Dict[str, Any]] = None,
                  capture_output: bool = False) -> Dict[str, Any]:
        """Run an anonymous PL/SQL block. If capture_output, return DBMS_OUTPUT lines.

        `plsql` is a full block, e.g.
            "BEGIN YBIRO_Import_Marfa.validate_input; END;"
        Set package g_* vars in the same block so session state is consistent.
        """
        lines: List[str] = []
        try:
            with self.connection.cursor() as cur:
                if capture_output:
                    cur.callproc("DBMS_OUTPUT.ENABLE", [None])
                cur.execute(plsql, params or {})
                if capture_output:
                    chunk = cur.var(str, 32767)  # avoid truncating long DBMS_OUTPUT lines
                    status = cur.var(int)
                    while True:
                        cur.callproc("DBMS_OUTPUT.GET_LINE", [chunk, status])
                        if status.getvalue() != 0:
                            break
                        lines.append(chunk.getvalue() or "")
            self.connection.commit()
            return {"success": True, "output_lines": lines}
        except Exception as e:
            self.connection.rollback()
            return {"success": False, "output_lines": lines, "message": str(e)}

    def test_connection(self) -> Dict[str, Any]:
        try:
            r = self.execute_query(
                "SELECT banner FROM v$version WHERE ROWNUM = 1")
            ver = r["data"][0][0] if r.get("data") else None
            return {"success": r["success"], "version": ver, "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}
