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

import re
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
_Q_ALL_CUSTOMERS = "SELECT DISTINCT customer_id FROM ticket WHERE customer_id IS NOT NULL"
_Q_MANUAL = """SELECT 'cli' t, code k, NULL v FROM nmon_cli WHERE origin = 'manual'
 UNION ALL SELECT 'otrs', otrs_customer_id, NULL FROM nmon_cli_otrs WHERE origin = 'manual'
 UNION ALL SELECT 'schema', db || '.' || schema_name, NULL FROM nmon_cli_schema WHERE origin = 'manual'"""


def _q(sql: str) -> dict:
    return {"sql": sql, "kind": "query"}


def gather() -> dict:
    res = ob._run([_q(_Q_LOGINS), _q(_Q_CUSTOMERS), _q(_Q_TITLES), _q(_Q_UNIV), _q(_Q_SCHEMAS),
                   _q(_Q_PROJECTS), _q(_Q_MANUAL), _q(_Q_ALL_CUSTOMERS)], timeout=300)
    names = ["logins", "customers", "titles", "univ", "schemas", "projects", "manual", "all_customers"]
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

    # 2. Логины клиентов OTRS: логин и код контрагента.
    # Бренд и юрлицо различаются постоянно (магазин «Brand» — «Omega Holding SRL»), это не ошибка.
    # Ошибка — когда код ведёт на юрлицо, которое в OTRS записано за ДРУГИМ
    # заказчиком: логин у заказчика «Beta», а код контрагента — юрлицо заказчика «Alfa».
    login_of_customer: dict[str, list[dict]] = {}
    # все заказчики за всё время: старый заказчик мог не писать годами
    otrs_keys = {ur.norm(r["customer_id"]): r["customer_id"]
                 for r in data.get("all_customers") or data["customers"] if r.get("customer_id")}
    for lg in data["logins"]:
        login_of_customer.setdefault(lg["customer_id"], []).append(lg)
        u = univ.get(lg.get("cod_univ"))
        if not u or not lg.get("customer_id") or ur.similar_names(u["denumirea"], lg["customer_id"]):
            continue
        uk = ur.norm(u["denumirea"])
        other = next((cid for k, cid in otrs_keys.items()
                      if cid != lg["customer_id"] and ur.match_score(uk, k)[0] >= 70), None)
        if other:
            issues.append({"kind": "cod_univ_mismatch", "subject": f"логин {lg['login']}",
                           "detail": f"в OTRS заказчик «{lg['customer_id']}», а код контрагента {lg['cod_univ']} "
                                     f"в бухгалтерии — «{u['denumirea']}», в OTRS это отдельный заказчик «{other}»",
                           "code": None})

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
            c["manager"] = _real(cu.get("manager")) or c["manager"]
            c["contract"] = _real(cu.get("contract")) or c["contract"]
        for lg in login_of_customer.get(cid, []):
            c["logins"][lg["login"]] = lg.get("cod_univ")
            u = univ.get(lg.get("cod_univ"))
            if u and not c["cod_univ"] and (ur.similar_names(u["denumirea"], cid) or ur.match_score(
                    ur.norm(u["denumirea"]), code)[0]):
                c["cod_univ"], c["name"], c["idno"] = lg["cod_univ"], u["denumirea"], u.get("codfiscal")
    # Один фискальный код (или код контрагента) — один клиент: отделы одной
    # сети, отдельно заведённая бухгалтерия, подразделения министерства сливаются в одного.
    _merge_same_entity(clients)
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
        host = ur.host_name(h["userhost"])
        p = clients[code]["points"].setdefault((kind, host), {
            "kind": kind, "host": host, "os_user": h["os_user"], "days": 0, "logons": 0,
            "first": h["first_at"], "last": h["last_at"]})
        p["days"] = max(p["days"], h["days"] or 0)
        p["logons"] += h["logons"] or 0
        p["first"] = min((x for x in (p["first"], h["first_at"]) if x), default=None)
        p["last"] = max((x for x in (p["last"], h["last_at"]) if x), default=None)

    # Компьютер точки магазина (своя база, касса, весы) — не рабочее место офиса
    for c in clients.values():
        shop_hosts = {h for (k, h) in c["points"] if k in ("shop", "pos", "scales")}
        for key in [k for k in c["points"] if k[0] == "office" and k[1] in shop_hosts]:
            del c["points"][key]

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
        c["kind"] = pin or ("internal" if ur.is_ours(code) else ur.kind_of(list(c["points"].values())))
        if not c["schemas"] and c["otrs"]:
            c["kind"] = pin or "none"

    # Клиент работает в базе, а в OTRS его не найти — не видно его заявок
    for code, c in clients.items():
        active = sum(s["logons_30d"] for s in c["schemas"].values())
        if c["schemas"] and active and not c["otrs"]:
            issues.append({"kind": "no_otrs", "subject": code,
                           "detail": f"схема работает ({active} входов за 30 дней), а заказчик в OTRS не связан — "
                                     f"его заявки не видны; связать вручную в карточке клиента", "code": code})
    return {"clients": clients, "issues": issues,
            "projects": data["projects"], "manual": {(m["t"], m["k"]) for m in data["manual"]}}


