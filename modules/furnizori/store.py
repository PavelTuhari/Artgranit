"""Хранилище модуля: весь SQL к таблицам FRZ_* — только здесь."""
from models.database import DatabaseModel


def _rows(r):
    return r.get("data") if isinstance(r, dict) else r


def counters() -> dict:
    with DatabaseModel() as db:
        r = db.execute_query(
            "SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME LIKE 'FRZ\\_%' ESCAPE '\\'"
        )
        rows = _rows(r) or [[0]]
    return {"tables": rows[0][0]}
