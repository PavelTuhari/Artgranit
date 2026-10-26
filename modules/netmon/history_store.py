"""SQL истории подключений (NMON_LOGON_DAY, NMON_STAFF_EVENT, NMON_STAFF_ID,
NMON_HIST_SYNC) — только здесь.

Перенос повторяемый: строки сливаются MERGE по ключу, повторный запуск не
дублирует. Имена привязок не :by и не :rollback — ORA-01745 (см. TBControl).
"""
from __future__ import annotations

from datetime import datetime

from models.database import DatabaseModel

_ISO = "YYYY-MM-DD\"T\"HH24:MI:SS"


def _since(days: int) -> datetime:
    """Начало периода по местному времени. В ADB SYSDATE — UTC, а даты
    событий записаны по Кишинёву, поэтому граница считается здесь."""
    from datetime import timedelta
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=max(0, days - 1))


def _cursor(db):
    cur = db.connection.cursor()
    cur.execute("ALTER SESSION DISABLE PARALLEL DML")   # ADB, см. fs_store.py
    return cur


def _rows(cur) -> list[dict]:
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---------------------------------------------------------------- состояние

def sync_state() -> dict[str, dict]:
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute(f"""SELECT SOURCE, LAST_AT, LAST_RUN, ROWS_IN, MESSAGE,
                               ROUND((SYSDATE - LAST_RUN) * 1440) AGE_MIN FROM NMON_HIST_SYNC""")
        return {r["source"]: r for r in _rows(cur)}


def save_sync(source: str, last_at: datetime | None, rows: int, message: str | None = None) -> None:
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute("""MERGE INTO NMON_HIST_SYNC s USING (SELECT :src src FROM DUAL) x ON (s.SOURCE = x.src)
                       WHEN MATCHED THEN UPDATE SET LAST_AT = NVL(:last_at, LAST_AT), LAST_RUN = SYSDATE,
                            ROWS_IN = :n, MESSAGE = :msg
                       WHEN NOT MATCHED THEN INSERT (SOURCE, LAST_AT, LAST_RUN, ROWS_IN, MESSAGE)
                            VALUES (:src, :last_at, SYSDATE, :n, :msg)""",
                    src=source, last_at=last_at, n=rows, msg=(message or None) and message[:1000])
        db.connection.commit()


# ------------------------------------------------------------- справочник

def staff_registry() -> dict[tuple[str, str], dict]:
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute("SELECT KIND, VALUE, STAFF, PERSON, NOTE, ORIGIN FROM NMON_STAFF_ID")
        return {(r["kind"], r["value"]): r for r in _rows(cur)}


def save_ident(kind: str, value: str, staff: int, person: str | None, note: str | None,
               origin: str, usr: str, keep_manual: bool = False) -> None:
    """keep_manual — для автоматической записи: ручную отметку не перетирать."""
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute(f"""MERGE INTO NMON_STAFF_ID s USING (SELECT :kind kind, :val val FROM DUAL) x
                          ON (s.KIND = x.kind AND s.VALUE = x.val)
                        WHEN MATCHED THEN UPDATE SET STAFF = :staff, PERSON = NVL(:person, PERSON),
                             NOTE = NVL(:note, NOTE), ORIGIN = :origin, UPDATED_AT = SYSTIMESTAMP,
                             UPDATED_BY = :usr
                             {"WHERE s.ORIGIN <> 'manual'" if keep_manual else ""}
                        WHEN NOT MATCHED THEN INSERT (KIND, VALUE, STAFF, PERSON, NOTE, ORIGIN, UPDATED_BY)
                             VALUES (:kind, :val, :staff, :person, :note, :origin, :usr)""",
                    kind=kind, val=value[:255], staff=int(staff), person=(person or None) and person[:100],
                    note=(note or None) and note[:300], origin=origin, usr=(usr or "system")[:60])
        db.connection.commit()


# ---------------------------------------------------------------- перенос

