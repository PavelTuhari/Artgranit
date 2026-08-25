"""Бэк-офис UNA в вебе — запись документов.

Вынесено в отдельный файл сознательно: `store.py` остаётся доказуемо
read-only (это закреплено тестом), а всё, что меняет боевой учёт, собрано
здесь — в одном небольшом файле, который можно прочитать целиком перед
тем, как разрешить запись.

## Что здесь можно и чего нельзя

Запись разрешена **только для собственных типов документов** контура
SEOForge — диапазон `DB ID` 60000..60099, заведённый под маркетинг.
Любой другой `SYSFID` отклоняется. Причина простая: чужие типы документов
имеют свои настройки проводок, свои обязательные реквизиты и свою
ответственность. Ошибиться в них из веба — значит испортить чужой учёт.

Расширять диапазон следует осознанно и по одному типу, вместе с тем, кто
отвечает за этот участок учёта.

## Авторство

`TMDB_DOCS.USERID` штатно подставляет триггер из сессионного параметра
`PARAM_USERID`. Веб-пользователь порталу известен, но соответствия
«пользователь портала → пользователь UNA» нет, а подставить чужой
идентификатор хуже, чем оставить пустой: документ будет числиться за
человеком, который его не делал.

Поэтому: если `BIRO26WEB_UNA_USERID` задан в окружении, он выставляется
через `SET_ENV` и попадает в документ; если нет — автор остаётся пустым,
а имя пользователя портала пишется в примечание документа. Ответ всегда
сообщает, каким из двух путей пошло дело.

## Проведение

Проводки генерирует `UN$GFC` по настройкам самого документа — так это
делают штатные пакеты схемы (`PKG_SALES`, `PKG_ORDERS_DOCS`):

    un$gfc.setDoc_GFC(nrdoc);
    un$gfc.setDoc_Correct(nrdoc);

Прямых `INSERT` в `TMDB_CM` здесь нет и быть не должно.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from models.biro26_db import Biro26DB

# Типы документов, которые модулю разрешено создавать. Это диапазон,
# заведённый контуром SEOForge под маркетинг: свои типы, свой журнал,
# своя ответственность.
WRITABLE_FROM, WRITABLE_TO = 60000, 60099

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class WriteRefused(Exception):
    """Запись отклонена до обращения к базе."""


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _done(data: Any = None, message: str = "") -> Dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def is_writable(sysfid: Optional[int]) -> bool:
    return (sysfid is not None
            and WRITABLE_FROM <= int(sysfid) <= WRITABLE_TO)


def una_userid() -> Optional[int]:
    raw = (os.environ.get("BIRO26WEB_UNA_USERID") or "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _rows(result: Dict[str, Any]):
    if not result.get("success"):
        return []
    columns = [c.lower() for c in (result.get("columns") or [])]
    return [dict(zip(columns, row)) for row in (result.get("data") or [])]


def create_document(sysfid: int, date: str, *, valuta: str = "LEI",
                    nrset: Optional[int] = None, div: Optional[int] = None,
                    comment: Optional[str] = None,
                    username: Optional[str] = None) -> Dict[str, Any]:
    """Создаёт документ разрешённого типа и возвращает его номер."""
    if not is_writable(sysfid):
        return _fail(
            f"тип документа {sysfid} вне разрешённого диапазона "
            f"{WRITABLE_FROM}..{WRITABLE_TO}: из веба можно создавать только "
            "собственные документы модуля")

    if not date or not _DATE_RE.match(date):
        return _fail("дата документа: ожидается формат YYYY-MM-DD")

    author = una_userid()
    note_parts = [p for p in (comment,
                              f"создан из веб-бэкофиса пользователем "
                              f"{username or 'system'}") if p]
    note = " | ".join(note_parts)[:4000]

    with Biro26DB() as db:
        # Номер берём заранее: RETURNING слой не поддерживает, а MAX(COD)+1
        # при одновременной работе двух сессий даёт дубль ключа.
        got = db.execute_query("SELECT ID_TMDB_DOCS.NEXTVAL AS COD FROM DUAL")
        rows = _rows(got)
        if not rows:
            return _fail(got.get("message", "не удалось получить номер документа"))
        cod = int(rows[0]["cod"])

        statements = []
        if author is not None:
            statements.append({
                "sql": "BEGIN SET_ENV('PARAM_USERID', :author_id); END;",
                "params": {"author_id": str(author)}, "kind": "dml"})

        # Имена bind-переменных :uid и :div недопустимы: UID — встроенная
        # функция Oracle, и запрос падает с ORA-01745. Отсюда :author_id
        # и :division.
        statements.append({
            "sql": "INSERT INTO TMDB_DOCS (COD, TIP, SYSFID, DATAMANUAL, "
                   "VALUTA, NRSET, DIV, USERID) "
                   "VALUES (:cod, 'H', :sysfid, "
                   "TO_DATE(:ddate, 'YYYY-MM-DD'), :valuta, :nrset, "
                   ":division, :author_id)",
            "params": {"cod": cod, "sysfid": int(sysfid), "ddate": date,
                       "valuta": valuta or "LEI", "nrset": nrset,
                       "division": div, "author_id": author},
            "kind": "dml"})

        statements.append({
            "sql": "INSERT INTO TMDB_DOCS_ADD (COD, TXTCOMMENT) "
                   "VALUES (:cod, :note)",
            "params": {"cod": cod, "note": note}, "kind": "dml"})

        result = db.execute_script(statements)

    if not result.get("success"):
        return _fail(result.get("message", ""))

    return _done({"cod": cod, "sysfid": int(sysfid), "date": date,
                  "userid": author},
                 "автор документа проставлен из BIRO26WEB_UNA_USERID"
                 if author is not None else
                 "автор документа не проставлен: соответствие пользователя "
                 "портала пользователю UNA не настроено")


def post_document(cod: int) -> Dict[str, Any]:
    """Проводит документ через UN$GFC — как это делают пакеты схемы."""
    with Biro26DB() as db:
        head = _rows(db.execute_query(
            "SELECT SYSFID, ISGFC FROM TMDB_DOCS WHERE COD = :c", {"c": cod}))
        if not head:
            return _fail("документ не найден")

        sysfid = head[0].get("sysfid")
        if not is_writable(sysfid):
            return _fail(
                f"документ типа {sysfid} вне разрешённого диапазона "
                f"{WRITABLE_FROM}..{WRITABLE_TO}: проводить чужие документы "
                "из веба нельзя")

        if head[0].get("isgfc"):
            return _fail("документ уже проведён")

        result = db.call_proc(
            "BEGIN UN$GFC.setDoc_GFC(:c); UN$GFC.setDoc_Correct(:c); END;",
            {"c": int(cod)})

    if not result.get("success"):
        return _fail(result.get("message", ""))

    with Biro26DB() as db:
        after = _rows(db.execute_query(
            "SELECT ISGFC, (SELECT COUNT(*) FROM TMDB_CM WHERE NRDOC = :c) CM "
            "FROM TMDB_DOCS WHERE COD = :c", {"c": int(cod)}))

    state = after[0] if after else {}
    return _done({"cod": cod, "isgfc": state.get("isgfc"),
                  "postings": state.get("cm")})
