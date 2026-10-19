-- Autopark: reference data of the 18.09.2026 ToR. Idempotent -- MERGE or
-- guarded UPDATE only, safe to re-run on a live schema.

-- ===== Loading terminals named in the ToR =====
-- Chisinau and MSPD are domestic, everything beyond the border makes the
-- trip an import one (and therefore pays no domestic trip bonus).
MERGE INTO FLT_LOAD_POINTS t
USING (SELECT 'KIS' CODE, 'Chisinau' NAME, 0 IS_FOREIGN FROM DUAL
       UNION ALL SELECT 'MSPD',   'MSPD',     0 FROM DUAL
       UNION ALL SELECT 'CONST',  'Constanta',1 FROM DUAL
       UNION ALL SELECT 'BURGAS', 'Burgas',   1 FROM DUAL
       UNION ALL SELECT 'RUSE',   'Ruse',     1 FROM DUAL
       UNION ALL SELECT 'NAVOD',  'Navodari', 1 FROM DUAL) s
ON (t.CODE = s.CODE)
WHEN NOT MATCHED THEN INSERT (CODE, NAME, IS_FOREIGN)
  VALUES (s.CODE, s.NAME, s.IS_FOREIGN);

-- ===== Parking lot: the point a norm route starts and ends at =====
-- The fleet ToR counts the leg "parking -> loading terminal" into the norm
-- mileage. Reusing FLT_END_POINTS for it instead of adding a near-identical
-- table -- a parking lot and a route end point are the same kind of object.
MERGE INTO FLT_END_POINTS t
USING (SELECT 'BAZA' CODE, 'Baza Chisinau' NAME FROM DUAL
       UNION ALL SELECT 'PARC', 'Parcare Chisinau' FROM DUAL) s
ON (t.CODE = s.CODE)
WHEN NOT MATCHED THEN INSERT (CODE, NAME) VALUES (s.CODE, s.NAME);

-- ===== Execution chain of p.9 =====
-- SORT_NO orders the chain, IS_PAYABLE decides whether the trip is payroll
-- basis, IS_FINAL closes it. DRAFT/APPROVED/DONE stay for the rows already
-- in the database -- deleting them would orphan live trips.
MERGE INTO FLT_REF_TRIP_STATUS t
USING (SELECT 'DRAFT'      CODE, 'Ciorna' NAME_RU,               10 SORT_NO, 0 IS_PAYABLE, 0 IS_FINAL FROM DUAL
       UNION ALL SELECT 'PLANNED',    'Planificat',              20, 0, 0 FROM DUAL
       UNION ALL SELECT 'LOAD_REQ',   'Cerere de incarcare',     30, 0, 0 FROM DUAL
       UNION ALL SELECT 'LOADED',     'Incarcat',                40, 0, 0 FROM DUAL
       UNION ALL SELECT 'IN_TRANSIT', 'In drum',                 50, 0, 0 FROM DUAL
       UNION ALL SELECT 'DELIVERED',  'Livrat',                  60, 1, 0 FROM DUAL
       UNION ALL SELECT 'ACCEPTED',   'Receptionat de statie',   70, 1, 1 FROM DUAL
       UNION ALL SELECT 'APPROVED',   'Aprobat',                 25, 1, 0 FROM DUAL
       UNION ALL SELECT 'DONE',       'Finalizat',               80, 1, 1 FROM DUAL
       UNION ALL SELECT 'CANCELLED',  'Anulat',                  90, 0, 1 FROM DUAL) s
ON (t.CODE = s.CODE)
WHEN MATCHED THEN UPDATE SET t.SORT_NO = s.SORT_NO,
                             t.IS_PAYABLE = s.IS_PAYABLE,
                             t.IS_FINAL = s.IS_FINAL
WHEN NOT MATCHED THEN INSERT (CODE, NAME_RU, SORT_NO, IS_PAYABLE, IS_FINAL)
  VALUES (s.CODE, s.NAME_RU, s.SORT_NO, s.IS_PAYABLE, s.IS_FINAL);

-- ===== Fuel families (p.6) =====
MERGE INTO FLT_PRODUCTS t
USING (SELECT 'A92' CODE, 'PETROL' FG FROM DUAL
       UNION ALL SELECT 'A95', 'PETROL' FROM DUAL
       UNION ALL SELECT 'A98', 'PETROL' FROM DUAL
       UNION ALL SELECT 'DIESEL', 'DIESEL' FROM DUAL) s
ON (t.CODE = s.CODE)
WHEN MATCHED THEN UPDATE SET t.FUEL_GROUP = s.FG;

-- ===== Rate of the 18.09.2026 ToR =====
-- 3.50 lei per km, and the per-trip bonus is gone: the new document states
-- the salary as mileage x rate and nothing else. Both stay editable in the
-- settings form -- "the rate is a changeable parameter" is in the ToR.
--
-- The guard matters. The update only fires on a contour still carrying the
-- previous default (2.75 / 600). A rate the customer has already tuned by
-- hand is not overwritten by a re-run of this file.
UPDATE FLT_SETTINGS
   SET RATE_PER_KM = 3.50, TRIP_BONUS = 0
 WHERE ID = 1 AND RATE_PER_KM = 2.75 AND TRIP_BONUS = 600;

UPDATE FLT_SETTINGS SET MAX_COVER_DAYS = 7 WHERE ID = 1 AND MAX_COVER_DAYS IS NULL;
UPDATE FLT_SETTINGS SET PLAN_HORIZON_DAYS = 2 WHERE ID = 1 AND PLAN_HORIZON_DAYS IS NULL;
UPDATE FLT_SETTINGS SET GROUP_MIN_STATIONS = 2 WHERE ID = 1 AND GROUP_MIN_STATIONS IS NULL;
UPDATE FLT_SETTINGS SET GROUP_MAX_STATIONS = 4 WHERE ID = 1 AND GROUP_MAX_STATIONS IS NULL;
UPDATE FLT_SETTINGS SET VOLUME_DIFF_PCT = 1 WHERE ID = 1 AND VOLUME_DIFF_PCT IS NULL;

-- ===== Compartments for tankers that have none described yet =====
-- The ToR fixes the layout: 5 compartments for petrol tankers, 4 for
-- diesel ones. Until the customer hands over the real per-compartment
-- volumes, the capacity is split evenly -- an explicit, replaceable
-- approximation rather than a silent one, and SECTIONS_CNT keeps telling
-- the truth about how many compartments the tanker has.
INSERT INTO FLT_TRUCK_SECTIONS (TRUCK_ID, SEQ_NO, VOLUME_L)
SELECT t.ID, lvl.COLUMN_VALUE,
       ROUND(t.CAPACITY_L / t.SECTIONS_CNT, 2)
  FROM FLT_TRUCKS t,
       TABLE(CAST(MULTISET(SELECT LEVEL FROM DUAL
                            CONNECT BY LEVEL <= t.SECTIONS_CNT) AS SYS.ODCINUMBERLIST)) lvl
 WHERE NOT EXISTS (SELECT 1 FROM FLT_TRUCK_SECTIONS s WHERE s.TRUCK_ID = t.ID);

COMMIT;
