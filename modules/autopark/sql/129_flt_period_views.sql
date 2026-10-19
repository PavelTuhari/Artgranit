-- Autopark: views that resolve the period-based parameters.
-- Supersedes the definitions of V_FLT_TANK_STATE (126) and V_FLT_TRIP_PAY
-- (121, then 126). Everything else in those files stays as it is.

-- ===== Parameters effective today =====
-- One row, or none when the customer has not scheduled any period yet --
-- in that case the caller falls back to FLT_SETTINGS.
CREATE OR REPLACE VIEW V_FLT_PARAMS_NOW AS
SELECT ID, VALID_FROM, VALID_TO, MAX_COVER_DAYS, PLAN_HORIZON_DAYS,
       GROUP_MIN_STATIONS, GROUP_MAX_STATIONS, VOLUME_DIFF_PCT, NOTE
  FROM (SELECT p.*, ROW_NUMBER() OVER (ORDER BY VALID_FROM DESC, ID DESC) AS RN
          FROM FLT_SUPPLY_PARAMS p
         WHERE p.VALID_FROM <= TRUNC(SYSDATE)
           AND (p.VALID_TO IS NULL OR p.VALID_TO >= TRUNC(SYSDATE)))
 WHERE RN = 1;

-- ===== Tank limits effective today =====
CREATE OR REPLACE VIEW V_FLT_TANK_LIMITS_NOW AS
SELECT TANK_ID, ID AS LIMIT_ID, VALID_FROM, VALID_TO,
       MIN_STOCK_L, MAX_FILL_L, MAX_COVER_DAYS, NOTE
  FROM (SELECT l.*, ROW_NUMBER() OVER (PARTITION BY l.TANK_ID
                                       ORDER BY l.VALID_FROM DESC, l.ID DESC) AS RN
          FROM FLT_TANK_LIMITS l
         WHERE l.VALID_FROM <= TRUNC(SYSDATE)
           AND (l.VALID_TO IS NULL OR l.VALID_TO >= TRUNC(SYSDATE)))
 WHERE RN = 1;

-- ===== State of one tank, now with period-aware limits =====
-- Priority of every limit: the scheduled period row, then the value on
-- the tank itself, then the global setting. The customer edits the
-- period, and the tank columns remain the fallback for everything he has
-- not scheduled, so nothing breaks the day periods are introduced.
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
       NVL(lim.MAX_FILL_L, NVL(tk.MAX_FILL_L, tk.CAPACITY_L)) AS MAX_FILL_L,
       NVL(sp.CURRENT_L, NVL(sl.LAST_CLOSE_L, 0)) AS CURRENT_L,
       NVL(sp.STOCK_TS, sl.LAST_STOCK_DATE)       AS STOCK_TS,
       CASE WHEN sp.CURRENT_L IS NOT NULL THEN 'PETROL_EXPERT' ELSE 'DAILY' END AS STOCK_SOURCE,
       NVL(sl.AVG_DAILY_L, 0) AS AVG_DAILY_L,
       NVL(lim.MIN_STOCK_L,
           NVL(tk.MIN_STOCK_L, NVL(sl.AVG_DAILY_L, 0) * cfg.SAFETY_DAYS)) AS MIN_STOCK_L,
       NVL(lim.MAX_COVER_DAYS,
           NVL(tk.MAX_COVER_DAYS, NVL(par.MAX_COVER_DAYS, cfg.MAX_COVER_DAYS))) AS MAX_COVER_DAYS,
       lim.LIMIT_ID,
       lim.VALID_FROM AS LIMIT_FROM,
       lim.VALID_TO   AS LIMIT_TO,
       NVL(tr.IN_TRANSIT_L, 0) AS IN_TRANSIT_L,
       GREATEST(NVL(lim.MAX_FILL_L, NVL(tk.MAX_FILL_L, tk.CAPACITY_L))
                - NVL(sp.CURRENT_L, NVL(sl.LAST_CLOSE_L, 0))
                - NVL(tr.IN_TRANSIT_L, 0), 0) AS ALLOWED_L,
       CASE WHEN NVL(sl.AVG_DAILY_L, 0) > 0
            THEN (NVL(sp.CURRENT_L, NVL(sl.LAST_CLOSE_L, 0))
                  + NVL(tr.IN_TRANSIT_L, 0)
                  - NVL(lim.MIN_STOCK_L,
                        NVL(tk.MIN_STOCK_L, NVL(sl.AVG_DAILY_L, 0) * cfg.SAFETY_DAYS)))
                 / sl.AVG_DAILY_L
       END AS DAYS_TO_MIN
  FROM FLT_STATION_TANKS tk
  JOIN FLT_STATIONS st ON st.ID = tk.STATION_ID
  JOIN FLT_PRODUCTS p  ON p.CODE = tk.PRODUCT_CODE
  LEFT JOIN snap sp    ON sp.TANK_ID = tk.ID AND sp.RN = 1
  LEFT JOIN sales sl   ON sl.STATION_ID = tk.STATION_ID AND sl.PRODUCT_CODE = tk.PRODUCT_CODE
  LEFT JOIN transit tr ON tr.STATION_ID = tk.STATION_ID AND tr.PRODUCT_CODE = tk.PRODUCT_CODE
  LEFT JOIN V_FLT_TANK_LIMITS_NOW lim ON lim.TANK_ID = tk.ID
  CROSS JOIN FLT_SETTINGS cfg
  LEFT JOIN V_FLT_PARAMS_NOW par ON 1 = 1
 WHERE st.ACTIVE = 1;

