-- =====================================================================
-- RO: Modulul SEOForge - conturul de promovare SEO in baza back-office.
-- EN: SEOForge module - SEO promotion contour in the back-office database.
--
-- RO: Sursa cerintelor: docs/superpowers/specs/2026-08-24-seoforge-backoffice-design.md
-- EN: Requirements source: docs/superpowers/specs/2026-08-24-seoforge-backoffice-design.md
--
-- RO: Reguli respectate: prefix YSEO_, chei primare din secvente prin
--     declansatoare BEFORE INSERT, index separat pe fiecare coloana FK,
--     fara stergeri (doar ISARHIV), comentarii doar RO/EN.
-- EN: Rules kept: YSEO_ prefix, primary keys from sequences via BEFORE
--     INSERT triggers, a separate index on every FK column, no deletes
--     (ISARHIV only), comments in RO/EN only.
-- =====================================================================

-- ---------------------------------------------------------------------
-- RO: Nomenclator comun al conturului. Inlocuieste sectiunile TMS_SYSS
--     W1..W7 din sistemul UNA: aceeasi idee, dar autonoma.
-- EN: Shared dictionary of the contour. Replaces the TMS_SYSS W1..W7
--     sections of the UNA system: same idea, but standalone.
--
-- RO: COD1 este unic global (nu doar in sectiune) ca sa poata fi tinta
--     cheilor straine. PK compus pastreaza cautarea in stil UNA.
-- EN: COD1 is globally unique (not only within a section) so that foreign
--     keys can target it. The composite PK keeps the UNA-style lookup.
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_DICT (
    SECTION         VARCHAR2(20)    NOT NULL,
    COD1            NUMBER          NOT NULL,
    CODE            VARCHAR2(50)    NOT NULL,
    NAME_RU         VARCHAR2(200),
    NAME_RO         VARCHAR2(200),
    NAME_EN         VARCHAR2(200),
    SORT_ORDER      NUMBER          DEFAULT 100 NOT NULL,
    ISARHIV         NUMBER(1)       DEFAULT 0 NOT NULL,
    CONSTRAINT PK_YSEO_DICT PRIMARY KEY (SECTION, COD1),
    CONSTRAINT UK_YSEO_DICT_COD1 UNIQUE (COD1),
    CONSTRAINT UK_YSEO_DICT_CODE UNIQUE (SECTION, CODE),
    CONSTRAINT CK_YSEO_DICT_SECTION CHECK (SECTION IN
        ('CHANNEL', 'ARTICLE', 'PROMO_TYPE', 'FORMAT', 'BUYUNIT', 'METRIC')),
    CONSTRAINT CK_YSEO_DICT_ARH CHECK (ISARHIV IN (0, 1))
);
COMMENT ON TABLE YSEO_DICT IS 'RO: Nomenclator comun al conturului SEO / EN: Shared SEO contour dictionary';

-- RO: Porneste de la 1001: codurile 101..999 sunt rezervate pentru
--     nomenclatorul livrat cu modulul (116_yseo_dict_seed.sql).
-- EN: Starts at 1001: codes 101..999 are reserved for the dictionary
--     shipped with the module (116_yseo_dict_seed.sql).
CREATE SEQUENCE YSEO_DICT_SEQ START WITH 1001 INCREMENT BY 1 NOCACHE;

-- ---------------------------------------------------------------------
-- RO: Profilul site-ului promovat (Site Profile din caietul de sarcini).
-- EN: Profile of a promoted site (Site Profile from the specification).
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_SITE (
    COD             NUMBER          NOT NULL,
    DOMAIN          VARCHAR2(255)   NOT NULL,
    LOCALES         VARCHAR2(200)   NOT NULL,
    GEO             VARCHAR2(100),
    NICHE           VARCHAR2(400),
    -- RO: Subdiviziunea pe care se aloca cheltuielile site-ului.
    -- EN: The division the site expenses are allocated to.
    DIV             VARCHAR2(20),
    TONE_OF_VOICE   VARCHAR2(2000),
    GUARDRAILS      VARCHAR2(4000),
    KPI_TARGET      VARCHAR2(2000),
    ISARHIV         NUMBER(1)       DEFAULT 0 NOT NULL,
    CONSTRAINT PK_YSEO_SITE PRIMARY KEY (COD),
    CONSTRAINT UK_YSEO_SITE_DOMAIN UNIQUE (DOMAIN),
    CONSTRAINT CK_YSEO_SITE_ARH CHECK (ISARHIV IN (0, 1))
);
COMMENT ON TABLE YSEO_SITE IS 'RO: Site-uri promovate / EN: Promoted sites';

