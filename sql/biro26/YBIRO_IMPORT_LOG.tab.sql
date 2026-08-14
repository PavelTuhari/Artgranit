-- =====================================================================
-- RO: Jurnalul importurilor + marcajul de sursa pe fiecare cartela.
--     Cerut de pasaportul fisierului officeshop (README-for-AI §3.1 si §3.3).
-- EN: Import journal + per-card source marker.
--     Required by the officeshop file passport (README-for-AI §3.1 and §3.3).
--
-- ── De ce ── / ── Why ──
-- RO: Pina acum nu se putea raspunde la intrebarea "de unde a aparut cartela
--     asta si din ce rind de fisier?". Cu aceste doua tabele, orice marfa
--     creata de import isi cunoaste sursa, rularea si rindul exact din Excel.
-- EN: Until now there was no way to answer "where did this card come from, and
--     from which file row?". These two tables give every imported product its
--     source, its import run and its exact spreadsheet row.
-- =====================================================================
SET SQLBLANKLINES ON

CREATE SEQUENCE YBIRO_IMPORT_LOG_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE TABLE YBIRO_IMPORT_LOG (
  IMPORT_ID     NUMBER        NOT NULL PRIMARY KEY,   -- RO: din YBIRO_IMPORT_LOG_SEQ
  SOURCE_CODE   VARCHAR2(30)  NOT NULL,   -- RO: = TMS_ORG_IMPSRC.SRC_CODE
  SRC_FILE      VARCHAR2(500) NOT NULL,   -- RO: numele/calea fisierului + data lui
  LOAD_ID       NUMBER,                   -- RO: = BIRO26PT_FILE.LOAD_ID
  STARTED_AT    TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
  FINISHED_AT   TIMESTAMP,
  ROWS_TOTAL    NUMBER,
  ROWS_INSERTED NUMBER,                   -- RO: cartele create
  ROWS_UPDATED  NUMBER,                   -- RO: cartele actualizate
  ROWS_MATCHED  NUMBER,                   -- RO: cartele existente gasite
  ROWS_SKIPPED  NUMBER,                   -- RO: randuri sarite (ambigue / fara articol)
  NOTES         VARCHAR2(2000)
);

COMMENT ON TABLE YBIRO_IMPORT_LOG IS 'RO: jurnalul rularilor de import; fiecare cartela creata trimite la IMPORT_ID / EN: import run journal';

-- =====================================================================
-- RO: Marcajul de sursa al cartelei — satelit 1:1 al dictionarului de marfa,
--     aceeasi schema de cheie ca TMS_MPT (COD = PK si FK catre TMS_UNIVERS).
-- EN: The card source marker — 1:1 satellite, same key schema as TMS_MPT.
-- =====================================================================
CREATE TABLE TMS_MPT_IMPSRC (
  COD             NUMBER        NOT NULL,   -- RO: = TMS_UNIVERS.COD
  SRC_SOURCE_CODE VARCHAR2(30)  NOT NULL,   -- RO: sursa: 'OFFICESHOP_MERGED' etc.
  SRC_IMPORT_ID   NUMBER,                   -- RO: = YBIRO_IMPORT_LOG.IMPORT_ID
  SRC_ROW_GUID    VARCHAR2(64),             -- RO: guid-ul rindului din fisier (guid_angro, altfel guid_retail)
  SRC_PID         VARCHAR2(40),             -- RO: ID-ul intern al produsului pe site (cheia de reimport)
  SRC_ID_1C       VARCHAR2(40),             -- RO: codul 1C al furnizorului (= numele fisierelor de imagini)
  SRC_ARTICOL     VARCHAR2(60),             -- RO: articolul EXACT din sursa, inainte de prefixare
  SRC_GROUP_PATH  VARCHAR2(400),            -- RO: calea completa de grupe din sursa (3-4 niveluri)
  MATCH_STATUS    VARCHAR2(20),             -- RO: both | retail_only | angro_only
  UPDATED_AT      DATE          DEFAULT SYSDATE,
  CONSTRAINT TMS_MPT_IMPSRC_PK PRIMARY KEY (COD),
  CONSTRAINT TMS_MPT_IMPSRC_FK FOREIGN KEY (COD) REFERENCES TMS_UNIVERS (COD)
);

CREATE INDEX TMS_MPT_IMPSRC_IX_PID ON TMS_MPT_IMPSRC (SRC_SOURCE_CODE, SRC_PID);
CREATE INDEX TMS_MPT_IMPSRC_IX_IMP ON TMS_MPT_IMPSRC (SRC_IMPORT_ID);

COMMENT ON TABLE  TMS_MPT_IMPSRC IS 'RO: din ce sursa, ce rulare si ce rind de fisier provine cartela / EN: which source, run and file row this card came from';
COMMENT ON COLUMN TMS_MPT_IMPSRC.SRC_PID     IS 'RO: cheia de idempotenta la reimportul aceleiasi surse';
COMMENT ON COLUMN TMS_MPT_IMPSRC.SRC_ARTICOL IS 'RO: articolul original, inainte de prefixare (vezi GHID 9.23)';
