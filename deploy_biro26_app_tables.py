#!/usr/bin/env python3
"""Deploy Biro26 app-owned mapping tables to OfficePlus (Oracle 11g).

Idempotent: skips if YBIRO_MAP_PROFILE already exists. Runs the DDL from
sql/biro26/01_biro26_app_tables.sql via the thick-mode subprocess worker
(no sqlplus required).

Usage: ./venv/bin/python deploy_biro26_app_tables.py
"""
from __future__ import annotations
import sys
from models.biro26_db import Biro26DB

DDL_TABLE_PROFILE = """
CREATE TABLE YBIRO_MAP_PROFILE (
  id          NUMBER PRIMARY KEY,
  name        VARCHAR2(60) NOT NULL,
  codprice    NUMBER,
  is_default  VARCHAR2(1) DEFAULT '0',
  created_at  TIMESTAMP DEFAULT SYSTIMESTAMP,
  created_by  VARCHAR2(60) DEFAULT USER,
  CONSTRAINT uq_ybiro_map_profile_name UNIQUE (name)
)"""

DDL_SEQ = "CREATE SEQUENCE YBIRO_MAP_PROFILE_SEQ START WITH 1 INCREMENT BY 1 NOCACHE"

DDL_TRIGGER = """
CREATE OR REPLACE TRIGGER YBIRO_MAP_PROFILE_BI
  BEFORE INSERT ON YBIRO_MAP_PROFILE FOR EACH ROW
  WHEN (NEW.id IS NULL)
BEGIN
  SELECT YBIRO_MAP_PROFILE_SEQ.NEXTVAL INTO :NEW.id FROM dual;
END;"""

DDL_TABLE_PARAM = """
CREATE TABLE YBIRO_MAP_PARAM (
  profile_id  NUMBER NOT NULL,
  param_name  VARCHAR2(30) NOT NULL,
  param_value VARCHAR2(200),
  CONSTRAINT pk_ybiro_map_param PRIMARY KEY (profile_id, param_name),
  CONSTRAINT fk_ybiro_map_param_prof FOREIGN KEY (profile_id)
    REFERENCES YBIRO_MAP_PROFILE(id)
)"""

SEED_BLOCK = """
DECLARE
  v_id NUMBER;
  PROCEDURE p(pn VARCHAR2, pv VARCHAR2) IS
  BEGIN
    INSERT INTO YBIRO_MAP_PARAM(profile_id, param_name, param_value)
    VALUES (v_id, pn, pv);
  END;
BEGIN
  INSERT INTO YBIRO_MAP_PROFILE (name, codprice, is_default) VALUES ('default', 1, '1');
  SELECT id INTO v_id FROM YBIRO_MAP_PROFILE WHERE name='default';
  p('tbl_goods','BIRO26_GOODS'); p('col_key','COD_UNIVERS'); p('col_id','ID');
  p('col_brand','BRAND'); p('col_articol','ARTICOL'); p('col_denumire','DENUMIRE');
  p('col_angro','ANGRO'); p('col_ionline','IONLINE'); p('col_retail','RETAIL1');
  p('seq_key','ID_TMS_UNIVERS'); p('codprice','1'); p('um','buc.');
  p('gr1','TVR'); p('tip','P'); p('caccess','11100'); p('codtva','A');
  p('date_start','2026-01-01'); p('date_end','3000-01-01'); p('group_type','P');
  p('empty_brand','NULL'); p('len_codvechi','20'); p('len_denumire','160');
  p('isarhiv_arc','1'); p('isarhiv_lock','2'); p('confus_max_cyr','3');
END;"""


def _run(db, label, sql, capture=False):
    if capture:
        r = db.call_proc(sql + ("" if sql.strip().endswith(";") else ";"))
    else:
        r = db.execute_dml(sql)
    ok = r.get("success")
    print(f"  [{'OK ' if ok else 'ERR'}] {label}" + ("" if ok else f" -> {r.get('message')}"))
    return ok


def main() -> int:
    db = Biro26DB()
    r = db.execute_query(
        "SELECT COUNT(*) FROM all_objects WHERE object_name='YBIRO_MAP_PROFILE'")
    if r["success"] and r["data"] and r["data"][0][0] > 0:
        print("YBIRO_MAP_PROFILE already exists — nothing to do (idempotent).")
        return 0

    print("Deploying Biro26 mapping tables to OfficePlus 11g...")
    steps = [
        ("table YBIRO_MAP_PROFILE", DDL_TABLE_PROFILE, False),
        ("sequence YBIRO_MAP_PROFILE_SEQ", DDL_SEQ, False),
        ("trigger YBIRO_MAP_PROFILE_BI", DDL_TRIGGER, True),
        ("table YBIRO_MAP_PARAM", DDL_TABLE_PARAM, False),
        ("seed default profile (25 params)", SEED_BLOCK, True),
    ]
    for label, sql, cap in steps:
        if not _run(db, label, sql, cap):
            print("Deployment FAILED.")
            return 1

    r = db.execute_query("SELECT COUNT(*) FROM YBIRO_MAP_PARAM")
    print(f"Done. YBIRO_MAP_PARAM rows = {r['data'][0][0] if r['success'] else '?'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
