#!/usr/bin/env python3
"""PECO: демо-датасет для презентации сети из 46 АЗС.

Мастер-данные (станции, резервуары, колонки, пистолеты, сотрудники, цены)
создаются прямым SQL по образцу sql/105_peco_demo_station.sql — для этих
таблиц в PecoStore нет операций создания, только чтение/обновление.

Операционная история (смены, транзакции, приход цистерн) НЕ вставляется
сырым SQL — она проводится через реальную бизнес-логику модулей:
    models.peco_shift  (open_shift, close_shift, PIN)
    models.peco_txn    (authorize, start_dispense, finish_dispense, settle, void)
    models.peco_inventory (receive_delivery)
Это гарантирует, что сверка (liter/cash/tank variance) считается тем же
кодом, что и в проде, а не подгоняется руками.

Запуск:
    ./venv/bin/python scripts/peco_seed_demo.py            # засеять
    ./venv/bin/python scripts/peco_seed_demo.py --reset    # очистить бизнес-данные PECO_* и выйти
    ./venv/bin/python scripts/peco_seed_demo.py --reset --seed  # очистить и сразу засеять заново

Идемпотентность:
  - мастер-данные: станция уже существует (по CODE) -> вся её ветка
    (резервуары/колонки/пистолеты/сотрудники/цены) пропускается целиком.
  - операционные сценарии: если у станции уже есть хоть одна смена
    (PECO_SHIFTS), сценарий для неё пропускается целиком.
"""
from __future__ import annotations

import argparse
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, ".")

from models.database import DatabaseModel
from models import peco_shift, peco_txn, peco_inventory
from models.peco_oracle_store import PecoStore

random.seed(42)

DEMO_MANAGER_PIN = "1926"

GRADES = ["A92", "A95", "A98", "DIESEL"]
BASE_PRICES = {"A92": 22.50, "A95": 23.90, "A98": 26.40, "DIESEL": 21.80}

# Бизнес-таблицы PECO в порядке удаления при --reset (дети раньше родителей).
# PECO_REF_* сюда намеренно не входят.
RESET_ORDER = [
    "PECO_TXN",
    "PECO_SHIFT_METERS",
    "PECO_SHIFT_TANKS",
    "PECO_SHIFTS",
    "PECO_DELIVERY_ITEMS",
    "PECO_DELIVERIES",
    "PECO_TANK_DIPS",
    "PECO_EVENT_LOG",
    "PECO_PRICES",
    "PECO_NOZZLES",
    "PECO_PUMPS",
    "PECO_TANKS",
    "PECO_EMPLOYEES",
    "PECO_STATIONS",
]

ALL_TABLES = RESET_ORDER  # тот же список для отчёта по количеству строк


# ------------------------------------------------------------------
# низкоуровневые помощники (эквивалент PecoStore._run, но локально —
# скрипт не должен зависеть от приватного имени другого модуля)
# ------------------------------------------------------------------

