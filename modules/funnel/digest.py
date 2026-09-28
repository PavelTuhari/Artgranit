"""Автономная сводка: сама собирается и сама уходит получателям.

RO: O data pe zi, la ora setata, modulul aduna cifrele palniei si le
    trimite administratiei si marketingului prin canalele DEJA
    configurate ale magazinului (Biro26Notify: e-mail, Telegram,
    WhatsApp). Nimeni nu trebuie sa-si aminteasca sa se uite.
EN: Once a day, at the configured hour, the module gathers the funnel
    numbers and sends them through the shop's ALREADY configured
    channels. Nobody has to remember to look.

RO: De ce prin YBIRO_SETTINGS si nu prin variabile de mediu: setarile se
    vad si se schimba din administrare, fara redesfasurare - aceeasi
    regula ca la UNA_USERID in contur.
"""

from __future__ import annotations

import datetime
import threading
import time
from typing import Any, Dict, Optional

# RO: cheile de setari / EN: the settings keys
K_ENABLED = "FUNNEL_DIGEST_ENABLED"    # 1/0, implicit pornit
K_HOUR = "FUNNEL_DIGEST_HOUR"          # ora locala, implicit 22
K_LAST = "FUNNEL_DIGEST_LAST"          # YYYY-MM-DD ultimei expedieri

# RO: ora implicita 22: serverul de mail al gazdei e PORNIT doar
#     22:00-02:00 (vezi OFFICEPLUS_HOST_SERVICES) - ziua expedierea pe
#     e-mail ar cadea. EN: default hour 22 - the host's mail server is
#     only ON 22:00-02:00, a daytime send would fail.
DEFAULT_HOUR = 22

_CHECK_EVERY = 600
_state = {"thread": None}


def _setting(key: str, default: str = "") -> str:
    try:
        from models.biro26_oracle_store import Biro26Store
        return Biro26Store.get_setting(key, default)
    except Exception:                                        # noqa: BLE001
        return default


def _set_setting(key: str, value: str) -> None:
    try:
        from models.biro26_oracle_store import Biro26Store
        Biro26Store.set_setting(key, value)
    except Exception:                                        # noqa: BLE001
        pass


def _fmt(v) -> str:
    try:
        return f"{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def compose() -> str:
    """RO: textul rezumatului - scurt, cu cifre si cu lista de actiune.
    EN: the digest text - short, numeric, with an action list."""
    from modules.funnel import store
    today = store.summary(1)
    week = store.summary(7)
    month = store.summary(30)
    groups = store.top_groups(30, 5)
    stale = store.stale_orders(3, 10)

    lines = [
        "📊 officeplus.md — воронка продаж",
        f"({datetime.date.today().isoformat()})",
        "",
        f"Сегодня: заказов {today['orders']}, на {_fmt(today['orders_sum'])} MDL",
        f"7 дней:  заказов {week['orders']}, на {_fmt(week['orders_sum'])} MDL, "
        f"отгружено {week['delivered']}"
        + (f" ({week['conversion_pct']}%)" if week['conversion_pct'] is not None else ""),
        f"30 дней: заказов {month['orders']}, на {_fmt(month['orders_sum'])} MDL"
        + (f", ср. чек {_fmt(month['avg_check'])} MDL" if month['avg_check'] else ""),
    ]
    if groups:
        lines += ["", "Топ групп за 30 дней:"]
        lines += [f"  • {g['grupa'][:40]}: {_fmt(g['total'])} MDL "
                  f"({g['orders']} зак.)" for g in groups]
    if stale:
        lines += ["", f"⚠ Не отгружено дольше 3 дней — {len(stale)} шт:"]
        lines += [f"  • {s.get('nr') or s['cod']} от {s['day']}: "
                  f"{_fmt(s.get('total'))} MDL — {str(s.get('client') or '?')[:34]}"
                  for s in stale[:10]]
    else:
        lines += ["", "✅ Зависших заказов нет."]
    lines += ["", "Панель: https://officeplus.md/UNA.md/orasldev/funnel"]
    return "\n".join(lines)


def send_now() -> Dict[str, Any]:
    """RO: expediere imediata prin canalele configurate ale magazinului.
    EN: immediate send through the shop's configured channels."""
    from models.biro26_notify import Biro26Notify
    text = compose()
    res = Biro26Notify.send_all("Воронка продаж officeplus.md", text)
    # RO: raspunsul canalelor sta in res["data"]: {email: {...}, telegram:
    #     {...}} - reusita inseamna ca MACAR un canal a dus mesajul.
    # EN: per-channel results live one level down, in res["data"].
    channels = (res or {}).get("data") or {}
    ok = any((v or {}).get("success") for v in channels.values()
             if isinstance(v, dict))
    if ok:
        _set_setting(K_LAST, datetime.date.today().isoformat())
    return {"success": ok, "channels": channels, "text": text}


def due() -> bool:
    """RO: e ora si azi inca nu s-a trimis? EN: right hour, not yet sent?"""
    if _setting(K_ENABLED, "1").strip() == "0":
        return False
    try:
        hour = int(_setting(K_HOUR, str(DEFAULT_HOUR)) or DEFAULT_HOUR)
    except ValueError:
        hour = DEFAULT_HOUR
    now = datetime.datetime.now()
    if now.hour < hour:
        return False
    return _setting(K_LAST, "") != now.date().isoformat()


def _loop() -> None:
    while True:
        time.sleep(_CHECK_EVERY)
        try:
            if due():
                send_now()
        except Exception:                                    # noqa: BLE001
            # RO: o cadere a expedierii nu are voie sa opreasca bucla -
            #     incearca din nou peste zece minute.
            pass


def start_scheduler() -> None:
    """RO: firul de fundal, o singura data pe proces. EN: one thread per
    process; the daemon flag lets the app exit freely."""
    if _state["thread"] is not None:
        return
    t = threading.Thread(target=_loop, daemon=True, name="funnel-digest")
    _state["thread"] = t
    t.start()
