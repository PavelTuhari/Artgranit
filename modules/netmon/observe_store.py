"""Локальный кэш «серьёзного наблюдения» за сервером баз данных (SQLite).

ЭТО КЭШ, А НЕ ХРАНИЛИЩЕ ДАННЫХ. CLAUDE.md запрещает SQLite как основное
хранилище бизнес-данных — здесь их нет: только временной ряд измерений
нагрузки на машине администратора, который сам себя чистит (хранится
`retention_days` дней). Потеря файла ничего не ломает — наблюдение просто
начнётся заново. Владелец явно попросил SQLite (08.10.2026): запись каждые
несколько секунд в Oracle, которая сама стоит на наблюдаемом сервере, сама
давала бы нагрузку и искажала бы картину.

Файл — вне репозитория: ~/.netmon/observe.sqlite (NETMON_OBSERVE_DB).

Схема — по сущностям, а не один JSON на замер:
  samples        — замер хоста: процессор, нагрузка, память, сеть;
  disk_samples   — по диску на замер;
  db_samples     — по базе на замер: сессии, блокировки, скорости из v$sysstat;
  session_samples — работающие сессии на момент замера (кто вызвал пик);
  settings       — интервал и прочие настройки (сохраняются между запусками);
  control        — желаемое состояние и пульс фонового процесса.
"""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("NETMON_OBSERVE_DB", Path.home() / ".netmon" / "observe.sqlite"))

