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

from modules.biro26web import store, writer

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

    @classmethod
    def _reply_write(cls, result: Dict[str, Any]) -> Reply:
        """Ответ операции записи.

        В отличие от чтения, сообщения ORA-20xxx здесь доходят до
        пользователя: это правила самого учёта, и текст у них
        осмысленный — «дата вне рабочего периода», «документ уже
        проведён». Спрятать их значило бы оставить человека с «ошибкой
        базы» вместо указания, что именно поправить.
        """
        if result.get("success"):
            return ({"success": True, "data": result.get("data"),
                     "message": result.get("message", "")}, 200)

        message = result.get("message", "")
        # Сообщение занимает несколько строк, и суть обычно во второй:
        # «Redactarea documentului este interzisa» — это заголовок, а
        # «Data documentului … inafara perioadei de lucru» — причина.
        # Поэтому берём всё до технического хвоста ORA-06512, а не первую
        # строку.
        business = re.search(r"ORA-20\d{3}:\s*(.+?)(?=ORA-0651|ORA-0408|$)",
                             message, re.S)
        if business:
            text = " ".join(business.group(1).split())
            return cls._fail(text, 409)
        if message.upper().startswith("ORA-") or "TNS" in message.upper():
            return cls._fail(_GENERIC_ERROR, 500)
        return cls._fail(message or _GENERIC_ERROR, 400)

    # ── запись ───────────────────────────────────────────────────────

    @classmethod
    def create_document(cls, payload: Dict[str, Any],
                        username: Optional[str] = None) -> Reply:
        sysfid = cls._int((payload or {}).get("sysfid"))
        if sysfid is None:
            return cls._fail("тип документа должен быть числом")
        return cls._reply_write(writer.create_document(
            sysfid,
            (payload or {}).get("date") or "",
            valuta=(payload or {}).get("valuta") or "LEI",
            nrset=cls._int((payload or {}).get("nrset")),
            div=cls._int((payload or {}).get("div")),
            comment=(payload or {}).get("comment"),
            username=username))

    @classmethod
    def post_document(cls, cod: Any) -> Reply:
        number = cls._int(cod)
        if number is None:
            return cls._fail("номер документа должен быть числом")
        return cls._reply_write(writer.post_document(number))

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

        lines = cls._store.document_lines(
            number,
            docname=head["data"].get("docname"),
            sysfid=head["data"].get("sysfid"),
            type_name=head["data"].get("type_name"))
        postings = cls._store.document_postings(number)

        return cls._ok({
            "head": head["data"],
            "lines": (lines.get("data") or {}).get("rows", []),
            "lines_note": (lines.get("data") or {}).get("note"),
            "lines_source": (lines.get("data") or {}).get("source"),
            "postings": postings.get("data") or [],
        })

    # ── номенклатура ─────────────────────────────────────────────────

    @classmethod
    def goods_roots(cls) -> Reply:
        return cls._reply(cls._store.goods_roots())

    @classmethod
    def goods_groups(cls, root: Any = 1, parent: Any = None) -> Reply:
        root_id = cls._int(root)
        if root_id is None:
            return cls._fail("корень дерева должен быть числом")
        parent_id = cls._int(parent) if parent not in (None, "") else None
        return cls._reply(cls._store.goods_groups(root_id, parent_id))

    @classmethod
    def goods_items(cls, group1: Any = None, group2: Any = None,
                    search: Optional[str] = None, limit: Any = 200) -> Reply:
        g1 = cls._int(group1) if group1 not in (None, "") else None
        g2 = cls._int(group2) if group2 not in (None, "") else None
        needle = (search or "").strip()

        if g1 is None and len(needle) < 2:
            return cls._fail("выберите группу или задайте не меньше "
                             "двух символов для поиска")

        rows = max(1, min(cls._int(limit) or 200, _MAX_ROWS))
        return cls._reply(cls._store.goods_items(g1, g2, needle or None, rows))

    @classmethod
    def goods_item(cls, cod: Any) -> Reply:
        number = cls._int(cod)
        if number is None:
            return cls._fail("код номенклатуры должен быть числом")
        return cls._reply(cls._store.goods_item(number))

    @classmethod
    def document_types(cls) -> Reply:
        return cls._reply(cls._store.document_types())
