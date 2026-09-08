#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Схлопывание дублей «ULT-карточка, созданная сегодня» ↔ «июльская GOG-карточка».

    python3 modules/partner/scripts/ultra_dedup.py            # разбор, без записи
    python3 modules/partner/scripts/ultra_dedup.py --apply    # схлопнуть

Откуда дубли. Публикация 09.09.2026 связала июльские карточки по штрихкоду,
найденному через uuid картинки. У части товаров Ultra картинки с июля
сменились (Galaxy A27: было cdn.ultra.md, стало esempla), мост промахнулся,
и конвейер честно завёл им новые ULT-карточки — 118 по ключу «имя+цвет» и
35 по картинкам из полного списка image_urls.

Что делается для каждой пары (выживает GOG — у неё адреса на сайте и история
продаж; уходит сегодняшний ULT-дубль), в порядке Y_AI_BIRO26.dup_delete:

  0. бэкап строк дубля: Y_AI_ULTRA_DUP_UNIV / _PRICE / _TREE / _BC / _MPT
  1. цена: GOG получает сегодняшний период с ценами ULT-дубля, прежний
     период GOG закрывается (DATAEND = сегодня-1) — как в do_writes
  2. маркер: TMS_MPT_IMPSRC для GOG <- SRC_PID/SRC_ARTICOL дубля
  3. ссылки дубля чистятся: TPR1D_PERPRLIST, TMS_SYSGRP, TMS_MPT_BARCODE,
     TMS_MPT_TVR, TMS_MPT_IMPSRC, TMS_MPT_WEBATTR, TMS_MPT_WEBIMG, TMS_MPT
  4. BIRO26_GOODS.COD_UNIVERS дубля -> GOG (иначе следующий импорт воссоздаст)
  5. dup_set_triggers(FALSE) -> DELETE TMS_UNIVERS дубля -> dup_set_triggers(TRUE)
     (включение обратно — и в обработчике ошибок)

Ключи пар считаются на лету из июльского файла + буфера, только уникальные.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# RO: incarcarea din iulie 2026 — sursa auxiliara de chei pentru punte.
#     Calea se ia din mediu, altfel din primul loc gasit: pe server fisierul
#     sta linga proiect, pe statia de lucru — in Set_data_import.
# EN: July 2026 load, auxiliary bridge-key source; path from env or first hit.
JULY_XLSX = next(
    (q for q in (os.environ.get("PARTNER_ULTRA_JULY_XLSX"),
                 os.path.join(ROOT, "data", "ULTRA_iulie_2026.xlsx"),
                 "/Users/pt/Projects.AI/BIRO26/Set_data_import/8/ULTRA.md (1).xlsx")
     if q and os.path.exists(q)), "")
REFS = [  # (таблица, колонка кода) — что чистится у дубля
    ("TPR1D_PERPRLIST", "SC"), ("TMS_SYSGRP", "SC"), ("TMS_MPT_BARCODE", "COD"),
    ("TMS_MPT_TVR", "COD"), ("TMS_MPT_IMPSRC", "COD"), ("TMS_MPT_WEBATTR", "COD"),
    ("TMS_MPT_WEBIMG", "COD"), ("TMS_MPT", "COD"),
]
BACKUP = {"TMS_UNIVERS": "COD", "TPR1D_PERPRLIST": "SC", "TMS_SYSGRP": "SC",
          "TMS_MPT_BARCODE": "COD", "TMS_MPT": "COD"}


def norm(x) -> str:
    return re.sub(r"[^A-Z0-9А-Я]", "", str(x or "").upper())


def connect():
    import oracledb
    from config import Config
    oracledb.init_oracle_client(lib_dir=Config.BIRO26_INSTANT_CLIENT)
    return oracledb.connect(user=Config.BIRO26_DB_USER, password=Config.BIRO26_DB_PASSWORD,
                            dsn=Config.BIRO26_DB_DSN)


