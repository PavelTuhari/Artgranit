"""Унификация клиентов: сбор, сопоставление и запись в NMON_CLI_* (cloudbd, схема OTRS).

Источники — только чтение:
  * OTRS: заявки (ticket.customer_id, свободные поля «договор» и «менеджер»,
    названия), логины клиентов (customer_user.login, cod_univ), проекты (PROJECT);
  * наша бухгалтерия UNI: TMS_UNIVERS (контрагент), TMS_ORG (фискальный код);
  * схемы клиентов UniAcc в cloudbd (владельцы TMS_UNIVERS);
  * история входов (ADB, NMON_LOGON_DAY) — точки за 30 дней;
  * справочники модуля: закреплённый тип (NMON_CLIENT), наши (NMON_STAFF_ID).

Правила — unify_rules.py. Строки с ORIGIN = manual не перезаписываются.
Запуск: из панели («Сопоставить заново») и modules/netmon/scripts/netmon_unify.py.
"""
from __future__ import annotations

from datetime import datetime

from modules.netmon import otrs_board as ob
from modules.netmon import unify_rules as ur

TICKET_YEARS = 3          # заказчики OTRS без заявок дольше — в прошлом
_ISO = "'YYYY-MM-DD\"T\"HH24:MI:SS'"

_Q_LOGINS = "SELECT login, customer_id, cod_univ, email FROM customer_user WHERE valid_id = 1"
_Q_CUSTOMERS = f"""
SELECT t.customer_id, COUNT(*) tickets,
       SUM(CASE WHEN st.name IN ('new', 'open', 'pending reminder', 'pending auto') THEN 1 ELSE 0 END) open_tickets,
       SUM(CASE WHEN t.create_time > SYSDATE - 90 THEN 1 ELSE 0 END) tickets_90d,
       TO_CHAR(MAX(t.create_time), {_ISO}) last_ticket,
       MAX(CASE WHEN t.freekey2 LIKE '%Contr%' THEN t.freetext2 END) KEEP (DENSE_RANK LAST ORDER BY t.create_time) contract,
       MAX(CASE WHEN t.freekey3 = 'Manager' THEN t.freetext3 END) KEEP (DENSE_RANK LAST ORDER BY t.create_time) manager
  FROM ticket t, ticket_state ts, ticket_state_type st
 WHERE ts.id = t.ticket_state_id AND st.id = ts.type_id AND t.customer_id IS NOT NULL
   AND t.create_time > ADD_MONTHS(SYSDATE, -12 * {TICKET_YEARS})
 GROUP BY t.customer_id"""
_Q_TITLES = f"""SELECT t.customer_id, t.tn, t.title FROM ticket t
 WHERE t.customer_id IS NOT NULL AND t.create_time > ADD_MONTHS(SYSDATE, -12 * {TICKET_YEARS})"""
_Q_UNIV = """SELECT u.cod, u.denumirea, o.codfiscal FROM uni.tms_univers u LEFT JOIN uni.tms_org o ON o.cod = u.cod
 WHERE u.cod IN (SELECT cod_univ FROM customer_user WHERE cod_univ IS NOT NULL)"""
_Q_SCHEMAS = f"""SELECT u.username, TO_CHAR(u.created, {_ISO}) created FROM all_users u
 WHERE EXISTS (SELECT 1 FROM all_tables t WHERE t.owner = u.username AND t.table_name = 'TMS_UNIVERS')"""
_Q_PROJECTS = "SELECT customer_id, name FROM project WHERE active = 1"
_Q_MANUAL = """SELECT 'cli' t, code k, NULL v FROM nmon_cli WHERE origin = 'manual'
 UNION ALL SELECT 'otrs', otrs_customer_id, NULL FROM nmon_cli_otrs WHERE origin = 'manual'
 UNION ALL SELECT 'schema', db || '.' || schema_name, NULL FROM nmon_cli_schema WHERE origin = 'manual'"""


def _q(sql: str) -> dict:
    return {"sql": sql, "kind": "query"}


def gather() -> dict:
    res = ob._run([_q(_Q_LOGINS), _q(_Q_CUSTOMERS), _q(_Q_TITLES), _q(_Q_UNIV), _q(_Q_SCHEMAS),
                   _q(_Q_PROJECTS), _q(_Q_MANUAL)], timeout=300)
    names = ["logins", "customers", "titles", "univ", "schemas", "projects", "manual"]
    data = {n: ob._rows(r) for n, r in zip(names, res)}
    from modules.netmon import history_store as hs
    from modules.netmon import clients_store
    data["hosts"] = _hosts_30d()
    data["staff"] = hs.staff_registry()
    try:
        data["pins"] = clients_store.registry()
    except Exception:  # noqa: BLE001
        data["pins"] = {}
    return data


