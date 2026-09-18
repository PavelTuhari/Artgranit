-- Autopark: views of the fuel-distribution contour (ToR of 18.09.2026).
-- Reporting only -- every figure here is derived, nothing is stored twice.

-- ===== State of one tank, as the planner sees it (p.2, p.3, p.4, p.5) =====
--
-- CURRENT_L is the latest Petrol Expert snapshot for the tank. When the
-- external feed has never delivered anything, the daily closing balance
-- of FLT_STATION_STOCK is used instead, so a freshly installed contour
-- still plans on the numbers the customer already keeps by hand.
--
-- IN_TRANSIT_L (p.5) is fuel already committed but not yet poured into
-- the tank: trip items in the live states of the execution chain. Without
-- this term the same volume is planned twice and the second tanker
-- arrives at a full tank.
--
-- What deliberately does NOT count as in transit, learned on live data:
--   * APPROVED -- in the first contour of the module that is the state of
--     an ALREADY EXECUTED trip (2199 of them sit in the demo database,
--     two years deep). Counting them added ~800 000 l of phantom fuel to
--     every station and the planner reported 620 days of cover on a tank
--     that had 1.1 days left.
--   * DELIVERED -- the tanker has discharged, the fuel is physically in
--     the tank and the Petrol Expert snapshot already shows it. Only the
--     acceptance paperwork is pending.
--   * legacy waybills dated in the past -- they are history, not a plan.
CREATE OR REPLACE VIEW V_FLT_TANK_STATE AS
WITH snap AS (
  SELECT TANK_ID, CURRENT_L, STOCK_TS,
         ROW_NUMBER() OVER (PARTITION BY TANK_ID ORDER BY STOCK_TS DESC, ID DESC) AS RN
    FROM FLT_TANK_STOCK
),
daily AS (
  SELECT STATION_ID, PRODUCT_CODE, CLOSE_L, SALES_L, STOCK_DATE,
         ROW_NUMBER() OVER (PARTITION BY STATION_ID, PRODUCT_CODE
                            ORDER BY STOCK_DATE DESC) AS RN
    FROM FLT_STATION_STOCK
),
sales AS (
  SELECT STATION_ID, PRODUCT_CODE,
         AVG(SALES_L) AS AVG_DAILY_L,
         MAX(CASE WHEN RN = 1 THEN CLOSE_L END) AS LAST_CLOSE_L,
         MAX(CASE WHEN RN = 1 THEN STOCK_DATE END) AS LAST_STOCK_DATE
    FROM daily
   WHERE RN <= 14
   GROUP BY STATION_ID, PRODUCT_CODE
),
transit AS (
  SELECT i.STATION_ID, i.PRODUCT_CODE, SUM(i.VOLUME_L) AS IN_TRANSIT_L
    FROM (SELECT s.STATION_ID, it.PRODUCT_CODE, it.VOLUME_L
            FROM FLT_TRIP_STOP_ITEMS it
            JOIN FLT_TRIP_STOPS s ON s.ID = it.STOP_ID
            JOIN FLT_TRIPS t      ON t.ID = s.TRIP_ID
           WHERE t.STATUS_CODE IN ('PLANNED','LOAD_REQ','LOADED','IN_TRANSIT')
          UNION ALL
          SELECT d.STATION_ID, d.PRODUCT_CODE, d.VOLUME_L
            FROM FLT_DELIVERIES d
           WHERE d.TRIP_ID IS NULL AND d.DELIV_DATE >= TRUNC(SYSDATE)) i
   GROUP BY i.STATION_ID, i.PRODUCT_CODE
)
SELECT tk.ID            AS TANK_ID,
       st.ID            AS STATION_ID,
       st.CODE          AS STATION_CODE,
       st.NAME          AS STATION_NAME,
       tk.PRODUCT_CODE,
       p.FUEL_GROUP,
       tk.CAPACITY_L,
       NVL(tk.MAX_FILL_L, tk.CAPACITY_L) AS MAX_FILL_L,
       NVL(sp.CURRENT_L, NVL(sl.LAST_CLOSE_L, 0)) AS CURRENT_L,
       NVL(sp.STOCK_TS, sl.LAST_STOCK_DATE)       AS STOCK_TS,
       CASE WHEN sp.CURRENT_L IS NOT NULL THEN 'PETROL_EXPERT' ELSE 'DAILY' END AS STOCK_SOURCE,
       NVL(sl.AVG_DAILY_L, 0) AS AVG_DAILY_L,
       NVL(tk.MIN_STOCK_L, NVL(sl.AVG_DAILY_L, 0) * cfg.SAFETY_DAYS) AS MIN_STOCK_L,
       NVL(tk.MAX_COVER_DAYS, cfg.MAX_COVER_DAYS) AS MAX_COVER_DAYS,
       NVL(tr.IN_TRANSIT_L, 0) AS IN_TRANSIT_L,
       -- p.4.1: allowed delivery = allowed fill - actual stock, and what
       -- is already on the road counts as if it were in the tank.
       GREATEST(NVL(tk.MAX_FILL_L, tk.CAPACITY_L)
                - NVL(sp.CURRENT_L, NVL(sl.LAST_CLOSE_L, 0))
                - NVL(tr.IN_TRANSIT_L, 0), 0) AS ALLOWED_L,
       -- Days until the stock falls to the minimum, counting the fuel in
       -- transit. NULL when there are no sales to consume it.
       CASE WHEN NVL(sl.AVG_DAILY_L, 0) > 0
            THEN (NVL(sp.CURRENT_L, NVL(sl.LAST_CLOSE_L, 0))
                  + NVL(tr.IN_TRANSIT_L, 0)
                  - NVL(tk.MIN_STOCK_L, NVL(sl.AVG_DAILY_L, 0) * cfg.SAFETY_DAYS))
                 / sl.AVG_DAILY_L
       END AS DAYS_TO_MIN
  FROM FLT_STATION_TANKS tk
  JOIN FLT_STATIONS st ON st.ID = tk.STATION_ID
  JOIN FLT_PRODUCTS p  ON p.CODE = tk.PRODUCT_CODE
  LEFT JOIN snap sp    ON sp.TANK_ID = tk.ID AND sp.RN = 1
  LEFT JOIN sales sl   ON sl.STATION_ID = tk.STATION_ID AND sl.PRODUCT_CODE = tk.PRODUCT_CODE
  LEFT JOIN transit tr ON tr.STATION_ID = tk.STATION_ID AND tr.PRODUCT_CODE = tk.PRODUCT_CODE
  CROSS JOIN FLT_SETTINGS cfg
 WHERE st.ACTIVE = 1;

