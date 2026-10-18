"""Поиск по XWiki и OTRS — обёртка над пакетом NMON_SRCH в базе cloudbd.

Вся логика поиска — в базе, на PL/SQL (modules/netmon/sql/cloudbd/301_nmon_srch_pkg.sql):
номер заявки, все слова точно / по основе / с опечаткой, исправление
раскладки, часть слов, вес заголовка и свежести, фрагмент с подсветкой и
оригинальная ссылка на https://xwiki.una.md или https://otrs.una.md.

Здесь только:
  * подготовка запроса — снять румынскую диакритику: база в кодировке
    CL8MSWIN1251, букв ă ș ț в ней нет, до PL/SQL они дошли бы знаком «?»;
  * вызов пакета через толстый процесс Oracle (как у доски заявок);
  * фоновая догрузка изменений в индекс, если он старше STALE_MIN минут.

Только чтение OTRS и XWIKI. Пишет пакет лишь в свои таблицы NMON_SRCH_*.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import unicodedata

from modules.netmon import otrs_board as ob

SOURCES = ("OTRS", "XWIKI")
ORDERS = ("rank", "date")
PAGE = 20
MAX_QUERY = 200
STALE_MIN = 10          # индекс старше — догрузить изменения фоном
SPAWN_PAUSE = 120       # не запускать догрузку чаще, чем раз в N секунд
MARK_START, MARK_END = "\x01", "\x02"   # подсветка во фрагменте (CTX_DOC.SNIPPET)

# Буквы, которых нет в CL8MSWIN1251: без замены база получила бы «?».
_RO = str.maketrans({"ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
                     "Ă": "A", "Â": "A", "Î": "I", "Ș": "S", "Ş": "S", "Ț": "T", "Ţ": "T"})

_SQL_SEARCH = "SELECT * FROM TABLE(nmon_srch.search(:q, :src, :op, :lim, :off, :ord))"
_SQL_STATUS = """SELECT source, status, docs, last_run_at, last_full_at, seconds, message,
                        ROUND((SYSDATE - NVL(last_run_at, SYSDATE - 1)) * 1440) age_min
                   FROM nmon_srch_sync ORDER BY source"""

_last_spawn = 0.0


def prepare_query(q: str | None) -> str:
    """Запрос для базы: без румынской диакритики, одной строкой, не длиннее MAX_QUERY."""
    if not q:
        return ""
    s = q.translate(_RO)
    # Остальная диакритика латиницы (é, ü…) — к базовой букве; кириллицу не трогаем.
    s = "".join(c for c in unicodedata.normalize("NFKD", s)
                if not (unicodedata.combining(c) and ord(unicodedata.normalize("NFC", c)[0]) < 0x400))
    s = unicodedata.normalize("NFC", s)
    return " ".join(s.split())[:MAX_QUERY]


def _hit(row: dict) -> dict:
    return {
        "source": row.get("source"), "title": row.get("title"), "url": row.get("url"),
        "snippet": row.get("snippet"), "score": row.get("score"), "rank": row.get("rnk"),
        "tn": row.get("tn"), "queue": row.get("queue"), "state": row.get("state"),
        "open": bool(row.get("is_open")), "customer": row.get("customer"), "owner": row.get("owner"),
        "space": row.get("space"), "lang": row.get("lang"), "author": row.get("author"),
        "parts": row.get("parts"), "created": row.get("created_at"), "changed": row.get("changed_at"),
        "matched_by": row.get("matched_by"),
    }


def _status(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        out[r["source"]] = {"status": r["status"], "docs": r["docs"], "last_run": r["last_run_at"],
                            "last_full": r["last_full_at"], "seconds": r["seconds"],
                            "message": r["message"], "age_min": r["age_min"]}
    return out


def find(q: str, source: str | None = None, open_: int | None = None, offset: int = 0,
         order: str = "rank", limit: int = PAGE) -> dict:
    """Результаты поиска и состояние индекса одним запуском толстого клиента."""
    query = prepare_query(q)
    src = (source or "").upper() if (source or "").upper() in SOURCES else None
    op = open_ if open_ in (0, 1) else None
    order = order if order in ORDERS else "rank"
    stmts = [{"sql": _SQL_STATUS, "kind": "query"}]
    if query:
        stmts.insert(0, {"sql": _SQL_SEARCH, "kind": "query",
                         "params": {"q": query, "src": src, "op": op, "lim": max(1, min(limit, 100)),
                                    "off": max(0, offset), "ord": order}})
    t = time.time()
    res = ob._run(stmts)
    hits = ob._rows(res[0]) if query else []
    status = _status(ob._rows(res[-1]))
    refreshing = maybe_refresh(status)
    first = hits[0] if hits else {}
    return {
        "query": query, "used_query": first.get("used_query") or query,
        "matched_by": next((h.get("matched_by") for h in hits if h.get("matched_by") != "номер заявки"),
                           first.get("matched_by")),
        "total": first.get("total") or 0, "offset": offset, "limit": limit,
        "hits": [_hit(h) for h in hits], "index": status, "refreshing": refreshing,
        "ms": round((time.time() - t) * 1000), "mark": [MARK_START, MARK_END],
    }


def status() -> dict:
    return _status(ob._rows(ob._run([{"sql": _SQL_STATUS, "kind": "query"}])[0]))


def is_stale(st: dict) -> bool:
    """Индекс нужно догрузить: давно не обновлялся и сейчас не обновляется."""
    if not st:
        return False
    if any(s.get("status") == "running" for s in st.values()):
        return False
    return any((s.get("age_min") or 0) >= STALE_MIN for s in st.values())


def refresh(full: bool = False) -> None:
    """Догрузить изменения в индекс фоном. Запуск не ждём: полная пересборка
    идёт минуты. Повторный запуск во время обновления пакет сам пропустит."""
    global _last_spawn
    req = {"op": "plsql", "plsql": "BEGIN nmon_srch.refresh(:f); END;", "params": {"f": 1 if full else 0},
           "auth": {"user": ob.DB_USER, "password": ob._password(), "dsn": ob.DB_DSN}}
    p = subprocess.Popen([sys.executable, str(ob.ROOT / "models" / "biro26_worker.py")],
                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd=str(ob.ROOT), start_new_session=True, text=True)
    p.stdin.write(json.dumps(req))
    p.stdin.close()
    _last_spawn = time.time()


def maybe_refresh(st: dict) -> bool:
    if not is_stale(st) or time.time() - _last_spawn < SPAWN_PAUSE:
        return False
    try:
        refresh(False)
        return True
    except Exception:  # noqa: BLE001 — поиск важнее догрузки
        return False
