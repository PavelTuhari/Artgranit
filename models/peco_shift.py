"""PECO: жизненный цикл смены и расчёт расхождений.

Функции расчёта — чистые: принимают и возвращают словари, к базе не
обращаются. Это делает главную бизнес-логику модуля тестируемой без Oracle.

Три расхождения соответствуют трём разным типам отказа и намеренно
не сводятся в одно число:

  liter_variance -- топливо вышло из пистолета, но не оплачено
  cash_variance  -- недостача или излишек денежного ящика
  tank_variance  -- утечка либо уход калибровки резервуара
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Допуски. Выход за пределы переводит смену в DISPUTED и требует PIN менеджера.
TOLERANCE_LITERS: float = 0.5
TOLERANCE_CASH: float = 1.0

# Допуск по резервуару. Он НЕ равен допуску по счётчику: замер метрштоком
# на резервуаре 20000 л даёт погрешность порядка ±5 л, а тепловое расширение
# дизеля (~0,08 %/°C) — около 16 л на градус. Допуск 0,5 л здесь означал бы
# DISPUTED на каждой смене, и статус перестал бы что-либо значить.
# Значение подлежит настройке владельцем по фактической статистике.
TOLERANCE_TANK_LITERS: float = 50.0


def meter_delta(meters: List[Dict[str, Any]]) -> float:
    """Сумма (METER_CLOSE - METER_OPEN) по пистолетам со снятым показанием."""
    total = 0.0
    for m in meters:
        close = m.get("meter_close")
        if close is None:
            continue
        total += float(close) - float(m.get("meter_open") or 0.0)
    return round(total, 3)


def compute_variances(
    meters: List[Dict[str, Any]],
    txn_liters: float,
    cash_declared: float,
    cash_expected: float,
) -> Dict[str, Any]:
    """Считает расхождения смены по счётчикам и кассе.

    tank_variance здесь всегда None: расхождение по резервуару считается
    только по резервуарам отдельно, функцией tank_variances() ниже —
    станционная сумма как раз и есть та ошибка, ради которой резервуары
    не сводятся в одно число (см. модуль docstring).
    """
    delta = meter_delta(meters)

    liter_variance = round(delta - float(txn_liters), 3)
    cash_variance = round(float(cash_declared) - float(cash_expected), 2)

    return {
        "meter_delta": delta,
        "liter_variance": liter_variance,
        "cash_variance": cash_variance,
        "tank_variance": None,
    }


def tank_variances(
    tank_rows: List[Dict[str, Any]],
    meters: List[Dict[str, Any]],
    dips: Dict[int, float],
) -> List[Dict[str, Any]]:
    """Расхождение по каждому резервуару отдельно.

    tank_rows — строки PECO_SHIFT_TANKS (остаток на открытие и приход за
    смену). meters — строки PECO_SHIFT_METERS, каждая с TANK_ID своего
    пистолета. dips — {tank_id: замер на закрытие}.

    Считается по резервуарам, а не суммой по станции: утечка в одном
    резервуаре и излишек в другом взаимно погасились бы и обе исчезли.
    """
    dispensed: Dict[int, float] = {}
    for m in meters:
        close = m.get("meter_close")
        if close is None:
            continue
        tank_id = m.get("tank_id")
        if tank_id is None:
            continue
        delta = float(close) - float(m.get("meter_open") or 0.0)
        dispensed[tank_id] = dispensed.get(tank_id, 0.0) + delta

    out: List[Dict[str, Any]] = []
    for t in tank_rows:
        tank_id = t["tank_id"]
        dip = dips.get(tank_id)
        variance = None
        if dip is not None:
            expected = (float(t.get("volume_open_l") or 0.0)
                        + float(t.get("delivered_l") or 0.0)
                        - dispensed.get(tank_id, 0.0))
            variance = round(float(dip) - expected, 3)
        out.append({
            "tank_id": tank_id,
            "grade_code": t.get("grade_code"),
            "dip_close_l": dip,
            "tank_variance": variance,
        })
    return out


def exceeds_tolerance(variances: Dict[str, Any]) -> bool:
    """Проверяется модуль отклонения: излишек — такое же расхождение."""
    if abs(float(variances.get("liter_variance") or 0.0)) > TOLERANCE_LITERS:
        return True
    if abs(float(variances.get("cash_variance") or 0.0)) > TOLERANCE_CASH:
        return True
    tank = variances.get("tank_variance")
    if tank is not None and abs(float(tank)) > TOLERANCE_LITERS:
        return True
    return False


def resolve_status(variances: Dict[str, Any]) -> str:
    """Итоговый статус смены по расхождениям."""
    return "DISPUTED" if exceeds_tolerance(variances) else "CLOSED"
