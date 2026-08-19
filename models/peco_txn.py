"""PECO: конечный автомат отпуска топлива.

Один автомат обслуживает оба режима — самообслуживание и отпуск
сотрудником. Различие сводится к флагу IS_SELF_SERVICE и к тому, кто
авторизовал операцию; отдельной ветки в коде для этого нет.

    AUTHORIZED -> DISPENSING -> AWAITING_PAY -> PAID
                       |              |
                       v              v
                    VOIDED         VOIDED

Функции этого модуля чистые: к базе не обращаются.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional, Set

from models.peco_oracle_store import PecoStore

TRANSITIONS: Dict[str, Set[str]] = {
    "AUTHORIZED":   {"DISPENSING", "VOIDED"},
    "DISPENSING":   {"AWAITING_PAY", "PAID", "VOIDED"},
    "AWAITING_PAY": {"PAID", "VOIDED"},
    "PAID":         set(),   # финальное состояние
    "VOIDED":       set(),   # финальное состояние
}

# Способы оплаты, требующие внешней ссылки на платёж
_REF_REQUIRED = {"MIA_QR"}

_SETTLEABLE = {"DISPENSING", "AWAITING_PAY"}


def can_transition(current: str, target: str) -> bool:
    """Разрешён ли переход. Неизвестный статус трактуется как запрет."""
    return target in TRANSITIONS.get(current, set())


def next_status_after_dispense(is_self_service: bool) -> str:
    """Самообслуживание предавторизовано по MIA QR — закрывается сразу
    при возврате пистолета. Отпуск сотрудником ждёт кассира."""
    return "PAID" if is_self_service else "AWAITING_PAY"


def liters_from_meter(meter_start: float, meter_end: float) -> float:
    """Литры считаются по счётчику, а не по вводу оператора.

    Механический счётчик пистолета может переполниться и начать считать с нуля
    (например, 999999.000 -> 0.001 -> 12.000). Возврат показания не возрастает
    при сбое или подмене: любое показание <= стартовому возвращает 0.0, чтобы
    отрицательный или нулевой объём не попал в сверку и не замаскировал
    недостачу.

    Переполнение счётчика намеренно НЕ восстанавливается. Для вычисления оборота
    пришлось бы предполагать максимум счётчика, но ошибка в этом предположении
    зачислила бы неотпущенное топливо — изобретение фиктивной продажи хуже, чем
    видимое расхождение, которое рассчитает и исследует оператор.

    Следствие: литры, пропущенные из-за переполнения, остаются в meter_delta
    смены, но не входят в объём транзакции. Они всплывают при закрытии смены
    как неоплаченное топливо и должны быть исследованы вручную.
    """
    delta = float(meter_end) - float(meter_start)
    return round(delta, 3) if delta > 0 else 0.0


def compute_amount(liters: float, price: float) -> float:
    """Сумма к оплате, округление половины вверх до копейки."""
    value = Decimal(str(liters)) * Decimal(str(price))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def validate_settlement(status: str, pay_method: str,
                        mia_ref: Optional[str]) -> Dict[str, Any]:
    """Можно ли закрыть транзакцию указанным способом оплаты."""
    if status not in _SETTLEABLE:
        return {"ok": False,
                "error": f"Нельзя оплатить транзакцию в статусе {status}"}
    if pay_method in _REF_REQUIRED and not mia_ref:
        return {"ok": False, "error": "Не указана ссылка платежа MIA"}
    return {"ok": True, "error": ""}


# ------------------------------------------------------------------
# Оркестрация
# ------------------------------------------------------------------


def authorize(shift_id: int, nozzle_id: int, grade_code: str,
              station_id: int, meter_start: float, is_self_service: bool,
              employee_id: Optional[int] = None) -> Dict[str, Any]:
    """Авторизует налив по действующей цене.

    Цена фиксируется в транзакции: смена цены посреди смены не должна
    переписывать то, что клиент уже заплатил.
    """
    price_r = PecoStore.current_price(station_id, grade_code)
    if not price_r.get("success"):
        return price_r

    created = PecoStore.insert_txn(
        shift_id=shift_id,
        nozzle_id=nozzle_id,
        grade_code=grade_code,
        price=price_r["price"],
        meter_start=meter_start,
        is_self_service=is_self_service,
        authorized_by=employee_id,
    )
    if not created.get("success"):
        return created

    PecoStore.log_event(
        "TXN_AUTHORIZED", station_id=station_id, shift_id=shift_id,
        entity_type="TXN", entity_id=created["txn_id"], employee_id=employee_id,
        payload={"grade": grade_code, "price": price_r["price"]},
    )
    return {"success": True, "txn_id": created["txn_id"],
            "price": price_r["price"]}


def start_dispense(txn_id: int) -> Dict[str, Any]:
    """AUTHORIZED -> DISPENSING."""
    txn_r = PecoStore.get_txn(txn_id)
    if not txn_r.get("success"):
        return txn_r
    current = txn_r["txn"]["status_code"]
    if not can_transition(current, "DISPENSING"):
        return {"success": False,
                "error": f"Недопустимый переход {current} -> DISPENSING"}
    saved = PecoStore.update_txn_status(txn_id, "DISPENSING")
    if not saved.get("success"):
        return saved
    return {"success": True, "status": "DISPENSING"}


def finish_dispense(txn_id: int, meter_end: float) -> Dict[str, Any]:
    """Завершает налив: литры и сумма считаются по счётчику."""
    txn_r = PecoStore.get_txn(txn_id)
    if not txn_r.get("success"):
        return txn_r
    txn = txn_r["txn"]
    current = txn["status_code"]

    is_self = bool(int(txn.get("is_self_service") or 0))
    target = next_status_after_dispense(is_self)

    if not can_transition(current, target):
        return {"success": False,
                "error": f"Недопустимый переход {current} -> {target}"}

    liters = liters_from_meter(float(txn["meter_start"]), meter_end)
    amount = compute_amount(liters, float(txn["price"]))

    fields: Dict[str, Any] = {"liters": liters, "amount": amount,
                              "meter_end": meter_end}
    if target == "PAID":
        # самообслуживание предавторизовано по MIA QR
        fields["pay_method"] = "MIA_QR"

    saved = PecoStore.update_txn_status(txn_id, target, **fields)
    if not saved.get("success"):
        return saved

    PecoStore.log_event(
        "TXN_DISPENSED", entity_type="TXN", entity_id=txn_id,
        payload={"liters": liters, "amount": amount, "status": target},
    )
    return {"success": True, "status": target, "liters": liters,
            "amount": amount}


def settle(txn_id: int, pay_method: str,
           mia_ref: Optional[str] = None) -> Dict[str, Any]:
    """Закрывает транзакцию оплатой на кассе или по MIA QR."""
    txn_r = PecoStore.get_txn(txn_id)
    if not txn_r.get("success"):
        return txn_r
    current = txn_r["txn"]["status_code"]

    check = validate_settlement(current, pay_method, mia_ref)
    if not check["ok"]:
        return {"success": False, "error": check["error"]}

    if not can_transition(current, "PAID"):
        return {"success": False,
                "error": f"Недопустимый переход {current} -> PAID"}

    saved = PecoStore.update_txn_status(
        txn_id, "PAID", pay_method=pay_method, mia_ref=mia_ref
    )
    if not saved.get("success"):
        return saved

    PecoStore.log_event(
        "TXN_PAID", entity_type="TXN", entity_id=txn_id,
        payload={"pay_method": pay_method},
    )
    return {"success": True, "status": "PAID"}


def void(txn_id: int, reason: str) -> Dict[str, Any]:
    """Аннулирует незавершённую транзакцию. Оплаченную аннулировать нельзя."""
    txn_r = PecoStore.get_txn(txn_id)
    if not txn_r.get("success"):
        return txn_r
    current = txn_r["txn"]["status_code"]

    if not can_transition(current, "VOIDED"):
        return {"success": False,
                "error": f"Нельзя аннулировать транзакцию в статусе {current}"}

    saved = PecoStore.update_txn_status(txn_id, "VOIDED")
    if not saved.get("success"):
        return saved

    PecoStore.log_event(
        "TXN_VOIDED", entity_type="TXN", entity_id=txn_id,
        payload={"reason": reason},
    )
    return {"success": True, "status": "VOIDED"}
