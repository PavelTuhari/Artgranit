"""RO: parametrul pauzei in YBIRO_SETTINGS, tinut in memorie.

O citire de setare costa ~2 s (worker-subproces Oracle thick) — nu se poate la fiecare
cerere. Valoarea se tine in memorie si se reimprospateaza in fundal la REFRESH_S;
comutatorul din backoffice o schimba imediat in procesul care a primit clicul, iar
celelalte procese o preiau in cel mult REFRESH_S secunde.
"""
import threading
import time
from typing import Dict

from models.biro26_oracle_store import Biro26Store
from modules.sitepause import rules

KEY = "SITE_PAUSE"
KEY_MSG_RO = "SITE_PAUSE_MSG_RO"
KEY_MSG_RU = "SITE_PAUSE_MSG_RU"
REFRESH_S = 20

_state: Dict[str, object] = {"on": None, "ro": "", "ru": "", "ts": 0.0, "busy": False}
_lock = threading.Lock()


def _read() -> None:
    try:
        s = Biro26Store.get_settings_many([KEY, KEY_MSG_RO, KEY_MSG_RU])
        _state.update(on=rules.flag_on(s.get(KEY)), ro=s.get(KEY_MSG_RO) or "",
                      ru=s.get(KEY_MSG_RU) or "", ts=time.time())
    except Exception:                                        # noqa: BLE001
        _state["ts"] = time.time()          # baza cazuta: pastram ultima valoare
    finally:
        _state["busy"] = False


def state() -> Dict[str, object]:
    """RO: prima data citeste sincron (o singura data dupa pornire), apoi doar in fundal."""
    if _state["on"] is None:
        with _lock:
            if _state["on"] is None:
                _read()
                if _state["on"] is None:
                    _state["on"] = False
    elif time.time() - float(_state["ts"]) > REFRESH_S and not _state["busy"]:
        _state["busy"] = True
        threading.Thread(target=_read, daemon=True).start()
    return dict(_state)


def set_pause(on: bool, msg_ro: str = None, msg_ru: str = None) -> Dict[str, object]:
    r = Biro26Store.set_setting(KEY, "1" if on else "0")
    if not r.get("success"):
        return r
    if msg_ro is not None:
        Biro26Store.set_setting(KEY_MSG_RO, msg_ro.strip()[:400])
        _state["ro"] = msg_ro.strip()[:400]
    if msg_ru is not None:
        Biro26Store.set_setting(KEY_MSG_RU, msg_ru.strip()[:400])
        _state["ru"] = msg_ru.strip()[:400]
    _state.update(on=bool(on), ts=time.time())
    return {"success": True, "on": bool(on)}
