"""Angajatii: citirea si scrierea peste arborele de configurare al UNA.

RO: sursa de adevar e ERP-ul — nodul utilizator `A$ADM` (7/0) cu
proprietatile din `A$ADP`; fisa `CRM_EMPLOYEE` doar completeaza (e-mail,
telefon, data inregistrarii, notite) si e tinuta la zi de triggere.

Ce facem prin API-ul ERP-ului, nu «pe linga» el:
  * parola — `a$util.set_passwd` (aceleasi verificari ca la schimbarea
    parolei din UniacCLNT);
  * intrarea — `a$util.login` (o folosim la «Verifica parola»);
  * blocarea — proprietatea `Enabled`, exact cea citita de `a$util.login`.
EN: employee store on top of the UNA config tree.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows

from modules.crm import employees as R

_COLS = ("SELECT e.OBJ_ID, e.USER_ID, e.USERNAME, e.FULL_NAME, e.EMAIL, e.PHONE, e.GROUP_ID, "
         "e.ENABLED, e.IS_ADMIN, TO_CHAR(e.REG_DATE,'YYYY-MM-DD') REG_DATE, "
         "TO_CHAR(e.PASS_DATE,'YYYY-MM-DD') PASS_DATE, TO_CHAR(e.LOCKED_DATE,'YYYY-MM-DD') LOCKED_DATE, "
         "e.NOTES, e.SRC, TO_CHAR(e.SYNCED,'YYYY-MM-DD HH24:MI') SYNCED, "
         "(SELECT g.NAME0 FROM A$ADM g WHERE g.OBJ_ID = e.GROUP_ID) GROUP_NAME "
         "FROM CRM_EMPLOYEE e")


class EmployeeStore:
    def __init__(self, db: Optional[Biro26DB] = None):
        self.db = db or Biro26DB()

    # ── citire ───────────────────────────────────────────────────────────
    def rows(self, sql: str, p: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return _rows(self.db.execute_query(sql, p or {}))

    def dml(self, sql: str, p: Optional[Dict[str, Any]] = None) -> None:
        r = self.db.execute_dml(sql, p or {})
        if not r.get("success"):
            raise RuntimeError(r.get("message") or "eroare DML")

    def scalar(self, sql: str, p: Optional[Dict[str, Any]] = None) -> Any:
        r = self.db.execute_query(sql, p or {})
        if not r.get("success"):
            raise RuntimeError(r.get("message") or "eroare SQL")
        d = r.get("data") or []
        return d[0][0] if d and d[0] else None

    def list(self, q: str = "", only: str = "all", sort: str = "username") -> List[Dict[str, Any]]:
        where, p = " WHERE 1=1", {}
        if only == "active":
            where += " AND e.ENABLED = 1"
        elif only == "disabled":
            where += " AND e.ENABLED = 0"
        if (q or "").strip():
            where += (" AND (UPPER(e.USERNAME) LIKE :q OR UPPER(NVL(e.FULL_NAME,' ')) LIKE :q "
                      "OR UPPER(NVL(e.EMAIL,' ')) LIKE :q OR NVL(e.PHONE,' ') LIKE :q2)")
            p["q"] = "%" + q.strip().upper() + "%"
            p["q2"] = "%" + q.strip() + "%"
        return self.rows(_COLS + where + " ORDER BY e." + R.sort_key(sort), p)

    def get(self, obj_id: int) -> Optional[Dict[str, Any]]:
        r = self.rows(_COLS + " WHERE e.OBJ_ID = :id", {"id": int(obj_id)})
        return r[0] if r else None

    def by_username(self, username: str) -> Optional[Dict[str, Any]]:
        r = self.rows(_COLS + " WHERE UPPER(e.USERNAME) = :u", {"u": (username or "").upper()})
        return r[0] if r else None

    def groups(self) -> List[Dict[str, Any]]:
        """RO: grupele de utilizatori din arbore (A$ADM 7/-1) — parintele nodului."""
        return self.rows(
            "SELECT g.OBJ_ID, g.NAME0, g.SECTION, "
            "(SELECT COUNT(*) FROM A$ADM u WHERE u.PARENT_ID = g.OBJ_ID AND u.OBJ_TYPE = 7 "
            " AND u.OBJ_SUBTYPE = 0) CNT "
            "FROM A$ADM g WHERE g.OBJ_TYPE = 7 AND g.OBJ_SUBTYPE = -1 ORDER BY g.NAME0")

    def next_user_id(self, group_id: int) -> int:
        """RO: numarul utilizatorului (proprietatea ID). Il luam urmatorul liber
        dupa cel mai mare din arbore — la fel ca administratorul in uniConf."""
        v = self.scalar("SELECT NVL(MAX(p.IVALUE),0) + 1 FROM A$ADP p JOIN A$ADM m ON m.OBJ_ID = p.OBJ_ID "
                        "WHERE p.KEY = 'ID' AND m.OBJ_TYPE = 7 AND m.OBJ_SUBTYPE = 0")
        return int(v or 1)

    # ── jurnal ───────────────────────────────────────────────────────────
    def log(self, action: str, obj_id: Optional[int], username: str, actor: str, detail: str = "") -> None:
        try:
            self.dml("INSERT INTO CRM_EMPLOYEE_LOG (OBJ_ID, USERNAME, ACTION, ACTOR, DETAIL) "
                     "VALUES (:o, :u, :a, :ac, :d)",
                     {"o": obj_id, "u": (username or "")[:100], "a": action[:30],
                      "ac": (actor or "")[:100], "d": (detail or "")[:1000]})
        except RuntimeError:
            pass

    def events(self, limit: int = 50, obj_id: Optional[int] = None) -> List[Dict[str, Any]]:
        w = " WHERE OBJ_ID = :o" if obj_id else ""
        p: Dict[str, Any] = {"l": max(1, min(int(limit), 500))}
        if obj_id:
            p["o"] = int(obj_id)
        return self.rows("SELECT * FROM (SELECT ID, TO_CHAR(TS,'DD.MM.YYYY HH24:MI') TS, OBJ_ID, USERNAME, "
                         "ACTION, ACTOR, DETAIL FROM CRM_EMPLOYEE_LOG%s ORDER BY ID DESC) "
                         "WHERE ROWNUM <= :l" % w, p)

    # ── scriere ──────────────────────────────────────────────────────────
    def create(self, username: str, group_id: int, full_name: str = "", email: str = "",
               phone: str = "", password: str = "", is_admin: bool = False,
               actor: str = "") -> Dict[str, Any]:
        """RO: inregistrarea unui angajat = un nod nou de utilizator in arbore,
        exact ca in uniConf, plus parola prin `a$util.set_passwd`."""
        username = R.check_username(username)
        R.check_optional(email, phone)
        pwd = R.check_password(password or R.gen_password())
        if self.by_username(username):
            raise ValueError("username: exista deja un angajat cu acest nume")
        n = self.scalar("SELECT COUNT(*) FROM A$ADP p JOIN A$ADM m ON m.OBJ_ID = p.OBJ_ID "
                        "WHERE p.KEY = 'USERNAME' AND UPPER(p.SVALUE) = :u AND m.OBJ_TYPE = 7",
                        {"u": username.upper()})
        if int(n or 0):
            raise ValueError("username: numele exista deja in arborele ERP")
        if not int(self.scalar("SELECT COUNT(*) FROM A$ADM WHERE OBJ_ID = :g AND OBJ_TYPE = 7 "
                               "AND OBJ_SUBTYPE = -1", {"g": int(group_id)}) or 0):
            raise ValueError("group_id: grupa de utilizatori nu exista")

        user_id = self.next_user_id(group_id)
        name0 = R.node_name(user_id, full_name, username)
        # RO: nodul + proprietatile intr-un singur bloc: daca ceva cade, nu ramine
        #     un utilizator pe jumatate creat in arborele ERP-ului.
        plsql = """
