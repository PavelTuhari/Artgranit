"""Цифры воронки — из живых таблиц ERP, без своих копий данных.

RO: Etapele pe care le putem masura CINSTIT din contabilitate:
      comanda creata (SYSFID 12280, contul de plata web)
        -> comanda livrata (CTNRDOC din VMDB_ST201M completat)
    Vizitele si cosurile traiesc in browser si in Google Analytics - cind
    apare accesul, se adauga deasupra; cifre inventate nu punem.
EN: The stages we can HONESTLY measure from the books: order created
    (SYSFID 12280) -> order delivered (CTNRDOC filled). Visits and carts
    live in the browser and in Analytics - added on top once access
    exists; we do not invent numbers.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB

# RO: tipurile de documente ale magazinului / EN: the shop's document types
SYSFID_ORDER = 12280       # cont de plata web — заказ покупателя
SYSFID_INVOICE = 1228      # factura fiscala — продажа/отгрузка

_cache: Dict[str, Any] = {}
_TTL = 600


def _rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not result.get("success"):
        return []
    cols = [c.lower() for c in (result.get("columns") or [])]
    return [dict(zip(cols, row)) for row in (result.get("data") or [])]


def _cached(key: str, build):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    value = build()
    _cache[key] = (time.time(), value)
    return value


def clear_cache() -> None:
    _cache.clear()


def orders_by_day(days: int = 14) -> List[Dict[str, Any]]:
    """RO: pe fiecare zi - comenzi create, suma lor, cite s-au livrat.
    EN: per day - orders created, their sum, how many got delivered."""
    days = max(1, min(int(days), 92))

    def build():
        return _rows(Biro26DB().execute_query(
            "SELECT TO_CHAR(d.DATAMANUAL,'YYYY-MM-DD') DAY, "
            "       COUNT(*) ORDERS, "
            "       ROUND(SUM(NVL(t.TOTAL,0)),2) TOTAL, "
            "       SUM(CASE WHEN m.CTNRDOC IS NOT NULL THEN 1 ELSE 0 END) DELIVERED, "
            "       ROUND(SUM(CASE WHEN m.CTNRDOC IS NOT NULL "
            "                      THEN NVL(t.TOTAL,0) ELSE 0 END),2) DELIVERED_SUM "
            "FROM TMDB_DOCS d "
            "JOIN VMDB_ST201M m ON m.NRDOC = d.COD "
            "LEFT JOIN (SELECT l.NRDOC, SUM(l.SUMA) TOTAL "
            "           FROM VMDB_ST201D l GROUP BY l.NRDOC) t ON t.NRDOC = d.COD "
            "WHERE d.SYSFID = :sf AND d.DATAMANUAL >= TRUNC(SYSDATE) - :days "
            "GROUP BY TO_CHAR(d.DATAMANUAL,'YYYY-MM-DD') "
            "ORDER BY 1", {"sf": SYSFID_ORDER, "days": days}))
    return _cached(f"days:{days}", build)


def summary(days: int = 7) -> Dict[str, Any]:
    """RO: palnia pe perioada: comenzi -> livrari, conversie, cec mediu.
    EN: the funnel over the period: orders -> deliveries, conversion,
    average check."""
    rows = orders_by_day(days)
    orders = sum(int(r.get("orders") or 0) for r in rows)
    total = round(sum(float(r.get("total") or 0) for r in rows), 2)
    delivered = sum(int(r.get("delivered") or 0) for r in rows)
    delivered_sum = round(sum(float(r.get("delivered_sum") or 0) for r in rows), 2)
    return {
        "days": days,
        "orders": orders,
        "orders_sum": total,
        "delivered": delivered,
        "delivered_sum": delivered_sum,
        "conversion_pct": round(delivered * 100.0 / orders, 1) if orders else None,
        "avg_check": round(total / orders, 2) if orders else None,
        "by_day": rows,
    }


def top_groups(days: int = 30, limit: int = 10) -> List[Dict[str, Any]]:
    """RO: ce grupe de marfa aduc banii - din liniile comenzilor.
    EN: which goods groups bring the money - from the order lines."""
    days = max(1, min(int(days), 92))
    limit = max(1, min(int(limit), 30))

    def build():
        return _rows(Biro26DB().execute_query(
            "SELECT * FROM ("
            "  SELECT NVL(g.GRUPA, '(fara grupa)') GRUPA, "
            "         COUNT(DISTINCT l.NRDOC) ORDERS, "
            "         ROUND(SUM(l.SUMA),2) TOTAL "
            "  FROM VMDB_ST201D l "
            "  JOIN TMDB_DOCS d ON d.COD = l.NRDOC AND d.SYSFID = :sf "
            "       AND d.DATAMANUAL >= TRUNC(SYSDATE) - :days "
            "  LEFT JOIN (SELECT gg.COD_UNIVERS, MAX(gg.GRUPA) GRUPA "
            "             FROM BIRO26_GOODS gg GROUP BY gg.COD_UNIVERS) g "
            "         ON g.COD_UNIVERS = l.CTSC "
            "  GROUP BY NVL(g.GRUPA, '(fara grupa)') "
            "  ORDER BY SUM(l.SUMA) DESC NULLS LAST"
            ") WHERE ROWNUM <= :lim",
            {"sf": SYSFID_ORDER, "days": days, "lim": limit}))
    return _cached(f"groups:{days}:{limit}", build)


def top_products(days: int = 30, limit: int = 10) -> List[Dict[str, Any]]:
    days = max(1, min(int(days), 92))
    limit = max(1, min(int(limit), 30))

    def build():
        return _rows(Biro26DB().execute_query(
            "SELECT * FROM ("
            "  SELECT u.COD, u.DENUMIREA, "
            "         ROUND(SUM(l.CANT),1) QTY, ROUND(SUM(l.SUMA),2) TOTAL "
            "  FROM VMDB_ST201D l "
            "  JOIN TMDB_DOCS d ON d.COD = l.NRDOC AND d.SYSFID = :sf "
            "       AND d.DATAMANUAL >= TRUNC(SYSDATE) - :days "
            "  JOIN TMS_UNIVERS u ON u.COD = l.CTSC "
            "  GROUP BY u.COD, u.DENUMIREA "
            "  ORDER BY SUM(l.SUMA) DESC NULLS LAST"
            ") WHERE ROWNUM <= :lim",
            {"sf": SYSFID_ORDER, "days": days, "lim": limit}))
    return _cached(f"prods:{days}:{limit}", build)


def stale_orders(older_days: int = 3, limit: int = 20) -> List[Dict[str, Any]]:
    """RO: comenzile NELIVRATE mai vechi de N zile - exact ce trebuie
    impins. Cel mai util rind din tot raportul.
    EN: UNDELIVERED orders older than N days - the most actionable list."""
    older = max(1, min(int(older_days), 60))
    limit = max(1, min(int(limit), 100))

    def build():
        return _rows(Biro26DB().execute_query(
            "SELECT * FROM ("
            "  SELECT d.COD, TRIM(d.NRMANUAL) NR, "
            "         TO_CHAR(d.DATAMANUAL,'YYYY-MM-DD') DAY, "
            "         (SELECT ROUND(SUM(l.SUMA),2) FROM VMDB_ST201D l "
            "          WHERE l.NRDOC = d.COD) TOTAL, "
            "         (SELECT u.DENUMIREA FROM TMS_UNIVERS u "
            "          WHERE u.COD = m.DTDEP) CLIENT "
            "  FROM TMDB_DOCS d "
            "  JOIN VMDB_ST201M m ON m.NRDOC = d.COD "
            "  WHERE d.SYSFID = :sf AND m.CTNRDOC IS NULL "
            "    AND d.DATAMANUAL < TRUNC(SYSDATE) - :older "
            "    AND d.DATAMANUAL >= TRUNC(SYSDATE) - 92 "
            "  ORDER BY d.DATAMANUAL"
            ") WHERE ROWNUM <= :lim",
            {"sf": SYSFID_ORDER, "older": older, "lim": limit}))
    return _cached(f"stale:{older}:{limit}", build)
