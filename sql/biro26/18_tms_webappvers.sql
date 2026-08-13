-- =====================================================================
-- RO: Versiunea aplicatiilor web. Numarul de versiune = DATA lansarii,
--     format YYYY.MM.DD — se vede in subsolul site-ului dupa
--     «UNA.md and ORACLE OCI based».
--
--     ACEEASI tabela, cu ACELEASI valori, exista in AMBELE baze:
--     Oracle (TMS_WEBAPPVERS) si MySQL-ul WordPress (tms_webappvers).
--     Asa se vede dintr-o privire daca cele doua baze sint sincrone.
--     `SRC_HASH` — suma de control a surselor (SHA-256), pentru urmarirea
--     codului livrat; deocamdata se completeaza optional.
-- EN: web application versions; the number IS the release date (YYYY.MM.DD).
--     The SAME table with the SAME rows lives in BOTH databases (Oracle and
--     the WordPress MySQL) so drift between them is visible at a glance.
--     `SRC_HASH` holds a SHA-256 checksum of the deployed sources.
-- Prefix: TMS_. Charset DB: CL8MSWIN1251 — apply via python-oracledb.
-- Vezi: docs/Biro26/WEB_APP_VERSIONING.md
-- =====================================================================

CREATE TABLE TMS_WEBAPPVERS (
  ID         NUMBER        NOT NULL,
  APP_CODE   VARCHAR2(30)  NOT NULL,   -- 'site' (Flask) | 'wordpress'
  VERS       VARCHAR2(20)  NOT NULL,   -- 'YYYY.MM.DD' — data lansarii
  IS_CURRENT VARCHAR2(1)   DEFAULT '0' NOT NULL,  -- '1' = versiunea afisata
  SRC_HASH   VARCHAR2(64),             -- SHA-256 al surselor livrate
  NOTE       VARCHAR2(400),
  RELEASED   DATE          DEFAULT SYSDATE,
  CREATED    DATE          DEFAULT SYSDATE,
  CONSTRAINT PK_TMS_WEBAPPVERS PRIMARY KEY (ID)
);

CREATE SEQUENCE TMS_WEBAPPVERS_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE OR REPLACE TRIGGER TMS_WEBAPPVERS_BI
  BEFORE INSERT ON TMS_WEBAPPVERS FOR EACH ROW WHEN (NEW.ID IS NULL)
BEGIN
  SELECT TMS_WEBAPPVERS_SEQ.NEXTVAL INTO :NEW.ID FROM dual;
END;
/

-- RO: o singura versiune curenta per aplicatie. APP_CODE trebuie sa fie
--     INAUNTRUL expresiei CASE: Oracle sare peste intrarea de index doar
--     cind TOATE coloanele cheii sint NULL, deci varianta compusa
--     (APP_CODE, CASE ...) permitea o singura versiune ISTORICA per
--     aplicatie si pica cu ORA-00001 la a doua retrogradare.
-- EN: APP_CODE must live INSIDE the CASE — a composite index is skipped
--     only when every key column is NULL, so the old form allowed just one
--     historical row per app and raised ORA-00001 on the second demote.
CREATE UNIQUE INDEX UX_TMS_WEBAPPVERS_CUR ON TMS_WEBAPPVERS (
  CASE WHEN IS_CURRENT = '1' THEN APP_CODE END);

CREATE OR REPLACE VIEW VMS_WEBAPPVERS AS
SELECT APP_CODE, VERS, SRC_HASH, NOTE, RELEASED, CREATED
  FROM TMS_WEBAPPVERS
 WHERE IS_CURRENT = '1';
