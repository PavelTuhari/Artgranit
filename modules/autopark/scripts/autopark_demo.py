#!/usr/bin/env python3
"""Autopark -- demo dataset (fuel-tanker fleet, client Bemol).

Зачем отдельный скрипт, а не SQL-файл: мастер-данные заводятся через
AutoparkStore, а операционка (накладные -> автоформирование рейсов ->
утверждение -> факт GPS -> ручной многоостановочный рейс -> импортный
рейс) -- через AutoparkController, точно тем же путём, каким пользуется
логист через UI. SQL-инсерт проверил бы только сам себя, а не реальный
код.

Идемпотентность:
  * мастер-данные (АЗС, автомобили, водители, матрица расстояний) --
    ищутся по естественному ключу (код/госномер/табельный номер) и
    создаются только если ещё не существуют; матрица расстояний всегда
    MERGE (AutoparkStore.set_distance), повторный запуск её не дублирует;
  * операционные данные (накладные, рейсы, суточный учёт остатков) --
    создаются один раз и помечаются меткой в FLT_EVENT_LOG
    (EVENT_TYPE='DEMO_SEED'); повторный запуск без --reset находит метку
    и не создаёт дублей.
  * `--reset` чистит ТОЛЬКО бизнес-данные (наклад­ные, рейсы, их
    остановки/позиции, суточный учёт остатков, журнал) в порядке внешних
    ключей -- справочники модуля (продукты/типы/статусы/настройки/пункты
    загрузки из sql/122_flt_seed.sql, а также АЗС/автомобили/водители/
    матрица расстояний, заведённые этим же скриптом) не трогает: их
    заново заводить не нужно, они и так идемпотентны.

    venv/bin/python modules/autopark/scripts/autopark_demo.py
    venv/bin/python modules/autopark/scripts/autopark_demo.py --reset
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import DatabaseModel                      # noqa: E402
from modules.autopark.controller import AutoparkController      # noqa: E402
from modules.autopark.store import AutoparkStore                # noqa: E402

USER = "demo"
SEED_MARK_EVENT = "DEMO_SEED"
SEED_MARK_VALUE = "autopark_demo v1"

TODAY = date.today()


def d(days_ago: int) -> date:
    return TODAY - timedelta(days=days_ago)


# ── Мастер-данные ────────────────────────────────────────────────────────

STATIONS = [
    {"code": "ORH", "name": "АЗС Оргеев", "address": "Оргеев, трасса Кишинёв-Оргеев",
     "tanks": {"A95": 18000, "DIESEL": 24000}},
    {"code": "BAL", "name": "АЗС Бельцы", "address": "Бельцы, ул. Индустриальная",
     "tanks": {"A92": 16000, "A95": 20000, "DIESEL": 28000}},
    {"code": "SOR", "name": "АЗС Сороки", "address": "Сороки, трасса R7",
     "tanks": {"A95": 15000, "DIESEL": 20000}},
    {"code": "CAH", "name": "АЗС Кагул", "address": "Кагул, ул. Республики",
     "tanks": {"A92": 14000, "DIESEL": 22000}},
    {"code": "UNG", "name": "АЗС Унгены", "address": "Унгены, трасса R1",
     "tanks": {"A95": 16000, "DIESEL": 20000}},
    {"code": "COM", "name": "АЗС Комрат", "address": "Комрат, ул. Ленина",
     "tanks": {"A92": 12000, "DIESEL": 18000}},
    {"code": "EDI", "name": "АЗС Единец", "address": "Единец, трасса R8",
     "tanks": {"A95": 13000, "DIESEL": 17000}},
    {"code": "STR", "name": "АЗС Стрэшень", "address": "Стрэшень, трасса M1",
     "tanks": {"A92": 12000, "A95": 15000, "DIESEL": 19000}},
    {"code": "CHI", "name": "АЗС Кишинёв-Центр", "address": "Кишинёв, Центр",
     "tanks": {"A92": 20000, "A95": 25000, "A98": 10000, "DIESEL": 30000}},
]

TRUCKS = [
    {"plate": "C AA 101", "brand": "MAN TGS", "capacity_l": 25000,
     "sections_cnt": 4, "norm_l_per_100km": 28.0,
     "products": ["A92", "A95", "DIESEL"]},
    {"plate": "C BB 202", "brand": "Mercedes Actros", "capacity_l": 30000,
     "sections_cnt": 5, "norm_l_per_100km": 31.0,
     "products": ["A92", "A95", "A98", "DIESEL"]},
    {"plate": "C CC 303", "brand": "Volvo FH", "capacity_l": 36000,
     "sections_cnt": 6, "norm_l_per_100km": 34.0,
     "products": ["A95", "DIESEL"]},
]

DRIVERS = [
    {"full_name": "Ион Морарь", "tab_no": "D-001", "truck_plate": "C AA 101"},
    {"full_name": "Виктор Кроитор", "tab_no": "D-002", "truck_plate": "C BB 202"},
    {"full_name": "Андрей Русу", "tab_no": "D-003", "truck_plate": "C CC 303"},
    {"full_name": "Сергей Цуркан", "tab_no": "D-004", "truck_plate": "C CC 303"},
]

# from_kind/from_code, to_kind/to_code, km -- codes resolved to ids at runtime.
# Km подобраны близко к реальным расстояниям по трассе (не по прямой).
DISTANCES = [
    ("LOAD", "KIS", "STATION", "ORH", 46.0),
    ("LOAD", "KIS", "STATION", "BAL", 135.0),
    ("LOAD", "KIS", "STATION", "SOR", 184.0),
    ("LOAD", "KIS", "STATION", "CAH", 180.0),
    ("LOAD", "KIS", "STATION", "UNG", 105.0),
    ("LOAD", "KIS", "STATION", "COM", 104.0),
    ("LOAD", "KIS", "STATION", "EDI", 200.0),
    ("LOAD", "KIS", "STATION", "STR", 12.0),
    ("LOAD", "KIS", "STATION", "CHI", 8.0),
    ("STATION", "ORH", "STATION", "BAL", 90.0),
    ("STATION", "BAL", "STATION", "SOR", 75.0),
    ("STATION", "ORH", "END", "BAZA", 46.0),
    ("STATION", "BAL", "END", "BAZA", 135.0),
    ("STATION", "SOR", "END", "BAZA", 184.0),
    ("STATION", "CAH", "END", "BAZA", 180.0),
    ("STATION", "UNG", "END", "BAZA", 105.0),
    ("STATION", "COM", "END", "BAZA", 104.0),
    ("STATION", "EDI", "END", "BAZA", 200.0),
    ("STATION", "STR", "END", "BAZA", 12.0),
    ("STATION", "CHI", "END", "BAZA", 8.0),
    ("LOAD", "CONST", "STATION", "CHI", 450.0),
]


def get_json(res, label):
    if not res.get("success"):
        raise RuntimeError(f"{label}: {res.get('message')}")
    return res["data"]


def by_key(rows, key):
    return {row[key]: row for row in rows}


def get_or_create_stations():
    existing = by_key(get_json(AutoparkStore.list_stations(), "list_stations"), "code")
    for spec in STATIONS:
        if spec["code"] in existing:
            continue
        payload = {
            "code": spec["code"], "name": spec["name"], "address": spec["address"],
            "tanks": [{"product_code": p, "capacity_l": c}
                     for p, c in spec["tanks"].items()],
        }
        res = AutoparkController.station_upsert(payload)
        if not res.get("success"):
            raise RuntimeError(f"АЗС {spec['code']}: {res.get('message')}")
    return by_key(get_json(AutoparkStore.list_stations(), "list_stations"), "code")


def get_or_create_trucks():
    existing = by_key(get_json(AutoparkStore.list_trucks(), "list_trucks"), "plate")
    for spec in TRUCKS:
        if spec["plate"] in existing:
            continue
        res = AutoparkController.truck_upsert({
            "plate": spec["plate"], "brand": spec["brand"],
            "capacity_l": spec["capacity_l"], "sections_cnt": spec["sections_cnt"],
            "norm_l_per_100km": spec["norm_l_per_100km"], "products": spec["products"],
        })
        if not res.get("success"):
            raise RuntimeError(f"Автомобиль {spec['plate']}: {res.get('message')}")
    return by_key(get_json(AutoparkStore.list_trucks(), "list_trucks"), "plate")


def get_or_create_drivers(trucks_by_plate):
    existing = by_key(get_json(AutoparkStore.list_drivers(), "list_drivers"), "tab_no")
    for spec in DRIVERS:
        if spec["tab_no"] in existing:
            continue
        truck_id = trucks_by_plate[spec["truck_plate"]]["id"]
        res = AutoparkController.driver_upsert({
            "full_name": spec["full_name"], "tab_no": spec["tab_no"],
            "truck_id": truck_id,
        })
        if not res.get("success"):
            raise RuntimeError(f"Водитель {spec['tab_no']}: {res.get('message')}")
    return by_key(get_json(AutoparkStore.list_drivers(), "list_drivers"), "tab_no")


def resolve_code_maps():
    load_points = by_key(get_json(AutoparkStore.list_load_points(), "load_points"), "code")
    end_points = by_key(get_json(AutoparkStore.list_end_points(), "end_points"), "code")
    stations = by_key(get_json(AutoparkStore.list_stations(), "stations"), "code")
    return load_points, end_points, stations


def seed_distances(load_points, end_points, stations):
    def resolve(kind, code):
        if kind == "LOAD":
            return load_points[code]["id"]
        if kind == "END":
            return end_points[code]["id"]
        return stations[code]["id"]

    for from_kind, from_code, to_kind, to_code, km in DISTANCES:
        from_id = resolve(from_kind, from_code)
        to_id = resolve(to_kind, to_code)
        res = AutoparkController.distance_set({
            "from_kind": from_kind, "from_id": from_id,
            "to_kind": to_kind, "to_id": to_id, "km": km,
        })
        if not res.get("success"):
            raise RuntimeError(f"Расстояние {from_kind}:{from_code} -> "
                              f"{to_kind}:{to_code}: {res.get('message')}")


# ── Учёт остатков АЗС (10 дней) ─────────────────────────────────────────
# ORH и SOR намеренно уходят ниже страхового запаса (без поступлений за
# 10 дней) -- план поставок не должен оказаться пустым. Остальные АЗС
# держат здоровый запас (регулярные поступления перекрывают реализацию).

STOCK_PROFILES = {
    "ORH": {"A95": {"start": 6000, "daily_sales": 900, "receive_day": None},
            "DIESEL": {"start": 9000, "daily_sales": 1400, "receive_day": None}},
    "SOR": {"A95": {"start": 4000, "daily_sales": 700, "receive_day": None},
            "DIESEL": {"start": 6000, "daily_sales": 1000, "receive_day": None}},
    "BAL": {"A92": {"start": 12000, "daily_sales": 800, "receive_day": 3},
            "A95": {"start": 15000, "daily_sales": 1000, "receive_day": 3},
            "DIESEL": {"start": 20000, "daily_sales": 1500, "receive_day": 3}},
    "CAH": {"A92": {"start": 10000, "daily_sales": 600, "receive_day": 4},
            "DIESEL": {"start": 16000, "daily_sales": 1100, "receive_day": 4}},
    "UNG": {"A95": {"start": 12000, "daily_sales": 750, "receive_day": 5},
            "DIESEL": {"start": 14000, "daily_sales": 950, "receive_day": 5}},
    "COM": {"A92": {"start": 9000, "daily_sales": 550, "receive_day": 6},
            "DIESEL": {"start": 12000, "daily_sales": 850, "receive_day": 6}},
    "EDI": {"A95": {"start": 9500, "daily_sales": 600, "receive_day": 2},
            "DIESEL": {"start": 11000, "daily_sales": 800, "receive_day": 2}},
    "STR": {"A92": {"start": 8500, "daily_sales": 500, "receive_day": 7},
            "A95": {"start": 10500, "daily_sales": 650, "receive_day": 7},
            "DIESEL": {"start": 13500, "daily_sales": 900, "receive_day": 7}},
    "CHI": {"A92": {"start": 15000, "daily_sales": 1200, "receive_day": 3},
            "A95": {"start": 18000, "daily_sales": 1500, "receive_day": 3},
            "A98": {"start": 6000, "daily_sales": 300, "receive_day": None},
            "DIESEL": {"start": 22000, "daily_sales": 1800, "receive_day": 3}},
}


def seed_station_stock(stations):
    rows = []
    for code, products in STOCK_PROFILES.items():
        station_id = stations[code]["id"]
        for product_code, profile in products.items():
            stock = profile["start"]
            for days_ago in range(9, -1, -1):  # oldest -> newest
                stock_date = d(days_ago)
                open_l = stock
                sales = profile["daily_sales"]
                received = 6000 if profile.get("receive_day") == (9 - days_ago) else 0
                close_l = max(0.0, open_l - sales + received)
                rows.append({
                    "station_id": station_id, "product_code": product_code,
                    "stock_date": stock_date, "open_l": open_l, "close_l": close_l,
                    "sales_l": sales, "received_l": received,
                })
                stock = close_l
    res = AutoparkStore.upsert_station_stock(rows)
    if not res.get("success"):
        raise RuntimeError(f"Учёт остатков: {res.get('message')}")
    return len(rows)


# ── Операционка: накладные -> автоформирование -> утверждение -> факт ──

def seed_deliveries(trucks_by_plate, drivers_by_tab, load_points, stations):
    kis = load_points["KIS"]["id"]
    plan = [
        (d(6), "DIESEL", 8000, "C AA 101", "D-001", "ORH"),
        (d(5), "A95", 10000, "C BB 202", "D-002", "BAL"),
        (d(4), "A92", 7000, "C CC 303", "D-003", "CAH"),
    ]
    created_ids = []
    for deliv_date, product_code, volume, plate, tab_no, station_code in plan:
        res = AutoparkController.delivery_add({
            "deliv_date": deliv_date, "product_code": product_code,
            "volume_l": volume, "load_point_id": kis,
            "station_id": stations[station_code]["id"],
            "truck_id": trucks_by_plate[plate]["id"],
            "driver_id": drivers_by_tab[tab_no]["id"],
            "_username": USER,
        })
        if not res.get("success"):
            raise RuntimeError(f"Накладная {station_code}: {res.get('message')}")
        created_ids.append(res["data"]["id"])
    return created_ids


def autoform_and_approve(date_from, date_to):
    res = AutoparkController.trip_autoform(date_from, date_to)
    if not res.get("success"):
        raise RuntimeError(f"Автоформирование рейсов: {res.get('message')}")
    created = res["data"]["trips"]
    skipped = res["data"]["skipped"]
    trip_ids = []
    for trip in created:
        approve = AutoparkController.trip_approve({"trip_id": trip["trip_id"]}, USER)
        if not approve.get("success"):
            raise RuntimeError(f"Утверждение рейса {trip['trip_id']}: "
                              f"{approve.get('message')}")
        trip_ids.append(trip["trip_id"])
    return trip_ids, skipped


def set_fact_for_autoformed(trip_ids, trucks_by_plate):
    """Один рейс с превышением пробега, один с перерасходом ДТ, один чистый."""
    if not trip_ids:
        return []
    trips = get_json(AutoparkController.trip_list({
        "date_from": d(10), "date_to": TODAY}), "trip_list")
    by_id = by_key(trips, "id")
    trucks_by_id = by_key(get_json(AutoparkStore.list_trucks(), "list_trucks"), "id")

    def norm_l_per_100km(trip_id):
        truck_id = by_id[trip_id]["truck_id"]
        return float(trucks_by_id[truck_id]["norm_l_per_100km"])

    notes = []
    # 1) превышение пробега: факт km на 40 больше нормы (лимит 15 км)
    if len(trip_ids) >= 1:
        t = by_id[trip_ids[0]]
        norm_km = float(t["norm_km"])
        fact_km = norm_km + 40
        AutoparkController.trip_set_fact({
            "trip_id": trip_ids[0], "fact_km": fact_km, "fact_minutes": 90,
            "fact_fuel_l": norm_km * norm_l_per_100km(trip_ids[0]) / 100,
        })
        notes.append(f"Рейс #{trip_ids[0]}: НАМЕРЕННОЕ превышение пробега "
                    f"(норм={norm_km}, факт={fact_km}, лимит=15км)")

    # 2) перерасход топлива: факт на 25% больше норматива (лимит 5%)
    if len(trip_ids) >= 2:
        t = by_id[trip_ids[1]]
        norm_km = float(t["norm_km"])
        norm_l = norm_km * norm_l_per_100km(trip_ids[1]) / 100
        fact_fuel = norm_l * 1.25
        AutoparkController.trip_set_fact({
            "trip_id": trip_ids[1], "fact_km": norm_km + 2, "fact_minutes": 150,
            "fact_fuel_l": fact_fuel,
        })
        notes.append(f"Рейс #{trip_ids[1]}: НАМЕРЕННЫЙ перерасход ДТ "
                    f"(норм~={norm_l:.1f}л, факт={fact_fuel:.1f}л, лимит=5%)")

    # 3) рейс без отклонений
    if len(trip_ids) >= 3:
        t = by_id[trip_ids[2]]
        norm_km = float(t["norm_km"])
        norm_l = norm_km * norm_l_per_100km(trip_ids[2]) / 100
        AutoparkController.trip_set_fact({
            "trip_id": trip_ids[2], "fact_km": norm_km + 3, "fact_minutes": 120,
            "fact_fuel_l": norm_l * 1.01,
        })
        notes.append(f"Рейс #{trip_ids[2]}: без отклонений (контрольный)")
    return notes


def create_manual_multi_stop_trip(trucks_by_plate, drivers_by_tab, load_points,
                                  end_points, stations):
    """Один рейс логиста вручную, несколько АЗС: Оргеев -> Бельцы -> Сороки."""
    payload = {
        "trip_date": d(2),
        "truck_id": trucks_by_plate["C CC 303"]["id"],
        "driver_id": drivers_by_tab["D-003"]["id"],
        "load_point_id": load_points["KIS"]["id"],
        "end_point_id": end_points["BAZA"]["id"],
        "stations": [
            {"station_id": stations["ORH"]["id"],
             "items": [{"product_code": "A95", "volume_l": 5000}]},
            {"station_id": stations["BAL"]["id"],
             "items": [{"product_code": "A95", "volume_l": 8000},
                      {"product_code": "DIESEL", "volume_l": 6000}]},
            {"station_id": stations["SOR"]["id"],
             "items": [{"product_code": "DIESEL", "volume_l": 4000}]},
        ],
        "_username": USER,
    }
    res = AutoparkController.trip_create_manual(payload)
    if not res.get("success"):
        raise RuntimeError(f"Ручной многоостановочный рейс: {res.get('message')}")
    trip_id = res["data"]["trip_id"]
    approve = AutoparkController.trip_approve({"trip_id": trip_id}, USER)
    if not approve.get("success"):
        raise RuntimeError(f"Утверждение ручного рейса: {approve.get('message')}")
    return trip_id, res["data"]["norm_km"]


def create_import_trip(trucks_by_plate, drivers_by_tab, load_points, end_points,
                       stations):
    """Импортный рейс Кишинёв-Констанца-Кишинёв -- доплата 600 леев НЕ начисляется."""
    payload = {
        "trip_date": d(1).isoformat(),
        "truck_id": trucks_by_plate["C BB 202"]["id"],
        "driver_id": drivers_by_tab["D-002"]["id"],
        "load_point_id": load_points["CONST"]["id"],
        "end_point_id": end_points["BAZA"]["id"],
        "stations": [
            {"station_id": stations["CHI"]["id"],
             "items": [{"product_code": "A98", "volume_l": 9000}]},
        ],
        "_username": USER,
    }
    res = AutoparkController.trip_create_manual(payload)
    if not res.get("success"):
        raise RuntimeError(f"Импортный рейс: {res.get('message')}")
    trip_id = res["data"]["trip_id"]
    approve = AutoparkController.trip_approve({"trip_id": trip_id}, USER)
    if not approve.get("success"):
        raise RuntimeError(f"Утверждение импортного рейса: {approve.get('message')}")
    return trip_id, res["data"]["norm_km"], payload["stations"][0]


# ── reset -----------------------------------------------------------------

RESET_TABLES_IN_FK_ORDER = (
    "FLT_TRIP_STOP_ITEMS",
    "FLT_TRIP_STOPS",
    "FLT_DELIVERIES",
    "FLT_TRIPS",
    "FLT_STATION_STOCK",
    "FLT_EVENT_LOG",
)


def reset_business_data():
    with DatabaseModel() as db:
        for table in RESET_TABLES_IN_FK_ORDER:
            r = db.execute_query(f"DELETE FROM {table}")
            if not r.get("success"):
                raise RuntimeError(f"Очистка {table}: {r.get('message')}")
        db.connection.commit()
    print("Бизнес-данные очищены (deliveries, trips, stops, items, stock, event log).")


def already_seeded() -> bool:
    with DatabaseModel() as db:
        r = db.execute_query(
            "SELECT COUNT(*) AS CNT FROM FLT_EVENT_LOG WHERE EVENT_TYPE = :t "
            "AND DETAILS = :v", {"t": SEED_MARK_EVENT, "v": SEED_MARK_VALUE})
        if r.get("success") and r.get("data"):
            return r["data"][0][0] > 0
    return False


def mark_seeded():
    AutoparkStore.log_event(SEED_MARK_EVENT, None, None, SEED_MARK_VALUE, USER)


# ── main --------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Autopark demo dataset")
    parser.add_argument("--reset", action="store_true",
                        help="clear business data before seeding "
                             "(deliveries/trips/stock/event log)")
    args = parser.parse_args()

    if args.reset:
        reset_business_data()
    elif already_seeded():
        print("Демо-данные уже засеяны (найдена метка DEMO_SEED в "
              "FLT_EVENT_LOG). Запустите с --reset для пересоздания "
              "бизнес-данных.")
        print_counts()
        return

    print("Мастер-данные: АЗС, автомобили, водители, матрица расстояний ...")
    stations = get_or_create_stations()
    trucks_by_plate = get_or_create_trucks()
    drivers_by_tab = get_or_create_drivers(trucks_by_plate)
    load_points, end_points, stations = resolve_code_maps()
    seed_distances(load_points, end_points, stations)
    print(f"  АЗС: {len(stations)}, автомобили: {len(trucks_by_plate)}, "
          f"водители: {len(drivers_by_tab)}, участков матрицы: {len(DISTANCES)}")

    print("Суточный учёт остатков АЗС за 10 дней ...")
    stock_rows = seed_station_stock(stations)
    print(f"  строк учёта: {stock_rows}")

    print("Накладные ...")
    seed_deliveries(trucks_by_plate, drivers_by_tab, load_points, stations)

    print("Автоформирование рейсов + утверждение ...")
    trip_ids, skipped = autoform_and_approve(d(7), TODAY)
    print(f"  создано и утверждено рейсов: {len(trip_ids)}, "
          f"не сформировано: {len(skipped)}")
    for s in skipped:
        print(f"    пропущено: {s['key']} -- {s['reason']}")

    print("Факт GPS/расхода ДТ по автосформированным рейсам ...")
    notes = set_fact_for_autoformed(trip_ids, trucks_by_plate)
    for n in (notes or []):
        print(f"  {n}")

    print("Ручной многоостановочный рейс логиста (Оргеев-Бельцы-Сороки) ...")
    manual_trip_id, manual_norm_km = create_manual_multi_stop_trip(
        trucks_by_plate, drivers_by_tab, load_points, end_points, stations)
    print(f"  рейс #{manual_trip_id}, норм. пробег {manual_norm_km} км")

    print("Импортный рейс Кишинёв-Констанца-Кишинёв (без доплаты 600 леев) ...")
    import_trip_id, import_norm_km, _ = create_import_trip(
        trucks_by_plate, drivers_by_tab, load_points, end_points, stations)
    print(f"  рейс #{import_trip_id}, норм. пробег {import_norm_km} км")

    mark_seeded()
    print_counts()
    print_payroll_check()


def print_counts():
    with DatabaseModel() as db:
        for table in ("FLT_STATIONS", "FLT_TRUCKS", "FLT_DRIVERS", "FLT_DISTANCES",
                     "FLT_STATION_STOCK", "FLT_DELIVERIES", "FLT_TRIPS",
                     "FLT_TRIP_STOPS", "FLT_TRIP_STOP_ITEMS"):
            r = db.execute_query(f"SELECT COUNT(*) AS CNT FROM {table}")
            cnt = r["data"][0][0] if r.get("success") and r.get("data") else "?"
            print(f"  {table}: {cnt}")


def print_payroll_check():
    date_from = d(15).isoformat()
    date_to = TODAY.isoformat()
    res = AutoparkController.driver_report({"date_from": date_from, "date_to": date_to})
    if not res.get("success"):
        print(f"Свод зарплаты недоступен: {res.get('message')}")
        return
    print("\nСвод зарплаты по водителям (проверка формулы км*2.75 + рейсы*600):")
    trip_res = AutoparkController.payroll_report({"date_from": date_from, "date_to": date_to})
    trips = trip_res.get("data") or []
    for row in res["data"]:
        driver_trips = [t for t in trips if t["driver_id"] == row["driver_id"]]
        expected = 0.0
        for t in driver_trips:
            expected += float(t["norm_km"]) * 2.75
            if t["type_code"] == "DOMESTIC":
                expected += 600.0
        actual = float(row["total_pay"])
        match = "OK" if abs(expected - actual) < 0.01 else "MISMATCH"
        print(f"  {row['full_name']}: внутр={row['domestic_cnt']} "
              f"импорт={row['import_cnt']} норм.км={row['total_norm_km']} "
              f"зарплата={actual:.2f} (ожидалось {expected:.2f}) [{match}]")


if __name__ == "__main__":
    main()
