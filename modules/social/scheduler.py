"""Автономная публикация по расписанию.

RO: O data pe zi, la ora setata, se publica postarea zilei in retelele
    pornite. Ora si pornirea stau in setari, ca sa se schimbe din
    administrare. Marca zilei se tine tot in setari - asa doua contururi
    care ruleaza acelasi cod nu publica de doua ori.
EN: once a day at the configured hour; the "already posted today" mark
    lives in the shared settings so two contours never double-post.
"""

from __future__ import annotations

import datetime
import threading
import time
from typing import Any, Dict

K_ENABLED = "SOCIAL_AUTOPOST_ENABLED"
K_HOUR = "SOCIAL_AUTOPOST_HOUR"
K_LANG = "SOCIAL_AUTOPOST_LANG"
K_LAST = "SOCIAL_AUTOPOST_LAST"

DEFAULT_HOUR = 10          # RO: dimineata, cind oamenii sint pe telefon
_CHECK_EVERY = 600
_state: Dict[str, Any] = {"thread": None}


def _setting(key: str, default: str = "") -> str:
    from modules.social.content import _setting as s
    return s(key, default)


def _set_setting(key: str, value: str) -> None:
    from modules.social.content import _set_setting as s
    s(key, value)


def due() -> bool:
    if _setting(K_ENABLED, "0").strip() != "1":
        return False
    try:
        hour = int(_setting(K_HOUR, str(DEFAULT_HOUR)) or DEFAULT_HOUR)
    except ValueError:
        hour = DEFAULT_HOUR
    now = datetime.datetime.now()
    if now.hour < hour:
        return False
    return _setting(K_LAST, "") != now.date().isoformat()


def post_now(lang: str = None) -> Dict[str, Any]:
    """RO: publicare imediata - si pentru verificare, si pentru orar."""
    from modules.social import channels, content
    lang = lang or _setting(K_LANG, "ro") or "ro"
    post = content.today_post(lang)
    if not post:
        return {"success": False, "error": "нет данных для поста"}
    res = channels.publish(post)
    ok = any((v or {}).get("success") for v in res.values())
    if ok:
        _set_setting(K_LAST, datetime.date.today().isoformat())
    return {"success": ok, "networks": res, "post": post}


def _loop() -> None:
    while True:
        time.sleep(_CHECK_EVERY)
        try:
            if due():
                post_now()
        except Exception:                                    # noqa: BLE001
            pass


def start() -> None:
    if _state["thread"] is not None:
        return
    t = threading.Thread(target=_loop, daemon=True, name="social-autopost")
    _state["thread"] = t
    t.start()
