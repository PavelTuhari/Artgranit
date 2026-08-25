"""SEOForge — хранилище модуля поверх контура YSEO_* в ERP OfficePlus/UNA.

Слой знает про SQL и ничего не знает про HTTP. Наружу отдаёт тот же
контракт, что и остальные модули портала:

    {"success": bool, "data": ..., "message": str}

Чтения идут через вьюшки `VSEO_*`, записи — либо прямо в таблицы, либо
через пакеты `PK_SEO_*`, если у операции есть инвариант (план бюджета).
Каждая запись сопровождается событием в `YSEO_EVENT_LOG` в той же
транзакции: журнал не должен переживать откат операции, которую он
описывает.

**Транспорт.** Контур живёт в боевой ERP OfficePlus (Oracle 11g,
`orange.una.md`), а туда ходят только через `models/biro26_db.py`:
thick-режим в отдельном процессе. Включить thick в основном процессе
нельзя — это переключатель на весь процесс, и он сломал бы облачное
подключение остальных модулей портала.

Отсюда важное следствие: постоянного соединения нет, каждый вызов —
своя транзакция. Многокомандные операции идут одним `execute_script`,
который воркер выполняет на одном соединении и коммитит только целиком.
Отдельного `commit()` здесь нет и быть не может.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from models.biro26_db import Biro26DB

# Таблицы фактов, куда ложится импорт. Отображение закрыто списком:
# произвольный `kind` не должен превращаться в имя таблицы.
_FACT_TABLES = {
    "SPEND": "YSEO_SPEND_FACT",
    "METRICS": "YSEO_METRICS_FACT",
}


# ── общие помощники ──────────────────────────────────────────────────

def _rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """columns + data -> список словарей с ключами в нижнем регистре."""
    if not result.get("success"):
        return []
    columns = [c.lower() for c in (result.get("columns") or [])]
    return [dict(zip(columns, row)) for row in (result.get("data") or [])]


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _done(data: Any = None, message: str = "") -> Dict[str, Any]:
    return {"success": True, "data": data, "message": message}


_LOG_SQL = (
    "BEGIN PK_SEO_UTIL.LOG_EVENT(:action, :entity_type, :entity_cod, "
    ":details, :username); END;"
)


def _log_params(action: str, entity_type: str, entity_cod, details: str,
                username: str) -> Dict[str, Any]:
    return {
        "action": action,
        "entity_type": entity_type,
        "entity_cod": entity_cod,
        "details": (details or "")[:2000],
        "username": username or "system",
    }


def _limited(sql: str) -> str:
    """Ограничение числа строк поверх готовой сортировки.

    ROWNUM в самом запросе применяется ДО ORDER BY и вернул бы произвольные
    строки, а не первые по порядку, поэтому лимит навешивается снаружи.
    """
    return f"SELECT * FROM ({sql}) WHERE ROWNUM <= :row_limit"


def _select(sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with Biro26DB() as db:
        result = db.execute_query(sql, params or {})
        if not result.get("success"):
            return _fail(result.get("message", ""))
        return _done(_rows(result))


def _script(statements: Sequence[tuple], *,
            log: Optional[tuple] = None) -> Dict[str, Any]:
    """Выполняет команды ОДНОЙ транзакцией через воркер ERP.

    `statements` — последовательность пар `(sql, params)`. Воркер выполняет
    их на одном соединении и коммитит только после последней: любая ошибка
    посередине отменяет всю операцию вместе с записью в журнал.

    Возвращает `{"success", "data": [результаты команд], "message"}`;
    результат команды с `kind="query"` содержит `columns` и `data`.
    """
    script = [{"sql": sql, "params": params or {}, "kind": kind}
              for sql, params, kind in _normalize(statements)]

    if log is not None:
        script.append({"sql": _LOG_SQL, "params": _log_params(*log),
                       "kind": "dml"})

    with Biro26DB() as db:
        result = db.execute_script(script)

    if not result.get("success"):
        return _fail(result.get("message", ""))
    return _done(result.get("results", []))


def _normalize(statements: Sequence[tuple]):
    """Пары (sql, params) и тройки (sql, params, kind) -> тройки."""
    for statement in statements:
        if len(statement) == 3:
            yield statement
        else:
            sql, params = statement
            yield sql, params, "dml"


def _write(statements: Sequence[tuple], *,
           log: Optional[tuple] = None) -> Dict[str, Any]:
    """Запись без возвращаемых данных: успех или сообщение об ошибке."""
    result = _script(statements, log=log)
    if not result.get("success"):
        return result
    return _done()


# ── сайты ────────────────────────────────────────────────────────────

_SITE_FIELDS = ("domain", "locales", "geo", "niche", "div",
                "tone_of_voice", "guardrails", "kpi_target")


def list_sites(include_archived: bool = False) -> Dict[str, Any]:
    sql = "SELECT * FROM VSEO_SITE"
    if not include_archived:
        sql += " WHERE ISARHIV = 0"
    sql += " ORDER BY DOMAIN"
    return _select(sql)


def save_site(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
    params = {name: payload.get(name) for name in _SITE_FIELDS}
    cod = payload.get("cod")

    if cod:
        params["cod"] = cod
        sql = ("UPDATE YSEO_SITE SET DOMAIN = :domain, LOCALES = :locales, "
               "GEO = :geo, NICHE = :niche, DIV = :div, "
               "TONE_OF_VOICE = :tone_of_voice, GUARDRAILS = :guardrails, "
               "KPI_TARGET = :kpi_target WHERE COD = :cod")
        action = "SITE_UPDATE"
    else:
        sql = ("INSERT INTO YSEO_SITE (DOMAIN, LOCALES, GEO, NICHE, DIV, "
               "TONE_OF_VOICE, GUARDRAILS, KPI_TARGET) "
               "VALUES (:domain, :locales, :geo, :niche, :div, "
               ":tone_of_voice, :guardrails, :kpi_target)")
        action = "SITE_INSERT"

    return _write([(sql, params)],
                  log=(action, "SITE", cod, payload.get("domain"), username))


def archive_site(cod: int, username: str) -> Dict[str, Any]:
    return _write(
        [("UPDATE YSEO_SITE SET ISARHIV = 1 WHERE COD = :cod", {"cod": cod})],
        log=("SITE_ARCHIVE", "SITE", cod, None, username))


# ── площадки ─────────────────────────────────────────────────────────

_PLATFORM_FIELDS = ("platform_code", "name", "url", "channel_cod1", "geo",
                    "has_api", "manual_publish", "quality_score",
                    "rate_limit_day", "posting_rules")


def list_platforms(include_archived: bool = False) -> Dict[str, Any]:
    sql = ("SELECT p.*, d.CODE AS CHANNEL_CODE FROM YSEO_PLATFORM p "
           "JOIN YSEO_DICT d ON d.COD1 = p.CHANNEL_COD1")
    if not include_archived:
        sql += " WHERE p.ISARHIV = 0"
    sql += " ORDER BY p.PLATFORM_CODE"
    return _select(sql)


def save_platform(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
    params = {name: payload.get(name) for name in _PLATFORM_FIELDS}
    cod = payload.get("cod")

    if cod:
        params["cod"] = cod
        sql = ("UPDATE YSEO_PLATFORM SET PLATFORM_CODE = :platform_code, "
               "NAME = :name, URL = :url, CHANNEL_COD1 = :channel_cod1, "
               "GEO = :geo, HAS_API = :has_api, "
               "MANUAL_PUBLISH = :manual_publish, "
               "QUALITY_SCORE = :quality_score, "
               "RATE_LIMIT_DAY = :rate_limit_day, "
               "POSTING_RULES = :posting_rules WHERE COD = :cod")
        action = "PLATFORM_UPDATE"
    else:
        sql = ("INSERT INTO YSEO_PLATFORM (PLATFORM_CODE, NAME, URL, "
               "CHANNEL_COD1, GEO, HAS_API, MANUAL_PUBLISH, QUALITY_SCORE, "
               "RATE_LIMIT_DAY, POSTING_RULES) "
               "VALUES (:platform_code, :name, :url, :channel_cod1, :geo, "
               ":has_api, :manual_publish, :quality_score, :rate_limit_day, "
               ":posting_rules)")
        action = "PLATFORM_INSERT"

    return _write([(sql, params)],
                  log=(action, "PLATFORM", cod, payload.get("platform_code"),
                       username))


def archive_platform(cod: int, username: str) -> Dict[str, Any]:
    return _write(
        [("UPDATE YSEO_PLATFORM SET ISARHIV = 1 WHERE COD = :cod", {"cod": cod})],
        log=("PLATFORM_ARCHIVE", "PLATFORM", cod, None, username))


# ── справочники и курсы ──────────────────────────────────────────────

def list_dict(section: Optional[str] = None,
              include_archived: bool = False) -> Dict[str, Any]:
    sql = "SELECT * FROM YSEO_DICT WHERE 1 = 1"
    params: Dict[str, Any] = {}
    if section:
        sql += " AND SECTION = :section"
        params["section"] = section
    if not include_archived:
        sql += " AND ISARHIV = 0"
    sql += " ORDER BY SECTION, SORT_ORDER, COD1"
    return _select(sql, params)


def save_dict(section: str, payload: Dict[str, Any],
              username: str) -> Dict[str, Any]:
    params = {
        "section": section,
        "code": payload.get("code"),
        "name_ru": payload.get("name_ru"),
        "name_ro": payload.get("name_ro"),
        "name_en": payload.get("name_en"),
        "sort_order": payload.get("sort_order") or 100,
        "isarhiv": 1 if payload.get("isarhiv") else 0,
    }
    cod1 = payload.get("cod1")

    if cod1:
        params["cod1"] = cod1
        sql = ("UPDATE YSEO_DICT SET CODE = :code, NAME_RU = :name_ru, "
               "NAME_RO = :name_ro, NAME_EN = :name_en, "
               "SORT_ORDER = :sort_order, ISARHIV = :isarhiv "
               "WHERE SECTION = :section AND COD1 = :cod1")
        action = "DICT_UPDATE"
    else:
        sql = ("INSERT INTO YSEO_DICT (SECTION, CODE, NAME_RU, NAME_RO, "
               "NAME_EN, SORT_ORDER, ISARHIV) "
               "VALUES (:section, :code, :name_ru, :name_ro, :name_en, "
               ":sort_order, :isarhiv)")
        action = "DICT_INSERT"

    return _write([(sql, params)],
                  log=(action, "DICT", cod1,
                       f"{section} {payload.get('code')}", username))


def list_fx() -> Dict[str, Any]:
    return _select("SELECT * FROM YSEO_FX_RATE ORDER BY VALUTA, RATE_DATE DESC")


def save_fx(valuta: str, rate_date: str, rate: float,
            username: str) -> Dict[str, Any]:
    sql = ("MERGE INTO YSEO_FX_RATE t "
           "USING (SELECT :valuta AS VALUTA, "
           "TO_DATE(:rate_date, 'YYYY-MM-DD') AS RATE_DATE FROM DUAL) s "
           "ON (t.VALUTA = s.VALUTA AND t.RATE_DATE = s.RATE_DATE) "
           "WHEN MATCHED THEN UPDATE SET t.RATE = :rate "
           "WHEN NOT MATCHED THEN INSERT (VALUTA, RATE_DATE, RATE) "
           "VALUES (s.VALUTA, s.RATE_DATE, :rate)")
    params = {"valuta": (valuta or "").upper(), "rate_date": rate_date,
              "rate": rate}
    return _write([(sql, params)],
                  log=("FX_UPSERT", "FX_RATE", None,
                       f"{valuta} {rate_date} {rate}", username))


# ── кампании ─────────────────────────────────────────────────────────

_CAMPAIGN_FIELDS = ("camp_code", "site_cod", "name_ru", "name_ro", "name_en",
                    "promo_type_cod1", "discount_value", "promo_code",
                    "scope_kind", "limit_qty", "limit_sum", "budget_plan",
                    "kpi_target", "legal_text_ref")


def list_campaigns(site_cod: Optional[int] = None,
                   include_archived: bool = False) -> Dict[str, Any]:
    sql = "SELECT * FROM VSEO_CAMPAIGN WHERE 1 = 1"
    params: Dict[str, Any] = {}
    if site_cod:
        sql += " AND SITE_COD = :site_cod"
        params["site_cod"] = site_cod
    if not include_archived:
        sql += " AND ISARHIV = 0"
    sql += " ORDER BY DATE_START DESC, CAMP_CODE"
    return _select(sql, params)


def save_campaign(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
    params = {name: payload.get(name) for name in _CAMPAIGN_FIELDS}
    params["scope_kind"] = payload.get("scope_kind") or "SITE"
    params["budget_plan"] = payload.get("budget_plan") or 0
    params["date_start"] = payload.get("date_start")
    params["date_end"] = payload.get("date_end")
    cod = payload.get("cod")

    if cod:
        params["cod"] = cod
        sql = ("UPDATE YSEO_CAMPAIGN SET CAMP_CODE = :camp_code, "
               "SITE_COD = :site_cod, NAME_RU = :name_ru, NAME_RO = :name_ro, "
               "NAME_EN = :name_en, PROMO_TYPE_COD1 = :promo_type_cod1, "
               "DISCOUNT_VALUE = :discount_value, PROMO_CODE = :promo_code, "
               "SCOPE_KIND = :scope_kind, "
               "DATE_START = TO_DATE(:date_start, 'YYYY-MM-DD'), "
               "DATE_END = TO_DATE(:date_end, 'YYYY-MM-DD'), "
               "LIMIT_QTY = :limit_qty, LIMIT_SUM = :limit_sum, "
               "BUDGET_PLAN = :budget_plan, KPI_TARGET = :kpi_target, "
               "LEGAL_TEXT_REF = :legal_text_ref WHERE COD = :cod")
        action = "CAMPAIGN_UPDATE"
    else:
        sql = ("INSERT INTO YSEO_CAMPAIGN (CAMP_CODE, SITE_COD, NAME_RU, "
               "NAME_RO, NAME_EN, PROMO_TYPE_COD1, DISCOUNT_VALUE, "
               "PROMO_CODE, SCOPE_KIND, DATE_START, DATE_END, LIMIT_QTY, "
               "LIMIT_SUM, BUDGET_PLAN, KPI_TARGET, LEGAL_TEXT_REF) "
               "VALUES (:camp_code, :site_cod, :name_ru, :name_ro, :name_en, "
               ":promo_type_cod1, :discount_value, :promo_code, :scope_kind, "
               "TO_DATE(:date_start, 'YYYY-MM-DD'), "
               "TO_DATE(:date_end, 'YYYY-MM-DD'), :limit_qty, :limit_sum, "
               ":budget_plan, :kpi_target, :legal_text_ref)")
        action = "CAMPAIGN_INSERT"

    return _write([(sql, params)],
                  log=(action, "CAMPAIGN", cod, payload.get("camp_code"),
                       username))


def set_campaign_status(cod: int, status: str, username: str) -> Dict[str, Any]:
    return _write(
        [("UPDATE YSEO_CAMPAIGN SET STATUS = :status WHERE COD = :cod",
          {"status": status, "cod": cod})],
        log=("CAMPAIGN_STATUS", "CAMPAIGN", cod, status, username))


def archive_campaign(cod: int, username: str) -> Dict[str, Any]:
    return _write(
        [("UPDATE YSEO_CAMPAIGN SET ISARHIV = 1 WHERE COD = :cod", {"cod": cod})],
        log=("CAMPAIGN_ARCHIVE", "CAMPAIGN", cod, None, username))


# ── бюджет ───────────────────────────────────────────────────────────

def plan_upsert(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
    """План пишется только через пакет: там лимит, проверка курса и журнал."""
    sql = ("BEGIN PK_SEO_BUDGET.PLAN_UPSERT(:period, :article, :channel, "
           ":site, :suma, :valuta, :note, :username); END;")
    params = {
        "period": payload.get("period"),
        "article": payload.get("article_cod1"),
        "channel": payload.get("channel_cod1"),
        "site": payload.get("site_cod"),
        "suma": payload.get("plan_suma") or 0,
        "valuta": payload.get("valuta") or "MDL",
        "note": payload.get("note"),
        "username": username or "system",
    }
    return _write([(sql, params)])


def planfact(period: Optional[str] = None,
             site_cod: Optional[int] = None) -> Dict[str, Any]:
    sql = ("SELECT f.*, "
           "a.CODE AS ARTICLE_CODE, a.NAME_RU AS ARTICLE_NAME_RU, "
           "a.NAME_RO AS ARTICLE_NAME_RO, a.NAME_EN AS ARTICLE_NAME_EN, "
           "c.CODE AS CHANNEL_CODE, s.DOMAIN AS SITE_DOMAIN "
           "FROM VSEO_BUDGET_PLANFACT f "
           "LEFT JOIN YSEO_DICT a ON a.COD1 = f.ARTICLE_COD1 "
           "LEFT JOIN YSEO_DICT c ON c.COD1 = f.CHANNEL_COD1 "
           "LEFT JOIN YSEO_SITE s ON s.COD = f.SITE_COD "
           "WHERE 1 = 1")
    params: Dict[str, Any] = {}
    if period:
        sql += " AND f.PERIOD = :period"
        params["period"] = period
    if site_cod:
        sql += " AND f.SITE_COD = :site_cod"
        params["site_cod"] = site_cod
    sql += " ORDER BY f.PERIOD DESC, ARTICLE_CODE, CHANNEL_CODE"
    return _select(sql, params)


# ── факты ────────────────────────────────────────────────────────────

def list_spend(period: Optional[str] = None,
               site_cod: Optional[int] = None,
               limit: int = 500) -> Dict[str, Any]:
    sql = ("SELECT f.*, s.DOMAIN AS SITE_DOMAIN, c.CODE AS CHANNEL_CODE, "
           "a.CODE AS ARTICLE_CODE, k.CAMP_CODE AS CAMP_CODE "
           "FROM YSEO_SPEND_FACT f "
           "JOIN YSEO_SITE s ON s.COD = f.SITE_COD "
           "JOIN YSEO_DICT c ON c.COD1 = f.CHANNEL_COD1 "
           "JOIN YSEO_DICT a ON a.COD1 = f.ARTICLE_COD1 "
           "LEFT JOIN YSEO_CAMPAIGN k ON k.COD = f.CAMP_COD "
           "WHERE 1 = 1")
    params: Dict[str, Any] = {"row_limit": limit}
    if period:
        sql += " AND f.PERIOD = :period"
        params["period"] = period
    if site_cod:
        sql += " AND f.SITE_COD = :site_cod"
        params["site_cod"] = site_cod
    sql += " ORDER BY f.SPEND_DATE DESC, f.COD DESC"
    return _select(_limited(sql), params)


def list_metrics(period: Optional[str] = None,
                 site_cod: Optional[int] = None,
                 limit: int = 500) -> Dict[str, Any]:
    sql = ("SELECT f.*, s.DOMAIN AS SITE_DOMAIN, m.CODE AS METRIC_CODE, "
           "c.CODE AS CHANNEL_CODE "
           "FROM YSEO_METRICS_FACT f "
           "JOIN YSEO_SITE s ON s.COD = f.SITE_COD "
           "JOIN YSEO_DICT m ON m.COD1 = f.METRIC_COD1 "
           "LEFT JOIN YSEO_DICT c ON c.COD1 = f.CHANNEL_COD1 "
           "WHERE 1 = 1")
    params: Dict[str, Any] = {"row_limit": limit}
    if period:
        sql += " AND f.PERIOD = :period"
        params["period"] = period
    if site_cod:
        sql += " AND f.SITE_COD = :site_cod"
        params["site_cod"] = site_cod
    sql += " ORDER BY f.FACT_DATE DESC, f.COD DESC"
    return _select(_limited(sql), params)


_SPEND_INSERT = (
    "INSERT INTO YSEO_SPEND_FACT (EXT_ID, SITE_COD, CAMP_COD, CHANNEL_COD1, "
    "PLATFORM_COD, ARTICLE_COD1, SPEND_DATE, PERIOD, SUMA, VALUTA, SUMA_MDL, "
    "CLICKS, IMPRESSIONS, CONVERSIONS, REVENUE, SOURCE, IMPORT_COD) "
    "SELECT :ext_id, s.COD, k.COD, c.COD1, NULL, a.COD1, "
    "TO_DATE(:spend_date, 'YYYY-MM-DD'), :period, :suma, :valuta, 0, "
    ":clicks, :impressions, :conversions, :revenue, :source, :import_cod "
    "FROM YSEO_SITE s "
    "JOIN YSEO_DICT c ON c.SECTION = 'CHANNEL' AND c.CODE = :channel "
    "JOIN YSEO_DICT a ON a.SECTION = 'ARTICLE' AND a.CODE = :article "
    "LEFT JOIN YSEO_CAMPAIGN k ON k.CAMP_CODE = :campaign "
    "WHERE s.DOMAIN = :site"
)

_METRICS_INSERT = (
    "INSERT INTO YSEO_METRICS_FACT (EXT_ID, SITE_COD, METRIC_COD1, "
    "CHANNEL_COD1, FACT_DATE, PERIOD, METRIC_VALUE, SOURCE, IMPORT_COD) "
    "SELECT :ext_id, s.COD, m.COD1, c.COD1, "
    "TO_DATE(:fact_date, 'YYYY-MM-DD'), :period, :value, :source, :import_cod "
    "FROM YSEO_SITE s "
    "JOIN YSEO_DICT m ON m.SECTION = 'METRIC' AND m.CODE = :metric "
    "LEFT JOIN YSEO_DICT c ON c.SECTION = 'CHANNEL' AND c.CODE = :channel "
    "WHERE s.DOMAIN = :site"
)


def _spend_params(row: Dict[str, Any], import_cod, source: str) -> Dict[str, Any]:
    return {
        "ext_id": row.get("ext_id"),
        "site": row.get("site"),
        "channel": row.get("channel"),
        "article": row.get("article"),
        "campaign": row.get("campaign") or None,
        "spend_date": row.get("spend_date"),
        "period": row.get("period"),
        "suma": row.get("suma") or 0,
        "valuta": row.get("valuta") or "MDL",
        "clicks": row.get("clicks") or 0,
        "impressions": row.get("impressions") or 0,
        "conversions": row.get("conversions") or 0,
        "revenue": row.get("revenue") or 0,
        "source": source,
        "import_cod": import_cod,
    }


def _metrics_params(row: Dict[str, Any], import_cod, source: str) -> Dict[str, Any]:
    return {
        "ext_id": row.get("ext_id"),
        "site": row.get("site"),
        "metric": row.get("metric"),
        "channel": row.get("channel") or None,
        "fact_date": row.get("fact_date"),
        "period": row.get("period"),
        "value": row.get("value") or 0,
        "source": row.get("source") or source,
        "import_cod": import_cod,
    }


_FACT_WRITERS = {
    "SPEND": (_SPEND_INSERT, _spend_params, "SPEND_ADD"),
    "METRICS": (_METRICS_INSERT, _metrics_params, "METRICS_ADD"),
}


def add_fact(kind: str, row: Dict[str, Any], username: str) -> Dict[str, Any]:
    """Ручной ввод одной строки факта."""
    if kind not in _FACT_WRITERS:
        raise ValueError(f"unknown fact kind: {kind!r}")
    sql, build, action = _FACT_WRITERS[kind]
    return _write([(sql, build(row, None, "MANUAL"))],
                  log=(action, kind, None, row.get("ext_id"), username))


def add_spend(row: Dict[str, Any], username: str) -> Dict[str, Any]:
    return add_fact("SPEND", row, username)


def add_metrics(row: Dict[str, Any], username: str) -> Dict[str, Any]:
    return add_fact("METRICS", row, username)


def existing_ext_ids(kind: str, ext_ids: Iterable[str]) -> set:
    """Какие из переданных ключей уже есть в базе.

    Пустой список не порождает запроса: пустое `IN ()` в Oracle — ошибка,
    да и ходить в базу незачем.
    """
    if kind not in _FACT_TABLES:
        raise ValueError(f"unknown fact kind: {kind!r}")
    values = [value for value in (ext_ids or []) if value]
    if not values:
        return set()

    # Oracle не принимает больше 1000 элементов в IN, а выгрузки бывают
    # длиннее: режем на порции и объединяем.
    known = set()
    for start in range(0, len(values), 900):
        chunk = values[start:start + 900]
        binds = {f"e{i}": value for i, value in enumerate(chunk)}
        placeholders = ", ".join(f":{name}" for name in binds)
        sql = (f"SELECT EXT_ID FROM {_FACT_TABLES[kind]} "
               f"WHERE EXT_ID IN ({placeholders})")
        with Biro26DB() as db:
            result = db.execute_query(sql, binds)
        known |= {row["ext_id"] for row in _rows(result)}
    return known


def next_import_cod() -> Optional[int]:
    """Номер будущей партии импорта.

    Берётся отдельным запросом ДО транзакции, а не внутри неё: иначе номер
    пришлось бы тянуть через CURRVAL, и та же команда INSERT перестала бы
    годиться для ручного ввода — там последовательность в сессии не
    использовалась и CURRVAL упал бы с ORA-08002. Потерянный при сбое
    номер последовательности ничего не стоит.
    """
    with Biro26DB() as db:
        result = db.execute_query(
            "SELECT YSEO_IMPORT_SEQ.NEXTVAL AS COD FROM DUAL")
    rows = _rows(result)
    return rows[0]["cod"] if rows else None


def import_commit(kind: str, file_name: str, rows: Sequence[Dict[str, Any]],
                  username: str) -> Dict[str, Any]:
    """Пишет партию импорта и её строки, пропуская уже загруженные ключи.

    Партия и строки идут одной транзакцией: если не запишется хоть одна
    строка, не останется и партии — иначе в журнале импорта висели бы
    записи о загрузках, которых не было.
    """
    if kind not in _FACT_WRITERS:
        raise ValueError(f"unknown fact kind: {kind!r}")

    rows = list(rows or [])
    known = existing_ext_ids(kind, [row.get("ext_id") for row in rows])
    fresh = [row for row in rows if row.get("ext_id") not in known]
    skipped = len(rows) - len(fresh)

    insert_sql, build, action = _FACT_WRITERS[kind]
    import_cod = next_import_cod()

    statements = [(
        "INSERT INTO YSEO_IMPORT (COD, KIND, FILE_NAME, USERNAME, ROWS_TOTAL, "
        "ROWS_LOADED, ROWS_SKIPPED, STATUS) "
        "VALUES (:cod, :kind, :file_name, :username, :total, :loaded, "
        ":skipped, :status)",
        {"cod": import_cod, "kind": kind, "file_name": file_name,
         "username": username, "total": len(rows), "loaded": len(fresh),
         "skipped": skipped,
         "status": "OK" if len(fresh) == len(rows) else "PARTIAL"})]

    statements += [(insert_sql, build(row, import_cod, "CSV"))
                   for row in fresh]

    outcome = _write(
        statements,
        log=(action, kind, import_cod,
             f"{file_name}: loaded={len(fresh)} skipped={skipped}", username))

    if not outcome.get("success"):
        return outcome
    return _done({"import_cod": import_cod,
                  "loaded": len(fresh), "skipped": skipped})


# ── отчёты, настройки, журнал ────────────────────────────────────────

def roi(period_from: Optional[str] = None, period_to: Optional[str] = None,
        site_cod: Optional[int] = None) -> Dict[str, Any]:
    sql = "SELECT * FROM VSEO_CHANNEL_ROI WHERE 1 = 1"
    params: Dict[str, Any] = {}
    if period_from:
        sql += " AND PERIOD >= :period_from"
        params["period_from"] = period_from
    if period_to:
        sql += " AND PERIOD <= :period_to"
        params["period_to"] = period_to
    if site_cod:
        sql += " AND SITE_COD = :site_cod"
        params["site_cod"] = site_cod
    sql += " ORDER BY PERIOD DESC, SPEND_SUMA DESC"
    return _select(sql, params)


def list_imports(limit: int = 100) -> Dict[str, Any]:
    return _select(
        _limited("SELECT * FROM YSEO_IMPORT ORDER BY LOADED_AT DESC, COD DESC"),
        {"row_limit": limit})


def get_settings() -> Dict[str, Any]:
    return _select("SELECT * FROM YSEO_SETUP ORDER BY PARAM_CODE")


def save_settings(values: Dict[str, str], username: str) -> Dict[str, Any]:
    statements = [
        ("UPDATE YSEO_SETUP SET PARAM_VALUE = :value WHERE PARAM_CODE = :code",
         {"value": value, "code": code})
        for code, value in (values or {}).items()
    ]
    if not statements:
        return _done()
    return _write(statements,
                  log=("SETTINGS_UPDATE", "SETUP", None,
                       ", ".join(f"{k}={v}" for k, v in values.items()),
                       username))


def list_events(limit: int = 200) -> Dict[str, Any]:
    return _select(
        _limited("SELECT * FROM YSEO_EVENT_LOG ORDER BY CREATED_AT DESC, COD DESC"),
        {"row_limit": limit})
