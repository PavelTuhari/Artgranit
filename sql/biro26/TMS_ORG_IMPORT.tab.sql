-- =====================================================================
-- RO: Extinderea cartelei furnizorului (TMS_ORG) cu SURSELE DE IMPORT.
--     Doua tabele:
--       TMS_ORG_IMPSRC  — descrierea sursei (de unde vin datele, ce algoritm,
--                         ce prefix de articol foloseste);
--       TMS_ORG_IMPFILE — fisierele propriu-zise, pastrate in baza (BLOB),
--                         ca sa poata fi reincarcate si auditate din back-office.
-- EN: Extends the supplier card (TMS_ORG) with IMPORT SOURCES.
--       TMS_ORG_IMPSRC  — source descriptor (where data comes from, which
--                         algorithm, which article prefix it uses);
--       TMS_ORG_IMPFILE — the files themselves, kept in the DB (BLOB), so they
--                         can be re-imported and audited from the back office.
--
-- ── De ce prefixul de articol ── / ── Why the article prefix ──
-- RO: Codurile scurte sau pur numerice ("248", "670", "2917") inseamna produse
--     DIFERITE la fiecare furnizor. Fara prefix, ele se ciocnesc si potrivesc
--     marfuri nelegate (incidentul officeshop, load 285: 629 potriviri false).
--     Prefixul face articolul unic in cadrul catalogului:
--       ARK-248, BASY-2917, OS-1841
--     Ordinea de alegere: BRAND (din fisier) -> FURNIZOR -> codul SURSEI.
-- EN: Short or purely numeric codes mean DIFFERENT products at each supplier and
--     collide across suppliers. The prefix makes the article unique; it is taken
--     from the row's BRAND, else the SUPPLIER, else the SOURCE code.
--
--   TMS_UNIVERS (master, TIP='O')
--        └── TMS_ORG              (cartela organizatiei: COD PK/FK)
--                 └── TMS_ORG_IMPSRC    (surse de import)        1:N
--                          └── TMS_ORG_IMPFILE (fisiere incarcate) 1:N
-- =====================================================================
SET SQLBLANKLINES ON

CREATE TABLE TMS_ORG_IMPSRC (
  SRC_CODE      VARCHAR2(30)  NOT NULL,   -- RO: codul sursei: 'OFFICESHOP', 'CRAFTI'
  COD_ORG       NUMBER,                   -- RO: = TMS_ORG.COD (poate lipsi la scraping)
  SRC_NAME      VARCHAR2(120) NOT NULL,   -- RO: denumirea lizibila a sursei
  SRC_TYPE      VARCHAR2(20)  NOT NULL,   -- RO: SCRAPING | EMAIL | B2B | MANUAL
  SRC_LOCATION  VARCHAR2(400),            -- RO: URL-ul site-ului, adresa e-mail, portalul B2B
  ALGO_CODE     VARCHAR2(30)  DEFAULT 'UNIVERSAL' NOT NULL,
                                          -- RO: UNIVERSAL | PRICES_ONLY | IMAGES | BARCODES
  ART_PREFIX    VARCHAR2(10),             -- RO: prefixul pentru articolele scurte/numerice
  ART_MIN_LEN   NUMBER        DEFAULT 6,  -- RO: sub cite caractere articolul e considerat slab
  FILE_FORMAT   VARCHAR2(200),             -- RO: xlsx | csv | zip; note despre foi
  MARK_NEW      NUMBER(1)     DEFAULT 0,  -- RO: 1 = toate randurile intra ca produse NOI
  ONLY_ARTICOL  NUMBER(1)     DEFAULT 1,  -- RO: 1 = preturile se reinnoiesc doar dupa articol
  NOTES         VARCHAR2(2000),           -- RO: particularitatile sursei (foi, coloane, capcane)
  ACTIVE        NUMBER(1)     DEFAULT 1   NOT NULL,
  CREATED_AT    DATE          DEFAULT SYSDATE,
  UPDATED_AT    DATE          DEFAULT SYSDATE,
  CONSTRAINT TMS_ORG_IMPSRC_PK  PRIMARY KEY (SRC_CODE),
  CONSTRAINT TMS_ORG_IMPSRC_FK  FOREIGN KEY (COD_ORG) REFERENCES TMS_ORG (COD),
  CONSTRAINT TMS_ORG_IMPSRC_CK1 CHECK (SRC_TYPE IN ('SCRAPING','EMAIL','B2B','MANUAL')),
  CONSTRAINT TMS_ORG_IMPSRC_CK2 CHECK (ALGO_CODE IN ('UNIVERSAL','PRICES_ONLY','IMAGES','BARCODES'))
);

