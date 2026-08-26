#!/usr/bin/env python3
"""Autopark -- fuel price history loader (FLT_FUEL_PRICES).

Daily price series 2024-09-01..2026-08-26 for 4 products (A92/A95/A98/
DIESEL). Two data sources, never blended silently:

  SOURCE='ANRE'  -- the REAL daily ceiling-price archive of anre.md.
                    Harvested 2026-08-26 through the site's own AJAX
                    endpoint `/oil-get-table?firstDate=&secondDate=&fuelId=`
                    (the same endpoint the date-range filter on
                    anre.md/benzina-95-3-2 and anre.md/motorina-3-3 calls;
                    fuelId=2 -> Benzina A95, fuelId=3 -> Motorina).
                    500 publication-day points per product covering the
                    whole window 2024-09-02..2026-08-26. The registry of
                    primary points lives in docs/Autopark/anre_prices_raw.csv
                    (date,product,price,source_url) -- this script only
                    LOADS it, it does not synthesize any of it.

                    ANRE publishes on working days; a ceiling price stays
                    legally in force until the next decision, so weekend/
                    holiday gaps BETWEEN two real points are closed by a
                    step function (forward-fill of the last published
                    price). CK_FLT_FUEL_PRICES_SRC only allows
                    ('ANRE','MODEL'), so forward-filled days also carry
                    SOURCE='ANRE'; which days are primary publications is
                    exactly the CSV registry (see docs/Autopark/
                    PRICES_ANRE.md for the methodology).

  SOURCE='MODEL' -- only where no real regulator data exists:
                    * A92/A98 for the whole period -- ANRE does NOT
                      regulate them (only A95 and diesel have ceiling
                      prices), so a real archive for them cannot exist;
                    * edge days outside the real archive (before the first
                      real point / after the last one) for A95/DIESEL --
                      in practice just 2024-09-01, a Sunday before the
                      first publication in the window. Edge MODEL days are
                      calibrated to the nearest real anchor
                      (calibrate_to_anchors) so the seam stays smooth,
                      but keep the honest MODEL label.

Idempotent: AutoparkStore.upsert_fuel_prices does one big executemany MERGE
by (PRICE_DATE, PRODUCT_CODE) -- re-running reloads/overwrites the same
~2900 rows, never duplicates them.

    venv/bin/python modules/autopark/scripts/autopark_prices.py --dry-run
    venv/bin/python modules/autopark/scripts/autopark_prices.py --yes
    venv/bin/python modules/autopark/scripts/autopark_prices.py \
        --anre-csv docs/Autopark/anre_prices_raw.csv --yes
"""
from __future__ import annotations

import argparse
import csv
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

# Registry of REAL ANRE ceiling prices (primary publication-day points).
ANRE_CSV_DEFAULT = os.path.join(ROOT, "docs", "Autopark",
                                "anre_prices_raw.csv")


def load_anre_csv(path: str) -> dict:
    """Read the harvested archive: {product: {date: price_lei}}.

    Only A95/DIESEL may appear -- ANRE regulates ceiling prices for
    Benzina A95 and Motorina only; A92/A98 are not price-regulated and a
    real ceiling-price archive for them does not exist.
    """
    out: dict = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = date.fromisoformat(row["date"])
            if START <= d <= END:
                out.setdefault(row["product"], {})[d] = float(row["price"])
    return out


# Real ANRE ceiling prices (lei/litru): the FULL harvested daily archive.
# Loaded at import time so the acceptance tests exercise the same data the
# loader writes. A92/A98 intentionally absent (not regulated by ANRE).
REAL_ANRE = load_anre_csv(ANRE_CSV_DEFAULT)

# 6 step-revision events for the MODEL series (A92/A98 only) -- typical
# profile: sharp +8-12% over a few days, then partial retracement.
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
        # (~day 15).
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


