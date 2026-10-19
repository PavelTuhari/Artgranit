"""Лёгкий частый сборщик нагрузки для «серьёзного наблюдения».

Полный сбор вкладки «Нагрузка БД» (dbload.py) идёт ~12 секунд: top, iostat,
vmstat с паузами и новый sqlplus на каждый замер. Для замеров раз в 3–30
секунд это не годится, поэтому здесь иначе:

* одно постоянное SSH-соединение к серверу;
* хост — чтение /proc одной командой (stat, loadavg, meminfo, diskstats,
  net/dev), скорости считаются по РАЗНИЦЕ счётчиков между замерами — так
  точнее, чем любая утилита с паузой, и ничего не ждёт;
* Oracle — по ПОСТОЯННО ОТКРЫТОМУ sqlplus к каждой базе: запрос подаётся в
  уже запущенный процесс, без нового входа каждый раз. Скорости (чтения,
  выполнения, фиксации, процессор базы) — тоже по разнице v$sysstat.

Первый замер после запуска — только опорный: скоростей по нему ещё нет.
"""
from __future__ import annotations

import re
import time

SECTOR = 512
_HOST_CMD = ("echo '@@STAT'; head -1 /proc/stat; grep -E '^procs_(running|blocked)' /proc/stat; "
             "echo '@@LOAD'; cat /proc/loadavg; "
             "echo '@@MEM'; grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo; "
             "echo '@@DISK'; cat /proc/diskstats; "
             "echo '@@NET'; tail -n +3 /proc/net/dev; echo '@@END'")

_STATS = ("physical reads", "session logical reads", "execute count", "user commits",
          "redo size", "CPU used by this session")

_SQL_TICK = """select 'SYS@@' || name || '@@' || value from v$sysstat where name in (%s);
select 'CNT@@' || count(*) || '@@' ||
       sum(case when not (state = 'WAITING' and wait_class = 'Idle') and status = 'ACTIVE' then 1 else 0 end) || '@@' ||
       sum(case when status = 'ACTIVE' and state <> 'WAITING' then 1 else 0 end) || '@@' ||
       sum(case when blocking_session is not null then 1 else 0 end) || '@@' ||
       max(case when status = 'ACTIVE' and not (state = 'WAITING' and wait_class = 'Idle') then last_call_et end)
  from v$session where type = 'USER' and sid <> sys_context('userenv', 'sid');
select 'SES@@' || sid || '@@' || serial# || '@@' || username || '@@' || replace(machine, '@', '') || '@@' ||
       replace(substr(program, 1, 40), '@', '') || '@@' || sql_id || '@@' || replace(event, '@', '') || '@@' ||
       decode(state, 'WAITING', 0, 1) || '@@' || last_call_et || '@@' || blocking_session
  from (select * from v$session where type = 'USER' and status = 'ACTIVE'
          and not (state = 'WAITING' and wait_class = 'Idle') and sid <> sys_context('userenv', 'sid')
        order by last_call_et desc) where rownum <= 12;
prompt @@TICKEND
""" % ", ".join(f"'{n}'" for n in _STATS)


# ---------------------------------------------------------- разбор (чистые)

def _sections(raw: str) -> dict[str, list[str]]:
    out, key = {}, None
    for line in raw.splitlines():
        m = re.match(r"^@@(\w+)$", line.strip())
        if m:
            key = m.group(1)
            out[key] = []
        elif key:
            out[key].append(line)
    return out


def parse_host_raw(raw: str) -> dict:
    """Счётчики хоста как есть (накопительные) — скорости считает delta()."""
    sec = _sections(raw)
    stat = sec.get("STAT", [])
    cpu = [int(x) for x in stat[0].split()[1:9]] if stat else [0] * 8
    procs = {l.split()[0]: int(l.split()[1]) for l in stat[1:] if len(l.split()) == 2}
    la = (sec.get("LOAD") or ["0 0 0"])[0].split()
    mem = {}
    for l in sec.get("MEM", []):
        k, v = l.split(":")
        mem[k] = int(v.split()[0])          # кБ
    disks = {}
    for l in sec.get("DISK", []):
        f = l.split()
        # целые устройства sdX и nvmeXnY, без разделов и dm-*
        if len(f) >= 14 and re.match(r"^(sd[a-z]+|vd[a-z]+|nvme\d+n\d+)$", f[2]):
            disks[f[2]] = {"reads": int(f[3]), "rsect": int(f[5]), "rtime": int(f[6]),
                           "writes": int(f[7]), "wsect": int(f[9]), "wtime": int(f[10]),
                           "ioticks": int(f[12])}
    rx = tx = 0
    for l in sec.get("NET", []):
        name, _, rest = l.partition(":")
        if name.strip() in ("lo", "") or not rest:
            continue
        f = rest.split()
        rx += int(f[0])
        tx += int(f[8])
    return {"cpu": cpu, "procs_running": procs.get("procs_running", 0),
            "procs_blocked": procs.get("procs_blocked", 0),
            "load1": float(la[0]), "load5": float(la[1]), "mem": mem, "disks": disks,
            "net_rx": rx, "net_tx": tx}


