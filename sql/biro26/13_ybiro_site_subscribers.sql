-- =====================================================================
-- Biro26: abonatii newsletter ai noului site Figma (TZ - footer/newsletter)
-- RO: stocare normalizata Oracle (nu localStorage/fisiere) — Phase "newsletter
--     backend". Adminul vede lista in limited admin (biro26-site-admin).
-- Prefix: YBIRO_SITE_. ASCII only (CL8MSWIN1251).
-- =====================================================================

CREATE TABLE YBIRO_SITE_SUBSCRIBER (
  ID      NUMBER NOT NULL,
  EMAIL   VARCHAR2(200) NOT NULL,
  LANG    VARCHAR2(4) DEFAULT 'ro',
  CREATED DATE DEFAULT SYSDATE,
  ENABLED VARCHAR2(1) DEFAULT '1',       -- '0' = dezabonat
  CONSTRAINT PK_YBIRO_SITE_SUBSCRIBER PRIMARY KEY (ID),
  CONSTRAINT UQ_YBIRO_SITE_SUBSCRIBER UNIQUE (EMAIL)
);
CREATE SEQUENCE YBIRO_SITE_SUBSCRIBER_SEQ START WITH 1 NOCACHE;
