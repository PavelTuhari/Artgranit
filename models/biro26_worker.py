"""Biro26 thick-mode Oracle worker (runs as an isolated subprocess).

WHY A SUBPROCESS: the OfficePlus ERP is Oracle 11g, which python-oracledb can
only reach in THICK mode (Instant Client). Thick mode is a whole-process switch
that breaks the main Flask app's thin cloud-wallet connection (the one production
nufarul.eminescu.md depends on). So all OfficePlus access happens here, in a
short-lived child process that the main (thin) app spawns via models/biro26_db.py.

PROTOCOL: read one JSON request object from stdin, write one JSON response object
to stdout. Requests:
  {"op":"test"}
  {"op":"query","sql":..,"params":{..}}              -> {success,columns,data,rowcount}
  {"op":"dml","sql":..,"params":{..}}                -> {success,rowcount} (commits)
  {"op":"plsql","plsql":..,"params":{..},"capture_output":bool}
                                                     -> {success,output_lines} (commits)
  {"op":"script","statements":[{"sql":..,"params":{..},"kind":"query|dml"}]}
                                                     -> {success,results:[..]} (one tx, commits)
All responses include "success"; on failure also "message".
Messages/comments in DB code stay RO+EN per project rule; this is app code (RU/EN ok).
"""
from __future__ import annotations

import datetime
import decimal
import json
import os
import sys

# Make `from config import Config` work regardless of cwd.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import oracledb  # noqa: E402
from config import Config  # noqa: E402


def _nls_statements(req=None):
    stmts = [
        f"ALTER SESSION SET NLS_LANGUAGE='{Config.BIRO26_NLS_LANGUAGE}'",
        f"ALTER SESSION SET NLS_TERRITORY='{Config.BIRO26_NLS_TERRITORY}'",
        "ALTER SESSION SET NLS_NUMERIC_CHARACTERS='. '",
    ]
    # RO: format de data optional per-request (ServOuts26/UNITEST are view-uri
    #     cu literali de data impliciti, ex. '1.1.3001' in VPR1D_PRDATE).
    # EN: optional per-request date format (ServOuts26/UNITEST views rely on
    #     implicit date literals, e.g. '1.1.3001' in VPR1D_PRDATE).
    fmt = (req or {}).get("nls_date_format")
    if fmt and fmt.replace(".", "").replace("-", "").replace("/", "").replace(" ", "").isalnum():
        stmts.append(f"ALTER SESSION SET NLS_DATE_FORMAT='{fmt}'")
    return stmts


def _cell(v):
    """Make a fetched value JSON-serializable while keeping numbers numeric."""
    if isinstance(v, decimal.Decimal):
        f = float(v)
        return int(f) if f.is_integer() else f
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return v


def _fetch(cur):
    cols = [d[0] for d in cur.description] if cur.description else []
    data = [[_cell(c) for c in row] for row in cur.fetchall()] if cur.description else []
    return cols, data


def _capture_dbms_output(cur):
    lines = []
    chunk = cur.var(str, 32767)
    status = cur.var(int)
    while True:
        cur.callproc("DBMS_OUTPUT.GET_LINE", [chunk, status])
        if status.getvalue() != 0:
            break
        lines.append(chunk.getvalue() or "")
    return lines


def _exec(cur, sql, params):
    """RO: executa cu suport pentru parametri binari prin JSON —
    {"__b64__": "..."} devine bytes legat explicit ca BLOB (peste 32KB
    Oracle l-ar lega altfel ca LONG -> ORA-01461); ex. atasarea PDF-urilor
    in VMDB_DOCS_OLE.
    EN: execute with binary-param support over the JSON contract —
    {"__b64__": "..."} becomes bytes explicitly bound as BLOB (beyond 32KB
    Oracle would otherwise bind LONG -> ORA-01461); e.g. attaching PDFs
    into VMDB_DOCS_OLE."""
    import base64
    out, blob_keys = {}, {}
    for k, v in (params or {}).items():
        if isinstance(v, dict) and "__b64__" in v:
            out[k] = base64.b64decode(v["__b64__"])
            blob_keys[k] = oracledb.DB_TYPE_BLOB
        else:
            out[k] = v
    if blob_keys:
        cur.setinputsizes(**blob_keys)
    cur.execute(sql, out)


def _handle(conn, req):
    op = req.get("op")
    cur = conn.cursor()
    for stmt in _nls_statements(req):
        cur.execute(stmt)

    if op == "test":
        cur.execute("SELECT banner FROM v$version WHERE ROWNUM = 1")
        row = cur.fetchone()
        return {"success": True, "version": row[0] if row else None}

    if op == "query":
        _exec(cur, req["sql"], req.get("params"))
        cols, data = _fetch(cur)
        return {"success": True, "columns": cols, "data": data, "rowcount": len(data)}

    if op == "dml":
        _exec(cur, req["sql"], req.get("params"))
        rc = cur.rowcount
        conn.commit()
        return {"success": True, "rowcount": rc}

    if op == "plsql":
        if req.get("capture_output"):
            cur.callproc("DBMS_OUTPUT.ENABLE", [None])
        _exec(cur, req["plsql"], req.get("params"))
        lines = _capture_dbms_output(cur) if req.get("capture_output") else []
        conn.commit()
        return {"success": True, "output_lines": lines}

    if op == "script":
        results = []
        for st in req.get("statements", []):
            _exec(cur, st["sql"], st.get("params"))
            if st.get("kind") == "query" and cur.description:
                cols, data = _fetch(cur)
                results.append({"columns": cols, "data": data, "rowcount": len(data)})
            else:
                results.append({"rowcount": cur.rowcount})
        conn.commit()
        return {"success": True, "results": results}

    return {"success": False, "message": f"unknown op: {op}"}


def main():
    try:
        req = json.loads(sys.stdin.read() or "{}")
    except Exception as e:
        print(json.dumps({"success": False, "message": f"bad request json: {e}"}))
        return

    try:
        oracledb.init_oracle_client(lib_dir=Config.BIRO26_INSTANT_CLIENT)
    except Exception as e:
        if "already been initialized" not in str(e):
            print(json.dumps({"success": False, "message": f"thick init failed: {e}"}))
            return

    # RO: "auth" optional in request — alte module (ex. ServOuts26/UNITEST)
    #     refolosesc acelasi worker cu credentiale proprii.
    # EN: optional "auth" in the request — other modules (e.g. ServOuts26/
    #     UNITEST) reuse this worker with their own credentials.
    auth = req.get("auth") or {}
    conn = None
    try:
        conn = oracledb.connect(
            user=auth.get("user") or Config.BIRO26_DB_USER,
            password=auth.get("password") or Config.BIRO26_DB_PASSWORD,
            dsn=auth.get("dsn") or Config.BIRO26_DB_DSN,
        )
        out = _handle(conn, req)
    except Exception as e:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        out = {"success": False, "message": str(e)}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
