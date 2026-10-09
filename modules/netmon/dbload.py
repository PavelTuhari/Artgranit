"""Нагрузка сервера баз данных: сам Linux и сессии Oracle cloudbd/clouddev.

Хост — cloudbd.internal.uniacc.md (192.168.0.24): CentOS 7.2, 16 ядер Xeon
E5-2623 v3, 64 ГБ памяти, аппаратный RAID (см. storage.py). На нём два
экземпляра Oracle 11.2.0.4 EE: cloudbd (боевая) и clouddev.

Один SSH-заход снимает всё:

* хост — /proc/loadavg, vmstat (процессор, ожидание диска), free, iostat -x
  (загрузка и задержка каждого диска), top за 2 секунды;
* по каждой базе через `sqlplus / as sysdba` — v$sysmetric, активные сессии
  с длительностью текущего вызова, ожиданием, SQL и блокировщиком, топ
  сессий по процессору и по чтениям с диска, длинные операции.

Почему top, а не ps: `ps -o pcpu` — это процессорное время, усреднённое за
ВСЮ жизнь процесса. Сессия, которая час назад подключилась и последние 10
секунд жжёт ядро, в ps выглядит тихой. top за 2 секунды показывает «сейчас».

Процесс ОС сопоставляется с сессией по v$process.spid — так видно, какая
сессия какой базы грузит процессор прямо сейчас.

Только чтение. Сессии не убиваются: панель показывает готовую команду
ALTER SYSTEM KILL SESSION для DBA, но не выполняет её.
"""
from __future__ import annotations

import base64
import re

from modules.netmon import frontoffice

HOST = frontoffice.DB_HOST
HOST_NAME = frontoffice.DB_HOST_NAME
DATABASES = frontoffice.DATABASES

# Пороги — в одном месте, их же использует Zabbix.
LONG_CALL_WARN = 300          # активный вызов дольше 5 минут
LONG_CALL_CRIT = 1800         # дольше 30 минут
BLOCK_WARN = 30               # сессия ждёт блокировку дольше 30 секунд
LOAD_PER_CORE_WARN = 0.8
LOAD_PER_CORE_CRIT = 1.2
IOWAIT_WARN = 15              # % процессорного времени в ожидании диска
DISK_UTIL_WARN = 85           # % загрузки устройства
DISK_AWAIT_WARN = 50          # мс на операцию
MEM_AVAIL_WARN = 10           # % доступной памяти

# Разделитель полей в выводе SQL. В текстах сессий его не бывает, а «|»
# бывает в модулях и программах.
SEP = "~^~"

