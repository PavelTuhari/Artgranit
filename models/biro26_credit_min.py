"""Минимальная сумма заказа для рассрочки и кредита.

RO: pragul de la care se poate achita in rate; conditia se scrie cu ROSU pe
    vitrina. Valoarea sta in YBIRO_SETTINGS.CREDIT_MIN_ORDER, deci se schimba
    fara atingerea codului.

Отдельный файл — намеренно (CLAUDE.md, правило №2): в прошлый раз эта логика
жила в app.py и была молча затёрта параллельной сессией. Здесь её видно, и
в общих файлах остаются только вызовы в одну строку.

Значение по умолчанию — 1500 лей (владелец, 18.08.2026).
"""
from __future__ import annotations

DEFAULT_MIN = 1500.0
SETTING_KEY = "CREDIT_MIN_ORDER"


def min_order() -> float:
    """Порог в леях. При недоступной БД — значение по умолчанию, не ноль:
    ноль означал бы «рассрочка доступна на любую сумму»."""
    try:
        from models.biro26_oracle_store import Biro26Store
        raw = Biro26Store.get_setting(SETTING_KEY, "")
        return float(str(raw).replace(",", ".")) if str(raw).strip() else DEFAULT_MIN
    except Exception:                                        # noqa: BLE001
        return DEFAULT_MIN


def check(total: float) -> tuple[bool, str]:
    """(можно ли в рассрочку, текст отказа для клиента).

    Текст двуязычный — витрина показывает его как есть.
    """
    m = min_order()
    if m > 0 and (total or 0) < m:
        return False, (
            f"Achitarea în rate / credit este disponibilă la comenzi de la "
            f"{m:.0f} lei · Оплата в рассрочку — при заказе от {m:.0f} лей")
    return True, ""
