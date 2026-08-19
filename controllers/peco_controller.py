"""Контроллер модуля PECO — розничная продажа топлива в сети АЗС.

Спецификация: docs/superpowers/specs/2026-08-19-peco-fuel-retail-design.md
Oracle-объекты: префикс PECO_ (sql/100_peco_tables.sql ... 104_peco_ref_data.sql;
демо-станция sql/105_peco_demo_station.sql — отдельно, не для production).

Слой отвечает только за приём запроса, проверку полей и формирование
ответа. Бизнес-правила живут в models/peco_shift.py, models/peco_txn.py
и models/peco_inventory.py.
"""
import math
import os
import sys
from typing import Any, Dict, List, Optional

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.peco_oracle_store import PecoStore
from models import peco_shift, peco_txn, peco_inventory


def _require(payload: Dict[str, Any], *names: str) -> Optional[str]:
    """Возвращает имя первого отсутствующего поля или None."""
    for n in names:
        if payload.get(n) in (None, ""):
            return n
    return None


class PecoInputError(Exception):
    """Некорректное значение поля во входящем запросе."""


def _as_int(payload: Dict[str, Any], name: str) -> int:
    """Целое из запроса. Клиент может прислать что угодно — строку, null,
    список; это ошибка запроса, а не сбой сервера."""
    try:
        return int(payload[name])
    except (TypeError, ValueError, KeyError):
        raise PecoInputError(f"Некорректное значение поля: {name}")


def _as_float(payload: Dict[str, Any], name: str) -> float:
    """Дробное из запроса. Бесконечность и NaN отбрасываются: они прошли бы
    арифметику сверки молча и испортили бы расхождения смены."""
    try:
        value = float(payload[name])
    except (TypeError, ValueError, KeyError):
        raise PecoInputError(f"Некорректное значение поля: {name}")
    if not math.isfinite(value):
        raise PecoInputError(f"Некорректное значение поля: {name}")
    return value


