-- FRZ_: Oracle-объекты модуля furnizori. Нормализованная схема, свой префикс.
-- Ставится ТОЛЬКО своим установщиком modules/furnizori/scripts/furnizori_deploy.py.
-- '/' обязателен и ПЕРЕД, и ПОСЛЕ каждого PL/SQL-блока (CLAUDE.md, §2 п.5).
--
-- RO: Corespondenta cu furnizorii — scrisori si atasamente.
--     De ce tabele proprii si nu TMDB_DOCS: TMDB_DOCS e registrul
--     documentelor CONTABILE (numerotare NRMANUAL, formule contabile, TVA).
--     O scrisoare catre furnizor nu e document contabil — nu are suma, nu
--     intra in balanta — si ar strica numerotarea conturilor.
-- EN: Supplier correspondence — letters and attachments. Deliberately kept
--     out of TMDB_DOCS: that is the ACCOUNTING register (invoice numbering,
--     posting formulas, VAT) and a letter is not an accounting document.
--
-- ATENTIE / NOTE: fara caracterul punct-si-virgula in comentarii — analizorul
--     comun deploy_oracle_objects.py taie instructiunile dupa el, si comentariul
--     ar rupe CREATE TABLE in doua bucati invalide.
--
--   TMS_ORG_IMPSRC (sursa furnizorului)
--        └── FRZ_LETTER        (scrisoarea = documentul)      1:N
--                 └── FRZ_LETTER_FILE (.eml, .xlsx in BLOB)   1:N

CREATE TABLE FRZ_LETTER (
  LETTER_ID   NUMBER        NOT NULL,
  SRC_CODE    VARCHAR2(30),             -- RO: = TMS_ORG_IMPSRC.SRC_CODE
  COD_ORG     NUMBER,                   -- RO: = TMS_ORG.COD, daca furnizorul are cartela
  FURNIZOR    VARCHAR2(160) NOT NULL,   -- RO: numele lizibil, si cind nu exista cartela
  SUBIECT     VARCHAR2(400) NOT NULL,
  TIP         VARCHAR2(30)  DEFAULT 'DENUMIRI' NOT NULL,
  N_POZITII   NUMBER,                   -- RO: cite pozitii cere scrisoarea sa fie corectate
  STATUS      VARCHAR2(20)  DEFAULT 'NOU' NOT NULL,
  SENT_TO     VARCHAR2(200),            -- RO: adresa la care s-a trimis
  SENT_AT     DATE,                     -- RO: cind s-a trimis (marcajul cerut)
  ANSWER_AT   DATE,                     -- RO: cind a raspuns furnizorul
  NOTES       VARCHAR2(2000),
  CREATED_BY  VARCHAR2(60),
  CREATED_AT  DATE          DEFAULT SYSDATE NOT NULL,
  UPDATED_AT  DATE          DEFAULT SYSDATE NOT NULL,
  CONSTRAINT PK_FRZ_LETTER  PRIMARY KEY (LETTER_ID),
  CONSTRAINT CK_FRZ_LETTER_ST  CHECK (STATUS IN ('NOU','TRIMIS','RASPUNS','INCHIS')),
  CONSTRAINT CK_FRZ_LETTER_TIP CHECK (TIP IN ('DENUMIRI','PRETURI','STOC','GENERAL'))
);

CREATE INDEX IX_FRZ_LETTER_SRC ON FRZ_LETTER (SRC_CODE, CREATED_AT);
CREATE SEQUENCE FRZ_LETTER_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/
CREATE OR REPLACE TRIGGER FRZ_LETTER_BI
BEFORE INSERT ON FRZ_LETTER FOR EACH ROW
BEGIN
  IF :NEW.LETTER_ID IS NULL THEN
    SELECT FRZ_LETTER_SEQ.NEXTVAL INTO :NEW.LETTER_ID FROM DUAL;
  END IF;
END;
/

COMMENT ON TABLE  FRZ_LETTER IS 'RO: scrisori catre furnizori, cu marcajul trimiterii / EN: supplier letters with sent marker';
COMMENT ON COLUMN FRZ_LETTER.SENT_AT  IS 'RO: completat cind operatorul marcheaza scrisoarea ca trimisa';
COMMENT ON COLUMN FRZ_LETTER.SRC_CODE IS 'RO: leaga scrisoarea de sursa de import a furnizorului';

CREATE TABLE FRZ_LETTER_FILE (
  FILE_ID     NUMBER        NOT NULL,
  LETTER_ID   NUMBER        NOT NULL,
  FILE_NAME   VARCHAR2(260) NOT NULL,
  FILE_KIND   VARCHAR2(20)  DEFAULT 'OTHER' NOT NULL,   -- RO: EML | XLSX | PDF | OTHER
  MIME        VARCHAR2(120),
  FILE_SIZE   NUMBER,
  FILE_SHA256 VARCHAR2(64),             -- RO: acelasi fisier incarcat de doua ori se recunoaste
  FILE_BLOB   BLOB,
  UPLOADED_BY VARCHAR2(60),
  UPLOADED_AT DATE          DEFAULT SYSDATE NOT NULL,
  CONSTRAINT PK_FRZ_LETTER_FILE PRIMARY KEY (FILE_ID),
  CONSTRAINT FK_FRZ_LETTER_FILE FOREIGN KEY (LETTER_ID)
             REFERENCES FRZ_LETTER (LETTER_ID) ON DELETE CASCADE
);

CREATE INDEX IX_FRZ_LETTER_FILE ON FRZ_LETTER_FILE (LETTER_ID);
CREATE SEQUENCE FRZ_LETTER_FILE_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/
CREATE OR REPLACE TRIGGER FRZ_LETTER_FILE_BI
BEFORE INSERT ON FRZ_LETTER_FILE FOR EACH ROW
BEGIN
  IF :NEW.FILE_ID IS NULL THEN
    SELECT FRZ_LETTER_FILE_SEQ.NEXTVAL INTO :NEW.FILE_ID FROM DUAL;
  END IF;
END;
/

COMMENT ON TABLE  FRZ_LETTER_FILE IS 'RO: atasamentele scrisorii (.eml trimis, .xlsx cu pozitii) pastrate in baza / EN: letter attachments kept in the DB';
COMMENT ON COLUMN FRZ_LETTER_FILE.FILE_BLOB IS 'RO: fisierul original, octet cu octet — .eml se redeschide in Outlook';