DECLARE
  v_obj NUMBER;
BEGIN
  -- RO: SECTION e UNIC pe toata tabela (A$ADM$UQ). In arbore conventia e
  --     SECTION = OBJ_ID, deci luam numarul din secventa inainte de insert.
  SELECT A$ADM$SQ.NEXTVAL INTO v_obj FROM dual;
  INSERT INTO A$ADM (OBJ_ID, OBJ_TYPE, OBJ_SUBTYPE, PARENT_ID, SECTION, NAME0)
    VALUES (v_obj, 7, 0, :grp, TO_CHAR(v_obj), :name0);
  INSERT INTO A$ADP (OBJ_ID, KEY, NAME, VTYPE, SVALUE) VALUES (v_obj, 'USERNAME', 'UserName', 'S', :uname);
  INSERT INTO A$ADP (OBJ_ID, KEY, NAME, VTYPE, IVALUE) VALUES (v_obj, 'ID', 'ID', 'I', :uid);
  INSERT INTO A$ADP (OBJ_ID, KEY, NAME, VTYPE, BVALUE) VALUES (v_obj, 'ENABLED', 'Enabled', 'B', 'T');
  INSERT INTO A$ADP (OBJ_ID, KEY, NAME, VTYPE, IVALUE) VALUES (v_obj, 'GROUPID', 'GroupID', 'I', :grp);
  INSERT INTO A$ADP (OBJ_ID, KEY, NAME, VTYPE, SVALUE) VALUES (v_obj, 'ADMIN', 'Admin', 'S', :adm);
  IF :fname IS NOT NULL THEN
    INSERT INTO A$ADP (OBJ_ID, KEY, NAME, VTYPE, SVALUE) VALUES (v_obj, 'FAMILIA', 'Familia', 'S', :fname);
  END IF;
  A$UTIL.SET_PASSWD(v_obj, :pwd);
  CRM_EMP_SYNC.from_erp(v_obj);
  UPDATE CRM_EMPLOYEE SET EMAIL = :mail, PHONE = :tel, SRC = 'web', REG_DATE = SYSDATE
   WHERE OBJ_ID = v_obj;
