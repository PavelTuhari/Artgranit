"""Сборка постов-разделов для WordPress по docs/SEOForge/WP_CATEGORY_POSTS.md.

RO: Scriptul NU publica nimic singur: aduna datele din ERP si scrie un
    fisier JSON cu articolele gata de creat. Publicarea se face separat,
    cu wp-cli, ca sa fie un pas constient si sa se poata verifica intii
    continutul. EN: this script only BUILDS the posts into a JSON file;
    publishing is a separate, deliberate step.

Каждый пост наполняется данными СВОЕГО раздела — количество, цены,
бренды, состав. Одинаковым остаётся только служебный блок про доставку.
"""

from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
from typing import Any, Dict, List

sys.path.insert(0, "/Users/pt/Projects.AI/Artgranit-core")

from models.biro26_db import Biro26DB  # noqa: E402

BASE = "https://officeplus.md"

# RO: aceeasi regula ca harta site-ului: fisa activa + pret in vigoare.
SELLABLE = ("NVL(u.isarhiv,'0') <> '2' AND g.retail1 IS NOT NULL "
            # RO: pretul zero nu e pret - articolul ar promite «de la 0 lei».
            # EN: a zero price is not a price.
            "AND REGEXP_LIKE(TRIM(g.retail1), '^[0-9]+([.,][0-9]+)?$') "
            "AND TO_NUMBER(REPLACE(TRIM(g.retail1),',','.')) > 0 "
            "AND EXISTS (SELECT 1 FROM tpr1d_perprlist p "
            "WHERE p.sc = g.cod_univers AND p.dataend >= TRUNC(SYSDATE))")

# RO: grupele tehnice nu se descriu - nu sint sectiuni pentru client.
SKIP_GROUPS = {"IMPORT PT"}

MIN_SUBGROUP = 100          # порог из инструкции, §2


def _rows(r: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not r.get("success"):
        raise RuntimeError(r.get("message") or "query failed")
    cols = [c.lower() for c in (r.get("columns") or [])]
    return [dict(zip(cols, row)) for row in (r.get("data") or [])]


def slugify(*parts: str) -> str:
    """RO: adresa postului. Diacriticele se transliterează, ca adresa sa
    ramina lizibila si stabila. EN: a stable, readable slug."""
    text = " ".join(p for p in parts if p)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return re.sub(r"-{2,}", "-", text)[:90]


def catalog_url(grupa: str, categorie: str = "") -> str:
    """RO: adresa de catalog, cu & scris ca &amp; - altfel HTML-ul e invalid."""
    from urllib.parse import urlencode
    q = [("grupa", grupa)] + ([("categorie", categorie)] if categorie else [])
    return f"{BASE}/catalog?" + urlencode(q).replace("&", "&amp;")


def _money(v) -> str:
    try:
        return f"{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def fetch_groups(db) -> List[Dict[str, Any]]:
    return _rows(db.execute_query(
        f"SELECT g.grupa GRUPA, COUNT(DISTINCT g.cod_univers) N, "
        f"  CEIL(MIN(TO_NUMBER(REPLACE(g.retail1,',','.')))) PMIN, "
        f"  ROUND(MEDIAN(TO_NUMBER(REPLACE(g.retail1,',','.'))),0) PMED, "
        f"  ROUND(MAX(TO_NUMBER(REPLACE(g.retail1,',','.'))),0) PMAX "
        f"FROM biro26_goods g JOIN tms_univers u ON u.cod = g.cod_univers "
        f"WHERE {SELLABLE} AND g.grupa IS NOT NULL "
        f"GROUP BY g.grupa ORDER BY COUNT(DISTINCT g.cod_univers) DESC", {}))


def fetch_subgroups(db) -> List[Dict[str, Any]]:
    return _rows(db.execute_query(
        f"SELECT g.grupa GRUPA, g.categorie CATEGORIE, "
        f"  COUNT(DISTINCT g.cod_univers) N, "
        f"  CEIL(MIN(TO_NUMBER(REPLACE(g.retail1,',','.')))) PMIN, "
        f"  ROUND(MEDIAN(TO_NUMBER(REPLACE(g.retail1,',','.'))),0) PMED, "
        f"  ROUND(MAX(TO_NUMBER(REPLACE(g.retail1,',','.'))),0) PMAX "
        f"FROM biro26_goods g JOIN tms_univers u ON u.cod = g.cod_univers "
        f"WHERE {SELLABLE} AND g.grupa IS NOT NULL AND g.categorie IS NOT NULL "
        f"GROUP BY g.grupa, g.categorie "
        f"HAVING COUNT(DISTINCT g.cod_univers) >= :m "
        f"ORDER BY COUNT(DISTINCT g.cod_univers) DESC", {"m": MIN_SUBGROUP}))


def fetch_brands(db) -> Dict[str, List[Dict[str, Any]]]:
    rows = _rows(db.execute_query(
        f"SELECT g.grupa GRUPA, g.brand BRAND, COUNT(DISTINCT g.cod_univers) N "
        f"FROM biro26_goods g JOIN tms_univers u ON u.cod = g.cod_univers "
        f"WHERE {SELLABLE} AND g.grupa IS NOT NULL AND g.brand IS NOT NULL "
        # RO: in feed exista marca scrisa literal «NULL» - nu e marca.
        # EN: the feed holds a literal 'NULL' brand; it is not a brand.
        f"  AND UPPER(TRIM(g.brand)) NOT IN ('NULL', 'N/A', '-') "
        f"GROUP BY g.grupa, g.brand ORDER BY g.grupa, COUNT(*) DESC", {}))
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["grupa"], []).append(r)
    return out