-- ===== Driver pay at the rate effective ON THE DATE OF THE TRIP =====
-- Not at today's rate. Payroll for August must stay what it was after the
-- rate changed in September -- otherwise a closed month silently changes
-- its numbers, and that is an accounting incident, not a feature.
CREATE OR REPLACE VIEW V_FLT_TRIP_PAY AS
SELECT t.ID AS TRIP_ID,
       t.TRIP_DATE,
       d.ID AS DRIVER_ID,
       d.FULL_NAME AS DRIVER_NAME,
       t.TYPE_CODE,
       t.STATUS_CODE,
       t.NORM_KM,
       eff.RATE_PER_KM,
       t.NORM_KM * eff.RATE_PER_KM AS KM_PAY,
       CASE WHEN tt.PAYS_BONUS = 1 AND NVL(rs.IS_PAYABLE, 0) = 1
            THEN eff.TRIP_BONUS ELSE 0
       END AS BONUS_PAY,
       t.NORM_KM * eff.RATE_PER_KM
         + CASE WHEN tt.PAYS_BONUS = 1 AND NVL(rs.IS_PAYABLE, 0) = 1
                THEN eff.TRIP_BONUS ELSE 0
           END AS TOTAL_PAY,
       NVL(rs.IS_PAYABLE, 0) AS IS_PAYABLE
  FROM FLT_TRIPS t
  JOIN FLT_DRIVERS d ON d.ID = t.DRIVER_ID
  JOIN FLT_REF_TRIP_TYPES tt ON tt.CODE = t.TYPE_CODE
  LEFT JOIN FLT_REF_TRIP_STATUS rs ON rs.CODE = t.STATUS_CODE
  CROSS JOIN FLT_SETTINGS cfg
  CROSS JOIN LATERAL (
        SELECT NVL((SELECT rp.RATE_PER_KM FROM FLT_RATE_PERIODS rp
                     WHERE rp.VALID_FROM <= t.TRIP_DATE
                       AND (rp.VALID_TO IS NULL OR rp.VALID_TO >= t.TRIP_DATE)
                     ORDER BY rp.VALID_FROM DESC, rp.ID DESC
                     FETCH FIRST 1 ROWS ONLY), cfg.RATE_PER_KM) AS RATE_PER_KM,
               NVL((SELECT rp.TRIP_BONUS FROM FLT_RATE_PERIODS rp
                     WHERE rp.VALID_FROM <= t.TRIP_DATE
                       AND (rp.VALID_TO IS NULL OR rp.VALID_TO >= t.TRIP_DATE)
                     ORDER BY rp.VALID_FROM DESC, rp.ID DESC
                     FETCH FIRST 1 ROWS ONLY), cfg.TRIP_BONUS) AS TRIP_BONUS
          FROM DUAL) eff;
