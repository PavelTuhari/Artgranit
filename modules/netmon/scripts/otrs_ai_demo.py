#!/usr/bin/env python3
"""Демонстрационная база заявок — для скриншотов, документации и обучения.

    python modules/netmon/scripts/otrs_ai_demo.py                    # ~/.netmon/otrs_ai/otrs_ai_demo.sqlite
    python modules/netmon/scripts/otrs_ai_demo.py --out /tmp/demo.sqlite

Та же схема, что у настоящей выгрузки (otrs_ai_export.SCHEMA), и те же
правила признаков (otrs_ai_rules.ticket_facts), но клиенты, люди и тексты
вымышленные. Поэтому её скриншоты можно класть в репозиторий и показывать
кому угодно — в отличие от настоящей базы с перепиской клиентов.
Генерация детерминированная: одинаковый результат при каждом запуске.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules.netmon import otrs_ai_rules as rules  # noqa: E402
from otrs_ai_export import SCHEMA  # noqa: E402

NOW = datetime(2026, 10, 17, 12, 0)
OWNER = "ptuhari"
USERS = [(2, "ptuhari", "Pavel", "Tuhari"), (11, "ivanov", "Ivan", "Ivanov"), (12, "popescu", "Ana", "Popescu"),
         (13, "rusu", "Mihai", "Rusu"), (14, "ceban", "Elena", "Ceban"), (1, "root", "Admin", "OTRS")]
CLIENTS = [("Demo Market SRL", "office@demomarket.example"), ("Agro Vest SA", "it@agrovest.example"),
           ("Farmacia Nova", "admin@farmacianova.example"), ("Construct Plus", "buh@constructplus.example"),
           ("Hotel Central", "reception@hotelcentral.example")]
QUEUES = [(1, "Support_UniAcc"), (2, "Bonus"), (3, "Biro26"), (4, "Infrastructura")]
STATES = [(1, "new", "new"), (2, "closed successful", "closed"), (4, "open", "open"),
          (6, "pending reminder", "pending reminder")]
TOPICS = [
    ("Не печатает чек на кассе №2", "Касса выдаёт ошибку принтера при закрытии смены."),
    ("Nu se încarcă raportul de vânzări", "Raportul lunar de vânzări se oprește la 60%."),
    ("Добавить нового сотрудника в CRM", "Прошу завести учётную запись для нового менеджера."),
    ("Обновить цены в каталоге", "Новый прайс во вложении, нужно загрузить до понедельника."),
    ("Eroare la sincronizarea e-Factura", "Facturile nu ajung în SFS, apare eroare de semnătură."),
    ("Медленно открывается журнал документов", "Журнал за год открывается больше минуты."),
    ("Настроить VPN для бухгалтера", "Бухгалтер будет работать из дома со следующей недели."),
    ("Bonusurile nu se acumulează", "Clienții nu primesc puncte la achiziții din ultima zi."),
    ("Перенести базу на новый сервер", "Нужен план переноса и окно простоя."),
    ("Ошибка при печати накладной", "Форма накладной обрезается справа."),
]


def build(out: Path) -> dict:
    rnd = random.Random(2026)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    con = sqlite3.connect(out)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO users VALUES (?,?,?,?,1)", USERS)
    con.executemany("INSERT INTO queues VALUES (?,?,1)", QUEUES)
    con.executemany("INSERT INTO states VALUES (?,?,?)", STATES)
    con.executemany("INSERT INTO priorities VALUES (?,?)", [(3, "3 normal"), (4, "4 high")])
    con.executemany("INSERT INTO article_types VALUES (?,?)", [(1, "email-external"), (5, "phone"), (9, "note-internal")])
    con.executemany("INSERT INTO sender_types VALUES (?,?)", [(1, "agent"), (2, "system"), (3, "customer")])
    con.executemany("INSERT INTO history_types VALUES (?,?)", [(1, "NewTicket"), (23, "OwnerUpdate"), (27, "StateUpdate")])
    con.executemany("INSERT INTO work_events VALUES (?,?,?,1)", [(10, "work_on_ticket_remote", "Работа по заявке (удалённо)"),
                                                                 (11, "work_on_ticket_office", "Работа по заявке (в офисе)")])
    con.executemany("INSERT INTO customers VALUES (?,?,?,?,?,1)",
                    [(f"client{i}", mail, name, "Contact", f"#{i}") for i, (name, mail) in enumerate(CLIENTS, 1)])
    iso = lambda d: d.replace(microsecond=0).isoformat()
    tickets, arts, hist, work = [], [], [], []
    aid = hid = wid = 1
    # сценарии подобраны так, чтобы показать все списки доски
    scen = (["review"] * 7 + ["to_close"] * 5 + ["returned"] * 4 + ["with_executor"] * 8
            + ["waiting_customer"] * 3 + ["closed"] * 5)
    for n, kind in enumerate(scen):
        tid = 1000 + n
        title, text = TOPICS[n % len(TOPICS)]
        cli = n % len(CLIENTS)
        created = NOW - timedelta(days=rnd.randint(2, 50), hours=rnd.randint(0, 8))
        ex = USERS[1 + n % 4]
        owner = {"review": 2, "to_close": 2, "returned": 2, "with_executor": ex[0],
                 "waiting_customer": 2, "closed": 2}[kind]
        state = 2 if kind == "closed" else 4
        t = {"id": tid, "tn": f"2026{created:%m%d}10{tid}", "title": title, "queue_id": 1 + n % 4,
             "state_id": state, "priority_id": 4 if n % 6 == 0 else 3, "owner_id": owner, "lock_id": 1,
             "answered": 0, "customer_id": CLIENTS[cli][0], "customer_user": f"client{cli + 1}", "until_time": 0,
             "created": iso(created), "changed": iso(NOW - timedelta(days=rnd.randint(0, 3))),
             "created_by": 1, "changed_by": 2, "free_fields": json.dumps({"Product": "Una.md"}),
             "url": f"https://otrs.una.md/otrs/index.pl?Action=AgentTicketZoom;TicketID={tid}"}
        tickets.append(t)
        thread = [(3, 1, created, text)]
        if kind != "review":
            thread.append((1, 1, created + timedelta(hours=rnd.randint(2, 30)), "Добрый день! Приняли, передаём специалисту."))
        if kind in ("to_close", "returned", "with_executor", "closed"):
            a1 = created + timedelta(hours=3)
            hist.append({"id": hid, "ticket_id": tid, "history_type_id": 23, "name": f"%%{ex[1]}%%{ex[0]}",
                         "created": iso(a1), "created_by": 2}); hid += 1
            if kind in ("to_close", "returned"):
                back = NOW - timedelta(days=rnd.randint(0, 9))
                hist.append({"id": hid, "ticket_id": tid, "history_type_id": 23, "name": f"%%{OWNER}%%2",
                             "created": iso(back), "created_by": ex[0]}); hid += 1
                if kind == "to_close":
                    for k in range(rnd.randint(1, 3)):
                        work.append({"id": wid, "ticket_tn": t["tn"], "ticket_id": tid, "user_id": ex[0], "event_id": 10,
                                     "comment": ["Исправлена настройка принтера, проверено с клиентом.",
                                                 "Actualizat șablonul, testat pe baza demo.",
                                                 "Загружен прайс, клиент подтвердил."][k % 3],
                                     "started": iso(back - timedelta(hours=5 + k)), "ended": iso(back - timedelta(hours=4 + k)),
                                     "seconds": 3600 * (k + 1), "deleted": 0}); wid += 1
                    thread.append((3, 1, back - timedelta(hours=1), "Спасибо, всё работает."))
        if kind == "review" and n % 2:
            thread.append((1, 1, created + timedelta(hours=5), "Уточните, пожалуйста, номер кассы."))
            thread.append((3, 1, NOW - timedelta(days=rnd.randint(1, 6)), "Касса №2, ошибка повторяется."))
        if kind == "waiting_customer":
            thread.append((1, 1, NOW - timedelta(days=1), "Прислали инструкцию, ждём подтверждения."))
        if kind == "closed":
            hist.append({"id": hid, "ticket_id": tid, "history_type_id": 27, "name": "closed", "state_id": 2,
                         "created": iso(created + timedelta(days=2)), "created_by": 2}); hid += 1
        thread.append((1, 9, created + timedelta(hours=1), "Внутренняя заметка: проверить версию программы у клиента."))
        for snd, typ, when, body in sorted(thread, key=lambda x: x[2]):
            arts.append({"id": aid, "ticket_id": tid, "type_id": typ, "sender_type_id": snd,
                         "a_from": CLIENTS[cli][1] if snd == 3 else "support@unisim-soft.example",
                         "a_to": "", "a_cc": "", "subject": ("Re: " if snd == 1 else "") + title,
                         "content_type": "text/plain", "body_text": body, "body_chars": len(body),
                         "body_truncated": 0, "secrets_masked": 0, "created": iso(when),
                         "created_by": 2 if snd == 1 else 1, "from_user": "",
                         "plan_confirm_by_client": 1 if kind == "to_close" and snd == 3 else 0,
                         "plan_confirm_by_mngr": 0}); aid += 1
        t["_kind"] = kind
    cols = lambda rows: list(rows[0].keys())
    ins = lambda table, rows, c: con.executemany(f"INSERT INTO {table} ({','.join(c)}) VALUES ({','.join('?' * len(c))})",
                                                 [[r.get(x) for x in c] for r in rows])
    ins("tickets", tickets, [c for c in cols(tickets) if not c.startswith("_")])
    ins("articles", arts, cols(arts))
    ins("history", hist, ["id", "ticket_id", "history_type_id", "name", "owner_id", "state_id", "queue_id",
                          "priority_id", "created", "created_by"])
    ins("work_log", work, cols(work) if work else [])
    login = {u[0]: u[1] for u in USERS}
    facts = []
    for t in tickets:
        f = rules.ticket_facts(t, [a for a in arts if a["ticket_id"] == t["id"]],
                               [h for h in hist if h["ticket_id"] == t["id"]],
                               [w for w in work if w["ticket_id"] == t["id"]], login, NOW, {2}, OWNER)
        f["board_list"] = t["_kind"]
        facts.append(f)
    ins("ticket_facts", facts, cols(facts))
    meta = {"exported_at": iso(NOW), "months": 4, "source": "ДЕМОНСТРАЦИОННЫЕ ДАННЫЕ — вымышленные клиенты и заявки",
            "otrs_url": "https://otrs.una.md/otrs/index.pl", "owner_login": OWNER, "tickets": len(tickets),
            "articles": len(arts), "history": len(hist), "work_log": len(work)}
    con.executemany("INSERT INTO meta VALUES (?, ?)", [(k, str(v)) for k, v in meta.items()])
    con.commit()
    con.close()
    return meta


def board_json(db: Path) -> dict:
    """Те же данные в формате /api/otrs — для скриншота доски."""
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = con.execute("""SELECT t.id, t.tn, t.title, t.customer_id, q.name queue, s.name state, p.name priority,
                                 t.created, t.url, f.*, u.login owner_login
                            FROM tickets t JOIN ticket_facts f ON f.ticket_id = t.id
                            JOIN queues q ON q.id = t.queue_id JOIN states s ON s.id = t.state_id
                            JOIN priorities p ON p.id = t.priority_id JOIN users u ON u.id = t.owner_id""").fetchall()
    out = {"review": [], "to_close": [], "returned": []}
    for r in map(dict, rows):
        lst = r["board_list"]
        if lst not in out:
            continue
        h = con.execute("SELECT h.created, u.login, trim(u.first_name||' '||u.last_name) nm, h.created_by FROM history h "
                        "JOIN users u ON u.id = h.created_by WHERE h.ticket_id = ? AND h.history_type_id = 23 "
                        "ORDER BY h.created DESC LIMIT 1", [r["id"]]).fetchone()
        w = con.execute("SELECT comment FROM work_log WHERE ticket_id = ? ORDER BY started DESC LIMIT 1", [r["id"]]).fetchone()
        a = con.execute("SELECT created FROM history WHERE ticket_id = ? AND history_type_id = 23 ORDER BY created LIMIT 1",
                        [r["id"]]).fetchone()
        base = {"id": r["id"], "tn": r["tn"], "title": r["title"], "customer_id": r["customer_id"], "queue": r["queue"],
                "state": r["state"], "priority": r["priority"], "created": r["created"], "url": r["url"]}
        if lst == "review":
            base.update({"reasons": ["customer"], "reason_titles": ["Клиент написал, ответа сотрудника ещё нет"],
                         "last_customer_at": r["last_customer_at"], "last_customer_subject": r["title"],
                         "owner_login": OWNER, "age_days": r["age_days"]})
        else:
            base.update({"returned_at": h["created"], "assigned_at": a["created"] if a else None,
                         "executor_login": h["login"], "executor_name": h["nm"],
                         "work_entries": r["work_entries"], "work_comment": w["comment"] if w else None,
                         "held_days": (datetime.fromisoformat(h["created"]) - datetime.fromisoformat(a["created"])).days if a else None})
        out[lst].append(base)
    open_mine = con.execute("SELECT COUNT(*) FROM v_open WHERE owner = ?", [OWNER]).fetchone()[0]
    stale_mine = con.execute("SELECT COUNT(*) FROM v_open WHERE owner = ? AND idle_days > 180", [OWNER]).fetchone()[0]
    con.close()
    return {"login": OWNER, "otrs_url": "https://otrs.una.md/otrs/index.pl", **out,
            "counts": {"review": len(out["review"]), "to_close": len(out["to_close"]), "returned": len(out["returned"]),
                       "open_mine": 27, "stale_mine": 0, "stuck_new": 0},
            "windows": {"return_days": 90, "review_days": 30, "stale_days": 180},
            "checked_at": NOW.strftime("%Y-%m-%d %H:%M"), "cached_sec": 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path.home() / ".netmon" / "otrs_ai" / "otrs_ai_demo.sqlite")
    a = ap.parse_args()
    print(json.dumps(build(a.out.expanduser()), ensure_ascii=False, indent=1))
    print("демонстрационная база:", a.out.expanduser())


if __name__ == "__main__":
    main()