def fetch_children(db) -> Dict[str, List[Dict[str, Any]]]:
    rows = _rows(db.execute_query(
        f"SELECT g.grupa GRUPA, g.categorie CATEGORIE, "
        f"  COUNT(DISTINCT g.cod_univers) N "
        f"FROM biro26_goods g JOIN tms_univers u ON u.cod = g.cod_univers "
        f"WHERE {SELLABLE} AND g.grupa IS NOT NULL AND g.categorie IS NOT NULL "
        f"GROUP BY g.grupa, g.categorie ORDER BY g.grupa, COUNT(*) DESC", {}))
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["grupa"], []).append(r)
    return out


def fetch_samples(db) -> Dict[str, List[Dict[str, Any]]]:
    """RO: cite un exemplu de marfa pentru fiecare subgrupa."""
    rows = _rows(db.execute_query(
        f"SELECT * FROM (SELECT g.grupa GRUPA, g.categorie CATEGORIE, "
        f"  u.cod COD, u.denumirea NAME, "
        f"  ROW_NUMBER() OVER (PARTITION BY g.grupa, g.categorie "
        f"                     ORDER BY u.cod) RN "
        f"FROM biro26_goods g JOIN tms_univers u ON u.cod = g.cod_univers "
        f"WHERE {SELLABLE} AND g.categorie IS NOT NULL) WHERE RN <= 6", {}))
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(f"{r['grupa']}||{r['categorie']}", []).append(r)
    return out


HOW_TO_BUY = (
    '<h2>Cum cumperi</h2>\n'
    '<ul>\n'
    f'<li><strong>Livrare</strong> în toată Moldova — '
    f'<a href="{BASE}/livrare">condiții și termene</a>.</li>\n'
    f'<li><strong>Rate fără dobândă</strong> — Liber Card MAIB și alte '
    f'programe: <a href="{BASE}/credite">vezi variantele</a>.</li>\n'
    '<li><strong>Pentru organizații</strong> — factură fiscală și livrare '
    'la birou, comandă direct din catalog.</li>\n'
    '</ul>\n')


def price_bands(url: str, pmin, pmed, pmax) -> str:
    """RO: trei benzi de pret, calculate din preturile REALE ale sectiunii."""
    try:
        lo, mid, hi = float(pmin), float(pmed), float(pmax)
    except (TypeError, ValueError):
        return ""
    b1 = int(max(1, round(mid / 2)))
    b2 = int(max(b1 + 1, round(mid * 2)))
    return (
        '<h2>După preț</h2>\n<ul>\n'
        f'<li><a href="{url}&amp;price_max={b1}">Până la {_money(b1)} lei</a> — '
        'variantele accesibile din secțiune.</li>\n'
        f'<li><a href="{url}&amp;price_min={b1}&amp;price_max={b2}">'
        f'{_money(b1)}–{_money(b2)} lei</a> — alegerea obișnuită.</li>\n'
        f'<li><a href="{url}&amp;price_min={b2}">Peste {_money(b2)} lei</a> — '
        f'până la {_money(hi)} lei.</li>\n</ul>\n')


