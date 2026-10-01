"""Relevanta cautarii in catalog (vitrina, Partner API, chatbot).

RO: pina la 01.10.2026 rezultatele cautarii veneau ALFABETIC: la "pix"
    primele erau "2E Gaming mouse…" si "34\\" ASUS ROG…" — se potriveau doar
    prin descriere (senzor PixArt din TMS_MPT_WEBATTR), iar pixurile adevarate
    erau la mii de rinduri distanta (4538 de rezultate). Aici sta ORDER BY-ul
    de relevanta; Biro26Store.get_products_stock doar il lipeste.
    Documentatie: docs/Biro26/CAUTARE_RELEVANTA_2026-10-01.md
EN: storefront search used to rank alphabetically; this is the relevance
    ORDER BY used by Biro26Store.get_products_stock when a search term is
    given and the sort is the default one.

Treptele (mai mic = mai sus):
    0  DENUMIREA incepe cu termenul, sau CODVECHI = termenul exact
    1  un cuvint din DENUMIREA incepe cu termenul ('% '||termen||'%')
    2  termenul apare oriunde in DENUMIREA
    3  NAMERUS / CODVECHI / cod de bare contin termenul
    4  potrivire doar prin TMS_MPT_WEBATTR (denumire completa, descriere)
In interiorul treptei — DENUMIREA, COD (ordinea alfabetica de pina acum).

FARA bind-uri noi: totul se scoate din `:s` = '%termen%', pe care filtrul de
cautare il leaga deja in AMBELE interogari (pagina si numaratoarea; si pe
drumul Oracle Text, unde `:sq` lipseste). SUBSTR(:s, 2) = 'termen%'. Asa
count_sql si cache-urile lui raman neatinse — nu exista riscul ORA-01036,
iar patch-ul se aplica identic peste versiunile diferite de pe servere.
"""
from typing import Optional

# RO: sortarile la care cautarea se ordoneaza dupa relevanta — doar cea
#     implicita (UI-ul nu trimite deloc ?sort=name). Pret si Z–A raman cum
#     le-a cerut vizitatorul.
DEFAULT_SORTS = ("name", "", None)

ORDER_BY = (
    " ORDER BY CASE"
    " WHEN UPPER(u.DENUMIREA) LIKE UPPER(SUBSTR(:s, 2))"
    "   OR u.CODVECHI = SUBSTR(:s, 2, LENGTH(:s) - 2) THEN 0"
    " WHEN UPPER(u.DENUMIREA) LIKE UPPER('% ' || SUBSTR(:s, 2)) THEN 1"
    " WHEN UPPER(u.DENUMIREA) LIKE UPPER(:s) THEN 2"
    " WHEN UPPER(u.NAMERUS) LIKE UPPER(:s) OR u.CODVECHI LIKE :s"
    "   OR EXISTS (SELECT 1 FROM TMS_MPT_BARCODE rb"
    "              WHERE rb.COD = u.COD AND rb.BARCODE LIKE :s) THEN 3"
    " ELSE 4 END, u.DENUMIREA, u.COD")


def applies(search: Optional[str], sort: Optional[str]) -> bool:
    return bool(search and str(search).strip()) and sort in DEFAULT_SORTS
