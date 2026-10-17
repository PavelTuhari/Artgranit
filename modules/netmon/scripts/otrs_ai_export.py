#!/usr/bin/env python3
"""Выгрузка заявок OTRS за последние N месяцев в SQLite — набор данных для ИИ.

    python modules/netmon/scripts/otrs_ai_export.py                 # 4 месяца, в ~/.netmon/otrs_ai/
    python modules/netmon/scripts/otrs_ai_export.py --months 6 --out /path/otrs_ai.sqlite

Постановка задачи для ИИ, который будет работать с этой базой, —
docs/Netmon/OTRS_AI_TASK.md (копия кладётся рядом с базой).

Что важно знать о файле
-----------------------
* Это СНИМОК для анализа, а не хранилище данных: источник истины — OTRS.
  Его можно удалить и пересобрать этой командой в любой момент.
* В НЁМ ПЕРЕПИСКА С КЛИЕНТАМИ: адреса, имена, тексты писем. Поэтому файл —
  вне репозитория, права 600, в git и облако не класть. Пароли, которые
  люди присылают в письмах, при выгрузке маскируются ([скрыто]); пароли
  клиентов OTRS (customer_user.pw) не выгружаются вовсе.
* Только чтение OTRS: ни одной записи в его базу.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from modules.netmon import otrs_ai_rules as rules  # noqa: E402
from modules.netmon import otrs_board as ob  # noqa: E402

DEFAULT_OUT = Path.home() / ".netmon" / "otrs_ai" / "otrs_ai.sqlite"
TASK_MD = ROOT / "docs" / "Netmon" / "OTRS_AI_TASK.md"
ISO = ob._ISO

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE users (id INTEGER PRIMARY KEY, login TEXT UNIQUE, first_name TEXT, last_name TEXT, valid INTEGER);
CREATE TABLE queues (id INTEGER PRIMARY KEY, name TEXT, valid INTEGER);
CREATE TABLE states (id INTEGER PRIMARY KEY, name TEXT, type TEXT);
CREATE TABLE priorities (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE article_types (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE sender_types (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE history_types (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE work_events (id INTEGER PRIMARY KEY, code TEXT, name_ru TEXT, valid INTEGER);
CREATE TABLE customers (login TEXT PRIMARY KEY, email TEXT, customer_id TEXT, first_name TEXT,
                        last_name TEXT, valid INTEGER);
CREATE TABLE tickets (
  id INTEGER PRIMARY KEY, tn TEXT UNIQUE, title TEXT,
  queue_id INTEGER REFERENCES queues(id), state_id INTEGER REFERENCES states(id),
  priority_id INTEGER REFERENCES priorities(id), owner_id INTEGER REFERENCES users(id),
  lock_id INTEGER, answered INTEGER, customer_id TEXT, customer_user TEXT,
  until_time INTEGER, created TEXT, changed TEXT, created_by INTEGER, changed_by INTEGER,
  free_fields TEXT, url TEXT
);
CREATE TABLE articles (
  id INTEGER PRIMARY KEY, ticket_id INTEGER REFERENCES tickets(id),
  type_id INTEGER REFERENCES article_types(id), sender_type_id INTEGER REFERENCES sender_types(id),
  a_from TEXT, a_to TEXT, a_cc TEXT, subject TEXT, content_type TEXT,
  body_text TEXT, body_chars INTEGER, body_truncated INTEGER, secrets_masked INTEGER,
  created TEXT, created_by INTEGER, from_user TEXT,
  plan_confirm_by_client INTEGER, plan_confirm_by_mngr INTEGER
);
CREATE INDEX ix_articles_ticket ON articles (ticket_id, created);
CREATE TABLE attachments (article_id INTEGER REFERENCES articles(id), filename TEXT,
                          size INTEGER, content_type TEXT);
CREATE TABLE history (
  id INTEGER PRIMARY KEY, ticket_id INTEGER REFERENCES tickets(id),
  history_type_id INTEGER REFERENCES history_types(id), name TEXT, owner_id INTEGER,
  state_id INTEGER, queue_id INTEGER, priority_id INTEGER, created TEXT, created_by INTEGER
);
CREATE INDEX ix_history_ticket ON history (ticket_id, created);
CREATE TABLE time_accounting (ticket_id INTEGER, article_id INTEGER, time_unit REAL, created TEXT, created_by INTEGER);
CREATE TABLE work_log (
  id INTEGER PRIMARY KEY, ticket_tn TEXT, ticket_id INTEGER, user_id INTEGER REFERENCES users(id),
  event_id INTEGER REFERENCES work_events(id), comment TEXT, started TEXT, ended TEXT,
  seconds INTEGER, deleted INTEGER
);
CREATE INDEX ix_work_ticket ON work_log (ticket_id);
CREATE INDEX ix_work_user ON work_log (user_id, started);
CREATE TABLE ticket_facts (
  ticket_id INTEGER PRIMARY KEY REFERENCES tickets(id),
  age_days INTEGER, idle_days INTEGER, customer_msgs INTEGER, agent_msgs INTEGER, internal_notes INTEGER,
  first_reply_hours REAL, last_customer_at TEXT, last_agent_at TEXT, waiting_on TEXT,
  owner_changes INTEGER, returns_to_owner INTEGER, executors TEXT,
  work_entries INTEGER, work_hours REAL, closed_at TEXT, resolution_hours REAL,
  plan_confirmed_client INTEGER, plan_confirmed_manager INTEGER, board_list TEXT
);
-- Сюда пишет ИИ. Формат — в OTRS_AI_TASK.md, раздел «Что ИИ отдаёт».
CREATE TABLE ai_recommendations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, ticket_id INTEGER,
  kind TEXT NOT NULL, action TEXT NOT NULL, params TEXT, reason TEXT NOT NULL,
  confidence REAL, evidence TEXT, status TEXT NOT NULL DEFAULT 'proposed',
  decided_by TEXT, decided_at TEXT, model TEXT
);
CREATE TABLE ai_actions_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, recommendation_id INTEGER
    REFERENCES ai_recommendations(id), ticket_id INTEGER, action TEXT NOT NULL, params TEXT,
  autonomy_level INTEGER NOT NULL, result TEXT, error TEXT
);
CREATE VIEW v_open AS
  SELECT t.*, s.name AS state, q.name AS queue, u.login AS owner, f.*
    FROM tickets t JOIN states s ON s.id = t.state_id JOIN queues q ON q.id = t.queue_id
    LEFT JOIN users u ON u.id = t.owner_id LEFT JOIN ticket_facts f ON f.ticket_id = t.id
   WHERE s.type IN ('new', 'open', 'pending reminder', 'pending auto');
CREATE VIEW v_thread AS
  SELECT a.ticket_id, a.created, st.name AS sender, at.name AS type, a.a_from, a.subject, a.body_text
    FROM articles a JOIN sender_types st ON st.id = a.sender_type_id JOIN article_types at ON at.id = a.type_id
   ORDER BY a.ticket_id, a.created;
"""


