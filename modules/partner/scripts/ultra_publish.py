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
JULY_XLSX = "/Users/pt/Projects.AI/BIRO26/Set_data_import/8/ULTRA.md (1).xlsx"

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
    # RO: uuid imaginii -> (cod GOG, un cod de bare UNIC al cartelei).
    #     Sursa PRINCIPALA: fisierul incarcarii din iulie (Set_data_import/8),
    #     unde coloana URL tine imaginea cu uuid — 15 952 potriviri verificate.
    #     IE_LINKADRES din TMS_MPT_TVR acopera doar 1 663 de cartele si e doar
    #     completare. EN: main source = July file map; IE_LINKADRES is a fallback.
    bridge = {}
    gog2bc = {g: b for g, b in cur.execute("""
        SELECT u.codvechi, MIN(b.barcode)
          FROM tms_univers u JOIN tms_mpt_barcode b ON b.cod = u.cod
         WHERE u.tip = 'P' AND u.codvechi LIKE 'GOG%' AND NVL(u.isarhiv,'0') <> '2'
           AND b.barcode LIKE '4841%'
           AND (SELECT COUNT(DISTINCT b2.cod) FROM tms_mpt_barcode b2
                 JOIN tms_univers u2 ON u2.cod = b2.cod AND u2.tip = 'P'
                  AND NVL(u2.isarhiv,'0') <> '2'
                WHERE b2.barcode = b.barcode) = 1
         GROUP BY u.codvechi""")}
    if os.path.exists(JULY_XLSX):
        import openpyxl as _ox
        wb0 = _ox.load_workbook(JULY_XLSX, read_only=True, data_only=True)
        for sn in wb0.sheetnames:
            it = wb0[sn].iter_rows(values_only=True)
            next(it, None)
            for r0 in it:
                if not r0 or not r0[1]:
                    continue
                m0 = UUID_RE.search(str(r0[0] or ""))
                g0 = str(r0[1]).strip()
                if m0 and g0 in gog2bc:
                    bridge.setdefault(m0.group(), (g0, gog2bc[g0]))
        wb0.close()
    # RO: a treia cheie — NUME + CULOARE. In fisierul din iulie culoarea nu e in
    #     nume, ci la sfirsitul DESCRIERE ("... | Negru"); la Ultra numele o
    #     contine ("..., Negru"). Normalizat (fara spatii/semne) cele doua
    #     coincid. Acopera cartelele ale caror imagini s-au schimbat intre timp
    #     (Galaxy A27: iulie cdn.ultra.md, acum esempla) — 118 dubluri create pe
    #     09.09.2026 exact din cauza asta. Doar chei UNICE pe ambele parti.
    # EN: third key = normalized name + colour (July colour lives at the end of
    #     DESCRIERE); unique on both sides only.
    def _norm(x):
        return re.sub(r"[^A-Z0-9А-Я]", "", str(x or "").upper())
    if os.path.exists(JULY_XLSX):
        jkey, jamb = {}, set()
        wb0 = _ox.load_workbook(JULY_XLSX, read_only=True, data_only=True)
        for sn in wb0.sheetnames:
            it = wb0[sn].iter_rows(values_only=True)
            next(it, None)
            for r0 in it:
                if not r0 or not r0[1]:
                    continue
                colour = str(r0[5] or "").split("|")[-1].strip() if r0[5] else ""
                k = _norm(str(r0[3] or "") + colour)
                g0 = str(r0[1]).strip()
                if k and g0 in gog2bc:
                    if k in jkey and jkey[k] != g0:
                        jamb.add(k)
                    jkey.setdefault(k, g0)
        wb0.close()
        for k in jamb:
            jkey.pop(k, None)
        name_bridge = {}
        for k, g0 in jkey.items():
            name_bridge[k] = (g0, gog2bc[g0])
    else:
        name_bridge = {}
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
           AND LOWER(t.ie_linkadres) LIKE '%ultra%'"""):
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
          FROM biro26_goods
         WHERE sheet = 'ULTRA' AND denumire IS NOT NULL
           -- RO: doar rindurile ATINSE de ultima sincronizare: ea pune mereu o
           --     grupa (sau «Ultra - diverse»). Rindurile cu GRUPA goala sint
           --     resturi vechi (pret vechi, denumiri cu «?») si NU se publica.
           -- EN: only rows refreshed by the sync (it always sets a group);
           --     stale leftovers are never published.
           AND grupa IS NOT NULL"""):
        m = UUID_RE.search(photo or "")
        hit = bridge.get(m.group()) if m else None
        if not hit:
            hit = name_bridge.get(_norm(den))
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
    # RO: pe Oracle 11g un BOOLEAN PL/SQL nu se poate lega ca parametru
    #     (ORA-03115) — se scrie literal in text.
    cur.execute(f"""BEGIN BIRO26PT_importData.import_file(
                     p_load_id => :lid, p_commit => {'TRUE' if commit else 'FALSE'},
                     p_mark_all_new => FALSE,
                     p_src => 'ULTRA', p_algo => 'UNIVERSAL'); END;""",
                lid=load_id)
    lines, line, status = [], cur.var(str), cur.var(int)
    while True:
        cur.callproc("dbms_output.get_line", (line, status))
        if status.getvalue() != 0:
            break
        lines.append(line.getvalue())
    return lines


