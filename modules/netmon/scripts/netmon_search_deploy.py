#!/usr/bin/env python3
"""Установщик объектов модуля в базе cloudbd (схема OTRS): поиск NMON_SRCH_ и унификация клиентов NMON_CLI_.

    python modules/netmon/scripts/netmon_search_deploy.py --dry-run     # разбор файлов, без базы
    python modules/netmon/scripts/netmon_search_deploy.py               # поставить / обновить объекты
    python modules/netmon/scripts/netmon_search_deploy.py --refresh     # догрузить изменения в индекс
    python modules/netmon/scripts/netmon_search_deploy.py --full        # пересобрать индекс с нуля
    python modules/netmon/scripts/netmon_search_deploy.py --selftest    # проверить поиск и ссылки
    python modules/netmon/scripts/netmon_search_deploy.py --drop --yes  # удалить всё NMON_SRCH_

Установка в боевую базу cloudbd разрешена владельцем 18.10.2026.

Это СВОЙ установщик: общий deploy_oracle_objects.py и netmon_deploy.py (они
ставят таблицы в основную базу ADB) не трогаем. Cloudbd — Oracle 11g, к ней
нужен толстый клиент, поэтому соединение своё, через Instant Client.
Пароль учётки OTRS — Keychain «oracle-cloudbd-otrs» (как у доски заявок).
--dry-run не доказывает, что схема встанет (CLAUDE.md §2 п.5): прогнать вживую.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from deploy_oracle_objects import _is_comment_only, _is_plsql_block, _split_ddl_dml, _sql_blocks  # noqa: E402

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "cloudbd"
# 302 — унификация клиентов (NMON_CLI_*), тот же контур и те же правила
INSTALL = ["300_nmon_srch_tables.sql", "301_nmon_srch_pkg.sql", "302_nmon_cli.sql"]
DROP = ["399_nmon_srch_drop.sql"]

# «Уже есть» — не ошибка: установщик запускается повторно.
ALREADY = ("ORA-00955", "ORA-01408", "ORA-00001", "ORA-02260", "ORA-02261", "ORA-02275")
# При удалении «нет такого объекта» — тоже не ошибка.
MISSING = ("ORA-00942", "ORA-04043", "ORA-01418", "ORA-02289")


def statements(files: list[str]) -> list[str]:
    """Команды из файлов: PL/SQL и CREATE TYPE — целиком, остальное — по «;»."""
    out = []
    for name in files:
        text = (SQL_DIR / name).read_text(encoding="utf-8")
        for block in _sql_blocks(text):
            if _is_comment_only(block):
                continue
            code = "\n".join(line for line in block.splitlines() if not line.strip().startswith("--")).strip()
            if _is_plsql_block(block) or re.match(r"CREATE\s+OR\s+REPLACE\s+TYPE\b", code, re.I):
                out.append(code.rstrip("/").rstrip())
            else:
                out += [s.strip() for s in _split_ddl_dml(block) if not _is_comment_only(s)]
    return out


def connect():
    import oracledb
    from config import Config
    from modules.netmon import otrs_board as ob
    try:
        oracledb.init_oracle_client(lib_dir=Config.BIRO26_INSTANT_CLIENT)
    except Exception as e:  # noqa: BLE001
        if "already been initialized" not in str(e):
            raise
    return oracledb.connect(user=ob.DB_USER, password=ob._password(), dsn=ob.DB_DSN)


def run(conn, stmts: list[str], tolerate: tuple[str, ...]) -> int:
    cur = conn.cursor()
    ok = skip = err = 0
    for s in stmts:
        head = " ".join(s.split())[:70]
        try:
            cur.execute(s)
            conn.commit()
            ok += 1
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if any(code in msg for code in tolerate):
                skip += 1
                continue
            print(f"  ошибка: {head}\n          {msg[:300]}")
            err += 1
    print(f"готово: успешно {ok}, уже было {skip}, ошибок {err}")
    return err


def compile_errors(conn) -> int:
    cur = conn.cursor()
    cur.execute("""SELECT name, type, line, position, text FROM user_errors
                    WHERE name IN ('NMON_SRCH', 'NMON_SRCH_HIT', 'NMON_SRCH_HITS') ORDER BY name, type, sequence""")
    rows = cur.fetchall()
    for r in rows:
        print(f"  {r[0]} {r[1]} строка {r[2]}:{r[3]} — {r[4].strip()}")
    cur.execute("SELECT object_name, object_type, status FROM user_objects WHERE object_name LIKE 'NMON_SRCH%' "
                "ORDER BY object_type, object_name")
    objs = cur.fetchall()
    bad = [r for r in objs if r[2] != "VALID"]
    for r in bad:
        print(f"  НЕ ГОТОВ: {r[1]} {r[0]} — {r[2]}")
    print(f"объектов NMON_SRCH: {len(objs)}, из них не готовы {len(bad)}")
    return len(rows) + len(bad)


def refresh(conn, full: bool) -> None:
    cur = conn.cursor()
    t = time.time()
    print(("полная пересборка" if full else "догрузка изменений") + " индекса…", flush=True)
    cur.callproc("nmon_srch.refresh", [1 if full else 0, None])
    cur.execute("SELECT source, status, docs, added, updated, removed, seconds, message "
                "FROM nmon_srch_sync ORDER BY source")
    for r in cur.fetchall():
        print(f"  {r[0]:<6} {r[1]:<8} документов {r[2]}, новых {r[3]}, обновлено {r[4]}, удалено {r[5]}, "
              f"{r[6]} с {r[7] or ''}")
    print(f"за {round(time.time() - t)} с")


# Проверки на живой базе: что функции разбора делают то, что обещано.
SELFTEST = [
    ("SELECT nmon_srch.fix_layout('ghbdtn') FROM dual", "привет", "раскладка: латиница → кириллица"),
    ("SELECT nmon_srch.fix_layout('щкфсду') FROM dual", "oracle", "раскладка: кириллица → латиница"),
    ("SELECT nmon_srch.stem('принтера') FROM dual", "принтер", "основа: принтера → принтер"),
    ("SELECT nmon_srch.stem('накладной') FROM dual", "накладн", "основа: накладной → накладн"),
    ("SELECT nmon_srch.stem('facturilor') FROM dual", "factur", "основа: facturilor → factur"),
    ("SELECT nmon_srch.normalize('Ёлка, VPN-клиент!') FROM dual", "елка vpn клиент", "нормализация запроса"),
    ("SELECT nmon_srch.mask_secrets('Пароль: Qwerty123 и логин') FROM dual", "Пароль: [скрыто] и логин",
     "маска пароля"),
    ("SELECT nmon_srch.mask_secrets('passport 123') FROM dual", "passport 123", "маска не трогает passport"),
    ("SELECT nmon_srch.xwiki_skip('XWiki') + nmon_srch.xwiki_skip('TasksCode') FROM dual", "2",
     "служебные разделы XWiki"),
    ("SELECT nmon_srch.xwiki_skip('UNA') FROM dual", "0", "раздел с документацией не пропускается"),
]


def selftest(conn) -> int:
    cur = conn.cursor()
    bad = 0
    for sql, want, title in SELFTEST:
        cur.execute(sql)
        got = str(cur.fetchone()[0])
        ok = got == want
        bad += not ok
        print(f"  {'✓' if ok else '✗'} {title}: {got!r}" + ("" if ok else f" (ожидалось {want!r})"))

    for q, src in (("принтер", None), ("ghbynth", None), ("руководство пользователя", "XWIKI")):
        t = time.time()
        cur.execute("SELECT title, url, matched_by, total, source, used_query "
                    "FROM TABLE(nmon_srch.search(:q, :s, NULL, 3))", q=q, s=src)
        rows = cur.fetchall()
        ok = bool(rows)
        bad += not ok
        print(f"  {'✓' if ok else '✗'} поиск «{q}»: найдено {rows[0][3] if rows else 0}, "
              f"{rows[0][2] if rows else '—'}, запрос «{rows[0][5] if rows else ''}», "
              f"{round((time.time() - t) * 1000)} мс")
        for r in rows:
            print(f"      {r[4]:<5} {r[0][:70]}  {r[1]}")

    cur.execute("SELECT tn FROM (SELECT tn FROM nmon_srch_doc WHERE source = 'OTRS' ORDER BY changed_at DESC) "
                "WHERE ROWNUM = 1")
    tn = cur.fetchone()[0]
    cur.execute("SELECT matched_by, tn FROM TABLE(nmon_srch.search(:q))", q=tn)
    rows = cur.fetchall()
    ok = bool(rows) and rows[0] == ("номер заявки", tn)
    bad += not ok
    print(f"  {'✓' if ok else '✗'} номер заявки {tn}: {rows[:1]}")

    # Оригинальные ссылки должны открываться: страница XWiki отвечает 200 и
    # называет себя тем же документом.
    cur.execute("""SELECT url, src_key FROM (SELECT url, src_key FROM nmon_srch_doc WHERE source = 'XWIKI'
                    ORDER BY DBMS_RANDOM.VALUE) WHERE ROWNUM <= 12""")
    links = cur.fetchall()
    good = 0
    for url, key in links:
        name = key.split(":")[0]
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                html = r.read(8000).decode("utf-8", "replace")
                hit = r.status == 200 and f'content="{name}"' in html
        except Exception as e:  # noqa: BLE001
            hit, html = False, str(e)
        good += hit
        if not hit:
            print(f"      ✗ {url}  ({key})")
    if links:
        ok = good == len(links)
        bad += not ok
        print(f"  {'✓' if ok else '✗'} ссылки XWiki открываются: {good} из {len(links)}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--drop", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()

    if a.drop:
        stmts = statements(DROP)
        print(f"удаление: команд {len(stmts)}")
        if a.dry_run:
            return
        if not a.yes:
            sys.exit("удаление индекса поиска: добавьте --yes")
        sys.exit(1 if run(connect(), stmts, MISSING) else 0)

    if a.refresh or a.full or a.selftest:
        if a.dry_run:
            return
        conn = connect()
        if a.refresh or a.full:
            refresh(conn, a.full)
        if a.selftest:
            sys.exit(1 if selftest(conn) else 0)
        return

    stmts = statements(INSTALL)
    print(f"команд к выполнению: {len(stmts)}")
    if a.dry_run:
        for s in stmts:
            print("  ·", " ".join(s.split())[:90])
        return
    conn = connect()
    err = run(conn, stmts, ALREADY)
    err += compile_errors(conn)
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
