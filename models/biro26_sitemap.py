"""RO: Harta site-ului (sitemap.xml) + robots.txt pentru magazinul public.
    EN: Sitemap and robots.txt for the public shop.

RO: De ce exista. Pina acum site-ul nu avea nici robots.txt, nici sitemap: motoarele
    de cautare trebuiau sa descopere singure catalogul urmarind legaturi — iar
    legaturile erau javascript:void(0), deci nu descopereau nimic. Legaturile sint
    reparate; harta face descoperirea rapida si controlabila: 1 251 de categorii si
    ~152 000 de produse, anuntate explicit.
EN: The site had no robots.txt and no sitemap; crawlers had to discover the catalogue
    by following links, and those were javascript:void(0). Links are fixed now; the
    sitemap makes discovery fast and explicit.

RO: Structura — un INDEX care trimite spre harti mai mici, pentru ca standardul
    accepta maxim 50 000 de adrese si 50 MB pe fisier:
      /sitemap.xml                -> indexul
      /sitemap-pages.xml          -> pagina principala + paginile de continut
      /sitemap-categories.xml     -> toate grupele si categoriile
      /sitemap-products-1..N.xml  -> produsele, cite 50 000
EN: An INDEX pointing to smaller sitemaps (the standard caps each file at 50 000 URLs).

RO: Interogarile spre Oracle sint SCUMPE (152 000 de randuri), de aceea fiecare harta
    se tine in memorie cite sase ore. Motoarele nu au nevoie de date la secunda.
EN: The Oracle queries are expensive, so each sitemap is cached in memory for 6 hours.
"""
from __future__ import annotations

import time
import urllib.parse
from typing import Any, Dict, List, Tuple
from xml.sax.saxutils import escape as xml_escape

from config import Config
from models.biro26_db import Biro26DB

# RO: cite adrese intr-un fisier (standardul admite 50 000) / EN: URLs per file
CHUNK = 50000
# RO: cit tine memoria harta, in secunde / EN: cache lifetime
TTL = 6 * 3600

# RO: paginile de continut care merita indexate. Cosul, contul, favoritele si
#     compararea NU au ce cauta in index — sint personale si fara continut util.
# EN: content pages worth indexing; cart/account/favourites/compare are personal.
STATIC_PAGES = ['/', '/catalog', '/branduri', '/livrare', '/credite',
                '/termeni-si-conditii', '/retur-produse', '/despre-noi',
                '/politica-de-confidentialitate', '/contacte']

_cache: Dict[str, Tuple[float, str]] = {}


def _base() -> str:
    return 'https://' + Config.BIRO26_PUBLIC_HOST


def _rows(r: Dict) -> List[Dict[str, Any]]:
    if not r.get('success'):
        return []
    cols = [c.lower() for c in (r.get('columns') or [])]
    return [dict(zip(cols, row)) for row in (r.get('data') or [])]


def _cached(key: str, build) -> str:
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    xml = build()
    _cache[key] = (time.time() + TTL, xml)
    return xml


def _urlset(locs: List[str]) -> str:
    """RO: invelisul <urlset>. Adresele se escapeaza pentru XML — numele de
    categorii contin '&', care altfel ar strica fisierul.
    EN: <urlset> wrapper; category names contain '&' which must be escaped."""
    body = '\n'.join('<url><loc>%s</loc></url>' % xml_escape(u) for u in locs)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + body + '\n</urlset>\n')


def product_count() -> int:
    """RO: cite produse intra in harta (activ + cu pret in vigoare).
    EN: how many products the sitemap covers."""
    def build() -> str:
        rows = _rows(Biro26DB().execute_query(
            # RO: feed-ul are mai multe rinduri per produs — fara DISTINCT
            #     harta numara duplicate. EN: the feed holds duplicate rows.
            "SELECT COUNT(DISTINCT g.cod_univers) CNT FROM biro26_goods g "
            "  JOIN tms_univers u ON u.cod = g.cod_univers "
            " WHERE NVL(u.isarhiv,'0') <> '2' AND g.retail1 IS NOT NULL "
            "   AND EXISTS (SELECT 1 FROM tpr1d_perprlist p "
            "                WHERE p.sc = g.cod_univers "
            "                  AND p.dataend >= TRUNC(SYSDATE))"))
        return str(int(rows[0]['cnt']) if rows else 0)
    return int(_cached('count', build))


