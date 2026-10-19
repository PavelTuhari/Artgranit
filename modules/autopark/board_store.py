"""Autopark — данные сводки руководителя одним подключением.

Отдельный store ради одной цифры: первая версия собирала сводку из семи
методов разных хранилищ, каждый открывал СВОЁ соединение с облачной ADB,
и экран первого лица грузился 3,8 секунды. Сама выборка при этом занимает
десятки миллисекунд — платили за семь рукопожатий с Ирландией.

Здесь все запросы идут в одном соединении. Это единственная причина
существования файла: никакой новой логики в нём нет, расчёты остались в
`board.py` и `supply_rules.py`.
"""
from __future__ import annotations

from typing import Any, Dict

from models.database import DatabaseModel
from modules.autopark.store import AutoparkSqlError, _done, _fail, _rows, _run

TANK_STATE = ("SELECT TANK_ID, STATION_ID, STATION_CODE, PRODUCT_CODE, CURRENT_L, "
              "MIN_STOCK_L, IN_TRANSIT_L, ALLOWED_L, DAYS_TO_MIN "
              "FROM V_FLT_TANK_STATE")

TRIPS = """
    SELECT t.ID AS TRIP_ID, t.TRIP_DATE, t.STATUS_CODE,
           t.NORM_KM, t.FACT_KM, t.FACT_FUEL_L, tr.CAPACITY_L,
           t.NORM_KM * tr.NORM_L_PER_100KM / 100 AS NORM_FUEL_L,
           NVL(vol.VOLUME_L, 0) AS VOLUME_L, NVL(pay.TOTAL_PAY, 0) AS PAY
      FROM FLT_TRIPS t
      JOIN FLT_TRUCKS tr ON tr.ID = t.TRUCK_ID
      LEFT JOIN (SELECT s.TRIP_ID, SUM(i.VOLUME_L) AS VOLUME_L
                   FROM FLT_TRIP_STOPS s
                   JOIN FLT_TRIP_STOP_ITEMS i ON i.STOP_ID = s.ID
                  GROUP BY s.TRIP_ID) vol ON vol.TRIP_ID = t.ID
      LEFT JOIN V_FLT_TRIP_PAY pay ON pay.TRIP_ID = t.ID
     WHERE t.TRIP_DATE >= :date_from AND t.TRIP_DATE < :date_to + 1
       AND t.STATUS_CODE <> 'DRAFT'"""

DRIVERS = """
    SELECT d.ID AS DRIVER_ID, d.FULL_NAME,
           SUM(CASE WHEN t.TYPE_CODE = 'DOMESTIC' THEN 1 ELSE 0 END) AS DOMESTIC_CNT,
           SUM(CASE WHEN t.TYPE_CODE = 'IMPORT' THEN 1 ELSE 0 END) AS IMPORT_CNT,
           NVL(SUM(t.NORM_KM), 0) AS TOTAL_NORM_KM,
           NVL(SUM(t.FACT_KM), 0) AS TOTAL_FACT_KM,
           NVL(SUM(vp.TOTAL_PAY), 0) AS TOTAL_PAY
      FROM FLT_DRIVERS d
      JOIN FLT_TRIPS t ON t.DRIVER_ID = d.ID
      JOIN V_FLT_TRIP_PAY vp ON vp.TRIP_ID = t.ID
     WHERE t.TRIP_DATE >= :date_from AND t.TRIP_DATE < :date_to + 1
       AND t.STATUS_CODE <> 'DRAFT'
     GROUP BY d.ID, d.FULL_NAME"""


def fetch_all(date_from, date_to) -> Dict[str, Any]:
    """Всё, что нужно сводке, за одно подключение."""
    window = {"date_from": date_from, "date_to": date_to}
    try:
        with DatabaseModel() as db:
            tanks = _rows(_run(db, TANK_STATE))
            trips = _rows(_run(db, TRIPS, window))
            drivers = _rows(_run(db, DRIVERS, window))
            params = _rows(_run(db,
                "SELECT ID, VALID_FROM, VALID_TO, MAX_COVER_DAYS, PLAN_HORIZON_DAYS "
                "FROM FLT_SUPPLY_PARAMS "
                "WHERE VALID_FROM <= :d AND (VALID_TO IS NULL OR VALID_TO >= :d) "
                "ORDER BY VALID_FROM DESC, ID DESC FETCH FIRST 1 ROWS ONLY",
                {"d": date_to}))
            rate = _rows(_run(db,
                "SELECT ID, VALID_FROM, VALID_TO, RATE_PER_KM, TRIP_BONUS "
                "FROM FLT_RATE_PERIODS "
                "WHERE VALID_FROM <= :d AND (VALID_TO IS NULL OR VALID_TO >= :d) "
                "ORDER BY VALID_FROM DESC, ID DESC FETCH FIRST 1 ROWS ONLY",
                {"d": date_to}))
            price = _rows(_run(db,
                "SELECT PRICE_LEI FROM FLT_FUEL_PRICES "
                "WHERE PRODUCT_CODE = 'DIESEL' AND PRICE_DATE <= :d "
                "ORDER BY PRICE_DATE DESC FETCH FIRST 1 ROWS ONLY", {"d": date_to}))
            settings = _rows(_run(db,
                "SELECT RATE_PER_KM, TRIP_BONUS, KM_DEVIATION_LIMIT "
                "FROM FLT_SETTINGS WHERE ID = 1"))
            plans = _rows(_run(db,
                "SELECT ID, PLAN_DATE, STATUS_CODE, TRIPS_CNT, VOLUME_L "
                "FROM FLT_SUPPLY_PLANS WHERE STATUS_CODE = 'CONFIRMED' "
                "ORDER BY ID DESC FETCH FIRST 50 ROWS ONLY"))
        return _done({"tanks": tanks, "trips": trips, "drivers": drivers,
                      "params": params[0] if params else None,
                      "rate": rate[0] if rate else None,
                      "fuel_price": float(price[0]["price_lei"]) if price else None,
                      "settings": settings[0] if settings else {},
                      "plans": plans})
    except AutoparkSqlError as exc:
        return _fail(str(exc))
