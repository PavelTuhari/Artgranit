-- =====================================================================
-- RO: Biro26/OfficePlus — cimpuri noi OBLIGATORII la inregistrarea
--     clientilor magazinului: adresa de livrare, telefon (deja exista),
--     IDNO + marcaj "persoana juridica" (IDNO obligatoriu pentru juridice).
-- EN: Biro26/OfficePlus — new MANDATORY sign-up fields for shop clients:
--     delivery address, IDNO + legal-entity flag (IDNO required for them).
-- Prefix: YBIRO_. Charset DB: CL8MSWIN1251 — apply via python-oracledb.
-- =====================================================================

ALTER TABLE YBIRO_CLIENT ADD (
  address     VARCHAR2(400),
  idno        VARCHAR2(20),
  is_company  VARCHAR2(1) DEFAULT '0'
);
