-- =====================================================================
-- RO: Biro26/OfficePlus — descrierea produsului si comentariile
--     clientilor pentru fereastra mare de produs din magazin + fisa
--     din backoffice.
-- EN: Biro26/OfficePlus — product description and client comments
--     backing the shop's large product window + the backoffice card.
-- Prefix: YBIRO_ (obiectele aplicatiei web in schema officeplus).
-- Charset DB: CL8MSWIN1251 — a se aplica prin python-oracledb (nu SQLcl).
-- =====================================================================

-- RO: descrierea produsului (1 rind per COD din TMS_UNIVERS)
-- EN: product description (1 row per TMS_UNIVERS COD)
CREATE TABLE YBIRO_PROD_INFO (
  COD        NUMBER NOT NULL,
  DESCRIERE  VARCHAR2(4000),
  UPDATED    DATE DEFAULT SYSDATE,
  CONSTRAINT PK_YBIRO_PROD_INFO PRIMARY KEY (COD)
);

-- RO: comentariile clientilor (autor = clientul magazinului sau operator)
-- EN: client comments (author = shop client or backoffice operator)
CREATE TABLE YBIRO_PROD_COMMENTS (
  ID         NUMBER NOT NULL,
  COD        NUMBER NOT NULL,
  AUTOR      VARCHAR2(200),
  CLIENT_COD NUMBER,
  TXT        VARCHAR2(2000) NOT NULL,
  CREATED    DATE DEFAULT SYSDATE,
  CONSTRAINT PK_YBIRO_PROD_COMMENTS PRIMARY KEY (ID)
);

CREATE INDEX IX_YBIRO_PCOM_COD ON YBIRO_PROD_COMMENTS (COD);

CREATE SEQUENCE YBIRO_PROD_COMMENTS_SEQ START WITH 1 NOCACHE;
