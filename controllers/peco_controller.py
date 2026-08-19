"""Контроллер модуля PECO — розничная продажа топлива в сети АЗС.

Спецификация: docs/superpowers/specs/2026-08-19-peco-fuel-retail-design.md
Oracle-объекты: префикс PECO_ (sql/100_peco_tables.sql ... 104_peco_demo_data.sql).

Слой отвечает только за приём запроса, проверку полей и формирование
ответа. Бизнес-правила живут в models/peco_shift.py, models/peco_txn.py
и models/peco_inventory.py.
"""
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

        prices: Dict[str, float] = {}
        for g in grades:
            p = PecoStore.current_price(station_id, g["code"])
            if p.get("success"):
                prices[g["code"]] = p["price"]

        return {
            "success": True,
            "station_id": station_id,
            "shift_id": shift_r["shift"]["id"],
            "nozzles": nozzles_r["items"],
            "grades": grades,
            "prices": prices,
        }

    @staticmethod
    def authorize(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "shift_id", "nozzle_id",
                           "grade_code", "meter_start")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}

        # mia_ref обязателен только для самообслуживания — эту проверку
        # делает сама модель (peco_txn.authorize), контроллер лишь
        # прокидывает значение, если оно пришло в запросе.
        return peco_txn.authorize(
            shift_id=int(payload["shift_id"]),
            nozzle_id=int(payload["nozzle_id"]),
            grade_code=payload["grade_code"],
            station_id=int(payload["station_id"]),
            meter_start=float(payload["meter_start"]),
            is_self_service=bool(payload.get("is_self_service")),
            employee_id=payload.get("employee_id"),
            mia_ref=payload.get("mia_ref"),
        )

    @staticmethod
    def start(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_txn.start_dispense(int(payload["txn_id"]))

    @staticmethod
    def finish(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id", "meter_end")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_txn.finish_dispense(int(payload["txn_id"]),
                                        float(payload["meter_end"]))

    @staticmethod
    def pay(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id", "pay_method")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_txn.settle(
            int(payload["txn_id"]),
            pay_method=payload["pay_method"],
            mia_ref=payload.get("mia_ref"),
        )

    @staticmethod
    def void(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_txn.void(int(payload["txn_id"]),
                             reason=payload.get("reason") or "не указана")

    # ---------------- консоль смены ----------------

    @staticmethod
    def shift_open(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "employee_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_shift.open_shift(int(payload["station_id"]),
                                     int(payload["employee_id"]))

    @staticmethod
    def shift_meters(shift_id: int) -> Dict[str, Any]:
        return PecoStore.get_shift_meters(shift_id)

    @staticmethod
    def shift_save_meter(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "shift_id", "nozzle_id", "meter_close")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return PecoStore.save_meter_close(
            int(payload["shift_id"]), int(payload["nozzle_id"]),
            float(payload["meter_close"]),
        )

    @staticmethod
    def shift_close(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Закрывает смену. dips — замеры НА ЗАКРЫТИЕ {tank_id: литры};
        остаток на открытие и приход за смену модель читает из БД сама —
        иначе оператор мог бы объявить удобные исходные цифры и обнулить
        любое расхождение."""
        missing = _require(payload, "shift_id", "employee_id", "cash_declared")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_shift.close_shift(
            int(payload["shift_id"]),
            employee_id=int(payload["employee_id"]),
            cash_declared=float(payload["cash_declared"]),
            dips={int(k): float(v) for k, v in (payload.get("dips") or {}).items()},
        )

    @staticmethod
    def shift_approve(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Подтверждение смены с расхождением менеджером/админом по PIN.

        PIN нигде здесь не логируется, не эхируется в ответе и не попадает
        в сообщение об ошибке — только имя отсутствующего поля."""
        missing = _require(payload, "shift_id", "manager_id", "pin")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_shift.approve_disputed(
            int(payload["shift_id"]), int(payload["manager_id"]),
            str(payload["pin"]),
        )

    # ---------------- склад ----------------

    @staticmethod
    def delivery_receive(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "supplier", "waybill_no",
                           "employee_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        items: List[Dict[str, Any]] = payload.get("items") or []
        return peco_inventory.receive_delivery(
            station_id=int(payload["station_id"]),
            supplier=payload["supplier"],
            waybill_no=payload["waybill_no"],
            items=items,
            employee_id=int(payload["employee_id"]),
            driver_name=payload.get("driver_name"),
            vehicle_no=payload.get("vehicle_no"),
        )

    @staticmethod
    def tank_levels(station_id: int) -> Dict[str, Any]:
        return peco_inventory.tank_levels(station_id)

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
        for st in stations_r["items"]:
            levels = PecoStore.list_tank_levels(st["id"])
            if not levels.get("success"):
                continue
            for t in levels["items"]:
                if int(t.get("is_low") or 0) == 1:
                    low.append(dict(t, station_name=st["name"]))

        return {"success": True, "stations": stations_r["items"],
                "low_tanks": low}

    @staticmethod
    def set_price(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "grade_code", "price")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return PecoStore.set_price(int(payload["station_id"]),
                                   payload["grade_code"],
                                   float(payload["price"]))
