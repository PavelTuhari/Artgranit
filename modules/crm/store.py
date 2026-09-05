"""Stratul de date al CRM-ului (conturul CRM_*), peste Oracle-ul OfficePlus.

RO: acelasi transport ca restul modulelor de ERP (`Biro26DB`, worker thick).
Cardul Contragenti se descompune ca in `uClientsDB.pas` din Demo CRM:
clientul + fondatorii + datoriile, deduplicare dupa IDNO (UNIQUE in baza,
verificare si inainte de INSERT). Jurnalul e append-only.
EN: CRM_* storage: client card, founders, debts, settings, event log.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows

from modules.crm import rules

DEFAULTS = {
    "contragenti_url": "http://127.0.0.1:9393",   # API-ul local al Contragenti
    "lang": "ro",                                  # limba ferestrei Contragenti
    "pick_timeout": "300",
}

_CLIENT_COLS = ("SELECT c.ID, c.IDNO, c.NAME, c.REG_DATE, c.LEGAL_FORM, c.IS_LIQUIDATED, "
                "c.ADDRESS, c.MANAGERS, c.SOURCE, c.SOURCE_UPDATED, c.NOTE, "
                "TO_CHAR(c.CREATED,'DD.MM.YYYY HH24:MI') CREATED, "
                "TO_CHAR(c.UPDATED,'DD.MM.YYYY HH24:MI') UPDATED, "
                "(SELECT COUNT(*) FROM CRM_FOUNDER f WHERE f.CLIENT_ID = c.ID) FOUNDERS_CNT, "
                "(SELECT NVL(SUM(d.AMOUNT),0) FROM CRM_DEBT d WHERE d.CLIENT_ID = c.ID) DEBT_SUM "
                "FROM CRM_CLIENT c")


class CrmStore:
    # ── setari ───────────────────────────────────────────────────────────
    @staticmethod
    def settings() -> Dict[str, str]:
        out = dict(DEFAULTS)
        for r in _rows(Biro26DB().execute_query("SELECT SKEY, SVALUE FROM CRM_SETTING")):
            out[str(r["skey"])] = r["svalue"] or ""
        return out

    @staticmethod
    def set_settings(values: Dict[str, Any]) -> Dict[str, Any]:
        db = Biro26DB()
        for k, v in values.items():
            if k not in DEFAULTS:
                continue
            r = db.execute_dml(
                "MERGE INTO CRM_SETTING s USING (SELECT :k SKEY FROM dual) n "
                "ON (s.SKEY = n.SKEY) WHEN MATCHED THEN UPDATE SET SVALUE = :v, UPDATED = SYSDATE "
                "WHEN NOT MATCHED THEN INSERT (SKEY, SVALUE) VALUES (:k, :v)",
                {"k": k, "v": str(v or "")[:2000]})
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
        return {"success": True}

    # ── clienti ──────────────────────────────────────────────────────────
    @staticmethod
    def list(preset: str = "all", q: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        where = " WHERE 1=1" + rules.preset_where(preset)
        params: Dict[str, Any] = {"l": max(1, min(int(limit), 1000))}
        if q and q.strip():
            where += (" AND (UPPER(c.NAME) LIKE :q OR c.IDNO LIKE :q2 "
                      "OR UPPER(c.ADDRESS) LIKE :q OR UPPER(c.MANAGERS) LIKE :q)")
            params["q"] = "%" + q.strip().upper() + "%"
            params["q2"] = "%" + q.strip() + "%"
        rows = _rows(Biro26DB().execute_query(
            "SELECT * FROM (" + _CLIENT_COLS + where + " ORDER BY c.CREATED DESC, c.ID DESC) "
            "WHERE ROWNUM <= :l", params))
        return rows

    @staticmethod
    def get(client_id: int) -> Optional[Dict[str, Any]]:
        db = Biro26DB()
        rows = _rows(db.execute_query(_CLIENT_COLS + " WHERE c.ID = :id", {"id": int(client_id)}))
        if not rows:
            return None
        c = rows[0]
        c["founders"] = _rows(db.execute_query(
            "SELECT NAME, SHARE_PCT FROM CRM_FOUNDER WHERE CLIENT_ID = :id ORDER BY ID",
            {"id": int(client_id)}))
        c["debts"] = _rows(db.execute_query(
            "SELECT NR, DEBT_TYPE, AMOUNT, CURRENCY FROM CRM_DEBT WHERE CLIENT_ID = :id ORDER BY NR, ID",
            {"id": int(client_id)}))
        det = _rows(db.execute_query(
            "SELECT DBMS_LOB.SUBSTR(DETAILS_TEXT, 4000, 1) T FROM CRM_CLIENT WHERE ID = :id",
            {"id": int(client_id)}))
        c["details_text"] = (det[0]["t"] if det else "") or ""
        return c

    @staticmethod
    def find_by_idno(idno: str) -> Optional[Dict[str, Any]]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT ID, NAME FROM CRM_CLIENT WHERE IDNO = :i", {"i": str(idno)}))
        return rows[0] if rows else None

    @staticmethod
    def add_from_card(card: Dict[str, Any], src: str = "xml",
                      refresh: bool = False) -> Dict[str, Any]:
        """RO: cele trei iesiri ale Demo CRM: added / dup / (cu refresh) updated."""
        db = Biro26DB()
        have = CrmStore.find_by_idno(card["idno"])
        if have and not refresh:
            CrmStore.log("dup", src, card["idno"], int(have["id"]), rules.card_summary(card))
            return {"success": True, "result": "dup", "id": int(have["id"]),
                    "name": have.get("name")}
        vals = {"idno": card["idno"][:20], "name": (card.get("denumire") or "")[:400],
                "reg": (card.get("inregistrare") or "")[:20],
                "lf": (card.get("forma_juridica") or "")[:200],
                "liq": 1 if card.get("lichidata") else 0,
                "addr": (card.get("adresa") or "")[:1000] or None,
                "mgr": (card.get("administratori") or "")[:1000],
                "det": card.get("details_text") or None,
                "src": (card.get("source") or "date.gov.md")[:60],
                "upd": (card.get("updated") or "")[:40]}
        if have:
            cid = int(have["id"])
            r = db.execute_dml(
                # RO: CLOB-ul ULTIMUL intre binduri (ORA-24816 altfel)
                "UPDATE CRM_CLIENT SET NAME=:name, REG_DATE=:reg, LEGAL_FORM=:lf, "
                "IS_LIQUIDATED=:liq, ADDRESS=:addr, MANAGERS=:mgr, SOURCE=:src, "
                "SOURCE_UPDATED=:upd, UPDATED=SYSDATE, DETAILS_TEXT=:det WHERE ID=:id",
                dict({k: v for k, v in vals.items() if k != "idno"}, id=cid))
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            db.execute_dml("DELETE FROM CRM_FOUNDER WHERE CLIENT_ID = :id", {"id": cid})
            db.execute_dml("DELETE FROM CRM_DEBT WHERE CLIENT_ID = :id", {"id": cid})
            result = "updated"
        else:
            nx = _rows(db.execute_query("SELECT CRM_CLIENT_SEQ.NEXTVAL N FROM dual"))
            cid = int(nx[0]["n"])
            r = db.execute_dml(
                # RO: CLOB-ul ULTIMUL intre binduri (ORA-24816 altfel)
                "INSERT INTO CRM_CLIENT (ID, IDNO, NAME, REG_DATE, LEGAL_FORM, IS_LIQUIDATED, "
                "ADDRESS, MANAGERS, SOURCE, SOURCE_UPDATED, DETAILS_TEXT) VALUES "
                "(:id, :idno, :name, :reg, :lf, :liq, :addr, :mgr, :src, :upd, :det)",
                dict(vals, id=cid))
            if not r.get("success"):
                msg = str(r.get("message") or "")
                if "ORA-00001" in msg:            # RO: cursa: altcineva l-a adaugat intre timp
                    have = CrmStore.find_by_idno(card["idno"]) or {}
                    return {"success": True, "result": "dup", "id": int(have.get("id") or 0)}
                return {"success": False, "error": msg}
            result = "added"
        for f in card.get("founders") or []:
            db.execute_dml("INSERT INTO CRM_FOUNDER (CLIENT_ID, NAME, SHARE_PCT) VALUES (:c, :n, :s)",
                           {"c": cid, "n": (f.get("name") or "")[:400], "s": f.get("share")})
        for d in card.get("debts") or []:
            db.execute_dml("INSERT INTO CRM_DEBT (CLIENT_ID, NR, DEBT_TYPE, AMOUNT, CURRENCY) "
                           "VALUES (:c, :nr, :t, :a, :cur)",
                           {"c": cid, "nr": d.get("nr"), "t": (d.get("type") or "")[:200],
                            "a": d.get("sum"), "cur": (card.get("currency") or "MDL")[:3]})
        CrmStore.log(result, src, card["idno"], cid, rules.card_summary(card))
        return {"success": True, "result": result, "id": cid, "name": vals["name"]}

    @staticmethod
    def delete(client_id: int) -> Dict[str, Any]:
        c = CrmStore.get(client_id)
        if not c:
            return {"success": False, "error": "client inexistent"}
        r = Biro26DB().execute_dml("DELETE FROM CRM_CLIENT WHERE ID = :id", {"id": int(client_id)})
        if not r.get("success"):
            return {"success": False, "error": r.get("message")}
        CrmStore.log("deleted", "ui", c.get("idno"), int(client_id), c.get("name") or "")
        return {"success": True}

    @staticmethod
    def set_note(client_id: int, note: str) -> Dict[str, Any]:
        r = Biro26DB().execute_dml("UPDATE CRM_CLIENT SET NOTE = :n, UPDATED = SYSDATE WHERE ID = :id",
                                   {"n": (note or "")[:2000], "id": int(client_id)})
        return {"success": bool(r.get("success")), "error": r.get("message")}

    # ── statistici + jurnal ──────────────────────────────────────────────
    @staticmethod
    def stats() -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT COUNT(*) TOTAL, SUM(CASE WHEN TRUNC(CREATED)=TRUNC(SYSDATE) THEN 1 ELSE 0 END) TODAY, "
            "SUM(CASE WHEN ADDRESS IS NOT NULL THEN 1 ELSE 0 END) WITH_ADDRESS, "
            "SUM(IS_LIQUIDATED) LIQUIDATED FROM CRM_CLIENT"))
        s = rows[0] if rows else {}
        return {k: int(s.get(k) or 0) for k in ("total", "today", "with_address", "liquidated")}

    @staticmethod
    def log(event: str, src: str, idno: Optional[str], client_id: Optional[int], detail: str) -> None:
        try:
            Biro26DB().execute_dml(
                "INSERT INTO CRM_EVENT_LOG (CLIENT_ID, IDNO, EVENT, SRC, DETAIL) "
                "VALUES (:c, :i, :e, :s, :d)",
                {"c": client_id, "i": (idno or "")[:20] or None, "e": event[:40],
                 "s": (src or "")[:20], "d": (detail or "")[:2000]})
        except Exception:                                    # noqa: BLE001
            pass

    @staticmethod
    def events(limit: int = 50, client_id: Optional[int] = None) -> List[Dict[str, Any]]:
        where = " WHERE CLIENT_ID = :c" if client_id else ""
        params: Dict[str, Any] = {"l": max(1, min(int(limit), 500))}
        if client_id:
            params["c"] = int(client_id)
        return _rows(Biro26DB().execute_query(
            "SELECT * FROM (SELECT ID, TO_CHAR(TS,'DD.MM.YYYY HH24:MI:SS') TS, CLIENT_ID, IDNO, "
            f"EVENT, SRC, DETAIL FROM CRM_EVENT_LOG{where} ORDER BY ID DESC) WHERE ROWNUM <= :l",
            params))
