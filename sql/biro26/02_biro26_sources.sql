-- =====================================================================
-- Biro26 source definitions (any read-only SELECT -> view).
-- RO: Definitii de surse: orice SELECT read-only devine o vedere importabila.
-- EN: Source definitions: any read-only SELECT becomes an importable view.
-- RO/EN comments only (project rule). Target: officeplus (Oracle 11g).
-- Oracle 11g: cheie prin secventa + trigger (fara IDENTITY).
-- Run: sqlplus officeplus/<pwd>@orange.una.md:4024/cloudbd.world @02_biro26_sources.sql
--   or: ./venv/bin/python deploy_biro26_sources.py
-- =====================================================================

CREATE TABLE YBIRO_SRC_DEF (
  id          NUMBER PRIMARY KEY,        -- RO: id sursa / EN: source id (via sequence)
  name        VARCHAR2(60) NOT NULL,     -- RO: nume sursa / EN: source name
  select_sql  CLOB,                       -- RO: interogarea / EN: the SELECT query
  view_name   VARCHAR2(40),              -- RO: vederea creata / EN: created view
  md_path     VARCHAR2(200),             -- RO: fisier descriere / EN: description file
  created_at  TIMESTAMP DEFAULT SYSTIMESTAMP,
  created_by  VARCHAR2(60) DEFAULT USER,
  CONSTRAINT uq_ybiro_src_def_name UNIQUE (name)
);

CREATE SEQUENCE YBIRO_SRC_DEF_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE OR REPLACE TRIGGER YBIRO_SRC_DEF_BI
  BEFORE INSERT ON YBIRO_SRC_DEF FOR EACH ROW WHEN (NEW.id IS NULL)
BEGIN
  -- RO: completeaza cheia din secventa / EN: fill key from the sequence
  SELECT YBIRO_SRC_DEF_SEQ.NEXTVAL INTO :NEW.id FROM dual;
END;
/
