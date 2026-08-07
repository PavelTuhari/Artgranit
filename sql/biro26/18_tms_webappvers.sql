-- =====================================================================
-- RO: Versiunea aplicatiilor web (site-ul Flask si WordPress-ul).
--     Numarul de versiune = DATA lansarii, format YYYY.MM.DD — se vede in
--     subsolul site-ului dupa «UNA.md and ORACLE OCI based».
--     Aceeasi valoare se scrie SI in MySQL-ul WordPress (wp_options),
--     ca ambele parti ale site-ului sa arate acelasi numar.
-- EN: web application versions; the number IS the release date (YYYY.MM.DD)
--     shown in the site footer. The same value is mirrored into WordPress
--     wp_options so both halves of the site report one version.
-- Prefix: TMS_. Charset DB: CL8MSWIN1251 — apply via python-oracledb.
-- =====================================================================

CREATE TABLE TMS_WEBAPPVERS (
  ID         NUMBER        NOT NULL,
  APP_CODE   VARCHAR2(30)  NOT NULL,   -- 'site' (Flask) | 'wordpress'
  VERS       VARCHAR2(20)  NOT NULL,   -- 'YYYY.MM.DD' — data lansarii
  IS_CURRENT VARCHAR2(1)   DEFAULT '0' NOT NULL,  -- '1' = versiunea afisata
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

-- RO: o singura versiune curenta per aplicatie — indexul UNIC pe
--     (APP_CODE, IS_CURRENT) cu '0' inlocuit prin NULL: randurile vechi nu
--     se ciocnesc intre ele, dar doua «curente» nu pot exista.
-- EN: at most one current row per app (NULLs are not indexed in Oracle).
CREATE UNIQUE INDEX UX_TMS_WEBAPPVERS_CUR ON TMS_WEBAPPVERS (
  APP_CODE, CASE WHEN IS_CURRENT = '1' THEN '1' END);

CREATE OR REPLACE VIEW VMS_WEBAPPVERS AS
SELECT APP_CODE, VERS, NOTE, RELEASED, CREATED
  FROM TMS_WEBAPPVERS
 WHERE IS_CURRENT = '1';
