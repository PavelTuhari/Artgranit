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


# RO: numele rusesti ale sectiunilor din dictionarul editabil
#     YBIRO_GRP_I18N (principiul una-shops: traducerile sint DATE).
#     Unde traducerea lipseste, ramine numele romanesc - mai bine numele
#     original decit masina de tradus.
# EN: Russian section names from the editable dictionary; where a
#     translation is missing the Romanian name stays.
def fetch_i18n(db) -> Dict[str, str]:
    rows = _rows(db.execute_query(
        "SELECT KIND, NAME_RO, NAME_RU FROM YBIRO_GRP_I18N "
        "WHERE NAME_RU IS NOT NULL", {}))
    return {f"{r['kind']}||{r['name_ro']}": r["name_ru"] for r in rows}


def ru(i18n: Dict[str, str], kind: str, name: str) -> str:
    return i18n.get(f"{kind}||{name}") or name


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


# RO/RU: blocul de serviciu - singurul care se repeta, si asta e normal:
# e informatie, nu continut. EN: the only repeated block, by design.
HOW_TO_BUY = {
    "ro": ('<h2>Cum cumperi</h2>\n<ul>\n'
           f'<li><strong>Livrare</strong> în toată Moldova — '
           f'<a href="{BASE}/livrare">condiții și termene</a>.</li>\n'
           f'<li><strong>Rate fără dobândă</strong> — Liber Card MAIB și alte '
           f'programe: <a href="{BASE}/credite">vezi variantele</a>.</li>\n'
           '<li><strong>Pentru organizații</strong> — factură fiscală și '
           'livrare la birou, comandă direct din catalog.</li>\n</ul>\n'),
    "ru": ('<h2>Как купить</h2>\n<ul>\n'
           f'<li><strong>Доставка</strong> по всей Молдове — '
           f'<a href="{BASE}/livrare">условия и сроки</a>.</li>\n'
           f'<li><strong>Рассрочка без процентов</strong> — Liber Card MAIB '
           f'и другие программы: <a href="{BASE}/credite">посмотреть</a>.</li>\n'
           '<li><strong>Для организаций</strong> — налоговая накладная и '
           'доставка в офис, заказ прямо из каталога.</li>\n</ul>\n'),
}

# RO: fraze scurte, pe limbi - ca sa nu se amestece in cod.
T = {
    "ro": {
        "band_h": "După preț", "upto": "Până la", "over": "Peste",
        "usual": "alegerea obișnuită", "cheap": "variantele accesibile din secțiune",
        "till": "până la", "lei": "lei",
        "brands_h": "Mărci din secțiune", "inside_h": "Ce găsești aici",
        "examples_h": "Exemple din secțiune", "pos": "poziții",
        "open": "Deschide", "in_catalog": "în catalog",
        "all_of": "Toate pozițiile", "other_lang": "Русская версия",
    },
    "ru": {
        "band_h": "По цене", "upto": "До", "over": "Свыше",
        "usual": "обычный выбор", "cheap": "доступные позиции раздела",
        "till": "до", "lei": "лей",
        "brands_h": "Марки в разделе", "inside_h": "Что внутри",
        "examples_h": "Примеры из раздела", "pos": "позиций",
        "open": "Открыть", "in_catalog": "в каталоге",
        "all_of": "Все позиции", "other_lang": "Versiunea în română",
    },
}


def price_bands(url: str, pmin, pmed, pmax, lang: str) -> str:
    """RO: trei benzi de pret, calculate din preturile REALE ale sectiunii."""
    try:
        mid, hi = float(pmed), float(pmax)
    except (TypeError, ValueError):
        return ""
    w = T[lang]
    b1 = int(max(1, round(mid / 2)))
    b2 = int(max(b1 + 1, round(mid * 2)))
    return (
        f'<h2>{w["band_h"]}</h2>\n<ul>\n'
        f'<li><a href="{url}&amp;price_max={b1}">{w["upto"]} {_money(b1)} '
        f'{w["lei"]}</a> — {w["cheap"]}.</li>\n'
        f'<li><a href="{url}&amp;price_min={b1}&amp;price_max={b2}">'
        f'{_money(b1)}–{_money(b2)} {w["lei"]}</a> — {w["usual"]}.</li>\n'
        f'<li><a href="{url}&amp;price_min={b2}">{w["over"]} {_money(b2)} '
        f'{w["lei"]}</a> — {w["till"]} {_money(hi)} {w["lei"]}.</li>\n</ul>\n')


