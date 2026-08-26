"""Autopark — хранилище модуля поверх таблиц FLT_* (Bemol, автопарк
бензовозов).

Только persistence: SQL и работа с Oracle. Бизнес-правила (нормативный
пробег, зарплата, планирование поставок) живут в modules/autopark/rules.py
и вызывающем коде (controller.py) — этот слой их не знает и не дублирует.

Конвенции — как в models/peco_oracle_store.py и modules/sda/store.py:
  * `_run(db, sql, params)` бросает PecoSqlError-подобное исключение при
    success=False — неудавшийся DML не должен молча доехать до commit();
  * каждый публичный метод ловит всё и возвращает
    {"success": bool, "data": ..., "message": str} — исключение наружу не
    выпускается;
  * явный `db.connection.commit()` после DML, один раз на транзакцию;
  * нулевой rowcount у UPDATE, где ожидалась ровно одна строка, — ошибка,
    а не тихий успех (строка могла исчезнуть между чтением формы и записью);
  * журнал (FLT_EVENT_LOG) — append-only и необязателен для успеха бизнес
    -операции: `log_event` глотает свои собственные ошибки (открывает
    отдельное соединение и не бросает исключений) — операция, которую он
    сопровождает, не должна падать из-за того, что не записалась строка
    журнала.

О хинте NO_PARALLEL (см. sql/120_flt_tables.sql, урок PECO 26.08.2026,
ORA-12860 на этой же ADB): в этом файле НЕТ ни одного "INSERT ... SELECT
... NEXTVAL" — каждый INSERT одной строки полагается на BEFORE INSERT
триггер таблицы (см. sql/120_flt_tables.sql), который присваивает ID
через `SELECT SEQ.NEXTVAL INTO :NEW.ID FROM DUAL` внутри самого триггера,
а не в тексте вызывающего INSERT. Именно многострочный INSERT...SELECT с
явным NEXTVAL в тексте вызывающего кода был причиной ORA-12860 у PECO —
здесь такого паттерна нет ни в одном методе. Если он появится в будущем
(например, ради пакетной вставки), хинт `/*+ NO_PARALLEL */` обязателен —
это проверяет tests/test_autopark.py::test_no_insert_select_nextval_without_no_parallel_hint.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from models.database import DatabaseModel

DistLookup = Callable[[str, object, str, object], Optional[float]]


class AutoparkSqlError(Exception):
    """SQL не выполнился (execute_query сообщил success=False)."""


def _run(db, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Выполняет запрос, бросает AutoparkSqlError при неудаче.

    execute_query никогда не бросает исключений сам — об ошибке он
    сообщает полем success. Без этой обёртки неудавшийся DML молча доехал
    бы до commit(), и вызывающий код получил бы success=True на операции,
    которая не выполнилась (см. модульный docstring).
    """
    r = db.execute_query(sql, params) if params is not None else db.execute_query(sql)
    if not r.get("success"):
        raise AutoparkSqlError(r.get("message") or "Ошибка SQL")
    return r