def _merge_same_entity(clients: dict[str, dict]) -> None:
    """Клиенты с одним фискальным кодом или кодом контрагента сливаются.
    Остаётся тот, у кого есть схема в базе, затем — с большим числом заявок."""
    groups: dict[str, list[str]] = {}
    for code, c in clients.items():
        key = c["idno"] or (f"univ:{c['cod_univ']}" if c["cod_univ"] else None)
        if key:
            groups.setdefault(key, []).append(code)
    for codes in groups.values():
        if len(codes) < 2:
            continue
        main = max(codes, key=lambda k: (bool(clients[k]["schemas"]), clients[k]["tickets"], -len(k)))
        m = clients[main]
        for code in codes:
            if code == main:
                continue
            o = clients.pop(code)
            for f in ("otrs", "logins", "schemas", "points"):
                m[f].update(o[f])
            m["tickets"] += o["tickets"]
            m["open_tickets"] += o["open_tickets"]
            if (o["last_ticket"] or "") > (m["last_ticket"] or ""):
                m["last_ticket"] = o["last_ticket"]
                m["manager"], m["contract"] = o["manager"] or m["manager"], o["contract"] or m["contract"]
            m.setdefault("merged", []).append(code)


# ---------------------------------------------------------------- запись

def _merge_cli(c: dict) -> dict:
    return {"sql": """MERGE INTO nmon_cli t USING (SELECT :b_code code FROM dual) s ON (t.code = s.code)
        WHEN MATCHED THEN UPDATE SET name = :b_name, idno = :b_idno, cod_univ = :b_cod, kind = :b_kind,
             manager = :b_manager, contract = :b_contract, updated_at = SYSDATE, updated_by = 'netmon'
             WHERE t.origin = 'auto'
        WHEN NOT MATCHED THEN INSERT (cli_id, code, name, idno, cod_univ, kind, manager, contract, updated_by)
             VALUES (nmon_cli_seq.NEXTVAL, :b_code, :b_name, :b_idno, :b_cod, :b_kind, :b_manager, :b_contract, 'netmon')""",
            "params": {"b_code": c["code"], "b_name": (c["name"] or "")[:300] or None, "b_idno": c["idno"],
                       "b_cod": c["cod_univ"], "b_kind": c["kind"], "b_manager": (c["manager"] or "")[:100] or None,
                       "b_contract": (c["contract"] or "")[:100] or None}, "b_kind": "dml"}


