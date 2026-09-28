-- =====================================================================
-- RO: Datele din formularul de credit, MEMORATE in cabinetul clientului:
--     la a doua cerere cimpurile se completeaza automat, iar orice
--     modificare se salveaza tacit peste cele vechi. Clientul poate opri
--     memorarea din cabinet (CREDIT_SAVE = '0') — atunci cimpurile se sterg.
-- EN: credit-form fields remembered in the client's cabinet; refilled
--     automatically next time and silently overwritten on edit. The client
--     can switch memorising off (CREDIT_SAVE = '0'), which clears them.
-- Prefix: YBIRO_. Charset DB: CL8MSWIN1251 — apply via python-oracledb.
-- =====================================================================

ALTER TABLE YBIRO_CLIENT ADD (
  credit_nnp     VARCHAR2(200),
  credit_idnp    VARCHAR2(20),
  credit_address VARCHAR2(400),
  credit_birth   DATE,
  credit_phone   VARCHAR2(40),
  credit_save    VARCHAR2(1) DEFAULT '1'
);
