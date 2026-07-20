-- =====================================================================
-- RO: Biro26/OfficePlus — achitare prin CREDITARE (rate):
--     lista DINAMICA a organizatiilor de creditare + pachetele lor.
--     MODE='manual' (conditii setate in admin) sau 'api' (integrare API
--     cu organizatia — URL-ul se seteaza, adaptorul per organizatie).
--     Calculul pretului la CREDIT: pret_credit = pret * (1 + MARKUP_PCT%)
--     (comisionul magazinului la pachetele 0%); rata lunara estimativa =
--     finantat/luni + finantat*(ANNUAL_PCT/12/100) + finantat*MONTHLY_FEE_PCT/100;
--     total = avans + rate*luni + ISSUE_FEE.
--     Sursa conditiilor: TaskDezvoltare/1 credite (tabelul EASYCREDIT).
-- EN: credit-payment module: dynamic list of credit organizations and
--     their plans (manual conditions or API integration); credit-mode
--     price recalculation via the store-commission markup.
-- Prefix: YBIRO_. Charset CL8MSWIN1251 — kirilica DOAR prin python-oracledb.
-- =====================================================================

CREATE TABLE YBIRO_CREDIT_ORG (
  ID        NUMBER NOT NULL,
  NAME      VARCHAR2(100) NOT NULL,       -- ex. EasyCredit
  ENABLED   VARCHAR2(1) DEFAULT '1',
  ORG_MODE  VARCHAR2(10) DEFAULT 'manual',-- 'manual' | 'api' (MODE e cuvint rezervat)
  API_URL   VARCHAR2(400),                -- pentru MODE='api'
  LOGO_URL  VARCHAR2(400),
  INFO      VARCHAR2(2000),               -- descriere/conditii afisate
  ORD       NUMBER DEFAULT 0,
  CONSTRAINT PK_YBIRO_CREDIT_ORG PRIMARY KEY (ID)
);
CREATE SEQUENCE YBIRO_CREDIT_ORG_SEQ START WITH 1 NOCACHE;

CREATE TABLE YBIRO_CREDIT_PLAN (
  ID              NUMBER NOT NULL,
  ORG_ID          NUMBER NOT NULL,
  NAME            VARCHAR2(120) NOT NULL, -- ex. Special 0% / 6 luni
  MONTHS_MIN      NUMBER NOT NULL,        -- termen fix => MIN = MAX
  MONTHS_MAX      NUMBER NOT NULL,
  AMOUNT_MIN      NUMBER DEFAULT 1000,
  AMOUNT_MAX      NUMBER DEFAULT 100000,
  MARKUP_PCT      NUMBER DEFAULT 0,       -- comision magazin -> majorare pret
  ANNUAL_PCT      NUMBER DEFAULT 0,       -- dobinda anuala (clientul)
  MONTHLY_FEE_PCT NUMBER DEFAULT 0,       -- comision lunar (clientul)
  ISSUE_FEE       NUMBER DEFAULT 0,       -- taxa de emitere, lei
  AVANS_MIN_PCT   NUMBER DEFAULT 0,
  ENABLED         VARCHAR2(1) DEFAULT '1',
  INFO            VARCHAR2(2000),
  CONSTRAINT PK_YBIRO_CREDIT_PLAN PRIMARY KEY (ID)
);
CREATE SEQUENCE YBIRO_CREDIT_PLAN_SEQ START WITH 1 NOCACHE;
CREATE INDEX IX_YBIRO_CRPLAN_ORG ON YBIRO_CREDIT_PLAN (ORG_ID);

-- RO: metadatele creditului pe documentul creat (extinde YBIRO_DOC_META)
ALTER TABLE YBIRO_DOC_META ADD (
  CREDIT_PLAN_ID NUMBER,
  CREDIT_MONTHS  NUMBER,
  CREDIT_AVANS   NUMBER
);
