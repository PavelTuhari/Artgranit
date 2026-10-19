"""Хранилище модуля: весь SQL к таблицам FRZ_* — только здесь.

BLOB-и читаем и пишем через сырой курсор (`db.connection`), а не через
`execute_query`: тот декодирует LOB в строку, и .eml/.xlsx после этого
перестают открываться.
"""
import hashlib

from models.database import DatabaseModel


def _rows(r):
    return (r.get("data") if isinstance(r, dict) else r) or []


def _dicts(r) -> list[dict]:
    cols = [c.upper() for c in (r.get("columns") or [])] if isinstance(r, dict) else []
    return [dict(zip(cols, row)) for row in _rows(r)]


# ------------------------------------------------------------------ письма

LETTER_COLS = ("LETTER_ID, SRC_CODE, COD_ORG, FURNIZOR, SUBIECT, TIP, N_POZITII, "
               "STATUS, SENT_TO, SENT_AT, ANSWER_AT, NOTES, CREATED_AT")


def list_letters(status: str | None = None) -> list[dict]:
    """Письма с числом вложений. Свежие — сверху."""
    sql = f"""SELECT {LETTER_COLS},
                     (SELECT COUNT(*) FROM FRZ_LETTER_FILE f WHERE f.LETTER_ID = l.LETTER_ID) N_FILES
                FROM FRZ_LETTER l"""
    params = {}
    if status:
        sql += " WHERE l.STATUS = :st"
        params["st"] = status
    sql += " ORDER BY l.CREATED_AT DESC, l.LETTER_ID DESC"
    with DatabaseModel() as db:
        return _dicts(db.execute_query(sql, params or None))


def get_letter(letter_id: int) -> dict | None:
    with DatabaseModel() as db:
        rows = _dicts(db.execute_query(
            f"SELECT {LETTER_COLS} FROM FRZ_LETTER WHERE LETTER_ID = :id", {"id": letter_id}))
    return rows[0] if rows else None


def create_letter(data: dict, user: str | None = None) -> int:
    """Создаёт письмо и возвращает его LETTER_ID."""
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        out = cur.var(int)
        cur.execute(
            """INSERT INTO FRZ_LETTER
                 (SRC_CODE, COD_ORG, FURNIZOR, SUBIECT, TIP, N_POZITII,
                  STATUS, SENT_TO, NOTES, CREATED_BY)
               VALUES (:src, :org, :furn, :subj, :tip, :npoz,
                       :status, :sent_to, :notes, :usr)
               RETURNING LETTER_ID INTO :out""",
            src=data.get("src_code"), org=data.get("cod_org"),
            furn=data["furnizor"], subj=data["subiect"],
            tip=data.get("tip", "DENUMIRI"), npoz=data.get("n_pozitii"),
            status=data.get("status", "NOU"), sent_to=data.get("sent_to"),
            notes=data.get("notes"), usr=user, out=out)
        db.connection.commit()
        return int(out.getvalue()[0])


# Белый список: через API нельзя переписать что угодно, только эти поля
_EDITABLE = {"status": "STATUS", "sent_to": "SENT_TO", "notes": "NOTES",
             "furnizor": "FURNIZOR", "subiect": "SUBIECT", "tip": "TIP"}


def update_letter(letter_id: int, fields: dict) -> bool:
    sets, params = [], {"id": letter_id}
    for key, col in _EDITABLE.items():
        if key in fields:
            sets.append(f"{col} = :{key}")
            params[key] = fields[key]
    # Отметка «отправлено» проставляет дату сама — оператору её не вводить
    if fields.get("status") == "TRIMIS":
        sets.append("SENT_AT = NVL(SENT_AT, SYSDATE)")
    if fields.get("status") == "RASPUNS":
        sets.append("ANSWER_AT = NVL(ANSWER_AT, SYSDATE)")
    if not sets:
        return False
    sets.append("UPDATED_AT = SYSDATE")
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        cur.execute(f"UPDATE FRZ_LETTER SET {', '.join(sets)} WHERE LETTER_ID = :id", params)
        db.connection.commit()
        return cur.rowcount > 0


