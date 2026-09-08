#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Публикация каталога Ultra из буфера в номенклатуру и прайс — ШТАТНЫМ конвейером.

    python3 modules/partner/scripts/ultra_publish.py            # разбор, без записи
    python3 modules/partner/scripts/ultra_publish.py --commit   # заливка в прод

Цепочка (та же, что у impreso/officeshop/atehno — ничего нового):

    BIRO26_GOODS (SHEET='ULTRA')
      -> xlsx с шапкой, которую понимает detect_columns
      -> models/biro26pt_loader.py  (RAW/HEADER/FILE, свой load_id)
      -> BIRO26PT_importData.import_file(load_id, p_src=>'ULTRA', p_commit)

Что даёт конвейер сам, без доработок: маркер источника TMS_MPT_IMPSRC, префикс
артикула, журнал YBIRO_IMPORT_LOG, размещение в дереве по GRUPA/CATEGORIE,
цены с НОВЫМ ПЕРИОДОМ и закрытием старого (витрина читает цену по периоду),
пометка «новинка» только для новых, EAN-13 для новых.

Мост к июльским карточкам GOG* — через приоритет 1 в classify(): ШТРИХКОД.
Июльская выгрузка дала каждой GOG-карточке штрихкод 4841…, и он уникален
(24 057 штрихкодов, у каждого ровно одна активная карточка). Мы находим
июльскую карточку по UUID картинки — он сохранён в TMS_MPT_TVR.IE_LINKADRES —
и кладём в колонку Barcode её штрихкод. Дальше classify сам делает
EXISTING + cod_univers. Ни одной строки логики сопоставления мы не пишем.

Почему не YBIRO_Import_Marfa.import_all напрямую: он читает ВСЮ таблицу без
фильтра по источнику, его assign_keys даёт новый код всему, что без ключа, а
import_prices не закрывает старый период — на витрине было бы две «текущих»
цены.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import datetime as dt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# RO: antetul EXACT dupa sabloanele din BIRO26PT_COLMAP (detect_columns)
HEAD = ["Articol", "Barcode", "Denumire", "Grupa", "Categorie", "Brand",
        "Angro", "Retail", "Image URL", "Stoc"]


def connect():
    import oracledb
    from config import Config
    oracledb.init_oracle_client(lib_dir=Config.BIRO26_INSTANT_CLIENT)
    return oracledb.connect(user=Config.BIRO26_DB_USER, password=Config.BIRO26_DB_PASSWORD,
                            dsn=Config.BIRO26_DB_DSN)


def export_xlsx(con, path: str) -> dict:
    """Буфер ULTRA -> xlsx; Barcode = штрихкод июльской GOG-карточки (мост)."""
    cur = con.cursor()
    # RO: uuid imaginii -> (cod GOG, un cod de bare UNIC al cartelei)
    bridge = {}
    for cod, link, bc in cur.execute("""
        SELECT u.cod, t.ie_linkadres,
               (SELECT MIN(b.barcode) FROM tms_mpt_barcode b
                 WHERE b.cod = u.cod AND b.barcode LIKE '4841%'
                   AND (SELECT COUNT(DISTINCT b2.cod) FROM tms_mpt_barcode b2
                         JOIN tms_univers u2 ON u2.cod = b2.cod AND u2.tip = 'P'
                          AND NVL(u2.isarhiv,'0') <> '2'
                        WHERE b2.barcode = b.barcode) = 1)
          FROM tms_univers u JOIN tms_mpt_tvr t ON t.cod = u.cod
         WHERE u.tip = 'P' AND u.codvechi LIKE 'GOG%' AND NVL(u.isarhiv,'0') <> '2'
           AND t.ie_linkadres LIKE '%cdn.ultra.md%'"""):
        m = UUID_RE.search(link or "")
        if m and bc:
            bridge.setdefault(m.group(), (cod, bc))

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ULTRA"
    ws.append(HEAD)
    n = linked = 0
    for art, den, grupa, categ, brand, angro, retail, photo, stoc in cur.execute("""
        SELECT articol, denumire, grupa, categorie, brand, angro, retail1, photo_url, stoc
          FROM biro26_goods WHERE sheet = 'ULTRA' AND denumire IS NOT NULL"""):
        m = UUID_RE.search(photo or "")
        hit = bridge.get(m.group()) if m else None
        if hit:
            linked += 1
        ws.append([art, hit[1] if hit else None, den, grupa, categ, brand,
                   angro, retail, photo, stoc])
        n += 1
    wb.save(path)
    return {"rows": n, "linked": linked, "bridge_cards": len(bridge)}


def load_raw(path: str) -> int:
    """Штатный загрузчик RAW; возвращает load_id."""
    py = sys.executable
    out = subprocess.run([py, os.path.join(ROOT, "models", "biro26pt_loader.py"), path],
                         capture_output=True, text=True, cwd=ROOT)
    m = re.search(r"load_id=(\d+)", out.stdout or "")
    if not m:
        sys.exit(f"loader: {out.stdout[-400:]} {out.stderr[-400:]}")
    return int(m.group(1))


def run_import(con, load_id: int, commit: bool) -> list[str]:
    """import_file + DBMS_OUTPUT. Период работы = текущий месяц (ORA-20101 иначе)."""
    cur = con.cursor()
    today = dt.date.today()
    first = today.replace(day=1).strftime("%d.%m.%Y")
    nxt = (today.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    cur.execute("BEGIN UN4PUBLIC.ENVUN4.EnvSetValue('PARAM_PERIODBEG', :d); END;", d=first)
    cur.execute("BEGIN UN4PUBLIC.ENVUN4.EnvSetValue('PARAM_PERIODEND', :d); END;",
                d=nxt.strftime("%d.%m.%Y"))
    cur.callproc("dbms_output.enable", [1_000_000])
    cur.execute("""BEGIN BIRO26PT_importData.import_file(
                     p_load_id => :lid, p_commit => :c, p_mark_all_new => FALSE,
                     p_src => 'ULTRA', p_algo => 'UNIVERSAL'); END;""",
                lid=load_id, c=commit)
    lines, line, status = [], cur.var(str), cur.var(int)
    while True:
        cur.callproc("dbms_output.get_line", (line, status))
        if status.getvalue() != 0:
            break
        lines.append(line.getvalue())
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--xlsx", default="/tmp/ULTRA_publish.xlsx")
    args = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))

    con = connect()
    st = export_xlsx(con, args.xlsx)
    print(f"экспорт: {st['rows']} строк, мост по штрихкоду: {st['linked']} "
          f"(карточек GOG с uuid: {st['bridge_cards']}) -> {args.xlsx}")
    load_id = load_raw(args.xlsx)
    print(f"загрузка RAW: load_id={load_id}")
    for ln in run_import(con, load_id, args.commit):
        print("  " + ln)
    print("\nрежим:", "ЗАПИСЬ (p_commit=TRUE)" if args.commit else "разбор без записи")


if __name__ == "__main__":
    main()
