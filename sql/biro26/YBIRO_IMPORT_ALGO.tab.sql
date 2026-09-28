-- =====================================================================
-- RO: Lista ALGORITMILOR de import, selectabila in back-office.
--     Pina acum algoritmul era implicit ("universal"); acum e o alegere
--     explicita a operatorului, iar fiecare algoritm isi declara ce face.
-- EN: The list of import ALGORITHMS, selectable in the back office.
--     Until now the algorithm was implicit; now it is an explicit choice.
--
-- ── De ce ── / ── Why ──
-- RO: Fisierele nu se mai potrivesc pe un singur tipar. Un pret-list are alt
--     algoritm decit un catalog cu foi-grupe sau decit o foaie de galerie.
--     Tabela face lista vizibila si extensibila fara sa se atinga codul.
-- EN: Files no longer fit one shape; this table makes the list visible and
--     extensible without touching code.
-- =====================================================================
SET SQLBLANKLINES ON

CREATE TABLE YBIRO_IMPORT_ALGO (
  ALGO_CODE    VARCHAR2(30)  NOT NULL,   -- RO: codul folosit in TMS_ORG_IMPSRC.ALGO_CODE
  ALGO_NAME    VARCHAR2(120) NOT NULL,   -- RO: denumirea pentru operator
  DESCR        VARCHAR2(1000),           -- RO: ce face, pe scurt
  SHEET_GROUP  NUMBER(1) DEFAULT 0 NOT NULL,  -- RO: 1 = numele FOII devine GRUPA
  CREATES_GOODS NUMBER(1) DEFAULT 1 NOT NULL, -- RO: 0 = nu creeaza marfa (doar actualizeaza)
  NEEDS_MAP    NUMBER(1) DEFAULT 0 NOT NULL,  -- RO: 1 = cere maparea manuala a coloanelor
  SORT_ORDER   NUMBER DEFAULT 100,
  ACTIVE       NUMBER(1) DEFAULT 1 NOT NULL,
  CONSTRAINT YBIRO_IMPORT_ALGO_PK PRIMARY KEY (ALGO_CODE)
);

COMMENT ON TABLE  YBIRO_IMPORT_ALGO IS 'RO: algoritmii de import selectabili in back-office / EN: import algorithms offered in the back office';
COMMENT ON COLUMN YBIRO_IMPORT_ALGO.SHEET_GROUP IS 'RO: 1 = numele foii Excel devine grupa de marfa';
COMMENT ON COLUMN YBIRO_IMPORT_ALGO.NEEDS_MAP   IS 'RO: 1 = operatorul trebuie sa confirme maparea coloanelor inainte de import';