CREATE SEQUENCE YSEO_SITE_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- ---------------------------------------------------------------------
-- RO: Platforme de plasare: retele sociale, cataloage, site-uri locale.
-- EN: Placement platforms: social networks, catalogues, local sites.
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_PLATFORM (
    COD             NUMBER          NOT NULL,
    PLATFORM_CODE   VARCHAR2(50)    NOT NULL,
    NAME            VARCHAR2(200)   NOT NULL,
    URL             VARCHAR2(500),
    CHANNEL_COD1    NUMBER          NOT NULL,
    GEO             VARCHAR2(100),
    HAS_API         NUMBER(1)       DEFAULT 0 NOT NULL,
    -- RO: 1 = publicarea se face doar de om (fara API sau contra regulilor).
    -- EN: 1 = publishing is human-only (no API or against platform rules).
    MANUAL_PUBLISH  NUMBER(1)       DEFAULT 1 NOT NULL,
    QUALITY_SCORE   NUMBER(4,2),
    RATE_LIMIT_DAY  NUMBER,
    POSTING_RULES   VARCHAR2(2000),
    ISARHIV         NUMBER(1)       DEFAULT 0 NOT NULL,
    CONSTRAINT PK_YSEO_PLATFORM PRIMARY KEY (COD),
    CONSTRAINT UK_YSEO_PLATFORM_CODE UNIQUE (PLATFORM_CODE),
    CONSTRAINT FK_YSEO_PLATFORM_CHANNEL FOREIGN KEY (CHANNEL_COD1)
        REFERENCES YSEO_DICT (COD1) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT CK_YSEO_PLATFORM_FLAGS CHECK (HAS_API IN (0, 1) AND MANUAL_PUBLISH IN (0, 1)),
    CONSTRAINT CK_YSEO_PLATFORM_SCORE CHECK (QUALITY_SCORE IS NULL OR QUALITY_SCORE BETWEEN 0 AND 10),
    CONSTRAINT CK_YSEO_PLATFORM_ARH CHECK (ISARHIV IN (0, 1))
);
COMMENT ON TABLE YSEO_PLATFORM IS 'RO: Platforme de plasare / EN: Placement platforms';

CREATE INDEX IX_YSEO_PLATFORM_CHANNEL ON YSEO_PLATFORM (CHANNEL_COD1);

