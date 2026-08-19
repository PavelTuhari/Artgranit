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
    """
    if not items:
        return {"success": False, "error": "Не указано ни одной строки прихода"}

    header = PecoStore.insert_delivery(
        station_id=station_id, supplier=supplier, waybill_no=waybill_no,
        driver_name=driver_name, vehicle_no=vehicle_no,
    )
    if not header.get("success"):
        return header
    delivery_id = header["delivery_id"]

    total_shortfall = 0.0
    for it in items:
        liters_doc = float(it.get("liters_doc") or 0.0)
        liters_recv = float(it.get("liters_recv") or 0.0)
        total_shortfall += shortfall(liters_doc, liters_recv)

        saved = PecoStore.insert_delivery_item(
            delivery_id=delivery_id,
            tank_id=it["tank_id"],
            grade_code=it["grade_code"],
            liters_doc=liters_doc,
            liters_recv=liters_recv,
            temperature_c=it.get("temperature_c"),
            dip_before=it.get("dip_before"),
            dip_after=it.get("dip_after"),
        )
        if not saved.get("success"):
            return saved

        added = PecoStore.add_tank_volume(tank_id=it["tank_id"],
                                          liters=liters_recv)
        if not added.get("success"):
            return added

        # Приход должен попасть и в реестр текущей смены, иначе при её
        # закрытии tank_variance покажет привезённое топливо как излишек.
        shift_credited = PecoStore.add_shift_tank_delivered(
            station_id=station_id, tank_id=it["tank_id"], liters=liters_recv
        )
        if not shift_credited.get("success"):
            return shift_credited

        if it.get("dip_after") is not None:
            dip_saved = PecoStore.insert_tank_dip(
                tank_id=it["tank_id"], measured_l=float(it["dip_after"]),
                dip_kind="DELIVERY", employee_id=employee_id,
            )
            if not dip_saved.get("success"):
                return dip_saved

    accepted = PecoStore.accept_delivery(delivery_id, employee_id)
    if not accepted.get("success"):
        return accepted

    result = {"success": True, "delivery_id": delivery_id,
              "total_shortfall": round(total_shortfall, 3)}

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
