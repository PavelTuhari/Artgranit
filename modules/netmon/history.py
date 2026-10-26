"""История подключений: клиенты по дням и наши специалисты — сбор, перенос, показ.

Источники на сервере баз 192.168.0.24 (тот же SSH, что у фронт-офисов):

  * аудит входов DBA_AUDIT_SESSION обеих баз (cloudbd, clouddev) — база
    хранит его 30 дней;
  * /var/log/secure* — входы SSH на сервер (4 недели);
  * `last -F -w` — сеансы на сервере с началом и концом (с мая 2024);
  * `who` — кто сидит на сервере прямо сейчас.

Перенос в Oracle (history_store.py) повторяемый и идёт с перекрытием, поэтому
история копится дольше, чем живут журналы. Запускается из панели при
открытии вкладки (не чаще раза в FRESH_MIN минут), кнопкой и скриптом
modules/netmon/scripts/netmon_history.py.

Правила — staff_rules.py и clients_rules.py. Базы и сервер только читаются.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from modules.netmon import clients_rules as crules
from modules.netmon import frontoffice as fo
from modules.netmon import staff_rules as srules

SEP = "\x1f"
FRESH_MIN = 15             # чаще не переносить
FIRST_DAYS = 31            # первый перенос — весь аудит (база хранит 30 дней)
OVERLAP = timedelta(hours=2)
SERVER = "cloudbd"         # имя сервера баз в событиях SSH

_lock = threading.Lock()
_running = {"since": 0.0}


# --------------------------------------------------------------- сбор

def _q(s: str) -> str:
    return s.replace("'", "''")


def _audit_sql(since: datetime, hosts: list[str], pairs: list[str]) -> str:
    """Сводка по дням для всех и подробно — по нашим (домен UNAMD, справочник, SYS)."""
    host_in = ", ".join(f"'{_q(h.upper())}'" for h in hosts) or "'-'"
    pair_in = ", ".join(f"'{_q(p.upper())}'" for p in pairs) or "'-'"
    s = since.strftime("%Y-%m-%d %H:%M:%S")
    iso = "'YYYY-MM-DD\"T\"HH24:MI:SS'"
    return f"""set heading off feedback off pagesize 0 linesize 2000 trimspool on
select 'A' || chr(31) || username || chr(31) || nvl(userhost, '-') || chr(31) || nvl(os_username, '-') || chr(31) ||
       to_char(trunc(timestamp), 'YYYY-MM-DD') || chr(31) || count(*) || chr(31) ||
       sum(case when returncode <> 0 then 1 else 0 end) || chr(31) ||
       to_char(min(timestamp), {iso}) || chr(31) || to_char(max(timestamp), {iso})
  from dba_audit_session where timestamp >= trunc(to_date('{s}', 'YYYY-MM-DD HH24:MI:SS'))
 group by username, userhost, os_username, trunc(timestamp);
select 'E' || chr(31) || username || chr(31) || userhost || chr(31) || os_username || chr(31) ||
       to_char(timestamp, {iso}) || chr(31) || to_char(logoff_time, {iso}) || chr(31) ||
       returncode || chr(31) || sessionid
  from dba_audit_session
 where timestamp >= to_date('{s}', 'YYYY-MM-DD HH24:MI:SS')
   and (upper(userhost) like 'UNAMD\\%' or upper(userhost) in ({host_in})
        or upper(userhost) || '|' || upper(os_username) in ({pair_in}) or username in ('SYS', 'SYSTEM'));
