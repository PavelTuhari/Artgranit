"""Бэк-офис UNA в вебе — HTTP-слой.

Знает про запросы и коды ответов, не знает про SQL. Каждый метод
возвращает пару `(payload, http_status)`.

Модуль только читает ERP, поэтому кодов на запись здесь нет: `400` —
неверный ввод, `404` — не найдено, `500` — сбой обращения к базе. Тексты
Oracle наружу не отдаются.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from modules.biro26web import store

Reply = Tuple[Dict[str, Any], int]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_ROWS = 1000

_GENERIC_ERROR = ("Ошибка обращения к учётной базе. Повторите операцию "
                  "или обратитесь к администратору.")


class Biro26WebController:
    """Журналы, документы и проводки учётной системы."""

    _store = store

    # ── общее ────────────────────────────────────────────────────────

    @classmethod
    def _ok(cls, data: Any = None) -> Reply:
        return {"success": True, "data": data, "message": ""}, 200

    @classmethod
    def _fail(cls, message: str, status: int = 400) -> Reply:
        return {"success": False, "data": None, "message": message}, status

    @classmethod
    def _reply(cls, result: Dict[str, Any]) -> Reply:
        if result.get("success"):
            return cls._ok(result.get("data"))

        message = result.get("message", "")
        if "не найден" in message:
            return cls._fail(message, 404)
        # Всё, что пришло от Oracle, наружу не выпускаем: там имена хостов,
        # схем и структура запросов.
        if message.upper().startswith("ORA-") or "TNS" in message.upper():
            return cls._fail(_GENERIC_ERROR, 500)
        return cls._fail(message or _GENERIC_ERROR, 400)

    @staticmethod
    def _int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    # ── журналы ──────────────────────────────────────────────────────

    @classmethod
    def journals(cls) -> Reply:
        return cls._reply(cls._store.journal_tree())

    @classmethod
    def journal(cls, journal_id: Any) -> Reply:
        cod = cls._int(journal_id)
        if cod is None:
            return cls._fail("номер журнала должен быть числом")
        return cls._reply(cls._store.journal(cod))

    # ── документы ────────────────────────────────────────────────────

    @classmethod
    def documents(cls, journal_id: Any, limit: Any = 200,
                  date_from: Optional[str] = None,
                  date_to: Optional[str] = None) -> Reply:
        cod = cls._int(journal_id)
        if cod is None:
            return cls._fail("номер журнала должен быть числом")

        rows = cls._int(limit) or 200
        # Верхняя граница нужна не для красоты: журнал «Все» может тянуть
        # десятки тысяч документов через thick-воркер.
        rows = max(1, min(rows, _MAX_ROWS))

        for value, name in ((date_from, "дата с"), (date_to, "дата по")):
            if value and not _DATE_RE.match(value):
                return cls._fail(f"{name}: ожидается формат YYYY-MM-DD")
        if date_from and date_to and date_to < date_from:
            return cls._fail("дата «по» раньше даты «с»")

        return cls._reply(cls._store.documents(cod, rows, date_from, date_to))

    @classmethod
    def document(cls, cod: Any) -> Reply:
        number = cls._int(cod)
        if number is None:
            return cls._fail("номер документа должен быть числом")

        head = cls._store.document(number)
        if not head.get("success"):
            return cls._reply(head)

        lines = cls._store.document_lines(number, head["data"].get("docname"))
        postings = cls._store.document_postings(number)

        return cls._ok({
            "head": head["data"],
            "lines": (lines.get("data") or {}).get("rows", []),
            "lines_note": (lines.get("data") or {}).get("note"),
            "postings": postings.get("data") or [],
        })

    @classmethod
    def document_types(cls) -> Reply:
        return cls._reply(cls._store.document_types())
