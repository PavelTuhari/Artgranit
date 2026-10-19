#!/usr/bin/env python3
"""Универсальное исправление буфера в рассыльщиках других схем cloudbd.

Тот же дефект, что в OTRS (docs/OTRS/MAIL_QUEUE_DIAGNOSIS.md): приёмник HTTP-
ответа и буфер строки объявлены как varchar2(4000), из-за чего письма крупнее
4000 байт падают с ORA-06502 и остаются в очереди навсегда.

Пакеты в разных схемах разные (PKG_MAIL_UTL, PKG_MAIL_UTIL, PKG_TICKETS_MAIL),
поэтому вместо переписывания процедуры целиком делается минимальная правка:
varchar2(4000) -> varchar2(32767) на строках объявления v_req_result и buffer.
32767 — максимум для переменной PL/SQL, покрывает любое реальное письмо.

    venv/bin/python docs/OTRS/patch_buffer.py <схема> <ПАКЕТ> [--apply]
    venv/bin/python docs/OTRS/patch_buffer.py <схема> <ПАКЕТ> --rollback

Без --apply только показывает, что будет заменено (dry-run). Пароль берётся
из Keychain: security find-generic-password -s oracle-cloudbd-<схема> -w
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from models.unisim_cassa import _call_worker, _rows  # noqa: E402

DSN = "orange.una.md:4024/cloudbd.world"
BACKUP = ROOT / "docs/OTRS/backup"
# объявление: <имя> varchar2(4000)  ->  <имя> varchar2(32767)
DECL = re.compile(r"\b(v_req_result|buffer)\s+varchar2\s*\(\s*4000\s*\)", re.IGNORECASE)


def auth(schema):
    pw = subprocess.run(["security", "find-generic-password", "-s", f"oracle-cloudbd-{schema}", "-w"],
                        capture_output=True, text=True, check=True).stdout.strip()
    return {"user": schema, "password": pw, "dsn": DSN}


def read_body(a, pkg):
    rows = _rows(_call_worker(a, "SELECT LINE, TEXT FROM USER_SOURCE "
                                 f"WHERE NAME='{pkg}' AND TYPE='PACKAGE BODY' ORDER BY LINE", 4000))
    return "".join((r["text"] or "") for r in sorted(rows, key=lambda x: x["line"])), len(rows)


def compile_body(a, pkg, ddl):
    ddl = ddl.rstrip().rstrip("/").rstrip()
    r = _call_worker(a, ddl, 60)
    print("    компиляция:", "OK" if r.get("success") else str(r.get("message"))[:220])
    for x in _rows(_call_worker(a, f"SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM USER_OBJECTS "
                                   f"WHERE OBJECT_NAME='{pkg}'", 10)):
        print("    ", x)
    errs = _rows(_call_worker(a, f"SELECT LINE, TEXT FROM USER_ERRORS WHERE NAME='{pkg}' "
                                 "ORDER BY SEQUENCE", 30))
    print("    ошибки:", errs if errs else "нет")
    return not errs


if __name__ == "__main__":
    schema, pkg = sys.argv[1].lower(), sys.argv[2].upper()
    apply = "--apply" in sys.argv
    rollback = "--rollback" in sys.argv
    a = auth(schema)
    bak = BACKUP / f"{schema.upper()}_{pkg}_20260825_original.sql"

    if rollback:
        ddl = bak.read_text(encoding="utf-8")
        print(f"откат {schema}.{pkg} из {bak.name}")
        compile_body(a, pkg, ddl)
        sys.exit()

    body, n = read_body(a, pkg)
    if n == 0:
        print(f"{schema}.{pkg}: тело пакета не найдено")
        sys.exit(1)
    hits = DECL.findall(body)
    print(f"{schema}.{pkg}: строк {n}, найдено объявлений varchar2(4000): {len(hits)} -> {hits}")
    for m in DECL.finditer(body):
        ln = body[:m.start()].count("\n") + 1
        print(f"    строка ~{ln}: {m.group(0)}")

    if not hits:
        print("    заменять нечего")
        sys.exit()

    if apply:
        BACKUP.mkdir(parents=True, exist_ok=True)
        bak.write_text("CREATE OR REPLACE " + body + "\n/\n", encoding="utf-8")
        print(f"    бэкап: {bak}")
        patched = DECL.sub(lambda m: f"{m.group(1)} varchar2(32767)", body)
        compile_body(a, pkg, "CREATE OR REPLACE " + patched)
    else:
        print("    (dry-run; добавьте --apply для установки)")