-- ===== The plan table the operator approves (p.7) =====
-- The trip a need is served by is taken from its FIRST compartment (the
-- one discharged earliest). Written as a windowed inline view rather than
-- a correlated subquery in the join condition: Oracle refuses the latter
-- with ORA-01799 "a column may not be outer-joined to a subquery".
CREATE OR REPLACE VIEW V_FLT_SUPPLY_PLAN AS
WITH first_load AS (
  SELECT NEED_ID, SUPPLY_TRIP_ID, UNLOAD_SEQ,
         ROW_NUMBER() OVER (PARTITION BY NEED_ID ORDER BY UNLOAD_SEQ) AS RN
    FROM FLT_SUPPLY_LOADS
   WHERE NEED_ID IS NOT NULL
)
SELECT n.PLAN_ID,
       pl.PLAN_DATE,
       pl.STATUS_CODE AS PLAN_STATUS,
       n.ID AS NEED_ID,
       n.STATION_ID,
       st.CODE AS STATION_CODE,
       st.NAME AS STATION_NAME,
       n.PRODUCT_CODE,
       n.CURRENT_L,
       n.AVG_DAILY_L,
       n.MIN_STOCK_L,
       n.MAX_FILL_L,
       n.IN_TRANSIT_L,
       n.DAYS_TO_MIN,
       n.ALLOWED_L,
       n.TARGET_L,
       n.PLANNED_L,
       n.COVER_DAYS,
       n.WARNING,
       stp.ID AS SUPPLY_TRIP_ID,
       stp.SEQ_NO AS TRIP_SEQ,
       tr.PLATE,
       stp.FUEL_GROUP,
       lp.NAME AS LOAD_POINT_NAME,
       stp.EST_KM
  FROM FLT_SUPPLY_NEEDS n
  JOIN FLT_SUPPLY_PLANS pl ON pl.ID = n.PLAN_ID
  JOIN FLT_STATIONS st     ON st.ID = n.STATION_ID
  LEFT JOIN first_load ld        ON ld.NEED_ID = n.ID AND ld.RN = 1
  LEFT JOIN FLT_SUPPLY_TRIPS stp ON stp.ID = ld.SUPPLY_TRIP_ID
  LEFT JOIN FLT_TRUCKS tr        ON tr.ID = stp.TRUCK_ID
  LEFT JOIN FLT_LOAD_POINTS lp   ON lp.ID = stp.LOAD_POINT_ID;