def build_group_post(g, brands, children) -> Dict[str, Any]:
    name = g["grupa"]
    url = catalog_url(name)
    n = int(g["n"])
    kids = [c for c in children.get(name, []) if int(c["n"]) >= 10][:14]
    brs = [b for b in brands.get(name, [])][:8]

    body = [
        f'<p><strong>{html.escape(name)}</strong> la OfficePlus — '
        f'<strong>{_money(n)}</strong> de poziții disponibile pentru comandă, '
        f'cu prețuri de la {_money(g["pmin"])} până la {_money(g["pmax"])} lei '
        f'(preț tipic — {_money(g["pmed"])} lei). '
        f'<a href="{url}">Vezi toată secțiunea în catalog</a>.</p>\n']

    if brs:
        body.append('<h2>Mărci din secțiune</h2>\n<p>' + ", ".join(
            f'{html.escape(str(b["brand"]))} ({_money(b["n"])})' for b in brs)
            + '.</p>\n')

    if kids:
        body.append('<h2>Ce găsești aici</h2>\n<ul>\n')
        for c in kids:
            cu = catalog_url(name, c["categorie"])
            body.append(f'<li><a href="{cu}">{html.escape(str(c["categorie"]))}</a>'
                        f' — {_money(c["n"])} poziții</li>\n')
        body.append('</ul>\n')

    body.append(price_bands(url, g["pmin"], g["pmed"], g["pmax"]))
    body.append(HOW_TO_BUY)
    body.append(f'<p><a href="{url}"><strong>Deschide '
                f'{html.escape(name)} în catalog →</strong></a></p>\n')

    return {
        "kind": "group",
        "slug": slugify(name),
        "title": f"{name} — cumpără online la OfficePlus",
        "excerpt": (f"{_money(n)} de poziții în secțiunea {name}, "
                    f"prețuri de la {_money(g['pmin'])} lei. "
                    f"Livrare în toată Moldova, rate fără dobândă."),
        "content": "".join(body),
        "catalog_url": url,
        "items": n,
    }


def build_subgroup_post(s, samples) -> Dict[str, Any]:
    grupa, categ = s["grupa"], s["categorie"]
    url = catalog_url(grupa, categ)
    n = int(s["n"])
    ex = samples.get(f"{grupa}||{categ}", [])[:6]

    body = [
        f'<p><strong>{html.escape(categ)}</strong> — '
        f'<strong>{_money(n)}</strong> de poziții în secțiunea '
        f'<a href="{catalog_url(grupa)}">{html.escape(grupa)}</a>, '
        f'prețuri {_money(s["pmin"])}–{_money(s["pmax"])} lei '
        f'(tipic {_money(s["pmed"])} lei). '
        f'<a href="{url}">Vezi în catalog</a>.</p>\n']

    if ex:
        body.append('<h2>Exemple din secțiune</h2>\n<ul>\n')
        for e in ex:
            body.append(f'<li><a href="{BASE}/produs/{int(e["cod"])}">'
                        f'{html.escape(str(e["name"])[:90])}</a></li>\n')
        body.append('</ul>\n')

    body.append(price_bands(url, s["pmin"], s["pmed"], s["pmax"]))
    body.append(HOW_TO_BUY)
    body.append(f'<p><a href="{url}"><strong>Toate pozițiile: '
                f'{html.escape(categ)} →</strong></a></p>\n')

    return {
        "kind": "subgroup",
        "slug": slugify(grupa, categ),
        "title": f"{categ} — {grupa} online la OfficePlus",
        "excerpt": (f"{_money(n)} de poziții: {categ} din secțiunea {grupa}. "
                    f"Prețuri de la {_money(s['pmin'])} lei, livrare rapidă."),
        "content": "".join(body),
        "catalog_url": url,
        "items": n,
    }


def main() -> int:
    db = Biro26DB()
    print("читаю ERP…")
    groups = [g for g in fetch_groups(db) if g["grupa"] not in SKIP_GROUPS]
    subs = [s for s in fetch_subgroups(db)
            if s["grupa"] not in SKIP_GROUPS
            # RO: subgrupa cu acelasi nume ca grupa nu adauga nimic
            and str(s["categorie"]).strip().lower() != str(s["grupa"]).strip().lower()]
    brands = fetch_brands(db)
    children = fetch_children(db)
    samples = fetch_samples(db)

    posts = [build_group_post(g, brands, children) for g in groups]
    posts += [build_subgroup_post(s, samples) for s in subs]

    # RO: adresele trebuie sa fie unice - altfel al doilea articol l-ar
    #     suprascrie pe primul. EN: slugs must be unique.
    seen, unique = set(), []
    for p in posts:
        if p["slug"] in seen:
            p["slug"] = f"{p['slug']}-{p['items']}"
        seen.add(p["slug"])
        unique.append(p)

    out = "/tmp/officeplus_wp_posts.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=1)
    print(f"готово: {len(groups)} групп + {len(subs)} подгрупп = "
          f"{len(unique)} постов -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
