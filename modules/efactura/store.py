"""Stratul de date al modulului e-Factura (conturul EFA_*).

RO: setarile, starea fiecarui document si jurnalul. Datele facturii NU se
duplica: se iau din `Biro26Report.doc_data` — aceeasi sursa din care se
tipareste contul de plata, deci ce vede clientul pe hirtie si ce pleaca la SFS
nu pot diverge.
EN: settings, per-document state and log; invoice data reuses the very source
the printed form uses.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows

# RO: setarile cunoscute + valorile implicite. `password` nu se intoarce
#     niciodata catre interfata (doar faptul ca e completata).
DEFAULTS = {
    "endpoint": "",
    "username": "",
    "password": "",
    "namespace": "http://tempuri.org/",
    "mode": "semi",              # semi | full  (vezi analiza SFS)
    "seller_idno": "",
    "seller_name": "",
    "seller_address": "",
    "seller_iban": "",
    "seller_bank_code": "",
    "seria": "",
    "auto_send": "0",            # trimitere automata la emiterea contului
    "only_companies": "1",       # doar clientilor persoane juridice
}
SECRET_KEYS = ("password",)


class EfaStore:

    # ── setari ─────────────────────────────────────────────────────────
    @staticmethod
    def settings() -> Dict[str, str]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT SKEY, SVALUE FROM EFA_SETTING"))
        out = dict(DEFAULTS)
        for r in rows:
            out[str(r["skey"])] = r["svalue"] or ""
        return out

    @staticmethod
    def settings_public() -> Dict[str, Any]:
        """RO: pentru interfata — fara secrete, dar cu semnalul «e completat»."""
        s = EfaStore.settings()
        pub = {k: v for k, v in s.items() if k not in SECRET_KEYS}
        pub["password_set"] = bool(s.get("password"))
        pub["configured"] = bool(s.get("endpoint") and s.get("username")
                                 and s.get("password"))
        return pub

    @staticmethod
    def set_settings(d: Dict[str, Any]) -> Dict[str, Any]:
        db = Biro26DB()
        saved = []
        for key, val in (d or {}).items():
            if key not in DEFAULTS:
                continue
            # RO: campurile secrete goale = «nu schimba», nu «sterge»
            if key in SECRET_KEYS and (val is None or str(val) == ""):
                continue
            r = db.execute_dml(
                "MERGE INTO EFA_SETTING t USING (SELECT :k SKEY FROM dual) s "
                "ON (t.SKEY = s.SKEY) "
                "WHEN MATCHED THEN UPDATE SET t.SVALUE = :v1, t.UPDATED = SYSDATE "
                "WHEN NOT MATCHED THEN INSERT (SKEY, SVALUE) VALUES (:k2, :v2)",
                {"k": key, "v1": str(val)[:2000], "k2": key,
                 "v2": str(val)[:2000]})
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            saved.append(key)
        EfaStore.log(None, "settings", ", ".join(saved), "backoffice")
        return {"success": True, "data": {"saved": saved}}

    # ── jurnal ─────────────────────────────────────────────────────────
    @staticmethod
    def log(doc_cod: Optional[int], event: str, detail: str = "",
            src: str = "") -> None:
        try:
            Biro26DB().execute_dml(
                "INSERT INTO EFA_LOG (DOC_COD, EVENT, DETAIL, SRC) "
                "VALUES (:d, :e, :t, :s)",
                {"d": doc_cod, "e": str(event)[:40],
                 "t": (detail or "")[:2000], "s": (src or "")[:20]})
        except Exception:                                    # noqa: BLE001
            pass

    @staticmethod
    def log_list(limit: int = 200) -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT * FROM (SELECT ID, TO_CHAR(TS,'DD.MM.YYYY HH24:MI:SS') TS, "
            "DOC_COD, EVENT, SRC, SUBSTR(DETAIL,1,400) DETAIL FROM EFA_LOG "
            "ORDER BY ID DESC) WHERE ROWNUM <= :l",
            {"l": max(1, min(int(limit), 500))}))
        return {"success": True, "data": rows}

    # ── documente ──────────────────────────────────────────────────────
    @staticmethod
    def doc_state(doc_cod: int) -> Optional[Dict[str, Any]]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT ID, DOC_COD, NRMANUAL, STATUS, SFS_SERIA, SFS_NUMBER, "
            "SFS_UUID, REQUEST_ID, ERR_MSG, "
            "TO_CHAR(SENT_AT,'DD.MM.YYYY HH24:MI') SENT_AT, "
            "TO_CHAR(UPDATED,'DD.MM.YYYY HH24:MI') UPDATED "
            "FROM EFA_DOC WHERE DOC_COD = :c", {"c": int(doc_cod)}))
        return rows[0] if rows else None

    @staticmethod
    def doc_upsert(doc_cod: int, **fields) -> None:
        """RO: o singura linie per document; statusul se rescrie la fiecare pas."""
        cols = {k: v for k, v in fields.items() if v is not None}
        db = Biro26DB()
        sets = ", ".join(f"{k.upper()} = :{k}" for k in cols)
        p = dict(cols, c=int(doc_cod))
        r = db.execute_dml(
            f"UPDATE EFA_DOC SET {sets}, UPDATED = SYSDATE WHERE DOC_COD = :c"
            if sets else
            "UPDATE EFA_DOC SET UPDATED = SYSDATE WHERE DOC_COD = :c", p)
        if r.get("success") and (r.get("rowcount") or 0) > 0:
            return
        names = ["DOC_COD"] + [k.upper() for k in cols]
        binds = [":c"] + [f":{k}" for k in cols]
        db.execute_dml(
            f"INSERT INTO EFA_DOC ({', '.join(names)}) "
            f"VALUES ({', '.join(binds)})", p)

    @staticmethod
    def doc_list(status: str = "", limit: int = 100) -> Dict[str, Any]:
        sql = ("SELECT ID, DOC_COD, NRMANUAL, CLIENT_COD, CLIENT_IDNO, TOTAL, "
               "STATUS, SFS_SERIA, SFS_NUMBER, ERR_MSG, "
               "TO_CHAR(SENT_AT,'DD.MM.YYYY HH24:MI') SENT_AT "
               "FROM EFA_DOC")
        p: Dict[str, Any] = {}
        if status:
            sql += " WHERE STATUS = :s"
            p["s"] = status.upper()[:20]
        sql = (f"SELECT * FROM ({sql} ORDER BY ID DESC) "
               "WHERE ROWNUM <= :l")
        p["l"] = max(1, min(int(limit), 500))
        return {"success": True, "data": _rows(Biro26DB().execute_query(sql, p))}