_SQL = r"""set heading off feedback off pagesize 0 linesize 4000 trimspool on long 200
set termout on
column x format a4000
select 'METRIC~^~' || metric_name || '~^~' || round(value, 2) from v$sysmetric
 where group_id = 2 and metric_name in (
  'Host CPU Utilization (%)', 'Average Active Sessions', 'Database CPU Time Ratio',
  'Physical Reads Per Sec', 'Physical Writes Per Sec', 'User Transaction Per Sec',
  'Executions Per Sec', 'Redo Generated Per Sec', 'Logical Reads Per Sec');
select 'SESS~^~' || count(*) || '~^~' || sum(decode(status, 'ACTIVE', 1, 0))
  from v$session where type = 'USER';
select 'CPUCOUNT~^~' || value from v$parameter where name = 'cpu_count';
-- Активные сессии: что делают, сколько длится текущий вызов, кого ждут
select 'ACT~^~' || s.sid || '~^~' || s.serial# || '~^~' || s.username || '~^~' ||
       replace(s.osuser, '~', '') || '~^~' || replace(s.machine, '~', '') || '~^~' ||
       replace(substr(s.program, 1, 48), '~', '') || '~^~' || replace(substr(s.module, 1, 48), '~', '') || '~^~' ||
       s.sql_id || '~^~' || replace(s.event, '~', '') || '~^~' || s.wait_class || '~^~' || s.state || '~^~' ||
       s.seconds_in_wait || '~^~' || s.last_call_et || '~^~' || s.blocking_session || '~^~' || p.spid || '~^~' ||
       (select st.value from v$sesstat st, v$statname n where st.statistic# = n.statistic#
         and n.name = 'CPU used by this session' and st.sid = s.sid) || '~^~' ||
       (select st.value from v$sesstat st, v$statname n where st.statistic# = n.statistic#
         and n.name = 'physical reads' and st.sid = s.sid)
  from v$session s, v$process p
 where s.paddr = p.addr and s.type = 'USER' and s.status = 'ACTIVE'
   and s.sid <> sys_context('userenv', 'sid')
 order by s.last_call_et desc;
-- Самые тяжёлые сессии по процессору и по чтениям с диска (с момента входа)
select 'TOP~^~' || kind || '~^~' || sid || '~^~' || serial# || '~^~' || username || '~^~' ||
       replace(machine, '~', '') || '~^~' || replace(substr(program, 1, 48), '~', '') || '~^~' ||
       status || '~^~' || sql_id || '~^~' || spid || '~^~' || val || '~^~' || logon_min
  from (
    select 'cpu' kind, s.sid, s.serial#, s.username, s.machine, s.program, s.status, s.sql_id, p.spid,
           st.value val, round((sysdate - s.logon_time) * 1440) logon_min,
           row_number() over (order by st.value desc) rn
      from v$session s, v$process p, v$sesstat st, v$statname n
     where s.paddr = p.addr and s.type = 'USER' and st.sid = s.sid
       and st.statistic# = n.statistic# and n.name = 'CPU used by this session'
    union all
    select 'io', s.sid, s.serial#, s.username, s.machine, s.program, s.status, s.sql_id, p.spid,
           st.value, round((sysdate - s.logon_time) * 1440),
           row_number() over (order by st.value desc)
      from v$session s, v$process p, v$sesstat st, v$statname n
     where s.paddr = p.addr and s.type = 'USER' and st.sid = s.sid
       and st.statistic# = n.statistic# and n.name = 'physical reads'
  ) where rn <= 8;
-- Длинные операции, которые ещё идут
select 'LONG~^~' || sid || '~^~' || serial# || '~^~' || replace(substr(opname, 1, 40), '~', '') || '~^~' ||
       replace(substr(target, 1, 60), '~', '') || '~^~' || round(sofar / nullif(totalwork, 0) * 100) || '~^~' ||
       elapsed_seconds || '~^~' || time_remaining
  from v$session_longops where time_remaining > 0;
-- Текст SQL для тех, кто сейчас активен или в топе
select 'SQL~^~' || sql_id || '~^~' || replace(replace(substr(sql_text, 1, 160), chr(10), ' '), '~', '')
  from (select sql_id, sql_text, row_number() over (partition by sql_id order by child_number) rn
          from v$sql where sql_id in (
            select sql_id from v$session where type = 'USER' and sql_id is not null
              and (status = 'ACTIVE' or sid in (
                select sid from (select st.sid from v$sesstat st, v$statname n
                  where st.statistic# = n.statistic# and n.name = 'CPU used by this session'
                  order by st.value desc) where rownum <= 8))))
 where rn = 1;
exit
"""

_SH = r"""
echo '===LOADAVG==='; cat /proc/loadavg; nproc
echo '===VMSTAT==='; vmstat 2 2 | tail -1
echo '===MEM==='; free -m | awk '/^Mem:/{print $2, $7} /^Swap:/{print $2, $3}'
echo '===IOSTAT==='; iostat -dxm 2 2 | awk '/^Device/{n++; next} n==2 && NF'
echo '===TOP==='; top -b -n 2 -d 2 -w 200 2>/dev/null | awk '/^top -/{n++} n==2' | awk 'f && NF {print} /PID USER/{f=1}' | head -15
echo %(b64)s | base64 -d > /tmp/netmon_dbload.sql && chmod 644 /tmp/netmon_dbload.sql
for db in %(dbs)s; do
  echo "===DB $db==="
  su - oracle -c "export ORACLE_SID=$db; sqlplus -s / as sysdba @/tmp/netmon_dbload.sql" 2>&1
done
rm -f /tmp/netmon_dbload.sql
echo '===END==='
"""