CREATE INDEX TMS_ORG_IMPSRC_IX_ORG ON TMS_ORG_IMPSRC (COD_ORG);

COMMENT ON TABLE  TMS_ORG_IMPSRC IS 'RO: sursele de import ale unui furnizor (scraping / e-mail / portal B2B) / EN: a supplier import sources';
COMMENT ON COLUMN TMS_ORG_IMPSRC.ART_PREFIX  IS 'RO: prefix pentru articolele scurte sau pur numerice, ca sa nu se ciocneasca intre furnizori';
COMMENT ON COLUMN TMS_ORG_IMPSRC.ALGO_CODE   IS 'RO: algoritmul de incarcare ales in back-office';
COMMENT ON COLUMN TMS_ORG_IMPSRC.ONLY_ARTICOL IS 'RO: 1 = preturile se reinnoiesc DOAR pentru marfa potrivita dupa articol';

CREATE TABLE TMS_ORG_IMPFILE (
  FILE_ID       NUMBER        NOT NULL,
  SRC_CODE      VARCHAR2(30)  NOT NULL,   -- RO: = TMS_ORG_IMPSRC.SRC_CODE
  FILE_NAME     VARCHAR2(260) NOT NULL,
  FILE_BLOB     BLOB,                     -- RO: fisierul original, octet cu octet
  FILE_SIZE     NUMBER,
  FILE_SHA256   VARCHAR2(64),             -- RO: ca sa recunoastem o reincarcare identica
  SHEET_INFO    VARCHAR2(1000),           -- RO: foile si numarul de randuri
  LOAD_ID       NUMBER,                   -- RO: = BIRO26PT_FILE.LOAD_ID (dupa incarcare)
  N_ROWS        NUMBER,
  IMPORTED      NUMBER(1)     DEFAULT 0,  -- RO: 0 = doar pastrat, 1 = importat in productie
  IMPORT_LOG    CLOB,                     -- RO: raportul importului (DBMS_OUTPUT)
  UPLOADED_BY   VARCHAR2(60),
  UPLOADED_AT   DATE          DEFAULT SYSDATE,
  CONSTRAINT TMS_ORG_IMPFILE_PK PRIMARY KEY (FILE_ID),
  CONSTRAINT TMS_ORG_IMPFILE_FK FOREIGN KEY (SRC_CODE) REFERENCES TMS_ORG_IMPSRC (SRC_CODE)
);

CREATE INDEX TMS_ORG_IMPFILE_IX_SRC ON TMS_ORG_IMPFILE (SRC_CODE, UPLOADED_AT);

CREATE SEQUENCE TMS_ORG_IMPFILE_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

COMMENT ON TABLE  TMS_ORG_IMPFILE IS 'RO: fisierele de import pastrate in baza, legate de sursa / EN: import files kept in the DB, linked to their source';
COMMENT ON COLUMN TMS_ORG_IMPFILE.FILE_SHA256 IS 'RO: amprenta fisierului - o reincarcare identica se poate recunoaste si sari';
COMMENT ON COLUMN TMS_ORG_IMPFILE.LOAD_ID     IS 'RO: legatura cu stagin-ul brut BIRO26PT_FILE';
