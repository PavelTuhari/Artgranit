"""Аналитика клиентов — для бизнеса и для техники в одном месте.

Опирается на унификацию (NMON_CLI_*, cloudbd): клиент = заказчик OTRS +
юрлицо в бухгалтерии + схемы + точки + продукты. К этому добавляются
заявки OTRS и история входов (ADB, NMON_LOGON_DAY).

Что считается:
  * бизнес: активные клиенты по типам, точки магазинов и рабочие места за
    30 дней, открытые заявки, нагрузка менеджеров, поток заявок по неделям,
    клиенты, которые затихли (входили, но не последнюю неделю) — риск ухода,
    работающие клиенты без договора в заявках;
  * техника: всплески входов (программа подключается на каждый запрос),
    неудачные входы, схемы без входов за 30 дней (кандидаты в архив),
    несостыковки данных (что поправить в OTRS и в учёте).

Только чтение. Ручные правки (связь с заказчиком OTRS, тип, статус,
«несостыковка решена») — отдельными функциями внизу, пишут только NMON_CLI_*.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from modules.netmon import otrs_board as ob
from modules.netmon import staff_rules as sr

QUIET_DAYS = 7          # не входил столько дней при входах раньше — «затих»
BACKLOG = 10            # открытых заявок у клиента — «завал»
_ISO = "'YYYY-MM-DD\"T\"HH24:MI:SS'"
_OPEN = "('new', 'open', 'pending reminder', 'pending auto')"


def _q(sql: str, **params) -> dict:
    return {"sql": sql, "kind": "query", "params": params or None}


_Q_CLIENTS = f"""SELECT cli_id, code, name, idno, cod_univ, kind, status, manager, contract, schemas, shop_points,
       workplaces, tickets, tickets_open, TO_CHAR(last_ticket, {_ISO}) last_ticket FROM nmon_cli_v"""
_Q_SCHEMAS = "SELECT cli_id, db, schema_name, role, logons_30d FROM nmon_cli_schema"
_Q_POINTS = f"""SELECT cli_id, kind, host, os_user, days_30d, logons_30d, TO_CHAR(last_seen, {_ISO}) last_seen
                  FROM nmon_cli_point"""
_Q_PRODUCTS = "SELECT cli_id, product, evidence FROM nmon_cli_product"
_Q_ISSUES = "SELECT issue_id, cli_id, kind, subject, detail FROM nmon_cli_issue WHERE resolved = 0 ORDER BY kind, subject"
_Q_MANAGERS = f"""SELECT NVL(t.freetext3, '—') manager, COUNT(*) open_tickets,
       SUM(CASE WHEN t.create_time < SYSDATE - 90 THEN 1 ELSE 0 END) older_90d
  FROM ticket t, ticket_state ts, ticket_state_type st
 WHERE ts.id = t.ticket_state_id AND st.id = ts.type_id AND st.name IN {_OPEN} AND t.freekey3 = 'Manager'
 GROUP BY NVL(t.freetext3, '—')"""
_Q_WEEKS = f"""SELECT TO_CHAR(TRUNC(create_time, 'IW'), 'YYYY-MM-DD') week, COUNT(*) created FROM ticket
 WHERE create_time >= TRUNC(SYSDATE, 'IW') - 7 * 11 GROUP BY TRUNC(create_time, 'IW') ORDER BY 1"""


def _adb_days(since: datetime) -> list[dict]:
    from models.database import DatabaseModel
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        cur.execute("""SELECT SCHEMA_NAME, TO_CHAR(DAY, 'YYYY-MM-DD') DAY, SUM(LOGONS) LOGONS, SUM(FAILED) FAILED
                         FROM NMON_LOGON_DAY WHERE DAY >= :since GROUP BY SCHEMA_NAME, DAY""", since=since)
        return [{"schema": r[0], "day": r[1], "logons": r[2] or 0, "failed": r[3] or 0} for r in cur.fetchall()]


def overview() -> dict:
    res = ob._run([_q(_Q_CLIENTS), _q(_Q_SCHEMAS), _q(_Q_POINTS), _q(_Q_PRODUCTS), _q(_Q_ISSUES),
                   _q(_Q_MANAGERS), _q(_Q_WEEKS)], timeout=180)
    clients, schemas, points, products, issues, managers, weeks = (ob._rows(r) for r in res)
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = _adb_days(today - timedelta(days=29))

    by_id = {c["cli_id"]: {**c, "schema_list": [], "points": [], "products": [], "issues": [],
                           "daily": {}, "failed_30d": 0} for c in clients}
    schema_owner = {}
    for s in schemas:
        if s["cli_id"] in by_id:
            by_id[s["cli_id"]]["schema_list"].append(s)
            schema_owner[s["schema_name"]] = s["cli_id"]
    for p in points:
        if p["cli_id"] in by_id:
            by_id[p["cli_id"]]["points"].append(p)
    for p in products:
        if p["cli_id"] in by_id:
            by_id[p["cli_id"]]["products"].append(p["product"])
    for i in issues:
        if i["cli_id"] in by_id:
            by_id[i["cli_id"]]["issues"].append(i["kind"])
    for d in days:
        cid = schema_owner.get(d["schema"])
        if cid:
            c = by_id[cid]
            c["daily"][d["day"]] = c["daily"].get(d["day"], 0) + d["logons"]
            c["failed_30d"] += d["failed"]

    week_ago = (today - timedelta(days=QUIET_DAYS)).strftime("%Y-%m-%d")
    two_weeks = (today - timedelta(days=2 * QUIET_DAYS)).strftime("%Y-%m-%d")
    rows = []
    for c in by_id.values():
        daily = c.pop("daily")
        pts = c.pop("points")
        last = max((p["last_seen"] for p in pts if p.get("last_seen")), default=None)
        logons = sum(daily.values())
        this_week = sum(n for d, n in daily.items() if d > week_ago)
        prev_week = sum(n for d, n in daily.items() if two_weeks < d <= week_ago)
        spikes = sr.spikes(daily)
        flags = []
        if logons and not this_week:
            flags.append("quiet")
        if c["schemas"] and not logons and c["kind"] != "none":
            flags.append("inactive")
        if (c["tickets_open"] or 0) >= BACKLOG:
            flags.append("backlog")
        if spikes:
            flags.append("storm")
        if "no_otrs" in c["issues"] or "cod_univ_mismatch" in c["issues"]:
            flags.append("data")
        if logons and not c["contract"]:
            flags.append("no_contract")
        rows.append({
            **{k: c[k] for k in ("cli_id", "code", "name", "idno", "kind", "status", "manager", "contract",
                                 "tickets", "tickets_open", "last_ticket", "failed_30d")},
            "schemas": [s["schema_name"] for s in c["schema_list"]],
            "shop_points": len({p["host"] for p in pts if p["kind"] in ("shop", "pos", "scales")}),
            "workplaces": len({p["host"] for p in pts if p["kind"] == "office"}),
            "web": len({p["host"] for p in pts if p["kind"] == "web"}),
            "logons_30d": logons, "days_active": len([n for n in daily.values() if n]),
            "this_week": this_week, "prev_week": prev_week, "last_seen": last,
            "products": sorted(c["products"]), "spikes": spikes, "flags": flags,
        })
    active = [r for r in rows if r["logons_30d"]]
    kinds = {k: sum(1 for r in active if r["kind"] == k) for k in ("shop", "back", "web", "none")}
    support_only = sum(1 for r in rows if not r["schemas"] and (r["tickets"] or 0) and r["last_ticket"]
                       and r["last_ticket"] >= (today - timedelta(days=365)).strftime("%Y-%m-%d"))
    flag_count = {f: sum(1 for r in rows if f in r["flags"])
                  for f in ("quiet", "inactive", "backlog", "storm", "data", "no_contract")}
    return {
        "checked_at": now.strftime("%Y-%m-%d %H:%M"),
        "kpi": {
            "active_clients": len(active), "kinds": kinds, "support_only": support_only,
            "shop_points": sum(r["shop_points"] for r in active), "workplaces": sum(r["workplaces"] for r in active),
            "tickets_open": sum(r["tickets_open"] or 0 for r in rows), "flags": flag_count,
            "inactive_schemas": sum(1 for s in schemas if not s["logons_30d"]),
            "issues": len(issues),
            "logons_week": sum(r["this_week"] for r in rows), "logons_prev_week": sum(r["prev_week"] for r in rows),
        },
        "clients": sorted(rows, key=lambda r: (-(r["logons_30d"] > 0), -(r["tickets_open"] or 0), r["code"])),
        "managers": sorted(managers, key=lambda m: -(m["open_tickets"] or 0)),
        "weeks": weeks, "issues": issues,
        "inactive_schemas": sorted(s["schema_name"] for s in schemas if not s["logons_30d"]),
    }


# ------------------------------------------------------------- карточка

def client_card(code: str) -> dict:
    code = (code or "").strip().upper()
    res = ob._run([
        _q(f"SELECT * FROM nmon_cli_v WHERE code = :code", code=code),
        _q("SELECT o.otrs_customer_id, o.match_by, o.score, o.origin FROM nmon_cli_otrs o, nmon_cli c "
           "WHERE c.cli_id = o.cli_id AND c.code = :code ORDER BY 1", code=code),
        _q("SELECT l.customer_login, l.cod_univ FROM nmon_cli_login l, nmon_cli c "
           "WHERE c.cli_id = l.cli_id AND c.code = :code ORDER BY 1", code=code),
        _q("SELECT s.db, s.schema_name, s.role, s.logons_30d, TO_CHAR(s.created, 'YYYY-MM-DD') created, s.origin "
           "FROM nmon_cli_schema s, nmon_cli c WHERE c.cli_id = s.cli_id AND c.code = :code "
           "ORDER BY s.logons_30d DESC", code=code),
        _q(f"SELECT p.kind, p.host, p.os_user, p.days_30d, p.logons_30d, TO_CHAR(p.last_seen, {_ISO}) last_seen "
           "FROM nmon_cli_point p, nmon_cli c WHERE c.cli_id = p.cli_id AND c.code = :code "
           "ORDER BY p.kind, p.logons_30d DESC", code=code),
        _q("SELECT p.product, p.evidence FROM nmon_cli_product p, nmon_cli c "
           "WHERE c.cli_id = p.cli_id AND c.code = :code ORDER BY 1", code=code),
        _q("SELECT i.issue_id, i.kind, i.subject, i.detail FROM nmon_cli_issue i, nmon_cli c "
           "WHERE c.cli_id = i.cli_id AND c.code = :code AND i.resolved = 0", code=code),
        _q(f"""SELECT * FROM (SELECT t.id, t.tn, t.title, q.name queue, s.name state, st.name state_type,
                      TO_CHAR(t.create_time, {_ISO}) created, TO_CHAR(t.change_time, {_ISO}) changed, u.login owner
                 FROM ticket t, queue q, ticket_state s, ticket_state_type st, system_user u, nmon_cli_otrs o, nmon_cli c
                WHERE q.id = t.queue_id AND s.id = t.ticket_state_id AND st.id = s.type_id AND u.id(+) = t.user_id
                  AND t.customer_id = o.otrs_customer_id AND o.cli_id = c.cli_id AND c.code = :code
                ORDER BY CASE WHEN st.name IN {_OPEN} THEN 0 ELSE 1 END, t.change_time DESC) WHERE ROWNUM <= 40""",
           code=code),
    ], timeout=120)
    head, otrs, logins, schemas, points, products, issues, tickets = (ob._rows(r) for r in res)
    if not head:
        raise ValueError(f"клиент {code} не найден — запустите «Сопоставить заново»")
    for t in tickets:
        t["url"] = ob.ticket_url(t["id"])
        t["open"] = t["state_type"] in ("new", "open", "pending reminder", "pending auto")
    return {"client": head[0], "otrs": otrs, "logins": logins, "schemas": schemas, "points": points,
            "products": products, "issues": issues, "tickets": tickets}


# ------------------------------------------------------------ ручные правки

def link_otrs(code: str, otrs_customer_id: str) -> None:
    """Связать заказчика OTRS с клиентом вручную (перезапишет автоматическую связь)."""
    code, cid = (code or "").strip().upper(), (otrs_customer_id or "").strip()
    if not code or not cid:
        raise ValueError("нужны клиент и заказчик OTRS")
    ob._run([{"sql": """MERGE INTO nmon_cli_otrs o
                         USING (SELECT :b_oc oc, (SELECT cli_id FROM nmon_cli WHERE code = :b_code) cli FROM dual) s
                            ON (o.otrs_customer_id = s.oc)
                          WHEN MATCHED THEN UPDATE SET cli_id = s.cli, match_by = 'manual', score = 100, origin = 'manual'
                          WHEN NOT MATCHED THEN INSERT (otrs_customer_id, cli_id, match_by, score, origin)
                               VALUES (s.oc, s.cli, 'manual', 100, 'manual')""",
              "params": {"b_oc": cid[:150], "b_code": code}, "kind": "dml"}])


def set_client(code: str, kind: str | None, status: str | None, note: str | None, usr: str) -> None:
    if kind and kind not in ("shop", "back", "web", "internal", "none"):
        raise ValueError("тип: shop|back|web|internal|none")
    if status and status not in ("active", "paused", "archived"):
        raise ValueError("статус: active|paused|archived")
    ob._run([{"sql": """UPDATE nmon_cli SET kind = NVL(:b_kind, kind), status = NVL(:b_status, status),
                               note = NVL(:b_note, note), origin = 'manual', updated_at = SYSDATE, updated_by = :b_usr
                         WHERE code = :b_code""",
              "params": {"b_kind": kind, "b_status": status, "b_note": (note or None) and note[:500],
                         "b_usr": (usr or "system")[:60], "b_code": (code or "").upper()}, "kind": "dml"}])


def resolve_issue(issue_id: int) -> None:
    ob._run([{"sql": "UPDATE nmon_cli_issue SET resolved = 1 WHERE issue_id = :b_id",
              "params": {"b_id": int(issue_id)}, "kind": "dml"}])


def otrs_customers(q: str) -> list[dict]:
    """Поиск заказчиков OTRS для ручной связи."""
    q = (q or "").strip()
    if len(q) < 2:
        return []
    return ob._rows(ob._run([_q("""SELECT * FROM (SELECT t.customer_id, COUNT(*) tickets,
                                         TO_CHAR(MAX(t.create_time), 'YYYY-MM-DD') last_ticket,
                                         (SELECT c.code FROM nmon_cli_otrs o, nmon_cli c
                                           WHERE o.otrs_customer_id = t.customer_id AND c.cli_id = o.cli_id) linked
                                    FROM ticket t WHERE UPPER(t.customer_id) LIKE '%' || UPPER(:b_q) || '%'
                                   GROUP BY t.customer_id ORDER BY MAX(t.create_time) DESC) WHERE ROWNUM <= 20""",
                                  b_q=q[:60])])[0])
