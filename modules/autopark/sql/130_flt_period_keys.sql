-- Autopark: make the keys period-aware.
--
-- Two constraints written before periods existed forbid exactly what
-- periods are for -- keeping the OLD configuration next to the new one:
--
--   UX_FLT_TRUCK_SECTIONS_SEQ (TRUCK_ID, SEQ_NO) -- a tanker cannot have
--     compartment 1 in two periods, so a re-certification would have to
--     delete the layout the past plans were built on.
--   PK_FLT_STATION_GROUP_ITEMS (GROUP_ID, STATION_ID) -- a station cannot
--     leave a group and come back later.
--
-- Both are replaced by period-aware uniqueness. NVL(VALID_FROM, 1900)
-- keeps rows entered before periods (VALID_FROM IS NULL) comparable:
-- without NVL Oracle treats every NULL as distinct and the index would
-- stop catching real duplicates.

DECLARE
  v_cnt NUMBER;
BEGIN
  -- ===== Compartments of a tanker =====
  SELECT COUNT(*) INTO v_cnt FROM USER_INDEXES
   WHERE INDEX_NAME = 'UX_FLT_TRUCK_SECTIONS_SEQ';
  IF v_cnt > 0 THEN
    EXECUTE IMMEDIATE 'DROP INDEX UX_FLT_TRUCK_SECTIONS_SEQ';
  END IF;

  SELECT COUNT(*) INTO v_cnt FROM USER_INDEXES
   WHERE INDEX_NAME = 'UX_FLT_TRUCK_SEC_PERIOD';
  IF v_cnt = 0 THEN
    EXECUTE IMMEDIATE q'[CREATE UNIQUE INDEX UX_FLT_TRUCK_SEC_PERIOD
      ON FLT_TRUCK_SECTIONS (TRUCK_ID, SEQ_NO, NVL(VALID_FROM, DATE '1900-01-01'))]';
  END IF;
END;
/

-- ===== Group membership gets its own surrogate key =====
DECLARE
  v_cnt NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_cnt FROM USER_TAB_COLUMNS
   WHERE TABLE_NAME = 'FLT_STATION_GROUP_ITEMS' AND COLUMN_NAME = 'ID';
  IF v_cnt = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE FLT_STATION_GROUP_ITEMS ADD (ID NUMBER(12))';
  END IF;

  SELECT COUNT(*) INTO v_cnt FROM USER_SEQUENCES
   WHERE SEQUENCE_NAME = 'SEQ_FLT_STATION_GROUP_ITEMS';
  IF v_cnt = 0 THEN
    EXECUTE IMMEDIATE 'CREATE SEQUENCE SEQ_FLT_STATION_GROUP_ITEMS '
                      || 'START WITH 1 INCREMENT BY 1 CACHE 20';
  END IF;

  -- Existing rows need an ID before it can become the primary key.
  EXECUTE IMMEDIATE 'UPDATE FLT_STATION_GROUP_ITEMS '
                    || 'SET ID = SEQ_FLT_STATION_GROUP_ITEMS.NEXTVAL WHERE ID IS NULL';

  SELECT COUNT(*) INTO v_cnt FROM USER_CONSTRAINTS
   WHERE CONSTRAINT_NAME = 'PK_FLT_STATION_GROUP_ITEMS';
  IF v_cnt > 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE FLT_STATION_GROUP_ITEMS '
                      || 'DROP CONSTRAINT PK_FLT_STATION_GROUP_ITEMS DROP INDEX';
  END IF;

  SELECT COUNT(*) INTO v_cnt FROM USER_CONSTRAINTS
   WHERE CONSTRAINT_NAME = 'PK_FLT_SGI';
  IF v_cnt = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE FLT_STATION_GROUP_ITEMS MODIFY (ID NOT NULL)';
    EXECUTE IMMEDIATE 'ALTER TABLE FLT_STATION_GROUP_ITEMS '
                      || 'ADD CONSTRAINT PK_FLT_SGI PRIMARY KEY (ID)';
  END IF;

  SELECT COUNT(*) INTO v_cnt FROM USER_INDEXES
   WHERE INDEX_NAME = 'UX_FLT_SGI_PERIOD';
  IF v_cnt = 0 THEN
    EXECUTE IMMEDIATE q'[CREATE UNIQUE INDEX UX_FLT_SGI_PERIOD
      ON FLT_STATION_GROUP_ITEMS
         (GROUP_ID, STATION_ID, NVL(VALID_FROM, DATE '1900-01-01'))]';
  END IF;
END;
/

CREATE OR REPLACE TRIGGER TRG_FLT_SGI_BI BEFORE INSERT ON FLT_STATION_GROUP_ITEMS FOR EACH ROW
BEGIN IF :NEW.ID IS NULL THEN SELECT SEQ_FLT_STATION_GROUP_ITEMS.NEXTVAL INTO :NEW.ID FROM DUAL; END IF; END;
/

COMMIT;
