"""RO: Harta site-ului pentru officeplus.md.
EN: The sitemap for officeplus.md.

RO: In harta intra DOAR ce se poate cumpara: pozitie cu stoc, cu pret de
    internet si cu fotografie. Vitrina arata mult mai mult, dar o pagina
    unde nu se poate comanda nimic nu merita indexata - aduce vizitatorul
    degeaba si strica parerea motorului de cautare despre magazin.
EN: Only what can actually be bought goes into the sitemap: an item with
    stock, with an online price and with a photo. The storefront shows far
    more, but a page where nothing can be ordered is not worth indexing.

RO: Un fisier de harta tine cel mult 50 000 de adrese, iar nucleul este mai
    mare, asa ca /sitemap.xml este un INDEX care trimite la fisiere pe
    bucati.
EN: One sitemap file holds at most 50 000 addresses and the core is larger,
    so /sitemap.xml is an INDEX pointing at chunk files.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from models.biro26_db import Biro26DB

# RO: limita standard e 50 000; luam mai putin ca fisierul sa ramina mic.
# EN: the standard limit is 50 000; we take less to keep each file small.
CHUNK = 20000

# RO: harta se schimba o data pe zi, nu la fiecare cerere.
# EN: the map changes once a day, not on every request.
CACHE_TTL = 3600

_cache: Dict[str, Any] = {}


def _cached(key: str, build):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    value = build()
    _cache[key] = (now, value)
    return value


def clear_cache() -> None:
    _cache.clear()


def _rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not result.get("success"):
        return []
    columns = [c.lower() for c in (result.get("columns") or [])]
    return [dict(zip(columns, row)) for row in (result.get("data") or [])]


# RO: conditia "se poate cumpara" - o singura data, ca sa nu se desincronizeze
#     intre harta si vitrina.
# EN: the "can be bought" condition in one place, so the sitemap and the
#     storefront cannot drift apart.
BUYABLE = ("g.STOC > 0 AND g.IONLINE > 1 "
           "AND NVL(g.PHOTO_URL, g.IMAGE_LINK) IS NOT NULL")

# RO: harta trebuie sa numere EXACT ca vitrina. Fisa poate lipsi din
#     dictionar sau poate fi arhivata - atunci adresa exista in feed, dar
#     magazinul nu o arata, iar motorul de cautare primeste o pagina goala.
# EN: the map must count EXACTLY like the storefront: an address in the feed
#     whose card is archived would give the crawler an empty page.
FROM_BUYABLE = ("FROM BIRO26_GOODS g "
                "JOIN TMS_UNIVERS u ON u.COD = g.COD_UNIVERS "
                f"WHERE u.TIP = 'P' AND NVL(u.ISARHIV, '0') <> '2' "
                f"AND {BUYABLE}")


def core_count() -> int:
    """RO: cite pozitii intra in harta. EN: how many items the map holds."""
    def build() -> int:
        rows = _rows(Biro26DB().execute_query(
            f"SELECT COUNT(DISTINCT g.COD_UNIVERS) N {FROM_BUYABLE}", {}))
        return int(rows[0]["n"]) if rows else 0
    return _cached("count", build)


def core_codes(part: int) -> List[int]:
    """RO: numerele pozitiilor din bucata ceruta (1, 2, 3...).

    Sortarea dupa COD tine bucatile stabile intre cereri: fara ea aceeasi
    pozitie ar putea sari dintr-un fisier in altul.
    """
    def build() -> List[int]:
        first = (part - 1) * CHUNK + 1
        last = part * CHUNK
        rows = _rows(Biro26DB().execute_query(
            "SELECT COD FROM ("
            "  SELECT COD, ROWNUM RN FROM ("
            f"   SELECT DISTINCT g.COD_UNIVERS AS COD {FROM_BUYABLE} "
            "    ORDER BY g.COD_UNIVERS"
            "  ) WHERE ROWNUM <= :last"
            ") WHERE RN >= :first",
            {"first": first, "last": last}))
        return [int(r["cod"]) for r in rows]
    return _cached(f"codes:{part}", build)


def core_groups() -> List[str]:
    """RO: grupele in care exista macar o pozitie de cumparat."""
    def build() -> List[str]:
        rows = _rows(Biro26DB().execute_query(
            f"SELECT g.GRUPA {FROM_BUYABLE} AND g.GRUPA IS NOT NULL "
            "GROUP BY g.GRUPA ORDER BY g.GRUPA", {}))
        return [r["grupa"] for r in rows if r.get("grupa")]
    return _cached("groups", build)


# RO: paginile fixe ale magazinului. EN: the shop's fixed pages.
STATIC_PAGES = ("/", "/catalog", "/branduri", "/livrare", "/despre-noi",
                "/contacte", "/retur-produse", "/credite",
                "/termeni-si-conditii", "/politica-de-confidentialitate")


def parts_count() -> int:
    total = core_count()
    return max(1, -(-total // CHUNK))


def _url(base: str, path: str, priority: str, freq: str) -> str:
    return ("  <url><loc>" + escape(base + path) + "</loc>"
            "<changefreq>" + freq + "</changefreq>"
            "<priority>" + priority + "</priority></url>")


def _wrap(body: List[str]) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(body) + "\n</urlset>\n")


def index_xml(base: str) -> str:
    """RO: /sitemap.xml - indexul care trimite la celelalte fisiere."""
    files = ["/sitemap-pages.xml", "/sitemap-categories.xml"]
    files += [f"/sitemap-products-{i}.xml" for i in range(1, parts_count() + 1)]
    body = ["  <sitemap><loc>" + escape(base + f) + "</loc></sitemap>"
            for f in files]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(body) + "\n</sitemapindex>\n")


def pages_xml(base: str) -> str:
    return _wrap([_url(base, p, "1.0" if p == "/" else "0.8", "daily")
                  for p in STATIC_PAGES])


def categories_xml(base: str) -> str:
    from urllib.parse import quote_plus
    body = [_url(base, "/catalog?grupa=" + quote_plus(g), "0.7", "daily")
            for g in core_groups()]
    return _wrap(body or [_url(base, "/catalog", "0.8", "daily")])


def products_xml(base: str, part: int) -> Optional[str]:
    if part < 1 or part > parts_count():
        return None
    codes = core_codes(part)
    return _wrap([_url(base, f"/produs/{c}", "0.6", "weekly") for c in codes])


def robots_txt(base: str) -> str:
    """RO: robots.txt care spune unde este harta.

    Regulile WordPress raman aceleasi; se adauga doar linia Sitemap si se
    inchid adresele care nu au ce cauta in index: cosul, contul, cautarea.
    """
    return (
        "User-agent: *\n"
        "Disallow: /wp-admin/\n"
        "Allow: /wp-admin/admin-ajax.php\n"
        "Disallow: /cos\n"
        "Disallow: /cont\n"
        "Disallow: /compara\n"
        "Disallow: /favorite\n"
        "Disallow: /*?q=\n"
        "Disallow: /*&q=\n"
        "Disallow: /*?sort=\n"
        "Disallow: /*&sort=\n"
        "Disallow: /*?page=\n"
        "Disallow: /*&page=\n"
        "\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
