-- =====================================================================
-- RO: TMS_MPT_WEBATTR — atribute WEB ale marfii, multilingv (RO/RU/EN).
--     Tabela-satelit a dictionarului de marfa, cu ACEEASI schema de cheie ca
--     TMS_MPT: COD = cheie primara SI cheie straina catre TMS_UNIVERS (1:1).
-- EN: TMS_MPT_WEBATTR — multilingual WEB attributes of goods (RO/RU/EN).
--     Satellite of the goods dictionary, same key schema as TMS_MPT:
--     COD is both PK and FK to TMS_UNIVERS (1:1).
--
-- ── De ce BLOB ── / ── Why BLOB ──
-- RO: Baza e CL8MSWIN1251 (un octet) — orice diacritica romaneasca sau semn
--     tipografic scris intr-un camp TEXT devine '?'. Un BLOB pastreaza OCTETII
--     asa cum sint (UTF-8), deci textul ORIGINAL, cu diacritice, supravietuieste
--     indiferent de charset-ul bazei.
-- EN: The DB is single-byte CL8MSWIN1251 — any Romanian diacritic or typographic
--     sign written to a TEXT column becomes '?'. A BLOB keeps the BYTES as-is
--     (UTF-8), so the ORIGINAL text with diacritics survives regardless of charset.
--
-- ── Cine ce editeaza ── / ── What is edited, what is derived ──
-- RO: Se editeaza DOAR campurile BLOB (originalul). Copiile pentru cautare si
--     indexare (CLOB / VARCHAR2, fara diacritice) sint completate AUTOMAT de
--     triggerul TMS_MPT_WEBATTR_BIU. Nu le scrieti manual.
-- EN: Only the BLOB columns are edited (the original). The search/index copies
--     (diacritics-free CLOB / VARCHAR2) are filled AUTOMATICALLY by the
--     TMS_MPT_WEBATTR_BIU trigger. Do not write them by hand.
--
--   TMS_UNIVERS (master, COD)
--        ├── TMS_MPT           (cartela: COD PK/FK)         1:1
--        ├── TMS_MPT_TVR       (imagine, dimensiuni)        1:1
--        ├── TMS_MPT_BARCODE   (COD, BARCODE)               1:N
--        └── TMS_MPT_WEBATTR   (atribute web: COD PK/FK)    1:1   <-- aceasta
-- =====================================================================
SET SQLBLANKLINES ON

CREATE TABLE TMS_MPT_WEBATTR (
  COD                     NUMBER        NOT NULL,  -- RO: = TMS_UNIVERS.COD

  -- ORIGINAL (editabil) — octeti UTF-8, pastreaza diacriticele
  DESCRIERE_RO            BLOB,                    -- RO: descriere / caracteristici tehnice
  DESCRIERE_RU            BLOB,                    -- RU: описание / характеристики
  DESCRIERE_EN            BLOB,                    -- EN: description / specs
  DENUMIRE_FULL_BLOB_RO   BLOB,                    -- RO: denumirea completa a produsului
  DENUMIRE_FULL_BLOB_RU   BLOB,                    -- RU: полное наименование продукта
  DENUMIRE_FULL_BLOB_EN   BLOB,                    -- EN: full product name

  -- DERIVAT de trigger (cautare / indexare vectoriala) — fara diacritice
  DESCRIERE_NON_DIACR_RO  CLOB,                    -- RO: copie text pt. index/cautare
  DESCRIERE_NON_DIACR_RU  CLOB,
  DESCRIERE_NON_DIACR_EN  CLOB,
  DENUMIRE_FULL_RO        VARCHAR2(4000),          -- RO: dublura pt. cautare/index
  DENUMIRE_FULL_RU        VARCHAR2(4000),
  DENUMIRE_FULL_EN        VARCHAR2(4000),

  -- trasabilitate
  SRC                     VARCHAR2(60),            -- RO: furnizor / fisier-sursa
  LOAD_ID                 NUMBER,
  UPDATED_AT              DATE DEFAULT SYSDATE,

  CONSTRAINT TMS_MPT_WEBATTR_PK PRIMARY KEY (COD),
  CONSTRAINT TMS_MPT_WEBATTR_FK FOREIGN KEY (COD) REFERENCES TMS_UNIVERS (COD)
);

