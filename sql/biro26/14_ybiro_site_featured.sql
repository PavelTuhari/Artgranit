-- =====================================================================
-- Biro26: lista de produse pentru capitolul "Cele mai populare" al
-- paginii principale (setata manual in backoffice / limited admin).
-- RO: goala = sectiunea cade inapoi pe esantionul automat din catalog.
-- Prefix: YBIRO_SITE_. ASCII only (CL8MSWIN1251).
-- =====================================================================

CREATE TABLE YBIRO_SITE_FEATURED (
  ID          NUMBER NOT NULL,
  PRODUCT_COD NUMBER NOT NULL,            -- COD din TMS_UNIVERS (ERP)
  ORD         NUMBER DEFAULT 0,
  CONSTRAINT PK_YBIRO_SITE_FEATURED PRIMARY KEY (ID)
);
CREATE SEQUENCE YBIRO_SITE_FEATURED_SEQ START WITH 1 NOCACHE;
