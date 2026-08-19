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

    Показание назад означает сбой или подмену: возвращаем 0, чтобы
    отрицательный объём не попал в сверку и не замаскировал недостачу.
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
