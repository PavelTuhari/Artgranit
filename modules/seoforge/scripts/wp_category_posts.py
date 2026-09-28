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
        f"  NVL(g.photo_url, g.image_link) IMG, "
        # RO: intii cele CU fotografie - un articol fara imagini se
        #     citeste ca un tabel. EN: photo-bearing items first.
        f"  ROW_NUMBER() OVER (PARTITION BY g.grupa, g.categorie "
        f"    ORDER BY CASE WHEN NVL(g.photo_url, g.image_link) IS NULL "
        f"                  THEN 1 ELSE 0 END, u.cod) RN "
        f"FROM biro26_goods g JOIN tms_univers u ON u.cod = g.cod_univers "
        f"WHERE {SELLABLE} AND g.categorie IS NOT NULL) WHERE RN <= 6", {}))
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(f"{r['grupa']}||{r['categorie']}", []).append(r)
    return out


# RO/RU: blocul de serviciu - singurul care se repeta, si asta e normal:
# e informatie, nu continut. EN: the only repeated block, by design.
# ── тексты, которые делают статью живой ───────────────────────────────
#
# Однотипные абзацы читаются как объявления и не удерживают человека.
# Поэтому: несколько вступлений, школьный блок к 1 сентября, отдельный
# блок про север Молдовы (там основное покрытие) и упор на широту
# ассортимента в одном месте.

# RO: sectiunile care tin de 1 septembrie / EN: the back-to-school ones
SCHOOL_GROUPS = {
    "Rechizite scolare", "Carti educationale", "Ghiozdane si Penare",
    "Articole din hirtie", "Instrumente de scris", "Arta si creatie",
    "Rechizite de birou",
}

LEADS = {
    "ro": [
        "Ai nevoie de {name}? La OfficePlus găsești {n} de poziții — "
        "de la {pmin} lei, cu prețul obișnuit în jur de {pmed} lei.",
        "{name}: {n} de poziții într-un singur loc, prețuri {pmin}–{pmax} lei. "
        "Nu trebuie să cauți prin cinci magazine.",
        "Secțiunea {name} numără {n} de poziții. Cel mai ieftin — {pmin} lei, "
        "alegerea obișnuită se face în jur de {pmed} lei.",
        "{n} de poziții la {name}, de la {pmin} lei. Comanzi online, "
        "primești acasă sau la birou.",
    ],
    "ru": [
        "Нужны {name}? В OfficePlus — {n} позиций, от {pmin} лей, "
        "обычный выбор в районе {pmed} лей.",
        "{name}: {n} позиций в одном месте, цены {pmin}–{pmax} лей. "
        "Не нужно обходить пять магазинов.",
        "В разделе «{name}» — {n} позиций. Самое доступное от {pmin} лей, "
        "обычно берут около {pmed} лей.",
        "{n} позиций в разделе «{name}», от {pmin} лей. Заказ онлайн, "
        "доставка домой или в офис.",
    ],
}

SCHOOL = {
    "ro": ('<h2>1 septembrie e aproape</h2>\n'
           '<p>Ghiozdanul, caietele, penarul, acuarelele — toate se strâng '
           'într-o singură comandă, fără drumuri prin oraș. Listele de '
           'rechizite pentru clasele I–XII se acoperă dintr-un singur '
           'catalog: dacă un articol lipsește dintr-un magazin, aici se '
           'găsește alternativa pe loc.</p>\n'
           '<p><strong>Sfat practic:</strong> comandați cu câteva zile '
           'înainte — la sfârșit de august cererea crește, iar cele mai '
           'căutate modele pleacă primele.</p>\n'),
    "ru": ('<h2>1 сентября на носу</h2>\n'
           '<p>Рюкзак, тетради, пенал, краски — всё собирается одним '
           'заказом, без поездок по городу. Списки для 1–12 классов '
           'закрываются из одного каталога: если чего-то нет, замена '
           'находится тут же.</p>\n'
           '<p><strong>Совет:</strong> заказывайте за несколько дней — '
           'в конце августа спрос растёт, и самое ходовое разбирают '
           'первым.</p>\n'),
}

