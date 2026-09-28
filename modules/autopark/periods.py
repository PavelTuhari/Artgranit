"""Autopark — параметры, действующие в периоде: чистые правила.

Заказчик правит настройки сам и правит их **на период**: ставка за
километр с 18.09.2026, минимальный остаток на зиму, состав группы АЗС на
время ремонта дороги. Отсюда одно требование, которое здесь и проверяется:

    в один момент времени по одному объекту действует ровно одна строка.

Без этого расчёт становится недетерминированным — два перекрывающихся
периода дают два разных ответа на один вопрос, и какой из них попадёт в
план, зависит от порядка строк в таблице.

Второе требование — **не переписывать прошлое**. Зарплата за август
считается по ставке августа, даже если в сентябре её изменили. Поэтому
период не правят «поверх», а закрывают датой и заводят новый: в
`close_open_period` ровно это и происходит.

Ни одного импорта БД: SQL живёт в supply_store.py.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

# Границы включительные: период «с 01.09 по 30.09» покрывает и 1-е, и 30-е.
# NULL в VALID_TO означает «бессрочно», NULL в VALID_FROM — «с начала
# времён» (так выглядят строки, заведённые до появления периодов).


def covers(row: Dict[str, Any], on_date: date) -> bool:
    """Действует ли строка на указанную дату."""
    start = row.get("valid_from")
    end = row.get("valid_to")
    if start and on_date < _as_date(start):
        return False
    if end and on_date > _as_date(end):
        return False
    return True


def _as_date(value: Any) -> date:
    return value.date() if hasattr(value, "date") else value


def effective(rows: Sequence[Dict[str, Any]], on_date: date) -> Optional[Dict[str, Any]]:
    """Строка, действующая на дату. При равных датах — заведённая позже.

    Тай-брейк по ID нужен не для красоты: если в базе всё же оказались
    две перекрывающиеся строки (например, их завели в обход интерфейса),
    расчёт обязан остаться воспроизводимым, а не зависеть от плана
    выполнения запроса.
    """
    matching = [r for r in rows if covers(r, on_date)]
    if not matching:
        return None
    matching.sort(key=lambda r: (_as_date(r["valid_from"]) if r.get("valid_from")
                                 else date.min, r.get("id") or 0))
    return matching[-1]


def effective_all(rows: Sequence[Dict[str, Any]], on_date: date,
                  key: str) -> List[Dict[str, Any]]:
    """Действующие строки по каждому значению ``key`` (резервуар, цистерна, группа)."""
    by_key: Dict[Any, List[Dict[str, Any]]] = {}
    for row in rows:
        by_key.setdefault(row.get(key), []).append(row)
    out = []
    for group in by_key.values():
        row = effective(group, on_date)
        if row is not None:
            out.append(row)
    return out


def validate_period(new_row: Dict[str, Any],
                    existing: Sequence[Dict[str, Any]]) -> List[str]:
    """Проверка одного периода перед сохранением.

    Возвращает список ошибок (пустой — можно сохранять). Правки самой
    строки (её ``id`` совпадает) из проверки исключаются: иначе период
    всегда конфликтовал бы сам с собой.
    """
    errors: List[str] = []
    start = new_row.get("valid_from")
    end = new_row.get("valid_to")
    if not start:
        errors.append("Не указана дата начала периода")
        return errors
    start = _as_date(start)
    end = _as_date(end) if end else None
    if end and end < start:
        errors.append("Дата окончания периода раньше даты начала")
        return errors

    for row in existing:
        if new_row.get("id") and row.get("id") == new_row.get("id"):
            continue
        other_start = _as_date(row["valid_from"]) if row.get("valid_from") else date.min
        other_end = _as_date(row["valid_to"]) if row.get("valid_to") else date.max
        if start <= other_end and (end or date.max) >= other_start:
            errors.append(
                "Период пересекается с уже заведённым "
                f"{other_start:%d.%m.%Y}—"
                + ("бессрочно" if not row.get("valid_to") else f"{other_end:%d.%m.%Y}")
                + ": в один день по одному объекту может действовать только одна настройка")
    return errors


def close_open_period(existing: Sequence[Dict[str, Any]],
                      new_from: date) -> List[Dict[str, Any]]:
    """Какие открытые периоды нужно закрыть днём раньше нового.

    Сценарий заказчика: «с 1 октября ставка 4 лея». Он не должен вручную
    закрывать сентябрьский период — система закрывает его 30 сентября
    сама. Возвращает список ``{"id", "valid_to"}`` для обновления.
    """
    new_from = _as_date(new_from)
    to_close = []
    for row in existing:
        start = _as_date(row["valid_from"]) if row.get("valid_from") else date.min
        if row.get("valid_to") is None and start < new_from:
            to_close.append({"id": row.get("id"), "valid_to": new_from - timedelta(days=1)})
    return to_close


def describe(row: Dict[str, Any]) -> str:
    """Человеческая подпись периода — одна и та же в UI, отчётах и логе."""
    start = _as_date(row["valid_from"]) if row.get("valid_from") else None
    end = _as_date(row["valid_to"]) if row.get("valid_to") else None
    if start and end:
        return f"{start:%d.%m.%Y} — {end:%d.%m.%Y}"
    if start:
        return f"с {start:%d.%m.%Y}"
    if end:
        return f"по {end:%d.%m.%Y}"
    return "бессрочно"
