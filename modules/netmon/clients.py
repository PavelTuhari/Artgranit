"""Подключения клиентов к базам cloudbd и clouddev — сбор.

Сессии снимаются на самом сервере баз (192.168.0.24) через
`sqlplus / as sysdba` — тот же путь, что у фронт-офисов (frontoffice.py):
к clouddev ни одна внешняя учётка не подходит. Одно соединение SSH на обе
базы. Кодировка вывода — UTF-8, иначе имена вроде «USER-ПК» приходят
вопросами. Поля разделены символом 0x1F: он не встречается в именах.

Классификация — clients_rules.py, справочник типов — clients_store.py.
Только чтение: в базах ничего не меняется.
"""
from __future__ import annotations

from datetime import datetime

from modules.netmon import clients_rules as rules
from modules.netmon import frontoffice as fo

SEP = "\x1f"
FIELDS = ["schema", "machine", "osuser", "program", "module", "status", "logon", "idle_sec", "sid"]

_SQL = """set heading off feedback off pagesize 0 linesize 1000 trimspool on
select 'S' || chr(31) || username || chr(31) || machine || chr(31) || osuser || chr(31) ||
       program || chr(31) || module || chr(31) || status || chr(31) ||
       to_char(logon_time, 'YYYY-MM-DD"T"HH24:MI:SS') || chr(31) || last_call_et || chr(31) || sid
  from v$session where type = 'USER' and username is not null;
exit
"""

_SH = """#!/bin/bash
for db in {dbs}; do
  su - oracle -c "export ORACLE_SID=$db NLS_LANG=AMERICAN_AMERICA.AL32UTF8; sqlplus -s / as sysdba @/tmp/netmon_clients.sql" 2>/dev/null |
    sed "s/^/${{db}}|/"
done
"""


def parse(out: str) -> list[dict]:
    rows = []
    for line in out.splitlines():
        db, _, payload = line.partition("|")
        if not payload.startswith("S" + SEP):
            continue
        parts = payload.split(SEP)[1:]
        if len(parts) < len(FIELDS):
            continue
        r = dict(zip(FIELDS, (p.strip() or None for p in parts)))
        r["db"] = db.strip()
        try:
            r["idle_sec"] = int(r["idle_sec"]) if r["idle_sec"] is not None else None
        except ValueError:
            r["idle_sec"] = None
        rows.append(r)
    return rows


def sessions() -> list[dict]:
    sql = _SQL.replace("'", "'\\''")
    sh = _SH.format(dbs=" ".join(fo.DATABASES)).replace("'", "'\\''")
    cmd = (f"printf '%s' '{sql}' > /tmp/netmon_clients.sql && chmod 644 /tmp/netmon_clients.sql && "
           f"printf '%s' '{sh}' > /tmp/netmon_clients.sh && bash /tmp/netmon_clients.sh; "
           f"rm -f /tmp/netmon_clients.sh /tmp/netmon_clients.sql")
    return parse(fo._ssh(cmd))


def collect() -> dict:
    """Клиенты по группам: магазинники, прямые бэки, веб, наши."""
    from modules.netmon import clients_store
    try:
        registry, reg_error = clients_store.registry(), None
    except Exception as e:  # noqa: BLE001 — без справочника вкладка всё равно работает
        registry, reg_error = {}, str(e)[:200]
    conns = rules.classify(sessions())
    _mark_staff(conns)
    data = rules.group(conns, registry)
    data["history"], data["dormant"], data["history_error"] = _history(data, conns)
    data.update({"checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "databases": list(fo.DATABASES), "host": fo.DB_HOST,
                 "registry_error": reg_error, "kinds": list(rules.KINDS),
                 "conn_titles": rules.CONN_TITLES})
    return data


HISTORY_DAYS = 30


def _history(data: dict, conns: list[dict]) -> tuple[dict, list, str | None]:
    """История за 30 дней по каждому клиенту и те, кто был, но сейчас не подключён.

    Заодно — запоминание наших по замеченным Toad/sqlplus и фоновый перенос
    свежего аудита (history.py). Без таблиц истории вкладка всё равно работает.
    """
    try:
        from modules.netmon import history, history_store
        history.learn_staff(conns)
        history.ensure_fresh()
        summary = history_store.clients_summary(HISTORY_DAYS)
    except Exception as e:  # noqa: BLE001
        return {}, [], str(e)[:200]
    for grp in data["groups"].values():
        for cl in grp:
            cl["history"] = summary.get(cl["client"])
    shown = {cl["client"] for grp in data["groups"].values() for cl in grp}
    dormant = sorted((dict(v, client=k) for k, v in summary.items()
                      if k not in shown and k not in rules.INTERNAL_SCHEMAS and k != "-"),
                     key=lambda r: r.get("last_at") or "", reverse=True)
    return {"days": HISTORY_DAYS}, dormant, None


def _mark_staff(conns: list[dict]) -> None:
    """Компьютер или пара «компьютер|пользователь» из справочника наших
    (NMON_STAFF_ID) — это наш специалист в схеме клиента, не рабочее место клиента."""
    try:
        from modules.netmon import history_store
        from modules.netmon import staff_rules
        reg = history_store.staff_registry()
    except Exception:  # noqa: BLE001
        return
    for c in conns:
        if c["kind"] in ("desktop", "other") and staff_rules.staff_of(c.get("machine"), c.get("osuser"), None, reg)[0]:
            c["kind"] = "staff"
            c["kind_title"] = rules.CONN_TITLES["staff"]
