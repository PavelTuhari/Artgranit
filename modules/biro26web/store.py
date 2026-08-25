"""Бэк-офис UNA в вебе — чтение ERP.

Модуль показывает то же, что дельфийский клиент UNA, и берёт это из тех же
мест: журналы и типы документов — из дерева конфигурации (`A$ADM$V`),
документы — из `TMDB_DOCS`, проводки — из `TMDB_CM`. Ничего не выдумывает
и ничего не пишет: слой только читает.

Почему так, а не «свой список журналов»: конфигурация — единственный
источник правды о том, какие журналы есть и какие документы в них попадают.
Захардкоженный список разошёлся бы с клиентом в первый же день, когда
администратор заведёт новый тип документа.

Транспорт — `models/biro26_db.py`: ERP это Oracle 11g в thick-режиме,
и ходить туда можно только отдельным процессом.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from models.biro26_db import Biro26DB

# Витрины строк документа по семействам. Общей витрины строк в UNA нет:
# каждый DLL-модуль хранит строки по-своему. Что известно — перечислено
# здесь; для остальных типов строки не показываем и говорим об этом прямо,
# вместо того чтобы показать пустую таблицу и выдать её за «строк нет».
LINE_VIEWS = {
    "201": ("VMDB_ST201D", "VMDB_ST201M"),
    "202": ("VMDB_CMN202D", "VMDB_CMN202M"),
}

# Фильтр журнала — сырой SQL из конфигурации. Он попадает в WHERE, поэтому
# пропускаем только то, из чего реальные фильтры и состоят: сравнения
# SYSFID/ID с числами, скобки и логические связки. Строка из конфигурации
# не приходит от пользователя, но испорченная запись в конфигурации иначе
# стала бы инъекцией в бэк-офис.
_FILTER_TOKEN = re.compile(
    r"""^(?: \s+
          | \d+
          | [()]
          | (?i:sysfid|id|isvalid)
          | <=|>=|<>|!=|=|<|>
          | (?i:and|or|not|in|between)
          | ,
        )+$""",
    re.X,
)


class UnsafeFilter(ValueError):
    """Фильтр журнала не прошёл проверку и в запрос не пойдёт."""


def is_safe_filter(text: str) -> bool:
    return bool(text) and bool(_FILTER_TOKEN.match(text.replace("\n", " ")))


def _rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not result.get("success"):
        return []
    columns = [c.lower() for c in (result.get("columns") or [])]
    return [dict(zip(columns, row)) for row in (result.get("data") or [])]


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _done(data: Any = None) -> Dict[str, Any]:
    return {"success": True, "data": data, "message": ""}


def _select(sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with Biro26DB() as db:
        result = db.execute_query(sql, params or {})
    if not result.get("success"):
        return _fail(result.get("message", ""))
    return _done(_rows(result))


# ── журналы из конфигурации ──────────────────────────────────────────

_JOURNAL_FIELDS = """
    n.OBJ_ID, n.PARENT_ID, n.SECTION, n.NAME, n.NRORD,
    (SELECT VALUE FROM A$ADP$V WHERE OBJ_ID = n.OBJ_ID AND KEY = 'CAPTION') CAPTION,
    (SELECT VALUE FROM A$ADP$V WHERE OBJ_ID = n.OBJ_ID AND KEY = 'ACTIVE') ACTIVE
