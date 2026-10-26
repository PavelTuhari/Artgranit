"""Наши специалисты на серверах и в базах — чистые правила, без базы и сети.

Что считается работой «в нерабочее время», кто наш, как разбирать журналы
сервера (`last` — сеансы, /var/log/secure — входы SSH) и что из входов —
автоматика, а не человек.

Рабочее время — понедельник–пятница, 08:00–19:00 по Кишинёву (сервер баз
живёт в том же поясе). Праздники не учитываются.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

WORK_DAYS = {0, 1, 2, 3, 4}          # пн–пт
WORK_START, WORK_END = 8, 19          # часы
STAFF_SCHEMAS = {"SYS", "SYSTEM"}
# Сколько одинаковых неинтерактивных входов за период — уже автоматика
AUTO_MIN = 20
# Входы одного человека в одну базу с промежутком меньше — один отрезок работы
BLOCK_GAP = timedelta(minutes=30)

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


# ------------------------------------------------------------- рабочее время

def _off(t: datetime) -> bool:
    return t.weekday() not in WORK_DAYS or not (WORK_START <= t.hour < WORK_END)


def off_hours(start: datetime, end: datetime | None = None) -> bool:
    """Хоть какая-то часть отрезка — вне рабочего времени."""
    if _off(start):
        return True
    if end and end > start:
        if end.date() != start.date():
            return True                       # перешёл через ночь
        if end > start.replace(hour=WORK_END, minute=0, second=0, microsecond=0):
            return True                       # засиделся после конца дня
    return False


def off_reason(start: datetime, end: datetime | None = None) -> str | None:
    if not off_hours(start, end):
        return None
    if start.weekday() not in WORK_DAYS:
        return "выходной"
    if start.hour < WORK_START or start.hour >= WORK_END:
        return f"ночь/вечер, {start:%H:%M}"
    return f"до {end:%d.%m %H:%M}" if end else "вне рабочего времени"


# ------------------------------------------------------------------ кто наш

def ident_keys(host: str | None, os_user: str | None) -> list[tuple[str, str]]:
    h = (host or "").strip()
    keys = [("host", h)] if h else []
    if h and os_user:
        keys.append(("hostuser", f"{h}|{os_user}"))
    return keys


def staff_of(host: str | None, os_user: str | None, account: str | None,
             registry: dict[tuple[str, str], dict]) -> tuple[bool, str | None]:
    """(наш ли, как зовут). Явная отметка «не наш» в справочнике сильнее правил."""
    person = None
    for k in reversed(ident_keys(host, os_user)):     # пара точнее, чем компьютер целиком
        r = registry.get(k)
        if r:
            return bool(r.get("staff", 1)), r.get("person")
    if (host or "").upper().startswith("UNAMD\\"):
        return True, person
    if (account or "").upper() in STAFF_SCHEMAS:
        return True, person
    return False, None


def ssh_person(user: str | None, ip: str | None, registry: dict[tuple[str, str], dict]) -> str | None:
    for k in (("ip", ip or ""), ("sshuser", user or "")):
        r = registry.get(k)
        if r and r.get("person"):
            return r["person"]
    return None


# --------------------------------------------------------------- журналы SSH

_LAST = re.compile(
    r"^(?P<user>\S+)\s+(?P<tty>\S+)\s+(?P<src>\S+)\s+"
    r"(?P<start>\w{3} \w{3}\s+\d+ \d\d:\d\d:\d\d \d{4})\s+"
    r"(?:-\s+(?P<end>\w{3} \w{3}\s+\d+ \d\d:\d\d:\d\d \d{4})|(?P<state>still logged in|gone - no logout|"
    r"- crash|- down))")


def _dt_last(s: str) -> datetime:
    return datetime.strptime(" ".join(s.split()), "%a %b %d %H:%M:%S %Y")


def parse_last(text: str) -> list[dict]:
    """`last -F -w` → сеансы. Перезагрузки (reboot) пропускаются."""
    out = []
    for line in text.splitlines():
        if line.startswith(("reboot", "wtmp", "shutdown")) or not line.strip():
            continue
        m = _LAST.match(line)
        if not m:
            continue
        src = m.group("src")
        out.append({
            "user": m.group("user"), "tty": m.group("tty"),
            "from": "screen" if src.startswith(":") else src,
            "start": _dt_last(m.group("start")),
            "end": _dt_last(m.group("end")) if m.group("end") else None,
            "still": m.group("state") == "still logged in",
        })
    return out


_SECURE = re.compile(
    r"^(?P<mon>\w{3})\s+(?P<day>\d+) (?P<time>\d\d:\d\d:\d\d) \S+ sshd\[(?P<pid>\d+)\]: "
    r"(?P<res>Accepted|Failed) (?P<method>\S+) for (?:invalid user )?(?P<user>\S+) from (?P<ip>\S+) port (?P<port>\d+)"
    r"(?: ssh2(?::? (?P<key>.+))?)?$")


def parse_secure(text: str, now: datetime) -> list[dict]:
    """Строки /var/log/secure* → входы SSH. Года в журнале нет: берём текущий,
    а дату из будущего относим к прошлому году."""
    out, seen = [], set()
    for line in text.splitlines():
        m = _SECURE.match(line.strip())
        if not m:
            continue
        t = datetime(now.year, _MONTHS[m.group("mon")], int(m.group("day")),
                     *map(int, m.group("time").split(":")))
        if t > now + timedelta(days=1):
            t = t.replace(year=now.year - 1)
        ref = f"{m.group('pid')}@{t:%Y%m%d%H%M%S}"
        if ref in seen:                 # «Failed password» пишется дважды на одну попытку
            continue
        seen.add(ref)
        out.append({"at": t, "result": "ok" if m.group("res") == "Accepted" else "fail",
                    "method": m.group("method"), "user": m.group("user"), "ip": m.group("ip"),
                    "key": (m.group("key") or "").strip() or None, "ref": ref})
    return out


def ssh_events(sessions: list[dict], auth: list[dict], server: str) -> list[dict]:
    """Сеансы (last) и входы (secure) → события. Вход, у которого есть сеанс,
    дополняет сеанс способом входа и ключом; вход без сеанса — команда без
    терминала (скрипт) или неудача."""
    events, used = [], set()
    for s in sessions:
        match = None
        for i, a in enumerate(auth):
            if i not in used and a["result"] == "ok" and a["user"] == s["user"] and a["ip"] == s["from"] \
                    and abs((a["at"] - s["start"]).total_seconds()) <= 5:
                match = i
                break
        a = auth[match] if match is not None else {}
        if match is not None:
            used.add(match)
        events.append({
            "source": "ssh", "target": server, "ref": f"wtmp:{s['user']}:{s['tty']}:{s['start']:%Y%m%d%H%M%S}",
            "account": s["user"], "from_host": s["from"], "os_user": None,
            "start_at": s["start"], "end_at": s["end"], "result": "ok",
            "method": f"сеанс {a.get('method') or 'терминал'}" + (" (не закрыт)" if s["still"] else ""),
            "detail": a.get("key") or s["tty"], "interactive": True,
        })
    for i, a in enumerate(auth):
        if i in used:
            continue
        events.append({
            "source": "ssh", "target": server, "ref": f"auth:{a['ref']}", "account": a["user"],
            "from_host": a["ip"], "os_user": None, "start_at": a["at"], "end_at": None,
            "result": a["result"], "method": a["method"], "detail": a.get("key"), "interactive": False,
        })
    return events


def mark_auto(events: list[dict]) -> list[dict]:
    """Одинаковые неинтерактивные успешные входы, повторённые AUTO_MIN раз и
    больше, — автоматика (резервные копии, наш мониторинг), не человек."""
    counts: dict[tuple, int] = {}
    for e in events:
        if e["source"] == "ssh" and not e.get("interactive") and e["result"] == "ok":
            k = (e["account"], e["from_host"], e["method"])
            counts[k] = counts.get(k, 0) + 1
    for e in events:
        k = (e["account"], e["from_host"], e["method"])
        e["auto"] = int(e["source"] == "ssh" and not e.get("interactive") and e["result"] == "ok"
                        and counts.get(k, 0) >= AUTO_MIN)
        e["off_hours"] = int(off_hours(e["start_at"], e.get("end_at")))
    return events


# ------------------------------------------------------- отрезки работы в базе

def blocks(events: list[dict]) -> list[dict]:
    """Входы в базу одного человека подряд → отрезки работы.

    У одного компьютера бывает по сотне входов в день (программа
    переподключается) — в списке это один отрезок «с … по …, входов N».
    """
    out: list[dict] = []
    key = lambda e: (e["target"], e.get("account"), e.get("from_host"), e.get("os_user"), e["result"])  # noqa: E731
    for e in sorted(events, key=lambda e: (key(e), e["start_at"])):
        end = e.get("end_at") or e["start_at"]
        last = out[-1] if out else None
        if last and last["_key"] == key(e) and e["start_at"] - last["end_at"] <= BLOCK_GAP:
            last["end_at"] = max(last["end_at"], end)
            last["logons"] += 1
            last["open"] = last["open"] or e.get("end_at") is None
            continue
        out.append({**e, "_key": key(e), "end_at": end, "logons": 1, "open": e.get("end_at") is None})
    for b in out:
        b.pop("_key", None)
        b["off_hours"] = int(off_hours(b["start_at"], b["end_at"]))
    return out


# ------------------------------------------------------- всплески у клиентов

def spikes(day_counts: dict, factor: int = 10, floor: int = 1000) -> list:
    """Дни, когда входов в разы больше обычного: признак переподключения на
    каждый запрос (так UNWEBSHOP с 25.10.2026 давал по 5 входов в секунду)."""
    vals = sorted(day_counts.values())
    if not vals:
        return []
    median = vals[len(vals) // 2]
    return sorted(d for d, n in day_counts.items() if n >= floor and n >= factor * max(median, 1))
