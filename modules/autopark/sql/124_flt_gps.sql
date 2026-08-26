-- Autopark module: GPS layer -- provider registry, live/replay track
-- storage, coordinates on the geo entities already in the schema.
-- Prefix: FLT_. Target database: platform cloud ADB (same as SDA/120-123).
-- Same PL/SQL-block fencing rule as sql/120_flt_tables.sql: '/' BEFORE and
-- AFTER the trigger block -- without the leading '/' the shared splitter
-- glues the preceding CREATE TABLE/INDEX into the same PL/SQL block
-- (SDA incident 25.08.2026, this module docstring in store.py).
--
-- Idempotency of the ALTER ADD statements below: a repeat run of this
-- file hits ORA-01430 ("column being added already exists in table")
-- on every ALTER once the columns are already there. The installer
-- (modules/autopark/scripts/autopark_deploy.py) already treats
-- ORA-01430 as tolerable-not-an-error for every file it runs (see its
-- shared ignore list), so this file needs no separate per-file list --
-- it rides the existing one. Verified live by running --only 124 twice
-- in a row (see .superpowers/sdd/autopark-task5-gps.md).

-- Coordinates on the three geo entities a route already references.
-- Nullable: an entity without a coordinate yet simply does not appear
-- on the map (modules/autopark/templates/autopark.html GPS panel) --
-- it is not an error, just an unmapped point.
ALTER TABLE FLT_STATIONS ADD (LAT NUMBER(9,6), LON NUMBER(9,6));
ALTER TABLE FLT_LOAD_POINTS ADD (LAT NUMBER(9,6), LON NUMBER(9,6));
ALTER TABLE FLT_END_POINTS ADD (LAT NUMBER(9,6), LON NUMBER(9,6));

-- Registry of GPS providers behind the interface (modules/autopark/gps.py).
-- SIM is the simulator seeded below, a real provider is a second row of
-- the same table -- KIND says whether the system pushes to it (HTTP_PUSH:
-- provider calls FLT ingest) or FLT pulls from it (HTTP_PULL: FLT calls
-- the provider API on a schedule) -- see docs/Autopark/GPS_INTEGRATION.md.
CREATE TABLE FLT_GPS_PROVIDERS (
  ID      NUMBER(12)    NOT NULL,
  CODE    VARCHAR2(20)  NOT NULL,
  NAME    VARCHAR2(200) NOT NULL,
  KIND    VARCHAR2(12)  NOT NULL,
  ACTIVE  NUMBER(1)     DEFAULT 1 NOT NULL,
  CONSTRAINT PK_FLT_GPS_PROVIDERS PRIMARY KEY (ID),
  CONSTRAINT CK_FLT_GPS_PROV_KIND CHECK (KIND IN ('SIM','HTTP_PUSH','HTTP_PULL')),
  CONSTRAINT CK_FLT_GPS_PROV_ACT CHECK (ACTIVE IN (0,1))
);
CREATE SEQUENCE SEQ_FLT_GPS_PROVIDERS START WITH 1 INCREMENT BY 1 CACHE 20;
/
CREATE OR REPLACE TRIGGER TRG_FLT_GPS_PROVIDERS_BI BEFORE INSERT ON FLT_GPS_PROVIDERS FOR EACH ROW
BEGIN IF :NEW.ID IS NULL THEN SELECT SEQ_FLT_GPS_PROVIDERS.NEXTVAL INTO :NEW.ID FROM DUAL; END IF; END;
/
CREATE UNIQUE INDEX UX_FLT_GPS_PROVIDERS_CODE ON FLT_GPS_PROVIDERS (CODE);

