-- Autopark module: reporting views over the FLT_* schema.
-- Prefix: FLT_. Target database: platform cloud ADB (same as SDA).

-- Stock-days coverage per station and product (ToR pt. 7).
--   avg daily sales   = average SALES_L over the last 7 stock dates on file
--   stock days        = current stock (last CLOSE_L) / avg daily sales
--   min stock          = avg daily sales * FLT_SETTINGS.SAFETY_DAYS
--   NEED_SUPPLY        = 1 when current stock is below the minimum
-- Division by a zero/undefined average is guarded with NULLIF/DECODE so
-- a station with no recorded sales yet reports NULL days instead of
-- raising ORA-01476.
CREATE OR REPLACE VIEW V_FLT_STOCK_DAYS AS
WITH ranked AS (
  SELECT s.STATION_ID, s.PRODUCT_CODE, s.STOCK_DATE, s.CLOSE_L, s.SALES_L,
         ROW_NUMBER() OVER (PARTITION BY s.STATION_ID, s.PRODUCT_CODE
                             ORDER BY s.STOCK_DATE DESC) AS RN
  FROM FLT_STATION_STOCK s
),
last7 AS (
  SELECT STATION_ID, PRODUCT_CODE,
         MAX(CASE WHEN RN = 1 THEN CLOSE_L END) AS CURRENT_L,
         MAX(CASE WHEN RN = 1 THEN STOCK_DATE END) AS LAST_STOCK_DATE,
         AVG(CASE WHEN RN <= 7 THEN SALES_L END) AS AVG_DAILY_SALES_L
  FROM ranked
  GROUP BY STATION_ID, PRODUCT_CODE
)
SELECT st.CODE AS STATION_CODE,
       st.NAME AS STATION_NAME,
       l.STATION_ID,
       l.PRODUCT_CODE,
       l.LAST_STOCK_DATE,
       l.CURRENT_L,
       l.AVG_DAILY_SALES_L,
       CASE WHEN NVL(l.AVG_DAILY_SALES_L, 0) > 0
            THEN l.CURRENT_L / l.AVG_DAILY_SALES_L
       END AS STOCK_DAYS,
       l.AVG_DAILY_SALES_L * cfg.SAFETY_DAYS AS MIN_STOCK_L,
       CASE WHEN NVL(l.AVG_DAILY_SALES_L, 0) > 0
                 AND l.CURRENT_L < l.AVG_DAILY_SALES_L * cfg.SAFETY_DAYS
            THEN 1 ELSE 0
       END AS NEED_SUPPLY
FROM last7 l
JOIN FLT_STATIONS st ON st.ID = l.STATION_ID
CROSS JOIN FLT_SETTINGS cfg;

-- Driver pay per trip (ToR pt. 10-11).
--   km pay  = NORM_KM * FLT_SETTINGS.RATE_PER_KM
--   bonus   = FLT_SETTINGS.TRIP_BONUS when the trip type pays a bonus
--             (DOMESTIC) and the trip is not a DRAFT -- a DRAFT trip is
--             not yet payroll basis (ToR pt. 6)
CREATE OR REPLACE VIEW V_FLT_TRIP_PAY AS
SELECT t.ID AS TRIP_ID,
       t.TRIP_DATE,
       d.ID AS DRIVER_ID,
       d.FULL_NAME AS DRIVER_NAME,
       t.TYPE_CODE,
       t.STATUS_CODE,
       t.NORM_KM,
       t.NORM_KM * cfg.RATE_PER_KM AS KM_PAY,
       CASE WHEN tt.PAYS_BONUS = 1 AND t.STATUS_CODE <> 'DRAFT'
            THEN cfg.TRIP_BONUS ELSE 0
       END AS BONUS_PAY,
       t.NORM_KM * cfg.RATE_PER_KM
         + CASE WHEN tt.PAYS_BONUS = 1 AND t.STATUS_CODE <> 'DRAFT'
                THEN cfg.TRIP_BONUS ELSE 0
           END AS TOTAL_PAY
FROM FLT_TRIPS t
JOIN FLT_DRIVERS d ON d.ID = t.DRIVER_ID
JOIN FLT_REF_TRIP_TYPES tt ON tt.CODE = t.TYPE_CODE
CROSS JOIN FLT_SETTINGS cfg;

-- Route/fuel control per trip (ToR pt. 9, 12).
--   km deviation    = FACT_KM - NORM_KM
--   over limit       = deviation exceeds FLT_SETTINGS.KM_DEVIATION_LIMIT
--   norm fuel        = NORM_KM * truck.NORM_L_PER_100KM / 100
CREATE OR REPLACE VIEW V_FLT_TRIP_CONTROL AS
SELECT t.ID AS TRIP_ID,
       t.TRIP_DATE,
       tr.PLATE,
       t.NORM_KM,
       t.FACT_KM,
       (t.FACT_KM - t.NORM_KM) AS KM_DEVIATION,
       CASE WHEN ABS(t.FACT_KM - t.NORM_KM) > cfg.KM_DEVIATION_LIMIT
            THEN 1 ELSE 0
       END AS OVER_KM_LIMIT,
       t.NORM_KM * tr.NORM_L_PER_100KM / 100 AS NORM_FUEL_L
FROM FLT_TRIPS t
JOIN FLT_TRUCKS tr ON tr.ID = t.TRUCK_ID
CROSS JOIN FLT_SETTINGS cfg
WHERE t.FACT_KM IS NOT NULL;
