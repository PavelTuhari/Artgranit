-- =====================================================================
-- Biro26: LIMITED ADMIN al vitrinei noului site Figma (shop1 / TZ par.6)
-- RO: doar continutul vitrinei (hero slides, "produsul zilei", sectiuni
--     ale paginii principale) — NU marfa/preturi (acelea raman in ERP) si
--     NU texte informative (acelea raman in WordPress).
-- EN: storefront-only content for the new Figma site homepage.
-- Prefix: YBIRO_SITE_. Charset CL8MSWIN1251 — ASCII only in DDL.
-- =====================================================================

CREATE TABLE YBIRO_SITE_HERO (
  ID        NUMBER NOT NULL,
  KICKER_RO VARCHAR2(200),
  KICKER_RU VARCHAR2(200),
  TITLE_RO  VARCHAR2(400),               -- poate contine <br>
  TITLE_RU  VARCHAR2(400),
  SUB_RO    VARCHAR2(400),
  SUB_RU    VARCHAR2(400),
  CTA_URL   VARCHAR2(400),               -- ex. /catalog?grupa=...
  BG        VARCHAR2(240),               -- CSS background (gradient/culoare)
  ORD       NUMBER DEFAULT 0,
  ENABLED   VARCHAR2(1) DEFAULT '1',
  CONSTRAINT PK_YBIRO_SITE_HERO PRIMARY KEY (ID)
);
CREATE SEQUENCE YBIRO_SITE_HERO_SEQ START WITH 1 NOCACHE;

CREATE TABLE YBIRO_SITE_DEAL (
  ID          NUMBER NOT NULL,
  PRODUCT_COD NUMBER,                    -- COD din TMS_UNIVERS (ERP)
  ENDS_AT     DATE,                      -- termenul cronometrului
  ENABLED     VARCHAR2(1) DEFAULT '1',
  CONSTRAINT PK_YBIRO_SITE_DEAL PRIMARY KEY (ID)
);
CREATE SEQUENCE YBIRO_SITE_DEAL_SEQ START WITH 1 NOCACHE;

CREATE TABLE YBIRO_SITE_SECTION (
  ID      NUMBER NOT NULL,
  CODE    VARCHAR2(40) NOT NULL,         -- categories/best/popular/brands/tabs/about/contact
  ENABLED VARCHAR2(1) DEFAULT '1',
  ORD     NUMBER DEFAULT 0,
  CONSTRAINT PK_YBIRO_SITE_SECTION PRIMARY KEY (ID),
  CONSTRAINT UQ_YBIRO_SITE_SECTION UNIQUE (CODE)
);
CREATE SEQUENCE YBIRO_SITE_SECTION_SEQ START WITH 1 NOCACHE;

INSERT INTO YBIRO_SITE_SECTION (ID, CODE, ENABLED, ORD) VALUES (YBIRO_SITE_SECTION_SEQ.NEXTVAL, 'categories', '1', 1);
INSERT INTO YBIRO_SITE_SECTION (ID, CODE, ENABLED, ORD) VALUES (YBIRO_SITE_SECTION_SEQ.NEXTVAL, 'best', '1', 2);
INSERT INTO YBIRO_SITE_SECTION (ID, CODE, ENABLED, ORD) VALUES (YBIRO_SITE_SECTION_SEQ.NEXTVAL, 'popular', '1', 3);
INSERT INTO YBIRO_SITE_SECTION (ID, CODE, ENABLED, ORD) VALUES (YBIRO_SITE_SECTION_SEQ.NEXTVAL, 'brands', '1', 4);
INSERT INTO YBIRO_SITE_SECTION (ID, CODE, ENABLED, ORD) VALUES (YBIRO_SITE_SECTION_SEQ.NEXTVAL, 'tabs', '1', 5);
INSERT INTO YBIRO_SITE_SECTION (ID, CODE, ENABLED, ORD) VALUES (YBIRO_SITE_SECTION_SEQ.NEXTVAL, 'about', '1', 6);
INSERT INTO YBIRO_SITE_SECTION (ID, CODE, ENABLED, ORD) VALUES (YBIRO_SITE_SECTION_SEQ.NEXTVAL, 'contact', '1', 7);
COMMIT;
