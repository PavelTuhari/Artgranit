"""
Лог EasyCredit и кредитных операций для виджета «Output» (как Oracle SQL Developer).
Файловое хранилище (JSONL) — общее для всех процессов/воркеров.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_ENTRIES = 2000
_LOG_DIR = Path(__file__).resolve().parent.parent / "data"
_LOG_PATH = _LOG_DIR / "credit_log.jsonl"
_lock = threading.Lock()


def _ensure_dir() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def append(
    source: str,
    message: str,
    level: str = "INFO",
    payload: dict[str, Any] | None = None,
) -> None:
    """Добавить запись в лог. source: easycredit.preapproved, easycredit.submit, credit.operator.application, ..."""
    entry = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "level": (level or "INFO").upper(),
        "source": source,
        "message": message,
        "payload": payload or {},
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _lock:
        try:
            _ensure_dir()
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


def get(limit: int = 500, since_ts: str | None = None) -> list[dict[str, Any]]:
    """Вернуть последние записи (новые в конце). since_ts — опционально фильтр по ISO ts."""
    with _lock:
        try:
            _ensure_dir()
            if not _LOG_PATH.exists():
                return []
            with open(_LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return []
    out: list[dict[str, Any]] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            e = json.loads(raw)
            if since_ts and (e.get("ts") or "") < since_ts:
                continue
            out.append(e)
        except Exception:
            continue
    return out[-limit:] if limit else out


def clear() -> None:
    """Очистить лог-файл."""
    with _lock:
        try:
            _ensure_dir()
            _LOG_PATH.write_text("", encoding="utf-8")
        except Exception:
            pass