def parse_db_raw(name: str, raw: str) -> dict:
    stats, cnt, sessions = {}, None, []
    for l in raw.splitlines():
        p = l.strip().split("@@")
        if p[0] == "SYS" and len(p) == 3:
            stats[p[1]] = float(p[2] or 0)
        elif p[0] == "CNT" and len(p) == 6:
            cnt = [int(float(x)) if x else 0 for x in p[1:]]
        elif p[0] == "SES" and len(p) == 11:
            sessions.append({"db": name, "sid": int(p[1]), "serial": int(p[2]), "username": p[3],
                             "machine": p[4], "program": p[5], "sql_id": p[6], "event": p[7],
                             "on_cpu": p[8] == "1", "call_seconds": int(float(p[9] or 0)),
                             "blocking_session": int(p[10]) if p[10] else None})
    cnt = cnt or [0, 0, 0, 0, 0]
    return {"db": name, "stats": stats, "sessions_total": cnt[0], "active": cnt[1], "on_cpu": cnt[2],
            "blocked": cnt[3], "longest_call": cnt[4], "sessions": sessions}


def delta(prev: dict, cur: dict, dt: float, cpu_count: int = 16) -> dict:
    """Из двух снимков счётчиков — проценты и скорости за интервал."""
    dt = max(dt, 0.001)
    c0, c1 = prev["cpu"], cur["cpu"]
    d = [max(b - a, 0) for a, b in zip(c0, c1)]
    total = sum(d) or 1
    user, nice, system, idle, iowait, irq, softirq, steal = d
    mem = cur["mem"]
    mt, ma = mem.get("MemTotal", 1), mem.get("MemAvailable", 0)
    disks = []
    for dev, x in cur["disks"].items():
        p = prev["disks"].get(dev)
        if not p:
            continue
        ops_r, ops_w = x["reads"] - p["reads"], x["writes"] - p["writes"]
        ios = ops_r + ops_w
        disks.append({
            "device": dev,
            "util_pct": round(min((x["ioticks"] - p["ioticks"]) / (dt * 1000) * 100, 100), 1),
            "r_s": round(ops_r / dt, 1), "w_s": round(ops_w / dt, 1),
            "read_mb_s": round((x["rsect"] - p["rsect"]) * SECTOR / dt / 1048576, 2),
            "write_mb_s": round((x["wsect"] - p["wsect"]) * SECTOR / dt / 1048576, 2),
            "await_ms": round(((x["rtime"] - p["rtime"]) + (x["wtime"] - p["wtime"])) / ios, 1) if ios else 0.0,
        })
    return {
        "cpu_user": round((user + nice) * 100 / total, 1),
        "cpu_system": round((system + irq + softirq) * 100 / total, 1),
        "cpu_iowait": round(iowait * 100 / total, 1),
        "cpu_idle": round(idle * 100 / total, 1),
        "cpu_steal": round(steal * 100 / total, 1),
        "load1": cur["load1"], "load5": cur["load5"],
        "procs_running": cur["procs_running"], "procs_blocked": cur["procs_blocked"],
        "mem_used_pct": round((mt - ma) * 100 / mt, 1),
        "mem_available_mb": round(ma / 1024),
        "swap_used_mb": round((mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)) / 1024),
        "net_rx_kbs": round(max(cur["net_rx"] - prev["net_rx"], 0) / dt / 1024, 1),
        "net_tx_kbs": round(max(cur["net_tx"] - prev["net_tx"], 0) / dt / 1024, 1),
        "disks": disks,
    }