CREATE SEQUENCE YSEO_PLATFORM_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- ---------------------------------------------------------------------
-- RO: Campanie / actiune promotionala. CAMP_CODE este si utm_campaign.
-- EN: Campaign / promotion. CAMP_CODE doubles as utm_campaign.
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_CAMPAIGN (
    COD             NUMBER          NOT NULL,
    CAMP_CODE       VARCHAR2(50)    NOT NULL,
    SITE_COD        NUMBER          NOT NULL,
    NAME_RU         VARCHAR2(400),
    NAME_RO         VARCHAR2(400),
    NAME_EN         VARCHAR2(400),
    PROMO_TYPE_COD1 NUMBER          NOT NULL,
    DISCOUNT_VALUE  NUMBER(12,2),
    PROMO_CODE      VARCHAR2(50),
    SCOPE_KIND      VARCHAR2(20)    DEFAULT 'SITE' NOT NULL,
    DATE_START      DATE            NOT NULL,
    DATE_END        DATE            NOT NULL,
    LIMIT_QTY       NUMBER,
    LIMIT_SUM       NUMBER(16,2),
    BUDGET_PLAN     NUMBER(16,2)    DEFAULT 0 NOT NULL,
    KPI_TARGET      VARCHAR2(2000),
    LEGAL_TEXT_REF  VARCHAR2(500),
    STATUS          VARCHAR2(20)    DEFAULT 'DRAFT' NOT NULL,
    ISARHIV         NUMBER(1)       DEFAULT 0 NOT NULL,
    CONSTRAINT PK_YSEO_CAMPAIGN PRIMARY KEY (COD),
    CONSTRAINT UK_YSEO_CAMPAIGN_CODE UNIQUE (CAMP_CODE),
    CONSTRAINT FK_YSEO_CAMPAIGN_SITE FOREIGN KEY (SITE_COD)
        REFERENCES YSEO_SITE (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_CAMPAIGN_PROMO FOREIGN KEY (PROMO_TYPE_COD1)
        REFERENCES YSEO_DICT (COD1) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT CK_YSEO_CAMPAIGN_PERIOD CHECK (DATE_END >= DATE_START),
    CONSTRAINT CK_YSEO_CAMPAIGN_SCOPE CHECK (SCOPE_KIND IN ('SITE', 'CATEGORY', 'ITEMS')),
    CONSTRAINT CK_YSEO_CAMPAIGN_STATUS CHECK (STATUS IN ('DRAFT', 'ACTIVE', 'CLOSED', 'CANCELLED')),
    CONSTRAINT CK_YSEO_CAMPAIGN_BUDGET CHECK (BUDGET_PLAN >= 0),
    CONSTRAINT CK_YSEO_CAMPAIGN_ARH CHECK (ISARHIV IN (0, 1))
);
COMMENT ON TABLE YSEO_CAMPAIGN IS 'RO: Campanii de promovare / EN: Promotion campaigns';

CREATE INDEX IX_YSEO_CAMPAIGN_SITE ON YSEO_CAMPAIGN (SITE_COD);
CREATE INDEX IX_YSEO_CAMPAIGN_PROMO ON YSEO_CAMPAIGN (PROMO_TYPE_COD1);

CREATE SEQUENCE YSEO_CAMPAIGN_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- ---------------------------------------------------------------------
-- RO: Planul de buget pe perioada, articol, canal si site.
-- EN: Budget plan by period, article, channel and site.
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_BUDGET_PLAN (
    COD             NUMBER          NOT NULL,
    -- RO: Perioada in format YYYY-MM. EN: Period in YYYY-MM format.
    PERIOD          VARCHAR2(10)    NOT NULL,
    ARTICLE_COD1    NUMBER          NOT NULL,
    CHANNEL_COD1    NUMBER,
    SITE_COD        NUMBER,
    PLAN_SUMA       NUMBER(16,2)    DEFAULT 0 NOT NULL,
    VALUTA          VARCHAR2(3)     DEFAULT 'MDL' NOT NULL,
    NOTE            VARCHAR2(1000),
    CONSTRAINT PK_YSEO_BUDGET_PLAN PRIMARY KEY (COD),
    CONSTRAINT FK_YSEO_BUDGET_PLAN_ARTICLE FOREIGN KEY (ARTICLE_COD1)
        REFERENCES YSEO_DICT (COD1) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_BUDGET_PLAN_CHANNEL FOREIGN KEY (CHANNEL_COD1)
        REFERENCES YSEO_DICT (COD1) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_BUDGET_PLAN_SITE FOREIGN KEY (SITE_COD)
        REFERENCES YSEO_SITE (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT CK_YSEO_BUDGET_PLAN_SUMA CHECK (PLAN_SUMA >= 0)
);
COMMENT ON TABLE YSEO_BUDGET_PLAN IS 'RO: Plan de buget marketing / EN: Marketing budget plan';

-- RO: Cheia naturala are coloane optionale, deci unicitatea se tine pe
--     index functional: altfel doua randuri cu NULL ar trece amandoua.
-- EN: The natural key has optional columns, so uniqueness lives in a
--     function-based index: otherwise two NULL rows would both pass.
CREATE UNIQUE INDEX UX_YSEO_BUDGET_PLAN_KEY ON YSEO_BUDGET_PLAN
    (PERIOD, ARTICLE_COD1, NVL(CHANNEL_COD1, -1), NVL(SITE_COD, -1));

CREATE INDEX IX_YSEO_BUDGET_PLAN_ARTICLE ON YSEO_BUDGET_PLAN (ARTICLE_COD1);
CREATE INDEX IX_YSEO_BUDGET_PLAN_CHANNEL ON YSEO_BUDGET_PLAN (CHANNEL_COD1);
CREATE INDEX IX_YSEO_BUDGET_PLAN_SITE ON YSEO_BUDGET_PLAN (SITE_COD);

CREATE SEQUENCE YSEO_BUDGET_PLAN_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- ---------------------------------------------------------------------
-- RO: Loturi de import CSV. Tine urma fiecarei incarcari de fapte.
-- EN: CSV import batches. Keeps track of every fact upload.
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_IMPORT (
    COD             NUMBER          NOT NULL,
    KIND            VARCHAR2(10)    NOT NULL,
    FILE_NAME       VARCHAR2(400),
    USERNAME        VARCHAR2(100),
    LOADED_AT       DATE            DEFAULT SYSDATE NOT NULL,
    ROWS_TOTAL      NUMBER          DEFAULT 0 NOT NULL,
    ROWS_LOADED     NUMBER          DEFAULT 0 NOT NULL,
    ROWS_SKIPPED    NUMBER          DEFAULT 0 NOT NULL,
    STATUS          VARCHAR2(20)    DEFAULT 'OK' NOT NULL,
    CONSTRAINT PK_YSEO_IMPORT PRIMARY KEY (COD),
    CONSTRAINT CK_YSEO_IMPORT_KIND CHECK (KIND IN ('SPEND', 'METRICS')),
    CONSTRAINT CK_YSEO_IMPORT_STATUS CHECK (STATUS IN ('OK', 'PARTIAL', 'FAILED'))
);
COMMENT ON TABLE YSEO_IMPORT IS 'RO: Loturi de import CSV / EN: CSV import batches';

CREATE SEQUENCE YSEO_IMPORT_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- ---------------------------------------------------------------------
-- RO: Faptul cheltuielii de publicitate. EXT_ID asigura idempotenta:
--     reincarcarea aceluiasi fisier nu creeaza duplicate.
-- EN: Advertising spend fact. EXT_ID guarantees idempotence: re-uploading
--     the same file creates no duplicates.
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_SPEND_FACT (
    COD             NUMBER          NOT NULL,
    EXT_ID          VARCHAR2(200)   NOT NULL,
    SITE_COD        NUMBER          NOT NULL,
    CAMP_COD        NUMBER,
    CHANNEL_COD1    NUMBER          NOT NULL,
    PLATFORM_COD    NUMBER,
    ARTICLE_COD1    NUMBER          NOT NULL,
    SPEND_DATE      DATE            NOT NULL,
    PERIOD          VARCHAR2(10)    NOT NULL,
    SUMA            NUMBER(16,2)    DEFAULT 0 NOT NULL,
    VALUTA          VARCHAR2(3)     DEFAULT 'MDL' NOT NULL,
    SUMA_MDL        NUMBER(16,2)    DEFAULT 0 NOT NULL,
    CLICKS          NUMBER          DEFAULT 0 NOT NULL,
    IMPRESSIONS     NUMBER          DEFAULT 0 NOT NULL,
    CONVERSIONS     NUMBER          DEFAULT 0 NOT NULL,
    REVENUE         NUMBER(16,2)    DEFAULT 0 NOT NULL,
    IS_OVERBUDGET   NUMBER(1)       DEFAULT 0 NOT NULL,
    SOURCE          VARCHAR2(20)    DEFAULT 'MANUAL' NOT NULL,
    IMPORT_COD      NUMBER,
    CONSTRAINT PK_YSEO_SPEND_FACT PRIMARY KEY (COD),
    CONSTRAINT UK_YSEO_SPEND_FACT_EXT UNIQUE (EXT_ID),
    CONSTRAINT FK_YSEO_SPEND_SITE FOREIGN KEY (SITE_COD)
        REFERENCES YSEO_SITE (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_SPEND_CAMP FOREIGN KEY (CAMP_COD)
        REFERENCES YSEO_CAMPAIGN (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_SPEND_CHANNEL FOREIGN KEY (CHANNEL_COD1)
        REFERENCES YSEO_DICT (COD1) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_SPEND_PLATFORM FOREIGN KEY (PLATFORM_COD)
        REFERENCES YSEO_PLATFORM (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_SPEND_ARTICLE FOREIGN KEY (ARTICLE_COD1)
        REFERENCES YSEO_DICT (COD1) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_SPEND_IMPORT FOREIGN KEY (IMPORT_COD)
        REFERENCES YSEO_IMPORT (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT CK_YSEO_SPEND_SUMA CHECK (SUMA >= 0),
    CONSTRAINT CK_YSEO_SPEND_OVER CHECK (IS_OVERBUDGET IN (0, 1)),
    CONSTRAINT CK_YSEO_SPEND_SOURCE CHECK (SOURCE IN ('MANUAL', 'CSV', 'API'))
);
COMMENT ON TABLE YSEO_SPEND_FACT IS 'RO: Fapt de cheltuiala publicitara / EN: Advertising spend fact';

CREATE INDEX IX_YSEO_SPEND_SITE ON YSEO_SPEND_FACT (SITE_COD);
CREATE INDEX IX_YSEO_SPEND_CAMP ON YSEO_SPEND_FACT (CAMP_COD);
CREATE INDEX IX_YSEO_SPEND_CHANNEL ON YSEO_SPEND_FACT (CHANNEL_COD1);
CREATE INDEX IX_YSEO_SPEND_PLATFORM ON YSEO_SPEND_FACT (PLATFORM_COD);
CREATE INDEX IX_YSEO_SPEND_ARTICLE ON YSEO_SPEND_FACT (ARTICLE_COD1);
CREATE INDEX IX_YSEO_SPEND_IMPORT ON YSEO_SPEND_FACT (IMPORT_COD);
CREATE INDEX IX_YSEO_SPEND_PERIOD ON YSEO_SPEND_FACT (PERIOD, SITE_COD);

CREATE SEQUENCE YSEO_SPEND_FACT_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- ---------------------------------------------------------------------
-- RO: Metricile site-ului: pozitii, trafic, CTR, conversii.
-- EN: Site metrics: positions, traffic, CTR, conversions.
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_METRICS_FACT (
    COD             NUMBER          NOT NULL,
    EXT_ID          VARCHAR2(200)   NOT NULL,
    SITE_COD        NUMBER          NOT NULL,
    METRIC_COD1     NUMBER          NOT NULL,
    CHANNEL_COD1    NUMBER,
    FACT_DATE       DATE            NOT NULL,
    PERIOD          VARCHAR2(10)    NOT NULL,
    METRIC_VALUE    NUMBER(20,4)    DEFAULT 0 NOT NULL,
    SOURCE          VARCHAR2(50),
    IMPORT_COD      NUMBER,
    CONSTRAINT PK_YSEO_METRICS_FACT PRIMARY KEY (COD),
    CONSTRAINT UK_YSEO_METRICS_FACT_EXT UNIQUE (EXT_ID),
    CONSTRAINT FK_YSEO_METRICS_SITE FOREIGN KEY (SITE_COD)
        REFERENCES YSEO_SITE (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_METRICS_METRIC FOREIGN KEY (METRIC_COD1)
        REFERENCES YSEO_DICT (COD1) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_METRICS_CHANNEL FOREIGN KEY (CHANNEL_COD1)
        REFERENCES YSEO_DICT (COD1) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT FK_YSEO_METRICS_IMPORT FOREIGN KEY (IMPORT_COD)
        REFERENCES YSEO_IMPORT (COD) DEFERRABLE INITIALLY DEFERRED
);
COMMENT ON TABLE YSEO_METRICS_FACT IS 'RO: Metrici de site / EN: Site metrics';

CREATE INDEX IX_YSEO_METRICS_SITE ON YSEO_METRICS_FACT (SITE_COD);
CREATE INDEX IX_YSEO_METRICS_METRIC ON YSEO_METRICS_FACT (METRIC_COD1);
CREATE INDEX IX_YSEO_METRICS_CHANNEL ON YSEO_METRICS_FACT (CHANNEL_COD1);
CREATE INDEX IX_YSEO_METRICS_IMPORT ON YSEO_METRICS_FACT (IMPORT_COD);
CREATE INDEX IX_YSEO_METRICS_PERIOD ON YSEO_METRICS_FACT (PERIOD, SITE_COD);

CREATE SEQUENCE YSEO_METRICS_FACT_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- ---------------------------------------------------------------------
-- RO: Cursul valutar pe data. Fara el sumele in valute diferite nu pot
--     fi adunate corect in rapoartele plan/fapt si ROI.
-- EN: Currency rate by date. Without it, amounts in different currencies
--     cannot be summed correctly in the plan/fact and ROI reports.
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_FX_RATE (
    VALUTA          VARCHAR2(3)     NOT NULL,
    RATE_DATE       DATE            NOT NULL,
    RATE            NUMBER(18,6)    NOT NULL,
    CONSTRAINT PK_YSEO_FX_RATE PRIMARY KEY (VALUTA, RATE_DATE),
    CONSTRAINT CK_YSEO_FX_RATE_POS CHECK (RATE > 0)
);
COMMENT ON TABLE YSEO_FX_RATE IS 'RO: Cursuri valutare / EN: Currency rates';

-- ---------------------------------------------------------------------
-- RO: Setarile conturului. Doar setari, nu date de business.
-- EN: Contour settings. Settings only, no business data.
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_SETUP (
    PARAM_CODE      VARCHAR2(50)    NOT NULL,
    PARAM_VALUE     VARCHAR2(400),
    DESCR           VARCHAR2(400),
    CONSTRAINT PK_YSEO_SETUP PRIMARY KEY (PARAM_CODE)
);
COMMENT ON TABLE YSEO_SETUP IS 'RO: Setarile conturului SEO / EN: SEO contour settings';

-- ---------------------------------------------------------------------
-- RO: Legatura cu documentele sistemului de evidenta UNA. Se completeaza
--     cand va fi confirmata interfata UNA (partea C a proiectului).
-- EN: Link to the UNA accounting documents. To be filled once the UNA
--     interface is confirmed (part C of the project).
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_XREF (
    COD             NUMBER          NOT NULL,
    ENTITY_TYPE     VARCHAR2(20)    NOT NULL,
    ENTITY_COD      NUMBER          NOT NULL,
    ERP_DOC_COD     NUMBER,
    ERP_NRMANUAL    VARCHAR2(50),
    NOTE            VARCHAR2(400),
    CREATED_AT      DATE            DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_YSEO_XREF PRIMARY KEY (COD),
    CONSTRAINT UK_YSEO_XREF_ENTITY UNIQUE (ENTITY_TYPE, ENTITY_COD)
);
COMMENT ON TABLE YSEO_XREF IS 'RO: Legatura cu documentele UNA / EN: Link to UNA documents';

CREATE SEQUENCE YSEO_XREF_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- ---------------------------------------------------------------------
-- RO: Jurnalul modulului. Doar adaugare, fara modificari si stergeri.
-- EN: Module journal. Append-only, no updates and no deletes.
-- ---------------------------------------------------------------------
CREATE TABLE YSEO_EVENT_LOG (
    COD             NUMBER          NOT NULL,
    ACTION          VARCHAR2(50)    NOT NULL,
    ENTITY_TYPE     VARCHAR2(30),
    ENTITY_COD      NUMBER,
    DETAILS         VARCHAR2(2000),
    USERNAME        VARCHAR2(100),
    CREATED_AT      DATE            DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_YSEO_EVENT_LOG PRIMARY KEY (COD)
);
COMMENT ON TABLE YSEO_EVENT_LOG IS 'RO: Jurnalul modulului SEOForge / EN: SEOForge module journal';

CREATE INDEX IX_YSEO_EVENT_LOG_TIME ON YSEO_EVENT_LOG (CREATED_AT);

CREATE SEQUENCE YSEO_EVENT_LOG_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/

-- =====================================================================
-- RO: Declansatoare de numerotare. EN: Numbering triggers.
-- =====================================================================

CREATE OR REPLACE TRIGGER TRG_YSEO_DICT_ID
BEFORE INSERT ON YSEO_DICT FOR EACH ROW
WHEN (NEW.COD1 IS NULL)
BEGIN
  :NEW.COD1 := YSEO_DICT_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER TRG_YSEO_SITE_ID
BEFORE INSERT ON YSEO_SITE FOR EACH ROW
WHEN (NEW.COD IS NULL)
BEGIN
  :NEW.COD := YSEO_SITE_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER TRG_YSEO_PLATFORM_ID
BEFORE INSERT ON YSEO_PLATFORM FOR EACH ROW
WHEN (NEW.COD IS NULL)
BEGIN
  :NEW.COD := YSEO_PLATFORM_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER TRG_YSEO_CAMPAIGN_ID
BEFORE INSERT ON YSEO_CAMPAIGN FOR EACH ROW
WHEN (NEW.COD IS NULL)
BEGIN
  :NEW.COD := YSEO_CAMPAIGN_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER TRG_YSEO_BUDGET_PLAN_ID
BEFORE INSERT ON YSEO_BUDGET_PLAN FOR EACH ROW
WHEN (NEW.COD IS NULL)
BEGIN
  :NEW.COD := YSEO_BUDGET_PLAN_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER TRG_YSEO_IMPORT_ID
BEFORE INSERT ON YSEO_IMPORT FOR EACH ROW
WHEN (NEW.COD IS NULL)
BEGIN
  :NEW.COD := YSEO_IMPORT_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER TRG_YSEO_XREF_ID
BEFORE INSERT ON YSEO_XREF FOR EACH ROW
WHEN (NEW.COD IS NULL)
BEGIN
  :NEW.COD := YSEO_XREF_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER TRG_YSEO_EVENT_LOG_ID
BEFORE INSERT ON YSEO_EVENT_LOG FOR EACH ROW
WHEN (NEW.COD IS NULL)
BEGIN
  :NEW.COD := YSEO_EVENT_LOG_SEQ.NEXTVAL;
END;
/

-- RO: Jurnalul este append-only: modificarea si stergerea sunt oprite.
-- EN: The journal is append-only: updates and deletes are blocked.
CREATE OR REPLACE TRIGGER TRG_YSEO_EVENT_LOG_RO
BEFORE UPDATE OR DELETE ON YSEO_EVENT_LOG
BEGIN
  RAISE_APPLICATION_ERROR(-20103,
    'RO: Jurnalul modulului este doar pentru adaugare. / '
    || 'EN: The module journal is append-only.');
END;
/

CREATE OR REPLACE TRIGGER TRG_YSEO_METRICS_FACT_ID
BEFORE INSERT OR UPDATE ON YSEO_METRICS_FACT FOR EACH ROW
BEGIN
  IF :NEW.COD IS NULL THEN
    :NEW.COD := YSEO_METRICS_FACT_SEQ.NEXTVAL;
  END IF;
  :NEW.PERIOD := TO_CHAR(:NEW.FACT_DATE, 'YYYY-MM');
END;
/

-- =====================================================================
-- RO: Controlul depasirii bugetului. Regula traieste in baza, nu in
--     aplicatie: o eroare de cod nu trebuie sa duca la bani necontrolati.
-- EN: Budget overrun control. The rule lives in the database, not in the
--     application: a code bug must not lead to uncontrolled money.
--
-- RO: Declansator compus dinadins: verificarea limitei citeste chiar
--     YSEO_SPEND_FACT, iar un declansator pe rand ar cadea cu ORA-04091
--     (tabel in mutatie). Randurile atinse se strang in BEFORE EACH ROW
--     si se verifica o singura data in AFTER STATEMENT.
-- EN: A compound trigger on purpose: the limit check reads YSEO_SPEND_FACT
--     itself, and a row-level trigger would fail with ORA-04091 (mutating
--     table). Touched rows are collected in BEFORE EACH ROW and checked
--     once in AFTER STATEMENT.
--
-- RO: Depinde de pachetele din 115_yseo_package.sql. La prima instalare
--     ramane invalid pana la crearea lor. Fisierul 116 il recompileaza.
-- EN: Depends on the packages from 115_yseo_package.sql. On first install
--     it stays invalid until they exist. File 116 recompiles it.
-- =====================================================================
CREATE OR REPLACE TRIGGER TRG_YSEO_SPEND_BUDGET
FOR INSERT OR UPDATE ON YSEO_SPEND_FACT
COMPOUND TRIGGER

  g_keys PK_SEO_BUDGET.T_KEYS;

  -- RO: Iesirea devreme prin RETURN este interzisa in declansatoarele
  --     compuse (PLS-00678), deci garda este un IF care inchide tot corpul.
  -- EN: An early RETURN is forbidden inside compound triggers (PLS-00678),
  --     so the guard is an IF that wraps the whole body.
  BEFORE EACH ROW IS
  BEGIN
    IF NOT PK_SEO_BUDGET.IS_FLAGGING THEN
      IF :NEW.COD IS NULL THEN
        :NEW.COD := YSEO_SPEND_FACT_SEQ.NEXTVAL;
      END IF;

      :NEW.PERIOD   := PK_SEO_UTIL.PERIOD_OF(:NEW.SPEND_DATE);
      :NEW.SUMA_MDL := PK_SEO_UTIL.TO_MDL(:NEW.SUMA, :NEW.VALUTA, :NEW.SPEND_DATE);

      g_keys(g_keys.COUNT + 1) := PK_SEO_BUDGET.MAKE_KEY(
          :NEW.PERIOD, :NEW.ARTICLE_COD1, :NEW.CHANNEL_COD1, :NEW.SITE_COD);
    END IF;
  END BEFORE EACH ROW;

  AFTER STATEMENT IS
  BEGIN
    IF NOT PK_SEO_BUDGET.IS_FLAGGING THEN
      PK_SEO_BUDGET.ENFORCE_KEYS(g_keys);
    END IF;
  END AFTER STATEMENT;

END TRG_YSEO_SPEND_BUDGET;
/
