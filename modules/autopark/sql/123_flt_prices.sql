-- Autopark module: fuel price history (ANRE ceiling prices / model series).
-- Prefix: FLT_. Target database: platform cloud ADB (same as SDA/120-122).
-- Same PL/SQL-block fencing rule as sql/120_flt_tables.sql: '/' BEFORE and
-- AFTER the trigger block -- without the leading '/' the shared splitter
-- glues the preceding CREATE TABLE/INDEX into the same PL/SQL block.

-- Daily fuel price per product. SOURCE distinguishes a real ANRE ceiling
-- price from a synthesized model series used where real data could not
-- be retrieved -- never blended silently into one unlabeled number.
CREATE TABLE FLT_FUEL_PRICES (
  ID            NUMBER(12)    NOT NULL,
  PRICE_DATE    DATE          NOT NULL,
  PRODUCT_CODE  VARCHAR2(20)  NOT NULL,
  PRICE_LEI     NUMBER(8,2)   NOT NULL,
  SOURCE        VARCHAR2(20)  NOT NULL,
  CONSTRAINT PK_FLT_FUEL_PRICES PRIMARY KEY (ID),
  CONSTRAINT FK_FLT_PRICES_PRODUCT FOREIGN KEY (PRODUCT_CODE) REFERENCES FLT_PRODUCTS (CODE),
  CONSTRAINT UQ_FLT_FUEL_PRICES UNIQUE (PRICE_DATE, PRODUCT_CODE),
  CONSTRAINT CK_FLT_FUEL_PRICES_AMT CHECK (PRICE_LEI > 0),
  CONSTRAINT CK_FLT_FUEL_PRICES_SRC CHECK (SOURCE IN ('ANRE','MODEL'))
);
CREATE SEQUENCE SEQ_FLT_FUEL_PRICES START WITH 1 INCREMENT BY 1 CACHE 20;
/
CREATE OR REPLACE TRIGGER TRG_FLT_FUEL_PRICES_BI BEFORE INSERT ON FLT_FUEL_PRICES FOR EACH ROW
BEGIN IF :NEW.ID IS NULL THEN SELECT SEQ_FLT_FUEL_PRICES.NEXTVAL INTO :NEW.ID FROM DUAL; END IF; END;
/
CREATE INDEX IX_FLT_FUEL_PRICES_DATE ON FLT_FUEL_PRICES (PRICE_DATE);
CREATE INDEX IX_FLT_FUEL_PRICES_PRODUCT ON FLT_FUEL_PRICES (PRODUCT_CODE);
