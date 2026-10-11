"""Доска заявок OTRS для владельца: что ждёт рассмотрения, что на закрытие, что вернулось.

Работа с заявками остаётся в самом OTRS — https://otrs.una.md/otrs/index.pl.
Доска только показывает три списка и ведёт в карточку заявки в OTRS.
Только чтение: в базу OTRS ничего не пишется.

Интерфейсы всего, что касается OTRS, — в стиле Asana (решение владельца
11.10.2026): списки с разделами, строки-задачи, кружки исполнителей,
спокойная светлая или тёмная палитра. См. docs/Netmon/OTRS_BOARD.md.

Откуда данные
-------------
OTRS 2.x, база — схема OTRS в Oracle cloudbd (192.168.0.24, SID CLOUDBD).
Это Oracle 11g: тонкий режим python-oracledb к нему не подключается,
поэтому запросы идут через толстый процесс models/biro26_worker.py (как у
Biro26 и ServOuts26). Пароль — Keychain «oracle-cloudbd-otrs» или
переменная NETMON_OTRS_DB_PASSWORD.

Как устроена работа в этом OTRS (по данным, 11.10.2026)
------------------------------------------------------
* Поле «ответственный» не используется — работа идёт через ВЛАДЕЛЬЦА
  заявки. Передача исполнителю — смена владельца; в ticket_history тип
  OwnerUpdate (23), name = «%%логин%%id», create_by — кто передал.
* Самописный журнал работ XUSERWORK: исполнитель записывает время по
  заявке, связь — по НОМЕРУ заявки (ticket.tn), не по id.
* Штатных статусов «на закрытие» / «вернули» нет. Поэтому:
    - ВЕРНУЛАСЬ — последняя смена владельца у открытой заявки — на меня,
      и сделал её не я (исполнитель отдал обратно);
    - НА ЗАКРЫТИЕ — вернулась, и исполнитель, пока заявка была у него,
      записывал по ней работу: сделал и отдал закрывать;
    - НЕ УСПЕЛ — вернулась без единой записи работы.
  Признак не идеальный (исполнитель мог поработать и не записать), поэтому
  на доске рядом стоит последний комментарий исполнителя из журнала работ.
* Открытых заявок на владельце больше тысячи, почти все — без движения
  больше полугода. В списки они не попадают, на доске — отдельной цифрой.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

OTRS_URL = "https://otrs.una.md/otrs/index.pl"
LOGIN = os.environ.get("NETMON_OTRS_LOGIN", "ptuhari")
DB_USER = "otrs"
DB_DSN = "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=192.168.0.24)(PORT=1521))(CONNECT_DATA=(SID=CLOUDBD)))"
KEYCHAIN_SERVICE = "oracle-cloudbd-otrs"

RETURN_DAYS = 90      # вернувшиеся за последние N дней
REVIEW_DAYS = 30      # «клиент написал» и «новые мои» — за последние N дней
STALE_DAYS = 180      # без движения дольше — архив, не в списках

ROOT = Path(__file__).resolve().parents[2]
_ISO = "'YYYY-MM-DD\"T\"HH24:MI:SS'"
_OPEN = ("(select s.id from ticket_state s, ticket_state_type st where s.type_id = st.id "
         "and st.name in ('new', 'open', 'pending reminder'))")


def ticket_url(ticket_id) -> str:
    return f"{OTRS_URL}?Action=AgentTicketZoom;TicketID={ticket_id}"


def _password() -> str:
    pw = os.environ.get("NETMON_OTRS_DB_PASSWORD", "")
    if pw:
        return pw
    r = subprocess.run(["security", "find-generic-password", "-a", DB_USER, "-s", KEYCHAIN_SERVICE, "-w"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"нет пароля базы OTRS: Keychain «{KEYCHAIN_SERVICE}» или NETMON_OTRS_DB_PASSWORD")
    return r.stdout.strip()


def _run(statements: list[dict], timeout: int = 120) -> list[dict]:
    """Несколько запросов одним процессом (запуск толстого клиента ~1–2 с)."""
    req = {"op": "script", "statements": statements,
           "auth": {"user": DB_USER, "password": _password(), "dsn": DB_DSN}}
    r = subprocess.run([sys.executable, str(ROOT / "models" / "biro26_worker.py")],
                       input=json.dumps(req), capture_output=True, text=True, cwd=str(ROOT), timeout=timeout)
    try:
        out = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        raise RuntimeError(f"процесс Oracle ответил не JSON: {(r.stdout or r.stderr)[-300:]}")
    if not out.get("success"):
        raise RuntimeError(f"база OTRS: {out.get('message') or r.stderr[-300:]}")
    return out["results"]


def _rows(res: dict) -> list[dict]:
    cols = [c.lower() for c in res.get("columns", [])]
    return [dict(zip(cols, row)) for row in res.get("data", [])]


# Вернувшиеся мне: последняя смена владельца — на меня, сделал не я.
_SQL_RETURNED = f"""
with mine as (
  select t.id from ticket t where t.user_id = :me and t.ticket_state_id in {_OPEN}),