def index_xml() -> str:
    """RO: indexul — trimite spre hartile mici. EN: the sitemap index."""
    def build() -> str:
        n = product_count()
        parts = ['/sitemap-pages.xml', '/sitemap-categories.xml']
        chunks = max(1, (n + CHUNK - 1) // CHUNK)
        parts += ['/sitemap-products-%d.xml' % i for i in range(1, chunks + 1)]
        body = '\n'.join('<sitemap><loc>%s</loc></sitemap>'
                         % xml_escape(_base() + p) for p in parts)
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + body + '\n</sitemapindex>\n')
    return _cached('index', build)


def pages_xml() -> str:
    return _cached('pages', lambda: _urlset([_base() + p for p in STATIC_PAGES]))


def categories_xml() -> str:
    """RO: fiecare grupa si fiecare categorie devine o adresa reala de catalog —
    exact formatul pe care il scrie si interfata: /catalog?grupa=..&categorie=..
    EN: every group and category becomes a real catalog URL, in the same format
    the UI itself produces."""
    def build() -> str:
        rows = _rows(Biro26DB().execute_query(
            "SELECT g.grupa GRUPA, g.categorie CATEGORIE, COUNT(*) CNT "
            "  FROM biro26_goods g "
            "  JOIN tms_univers u ON u.cod = g.cod_univers "
            " WHERE NVL(u.isarhiv,'0') <> '2' AND g.grupa IS NOT NULL "
            " GROUP BY g.grupa, g.categorie "
            " ORDER BY g.grupa, g.categorie"))
        locs, seen = [], set()
        for r in rows:
            grupa, categ = r.get('grupa'), r.get('categorie')
            if not grupa:
                continue
            # RO: intii pagina grupei (o singura data), apoi a categoriei
            for params in ([('grupa', grupa)],
                           [('grupa', grupa), ('categorie', categ)] if categ else None):
                if not params:
                    continue
                url = _base() + '/catalog?' + urllib.parse.urlencode(params)
                if url not in seen:
                    seen.add(url)
                    locs.append(url)
        return _urlset(locs)
    return _cached('categories', build)


def products_xml(part: int) -> str:
    """RO: produsele, bucata `part` (1-based), cite CHUNK.
    Paginare in stil Oracle 11g (ROWNUM) — FETCH FIRST nu exista aici.
    EN: products, chunk `part`; Oracle 11g ROWNUM paging (no FETCH FIRST)."""
    def build() -> str:
        lo = (part - 1) * CHUNK
        hi = part * CHUNK
        rows = _rows(Biro26DB().execute_query(
            "SELECT cod FROM ("
            "  SELECT cod, ROWNUM rn FROM ("
            "    SELECT DISTINCT g.cod_univers cod "
            "      FROM biro26_goods g "
            "      JOIN tms_univers u ON u.cod = g.cod_univers "
            "     WHERE NVL(u.isarhiv,'0') <> '2' AND g.retail1 IS NOT NULL "
            "       AND EXISTS (SELECT 1 FROM tpr1d_perprlist p "
            "                    WHERE p.sc = g.cod_univers "
            "                      AND p.dataend >= TRUNC(SYSDATE)) "
            "     ORDER BY g.cod_univers) "
            "  WHERE ROWNUM <= :hi) "
            "WHERE rn > :lo", {'hi': hi, 'lo': lo}))
        return _urlset([_base() + '/produs/' + str(r['cod']) for r in rows])
    return _cached('prod%d' % part, build)


def robots_txt() -> str:
    """RO: ce se indexeaza si ce nu. Paginile personale (cos, cont, favorite,
    comparare, rezultatul platii) si API-ul nu au ce cauta in cautare.
    EN: personal pages and the API stay out of the index."""
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /cos\n"
        "Disallow: /cont\n"
        "Disallow: /favorite\n"
        "Disallow: /compara\n"
        "Disallow: /payment-result\n"
        "Disallow: /cerere-credit\n"
        "Disallow: /UNA.md/\n"
        "\n"
        "Sitemap: " + _base() + "/sitemap.xml\n")