"""


def journal_tree() -> Dict[str, Any]:
    """Группы журналов и журналы в них — как в дереве клиента UNA."""
    groups = _select(
        f"SELECT {_JOURNAL_FIELDS} FROM A$ADM$V n "
        "WHERE n.OBJ_TYPE = 2 AND n.OBJ_SUBTYPE = -1 "
        "ORDER BY n.NRORD, n.NAME")
    if not groups.get("success"):
        return groups

    journals = _select(
        f"SELECT {_JOURNAL_FIELDS} FROM A$ADM$V n "
        "WHERE n.OBJ_TYPE = 2 AND n.OBJ_SUBTYPE = 0 "
        "ORDER BY NVL((SELECT VALUE FROM A$ADP$V "
        "WHERE OBJ_ID = n.OBJ_ID AND KEY = 'CAPTION'), n.NAME)")
    if not journals.get("success"):
        return journals

    by_parent: Dict[Any, List[Dict[str, Any]]] = {}
    for row in journals["data"]:
        row["title"] = row.get("caption") or row.get("name")
        by_parent.setdefault(row.get("parent_id"), []).append(row)

    tree = []
    for group in groups["data"]:
        group["title"] = group.get("caption") or group.get("name")
        group["journals"] = by_parent.pop(group["obj_id"], [])
        tree.append(group)

    # Журналы без группы или с группой, которой уже нет: в клиенте они
    # висят в корне, и прятать их нельзя — иначе часть документов станет
    # недоступной, а понять почему будет нечем.
    orphans = [row for rows in by_parent.values() for row in rows]
    if orphans:
        tree.append({"obj_id": None, "title": "Без группы",
                     "journals": sorted(orphans, key=lambda r: r["title"] or "")})

    return _done(tree)


def journal(obj_id: int) -> Dict[str, Any]:
    """Карточка журнала вместе с его фильтром документов."""
    rows = _select(
        f"SELECT {_JOURNAL_FIELDS}, "
        "(SELECT TO_CHAR(SUBSTR(LVALUE, 1, 4000)) FROM A$ADP$V "
        " WHERE OBJ_ID = n.OBJ_ID AND KEY = 'SQLFILTER') SQLFILTER, "
        "(SELECT VALUE FROM A$ADP$V "
        " WHERE OBJ_ID = n.OBJ_ID AND KEY = 'DOCTYPESDEFAULT') DOCTYPESDEFAULT "
        "FROM A$ADM$V n "
        "WHERE n.OBJ_TYPE = 2 AND n.OBJ_SUBTYPE = 0 AND n.OBJ_ID = :o",
        {"o": obj_id})
    if not rows.get("success"):
        return rows
    if not rows["data"]:
        return _fail("журнал не найден")

    row = rows["data"][0]
    row["title"] = row.get("caption") or row.get("name")
    return _done(row)


# ── типы документов ──────────────────────────────────────────────────

def document_types() -> Dict[str, Any]:
    """SYSFID -> тип документа. Связь проверена: SYSFID = свойство DB ID."""
    return _select(
        "SELECT TO_NUMBER(dbid.VALUE) SYSFID, n.OBJ_ID, n.SECTION, n.NAME, "
        "dll.VALUE DLL_ID, dn.VALUE DOCNAME "
        "FROM A$ADM$V n "
        "JOIN A$ADP$V dbid ON dbid.OBJ_ID = n.OBJ_ID AND dbid.KEY = 'DB ID' "
        "LEFT JOIN A$ADP$V dll ON dll.OBJ_ID = n.OBJ_ID AND dll.KEY = 'DLL ID' "
        "LEFT JOIN A$ADP$V dn ON dn.OBJ_ID = n.OBJ_ID AND dn.KEY = 'DOCNAME' "
        "WHERE n.OBJ_TYPE = 1 AND n.OBJ_SUBTYPE = 0 "
        "AND REGEXP_LIKE(dbid.VALUE, '^[0-9]+$')")


# ── документы журнала ────────────────────────────────────────────────

def documents(journal_id: int, limit: int = 200,
              date_from: Optional[str] = None,
              date_to: Optional[str] = None) -> Dict[str, Any]:
    """Документы журнала — по фильтру из конфигурации.

    Фильтр берётся из конфигурации по номеру журнала и никогда из запроса:
    запрос несёт только числовой `journal_id`. Даты — обычные bind-переменные.
    """
    card = journal(journal_id)
    if not card.get("success"):
        return card

    raw = (card["data"].get("sqlfilter") or "").strip()
    if not raw:
        return _done({"journal": card["data"], "rows": [],
                      "note": "у журнала не задан фильтр документов"})

    if not is_safe_filter(raw):
        return _fail("фильтр журнала содержит недопустимые конструкции "
                     "и в запрос не пойдёт")

    where = [f"({raw})"]
    params: Dict[str, Any] = {"row_limit": int(limit)}
    if date_from:
        where.append("d.DATAMANUAL >= TO_DATE(:date_from, 'YYYY-MM-DD')")
        params["date_from"] = date_from
    if date_to:
        where.append("d.DATAMANUAL <= TO_DATE(:date_to, 'YYYY-MM-DD')")
        params["date_to"] = date_to

    sql = (
        "SELECT * FROM ("
        "  SELECT d.COD, TRIM(d.NRMANUAL) NRMANUAL, d.SYSFID, d.VALUTA, "
        "         TO_CHAR(d.DATAMANUAL, 'YYYY-MM-DD') DDATE, "
        "         d.ISGFC, d.DOCCOLOR, d.USERID, d.DIV, "
        # Суммы документа здесь намеренно НЕТ. Напрашивающееся
        # SUM(TMDB_CM.SUMA) даёт ноль: проводки двойной записи
        # взаимопогашаются (проверено на документе 386 — двадцать проводок,
        # сумма 0, при этом строки документа дают 5100). Настоящая сумма
        # лежит в строках, а витрина строк у каждого семейства своя, и в
        # списке журнала её не собрать. Неверная сумма на экране хуже,
        # чем её отсутствие, поэтому показываем число проводок.
        "         (SELECT COUNT(*) FROM TMDB_CM c "
        "           WHERE c.NRDOC = d.COD) CM_COUNT "
        "  FROM TMDB_DOCS d "
        f"  WHERE {' AND '.join(where)} "
        "  ORDER BY d.DATAMANUAL DESC, d.COD DESC"
        ") WHERE ROWNUM <= :row_limit")

    rows = _select(sql, params)
    if not rows.get("success"):
        return rows

    types = {t["sysfid"]: t for t in (document_types().get("data") or [])}
    for row in rows["data"]:
        kind = types.get(row.get("sysfid")) or {}
        row["type_name"] = kind.get("name")
        row["docname"] = kind.get("docname")

    return _done({"journal": card["data"], "rows": rows["data"]})


# ── карточка документа ───────────────────────────────────────────────

def document(cod: int) -> Dict[str, Any]:
    head = _select(
        "SELECT d.COD, TRIM(d.NRMANUAL) NRMANUAL, "
        "TO_CHAR(d.DATAMANUAL, 'YYYY-MM-DD') DDATE, d.SYSFID, d.VALUTA, "
        "d.ISGFC, d.DOCCOLOR, d.USERID, d.DIV, d.TIP, d.NRSET, d.STATUS, "
        "(SELECT TO_CHAR(SUBSTR(a.TXTCOMMENT, 1, 2000)) FROM TMDB_DOCS_ADD a "
        "  WHERE a.COD = d.COD) TXTCOMMENT "
        "FROM TMDB_DOCS d WHERE d.COD = :c", {"c": cod})
    if not head.get("success"):
        return head
    if not head["data"]:
        return _fail("документ не найден")

    row = head["data"][0]
    kind = next((t for t in (document_types().get("data") or [])
                 if t["sysfid"] == row.get("sysfid")), {})
    row["type_name"] = kind.get("name")
    row["docname"] = kind.get("docname")
    return _done(row)


def document_lines(cod: int, docname: Optional[str] = None) -> Dict[str, Any]:
    """Строки документа из витрины его семейства.

    Общей витрины строк в UNA нет. Если для типа она неизвестна, честно
    возвращаем пустой список с пояснением: пустая таблица без пояснения
    читалась бы как «в документе нет строк».
    """
    family = (docname or "").strip()
    view = LINE_VIEWS.get(family, (None, None))[0]
    if view is None:
        return _done({"rows": [],
                      "note": f"строки документов вида «{family or '—'}» "
                              "в вебе пока не подключены"})

    rows = _select(
        f"SELECT l.CTSC, l.CANT, l.PRET, l.SUMA, "
        "u.DENUMIREA, u.UM, u.CODVECHI "
        f"FROM {view} l LEFT JOIN TMS_UNIVERS u ON u.COD = l.CTSC "
        "WHERE l.NRDOC = :c ORDER BY l.RROWID", {"c": cod})
    if not rows.get("success"):
        return rows
    return _done({"rows": rows["data"], "note": None})


def document_postings(cod: int) -> Dict[str, Any]:
    """Проводки документа. Работает для любого типа: TMDB_CM общая."""
    return _select(
        "SELECT c.COD, TO_CHAR(c.DATA, 'YYYY-MM-DD') DATA, c.FUNCT, "
        "c.DT, c.DTSC, c.DTDEP, c.CT, c.CTSC, c.CTDEP, "
        "c.CANT, c.SUMA, c.VALUTADT, c.ISVALID "
        "FROM TMDB_CM c WHERE c.NRDOC = :c "
        "ORDER BY c.COD", {"c": cod})
