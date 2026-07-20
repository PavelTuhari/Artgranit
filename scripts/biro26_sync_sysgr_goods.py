#!/usr/bin/env python3
"""RO: SINCRONIZARE plasarea nativa din arborele TMS_SYSGR* -> gruparea
Biro26 (BIRO26_GOODS.GRUPA/CATEGORIE) — sursa din care back-office-ul
si magazinul construiesc «Grupe de marfa». Vezi
docs/Biro26/RASPUNS_TASK_BACKOFFICE_ARBORE_GRUPE.md pentru context.

Model nativ (ID0=1): TMS_SYSGRPH — noduri (GROUP1=cod nivel 1,
GROUP2=cod nivel 2, 0 = nodul insusi; COMENT=numele; SCH=TMS_UNIVERS
TIP='T'); TMS_SYSGRP — plasari produse (GROUP1/GROUP2 + SC=cod produs).

Utilizare:
  python3 scripts/biro26_sync_sysgr_goods.py --group1 301            # dry-run
  python3 scripts/biro26_sync_sysgr_goods.py --group1 301 --go       # aplica
  python3 scripts/biro26_sync_sysgr_goods.py --group1 301 --brand ULTRA --go
NB: numele cu '?' (diacritice pierdute la scriere in CL8MSWIN1251) se
raporteaza — corectati-le intai in TMS_SYSGRPH.COMENT (fara diacritice).
"""
import argparse
import sys

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(
    __import__('os').path.abspath(__file__))))

from config import Config  # noqa: E402
import oracledb  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--group1', type=int, required=True,
                   help='codul GROUP1 al nodului de nivel 1 (ex. 301)')
    p.add_argument('--brand', default='', help='BRAND/FURNIZOR de scris')
    p.add_argument('--go', action='store_true', help='aplica (implicit dry-run)')
    a = p.parse_args()

    oracledb.init_oracle_client(lib_dir=Config.BIRO26_INSTANT_CLIENT)
    c = oracledb.connect(user=Config.BIRO26_DB_USER,
                         password=Config.BIRO26_DB_PASSWORD,
                         dsn=Config.BIRO26_DB_DSN)
    cur = c.cursor()

    cur.execute("SELECT COMENT FROM TMS_SYSGRPH WHERE ID0=1 AND GROUP1=:g AND GROUP2=0",
                {'g': a.group1})
    row = cur.fetchone()
    if not row:
        sys.exit(f"Nodul GROUP1={a.group1} nu exista in TMS_SYSGRPH")
    grupa = row[0]
    cur.execute("SELECT GROUP2, COMENT FROM TMS_SYSGRPH WHERE ID0=1 AND GROUP1=:g AND GROUP2>0 ORDER BY GROUP2",
                {'g': a.group1})
    cats = dict(cur.fetchall())
    bad = [n for n in [grupa] + list(cats.values()) if '?' in (n or '')]
    if bad:
        print("ATENTIE — nume cu diacritice pierdute ('?'), corectati intai:")
        for b in bad:
            print('  ', b)
        sys.exit(1)

    print(f"Grupa: {grupa} | {len(cats)} categorii")
    total = 0
    for g2, cat in cats.items():
        cur.execute("""SELECT COUNT(*) FROM TMS_SYSGRP p
                       JOIN TMS_UNIVERS u ON u.COD=p.SC AND u.TIP='P'
                       WHERE p.ID0=1 AND p.GROUP1=:g AND p.GROUP2=:g2
                       AND NOT EXISTS (SELECT 1 FROM BIRO26_GOODS b
                                       WHERE b.COD_UNIVERS=p.SC)""",
                    {'g': a.group1, 'g2': g2})
        n = cur.fetchone()[0]
        total += n
        print(f"  {cat}: {n} produse de sincronizat")
        if a.go and n:
            cur.execute("""INSERT INTO BIRO26_GOODS
                             (COD_UNIVERS, GRUPA, CATEGORIE, BRAND, FURNIZOR, DENUMIRE)
                           SELECT p.SC, :gr, :cat, :br, :br2, u.DENUMIREA
                           FROM TMS_SYSGRP p
                           JOIN TMS_UNIVERS u ON u.COD=p.SC AND u.TIP='P'
                           WHERE p.ID0=1 AND p.GROUP1=:g AND p.GROUP2=:g2
                           AND NOT EXISTS (SELECT 1 FROM BIRO26_GOODS b
                                           WHERE b.COD_UNIVERS=p.SC)""",
                        {'gr': grupa, 'cat': cat, 'br': a.brand or None,
                         'br2': a.brand or None, 'g': a.group1, 'g2': g2})
    if a.go:
        c.commit()
        print(f"APLICAT: {total} rinduri inserate in BIRO26_GOODS")
        print("Nu uitati traducerile RU/EN: /UNA.md/orasldev/biro26-translations")
    else:
        print(f"DRY-RUN: {total} rinduri de inserat — rulati cu --go")
    c.close()


if __name__ == '__main__':
    main()