def delete_letter(letter_id: int) -> bool:
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        cur.execute("DELETE FROM FRZ_LETTER WHERE LETTER_ID = :id", {"id": letter_id})
        db.connection.commit()
        return cur.rowcount > 0


# --------------------------------------------------------------- вложения

KINDS = {"eml": ("EML", "message/rfc822"),
         "xlsx": ("XLSX", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
         "pdf": ("PDF", "application/pdf")}


def list_files(letter_id: int) -> list[dict]:
    with DatabaseModel() as db:
        return _dicts(db.execute_query(
            """SELECT FILE_ID, FILE_NAME, FILE_KIND, MIME, FILE_SIZE, UPLOADED_AT
                 FROM FRZ_LETTER_FILE WHERE LETTER_ID = :id ORDER BY FILE_ID""",
            {"id": letter_id}))


def add_file(letter_id: int, name: str, blob: bytes, user: str | None = None) -> int:
    ext = (name.rsplit(".", 1)[-1] if "." in name else "").lower()
    kind, mime = KINDS.get(ext, ("OTHER", "application/octet-stream"))
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        out = cur.var(int)
        cur.execute(
            """INSERT INTO FRZ_LETTER_FILE
                 (LETTER_ID, FILE_NAME, FILE_KIND, MIME, FILE_SIZE, FILE_SHA256,
                  FILE_BLOB, UPLOADED_BY)
               VALUES (:lid, :nm, :kind, :mime, :sz, :sha, :blob, :usr)
               RETURNING FILE_ID INTO :out""",
            lid=letter_id, nm=name, kind=kind, mime=mime, sz=len(blob),
            sha=hashlib.sha256(blob).hexdigest(), blob=blob, usr=user, out=out)
        db.connection.commit()
        return int(out.getvalue()[0])


def read_file(file_id: int) -> tuple[str, str, bytes] | None:
    """(имя, mime, содержимое) — сырым курсором, чтобы не портить бинарник."""
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        cur.execute("SELECT FILE_NAME, MIME, FILE_BLOB FROM FRZ_LETTER_FILE WHERE FILE_ID = :id",
                    {"id": file_id})
        row = cur.fetchone()
        if not row:
            return None
        lob = row[2]
        return row[0], row[1] or "application/octet-stream", (lob.read() if lob else b"")


def delete_file(file_id: int) -> bool:
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        cur.execute("DELETE FROM FRZ_LETTER_FILE WHERE FILE_ID = :id", {"id": file_id})
        db.connection.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------- справки

def suppliers() -> list[dict]:
    """Поставщики берутся из реестра источников импорта — письмо привязано к
    той же сущности, из которой приходят прайсы.

    Реестр живёт НЕ здесь: FRZ_* лежат в базе портала una.md (OCI, wallet), а
    TMS_ORG_IMPSRC — в боевой ERP OfficePlus (Oracle 11g, orange.una.md). Туда
    ходят только через Biro26DB: thick-режим переключает весь процесс и убил бы
    облачное подключение остальных модулей портала. Поэтому связь между письмом
    и поставщиком — по коду SRC_CODE, а не внешним ключом.
    """
    from models.biro26_db import Biro26DB
    with Biro26DB() as erp:
        return _dicts(erp.execute_query(
            "SELECT SRC_CODE, SRC_NAME, COD_ORG FROM TMS_ORG_IMPSRC WHERE ACTIVE = 1 ORDER BY SRC_NAME"))


def counters() -> dict:
    with DatabaseModel() as db:
        r = db.execute_query("SELECT STATUS, COUNT(*) FROM FRZ_LETTER GROUP BY STATUS")
    by = {row[0]: row[1] for row in _rows(r)}
    return {"total": sum(by.values()), "by_status": by}