def build_group_post(g, brands, children, i18n, lang: str) -> Dict[str, Any]:
    ro_name = g["grupa"]
    name = ro_name if lang == "ro" else ru(i18n, "grupa", ro_name)
    url = catalog_url(ro_name)
    n = int(g["n"])
    w = T[lang]
    kids = [c for c in children.get(ro_name, []) if int(c["n"]) >= 10][:14]
    brs = brands.get(ro_name, [])[:8]

    if lang == "ro":
        lead = (f'<p><strong>{html.escape(name)}</strong> la OfficePlus — '
                f'<strong>{_money(n)}</strong> de poziții disponibile pentru '
                f'comandă, cu prețuri de la {_money(g["pmin"])} până la '
                f'{_money(g["pmax"])} lei (preț tipic — {_money(g["pmed"])} lei). '
                f'<a href="{url}">Vezi toată secțiunea în catalog</a>.</p>\n')
        title = f"{name} — cumpără online la OfficePlus"
        excerpt = (f"{_money(n)} de poziții în secțiunea {name}, prețuri de la "
                   f"{_money(g['pmin'])} lei. Livrare în toată Moldova, "
                   f"rate fără dobândă.")
    else:
        lead = (f'<p><strong>{html.escape(name)}</strong> в OfficePlus — '
                f'<strong>{_money(n)}</strong> позиций, доступных к заказу, '
                f'по ценам от {_money(g["pmin"])} до {_money(g["pmax"])} лей '
                f'(обычная цена — {_money(g["pmed"])} лей). '
                f'<a href="{url}">Открыть раздел в каталоге</a>.</p>\n')
        title = f"{name} — купить онлайн в OfficePlus"
        excerpt = (f"{_money(n)} позиций в разделе «{name}», цены от "
                   f"{_money(g['pmin'])} лей. Доставка по всей Молдове, "
                   f"рассрочка без процентов.")

    body = [lead]
    if brs:
        body.append(f'<h2>{w["brands_h"]}</h2>\n<p>' + ", ".join(
            f'{html.escape(str(b["brand"]))} ({_money(b["n"])})' for b in brs)
            + '.</p>\n')
    if kids:
        body.append(f'<h2>{w["inside_h"]}</h2>\n<ul>\n')
        for c in kids:
            label = (c["categorie"] if lang == "ro"
                     else ru(i18n, "categorie", c["categorie"]))
            body.append(f'<li><a href="{catalog_url(ro_name, c["categorie"])}">'
                        f'{html.escape(str(label))}</a> — {_money(c["n"])} '
                        f'{w["pos"]}</li>\n')
        body.append('</ul>\n')
    body.append(price_bands(url, g["pmin"], g["pmed"], g["pmax"], lang))
    body.append(HOW_TO_BUY[lang])
    body.append(f'<p><a href="{url}"><strong>{w["open"]} '
                f'{html.escape(name)} {w["in_catalog"]} →</strong></a></p>\n')

    slug = slugify(ro_name) + ("" if lang == "ro" else "-ru")
    return {"kind": "group", "lang": lang, "slug": slug, "title": title,
            "excerpt": excerpt, "content": "".join(body),
            "catalog_url": url, "items": n,
            "pair_slug": slugify(ro_name) + ("-ru" if lang == "ro" else "")}


