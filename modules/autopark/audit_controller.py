"""Autopark — валидация и сборка аудиторского отчёта для HTTP-слоя.

Между маршрутом и движком, по образцу остальных контроллеров модуля:
маршрут не считает и не разбирает параметры, движок не знает про HTTP.

Здесь же — единственное место, где решается, что отдавать наружу. Полный
результат `audit.run_audit` содержит расшифровку каждого отклонения: на
годовом объёме это сотни строк, и отдавать их в JSON вместе со сводкой
незачем — панель показывает итоги, а расшифровка живёт в книге Excel.
"""
from __future__ import annotations

import os
import tempfile
from datetime import date, timedelta
from typing import Any, Dict, Optional, Tuple

from modules.autopark import audit, audit_data

# `audit_excel` намеренно НЕ импортируется здесь. Он тянет openpyxl, а
# цепочка импортов у модуля такая: __init__ → audit_routes →
# audit_controller. Отсутствие библиотеки отчётности уронило бы загрузку
# всего контура — вместе с планированием завоза и зарплатой, — и модуль
# просто исчез бы из меню портала. Выгрузка книги важна, но не настолько.
# Импорт живёт внутри `workbook()`: без openpyxl ломается одна кнопка.

#: Период по умолчанию, если его не передали: последний квартал.
DEFAULT_DAYS = 90


def _parse_date(value: Any, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return fallback


def _window(params: Dict[str, Any]) -> Tuple[date, date]:
    today = date.today()
    date_to = _parse_date(params.get("date_to"), today)
    date_from = _parse_date(params.get("date_from"),
                            date_to - timedelta(days=DEFAULT_DAYS))
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return date_from, date_to


def _summary(rep: Dict[str, Any]) -> Dict[str, Any]:
    """Сводка без расшифровки отклонений — то, что нужно панели."""
    return {
        "entity": rep["entity"],
        "period": {"from": str(rep["period"].get("from")),
                   "to": str(rep["period"].get("to"))},
        "data_label": rep.get("data_label"),
        "opinion": rep["opinion"],
        "facts": rep["facts"],
        "controls": rep["controls"],
        "findings": rep["findings"],
        "heat_map": rep["heat_map"],
        "tests": [{k: v for k, v in t.items() if k not in ("rows", "columns")}
                  for t in rep["tests"]],
        "limitations": rep["limitations"],
        "methodology": rep["methodology"],
        "scope": rep["scope"],
    }


class AuditController:
    """Аудит контура: сводка для панели и книга Excel для выгрузки."""

    @staticmethod
    def report(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Сводка по боевым данным за период."""
        date_from, date_to = _window(params or {})
        try:
            pop = audit_data.live_population(date_from, date_to)
            rep = audit.run_audit(pop)
        except audit.AuditInputError as exc:
            return {"success": False, "message": f"Нет данных для проверки: {exc}"}
        except Exception as exc:                    # noqa: BLE001
            # Аудит не имеет права отдать пустой результат как «всё чисто»:
            # молчание проверки читается как её успех. Ошибку поднимаем.
            return {"success": False,
                    "message": f"Проверка не выполнена: {exc}"}
        return {"success": True, "data": _summary(rep)}

    @staticmethod
    def demo_report(seed: int = 20260919) -> Dict[str, Any]:
        """Сводка по сгенерированному набору — вместе с самопроверкой."""
        pop = audit_data.demo_population(seed)
        rep = audit.run_audit(pop)
        data = _summary(rep)
        found = {t["id"]: t["exceptions"] for t in rep["tests"]}
        data["selfcheck"] = {
            "rows": [{"test": tid, "injected": pop["injected"].get(tid, 0),
                      "found": found.get(tid, 0)}
                     for tid in sorted(set(pop["injected"]) | set(found))],
            "passed": all(pop["injected"].get(k, 0) == found.get(k, 0)
                          for k in set(pop["injected"]) | set(found)),
        }
        return {"success": True, "data": data}

    @staticmethod
    def workbook(params: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """Книга Excel по боевым данным. Возвращает (путь, имя файла)."""
        from modules.autopark import audit_excel

        date_from, date_to = _window(params or {})
        pop = audit_data.live_population(date_from, date_to)
        rep = audit.run_audit(pop)
        name = f"autopark_audit_{date_from}_{date_to}.xlsx"
        path = os.path.join(tempfile.mkdtemp(prefix="autopark_audit_"), name)
        audit_excel.build_workbook(rep, pop, path)
        return path, name
