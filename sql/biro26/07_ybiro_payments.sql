-- =====================================================================
-- RO: Biro26/OfficePlus — jurnalul platilor online din magazin:
--     MAIB e-commerce (card, redirect payUrl) si MIA instant payments
--     (QR dinamic prin QMoney/api.qiwi.md). Un rind per incercare de
--     plata; STATUS: PENDING -> PAID / FAILED.
-- EN: Online payment journal for the shop: MAIB e-commerce (card) and
--     MIA instant payments (dynamic QR). One row per payment attempt.
-- Prefix: YBIRO_. Charset DB: CL8MSWIN1251 — apply via python-oracledb.
-- =====================================================================

CREATE TABLE YBIRO_PAYMENTS (
  ID        NUMBER NOT NULL,
  DOC_COD   NUMBER NOT NULL,               -- TMDB_DOCS.COD (contul de plata)
  METHOD    VARCHAR2(10) NOT NULL,         -- 'maib' | 'mia'
  ORDER_ID  VARCHAR2(60) NOT NULL,         -- BIRO26-<doc>-<ts> (merchant/order id)
  PAY_ID    VARCHAR2(80),                  -- MAIB payId / MIA qrExtensionUUID
  AMOUNT    NUMBER(12,2),
  STATUS    VARCHAR2(12) DEFAULT 'PENDING',-- PENDING / PAID / FAILED
  RRN       VARCHAR2(40),                  -- MAIB retrieval reference number
  DETAILS   VARCHAR2(1000),
  CREATED   DATE DEFAULT SYSDATE,
  CONFIRMED DATE,
  CONSTRAINT PK_YBIRO_PAYMENTS PRIMARY KEY (ID)
);

CREATE INDEX IX_YBIRO_PAY_DOC   ON YBIRO_PAYMENTS (DOC_COD);
CREATE INDEX IX_YBIRO_PAY_ORDER ON YBIRO_PAYMENTS (ORDER_ID);

CREATE SEQUENCE YBIRO_PAYMENTS_SEQ START WITH 1 NOCACHE;