-- ===== Compartment layout of a proposed trip (p.7) =====
-- Ordered the way the driver works: UNLOAD_SEQ 1 first, and that is the
-- tail compartment of the tanker (p.4.2 note).
CREATE OR REPLACE VIEW V_FLT_SUPPLY_LOADS AS
SELECT ld.ID,
       ld.SUPPLY_TRIP_ID,
       stp.PLAN_ID,
       tr.PLATE,
       sec.SEQ_NO AS SECTION_NO,
       sec.VOLUME_L AS SECTION_VOLUME_L,
       ld.STATION_ID,
       st.CODE AS STATION_CODE,
       st.NAME AS STATION_NAME,
       ld.PRODUCT_CODE,
       ld.VOLUME_L,
       ld.UNLOAD_SEQ,
       CASE WHEN ld.VOLUME_L < sec.VOLUME_L THEN 1 ELSE 0 END AS PARTIAL_SECTION
  FROM FLT_SUPPLY_LOADS ld
  JOIN FLT_SUPPLY_TRIPS stp   ON stp.ID = ld.SUPPLY_TRIP_ID
  JOIN FLT_TRUCK_SECTIONS sec ON sec.ID = ld.SECTION_ID
  JOIN FLT_TRUCKS tr          ON tr.ID = stp.TRUCK_ID
  JOIN FLT_STATIONS st        ON st.ID = ld.STATION_ID;

