-- =====================================================================
-- RO: Documentele de strategie si playbook-urile modulului SEOForge.
-- EN: Strategy documents and playbooks of the SEOForge module.
--
-- RO: Caietul de sarcini cere ca lucrul sa fie condus de fisiere Markdown
--     versionate - strategia, planurile, instructiunile pentru sesiunile
--     AI. Ele nu sunt documente contabile si nu au ce cauta in TMDB_DOCS,
--     dar trebuie pastrate langa contur cu istorie completa.
-- EN: The specification requires the work to be driven by versioned
--     Markdown files - the strategy, the plans, the instructions for AI
--     sessions. They are not accounting documents and have no place in
--     TMDB_DOCS, but they must live next to the contour with a full history.
--
-- RO: Regula principala: o versiune publicata nu se mai schimba. Daca
--     strategia s-a schimbat, apare o versiune noua. Altfel peste jumatate
--     de an nu s-ar mai putea spune de ce a fost luata o decizie.
-- EN: The main rule: a published version is never changed again. If the
--     strategy changed, a new version appears. Otherwise in half a year
--     nobody could tell why a decision was taken.
-- =====================================================================

CREATE TABLE YSEO_PLAYBOOK (
    COD             NUMBER          NOT NULL,
    -- RO: Cheia stabila a documentului. Versiunile o impart.
    -- EN: The stable key of the document. Versions share it.
    CODE            VARCHAR2(50)    NOT NULL,
    VERSION         NUMBER          DEFAULT 1 NOT NULL,
    KIND            VARCHAR2(20)    DEFAULT 'STRATEGY' NOT NULL,
    SITE_COD        NUMBER,
    TITLE           VARCHAR2(400)   NOT NULL,
    -- RO: Perioada la care se refera - anul sau luna. EN: The period it
    --     refers to - the year or the month.
    PERIOD          VARCHAR2(10),
    BODY            CLOB            NOT NULL,
    -- RO: Amprenta continutului. Arata dintr-o privire daca textul
    --     coincide cu cel din depozitul de cod.
    -- EN: The content fingerprint. Shows at a glance whether the text
    --     matches the one in the code repository.
    BODY_SHA        VARCHAR2(64)    NOT NULL,
    STATUS          VARCHAR2(20)    DEFAULT 'DRAFT' NOT NULL,
    AUTHOR          VARCHAR2(100),
    NOTE            VARCHAR2(2000),
    CREATED_AT      DATE            DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_YSEO_PLAYBOOK PRIMARY KEY (COD),
    CONSTRAINT UK_YSEO_PLAYBOOK_VER UNIQUE (CODE, VERSION),
    CONSTRAINT FK_YSEO_PLAYBOOK_SITE FOREIGN KEY (SITE_COD)
        REFERENCES YSEO_SITE (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT CK_YSEO_PLAYBOOK_KIND CHECK (
        KIND IN ('STRATEGY', 'PLAYBOOK', 'PLAN', 'REPORT')),
    CONSTRAINT CK_YSEO_PLAYBOOK_STATUS CHECK (
        STATUS IN ('DRAFT', 'ACTIVE', 'ARCHIVED')),
    CONSTRAINT CK_YSEO_PLAYBOOK_PERIOD CHECK (
        PERIOD IS NULL OR REGEXP_LIKE(PERIOD, '^[0-9]{4}(-[0-9]{2})?$'))
);
COMMENT ON TABLE YSEO_PLAYBOOK IS 'RO: Strategii si playbook-uri in Markdown / EN: Strategies and playbooks in Markdown';

CREATE INDEX IX_YSEO_PLAYBOOK_SITE ON YSEO_PLAYBOOK (SITE_COD);
CREATE INDEX IX_YSEO_PLAYBOOK_CODE ON YSEO_PLAYBOOK (CODE, VERSION DESC);

CREATE SEQUENCE YSEO_PLAYBOOK_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/

-- RO: Numarul si versiunea se pun singure. Versiunea se ia din maximul
--     existent pentru aceeasi cheie, ca apelantul sa nu fie nevoit sa o
--     numere si sa nu poata gresi.
-- EN: The number and the version assign themselves. The version is taken
--     from the existing maximum for the same key, so that the caller does
--     not have to count it and cannot get it wrong.
CREATE OR REPLACE TRIGGER TRG_YSEO_PLAYBOOK_ID
BEFORE INSERT ON YSEO_PLAYBOOK FOR EACH ROW
DECLARE
  v_max NUMBER;
BEGIN
  IF :NEW.COD IS NULL THEN
    :NEW.COD := YSEO_PLAYBOOK_SEQ.NEXTVAL;
  END IF;

  IF :NEW.VERSION IS NULL OR :NEW.VERSION = 1 THEN
    SELECT NVL(MAX(VERSION), 0) INTO v_max
    FROM   YSEO_PLAYBOOK WHERE CODE = :NEW.CODE;
    :NEW.VERSION := v_max + 1;
  END IF;
END;
/

-- RO: O versiune publicata este imuabila. Textul si amprenta nu se mai
--     modifica - se creeaza o versiune noua. Statusul si nota raman
--     editabile, ca sa se poata arhiva sau adauga o explicatie.
-- EN: A published version is immutable. The text and the fingerprint are
--     not modified any more - a new version is created instead. The status
--     and the note stay editable, so it can be archived or annotated.
CREATE OR REPLACE TRIGGER TRG_YSEO_PLAYBOOK_FROZEN
BEFORE UPDATE ON YSEO_PLAYBOOK FOR EACH ROW
BEGIN
  IF :OLD.STATUS <> 'DRAFT' THEN
    IF NVL(DBMS_LOB.COMPARE(:NEW.BODY, :OLD.BODY), 1) <> 0
       OR NVL(:NEW.BODY_SHA, '~') <> NVL(:OLD.BODY_SHA, '~')
       OR NVL(:NEW.CODE, '~') <> NVL(:OLD.CODE, '~')
       OR NVL(:NEW.VERSION, -1) <> NVL(:OLD.VERSION, -1) THEN
      RAISE_APPLICATION_ERROR(-20120,
        'RO: Versiunea publicata nu se schimba. Creati o versiune noua. / '
        || 'EN: A published version is not changed. Create a new version.');
    END IF;
  END IF;
END;
/

-- RO: Vederea de lista - fara textul integral, cu lungimea lui si cu
--     descifrarea site-ului. Textul se citeste separat, dupa numar.
-- EN: The list view - without the full text, with its length and with the
--     site lookup. The text is read separately, by number.
CREATE OR REPLACE VIEW VSEO_PLAYBOOK AS
SELECT p.COD, p.CODE, p.VERSION, p.KIND, p.SITE_COD, p.TITLE, p.PERIOD,
       p.BODY_SHA, p.STATUS, p.AUTHOR, p.NOTE, p.CREATED_AT,
       DBMS_LOB.GETLENGTH(p.BODY)                          AS BODY_LEN,
       (SELECT s.DOMAIN FROM YSEO_SITE s WHERE s.COD = p.SITE_COD) CLCSITET,
       CASE WHEN p.VERSION = (SELECT MAX(v.VERSION) FROM YSEO_PLAYBOOK v
                              WHERE v.CODE = p.CODE)
            THEN 1 ELSE 0 END                              AS IS_LATEST
FROM   YSEO_PLAYBOOK p;
