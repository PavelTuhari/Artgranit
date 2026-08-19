"""PECO: складской контур — приход цистерн, замеры, остатки резервуаров.

Реестр резервуара ведётся по формуле
    остаток = предыдущий остаток + принято − отпущено по счётчику
с периодической корректировкой ручными замерами (PECO_TANK_DIPS).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.peco_oracle_store import PecoStore


def shortfall(liters_doc: float, liters_recv: float) -> float:
    """Недолив: положительное значение = приняли меньше, чем по накладной."""
    return round(float(liters_doc) - float(liters_recv), 3)


def receive_delivery(
    station_id: int,
    supplier: str,
    waybill_no: str,
    items: List[Dict[str, Any]],
    employee_id: int,
    driver_name: Optional[str] = None,
    vehicle_no: Optional[str] = None,
) -> Dict[str, Any]:
    """Принимает цистерну: шапка + строки по резервуарам.

    Остаток резервуара растёт на ФАКТИЧЕСКИ принятый объём, а не на
    документальный: иначе недолив осел бы в учёте как наличное топливо
    и всплыл позже как необъяснимая утечка.

    Персистенция (шапка, строки, остатки резервуаров, реестр смены, замер)
    выполняется одним вызовом PecoStore.apply_delivery — одной транзакцией
    с одним commit. Раньше это были отдельные вызовы store с отдельными
    коммитами: сбой на середине списка строк оставлял резервуары уже
    зачисленными по накладной, которую не довели до конца, а уникальность
    (STATION_ID, WAYBILL_NO) не давала повторить приём начисто под той же
    накладной — повторная отправка под новой накладной удваивала зачисление.
    """
    if not items:
        return {"success": False, "error": "Не указано ни одной строки прихода"}

    total_shortfall = 0.0
    shortfalls = []
    for it in items:
        liters_doc = float(it.get("liters_doc") or 0.0)
        liters_recv = float(it.get("liters_recv") or 0.0)
        sf = shortfall(liters_doc, liters_recv)
        total_shortfall += sf
        # Чистая сумма (total_shortfall) складывает недостачи и излишки
        # алгебраически и может дать ноль, спрятав реальную недостачу в
        # одном резервуаре за излишком в другом. Поэтому недостачу каждой
        # строки репортим отдельно, а не только суммарно.
        if sf != 0:
            shortfalls.append({"tank_id": it["tank_id"],
                               "grade_code": it["grade_code"],
                               "shortfall": sf})

    applied = PecoStore.apply_delivery(
        station_id=station_id, supplier=supplier, waybill_no=waybill_no,
        items=items, employee_id=employee_id,
        driver_name=driver_name, vehicle_no=vehicle_no,
    )
    if not applied.get("success"):
        return applied
    delivery_id = applied["delivery_id"]

    result = {"success": True, "delivery_id": delivery_id,
              "total_shortfall": round(total_shortfall, 3),
              "shortfalls": shortfalls}

    logged = PecoStore.log_event(
        "DELIVERY_RECEIVED", station_id=station_id, entity_type="DELIVERY",
        entity_id=delivery_id, employee_id=employee_id,
        payload={"waybill": waybill_no, "items": len(items),
                 "shortfall": round(total_shortfall, 3)},
    )
    if not logged.get("success"):
        result["audit_warning"] = logged.get("error")

    return result


def record_dip(tank_id: int, measured_l: float, dip_kind: str,
               shift_id: Optional[int] = None,
               employee_id: Optional[int] = None) -> Dict[str, Any]:
    """Фиксирует ручной замер уровня."""
    if dip_kind not in ("OPEN", "CLOSE", "DELIVERY", "CONTROL"):
        return {"success": False, "error": f"Неизвестный тип замера: {dip_kind}"}
    return PecoStore.insert_tank_dip(
        tank_id=tank_id, measured_l=measured_l, dip_kind=dip_kind,
        shift_id=shift_id, employee_id=employee_id,
    )


def tank_levels(station_id: int) -> Dict[str, Any]:
    """Остатки резервуаров станции с признаком низкого уровня."""
    return PecoStore.list_tank_levels(station_id)
