#!/usr/bin/env python3
"""Autopark -- fuel price history loader (FLT_FUEL_PRICES).

Daily price series 2024-09-01..2026-08-26 for 4 products (A92/A95/A98/
DIESEL). Two data sources, never blended silently:

  SOURCE='ANRE'  -- literal ceiling prices published by anre.md, fetched
                    2026-08-26 via WebFetch of https://anre.md/benzina-95-3-2
                    and https://anre.md/motorina-3-3 plus the retrospective
                    articles for 2025/2026 milestones (see REAL_ANRE below,
                    each value carries its source date as a comment where it
                    isn't obvious). Only A95 and DIESEL have retrievable
                    anchors -- the live anre.md pages expose only a short
                    rolling window (no full 2-year archive reachable without
                    an authenticated/paginated query form), and A92/A98 have
                    no equivalent public history page at all.
  SOURCE='MODEL' -- every other date/product: a synthesized series (slow
                    drift + seasonality + 4-6 sharp step-revisions with
                    partial retracement, matching the profile ANRE's own
                    real jumps show -- see REAL_ANRE's Aug-2026 run and the
                    July-2026 "Middle East tensions" spike in the
                    retrospective article) -- explicitly labeled as a model,
                    not represented as real regulator data.

Idempotent: AutoparkStore.upsert_fuel_prices does one big executemany MERGE
by (PRICE_DATE, PRODUCT_CODE) -- re-running reloads/overwrites the same
~2900 rows, never duplicates them.

    venv/bin/python modules/autopark/scripts/autopark_prices.py --dry-run
    venv/bin/python modules/autopark/scripts/autopark_prices.py --yes
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.autopark.store import AutoparkStore              # noqa: E402

START = date(2024, 9, 1)
END = date(2026, 8, 26)

PRODUCTS = ("A92", "A95", "A98", "DIESEL")

BASE_LEVELS = {
    "A95": 25.0,
    "A92": 24.0,
    "A98": 27.0,
    "DIESEL": 22.5,
}

# Real ANRE ceiling prices (lei/litru), fetched 2026-08-26 from anre.md.
# Kept as exact literal anchors -- SOURCE='ANRE'. Everything else on the
# calendar is SOURCE='MODEL' (see module docstring for why).
REAL_ANRE = {
    "A95": {
        # anre.md/retrospectiva-anului-2025...: max of 2025 was 24.79
        # during 25-28 Jan 2025.
        date(2025, 1, 25): 24.79, date(2025, 1, 26): 24.79,
        date(2025, 1, 27): 24.79, date(2025, 1, 28): 24.79,
        # same source: min of 2025 was 21.72 on 31 Dec 2025.
        date(2025, 12, 31): 21.72,
        # ANRE set 21.92 for 3-5 Jan 2026.
        date(2026, 1, 3): 21.92, date(2026, 1, 4): 21.92,
        date(2026, 1, 5): 21.92,
        # Middle East tensions spike: 30.16 for 25-27 Jul 2026.
        date(2026, 7, 25): 30.16, date(2026, 7, 26): 30.16,
        date(2026, 7, 27): 30.16,
        # anre.md/benzina-95-3-2 rolling window (fetched 26.08.2026).
        date(2026, 8, 12): 30.00, date(2026, 8, 13): 29.98,
        date(2026, 8, 14): 30.01, date(2026, 8, 17): 30.02,
        date(2026, 8, 18): 30.12, date(2026, 8, 19): 30.37,
        date(2026, 8, 20): 30.62, date(2026, 8, 21): 30.82,
        date(2026, 8, 24): 30.95, date(2026, 8, 25): 31.01,
    },
    "DIESEL": {
        date(2025, 1, 25): 21.71, date(2025, 1, 26): 21.71,
        date(2025, 1, 27): 21.71,
        date(2026, 1, 3): 18.70, date(2026, 1, 4): 18.70,
        date(2026, 1, 5): 18.70,
        date(2026, 7, 25): 30.29, date(2026, 7, 26): 30.29,
        date(2026, 7, 27): 30.29,
        # anre.md/motorina-3-3 rolling window (fetched 26.08.2026).
        date(2026, 8, 12): 32.07, date(2026, 8, 13): 31.97,
        date(2026, 8, 14): 31.90, date(2026, 8, 17): 31.77,
        date(2026, 8, 18): 31.98, date(2026, 8, 19): 32.37,
        date(2026, 8, 20): 32.72, date(2026, 8, 21): 33.06,
        date(2026, 8, 24): 33.30, date(2026, 8, 25): 33.32,
    },
}

# 6 step-revision events spread across the 2-year horizon -- typical ANRE
# profile per the task: sharp +8-12% over 1-2 weeks, then partial pullback.
JUMPS = [
    date(2024, 11, 15),
    date(2025, 3, 10),
    date(2025, 6, 20),
    date(2025, 10, 5),
    date(2026, 2, 12),
    date(2026, 6, 28),
]

RAMP_DAYS = 3      # sharp rise (single-day change during the ramp exceeds 3%)
RETRACE_DAYS = 12  # partial pullback afterwards
RETRACE_TO = 0.5   # settles at 50% of the peak increase (permanent step)

RANDOM_SEED = 20260826


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _jump_contribution(d: date, jump_date: date, peak: float) -> float:
    delta = (d - jump_date).days
    if delta < 0:
        return 0.0
    if delta <= RAMP_DAYS:
        return peak * (delta / RAMP_DAYS)
    if delta <= RAMP_DAYS + RETRACE_DAYS:
        frac = (delta - RAMP_DAYS) / RETRACE_DAYS
        return peak * (1 - (1 - RETRACE_TO) * frac)
    return peak * RETRACE_TO


def build_series(product: str, rnd: random.Random) -> dict:
    """One product's full daily MODEL price series (before ANRE override)."""
    base = BASE_LEVELS[product]
    jump_pct = {j: rnd.uniform(0.08, 0.12) for j in JUMPS}
    is_diesel = product == "DIESEL"
    prices = {}
    for i, d in enumerate(daterange(START, END)):
        drift = base * 0.00007 * i
        yday = d.timetuple().tm_yday
        # Gasoline peaks mid-summer (~day 200), diesel peaks mid-winter
        # (~day 15) -- task requirement "летом бензин выше, зимой дизель выше".
        if is_diesel:
            season = 0.4 * math.cos(2 * math.pi * (yday - 15) / 365.0)
        else:
            season = 0.4 * math.cos(2 * math.pi * (yday - 200) / 365.0)
        jump_component = sum(
            _jump_contribution(d, j, base * pct) for j, pct in jump_pct.items())
        noise = rnd.uniform(-0.12, 0.12)
        price = base + drift + season + jump_component + noise
        prices[d] = max(1.0, round(price, 2))
    return prices