def db_delta(prev: dict, cur: dict, dt: float, cpu_count: int = 16) -> dict:
    dt = max(dt, 0.001)
    rate = lambda k: round(max(cur["stats"].get(k, 0) - prev["stats"].get(k, 0), 0) / dt, 1)
    cpu_cs = max(cur["stats"].get("CPU used by this session", 0)
                 - prev["stats"].get("CPU used by this session", 0), 0)
    return {"db": cur["db"], "sessions": cur["sessions_total"], "active": cur["active"],
            "on_cpu": cur["on_cpu"], "blocked": cur["blocked"], "longest_call": cur["longest_call"],
            # процессор базы в процентах ВСЕГО сервера: 100 % = все ядра заняты базой
            "db_cpu_pct": round(min(cpu_cs / 100 / dt / max(cpu_count, 1) * 100, 100), 1),
            "phys_reads_s": rate("physical reads"), "logical_reads_s": rate("session logical reads"),
            "executions_s": rate("execute count"), "commits_s": rate("user commits"),
            "redo_kbs": round(rate("redo size") / 1024, 1)}


# ------------------------------------------------------------ живой сборщик

class SqlplusSession:
    """Постоянно открытый sqlplus к одной базе внутри SSH-соединения."""

    def __init__(self, transport, db: str):
        self.db = db
        self.ch = transport.open_session()
        self.ch.settimeout(60)
        self.ch.exec_command(f"su - oracle -c 'export ORACLE_SID={db}; sqlplus -s / as sysdba'")
        self._send("set heading off feedback off pagesize 0 linesize 1000 trimspool on verify off echo off\n"
                   "prompt @@READY\n")
        self._read_until("@@READY")

    def _send(self, text: str) -> None:
        self.ch.sendall(text.encode("utf-8"))

    def _read_until(self, marker: str, timeout: float = 60) -> str:
        buf, end = b"", time.monotonic() + timeout
        while marker.encode() not in buf:
            if time.monotonic() > end:
                raise TimeoutError(f"{self.db}: sqlplus не ответил за {timeout} с")
            if self.ch.exit_status_ready() and not self.ch.recv_ready():
                raise RuntimeError(f"{self.db}: sqlplus завершился")
            chunk = self.ch.recv(65536)
            if not chunk:
                raise RuntimeError(f"{self.db}: соединение закрыто")
            buf += chunk
        return buf.decode("utf-8", "replace").split(marker)[0]

    def tick(self) -> str:
        self._send(_SQL_TICK)
        return self._read_until("@@TICKEND")

    def close(self) -> None:
        try:
            self._send("exit\n")
            self.ch.close()
        except Exception:  # noqa: BLE001
            pass


class Sampler:
    """Одно SSH-соединение и по sqlplus на базу; переподключается при сбое."""

    def __init__(self, databases=("cloudbd", "clouddev")):
        self.databases = databases
        self.client = None
        self.sql: dict[str, SqlplusSession] = {}
        self.prev = None
        self.prev_db: dict[str, dict] = {}
        self.prev_t = None
        self.cpu_count = 16

    def connect(self) -> None:
        import paramiko
        from modules.netmon import frontoffice
        pw = frontoffice.keychain_root()
        if not pw:
            raise RuntimeError("нет пароля root сервера баз данных в Keychain")
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(frontoffice.DB_HOST, username="root", password=pw, timeout=20,
                            look_for_keys=False, allow_agent=False)
        self.client.get_transport().set_keepalive(15)
        self.sql = {db: SqlplusSession(self.client.get_transport(), db) for db in self.databases}
        _, o, _ = self.client.exec_command("nproc", timeout=20)
        self.cpu_count = int(o.read().decode().strip() or 16)
        self.prev = None

    def close(self) -> None:
        for s in self.sql.values():
            s.close()
        if self.client:
            self.client.close()
        self.client, self.sql = None, {}

    def sample(self) -> dict | None:
        """Один замер. None — первый, опорный: скоростей по нему ещё нет."""
        if not self.client or not self.client.get_transport() or not self.client.get_transport().is_active():
            self.close()
            self.connect()
        t0 = time.monotonic()
        now = time.time()
        _, o, _ = self.client.exec_command(_HOST_CMD, timeout=30)
        host = parse_host_raw(o.read().decode("utf-8", "replace"))
        dbs = {db: parse_db_raw(db, s.tick()) for db, s in self.sql.items()}
        collect_ms = round((time.monotonic() - t0) * 1000)
        prev, prev_db, prev_t = self.prev, self.prev_db, self.prev_t
        self.prev, self.prev_db, self.prev_t = host, dbs, now
        if prev is None:
            return None
        dt = now - prev_t
        h = delta(prev, host, dt, self.cpu_count)
        return {"ts": now, "interval": round(dt, 2), "collect_ms": collect_ms, **h,
                "dbs": [db_delta(prev_db[d], dbs[d], dt, self.cpu_count) for d in dbs if d in prev_db],
                "sessions": [s for d in dbs.values() for s in d["sessions"]]}