last_own as (
  select h.ticket_id, h.name, h.create_by, h.create_time,
         row_number() over (partition by h.ticket_id order by h.create_time desc, h.id desc) rn
    from ticket_history h where h.history_type_id = 23 and h.ticket_id in (select id from mine)),
ret as (
  select l.ticket_id, l.create_by executor_id, l.create_time ret_time,
         (select max(a.create_time) from ticket_history a, system_user u
           where a.ticket_id = l.ticket_id and a.history_type_id = 23 and u.id = l.create_by
             and a.create_time < l.create_time and a.name like '%%' || u.login || '%%%') asg_time
    from last_own l
   where l.rn = 1 and l.name = '%%' || :login || '%%' || :me and l.create_by <> :me
     and l.create_time > sysdate - :ret_days)
select t.id, t.tn, t.title, t.customer_id, q.name queue, s.name state, p.name priority,
       to_char(t.create_time, {_ISO}) created, to_char(r.ret_time, {_ISO}) returned_at,
       to_char(r.asg_time, {_ISO}) assigned_at,
       u.login executor_login, trim(u.first_name || ' ' || u.last_name) executor_name,
       (select count(*) from xuserwork w where w.nticket = to_number(t.tn) and w.userid = r.executor_id
           and nvl(w.del, 0) = 0 and w.datest between nvl(r.asg_time, r.ret_time - 30) and r.ret_time + 1/24) work_entries,
       (select max(w.wcomment) keep (dense_rank last order by w.datest) from xuserwork w
         where w.nticket = to_number(t.tn) and w.userid = r.executor_id and nvl(w.del, 0) = 0
           and w.datest between nvl(r.asg_time, r.ret_time - 30) and r.ret_time + 1/24) work_comment
  from ret r, ticket t, queue q, ticket_state s, ticket_priority p, system_user u
 where t.id = r.ticket_id and q.id = t.queue_id and s.id = t.ticket_state_id
   and p.id = t.ticket_priority_id and u.id = r.executor_id
 order by r.ret_time desc
"""

# Требуют рассмотрения: три причины, одна заявка может подходить под несколько.
_SQL_REVIEW = f"""
select 'unassigned' reason, t.id, t.tn, t.title, t.customer_id, q.name queue, s.name state, p.name priority,
       to_char(t.create_time, {_ISO}) created, to_char(t.change_time, {_ISO}) changed,
       null last_customer_at, null last_customer_subject, ou.login owner_login
  from ticket t, queue q, ticket_state s, ticket_priority p, system_user ou, ticket_state_type st
 where q.id = t.queue_id and s.id = t.ticket_state_id and p.id = t.ticket_priority_id and ou.id = t.user_id
   and st.id = s.type_id and st.name = 'new'
union all
select 'customer', t.id, t.tn, t.title, t.customer_id, q.name, s.name, p.name,
       to_char(t.create_time, {_ISO}), to_char(t.change_time, {_ISO}),
       to_char(c.last_c, {_ISO}),
       (select max(a.a_subject) keep (dense_rank last order by a.create_time) from article a
         where a.ticket_id = t.id and a.article_sender_type_id = 3), null
  from ticket t, queue q, ticket_state s, ticket_priority p,
       (select a.ticket_id, max(a.create_time) last_c from article a
         where a.article_sender_type_id = 3 and a.create_time > sysdate - :review_days group by a.ticket_id) c
 where t.user_id = :me and t.ticket_state_id in {_OPEN} and c.ticket_id = t.id
   and q.id = t.queue_id and s.id = t.ticket_state_id and p.id = t.ticket_priority_id
   and c.last_c > nvl((select max(b.create_time) from article b
                        where b.ticket_id = t.id and b.article_sender_type_id = 1), date '2000-01-01')
