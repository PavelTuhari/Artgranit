"""Есть ли база ADB — быстро и один раз в минуту, а не на каждом запросе.

08.11.2026 база ADB перестала отвечать: недоступная ADB не отказывает сразу,
а молчит больше минуты. Каждый адрес панели, читающий NMON_*, висел по
минуте и отдавал 500, а дашборд не грузил вообще ничего: следом за сводкой
не загружались и разделы, которым база не нужна (Proxmox, Zabbix, VPN,
MikroTik). Здесь — одна проверка с коротким ожиданием и памятью на минуту:
пока база лежит, панель отвечает сразу и берёт что может из Zabbix.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

WAIT_SEC = 6
REMEMBER_SEC = 60
_lock = threading.Lock()
_state = {"at": 0.0, "ok": True, "reason": ""}


class DbDown(RuntimeError):
    """База недоступна — текст для человека, без трассировки."""


def _probe() -> None:
    from models.database import DatabaseConnection
    conn = DatabaseConnection.get_connection()
    try:
        conn.cursor().execute("SELECT 1 FROM dual").fetchone()
    finally:
        conn.close()


def status(force: bool = False) -> dict:
    """{'ok': bool, 'reason': str, 'checked_at': unix} — проверка не чаще раза в минуту."""
    with _lock:
        if not force and time.time() - _state["at"] < REMEMBER_SEC:
            return dict(_state)
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            pool.submit(_probe).result(timeout=WAIT_SEC)
            _state.update(ok=True, reason="")
        except Exception as e:  # noqa: BLE001
            msg = "не ответила за %d с" % WAIT_SEC if type(e).__name__ == "TimeoutError" \
                else (str(e).splitlines() or ["ошибка"])[0][:160]
            _state.update(ok=False, reason=msg)
        finally:
            pool.shutdown(wait=False)
        _state["at"] = time.time()
        return dict(_state)


def require() -> None:
    """Перед чтением NMON_*: база лежит — сразу DbDown, без минутного ожидания."""
    s = status()
    if not s["ok"]:
        raise DbDown(f"база ADB недоступна ({s['reason']}); раздел заработает, когда её включат")


def mark_down(reason: str) -> None:
    """Запрос к базе упал по дороге — запомнить, чтобы следующие не ждали."""
    with _lock:
        _state.update(ok=False, reason=reason[:160], at=time.time())
