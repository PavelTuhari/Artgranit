-- =====================================================================
-- Biro26 application tables (mapping profiles)
-- RO: Profile de mapare pentru variabilele g_* ale pachetului YBIRO_Import_Marfa.
-- EN: Mapping profiles for the YBIRO_Import_Marfa package g_* variables.
-- RO/EN: Comentarii numai RO + EN (regula proiectului) / comments RO + EN only.
-- Target DB: officeplus@orange.una.md:4024/cloudbd.world (Oracle 11g, NOT the wallet DB).
-- Oracle 11g: fara IDENTITY/FETCH; cheia prin secventa + trigger.
--             no IDENTITY/FETCH; key via sequence + trigger.
-- Run (sqlplus): sqlplus officeplus/<pwd>@orange.una.md:4024/cloudbd.world @01_biro26_app_tables.sql
-- Or via the app worker: python deploy_biro26_app_tables.py (executes the statements below).
-- =====================================================================

CREATE TABLE YBIRO_MAP_PROFILE (
  id          NUMBER PRIMARY KEY,        -- RO: id profil / EN: profile id (via sequence)
  name        VARCHAR2(60) NOT NULL,     -- RO: nume profil / EN: profile name
  codprice    NUMBER,                    -- RO: lista de preturi / EN: price list code
  is_default  VARCHAR2(1) DEFAULT '0',   -- RO: profil implicit / EN: default ('1'/'0')
  created_at  TIMESTAMP DEFAULT SYSTIMESTAMP,
  created_by  VARCHAR2(60) DEFAULT USER,
  CONSTRAINT uq_ybiro_map_profile_name UNIQUE (name)
);

CREATE SEQUENCE YBIRO_MAP_PROFILE_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE OR REPLACE TRIGGER YBIRO_MAP_PROFILE_BI
  BEFORE INSERT ON YBIRO_MAP_PROFILE FOR EACH ROW
  WHEN (NEW.id IS NULL)
BEGIN
  -- RO: completeaza cheia din secventa / EN: fill key from the sequence
  SELECT YBIRO_MAP_PROFILE_SEQ.NEXTVAL INTO :NEW.id FROM dual;
END;
/

CREATE TABLE YBIRO_MAP_PARAM (
  profile_id  NUMBER NOT NULL,           -- RO: profil / EN: profile
  param_name  VARCHAR2(30) NOT NULL,     -- RO: nume g_* (fara prefix g_) / EN: g_* name (no g_)
  param_value VARCHAR2(200),             -- RO: valoare / EN: value
  CONSTRAINT pk_ybiro_map_param PRIMARY KEY (profile_id, param_name),
  CONSTRAINT fk_ybiro_map_param_prof FOREIGN KEY (profile_id)
    REFERENCES YBIRO_MAP_PROFILE(id)
);

-- RO: Profil implicit din valorile din antetul pachetului (TZ §4 / §7.1)
-- EN: Default profile seeded from the package header defaults (TZ §4 / §7.1)
INSERT INTO YBIRO_MAP_PROFILE (name, codprice, is_default) VALUES ('default', 1, '1');

DECLARE
  v_id NUMBER;
  PROCEDURE p(pn VARCHAR2, pv VARCHAR2) IS
  BEGIN
    INSERT INTO YBIRO_MAP_PARAM(profile_id, param_name, param_value)
    VALUES (v_id, pn, pv);
  END;
BEGIN
  SELECT id INTO v_id FROM YBIRO_MAP_PROFILE WHERE name='default';
  p('tbl_goods','BIRO26_GOODS'); p('col_key','COD_UNIVERS'); p('col_id','ID');
  p('col_brand','BRAND'); p('col_articol','ARTICOL'); p('col_denumire','DENUMIRE');
  p('col_angro','ANGRO'); p('col_ionline','IONLINE'); p('col_retail','RETAIL1');
  p('seq_key','ID_TMS_UNIVERS'); p('codprice','1'); p('um','buc.');
  p('gr1','TVR'); p('tip','P'); p('caccess','11100'); p('codtva','A');
  p('date_start','2026-01-01'); p('date_end','3000-01-01'); p('group_type','P');
  p('empty_brand','NULL'); p('len_codvechi','20'); p('len_denumire','160');
  p('isarhiv_arc','1'); p('isarhiv_lock','2'); p('confus_max_cyr','3');
END;
/
COMMIT;
