#!/usr/bin/env python3
"""Actiunea «Выгрузить в e-Factura» in back-office-ul NATIV una.md.

RO: back-office-ul nativ isi tine actiunile formularelor in tabelele
configuratorului (uniConf.exe): `A$ADM` (obiectul: tip 1 / subtip 2,
parintele = tipul de document, NAME0/1/2 = RU/RO/EN, SECTION unic) si
`A$ADP` (proprietatile: SQL1 = blocul PL/SQL executat cu `:nrdoc`,
TEXTFORUSER, VISIBLE, REFRESHDDOCNEED…). «Contul de plata» e obiectul 11476
(«Сгенерировать счета», SQL1 = `BEGIN commit; y_ai_BIRO26.gen_conturi_pr(:nrdoc); END;`).

Scriptul cloneaza EXACT acel obiect, cu SQL1 = `EFA_NATIVE.send_doc_pr` si
podpisurile e-Factura, in acelasi formular («CONT la plata», parinte 11256).
Idempotent: daca actiunea exista, nu face nimic. Creat prima data pe
02.09.2026 -> OBJ_ID 11522 (aparut imediat in aplicatie; audit in A$ACT).

Rulare:   venv/bin/python modules/efactura/scripts/efactura_native_action.py
Rollback: venv/bin/python modules/efactura/scripts/efactura_native_action.py --remove
EN: registers (or removes) the native back-office action by cloning the
payment-invoice action object.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

SOURCE_OBJ = 11476                      # «Сгенерировать счета»
PARENT_OBJ = 11256                      # formularul «CONT la plata»
SECTION = "2:9:VZ202MIACTION:0:20:5:5:5:43:43:4"
NAMES = ("Выгрузить в e-Factura", "Trimite in e-Factura", "Send to e-Factura")
SQL1 = "BEGIN commit; EFA_NATIVE.send_doc_pr(:nrdoc); END;"
ACTION_ID = 12                          # prop ID: urmatorul liber in formular


def _load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    _load_env()
    os.chdir(ROOT)
    from models.biro26_db import Biro26DB
    from models.biro26_oracle_store import _rows
    db = Biro26DB()
    have = _rows(db.execute_query(
        "SELECT OBJ_ID FROM A$ADM WHERE PARENT_ID = :p AND OBJ_TYPE = 1 "
        "AND OBJ_SUBTYPE = 2 AND SECTION = :s", {"p": PARENT_OBJ, "s": SECTION}))
    if "--remove" in sys.argv:
        if not have:
            print("actiunea nu exista — nimic de sters")
            return 0
        oid = int(have[0]["obj_id"])
        db.execute_dml("DELETE FROM A$ADP WHERE OBJ_ID = :o", {"o": oid})
        db.execute_dml("DELETE FROM A$ADM WHERE OBJ_ID = :o", {"o": oid})
        print("stearsa actiunea OBJ_ID", oid)
        return 0
    if have:
        print("actiunea exista deja: OBJ_ID", have[0]["obj_id"])
        return 0
    r = db.call_proc("""
DECLARE
  v_new NUMBER;
BEGIN
  SELECT A$ADM$SQ.NEXTVAL INTO v_new FROM dual;
  INSERT INTO A$ADM (OBJ_ID, SYS_ID, OBJ_TYPE, OBJ_SUBTYPE, LINK_ID, PARENT_ID, TEMPLATE_ID,
                     NAME0, NAME1, NAME2, SECTION, NRORD, DATE_BEGIN, DATE_FINAL, MODIFIED)
  SELECT v_new, SYS_ID, OBJ_TYPE, OBJ_SUBTYPE, LINK_ID, PARENT_ID, TEMPLATE_ID,
         :n0, :n1, :n2, :sec, v_new, DATE_BEGIN, DATE_FINAL, SYSDATE
    FROM A$ADM WHERE OBJ_ID = :src;
  INSERT INTO A$ADP (OBJ_ID, KEY, NAME, HINT, GR, VTYPE, VALUE0, VALUE1, VALUE2,
                     SVALUE, IVALUE, BVALUE, DVALUE, LVALUE, ATTR, FVALUE)
  SELECT v_new, KEY, NAME,
         CASE WHEN KEY = 'SQL1' THEN 'e-Factura: Oracle -> UTL_HTTP -> API web -> SFS (EFA_NATIVE)' ELSE HINT END,
         GR, VTYPE, VALUE0, VALUE1, VALUE2,
         CASE WHEN KEY = 'TEXTFORUSER' THEN :n0 ELSE SVALUE END,
         CASE WHEN KEY = 'ID' THEN :aid ELSE IVALUE END,
         BVALUE, DVALUE,
         CASE WHEN KEY = 'SQL1' THEN TO_CLOB(:sql1) ELSE LVALUE END,
         ATTR, FVALUE
    FROM A$ADP WHERE OBJ_ID = :src;
  DBMS_OUTPUT.PUT_LINE('NEW_OBJ_ID=' || v_new);
END;""", {"n0": NAMES[0], "n1": NAMES[1], "n2": NAMES[2], "sec": SECTION,
          "src": SOURCE_OBJ, "aid": ACTION_ID, "sql1": SQL1}, capture_output=True)
    print("creata:", r.get("success"), r.get("output_lines") or str(r.get("message"))[:300])
    return 0 if r.get("success") else 2


if __name__ == "__main__":
    sys.exit(main())