def upsert_logon_days(rows: list[dict]) -> int:
    if not rows:
        return 0
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.executemany("""MERGE INTO NMON_LOGON_DAY t
            USING (SELECT :db db, :sch sch, :host host, :osu osu, :day day FROM DUAL) x
               ON (t.DB = x.db AND t.SCHEMA_NAME = x.sch AND t.USERHOST = x.host AND t.OS_USER = x.osu AND t.DAY = x.day)
            WHEN MATCHED THEN UPDATE SET LOGONS = :logons, FAILED = :failed, FIRST_AT = :first_at,
                 LAST_AT = :last_at, CLIENT_KEY = :client
            WHEN NOT MATCHED THEN INSERT (DB, SCHEMA_NAME, USERHOST, OS_USER, DAY, CLIENT_KEY, LOGONS, FAILED,
                 FIRST_AT, LAST_AT)
                 VALUES (:db, :sch, :host, :osu, :day, :client, :logons, :failed, :first_at, :last_at)""",
            [{"db": r["db"], "sch": r["schema"], "host": r["userhost"][:255], "osu": r["os_user"][:255],
              "day": r["day"], "client": r["client"], "logons": r["logons"], "failed": r["failed"],
              "first_at": r["first_at"], "last_at": r["last_at"]} for r in rows])
        db.connection.commit()
    return len(rows)


def upsert_events(rows: list[dict]) -> int:
    if not rows:
        return 0
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.executemany("""MERGE INTO NMON_STAFF_EVENT t
            USING (SELECT :src src, :tgt tgt, :ref ref FROM DUAL) x
               ON (t.SOURCE = x.src AND t.TARGET = x.tgt AND t.REF = x.ref)
            WHEN MATCHED THEN UPDATE SET END_AT = :end_at, OFF_HOURS = :off, AUTO = :auto, METHOD = :method,
                 DETAIL = :detail
            WHEN NOT MATCHED THEN INSERT (SOURCE, TARGET, REF, ACCOUNT, FROM_HOST, OS_USER, START_AT, END_AT,
                 RESULT, METHOD, DETAIL, OFF_HOURS, AUTO)
                 VALUES (:src, :tgt, :ref, :acc, :host, :osu, :start_at, :end_at, :res, :method, :detail,
                         :off, :auto)""",
            [{"src": e["source"], "tgt": e["target"], "ref": e["ref"][:160], "acc": (e.get("account") or "")[:128],
              "host": (e.get("from_host") or "")[:255], "osu": (e.get("os_user") or "")[:255] or None,
              "start_at": e["start_at"], "end_at": e.get("end_at"), "res": e["result"],
              "method": (e.get("method") or "")[:80] or None, "detail": (e.get("detail") or "")[:400] or None,
              "off": int(e.get("off_hours", 0)), "auto": int(e.get("auto", 0))} for e in rows])
        db.connection.commit()
    return len(rows)


# ------------------------------------------------------------------ чтение

def staff_events(days: int) -> list[dict]:
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute("""SELECT SOURCE, TARGET, ACCOUNT, FROM_HOST, OS_USER, START_AT, END_AT, RESULT, METHOD,
                              DETAIL, OFF_HOURS, AUTO
                         FROM NMON_STAFF_EVENT
                        WHERE START_AT >= :since
                        ORDER BY START_AT DESC""", since=_since(days))
        return _rows(cur)


def clients_summary(days: int) -> dict[str, dict]:
    """По клиенту за период: дней с входами, входов, компьютеров, последний вход."""
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute(f"""SELECT CLIENT_KEY, COUNT(DISTINCT DAY) DAYS_ACTIVE, SUM(LOGONS) LOGONS,
                               SUM(FAILED) FAILED, COUNT(DISTINCT USERHOST) HOSTS,
                               TO_CHAR(MAX(LAST_AT), '{_ISO}') LAST_AT
                          FROM NMON_LOGON_DAY WHERE DAY >= :since
                         GROUP BY CLIENT_KEY""", since=_since(days))
        return {r["client_key"]: r for r in _rows(cur)}


def client_days(client: str, days: int) -> list[dict]:
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute(f"""SELECT TO_CHAR(DAY, 'YYYY-MM-DD') DAY, DB, SCHEMA_NAME, USERHOST, OS_USER,
                               LOGONS, FAILED, TO_CHAR(FIRST_AT, '{_ISO}') FIRST_AT,
                               TO_CHAR(LAST_AT, '{_ISO}') LAST_AT
                          FROM NMON_LOGON_DAY
                         WHERE CLIENT_KEY = :c AND DAY >= :since
                         ORDER BY DAY DESC, LOGONS DESC""", c=client.upper(), since=_since(days))
        return _rows(cur)
