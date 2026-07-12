"""BIRO26PT web import — store layer over the BIRO26PT_importData package.

RO: Interfata web NU contine logica de import (cerinta proiectului): primeste
    fisiere, ruleaza loader-ul (models/biro26pt_loader.py, subproces thick),
    apeleaza pachetul (dry-run p_commit=FALSE / commit TRUE) si CITESTE
    tabelele de rezultat (BIRO26PT_MAP/STG/LOG) — fara parsarea DBMS_OUTPUT.
EN: The web interface holds NO import business logic (project requirement):
    it accepts files, runs the loader (thick subprocess), calls the package
    (dry-run p_commit=FALSE / commit TRUE) and READS the result tables
    (BIRO26PT_MAP/STG/LOG) directly — no DBMS_OUTPUT parsing.
Spec: /BIRO26/BIRO26PT_WEB_INTERFACE_SPEC.md (§6 SQL adapted to Oracle 11g:
ROWNUM paging instead of OFFSET/FETCH).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
import zipfile
from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows, _result

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOADER = os.path.join(_PROJECT_ROOT, "models", "biro26pt_loader.py")
UPLOAD_ROOT = os.path.join(_PROJECT_ROOT, "uploads", "biro26pt")

ALLOWED_EXT = {".xlsx", ".xls", ".csv"}
MAX_UPLOAD_MB = 50
# RO: numele canonice ale campurilor logice — cum le foloseste pachetul
#     (dictionar BIRO26PT_COLMAP, UPPERCASE). / EN: canonical logical field
#     names as the package uses them (BIRO26PT_COLMAP dictionary, UPPERCASE).
LOGICAL_FIELDS = ["ARTICOL", "DENUMIRE", "ANGRO", "ONLINE", "RETAIL",
                  "VAT", "BARCODE", "URL", "IGNORE"]


class Biro26PTStore:

    # ── phase 1: receive files, run the loader ──

    @staticmethod
    def save_uploads(files: List, zip_mode: bool = False) -> Dict[str, Any]:
        """Store uploaded files (or one zip) into an isolated session folder.
        Whitelisted extensions only; zip entries with '..'/absolute paths or
        service junk (__MACOSX, ~$) are dropped (path-traversal guard)."""
        os.makedirs(UPLOAD_ROOT, exist_ok=True)
        session = uuid.uuid4().hex[:12]
        folder = os.path.join(UPLOAD_ROOT, session)
        os.makedirs(folder)
        saved, total = [], 0
        try:
            for f in files:
                name = os.path.basename(f.filename or "")
                ext = os.path.splitext(name)[1].lower()
                if ext == ".zip":
                    tmp = os.path.join(folder, "_upload.zip")
                    f.save(tmp)
                    total += os.path.getsize(tmp)
                    saved += Biro26PTStore._extract_zip(tmp, folder)
                    os.remove(tmp)
                elif ext in ALLOWED_EXT:
                    if not re.match(r"^[\w .()\[\]&+,%№-]+$", name, re.UNICODE):
                        name = f"file_{len(saved)}{ext}"
                    p = os.path.join(folder, name)
                    f.save(p)
                    total += os.path.getsize(p)
                    saved.append(name)
                # other extensions are silently skipped (whitelist)
            if total > MAX_UPLOAD_MB * 1024 * 1024:
                import shutil
                shutil.rmtree(folder, ignore_errors=True)
                return {"success": False,
                        "error": f"upload exceeds {MAX_UPLOAD_MB} MB"}
            if not saved:
                return {"success": False,
                        "error": "no accepted files (.xlsx/.xls/.csv/.zip)"}
            return {"success": True, "data": {"session": session, "files": saved}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _extract_zip(zpath: str, folder: str) -> List[str]:
        out = []
        with zipfile.ZipFile(zpath) as z:
            for info in z.infolist():
                name = info.filename
                base = os.path.basename(name)
                if (info.is_dir() or name.startswith("/") or ".." in name
                        or "__MACOSX" in name or base.startswith("~$")
                        or base.startswith(".")):
                    continue
                if os.path.splitext(base)[1].lower() not in ALLOWED_EXT:
                    continue
                target = os.path.join(folder, base)
                # RO: doar nume plat, fara cai / EN: flat basename only, no paths
                with z.open(info) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                out.append(base)
        return out

    @staticmethod
    def run_loader(session: str) -> Dict[str, Any]:
        """Run models/biro26pt_loader.py over the session folder; parse its
        stdout lines `load_id=<n> file='<f>' sheet='<s>' rows=<r> cols=<c>`."""
        folder = os.path.join(UPLOAD_ROOT, os.path.basename(session))
        if not os.path.isdir(folder):
            return {"success": False, "error": "unknown upload session"}
        try:
            proc = subprocess.run(
                [sys.executable, _LOADER, folder],
                capture_output=True, text=True, timeout=600,
                cwd=_PROJECT_ROOT)
            loads = []
            for m in re.finditer(
                    r"load_id=(\d+) file='(.*?)' sheet='(.*?)' rows=(\d+) cols=(\d+)",
                    proc.stdout):
                loads.append({"load_id": int(m.group(1)), "file": m.group(2),
                              "sheet": m.group(3), "rows": int(m.group(4)),
                              "cols": int(m.group(5))})
            if proc.returncode != 0 or not loads:
                return {"success": False,
                        "error": "loader failed: " +
                                 (proc.stderr or proc.stdout or "")[-400:]}
            return {"success": True, "data": {"loads": loads}}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "loader timeout (600s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            import shutil
            shutil.rmtree(folder, ignore_errors=True)   # spec §10: clean temp files

    # ── phase 2: dry-run / commit through the package ──

    @staticmethod
    def _run_import(load_id: int, grupa: Optional[str], codprice: int,
                    commit: bool, mark_all_new: bool = True,
                    price_date: Optional[str] = None) -> Dict[str, Any]:
        # RO: p_mark_all_new => MATGR1=1 (filtrul "produse noi"); p_date =
        #     data intrarii in vigoare a pretului (NULL = azi).
        # EN: p_mark_all_new flags MATGR1=1 (the "new products" filter);
        #     p_date = the price effective date (NULL = today).
        date_expr = "TO_DATE(:d,'YYYY-MM-DD')" if price_date else "NULL"
        params = {"l": int(load_id), "g": (grupa or None), "cp": int(codprice)}
        if price_date:
            params["d"] = price_date
        r = Biro26DB().execute_dml(
            "BEGIN BIRO26PT_importData.import_file("
            "p_load_id => :l, p_grupa => :g, p_codprice => :cp, "
            "p_commit => " + ("TRUE" if commit else "FALSE") + ", "
            "p_mark_all_new => " + ("TRUE" if mark_all_new else "FALSE") + ", "
            f"p_date => {date_expr}); END;", params)
        if not r.get("success"):
            return {"success": False, "error": r.get("message")}
        return {"success": True}

    @staticmethod
    def analyze(load_id: int, grupa: Optional[str] = None,
                codprice: int = 1, mark_all_new: bool = True,
                price_date: Optional[str] = None) -> Dict[str, Any]:
        """DRY-RUN (p_commit=FALSE, nothing written to production) + read the
        detection results for the UI (spec §6.1—6.3)."""
        run = Biro26PTStore._run_import(load_id, grupa, codprice, commit=False,
                                        mark_all_new=mark_all_new,
                                        price_date=price_date)
        if not run["success"]:
            return run
        try:
            db = Biro26DB()
            mapping = _rows(db.execute_query(
                "SELECT m.col_idx, 'c'||m.col_idx phys_col, m.logical_field, "
                "m.strategy, h.header_text "
                "FROM biro26pt_map m "
                "LEFT JOIN biro26pt_header h "
                "  ON h.load_id = m.load_id AND h.col_idx = m.col_idx "
                "WHERE m.load_id = :l ORDER BY m.col_idx", {"l": int(load_id)}))
            counters = _rows(db.execute_query(
                "SELECT status, COUNT(*) cnt FROM biro26pt_stg "
                "WHERE load_id = :l GROUP BY status", {"l": int(load_id)}))
            price_changed = _rows(db.execute_query(
                "SELECT COUNT(*) price_changed FROM biro26pt_stg s "
                "WHERE s.load_id = :l AND s.status = 'EXISTING' "
                "  AND s.retail1 IS NOT NULL "
                "  AND EXISTS (SELECT 1 FROM vtpr1d_perprlist p "
                "    WHERE p.sc = s.cod_univers AND p.codprice = :cp "
                "      AND NVL(p.pretv,-1) <> "
                "          NVL(YBIRO_Import_Marfa.parse_price(s.retail1),-2) "
                "      AND p.datastart = (SELECT MAX(p2.datastart) "
                "          FROM vtpr1d_perprlist p2 "
                "          WHERE p2.sc = p.sc AND p2.codprice = :cp2))",
                {"l": int(load_id), "cp": int(codprice), "cp2": int(codprice)}))
            headers = _rows(db.execute_query(
                "SELECT col_idx, header_text FROM biro26pt_header "
                "WHERE load_id = :l ORDER BY col_idx", {"l": int(load_id)}))
            return {"success": True, "data": {
                "load_id": int(load_id),
                "mapping": mapping,
                "counters": {c["status"]: c["cnt"] for c in counters},
                "price_changed": (price_changed[0]["price_changed"]
                                  if price_changed else 0),
                "headers": headers,
                "logical_fields": LOGICAL_FIELDS,
            }}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def preview(load_id: int, offset: int = 0, limit: int = 50) -> Dict[str, Any]:
        """Row preview (§6.4) — ROWNUM paging (the ERP is Oracle 11g, no
        OFFSET/FETCH there despite the spec's 12c-style SQL)."""
        try:
            limit = max(1, min(int(limit), 500))
            offset = max(0, int(offset))
            return _result(Biro26DB().execute_query(
                "SELECT * FROM (SELECT a.*, ROWNUM rn FROM ("
                "  SELECT row_no, status, articol, denumire, grupa, "
                "         angro, ionline, retail1, barcode, img_url "
                "  FROM biro26pt_stg WHERE load_id = :l ORDER BY row_no"
                ") a WHERE ROWNUM <= :hi) WHERE rn > :lo",
                {"l": int(load_id), "hi": offset + limit, "lo": offset}))
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def commit(load_id: int, grupa: Optional[str] = None,
               codprice: int = 1, mark_all_new: bool = True,
               price_date: Optional[str] = None) -> Dict[str, Any]:
        """Real import (p_commit=TRUE) + the log and final counters."""
        run = Biro26PTStore._run_import(load_id, grupa, codprice, commit=True,
                                        mark_all_new=mark_all_new,
                                        price_date=price_date)
        if not run["success"]:
            return run
        try:
            db = Biro26DB()
            log = _rows(db.execute_query(
                "SELECT phase, logical_field, strategy, note, "
                "TO_CHAR(ts,'DD.MM.YYYY HH24:MI:SS') ts "
                "FROM biro26pt_log WHERE load_id = :l ORDER BY log_id",
                {"l": int(load_id)}))
            counters = _rows(db.execute_query(
                "SELECT status, COUNT(*) cnt FROM biro26pt_stg "
                "WHERE load_id = :l GROUP BY status", {"l": int(load_id)}))
            return {"success": True, "data": {
                "load_id": int(load_id),
                "log": log,
                "counters": {c["status"]: c["cnt"] for c in counters}}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── manual mapping override (spec §9) ──

    @staticmethod
    def remap(load_id: int, field: str, col_idx: Optional[int]) -> Dict[str, Any]:
        """Override one logical field -> column before re-running the dry-run.
        col_idx None removes the field from the mapping."""
        if field not in LOGICAL_FIELDS:
            return {"success": False, "error": f"unknown field: {field}"}
        try:
            steps = [{"sql": "DELETE FROM biro26pt_map "
                             "WHERE load_id = :l AND logical_field = :f",
                      "params": {"l": int(load_id), "f": field}, "kind": "dml"}]
            if col_idx is not None:
                steps.append({
                    "sql": "INSERT INTO biro26pt_map"
                           "(load_id, logical_field, col_idx, strategy, confidence) "
                           "VALUES (:l, :f, :c, 'MANUAL', 1)",
                    "params": {"l": int(load_id), "f": field, "c": int(col_idx)},
                    "kind": "dml"})
            r = Biro26DB().execute_script(steps)
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def algo_md() -> Dict[str, Any]:
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT BIRO26PT_importData.algo_md md FROM dual"))
            return {"success": True,
                    "data": {"md": rows[0]["md"] if rows else ""}}
        except Exception as e:
            return {"success": False, "error": str(e)}
