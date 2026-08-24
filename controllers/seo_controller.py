"""SEOForge — контроллер модуля: HTTP-слой поверх хранилища.

Знает про запросы и коды ответов, не знает про SQL. Три обязанности:

1. валидировать ввод до обращения к базе — пустые обязательные поля,
   перевёрнутые даты, неизвестный вид импорта;
2. разбирать CSV и вести двухшаговый импорт (предпросмотр ничего не пишет);
3. переводить ошибки Oracle в HTTP-коды, показывая пользователю только
   бизнес-сообщения — тексты вроде «TNS:no listener at host …» наружу
   не уходят.

Каждый метод возвращает пару `(payload, http_status)`.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from models import seo_csv
from models import seo_oracle_store

Reply = Tuple[Dict[str, Any], int]

_PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_CAMPAIGN_STATUSES = ("DRAFT", "ACTIVE", "CLOSED", "CANCELLED")
_DICT_SECTIONS = ("CHANNEL", "ARTICLE", "PROMO_TYPE", "FORMAT", "BUYUNIT", "METRIC")

_IMPORT_PARSERS = {
    "SPEND": seo_csv.parse_spend_csv,
    "METRICS": seo_csv.parse_metrics_csv,
}

# Показываем пользователю только то, что он может исправить сам.
_GENERIC_ERROR = ("Ошибка обращения к базе данных. "
                  "Повторите операцию или обратитесь к администратору.")


class SeoController:
    """Маршрутизация и валидация модуля SEOForge."""

    # Вынесено атрибутом класса, чтобы тесты могли подменить хранилище.
    _store = seo_oracle_store

    # ── общие помощники ──────────────────────────────────────────────

    @staticmethod
    def _username() -> str:
        try:
            from flask import session
            return session.get("username", "system")
        except Exception:                                        # noqa: BLE001
            # Вне запроса (скрипты, тесты) сессии нет — это не ошибка.
            return "system"

    @staticmethod
    def error_status(message: str) -> int:
        """Сообщение Oracle -> HTTP-код.

        ORA-20xxx — бизнес-правило контура, ORA-00001 — нарушенная
        уникальность (дубль кода): и то и другое пользователь исправляет
        сам, это 409. Всё прочее — сбой инфраструктуры, 500.
        """
        text = (message or "").upper()
        if re.search(r"ORA-20\d{3}", text):
            return 409
        if "ORA-00001" in text or "UNIQUE CONSTRAINT" in text:
            return 409
        return 500

    @classmethod
    def _fail(cls, message: str, status: int = 400) -> Reply:
        return {"success": False, "data": None, "message": message}, status

    @classmethod
    def _ok(cls, data: Any = None, message: str = "") -> Reply:
        return {"success": True, "data": data, "message": message}, 200

    @classmethod
    def _reply(cls, result: Dict[str, Any]) -> Reply:
        """Ответ хранилища -> пара (payload, status)."""
        if result.get("success"):
            return cls._ok(result.get("data"), result.get("message", ""))
        message = result.get("message", "")
        status = cls.error_status(message)
        if status == 500:
            message = _GENERIC_ERROR
        return {"success": False, "data": None, "message": message}, status

    # ── валидаторы ───────────────────────────────────────────────────

    @staticmethod
    def _text(payload: Dict[str, Any], name: str) -> str:
        return str(payload.get(name) or "").strip()

    @classmethod
    def _require(cls, payload: Dict[str, Any], *names: str) -> Optional[str]:
        missing = [name for name in names if not cls._text(payload, name)]
        if missing:
            return "Не заполнены обязательные поля: " + ", ".join(missing)
        return None

    # ── сайты ────────────────────────────────────────────────────────

    @classmethod
    def sites(cls, include_archived: bool = False) -> Reply:
        return cls._reply(cls._store.list_sites(include_archived))

    @classmethod
    def save_site(cls, payload: Dict[str, Any]) -> Reply:
        problem = cls._require(payload, "domain", "locales")
        if problem:
            return cls._fail(problem)
        return cls._reply(cls._store.save_site(payload, cls._username()))

    @classmethod
    def archive_site(cls, cod: int) -> Reply:
        return cls._reply(cls._store.archive_site(cod, cls._username()))

    # ── площадки ─────────────────────────────────────────────────────

    @classmethod
    def platforms(cls, include_archived: bool = False) -> Reply:
        return cls._reply(cls._store.list_platforms(include_archived))

    @classmethod
    def save_platform(cls, payload: Dict[str, Any]) -> Reply:
        problem = cls._require(payload, "platform_code", "name", "channel_cod1")
        if problem:
            return cls._fail(problem)
        return cls._reply(cls._store.save_platform(payload, cls._username()))

    @classmethod
    def archive_platform(cls, cod: int) -> Reply:
        return cls._reply(cls._store.archive_platform(cod, cls._username()))

    # ── справочники и курсы ──────────────────────────────────────────

    @classmethod
    def dictionary(cls, section: Optional[str] = None) -> Reply:
        if section and section.upper() not in _DICT_SECTIONS:
            return cls._fail(f"Неизвестный раздел справочника: {section}")
        return cls._reply(cls._store.list_dict(
            section.upper() if section else None))

    @classmethod
    def save_dictionary(cls, section: str, payload: Dict[str, Any]) -> Reply:
        if (section or "").upper() not in _DICT_SECTIONS:
            return cls._fail(f"Неизвестный раздел справочника: {section}")
        problem = cls._require(payload, "code")
        if problem:
            return cls._fail(problem)
        return cls._reply(cls._store.save_dict(
            section.upper(), payload, cls._username()))

    @classmethod
    def fx(cls) -> Reply:
        return cls._reply(cls._store.list_fx())

    @classmethod
    def save_fx(cls, payload: Dict[str, Any]) -> Reply:
        problem = cls._require(payload, "valuta", "rate_date", "rate")
        if problem:
            return cls._fail(problem)
        if not _DATE_RE.match(cls._text(payload, "rate_date")):
            return cls._fail("Дата курса должна быть в формате YYYY-MM-DD")
        try:
            rate = float(str(payload.get("rate")).replace(",", "."))
        except (TypeError, ValueError):
            return cls._fail("Курс должен быть числом")
        if rate <= 0:
            return cls._fail("Курс должен быть больше нуля")
        return cls._reply(cls._store.save_fx(
            cls._text(payload, "valuta"), cls._text(payload, "rate_date"),
            rate, cls._username()))

    # ── кампании ─────────────────────────────────────────────────────

    @classmethod
    def campaigns(cls, site_cod: Optional[int] = None,
                  include_archived: bool = False) -> Reply:
        return cls._reply(cls._store.list_campaigns(site_cod, include_archived))

    @classmethod
    def save_campaign(cls, payload: Dict[str, Any]) -> Reply:
        problem = cls._require(payload, "camp_code", "site_cod",
                               "promo_type_cod1", "date_start", "date_end")
        if problem:
            return cls._fail(problem)

        start = cls._text(payload, "date_start")
        end = cls._text(payload, "date_end")
        if not _DATE_RE.match(start) or not _DATE_RE.match(end):
            return cls._fail("Даты кампании должны быть в формате YYYY-MM-DD")
        if end < start:
            return cls._fail("Дата окончания раньше даты начала")

        return cls._reply(cls._store.save_campaign(payload, cls._username()))

    @classmethod
    def set_campaign_status(cls, cod: int, status: str) -> Reply:
        value = (status or "").upper()
        if value not in _CAMPAIGN_STATUSES:
            return cls._fail("Неизвестный статус кампании: "
                             + ", ".join(_CAMPAIGN_STATUSES))
        return cls._reply(cls._store.set_campaign_status(
            cod, value, cls._username()))

    @classmethod
    def archive_campaign(cls, cod: int) -> Reply:
        return cls._reply(cls._store.archive_campaign(cod, cls._username()))

    # ── бюджет ───────────────────────────────────────────────────────

    @classmethod
    def plan_save(cls, payload: Dict[str, Any]) -> Reply:
        problem = cls._require(payload, "period", "article_cod1")
        if problem:
            return cls._fail(problem)
        if not _PERIOD_RE.match(cls._text(payload, "period")):
            return cls._fail("Период должен быть в формате YYYY-MM")
        try:
            suma = float(str(payload.get("plan_suma") or 0).replace(",", "."))
        except (TypeError, ValueError):
            return cls._fail("Сумма плана должна быть числом")
        if suma < 0:
            return cls._fail("Сумма плана не может быть отрицательной")
        payload = dict(payload, plan_suma=suma)
        return cls._reply(cls._store.plan_upsert(payload, cls._username()))

    @classmethod
    def planfact(cls, period: Optional[str] = None,
                 site_cod: Optional[int] = None) -> Reply:
        if period and not _PERIOD_RE.match(period):
            return cls._fail("Период должен быть в формате YYYY-MM")
        return cls._reply(cls._store.planfact(period, site_cod))

    # ── факты ────────────────────────────────────────────────────────

    @classmethod
    def spend(cls, period: Optional[str] = None,
              site_cod: Optional[int] = None) -> Reply:
        return cls._reply(cls._store.list_spend(period, site_cod))

    @classmethod
    def metrics(cls, period: Optional[str] = None,
                site_cod: Optional[int] = None) -> Reply:
        return cls._reply(cls._store.list_metrics(period, site_cod))

    @classmethod
    def add_spend(cls, payload: Dict[str, Any]) -> Reply:
        return cls._add_fact("SPEND", payload)

    @classmethod
    def add_metrics(cls, payload: Dict[str, Any]) -> Reply:
        return cls._add_fact("METRICS", payload)

    @classmethod
    def _add_fact(cls, kind: str, payload: Dict[str, Any]) -> Reply:
        """Ручной ввод проходит через тот же разбор, что и CSV.

        Одна строка собирается в мини-файл и отдаётся парсеру: правила
        валидации остаются в одном месте, а не расходятся между формой
        и импортом.
        """
        parser = _IMPORT_PARSERS.get(kind)
        if parser is None:
            return cls._fail(f"Неизвестный вид данных: {kind}")

        columns = (seo_csv.SPEND_COLUMNS if kind == "SPEND"
                   else seo_csv.METRICS_COLUMNS)
        header = ";".join(columns)
        line = ";".join(str(payload.get(name, "") or "") for name in columns)
        parsed = parser(f"{header}\n{line}")

        if parsed.errors or not parsed.rows:
            message = (parsed.errors[0]["message"] if parsed.errors
                       else "Строка не распознана")
            return cls._fail(message)

        return cls._reply(cls._store.add_fact(
            kind, parsed.rows[0], cls._username()))

    # ── импорт ───────────────────────────────────────────────────────

    @classmethod
    def import_preview(cls, kind: str, file_name: str, text: str) -> Reply:
        parsed = cls._parse_import(kind, text)
        if isinstance(parsed, tuple):
            return parsed

        ext_ids = [row["ext_id"] for row in parsed.rows]
        try:
            known = cls._store.existing_ext_ids(kind, ext_ids)
        except ValueError as exc:
            return cls._fail(str(exc))

        rows = [dict(row, is_duplicate=row["ext_id"] in known)
                for row in parsed.rows]

        return cls._ok({
            "file_name": file_name,
            "columns": parsed.columns,
            "rows": rows,
            "errors": parsed.errors,
            "duplicates": sorted(known),
            "will_load": sum(1 for row in rows if not row["is_duplicate"]),
        })

    @classmethod
    def import_commit(cls, kind: str, file_name: str, text: str) -> Reply:
        parsed = cls._parse_import(kind, text)
        if isinstance(parsed, tuple):
            return parsed

        if not parsed.rows:
            return cls._fail("В файле нет ни одной пригодной строки")

        result = cls._store.import_commit(
            kind, file_name, parsed.rows, cls._username())
        payload, status = cls._reply(result)
        if status == 200:
            # Ошибки разбора не отменяют загрузку годных строк, но должны
            # вернуться пользователю вместе с итогом.
            payload["data"] = dict(payload.get("data") or {},
                                   errors=parsed.errors)
        return payload, status

    @classmethod
    def _parse_import(cls, kind: str, text: str):
        parser = _IMPORT_PARSERS.get((kind or "").upper())
        if parser is None:
            return cls._fail(
                "Неизвестный вид импорта: допустимы SPEND и METRICS")

        parsed = parser(text or "")

        # Структурная ошибка (пустой файл, нет обязательных колонок)
        # относится к файлу целиком — читать нечего, это 400. Ошибка в
        # строке относится только к ней: предпросмотр обязан показать её
        # пользователю вместе с годными строками, а не отвергнуть файл.
        structural = [err for err in parsed.errors if err.get("line", 0) <= 1]
        if structural:
            return cls._fail(structural[0]["message"])
        return parsed

    @classmethod
    def imports(cls) -> Reply:
        return cls._reply(cls._store.list_imports())

    # ── отчёты, настройки, журнал ────────────────────────────────────

    @classmethod
    def roi(cls, period_from: Optional[str] = None,
            period_to: Optional[str] = None,
            site_cod: Optional[int] = None) -> Reply:
        for value in (period_from, period_to):
            if value and not _PERIOD_RE.match(value):
                return cls._fail("Период должен быть в формате YYYY-MM")
        return cls._reply(cls._store.roi(period_from, period_to, site_cod))

    @classmethod
    def settings(cls) -> Reply:
        return cls._reply(cls._store.get_settings())

    @classmethod
    def save_settings(cls, payload: Dict[str, Any]) -> Reply:
        values = {str(code): str(value) for code, value in (payload or {}).items()}
        mode = values.get("BUDGET_OVERRUN_MODE")
        if mode is not None and mode not in ("BLOCK", "WARN"):
            return cls._fail("BUDGET_OVERRUN_MODE принимает только BLOCK или WARN")
        return cls._reply(cls._store.save_settings(values, cls._username()))

    @classmethod
    def events(cls) -> Reply:
        return cls._reply(cls._store.list_events())
