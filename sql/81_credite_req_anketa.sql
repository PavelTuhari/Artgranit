-- =====================================================================
-- TMS_CREDITE_REQ — datele COMPLETE ale anchetei de cerere de credit.
-- RO: operatorul copiaza de aici in cererea depusa la BANCA (Microinvest
--     nu are API). Pina acum o parte din date se ingramadeau ca text in
--     CLIENT_ADDRESS — acum fiecare cimp are coloana lui.
-- EN: full credit-application data, one column per field, so the operator
--     can copy them into the lender's own form.
-- =====================================================================
ALTER TABLE TMS_CREDITE_REQ ADD (
  CLIENT_COD   NUMBER,                 -- TMS_UNIVERS.COD (dosarul cu acte)
  EMAIL        VARCHAR2(160),
  IDNP         VARCHAR2(13),           -- complet: necesar dosarului de credit
  BIRTH_DATE   VARCHAR2(10),           -- YYYY-MM-DD
  ACT_SERIE    VARCHAR2(40),           -- seria si nr. buletinului
  ACT_DATA     VARCHAR2(10),           -- data eliberarii
  ACT_OFICIU   VARCHAR2(120),          -- oficiul emitent
  LOCALITATE   VARCHAR2(120),
  SCOP         VARCHAR2(60),           -- scopul creditului
  VENIT        NUMBER,                 -- venit lunar net
  ALTE_RATE    NUMBER,                 -- alte credite (rate lunare)
  ANGAJATOR    VARCHAR2(160),
  ACORD_MKT    CHAR(1) DEFAULT '0'     -- acordul de marketing (optional)
);
