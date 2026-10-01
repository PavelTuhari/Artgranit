"""Relevanta cautarii in catalog (vitrina, Partner API, chatbot).

RO: pina la 01.10.2026 rezultatele cautarii veneau ALFABETIC: la "pix"
    primele erau "2E Gaming mouse…" si "34\\" ASUS ROG…" — se potriveau doar
    prin descriere (senzor PixArt din TMS_MPT_WEBATTR), iar pixurile adevarate
    erau la mii de rinduri distanta (4538 de rezultate). Aici se construieste
    ORDER BY-ul de relevanta; Biro26Store.get_products_stock doar il cheama.
    Documentatie: docs/Biro26/CAUTARE_RELEVANTA_2026-10-01.md
EN: storefront search used to rank alphabetically; this builds the relevance
    ORDER BY used by Biro26Store.get_products_stock when a search term is given
    and the sort is the default one.

Treptele (mai mic = mai sus):
    0  DENUMIREA incepe cu termenul, sau CODVECHI = termenul exact
    1  un cuvint din DENUMIREA incepe cu termenul ('% '||termen||'%')
    2  termenul apare oriunde in DENUMIREA
    3  NAMERUS / CODVECHI / cod de bare contin termenul
    4  potrivire doar prin TMS_MPT_WEBATTR (denumire completa, descriere)
In interiorul treptei — DENUMIREA, COD (ordinea alfabetica de pina acum).

Bind-urile au prefixul `rk_` si NU apar in interogarea de numarare (count_sql
se construieste inainte de ORDER BY). Apelantul le adauga doar la interogarea
paginii — altfel Oracle da ORA-01036 pe bind-urile in plus.
"""
from typing import Any, Dict, Optional, Tuple

# RO: sortarile la care cautarea se ordoneaza dupa relevanta — doar cea
#     implicita (UI-ul nu trimite deloc ?sort=name). Pret si Z–A raman cum
#     le-a cerut vizitatorul.
DEFAULT_SORTS = ("name", "", None)


def applies(search: Optional[str], sort: Optional[str]) -> bool:
    return bool(search and str(search).strip()) and sort in DEFAULT_SORTS


def order_by(q_norm: str) -> Tuple[str, Dict[str, Any]]:
    """RO: (clauza ORDER BY, bind-uri rk_*) pentru termenul normalizat."""
    q = (q_norm or "").strip()
    sql = (" ORDER BY CASE"
           " WHEN UPPER(u.DENUMIREA) LIKE UPPER(:rk_pre) OR u.CODVECHI = :rk_eq THEN 0"
           " WHEN UPPER(u.DENUMIREA) LIKE UPPER(:rk_word) THEN 1"
           " WHEN UPPER(u.DENUMIREA) LIKE UPPER(:rk_any) THEN 2"
           " WHEN UPPER(u.NAMERUS) LIKE UPPER(:rk_any) OR u.CODVECHI LIKE :rk_any"
           "   OR EXISTS (SELECT 1 FROM TMS_MPT_BARCODE rb"
           "              WHERE rb.COD = u.COD AND rb.BARCODE LIKE :rk_any) THEN 3"
           " ELSE 4 END, u.DENUMIREA, u.COD")
    binds = {"rk_pre": f"{q}%", "rk_eq": q,
             "rk_word": f"% {q}%", "rk_any": f"%{q}%"}
    return sql, binds