NORTH = {
    "ro": ('<h2>Livrăm în nordul Moldovei</h2>\n'
           '<p>Bălți, Soroca, Edineț, Fălești, Drochia, Rîșcani — nordul '
           'este zona noastră de acoperire principală. Comanda din Bălți '
           'ajunge rapid, iar la Soroca — orașul cetății de pe Nistru — '
           'livrăm regulat, nu ocazional.</p>\n'
           '<p>Pentru școli, birouri și organizații din nord: factură '
           'fiscală, livrare la adresă și o singură comandă în loc de '
           'zece drumuri la Chișinău.</p>\n'),
    "ru": ('<h2>Доставляем на север Молдовы</h2>\n'
           '<p>Бельцы, Сорока, Единец, Фалешты, Дрокия, Рышканы — север '
           'наша основная зона покрытия. Заказ из Бельц доходит быстро, '
           'а в Сороки — город с крепостью на Днестре — возим регулярно, '
           'а не от случая к случаю.</p>\n'
           '<p>Школам, офисам и организациям севера: налоговая накладная, '
           'доставка по адресу и один заказ вместо десяти поездок '
           'в Кишинёв.</p>\n'),
}


def breadth_block(lang: str, total: int, sections_n: int) -> str:
    """RO: de ce merita un singur magazin - cu cifre, nu cu laude."""
    if lang == "ro":
        return ('<h2>De ce într-un singur loc</h2>\n'
                f'<p>În catalog sunt <strong>{_money(total)}</strong> de '
                f'poziții în {sections_n} de secțiuni: de la caiete și pixuri '
                'până la tehnică de birou, articole pentru artă și mărfuri '
                'pentru casă. O comandă — o livrare — o factură, în loc să '
                'strângeți aceleași lucruri din trei-patru magazine '
                'diferite.</p>\n')
    return ('<h2>Почему в одном месте</h2>\n'
            f'<p>В каталоге <strong>{_money(total)}</strong> позиций '
            f'в {sections_n} разделах: от тетрадей и ручек до офисной '
            'техники, товаров для творчества и хозяйственных мелочей. '
            'Один заказ — одна доставка — одна накладная, вместо того '
            'чтобы собирать то же самое по трём-четырём магазинам.</p>\n')


def gallery(photos: List[Dict[str, Any]], lang: str) -> str:
    """RO: 3-4 fotografii reale de produs; fara ele articolul e un tabel."""
    if not photos:
        return ""
    cells = []
    for ph in photos[:4]:
        src = html.escape(str(ph.get("img") or ""))
        alt = html.escape(str(ph.get("name") or "")[:80])
        cells.append(
            f'<figure class="wp-block-image size-large" '
            f'style="flex:1 1 22%;margin:0">'
            f'<a href="{BASE}/produs/{int(ph["cod"])}">'
            f'<img src="{src}" alt="{alt}" loading="lazy" '
            f'style="width:100%;height:auto;border-radius:8px"></a></figure>')
    return ('<div style="display:flex;gap:10px;flex-wrap:wrap;margin:18px 0">'
            + "".join(cells) + '</div>\n')


def fetch_photos(db) -> Dict[str, List[Dict[str, Any]]]:
    """RO: cite patru fotografii pentru fiecare sectiune, luate din
    SUBGRUPE DIFERITE.

    Daca se iau primele patru la rind, ies patru tuburi de vopsea din
    aceeasi serie - arata sarac si nu spune nimic despre gama. Cite una
    din fiecare subgrupa arata exact ce vrem sa aratam: largimea.
    EN: four photos per section, each from a DIFFERENT subgroup - taking
    consecutive rows yields four near-identical items.
    """
    rows = _rows(db.execute_query(
        "SELECT GRUPA, NAME, COD, IMG FROM ("
        "  SELECT GRUPA, CATEGORIE, NAME, COD, IMG, "
        "         ROW_NUMBER() OVER (ORDER BY GRUPA, CATEGORIE) RNG "
        "  FROM ("
        "    SELECT g.grupa GRUPA, g.categorie CATEGORIE, u.denumirea NAME, "
        "           u.cod COD, NVL(g.photo_url, g.image_link) IMG, "
        "           ROW_NUMBER() OVER (PARTITION BY g.grupa, g.categorie "
        "                              ORDER BY u.cod) RNC "
        "    FROM biro26_goods g JOIN tms_univers u ON u.cod = g.cod_univers "
        # RO: pentru FOTOGRAFIE nu cerem pret in vigoare - poza ramine
        #     valabila si daca pretul se recalculeaza.
        "    WHERE NVL(u.isarhiv,'0') <> '2' AND u.tip = 'P' "
        "      AND NVL(g.photo_url, g.image_link) IS NOT NULL "
        "      AND g.grupa IS NOT NULL) "
        "  WHERE RNC = 1)"          # по одному товару на подгруппу
        " ORDER BY GRUPA, RNG", {}))
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        bucket = out.setdefault(r["grupa"], [])
        if len(bucket) < 4:
            bucket.append(r)
    return out


