#!/usr/bin/env python3
"""Версия веб-приложения — ставится ОДНОВРЕМЕННО в Oracle и в MySQL.

RO: numarul de versiune = DATA lansarii (YYYY.MM.DD). Se scrie in AMBELE
    baze, ca sa se vada imediat daca Oracle si MySQL au ramas sincrone.
EN: the version number IS the release date; written to BOTH databases.

Использование:
    python scripts/set_app_version.py                 # версия = сегодня, обе БД
    python scripts/set_app_version.py --show          # что записано сейчас
    python scripts/set_app_version.py --version 2026.08.08 --note "EasyCredit v3"
    python scripts/set_app_version.py --hash          # посчитать SHA-256 исходников
    python scripts/set_app_version.py --app wordpress # только WordPress

MySQL берётся из wp-config.php (или из --mysql-* / переменных окружения),
Oracle — из обычного подключения проекта. Подробности и правило обновления:
docs/Biro26/WEB_APP_VERSIONING.md
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

APPS = ("site", "wordpress")
WP_CONFIG_CANDIDATES = ("/var/www/officeplus/wp-config.php",
                        "/home/admin/web/officeplus.md/public_html/wp-config.php")
# RO: ce intra in suma de control a surselor (fara artefacte si secrete)
HASH_GLOBS = ("*.py", "templates/**/*.html", "static/**/*.js", "static/**/*.css",
              "sql/**/*.sql")
HASH_SKIP = ("venv", ".venv", "__pycache__", ".git", "backups",
             "AccountingDemoXcode", "node_modules")


# ── версия ──

def today_version() -> str:
    """RO: data de AZI la ora Moldovei — nu a masinii pe care rulam.

    Serverul e in UTC, laptopul in EEST: pornit seara, acelasi script ar fi
    scris «08» in Oracle si «07» in MySQL, adica o desincronizare inventata
    din nimic. Fusul se fixeaza explicit, ca rezultatul sa nu depinda de locul
    rularii.
    EN: today's date in Moldova time, not in the runner's timezone — the
    server runs UTC and the laptop EEST, which would otherwise produce two
    different "today"s and a fake mismatch between the databases.
    """
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Chisinau")).strftime("%Y.%m.%d")
    except Exception:                                  # noqa: BLE001
        return date.today().strftime("%Y.%m.%d")


def source_hash() -> str:
    """SHA-256 всех исходников проекта — по путям и содержимому."""
    h = hashlib.sha256()
    files = []
    for pat in HASH_GLOBS:
        for f in ROOT.glob(pat):
            if any(part in HASH_SKIP for part in f.parts):
                continue
            if f.is_file():
                files.append(f)
    for f in sorted(set(files), key=lambda x: str(x).lower()):
        h.update(str(f.relative_to(ROOT)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


# ── Oracle ──

def oracle_set(app: str, vers: str, src_hash: Optional[str],
               note: str) -> Dict[str, Any]:
    from models.biro26_db import Biro26DB
    db = Biro26DB()
    # RO: retrogradarea versiunii curente si inserarea celei noi TREBUIE sa
    #     fie in acelasi bloc — indexul unic UX_TMS_WEBAPPVERS_CUR (un singur
    #     IS_CURRENT='1' pe APP_CODE) pica daca UPDATE-ul ramine necomis.
    # EN: demote + insert in ONE block, else the unique index rejects it.
    r = db.execute_dml(
        "BEGIN "
        "  UPDATE TMS_WEBAPPVERS SET IS_CURRENT = '0' "
        "   WHERE APP_CODE = :a AND IS_CURRENT = '1'; "
        "  INSERT INTO TMS_WEBAPPVERS (APP_CODE, VERS, IS_CURRENT, SRC_HASH, NOTE) "
        "  VALUES (:a2, :v, '1', :h, :n); "
        "END;",
        {"a": app, "a2": app, "v": vers, "h": src_hash,
         "n": note[:400] or None})
    if not r.get("success"):
        return {"success": False, "error": r.get("message")}
    return {"success": True}


def oracle_show() -> Dict[str, Any]:
    from models.biro26_db import Biro26DB
    r = Biro26DB().execute_query(
        "SELECT APP_CODE, VERS, SRC_HASH, TO_CHAR(RELEASED,'YYYY-MM-DD HH24:MI') "
        "FROM VMS_WEBAPPVERS ORDER BY APP_CODE")
    if not r.get("success"):
        return {"success": False, "error": r.get("message")}
    return {"success": True, "rows": r.get("data") or []}


# ── MySQL (WordPress) ──

def wp_config(path: Optional[str] = None) -> Dict[str, str]:
    """Реквизиты MySQL из wp-config.php (или из окружения WP_DB_*)."""
    env = {k: os.getenv(f"WP_DB_{k.upper()}", "")
           for k in ("name", "user", "password", "host")}
    if all(env[k] for k in ("name", "user", "password")):
        return {**env, "host": env["host"] or "localhost"}
    paths = [path] if path else list(WP_CONFIG_CANDIDATES)
    for p in paths:
        if not p or not os.path.exists(p):
            continue
        try:
            txt = Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            # RO: wp-config.php e citibil doar de www-data/root — nu e o
            #     eroare de program, ci lipsa de drepturi. Spunem CE sa faca.
            print(f"   {p}: {e.strerror}. Запустите через sudo -E "
                  f"или задайте WP_DB_NAME/WP_DB_USER/WP_DB_PASSWORD.",
                  file=sys.stderr)
            continue
        out = {}
        for key, name in (("DB_NAME", "name"), ("DB_USER", "user"),
                          ("DB_PASSWORD", "password"), ("DB_HOST", "host")):
            m = re.search(rf"""define\(\s*['"]{key}['"]\s*,\s*['"](.*?)['"]""", txt)
            if m:
                out[name] = m.group(1)
        if out.get("name"):
            out.setdefault("host", "localhost")
            return out
    return {}


def mysql_run(cfg: Dict[str, str], sql: str) -> subprocess.CompletedProcess:
    """RO: parola prin variabila de mediu — NU pe linia de comanda (ps o vede)."""
    env = {**os.environ, "MYSQL_PWD": cfg.get("password", "")}
    return subprocess.run(
        ["mysql", "-h", cfg.get("host", "localhost"), "-u", cfg["user"],
         "-D", cfg["name"], "--batch", "--skip-column-names", "-e", sql],
        capture_output=True, text=True, env=env, timeout=60)


def _q(s: Optional[str]) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


def mysql_set(cfg: Dict[str, str], app: str, vers: str,
              src_hash: Optional[str], note: str) -> Dict[str, Any]:
    sql = (f"UPDATE tms_webappvers SET is_current='0' "
           f"WHERE app_code={_q(app)} AND is_current='1'; "
           f"INSERT INTO tms_webappvers (app_code, vers, is_current, src_hash, note) "
           f"VALUES ({_q(app)}, {_q(vers)}, '1', {_q(src_hash)}, {_q(note[:400] or None)});")
    p = mysql_run(cfg, sql)
    if p.returncode:
        return {"success": False, "error": (p.stderr or p.stdout).strip()[:300]}
    # RO: WordPress citeste versiunea din wp_options, nu din tabela noastra
    p = mysql_run(cfg, (
        "INSERT INTO wp_options (option_name, option_value, autoload) "
        f"VALUES ('officeplus_app_version', {_q(vers)}, 'yes') "
        "ON DUPLICATE KEY UPDATE option_value = VALUES(option_value);"))
    if p.returncode:
        return {"success": False, "error": (p.stderr or p.stdout).strip()[:300]}
    return {"success": True}


def mysql_show(cfg: Dict[str, str]) -> Dict[str, Any]:
    p = mysql_run(cfg, "SELECT app_code, vers, IFNULL(src_hash,'—'), released "
                       "FROM tms_webappvers WHERE is_current='1' ORDER BY app_code;")
    if p.returncode:
        return {"success": False, "error": (p.stderr or p.stdout).strip()[:300]}
    rows = [tuple(l.split("\t")) for l in p.stdout.splitlines() if l.strip()]
    return {"success": True, "rows": rows}


# ── main ──

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="", help="номер версии (по умолчанию — сегодня)")
    ap.add_argument("--app", default="", choices=("",) + APPS,
                    help="только одно приложение (по умолчанию оба)")
    ap.add_argument("--note", default="", help="комментарий к релизу")
    ap.add_argument("--hash", action="store_true", help="посчитать SHA-256 исходников")
    ap.add_argument("--show", action="store_true", help="показать текущие версии")
    ap.add_argument("--wp-config", default="", help="путь к wp-config.php")
    ap.add_argument("--oracle-only", action="store_true")
    ap.add_argument("--mysql-only", action="store_true")
    a = ap.parse_args()

    cfg = wp_config(a.wp_config or None)

    if a.show:
        print("=== Oracle (VMS_WEBAPPVERS) ===")
        r = oracle_show()
        if r["success"]:
            for row in r["rows"]:
                print("  ", "  ".join(str(x) for x in row))
            if not r["rows"]:
                print("   (пусто)")
        else:
            print("   ОШИБКА:", r["error"])
        print("=== MySQL (tms_webappvers) ===")
        if not cfg:
            print("   wp-config.php не найден — укажите --wp-config")
        else:
            r = mysql_show(cfg)
            if r["success"]:
                for row in r["rows"]:
                    print("  ", "  ".join(row))
                if not r["rows"]:
                    print("   (пусто)")
            else:
                print("   ОШИБКА:", r["error"])
        return 0

    vers = a.version or today_version()
    src_hash = source_hash() if a.hash else None
    if a.hash:
        print("SHA-256 исходников:", src_hash)
    apps = [a.app] if a.app else list(APPS)

    rc = 0
    for app in apps:
        if not a.mysql_only:
            r = oracle_set(app, vers, src_hash, a.note)
            print(f"Oracle  {app:<10} {vers} — "
                  + ("OK" if r["success"] else "ОШИБКА: " + str(r.get("error"))[:200]))
            rc |= 0 if r["success"] else 1
        if not a.oracle_only:
            if not cfg:
                print(f"MySQL   {app:<10} пропуск: wp-config.php не найден")
                rc |= 1
            else:
                r = mysql_set(cfg, app, vers, src_hash, a.note)
                print(f"MySQL   {app:<10} {vers} — "
                      + ("OK" if r["success"] else "ОШИБКА: " + str(r.get("error"))[:200]))
                rc |= 0 if r["success"] else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