union all
select 'fresh', t.id, t.tn, t.title, t.customer_id, q.name, s.name, p.name,
       to_char(t.create_time, {_ISO}), to_char(t.change_time, {_ISO}), null, null, null
  from ticket t, queue q, ticket_state s, ticket_priority p
 where t.user_id = :me and t.ticket_state_id in {_OPEN} and t.create_time > sysdate - :review_days
   and q.id = t.queue_id and s.id = t.ticket_state_id and p.id = t.ticket_priority_id
   and not exists (select 1 from ticket_history h where h.ticket_id = t.id and h.history_type_id = 23
                     and h.name <> '%%' || :login || '%%' || :me)
"""

_SQL_COUNTS = f"""
select count(*) open_mine,
       sum(case when t.change_time < sysdate - :stale_days then 1 else 0 end) stale_mine
  from ticket t where t.user_id = :me and t.ticket_state_id in {_OPEN}
"""

REASONS = {
    "unassigned": "Новая, ни на кого не назначена",
    "customer": "Клиент написал, ответа сотрудника ещё нет",
    "fresh": "Новая на мне, исполнителю не передана",
}
_REASON_ORDER = ("unassigned", "customer", "fresh")


def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    return (datetime.now() - datetime.fromisoformat(iso)).days


def classify_returned(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """(на закрытие, не успел) — по тому, записывал ли исполнитель работу."""
    to_close, not_done = [], []
    for r in rows:
        r["url"] = ticket_url(r["id"])
        r["returned_days"] = _days_since(r.get("returned_at"))
        r["held_days"] = (None if not r.get("assigned_at") else
                          (datetime.fromisoformat(r["returned_at"]) - datetime.fromisoformat(r["assigned_at"])).days)
        (to_close if int(r.get("work_entries") or 0) > 0 else not_done).append(r)
    return to_close, not_done


def merge_review(rows: list[dict], exclude_ids: set) -> list[dict]:
    """Одна строка на заявку, все причины — списком; вернувшиеся сюда не попадают."""
    by_id: dict = {}
    for r in rows:
        if r["id"] in exclude_ids:
            continue
        cur = by_id.get(r["id"])
        if cur is None:
            cur = by_id[r["id"]] = {**r, "reasons": []}
        if r["reason"] not in cur["reasons"]:
            cur["reasons"].append(r["reason"])
        for k in ("last_customer_at", "last_customer_subject", "owner_login"):
            if r.get(k) and not cur.get(k):
                cur[k] = r[k]
    out = []
    for r in by_id.values():
        r.pop("reason", None)
        r["reasons"].sort(key=_REASON_ORDER.index)
        r["reason_titles"] = [REASONS[x] for x in r["reasons"]]
        r["url"] = ticket_url(r["id"])
        r["age_days"] = _days_since(r.get("created"))
        out.append(r)
    # сначала неназначенные, потом «клиент ждёт» — самые давние сверху
    out.sort(key=lambda x: (_REASON_ORDER.index(x["reasons"][0]),
                            x.get("last_customer_at") or x.get("created") or ""))
    return out


def board() -> dict:
    binds = {"me": None, "login": LOGIN}
    res = _run([{"sql": "select id from system_user where login = :login", "params": {"login": LOGIN},
                 "kind": "query"}])
    users = _rows(res[0])
    if not users:
        raise RuntimeError(f"в OTRS нет пользователя {LOGIN}")
    binds["me"] = users[0]["id"]
    res = _run([
        {"sql": _SQL_RETURNED, "params": {**binds, "ret_days": RETURN_DAYS}, "kind": "query"},
        {"sql": _SQL_REVIEW, "params": {**binds, "review_days": REVIEW_DAYS}, "kind": "query"},
        {"sql": _SQL_COUNTS, "params": {"me": binds["me"], "stale_days": STALE_DAYS}, "kind": "query"},
    ])
    returned = _rows(res[0])
    to_close, not_done = classify_returned(returned)
    review = merge_review(_rows(res[1]), {r["id"] for r in returned})
    counts = (_rows(res[2]) or [{}])[0]
    return {
        "login": LOGIN, "otrs_url": OTRS_URL,
        "review": review, "to_close": to_close, "returned": not_done,
        "counts": {"review": len(review), "to_close": len(to_close), "returned": len(not_done),
                   "open_mine": int(counts.get("open_mine") or 0),
                   "stale_mine": int(counts.get("stale_mine") or 0)},
        "windows": {"return_days": RETURN_DAYS, "review_days": REVIEW_DAYS, "stale_days": STALE_DAYS},
        "reasons": REASONS,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
