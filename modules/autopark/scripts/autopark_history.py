#!/usr/bin/env python3
"""Autopark -- 2-year operational history generator (Bemol presentation demo).

Zачем отдельный скрипт, а не продолжение autopark_demo.py (10-дневный,
малый набор): здесь нужен масштаб (~700+ рейсов, ~26 тыс. строк учёта
остатков за 2024-09-01..2026-08-26) -- построчная вставка через
AutoparkController/AutoparkStore (как делает autopark_demo.py) означала бы
тысячи отдельных сетевых round-trip к облачному ADB и заняла бы часы.
Вместо этого:

  * бизнес-цифры (NORM_KM, распределение поставок по бензовозам,
    зарплата) считаются ТЕМИ ЖЕ функциями modules/autopark/rules.py,
    что использует контроллер -- rules.route_legs/norm_route_km для
    норматива и rules.plan_trips для распределения поставок по
    бензовозам/секциям (жадный ближайший сосед, та же эвристика, что и в
    ручном планировании через UI);
  * запись в Oracle -- пакетным `cursor.executemany()` по одному вызову
    на таблицу (FLT_STATION_STOCK, FLT_DELIVERIES, FLT_TRIPS,
    FLT_TRIP_STOPS, FLT_TRIP_STOP_ITEMS), а не поштучными INSERT;
  * ID для родительских строк (рейс -> его остановки -> их позиции)
    нужны ДО вставки, чтобы связать их в памяти одним проходом --
    получены заранее одним запросом на таблицу
    (`SELECT SEQ.NEXTVAL FROM DUAL CONNECT BY LEVEL <= :n`), а не через
    CURRVAL после потриginateд построчной вставки (batched insert не
    гарантирует, что CURRVAL после executemany укажет на нужную строку).
    Триггер BEFORE INSERT каждой таблицы (см. sql/120_flt_tables.sql)
    присваивает ID только когда :NEW.ID IS NULL -- переданный явно ID
    его не трогает.

Идемпотентность: без `--reset` скрипت проверяет, есть ли уже рейсы
старше 30 дней (признак того, что история уже сгенерирована), и выходит
с сообщением вместо повторной генерации. `--reset` чистит ТОЛЬКО
операционные FLT_-таблицы (рейсы/стопы/позиции/накладные/сток/журнал) --
справочники (АЗС/автомобили/водители/матрица расстояний/продукты/цены)
не трогает.

    venv/bin/python modules/autopark/scripts/autopark_history.py --dry-run
    venv/bin/python modules/autopark/scripts/autopark_history.py --reset --yes
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

from models.database import DatabaseModel                        # noqa: E402
from modules.autopark import rules                                # noqa: E402
from modules.autopark.controller import AutoparkController        # noqa: E402
from modules.autopark.store import AutoparkStore                  # noqa: E402

START = date(2024, 9, 1)
END = date(2026, 8, 26)

USER = "history_gen"
RANDOM_SEED = 20260826

GASOLINE = ("A92", "A95", "A98")

# Operational tables reset by --reset, in FK-safe order (children first).
RESET_TABLES_IN_FK_ORDER = (
    "FLT_TRIP_STOP_ITEMS",
    "FLT_TRIP_STOPS",
    "FLT_DELIVERIES",
    "FLT_TRIPS",
    "FLT_STATION_STOCK",
)


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def get_json(res, label):
    if not res.get("success"):
        raise RuntimeError(f"{label}: {res.get('message')}")
    return res["data"]


def next_ids(db, seq_name: str, n: int):
    """Pre-fetch `n` sequence values in one round trip (see module docstring)."""
    if n <= 0:
        return []
    r = db.execute_query(
        f"SELECT {seq_name}.NEXTVAL AS ID FROM DUAL CONNECT BY LEVEL <= :n",
        {"n": n})
    if not r.get("success"):
        raise RuntimeError(f"{seq_name}: {r.get('message')}")
    return [row[0] for row in r["data"]]


# ── reset / guard -------------------------------------------------------

def reset_operational_data():
    with DatabaseModel() as db:
        for table in RESET_TABLES_IN_FK_ORDER:
            r = db.execute_query(f"DELETE /*+ NO_PARALLEL */ FROM {table}")
            if not r.get("success"):
                raise RuntimeError(f"Очистка {table}: {r.get('message')}")
        db.connection.commit()
    print("Операционные данные очищены (рейсы, стопы, позиции, накладные, "
          "учёт остатков).")


def history_already_present() -> bool:
    with DatabaseModel() as db:
        r = db.execute_query(
            "SELECT COUNT(*) AS CNT FROM FLT_TRIPS WHERE TRIP_DATE < :cutoff",
            {"cutoff": date.today() - timedelta(days=30)})
        if r.get("success") and r.get("data"):
            return r["data"][0][0] > 0
    return False


# ── master data load -----------------------------------------------------

class MasterData:
    def __init__(self):
        self.stations = get_json(AutoparkStore.list_stations(), "list_stations")
        self.trucks = get_json(AutoparkStore.list_trucks(), "list_trucks")
        self.drivers = get_json(AutoparkStore.list_drivers(), "list_drivers")
        load_points = get_json(AutoparkStore.list_load_points(), "list_load_points")
        end_points = get_json(AutoparkStore.list_end_points(), "list_end_points")
        self.load_points_by_code = {p["code"]: p for p in load_points}
        self.end_points_by_code = {p["code"]: p for p in end_points}
        settings = get_json(AutoparkStore.get_settings(), "get_settings")
        self.rate_per_km = float(settings["rate_per_km"])
        self.trip_bonus = float(settings["trip_bonus"])
        self.safety_days = float(settings["safety_days"])
        self.dist_lookup = AutoparkStore.distance_lookup_fn()

        if not self.stations:
            raise RuntimeError(
                "FLT_STATIONS пуст -- сначала запустите autopark_demo.py "
                "(master-данные), затем autopark_history.py")
        if "KIS" not in self.load_points_by_code or "CONST" not in self.load_points_by_code:
            raise RuntimeError("Пункты загрузки KIS/CONST не заведены")
        if "BAZA" not in self.end_points_by_code:
            raise RuntimeError("Конечный пункт BAZA не заведён")


# ── station/product baseline sales profile -------------------------------

def build_sales_profiles(stations, rnd: random.Random):
    """Base daily sales per (station_id, product_code) -- deterministic per
    tank, derived from its capacity so bigger tanks sell more (task: own
    average per station/product)."""
    profiles = {}
    for st in stations:
        for tank in st["tanks"]:
            cap = tank["capacity_l"]
            cycle_days = rnd.uniform(12.0, 18.0)  # ~ full-tank sell-through cycle
            base_sales = cap / cycle_days
            profiles[(st["id"], tank["product_code"])] = {
                "capacity_l": cap,
                "base_sales": base_sales,
                "initial_l": cap * 0.6,
            }
    return profiles


def daily_sales(base_sales: float, product: str, d: date, rnd: random.Random) -> float:
    weekday = d.weekday()  # 0=Mon .. 6=Sun
    weekly = 1.25 if weekday in (4, 5) else (0.85 if weekday == 6 else 1.0)
    yday = d.timetuple().tm_yday
    if product in GASOLINE:
        seasonal = 1.0 + 0.15 * math.cos(2 * math.pi * (yday - 200) / 365.0)
    else:
        seasonal = 1.0 + 0.15 * math.cos(2 * math.pi * (yday - 15) / 365.0)
    noise = rnd.uniform(0.85, 1.15)
    return max(0.0, base_sales * weekly * seasonal * noise)


# ── trip generation --------------------------------------------------------

def build_import_trip_dates():
    """~1 import (Chisinau-Constanta-Chisinau) trip per month, day varies."""
    dates = []
    d = date(START.year, START.month, 12)
    while d <= END:
        dates.append(d)
        month = d.month + 1
        year = d.year
        if month > 12:
            month = 1
            year += 1
        day = 8 + (d.month * 7) % 15  # varies 8..22, deterministic per month
        d = date(year, month, min(day, 27))
    return [d for d in dates if START <= d <= END]


def generate(md: MasterData, rnd: random.Random):
    profiles = build_sales_profiles(md.stations, rnd)
    current = {k: v["initial_l"] for k, v in profiles.items()}

    kis_id = md.load_points_by_code["KIS"]["id"]
    const_id = md.load_points_by_code["CONST"]["id"]
    baza_id = md.end_points_by_code["BAZA"]["id"]
    chi_station = next(s for s in md.stations if s["code"] == "CHI")

    stock_rows = []
    trip_records = []       # dicts: header + stops + items, filled with tmp ids
    import_dates = set(build_import_trip_dates())

    truck_i = 0
    driver_i = 0
    tmp_trip_seq = 0

    for day_index, d in enumerate(daterange(START, END)):
        received_today = {}  # (station_id, product) -> volume_l

        # -- import trip (Chisinau-Constanta-Chisinau), ~monthly ------------
        if d in import_dates:
            truck = md.trucks[truck_i % len(md.trucks)]
            driver = md.drivers[driver_i % len(md.drivers)]
            truck_i += 1
            driver_i += 1
            legs = rules.route_legs(const_id, [chi_station["id"]], baza_id,
                                    md.dist_lookup)
            norm_km = rules.norm_route_km([leg["km"] for leg in legs])
            fact_km = norm_km + rnd.uniform(-5, 5)
            norm_fuel = rules.fuel_norm_l(norm_km, truck["norm_l_per_100km"])
            fact_fuel = norm_fuel * rnd.uniform(0.97, 1.03)
            volume = rnd.uniform(9000, 12000)
            tmp_trip_seq += 1
            trip_records.append({
                "tmp_id": tmp_trip_seq,
                "trip_date": d, "truck_id": truck["id"], "driver_id": driver["id"],
                "type_code": "IMPORT", "status_code": "APPROVED",
                "load_point_id": const_id, "end_point_id": baza_id,
                "source": "AUTO", "norm_km": norm_km, "fact_km": fact_km,
                "fact_minutes": int(fact_km / 55 * 60 + rnd.uniform(-10, 10)),
                "fact_fuel_l": fact_fuel,
                "stops": [{"station_id": chi_station["id"],
                          "items": [{"product_code": "A98", "volume_l": volume}]}],
            })
            received_today[(chi_station["id"], "A98")] = (
                received_today.get((chi_station["id"], "A98"), 0.0) + volume)

        # -- domestic supply planning (rules.plan_trips) --------------------
        needs = []
        pair_sales = {}
        for (station_id, product), prof in profiles.items():
            cur_l = current[(station_id, product)]
            base_sales = prof["base_sales"]
            sales = daily_sales(base_sales, product, d, rnd)
            pair_sales[(station_id, product)] = sales
            days_left = rules.stock_days(cur_l, base_sales)
            min_stock = rules.min_stock_l(base_sales, md.safety_days)
            forecast = base_sales * md.safety_days
            need_l = rules.need_volume_l(cur_l, min_stock, forecast, 0.0,
                                        prof["capacity_l"])
            if need_l > 200:
                needs.append({"station_id": station_id, "product_code": product,
                            "need_l": need_l, "days_left": days_left})

        if needs:
            rotated = md.trucks[truck_i % len(md.trucks):] + \
                md.trucks[:truck_i % len(md.trucks)]
            # Route length constraint (task: маршруты 1-3 АЗС): cap each
            # truck's usable sections for this trip to 1-3, even though its
            # real hardware has 4-6 -- a route visiting every section's
            # worth of stations in one run would routinely hit 4-6 stops.
            trucks_today = [
                dict(t, sections_cnt=min(t["sections_cnt"], rnd.randint(1, 3)))
                for t in rotated
            ]
            planned = rules.plan_trips(needs, trucks_today, md.dist_lookup, kis_id)
            for trip in planned:
                truck = next(t for t in md.trucks if t["id"] == trip["truck"])
                driver = md.drivers[driver_i % len(md.drivers)]
                driver_i += 1
                truck_i += 1
                station_ids_seq = [s["station_id"] for s in trip["stops"]]
                legs = rules.route_legs(kis_id, station_ids_seq, baza_id,
                                        md.dist_lookup)
                norm_km = rules.norm_route_km([leg["km"] for leg in legs])

                over_km = rnd.random() < 0.04
                fact_km = (norm_km + rnd.uniform(20, 60) if over_km
                          else norm_km + rnd.uniform(-9, 9))
                norm_fuel = rules.fuel_norm_l(norm_km, truck["norm_l_per_100km"])
                over_fuel = rnd.random() < 0.03
                fact_fuel = (norm_fuel * rnd.uniform(1.06, 1.15) if over_fuel
                            else norm_fuel * rnd.uniform(0.97, 1.03))

                tmp_trip_seq += 1
                trip_records.append({
                    "tmp_id": tmp_trip_seq,
                    "trip_date": d, "truck_id": truck["id"], "driver_id": driver["id"],
                    "type_code": "DOMESTIC", "status_code": "APPROVED",
                    "load_point_id": kis_id, "end_point_id": baza_id,
                    "source": "AUTO", "norm_km": norm_km, "fact_km": fact_km,
                    "fact_minutes": int(fact_km / 45 * 60 + rnd.uniform(-10, 10)),
                    "fact_fuel_l": fact_fuel,
                    "stops": trip["stops"],
                })
                for stop in trip["stops"]:
                    for item in stop["items"]:
                        key = (stop["station_id"], item["product"])
                        received_today[key] = received_today.get(key, 0.0) + item["volume"]

        # -- apply sales/received, close the day for every pair ------------
        for key, prof in profiles.items():
            open_l = current[key]
            sales = min(pair_sales[key], open_l)
            received = received_today.get(key, 0.0)
            close_l = max(0.0, open_l - sales + received)
            stock_rows.append({
                "station_id": key[0], "product_code": key[1], "stock_date": d,
                "open_l": round(open_l, 2), "close_l": round(close_l, 2),
                "sales_l": round(sales, 2), "received_l": round(received, 2),
            })
            current[key] = close_l

    return stock_rows, trip_records


# ── bulk write ------------------------------------------------------------

def write_all(trip_records, stock_rows):
    with DatabaseModel() as db:
        # 1) pre-fetch ids for parent rows so children can reference them
        #    in-memory before the batch insert.
        trip_ids = next_ids(db, "SEQ_FLT_TRIPS", len(trip_records))
        n_stops = sum(len(t["stops"]) for t in trip_records)
        stop_ids = next_ids(db, "SEQ_FLT_TRIP_STOPS", n_stops)
        n_items = sum(len(s["items"]) for t in trip_records for s in t["stops"])
        item_ids = next_ids(db, "SEQ_FLT_TRIP_STOP_ITEMS", n_items)
        n_deliv = n_items  # one delivery row per stop-item (see module docstring)
        deliv_ids = next_ids(db, "SEQ_FLT_DELIVERIES", n_deliv)

        trip_binds, stop_binds, item_binds, deliv_binds = [], [], [], []
        stop_cursor = 0
        item_cursor = 0
        deliv_cursor = 0
        for trip, trip_id in zip(trip_records, trip_ids):
            trip_binds.append({
                "id": trip_id, "trip_date": trip["trip_date"],
                "truck_id": trip["truck_id"], "driver_id": trip["driver_id"],
                "type_code": trip["type_code"], "status_code": trip["status_code"],
                "load_point_id": trip["load_point_id"],
                "end_point_id": trip["end_point_id"], "source": trip["source"],
                "norm_km": round(trip["norm_km"], 1),
                "fact_km": round(trip["fact_km"], 1),
                "fact_minutes": max(1, trip["fact_minutes"]),
                "fact_fuel_l": round(trip["fact_fuel_l"], 1),
            })
            for seq_no, stop in enumerate(trip["stops"], start=1):
                stop_id = stop_ids[stop_cursor]
                stop_cursor += 1
                stop_binds.append({
                    "id": stop_id, "trip_id": trip_id, "seq_no": seq_no,
                    "station_id": stop["station_id"],
                })
                for item in stop["items"]:
                    item_id = item_ids[item_cursor]
                    item_cursor += 1
                    item_binds.append({
                        "id": item_id, "stop_id": stop_id,
                        "product_code": item["product_code"] if "product_code" in item
                        else item["product"],
                        "volume_l": round(item["volume_l"] if "volume_l" in item
                                         else item["volume"], 2),
                    })
                    deliv_id = deliv_ids[deliv_cursor]
                    deliv_cursor += 1
                    deliv_binds.append({
                        "id": deliv_id, "deliv_date": trip["trip_date"],
                        "product_code": item["product_code"] if "product_code" in item
                        else item["product"],
                        "volume_l": round(item["volume_l"] if "volume_l" in item
                                         else item["volume"], 2),
                        "load_point_id": trip["load_point_id"],
                        "station_id": stop["station_id"],
                        "truck_id": trip["truck_id"], "driver_id": trip["driver_id"],
                        "trip_id": trip_id,
                    })

        with db.connection.cursor() as cur:
            cur.executemany(
                "INSERT INTO FLT_TRIPS (ID, TRIP_DATE, TRUCK_ID, DRIVER_ID, "
                "TYPE_CODE, STATUS_CODE, LOAD_POINT_ID, END_POINT_ID, "
                "SOURCE, NORM_KM, FACT_KM, FACT_MINUTES, FACT_FUEL_L) "
                "VALUES (:id, :trip_date, :truck_id, :driver_id, :type_code, "
                ":status_code, :load_point_id, :end_point_id, :source, "
                ":norm_km, :fact_km, :fact_minutes, :fact_fuel_l)", trip_binds)
            cur.executemany(
                "INSERT INTO FLT_TRIP_STOPS (ID, TRIP_ID, SEQ_NO, STATION_ID) "
                "VALUES (:id, :trip_id, :seq_no, :station_id)", stop_binds)
            cur.executemany(
                "INSERT INTO FLT_TRIP_STOP_ITEMS (ID, STOP_ID, PRODUCT_CODE, "
                "VOLUME_L) VALUES (:id, :stop_id, :product_code, :volume_l)",
                item_binds)
            cur.executemany(
                "INSERT INTO FLT_DELIVERIES (ID, DELIV_DATE, PRODUCT_CODE, "
                "VOLUME_L, LOAD_POINT_ID, STATION_ID, TRUCK_ID, DRIVER_ID, "
                "TRIP_ID) VALUES (:id, :deliv_date, :product_code, "
                ":volume_l, :load_point_id, :station_id, :truck_id, "
                ":driver_id, :trip_id)", deliv_binds)
            stock_binds = [{
                "station_id": r["station_id"], "product_code": r["product_code"],
                "stock_date": r["stock_date"], "open_l": r["open_l"],
                "close_l": r["close_l"], "sales_l": r["sales_l"],
                "received_l": r["received_l"],
            } for r in stock_rows]
            cur.executemany(
                "INSERT INTO FLT_STATION_STOCK (STATION_ID, PRODUCT_CODE, "
                "STOCK_DATE, OPEN_L, CLOSE_L, SALES_L, RECEIVED_L) VALUES "
                "(:station_id, :product_code, :stock_date, :open_l, "
                ":close_l, :sales_l, :received_l)", stock_binds)
        db.connection.commit()

    return {
        "trips": len(trip_binds), "stops": len(stop_binds),
        "items": len(item_binds), "deliveries": len(deliv_binds),
        "stock": len(stock_binds),
    }


# ── payroll parity check ---------------------------------------------------

def payroll_parity_check(trip_records, rate: float, bonus: float):
    """One month, hand-computed from the in-memory generated trips vs the
    controller's own payroll report -- the two MUST match exactly."""
    candidates = sorted({t["trip_date"].strftime("%Y-%m")
                        for t in trip_records if t["trip_date"] >= date(2026, 1, 1)})
    if not candidates:
        candidates = sorted({t["trip_date"].strftime("%Y-%m") for t in trip_records})
    month = candidates[len(candidates) // 2] if candidates else None
    if not month:
        print("Сверка зарплаты пропущена: нет рейсов")
        return

    year, mon = (int(x) for x in month.split("-"))
    date_from = date(year, mon, 1)
    date_to = date(year + (1 if mon == 12 else 0), 1 if mon == 12 else mon + 1, 1) \
        - timedelta(days=1)

    by_driver = {}
    for t in trip_records:
        if not (date_from <= t["trip_date"] <= date_to):
            continue
        if t["status_code"] == "DRAFT":
            continue
        acc = by_driver.setdefault(t["driver_id"], {"norm_km": 0.0, "domestic": 0})
        acc["norm_km"] += t["norm_km"]
        if t["type_code"] == "DOMESTIC":
            acc["domestic"] += 1

    expected = {
        driver_id: acc["norm_km"] * rate + acc["domestic"] * bonus
        for driver_id, acc in by_driver.items()
    }

    res = AutoparkController.payroll_report({
        "date_from": date_from.isoformat(), "date_to": date_to.isoformat()})
    if not res.get("success"):
        print(f"Сверка зарплаты: контроллер вернул ошибку: {res.get('message')}")
        return
    trips = res.get("data") or []
    actual = {}
    for t in trips:
        if t.get("status") == "DRAFT":
            continue
        actual.setdefault(t["driver_id"], 0.0)
        actual[t["driver_id"]] += float(t.get("total_pay") or 0)

    driver_names = {d["id"]: d["full_name"] for d in get_json(
        AutoparkStore.list_drivers(), "list_drivers")}

    print(f"\nСверка зарплаты за {month} (ручной расчёт из сгенерированных "
        f"рейсов vs controller.payroll_report):")
    all_ok = True
    for driver_id, exp in expected.items():
        act = actual.get(driver_id, 0.0)
        ok = abs(exp - act) < 0.01
        all_ok = all_ok and ok
        print(f"  {driver_names.get(driver_id, driver_id)}: ожидалось "
            f"{exp:.2f}, controller вернул {act:.2f} [{'OK' if ok else 'MISMATCH'}]")
    print(f"  Итог: {'СХОДИТСЯ' if all_ok else 'РАСХОЖДЕНИЕ'}")


# ── main --------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autopark 2-year operational history generator")
    parser.add_argument("--reset", action="store_true",
                        help="clear operational data first (trips/stops/"
                             "items/deliveries/stock)")
    parser.add_argument("--yes", action="store_true",
                        help="confirm writing to the database")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the dataset and print counts only")
    args = parser.parse_args()

    if not args.yes and not args.dry_run:
        print("Run with --yes or --dry-run.")
        sys.exit(2)

    if args.reset:
        if not args.dry_run:
            reset_operational_data()
    elif history_already_present():
        print("История уже сгенерирована (найдены рейсы старше 30 дней). "
            "Запустите с --reset для пересоздания.")
        sys.exit(0)

    md = MasterData()
    rnd = random.Random(RANDOM_SEED)
    print(f"Период: {START.isoformat()} .. {END.isoformat()}")
    print("Генерация ...")
    stock_rows, trip_records = generate(md, rnd)

    n_stops = sum(len(t["stops"]) for t in trip_records)
    n_items = sum(len(s["items"]) for t in trip_records for s in t["stops"])
    print(f"  рейсов: {len(trip_records)}, остановок: {n_stops}, "
        f"позиций/накладных: {n_items}, строк учёта остатков: {len(stock_rows)}")
    import_cnt = sum(1 for t in trip_records if t["type_code"] == "IMPORT")
    over_km_cnt = sum(1 for t in trip_records
                      if abs(t["fact_km"] - t["norm_km"]) > 15)
    print(f"  из них импортных: {import_cnt}, "
        f"с превышением пробега (>15км): {over_km_cnt}")

    if args.dry_run:
        print("[dry-run] запись в БД пропущена")
        return

    print("Запись в Oracle (executemany) ...")
    counts = write_all(trip_records, stock_rows)
    print(f"  вставлено: {counts}")

    AutoparkStore.log_event("HISTORY_GEN", None, None,
                            f"autopark_history v1: {len(trip_records)} trips, "
                            f"{len(stock_rows)} stock rows", USER)

    payroll_parity_check(trip_records, md.rate_per_km, md.trip_bonus)


if __name__ == "__main__":
    main()
