-- Autopark: parameters with validity periods -- so the customer edits
-- everything himself, and edits it "as of a date" rather than in place.
--
-- Why periods and not plain columns. Every figure here is a business
-- decision that CHANGES: the per-kilometre rate changed from 2.75 to 3.50
-- on 18.09.2026, minimum stock on a station differs between summer and
-- winter, a tanker gets re-certified with other compartments, a station
-- moves from the northern round to the central one. Overwriting the old
-- value destroys the only thing that explains last month's payroll and
-- last month's plan. A period row keeps both answers: what is true now
-- and what was true then.
--
-- Convention for all tables here: VALID_FROM is inclusive, VALID_TO is
-- inclusive and NULL means "open ended". Overlaps are rejected by the
-- application (modules/autopark/supply_rules.py:validate_periods) rather
-- than by a constraint -- Oracle cannot express "no overlapping ranges
-- per key" declaratively without a trigger, and a trigger here would hide
-- the rule from the code that must explain the conflict to the user.

-- ===== Per-kilometre rate and per-trip bonus by period =====
-- The payroll of a past month must not change because somebody edited
-- the rate today. V_FLT_TRIP_PAY picks the row covering TRIP_DATE.
CREATE TABLE FLT_RATE_PERIODS (
  ID           NUMBER(12)    NOT NULL,
  VALID_FROM   DATE          NOT NULL,
  VALID_TO     DATE,
  RATE_PER_KM  NUMBER(6,2)   NOT NULL,
  TRIP_BONUS   NUMBER(8,2)   DEFAULT 0 NOT NULL,
  NOTE         VARCHAR2(300),
  CREATED_AT   DATE          DEFAULT SYSDATE NOT NULL,
  CREATED_BY   VARCHAR2(120),
  CONSTRAINT PK_FLT_RATE_PERIODS PRIMARY KEY (ID),
  CONSTRAINT CK_FLT_RATE_PERIODS_R CHECK (RATE_PER_KM >= 0),
  CONSTRAINT CK_FLT_RATE_PERIODS_B CHECK (TRIP_BONUS >= 0),
  CONSTRAINT CK_FLT_RATE_PERIODS_D CHECK (VALID_TO IS NULL OR VALID_TO >= VALID_FROM)
);
CREATE SEQUENCE SEQ_FLT_RATE_PERIODS START WITH 1 INCREMENT BY 1 CACHE 20;
CREATE INDEX IX_FLT_RATE_PERIODS_FROM ON FLT_RATE_PERIODS (VALID_FROM);
/
CREATE OR REPLACE TRIGGER TRG_FLT_RATE_PERIODS_BI BEFORE INSERT ON FLT_RATE_PERIODS FOR EACH ROW
BEGIN IF :NEW.ID IS NULL THEN SELECT SEQ_FLT_RATE_PERIODS.NEXTVAL INTO :NEW.ID FROM DUAL; END IF; END;
/

-- ===== Planning parameters by period =====
-- The seven-day stock ceiling is a seasonal decision, not a constant:
-- in winter the network holds more, before a price change -- more still.
CREATE TABLE FLT_SUPPLY_PARAMS (
  ID                  NUMBER(12)   NOT NULL,
  VALID_FROM          DATE         NOT NULL,
  VALID_TO            DATE,
  MAX_COVER_DAYS      NUMBER(4,1)  DEFAULT 7 NOT NULL,
  PLAN_HORIZON_DAYS   NUMBER(3)    DEFAULT 2 NOT NULL,
  GROUP_MIN_STATIONS  NUMBER(3)    DEFAULT 2 NOT NULL,
  GROUP_MAX_STATIONS  NUMBER(3)    DEFAULT 4 NOT NULL,
  VOLUME_DIFF_PCT     NUMBER(5,2)  DEFAULT 1 NOT NULL,
  NOTE                VARCHAR2(300),
  CREATED_AT          DATE         DEFAULT SYSDATE NOT NULL,
  CREATED_BY          VARCHAR2(120),
  CONSTRAINT PK_FLT_SUPPLY_PARAMS PRIMARY KEY (ID),
  CONSTRAINT CK_FLT_SP_COVER CHECK (MAX_COVER_DAYS > 0),
  CONSTRAINT CK_FLT_SP_GROUP CHECK (GROUP_MAX_STATIONS >= GROUP_MIN_STATIONS),
  CONSTRAINT CK_FLT_SP_DATES CHECK (VALID_TO IS NULL OR VALID_TO >= VALID_FROM)
);
CREATE SEQUENCE SEQ_FLT_SUPPLY_PARAMS START WITH 1 INCREMENT BY 1 CACHE 20;
CREATE INDEX IX_FLT_SP_FROM ON FLT_SUPPLY_PARAMS (VALID_FROM);
/
CREATE OR REPLACE TRIGGER TRG_FLT_SUPPLY_PARAMS_BI BEFORE INSERT ON FLT_SUPPLY_PARAMS FOR EACH ROW
BEGIN IF :NEW.ID IS NULL THEN SELECT SEQ_FLT_SUPPLY_PARAMS.NEXTVAL INTO :NEW.ID FROM DUAL; END IF; END;
/

