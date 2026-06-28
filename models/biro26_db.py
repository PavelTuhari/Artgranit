"""Biro26 module — OfficePlus ERP access from the main (thin-mode) Flask app.

The OfficePlus ERP is Oracle 11g and needs python-oracledb THICK mode, which is a
whole-process switch that would break the main app's thin cloud-wallet connection
(production nufarul.eminescu.md). So Biro26DB does NOT connect in-process: it spawns
an isolated thick-mode subprocess worker (models/biro26_worker.py) per operation and
exchanges JSON over stdin/stdout. The main process never enables thick mode.

Method contract mirrors models.database.DatabaseModel so the store/controller layers
are identical to other modules:
    execute_query -> {success, data, columns, rowcount, message}
    execute_dml   -> {success, rowcount, message}
    call_proc     -> {success, output_lines, message}
    execute_script-> {success, results, message}   (multiple statements, one tx)
    test_connection -> {success, version, error}

Usable as a context manager for parity with DatabaseModel (`with Biro26DB() as db:`),
but there is no persistent connection — each call is its own subprocess/transaction.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKER = os.path.join(_PROJECT_ROOT, "models", "biro26_worker.py")
_TIMEOUT = int(os.environ.get("BIRO26_WORKER_TIMEOUT", "300"))


class Biro26DB:
    """Subprocess-backed accessor for the OfficePlus ERP (Oracle 11g, thick mode)."""

    def __enter__(self) -> "Biro26DB":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    # -- transport ----------------------------------------------------
    def _call(self, req: Dict[str, Any]) -> Dict[str, Any]:
        try:
            proc = subprocess.run(
                [sys.executable, _WORKER],
                input=json.dumps(req),
                capture_output=True,
                text=True,
                cwd=_PROJECT_ROOT,
                timeout=_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return {"success": False, "message": f"worker timeout after {_TIMEOUT}s"}
        except Exception as e:
            return {"success": False, "message": f"worker spawn failed: {e}"}
        if proc.returncode != 0:
            return {"success": False,
                    "message": f"worker exit {proc.returncode}: {(proc.stderr or '')[:500]}"}
        try:
            return json.loads(proc.stdout)
        except Exception:
            return {"success": False,
                    "message": f"bad worker output: {(proc.stdout or '')[:300]} "
                               f"{(proc.stderr or '')[:300]}"}

    # -- queries ------------------------------------------------------
    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        r = self._call({"op": "query", "sql": sql, "params": params or {}})
        return {
            "success": r.get("success", False),
            "columns": r.get("columns", []),
            "data": [tuple(row) for row in r.get("data", [])],
            "rowcount": r.get("rowcount", 0),
            "message": r.get("message", ""),
        }

    def execute_dml(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        r = self._call({"op": "dml", "sql": sql, "params": params or {}})
        return {"success": r.get("success", False),
                "rowcount": r.get("rowcount", 0),
                "message": r.get("message", "")}

    def call_proc(self, plsql: str, params: Optional[Dict[str, Any]] = None,
                  capture_output: bool = False) -> Dict[str, Any]:
        """Run an anonymous PL/SQL block (optionally capturing DBMS_OUTPUT).

        `plsql` is a full block, e.g. "BEGIN YBIRO_Import_Marfa.validate_input; END;".
        Set package g_* vars in the SAME block so session state is consistent — the
        worker uses one connection for the whole block.
        """
        r = self._call({"op": "plsql", "plsql": plsql, "params": params or {},
                        "capture_output": capture_output})
        return {"success": r.get("success", False),
                "output_lines": r.get("output_lines", []),
                "message": r.get("message", "")}

    def execute_script(self, statements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run several statements in ONE transaction (atomic multi-statement ops).

        Each statement: {"sql": str, "params": dict, "kind": "query"|"dml"}.
        Returns {success, results:[{columns,data,rowcount} | {rowcount}], message}.
        """
        r = self._call({"op": "script", "statements": statements})
        return {"success": r.get("success", False),
                "results": r.get("results", []),
                "message": r.get("message", "")}

    def test_connection(self) -> Dict[str, Any]:
        r = self._call({"op": "test"})
        return {"success": r.get("success", False),
                "version": r.get("version"),
                "error": r.get("message")}
