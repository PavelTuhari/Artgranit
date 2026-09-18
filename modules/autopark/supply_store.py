"""Autopark — хранилище контура распределения топлива (ТЗ от 18.09.2026).

Отдельный файл от `store.py` намеренно: там persistence первого контура
(зарплата, рейсы, накладные), здесь — второго (остатки резервуаров,
отсеки цистерн, группы АЗС, план распределения и его исполнение).
Правило проекта «логика — в свой файл» (CLAUDE.md, правило №2) касается
и SQL: переписать один большой store.py целиком параллельная сессия может
случайно, два файла — уже нет.

Конвенции те же, что в `store.py`: `_run` бросает при success=False,
каждый публичный метод возвращает `{"success", "data", "message"}`,
commit после DML ровно один раз, ни одного `INSERT ... SELECT NEXTVAL`
(ID проставляет BEFORE INSERT триггер — см. sql/125_flt_supply.sql).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from models.database import DatabaseModel
from modules.autopark.store import AutoparkSqlError, _done, _fail, _rows, _run


class SupplyStore:
    """Таблицы FLT_TANK_STOCK / FLT_TRUCK_SECTIONS / FLT_SUPPLY_* ."""

    # ── остатки резервуаров ─────────────────────────────────────────

    @staticmethod
    def tank_state() -> Dict[str, Any]:
        """Состояние всех резервуаров сети — вход планировщика (ТЗ п.2)."""
        try:
            with DatabaseModel() as db:
                r = _run(db,
                         "SELECT TANK_ID, STATION_ID, STATION_CODE, STATION_NAME, "
                         "PRODUCT_CODE, FUEL_GROUP, CAPACITY_L, MAX_FILL_L, "
                         "CURRENT_L, STOCK_TS, STOCK_SOURCE, AVG_DAILY_L, "
                         "MIN_STOCK_L, MAX_COVER_DAYS, IN_TRANSIT_L, ALLOWED_L, "
                         "DAYS_TO_MIN FROM V_FLT_TANK_STATE "
                         "ORDER BY DAYS_TO_MIN NULLS LAST, STATION_CODE, PRODUCT_CODE")
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def save_tank_limits(tank_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ручные параметры резервуара (ТЗ п.2, п.4.2).

        Минимальный остаток и допустимый запас в днях заказчик вводит
        руками — это коммерческое решение, а не расчёт. NULL в
        MAX_COVER_DAYS означает «брать общий потолок из настроек».
        """
        params = {"tank_id": tank_id,
                  "max_fill_l": payload.get("max_fill_l"),
                  "min_stock_l": payload.get("min_stock_l"),
                  "max_cover_days": payload.get("max_cover_days"),
                  "ext_code": payload.get("ext_code")}
        try:
            with DatabaseModel() as db:
                r = _run(db, "UPDATE FLT_STATION_TANKS SET "
                             "MAX_FILL_L = :max_fill_l, "
                             "MIN_STOCK_L = :min_stock_l, "
                             "MAX_COVER_DAYS = :max_cover_days, "
                             "EXT_CODE = :ext_code WHERE ID = :tank_id", params)
                if not r.get("rowcount"):
                    return _fail(f"Резервуар {tank_id} не найден")
                db.connection.commit()
            return _done(params)
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def push_stock(rows: Sequence[Dict[str, Any]], source: str = "PETROL_EXPERT"
                   ) -> Dict[str, Any]:
        """Приём остатков из внешней системы (Petrol Expert).

        Пишется снимок, а не «текущее значение поверх»: план, сделанный
        вчера, должен объясняться теми числами, что были вчера.
        """
        if not rows:
            return _fail("Пустой пакет остатков")
        try:
            saved = 0
            with DatabaseModel() as db:
                for row in rows:
                    tank_id = row.get("tank_id")
                    if tank_id is None:
                        # Внешняя система знает станцию и продукт, а не наш ID.
                        found = _rows(_run(db,
                            "SELECT t.ID FROM FLT_STATION_TANKS t "
                            "JOIN FLT_STATIONS s ON s.ID = t.STATION_ID "
                            "WHERE (t.EXT_CODE = :ext OR s.CODE = :ext) "
                            "AND t.PRODUCT_CODE = :product",
                            {"ext": row.get("station_code") or row.get("ext_code"),
                             "product": row.get("product_code")}))
                        if not found:
                            continue
                        tank_id = found[0]["id"]
                    _run(db, "INSERT INTO FLT_TANK_STOCK (TANK_ID, CURRENT_L, SOURCE) "
                             "VALUES (:tank_id, :current_l, :source)",
                         {"tank_id": tank_id,
                          "current_l": row.get("current_l"),
                          "source": source})
                    saved += 1
                db.connection.commit()
            return _done({"saved": saved, "received": len(rows)})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── отсеки цистерн ──────────────────────────────────────────────

    @staticmethod
    def list_sections(truck_id: Optional[int] = None) -> Dict[str, Any]:
        sql = ("SELECT s.ID, s.TRUCK_ID, t.PLATE, s.SEQ_NO, s.VOLUME_L, s.ACTIVE "
               "FROM FLT_TRUCK_SECTIONS s JOIN FLT_TRUCKS t ON t.ID = s.TRUCK_ID")
        params: Dict[str, Any] = {}
        if truck_id is not None:
            sql += " WHERE s.TRUCK_ID = :truck_id"
            params["truck_id"] = truck_id
        sql += " ORDER BY s.TRUCK_ID, s.SEQ_NO"
        try:
            with DatabaseModel() as db:
                return _done(_rows(_run(db, sql, params or None)))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def save_sections(truck_id: int, sections: Sequence[Dict[str, Any]]
                      ) -> Dict[str, Any]:
        """Перезаписывает набор отсеков цистерны целиком.

        Именно целиком, а не по одному: отсеки нумеруются подряд от кабины
        к хвосту, и правка по одному оставляла бы дыры в нумерации, от
        которой зависит порядок слива.
        """
        try:
            with DatabaseModel() as db:
                used = _rows(_run(db, "SELECT COUNT(*) AS CNT FROM FLT_SUPPLY_LOADS l "
                                      "JOIN FLT_TRUCK_SECTIONS s ON s.ID = l.SECTION_ID "
                                      "WHERE s.TRUCK_ID = :truck_id",
                                  {"truck_id": truck_id}))
                if used and int(used[0]["cnt"]) > 0:
                    return _fail("Отсеки этой цистерны уже используются в планах — "
                                 "правка нарушила бы сохранённые расчёты")
                _run(db, "DELETE FROM FLT_TRUCK_SECTIONS WHERE TRUCK_ID = :truck_id",
                     {"truck_id": truck_id})
                for idx, sec in enumerate(sections, start=1):
                    _run(db, "INSERT INTO FLT_TRUCK_SECTIONS "
                             "(TRUCK_ID, SEQ_NO, VOLUME_L) "
                             "VALUES (:truck_id, :seq_no, :volume_l)",
                         {"truck_id": truck_id,
                          "seq_no": sec.get("seq_no") or idx,
                          "volume_l": sec.get("volume_l")})
                db.connection.commit()
            return _done({"truck_id": truck_id, "sections": len(sections)})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── группы АЗС ──────────────────────────────────────────────────

    @staticmethod
    def list_groups() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                groups = _rows(_run(db, "SELECT ID, CODE, NAME, ACTIVE "
                                        "FROM FLT_STATION_GROUPS ORDER BY CODE"))
                items = _rows(_run(db, "SELECT GROUP_ID, STATION_ID, SEQ_NO "
                                       "FROM FLT_STATION_GROUP_ITEMS "
                                       "ORDER BY GROUP_ID, SEQ_NO"))
            by_group: Dict[Any, List[Any]] = {}
            for it in items:
                by_group.setdefault(it["group_id"], []).append(it["station_id"])
            for g in groups:
                g["station_ids"] = by_group.get(g["id"], [])
            return _done(groups)
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def save_group(payload: Dict[str, Any]) -> Dict[str, Any]:
        group_id = payload.get("id")
        params = {"code": payload.get("code"), "name": payload.get("name"),
                  "active": 1 if payload.get("active", True) else 0}
        try:
            with DatabaseModel() as db:
                if group_id:
                    params["id"] = group_id
                    r = _run(db, "UPDATE FLT_STATION_GROUPS SET CODE = :code, "
                                 "NAME = :name, ACTIVE = :active WHERE ID = :id",
                             params)
                    if not r.get("rowcount"):
                        return _fail(f"Группа {group_id} не найдена")
                else:
                    _run(db, "INSERT INTO FLT_STATION_GROUPS (CODE, NAME, ACTIVE) "
                             "VALUES (:code, :name, :active)", params)
                    new_id = _rows(_run(db, "SELECT ID FROM FLT_STATION_GROUPS "
                                            "WHERE CODE = :code", {"code": params["code"]}))
                    group_id = new_id[0]["id"] if new_id else None
                _run(db, "DELETE FROM FLT_STATION_GROUP_ITEMS WHERE GROUP_ID = :id",
                     {"id": group_id})
                for seq, station_id in enumerate(payload.get("station_ids") or [], 1):
                    _run(db, "INSERT INTO FLT_STATION_GROUP_ITEMS "
                             "(GROUP_ID, STATION_ID, SEQ_NO) "
                             "VALUES (:group_id, :station_id, :seq_no)",
                         {"group_id": group_id, "station_id": station_id, "seq_no": seq})
                db.connection.commit()
            return _done({"id": group_id})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── план распределения ──────────────────────────────────────────

    @staticmethod
    def save_plan(plan: Dict[str, Any], settings: Dict[str, Any],
                  username: str) -> Dict[str, Any]:
        """Сохраняет рассчитанный план целиком (шапка, потребности, рейсы, отсеки)."""
        needs = plan.get("needs") or []
        trips = plan.get("trips") or []
        try:
            with DatabaseModel() as db:
                _run(db, "INSERT INTO FLT_SUPPLY_PLANS "
                         "(HORIZON_DAYS, COVER_DAYS, NEEDS_CNT, TRIPS_CNT, "
                         " VOLUME_L, CREATED_BY) "
                         "VALUES (:horizon, :cover, :needs_cnt, :trips_cnt, "
                         "        :volume, :username)",
                     {"horizon": settings.get("plan_horizon_days") or 0,
                      "cover": settings.get("max_cover_days") or 7,
                      "needs_cnt": len(needs), "trips_cnt": len(trips),
                      "volume": sum(float(t.get("volume_l") or 0) for t in trips),
                      "username": username})
                plan_id = _rows(_run(db, "SELECT MAX(ID) AS ID FROM FLT_SUPPLY_PLANS"))[0]["id"]

                need_ids: Dict[Any, int] = {}
                for need in needs:
                    _run(db, "INSERT INTO FLT_SUPPLY_NEEDS "
                             "(PLAN_ID, STATION_ID, PRODUCT_CODE, TANK_ID, CURRENT_L, "
                             " AVG_DAILY_L, MIN_STOCK_L, MAX_FILL_L, IN_TRANSIT_L, "
                             " DAYS_TO_MIN, ALLOWED_L, TARGET_L, PLANNED_L, COVER_DAYS, "
                             " WARNING) "
                             "VALUES (:plan_id, :station_id, :product_code, :tank_id, "
                             " :current_l, :avg_daily_l, :min_stock_l, :max_fill_l, "
                             " :in_transit_l, :days_to_min, :allowed_l, :target_l, "
                             " :planned_l, :cover_days, :warning)",
                         {"plan_id": plan_id,
                          "station_id": need["station_id"],
                          "product_code": need["product_code"],
                          "tank_id": need.get("tank_id"),
                          "current_l": need["current_l"],
                          "avg_daily_l": need["avg_daily_l"],
                          "min_stock_l": need["min_stock_l"],
                          "max_fill_l": need["max_fill_l"],
                          "in_transit_l": need["in_transit_l"],
                          "days_to_min": need.get("days_to_min"),
                          "allowed_l": need["allowed_l"],
                          "target_l": need["target_l"],
                          "planned_l": need.get("planned_l") or 0,
                          "cover_days": need.get("cover_days_after"),
                          "warning": ",".join(need.get("warnings") or []) or None})
                    row = _rows(_run(db, "SELECT MAX(ID) AS ID FROM FLT_SUPPLY_NEEDS "
                                         "WHERE PLAN_ID = :plan_id AND STATION_ID = :station_id "
                                         "AND PRODUCT_CODE = :product_code",
                                     {"plan_id": plan_id,
                                      "station_id": need["station_id"],
                                      "product_code": need["product_code"]}))
                    need_ids[(need["station_id"], need["product_code"])] = row[0]["id"]

                for trip in trips:
                    _run(db, "INSERT INTO FLT_SUPPLY_TRIPS "
                             "(PLAN_ID, SEQ_NO, TRUCK_ID, FUEL_GROUP, LOAD_POINT_ID, "
                             " GROUP_ID, VOLUME_L, EST_KM) "
                             "VALUES (:plan_id, :seq_no, :truck_id, :fuel_group, "
                             " :load_point_id, :group_id, :volume_l, :est_km)",
                         {"plan_id": plan_id, "seq_no": trip.get("seq_no") or 1,
                          "truck_id": trip["truck_id"],
                          "fuel_group": trip.get("fuel_group") or "PETROL",
                          "load_point_id": trip["load_point_id"],
                          "group_id": trip.get("group_id"),
                          "volume_l": trip.get("volume_l") or 0,
                          "est_km": trip.get("est_km")})
                    strip_id = _rows(_run(db, "SELECT MAX(ID) AS ID FROM FLT_SUPPLY_TRIPS "
                                              "WHERE PLAN_ID = :plan_id",
                                          {"plan_id": plan_id}))[0]["id"]
                    for load in trip.get("loads") or []:
                        _run(db, "INSERT INTO FLT_SUPPLY_LOADS "
                                 "(SUPPLY_TRIP_ID, NEED_ID, SECTION_ID, STATION_ID, "
                                 " PRODUCT_CODE, VOLUME_L, UNLOAD_SEQ) "
                                 "VALUES (:trip_id, :need_id, :section_id, :station_id, "
                                 " :product_code, :volume_l, :unload_seq)",
                             {"trip_id": strip_id,
                              "need_id": need_ids.get((load["station_id"],
                                                       load["product_code"])),
                              "section_id": load["section_id"],
                              "station_id": load["station_id"],
                              "product_code": load["product_code"],
                              "volume_l": load["volume_l"],
                              "unload_seq": load["unload_seq"]})
                db.connection.commit()
            return _done({"plan_id": plan_id, "needs": len(needs), "trips": len(trips)})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def list_plans(limit: int = 20) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                return _done(_rows(_run(db,
                    "SELECT ID, PLAN_DATE, STATUS_CODE, HORIZON_DAYS, COVER_DAYS, "
                    "NEEDS_CNT, TRIPS_CNT, VOLUME_L, CREATED_BY, CREATED_AT "
                    "FROM FLT_SUPPLY_PLANS ORDER BY ID DESC "
                    "FETCH FIRST :lim ROWS ONLY", {"lim": limit})))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def get_plan(plan_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                head = _rows(_run(db, "SELECT ID, PLAN_DATE, STATUS_CODE, HORIZON_DAYS, "
                                      "COVER_DAYS, NEEDS_CNT, TRIPS_CNT, VOLUME_L, "
                                      "CREATED_BY FROM FLT_SUPPLY_PLANS WHERE ID = :id",
                                  {"id": plan_id}))
                if not head:
                    return _fail(f"План {plan_id} не найден")
                needs = _rows(_run(db, "SELECT * FROM V_FLT_SUPPLY_PLAN "
                                       "WHERE PLAN_ID = :id "
                                       "ORDER BY DAYS_TO_MIN NULLS LAST, STATION_CODE",
                                   {"id": plan_id}))
                loads = _rows(_run(db, "SELECT * FROM V_FLT_SUPPLY_LOADS "
                                       "WHERE PLAN_ID = :id "
                                       "ORDER BY SUPPLY_TRIP_ID, UNLOAD_SEQ",
                                   {"id": plan_id}))
                trips = _rows(_run(db, "SELECT st.ID, st.SEQ_NO, st.TRUCK_ID, tr.PLATE, "
                                       "st.FUEL_GROUP, st.LOAD_POINT_ID, lp.NAME AS LOAD_POINT_NAME, "
                                       "st.GROUP_ID, g.NAME AS GROUP_NAME, st.VOLUME_L, "
                                       "st.EST_KM, st.TRIP_ID "
                                       "FROM FLT_SUPPLY_TRIPS st "
                                       "JOIN FLT_TRUCKS tr ON tr.ID = st.TRUCK_ID "
                                       "JOIN FLT_LOAD_POINTS lp ON lp.ID = st.LOAD_POINT_ID "
                                       "LEFT JOIN FLT_STATION_GROUPS g ON g.ID = st.GROUP_ID "
                                       "WHERE st.PLAN_ID = :id ORDER BY st.SEQ_NO",
                                   {"id": plan_id}))
            for trip in trips:
                trip["loads"] = [l for l in loads if l["supply_trip_id"] == trip["id"]]
            return _done({"plan": head[0], "needs": needs, "trips": trips})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def update_load(load_id: int, volume_l: float) -> Dict[str, Any]:
        """Ручная правка объёма в отсеке (ТЗ п.7). Проверки — в контроллере."""
        try:
            with DatabaseModel() as db:
                r = _run(db, "UPDATE FLT_SUPPLY_LOADS SET VOLUME_L = :volume_l "
                             "WHERE ID = :id",
                         {"volume_l": volume_l, "id": load_id})
                if not r.get("rowcount"):
                    return _fail(f"Строка плана {load_id} не найдена")
                db.connection.commit()
            return _done({"id": load_id, "volume_l": volume_l})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def delete_load(load_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db, "DELETE FROM FLT_SUPPLY_LOADS WHERE ID = :id",
                         {"id": load_id})
                if not r.get("rowcount"):
                    return _fail(f"Строка плана {load_id} не найдена")
                db.connection.commit()
            return _done({"id": load_id})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def plan_context(plan_id: int) -> Dict[str, Any]:
        """Данные, нужные для перепроверки ручной правки (ТЗ п.7)."""
        try:
            with DatabaseModel() as db:
                loads = _rows(_run(db,
                    "SELECT l.ID, l.SUPPLY_TRIP_ID, l.SECTION_ID, l.STATION_ID, "
                    "l.PRODUCT_CODE, l.VOLUME_L, l.UNLOAD_SEQ, p.FUEL_GROUP "
                    "FROM FLT_SUPPLY_LOADS l "
                    "JOIN FLT_SUPPLY_TRIPS st ON st.ID = l.SUPPLY_TRIP_ID "
                    "JOIN FLT_PRODUCTS p ON p.CODE = l.PRODUCT_CODE "
                    "WHERE st.PLAN_ID = :id", {"id": plan_id}))
                sections = _rows(_run(db,
                    "SELECT s.ID, s.TRUCK_ID, s.SEQ_NO, s.VOLUME_L "
                    "FROM FLT_TRUCK_SECTIONS s"))
                tanks = _rows(_run(db,
                    "SELECT STATION_ID, PRODUCT_CODE, ALLOWED_L, MAX_FILL_L, "
                    "CURRENT_L, IN_TRANSIT_L FROM V_FLT_TANK_STATE"))
            return _done({"loads": loads, "sections": sections, "tanks": tanks})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── превращение плана в рейсы (ТЗ п.9) ──────────────────────────

    @staticmethod
    def confirm_plan(plan_id: int, driver_by_truck: Dict[int, int],
                     end_point_id: Optional[int], start_point_id: Optional[int],
                     norm_km_by_trip: Dict[int, Optional[float]],
                     username: str) -> Dict[str, Any]:
        """Создаёт рейсы из утверждённого плана.

        Каждый предложенный рейс становится строкой FLT_TRIPS в статусе
        PLANNED со своими остановками и позициями. Плановый объём
        позиции — VOLUME_L, факт (загружено/документ/принято) заполняется
        позже по ходу исполнения.

        SOURCE = 'AUTO' (справочник допускает только AUTO/MANUAL), а
        происхождение рейса точнее показывает PLAN_ID: рейс из плана
        распределения всегда ссылается на свой расчёт, и по этой ссылке
        видно, каким именно набором чисел он обоснован.
        """
        try:
            created: List[int] = []
            with DatabaseModel() as db:
                head = _rows(_run(db, "SELECT STATUS_CODE FROM FLT_SUPPLY_PLANS "
                                      "WHERE ID = :id", {"id": plan_id}))
                if not head:
                    return _fail(f"План {plan_id} не найден")
                if head[0]["status_code"] == "CONFIRMED":
                    return _fail("План уже утверждён — повторное утверждение "
                                 "создало бы вторые рейсы на тот же объём")

                trips = _rows(_run(db,
                    "SELECT st.ID, st.TRUCK_ID, st.FUEL_GROUP, st.LOAD_POINT_ID, "
                    "lp.IS_FOREIGN FROM FLT_SUPPLY_TRIPS st "
                    "JOIN FLT_LOAD_POINTS lp ON lp.ID = st.LOAD_POINT_ID "
                    "WHERE st.PLAN_ID = :id ORDER BY st.SEQ_NO", {"id": plan_id}))
                for trip in trips:
                    driver_id = driver_by_truck.get(trip["truck_id"])
                    if driver_id is None:
                        return _fail(f"Для цистерны {trip['truck_id']} не выбран водитель")
                    trip_type = "IMPORT" if int(trip.get("is_foreign") or 0) else "DOMESTIC"
                    _run(db, "INSERT INTO FLT_TRIPS "
                             "(TRIP_DATE, TRUCK_ID, DRIVER_ID, TYPE_CODE, STATUS_CODE, "
                             " LOAD_POINT_ID, END_POINT_ID, START_POINT_ID, SOURCE, "
                             " NORM_KM, PLAN_ID, FUEL_GROUP) "
                             "VALUES (TRUNC(SYSDATE), :truck_id, :driver_id, :type_code, "
                             " 'PLANNED', :load_point_id, :end_point_id, :start_point_id, "
                             " 'AUTO', :norm_km, :plan_id, :fuel_group)",
                         {"truck_id": trip["truck_id"], "driver_id": driver_id,
                          "type_code": trip_type,
                          "load_point_id": trip["load_point_id"],
                          "end_point_id": end_point_id,
                          "start_point_id": start_point_id,
                          "norm_km": norm_km_by_trip.get(trip["id"]),
                          "plan_id": plan_id,
                          "fuel_group": trip.get("fuel_group")})
                    trip_id = _rows(_run(db, "SELECT MAX(ID) AS ID FROM FLT_TRIPS"))[0]["id"]
                    created.append(trip_id)
                    _run(db, "UPDATE FLT_SUPPLY_TRIPS SET TRIP_ID = :trip_id "
                             "WHERE ID = :id", {"trip_id": trip_id, "id": trip["id"]})

                    loads = _rows(_run(db,
                        "SELECT ID, SECTION_ID, STATION_ID, PRODUCT_CODE, VOLUME_L, "
                        "UNLOAD_SEQ FROM FLT_SUPPLY_LOADS WHERE SUPPLY_TRIP_ID = :id "
                        "ORDER BY UNLOAD_SEQ", {"id": trip["id"]}))
                    stop_by_station: Dict[Any, int] = {}
                    for load in loads:
                        station_id = load["station_id"]
                        if station_id not in stop_by_station:
                            seq = len(stop_by_station) + 1
                            _run(db, "INSERT INTO FLT_TRIP_STOPS (TRIP_ID, SEQ_NO, "
                                     "STATION_ID) VALUES (:trip_id, :seq_no, :station_id)",
                                 {"trip_id": trip_id, "seq_no": seq,
                                  "station_id": station_id})
                            stop_id = _rows(_run(db, "SELECT MAX(ID) AS ID FROM "
                                                     "FLT_TRIP_STOPS WHERE TRIP_ID = :t",
                                                 {"t": trip_id}))[0]["id"]
                            stop_by_station[station_id] = stop_id
                        _run(db, "INSERT INTO FLT_TRIP_STOP_ITEMS "
                                 "(STOP_ID, PRODUCT_CODE, VOLUME_L, SECTION_ID, UNLOAD_SEQ) "
                                 "VALUES (:stop_id, :product_code, :volume_l, "
                                 " :section_id, :unload_seq)",
                             {"stop_id": stop_by_station[station_id],
                              "product_code": load["product_code"],
                              "volume_l": load["volume_l"],
                              "section_id": load["section_id"],
                              "unload_seq": load["unload_seq"]})

                _run(db, "UPDATE FLT_SUPPLY_PLANS SET STATUS_CODE = 'CONFIRMED' "
                         "WHERE ID = :id", {"id": plan_id})
                db.connection.commit()
            return _done({"plan_id": plan_id, "trips": created})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── исполнение (ТЗ п.9) ─────────────────────────────────────────

    @staticmethod
    def set_trip_status(trip_id: int, status_code: str) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                known = _rows(_run(db, "SELECT CODE, SORT_NO FROM FLT_REF_TRIP_STATUS "
                                       "WHERE CODE = :code", {"code": status_code}))
                if not known:
                    return _fail(f"Неизвестный статус рейса: {status_code}")
                current = _rows(_run(db, "SELECT t.STATUS_CODE, s.SORT_NO "
                                         "FROM FLT_TRIPS t "
                                         "LEFT JOIN FLT_REF_TRIP_STATUS s ON s.CODE = t.STATUS_CODE "
                                         "WHERE t.ID = :id", {"id": trip_id}))
                if not current:
                    return _fail(f"Рейс {trip_id} не найден")
                r = _run(db, "UPDATE FLT_TRIPS SET STATUS_CODE = :code WHERE ID = :id",
                         {"code": status_code, "id": trip_id})
                if not r.get("rowcount"):
                    return _fail(f"Рейс {trip_id} не найден")
                db.connection.commit()
            return _done({"trip_id": trip_id, "status_code": status_code,
                          "previous": current[0].get("status_code")})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def set_item_fact(item_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Факт по позиции: загружено / по документу / принято АЗС (ТЗ п.9)."""
        params = {"id": item_id,
                  "loaded_l": payload.get("loaded_l"),
                  "doc_l": payload.get("doc_l"),
                  "accepted_l": payload.get("accepted_l")}
        try:
            with DatabaseModel() as db:
                r = _run(db, "UPDATE FLT_TRIP_STOP_ITEMS SET "
                             "LOADED_L = NVL(:loaded_l, LOADED_L), "
                             "DOC_L = NVL(:doc_l, DOC_L), "
                             "ACCEPTED_L = NVL(:accepted_l, ACCEPTED_L) "
                             "WHERE ID = :id", params)
                if not r.get("rowcount"):
                    return _fail(f"Позиция {item_id} не найдена")
                db.connection.commit()
            return _done(params)
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def execution_report(date_from, date_to, only_discrepancies: bool = False
                         ) -> Dict[str, Any]:
        sql = ("SELECT TRIP_ID, TRIP_DATE, STATUS_CODE, STATUS_NAME, STATUS_SORT, "
               "PLATE, DRIVER_NAME, STOP_SEQ, STATION_CODE, STATION_NAME, ITEM_ID, "
               "PRODUCT_CODE, PLAN_L, LOADED_L, DOC_L, ACCEPTED_L, UNLOAD_SEQ, "
               "DIFF_LOADED_L, DIFF_DOC_L, DIFF_ACCEPTED_L, HAS_DISCREPANCY "
               # Граница периода -- полуинтервал, а не BETWEEN: рейс, созданный
               # сегодня в 20:27, имеет время в DATE, и BETWEEN с датой-по
               # на полуночи его теряет. На демо-данных с полуночными датами
               # эта ошибка не проявлялась -- вылезла на первом же живом
               # рейсе, созданном из плана.
               "FROM V_FLT_TRIP_EXECUTION "
               "WHERE TRIP_DATE >= :date_from AND TRIP_DATE < :date_to + 1")
        if only_discrepancies:
            sql += " AND HAS_DISCREPANCY = 1"
        sql += " ORDER BY TRIP_DATE DESC, TRIP_ID, STOP_SEQ, UNLOAD_SEQ"
        try:
            with DatabaseModel() as db:
                return _done(_rows(_run(db, sql, {"date_from": date_from,
                                                  "date_to": date_to})))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def supply_settings() -> Dict[str, Any]:
        """Настройки контура распределения (ТЗ п.4.2, п.6, п.9)."""
        try:
            with DatabaseModel() as db:
                rows = _rows(_run(db, "SELECT MAX_COVER_DAYS, PLAN_HORIZON_DAYS, "
                                      "GROUP_MIN_STATIONS, GROUP_MAX_STATIONS, "
                                      "VOLUME_DIFF_PCT, SAFETY_DAYS, RATE_PER_KM, "
                                      "TRIP_BONUS FROM FLT_SETTINGS WHERE ID = 1"))
                if not rows:
                    return _fail("Настройки модуля не найдены (ID=1)")
                return _done(rows[0])
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def update_supply_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
        params = {"max_cover_days": payload.get("max_cover_days"),
                  "plan_horizon_days": payload.get("plan_horizon_days"),
                  "group_min_stations": payload.get("group_min_stations"),
                  "group_max_stations": payload.get("group_max_stations"),
                  "volume_diff_pct": payload.get("volume_diff_pct")}
        try:
            with DatabaseModel() as db:
                r = _run(db, "UPDATE FLT_SETTINGS SET "
                             "MAX_COVER_DAYS = :max_cover_days, "
                             "PLAN_HORIZON_DAYS = :plan_horizon_days, "
                             "GROUP_MIN_STATIONS = :group_min_stations, "
                             "GROUP_MAX_STATIONS = :group_max_stations, "
                             "VOLUME_DIFF_PCT = :volume_diff_pct "
                             "WHERE ID = 1", params)
                if not r.get("rowcount"):
                    return _fail("Настройки модуля не найдены (ID=1)")
                db.connection.commit()
            return _done(params)
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── экономика перевозки (ТЗ автопарка, отчёт руководству) ───────

    @staticmethod
    def trips_economics(date_from, date_to) -> Dict[str, Any]:
        """Рейсы периода с объёмом, нормой и фактом расхода.

        Объём считается ОТДЕЛЬНЫМ подзапросом, а не join'ом к позициям:
        рейс с тремя остановками дал бы три строки, и расход топлива
        просуммировался бы трижды (та же грабля описана в store.py у
        truck_summary).
        """
        try:
            with DatabaseModel() as db:
                r = _run(db, """
                    SELECT t.ID AS TRIP_ID, t.TRIP_DATE, t.STATUS_CODE,
                           t.NORM_KM, t.FACT_KM, t.FACT_FUEL_L,
                           tr.CAPACITY_L,
                           t.NORM_KM * tr.NORM_L_PER_100KM / 100 AS NORM_FUEL_L,
                           NVL(vol.VOLUME_L, 0) AS VOLUME_L,
                           NVL(pay.TOTAL_PAY, 0) AS PAY
                      FROM FLT_TRIPS t
                      JOIN FLT_TRUCKS tr ON tr.ID = t.TRUCK_ID
                      LEFT JOIN (SELECT s.TRIP_ID, SUM(i.VOLUME_L) AS VOLUME_L
                                   FROM FLT_TRIP_STOPS s
                                   JOIN FLT_TRIP_STOP_ITEMS i ON i.STOP_ID = s.ID
                                  GROUP BY s.TRIP_ID) vol ON vol.TRIP_ID = t.ID
                      LEFT JOIN V_FLT_TRIP_PAY pay ON pay.TRIP_ID = t.ID
                     WHERE t.TRIP_DATE >= :date_from AND t.TRIP_DATE < :date_to + 1
                       AND t.STATUS_CODE <> 'DRAFT'""",
                        {"date_from": date_from, "date_to": date_to})
                return _done(_rows(r))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def diesel_price(on_date) -> Dict[str, Any]:
        """Цена дизеля на дату (или ближайшая более ранняя)."""
        try:
            with DatabaseModel() as db:
                rows = _rows(_run(db,
                    "SELECT PRICE_LEI, PRICE_DATE FROM FLT_FUEL_PRICES "
                    "WHERE PRODUCT_CODE = 'DIESEL' AND PRICE_DATE <= :d "
                    "ORDER BY PRICE_DATE DESC FETCH FIRST 1 ROWS ONLY",
                    {"d": on_date}))
                return _done(rows[0] if rows else None)
        except AutoparkSqlError as exc:
            return _fail(str(exc))