def _sections(raw: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    key = None
    for line in raw.splitlines():
        m = re.match(r"^===(.+?)===$", line.strip())
        if m:
            key = m.group(1)
            out[key] = []
        elif key:
            out[key].append(line)
    return out


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_host(sec: dict) -> dict:
    load = (sec.get("LOADAVG") or ["0 0 0", "1"])
    la = load[0].split()
    cores = int(load[1]) if len(load) > 1 and load[1].strip().isdigit() else 1
    vm = (sec.get("VMSTAT") or [""])[0].split()
    # vmstat: r b swpd free buff cache si so bi bo in cs us sy id wa st
    cpu = {}
    if len(vm) >= 16:
        cpu = {"user": int(vm[12]), "system": int(vm[13]), "idle": int(vm[14]),
               "iowait": int(vm[15]), "running": int(vm[0]), "blocked": int(vm[1])}
    mem_lines = sec.get("MEM") or []
    mem = {}
    if mem_lines:
        t, a = (mem_lines[0].split() + ["0", "0"])[:2]
        mem = {"total_mb": int(_num(t)), "available_mb": int(_num(a)),
               "available_pct": round(_num(a) * 100 / _num(t, 1))}
        if len(mem_lines) > 1:
            st, su = (mem_lines[1].split() + ["0", "0"])[:2]
            mem.update({"swap_total_mb": int(_num(st)), "swap_used_mb": int(_num(su))})
    disks = []
    for line in sec.get("IOSTAT") or []:
        f = line.split()
        # Device rrqm/s wrqm/s r/s w/s rMB/s wMB/s avgrq-sz avgqu-sz await r_await w_await svctm %util
        if len(f) >= 14 and not f[0].startswith("dm-"):
            disks.append({"device": f[0], "r_s": _num(f[3]), "w_s": _num(f[4]),
                          "read_mb_s": _num(f[5]), "write_mb_s": _num(f[6]),
                          "queue": _num(f[8]), "await_ms": _num(f[9]), "util_pct": _num(f[13])})
    procs = []
    for line in sec.get("TOP") or []:
        f = line.split(None, 11)
        if len(f) >= 12 and f[0].isdigit():
            procs.append({"pid": f[0], "user": f[1], "cpu_pct": _num(f[8]), "mem_pct": _num(f[9]),
                          "time": f[10], "command": f[11].strip()})
    return {
        "load1": _num(la[0]) if la else 0, "load5": _num(la[1]) if len(la) > 1 else 0,
        "load15": _num(la[2]) if len(la) > 2 else 0, "cores": cores,
        "cpu": cpu, "mem": mem, "disks": disks, "top": procs,
    }


_ACT = ["sid", "serial", "username", "osuser", "machine", "program", "module", "sql_id", "event",
        "wait_class", "state", "seconds_in_wait", "call_seconds", "blocking_session", "spid",
        "cpu_cs", "phys_reads"]
_TOP = ["kind", "sid", "serial", "username", "machine", "program", "status", "sql_id", "spid",
        "value", "logon_min"]
_LONG = ["sid", "serial", "opname", "target", "pct", "elapsed", "remaining"]
_INT = {"sid", "serial", "seconds_in_wait", "call_seconds", "cpu_cs", "phys_reads", "value",
        "logon_min", "pct", "elapsed", "remaining"}


def _rows(lines: list[str], tag: str, fields: list[str]) -> list[dict]:
    out = []
    for line in lines:
        if not line.startswith(tag + SEP):
            continue
        parts = line.split(SEP)[1:]
        if len(parts) != len(fields):
            continue
        row = dict(zip(fields, (p.strip() for p in parts)))
        for k in _INT & row.keys():
            row[k] = int(_num(row[k]))
        out.append(row)
    return out


def parse_db(name: str, lines: list[str]) -> dict:
    metrics = {}
    for line in lines:
        if line.startswith("METRIC" + SEP):
            _, k, v = line.split(SEP)[:3]
            metrics[k] = _num(v)
    sess = next((l.split(SEP) for l in lines if l.startswith("SESS" + SEP)), ["", "0", "0"])
    cpus = next((int(_num(l.split(SEP)[1])) for l in lines if l.startswith("CPUCOUNT" + SEP)), 0)
    active = _rows(lines, "ACT", _ACT)
    for a in active:
        a["blocking_session"] = int(_num(a["blocking_session"])) if a["blocking_session"] else None
        a["cpu_seconds"] = round(a.pop("cpu_cs") / 100)
        a["kill"] = f"ALTER SYSTEM KILL SESSION '{a['sid']},{a['serial']}' IMMEDIATE;"
    top = _rows(lines, "TOP", _TOP)
    for t in top:
        if t["kind"] == "cpu":
            t["cpu_seconds"] = round(t["value"] / 100)
    sqls = {}
    for line in lines:
        if line.startswith("SQL" + SEP):
            p = line.split(SEP)
            if len(p) >= 3:
                sqls[p[1]] = p[2].strip()
    for row in active + top:
        row["sql_text"] = sqls.get(row.get("sql_id") or "", "")
    errors = [l.strip() for l in lines if re.match(r"^\s*(ORA|SP2)-\d+", l)]
    return {
        "name": name,
        "sessions": int(_num(sess[1])) if len(sess) > 1 else 0,
        "active_count": int(_num(sess[2])) if len(sess) > 2 else 0,
        "cpu_count": cpus,
        "metrics": metrics,
        "active": active,
        "blocked": [a for a in active if a["blocking_session"]],
        "top_cpu": [t for t in top if t["kind"] == "cpu"],
        "top_io": [t for t in top if t["kind"] == "io"],
        "longops": _rows(lines, "LONG", _LONG),
        "errors": errors[:5],
    }


def collect() -> dict:
    b64 = base64.b64encode(_SQL.encode("utf-8")).decode("ascii")
    raw = frontoffice._ssh(_SH % {"b64": b64, "dbs": " ".join(DATABASES)}, timeout=150)
    sec = _sections(raw)
    host = parse_host(sec)
    dbs = [parse_db(db, sec.get(f"DB {db}", [])) for db in DATABASES]
    # Процесс ОС → сессия Oracle: кто именно грузит процессор прямо сейчас
    by_spid = {}
    for d in dbs:
        for row in d["active"] + d["top_cpu"] + d["top_io"]:
            if row.get("spid"):
                by_spid.setdefault(row["spid"], {"db": d["name"], **row})
    for p in host["top"]:
        s = by_spid.get(p["pid"])
        if s:
            p["session"] = {k: s.get(k) for k in ("db", "sid", "serial", "username", "machine",
                                                  "program", "sql_id", "sql_text")}
        elif p["command"].startswith("ora_"):
            p["background"] = True        # фоновый процесс экземпляра (dbw, lgwr, ...)
    return {"host": HOST, "host_name": HOST_NAME, "os": host, "databases": dbs,
            "findings": findings(host, dbs)}


def findings(host: dict, dbs: list[dict]) -> list[dict]:
    out = []
    per_core = host["load1"] / max(host["cores"], 1)
    if per_core >= LOAD_PER_CORE_WARN:
        out.append({"level": "crit" if per_core >= LOAD_PER_CORE_CRIT else "warn",
                    "title": f"Нагрузка {host['load1']} на {host['cores']} ядер",
                    "text": "Очередь на процессор длиннее, чем ядер: запросы стоят в очереди."})
    wa = host.get("cpu", {}).get("iowait", 0)
    if wa >= IOWAIT_WARN:
        out.append({"level": "warn", "title": f"Процессор {wa} % времени ждёт диск",
                    "text": "Узкое место — диски, а не процессор. Смотрите сессии с большими чтениями."})
    mem = host.get("mem", {})
    if mem and mem.get("available_pct", 100) < MEM_AVAIL_WARN:
        out.append({"level": "warn", "title": f"Доступно памяти {mem['available_pct']} %",
                    "text": f"Свободно {mem.get('available_mb')} МБ из {mem.get('total_mb')} МБ."})
    for dsk in host.get("disks", []):
        if dsk["util_pct"] >= DISK_UTIL_WARN or (dsk["await_ms"] >= DISK_AWAIT_WARN and dsk["r_s"] + dsk["w_s"] > 5):
            out.append({"level": "warn",
                        "title": f"Диск {dsk['device']}: загрузка {dsk['util_pct']:.0f} %, задержка {dsk['await_ms']:.0f} мс",
                        "text": f"Чтение {dsk['read_mb_s']:.1f} МБ/с, запись {dsk['write_mb_s']:.1f} МБ/с."})
    for d in dbs:
        if d["errors"]:
            out.append({"level": "warn", "title": f"{d['name']}: сбор с ошибками",
                        "text": "; ".join(d["errors"])})
        aas = d["metrics"].get("Average Active Sessions")
        if aas and d["cpu_count"] and aas > d["cpu_count"]:
            out.append({"level": "crit",
                        "title": f"{d['name']}: активных сессий в среднем {aas:.1f} при {d['cpu_count']} ядрах",
                        "text": "База перегружена: работы больше, чем процессор успевает."})
        for b in d["blocked"]:
            if b["seconds_in_wait"] >= BLOCK_WARN:
                out.append({"level": "crit",
                            "title": f"{d['name']}: сессия {b['sid']} ({b['username']}) {b['seconds_in_wait']} с "
                                     f"ждёт блокировку от сессии {b['blocking_session']}",
                            "text": f"{b['event']}. Пока блокировщик не закончит транзакцию, эта сессия стоит."})
        for a in d["active"]:
            if a["call_seconds"] >= LONG_CALL_WARN and a["wait_class"] != "Idle":
                mins = a["call_seconds"] // 60
                out.append({"level": "crit" if a["call_seconds"] >= LONG_CALL_CRIT else "warn",
                            "title": f"{d['name']}: запрос сессии {a['sid']} ({a['username']}, "
                                     f"{a['machine']}) идёт {mins} мин",
                            "text": f"{a['event'] or 'на процессоре'}; SQL {a['sql_id'] or '—'}: "
                                    f"{(a['sql_text'] or '')[:120]}"})
    order = {"crit": 0, "warn": 1}
    return sorted(out, key=lambda x: order.get(x["level"], 2))


def summary(d: dict) -> dict:
    os_ = d["os"]
    db = {x["name"]: x for x in d["databases"]}
    main = db.get("cloudbd", {})
    return {
        "load1": os_["load1"], "cores": os_["cores"],
        "cpu_busy": 100 - os_.get("cpu", {}).get("idle", 100),
        "iowait": os_.get("cpu", {}).get("iowait", 0),
        "mem_available_pct": os_.get("mem", {}).get("available_pct"),
        "disk_util_max": max((x["util_pct"] for x in os_.get("disks", [])), default=0),
        "cloudbd_active": main.get("active_count", 0),
        "cloudbd_sessions": main.get("sessions", 0),
        "cloudbd_blocked": len(main.get("blocked", [])),
        "cloudbd_longest_call": max((a["call_seconds"] for a in main.get("active", [])
                                     if a.get("wait_class") != "Idle"), default=0),
        "cloudbd_aas": main.get("metrics", {}).get("Average Active Sessions", 0),
        "cloudbd_phys_reads": main.get("metrics", {}).get("Physical Reads Per Sec", 0),
        "crit": sum(1 for f in d["findings"] if f["level"] == "crit"),
        "warn": sum(1 for f in d["findings"] if f["level"] == "warn"),
    }
