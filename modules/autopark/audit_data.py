"""Autopark — популяция для аудита: боевая из Oracle и сгенерированная.

Один контракт, два источника. Аудиторский движок (`audit.py`) не знает,
откуда пришли данные, — это и позволяет прогнать его на объёме, которого
в боевой базе пока нет, а потом тем же кодом проверить боевую.

Контракт популяции:

    {"entity": str, "data_label": str,
     "period": {"from": date, "to": date},
     "settings": {...}, "rate_periods": [...], "prices": {"DIESEL": float},
     "stations": [...], "tanks": [...], "trucks": [...], "drivers": [...],
     "trips": [...], "trip_items": [...]}

Про сгенерированный набор — главное, и это повторяется в самом отчёте:
**в него намеренно заложены ошибки**. Аудит, которому нечего находить,
ничего не доказывает: он одинаково молчит и когда всё чисто, и когда
проверка не работает. Поэтому генератор подкладывает известное число
нарушений каждого вида и записывает их в раздел `injected`. Лист
«Самопроверка» в книге сравнивает «подложено» с «найдено» — если аудит
что-то пропустил, это видно на первом же экране, а не в тот день, когда
на боевых данных он промолчит.

Детерминированность: `random.Random(seed)` — Mersenne Twister, одинаков
на любой сборке CPython, поэтому один и тот же seed даёт побайтово ту же
популяцию и тот же акт. Для самой аудиторской выборки random не
используется вовсе (см. `audit.sample_indexes`).
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

# ── Справочные заготовки ────────────────────────────────────────────────

REGIONS = ["Кишинёв", "Бэлць", "Кагул", "Орхей", "Унгень", "Комрат"]
PRODUCTS = ["A95", "A92", "DIESEL", "GPL"]
FUEL_GROUP = {"A95": "PETROL", "A92": "PETROL", "DIESEL": "DIESEL",
              "GPL": "GPL"}
SURNAMES = ["Ciobanu", "Rusu", "Popa", "Lungu", "Cazacu", "Moraru", "Balan",
            "Gutu", "Croitoru", "Sirbu", "Bejan", "Rotaru", "Ursu", "Zaharia",
            "Negru", "Cebotari", "Munteanu", "Postolache", "Grosu", "Damian",
            "Vieru", "Stratan", "Bors", "Chirica"]
NAMES = ["Ion", "Vasile", "Mihai", "Andrei", "Sergiu", "Igor", "Victor",
         "Nicolae", "Dumitru", "Alexandru", "Petru", "Grigore"]
USERS = ["logist1", "logist2", "dispecer1", "dispecer2", "sef.transport",
         "contabil1"]

STATUS_FLOW = ["PLANNED", "LOAD_REQ", "LOADED", "IN_TRANSIT", "DELIVERED",
               "APPROVED"]


def _plate(rnd: random.Random, i: int) -> str:
    return f"{rnd.choice('ABCKMNPT')}{rnd.randint(100, 999)}{rnd.choice('ABCDEFGHJ')}{rnd.choice('ABCDEFGHJ')}"


def demo_population(seed: int = 20260919, *, months: int = 12,
                    stations: int = 24, trucks: int = 14,
                    drivers: int = 22,
                    end: Optional[date] = None) -> Dict[str, Any]:
    """Представительный набор за `months` месяцев с известными дефектами."""
    rnd = random.Random(seed)
    end = end or date(2026, 9, 30)
    start = date(end.year - 1, end.month, 1) if months >= 12 else \
        (end - timedelta(days=30 * months))

    # ── Справочники ─────────────────────────────────────────────────────
    st_list: List[Dict[str, Any]] = []
    tank_list: List[Dict[str, Any]] = []
    tank_id = 1
    for i in range(1, stations + 1):
        region = REGIONS[(i - 1) % len(REGIONS)]
        code = f"{region[:3].upper()}-{i:02d}"
        st_list.append({"id": i, "code": code,
                        "name": f"АЗС {code}", "region": region,
                        "km_from_depot": rnd.randint(8, 210)})
        for product in PRODUCTS[: rnd.choice([3, 3, 4])]:
            capacity = rnd.choice([20000, 25000, 30000, 40000])
            max_fill = round(capacity * 0.95)
            avg = rnd.randint(900, 4200) if product != "GPL" else rnd.randint(300, 900)
            min_stock = round(avg * 2.0)
            # Выше страхового запаса и ниже допустимого налива: иначе
            # «риск сухого бака» появлялся бы сам собой и лист
            # самопроверки не сходился бы с числом подложенных дефектов.
            current = round(rnd.uniform(min_stock * 1.15, max_fill * 0.93))
            tank_list.append({
                "id": tank_id, "station_id": i, "station_code": code,
                "product_code": product, "capacity_l": capacity,
                "max_fill_l": max_fill, "min_stock_l": min_stock,
                "current_l": current, "avg_daily_l": avg})
            tank_id += 1

    truck_list: List[Dict[str, Any]] = []
    sec_id = 1
    for i in range(1, trucks + 1):
        n_sec = rnd.choice([4, 5, 6])
        unit = rnd.choice([4000, 5000, 6000])
        sections = []
        for s in range(1, n_sec + 1):
            vol = unit if s <= n_sec - 1 else rnd.choice([3000, 4000, unit])
            sections.append({"id": sec_id, "seq_no": s, "volume_l": vol})
            sec_id += 1
        truck_list.append({
            "id": i, "plate": _plate(rnd, i),
            "capacity_l": sum(s["volume_l"] for s in sections),
            "norm_l_per_100km": round(rnd.uniform(28.0, 36.0), 1),
            "fuel_groups": rnd.choice([["PETROL", "DIESEL"], ["DIESEL"],
                                       ["PETROL"], ["PETROL", "DIESEL", "GPL"]]),
            "sections": sections})

    driver_list = []
    for i in range(1, drivers + 1):
        driver_list.append({
            "id": i,
            "full_name": f"{rnd.choice(SURNAMES)} {rnd.choice(NAMES)}"})

    settings = {"rate_per_km": 3.50, "trip_bonus": 0.0,
                "km_deviation_limit": 5.0, "fuel_deviation_limit": 5.0,
                "loss_tolerance_l": 50.0, "max_cover_days": 10.0}
    rate_periods = [
        {"id": 1, "valid_from": date(start.year, 1, 1),
         "valid_to": date(2026, 8, 31), "rate_per_km": 2.75,
         "trip_bonus": 600.0},
        {"id": 2, "valid_from": date(2026, 9, 1), "valid_to": None,
         "rate_per_km": 3.50, "trip_bonus": 0.0},
    ]

    # ── План дефектов ───────────────────────────────────────────────────
    # Доли подобраны так, чтобы в отчёте оказались находки всех трёх
    # уровней значимости: аудит, у которого всё «низкий», не показывает,
    # что шкала вообще работает.
    plan = {"payroll": 0.004, "km": 0.045, "fuel": 0.030, "loss": 0.018,
            "sod": 0.022, "status": 0.010, "incomplete": 0.004}
    injected: Dict[str, int] = {k: 0 for k in
                                ["T-01", "T-03", "T-04", "T-05", "T-06",
                                 "T-07", "T-08", "T-09", "T-10", "T-11",
                                 "T-12", "T-13"]}

    # ── Рейсы ───────────────────────────────────────────────────────────
    trips: List[Dict[str, Any]] = []
    items: List[Dict[str, Any]] = []
    trip_id = 0
    item_id = 0
    waybill = 40000
    day = start
    used_waybills: List[str] = []
    while day <= end:
        if day.weekday() == 6:                       # воскресенье — парк стоит
            day += timedelta(days=1)
            continue
        for truck in rnd.sample(truck_list, k=rnd.randint(
                max(1, trucks // 2), trucks)):
            trip_id += 1
            driver = rnd.choice(driver_list)
            type_code = "IMPORT" if rnd.random() < 0.18 else "DOMESTIC"
            norm_km = round(rnd.uniform(120, 480) if type_code == "DOMESTIC"
                            else rnd.uniform(620, 1150), 1)

            rate = 2.75 if day <= date(2026, 8, 31) else 3.50
            bonus = 600.0 if day <= date(2026, 8, 31) else 0.0
            pay = norm_km * rate + (bonus if type_code == "DOMESTIC" else 0.0)

            # Факт пробега: обычно около норматива, иногда — с превышением.
            if rnd.random() < plan["km"]:
                fact_km = round(norm_km * rnd.uniform(1.06, 1.22), 1)
                injected["T-06"] += 1
            else:
                fact_km = round(norm_km * rnd.uniform(0.985, 1.045), 1)

            norm_l = norm_km * truck["norm_l_per_100km"] / 100
            if rnd.random() < plan["fuel"]:
                fact_fuel = round(norm_l * rnd.uniform(1.07, 1.28), 1)
                injected["T-07"] += 1
            else:
                fact_fuel = round(norm_l * rnd.uniform(0.96, 1.04), 1)

            created = rnd.choice(USERS[:4])
            approved = created if rnd.random() < plan["sod"] else \
                rnd.choice([u for u in USERS if u != created])
            if approved == created:
                injected["T-10"] += 1

            waybill += 1
            wb = f"AP-{waybill}"
            if rnd.random() < 0.0007 and used_waybills:
                wb = rnd.choice(used_waybills[-50:])
                injected["T-11"] += 1
            used_waybills.append(wb)

            history = list(STATUS_FLOW)
            if rnd.random() < plan["status"]:
                history = [s for s in STATUS_FLOW if s != "IN_TRANSIT"]
                injected["T-09"] += 1

            stored_pay: Optional[float] = round(pay, 2)
            if rnd.random() < plan["payroll"]:
                stored_pay = round(pay * rnd.uniform(1.03, 1.18), 2)
                injected["T-01"] += 1

            incomplete = rnd.random() < plan["incomplete"]
            if incomplete:
                stored_pay = None
                injected["T-08"] += 1

            trips.append({
                "id": trip_id, "trip_date": day, "driver_id": driver["id"],
                "truck_id": truck["id"], "status_code": "APPROVED",
                "type_code": type_code, "norm_km": norm_km,
                "fact_km": fact_km, "fact_fuel_l": fact_fuel,
                "pay_stored": stored_pay, "source": "AUTO" if rnd.random() < 0.4
                else "MANUAL", "created_by": created, "approved_by": approved,
                "waybill_no": wb, "status_history": history,
                "region": rnd.choice(REGIONS)})

            if incomplete:
                continue

            # ── Позиции груза: отсеки бензовоза целиком ─────────────────
            free = list(truck["sections"])
            rnd.shuffle(free)
            n_items = rnd.randint(2, min(4, len(free)))
            targets = rnd.sample(tank_list, k=n_items)
            for sec, tank in zip(free[:n_items], targets):
                item_id += 1
                planned = float(sec["volume_l"])
                if rnd.random() < 0.0009:
                    planned = round(planned * rnd.uniform(0.55, 0.85))
                    injected["T-03"] += 1
                loaded = planned
                doc_l = planned
                accepted = planned
                if rnd.random() < plan["loss"]:
                    accepted = round(planned - rnd.uniform(60, 420))
                    injected["T-05"] += 1
                else:
                    accepted = round(planned - rnd.uniform(0, 28))
                if rnd.random() < 0.0006:
                    accepted = round(tank["max_fill_l"] + rnd.uniform(400, 2500))
                    loaded = doc_l = accepted
                    injected["T-04"] += 1
                items.append({
                    "id": item_id, "trip_id": trip_id,
                    "station_id": tank["station_id"],
                    "station_code": tank["station_code"],
                    "tank_id": tank["id"],
                    "product_code": tank["product_code"],
                    "section_id": sec["id"], "planned_l": planned,
                    "loaded_l": float(loaded), "doc_l": float(doc_l),
                    "accepted_l": float(accepted),
                    "trip_date": day, "region": next(
                        s["region"] for s in st_list
                        if s["id"] == tank["station_id"])})
        day += timedelta(days=1)

    # ── Дефекты справочников: ровно два, чтобы счёт сходился ────────────
    bad_tank = tank_list[7]
    bad_tank["max_fill_l"] = bad_tank["capacity_l"] + 1500
    injected["T-12"] += 1
    bad_truck = truck_list[3]
    bad_truck["capacity_l"] = bad_truck["capacity_l"] + 2000
    injected["T-12"] += 1

    # ── Риск сухого бака: часть резервуаров ниже страхового запаса ──────
    for tank in rnd.sample(tank_list, k=max(3, len(tank_list) // 12)):
        tank["current_l"] = round(tank["min_stock_l"] * rnd.uniform(0.35, 0.92))
        injected["T-13"] += 1

    return {
        "entity": "BEMOL — сеть АЗС и автопарк бензовозов",
        "data_label": "СГЕНЕРИРОВАННЫЙ НАБОР ДЛЯ ПРОВЕРКИ МЕТОДИКИ",
        "period": {"from": start, "to": end},
        "settings": settings, "rate_periods": rate_periods,
        "prices": {"DIESEL": 23.40, "A95": 25.10, "A92": 24.20, "GPL": 13.80},
        "stations": st_list, "tanks": tank_list, "trucks": truck_list,
        "drivers": driver_list, "trips": trips, "trip_items": items,
        "injected": injected,
        "seed": seed,
    }


# ── Боевая популяция из Oracle ──────────────────────────────────────────

TRIPS_SQL = """
    SELECT t.ID, t.TRIP_DATE, t.DRIVER_ID, t.TRUCK_ID, t.STATUS_CODE,
           t.TYPE_CODE, t.NORM_KM, t.FACT_KM, t.FACT_FUEL_L, t.SOURCE,
           t.APPROVED_BY, p.TOTAL_PAY
      FROM FLT_TRIPS t
      LEFT JOIN V_FLT_TRIP_PAY p ON p.TRIP_ID = t.ID
     WHERE t.TRIP_DATE >= :date_from AND t.TRIP_DATE < :date_to + 1"""

#: Резервуар у позиции груза не хранится: позиция знает АЗС и продукт.
#: Поэтому TANK_ID выводится соединением с FLT_STATION_TANKS по паре
#: (АЗС, продукт) — та же связь, по которой его определяет и планировщик.
ITEMS_SQL = """
    SELECT i.ID, s.TRIP_ID, s.STATION_ID, st.CODE AS STATION_CODE,
           k.ID AS TANK_ID, i.PRODUCT_CODE, i.SECTION_ID, i.VOLUME_L,
           i.LOADED_L, i.DOC_L, i.ACCEPTED_L, t.TRIP_DATE
      FROM FLT_TRIP_STOP_ITEMS i
      JOIN FLT_TRIP_STOPS s ON s.ID = i.STOP_ID
      JOIN FLT_TRIPS t ON t.ID = s.TRIP_ID
      LEFT JOIN FLT_STATIONS st ON st.ID = s.STATION_ID
      LEFT JOIN FLT_STATION_TANKS k ON k.STATION_ID = s.STATION_ID
                                   AND k.PRODUCT_CODE = i.PRODUCT_CODE
     WHERE t.TRIP_DATE >= :date_from AND t.TRIP_DATE < :date_to + 1"""


def live_population(date_from: date, date_to: date) -> Dict[str, Any]:
    """Снимок боевого контура одним подключением к Oracle.

    Одно подключение, а не тринадцать: каждое рукопожатие с облачной ADB
    в Ирландии стоит ~250 мс, и аудит всей популяции иначе превращается в
    минуты ожидания (та же причина, что у `board_store.py`).

    Реквизиты, которых в схеме нет, не подменяются заглушкой: `created_by`
    и журнал статусов остаются пустыми, и соответствующие тесты честно
    отмечаются как «не тестировался». Придумать значение здесь означало бы
    получить контроль, эффективный по построению.
    """
    from models.database import DatabaseModel
    from modules.autopark.store import _rows, _run

    window = {"date_from": date_from, "date_to": date_to}
    with DatabaseModel() as db:
        trips_raw = _rows(_run(db, TRIPS_SQL, window))
        items_raw = _rows(_run(db, ITEMS_SQL, window))
        # Состояние резервуаров берём из представления, а не из таблиц:
        # там уже сведены паспорт (FLT_STATION_TANKS), лимиты периода
        # (FLT_TANK_LIMITS) и последний остаток (FLT_TANK_STOCK). Собирать
        # эту связку второй раз в аудите значило бы завести второе место,
        # где живёт правило «какой лимит действует сегодня».
        tanks_raw = _rows(_run(db,
            "SELECT TANK_ID AS ID, STATION_ID, STATION_CODE, PRODUCT_CODE, "
            "CAPACITY_L, MAX_FILL_L, MIN_STOCK_L, CURRENT_L, AVG_DAILY_L "
            "FROM V_FLT_TANK_STATE"))
        trucks_raw = _rows(_run(db,
            "SELECT ID, PLATE, CAPACITY_L, NORM_L_PER_100KM FROM FLT_TRUCKS"))
        sections_raw = _rows(_run(db,
            "SELECT ID, TRUCK_ID, SEQ_NO, VOLUME_L FROM FLT_TRUCK_SECTIONS"))
        drivers_raw = _rows(_run(db,
            "SELECT ID, FULL_NAME FROM FLT_DRIVERS"))
        stations_raw = _rows(_run(db,
            "SELECT ID, CODE, NAME FROM FLT_STATIONS"))
        rates_raw = _rows(_run(db,
            "SELECT ID, VALID_FROM, VALID_TO, RATE_PER_KM, TRIP_BONUS "
            "FROM FLT_RATE_PERIODS ORDER BY VALID_FROM"))
        settings_raw = _rows(_run(db,
            "SELECT RATE_PER_KM, TRIP_BONUS, KM_DEVIATION_LIMIT, "
            "FUEL_DEVIATION_PCT FROM FLT_SETTINGS WHERE ID = 1"))
        price_raw = _rows(_run(db,
            "SELECT PRODUCT_CODE, PRICE_LEI FROM FLT_FUEL_PRICES f "
            "WHERE PRICE_DATE = (SELECT MAX(PRICE_DATE) FROM FLT_FUEL_PRICES "
            "WHERE PRODUCT_CODE = f.PRODUCT_CODE AND PRICE_DATE <= :date_to)",
            {"date_to": date_to}))

    sec_by_truck: Dict[Any, List[Dict[str, Any]]] = {}
    for s in sections_raw:
        sec_by_truck.setdefault(s["truck_id"], []).append(
            {"id": s["id"], "seq_no": s["seq_no"],
             "volume_l": s["volume_l"]})

    st = (settings_raw or [{}])[0]
    settings = {"rate_per_km": st.get("rate_per_km"),
                "trip_bonus": st.get("trip_bonus"),
                "km_deviation_limit": st.get("km_deviation_limit") or 5.0,
                "fuel_deviation_limit": st.get("fuel_deviation_pct") or 5.0,
                "loss_tolerance_l": 50.0}

    station_name = {s["id"]: s.get("code") for s in stations_raw}
    return {
        "entity": "BEMOL — сеть АЗС и автопарк бензовозов",
        "data_label": "БОЕВЫЕ ДАННЫЕ КОНТУРА",
        "period": {"from": date_from, "to": date_to},
        "settings": settings,
        "rate_periods": [dict(r) for r in rates_raw],
        "prices": {r["product_code"]: r["price_lei"] for r in price_raw},
        "stations": [{"id": s["id"], "code": s.get("code"),
                      "name": s.get("name"), "region": "—"}
                     for s in stations_raw],
        "tanks": [dict(t) for t in tanks_raw],
        "trucks": [{"id": t["id"], "plate": t.get("plate"),
                    "capacity_l": t.get("capacity_l"),
                    "norm_l_per_100km": t.get("norm_l_per_100km"),
                    "sections": sec_by_truck.get(t["id"], [])}
                   for t in trucks_raw],
        "drivers": [dict(d) for d in drivers_raw],
        "trips": [{"id": t["id"], "trip_date": t["trip_date"],
                   "driver_id": t["driver_id"], "truck_id": t["truck_id"],
                   "status_code": t["status_code"],
                   "type_code": t["type_code"], "norm_km": t["norm_km"],
                   "fact_km": t["fact_km"], "fact_fuel_l": t["fact_fuel_l"],
                   "pay_stored": t.get("total_pay"), "source": t.get("source"),
                   "created_by": None, "approved_by": t.get("approved_by"),
                   "waybill_no": None, "status_history": [],
                   "region": "—"} for t in trips_raw],
        "trip_items": [{"id": i["id"], "trip_id": i["trip_id"],
                        "station_id": i.get("station_id"),
                        "station_code": i.get("station_code")
                        or station_name.get(i.get("station_id")),
                        "tank_id": i.get("tank_id"),
                        "product_code": i.get("product_code"),
                        "section_id": i.get("section_id"),
                        "planned_l": i.get("volume_l"),
                        "loaded_l": i.get("loaded_l"),
                        "doc_l": i.get("doc_l"),
                        "accepted_l": i.get("accepted_l"),
                        "trip_date": i.get("trip_date"),
                        "region": "—"} for i in items_raw],
        "injected": {},
    }
