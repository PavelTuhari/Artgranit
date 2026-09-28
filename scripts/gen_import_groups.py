#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RO: Exporta grupele aduse de un import ca FISIERE: CSV (lizibil) + SQL de anulare.
       Asa se poate raspunde, luni mai tirziu, la "de unde a aparut grupa asta si
       cum o scot?" fara sa deschizi baza.
   EN: Export the groups one import brought as FILES: a readable CSV plus a
       rollback SQL script.

RO: Utilizare / EN: usage:
      python3 scripts/gen_import_groups.py <import_id>
      python3 scripts/gen_import_groups.py --all

RO: Rezultatul ajunge in `grupe_import/<SURSA>_<import_id>_<data>.{csv,rollback.sql}`.
"""
import csv
import io
import os
import sys

import oracledb

LIB = "/Users/pt/Downloads/instantclient_23_26"
DSN = "orange.una.md:4024/cloudbd.world"
USER, PWD = "officeplus", "officeplus26"
OUTDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "grupe_import")


def export(cur, import_id):
    hdr = list(cur.execute(
        "SELECT l.source_code, l.src_file, TO_CHAR(l.started_at,'YYYY-MM-DD') d, "
        "       l.rows_total, l.rows_inserted, l.rows_matched, l.rows_skipped "
        "  FROM ybiro_import_log l WHERE l.import_id = :i", [import_id]))
    if not hdr:
        print(f"  import {import_id}: nu exista in jurnal"); return
    src, srcfile, day, tot, ins, mat, skp = hdr[0]

    rows = list(cur.execute(
        "SELECT group_path, group1, group2, group3, action, n_products, "
        "       (SELECT COUNT(*) FROM biro26_goods g "
        "         WHERE UPPER(TRIM(g.grupa)) = UPPER(TRIM(gg.group1)) "
        "           AND NVL(UPPER(TRIM(g.categorie)),'~') = NVL(UPPER(TRIM(gg.group2)),'~')) total_now "
        "  FROM ybiro_import_groups gg WHERE import_id = :i "
        " ORDER BY group1, group2, group3", [import_id]))
    if not rows:
        print(f"  import {import_id}: nicio grupa inregistrata"); return

    os.makedirs(OUTDIR, exist_ok=True)
    base = os.path.join(OUTDIR, f"{src}_{import_id}_{day}")

    with io.open(base + ".csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["GROUP_PATH", "GROUP1", "GROUP2", "GROUP3", "ACTION",
                    "N_PRODUCTS_THIS_IMPORT", "N_PRODUCTS_TOTAL_NOW"])
        for r in rows:
            w.writerow([r[0], r[1], r[2] or "", r[3] or "", r[4], r[5], r[6]])

    created = [r for r in rows if r[4] == "CREATED"]
    with io.open(base + ".rollback.sql", "w", encoding="utf-8") as f:
        a = f.write
        a("-- =====================================================================\n")
        a(f"-- RO: ANULAREA grupelor aduse de importul {import_id} ({src}).\n")
        a(f"-- EN: ROLLBACK of the groups brought by import {import_id} ({src}).\n")
        a(f"--     Fisier sursa / source file: {srcfile}\n")
        a(f"--     Data / date: {day}\n")
        a(f"--     Randuri: total {tot}, create {ins}, potrivite {mat}, sarite {skp}\n")
        a("--\n")
        a("-- RO: ATENTIE — scriptul NU se ruleaza automat. Citeste-l, verifica\n")
        a("--     numarul de marfuri din fiecare grupa (coloana N_PRODUCTS_TOTAL_NOW\n")
        a("--     din CSV-ul alaturat) si ruleaza doar ce vrei sa anulezi.\n")
        a("-- EN: WARNING — this script does not run itself. Read it, check how many\n")
        a("--     goods each group holds NOW, and run only what you mean to undo.\n")
        a("-- =====================================================================\n\n")
        a("-- RO: 1) marfurile aduse de acest import (le poti arhiva in loc sa le stergi)\n")
        a("-- EN: 1) the goods this import brought (archive rather than delete)\n")
        a("-- UPDATE tms_univers SET isarhiv = '2'\n")
        a("--  WHERE cod IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = "
          f"{import_id});\n\n")
        a("-- RO: 2) grupele CREATE de acest import (doar cele ramase goale)\n")
        a("-- EN: 2) groups CREATED by this import (only the ones left empty)\n")
        for r in created:
            g1, g2 = r[1], r[2]
            cond = f"UPPER(TRIM(grupa)) = UPPER(TRIM('{g1}'))"
            if g2:
                cond += f" AND UPPER(TRIM(categorie)) = UPPER(TRIM('{g2}'))"
            else:
                cond += " AND categorie IS NULL"
            a(f"-- {r[0]}   (acest import: {r[5]} marfuri; acum in total: {r[6]})\n")
            a(f"-- DELETE FROM biro26_goods WHERE {cond}\n")
            a(f"--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc "
              f"WHERE src_import_id = {import_id});\n\n")
        a("-- RO: 3) nodurile din arborele nativ ramase fara marfa\n")
        a("-- EN: 3) native-tree nodes left with no goods\n")
        a("-- DELETE FROM tms_sysgrph h WHERE h.id0 = 1\n")
        a("--   AND NOT EXISTS (SELECT 1 FROM tms_sysgrp g WHERE g.id0 = 1 AND g.id1 = h.id1)\n")
        a(f"--   AND UPPER(TRIM(h.coment)) IN (\n")
        names = sorted({(r[1] or "").strip().upper() for r in created if r[1]})
        a("--     " + ", ".join(f"'{n}'" for n in names) + ");\n\n")
        a(f"-- RO: 4) marcajele de sursa si evidenta grupelor\n")
        a(f"-- DELETE FROM tms_mpt_impsrc      WHERE src_import_id = {import_id};\n")
        a(f"-- DELETE FROM ybiro_import_groups WHERE import_id     = {import_id};\n")
        a(f"-- UPDATE ybiro_import_log SET notes = notes || ' [ANULAT]' "
          f"WHERE import_id = {import_id};\n")

    print(f"  {os.path.basename(base)}.csv          — {len(rows)} grupe "
          f"({len(created)} create)")
    print(f"  {os.path.basename(base)}.rollback.sql — script de anulare (comentat)")


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    oracledb.init_oracle_client(lib_dir=LIB)
    con = oracledb.connect(user=USER, password=PWD, dsn=DSN)
    cur = con.cursor()
    if sys.argv[1] == "--all":
        ids = [r[0] for r in cur.execute(
            "SELECT DISTINCT import_id FROM ybiro_import_groups ORDER BY import_id")]
    else:
        ids = [int(sys.argv[1])]
    for i in ids:
        export(cur, i)
    con.close()


if __name__ == "__main__":
    main()
