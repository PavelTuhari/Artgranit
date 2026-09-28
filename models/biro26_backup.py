"""RO: Biro26Backup — arhivele saptaminale ale SITE-ului (surse+metadate,
fara marfa ERP/imagini produse): lista arhivelor de pe disc, destinatiile
FTP/SFTP (YBIRO_BACKUP_DEST), jurnalul (YBIRO_BACKUP_LOG), rulare manuala.
EN: weekly site-backup management (archives list, FTP/SFTP fan-out CRUD)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Any, Dict

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows

BACKUP_DIR = os.environ.get("BIRO26_BACKUP_DIR", "/home/ubuntu/backups_site")
PREFIX = "site_backup_"
_SAFE = re.compile(r"^site_backup_\d{8}_\d{6}\.tar\.gz$")


class Biro26Backup:

    @staticmethod
    def archives() -> Dict[str, Any]:
        out = []
        try:
            if os.path.isdir(BACKUP_DIR):
                for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
                    if f.startswith(PREFIX) and f.endswith(".tar.gz"):
                        p = os.path.join(BACKUP_DIR, f)
                        st = os.stat(p)
                        out.append({
                            "name": f,
                            "size_mb": round(st.st_size / 1048576, 1),
                            "created": __import__("datetime").datetime
                                .fromtimestamp(st.st_mtime)
                                .strftime("%d.%m.%Y %H:%M")})
            return {"success": True, "data": out}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def archive_path(name: str):
        """RO: cale sigura (doar nume valide de arhiva) pentru download."""
        if not _SAFE.match(name or ""):
            return None
        p = os.path.join(BACKUP_DIR, name)
        return p if os.path.isfile(p) else None

    @staticmethod
    def run_now() -> Dict[str, Any]:
        """RO: porneste arhivarea in fundal (nu blocheaza requestul)."""
        try:
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            script = os.path.join(app_dir, "scripts", "biro26_site_backup.py")
            os.makedirs(BACKUP_DIR, exist_ok=True)
            log = open(os.path.join(BACKUP_DIR, "backup.log"), "a")
            subprocess.Popen([sys.executable, script], cwd=app_dir,
                             stdout=log, stderr=log,
                             start_new_session=True)
            return {"success": True,
                    "data": {"note": "pornit in fundal; vezi jurnalul"}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── destinatii FTP/SFTP ────────────────────────────────────────────
    @staticmethod
    def dest_list() -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT ID, NAME, PROTO, HOST, PORT, USERNAME, REMOTE_DIR, "
            "ENABLED FROM YBIRO_BACKUP_DEST ORDER BY ID"))
        # RO: parola NU se trimite in UI (se pastreaza la salvare daca e goala)
        return {"success": True,
                "data": [{k.lower(): v for k, v in r.items()} for r in rows]}

    @staticmethod
    def dest_save(d: Dict[str, Any]) -> Dict[str, Any]:
        proto = (d.get("proto") or "sftp").lower()
        if proto not in ("ftp", "sftp"):
            return {"success": False, "error": "proto: ftp | sftp"}
        p = {"n": (d.get("name") or "")[:100],
             "pr": proto,
             "h": (d.get("host") or "")[:200],
             "po": int(d["port"]) if str(d.get("port") or "").isdigit() else None,
             "u": (d.get("username") or "")[:100],
             "rd": (d.get("remote_dir") or "/")[:400],
             "e": "1" if str(d.get("enabled", "1")) == "1" else "0"}
        if not p["n"] or not p["h"]:
            return {"success": False, "error": "nume si host obligatorii"}
        db = Biro26DB()
        if d.get("id"):
            p["i"] = int(d["id"])
            sql = ("UPDATE YBIRO_BACKUP_DEST SET NAME=:n, PROTO=:pr, HOST=:h, "
                   "PORT=:po, USERNAME=:u, REMOTE_DIR=:rd, ENABLED=:e")
            if d.get("passwd"):                      # goala = neschimbata
                sql += ", PASSWD=:pw"
                p["pw"] = str(d["passwd"])[:200]
            r = db.execute_dml(sql + " WHERE ID=:i", p)
        else:
            p["pw"] = str(d.get("passwd") or "")[:200]
            r = db.execute_dml(
                "INSERT INTO YBIRO_BACKUP_DEST (ID, NAME, PROTO, HOST, PORT, "
                "USERNAME, PASSWD, REMOTE_DIR, ENABLED) VALUES "
                "(YBIRO_BACKUP_DEST_SEQ.NEXTVAL, :n, :pr, :h, :po, :u, :pw, "
                ":rd, :e)", p)
        return r if r.get("success") else {"success": False,
                                           "error": r.get("message")}

    @staticmethod
    def dest_delete(did: int) -> Dict[str, Any]:
        return Biro26DB().execute_dml(
            "DELETE FROM YBIRO_BACKUP_DEST WHERE ID = :i", {"i": int(did)})

    @staticmethod
    def log_list() -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT * FROM (SELECT ID, TO_CHAR(TS,'DD.MM.YYYY HH24:MI') TS, "
            "FILE_NAME, SIZE_MB, STATUS, NOTE FROM YBIRO_BACKUP_LOG "
            "ORDER BY ID DESC) WHERE ROWNUM <= 100"))
        return {"success": True,
                "data": [{k.lower(): v for k, v in r.items()} for r in rows]}