def build_subgroup_post(s, samples, i18n, lang: str) -> Dict[str, Any]:
    ro_g, ro_c = s["grupa"], s["categorie"]
    gname = ro_g if lang == "ro" else ru(i18n, "grupa", ro_g)
    cname = ro_c if lang == "ro" else ru(i18n, "categorie", ro_c)
    url = catalog_url(ro_g, ro_c)
    n = int(s["n"])
    w = T[lang]
    ex = samples.get(f"{ro_g}||{ro_c}", [])[:6]

    if lang == "ro":
        lead = (f'<p><strong>{html.escape(cname)}</strong> — '
                f'<strong>{_money(n)}</strong> de poziții în secțiunea '
                f'<a href="{catalog_url(ro_g)}">{html.escape(gname)}</a>, '
                f'prețuri {_money(s["pmin"])}–{_money(s["pmax"])} lei '
                f'(tipic {_money(s["pmed"])} lei). '
                f'<a href="{url}">Vezi în catalog</a>.</p>\n')
        title = f"{cname} — {gname} online la OfficePlus"
        excerpt = (f"{_money(n)} de poziții: {cname} din secțiunea {gname}. "
                   f"Prețuri de la {_money(s['pmin'])} lei, livrare rapidă.")
    else:
        lead = (f'<p><strong>{html.escape(cname)}</strong> — '
                f'<strong>{_money(n)}</strong> позиций в разделе '
                f'<a href="{catalog_url(ro_g)}">{html.escape(gname)}</a>, '
                f'цены {_money(s["pmin"])}–{_money(s["pmax"])} лей '
                f'(обычно {_money(s["pmed"])} лей). '
                f'<a href="{url}">Смотреть в каталоге</a>.</p>\n')
        title = f"{cname} — {gname} онлайн в OfficePlus"
        excerpt = (f"{_money(n)} позиций: {cname} из раздела «{gname}». "
                   f"Цены от {_money(s['pmin'])} лей, быстрая доставка.")

    body = [lead]
    if ex:
        body.append(f'<h2>{w["examples_h"]}</h2>\n<ul>\n')
        for e in ex:
            body.append(f'<li><a href="{BASE}/produs/{int(e["cod"])}">'
                        f'{html.escape(str(e["name"])[:90])}</a></li>\n')
        body.append('</ul>\n')
    body.append(price_bands(url, s["pmin"], s["pmed"], s["pmax"], lang))
    body.append(HOW_TO_BUY[lang])
    body.append(f'<p><a href="{url}"><strong>{w["all_of"]}: '
                f'{html.escape(cname)} →</strong></a></p>\n')

    base_slug = slugify(ro_g, ro_c)
    return {"kind": "subgroup", "lang": lang,
            "slug": base_slug + ("" if lang == "ro" else "-ru"),
            "title": title, "excerpt": excerpt, "content": "".join(body),
            "catalog_url": url, "items": n,
            "pair_slug": base_slug + ("-ru" if lang == "ro" else "")}


def main() -> int:
    db = Biro26DB()
    print("читаю ERP…")
    groups = [g for g in fetch_groups(db) if g["grupa"] not in SKIP_GROUPS]
    subs = [s for s in fetch_subgroups(db)
            if s["grupa"] not in SKIP_GROUPS
            and str(s["categorie"]).strip().lower() != str(s["grupa"]).strip().lower()]
    brands, children = fetch_brands(db), fetch_children(db)
    samples, i18n = fetch_samples(db), fetch_i18n(db)

    posts = []
    for lang in ("ro", "ru"):
        posts += [build_group_post(g, brands, children, i18n, lang) for g in groups]
        posts += [build_subgroup_post(s, samples, i18n, lang) for s in subs]

    seen, unique = set(), []
    for p in posts:
        if p["slug"] in seen:
            p["slug"] = f"{p['slug']}-{p['items']}"
        seen.add(p["slug"])
        unique.append(p)

    out = "/tmp/officeplus_wp_posts.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=1)
    per = len(groups) + len(subs)
    print(f"готово: {len(groups)} групп + {len(subs)} подгрупп x 2 языка = "
          f"{len(unique)} постов ({per} на язык) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
