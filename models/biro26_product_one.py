"""Fisa UNUI singur produs — drum scurt, fara masinaria de catalog.

RO: pagina produsului si robotii cer mereu acelasi lucru: UN rind, dupa COD.
Pina acum trecea prin interogarea de catalog, care aduna stocul si rezervarile
pentru INTREG nomenclatorul (`GROUP BY` peste `YBIRO_STOCK_CALC_ITEM` si peste
comenzile din `VMDB_ST201D`), apoi lipea rezultatul de un singur rind. Costa
~1,3 s de fiecare data si a incarcat baza cind Googlebot a inceput sa citeasca
magazinul (01.09.2026: peste 130 de apeluri `?cod=N&limit=1` intr-o singura
fereastra de log).

Aici acelasi rezultat se ia cu subinterogari CORELATE, filtrate din start dupa
COD-ul cerut: aceleasi valori, dar Oracle atinge doar rindurile produsului.

Fisier separat intentionat (regula nr. 2 din CLAUDE.md): in
`biro26_oracle_store.py` ramine o singura linie de apel, ca sa nu se piarda la
prima rescriere a fisierului comun.

EN: fast single-product lookup; correlated scalar subqueries instead of the
catalog-wide aggregates.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# RO: pretul retail efectiv — aceeasi expresie ca in catalog (RETAIL1 e text
#     in feed, se converteste doar daca arata a numar).
_PRICE = ("NVL(pl.PRETV, CASE WHEN REGEXP_LIKE(TRIM(g.RETAIL1), "
          "'^-?[0-9]+([.,][0-9]+)?$') THEN "
          "TO_NUMBER(REPLACE(TRIM(g.RETAIL1),',','.')) END)")

# RO: cantitatea blocata de comenzile magazinului — aceeasi regula ca in
#     catalog (comanda nelivrata SAU livrata dupa data instantaneului de
#     stoc), dar corelata pe un singur COD.
_RESERVED = (
    "(SELECT NVL(SUM(NVL(d.CANT, 0)), 0) FROM VMDB_ST201D d "
    "   JOIN VMDB_ST201M mm ON mm.NRDOC = d.NRDOC "
    "   JOIN VMDB_DOCS   hh ON hh.COD = d.NRDOC AND hh.SYSFID = 12280 "
    "  WHERE d.CTSC = u.COD AND ("
    "        mm.CTNRDOC IS NULL "
    "     OR NVL((SELECT dh.DATAMANUAL FROM VMDB_DOCS dh "
    "               WHERE dh.COD = mm.CTNRDOC), hh.DATAMANUAL) > "
    "        NVL((SELECT MAX(DATA_DOC) FROM YBIRO_STOCK_CALC "
    "               WHERE IS_LATEST = '1'), DATE '1900-01-01')))")

_SQL = f"""
SELECT x.*, GREATEST(NVL(x.REAL_CANT, 0) - NVL(x.RESERVED, 0), 0) AVAIL_CANT
FROM (
  SELECT u.COD, u.CODVECHI, u.DENUMIREA, u.NAMERUS, u.UM, u.TIP,
         g.GRUPA, g.CATEGORIE, g.BRAND,
         NVL(mp.MATGR1, 0) MATGR1,
         NVL(pl.PRETV1, g.ANGRO) ANGRO,
         NVL(pl.PRETV2, g.IONLINE) IONLINE,
         {_PRICE} RETAIL1,
         ROUND(NVL(pl.PRETV1, g.ANGRO)/1.2, 2) ANGRO_FARA_TVA,
         NVL((SELECT mt.IE_LINKADRES FROM VMS_MPT_TVR mt
               WHERE mt.COD = u.COD AND ROWNUM = 1),
             NVL(g.PHOTO_URL, g.IMAGE_LINK)) IMAGE,
         (SELECT SUM(i.CANT) FROM YBIRO_STOCK_CALC_ITEM i
           WHERE i.SC = u.COD
             AND i.CALC_ID = (SELECT id FROM YBIRO_STOCK_CALC
                               WHERE is_latest = '1')) REAL_CANT,
         {_RESERVED} RESERVED,
         (SELECT MIN(b.BARCODE) FROM TMS_MPT_BARCODE b
           WHERE b.COD = u.COD) BARCODE,
         (SELECT COUNT(*) FROM TMS_MPT_BARCODE b
           WHERE b.COD = u.COD) BC_CNT,
         vr.VARIANT, vr.MASTER_COD,
         CASE WHEN vr.MASTER_COD IS NULL THEN 1 ELSE
           (SELECT COUNT(*) FROM BIRO26_VARIANTS v2
             WHERE v2.MASTER_COD = vr.MASTER_COD) END VAR_CNT,
         w.DENUMIRE_FULL_RO DENUM_FULL, w.DENUMIRE_FULL_RU DENUM_FULL_RU
  FROM TMS_UNIVERS u
  LEFT JOIN (SELECT * FROM (SELECT g0.* FROM BIRO26_GOODS g0
                             WHERE g0.COD_UNIVERS = :cod
                             ORDER BY g0.ID)
              WHERE ROWNUM = 1) g ON g.COD_UNIVERS = u.COD
  LEFT JOIN TPR1D_PERPRLIST pl ON pl.CODPRICE = 1 AND pl.SC = u.COD
        AND TO_DATE(:pd,'YYYY-MM-DD') BETWEEN pl.DATASTART AND pl.DATAEND
  LEFT JOIN TMS_MPT mp ON mp.COD = u.COD
  LEFT JOIN TMS_MPT_WEBATTR w ON w.COD = u.COD
  LEFT JOIN BIRO26_VARIANTS vr ON vr.COD_UNIVERS = u.COD
  WHERE u.COD = :cod AND u.TIP = 'P' {{arch}}
) x
"""


def fetch(cod: int, price_date: str,
          archived: bool = False) -> Optional[Dict[str, Any]]:
    """RO: un rind in exact forma pe care o intoarce grila de catalog.

    None inseamna „nu s-a putut pe drumul scurt" — apelantul continua pe
    drumul obisnuit, deci o schimbare in baza nu poate strica pagina.
    """
    try:
        from models.biro26_db import Biro26DB
        from models.biro26_oracle_store import _rows
        sql = _SQL.replace("{arch}", " AND u.ISARHIV = '2'" if archived
                           else " AND NVL(u.ISARHIV,'0') <> '2'")
        rows = _rows(Biro26DB().execute_query(
            sql, {"cod": int(cod), "pd": price_date}))
        if not rows:
            return {"success": True, "data": [], "total": 0}
        from models.biro26_imgproxy import rewrite_rows
        rewrite_rows(rows, "IMAGE")
        return {"success": True, "data": rows, "total": len(rows)}
    except Exception:                                        # noqa: BLE001
        return None