COMMENT ON TABLE  TMS_MPT_WEBATTR IS 'RO: atribute web multilingve; BLOB = original cu diacritice, CLOB/VARCHAR2 = copii fara diacritice completate de trigger / EN: multilingual web attributes; BLOB = original, text columns = trigger-filled search copies';
COMMENT ON COLUMN TMS_MPT_WEBATTR.COD                    IS 'RO: cheie = TMS_UNIVERS.COD (ca la TMS_MPT)';
COMMENT ON COLUMN TMS_MPT_WEBATTR.DESCRIERE_RO           IS 'RO: ORIGINAL UTF-8 (se editeaza)';
COMMENT ON COLUMN TMS_MPT_WEBATTR.DESCRIERE_NON_DIACR_RO IS 'RO: DERIVAT de trigger - fara diacritice, pentru cautare/index';
COMMENT ON COLUMN TMS_MPT_WEBATTR.DENUMIRE_FULL_BLOB_RO  IS 'RO: ORIGINAL UTF-8 (se editeaza)';
COMMENT ON COLUMN TMS_MPT_WEBATTR.DENUMIRE_FULL_RO       IS 'RO: DERIVAT de trigger - fara diacritice, pentru cautare/index';

-- =====================================================================
-- RO: Trigger — completeaza AUTOMAT copiile de cautare din campurile BLOB.
--     Ruleaza doar cind BLOB-ul chiar se schimba (INSERT sau UPDATE pe BLOB).
-- EN: Trigger — AUTOMATICALLY fills the search copies from the BLOB columns.
--     Runs only when a BLOB actually changes.
-- =====================================================================
CREATE OR REPLACE TRIGGER TMS_MPT_WEBATTR_BIU
  BEFORE INSERT OR UPDATE ON TMS_MPT_WEBATTR
  FOR EACH ROW
DECLARE
  -- RO: taie la 4000 pentru coloanele VARCHAR2 / EN: cut to 4000 for VARCHAR2 columns
  FUNCTION plain4000(p_blob IN BLOB) RETURN VARCHAR2 IS
    v CLOB := YBIRO_TEXT_UTIL.blob_to_plain(p_blob);
  BEGIN
    IF v IS NULL THEN RETURN NULL; END IF;
    RETURN DBMS_LOB.SUBSTR(v, 4000, 1);
  END;
BEGIN
  -- DESCRIERE_* (BLOB) -> DESCRIERE_NON_DIACR_* (CLOB)
  IF INSERTING OR NVL(DBMS_LOB.COMPARE(:NEW.descriere_ro, :OLD.descriere_ro), 1) <> 0 THEN
    :NEW.descriere_non_diacr_ro := YBIRO_TEXT_UTIL.blob_to_plain(:NEW.descriere_ro);
  END IF;
  IF INSERTING OR NVL(DBMS_LOB.COMPARE(:NEW.descriere_ru, :OLD.descriere_ru), 1) <> 0 THEN
    :NEW.descriere_non_diacr_ru := YBIRO_TEXT_UTIL.blob_to_plain(:NEW.descriere_ru);
  END IF;
  IF INSERTING OR NVL(DBMS_LOB.COMPARE(:NEW.descriere_en, :OLD.descriere_en), 1) <> 0 THEN
    :NEW.descriere_non_diacr_en := YBIRO_TEXT_UTIL.blob_to_plain(:NEW.descriere_en);
  END IF;

  -- DENUMIRE_FULL_BLOB_* (BLOB) -> DENUMIRE_FULL_* (VARCHAR2 4000)
  IF INSERTING OR NVL(DBMS_LOB.COMPARE(:NEW.denumire_full_blob_ro, :OLD.denumire_full_blob_ro), 1) <> 0 THEN
    :NEW.denumire_full_ro := plain4000(:NEW.denumire_full_blob_ro);
  END IF;
  IF INSERTING OR NVL(DBMS_LOB.COMPARE(:NEW.denumire_full_blob_ru, :OLD.denumire_full_blob_ru), 1) <> 0 THEN
    :NEW.denumire_full_ru := plain4000(:NEW.denumire_full_blob_ru);
  END IF;
  IF INSERTING OR NVL(DBMS_LOB.COMPARE(:NEW.denumire_full_blob_en, :OLD.denumire_full_blob_en), 1) <> 0 THEN
    :NEW.denumire_full_en := plain4000(:NEW.denumire_full_blob_en);
  END IF;

  :NEW.updated_at := SYSDATE;
END;
/