def find_pairs(con) -> dict[int, int]:
    """{cod дубля ULT: cod выжившей GOG} — по SRC_PID (uuid товара у Ultra).

    Раньше пары искались по июльскому xlsx, лежащему только на рабочей машине.
    На сервере файла нет, мост молча деградировал и прогон 08.09.2026 завёл
    1 339 дублей. Теперь источник — сама база: после публикации у каждой
    карточки в TMS_MPT_IMPSRC стоит SRC_PID = uuid товара у Ultra, и один
    uuid на двух активных карточках это и есть дубль.

    Берём только пары «GOG (июльская, выживает) + ULT (созданная импортом)»
    ровно по две на uuid. Пары GOG+GOG — старые июльские дубли, отдельный
    вопрос ассортимента, их не трогаем.
    """
    cur = con.cursor()
    pairs: dict[int, int] = {}
    for pid, cards in cur.execute("""
        SELECT i.src_pid,
               LISTAGG(u.codvechi || '=' || u.cod, ',') WITHIN GROUP (ORDER BY u.cod)
          FROM tms_mpt_impsrc i
          JOIN tms_univers u ON u.cod = i.cod AND u.tip = 'P'
                            AND NVL(u.isarhiv, '0') <> '2'
         WHERE i.src_source_code = 'ULTRA' AND i.src_pid IS NOT NULL
         GROUP BY i.src_pid
        HAVING COUNT(*) = 2"""):
        items = [x.split("=") for x in str(cards).split(",")]
        gog = [int(c) for a, c in items if a.startswith("GOG")]
        ult = [int(c) for a, c in items if a.startswith("ULT") and not a.startswith("ULTRAC")]
        if len(gog) == 1 and len(ult) == 1:
            pairs[ult[0]] = gog[0]
    # RO: acelasi predicat ca la punte — nu schlopuim doua marfuri diferite.
    #     Fara el, 08.09.2026 legatura a unit Xiaomi Poco M8 cu Epson L6550.
    import sys as _s
    _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ultra_publish import same_product
    ok, dropped = {}, 0
    for d, k in pairs.items():
        nd = cur.execute("SELECT denumirea FROM tms_univers WHERE cod=:c", c=d).fetchone()
        nk = cur.execute("SELECT denumirea FROM tms_univers WHERE cod=:c", c=k).fetchone()
        if nd and nk and same_product(nd[0], nk[0]):
            ok[d] = k
        else:
            dropped += 1
    if dropped:
        print(f"  отклонено пар с непохожими названиями: {dropped}")
    return ok