-- Saved GPS track points -- one row per position sample, per trip. Both
-- the live simulator (autopark_gps_sim.py --live) and a replayed past
-- trip (AutoparkController.gps_replay) write here through the very same
-- ingest path (AutoparkStore.insert_track_points) -- a real device feed
-- would land in the same table through the same call.
CREATE TABLE FLT_GPS_TRACKS (
  ID           NUMBER(12)   NOT NULL,
  TRIP_ID      NUMBER(12)   NOT NULL,
  PROVIDER_ID  NUMBER(12)   NOT NULL,
  TS           DATE         NOT NULL,
  LAT          NUMBER(9,6)  NOT NULL,
  LON          NUMBER(9,6)  NOT NULL,
  SPEED_KMH    NUMBER(6,2),
  CONSTRAINT PK_FLT_GPS_TRACKS PRIMARY KEY (ID),
  CONSTRAINT FK_FLT_GPS_TRACKS_TRIP FOREIGN KEY (TRIP_ID) REFERENCES FLT_TRIPS (ID),
  CONSTRAINT FK_FLT_GPS_TRACKS_PROV FOREIGN KEY (PROVIDER_ID) REFERENCES FLT_GPS_PROVIDERS (ID)
);
CREATE SEQUENCE SEQ_FLT_GPS_TRACKS START WITH 1 INCREMENT BY 1 CACHE 20;
/
CREATE OR REPLACE TRIGGER TRG_FLT_GPS_TRACKS_BI BEFORE INSERT ON FLT_GPS_TRACKS FOR EACH ROW
BEGIN IF :NEW.ID IS NULL THEN SELECT SEQ_FLT_GPS_TRACKS.NEXTVAL INTO :NEW.ID FROM DUAL; END IF; END;
/
CREATE INDEX IX_FLT_GPS_TRACKS_TRIP_TS ON FLT_GPS_TRACKS (TRIP_ID, TS);

-- Seed: register the simulator as a provider (idempotent MERGE, same
-- pattern as sql/122_flt_seed.sql).
MERGE INTO FLT_GPS_PROVIDERS t
USING (SELECT 'SIM' CODE, 'Симулятор GPS (autopark_gps_sim.py)' NAME,
              'SIM' KIND FROM DUAL) s
ON (t.CODE = s.CODE)
WHEN NOT MATCHED THEN INSERT (CODE, NAME, KIND) VALUES (s.CODE, s.NAME, s.KIND)
WHEN MATCHED THEN UPDATE SET t.NAME = s.NAME, t.KIND = s.KIND;

-- Seed coordinates for the 9 demo stations (approximate town centres,
-- Moldova). UPDATE by CODE -- idempotent, a repeat run just overwrites
-- with the same values.
UPDATE FLT_STATIONS SET LAT = 47.380000, LON = 28.820000 WHERE CODE = 'ORH';
UPDATE FLT_STATIONS SET LAT = 47.760000, LON = 27.930000 WHERE CODE = 'BAL';
UPDATE FLT_STATIONS SET LAT = 48.160000, LON = 28.300000 WHERE CODE = 'SOR';
UPDATE FLT_STATIONS SET LAT = 45.900000, LON = 28.190000 WHERE CODE = 'CAH';
UPDATE FLT_STATIONS SET LAT = 47.210000, LON = 27.800000 WHERE CODE = 'UNG';
UPDATE FLT_STATIONS SET LAT = 46.300000, LON = 28.660000 WHERE CODE = 'COM';
UPDATE FLT_STATIONS SET LAT = 48.170000, LON = 27.310000 WHERE CODE = 'EDI';
UPDATE FLT_STATIONS SET LAT = 47.140000, LON = 28.610000 WHERE CODE = 'STR';
UPDATE FLT_STATIONS SET LAT = 47.030000, LON = 28.830000 WHERE CODE = 'CHI';

-- Loading points: Chisinau (KIS) and MSPD share the Chisinau area, both
-- around 47.0/28.85; Constanta (CONST) is the one foreign point.
UPDATE FLT_LOAD_POINTS SET LAT = 47.010000, LON = 28.850000 WHERE CODE = 'KIS';
UPDATE FLT_LOAD_POINTS SET LAT = 47.000000, LON = 28.860000 WHERE CODE = 'MSPD';
UPDATE FLT_LOAD_POINTS SET LAT = 44.170000, LON = 28.650000 WHERE CODE = 'CONST';

-- Base/garage end point.
UPDATE FLT_END_POINTS SET LAT = 47.020000, LON = 28.860000 WHERE CODE = 'BAZA';
