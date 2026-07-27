#!/usr/bin/env python3
"""RO: Arhivarea saptaminala (noaptea) a SITE-ului OfficePlus:
    - SURSE + METADATE: codul Flask (artgranit + artgranit_shop1, fara venv/
      logs/git), fisierele WordPress (officeplus.md, shop1, shop2), dump-urile
      bazelor WP (MariaDB), configurile nginx/Hestia si unitatile systemd;
    - FARA marfa din ERP Oracle si FARA imaginile produselor (acelea traiesc
      in ERP/URL-uri externe) — DOAR site-ul.
    - Retentie: STRICT ultimele 7 arhive + cite 1 arhiva pe fiecare luna
      (cea mai veche a lunii ramine ca reper lunar).
    - Dupa creare, arhiva se copiaza automat pe destinatiile FTP/SFTP
      active din YBIRO_BACKUP_DEST (pagina de setari din backoffice).
    - Jurnal: YBIRO_BACKUP_LOG (vizibil in pagina «Arhive site»).

EN: weekly night backup of the SITE ONLY (sources + metadata, no ERP goods,
no product images), 7 rolling + 1 per month retention, FTP/SFTP fan-out.

Rulare (cron, duminica 03:30):
  30 3 * * 0  cd /home/ubuntu/artgranit && ./venv/bin/python scripts/biro26_site_backup.py >> /home/ubuntu/backups_site/backup.log 2>&1
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime

APP_DIR = "/home/ubuntu/artgranit"
BACKUP_DIR = "/home/ubuntu/backups_site"
KEEP_LAST = 7          # RO: strict ultimele 7 arhive
PREFIX = "site_backup_"

# RO: ce intra in arhiva (site-ul complet, fara date de marfa)
CODE_DIRS = ["/home/ubuntu/artgranit", "/home/ubuntu/artgranit_shop1"]
WP_DIRS = ["/home/admin/web/officeplus.md/public_html",
           "/home/admin/web/shop1.officeplus.md/public_html",
           "/home/admin/web/shop2.officeplus.md/public_html"]
CONF_DIRS = ["/home/admin/conf/web"]
WP_DBS = ["wordpress", "wordpress_shop1", "wordpress_shop2"]
SYSTEMD_UNITS = ["artgranit.service", "artgranit-shop1.service",
                 "jsreport.service", "pdfme.service"]
# RO: excluderi — medii virtuale, jurnale, git, fisiere de DATE incarcate
#     (fisierele de import cu marfa NU sint surse ale site-ului)
EXCLUDES = ["venv", ".venv*", "__pycache__", "*.pyc", ".git", "backups",
            "logs", "*.log", "node_modules", "uploads", "biro26pt_uploads",
            "wp-content/cache", "wp-content/uploads/backup*"]


def _load_env():
    """RO: incarca .env al aplicatiei (cron nu are EnvironmentFile)."""
    p = os.path.join(APP_DIR, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _db():
    sys.path.insert(0, APP_DIR)
    from models.biro26_db import Biro26DB
    return Biro26DB()


def _log(db, fname, size_mb, status, note):
    try:
        db.execute_dml(
            "INSERT INTO YBIRO_BACKUP_LOG (ID, FILE_NAME, SIZE_MB, STATUS, NOTE) "
            "VALUES (YBIRO_BACKUP_LOG_SEQ.NEXTVAL, :f, :s, :st, :n)",
            {"f": fname[:200], "s": round(size_mb, 1), "st": status[:20],
             "n": (note or "")[:2000]})
    except Exception as e:
        print("log err:", e)


def make_archive() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(BACKUP_DIR, f"{PREFIX}{stamp}.tar.gz")
    staging = os.path.join(BACKUP_DIR, f".staging_{stamp}")
    os.makedirs(staging, exist_ok=True)

    # 1) dump-urile WP (site-ul; NU baza Oracle cu marfa)
    for dbname in WP_DBS:
        r = _run(["sudo", "sh", "-c",
                  f"mysqldump {dbname} | gzip > {staging}/{dbname}.sql.gz"])
        print(f"dump {dbname}:", "ok" if r.returncode == 0 else r.stderr[:200])

    # 2) unitatile systemd + crontab (metadate de rulare)
    for u in SYSTEMD_UNITS:
        _run(["sudo", "sh", "-c",
              f"cp /etc/systemd/system/{u} {staging}/ 2>/dev/null || true"])
    _run(["sh", "-c", f"crontab -l > {staging}/crontab_ubuntu.txt 2>/dev/null || true"])

    # 3) tar peste cod + WP + confs + staging (cu sudo: caile admin)
    excl = " ".join(f"--exclude='{e}'" for e in EXCLUDES)
    paths = " ".join(CODE_DIRS + WP_DIRS + CONF_DIRS + [staging])
    r = _run(["sudo", "sh", "-c",
              f"tar czf {out} {excl} {paths} 2>/dev/null; "
              f"chown ubuntu:ubuntu {out}"])
    _run(["sudo", "rm", "-rf", staging])
    if r.returncode not in (0, 1):        # 1 = "file changed as we read it"
        raise RuntimeError(f"tar exit {r.returncode}: {r.stderr[:300]}")
    return out


def apply_retention():
    """RO: strict ultimele 7 + cite o arhiva (cea mai veche) pe luna."""
    files = sorted(
        [f for f in os.listdir(BACKUP_DIR)
         if f.startswith(PREFIX) and f.endswith(".tar.gz")], reverse=True)
    keep = set(files[:KEEP_LAST])
    monthly = {}
    for f in files:                       # cea mai VECHE arhiva a fiecarei luni
        m = re.match(rf"{PREFIX}(\d{{6}})", f)
        if m:
            monthly[m.group(1)] = f       # files desc -> ultima atribuire = cea mai veche
    keep.update(monthly.values())
    removed = []
    for f in files:
        if f not in keep:
            os.remove(os.path.join(BACKUP_DIR, f))
            removed.append(f)
    print("retention: keep", len(keep), "removed", removed)


def upload_all(db, path: str):
    """RO: copiere automata pe destinatiile FTP/SFTP active."""
    r = db.execute_query(
        "SELECT ID, NAME, PROTO, HOST, PORT, USERNAME, PASSWD, REMOTE_DIR "
        "FROM YBIRO_BACKUP_DEST WHERE ENABLED = '1'")
    rows = r.get("data") or []
    cols = [c.lower() for c in (r.get("columns") or [])]
    fname = os.path.basename(path)
    for row in rows:
        d = dict(zip(cols, row))
        label = f"{d['proto']}://{d['host']}:{d.get('port') or ''}{d.get('remote_dir') or '/'}"
        try:
            if (d.get("proto") or "").lower() == "ftp":
                import ftplib
                ftp = ftplib.FTP()
                ftp.connect(d["host"], int(d.get("port") or 21), timeout=30)
                ftp.login(d.get("username") or "", d.get("passwd") or "")
                if d.get("remote_dir"):
                    ftp.cwd(d["remote_dir"])
                with open(path, "rb") as fh:
                    ftp.storbinary(f"STOR {fname}", fh)
                ftp.quit()
            else:                                    # sftp
                import paramiko
                tr = paramiko.Transport((d["host"], int(d.get("port") or 22)))
                tr.connect(username=d.get("username") or "",
                           password=d.get("passwd") or "")
                sftp = paramiko.SFTPClient.from_transport(tr)
                remote = (d.get("remote_dir") or "/").rstrip("/") + "/" + fname
                sftp.put(path, remote)
                sftp.close()
                tr.close()
            _log(db, fname, 0, "UPLOAD_OK", f"{d['name']} -> {label}")
            print("upload ok:", label)
        except Exception as e:
            _log(db, fname, 0, "UPLOAD_ERR", f"{d['name']} -> {label}: {e}")
            print("upload ERR:", label, e)


def main():
    _load_env()
    os.chdir(APP_DIR)
    db = _db()
    try:
        path = make_archive()
        size_mb = os.path.getsize(path) / 1024 / 1024
        print("archive:", path, f"{size_mb:.1f} MB")
        _log(db, os.path.basename(path), size_mb, "OK",
             "site sources + WP dumps + nginx/systemd (no ERP goods/images)")
        apply_retention()
        upload_all(db, path)
    except Exception as e:
        _log(db, "-", 0, "ERROR", str(e))
        print("BACKUP ERROR:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