"""Сборка постов-разделов для WordPress по docs/SEOForge/WP_CATEGORY_POSTS.md.

RO: Scriptul NU publica nimic singur: aduna datele din ERP si scrie un
    fisier JSON cu articolele gata de creat. Publicarea se face separat,
    cu wp-cli, ca sa fie un pas constient si sa se poata verifica intii
    continutul. EN: this script only BUILDS the posts into a JSON file;
    publishing is a separate, deliberate step.

Каждый пост наполняется данными СВОЕГО раздела — количество, цены,
бренды, состав. Одинаковым остаётся только служебный блок про доставку.
"""


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


def _variant(name: str, n: int) -> int:
    """RO: acelasi articol primeste mereu aceeasi varianta de text - stabil
    intre rulari, dar diferit intre sectiuni."""
    return sum(ord(c) for c in name) % n


def build_group_post(g, brands, children, i18n, photos, totals, lang):
    ro_name = g["grupa"]
    name = ro_name if lang == "ro" else ru(i18n, "grupa", ro_name)
    url = catalog_url(ro_name)
    n = int(g["n"])
    w = T[lang]
    kids = [c for c in children.get(ro_name, []) if int(c["n"]) >= 10][:14]
    brs = brands.get(ro_name, [])[:8]
    school = ro_name in SCHOOL_GROUPS

    leads = LEADS[lang]
    lead_txt = leads[_variant(ro_name, len(leads))].format(
        name=name, n=_money(n), pmin=_money(g["pmin"]),
        pmed=_money(g["pmed"]), pmax=_money(g["pmax"]))

    if lang == "ro":
        titles = [f"{name} — cumpără online la OfficePlus",
                  f"{name}: {_money(n)} de poziții, livrare în nordul Moldovei",
                  f"{name} pentru școală, birou și acasă"]
        excerpts = [
            f"{_money(n)} de poziții, de la {_money(g['pmin'])} lei. "
            f"Livrăm în Bălți, Soroca și tot nordul.",
            f"Toată secțiunea {name} într-un singur catalog — {_money(n)} "
            f"de poziții, o comandă, o livrare.",
            f"De la {_money(g['pmin'])} lei. {_money(n)} de poziții gata "
            f"de comandă, cu livrare rapidă în nord."]
    else:
        titles = [f"{name} — купить онлайн в OfficePlus",
                  f"{name}: {_money(n)} позиций, доставка на север Молдовы",
                  f"{name} для школы, офиса и дома"]
        excerpts = [
            f"{_money(n)} позиций, от {_money(g['pmin'])} лей. "
            f"Возим в Бельцы, Сороки и по всему северу.",
            f"Весь раздел «{name}» в одном каталоге — {_money(n)} позиций, "
            f"один заказ, одна доставка.",
            f"От {_money(g['pmin'])} лей. {_money(n)} позиций готовы "
            f"к заказу, быстрая доставка на север."]

    v = _variant(ro_name, 3)
    body = [f'<p>{lead_txt} <a href="{url}">'
            + ("Vezi secțiunea în catalog" if lang == "ro"
               else "Открыть раздел в каталоге") + '</a>.</p>\n']
    body.append(gallery(photos.get(ro_name, []), lang))
    if school:
        body.append(SCHOOL[lang])
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
    body.append(breadth_block(lang, totals["items"], totals["sections"]))
    body.append(NORTH[lang])
    body.append(HOW_TO_BUY[lang])
    body.append(f'<p><a href="{url}"><strong>{w["open"]} '
                f'{html.escape(name)} {w["in_catalog"]} →</strong></a></p>\n')

    slug = slugify(ro_name) + ("" if lang == "ro" else "-ru")
    return {"kind": "group", "lang": lang, "slug": slug,
            "title": titles[v], "excerpt": excerpts[v],
            "content": "".join(body), "catalog_url": url, "items": n,
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
    # RO: fotografii din chiar aceasta subgrupa - nu poze generice
    body.append(gallery([e for e in ex if e.get("img")], lang))
    if ro_g in SCHOOL_GROUPS:
        body.append(SCHOOL[lang])
    if ex:
        body.append(f'<h2>{w["examples_h"]}</h2>\n<ul>\n')
        for e in ex:
            body.append(f'<li><a href="{BASE}/produs/{int(e["cod"])}">'
                        f'{html.escape(str(e["name"])[:90])}</a></li>\n')
        body.append('</ul>\n')
    body.append(price_bands(url, s["pmin"], s["pmed"], s["pmax"], lang))
    body.append(NORTH[lang])
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
    photos = fetch_photos(db)
    totals = {"items": sum(int(g["n"]) for g in groups),
              "sections": len(groups)}

    posts = []
    for lang in ("ro", "ru"):
        posts += [build_group_post(g, brands, children, i18n, photos,
                                   totals, lang) for g in groups]
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