def q(sql: str, params: dict | None = None) -> list[dict]:
    return ob._rows(ob._run([{"sql": sql, "params": params or {}, "kind": "query"}], timeout=600)[0])


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def in_list(ids) -> str:
    return ",".join(str(int(i)) for i in ids) or "0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=4)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    t0 = time.time()
    out: Path = a.out.expanduser()
    if str(out.resolve()).startswith(str(ROOT)):
        sys.exit(f"✗ {out} внутри репозитория — в базе переписка с клиентами, ей там не место")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".building")
    tmp.unlink(missing_ok=True)

    print(f"OTRS → SQLite, последние {a.months} мес.")
    users = q("select id, login, first_name, last_name, valid_id from system_user")
    queues = q("select id, name, valid_id from queue")
    states = q("select s.id, s.name, t.name type from ticket_state s, ticket_state_type t where s.type_id = t.id")
    prios = q("select id, name from ticket_priority")
    atypes = q("select id, name from article_type")
    stypes = q("select id, name from article_sender_type")
    htypes = q("select id, name from ticket_history_type")
    wevents = q("select id, ievent, ievent_ru, event_valid from xuserwork_events")

    ids = [r["id"] for r in q("select id from ticket where change_time > add_months(sysdate, -:m)", {"m": a.months})]
    print(f"  заявок: {len(ids)}")

    tickets, articles, attach, history, ta = [], [], [], [], []
    free = ", ".join(f"freekey{i}, freetext{i}" for i in range(1, 11))
    for part in chunks(ids, 500):
        tickets += q(f"""select id, tn, title, queue_id, state_id_x state_id, ticket_priority_id priority_id,
                user_id owner_id, ticket_lock_id lock_id, ticket_answered answered, customer_id, customer_user_id,
                until_time, to_char(create_time, {ISO}) created, to_char(change_time, {ISO}) changed,
                create_by, change_by, {free}
              from (select t.*, t.ticket_state_id state_id_x from ticket t) where id in ({in_list(part)})""")
        history += q(f"""select id, ticket_id, history_type_id, name, owner_id, state_id, queue_id, priority_id,
                to_char(create_time, {ISO}) created, create_by from ticket_history
              where ticket_id in ({in_list(part)})""")
        ta += q(f"""select ticket_id, article_id, time_unit, to_char(create_time, {ISO}) created, create_by
              from time_accounting where ticket_id in ({in_list(part)})""")
    print(f"  истории: {len(history)}, учёта времени: {len(ta)}")
    for i, part in enumerate(chunks(ids, 120)):
        articles += q(f"""select id, ticket_id, article_type_id type_id, article_sender_type_id sender_type_id,
                a_from, a_to, a_cc, a_subject subject, a_content_type content_type, a_body body,
                to_char(create_time, {ISO}) created, create_by, a_from_user from_user,
                plan_confirm_by_client, plan_confirm_by_mngr
              from article where ticket_id in ({in_list(part)})""")
        print(f"\r  писем: {len(articles)}", end="", flush=True)
    print()
    art_ids = [r["id"] for r in articles]
    for part in chunks(art_ids, 900):
        attach += q(f"""select article_id, filename, content_size, content_type from article_attachment
              where article_id in ({in_list(part)})""")
    tn_of = {r["id"]: r["tn"] for r in tickets}
    id_of_tn = {v: k for k, v in tn_of.items()}
    work = q(f"""select id, ieventid, nticket, wcomment, to_char(datest, {ISO}) started,
                  to_char(dateend, {ISO}) ended, utime, userid, del
             from xuserwork where datest > add_months(sysdate, -:m)""", {"m": a.months})
    print(f"  вложений: {len(attach)}, журнал работ: {len(work)}")
    cust_logins = sorted({r["customer_user_id"] for r in tickets if r.get("customer_user_id")})
    customers = []
    for part in chunks(cust_logins, 500):
        binds = {f"c{i}": v for i, v in enumerate(part)}
        customers += q("select login, email, customer_id, first_name, last_name, valid_id from customer_user "
                       f"where login in ({','.join(':' + k for k in binds)})", binds)   # без pw

    # --------------------------------------------------------------- запись
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    ins = lambda table, rows, cols: con.executemany(
        f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        [[r.get(c) for c in cols] for r in rows])
    ins("users", [{**u, "valid": u["valid_id"]} for u in users], ["id", "login", "first_name", "last_name", "valid"])
    ins("queues", [{**x, "valid": x["valid_id"]} for x in queues], ["id", "name", "valid"])
    ins("states", states, ["id", "name", "type"])
    ins("priorities", prios, ["id", "name"])
    ins("article_types", atypes, ["id", "name"])
    ins("sender_types", stypes, ["id", "name"])
    ins("history_types", htypes, ["id", "name"])
    ins("work_events", [{"id": w["id"], "code": w["ievent"], "name_ru": w["ievent_ru"], "valid": w["event_valid"]}
                        for w in wevents], ["id", "code", "name_ru", "valid"])
    ins("customers", [{**c, "valid": c["valid_id"]} for c in customers],
        ["login", "email", "customer_id", "first_name", "last_name", "valid"])
    for t in tickets:
        t["customer_user"] = t.get("customer_user_id")
        t["free_fields"] = json.dumps({t[f"freekey{i}"]: t[f"freetext{i}"] for i in range(1, 11)
                                       if t.get(f"freekey{i}") and t.get(f"freetext{i}")}, ensure_ascii=False)
        t["url"] = ob.ticket_url(t["id"])
    ins("tickets", tickets, ["id", "tn", "title", "queue_id", "state_id", "priority_id", "owner_id", "lock_id",
                             "answered", "customer_id", "customer_user", "until_time", "created", "changed",
                             "created_by", "changed_by", "free_fields", "url"])
    masked = 0
    for r in articles:
        r.update(rules.prepare_body(r.pop("body", None), r.get("content_type")))
        masked += r["secrets_masked"]
    ins("articles", articles, ["id", "ticket_id", "type_id", "sender_type_id", "a_from", "a_to", "a_cc", "subject",
                               "content_type", "body_text", "body_chars", "body_truncated", "secrets_masked",
                               "created", "created_by", "from_user", "plan_confirm_by_client",
                               "plan_confirm_by_mngr"])
    ins("attachments", [{**x, "size": x["content_size"]} for x in attach],
        ["article_id", "filename", "size", "content_type"])
    ins("history", history, ["id", "ticket_id", "history_type_id", "name", "owner_id", "state_id", "queue_id",
                             "priority_id", "created", "created_by"])
    ins("time_accounting", ta, ["ticket_id", "article_id", "time_unit", "created", "created_by"])
    wl = [{"id": w["id"], "ticket_tn": str(w["nticket"]) if w.get("nticket") else None,
           "ticket_id": id_of_tn.get(str(w["nticket"])) if w.get("nticket") else None,
           "user_id": w["userid"], "event_id": w["ieventid"], "comment": rules.redact(w.get("wcomment") or "")[0],
           "started": w["started"], "ended": w["ended"], "seconds": w["utime"], "deleted": w["del"]} for w in work]
    ins("work_log", wl, ["id", "ticket_tn", "ticket_id", "user_id", "event_id", "comment", "started", "ended",
                         "seconds", "deleted"])

    # ------------------------------------------------- вычисляемые признаки
    login_of = {u["id"]: u["login"] for u in users}
    closed = {s["id"] for s in states if s["type"] in ("closed", "removed", "merged")}
    by_t = lambda rows: {k: sorted([r for r in rows if r["ticket_id"] == k], key=lambda r: r["created"] or "")
                         for k in ids}
    a_by, h_by = by_t(articles), by_t(history)
    w_by: dict = {}
    for w in wl:
        if w["ticket_id"] and not w["deleted"]:
            w_by.setdefault(w["ticket_id"], []).append(w)
    now = datetime.now()
    facts = []
    for t in tickets:
        f = rules.ticket_facts(t, a_by[t["id"]], h_by[t["id"]], w_by.get(t["id"], []), login_of, now,
                               closed, ob.LOGIN)
        f["board_list"] = board_list(t, f, h_by[t["id"]], w_by.get(t["id"], []), login_of, closed)
        facts.append(f)
    ins("ticket_facts", facts, list(facts[0].keys()) if facts else [])

    meta = {"exported_at": now.isoformat(timespec="seconds"), "months": a.months,
            "source": f"OTRS 2.1.3, Oracle cloudbd схема OTRS ({ob.DB_DSN})",
            "otrs_url": ob.OTRS_URL, "owner_login": ob.LOGIN,
            "tickets": len(tickets), "articles": len(articles), "history": len(history),
            "work_log": len(wl), "customers": len(customers), "secrets_masked": masked,
            "body_limit_chars": rules.BODY_LIMIT, "task": "OTRS_AI_TASK.md рядом с базой"}
    con.executemany("INSERT INTO meta VALUES (?, ?)", [(k, str(v)) for k, v in meta.items()])
    con.commit()
    con.execute("VACUUM")
    con.close()
    os.replace(tmp, out)
    os.chmod(out, 0o600)
    if TASK_MD.exists():
        shutil.copy2(TASK_MD, out.parent / TASK_MD.name)
    print(f"готово за {time.time() - t0:.0f} с: {out} ({out.stat().st_size // 1048576} МБ), "
          f"паролей в письмах замаскировано: {masked}")
    print(json.dumps(meta, ensure_ascii=False, indent=1))


def board_list(t, f, history, work, login_of, closed) -> str:
    """В каком списке доски заявка была бы сейчас (те же правила, что otrs_board.py)."""
    if t["state_id"] in closed:
        return "closed"
    me = ob.LOGIN
    if login_of.get(t["owner_id"]) == me:
        owners = [h for h in history if h["history_type_id"] == rules.HISTORY_OWNER]
        if owners and rules.owner_login_from_history(owners[-1]["name"]) == me \
                and login_of.get(owners[-1]["created_by"]) != me and len(owners) > 1:
            ex = owners[-1]["created_by"]
            prev = [h for h in owners[:-1] if rules.owner_login_from_history(h["name"]) == login_of.get(ex)]
            since = prev[-1]["created"] if prev else ""
            did = any(w["user_id"] == ex and (w["started"] or "") >= since and
                      (w["started"] or "") <= owners[-1]["created"] for w in work)
            return "to_close" if did else "returned"
    if f["waiting_on"] == "agent":
        return "review"
    return "waiting_customer"


if __name__ == "__main__":
    main()