def write(result: dict) -> dict:
    """Запись. Все привязки с префиксом b_: :by и подобные — ORA-01745."""
    clients = result["clients"]
    # 1. Клиенты, затем их номера
    ob._run([_merge_cli(c) for c in clients.values()], timeout=600)
    ids = {r["code"]: r["cli_id"] for r in ob._rows(ob._run([_q("SELECT cli_id, code FROM nmon_cli")])[0])}
    st = [{"sql": f"DELETE FROM {t} WHERE origin = 'auto'", "b_kind": "dml"}
          for t in ("nmon_cli_otrs", "nmon_cli_login", "nmon_cli_schema", "nmon_cli_point", "nmon_cli_product")]
    st.append({"sql": "DELETE FROM nmon_cli_issue WHERE resolved = 0", "b_kind": "dml"})
    n = {"otrs": 0, "schemas": 0, "points": 0, "products": 0, "logins": 0}
    for code, c in clients.items():
        cid = ids.get(code)
        if not cid:
            continue
        for oc, m in c["otrs"].items():
            if ("otrs", oc) in result["manual"]:
                continue
            st.append({"sql": """INSERT INTO nmon_cli_otrs (otrs_customer_id, cli_id, match_by, score)
                                 SELECT :b_oc, :b_cid, :b_by, :b_sc FROM dual
                                  WHERE NOT EXISTS (SELECT 1 FROM nmon_cli_otrs WHERE otrs_customer_id = :b_oc)""",
                       "params": {"b_oc": oc[:150], "b_cid": cid, "b_by": m["match_by"], "b_sc": m["score"]}, "b_kind": "dml"})
            n["otrs"] += 1
        for lg, cod in c["logins"].items():
            st.append({"sql": """INSERT INTO nmon_cli_login (customer_login, cli_id, cod_univ)
                                 SELECT :b_lg, :b_cid, :b_cod FROM dual
                                  WHERE NOT EXISTS (SELECT 1 FROM nmon_cli_login WHERE customer_login = :b_lg)""",
                       "params": {"b_lg": lg[:100], "b_cid": cid, "b_cod": cod}, "b_kind": "dml"})
            n["logins"] += 1
        for (db, sch), s in c["schemas"].items():
            if ("schema", f"{db}.{sch}") in result["manual"]:
                continue
            st.append({"sql": """INSERT INTO nmon_cli_schema (db, schema_name, cli_id, role, match_by, logons_30d, created)
                                 VALUES (:b_db, :b_sch, :b_cid, :b_role, :b_by, :b_n, TO_DATE(:b_cr, 'YYYY-MM-DD"T"HH24:MI:SS'))""",
                       "params": {"b_db": db, "b_sch": sch, "b_cid": cid, "b_role": s["role"], "b_by": s["match_by"],
                                  "b_n": s["logons_30d"], "b_cr": s.get("created")}, "b_kind": "dml"})
            n["schemas"] += 1
        for (kind, host), p in c["points"].items():
            st.append({"sql": """INSERT INTO nmon_cli_point (point_id, cli_id, kind, host, os_user, first_seen, last_seen,
                                                             days_30d, logons_30d)
                                 SELECT nmon_cli_point_seq.NEXTVAL, :b_cid, :b_kind, :b_host, :b_osu,
                                        TO_DATE(:b_f, 'YYYY-MM-DD"T"HH24:MI:SS'), TO_DATE(:b_l, 'YYYY-MM-DD"T"HH24:MI:SS'),
                                        :b_d, :b_n FROM dual
                                  WHERE NOT EXISTS (SELECT 1 FROM nmon_cli_point
                                                     WHERE cli_id = :b_cid AND kind = :b_kind AND host = :b_host)""",
                       "params": {"b_cid": cid, "b_kind": kind, "b_host": host[:255], "b_osu": (p["os_user"] or "")[:255] or None,
                                  "b_f": _d(p["first"]), "b_l": _d(p["last"]), "b_d": p["days"], "b_n": p["logons"]},
                       "b_kind": "dml"})
            n["points"] += 1
        for prod, ev in c["products"].items():
            st.append({"sql": """INSERT INTO nmon_cli_product (cli_id, product, evidence, first_seen, last_seen)
                                 SELECT :b_cid, :b_p, :b_ev, SYSDATE, SYSDATE FROM dual
                                  WHERE NOT EXISTS (SELECT 1 FROM nmon_cli_product WHERE cli_id = :b_cid AND product = :b_p)""",
                       "params": {"b_cid": cid, "b_p": prod[:60], "b_ev": ev[:300]}, "b_kind": "dml"})
            n["products"] += 1
    for i in result["issues"]:
        st.append({"sql": """INSERT INTO nmon_cli_issue (issue_id, cli_id, kind, subject, detail)
                             SELECT nmon_cli_issue_seq.NEXTVAL, :b_cid, :b_k, :b_s, :b_d FROM dual
                              WHERE NOT EXISTS (SELECT 1 FROM nmon_cli_issue WHERE kind = :b_k AND subject = :b_s)""",
                   "params": {"b_cid": ids.get(i.get("code")), "b_k": i["kind"], "b_s": i["subject"][:200],
                              "b_d": i["detail"][:1000]}, "b_kind": "dml"})
    ob._run(st, timeout=900)          # одна транзакция: либо всё, либо ничего
    return {"clients": len(clients), "issues": len(result["issues"]), **n}


def _real(v: str | None) -> str | None:
    """Заглушки OTRS — не значение: «Fara manager», «Nu este contract valid»."""
    s = (v or "").strip()
    return None if not s or re.match(r"(?i)^(fara|nu este|без|нет|-+$|n/?a$)", s) else s


def _d(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%dT%H:%M:%S")
    return v


def run() -> dict:
    t = datetime.now()
    res = write(build(gather()))
    res["seconds"] = round((datetime.now() - t).total_seconds(), 1)
    return res
