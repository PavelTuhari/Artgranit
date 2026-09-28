-- ============================================================================
-- ServOuts26 front-office (magazin de servicii) — obiecte proprii (prefix SRVO)
-- ServOuts26 front-office (services storefront) — module-owned objects (SRVO)
--
-- RO: clientii si comenzile magazinului traiesc in tabele normalizate proprii
--     ale modulului; TMDB_* (nucleul contabil ERP) NU se atinge in faza 1
--     (vezi TZ §10.3 — necesita obследование separat).
-- EN: shop clients and orders live in the module's own normalized tables;
--     the ERP accounting core TMDB_* is NOT touched in phase 1 (TZ §10.3).
-- ============================================================================

-- RO: clientii magazinului (cont personal); parola doar ca hash.
-- EN: storefront clients (personal cabinet); password stored as hash only.
CREATE TABLE SRVO_CLIENT (
  ID          NUMBER        NOT NULL,
  EMAIL       VARCHAR2(120) NOT NULL,
  FULL_NAME   VARCHAR2(160) NOT NULL,
  PHONE       VARCHAR2(40),
  PWD_HASH    VARCHAR2(200) NOT NULL,
  ADDRESS     VARCHAR2(400),
  IDNO        VARCHAR2(20),
  IS_COMPANY  VARCHAR2(1) DEFAULT '0',
  CREATED_AT  DATE DEFAULT SYSDATE,
  CONSTRAINT SRVO_CLIENT_PK PRIMARY KEY (ID),
  CONSTRAINT SRVO_CLIENT_EMAIL_UK UNIQUE (EMAIL)
)
/

CREATE SEQUENCE SRVO_CLIENT_SEQ START WITH 1 NOCACHE
/

-- RO: comenzile de servicii (abonamente/pachete de contabilitate).
-- EN: service orders (accounting subscriptions/packages).
CREATE TABLE SRVO_ORDERS (
  ORDER_ID    NUMBER        NOT NULL,
  ORDER_NO    VARCHAR2(20)  NOT NULL,
  CLIENT_ID   NUMBER        NOT NULL,
  STATUS      VARCHAR2(16) DEFAULT 'NEW' NOT NULL,
  TOTAL       NUMBER(14,2) DEFAULT 0 NOT NULL,
  CURRENCY    VARCHAR2(3)  DEFAULT 'LEI' NOT NULL,
  NOTE        VARCHAR2(500),
  CREATED_AT  DATE DEFAULT SYSDATE,
  UPDATED_AT  DATE,
  CONSTRAINT SRVO_ORDERS_PK PRIMARY KEY (ORDER_ID),
  CONSTRAINT SRVO_ORDERS_NO_UK UNIQUE (ORDER_NO),
  CONSTRAINT SRVO_ORDERS_CLIENT_FK FOREIGN KEY (CLIENT_ID)
    REFERENCES SRVO_CLIENT (ID),
  CONSTRAINT SRVO_ORDERS_STATUS_CK CHECK
    (STATUS IN ('NEW','CONFIRMED','IN_WORK','DONE','CANCELED'))
)
/

CREATE SEQUENCE SRVO_ORDERS_SEQ START WITH 1 NOCACHE
/

-- RO: liniile comenzii; SC = TMS_UNIVERS.COD al serviciului; pretul este
--     cel autoritar de pe server (pricelist-ul modulului) la momentul comenzii.
-- EN: order lines; SC = the service's TMS_UNIVERS.COD; the price is the
--     server-side authoritative pricelist value at order time.
CREATE TABLE SRVO_ORDER_ITEMS (
  ORDER_ID  NUMBER        NOT NULL,
  LINE_NO   NUMBER        NOT NULL,
  SC        NUMBER        NOT NULL,
  NAME      VARCHAR2(200),
  QTY       NUMBER(12,3) DEFAULT 1 NOT NULL,
  PRICE     NUMBER(14,2) DEFAULT 0 NOT NULL,
  SUMA      NUMBER(14,2) DEFAULT 0 NOT NULL,
  CONSTRAINT SRVO_ORDER_ITEMS_PK PRIMARY KEY (ORDER_ID, LINE_NO),
  CONSTRAINT SRVO_ORDER_ITEMS_ORD_FK FOREIGN KEY (ORDER_ID)
    REFERENCES SRVO_ORDERS (ORDER_ID)
)
/
