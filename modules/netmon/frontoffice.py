"""Фронт-офисы на базах cloudbd и clouddev.

Фронт-офис здесь — это схема Oracle, под которой работает торговая точка
или контора: `RETAILMARKETS`, `AURUM`, `DORIMAX` и так далее. Их около
сорока, и обычный мониторинг сервера про них ничего не говорит — база
может быть жива, а конкретный магазин уже час как не подключается.

Данные снимаются **на самом сервере** через `sqlplus / as sysdba`: у
внешних учётных записей нет прав на `V$SESSION`, а к `clouddev` ни одна
известная учётка вообще не подходит. Пароль root сервера — в Keychain.
"""
from __future__ import annotations

import os
import re
import subprocess

DB_HOST = "192.168.0.24"
DB_HOST_NAME = "cloudbd.internal.uniacc.md"
KEYCHAIN_SERVICE = "192.168.0.24"
DATABASES = ("cloudbd", "clouddev")

# Схемы, которые не являются фронт-офисами: служебные и внутренние
NOT_FRONTOFFICE = {
    "SYS", "SYSTEM", "DBSNMP", "SYSMAN", "OUTLN", "XDB", "ANONYMOUS",
    "HARUZ", "HARUZDAR2018", "XWIKI", "TICKETS_WS", "TICKETS",
}

# Сколько сессий считается «фронт-офис живёт». Одна сессия бывает у
# фонового задания, поэтому порог именно 1, а не 0.
MIN_SESSIONS = 1

_REMOTE_SQL = """set heading off feedback off pagesize 0 linesize 200 trimspool on
select 'INSTANCE:' || instance_name || ':' || status || ':' ||
       floor(sysdate - startup_time) from v$instance;
select 'SESSIONS:' || count(*) from v$session where type = 'USER';
select 'FRONT:' || username || ':' || count(*) from v$session
 where type = 'USER' and username is not null group by username;
exit
"""

_REMOTE_SH = """#!/bin/bash
for db in {dbs}; do
  su - oracle -c "export ORACLE_SID=$db; sqlplus -s / as sysdba @/tmp/netmon_dbstat.sql" 2>/dev/null |
    sed "s/^/${{db}}|/"
done
"""


def keychain_root() -> str:
    r = subprocess.run(["security", "find-internet-password", "-s", KEYCHAIN_SERVICE,
                        "-a", "root", "-w"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _ssh(command: str, timeout: int = 120) -> str:
    pw = keychain_root()
    if not pw:
        raise RuntimeError(f"нет пароля сервера {DB_HOST} в Keychain")
    env = dict(os.environ)
    env["SSHPASS"] = pw
    r = subprocess.run(
        ["sshpass", "-e", "ssh", "-o", "HostKeyAlgorithms=+ssh-rsa",
         "-o", "PubkeyAcceptedKeyTypes=+ssh-rsa", "-o", "StrictHostKeyChecking=no",
         "-o", "ConnectTimeout=15", f"root@{DB_HOST}", command],
        capture_output=True, text=True, env=env, timeout=timeout)
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError(f"сервер {DB_HOST} недоступен: {r.stderr.strip()[:140]}")
    return r.stdout


def collect() -> dict:
    """Состояние обеих баз и активность каждого фронт-офиса."""
    sql = _REMOTE_SQL.replace("'", "'\\''")
    sh = _REMOTE_SH.format(dbs=" ".join(DATABASES)).replace("'", "'\\''")
    cmd = (f"printf '%s' '{sql}' > /tmp/netmon_dbstat.sql && chmod 644 /tmp/netmon_dbstat.sql && "
           f"printf '%s' '{sh}' > /tmp/netmon_dbstat.sh && bash /tmp/netmon_dbstat.sh; "
           f"rm -f /tmp/netmon_dbstat.sh /tmp/netmon_dbstat.sql")
    out = _ssh(cmd)

    dbs: dict[str, dict] = {d: {"name": d, "status": "unknown", "uptime_days": None,
                                "sessions": 0, "fronts": {}} for d in DATABASES}
    for line in out.splitlines():
        if "|" not in line:
            continue
        db, _, payload = line.partition("|")
        db, payload = db.strip(), payload.strip()
        if db not in dbs or not payload:
            continue
        if payload.startswith("INSTANCE:"):
            p = payload.split(":")
            if len(p) >= 4:
                dbs[db].update({"status": p[2], "uptime_days": int(p[3] or 0)})
        elif payload.startswith("SESSIONS:"):
            dbs[db]["sessions"] = int(payload.split(":", 1)[1] or 0)
        elif payload.startswith("FRONT:"):
            p = payload.split(":")
            if len(p) >= 3:
                dbs[db]["fronts"][p[1]] = int(p[2] or 0)

    fronts = []
    for db, info in dbs.items():
        for schema, sess in sorted(info["fronts"].items(), key=lambda x: -x[1]):
            if schema.upper() in NOT_FRONTOFFICE:
                continue
            fronts.append({"db": db, "schema": schema, "sessions": sess,
                           "alive": sess >= MIN_SESSIONS})
    return {"host": DB_HOST, "host_name": DB_HOST_NAME,
            "databases": [dbs[d] for d in DATABASES], "fronts": fronts}


def summary(data: dict) -> dict:
    f = data["fronts"]
    return {
        "databases": len(data["databases"]),
        "db_open": sum(1 for d in data["databases"] if d["status"] == "OPEN"),
        "fronts": len(f),
        "fronts_alive": sum(1 for x in f if x["alive"]),
        "sessions": sum(d["sessions"] for d in data["databases"]),
        "by_db": {d["name"]: {"status": d["status"], "sessions": d["sessions"],
                              "uptime_days": d["uptime_days"],
                              "fronts": sum(1 for x in f if x["db"] == d["name"])}
                  for d in data["databases"]},
    }
