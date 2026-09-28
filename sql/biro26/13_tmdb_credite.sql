-- =====================================================================
-- RO: Cererile de credit ca DOCUMENTE separate, dupa principiul
--     TMDB_ST201M/D, dar cu coloane PLATE (fara tipul obiect UN$CM).
--     Documentul se inregistreaza in TMDB_DOCS cu NRSET = 201
--     (strat managerial; 301 = contabil) si pastreaza in DOC_COD_ORDER
--     COD-ul documentului de comanda/cont din TMDB_DOCS.
-- EN: credit requests as separate documents (flat columns), registered in
--     TMDB_DOCS with NRSET = 201 and linked to the order document.
-- Decizii proprietar 2026-08-01: docs/superpowers/specs/2026-08-01-credite-documents-spec.md
-- Charset CL8MSWIN1251 — chirilica DOAR prin python-oracledb.
-- =====================================================================

CREATE TABLE TMDB_CREDITE_M (
  COD             NUMBER NOT NULL,          -- = TMDB_DOCS.COD (documentul de credit)
  DOC_COD_ORDER   NUMBER,                   -- = TMDB_DOCS.COD al comenzii/contului
  CLIENT_COD      NUMBER,                   -- TMS_UNIVERS.COD (clientul magazinului)
  NNP             VARCHAR2(200),            -- nume, prenume, patronimic
  IDNP            VARCHAR2(20),             -- IDNP / IDNO (mascat la nevoie)
  PHONE           VARCHAR2(40),
  ADRESA          VARCHAR2(300),            -- domiciliu sau juridica
  BIRTH_DATE      DATE,
  ORG_ID          NUMBER,                   -- TMS_CREDITE_ORG.ID
  ORG_NAME        VARCHAR2(100),
  PLAN_ID         NUMBER,                   -- TMS_CREDITE_PLAN.ID
  PLAN_NAME       VARCHAR2(120),
  MONTHS          NUMBER,
  AVANS           NUMBER,
  AMOUNT          NUMBER,                   -- pretul standard
  CREDIT_PRICE    NUMBER,                   -- pretul in rate (naceta activa)
  MONTHLY         NUMBER,
  PROVIDER_CODE   VARCHAR2(30),             -- easycredit / iute / NULL (manual)
  EXT_REF         VARCHAR2(120),            -- URN / order id la creditor
  API_STATUS      VARCHAR2(60),
  REQ_ID          NUMBER,                   -- TMS_CREDITE_REQ.ID (cererea tehnica)
  CREATED         DATE DEFAULT SYSDATE,
  CONSTRAINT PK_TMDB_CREDITE_M PRIMARY KEY (COD)
);
CREATE INDEX IX_TMDB_CREDITE_M_ORD ON TMDB_CREDITE_M (DOC_COD_ORDER);
CREATE INDEX IX_TMDB_CREDITE_M_CLI ON TMDB_CREDITE_M (CLIENT_COD);

CREATE TABLE TMDB_CREDITE_D (
  COD        NUMBER NOT NULL,               -- = TMDB_CREDITE_M.COD
  COD1       NUMBER NOT NULL,               -- numarul rindului
  SC         NUMBER,                        -- TMS_UNIVERS.COD (marfa)
  DENUMIREA  VARCHAR2(300),
  UM         VARCHAR2(20),
  CANT       NUMBER,
  PRET       NUMBER,                        -- pretul standard, per unitate
  PRET_CREDIT NUMBER,                       -- pretul in rate, per unitate
  SUMA       NUMBER,
  TXTCOMENT  VARCHAR2(250),
  CONSTRAINT PK_TMDB_CREDITE_D PRIMARY KEY (COD, COD1)
);
CREATE INDEX IX_TMDB_CREDITE_D_SC ON TMDB_CREDITE_D (SC);

-- RO: vederile — acelasi rol ca VMDB_ST201M/D: date gata de afisat in grid
CREATE OR REPLACE VIEW VMDB_CREDITE_M AS
SELECT m.COD, m.DOC_COD_ORDER, m.CLIENT_COD, m.NNP, m.IDNP, m.PHONE, m.ADRESA,
       m.BIRTH_DATE, m.ORG_ID, m.ORG_NAME, m.PLAN_ID, m.PLAN_NAME, m.MONTHS,
       m.AVANS, m.AMOUNT, m.CREDIT_PRICE, m.MONTHLY, m.PROVIDER_CODE,
       m.EXT_REF, m.API_STATUS, m.REQ_ID, m.CREATED,
       d.NRMANUAL, d.DATAMANUAL, d.NRSET, d.STATUS AS DOC_STATUS,
       o.NRMANUAL AS ORDER_NRMANUAL,
       (SELECT u.DENUMIREA__1 FROM VMS_UNIVERS u WHERE u.COD = m.CLIENT_COD) CLIENT_NAME,
       (SELECT COUNT(*) FROM TMDB_CREDITE_D x WHERE x.COD = m.COD) LINES
  FROM TMDB_CREDITE_M m
  LEFT JOIN TMDB_DOCS d ON d.COD = m.COD
  LEFT JOIN TMDB_DOCS o ON o.COD = m.DOC_COD_ORDER;

CREATE OR REPLACE VIEW VMDB_CREDITE_D AS
SELECT l.COD AS NRDOC, l.COD1, l.SC, l.DENUMIREA, l.UM, l.CANT,
       l.PRET, l.PRET_CREDIT, l.SUMA, l.TXTCOMENT,
       (SELECT u.CODVECHI FROM TMS_UNIVERS u WHERE u.COD = l.SC) CODVECHI
  FROM TMDB_CREDITE_D l;