class PecoController:
    """Маршрутная логика фронт-офиса, консоли смены и бэк-офиса."""

    # ---------------- фронт-офис колонки ----------------

    @staticmethod
    def pump_state(station_id: int) -> Dict[str, Any]:
        """Состояние станции для экрана колонки: смена, пистолеты, цены."""
        shift_r = PecoStore.get_open_shift(station_id)
        if not shift_r.get("success"):
            return {"success": False,
                    "error": "Нет открытой смены — отпуск невозможен"}

        nozzles_r = PecoStore.list_nozzles(station_id)
        if not nozzles_r.get("success"):
            return nozzles_r

        grades_r = PecoStore.list_grades()
        grades = grades_r.get("items", []) if grades_r.get("success") else []

        # Сорт, чью цену не удалось прочитать, не должен молча исчезать из
        # prices: это выглядело бы так же, как сорт без действующей цены
        # вовсе, а колонка узнаёт об отказе БД только через отсутствие цены.
        # unavailable_prices делает разницу видимой вызывающему.
        prices: Dict[str, float] = {}
        unavailable_prices: List[str] = []
        for g in grades:
            p = PecoStore.current_price(station_id, g["code"])
            if p.get("success"):
                prices[g["code"]] = p["price"]
            else:
                unavailable_prices.append(g["code"])

        result: Dict[str, Any] = {
            "success": True,
            "station_id": station_id,
            "shift_id": shift_r["shift"]["id"],
            "nozzles": nozzles_r["items"],
            "grades": grades,
            "prices": prices,
        }
        if unavailable_prices:
            result["unavailable_prices"] = unavailable_prices
        return result

    @staticmethod
    def authorize(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "nozzle_id", "shift_id",
                           "grade_code", "meter_start")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}

        # mia_ref обязателен только для самообслуживания — эту проверку
        # делает сама модель (peco_txn.authorize), контроллер лишь
        # прокидывает значение, если оно пришло в запросе.
        try:
            # employee_id необязателен (кассир не участвует при
            # самообслуживании), но если он пришёл, обязан пройти через
            # тот же _as_int, что и остальные числовые поля — иначе
            # JSON-строка вместо числа доезжает до Oracle и падает
            # необработанным ORA-01722 вместо доменной ошибки запроса.
            employee_id = (_as_int(payload, "employee_id")
                          if payload.get("employee_id") is not None else None)
            return peco_txn.authorize(
                shift_id=_as_int(payload, "shift_id"),
                nozzle_id=_as_int(payload, "nozzle_id"),
                grade_code=payload["grade_code"],
                station_id=_as_int(payload, "station_id"),
                meter_start=_as_float(payload, "meter_start"),
                is_self_service=bool(payload.get("is_self_service")),
                employee_id=employee_id,
                mia_ref=payload.get("mia_ref"),
            )
        except PecoInputError as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def start(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        try:
            return peco_txn.start_dispense(_as_int(payload, "txn_id"))
        except PecoInputError as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def finish(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id", "meter_end")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        try:
            return peco_txn.finish_dispense(_as_int(payload, "txn_id"),
                                            _as_float(payload, "meter_end"))
        except PecoInputError as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def pay(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id", "pay_method")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        try:
            return peco_txn.settle(
                _as_int(payload, "txn_id"),
                pay_method=payload["pay_method"],
                mia_ref=payload.get("mia_ref"),
            )
        except PecoInputError as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def void(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        try:
            return peco_txn.void(_as_int(payload, "txn_id"),
                                 reason=payload.get("reason") or "не указана")
        except PecoInputError as e:
            return {"success": False, "error": str(e)}

    # ---------------- консоль смены ----------------

    @staticmethod
    def shift_open(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "employee_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        try:
            return peco_shift.open_shift(_as_int(payload, "station_id"),
                                         _as_int(payload, "employee_id"))
        except PecoInputError as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shift_meters(shift_id: int) -> Dict[str, Any]:
        return PecoStore.get_shift_meters(shift_id)

    @staticmethod
    def shift_save_meter(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "shift_id", "nozzle_id", "meter_close")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        try:
            return PecoStore.save_meter_close(
                _as_int(payload, "shift_id"), _as_int(payload, "nozzle_id"),
                _as_float(payload, "meter_close"),
            )
        except PecoInputError as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shift_close(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Закрывает смену. dips — замеры НА ЗАКРЫТИЕ {tank_id: литры};
        остаток на открытие и приход за смену модель читает из БД сама —
        иначе оператор мог бы объявить удобные исходные цифры и обнулить
        любое расхождение."""
        missing = _require(payload, "shift_id", "employee_id", "cash_declared")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        try:
            raw_dips = payload.get("dips") or {}
            if not isinstance(raw_dips, dict):
                return {"success": False, "error": "Некорректное значение поля: dips"}
            dips: Dict[int, float] = {}
            for key, value in raw_dips.items():
                try:
                    tank = _as_int({"tank_id": key}, "tank_id")
                    litres = _as_float({"dip": value}, "dip")
                except PecoInputError:
                    return {"success": False, "error": "Некорректное значение поля: dips"}
                dips[tank] = litres

            return peco_shift.close_shift(
                _as_int(payload, "shift_id"),
                employee_id=_as_int(payload, "employee_id"),
                cash_declared=_as_float(payload, "cash_declared"),
                dips=dips,
            )
        except PecoInputError as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shift_approve(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Подтверждение смены с расхождением менеджером/админом по PIN.

        PIN нигде здесь не логируется, не эхируется в ответе и не попадает
        в сообщение об ошибке — только имя отсутствующего поля."""
        missing = _require(payload, "shift_id", "manager_id", "pin")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        try:
            return peco_shift.approve_disputed(
                _as_int(payload, "shift_id"), _as_int(payload, "manager_id"),
                str(payload["pin"]),
            )
        except PecoInputError as e:
            return {"success": False, "error": str(e)}

    # ---------------- склад ----------------

    @staticmethod
    def delivery_receive(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "supplier", "waybill_no",
                           "employee_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        items: List[Dict[str, Any]] = payload.get("items") or []
        try:
            return peco_inventory.receive_delivery(
                station_id=_as_int(payload, "station_id"),
                supplier=payload["supplier"],
                waybill_no=payload["waybill_no"],
                items=items,
                employee_id=_as_int(payload, "employee_id"),
                driver_name=payload.get("driver_name"),
                vehicle_no=payload.get("vehicle_no"),
            )
        except PecoInputError as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def tank_levels(station_id: int) -> Dict[str, Any]:
        return peco_inventory.tank_levels(station_id)

    @staticmethod
    def default_station_id() -> Dict[str, Any]:
        return PecoStore.default_station_id()

    @staticmethod
    def prices(station_id: int) -> Dict[str, Any]:
        return PecoStore.list_prices(station_id)

    # ---------------- бэк-офис ----------------

    @staticmethod
    def admin_overview() -> Dict[str, Any]:
        """Сводка по сети: станции и резервуары с низким уровнем.

        Обходит все станции сети (46 АЗС) и для каждой отдельно читает
        уровни резервуаров — N+1 запросов на один вызов. Оставлено как в
        спецификации; при росте сети или частых вызовах стоит рассмотреть
        один агрегирующий запрос вместо цикла PecoStore.list_tank_levels.
        """
        stations_r = PecoStore.list_stations()
        if not stations_r.get("success"):
            return stations_r

        low: List[Dict[str, Any]] = []
        # Станция, чьи резервуары не удалось прочитать, обязана быть видна
        # отдельно: "continue" без следа делает сбой чтения неотличимым от
        # "у станции нет резервуаров с низким уровнем" — а это ложное
        # спокойствие ровно там, где нужен сигнал "не проверено".
        unavailable_stations: List[Any] = []
        for st in stations_r["items"]:
            levels = PecoStore.list_tank_levels(st["id"])
            if not levels.get("success"):
                unavailable_stations.append(st["id"])
                continue
            for t in levels["items"]:
                if int(t.get("is_low") or 0) == 1:
                    low.append(dict(t, station_name=st["name"]))

        result: Dict[str, Any] = {"success": True, "stations": stations_r["items"],
                                  "low_tanks": low}
        if unavailable_stations:
            result["unavailable_stations"] = unavailable_stations
        return result

    @staticmethod
    def set_price(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "grade_code", "price")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        try:
            return PecoStore.set_price(_as_int(payload, "station_id"),
                                       payload["grade_code"],
                                       _as_float(payload, "price"))
        except PecoInputError as e:
            return {"success": False, "error": str(e)}
