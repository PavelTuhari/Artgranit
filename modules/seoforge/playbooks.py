"""SEOForge — стратегии и плейбуки: хранение Markdown в контуре.

ТЗ платформы требует, чтобы работа велась версионируемыми `.md`-файлами:
стратегия, планы, инструкции для AI-сессий. Это не учётные документы, им
нечего делать в `TMDB_DOCS`, но храниться они должны рядом с контуром и
с полной историей — иначе через полгода не восстановить, почему решение
было принято именно таким.

Главное правило: **опубликованная версия неизменяема**. Правка создаёт
новую версию, а не переписывает старую. Держит это триггер в базе, а не
договорённость.

`BODY_SHA` — отпечаток текста. По нему видно, совпадает ли то, что лежит
в контуре, с файлом в репозитории: расхождение означает, что кто-то правил
документ мимо репозитория, и это надо заметить, а не гадать.
"""
from __future__ import annotations

import hashlib
import os
import sys
from typing import Any, Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from models.biro26_db import Biro26DB

KINDS = ("STRATEGY", "PLAYBOOK", "PLAN", "REPORT")
STATUSES = ("DRAFT", "ACTIVE", "ARCHIVED")

# Кодировка учётной базы. CLOB хранит текст в ней, и символ, которого в
# ней нет, Oracle молча заменяет на "?": длина та же, содержимое другое.
# Проверено на этой базе: знак >= (U+2265) превратился в "?" четыре раза,
# и расхождение было видно только по отпечатку. Поэтому текст проверяется
# ДО записи, а не после.
#
# Отдельно про румынский: CP1251 не содержит диакритики (ș, ț, ă, î, â).
# Поэтому и сама ERP хранит наименования без знаков — «Rechizite scolare».
# Документы контура подчиняются тому же ограничению. Если понадобится
# полный Unicode, текст надо хранить BLOB-ом в UTF-8, а не CLOB-ом; здесь
# это сознательно не сделано, потому что тогда документ перестанет
# читаться обычными средствами SQL.
_ORACLE_TO_PYTHON_CODEC = {
    "CL8MSWIN1251": "cp1251",
    "EE8MSWIN1250": "cp1250",
    "WE8MSWIN1252": "cp1252",
    "AL32UTF8": "utf-8",
    "UTF8": "utf-8",
}

_charset_cache = {}


def db_codec() -> Optional[str]:
    """Кодек Python, соответствующий кодировке базы, либо None."""
    if "codec" not in _charset_cache:
        codec = None
        try:
            with Biro26DB() as db:
                rows = _rows(db.execute_query(
                    "SELECT VALUE FROM NLS_DATABASE_PARAMETERS "
                    "WHERE PARAMETER = 'NLS_CHARACTERSET'"))
            if rows:
                charset = str(rows[0].get("value") or "").upper()
                codec = _ORACLE_TO_PYTHON_CODEC.get(charset)
        except Exception:                                        # noqa: BLE001
            codec = None
        _charset_cache["codec"] = codec
    return _charset_cache["codec"]


def unsupported_chars(text: str, codec: Optional[str] = None) -> list:
    """Символы, которые кодировка базы не сохранит.

    Возвращает список пар (символ, номер строки) — чтобы автор сразу видел,
    где править, а не искал по всему документу.
    """
    codec = codec if codec is not None else db_codec()
    if not codec or codec == "utf-8":
        return []

    bad = []
    seen = set()
    for lineno, line in enumerate((text or "").splitlines(), 1):
        for ch in line:
            if ch in seen:
                continue
            try:
                ch.encode(codec)
            except UnicodeEncodeError:
                seen.add(ch)
                bad.append((ch, lineno))
    return bad


def body_sha(text: str) -> str:
    """Отпечаток текста. Переводы строк нормализуются: иначе один и тот же
    документ с Windows-переносами дал бы другой отпечаток."""
    normalized = (text or "").replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not result.get("success"):
        return []
    columns = [c.lower() for c in (result.get("columns") or [])]
    return [dict(zip(columns, row)) for row in (result.get("data") or [])]


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _done(data: Any = None, message: str = "") -> Dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def list_playbooks(site_cod: Optional[int] = None, kind: Optional[str] = None,
                   latest_only: bool = True) -> Dict[str, Any]:
    sql = "SELECT * FROM VSEO_PLAYBOOK WHERE 1 = 1"
    params: Dict[str, Any] = {}
    if site_cod:
        sql += " AND SITE_COD = :site_cod"
        params["site_cod"] = site_cod
    if kind:
        sql += " AND KIND = :kind"
        params["kind"] = kind
    if latest_only:
        sql += " AND IS_LATEST = 1"
    sql += " ORDER BY CREATED_AT DESC, COD DESC"

    with Biro26DB() as db:
        result = db.execute_query(sql, params)
    if not result.get("success"):
        return _fail(result.get("message", ""))
    return _done(_rows(result))


