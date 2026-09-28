-- =====================================================================
-- Biro26 stock-balance calculation cache.
-- RO: Rezultatul calculului de sold (UN$SOLD.GET_SOLDT) e o vedere GTT
--     valabila doar in sesiunea Oracle care a calculat-o. Aici pastram
--     rezultatul intr-un tabel normal (permanent), ca sa poata fi
--     citit rapid din orice sesiune ulterioara ("ultimul calcul").
-- EN: UN$SOLD.GET_SOLDT's result is a Global Temporary Table, visible
--     only in the Oracle session that computed it. We persist the
--     result into a normal (permanent) table so any later session/
--     request can read it quickly ("last calculation").
-- RO/EN comments only (project rule). Target: officeplus (Oracle 11g).
-- Run: sqlplus officeplus/<pwd>@orange.una.md:4024/cloudbd.world @03_biro26_stock_tables.sql
--   or: ./venv/bin/python deploy_biro26_stock_tables.py
-- =====================================================================

CREATE TABLE YBIRO_STOCK_CALC (
  id           NUMBER PRIMARY KEY,          -- via secventa+trigger (11g)
  run_at       TIMESTAMP DEFAULT SYSTIMESTAMP,
  data_doc     DATE,                        -- RO: data documentului (:datadoc) / EN: as-of date used
  dep_filter   VARCHAR2(60),                -- RO: filtru departament (:m_ctdep) / EN: department filter used
  cont_filter  VARCHAR2(60),                -- RO: conturi (pCont) / EN: GL accounts used
  pfilt        VARCHAR2(30),                -- RO: masca filtru (pFilt) / EN: filter mask used
  src_table    VARCHAR2(100),               -- RO: numele GTT generat de GET_SOLDT / EN: GTT name returned
  row_count    NUMBER DEFAULT 0,
  is_latest    VARCHAR2(1) DEFAULT '1',     -- '1' = ultimul calcul valabil / latest valid run
  status       VARCHAR2(10) DEFAULT 'OK',   -- OK / ERROR
  err_text     VARCHAR2(2000),
  created_by   VARCHAR2(60) DEFAULT USER
);

CREATE SEQUENCE YBIRO_STOCK_CALC_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE OR REPLACE TRIGGER YBIRO_STOCK_CALC_BI
  BEFORE INSERT ON YBIRO_STOCK_CALC FOR EACH ROW WHEN (NEW.id IS NULL)
BEGIN
  SELECT YBIRO_STOCK_CALC_SEQ.NEXTVAL INTO :NEW.id FROM dual;
END;
/

CREATE TABLE YBIRO_STOCK_CALC_ITEM (
  calc_id  NUMBER NOT NULL,                 -- RO: id calcul / EN: calc run id
  sc       NUMBER NOT NULL,                 -- RO: subconto = cod marfa (TMS_UNIVERS.COD) / EN: item code
  dep      NUMBER,                          -- RO: departament / EN: department
  cant     NUMBER,                          -- RO: cantitate sold / EN: balance quantity
  cant1    NUMBER,                          -- RO: cantitate UM2 / EN: secondary-unit quantity
  CONSTRAINT pk_ybiro_stock_item PRIMARY KEY (calc_id, sc, dep),
  CONSTRAINT fk_ybiro_stock_item_calc FOREIGN KEY (calc_id)
    REFERENCES YBIRO_STOCK_CALC(id)
);

-- RO: index pentru JOIN rapid cu nomenclatorul (grid produs+stoc)
-- EN: index for a fast JOIN against the dictionary (product+stock grid)
CREATE INDEX IX_YBIRO_STOCK_ITEM_SC ON YBIRO_STOCK_CALC_ITEM(sc);