def run(db, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    r = db.execute_query(sql, params) if params else db.execute_query(sql)
    if not r.get("success"):
        raise RuntimeError(f"SQL failed: {r.get('message')}\nSQL: {sql}\nparams: {params}")
    return r


def fetch_all(db, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    r = run(db, sql, params)
    cols = [c.lower() for c in (r.get("columns") or [])]
    return [dict(zip(cols, row)) for row in (r.get("data") or [])]


def currval(db, seq: str) -> int:
    rows = fetch_all(db, f"SELECT {seq}.CURRVAL AS ID FROM dual")
    return int(rows[0]["id"])


def die(step: str, result: Dict[str, Any]):
    print(f"\nFATAL at {step}: {result}")
    sys.exit(1)


# ------------------------------------------------------------------
# --reset
# ------------------------------------------------------------------

def do_reset():
    print("Очистка бизнес-данных PECO_* (PECO_REF_* не трогается)...")
    with DatabaseModel() as db:
        for t in RESET_ORDER:
            r = run(db, f"DELETE FROM {t}")
            print(f"  DELETE FROM {t}: {r.get('rowcount', 0)} строк")
        db.connection.commit()
    print("Готово.")


# ------------------------------------------------------------------
# мастер-данные: 46 станций
# ------------------------------------------------------------------

# (город/регион, число станций, пул улиц)
CITY_PLAN: List[Tuple[str, int, List[str]]] = [
    ("Кишинёв", 10, [
        "бул. Штефан чел Маре", "ул. Албишоара", "Каля Мошилор",
        "ул. Хынчешть", "бул. Дачия", "ул. Мирча чел Бэтрын",
        "Каля Орхеюлуй", "ул. Индустриальная", "ул. Алба Юлия",
        "бул. Негруцци",
    ]),
    ("Бэлць", 5, ["ул. Индепенденцей", "ул. Штефан чел Маре", "ул. Дечебал",
                  "ул. Богдан Воде", "ул. Николае Йорга"]),
    ("Кагул", 3, ["ул. Штефан чел Маре", "ул. Индепенденцей", "ул. Академика"]),
    ("Орхей", 3, ["ул. Василе Лупу", "ул. Виорэ Косе", "ул. Митрополит Варлаам"]),
    ("Унгень", 3, ["ул. Национала", "ул. Александру чел Бун", "ул. Фрумоаса"]),
    ("Сорока", 3, ["ул. Индепенденцей", "ул. Дечебал", "ул. Каля Бэлций"]),
    ("Комрат", 3, ["ул. Ленина", "ул. Пушкина", "ул. Победы"]),
    ("Единец", 2, ["ул. Индепенденцей", "ул. 1 Мая"]),
    ("Хынчешть", 2, ["ул. Михалча Спэтарул", "ул. Ренаштерий"]),
    ("Кэушень", 2, ["ул. Штефан чел Маре", "ул. Ткаченко"]),
    ("Стрэшень", 2, ["ул. Мирча чел Бэтрын", "ул. Индепенденцей"]),
    ("Яловень", 2, ["ул. Алексей Матеевич", "ул. Каля Кишинэулуй"]),
    ("Анений Ной", 2, ["ул. Ленина", "ул. Данила Кьошия"]),
    ("Фэлешть", 2, ["ул. Штефан чел Маре", "ул. Труенешть"]),
    ("Нispорень", 2, ["ул. Александру чел Бун", "ул. Михай Эминеску"]),
]
# опечатка "Нispорень" исправляется явно ниже
CITY_PLAN[-1] = ("Ниспорень", 2, ["ул. Александру чел Бун", "ул. Михай Эминеску"])


def build_station_plan() -> List[Dict[str, str]]:
    stations = []
    n = 0
    for city, count, streets in CITY_PLAN:
        for i in range(count):
            n += 1
            code = f"AZS-{n:03d}"
            street = streets[i % len(streets)]
            house = 3 + i * 7
            suffix = f" №{i + 1}" if count > 1 else ""
            name = f"АЗС{suffix} {city}"
            address = f"{street}, {house}"
            stations.append({
                "code": code, "name": name, "address": address, "region": city,
            })
    return stations


def seed_master_data() -> Dict[str, Any]:
    plan = build_station_plan()
    assert len(plan) == 46, f"expected 46 stations, got {len(plan)}"

    created_stations = 0
    skipped_stations = 0
    created_tanks = created_pumps = created_nozzles = created_emps = created_prices = 0
    managers_with_pin: List[Tuple[str, str]] = []  # (station_code, full_name)
    low_alarm_tanks: List[str] = []
    station_ids: Dict[str, int] = {}

    for st in plan:
        with DatabaseModel() as db:
            existing = fetch_all(db, "SELECT ID FROM PECO_STATIONS WHERE CODE = :c",
                                  {"c": st["code"]})
            if existing:
                station_ids[st["code"]] = int(existing[0]["id"])
                skipped_stations += 1
                continue

            run(db, """INSERT INTO PECO_STATIONS (ID, CODE, NAME, ADDRESS, REGION)
                       VALUES (PECO_STATIONS_SEQ.NEXTVAL, :code, :name, :address, :region)""",
                {"code": st["code"], "name": st["name"],
                 "address": st["address"], "region": st["region"]})
            station_id = currval(db, "PECO_STATIONS_SEQ")
            station_ids[st["code"]] = station_id

            # ---- резервуары: один на вид топлива ----
            tank_ids: Dict[str, int] = {}
            # каждая станция даёт шанс ~1 резервуару оказаться у сигнальной отметки —
            # иначе список тревог на демо пуст, а это скучно и неубедительно
            near_alarm_grade = random.choice(GRADES) if random.random() < 0.35 else None
            for grade in GRADES:
                capacity = round(random.randint(20000, 30000) / 500) * 500
                min_alarm = round(capacity * 0.15)
                if grade == near_alarm_grade:
                    current = round(min_alarm * random.uniform(0.75, 1.08))
                    low_alarm_tanks.append(f"{st['code']}/{grade}")
                else:
                    current = round(capacity * random.uniform(0.35, 0.85))
                run(db, """INSERT INTO PECO_TANKS
                                  (ID, STATION_ID, GRADE_CODE, CODE, CAPACITY_L,
                                   CURRENT_L, MIN_ALARM_L)
                           VALUES (PECO_TANKS_SEQ.NEXTVAL, :sid, :grade, :code,
                                   :cap, :cur, :alarm)""",
                    {"sid": station_id, "grade": grade, "code": f"T-{grade}",
                     "cap": capacity, "cur": current, "alarm": min_alarm})
                tank_ids[grade] = currval(db, "PECO_TANKS_SEQ")
                created_tanks += 1

            # ---- колонки ----
            pump_count = random.choice([2, 2, 3])
            pump_ids: List[int] = []
            for p in range(pump_count):
                self_service = 1 if p % 2 == 0 else 0
                run(db, """INSERT INTO PECO_PUMPS (ID, STATION_ID, CODE, SELF_SERVICE)
                           VALUES (PECO_PUMPS_SEQ.NEXTVAL, :sid, :code, :ss)""",
                    {"sid": station_id, "code": f"P-{p + 1}", "ss": self_service})
                pump_ids.append(currval(db, "PECO_PUMPS_SEQ"))
                created_pumps += 1

            # ---- пистолеты: каждый вид топлива закреплён за одной колонкой ----
            for gi, grade in enumerate(GRADES):
                pump_id = pump_ids[gi % pump_count]
                run(db, """INSERT INTO PECO_NOZZLES
                                  (ID, STATION_ID, PUMP_ID, TANK_ID, GRADE_CODE, CODE)
                           VALUES (PECO_NOZZLES_SEQ.NEXTVAL, :sid, :pid, :tid,
                                   :grade, :code)""",
                    {"sid": station_id, "pid": pump_id, "tid": tank_ids[grade],
                     "grade": grade, "code": f"N-{grade}"})
                created_nozzles += 1

            # ---- сотрудники: 1 менеджер (с рабочим PIN) + 1-3 оператора ----
            emp_count = random.randint(2, 4)
            salt = peco_shift.new_salt()
            pin_hash = peco_shift.hash_pin(DEMO_MANAGER_PIN, salt)
            manager_name = f"Менеджер {st['region']} {st['code'][-3:]}"
            run(db, """INSERT INTO PECO_EMPLOYEES
                              (ID, STATION_ID, FULL_NAME, ROLE_CODE, PIN_SALT, PIN_HASH)
                       VALUES (PECO_EMPLOYEES_SEQ.NEXTVAL, :sid, :name, 'MANAGER',
                               :salt, :hash)""",
                {"sid": station_id, "name": manager_name, "salt": salt, "hash": pin_hash})
            created_emps += 1
            managers_with_pin.append((st["code"], manager_name))

            for a in range(emp_count - 1):
                run(db, """INSERT INTO PECO_EMPLOYEES
                                  (ID, STATION_ID, FULL_NAME, ROLE_CODE, PIN_SALT, PIN_HASH)
                           VALUES (PECO_EMPLOYEES_SEQ.NEXTVAL, :sid, :name, 'ATTENDANT',
                                   'NO_SALT_SET', 'NO_PIN_SET')""",
                    {"sid": station_id, "name": f"Оператор {st['code']}-{a + 1}"})
                created_emps += 1

            # ---- цены: базовая цена вида топлива +- региональный разброс ----
            for grade, base in BASE_PRICES.items():
                price = round(base * random.uniform(0.97, 1.04), 2)
                run(db, """INSERT INTO PECO_PRICES (ID, STATION_ID, GRADE_CODE, PRICE)
                           VALUES (PECO_PRICES_SEQ.NEXTVAL, :sid, :grade, :price)""",
                    {"sid": station_id, "grade": grade, "price": price})
                created_prices += 1

            db.connection.commit()
            created_stations += 1

    return {
        "plan": plan,
        "station_ids": station_ids,
        "created_stations": created_stations,
        "skipped_stations": skipped_stations,
        "created_tanks": created_tanks,
        "created_pumps": created_pumps,
        "created_nozzles": created_nozzles,
        "created_emps": created_emps,
        "created_prices": created_prices,
        "managers_with_pin": managers_with_pin,
        "low_alarm_tanks": low_alarm_tanks,
    }


# ------------------------------------------------------------------
# операционные сценарии — только через models.peco_shift/peco_txn/peco_inventory
# ------------------------------------------------------------------

def station_has_shifts(station_id: int) -> bool:
    with DatabaseModel() as db:
        rows = fetch_all(db, "SELECT COUNT(*) AS C FROM PECO_SHIFTS WHERE STATION_ID = :s",
                          {"s": station_id})
        return int(rows[0]["c"]) > 0


def get_employees(station_id: int) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    r = PecoStore.list_employees(station_id)
    if not r.get("success"):
        die("list_employees", r)
    items = r["items"]
    manager = next(e for e in items if e["role_code"] == "MANAGER")
    attendants = [e for e in items if e["role_code"] == "ATTENDANT"]
    return manager, attendants


def get_nozzles(station_id: int) -> List[Dict[str, Any]]:
    r = PecoStore.list_nozzles(station_id)
    if not r.get("success"):
        die("list_nozzles", r)
    return r["items"]


def get_tank_current(station_id: int) -> Dict[int, float]:
    """Текущий физический остаток резервуаров станции — {tank_id: litres}."""
    r = PecoStore.list_tank_levels(station_id)
    if not r.get("success"):
        die("list_tank_levels", r)
    return {int(t["tank_id"]): float(t["current_l"]) for t in r["items"]}


def dispense(shift_id: int, station_id: int, nozzle: Dict[str, Any],
             meter_state: Dict[int, float], liters: float, employee_id: int,
             is_self_service: bool, pay_method: str = "CASH",
             mia_ref: Optional[str] = None, settle_it: bool = True) -> Dict[str, Any]:
    """Полный цикл AUTHORIZED->...->PAID (или без settle, если settle_it=False)."""
    nid = int(nozzle["id"])
    meter_start = meter_state[nid]
    auth = peco_txn.authorize(
        shift_id, nid, nozzle["grade_code"], station_id, meter_start,
        is_self_service,
        employee_id=None if is_self_service else employee_id,
        mia_ref=mia_ref if is_self_service else None,
    )
    if not auth.get("success"):
        die("peco_txn.authorize", auth)
    txn_id = auth["txn_id"]

    started = peco_txn.start_dispense(txn_id)
    if not started.get("success"):
        die("peco_txn.start_dispense", started)

    meter_end = round(meter_start + liters, 3)
    fin = peco_txn.finish_dispense(txn_id, meter_end)
    if not fin.get("success"):
        die("peco_txn.finish_dispense", fin)
    meter_state[nid] = meter_end

    if not is_self_service and settle_it:
        settled = peco_txn.settle(txn_id, pay_method,
                                   mia_ref=mia_ref if pay_method == "MIA_QR" else None)
        if not settled.get("success"):
            die("peco_txn.settle", settled)

    return {"txn_id": txn_id, "status": fin["status"], "liters": fin["liters"],
            "amount": fin["amount"]}


def init_meter_state(nozzles: List[Dict[str, Any]]) -> Dict[int, float]:
    return {int(n["id"]): float(n["meter_total"]) for n in nozzles}


def close_clean(shift_id: int, station_id: int, employee_id: int,
                 nozzles: List[Dict[str, Any]], meter_state: Dict[int, float],
                 expected_cash: float) -> Dict[str, Any]:
    for n in nozzles:
        r = PecoStore.save_meter_close(shift_id, int(n["id"]), meter_state[int(n["id"])])
        if not r.get("success"):
            die("save_meter_close", r)
    dips = get_tank_current(station_id)  # физический замер = точный книжный остаток
    closed = peco_shift.close_shift(shift_id, employee_id, expected_cash, dips=dips)
    if not closed.get("success"):
        die("peco_shift.close_shift", closed)
    return closed


def scenario_clean(station_code: str, station_ids: Dict[str, int], label: str) -> Optional[Dict[str, Any]]:
    station_id = station_ids[station_code]
    if station_has_shifts(station_id):
        print(f"  [{label}] {station_code}: смены уже есть, пропуск")
        return None

    manager, attendants = get_employees(station_id)
    attendant = attendants[0] if attendants else manager
    nozzles = get_nozzles(station_id)

    opened = peco_shift.open_shift(station_id, attendant["id"])
    if not opened.get("success"):
        die("peco_shift.open_shift", opened)
    shift_id = opened["shift_id"]
    meter_state = init_meter_state(nozzles)

    cash_total = 0.0
    mia_total = 0.0
    for n in nozzles:
        is_self = bool(n["self_service"])
        liters = round(random.uniform(18, 45), 2)
        if is_self:
            res = dispense(shift_id, station_id, n, meter_state, liters,
                            employee_id=attendant["id"], is_self_service=True,
                            mia_ref=f"MIA-{station_code}-{n['code']}-{random.randint(100000,999999)}")
            mia_total += res["amount"]
        else:
            pay = "CASH" if random.random() < 0.6 else "MIA_QR"
            res = dispense(shift_id, station_id, n, meter_state, liters,
                            employee_id=attendant["id"], is_self_service=False,
                            pay_method=pay,
                            mia_ref=(f"MIA-{station_code}-{n['code']}-{random.randint(100000,999999)}"
                                     if pay == "MIA_QR" else None))
            if pay == "CASH":
                cash_total += res["amount"]
            else:
                mia_total += res["amount"]
        # второй заезд на части пистолетов, для разнообразия картины
        if random.random() < 0.5:
            liters2 = round(random.uniform(10, 30), 2)
            if is_self:
                res2 = dispense(shift_id, station_id, n, meter_state, liters2,
                                 employee_id=attendant["id"], is_self_service=True,
                                 mia_ref=f"MIA-{station_code}-{n['code']}-{random.randint(100000,999999)}")
                mia_total += res2["amount"]
            else:
                pay2 = "CASH" if random.random() < 0.6 else "MIA_QR"
                res2 = dispense(shift_id, station_id, n, meter_state, liters2,
                                 employee_id=attendant["id"], is_self_service=False,
                                 pay_method=pay2,
                                 mia_ref=(f"MIA-{station_code}-{n['code']}-{random.randint(100000,999999)}"
                                          if pay2 == "MIA_QR" else None))
                if pay2 == "CASH":
                    cash_total += res2["amount"]
                else:
                    mia_total += res2["amount"]

    closed = close_clean(shift_id, station_id, attendant["id"], nozzles, meter_state,
                          expected_cash=round(cash_total, 2))
    print(f"  [{label}] {station_code}: смена {shift_id} -> {closed['status']} "
          f"variances={closed['variances']}")
    return {"shift_id": shift_id, "station_code": station_code, "label": label,
            "result": closed}


def scenario_disputed(station_code: str, station_ids: Dict[str, int]) -> Optional[Dict[str, Any]]:
    station_id = station_ids[station_code]
    if station_has_shifts(station_id):
        print(f"  [disputed] {station_code}: смены уже есть, пропуск")
        return None

    manager, attendants = get_employees(station_id)
    attendant = attendants[0] if attendants else manager
    nozzles = get_nozzles(station_id)

    opened = peco_shift.open_shift(station_id, attendant["id"])
    if not opened.get("success"):
        die("peco_shift.open_shift (disputed)", opened)
    shift_id = opened["shift_id"]
    meter_state = init_meter_state(nozzles)

    cash_total = 0.0
    # обычные, честно оплаченные продажи на всех пистолетах кроме одного
    driveoff_nozzle = next(n for n in nozzles if not n["self_service"])
    for n in nozzles:
        liters = round(random.uniform(20, 40), 2)
        is_self = bool(n["self_service"])
        if is_self:
            dispense(shift_id, station_id, n, meter_state, liters,
                     employee_id=attendant["id"], is_self_service=True,
                     mia_ref=f"MIA-{station_code}-{n['code']}-{random.randint(100000,999999)}")
        else:
            res = dispense(shift_id, station_id, n, meter_state, liters,
                            employee_id=attendant["id"], is_self_service=False,
                            pay_method="CASH")
            cash_total += res["amount"]

    # "слив без оплаты": налив состоялся (счётчик и резервуар сдвинулись),
    # но транзакция аннулируется вместо оплаты -> в кассе и в PAID-литрах
    # этого отпуска нет, а в показаниях счётчика он есть. Это и есть
    # liter_variance, не сводимый в ноль.
    drive_liters = 12.7
    meter_start = meter_state[int(driveoff_nozzle["id"])]
    auth = peco_txn.authorize(shift_id, int(driveoff_nozzle["id"]), driveoff_nozzle["grade_code"],
                               station_id, meter_start, False, employee_id=attendant["id"])
    if not auth.get("success"):
        die("authorize (drive-off)", auth)
    txn_id = auth["txn_id"]
    st = peco_txn.start_dispense(txn_id)
    if not st.get("success"):
        die("start_dispense (drive-off)", st)
    meter_end = round(meter_start + drive_liters, 3)
    fin = peco_txn.finish_dispense(txn_id, meter_end)
    if not fin.get("success"):
        die("finish_dispense (drive-off)", fin)
    meter_state[int(driveoff_nozzle["id"])] = meter_end
    voided = peco_txn.void(txn_id, reason="Клиент уехал без оплаты (демо-инцидент)")
    if not voided.get("success"):
        die("void (drive-off)", voided)

    for n in nozzles:
        r = PecoStore.save_meter_close(shift_id, int(n["id"]), meter_state[int(n["id"])])
        if not r.get("success"):
            die("save_meter_close (disputed)", r)

    # физические замеры на закрытие: для одного резервуара занижаем дип,
    # имитируя утечку сверх допуска TOLERANCE_TANK_LITERS (50 л)
    dips = get_tank_current(station_id)
    leak_tank_id = int(driveoff_nozzle["tank_id"])
    dips[leak_tank_id] = round(dips[leak_tank_id] - 85.0, 3)

    closed = peco_shift.close_shift(shift_id, attendant["id"], round(cash_total, 2), dips=dips)
    if not closed.get("success"):
        die("peco_shift.close_shift (disputed)", closed)
    print(f"  [disputed] {station_code}: смена {shift_id} -> {closed['status']} "
          f"variances={closed['variances']}")
    return {"shift_id": shift_id, "station_code": station_code, "label": "disputed",
            "result": closed, "leak_tank_id": leak_tank_id}


def scenario_delivery(station_code: str, station_ids: Dict[str, int]) -> Optional[Dict[str, Any]]:
    station_id = station_ids[station_code]
    if station_has_shifts(station_id):
        print(f"  [delivery] {station_code}: смены уже есть, пропуск")
        return None

    manager, attendants = get_employees(station_id)
    attendant = attendants[0] if attendants else manager
    nozzles = get_nozzles(station_id)

    opened = peco_shift.open_shift(station_id, attendant["id"])
    if not opened.get("success"):
        die("peco_shift.open_shift (delivery)", opened)
    shift_id = opened["shift_id"]
    meter_state = init_meter_state(nozzles)

    cash_total = 0.0
    # продажи до прихода цистерны
    for n in nozzles:
        liters = round(random.uniform(15, 30), 2)
        is_self = bool(n["self_service"])
        if is_self:
            dispense(shift_id, station_id, n, meter_state, liters,
                     employee_id=attendant["id"], is_self_service=True,
                     mia_ref=f"MIA-{station_code}-{n['code']}-{random.randint(100000,999999)}")
        else:
            res = dispense(shift_id, station_id, n, meter_state, liters,
                            employee_id=attendant["id"], is_self_service=False,
                            pay_method="CASH")
            cash_total += res["amount"]

    # приход цистерны: несколько резервуаров, одна строка -- недолив
    r = PecoStore.get_shift_tanks(shift_id)
    if not r.get("success"):
        die("get_shift_tanks (delivery)", r)
    tank_rows = {row["grade_code"]: row for row in r["items"]}

    items = []
    for grade in ["A92", "A95", "DIESEL"]:
        tank_id = int(tank_rows[grade]["tank_id"])
        doc = 5000.0
        recv = doc if grade != "DIESEL" else doc - 120.0  # недолив по дизелю
        items.append({"tank_id": tank_id, "grade_code": grade,
                       "liters_doc": doc, "liters_recv": recv})

    delivered = peco_inventory.receive_delivery(
        station_id, supplier="Petrom Moldova SRL",
        waybill_no=f"WB-{station_code}-{random.randint(10000,99999)}",
        items=items, employee_id=attendant["id"],
        driver_name="Ион Кантемир", vehicle_no="C AA 123",
    )
    if not delivered.get("success"):
        die("peco_inventory.receive_delivery", delivered)
    print(f"  [delivery] {station_code}: приход {delivered['delivery_id']}, "
          f"недолив={delivered['total_shortfall']} л, детали={delivered['shortfalls']}")

    # продажи после прихода
    for n in nozzles:
        liters = round(random.uniform(10, 25), 2)
        is_self = bool(n["self_service"])
        if is_self:
            dispense(shift_id, station_id, n, meter_state, liters,
                     employee_id=attendant["id"], is_self_service=True,
                     mia_ref=f"MIA-{station_code}-{n['code']}-{random.randint(100000,999999)}")
        else:
            res = dispense(shift_id, station_id, n, meter_state, liters,
                            employee_id=attendant["id"], is_self_service=False,
                            pay_method="MIA_QR",
                            mia_ref=f"MIA-{station_code}-{n['code']}-{random.randint(100000,999999)}")

    closed = close_clean(shift_id, station_id, attendant["id"], nozzles, meter_state,
                          expected_cash=round(cash_total, 2))
    print(f"  [delivery] {station_code}: смена {shift_id} -> {closed['status']} "
          f"variances={closed['variances']}")
    return {"shift_id": shift_id, "station_code": station_code, "label": "delivery",
            "result": closed, "delivery_id": delivered["delivery_id"],
            "shortfalls": delivered["shortfalls"]}


def scenario_open(station_code: str, station_ids: Dict[str, int]) -> Optional[Dict[str, Any]]:
    station_id = station_ids[station_code]
    if station_has_shifts(station_id):
        print(f"  [open] {station_code}: смены уже есть, пропуск")
        return None

    manager, attendants = get_employees(station_id)
    attendant = attendants[0] if attendants else manager
    nozzles = get_nozzles(station_id)

    opened = peco_shift.open_shift(station_id, attendant["id"])
    if not opened.get("success"):
        die("peco_shift.open_shift (open)", opened)
    shift_id = opened["shift_id"]
    meter_state = init_meter_state(nozzles)

    # немного "живой" активности: пара честных продаж и одна авторизация,
    # которая сейчас как раз "у колонки" -- топливо ещё льётся
    for n in nozzles[:2]:
        liters = round(random.uniform(15, 25), 2)
        is_self = bool(n["self_service"])
        if is_self:
            dispense(shift_id, station_id, n, meter_state, liters,
                     employee_id=attendant["id"], is_self_service=True,
                     mia_ref=f"MIA-{station_code}-{n['code']}-{random.randint(100000,999999)}")
        else:
            dispense(shift_id, station_id, n, meter_state, liters,
                     employee_id=attendant["id"], is_self_service=False, pay_method="CASH")

    live_nozzle = nozzles[-1]
    meter_start = meter_state[int(live_nozzle["id"])]
    auth = peco_txn.authorize(shift_id, int(live_nozzle["id"]), live_nozzle["grade_code"],
                               station_id, meter_start, bool(live_nozzle["self_service"]),
                               employee_id=None if live_nozzle["self_service"] else attendant["id"],
                               mia_ref=(f"MIA-{station_code}-live-{random.randint(100000,999999)}"
                                        if live_nozzle["self_service"] else None))
    if not auth.get("success"):
        die("authorize (open/live)", auth)
    started = peco_txn.start_dispense(auth["txn_id"])
    if not started.get("success"):
        die("start_dispense (open/live)", started)
    # намеренно НЕ finish_dispense -- топливо "ещё льётся" на момент демо

    print(f"  [open] {station_code}: смена {shift_id} оставлена OPEN "
          f"(txn {auth['txn_id']} сейчас DISPENSING)")
    return {"shift_id": shift_id, "station_code": station_code, "label": "open"}


# ------------------------------------------------------------------
# верификация
# ------------------------------------------------------------------

def verify_and_report(scenario_results: List[Dict[str, Any]]):
    print("\n" + "=" * 70)
    print("Итоговая сверка")
    print("=" * 70)

    with DatabaseModel() as db:
        print("\nКоличество строк по таблицам PECO_*:")
        for t in ALL_TABLES:
            rows = fetch_all(db, f"SELECT COUNT(*) AS C FROM {t}")
            print(f"  {t:<24} {rows[0]['c']}")

        print("\nЗакрытые/спорные смены (V_PECO_VARIANCE):")
        rows = fetch_all(db, """SELECT SHIFT_ID, STATION_NAME, STATUS_CODE,
                                        LITER_VARIANCE, CASH_VARIANCE, TANK_VARIANCE
                                   FROM V_PECO_VARIANCE ORDER BY SHIFT_ID""")
        for r in rows:
            print(f"  shift={r['shift_id']:>4}  {r['station_name']:<28} "
                  f"status={r['status_code']:<10} "
                  f"liter_var={r['liter_variance']}  "
                  f"cash_var={r['cash_variance']}  "
                  f"tank_var={r['tank_variance']}")

        print("\nОткрытые смены:")
        open_rows = fetch_all(db, """SELECT sh.ID, st.NAME, sh.STATUS_CODE
                                        FROM PECO_SHIFTS sh JOIN PECO_STATIONS st
                                          ON st.ID = sh.STATION_ID
                                       WHERE sh.STATUS_CODE = 'OPEN'""")
        for r in open_rows:
            print(f"  shift={r['id']:>4}  {r['name']}")

    clean = [s for s in scenario_results if s and s["label"] in ("clean", "delivery")]
    disputed = [s for s in scenario_results if s and s["label"] == "disputed"]

    ok = True
    for s in clean:
        v = s["result"]["variances"]
        is_zero = (abs(v["liter_variance"]) < 1e-6 and abs(v["cash_variance"]) < 1e-6
                   and (v["tank_variance"] is None or abs(v["tank_variance"]) < 1e-6))
        status_ok = s["result"]["status"] == "CLOSED"
        print(f"\n[{s['label']}] {s['station_code']} shift {s['shift_id']}: "
              f"status={s['result']['status']} zero_variances={is_zero}")
        ok = ok and status_ok and is_zero

    for s in disputed:
        v = s["result"]["variances"]
        is_nonzero = (abs(v["liter_variance"]) > 1e-6 or (v["tank_variance"] is not None
                      and abs(v["tank_variance"]) > 50.0))
        status_ok = s["result"]["status"] == "DISPUTED"
        print(f"\n[{s['label']}] {s['station_code']} shift {s['shift_id']}: "
              f"status={s['result']['status']} nonzero_variances={is_nonzero}")
        ok = ok and status_ok and is_nonzero

    print("\n" + ("ВСЕ ПРОВЕРКИ ПРОШЛИ" if ok else "ЕСТЬ РАСХОЖДЕНИЯ С ОЖИДАНИЕМ — см. выше"))
    return ok


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reset", action="store_true",
                     help="удалить бизнес-данные PECO_* (PECO_REF_* не трогается)")
    ap.add_argument("--seed", action="store_true",
                     help="явно запустить посев (по умолчанию посев и так выполняется, "
                          "если не передан только --reset)")
    args = ap.parse_args()

    if args.reset:
        do_reset()
        if not args.seed:
            return

    print("=" * 70)
    print("PECO demo seed — мастер-данные (46 станций)")
    print("=" * 70)
    md = seed_master_data()
    print(f"\nСтанций создано: {md['created_stations']}, уже существовало: {md['skipped_stations']}")
    print(f"Резервуаров создано: {md['created_tanks']}")
    print(f"Колонок создано: {md['created_pumps']}")
    print(f"Пистолетов создано: {md['created_nozzles']}")
    print(f"Сотрудников создано: {md['created_emps']}")
    print(f"Цен создано: {md['created_prices']}")
    if md["low_alarm_tanks"]:
        print(f"Резервуары у сигнальной отметки (демо-алармы): {', '.join(md['low_alarm_tanks'])}")
    if md["managers_with_pin"]:
        print(f"\nМенеджерам назначен рабочий PIN = {DEMO_MANAGER_PIN} "
              f"({len(md['managers_with_pin'])} чел., например: "
              f"{md['managers_with_pin'][0][1]} @ {md['managers_with_pin'][0][0]})")

    station_ids = md["station_ids"]

    # 5 станций для операционных сценариев: по одной из первых пяти городов сети
    def first_code_of(region: str) -> str:
        return next(s["code"] for s in md["plan"] if s["region"] == region)

    st_clean = first_code_of("Кишинёв")
    st_clean2 = first_code_of("Бэлць")
    st_disputed = first_code_of("Кагул")
    st_delivery = first_code_of("Орхей")
    st_open = first_code_of("Унгень")

    print("\n" + "=" * 70)
    print("PECO demo seed — операционная история (через peco_shift/peco_txn/peco_inventory)")
    print("=" * 70)

    results: List[Dict[str, Any]] = []
    print(f"\nСтанция {st_clean}: чистая смена")
    results.append(scenario_clean(st_clean, station_ids, "clean"))
    print(f"\nСтанция {st_clean2}: чистая смена (вторая станция сети — для разнообразия картины)")
    results.append(scenario_clean(st_clean2, station_ids, "clean"))
    print(f"\nСтанция {st_disputed}: смена с расхождением")
    results.append(scenario_disputed(st_disputed, station_ids))
    print(f"\nСтанция {st_delivery}: смена с приходом цистерны")
    results.append(scenario_delivery(st_delivery, station_ids))
    print(f"\nСтанция {st_open}: смена остаётся OPEN")
    results.append(scenario_open(st_open, station_ids))

    verify_and_report(results)


if __name__ == "__main__":
    main()