END;"""
        # RO: `call_proc` nu intoarce parametri OUT — nodul nou il regasim dupa nume
        r = self.db.call_proc(plsql, {
            "grp": int(group_id), "section": str(group_id), "name0": name0[:255],
            "uname": username, "uid": user_id, "adm": "1" if is_admin else "0",
            "fname": (full_name or "").strip()[:200] or None, "pwd": pwd,
            "mail": (email or "").strip()[:120] or None, "tel": (phone or "").strip()[:60] or None})
        if not r.get("success"):
            raise RuntimeError(r.get("message") or "nu s-a putut crea utilizatorul")
        row = self.by_username(username)
        obj_id = int((row or {}).get("obj_id") or 0)
        self.log("created", obj_id, username, actor,
                 "grupa %s, ID %s%s" % (group_id, user_id, ", admin" if is_admin else ""))
        return {"employee": row, "password": pwd}

    def set_enabled(self, obj_id: int, enabled: bool, actor: str = "") -> Dict[str, Any]:
        """RO: dezactivarea contului — proprietatea `Enabled` din arbore, cea pe
        care o citeste `a$util.login`. O scriem prin fisa, triggerul o duce mai
        departe; la reactivare stergem si contorul de parole gresite."""
        e = self.get(obj_id)
        if not e:
            raise LookupError("angajat inexistent")
        self.dml("UPDATE CRM_EMPLOYEE SET ENABLED = :v WHERE OBJ_ID = :id",
                 {"v": 1 if enabled else 0, "id": int(obj_id)})
        if enabled:
            self.dml("DELETE FROM A$ADP WHERE OBJ_ID = :id AND KEY IN ('PASSERRORS','AUTOLOCKEDDATE')",
                     {"id": int(obj_id)})
            self.dml("UPDATE CRM_EMPLOYEE SET LOCKED_DATE = NULL WHERE OBJ_ID = :id", {"id": int(obj_id)})
        self.log("enabled" if enabled else "disabled", int(obj_id), e.get("username") or "", actor)
        return self.get(obj_id) or {}

    def set_password(self, obj_id: int, password: str = "", actor: str = "") -> Dict[str, Any]:
        """RO: parola standard / recuperarea ei. Nu o tinem nicaieri la noi:
        o scrie `a$util.set_passwd` si o aratam administratorului o data."""
        e = self.get(obj_id)
        if not e:
            raise LookupError("angajat inexistent")
        pwd = R.check_password(password or R.gen_password())
        r = self.db.call_proc("BEGIN A$UTIL.SET_PASSWD(:id, :pwd); "
                              "CRM_EMP_SYNC.from_erp(:id); END;",
                              {"id": int(obj_id), "pwd": pwd})
        if not r.get("success"):
            raise RuntimeError(r.get("message") or "parola nu a fost acceptata de ERP")
        self.log("password", int(obj_id), e.get("username") or "", actor,
                 "parola noua generata" if not password else "parola pusa manual")
        return {"employee": self.get(obj_id), "password": pwd}

    def update_card(self, obj_id: int, values: Dict[str, Any], actor: str = "") -> Dict[str, Any]:
        """RO: e-mail, telefon, nume complet, notite — partea de fisa. Numele
        complet si contactele urca in arbore prin trigger."""
        e = self.get(obj_id)
        if not e:
            raise LookupError("angajat inexistent")
        R.check_optional(values.get("email"), values.get("phone"))
        self.dml("UPDATE CRM_EMPLOYEE SET FULL_NAME = :f, EMAIL = :m, PHONE = :t, NOTES = :n "
                 "WHERE OBJ_ID = :id",
                 {"f": (values.get("full_name") or "").strip()[:200] or None,
                  "m": (values.get("email") or "").strip()[:120] or None,
                  "t": (values.get("phone") or "").strip()[:60] or None,
                  "n": (values.get("notes") or "").strip()[:1000] or None,
                  "id": int(obj_id)})
        self.log("updated", int(obj_id), e.get("username") or "", actor)
        return self.get(obj_id) or {}

    def check_login(self, username: str, password: str) -> Dict[str, Any]:
        """RO: «Verifica parola» — chiar apelul pe care il face UniacCLNT.
        Nu se poate chema din SELECT: la parola gresita `a$util.login` scrie
        contorul de incercari si face commit (ORA-14551 intr-o interogare).
        De aceea bloc PL/SQL, iar rezultatul vine prin DBMS_OUTPUT."""
        r = self.db.call_proc(
            "DECLARE v NUMBER; BEGIN v := A$UTIL.LOGIN(:u, :p); "
            "DBMS_OUTPUT.PUT_LINE('OBJ_ID=' || v); END;",
            {"u": username, "p": password}, capture_output=True)
        if not r.get("success"):
            return {"ok": False, "error": str(r.get("message") or "")[:300]}
        out = " ".join(r.get("output_lines") or [])
        return {"ok": "OBJ_ID=" in out, "detail": out.strip()[:200]}

    def sync(self, actor: str = "") -> Dict[str, Any]:
        """RO: aduce din arbore utilizatorii aparuti / schimbati din uniConf."""
        before = int(self.scalar("SELECT COUNT(*) FROM CRM_EMPLOYEE") or 0)
        r = self.db.call_proc("DECLARE n NUMBER; BEGIN n := CRM_EMP_SYNC.PULL_ALL; END;")
        if not r.get("success"):
            raise RuntimeError(r.get("message") or "sincronizare esuata")
        after = int(self.scalar("SELECT COUNT(*) FROM CRM_EMPLOYEE") or 0)
        self.log("synced", None, "", actor, "in arbore: %d, fise noi: %d" % (after, after - before))
        return {"total": after, "added": after - before}
