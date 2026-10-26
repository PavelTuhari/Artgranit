"""SQL справочника клиентов (NMON_CLIENT) — только здесь.

Справочник закрепляет тип за клиентом: магазинник, прямой бэк, веб или
наше. Без записи тип определяется по текущим подключениям
(clients_rules.py) — запись нужна для тех, кто сейчас не подключён.
"""
from __future__ import annotations

from models.database import DatabaseModel

from modules.netmon.clients_rules import KINDS


def _cursor(db):
    cur = db.connection.cursor()
    # ADB по умолчанию делает DML параллельно — см. fs_store.py
    cur.execute("ALTER SESSION DISABLE PARALLEL DML")
    return cur


def registry() -> dict[str, dict]:
    with DatabaseModel() as db:
        cur = _cursor(db)
        cur.execute("""SELECT CLIENT_KEY, KIND, TITLE, NOTE,
                              TO_CHAR(UPDATED_AT, 'YYYY-MM-DD HH24:MI'), UPDATED_BY
                         FROM NMON_CLIENT""")
        return {r[0]: {"kind": r[1], "title": r[2], "note": r[3], "updated_at": r[4], "updated_by": r[5]}
                for r in cur.fetchall()}


def save(client_key: str, kind: str | None, title: str | None, note: str | None, by: str) -> None:
    """kind=None — снять закрепление: тип снова определяется по подключениям."""
    key = (client_key or "").strip().upper()[:60]
    if not key:
        raise ValueError("не указан клиент")
    with DatabaseModel() as db:
        cur = _cursor(db)
        if not kind:
            cur.execute("DELETE FROM NMON_CLIENT WHERE CLIENT_KEY = :k", k=key)
        else:
            if kind not in KINDS:
                raise ValueError(f"тип клиента: {', '.join(KINDS)}")
            cur.execute("""MERGE INTO NMON_CLIENT c USING (SELECT :k k FROM DUAL) s ON (c.CLIENT_KEY = s.k)
                           WHEN MATCHED THEN UPDATE SET KIND = :kind, TITLE = :title, NOTE = :note,
                                UPDATED_AT = SYSTIMESTAMP, UPDATED_BY = :by
                           WHEN NOT MATCHED THEN INSERT (CLIENT_KEY, KIND, TITLE, NOTE, UPDATED_BY)
                                VALUES (:k, :kind, :title, :note, :by)""",
                        k=key, kind=kind, title=(title or "").strip()[:200] or None,
                        note=(note or "").strip()[:500] or None, by=(by or "system")[:60])
        db.connection.commit()
