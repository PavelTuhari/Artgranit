"""SQL раздела «Файловые ресурсы»: политика, сотрудники, журнал (NMON_FS_*).

Политика доступа — в базе, а не в коде: роли, ресурсы, какая роль куда
входит. fileshare.py рисует из неё конфигурацию Samba.

Курсоры — с выключенным параллельным DML: Autonomous Database по умолчанию
выполняет DML параллельно, и на таблицах с внешними ключами это давало
ORA-12860 (см. modules/vpnguide/store.py).
"""
from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo

from models.database import DatabaseModel

LOCAL_TZ = ZoneInfo("Europe/Chisinau")
_ISO = "YYYY-MM-DD\"T\"HH24:MI:SS"


def _cursor(db):
    cur = db.connection.cursor()
    cur.execute("ALTER SESSION DISABLE PARALLEL DML")
    return cur


def _local(iso_utc: str | None) -> str | None:
    if not iso_utc:
        return None
    from datetime import datetime
    dt = datetime.strptime(iso_utc, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ).strftime("%d.%m.%Y %H:%M")


# ------------------------------------------------------------------ политика

def load_policy() -> dict:
    """{'roles': {code: {...}}, 'shares': [{name, drive, title, roles: [...]}]}"""
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute("SELECT CODE, TITLE, UNIX_GROUP FROM NMON_FS_ROLES ORDER BY SORT_ORDER")
        roles = {c: {"code": c, "title": t, "group": g} for c, t, g in cur.fetchall()}
        cur.execute("SELECT s.NAME, s.DRIVE, s.TITLE, p.ROLE_CODE FROM NMON_FS_SHARES s "
                    "LEFT JOIN NMON_FS_POLICY p ON p.SHARE_NAME = s.NAME "
                    "LEFT JOIN NMON_FS_ROLES r ON r.CODE = p.ROLE_CODE "
                    "ORDER BY s.SORT_ORDER, r.SORT_ORDER")
        shares: dict[str, dict] = {}
        for name, drive, title, role in cur.fetchall():
            sh = shares.setdefault(name, {"name": name, "drive": drive.strip(), "title": title, "roles": []})
            if role:
                sh["roles"].append(role)
    if not roles or not shares:
        raise RuntimeError("политика доступа в базе пуста: запустите netmon_deploy.py")
    return {"roles": roles, "shares": list(shares.values())}


# ----------------------------------------------------------------- сотрудники

def list_people() -> list[dict]:
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute(f"SELECT ID, EMAIL, LOGIN, FULL_NAME, ROLE_CODE, STATUS, "
                    f"TO_CHAR(SYS_EXTRACT_UTC(CREATED_AT), '{_ISO}'), CREATED_BY, NOTE "
                    "FROM NMON_FS_PEOPLE ORDER BY STATUS, EMAIL")
        rows = cur.fetchall()
    return [{"id": r[0], "email": r[1], "login": r[2], "full_name": r[3], "role": r[4],
             "status": r[5], "created": _local(r[6]), "created_by": r[7], "note": r[8]}
            for r in rows]


def get_person(login: str) -> dict | None:
    return next((p for p in list_people() if p["login"] == login), None)


def add_person(email: str, login: str, full_name: str, role: str, by: str) -> int:
    with DatabaseModel() as db:
        cur = _cursor(db)
        nid = cur.var(int)
        cur.execute("INSERT INTO NMON_FS_PEOPLE (EMAIL, LOGIN, FULL_NAME, ROLE_CODE, CREATED_BY) "
                    "VALUES (:em, :lg, :fn, :rl, :usr) RETURNING ID INTO :nid",
                    em=email, lg=login, fn=(full_name or "")[:200] or None, rl=role,
                    usr=(by or "system")[:100], nid=nid)
        db.connection.commit()
        return nid.getvalue()[0]


def update_person(login: str, *, role: str | None = None, status: str | None = None) -> None:
    sets, binds = ["UPDATED_AT = SYSTIMESTAMP"], {"lg": login}
    if role:
        sets.append("ROLE_CODE = :rl")
        binds["rl"] = role
    if status:
        sets.append("STATUS = :st")
        binds["st"] = status
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute(f"UPDATE NMON_FS_PEOPLE SET {', '.join(sets)} WHERE LOGIN = :lg", **binds)
        if cur.rowcount != 1:
            raise ValueError(f"сотрудника с учёткой {login} в учёте нет")
        db.connection.commit()


def delete_person(login: str) -> None:
    """Только откат неудачного создания: учётная запись в базе есть, на сервере нет."""
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute("DELETE FROM NMON_FS_PEOPLE WHERE LOGIN = :lg", lg=login)
        db.connection.commit()


# -------------------------------------------------------------------- журнал

def log(actor: str, action: str, target: str = "", details: str = "") -> None:
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute("INSERT INTO NMON_FS_LOG (ACTOR, ACTION, TARGET, DETAILS) "
                    "VALUES (:a, :ac, :t, :d)",
                    a=(actor or "system")[:100], ac=action[:30], t=(target or "")[:100],
                    d=(details or "")[:2000])
        db.connection.commit()


def recent_log(limit: int = 40) -> list[dict]:
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute(f"SELECT * FROM (SELECT TO_CHAR(SYS_EXTRACT_UTC(AT), '{_ISO}'), ACTOR, ACTION, "
                    "TARGET, DETAILS FROM NMON_FS_LOG ORDER BY ID DESC) WHERE ROWNUM <= :n",
                    n=int(limit))
        rows = cur.fetchall()
    return [{"at": _local(r[0]), "actor": r[1], "action": r[2], "target": r[3], "details": r[4]}
            for r in rows]