exit
"""


def _run_on_server(script: str, sh: str, timeout: int = 240) -> str:
    sql = script.replace("'", "'\\''")
    sh = sh.replace("'", "'\\''")
    return fo._ssh(f"printf '%s' '{sql}' > /tmp/netmon_hist.sql && chmod 644 /tmp/netmon_hist.sql && "
                   f"printf '%s' '{sh}' > /tmp/netmon_hist.sh && bash /tmp/netmon_hist.sh; "
                   f"rm -f /tmp/netmon_hist.sh /tmp/netmon_hist.sql", timeout=timeout)


def collect_audit(since: datetime, registry: dict) -> tuple[list[dict], list[dict]]:
    hosts = [v for (k, v), r in registry.items() if k == "host" and r.get("staff", 1)]
    pairs = [v for (k, v), r in registry.items() if k == "hostuser" and r.get("staff", 1)]
    sh = ("for db in " + " ".join(fo.DATABASES) + "; do\n"
          "  su - oracle -c \"export ORACLE_SID=$db NLS_LANG=AMERICAN_AMERICA.AL32UTF8; "
          "sqlplus -s / as sysdba @/tmp/netmon_hist.sql\" 2>/dev/null | sed \"s/^/${db}|/\"\ndone\n")
    out = _run_on_server(_audit_sql(since, hosts, pairs), sh)
    return parse_audit(out)


def _dt(s: str | None) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S") if s else None
    except ValueError:
        return None


def parse_audit(out: str) -> tuple[list[dict], list[dict]]:
    days, events = [], []
    for line in out.splitlines():
        db, _, p = line.partition("|")
        f = p.split(SEP)
        if f[0] == "A" and len(f) >= 9:
            # неудачный вход бывает без имени схемы — ключ строки не может быть пустым
            days.append({"db": db, "schema": f[1] or "-", "userhost": f[2] or "-", "os_user": f[3] or "-",
                         "day": datetime.strptime(f[4], "%Y-%m-%d"), "logons": int(f[5] or 0),
                         "failed": int(f[6] or 0), "first_at": _dt(f[7]), "last_at": _dt(f[8]),
                         "client": crules.client_key(f[1]) or "-"})
        elif f[0] == "E" and len(f) >= 8 and _dt(f[4]):
            events.append({"source": "db", "target": db, "ref": f"{f[7]}@{f[4]}", "account": f[1] or "-",
                           "from_host": f[2], "os_user": f[3], "start_at": _dt(f[4]), "end_at": _dt(f[5]),
                           "result": "ok" if f[6] in ("0", "") else "fail",
                           "method": "вход в базу" if f[6] in ("0", "") else f"отказ ORA-{int(f[6]):05d}",
                           "detail": None, "interactive": True})
    return days, events


def collect_ssh(now: datetime | None = None) -> tuple[list[dict], list[dict]]:
    """События SSH и кто на сервере прямо сейчас."""
    now = now or datetime.now()
    out = fo._ssh("echo '##LAST'; last -F -w; echo '##SECURE'; "
                  "cat $(ls -tr /var/log/secure*) | grep -E 'sshd\\[[0-9]+\\]: (Accepted|Failed) '; "
                  "echo '##WHO'; who", timeout=120)
    part = {"LAST": [], "SECURE": [], "WHO": []}
    cur = None
    for line in out.splitlines():
        if line.startswith("##") and line[2:] in part:
            cur = line[2:]
        elif cur:
            part[cur].append(line)
    sessions = srules.parse_last("\n".join(part["LAST"]))
    auth = srules.parse_secure("\n".join(part["SECURE"]), now)
    return srules.ssh_events(sessions, auth, SERVER), srules.parse_who("\n".join(part["WHO"]), now)


# ------------------------------------------------------------- перенос

def import_all() -> dict:
    """Перенести новое из аудита и журналов в Oracle. Повторный запуск безопасен."""
    from modules.netmon import history_store as hs
    if not _lock.acquire(blocking=False):
        return {"skipped": "перенос уже идёт"}
    try:
        _running["since"] = time.time()
        now = datetime.now()
        state = hs.sync_state()
        registry = hs.staff_registry()
        last = (state.get("audit") or {}).get("last_at")
        since = (last - OVERLAP) if last else now - timedelta(days=FIRST_DAYS)
        days, db_events = collect_audit(since, registry)
        for e in db_events:
            e["off_hours"] = int(srules.starts_off(e["start_at"]))
            e["auto"] = 0
        n_days = hs.upsert_logon_days(days)
        n_db = hs.upsert_events(db_events)
        hs.save_sync("audit", now, n_days + n_db)

        ssh_events, _who = collect_ssh(now)
        ssh_events = srules.mark_auto(ssh_events)
        last_ssh = (state.get("ssh") or {}).get("last_at")
        if last_ssh:   # wtmp с 2024 года — после первого раза только свежее и незакрытое
            ssh_events = [e for e in ssh_events
                          if e["start_at"] >= last_ssh - timedelta(days=3) or e.get("end_at") is None]
        n_ssh = hs.upsert_events(ssh_events)
        hs.save_sync("ssh", now, n_ssh)
        return {"days": n_days, "db_events": n_db, "ssh_events": n_ssh, "since": since.isoformat(" ", "minutes"),
                "seconds": round(time.time() - _running["since"], 1)}
    finally:
        _lock.release()


def ensure_fresh() -> bool:
    """Перенести в фоне, если с прошлого раза прошло больше FRESH_MIN минут."""
    from modules.netmon import history_store as hs
    try:
        st = hs.sync_state().get("audit") or {}
    except Exception:  # noqa: BLE001 — таблиц ещё нет
        return False
    age = st.get("age_min")
    if age is not None and age < FRESH_MIN or _lock.locked():
        return False
    threading.Thread(target=_safe_import, daemon=True).start()
    return True


def _safe_import() -> None:
    try:
        import_all()
    except Exception as e:  # noqa: BLE001
        try:
            from modules.netmon import history_store as hs
            hs.save_sync("audit", None, 0, f"ошибка: {e}"[:900])
        except Exception:  # noqa: BLE001
            pass


def learn_staff(conns: list[dict]) -> int:
    """Пары «компьютер|пользователь», замеченные с Toad, sqlplus и т. п. не из
    домена UNAMD, запоминаются как наши (ручную отметку не перетирают)."""
    from modules.netmon import history_store as hs
    reg = hs.staff_registry()
    n = 0
    for c in conns:
        if c.get("kind") != "staff" or not c.get("machine") or not c.get("osuser"):
            continue
        if c["machine"].upper().startswith("UNAMD\\") or "MACBOOK" in c["machine"].upper():
            continue
        key = ("hostuser", f"{c['machine']}|{c['osuser']}")
        if key in reg or ("host", c["machine"]) in reg:
            continue
        hs.save_ident(key[0], key[1], 1, None, f"замечен с {c.get('program') or 'инструментом'}",
                      "auto", "netmon", keep_manual=True)
        reg[key] = {"staff": 1}
        n += 1
    return n


# --------------------------------------------------------------- показ

def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%S") if isinstance(d, datetime) else d


def staff_view(days: int = 7) -> dict:
    """Вкладка «Наши специалисты»: сейчас, нерабочее время, вся активность."""
    from modules.netmon import clients as cl
    from modules.netmon import history_store as hs
    registry = hs.staff_registry()
    rows = hs.staff_events(days)
    clock = srules.round_the_clock([r for r in rows if r["source"] == "db"])

    db_rows = []
    out = []
    for r in rows:
        e = {"source": r["source"], "target": r["target"], "account": r["account"], "from_host": r["from_host"],
             "os_user": r["os_user"], "start_at": r["start_at"], "end_at": r["end_at"], "result": r["result"],
             "method": r["method"], "detail": r["detail"], "auto": int(r["auto"] or 0)}
        if e["source"] == "db":
            staff, person = srules.staff_of(e["from_host"], e["os_user"], e["account"], registry)
            if not staff:
                continue
            e["person"] = person
            e["auto"] = int((e["target"], e["account"], e["from_host"], e["os_user"]) in clock)
            db_rows.append(e)
        else:
            e["person"] = srules.ssh_person(e["account"], e["from_host"], registry)
            e["logons"] = 1
            e["open"] = bool(e["end_at"] is None and (e["method"] or "").startswith("сеанс"))
            e["off_hours"] = int(srules.starts_off(e["start_at"]))
            out.append(e)
    out += srules.blocks(db_rows)
    for e in out:
        e["off_reason"] = srules.off_reason(e["start_at"], e.get("end_at"))
        e["overnight"] = int(not e["off_hours"] and srules.off_hours(e["start_at"], e.get("end_at")))
        e["start_at"], e["end_at"] = _iso(e["start_at"]), _iso(e.get("end_at"))
    out.sort(key=lambda e: e["start_at"], reverse=True)

    # Сейчас: наши в базах (V$SESSION) и на сервере (who)
    now_db, now_err = [], None
    try:
        conns = crules.classify(cl.sessions())
        learn_staff(conns)
        for c in conns:
            if srules.is_self_probe(c):
                continue
            staff, person = srules.staff_of(c.get("machine"), c.get("osuser"), c.get("schema"), registry)
            if c["kind"] == "staff" or staff:
                now_db.append({**c, "person": person,
                               "off_hours": int(srules.starts_off(datetime.now()))})
    except Exception as e:  # noqa: BLE001
        now_err = str(e)[:200]
    try:
        _ev, who = collect_ssh()
    except Exception as e:  # noqa: BLE001
        who, now_err = [], (now_err or str(e)[:200])
    for w in who:
        w["person"] = srules.ssh_person(w["user"], w["from"], registry)

    visible = [e for e in out if not e["auto"]]
    people = {e.get("person") or f"{e.get('from_host')}|{e.get('os_user') or e.get('account')}" for e in visible}
    state = hs.sync_state()
    return {
        "days": days, "events": out, "now_db": now_db, "now_ssh": who, "now_error": now_err,
        "summary": {
            "now_db": len(now_db), "now_ssh": len(who),
            "off_hours": sum(1 for e in visible if e["off_hours"]),
            "overnight": sum(1 for e in visible if e.get("overnight")),
            "failed": sum(1 for e in visible if e["result"] == "fail"),
            "ssh": sum(1 for e in visible if e["source"] == "ssh" and e["result"] == "ok"),
            "identities": len(people), "auto": sum(1 for e in out if e["auto"]),
        },
        "work_hours": {"days": "пн–пт", "from": srules.WORK_START, "to": srules.WORK_END},
        "sync": {k: {"last_run": _iso(v.get("last_run")), "age_min": v.get("age_min"),
                     "message": v.get("message")} for k, v in state.items()},
        "refreshing": ensure_fresh(),
    }


def client_history(client: str, days: int = 30) -> dict:
    from modules.netmon import history_store as hs
    rows = hs.client_days(client, days)
    per_day: dict[str, dict] = {}
    for r in rows:
        d = per_day.setdefault(r["day"], {"day": r["day"], "logons": 0, "failed": 0, "hosts": set()})
        d["logons"] += r["logons"] or 0
        d["failed"] += r["failed"] or 0
        d["hosts"].add(r["userhost"])
    daily = [{**d, "hosts": len(d["hosts"])} for d in sorted(per_day.values(), key=lambda x: x["day"])]
    spikes = set(srules.spikes({d["day"]: d["logons"] for d in daily}))
    for d in daily:
        d["spike"] = d["day"] in spikes
    hosts: dict[tuple, dict] = {}
    for r in rows:
        h = hosts.setdefault((r["userhost"], r["os_user"]), {
            "userhost": r["userhost"], "os_user": r["os_user"], "logons": 0, "days": set(),
            "first_at": r["first_at"], "last_at": r["last_at"], "schemas": set(), "dbs": set()})
        h["logons"] += r["logons"] or 0
        h["days"].add(r["day"])
        h["schemas"].add(r["schema_name"])
        h["dbs"].add(r["db"])
        h["first_at"] = min(h["first_at"] or r["first_at"], r["first_at"] or h["first_at"])
        h["last_at"] = max(h["last_at"] or r["last_at"], r["last_at"] or h["last_at"])
    hl = sorted(({**h, "days": len(h["days"]), "schemas": sorted(h["schemas"]), "dbs": sorted(h["dbs"])}
                 for h in hosts.values()), key=lambda h: h["last_at"] or "", reverse=True)
    return {"client": client.upper(), "days": days, "daily": daily, "hosts": hl,
            "spikes": sorted(spikes)}
