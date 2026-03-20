"""
Лог EasyCredit и кредитных операций для виджета «Output».
Хранение в Oracle; существующий JSONL мигрируется при первом обращении.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models.oracle_runtime_store import (
    append_event_log,
    bulk_insert_event_logs,
    clear_event_logs,
    count_event_logs,
    get_event_logs,
)

MAX_ENTRIES = 2000
_LOG_DIR = Path(__file__).resolve().parent.parent / "data"
_LOG_PATH = _LOG_DIR / "credit_log.jsonl"
_lock = threading.Lock()
_migration_done = False


def _ensure_dir() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def append(
    source: str,
    message: str,
    level: str = "INFO",
    payload: dict[str, Any] | None = None,
) -> None:
    """Добавить запись в лог. source: easycredit.preapproved, easycredit.submit, credit.operator.application, ..."""
    _migrate_if_needed()
    entry = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "level": (level or "INFO").upper(),
        "source": source,
        "message": message,
        "payload": payload or {},
    }
    with _lock:
        try:
            append_event_log(
                source=entry["source"],
                message=entry["message"],
                level=entry["level"],
                payload=entry["payload"],
                ts_iso=entry["ts"],
            )
        except Exception:
            pass


def get(limit: int = 500, since_ts: str | None = None) -> list[dict[str, Any]]:
    """Вернуть последние записи (новые в конце). since_ts — опционально фильтр по ISO ts."""
    _migrate_if_needed()
    with _lock:
        try:
            return get_event_logs(limit=limit, since_ts=since_ts)
        except Exception:
            return []


def clear() -> None:
    """Очистить лог-файл."""
    _migrate_if_needed()
    with _lock:
        try:
            clear_event_logs()
        except Exception:
            pass


def _migrate_if_needed() -> None:
    global _migration_done
    if _migration_done:
        return

    with _lock:
        if _migration_done:
            return
        try:
            if count_event_logs() > 0:
                _migration_done = True
                return
        except Exception:
            return

        try:
            _ensure_dir()
            if not _LOG_PATH.exists():
                _migration_done = True
                return

            entries: list[dict[str, Any]] = []
            with open(_LOG_PATH, "r", encoding="utf-8") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        entry = json.loads(raw)
                    except Exception:
                        continue
                    if isinstance(entry, dict):
                        entries.append(entry)
                    if len(entries) >= MAX_ENTRIES:
                        entries = entries[-MAX_ENTRIES:]

            bulk_insert_event_logs(entries)
            _migration_done = True
        except Exception:
            pass