def apply(con, pairs: dict[int, int]) -> None:
    cur = con.cursor()
    today = dt.date.today()
    # 0) бэкап
    for tbl, col in BACKUP.items():
        bk = f"Y_AI_ULTRA_DUP_{tbl.replace('TMS_','').replace('TPR1D_','')[:18]}"
        if not cur.execute("SELECT COUNT(*) FROM user_tables WHERE table_name=:t", t=bk).fetchone()[0]:
            cur.execute(f"CREATE TABLE {bk} AS SELECT SYSDATE bak_at, t.* FROM {tbl} t WHERE 1=0")
        cur.executemany(f"INSERT INTO {bk} SELECT SYSDATE, t.* FROM {tbl} t WHERE t.{col} = :1",
                        [(d,) for d in pairs])
    con.commit()
    print("  бэкап сделан")

    for dup, keep in pairs.items():
        # 1) цена: период дубля (сегодня) -> GOG, старый период GOG закрыть
        row = cur.execute("""SELECT codgrp, pretv, pretv1, pretv2 FROM tpr1d_perprlist
                              WHERE codprice=1 AND sc=:d AND datastart=:t""", d=dup, t=today).fetchone()
        if row:
            cur.execute("""UPDATE tpr1d_perprlist SET dataend = :t - 1
                            WHERE codprice=1 AND sc=:k AND datastart < :t AND dataend >= :t""",
                        t=today, k=keep)
            cur.execute("""MERGE INTO tpr1d_perprlist p
                           USING (SELECT :k sc FROM dual) s ON (p.codprice=1 AND p.sc=s.sc AND p.datastart=:t)
                           WHEN MATCHED THEN UPDATE SET p.pretv=:pv, p.pretv1=:p1, p.pretv2=:p2
                           WHEN NOT MATCHED THEN INSERT (codprice, codgrp, sc, datastart, dataend, pretv, pretv1, pretv2)
                                VALUES (1, :cg, :k, :t, DATE '3000-01-01', :pv, :p1, :p2)""",
                        k=keep, t=today, cg=row[0], pv=row[1], p1=row[2], p2=row[3])
        # 2) маркер источника -> GOG
        cur.execute("""MERGE INTO tms_mpt_impsrc t
                       USING (SELECT src_import_id, src_row_guid, src_pid, src_articol, src_group_path
                                FROM tms_mpt_impsrc WHERE cod=:d) u ON (t.cod=:k)
                       WHEN MATCHED THEN UPDATE SET t.src_source_code='ULTRA', t.src_import_id=u.src_import_id,
                            t.src_row_guid=u.src_row_guid, t.src_pid=u.src_pid, t.src_articol=u.src_articol,
                            t.src_group_path=u.src_group_path, t.match_status='DEDUP', t.updated_at=SYSDATE
                       WHEN NOT MATCHED THEN INSERT (cod, src_source_code, src_import_id, src_row_guid, src_pid,
                            src_articol, src_group_path, match_status, updated_at)
                            VALUES (:k, 'ULTRA', u.src_import_id, u.src_row_guid, u.src_pid, u.src_articol,
                                    u.src_group_path, 'DEDUP', SYSDATE)""", d=dup, k=keep)
        # 3) ссылки дубля
        for tbl, col in REFS:
            cur.execute(f"DELETE FROM {tbl} WHERE {col} = :d", d=dup)
        # 4) буфер -> GOG. На BIRO26_GOODS.COD_UNIVERS стоит УНИКАЛЬНЫЙ индекс,
        #    а код GOG уже держит июльская строка буфера: сначала убираем её
        #    (устаревший буфер июля; строка ULTRA несёт свежие фото и angro),
        #    потом переводим строку ULTRA на код GOG.
        cur.execute("DELETE FROM biro26_goods WHERE cod_univers=:k AND NVL(sheet,'-') <> 'ULTRA'", k=keep)
        cur.execute("UPDATE biro26_goods SET cod_univers=:k WHERE cod_univers=:d", k=keep, d=dup)
    con.commit()
    print(f"  цена, маркер и ссылки перенесены для {len(pairs)} пар")

    # 5) удаление дублей из TMS_UNIVERS под выключенными защитными триггерами
    # RO: Y_AI_BIRO26.dup_set_triggers exista doar in .pkg.sql, NU in baza
    #     (09.09.2026: PLS-00302). Facem acelasi lucru direct, cu lista lui.
    TRG = ("TMS_UNIVERS_DONT_DELETE", "TMS_UNIVERS_DONT_DELETE_2022", "TMH_UNIVERS_TRG")
    for t in TRG:
        cur.execute(f"ALTER TRIGGER {t} DISABLE")
    deleted = failed = 0
    try:
        for dup in pairs:
            try:
                cur.execute("DELETE FROM tmh_univers WHERE cod = :d", d=dup)
            except Exception:  # noqa: BLE001 — истории может не быть
                pass
            try:
                cur.execute("DELETE FROM tms_univers WHERE cod = :d", d=dup)
                deleted += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  ! {dup}: {str(e)[:90]}")
        con.commit()
    finally:
        for t in TRG:
            cur.execute(f"ALTER TRIGGER {t} ENABLE")
        con.commit()
    print(f"  удалено дублей: {deleted}, не удалось: {failed}; триггеры включены обратно")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    con = connect()
    pairs = find_pairs(con)
    print(f"пар дубль(ULT) -> выживший(GOG): {len(pairs)}")
    cur = con.cursor()
    for d, k in list(pairs.items())[:5]:
        print("  ", cur.execute("SELECT codvechi||' '||SUBSTR(denumirea,1,40) FROM tms_univers WHERE cod=:c", c=d).fetchone()[0],
              " ->", cur.execute("SELECT codvechi||' '||SUBSTR(denumirea,1,40) FROM tms_univers WHERE cod=:c", c=k).fetchone()[0])
    json.dump(pairs, open("/tmp/ultra_dedup_pairs.json", "w"))
    if not args.apply:
        print("разбор без записи (нужен --apply)")
        return
    apply(con, pairs)


if __name__ == "__main__":
    main()