-- ===== Execution control: plan vs loaded vs document vs accepted (p.9) =====
-- A discrepancy is flagged when any pair differs by more than
-- FLT_SETTINGS.VOLUME_DIFF_PCT of the planned volume. Comparing in per
-- cent rather than in litres keeps a 20 l measurement error on a 30 000 l
-- delivery out of the report while still catching a missing compartment.
CREATE OR REPLACE VIEW V_FLT_TRIP_EXECUTION AS
SELECT t.ID AS TRIP_ID,
       t.TRIP_DATE,
       t.STATUS_CODE,
       rs.NAME_RU AS STATUS_NAME,
       rs.SORT_NO AS STATUS_SORT,
       tr.PLATE,
       d.FULL_NAME AS DRIVER_NAME,
       s.SEQ_NO AS STOP_SEQ,
       st.CODE AS STATION_CODE,
       st.NAME AS STATION_NAME,
       it.ID AS ITEM_ID,
       it.PRODUCT_CODE,
       it.VOLUME_L   AS PLAN_L,
       it.LOADED_L,
       it.DOC_L,
       it.ACCEPTED_L,
       it.UNLOAD_SEQ,
       (NVL(it.LOADED_L, it.VOLUME_L) - it.VOLUME_L)            AS DIFF_LOADED_L,
       (NVL(it.DOC_L, NVL(it.LOADED_L, it.VOLUME_L))
          - NVL(it.LOADED_L, it.VOLUME_L))                      AS DIFF_DOC_L,
       (NVL(it.ACCEPTED_L, NVL(it.DOC_L, it.VOLUME_L))
          - NVL(it.DOC_L, it.VOLUME_L))                         AS DIFF_ACCEPTED_L,
       CASE WHEN it.VOLUME_L > 0 AND (
              ABS(NVL(it.LOADED_L, it.VOLUME_L) - it.VOLUME_L) / it.VOLUME_L * 100 > cfg.VOLUME_DIFF_PCT
           OR ABS(NVL(it.DOC_L, it.VOLUME_L) - it.VOLUME_L) / it.VOLUME_L * 100 > cfg.VOLUME_DIFF_PCT
           OR ABS(NVL(it.ACCEPTED_L, it.VOLUME_L) - it.VOLUME_L) / it.VOLUME_L * 100 > cfg.VOLUME_DIFF_PCT)
            THEN 1 ELSE 0
       END AS HAS_DISCREPANCY
  FROM FLT_TRIP_STOP_ITEMS it
  JOIN FLT_TRIP_STOPS s  ON s.ID = it.STOP_ID
  JOIN FLT_TRIPS t       ON t.ID = s.TRIP_ID
  JOIN FLT_STATIONS st   ON st.ID = s.STATION_ID
  JOIN FLT_TRUCKS tr     ON tr.ID = t.TRUCK_ID
  JOIN FLT_DRIVERS d     ON d.ID = t.DRIVER_ID
  LEFT JOIN FLT_REF_TRIP_STATUS rs ON rs.CODE = t.STATUS_CODE
  CROSS JOIN FLT_SETTINGS cfg;

-- ===== Driver pay, redefined over the execution chain =====
-- Supersedes the definition in 121_flt_views.sql. The old rule "anything
-- that is not a DRAFT pays" stopped being true once the chain grew the
-- intermediate states of p.9: a trip that is merely PLANNED or still
-- IN_TRANSIT must not generate salary. The decision now lives in the
-- reference table (FLT_REF_TRIP_STATUS.IS_PAYABLE), not in the SQL text,
-- so adding a state does not mean editing a view.
CREATE OR REPLACE VIEW V_FLT_TRIP_PAY AS
SELECT t.ID AS TRIP_ID,
       t.TRIP_DATE,
       d.ID AS DRIVER_ID,
       d.FULL_NAME AS DRIVER_NAME,
       t.TYPE_CODE,
       t.STATUS_CODE,
       t.NORM_KM,
       t.NORM_KM * cfg.RATE_PER_KM AS KM_PAY,
       CASE WHEN tt.PAYS_BONUS = 1 AND NVL(rs.IS_PAYABLE, 0) = 1
            THEN cfg.TRIP_BONUS ELSE 0
       END AS BONUS_PAY,
       t.NORM_KM * cfg.RATE_PER_KM
         + CASE WHEN tt.PAYS_BONUS = 1 AND NVL(rs.IS_PAYABLE, 0) = 1
                THEN cfg.TRIP_BONUS ELSE 0
           END AS TOTAL_PAY,
       NVL(rs.IS_PAYABLE, 0) AS IS_PAYABLE
  FROM FLT_TRIPS t
  JOIN FLT_DRIVERS d ON d.ID = t.DRIVER_ID
  JOIN FLT_REF_TRIP_TYPES tt ON tt.CODE = t.TYPE_CODE
  LEFT JOIN FLT_REF_TRIP_STATUS rs ON rs.CODE = t.STATUS_CODE
  CROSS JOIN FLT_SETTINGS cfg;