def get_playbook(cod: int) -> Dict[str, Any]:
    """Карточка вместе с текстом.

    CLOB читается кусками: слой обмена с воркером ходит через JSON, а
    целиком большой документ в один ответ класть незачем.
    """
    with Biro26DB() as db:
        head = _rows(db.execute_query(
            "SELECT * FROM VSEO_PLAYBOOK WHERE COD = :c", {"c": cod}))
        if not head:
            return _fail("документ не найден")

        length = int(head[0].get("body_len") or 0)
        chunks = []
        offset = 1
        while offset <= length:
            part = _rows(db.execute_query(
                "SELECT DBMS_LOB.SUBSTR(BODY, 3000, :off) T "
                "FROM YSEO_PLAYBOOK WHERE COD = :c",
                {"off": offset, "c": cod}))
            if not part or part[0].get("t") is None:
                break
            chunks.append(part[0]["t"])
            offset += 3000

    item = dict(head[0])
    item["body"] = "".join(chunks)
    return _done(item)


def save_playbook(code: str, title: str, body: str, *, kind: str = "STRATEGY",
                  site_cod: Optional[int] = None, period: Optional[str] = None,
                  status: str = "DRAFT", author: Optional[str] = None,
                  note: Optional[str] = None) -> Dict[str, Any]:
    """Сохраняет НОВУЮ версию документа. Старые не трогает."""
    if not (code or "").strip():
        return _fail("код документа обязателен")
    if not (title or "").strip():
        return _fail("заголовок обязателен")
    if not (body or "").strip():
        return _fail("текст документа пуст")
    if kind not in KINDS:
        return _fail(f"вид документа: допустимы {', '.join(KINDS)}")
    if status not in STATUSES:
        return _fail(f"статус: допустимы {', '.join(STATUSES)}")

    bad = unsupported_chars(body)
    if bad:
        listed = ", ".join(f"{ch!r} (U+{ord(ch):04X}, строка {ln})"
                           for ch, ln in bad[:8])
        return _fail(
            "текст содержит символы, которых нет в кодировке учётной базы: "
            f"{listed}. Oracle заменил бы их на «?» молча, поэтому запись "
            "отклонена — замените их обычными знаками")

    sha = body_sha(body)

    with Biro26DB() as db:
        same = _rows(db.execute_query(
            "SELECT COD, VERSION FROM YSEO_PLAYBOOK "
            "WHERE CODE = :code AND BODY_SHA = :sha "
            "ORDER BY VERSION DESC", {"code": code, "sha": sha}))
        if same:
            # Тот же текст уже лежит — плодить одинаковые версии незачем.
            return _done({"cod": same[0]["cod"], "version": same[0]["version"],
                          "created": False},
                         "текст совпадает с уже сохранённой версией")

        result = db.execute_script([
            {"sql": "INSERT INTO YSEO_PLAYBOOK (CODE, KIND, SITE_COD, TITLE, "
                    "PERIOD, BODY, BODY_SHA, STATUS, AUTHOR, NOTE) "
                    "VALUES (:code, :kind, :site_cod, :title, :period, "
                    ":body, :sha, :status, :author, :note)",
             "params": {"code": code, "kind": kind, "site_cod": site_cod,
                        "title": title, "period": period, "body": body,
                        "sha": sha, "status": status,
                        "author": author or "system", "note": note},
             "kind": "dml"},
            {"sql": "BEGIN PK_SEO_UTIL.LOG_EVENT('PLAYBOOK_SAVE', 'PLAYBOOK', "
                    "NULL, :details, :author); END;",
             "params": {"details": f"{code}: {title}"[:2000],
                        "author": author or "system"},
             "kind": "dml"},
            {"sql": "SELECT COD, VERSION FROM YSEO_PLAYBOOK "
                    "WHERE CODE = :code AND BODY_SHA = :sha",
             "params": {"code": code, "sha": sha}, "kind": "query"},
        ])

    if not result.get("success"):
        return _fail(result.get("message", ""))

    saved = {}
    for part in result.get("results", []):
        if part.get("columns") and part.get("data"):
            cols = [c.lower() for c in part["columns"]]
            saved = dict(zip(cols, part["data"][0]))

    return _done({"cod": saved.get("cod"), "version": saved.get("version"),
                  "created": True, "sha": sha})


def set_status(cod: int, status: str, author: Optional[str] = None) -> Dict[str, Any]:
    """Публикация или архивирование. Текст при этом не меняется."""
    if status not in STATUSES:
        return _fail(f"статус: допустимы {', '.join(STATUSES)}")

    with Biro26DB() as db:
        result = db.execute_script([
            {"sql": "UPDATE YSEO_PLAYBOOK SET STATUS = :status WHERE COD = :c",
             "params": {"status": status, "c": cod}, "kind": "dml"},
            {"sql": "BEGIN PK_SEO_UTIL.LOG_EVENT('PLAYBOOK_STATUS', 'PLAYBOOK', "
                    ":c, :details, :author); END;",
             "params": {"c": cod, "details": status,
                        "author": author or "system"}, "kind": "dml"},
        ])
    if not result.get("success"):
        return _fail(result.get("message", ""))
    return _done({"cod": cod, "status": status})