-- ===== Tank limits by period =====
-- Minimum stock, allowed fill and the stock ceiling in days -- per tank,
-- per period. The columns on FLT_STATION_TANKS stay as the fallback for
-- tanks the customer has not scheduled yet.
CREATE TABLE FLT_TANK_LIMITS (
  ID              NUMBER(12)    NOT NULL,
  TANK_ID         NUMBER(12)    NOT NULL,
  VALID_FROM      DATE          NOT NULL,
  VALID_TO        DATE,
  MIN_STOCK_L     NUMBER(10,2),
  MAX_FILL_L      NUMBER(10,2),
  MAX_COVER_DAYS  NUMBER(4,1),
  NOTE            VARCHAR2(300),
  CREATED_AT      DATE          DEFAULT SYSDATE NOT NULL,
  CREATED_BY      VARCHAR2(120),
  CONSTRAINT PK_FLT_TANK_LIMITS PRIMARY KEY (ID),
  CONSTRAINT FK_FLT_TANK_LIMITS_TANK FOREIGN KEY (TANK_ID) REFERENCES FLT_STATION_TANKS (ID),
  CONSTRAINT CK_FLT_TL_DATES CHECK (VALID_TO IS NULL OR VALID_TO >= VALID_FROM)
);
CREATE SEQUENCE SEQ_FLT_TANK_LIMITS START WITH 1 INCREMENT BY 1 CACHE 20;
CREATE INDEX IX_FLT_TANK_LIMITS_TANK ON FLT_TANK_LIMITS (TANK_ID, VALID_FROM);
/
CREATE OR REPLACE TRIGGER TRG_FLT_TANK_LIMITS_BI BEFORE INSERT ON FLT_TANK_LIMITS FOR EACH ROW
BEGIN IF :NEW.ID IS NULL THEN SELECT SEQ_FLT_TANK_LIMITS.NEXTVAL INTO :NEW.ID FROM DUAL; END IF; END;
/

-- ===== Validity on the objects that already exist =====
DECLARE
  PROCEDURE add_col(p_table VARCHAR2, p_col VARCHAR2, p_def VARCHAR2) IS
    v_cnt NUMBER;
  BEGIN
    SELECT COUNT(*) INTO v_cnt FROM USER_TAB_COLUMNS
     WHERE TABLE_NAME = p_table AND COLUMN_NAME = p_col;
    IF v_cnt = 0 THEN
      EXECUTE IMMEDIATE 'ALTER TABLE ' || p_table || ' ADD (' || p_col || ' ' || p_def || ')';
    END IF;
  END;
BEGIN
  -- A tanker can be re-certified with a different compartment layout.
  -- NULL on both ends means "always valid", which is what every row
  -- entered before periods existed means.
  add_col('FLT_TRUCK_SECTIONS', 'VALID_FROM', 'DATE');
  add_col('FLT_TRUCK_SECTIONS', 'VALID_TO',   'DATE');

  -- A station can join the northern round in winter and the central one
  -- in summer, so the MEMBERSHIP carries the period, not the group.
  add_col('FLT_STATION_GROUP_ITEMS', 'VALID_FROM', 'DATE');
  add_col('FLT_STATION_GROUP_ITEMS', 'VALID_TO',   'DATE');

  -- Which period row a saved plan was computed with -- so a plan can be
  -- explained months later even after the parameters changed again.
  add_col('FLT_SUPPLY_PLANS', 'PARAMS_ID', 'NUMBER(12)');
END;
/

CREATE INDEX IX_FLT_SUPPLY_PLANS_PARAMS ON FLT_SUPPLY_PLANS (PARAMS_ID);

-- Seed: the currently effective values become the first, open-ended
-- period. Guarded by NOT EXISTS so a re-run adds nothing.
INSERT INTO FLT_RATE_PERIODS (VALID_FROM, VALID_TO, RATE_PER_KM, TRIP_BONUS, NOTE, CREATED_BY)
SELECT DATE '2026-09-18', NULL, s.RATE_PER_KM, s.TRIP_BONUS,
       'Redactia TZ din 18.09.2026', 'seed'
  FROM FLT_SETTINGS s
 WHERE s.ID = 1
   AND NOT EXISTS (SELECT 1 FROM FLT_RATE_PERIODS);

INSERT INTO FLT_SUPPLY_PARAMS (VALID_FROM, VALID_TO, MAX_COVER_DAYS, PLAN_HORIZON_DAYS,
                               GROUP_MIN_STATIONS, GROUP_MAX_STATIONS, VOLUME_DIFF_PCT,
                               NOTE, CREATED_BY)
SELECT DATE '2026-09-18', NULL, NVL(s.MAX_COVER_DAYS, 7), NVL(s.PLAN_HORIZON_DAYS, 2),
       NVL(s.GROUP_MIN_STATIONS, 2), NVL(s.GROUP_MAX_STATIONS, 4),
       NVL(s.VOLUME_DIFF_PCT, 1), 'Redactia TZ din 18.09.2026', 'seed'
  FROM FLT_SETTINGS s
 WHERE s.ID = 1
   AND NOT EXISTS (SELECT 1 FROM FLT_SUPPLY_PARAMS);

COMMIT;
