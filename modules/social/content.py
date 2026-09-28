"""Что публиковать. Только реальные данные магазина, без выдумок.

RO: Continutul se ia din ERP: sectiuni cu numarul de pozitii si pretul
    tipic, bestselleruri din COMENZILE reale. Textele inventate ("cea mai
    buna oferta a anului") nu se scriu: le vede si clientul, si reteaua.
EN: Content comes from the ERP; nothing is invented.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

BASE = "https://officeplus.md"

# RO: rotatia zilnica trece prin sectiuni, ca sa nu se repete acelasi text.
# EN: a daily rotation through sections so the same text never repeats.
KEY_LAST_INDEX = "SOCIAL_LAST_INDEX"


def _money(v) -> str:
    try:
        return f"{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def _setting(key: str, default: str = "") -> str:
    try:
        from models.biro26_oracle_store import Biro26Store
        return Biro26Store.get_setting(key, default)
    except Exception:                                        # noqa: BLE001
        return default


def _set_setting(key: str, value: str) -> None:
    try:
        from models.biro26_oracle_store import Biro26Store
        Biro26Store.set_setting(key, value)
    except Exception:                                        # noqa: BLE001
        pass


def sections(limit: int = 40) -> List[Dict[str, Any]]:
    """RO: sectiunile cu marfa de vinzare, cele mai mari intii."""
    from models.biro26_db import Biro26DB
    sellable = ("NVL(u.isarhiv,'0') <> '2' AND g.retail1 IS NOT NULL "
                "AND REGEXP_LIKE(TRIM(g.retail1), '^[0-9]+([.,][0-9]+)?$') "
                "AND TO_NUMBER(REPLACE(TRIM(g.retail1),',','.')) > 0")
    r = Biro26DB().execute_query(
        f"SELECT * FROM (SELECT g.grupa GRUPA, "
        f"  COUNT(DISTINCT g.cod_univers) N, "
        f"  CEIL(MIN(TO_NUMBER(REPLACE(g.retail1,',','.')))) PMIN, "
        f"  ROUND(MEDIAN(TO_NUMBER(REPLACE(g.retail1,',','.')))) PMED "
        f"FROM biro26_goods g JOIN tms_univers u ON u.cod = g.cod_univers "
        f"WHERE {sellable} AND g.grupa IS NOT NULL AND g.grupa <> 'IMPORT PT' "
        f"GROUP BY g.grupa HAVING COUNT(DISTINCT g.cod_univers) >= 50 "
        f"ORDER BY COUNT(DISTINCT g.cod_univers) DESC) WHERE ROWNUM <= :n",
        {"n": limit})
    if not r.get("success"):
        return []
    cols = [c.lower() for c in (r.get("columns") or [])]
    return [dict(zip(cols, row)) for row in (r.get("data") or [])]


def section_post(lang: str = "ro") -> Optional[Dict[str, str]]:
    """RO: postarea de azi despre o sectiune, prin rotatie."""
    rows = sections()
    if not rows:
        return None
    try:
        idx = int(_setting(KEY_LAST_INDEX, "-1")) + 1
    except ValueError:
        idx = 0
    row = rows[idx % len(rows)]
    _set_setting(KEY_LAST_INDEX, str(idx % len(rows)))

    from urllib.parse import urlencode
    url = f"{BASE}/catalog?" + urlencode([("grupa", row["grupa"])])
    name = row["grupa"]
    if lang == "ru":
        text = (f"📦 {name} — {_money(row['n'])} позиций в наличии и под заказ.\n"
                f"Цены от {_money(row['pmin'])} лей, обычная — "
                f"{_money(row['pmed'])} лей.\n"
                f"Доставка по всей Молдове, рассрочка без процентов.\n{url}")
    else:
        text = (f"📦 {name} — {_money(row['n'])} de poziții în catalog.\n"
                f"Prețuri de la {_money(row['pmin'])} lei, tipic "
                f"{_money(row['pmed'])} lei.\n"
                f"Livrare în toată Moldova, rate fără dobândă.\n{url}")
    return {"text": text, "url": url, "kind": "section", "title": name}


def bestsellers_post(lang: str = "ro") -> Optional[Dict[str, str]]:
    """RO: ce se cumpara chiar acum - din comenzile reale."""
    try:
        from models.biro26_oracle_store import Biro26Store
        rows = (Biro26Store.get_shop_bestsellers(30, 5) or {}).get("data") or []
    except Exception:                                        # noqa: BLE001
        return None
    if not rows:
        return None
    head = ("🔥 Se cumpără acum la OfficePlus:" if lang == "ro"
            else "🔥 Сейчас покупают в OfficePlus:")
    lines = [f"• {str(r.get('denumirea'))[:64]}" for r in rows[:5]]
    tail = (f"\n{BASE}/catalog")
    return {"text": head + "\n" + "\n".join(lines) + tail,
            "url": f"{BASE}/catalog", "kind": "bestsellers",
            "title": "bestsellers"}


def today_post(lang: str = "ro") -> Optional[Dict[str, str]]:
    """RO: luni - bestselleruri, restul zilelor - o sectiune."""
    if datetime.date.today().weekday() == 0:
        return bestsellers_post(lang) or section_post(lang)
    return section_post(lang)