def build_all_rows():
    rnd = random.Random(RANDOM_SEED)
    rows = []
    jump_days = set()
    for product in PRODUCTS:
        series = build_series(product, rnd)
        anre = REAL_ANRE.get(product, {})
        prev = None
        for d in daterange(START, END):
            if d in anre:
                price = anre[d]
                source = "ANRE"
            else:
                price = series[d]
                source = "MODEL"
            if prev is not None and prev > 0:
                pct_change = abs(price - prev) / prev * 100
                if pct_change > 3:
                    jump_days.add((product, d))
            prev = price
            rows.append({"price_date": d, "product_code": product,
                        "price_lei": price, "source": source})
    return rows, jump_days


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load 2-year FLT_FUEL_PRICES history (ANRE + model)")
    parser.add_argument("--yes", action="store_true",
                        help="confirm writing to the database")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the series and print diagnostics only")
    args = parser.parse_args()

    if not args.yes and not args.dry_run:
        print("Run with --yes or --dry-run.")
        sys.exit(2)

    rows, jump_days = build_all_rows()
    anre_cnt = sum(1 for r in rows if r["source"] == "ANRE")
    model_cnt = len(rows) - anre_cnt

    print(f"Период: {START.isoformat()} .. {END.isoformat()}")
    print(f"Строк: {len(rows)} ({len(PRODUCTS)} продукта x "
          f"{(END - START).days + 1} дней)")
    print(f"Скачков (день-к-дню > 3%): {len(jump_days)}")
    print(f"ANRE: {anre_cnt} ({anre_cnt / len(rows) * 100:.1f}%), "
          f"MODEL: {model_cnt} ({model_cnt / len(rows) * 100:.1f}%)")

    if args.dry_run:
        print("[dry-run] запись в БД пропущена")
        return

    res = AutoparkStore.upsert_fuel_prices(rows)
    if not res.get("success"):
        print(f"ОШИБКА: {res.get('message')}")
        sys.exit(1)
    print(f"Загружено/обновлено строк: {res['data']['rows']}")


if __name__ == "__main__":
    main()
