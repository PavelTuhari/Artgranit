"""Autopark — persistence параметров по периодам (админка заказчика).

Отдельный файл от `supply_store.py`: там поток «остатки → план → рейсы»,
здесь — справочные настройки, которые заказчик правит сам. Разделение
не стилистическое: правило №2 проекта требует, чтобы своя логика лежала
в своём файле, и чем мельче файл, тем меньше шансов потерять его при
параллельной правке.

Все таблицы контура периодов однотипны, поэтому CRUD написан один раз и
параметризован описанием таблицы (`SPECS`), а не скопирован пять раз.
Описание закрытое: имена таблиц и колонок берутся только отсюда, в SQL
не попадает ничего из запроса пользователя.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.database import DatabaseModel
from modules.autopark.store import AutoparkSqlError, _done, _fail, _rows, _run


class Spec:
    """Описание таблицы периодов: как её читать, писать и к чему привязана."""

    def __init__(self, table: str, columns: List[str],
                 owner_column: Optional[str] = None,
                 order_by: str = "VALID_FROM DESC, ID DESC",
                 extra_select: str = ""):
        self.table = table
        self.columns = columns
        self.owner_column = owner_column
        self.order_by = order_by
        self.extra_select = extra_select


SPECS: Dict[str, Spec] = {
    # Ставка за километр и доплата за рейс.
    "rates": Spec("FLT_RATE_PERIODS", ["RATE_PER_KM", "TRIP_BONUS", "NOTE"]),
    # Параметры планирования: потолок запаса в днях, горизонт, размер группы.
    "params": Spec("FLT_SUPPLY_PARAMS",
                   ["MAX_COVER_DAYS", "PLAN_HORIZON_DAYS", "GROUP_MIN_STATIONS",
                    "GROUP_MAX_STATIONS", "VOLUME_DIFF_PCT", "NOTE"]),
    # Лимиты конкретного резервуара.
    "tank_limits": Spec("FLT_TANK_LIMITS",
                        ["MIN_STOCK_L", "MAX_FILL_L", "MAX_COVER_DAYS", "NOTE"],
                        owner_column="TANK_ID",
                        order_by="TANK_ID, VALID_FROM DESC, ID DESC"),
}


class PeriodsStore:
    """Чтение и запись строк с периодом действия."""

    @staticmethod
    def list(kind: str, owner_id: Optional[int] = None) -> Dict[str, Any]:
        spec = SPECS[kind]
        cols = ["ID", "VALID_FROM", "VALID_TO"] + spec.columns + ["CREATED_AT", "CREATED_BY"]
        if spec.owner_column:
            cols.insert(1, spec.owner_column)
        sql = f"SELECT {', '.join(cols)}{spec.extra_select} FROM {spec.table}"
        params: Dict[str, Any] = {}
        if spec.owner_column and owner_id is not None:
            sql += f" WHERE {spec.owner_column} = :owner_id"
            params["owner_id"] = owner_id
        sql += f" ORDER BY {spec.order_by}"
        try:
            with DatabaseModel() as db:
                return _done(_rows(_run(db, sql, params or None)))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def save(kind: str, payload: Dict[str, Any], username: str,
             close_previous: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Создаёт или правит строку периода.

        ``close_previous`` — строки, которые нужно закрыть днём раньше
        нового периода (их вычисляет `periods.close_open_period`). Это
        делается в ОДНОЙ транзакции с записью: иначе при сбое между
        двумя операциями в базе остались бы два открытых периода, то есть
        ровно то состояние, которое вся эта механика и запрещает.
        """
        spec = SPECS[kind]
        row_id = payload.get("id")
        values = {c.lower(): payload.get(c.lower()) for c in spec.columns}
        values["valid_from"] = payload.get("valid_from")
        values["valid_to"] = payload.get("valid_to")
        if spec.owner_column:
            values[spec.owner_column.lower()] = payload.get(spec.owner_column.lower())
        try:
            with DatabaseModel() as db:
                for closing in (close_previous or []):
                    _run(db, f"UPDATE {spec.table} SET VALID_TO = :valid_to WHERE ID = :id",
                         {"valid_to": closing["valid_to"], "id": closing["id"]})
                if row_id:
                    sets = ", ".join(f"{c} = :{c.lower()}" for c in
                                     (["VALID_FROM", "VALID_TO"] + spec.columns))
                    values["id"] = row_id
                    r = _run(db, f"UPDATE {spec.table} SET {sets} WHERE ID = :id", values)
                    if not r.get("rowcount"):
                        return _fail(f"Период {row_id} не найден")
                else:
                    cols = ["VALID_FROM", "VALID_TO"] + spec.columns + ["CREATED_BY"]
                    if spec.owner_column:
                        cols.insert(0, spec.owner_column)
                    values["created_by"] = username
                    binds = ", ".join(":" + c.lower() for c in cols)
                    _run(db, f"INSERT INTO {spec.table} ({', '.join(cols)}) "
                             f"VALUES ({binds})", values)
                    row_id = _rows(_run(db, f"SELECT MAX(ID) AS ID FROM {spec.table}"))[0]["id"]
                db.connection.commit()
            return _done({"id": row_id})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def delete(kind: str, row_id: int) -> Dict[str, Any]:
        spec = SPECS[kind]
        try:
            with DatabaseModel() as db:
                r = _run(db, f"DELETE FROM {spec.table} WHERE ID = :id", {"id": row_id})
                if not r.get("rowcount"):
                    return _fail(f"Период {row_id} не найден")
                db.connection.commit()
            return _done({"id": row_id})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    # ── отсеки и группы: у них период живёт прямо в строке ──────────

    @staticmethod
    def sections(truck_id: Optional[int] = None) -> Dict[str, Any]:
        sql = ("SELECT s.ID, s.TRUCK_ID, t.PLATE, s.SEQ_NO, s.VOLUME_L, s.ACTIVE, "
               "s.VALID_FROM, s.VALID_TO "
               "FROM FLT_TRUCK_SECTIONS s JOIN FLT_TRUCKS t ON t.ID = s.TRUCK_ID")
        params: Dict[str, Any] = {}
        if truck_id is not None:
            sql += " WHERE s.TRUCK_ID = :truck_id"
            params["truck_id"] = truck_id
        sql += " ORDER BY s.TRUCK_ID, s.VALID_FROM NULLS FIRST, s.SEQ_NO"
        try:
            with DatabaseModel() as db:
                return _done(_rows(_run(db, sql, params or None)))
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def save_sections(truck_id: int, sections: List[Dict[str, Any]],
                      valid_from, valid_to) -> Dict[str, Any]:
        """Новая конфигурация отсеков цистерны с даты.

        Прежняя конфигурация не удаляется, а закрывается днём раньше:
        планы, посчитанные на старых отсеках, должны остаться
        объяснимыми. Именно поэтому здесь нет DELETE — в отличие от
        первой версии, где смена отсеков стирала историю и запрещалась,
        если отсек уже участвовал в плане.
        """
        from datetime import timedelta
        try:
            with DatabaseModel() as db:
                if valid_from:
                    _run(db, "UPDATE FLT_TRUCK_SECTIONS SET VALID_TO = :prev_to "
                             "WHERE TRUCK_ID = :truck_id AND VALID_TO IS NULL "
                             "AND (VALID_FROM IS NULL OR VALID_FROM < :valid_from)",
                         {"prev_to": valid_from - timedelta(days=1),
                          "truck_id": truck_id, "valid_from": valid_from})
                else:
                    _run(db, "DELETE FROM FLT_TRUCK_SECTIONS WHERE TRUCK_ID = :truck_id "
                             "AND NOT EXISTS (SELECT 1 FROM FLT_SUPPLY_LOADS l "
                             "                 WHERE l.SECTION_ID = FLT_TRUCK_SECTIONS.ID)",
                         {"truck_id": truck_id})
                for idx, sec in enumerate(sections, start=1):
                    _run(db, "INSERT INTO FLT_TRUCK_SECTIONS "
                             "(TRUCK_ID, SEQ_NO, VOLUME_L, VALID_FROM, VALID_TO) "
                             "VALUES (:truck_id, :seq_no, :volume_l, :valid_from, :valid_to)",
                         {"truck_id": truck_id, "seq_no": sec.get("seq_no") or idx,
                          "volume_l": sec.get("volume_l"),
                          "valid_from": valid_from, "valid_to": valid_to})
                db.connection.commit()
            return _done({"truck_id": truck_id, "sections": len(sections)})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def groups(include_history: bool = True) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                groups = _rows(_run(db, "SELECT ID, CODE, NAME, ACTIVE "
                                        "FROM FLT_STATION_GROUPS ORDER BY CODE"))
                items = _rows(_run(db,
                    "SELECT i.GROUP_ID, i.STATION_ID, i.SEQ_NO, i.VALID_FROM, i.VALID_TO, "
                    "s.CODE AS STATION_CODE, s.NAME AS STATION_NAME "
                    "FROM FLT_STATION_GROUP_ITEMS i "
                    "JOIN FLT_STATIONS s ON s.ID = i.STATION_ID "
                    "ORDER BY i.GROUP_ID, i.VALID_FROM NULLS FIRST, i.SEQ_NO"))
            by_group: Dict[Any, List[Dict[str, Any]]] = {}
            for it in items:
                by_group.setdefault(it["group_id"], []).append(it)
            for g in groups:
                g["items"] = by_group.get(g["id"], [])
                g["station_ids"] = [i["station_id"] for i in g["items"]]
            _ = include_history
            return _done(groups)
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def save_group_period(group_id: int, station_ids: List[int],
                          valid_from, valid_to) -> Dict[str, Any]:
        """Состав группы АЗС на период.

        Прежний состав закрывается днём раньше — по той же причине, что и
        отсеки: план, собранный на старом составе, должен остаться
        объяснимым.
        """
        from datetime import timedelta
        try:
            with DatabaseModel() as db:
                if valid_from:
                    _run(db, "UPDATE FLT_STATION_GROUP_ITEMS SET VALID_TO = :prev_to "
                             "WHERE GROUP_ID = :group_id AND VALID_TO IS NULL "
                             "AND (VALID_FROM IS NULL OR VALID_FROM < :valid_from)",
                         {"prev_to": valid_from - timedelta(days=1),
                          "group_id": group_id, "valid_from": valid_from})
                else:
                    _run(db, "DELETE FROM FLT_STATION_GROUP_ITEMS WHERE GROUP_ID = :group_id",
                         {"group_id": group_id})
                for seq, station_id in enumerate(station_ids, 1):
                    _run(db, "INSERT INTO FLT_STATION_GROUP_ITEMS "
                             "(GROUP_ID, STATION_ID, SEQ_NO, VALID_FROM, VALID_TO) "
                             "VALUES (:group_id, :station_id, :seq_no, :valid_from, :valid_to)",
                         {"group_id": group_id, "station_id": station_id, "seq_no": seq,
                          "valid_from": valid_from, "valid_to": valid_to})
                db.connection.commit()
            return _done({"group_id": group_id, "stations": len(station_ids)})
        except AutoparkSqlError as exc:
            return _fail(str(exc))

    @staticmethod
    def effective_params(on_date) -> Dict[str, Any]:
        """Параметры планирования на дату + ставка на ту же дату."""
        try:
            with DatabaseModel() as db:
                params = _rows(_run(db,
                    "SELECT ID, VALID_FROM, VALID_TO, MAX_COVER_DAYS, PLAN_HORIZON_DAYS, "
                    "GROUP_MIN_STATIONS, GROUP_MAX_STATIONS, VOLUME_DIFF_PCT "
                    "FROM FLT_SUPPLY_PARAMS "
                    "WHERE VALID_FROM <= :d AND (VALID_TO IS NULL OR VALID_TO >= :d) "
                    "ORDER BY VALID_FROM DESC, ID DESC FETCH FIRST 1 ROWS ONLY",
                    {"d": on_date}))
                rate = _rows(_run(db,
                    "SELECT ID, VALID_FROM, VALID_TO, RATE_PER_KM, TRIP_BONUS "
                    "FROM FLT_RATE_PERIODS "
                    "WHERE VALID_FROM <= :d AND (VALID_TO IS NULL OR VALID_TO >= :d) "
                    "ORDER BY VALID_FROM DESC, ID DESC FETCH FIRST 1 ROWS ONLY",
                    {"d": on_date}))
            return _done({"params": params[0] if params else None,
                          "rate": rate[0] if rate else None})
        except AutoparkSqlError as exc:
            return _fail(str(exc))
