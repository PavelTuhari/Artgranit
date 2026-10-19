"""Чистые правила выгрузки OTRS для ИИ: текст писем, маскировка секретов, признаки заявки.

Без базы и без сети — проверяются тестами. Сама выгрузка —
modules/netmon/scripts/otrs_ai_export.py, постановка задачи для ИИ —
docs/Netmon/OTRS_AI_TASK.md.
"""
from __future__ import annotations

import html
import re
from datetime import datetime

BODY_LIMIT = 30000        # символов текста на письмо; длиннее — HTML-рассылки и цитаты
SENDER_AGENT, SENDER_SYSTEM, SENDER_CUSTOMER = 1, 2, 3
HISTORY_OWNER = 23

# ---------------------------------------------------------------- текст письма

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"(?i)<\s*(br|/p|/div|/tr|/li|/h\d)\b[^>]*>")
_DROP = re.compile(r"(?is)<\s*(style|script|head)\b.*?<\s*/\s*\1\s*>")


def to_text(body: str | None, content_type: str | None = "") -> str:
    """HTML → обычный текст; обычный текст — как есть, без лишних пустых строк."""
    if not body:
        return ""
    s = body
    if "html" in (content_type or "").lower() or re.search(r"(?i)<\s*(html|body|div|p|br|table)\b", s[:2000]):
        s = _DROP.sub(" ", s)
        s = _BLOCK.sub("\n", s)
        s = _TAG.sub(" ", s)
        s = html.unescape(s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t ]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


# ------------------------------------------------------------ маскировка секретов

# «пароль: abc123», «password = Qwe!12», «parola - x», «pwd:xyz» и т. п.
_SECRET = re.compile(
    r"(?i)\b(парол[ьяи]|password|passwd|pass|pwd|parol[aă]|parola|psw|пасс|пин|pin)\b"
    r"(\s*(?:[:=\-–]|is|este|—)\s*)(\S{3,64})")
# «логин / пароль» в одной строке: «user: admin / Pa$$w0rd»
_PAIR = re.compile(r"(?i)\b(login|логин|user|utilizator|пользователь)\b(\s*[:=]\s*\S{1,40}\s*[/\\|]\s*)(\S{3,64})")


def redact(text: str) -> tuple[str, int]:
    """Пароли в письмах заменяются на [скрыто]. Возвращает (текст, сколько заменено).

    Люди присылают в заявках пароли от касс, баз и почты. ИИ для анализа
    заявки их значение не нужно, а база с ними — готовая утечка.
    """
    n = 0

    def sub(m):
        nonlocal n
        n += 1
        return m.group(1) + m.group(2) + "[скрыто]"

    text = _SECRET.sub(sub, text or "")
    text = _PAIR.sub(sub, text)
    return text, n


def prepare_body(body: str | None, content_type: str | None) -> dict:
    t = to_text(body, content_type)
    original = len(t)
    t, n = redact(t)
    truncated = len(t) > BODY_LIMIT
    return {"body_text": t[:BODY_LIMIT], "body_chars": original, "body_truncated": int(truncated),
            "secrets_masked": n}


# ---------------------------------------------------------- признаки заявки

def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _hours(a: datetime | None, b: datetime | None) -> float | None:
    return round((b - a).total_seconds() / 3600, 1) if a and b else None


def owner_login_from_history(name: str | None) -> str | None:
    """«%%aivancioglo%%723» → aivancioglo."""
    m = re.match(r"^%%([^%]+)%%", name or "")
    return m.group(1) if m else None


def ticket_facts(t: dict, articles: list[dict], history: list[dict], work: list[dict],
                 users: dict[int, str], now: datetime, closed_state_ids: set[int],
                 owner_login: str) -> dict:
    """Вычисляемые признаки одной заявки — то, что ИИ иначе считал бы сам каждый раз.

    t — строка заявки; articles/history/work — её письма, история, журнал работ
    (отсортированы по времени); users — id → логин.
    """
    created = _dt(t["created"])
    cust = [a for a in articles if a["sender_type_id"] == SENDER_CUSTOMER]
    agent_ext = [a for a in articles if a["sender_type_id"] == SENDER_AGENT and a["type_id"] not in (9, 11)]
    notes = [a for a in articles if a["type_id"] in (9, 10, 11)]
    first_agent = _dt(agent_ext[0]["created"]) if agent_ext else None
    last_c = _dt(cust[-1]["created"]) if cust else None
    last_a = _dt(agent_ext[-1]["created"]) if agent_ext else None

    owners = [h for h in history if h["history_type_id"] == HISTORY_OWNER]
    owner_seq = [owner_login_from_history(h["name"]) for h in owners]
    executors = sorted({o for o in owner_seq if o and o != owner_login})
    returns = 0
    prev = None
    for h, who in zip(owners, owner_seq):
        if who == owner_login and prev and prev != owner_login and users.get(h["created_by"]) != owner_login:
            returns += 1
        prev = who

    closed_at = None
    if t["state_id"] in closed_state_ids:
        st = [h for h in history if h.get("state_id") in closed_state_ids]
        closed_at = _dt(st[0]["created"]) if st else _dt(t["changed"])

    work_secs = sum(int(w.get("seconds") or 0) for w in work)
    last_event = max([d for d in (_dt(t["changed"]), last_c, last_a) if d], default=created)

    if t["state_id"] in closed_state_ids:
        waiting = "closed"
    elif last_c and (not last_a or last_c > last_a):
        waiting = "agent"          # клиент написал последним — ход за нами
    elif last_a:
        waiting = "customer"
    else:
        waiting = "agent"

    return {
        "ticket_id": t["id"],
        "age_days": (now - created).days if created else None,
        "idle_days": (now - last_event).days if last_event else None,
        "customer_msgs": len(cust), "agent_msgs": len(agent_ext), "internal_notes": len(notes),
        "first_reply_hours": _hours(created, first_agent),
        "last_customer_at": cust[-1]["created"] if cust else None,
        "last_agent_at": agent_ext[-1]["created"] if agent_ext else None,
        "waiting_on": waiting,
        "owner_changes": len(owners),
        "returns_to_owner": returns,
        "executors": ",".join(executors),
        "work_entries": len(work), "work_hours": round(work_secs / 3600, 2),
        "closed_at": closed_at.isoformat() if closed_at else None,
        "resolution_hours": _hours(created, closed_at),
        "plan_confirmed_client": int(any(a.get("plan_confirm_by_client") for a in articles)),
        "plan_confirmed_manager": int(any(a.get("plan_confirm_by_mngr") for a in articles)),
    }