def write_markers(con, load_id: int) -> dict:
    """Журнал YBIRO_IMPORT_LOG + маркеры TMS_MPT_IMPSRC для загрузки.

    Пакет BIRO26PT_importData этого НЕ делает — у прошлых импортов (atehno,
    bestbuy…) это писала python-обёртка. Без маркера карточка не знает, откуда
    пришла, а инкрементальный синк не может её узнать по uuid (SRC_PID).
    """
    cur = con.cursor()
    cur.execute("""SELECT COUNT(*),
                          SUM(CASE WHEN status='NEW' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN status='EXISTING' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN status IN ('AMBIGUOUS','NOARTICOL') THEN 1 ELSE 0 END)
                     FROM biro26pt_stg WHERE load_id = :l""", l=load_id)
    total, new, exist, skipped = cur.fetchone()
    cur.execute("SELECT YBIRO_IMPORT_LOG_SEQ.NEXTVAL FROM dual")
    import_id = cur.fetchone()[0]
    cur.execute("""INSERT INTO ybiro_import_log
                     (import_id, source_code, src_file, load_id, started_at, finished_at,
                      rows_total, rows_inserted, rows_matched, rows_skipped, notes)
                   VALUES (:i, 'ULTRA', :f, :l, SYSTIMESTAMP, SYSTIMESTAMP,
                           :t, :n, :e, :s, :note)""",
                i=import_id, f=f"Ultra B2B API /product ({dt.date.today()})", l=load_id,
                t=total, n=new, e=exist, s=skipped,
                note="RO: punte prin cod de bare 4841 al cartelelor GOG din iulie; "
                     "SRC_PID = uuid-ul produsului la Ultra")
    # RO: marcajul de sursa: uuid din tampon (dupa articol), cale de grup, statusul potrivirii
    cur.execute("""MERGE INTO tms_mpt_impsrc t
                   USING (SELECT cod, articol, status, gpath, guid FROM (
                            -- RO: o singura linie per cartela: catalogul Ultra are
                            --     ~1 800 de pozitii dublate, iar MERGE ar insera
                            --     acelasi COD de doua ori (ORA-00001).
                            SELECT s.cod_univers cod, s.articol, s.status,
                                   SUBSTR(s.grupa || ' > ' || s.categ, 1, 400) gpath,
                                   (SELECT MAX(g.guid) FROM biro26_goods g
                                     WHERE g.sheet='ULTRA' AND g.articol = s.articol) guid,
                                   ROW_NUMBER() OVER (PARTITION BY s.cod_univers ORDER BY s.id) rn
                              FROM biro26pt_stg s
                             WHERE s.load_id = :l AND s.cod_univers IS NOT NULL
                               AND s.status IN ('NEW','EXISTING')) WHERE rn = 1) u
                   ON (t.cod = u.cod)
                   WHEN MATCHED THEN UPDATE SET
                        t.src_source_code = 'ULTRA', t.src_import_id = :i,
                        t.src_row_guid = u.guid, t.src_pid = u.guid,
                        t.src_articol = u.articol, t.src_group_path = u.gpath,
                        t.match_status = u.status, t.updated_at = SYSDATE
                   WHEN NOT MATCHED THEN INSERT
                        (cod, src_source_code, src_import_id, src_row_guid, src_pid,
                         src_articol, src_group_path, match_status, updated_at)
                        VALUES (u.cod, 'ULTRA', :i, u.guid, u.guid, u.articol,
                                u.gpath, u.status, SYSDATE)""",
                l=load_id, i=import_id)
    marked = cur.rowcount
    con.commit()
    return {"import_id": import_id, "marked": marked, "new": new, "existing": exist}


def prune_staging(con, keep: int = 3) -> None:
    """Уборка СТЕЙДЖИНГА (не прода): старые загрузки ULTRA_*, кроме последних N.
    Почасовой cron иначе оставлял бы 37k строк RAW каждый час."""
    cur = con.cursor()
    cur.execute("""SELECT load_id FROM biro26pt_file
                    WHERE src_file LIKE 'ULTRA%' ORDER BY load_id DESC""")
    old = [r[0] for r in cur.fetchall()][keep:]
    for lid in old:
        for t in ("biro26pt_stg", "biro26pt_map", "biro26pt_raw",
                  "biro26pt_header", "biro26pt_file"):
            cur.execute(f"DELETE FROM {t} WHERE load_id = :l", l=lid)
    con.commit()
    if old:
        print(f"  стейджинг: убраны старые загрузки ULTRA {old}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--xlsx", default="/tmp/ULTRA_publish.xlsx")
    # RO: ca operatorul: DRY-RUN pe o incarcare, apoi --commit pe ACEEASI incarcare
    ap.add_argument("--load-id", type=int, help="reuse an already loaded/classified load")
    args = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))

    con = connect()
    if args.load_id:
        load_id = args.load_id
        print(f"повторное использование загрузки load_id={load_id}")
    else:
        st = export_xlsx(con, args.xlsx)
        print(f"экспорт: {st['rows']} строк, мост по штрихкоду: {st['linked']} "
              f"(карточек GOG с uuid: {st['bridge_cards']}) -> {args.xlsx}")
        load_id = load_raw(args.xlsx)
        print(f"загрузка RAW: load_id={load_id}")
    for ln in run_import(con, load_id, args.commit):
        print("  " + ln)
    if args.commit:
        mk = write_markers(con, load_id)
        print(f"  журнал import_id={mk['import_id']}, маркеров источника: {mk['marked']} "
              f"(новых {mk['new']}, существующих {mk['existing']})")
        prune_staging(con, keep=3)
    print("\nрежим:", "ЗАПИСЬ (p_commit=TRUE)" if args.commit else "разбор без записи")


if __name__ == "__main__":
    main()