DEFAULTS = {"interval_sec": 30, "max_hours": 8, "retention_days": 7}
LIMITS = {"interval_sec": (3, 300), "max_hours": (1, 72), "retention_days": (1, 90)}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL NOT NULL);
CREATE TABLE IF NOT EXISTS control (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  desired TEXT NOT NULL DEFAULT 'stopped' CHECK (desired IN ('running','stopped')),
  pid INTEGER, started_at REAL, heartbeat REAL, last_error TEXT, samples INTEGER DEFAULT 0
);
INSERT OR IGNORE INTO control (id) VALUES (1);
CREATE TABLE IF NOT EXISTS samples (
  ts REAL PRIMARY KEY, interval REAL,
  cpu_user REAL, cpu_system REAL, cpu_iowait REAL, cpu_idle REAL, cpu_steal REAL,
  load1 REAL, load5 REAL, procs_running INTEGER, procs_blocked INTEGER,
  mem_used_pct REAL, mem_available_mb REAL, swap_used_mb REAL,
  net_rx_kbs REAL, net_tx_kbs REAL, collect_ms REAL
);
CREATE TABLE IF NOT EXISTS disk_samples (
  ts REAL NOT NULL REFERENCES samples(ts) ON DELETE CASCADE, device TEXT NOT NULL,
  util_pct REAL, r_s REAL, w_s REAL, read_mb_s REAL, write_mb_s REAL, await_ms REAL,
  PRIMARY KEY (ts, device)
);
CREATE TABLE IF NOT EXISTS db_samples (
  ts REAL NOT NULL REFERENCES samples(ts) ON DELETE CASCADE, db TEXT NOT NULL,
  sessions INTEGER, active INTEGER, on_cpu INTEGER, blocked INTEGER, longest_call INTEGER,
  db_cpu_pct REAL, phys_reads_s REAL, logical_reads_s REAL, executions_s REAL,
  commits_s REAL, redo_kbs REAL,
  PRIMARY KEY (ts, db)
);
CREATE TABLE IF NOT EXISTS session_samples (
  ts REAL NOT NULL REFERENCES samples(ts) ON DELETE CASCADE, db TEXT NOT NULL,
  sid INTEGER, serial INTEGER, username TEXT, machine TEXT, program TEXT, sql_id TEXT,
  event TEXT, on_cpu INTEGER, call_seconds INTEGER, blocking_session INTEGER
);
CREATE INDEX IF NOT EXISTS ix_session_samples_ts ON session_samples (ts);
"""


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    try:
        con.execute("PRAGMA journal_mode=WAL")      # страница читает, пока процесс пишет
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(_SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


# ------------------------------------------------------------------ настройки

def get_settings() -> dict:
    with connect() as con:
        rows = dict(con.execute("SELECT key, value FROM settings").fetchall())
    out = {}
    for k, d in DEFAULTS.items():
        v = rows.get(k, d)
        out[k] = int(v) if float(v).is_integer() else float(v)
    return out


def save_settings(values: dict) -> dict:
    clean = {}
    for k, v in values.items():
        if k not in DEFAULTS:
            continue
        try:
            n = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"{k}: нужно число")
        lo, hi = LIMITS[k]
        if not lo <= n <= hi:
            raise ValueError(f"{k}: от {lo} до {hi}")
        clean[k] = n
    with connect() as con:
        con.executemany("INSERT INTO settings (key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value", clean.items())
    return get_settings()


# ---------------------------------------------------------------- управление

def control() -> dict:
    with connect() as con:
        r = con.execute("SELECT desired, pid, started_at, heartbeat, last_error, samples "
                        "FROM control WHERE id = 1").fetchone()
    return {"desired": r[0], "pid": r[1], "started_at": r[2], "heartbeat": r[3],
            "last_error": r[4], "samples": r[5] or 0}


def set_control(**kw) -> None:
    if not kw:
        return
    cols = ", ".join(f"{k} = ?" for k in kw)
    with connect() as con:
        con.execute(f"UPDATE control SET {cols} WHERE id = 1", list(kw.values()))


# -------------------------------------------------------------------- запись

def save_sample(s: dict) -> None:
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [s["ts"], s["interval"], s["cpu_user"], s["cpu_system"], s["cpu_iowait"],
                     s["cpu_idle"], s["cpu_steal"], s["load1"], s["load5"], s["procs_running"],
                     s["procs_blocked"], s["mem_used_pct"], s["mem_available_mb"], s["swap_used_mb"],
                     s["net_rx_kbs"], s["net_tx_kbs"], s["collect_ms"]])
        con.executemany("INSERT OR REPLACE INTO disk_samples VALUES (?,?,?,?,?,?,?,?)",
                        [[s["ts"], d["device"], d["util_pct"], d["r_s"], d["w_s"], d["read_mb_s"],
                          d["write_mb_s"], d["await_ms"]] for d in s["disks"]])
        con.executemany("INSERT OR REPLACE INTO db_samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [[s["ts"], d["db"], d["sessions"], d["active"], d["on_cpu"], d["blocked"],
                          d["longest_call"], d["db_cpu_pct"], d["phys_reads_s"], d["logical_reads_s"],
                          d["executions_s"], d["commits_s"], d["redo_kbs"]] for d in s["dbs"]])
        con.executemany("INSERT INTO session_samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [[s["ts"], x["db"], x["sid"], x["serial"], x["username"], x["machine"],
                          x["program"], x["sql_id"], x["event"], int(x["on_cpu"]), x["call_seconds"],
                          x["blocking_session"]] for x in s["sessions"]])
        con.execute("UPDATE control SET heartbeat = ?, samples = samples + 1 WHERE id = 1", [time.time()])


def prune(retention_days: float) -> int:
    cutoff = time.time() - retention_days * 86400
    with connect() as con:
        n = con.execute("DELETE FROM samples WHERE ts < ?", [cutoff]).rowcount
        con.execute("DELETE FROM session_samples WHERE ts < ?", [cutoff])
    return n


# ------------------------------------------------------------------- чтение

def series(minutes: float, points: int = 600) -> dict:
    """Ряды для графиков за последние `minutes`, не больше `points` точек.

    Длинное окно сжимается в корзины: среднее для процентов и скоростей,
    МАКСИМУМ для сессий и блокировок — иначе короткий пик растворится в
    среднем и на графике его не будет видно, а ради пиков наблюдение и
    включают.
    """
    since = time.time() - minutes * 60
    bucket = max(minutes * 60 / points, 0.001)
    with connect() as con:
        host = con.execute(f"""
            SELECT CAST(ts / {bucket} AS INTEGER) b, MAX(ts),
                   AVG(cpu_user), AVG(cpu_system), AVG(cpu_iowait), AVG(100 - cpu_idle),
                   AVG(load1), MAX(load1), AVG(mem_used_pct), AVG(swap_used_mb),
                   AVG(net_rx_kbs), AVG(net_tx_kbs), MAX(procs_blocked), COUNT(*)
              FROM samples WHERE ts >= ? GROUP BY b ORDER BY b""", [since]).fetchall()
        disks = con.execute(f"""
            SELECT device, CAST(ts / {bucket} AS INTEGER) b, MAX(ts), AVG(util_pct), MAX(util_pct),
                   AVG(read_mb_s), AVG(write_mb_s), AVG(await_ms)
              FROM disk_samples WHERE ts >= ? GROUP BY device, b ORDER BY device, b""", [since]).fetchall()
        dbs = con.execute(f"""
            SELECT db, CAST(ts / {bucket} AS INTEGER) b, MAX(ts), MAX(active), MAX(on_cpu), MAX(blocked),
                   MAX(longest_call), AVG(db_cpu_pct), AVG(phys_reads_s), AVG(logical_reads_s),
                   AVG(executions_s), AVG(commits_s), AVG(redo_kbs), MAX(sessions)
              FROM db_samples WHERE ts >= ? GROUP BY db, b ORDER BY db, b""", [since]).fetchall()
    r1 = lambda v: None if v is None else round(v, 1)
    out = {"bucket_sec": round(bucket, 1), "minutes": minutes,
           "host": {"t": [], "cpu_user": [], "cpu_system": [], "cpu_iowait": [], "cpu_busy": [],
                    "load1": [], "load1_max": [], "mem_used_pct": [], "swap_used_mb": [],
                    "net_rx_kbs": [], "net_tx_kbs": [], "procs_blocked": []},
           "disks": {}, "dbs": {}}
    h = out["host"]
    for row in host:
        h["t"].append(row[1])
        for i, k in enumerate(["cpu_user", "cpu_system", "cpu_iowait", "cpu_busy", "load1", "load1_max",
                               "mem_used_pct", "swap_used_mb", "net_rx_kbs", "net_tx_kbs",
                               "procs_blocked"], start=2):
            h[k].append(r1(row[i]))
    for dev, _, t, u, umax, rmb, wmb, aw in disks:
        d = out["disks"].setdefault(dev, {"t": [], "util_pct": [], "util_max": [], "read_mb_s": [],
                                          "write_mb_s": [], "await_ms": []})
        for k, v in zip(d, (t, u, umax, rmb, wmb, aw)):
            d[k].append(r1(v) if k != "t" else v)
    for db, _, t, act, cpu, blk, lng, dcpu, pr, lr, ex, cm, redo, sess in dbs:
        d = out["dbs"].setdefault(db, {"t": [], "active": [], "on_cpu": [], "blocked": [], "longest_call": [],
                                       "db_cpu_pct": [], "phys_reads_s": [], "logical_reads_s": [],
                                       "executions_s": [], "commits_s": [], "redo_kbs": [], "sessions": []})
        for k, v in zip(d, (t, act, cpu, blk, lng, dcpu, pr, lr, ex, cm, redo, sess)):
            d[k].append(v if k == "t" else r1(v))
    return out


def sessions_at(ts: float, window: float = 0) -> list[dict]:
    """Кто работал в момент `ts` (ближайший замер) — для щелчка по пику графика."""
    with connect() as con:
        near = con.execute("SELECT ts FROM samples ORDER BY ABS(ts - ?) LIMIT 1", [ts]).fetchone()
        if not near:
            return []
        rows = con.execute("SELECT ts, db, sid, serial, username, machine, program, sql_id, event, "
                           "on_cpu, call_seconds, blocking_session FROM session_samples "
                           "WHERE ts BETWEEN ? AND ? ORDER BY call_seconds DESC",
                           [near[0] - window, near[0] + window]).fetchall()
    keys = ["ts", "db", "sid", "serial", "username", "machine", "program", "sql_id", "event",
            "on_cpu", "call_seconds", "blocking_session"]
    return [dict(zip(keys, r)) for r in rows]


def stats() -> dict:
    with connect() as con:
        n, first, last = con.execute("SELECT COUNT(*), MIN(ts), MAX(ts) FROM samples").fetchone()
    size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    return {"samples": n, "first": first, "last": last, "size_mb": round(size / 1048576, 2),
            "path": str(DB_PATH)}
