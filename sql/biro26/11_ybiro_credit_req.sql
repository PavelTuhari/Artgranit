-- =====================================================================
-- RO: Biro26/OfficePlus — CERERILE de credit/rate din fereastra
--     produsului (flux bomba.md: tabel oferte + buton «Solicita in rate
--     sau credit» + formular Prenume/Nume/Telefon).
--     Integrarea cu organizatia are DOUA niveluri, comutabile per
--     organizatie prin YBIRO_CREDIT_ORG.ORG_MODE:
--       'manual' (minim)  — cererea se jurnalizeaza + notificare
--                           magazinului (managerul suna clientul);
--       'api'    (maxim)  — cererea se trimite si la API_URL-ul
--                           organizatiei (adaptor JSON, best-effort).
-- EN: credit/installment REQUESTS from the product window; two
--     integration levels switchable per organization (manual lead vs
--     API forward).
-- Prefix: YBIRO_. Charset CL8MSWIN1251 — kirilica prin python-oracledb.
-- =====================================================================

CREATE TABLE YBIRO_CREDIT_REQ (
  ID           NUMBER NOT NULL,
  ORG_ID       NUMBER,
  PLAN_ID      NUMBER,
  MONTHS       NUMBER,
  PRODUCT_COD  NUMBER,
  PRODUCT_NAME VARCHAR2(300),
  QTY          NUMBER DEFAULT 1,
  AMOUNT       NUMBER(12,2),          -- pret standard total
  CREDIT_PRICE NUMBER(12,2),          -- pret la credit (cu comision)
  MONTHLY      NUMBER(12,2),          -- rata lunara estimativa
  CLIENT_NAME  VARCHAR2(200),
  PHONE        VARCHAR2(40),
  STATUS       VARCHAR2(12) DEFAULT 'NEW',   -- NEW / PROCESSED
  API_SENT     VARCHAR2(1) DEFAULT '0',      -- trimis la API-ul organizatiei
  API_RESULT   VARCHAR2(400),
  CREATED      DATE DEFAULT SYSDATE,
  CONSTRAINT PK_YBIRO_CREDIT_REQ PRIMARY KEY (ID)
);
CREATE SEQUENCE YBIRO_CREDIT_REQ_SEQ START WITH 1 NOCACHE;
