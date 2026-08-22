#!/usr/bin/env python3
"""
Демо-данные контура снабжения топливом: нефтебаза, поставщики, парк
бензовозов, координаты АЗС и история суточного отпуска.

Почему скриптом, а не SQL-файлом: история отпуска — это 46 станций × 4
резервуара × 60 дней ≈ 11 тысяч строк со связным профилем спроса
(будни/выходные, трасса/город, сезон), и порождать её PL/SQL-ом
нечитаемо. Координаты станций проставляются по реальным городам
Молдовы с разбросом внутри города — так карта выглядит правдоподобно
без ручной расстановки 46 точек.

Запуск:  python3 scripts/seed_peco_supply_demo.py [--reset] [--days 60]
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import DatabaseModel

SEED = 20260820

# Реальные координаты районных центров Молдовы. Станции разбрасываются
# вокруг центра города в пределах нескольких километров.
CITIES = {
    'Кишинёв':     (47.0105, 28.8638, 0.045),
    'Бэлць':       (47.7615, 27.9294, 0.025),
    'Кагул':       (45.9075, 28.1917, 0.020),
    'Орхей':       (47.3831, 28.8231, 0.018),
    'Унгень':      (47.2065, 27.7963, 0.018),
    'Сорока':      (48.1553, 28.2975, 0.018),
    'Комрат':      (46.2985, 28.6575, 0.018),
    'Единец':      (48.1681, 27.3044, 0.015),
    'Хынчешть':    (46.8281, 28.5856, 0.015),
    'Кэушень':     (46.6417, 29.4103, 0.015),
    'Стрэшень':    (47.1414, 28.6103, 0.015),
    'Яловень':     (46.9469, 28.7833, 0.015),
    'Анений Ной':  (46.8797, 29.2317, 0.015),
    'Фэлешть':     (47.5722, 27.7106, 0.015),
    'Ниспорень':   (47.0806, 28.1750, 0.015),
}

# Нефтебаза: промзона Сынжера под Кишинёвом
DEPOT = {'code': 'NB-01', 'name': 'Нефтебаза Сынжера', 'address': 'Кишинёв, Сынжера, промзона',
         'lat': 46.9297, 'lon': 28.9686, 'bays': 3}

DEPOT_TANKS = [
    ('A92',    'NB-T-A92',    400000, 0.62, 60000),
    ('A95',    'NB-T-A95',    600000, 0.55, 90000),
    ('A98',    'NB-T-A98',    150000, 0.70, 25000),
    ('DIESEL', 'NB-T-DIESEL', 700000, 0.48, 100000),
]

SUPPLIERS = [
    ('DEPOT-OWN', 'Собственная нефтебаза Сынжера', 'depot',  'MD', None,  0.5, 0,      21.40),
    ('IMP-RO-01', 'Rompetrol Rafinare (Румыния)',  'import', 'RO', 'DAP', 9,   200000, 19.85),
    ('IMP-GR-01', 'Motor Oil Hellas (Греция)',     'import', 'GR', 'CIF', 14,  400000, 19.20),
    ('MKT-MD-01', 'Тирекс-Петрол (внутр. рынок)',  'market', 'MD', 'EXW', 2,   20000,  22.10),
]

# Бензовозы: секции разного объёма — это и есть кратность заказа
TRUCKS = [
    ('CDF-421', 'Volvo FM 6x2 + прицеп', 'Ион Урсу',     '+373 69 112 233', [8000, 8000, 6000, 6000]),
    ('CDF-508', 'MAN TGS 6x2',           'Виктор Мунтяну', '+373 69 445 566', [6000, 6000, 5000, 5000]),
    ('CDF-733', 'Scania P410 + прицеп',  'Сергей Балан',  '+373 69 778 899', [10000, 8000, 8000, 6000]),
    ('CDF-914', 'DAF XF 4x2',            'Андрей Чобану', '+373 69 220 011', [7000, 7000, 5000]),
]

# Профиль спроса: город против трассы, будни против выходных
GRADE_SHARE = {'A92': 0.22, 'A95': 0.44, 'A98': 0.06, 'DIESEL': 0.28}
WEEKDAY_K = [1.02, 1.00, 1.01, 1.06, 1.18, 1.12, 0.82]   # пн..вс


def rows(res):
    if not res or not res.get('success'):
        return []
    cols = [c.lower() for c in (res.get('columns') or [])]
    return [dict(zip(cols, r)) for r in (res.get('data') or [])]


def seed_geo(db, rnd):
    """Координаты станций: центр города + устойчивый разброс по коду АЗС."""
    stations = rows(db.execute_query(
        "SELECT ID, CODE, NAME, REGION, LAT FROM PECO_STATIONS ORDER BY ID"))
    n = 0
    for st in stations:
        if st.get('lat') is not None:
            continue
        city = CITIES.get(st.get('region'))
        if not city:
            continue
        lat0, lon0, spread = city
        # Разброс детерминирован кодом станции: повторный запуск не двигает точки
        r = random.Random(SEED + hash(st['code']) % 100000)
        lat = lat0 + r.uniform(-spread, spread)
        lon = lon0 + r.uniform(-spread * 1.4, spread * 1.4)
        zone = 'Центр' if st['region'] == 'Кишинёв' else (
            'Север' if st['region'] in ('Бэлць', 'Сорока', 'Единец', 'Фэлешть') else (
                'Юг' if st['region'] in ('Кагул', 'Комрат', 'Кэушень') else 'Центр-район'))
        db.execute_query(
            "UPDATE PECO_STATIONS SET LAT = :p_lat, LON = :p_lon, GEO_SOURCE = 'demo', "
            "GEO_AT = SYSTIMESTAMP, ROUTE_ZONE = :p_zone WHERE ID = :p_id",
            {'p_lat': round(lat, 6), 'p_lon': round(lon, 6), 'p_zone': zone, 'p_id': st['id']})
        n += 1
    return n


def seed_depot(db):
    have = rows(db.execute_query("SELECT ID FROM PECO_DEPOTS WHERE CODE = :p",
                                 {'p': DEPOT['code']}))
    if have:
        return have[0]['id'], 0
    db.execute_query(
        "INSERT INTO PECO_DEPOTS (CODE, NAME, ADDRESS, LAT, LON, LOAD_BAYS) "
        "VALUES (:p_c, :p_n, :p_a, :p_lat, :p_lon, :p_b)",
        {'p_c': DEPOT['code'], 'p_n': DEPOT['name'], 'p_a': DEPOT['address'],
         'p_lat': DEPOT['lat'], 'p_lon': DEPOT['lon'], 'p_b': DEPOT['bays']})
    depot_id = rows(db.execute_query(
        "SELECT ID FROM PECO_DEPOTS WHERE CODE = :p", {'p': DEPOT['code']}))[0]['id']
    for grade, code, cap, fill, minst in DEPOT_TANKS:
        db.execute_query(
            "INSERT INTO PECO_DEPOT_TANKS (DEPOT_ID, GRADE_CODE, CODE, CAPACITY_L, "
            "CURRENT_L, MIN_STOCK_L) VALUES (:p_d, :p_g, :p_c, :p_cap, :p_cur, :p_min)",
            {'p_d': depot_id, 'p_g': grade, 'p_c': code, 'p_cap': cap,
             'p_cur': round(cap * fill, 3), 'p_min': minst})
    return depot_id, len(DEPOT_TANKS)


def seed_suppliers(db):
    n = 0
    for code, name, src, country, inc, lead, min_lot, price in SUPPLIERS:
        if rows(db.execute_query("SELECT ID FROM PECO_FUEL_SUPPLIERS WHERE CODE = :p",
                                 {'p': code})):
            continue
        db.execute_query(
            "INSERT INTO PECO_FUEL_SUPPLIERS (CODE, NAME, SOURCE_CODE, COUNTRY, INCOTERMS, "
            "LEAD_DAYS, MIN_LOT_L, PRICE_PER_L) VALUES (:p_c, :p_n, :p_s, :p_co, :p_i, "
            ":p_l, :p_m, :p_p)",
            {'p_c': code, 'p_n': name, 'p_s': src, 'p_co': country, 'p_i': inc,
             'p_l': lead, 'p_m': min_lot, 'p_p': price})
        n += 1
    return n


def seed_fleet(db, depot_id):
    prov = rows(db.execute_query("SELECT ID FROM PECO_GPS_PROVIDERS WHERE CODE = 'GPSMD'"))
    if prov:
        prov_id = prov[0]['id']
    else:
        db.execute_query(
            "INSERT INTO PECO_GPS_PROVIDERS (CODE, NAME, CONTACT) "
            "VALUES ('GPSMD', 'GPS Monitor MD (аутсорс телеметрии)', 'support@gpsmonitor.md')")
        prov_id = rows(db.execute_query(
            "SELECT ID FROM PECO_GPS_PROVIDERS WHERE CODE = 'GPSMD'"))[0]['id']

    n = 0
    for plate, model, driver, phone, comps in TRUCKS:
        if rows(db.execute_query("SELECT ID FROM PECO_TRUCKS WHERE PLATE_NO = :p",
                                 {'p': plate})):
            continue
        db.execute_query(
            "INSERT INTO PECO_TRUCKS (PLATE_NO, MODEL, DEPOT_ID, CAPACITY_L, COMP_COUNT, "
            "GPS_PROVIDER_ID, GPS_DEVICE_ID, DRIVER_NAME, DRIVER_PHONE) "
            "VALUES (:p_pl, :p_m, :p_d, :p_cap, :p_cc, :p_gp, :p_dev, :p_dr, :p_ph)",
            {'p_pl': plate, 'p_m': model, 'p_d': depot_id, 'p_cap': sum(comps),
             'p_cc': len(comps), 'p_gp': prov_id, 'p_dev': 'GPS-' + plate.replace('-', ''),
             'p_dr': driver, 'p_ph': phone})
        truck_id = rows(db.execute_query(
            "SELECT ID FROM PECO_TRUCKS WHERE PLATE_NO = :p", {'p': plate}))[0]['id']
        for i, vol in enumerate(comps, 1):
            db.execute_query(
                "INSERT INTO PECO_TRUCK_COMPARTMENTS (TRUCK_ID, COMP_NO, VOLUME_L) "
                "VALUES (:p_t, :p_no, :p_v)",
                {'p_t': truck_id, 'p_no': i, 'p_v': vol})
        n += 1
    return n


def seed_daily(db, days, rnd):
    """
    История суточного отпуска. Уровень станции зависит от города
    (Кишинёв и трасса продают больше), профиль недели общий, шум 12 %.
    """
    tanks = rows(db.execute_query(
        "SELECT t.ID AS TANK_ID, t.STATION_ID, t.GRADE_CODE, t.CAPACITY_L, s.REGION, s.CODE "
        "FROM PECO_TANKS t JOIN PECO_STATIONS s ON s.ID = t.STATION_ID "
        "WHERE t.ACTIVE = 1 ORDER BY t.ID"))
    if not tanks:
        return 0
    last = date.today() - timedelta(days=1)
    batch, total = [], 0
    sql = ("INSERT INTO PECO_TANK_DAILY (TANK_ID, STATION_ID, GRADE_CODE, SALE_DATE, "
           "LITERS, AMOUNT, LEVEL_END_L) VALUES (:1, :2, :3, :4, :5, :6, :7)")
    cur = db.connection.cursor()
    for t in tanks:
        # Базовый суточный отпуск станции: от размера города и ёмкости резервуара
        r = random.Random(SEED + int(t['tank_id']) * 7919)
        city_k = {'Кишинёв': 1.55, 'Бэлць': 1.15, 'Кагул': 0.95}.get(t['region'], 0.80)
        base = float(t['capacity_l']) * 0.055 * city_k * GRADE_SHARE[t['grade_code']] / 0.25
        base *= r.uniform(0.82, 1.18)
        for i in range(days):
            d = last - timedelta(days=days - 1 - i)
            k = WEEKDAY_K[d.weekday()]
            # Мягкий сезонный ход: к концу лета спрос выше
            season = 1.0 + 0.06 * math.sin((d.timetuple().tm_yday / 365.0) * 2 * math.pi)
            liters = max(0.0, base * k * season * r.gauss(1.0, 0.12))
            batch.append((int(t['tank_id']), int(t['station_id']), t['grade_code'], d,
                          round(liters, 3), round(liters * 22.5, 2), None))
            if len(batch) >= 5000:
                cur.executemany(sql, batch); db.connection.commit()
                total += len(batch); batch = []
    if batch:
        cur.executemany(sql, batch); db.connection.commit()
        total += len(batch)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reset', action='store_true', help='очистить контур снабжения')
    ap.add_argument('--days', type=int, default=60, help='глубина истории отпуска')
    args = ap.parse_args()
    rnd = random.Random(SEED)

    with DatabaseModel() as db:
        if args.reset:
            for tbl in ('PECO_GPS_EVENTS', 'PECO_GPS_PINGS', 'PECO_TRIP_STOPS', 'PECO_TRIPS',
                        'PECO_FUEL_ORDER_ITEMS', 'PECO_FUEL_ORDERS', 'PECO_ORDER_RUNS',
                        'PECO_TANK_DAILY', 'PECO_TRUCK_COMPARTMENTS', 'PECO_TRUCKS',
                        'PECO_DEPOT_TANKS', 'PECO_DEPOTS', 'PECO_FUEL_SUPPLIERS',
                        'PECO_GPS_PROVIDERS'):
                db.execute_query(f"DELETE FROM {tbl}")
            db.execute_query("UPDATE PECO_STATIONS SET LAT = NULL, LON = NULL, "
                             "GEO_SOURCE = NULL, ROUTE_ZONE = NULL")
            db.connection.commit()
            print('контур снабжения очищен')

        n_geo = seed_geo(db, rnd)
        depot_id, n_dt = seed_depot(db)
        n_sup = seed_suppliers(db)
        n_truck = seed_fleet(db, depot_id)
        db.connection.commit()

        have_daily = rows(db.execute_query("SELECT COUNT(*) AS C FROM PECO_TANK_DAILY"))
        n_daily = 0
        if not have_daily or not have_daily[0]['c']:
            n_daily = seed_daily(db, args.days, rnd)

        print(f'координат станций: {n_geo}')
        print(f'нефтебаза: {DEPOT["code"]} (резервуаров {n_dt})')
        print(f'поставщиков: {n_sup}, бензовозов: {n_truck}')
        print(f'строк суточного отпуска: {n_daily}')

        for r in rows(db.execute_query(
                "SELECT GRADE_CODE, ROUND(SUM(NVL(AVG_L_28,0))) AS NET_DAILY, "
                "COUNT(*) AS TANKS, SUM(IS_DRY_RISK) AS DRY "
                "FROM V_PECO_TANK_SUPPLY GROUP BY GRADE_CODE ORDER BY GRADE_CODE")):
            print(f"  {r['grade_code']:7} сеть {r['net_daily']:>8} л/сут · "
                  f"резервуаров {r['tanks']:>3} · риск сухого бака {r['dry']}")


if __name__ == '__main__':
    main()