def _hosts_30d() -> list[dict]:
    from models.database import DatabaseModel
    from modules.netmon.history_store import _since
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        cur.execute("""SELECT DB, SCHEMA_NAME, USERHOST, OS_USER, COUNT(DISTINCT DAY) DAYS, SUM(LOGONS) LOGONS,
                              MIN(FIRST_AT) FIRST_AT, MAX(LAST_AT) LAST_AT
                         FROM NMON_LOGON_DAY WHERE DAY >= :since AND SCHEMA_NAME <> '-'
                        GROUP BY DB, SCHEMA_NAME, USERHOST, OS_USER""", since=_since(30))
        cols = [d[0].lower() for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# --------------------------------------------------------- сопоставление

def build(data: dict) -> dict:
    """Всё сопоставление в памяти: клиенты, связи, точки, продукты, несостыковки."""
    from modules.netmon import staff_rules as sr
    clients: dict[str, dict] = {}

    def client(code: str) -> dict:
        return clients.setdefault(code, {"code": code, "name": None, "idno": None, "cod_univ": None,
                                         "kind": "none", "manager": None, "contract": None,
                                         "otrs": {}, "logins": {}, "schemas": {}, "points": {},
                                         "products": {}, "tickets": 0, "open_tickets": 0, "last_ticket": None})
    # 1. Схемы клиентов UniAcc → клиенты по основе имени
    logons = {}
    for h in data["hosts"]:
        k = (h["db"], h["schema_name"])
        logons[k] = logons.get(k, 0) + (h["logons"] or 0)
    for s in data["schemas"]:
        name = s["username"]
        base = ur.base_of(name)
        if not base or base in ("UNI", "UNITEST", "TICKETS", "OTRS"):
            continue
        c = client(base)
        c["schemas"][("cloudbd", name)] = {"role": ur.role_of(name), "match_by": "schema",
                                           "created": s.get("created"), "logons_30d": logons.get(("cloudbd", name), 0)}
    # Схема прошлых лет: если у клиента несколько «бэков», основной — с входами
    for c in clients.values():
        backs = [k for k, v in c["schemas"].items() if v["role"] == "back"]
        if len(backs) > 1:
            main = max(backs, key=lambda k: (c["schemas"][k]["logons_30d"], k[1]))
            for k in backs:
                if k != main and k[1] != c["code"]:
                    c["schemas"][k]["role"] = "year"

    keys = {code: code for code in clients}   # нормализованный ключ → код клиента
    univ = {u["cod"]: u for u in data["univ"]}
    issues: list[dict] = []

    def find(key: str) -> tuple[str | None, int, str]:
        if key in keys:
            return keys[key], 100, "name"
        best = (None, 0, "")
        for k, code in keys.items():
            sc, by = ur.match_score(key, k)
            if sc > best[1]:
                best = (code, sc, by)
        return best

    # 2. Логины клиентов OTRS: логин и код контрагента
    login_of_customer: dict[str, list[dict]] = {}
    for lg in data["logins"]:
        login_of_customer.setdefault(lg["customer_id"], []).append(lg)
        u = univ.get(lg.get("cod_univ"))
        if u and lg.get("customer_id"):
            a, b = ur.norm(u["denumirea"]), ur.norm(lg["customer_id"])
            if a and b and not ur.match_score(a, b)[0] and a not in b and b not in a:
                issues.append({"kind": "cod_univ_mismatch", "subject": f"логин {lg['login']}",
                               "detail": f"в OTRS заказчик «{lg['customer_id']}», а код контрагента {lg['cod_univ']} "
                                         f"в бухгалтерии — «{u['denumirea']}»", "code": None})

    # 3. Заказчики из заявок OTRS
    customers = {c["customer_id"]: c for c in data["customers"]}
    for cid, cu in customers.items():
        key = ur.norm(cid)
        code, score, by = find(key)
        for lg in login_of_customer.get(cid, []):            # логин точнее названия
            lk = ur.norm(lg["login"])
            if lk in keys and score < 95:
                code, score, by = keys[lk], 95, "login"
            u = univ.get(lg.get("cod_univ"))
            if u and score < 90:
                uc, us, _ = find(ur.norm(u["denumirea"]))
                if us >= 100:
                    code, score, by = uc, 90, "cod_univ"
        if not code or score < 70:
            if not key or (cu.get("tickets") or 0) < 2:
                continue
            code, score, by = key[:60], 100, "otrs_only"     # клиент без базы у нас — только сопровождение
            keys[key] = code
        c = client(code)
        c["otrs"][cid] = {"match_by": by, "score": score}
        c["tickets"] += cu.get("tickets") or 0
        c["open_tickets"] += cu.get("open_tickets") or 0
        if (cu.get("last_ticket") or "") > (c["last_ticket"] or ""):
            c["last_ticket"] = cu["last_ticket"]
            c["manager"] = cu.get("manager") or c["manager"]
            c["contract"] = cu.get("contract") or c["contract"]
        for lg in login_of_customer.get(cid, []):
            c["logins"][lg["login"]] = lg.get("cod_univ")
            u = univ.get(lg.get("cod_univ"))
            if u and not c["cod_univ"]:
                c["cod_univ"], c["name"], c["idno"] = lg["cod_univ"], u["denumirea"], u.get("codfiscal")
    for c in clients.values():
        if not c["name"] and c["otrs"]:
            c["name"] = max(c["otrs"], key=len)
        if len(c["otrs"]) > 1:
            issues.append({"kind": "otrs_variants", "subject": c["code"],
                           "detail": "один клиент записан в заявках по-разному: " + "; ".join(sorted(c["otrs"])),
                           "code": c["code"]})

    # 4. Точки за 30 дней по истории входов (без наших специалистов)
    schema_client = {s: code for code, c in clients.items() for (_db, s) in c["schemas"]}
    for h in data["hosts"]:
        code = schema_client.get(h["schema_name"]) or (ur.base_of(h["schema_name"]) if ur.base_of(h["schema_name"]) in clients else None)
        if not code or sr.staff_of(h["userhost"], h["os_user"], h["schema_name"], data["staff"])[0]:
            continue
        kind = ur.host_kind(h["userhost"], h["os_user"])
        host = ur.host_name(h["userhost"]) if kind != "office" else h["userhost"]
        p = clients[code]["points"].setdefault((kind, host), {
            "kind": kind, "host": host, "os_user": h["os_user"], "days": 0, "logons": 0,
            "first": h["first_at"], "last": h["last_at"]})
        p["days"] = max(p["days"], h["days"] or 0)
        p["logons"] += h["logons"] or 0
        p["first"] = min(p["first"] or h["first_at"], h["first_at"] or p["first"])
        p["last"] = max(p["last"] or h["last_at"], h["last_at"] or p["last"])

    # 5. Продукты: по заявкам и по точкам; тип клиента
    titles: dict[str, list] = {}
    for t in data["titles"]:
        titles.setdefault(t["customer_id"], []).append((t["tn"], t["title"]))
    for code, c in clients.items():
        tl = [x for cid in c["otrs"] for x in titles.get(cid, [])]
        c["products"] = ur.products_of_titles(tl)
        for (kind, host) in c["points"]:
            c["products"].setdefault(ur.HOST_PRODUCT[kind], f"подключение {host}")
        pin = (data["pins"].get(code) or {}).get("kind")
        c["kind"] = pin or ur.kind_of(list(c["points"].values()))
        if not c["schemas"] and c["otrs"]:
            c["kind"] = pin or "none"

    # 6. Несостыковки: одинаковый фискальный код у разных клиентов
    by_idno: dict[str, list] = {}
    for c in clients.values():
        if c["idno"]:
            by_idno.setdefault(c["idno"], []).append(c["code"])
    for idno, codes in by_idno.items():
        if len(codes) > 1:
            issues.append({"kind": "dup_idno", "subject": idno,
                           "detail": f"фискальный код {idno} у нескольких клиентов: {', '.join(sorted(codes))}",
                           "code": None})
    return {"clients": clients, "issues": issues,
            "projects": data["projects"], "manual": {(m["t"], m["k"]) for m in data["manual"]}}


# ---------------------------------------------------------------- запись

def _merge_cli(c: dict) -> dict:
    return {"sql": """MERGE INTO nmon_cli t USING (SELECT :code code FROM dual) s ON (t.code = s.code)
        WHEN MATCHED THEN UPDATE SET name = :name, idno = :idno, cod_univ = :cod, kind = :kind,
             manager = :manager, contract = :contract, updated_at = SYSDATE, updated_by = 'netmon'
             WHERE t.origin = 'auto'
        WHEN NOT MATCHED THEN INSERT (cli_id, code, name, idno, cod_univ, kind, manager, contract, updated_by)
             VALUES (nmon_cli_seq.NEXTVAL, :code, :name, :idno, :cod, :kind, :manager, :contract, 'netmon')""",
            "params": {"code": c["code"], "name": (c["name"] or "")[:300] or None, "idno": c["idno"],
                       "cod": c["cod_univ"], "kind": c["kind"], "manager": (c["manager"] or "")[:100] or None,
                       "contract": (c["contract"] or "")[:100] or None}, "kind": "dml"}


def write(result: dict) -> dict:
    clients = result["clients"]
    # 1. Клиенты, затем их номера
    ob._run([_merge_cli(c) for c in clients.values()], timeout=600)
    ids = {r["code"]: r["cli_id"] for r in ob._rows(ob._run([_q("SELECT cli_id, code FROM nmon_cli")])[0])}
    st = [{"sql": f"DELETE FROM {t} WHERE origin = 'auto'", "kind": "dml"}
          for t in ("nmon_cli_otrs", "nmon_cli_login", "nmon_cli_schema", "nmon_cli_point", "nmon_cli_product")]
    st.append({"sql": "DELETE FROM nmon_cli_issue WHERE resolved = 0", "kind": "dml"})
    n = {"otrs": 0, "schemas": 0, "points": 0, "products": 0, "logins": 0}
    for code, c in clients.items():
        cid = ids.get(code)
        if not cid:
            continue
        for oc, m in c["otrs"].items():
            if ("otrs", oc) in result["manual"]:
                continue
            st.append({"sql": """INSERT INTO nmon_cli_otrs (otrs_customer_id, cli_id, match_by, score)
                                 SELECT :oc, :cid, :by, :sc FROM dual
                                  WHERE NOT EXISTS (SELECT 1 FROM nmon_cli_otrs WHERE otrs_customer_id = :oc)""",
                       "params": {"oc": oc[:150], "cid": cid, "by": m["match_by"], "sc": m["score"]}, "kind": "dml"})
            n["otrs"] += 1
        for lg, cod in c["logins"].items():
            st.append({"sql": """INSERT INTO nmon_cli_login (customer_login, cli_id, cod_univ)
                                 SELECT :lg, :cid, :cod FROM dual
                                  WHERE NOT EXISTS (SELECT 1 FROM nmon_cli_login WHERE customer_login = :lg)""",
                       "params": {"lg": lg[:100], "cid": cid, "cod": cod}, "kind": "dml"})
            n["logins"] += 1
        for (db, sch), s in c["schemas"].items():
            if ("schema", f"{db}.{sch}") in result["manual"]:
                continue
            st.append({"sql": """INSERT INTO nmon_cli_schema (db, schema_name, cli_id, role, match_by, logons_30d, created)
                                 VALUES (:db, :sch, :cid, :role, :by, :n, TO_DATE(:cr, 'YYYY-MM-DD"T"HH24:MI:SS'))""",
                       "params": {"db": db, "sch": sch, "cid": cid, "role": s["role"], "by": s["match_by"],
                                  "n": s["logons_30d"], "cr": s.get("created")}, "kind": "dml"})
            n["schemas"] += 1
        for (kind, host), p in c["points"].items():
            st.append({"sql": """INSERT INTO nmon_cli_point (point_id, cli_id, kind, host, os_user, first_seen, last_seen,
                                                             days_30d, logons_30d)
                                 SELECT nmon_cli_point_seq.NEXTVAL, :cid, :kind, :host, :osu, :f, :l, :d, :n FROM dual
                                  WHERE NOT EXISTS (SELECT 1 FROM nmon_cli_point
                                                     WHERE cli_id = :cid AND kind = :kind AND host = :host)""",
                       "params": {"cid": cid, "kind": kind, "host": host[:255], "osu": (p["os_user"] or "")[:255] or None,
                                  "f": _d(p["first"]), "l": _d(p["last"]), "d": p["days"], "n": p["logons"]},
                       "kind": "dml"})
            n["points"] += 1
        for prod, ev in c["products"].items():
            st.append({"sql": """INSERT INTO nmon_cli_product (cli_id, product, evidence, first_seen, last_seen)
                                 SELECT :cid, :p, :ev, SYSDATE, SYSDATE FROM dual
                                  WHERE NOT EXISTS (SELECT 1 FROM nmon_cli_product WHERE cli_id = :cid AND product = :p)""",
                       "params": {"cid": cid, "p": prod[:60], "ev": ev[:300]}, "kind": "dml"})
            n["products"] += 1
    for i in result["issues"]:
        st.append({"sql": """INSERT INTO nmon_cli_issue (issue_id, cli_id, kind, subject, detail)
                             SELECT nmon_cli_issue_seq.NEXTVAL, :cid, :k, :s, :d FROM dual
                              WHERE NOT EXISTS (SELECT 1 FROM nmon_cli_issue WHERE kind = :k AND subject = :s)""",
                   "params": {"cid": ids.get(i.get("code")), "k": i["kind"], "s": i["subject"][:200],
                              "d": i["detail"][:1000]}, "kind": "dml"})
    ob._run(st, timeout=900)          # одна транзакция: либо всё, либо ничего
    return {"clients": len(clients), "issues": len(result["issues"]), **n}


def _d(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%dT%H:%M:%S")
    return v


def run() -> dict:
    t = datetime.now()
    res = write(build(gather()))
    res["seconds"] = round((datetime.now() - t).total_seconds(), 1)
    return res