def calibrate_to_anchors(series: dict, anchors: dict) -> dict:
    """Multiply the raw MODEL series by a piecewise-linear correction
    factor tied to the real ANRE anchors, so any MODEL day that survives
    next to real data (in practice only the edge days outside the real
    archive) sits at the real level instead of the synthetic one.

    The factor is 1.0 exactly AT each anchor date (by construction:
    anchor_price / raw_model_price_at_that_date), linearly interpolated
    BETWEEN consecutive anchors, and held flat before the first/after the
    last anchor. Products with no anchors are returned unchanged.
    """
    if not anchors:
        return dict(series)

    anchor_days = sorted(anchors)
    factors = {}
    for ad in anchor_days:
        base = series.get(ad)
        if base:
            factors[ad] = anchors[ad] / base
    if not factors:
        return dict(series)

    ordered = sorted(factors)
    ordinals = [d.toordinal() for d in ordered]
    fvalues = [factors[d] for d in ordered]

    def factor_at(d: date) -> float:
        o = d.toordinal()
        if o <= ordinals[0]:
            return fvalues[0]
        if o >= ordinals[-1]:
            return fvalues[-1]
        # binary search: with a 500-anchor real archive a linear scan per
        # calendar day would be ~360k comparisons for nothing.
        lo, hi = 0, len(ordinals) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if ordinals[mid] <= o:
                lo = mid
            else:
                hi = mid
        o0, o1 = ordinals[lo], ordinals[hi]
        f0, f1 = fvalues[lo], fvalues[hi]
        if o1 == o0:
            return f1
        frac = (o - o0) / (o1 - o0)
        return f0 + (f1 - f0) * frac

    return {d: max(1.0, round(price * factor_at(d), 2))
            for d, price in series.items()}


def build_all_rows(anre: dict | None = None):
    """Full 4-product daily series.

    A95/DIESEL: real ANRE points on publication days, step-function
    forward-fill of the last published price BETWEEN them (both
    SOURCE='ANRE' -- the ceiling stays in force until the next decision;
    the CSV registry distinguishes primary points), MODEL only on edge
    days outside the real archive. A92/A98: MODEL everywhere (not
    regulated). Returns (rows, jump_days) plus per-product stat fields on
    each row via 'source'; jump_days flags day-to-day moves > 3%.
    """
    if anre is None:
        anre = REAL_ANRE
    rnd = random.Random(RANDOM_SEED)
    rows = []
    jump_days = set()
    stats: dict = {}
    for product in PRODUCTS:
        raw_series = build_series(product, rnd)
        real = anre.get(product, {})
        series = calibrate_to_anchors(raw_series, real) if real else raw_series
        first = min(real) if real else None
        last = max(real) if real else None
        st = stats.setdefault(product, {"real": 0, "ff": 0, "model": 0})
        prev = None
        last_real_price = None
        for d in daterange(START, END):
            if d in real:
                price = real[d]
                last_real_price = price
                source = "ANRE"
                st["real"] += 1
            elif first is not None and first < d < last:
                # gap between two real decisions: the last published
                # ceiling price is still legally in force (step function).
                price = last_real_price
                source = "ANRE"
                st["ff"] += 1
            else:
                price = series[d]
                source = "MODEL"
                st["model"] += 1
            if prev is not None and prev > 0:
                pct_change = abs(price - prev) / prev * 100
                if pct_change > 3:
                    jump_days.add((product, d))
            prev = price
            rows.append({"price_date": d, "product_code": product,
                        "price_lei": price, "source": source})
    build_all_rows.last_stats = stats
    return rows, jump_days


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load 2-year FLT_FUEL_PRICES history (real ANRE archive "
                    "+ forward-fill; MODEL only for unregulated A92/A98)")
    parser.add_argument("--yes", action="store_true",
                        help="confirm writing to the database")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the series and print diagnostics only")
    parser.add_argument("--anre-csv", default=ANRE_CSV_DEFAULT,
                        help="registry of real ANRE points "
                             "(date,product,price,source_url)")
    args = parser.parse_args()

    if not args.yes and not args.dry_run:
        print("Run with --yes or --dry-run.")
        sys.exit(2)

    anre = load_anre_csv(args.anre_csv)
    rows, jump_days = build_all_rows(anre)
    stats = build_all_rows.last_stats

    print(f"Период: {START.isoformat()} .. {END.isoformat()}")
    print(f"Строк: {len(rows)} ({len(PRODUCTS)} продукта x "
          f"{(END - START).days + 1} дней)")
    print(f"Скачков (день-к-дню > 3%): {len(jump_days)}")
    for product in PRODUCTS:
        st = stats[product]
        real = anre.get(product, {})
        span = (f"{min(real).isoformat()}..{max(real).isoformat()}"
                if real else "нет реальных точек (ANRE не регулирует)")
        print(f"  {product}: реальных ANRE {st['real']}, forward-fill "
              f"{st['ff']}, MODEL {st['model']}  [{span}]")

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