def _rows(r: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not r.get("success") or not r.get("data"):
        return []
    cols = [c.lower() for c in r["columns"]]
    return [dict(zip(cols, row)) for row in r["data"]]


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _done(data: Any = None, message: str = "") -> Dict[str, Any]:
    return {"success": True, "data": data, "message": message}


class AutoparkStore:
    """Все обращения к Oracle для модуля Autopark (FLT_*)."""

    # ── справочники ──────────────────────────────────────────────────

    @staticmethod
    def list_products() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "SELECT CODE, NAME_RU, ACTIVE FROM FLT_PRODUCTS "
                             "WHERE ACTIVE = 1 ORDER BY CODE")
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def list_stations() -> Dict[str, Any]:
        """АЗС вместе с вместимостью резервуаров по каждому продукту."""
        try:
            with DatabaseModel() as db:
                r = _run(db, "SELECT ID, CODE, NAME, ADDRESS, ACTIVE "
                             "FROM FLT_STATIONS ORDER BY CODE")
                stations = _rows(r)
                t = _run(db, "SELECT STATION_ID, PRODUCT_CODE, CAPACITY_L "
                             "FROM FLT_STATION_TANKS ORDER BY STATION_ID")
                tanks_by_station: Dict[int, List[Dict[str, Any]]] = {}
                for row in _rows(t):
                    tanks_by_station.setdefault(row["station_id"], []).append({
                        "product_code": row["product_code"],
                        "capacity_l": float(row["capacity_l"]),
                    })
                for s in stations:
                    s["tanks"] = tanks_by_station.get(s["id"], [])
                return _done(stations)
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def upsert_station(payload: Dict[str, Any]) -> Dict[str, Any]:
        station_id = payload.get("id")
        params = {
            "id": station_id,
            "code": payload.get("code"),
            "name": payload.get("name"),
            "address": payload.get("address") or None,
        }
        try:
            with DatabaseModel() as db:
                if station_id:
                    r = _run(db, "UPDATE FLT_STATIONS SET CODE = :code, "
                                 "NAME = :name, ADDRESS = :address "
                                 "WHERE ID = :id", params)
                    if not r.get("rowcount"):
                        return _fail(f"АЗС {station_id} не существует")
                    new_id = station_id
                else:
                    params.pop("id")
                    _run(db, "INSERT INTO FLT_STATIONS (CODE, NAME, ADDRESS) "
                             "VALUES (:code, :name, :address)", params)
                    new_id = _rows(_run(
                        db, "SELECT SEQ_FLT_STATIONS.CURRVAL AS ID FROM DUAL"
                    ))[0]["id"]

                tanks = payload.get("tanks") or []
                for tank in tanks:
                    _run(db, "MERGE INTO FLT_STATION_TANKS t USING "
                             "(SELECT :station_id AS STATION_ID, "
                             ":product_code AS PRODUCT_CODE FROM DUAL) s "
                             "ON (t.STATION_ID = s.STATION_ID "
                             "AND t.PRODUCT_CODE = s.PRODUCT_CODE) "
                             "WHEN MATCHED THEN UPDATE SET "
                             "t.CAPACITY_L = :capacity_l "
                             "WHEN NOT MATCHED THEN INSERT "
                             "(STATION_ID, PRODUCT_CODE, CAPACITY_L) "
                             "VALUES (:station_id, :product_code, :capacity_l)",
                        {"station_id": new_id,
                         "product_code": tank.get("product_code"),
                         "capacity_l": tank.get("capacity_l")})
                db.connection.commit()
            return _done({"id": new_id})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def list_load_points() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "SELECT ID, CODE, NAME, IS_FOREIGN FROM "
                             "FLT_LOAD_POINTS ORDER BY CODE")
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def list_end_points() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "SELECT ID, CODE, NAME FROM FLT_END_POINTS "
                             "ORDER BY CODE")
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def list_trucks() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "SELECT ID, PLATE, BRAND, CAPACITY_L, "
                             "SECTIONS_CNT, NORM_L_PER_100KM, ACTIVE "
                             "FROM FLT_TRUCKS ORDER BY PLATE")
                trucks = _rows(r)
                p = _run(db, "SELECT TRUCK_ID, PRODUCT_CODE FROM "
                             "FLT_TRUCK_PRODUCTS")
                products_by_truck: Dict[int, List[str]] = {}
                for row in _rows(p):
                    products_by_truck.setdefault(row["truck_id"], []).append(
                        row["product_code"])
                for t in trucks:
                    t["products"] = products_by_truck.get(t["id"], [])
                return _done(trucks)
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def upsert_truck(payload: Dict[str, Any]) -> Dict[str, Any]:
        truck_id = payload.get("id")
        params = {
            "id": truck_id,
            "plate": payload.get("plate"),
            "brand": payload.get("brand") or None,
            "capacity_l": payload.get("capacity_l"),
            "sections_cnt": payload.get("sections_cnt") or 1,
            "norm_l_per_100km": payload.get("norm_l_per_100km"),
        }
        try:
            with DatabaseModel() as db:
                if truck_id:
                    r = _run(db, "UPDATE FLT_TRUCKS SET PLATE = :plate, "
                                 "BRAND = :brand, CAPACITY_L = :capacity_l, "
                                 "SECTIONS_CNT = :sections_cnt, "
                                 "NORM_L_PER_100KM = :norm_l_per_100km "
                                 "WHERE ID = :id", params)
                    if not r.get("rowcount"):
                        return _fail(f"Автомобиль {truck_id} не существует")
                    new_id = truck_id
                    _run(db, "DELETE FROM FLT_TRUCK_PRODUCTS WHERE "
                             "TRUCK_ID = :id", {"id": truck_id})
                else:
                    params.pop("id")
                    _run(db, "INSERT INTO FLT_TRUCKS (PLATE, BRAND, "
                             "CAPACITY_L, SECTIONS_CNT, NORM_L_PER_100KM) "
                             "VALUES (:plate, :brand, :capacity_l, "
                             ":sections_cnt, :norm_l_per_100km)", params)
                    new_id = _rows(_run(
                        db, "SELECT SEQ_FLT_TRUCKS.CURRVAL AS ID FROM DUAL"
                    ))[0]["id"]

                for product_code in (payload.get("products") or []):
                    _run(db, "INSERT INTO FLT_TRUCK_PRODUCTS (TRUCK_ID, "
                             "PRODUCT_CODE) VALUES (:truck_id, "
                             ":product_code)",
                        {"truck_id": new_id, "product_code": product_code})
                db.connection.commit()
            return _done({"id": new_id})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def list_drivers() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "SELECT ID, FULL_NAME, TAB_NO, TRUCK_ID, "
                             "ACTIVE FROM FLT_DRIVERS ORDER BY FULL_NAME")
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def upsert_driver(payload: Dict[str, Any]) -> Dict[str, Any]:
        driver_id = payload.get("id")
        params = {
            "id": driver_id,
            "full_name": payload.get("full_name"),
            "tab_no": payload.get("tab_no"),
            "truck_id": payload.get("truck_id") or None,
        }
        try:
            with DatabaseModel() as db:
                if driver_id:
                    r = _run(db, "UPDATE FLT_DRIVERS SET FULL_NAME = "
                                 ":full_name, TAB_NO = :tab_no, "
                                 "TRUCK_ID = :truck_id WHERE ID = :id", params)
                    if not r.get("rowcount"):
                        return _fail(f"Водитель {driver_id} не существует")
                    new_id = driver_id
                else:
                    params.pop("id")
                    _run(db, "INSERT INTO FLT_DRIVERS (FULL_NAME, TAB_NO, "
                             "TRUCK_ID) VALUES (:full_name, :tab_no, "
                             ":truck_id)", params)
                    new_id = _rows(_run(
                        db, "SELECT SEQ_FLT_DRIVERS.CURRVAL AS ID FROM DUAL"
                    ))[0]["id"]
                db.connection.commit()
            return _done({"id": new_id})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── матрица расстояний ──────────────────────────────────────────

    @staticmethod
    def list_distances() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "SELECT FROM_KIND, FROM_ID, TO_KIND, TO_ID, "
                             "KM FROM FLT_DISTANCES ORDER BY FROM_KIND, "
                             "FROM_ID")
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def set_distance(from_kind: str, from_id, to_kind: str, to_id,
                      km: float) -> Dict[str, Any]:
        """MERGE участка матрицы + симметричная запись обратного участка.

        Матрица логически симметрична (расстояние туда и обратно одно и
        то же), но обратное направление записывается явным MERGE, а не
        подставляется на лету при чтении — это осознанно допускает в
        будущем асимметрию (например, объезд с односторонним движением),
        если кто-то отдельно переопределит только один из двух участков.
        Прямое направление перезаписывается безусловно (WHEN MATCHED
        UPDATE); обратное — только если его ещё нет (WHEN NOT MATCHED),
        чтобы не затирать уже заданную асимметрию.
        """
        try:
            with DatabaseModel() as db:
                _run(db, "MERGE INTO FLT_DISTANCES t USING "
                         "(SELECT :from_kind AS FROM_KIND, :from_id AS "
                         "FROM_ID, :to_kind AS TO_KIND, :to_id AS TO_ID "
                         "FROM DUAL) s ON (t.FROM_KIND = s.FROM_KIND AND "
                         "t.FROM_ID = s.FROM_ID AND t.TO_KIND = s.TO_KIND "
                         "AND t.TO_ID = s.TO_ID) "
                         "WHEN MATCHED THEN UPDATE SET t.KM = :km "
                         "WHEN NOT MATCHED THEN INSERT (FROM_KIND, FROM_ID, "
                         "TO_KIND, TO_ID, KM) VALUES (:from_kind, :from_id, "
                         ":to_kind, :to_id, :km)",
                    {"from_kind": from_kind, "from_id": from_id,
                     "to_kind": to_kind, "to_id": to_id, "km": km})
                _run(db, "MERGE INTO FLT_DISTANCES t USING "
                         "(SELECT :to_kind AS FROM_KIND, :to_id AS FROM_ID, "
                         ":from_kind AS TO_KIND, :from_id AS TO_ID "
                         "FROM DUAL) s ON (t.FROM_KIND = s.FROM_KIND AND "
                         "t.FROM_ID = s.FROM_ID AND t.TO_KIND = s.TO_KIND "
                         "AND t.TO_ID = s.TO_ID) "
                         "WHEN NOT MATCHED THEN INSERT (FROM_KIND, FROM_ID, "
                         "TO_KIND, TO_ID, KM) VALUES (:to_kind, :to_id, "
                         ":from_kind, :from_id, :km)",
                    {"from_kind": from_kind, "from_id": from_id,
                     "to_kind": to_kind, "to_id": to_id, "km": km})
                db.connection.commit()
            return _done({"from_kind": from_kind, "from_id": from_id,
                         "to_kind": to_kind, "to_id": to_id, "km": km})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def distance_lookup(db) -> DistLookup:
        """Строит функцию поиска расстояния поверх УЖЕ открытого `db`.

        Вся матрица читается одним запросом в словарь — участков мало
        (десятки-сотни), а маршрут может проверять каждый из них, так что
        поштучные SELECT на каждый rules.route_legs()-шаг были бы N
        запросов вместо одного. Функция, которую метод возвращает, не
        держит соединение открытым — она замыкает уже прочитанный словарь,
        так что `db` можно закрыть сразу после вызова.
        """
        r = _run(db, "SELECT FROM_KIND, FROM_ID, TO_KIND, TO_ID, KM FROM "
                     "FLT_DISTANCES")
        matrix = {(row["from_kind"], row["from_id"], row["to_kind"],
                   row["to_id"]): float(row["km"]) for row in _rows(r)}

        def _lookup(from_kind, from_id, to_kind, to_id):
            return matrix.get((from_kind, from_id, to_kind, to_id))
        return _lookup

    @staticmethod
    def distance_lookup_fn() -> DistLookup:
        """Обёртка без параметра db — для вызова из controller.py.

        controller не открывает соединения напрямую (это привилегия
        store); эта обёртка открывает и сразу закрывает своё соединение,
        возвращая уже готовую замкнутую функцию поиска (см. distance_lookup).
        """
        with DatabaseModel() as db:
            return AutoparkStore.distance_lookup(db)

    # ── настройки ────────────────────────────────────────────────────

    @staticmethod
    def get_settings() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "SELECT RATE_PER_KM, TRIP_BONUS, SAFETY_DAYS, "
                             "KM_DEVIATION_LIMIT, FUEL_DEVIATION_PCT FROM "
                             "FLT_SETTINGS WHERE ID = 1")
                rows = _rows(r)
                if not rows:
                    return _fail("Настройки модуля не найдены (ID=1)")
                return _done(rows[0])
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def update_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
        params = {
            "rate_per_km": payload.get("rate_per_km"),
            "trip_bonus": payload.get("trip_bonus"),
            "safety_days": payload.get("safety_days"),
            "km_deviation_limit": payload.get("km_deviation_limit"),
            "fuel_deviation_pct": payload.get("fuel_deviation_pct"),
        }
        try:
            with DatabaseModel() as db:
                r = _run(db, "UPDATE FLT_SETTINGS SET "
                             "RATE_PER_KM = :rate_per_km, "
                             "TRIP_BONUS = :trip_bonus, "
                             "SAFETY_DAYS = :safety_days, "
                             "KM_DEVIATION_LIMIT = :km_deviation_limit, "
                             "FUEL_DEVIATION_PCT = :fuel_deviation_pct "
                             "WHERE ID = 1", params)
                if not r.get("rowcount"):
                    return _fail("Настройки модуля не найдены (ID=1)")
                db.connection.commit()
            return _done(params)
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── поставки (накладные) ────────────────────────────────────────

    @staticmethod
    def insert_delivery(payload: Dict[str, Any]) -> Dict[str, Any]:
        params = {
            "deliv_date": payload.get("deliv_date"),
            "product_code": payload.get("product_code"),
            "volume_l": payload.get("volume_l"),
            "load_point_id": payload.get("load_point_id"),
            "station_id": payload.get("station_id"),
            "truck_id": payload.get("truck_id"),
            "driver_id": payload.get("driver_id"),
        }
        try:
            with DatabaseModel() as db:
                _run(db, "INSERT INTO FLT_DELIVERIES (DELIV_DATE, "
                         "PRODUCT_CODE, VOLUME_L, LOAD_POINT_ID, "
                         "STATION_ID, TRUCK_ID, DRIVER_ID) VALUES "
                         "(:deliv_date, :product_code, :volume_l, "
                         ":load_point_id, :station_id, :truck_id, "
                         ":driver_id)", params)
                new_id = _rows(_run(
                    db, "SELECT SEQ_FLT_DELIVERIES.CURRVAL AS ID FROM DUAL"
                ))[0]["id"]
                db.connection.commit()
            return _done({"id": new_id})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def list_deliveries(date_from, date_to,
                        unassigned_only: bool = False) -> Dict[str, Any]:
        sql = ("SELECT ID, DELIV_DATE, PRODUCT_CODE, VOLUME_L, "
               "LOAD_POINT_ID, STATION_ID, TRUCK_ID, DRIVER_ID, TRIP_ID "
               "FROM FLT_DELIVERIES WHERE DELIV_DATE BETWEEN :date_from "
               "AND :date_to")
        params = {"date_from": date_from, "date_to": date_to}
        if unassigned_only:
            sql += " AND TRIP_ID IS NULL"
        sql += " ORDER BY DELIV_DATE, ID"
        try:
            with DatabaseModel() as db:
                r = _run(db, sql, params)
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── рейсы ────────────────────────────────────────────────────────

    @staticmethod
    def create_trip(payload: Dict[str, Any],
                    stops: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        """Один рейс: шапка + стопы + позиции + привязка накладных.

        Одна транзакция, один commit в конце — критично: атомарность
        здесь та же проблема, что уронила PECO на "доставках, потерявших
        привязку к рейсу" (см. модульный docstring PECO), только для
        рейсов бензовозов. ``payload`` должен уже нести посчитанный
        ``norm_km`` и выбранный ``type_code`` — их расчёт и
        классификация не дело store, это ответственность controller
        (rules.route_legs/classify_trip).
        """
        header = {
            "trip_date": payload.get("trip_date"),
            "truck_id": payload.get("truck_id"),
            "driver_id": payload.get("driver_id"),
            "type_code": payload.get("type_code"),
            "load_point_id": payload.get("load_point_id"),
            "end_point_id": payload.get("end_point_id"),
            "source": payload.get("source") or "MANUAL",
            "norm_km": payload.get("norm_km"),
        }
        delivery_ids = payload.get("delivery_ids") or []
        try:
            with DatabaseModel() as db:
                _run(db, "INSERT INTO FLT_TRIPS (TRIP_DATE, TRUCK_ID, "
                         "DRIVER_ID, TYPE_CODE, LOAD_POINT_ID, "
                         "END_POINT_ID, SOURCE, NORM_KM) VALUES "
                         "(:trip_date, :truck_id, :driver_id, :type_code, "
                         ":load_point_id, :end_point_id, :source, "
                         ":norm_km)", header)
                trip_id = _rows(_run(
                    db, "SELECT SEQ_FLT_TRIPS.CURRVAL AS ID FROM DUAL"
                ))[0]["id"]

                for seq_no, stop in enumerate(stops, start=1):
                    _run(db, "INSERT INTO FLT_TRIP_STOPS (TRIP_ID, "
                             "SEQ_NO, STATION_ID) VALUES (:trip_id, "
                             ":seq_no, :station_id)",
                        {"trip_id": trip_id, "seq_no": seq_no,
                         "station_id": stop["station_id"]})
                    stop_id = _rows(_run(
                        db, "SELECT SEQ_FLT_TRIP_STOPS.CURRVAL AS ID "
                            "FROM DUAL"
                    ))[0]["id"]
                    for item in stop.get("items") or []:
                        _run(db, "INSERT INTO FLT_TRIP_STOP_ITEMS "
                                 "(STOP_ID, PRODUCT_CODE, VOLUME_L) "
                                 "VALUES (:stop_id, :product_code, "
                                 ":volume_l)",
                            {"stop_id": stop_id,
                             "product_code": item["product_code"],
                             "volume_l": item["volume_l"]})

                for delivery_id in delivery_ids:
                    ur = _run(db, "UPDATE FLT_DELIVERIES SET TRIP_ID = "
                                  ":trip_id WHERE ID = :delivery_id",
                             {"trip_id": trip_id, "delivery_id": delivery_id})
                    if not ur.get("rowcount"):
                        return _fail(
                            f"Накладная {delivery_id} не найдена — рейс не "
                            "создан")

                db.connection.commit()
            return _done({"trip_id": trip_id, "norm_km": header["norm_km"]})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def list_trips(date_from, date_to,
                   driver_id: Optional[int] = None) -> Dict[str, Any]:
        sql = ("SELECT ID, TRIP_DATE, TRUCK_ID, DRIVER_ID, TYPE_CODE, "
               "STATUS_CODE, LOAD_POINT_ID, END_POINT_ID, SOURCE, "
               "NORM_KM, FACT_KM, FACT_MINUTES, APPROVED_BY FROM "
               "FLT_TRIPS WHERE TRIP_DATE BETWEEN :date_from AND :date_to")
        params: Dict[str, Any] = {"date_from": date_from, "date_to": date_to}
        if driver_id is not None:
            sql += " AND DRIVER_ID = :driver_id"
            params["driver_id"] = driver_id
        sql += " ORDER BY TRIP_DATE, ID"
        try:
            with DatabaseModel() as db:
                r = _run(db, sql, params)
                trips = _rows(r)
                if not trips:
                    return _done([])
                trip_ids = [t["id"] for t in trips]
                placeholders = ", ".join(f":id{i}" for i in range(len(trip_ids)))
                sp = _run(db, "SELECT ID, TRIP_ID, SEQ_NO, STATION_ID FROM "
                             f"FLT_TRIP_STOPS WHERE TRIP_ID IN ({placeholders}) "
                             "ORDER BY TRIP_ID, SEQ_NO",
                         {f"id{i}": v for i, v in enumerate(trip_ids)})
                stops_by_trip: Dict[int, List[Dict[str, Any]]] = {}
                for row in _rows(sp):
                    stops_by_trip.setdefault(row["trip_id"], []).append(row)
                for t in trips:
                    t["stops"] = stops_by_trip.get(t["id"], [])
                return _done(trips)
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def approve_trip(trip_id, username: str) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "UPDATE FLT_TRIPS SET STATUS_CODE = "
                             "'APPROVED', APPROVED_BY = :username WHERE "
                             "ID = :trip_id AND STATUS_CODE = 'DRAFT'",
                        {"trip_id": trip_id, "username": username})
                if not r.get("rowcount"):
                    return _fail(
                        f"Рейс {trip_id} не найден или уже не в статусе "
                        "DRAFT")
                db.connection.commit()
            return _done({"trip_id": trip_id, "status": "APPROVED"})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def set_trip_fact(trip_id, fact_km: float,
                      fact_minutes: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "UPDATE FLT_TRIPS SET FACT_KM = :fact_km, "
                             "FACT_MINUTES = :fact_minutes WHERE ID = "
                             ":trip_id AND STATUS_CODE <> 'DRAFT'",
                        {"trip_id": trip_id, "fact_km": fact_km,
                         "fact_minutes": fact_minutes})
                if not r.get("rowcount"):
                    return _fail(
                        f"Рейс {trip_id} не найден или ещё не утверждён "
                        "(DRAFT)")
                db.connection.commit()
            return _done({"trip_id": trip_id, "fact_km": fact_km,
                         "fact_minutes": fact_minutes})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── учёт АЗС ─────────────────────────────────────────────────────

    @staticmethod
    def upsert_station_stock(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                for row in rows:
                    _run(db, "MERGE INTO FLT_STATION_STOCK t USING "
                             "(SELECT :station_id AS STATION_ID, "
                             ":product_code AS PRODUCT_CODE, "
                             ":stock_date AS STOCK_DATE FROM DUAL) s ON "
                             "(t.STATION_ID = s.STATION_ID AND "
                             "t.PRODUCT_CODE = s.PRODUCT_CODE AND "
                             "t.STOCK_DATE = s.STOCK_DATE) WHEN MATCHED "
                             "THEN UPDATE SET t.OPEN_L = :open_l, "
                             "t.CLOSE_L = :close_l, t.SALES_L = :sales_l, "
                             "t.RECEIVED_L = :received_l WHEN NOT MATCHED "
                             "THEN INSERT (STATION_ID, PRODUCT_CODE, "
                             "STOCK_DATE, OPEN_L, CLOSE_L, SALES_L, "
                             "RECEIVED_L) VALUES (:station_id, "
                             ":product_code, :stock_date, :open_l, "
                             ":close_l, :sales_l, :received_l)",
                        {"station_id": row["station_id"],
                         "product_code": row["product_code"],
                         "stock_date": row["stock_date"],
                         "open_l": row["open_l"], "close_l": row["close_l"],
                         "sales_l": row.get("sales_l") or 0,
                         "received_l": row.get("received_l") or 0})
                db.connection.commit()
            return _done({"rows": len(rows)})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def stock_days_report() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "SELECT STATION_CODE, STATION_NAME, "
                             "STATION_ID, PRODUCT_CODE, LAST_STOCK_DATE, "
                             "CURRENT_L, AVG_DAILY_SALES_L, STOCK_DAYS, "
                             "MIN_STOCK_L, NEED_SUPPLY FROM "
                             "V_FLT_STOCK_DAYS ORDER BY STATION_CODE, "
                             "PRODUCT_CODE")
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── зарплата / контроль ──────────────────────────────────────────

    @staticmethod
    def trip_pay_report(date_from, date_to,
                        driver_id: Optional[int] = None) -> Dict[str, Any]:
        """Оплата по рейсам за период. DRAFT исключается ЗДЕСЬ (фильтр —
        слой store, а не controller): черновик не основание для
        начисления (ТЗ п.6), и это правило не должно зависеть от того,
        кто вызвал отчёт."""
        sql = ("SELECT TRIP_ID, TRIP_DATE, DRIVER_ID, DRIVER_NAME, "
               "TYPE_CODE, STATUS_CODE, NORM_KM, KM_PAY, BONUS_PAY, "
               "TOTAL_PAY FROM V_FLT_TRIP_PAY WHERE STATUS_CODE <> "
               "'DRAFT' AND TRIP_DATE BETWEEN :date_from AND :date_to")
        params: Dict[str, Any] = {"date_from": date_from, "date_to": date_to}
        if driver_id is not None:
            sql += " AND DRIVER_ID = :driver_id"
            params["driver_id"] = driver_id
        sql += " ORDER BY TRIP_DATE, TRIP_ID"
        try:
            with DatabaseModel() as db:
                r = _run(db, sql, params)
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def trip_control_report(date_from, date_to) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "SELECT TRIP_ID, TRIP_DATE, PLATE, NORM_KM, "
                             "FACT_KM, KM_DEVIATION, OVER_KM_LIMIT, "
                             "NORM_FUEL_L FROM V_FLT_TRIP_CONTROL WHERE "
                             "TRIP_DATE BETWEEN :date_from AND :date_to "
                             "ORDER BY TRIP_DATE, TRIP_ID",
                        {"date_from": date_from, "date_to": date_to})
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def driver_summary(date_from, date_to) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, """
                    SELECT d.ID AS DRIVER_ID, d.FULL_NAME,
                           SUM(CASE WHEN t.TYPE_CODE = 'DOMESTIC' THEN 1
                                    ELSE 0 END) AS DOMESTIC_CNT,
                           SUM(CASE WHEN t.TYPE_CODE = 'IMPORT' THEN 1
                                    ELSE 0 END) AS IMPORT_CNT,
                           NVL(SUM(t.NORM_KM), 0) AS TOTAL_NORM_KM,
                           NVL(SUM(t.FACT_KM), 0) AS TOTAL_FACT_KM,
                           NVL(SUM(vp.TOTAL_PAY), 0) AS TOTAL_PAY
                    FROM FLT_DRIVERS d
                    JOIN FLT_TRIPS t ON t.DRIVER_ID = d.ID
                    JOIN V_FLT_TRIP_PAY vp ON vp.TRIP_ID = t.ID
                    WHERE t.TRIP_DATE BETWEEN :date_from AND :date_to
                      AND t.STATUS_CODE <> 'DRAFT'
                    GROUP BY d.ID, d.FULL_NAME
                    ORDER BY d.FULL_NAME""",
                        {"date_from": date_from, "date_to": date_to})
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def truck_summary(date_from, date_to) -> Dict[str, Any]:
        """По автомобилю: рейсы, перевезённый объём, нормативный расход.

        Фактический расход ДТ (ТЗ п.14) намеренно НЕ считается здесь:
        схема FLT_TRIPS не хранит фактически залитое/израсходованное
        топливо на рейс (только FACT_KM/FACT_MINUTES) — источника данных
        для него в первой очереди схемы нет. Возвращаем "fact_fuel_l":
        None и явно документируем это как известное ограничение (нужна
        отдельная колонка/источник GPS-заправок в следующей итерации),
        а не подменяем неизвестное значение нулём.
        """
        try:
            with DatabaseModel() as db:
                r = _run(db, """
                    SELECT tr.ID AS TRUCK_ID, tr.PLATE,
                           COUNT(DISTINCT t.ID) AS TRIP_CNT,
                           NVL(SUM(ti.VOLUME_L), 0) AS TOTAL_VOLUME_L,
                           NVL(SUM(t.NORM_KM * tr.NORM_L_PER_100KM / 100),
                               0) AS NORM_FUEL_L
                    FROM FLT_TRUCKS tr
                    LEFT JOIN FLT_TRIPS t ON t.TRUCK_ID = tr.ID
                           AND t.TRIP_DATE BETWEEN :date_from AND :date_to
                           AND t.STATUS_CODE <> 'DRAFT'
                    LEFT JOIN FLT_TRIP_STOPS ts ON ts.TRIP_ID = t.ID
                    LEFT JOIN FLT_TRIP_STOP_ITEMS ti ON ti.STOP_ID = ts.ID
                    GROUP BY tr.ID, tr.PLATE
                    ORDER BY tr.PLATE""",
                        {"date_from": date_from, "date_to": date_to})
                rows = _rows(r)
                for row in rows:
                    row["fact_fuel_l"] = None
                return _done(rows)
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def station_supply_report(date_from, date_to) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, """
                    SELECT s.STATION_ID, s.STATION_CODE, s.STATION_NAME,
                           s.PRODUCT_CODE, s.STOCK_DAYS, s.NEED_SUPPLY,
                           NVL(d.DELIV_CNT, 0) AS DELIV_CNT,
                           NVL(d.DELIV_VOLUME_L, 0) AS DELIV_VOLUME_L
                    FROM V_FLT_STOCK_DAYS s
                    LEFT JOIN (
                        SELECT STATION_ID, PRODUCT_CODE,
                               COUNT(*) AS DELIV_CNT,
                               SUM(VOLUME_L) AS DELIV_VOLUME_L
                        FROM FLT_DELIVERIES
                        WHERE DELIV_DATE BETWEEN :date_from AND :date_to
                        GROUP BY STATION_ID, PRODUCT_CODE
                    ) d ON d.STATION_ID = s.STATION_ID
                       AND d.PRODUCT_CODE = s.PRODUCT_CODE
                    ORDER BY s.STATION_CODE, s.PRODUCT_CODE""",
                        {"date_from": date_from, "date_to": date_to})
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── журнал ───────────────────────────────────────────────────────

    @staticmethod
    def log_event(event_type: str, ref_kind: Optional[str], ref_id,
                  details: str, username: str) -> None:
        """Append-only запись в FLT_EVENT_LOG. Ошибки ГЛОТАЕТ намеренно.

        Журнал сопровождает бизнес-операцию, но не должен иметь права её
        обрушить: он пишется в СВОЁМ отдельном соединении/транзакции уже
        ПОСЛЕ commit'а основной операции (см. вызовы в controller.py),
        поэтому даже проблема с самим журналом (переполненная колонка,
        временная недоступность БД) не откатывает то, что уже
        зафиксировано в бизнес-таблицах.
        """
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "INSERT INTO FLT_EVENT_LOG (EVENT_TYPE, REF_KIND, "
                    "REF_ID, DETAILS, USERNAME) VALUES (:event_type, "
                    ":ref_kind, :ref_id, :details, :username)",
                    {"event_type": event_type, "ref_kind": ref_kind,
                     "ref_id": ref_id, "details": (details or "")[:1000],
                     "username": username})
                if r.get("success"):
                    db.connection.commit()
        except Exception:
            # Намеренно: см. docstring — журнал никогда не должен
            # выбрасывать исключение наружу.
            pass
