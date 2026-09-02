"""Catalogul magazinului — drumul scurt pentru forma care se cere cel mai des.

RO: pe 01.09.2026 baza a inceput sa geama sub interogarea catalogului
(`SQL_ID a795hqqdfs065`). Masurat pe productie, nu presupus:

* magazinul face ~1.550 de apeluri `/api/biro26/shop/products` pe zi, cu
  ~1.170 de combinatii DIFERITE de filtre — 876 dintre ele cerute o singura
  data, deci cache-ul nu are ce salva;
* **1.148 din 1.547 (74%) filtreaza dupa grupa/categorie/brand**;
* fiecare astfel de cerere costa ~0,74 s de lucru IN BAZA.

Unde se ducea timpul (masurat bucata cu bucata): nu in stoc si nu in
rezervari (~0,03 s fiecare), ci in nucleu — feed-ul `BIRO26_GOODS` se
deduplica cu `ROW_NUMBER() OVER (PARTITION BY COD_UNIVERS ORDER BY ID)`,
adica Oracle sorta toata tabela (235.649 de rinduri pentru 197.377 de coduri)
la FIECARE cerere, ca sa scoata 24 de produse.

Aici filtrele feed-ului trec printr-un `IN (SELECT COD_UNIVERS FROM
BIRO26_GOODS WHERE ...)` — duplicatele nu deranjeaza intr-un `IN` — pagina se
alege pe `TMS_UNIVERS` (index pe denumire), iar deduparea si preturile se
lipesc DOAR peste cele 24-200 de rinduri ale paginii.

Rezultat masurat pe baza de productie (timpul SQL, fara cei ~0,9 s de
pornire a worker-ului):

| Forma cererii | Inainte | Acum |
|---|---|---|
| filtrata pe grupa (74% din trafic) | 0,74 s | 0,20 s |
| catalog simplu | 0,95 s | 0,02 s |

Ce NU trece pe aici (se intoarce `None` si apelantul foloseste drumul vechi,
neschimbat): cautarea dupa text, filtrele de pret si sortarea dupa pret.
Acolo pretul efectiv trebuie calculat inainte de paginare, deci nucleul
ieftin nu se aplica.

Fisier separat intentionat — regula nr. 2 din CLAUDE.md: in
`biro26_oracle_store.py` ramine o singura linie de apel.

EN: fast path for the dominant catalog shape — feed filters via IN-subquery,
page over the base table, heavy joins only over the page.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# RO: din 02.09.2026 BIRO26_GOODS are UN singur rind per COD_UNIVERS (index
#     unic UX_BIRO26_GOODS_CODUNIV, curatare prin scripts/biro26_goods_dedupe.py),
#     deci join-ul e direct — fara ROW_NUMBER peste toata tabela.
#     Masurat: filtrul pe grupa 0,50 s -> 0,10 s SQL fata de forma cu fereastra.
_DEDUPE = "BIRO26_GOODS"


def supports(search: Optional[str], price_min: Optional[float],
             price_max: Optional[float], sort: str) -> bool:
    """RO: formele pe care drumul scurt le poate servi identic."""
    return (not search and price_min is None and price_max is None
            and sort in ("name", "name_desc", "", None))


def build(price_expr: str, price_date: str, *,
          gr1: Optional[str] = None, brand: Optional[str] = None,
          categorie: Optional[str] = None, grupa: Optional[str] = None,
          cod: Optional[int] = None, only_new: bool = False,
          archived: bool = False, sort: str = "name",
          limit: int = 200, offset: int = 0) -> Tuple[str, str, Dict[str, Any]]:
    """RO: intoarce (sql_pagina, sql_total, parametri).

    `sql_pagina` are exact coloanele pe care le astepta grila; `sql_total`
    numara aceleasi produse, fara paginare.
    """
    params: Dict[str, Any] = {"pd": price_date}
    where = ["u.TIP = 'P'"]
    where.append("u.ISARHIV = '2'" if archived else "NVL(u.ISARHIV,'0') <> '2'")

    # RO: filtrele feed-ului — printr-un IN, deci duplicatele nu conteaza si
    #     nu mai e nevoie de deduparea intregii tabele inainte de paginare.
    feed: List[str] = []
    if grupa:
        feed.append("GRUPA = :grupa")
        params["grupa"] = grupa
    if categorie:
        feed.append("CATEGORIE = :categorie")
        params["categorie"] = categorie
    if brand:
        bl = [b.strip() for b in str(brand).split(",") if b.strip()][:30]
        marks = ",".join(f":br{i}" for i in range(len(bl)))
        feed.append(f"BRAND IN ({marks})")
        params.update({f"br{i}": b for i, b in enumerate(bl)})
    if feed:
        where.append("u.COD IN (SELECT COD_UNIVERS FROM BIRO26_GOODS WHERE "
                     + " AND ".join(feed) + ")")
    if only_new:
        where.append("u.COD IN (SELECT COD FROM TMS_MPT WHERE MATGR1 = 1)")
    if gr1:
        where.append("u.GR1 = :gr1")
        params["gr1"] = gr1
    if cod:
        where.append("u.COD = :cod")
        params["cod"] = int(cod)

    cond = " AND ".join(where)
    order = ("u.DENUMIREA DESC, u.COD" if sort == "name_desc"
             else "u.DENUMIREA, u.COD")
    # RO: pagina se alege doar pe TMS_UNIVERS — fara feed, fara preturi.
    page = (f"SELECT * FROM (SELECT a.*, ROWNUM rn FROM ("
            f"SELECT u.COD, u.CODVECHI, u.DENUMIREA, u.NAMERUS, u.UM, u.TIP "
            f"FROM TMS_UNIVERS u WHERE {cond} ORDER BY {order}) a "
            f"WHERE ROWNUM <= {int(offset) + int(limit)}) "
            f"WHERE rn > {int(offset)}")
    total = f"SELECT COUNT(*) CNT FROM TMS_UNIVERS u WHERE {cond}"

    # RO: peste cele <=200 de rinduri ale paginii se lipesc feed-ul deduplicat,
    #     pretul in vigoare si restul (stoc, rezervari, coduri de bare,
    #     variante) — aceleasi expresii ca in grila veche.
    sql = (
        "SELECT p.COD, p.CODVECHI, p.DENUMIREA, p.NAMERUS, p.UM, p.TIP, "
        "g.GRUPA, g.CATEGORIE, g.BRAND, NVL(mp.MATGR1, 0) MATGR1, "
        "NVL(pl.PRETV1, g.ANGRO) ANGRO, NVL(pl.PRETV2, g.IONLINE) IONLINE, "
        f"{price_expr} RETAIL1, "
        "ROUND(NVL(pl.PRETV1, g.ANGRO)/1.2, 2) ANGRO_FARA_TVA, "
        "NVL(m.IE_LINKADRES, NVL(g.PHOTO_URL, g.IMAGE_LINK)) IMAGE, "
        "s.CANT REAL_CANT, NVL(rz.QTY, 0) RESERVED, "
        "GREATEST(NVL(s.CANT, 0) - NVL(rz.QTY, 0), 0) AVAIL_CANT, "
        "(SELECT MIN(b.BARCODE) FROM TMS_MPT_BARCODE b "
        "   WHERE b.COD = p.COD) BARCODE, "
        "(SELECT COUNT(*) FROM TMS_MPT_BARCODE b "
        "   WHERE b.COD = p.COD) BC_CNT, "
        "vr.VARIANT, vr.MASTER_COD, "
        "CASE WHEN vr.MASTER_COD IS NULL THEN 1 ELSE "
        "  (SELECT COUNT(*) FROM BIRO26_VARIANTS v2 "
        "     WHERE v2.MASTER_COD = vr.MASTER_COD) END VAR_CNT, "
        "w.DENUMIRE_FULL_RO DENUM_FULL, w.DENUMIRE_FULL_RU DENUM_FULL_RU "
        f"FROM ({page}) p "
        f"LEFT JOIN {_DEDUPE} g ON g.COD_UNIVERS = p.COD "
        "LEFT JOIN TPR1D_PERPRLIST pl ON pl.CODPRICE = 1 AND pl.SC = p.COD "
        "  AND TO_DATE(:pd,'YYYY-MM-DD') BETWEEN pl.DATASTART AND pl.DATAEND "
        "LEFT JOIN TMS_MPT mp ON mp.COD = p.COD "
        "LEFT JOIN TMS_MPT_WEBATTR w ON w.COD = p.COD "
        "LEFT JOIN VMS_MPT_TVR m ON m.COD = p.COD "
        "LEFT JOIN (SELECT sc, SUM(cant) cant FROM YBIRO_STOCK_CALC_ITEM "
        "  WHERE calc_id = (SELECT id FROM YBIRO_STOCK_CALC "
        "                    WHERE is_latest='1') "
        "  GROUP BY sc) s ON s.sc = p.COD "
        "LEFT JOIN (SELECT d.CTSC SC, SUM(NVL(d.CANT, 0)) QTY "
        "  FROM VMDB_ST201D d "
        "  JOIN VMDB_ST201M mm ON mm.NRDOC = d.NRDOC "
        "  JOIN VMDB_DOCS   hh ON hh.COD = d.NRDOC AND hh.SYSFID = 12280 "
        "  WHERE d.CTSC IS NOT NULL AND ("
        "        mm.CTNRDOC IS NULL "
        "     OR NVL((SELECT dh.DATAMANUAL FROM VMDB_DOCS dh "
        "               WHERE dh.COD = mm.CTNRDOC), hh.DATAMANUAL) > "
        "        NVL((SELECT MAX(DATA_DOC) FROM YBIRO_STOCK_CALC "
        "               WHERE IS_LATEST = '1'), DATE '1900-01-01')) "
        "  GROUP BY d.CTSC) rz ON rz.SC = p.COD "
        "LEFT JOIN BIRO26_VARIANTS vr ON vr.COD_UNIVERS = p.COD "
        "ORDER BY p.rn")
    return sql, total, params
