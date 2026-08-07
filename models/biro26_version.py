"""Версия веб-приложения для подвала сайта.

RO: numarul de versiune = DATA lansarii (YYYY.MM.DD) si sta in
    TMS_WEBAPPVERS (Oracle), oglindit in MySQL-ul WordPress. Se pune in
    subsolul site-ului dupa «UNA.md and ORACLE OCI based».
    Se citeste rar si se schimba doar la livrare — de aceea un cache in
    memorie, ca sa nu pornim un worker-subproces Oracle la fiecare pagina.
EN: the version number IS the release date; stored in Oracle and mirrored in
    the WordPress MySQL. Cached in memory — it only changes on release.

Cum se seteaza / как ставится: scripts/set_app_version.py (пишет в ОБЕ БД).
Правило: docs/Biro26/WEB_APP_VERSIONING.md
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from models.biro26_db import Biro26DB

CACHE_TTL_SEC = 600.0

_lock = threading.Lock()
_cache: Optional[tuple[float, str]] = None


def invalidate() -> None:
    global _cache
    with _lock:
        _cache = None


def current(app_code: str = "site") -> str:
    """Текущая версия. Пустая строка, если БД недоступна — подвал не ломаем."""
    global _cache
    with _lock:
        hit = _cache
    if hit and time.time() - hit[0] < CACHE_TTL_SEC:
        return hit[1]
    vers = ""
    try:
        r = Biro26DB().execute_query(
            "SELECT VERS FROM VMS_WEBAPPVERS WHERE APP_CODE = :a", {"a": app_code})
        rows = r.get("data") or []
        if rows:
            vers = str(rows[0][0] or "")
    except Exception:                                  # noqa: BLE001
        vers = ""
    with _lock:
        _cache = (time.time(), vers)
    return vers
