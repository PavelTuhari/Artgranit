-- ============================================================
-- PECO: представления контура снабжения топливом
--
-- Все расчёты, которые не должны дублироваться в коде: покрытие
-- резервуара в днях, свободная ёмкость, риск сухого бака, загрузка
-- бензовоза, последнее положение по GPS.
-- ============================================================

-- Резервуар АЗС со средним суточным отпуском и покрытием.
-- Средний отпуск берётся за 28 дней по сверенному факту смен
-- (PECO_TANK_DAILY), а не по сырым транзакциям.
CREATE OR REPLACE VIEW V_PECO_TANK_SUPPLY AS
SELECT t.ID                AS TANK_ID,
       t.STATION_ID,
       s.CODE              AS STATION_CODE,
       s.NAME              AS STATION_NAME,
       s.REGION,
       s.LAT, s.LON, s.ROUTE_ZONE,
       t.CODE              AS TANK_CODE,
       t.GRADE_CODE,
       g.NAME              AS GRADE_NAME,
       g.COLOR             AS GRADE_COLOR,
       t.CAPACITY_L,
       t.CURRENT_L,
       t.MIN_ALARM_L,
       ROUND(t.CURRENT_L / NULLIF(t.CAPACITY_L, 0) * 100, 1) AS FILL_PCT,
       -- Свободная ёмкость: наливать под горловину нельзя, потолок 95 %
       ROUND(t.CAPACITY_L * 0.95 - t.CURRENT_L, 1) AS ULLAGE_L,
       d.AVG_L_28,
       d.AVG_L_7,
       d.DAYS_WITH_DATA,
       -- Покрытие: сколько суток до неснижаемого остатка при текущем темпе
       CASE WHEN NVL(d.AVG_L_28, 0) > 0
            THEN ROUND(GREATEST(t.CURRENT_L - t.MIN_ALARM_L, 0) / d.AVG_L_28, 2)
       END AS DAYS_TO_DRY,
       CASE WHEN NVL(d.AVG_L_28, 0) > 0
             AND GREATEST(t.CURRENT_L - t.MIN_ALARM_L, 0) / d.AVG_L_28 < 2
            THEN 1 ELSE 0 END AS IS_DRY_RISK,
       CASE WHEN t.CURRENT_L <= t.MIN_ALARM_L THEN 1 ELSE 0 END AS IS_BELOW_ALARM
  FROM PECO_TANKS t
  JOIN PECO_STATIONS s        ON s.ID = t.STATION_ID
  JOIN PECO_REF_FUEL_GRADES g ON g.CODE = t.GRADE_CODE
  LEFT JOIN (
      SELECT TANK_ID,
             ROUND(AVG(LITERS), 3) AS AVG_L_28,
             ROUND(AVG(CASE WHEN SALE_DATE > (SELECT MAX(SALE_DATE) - 7 FROM PECO_TANK_DAILY)
                            THEN LITERS END), 3) AS AVG_L_7,
             COUNT(*) AS DAYS_WITH_DATA
        FROM PECO_TANK_DAILY
       WHERE SALE_DATE > (SELECT MAX(SALE_DATE) - 28 FROM PECO_TANK_DAILY)
       GROUP BY TANK_ID
  ) d ON d.TANK_ID = t.ID
 WHERE t.ACTIVE = 1;

-- Станция целиком: сколько резервуаров в риске, суммарная потребность
CREATE OR REPLACE VIEW V_PECO_STATION_SUPPLY AS
SELECT s.ID                AS STATION_ID,
       s.CODE              AS STATION_CODE,
       s.NAME              AS STATION_NAME,
       s.ADDRESS, s.REGION, s.LAT, s.LON, s.ROUTE_ZONE, s.ACCESS_NOTE,
       COUNT(v.TANK_ID)                                  AS TANK_COUNT,
       SUM(v.IS_DRY_RISK)                                AS DRY_RISK_COUNT,
       SUM(v.IS_BELOW_ALARM)                             AS BELOW_ALARM_COUNT,
       ROUND(MIN(v.DAYS_TO_DRY), 2)                      AS MIN_DAYS_TO_DRY,
       ROUND(SUM(v.CURRENT_L), 1)                        AS CURRENT_L,
       ROUND(SUM(v.CAPACITY_L), 1)                       AS CAPACITY_L,
       ROUND(SUM(v.ULLAGE_L), 1)                         AS ULLAGE_L,
       ROUND(SUM(NVL(v.AVG_L_28, 0)), 1)                 AS DAILY_RATE_L,
       CASE WHEN s.LAT IS NULL OR s.LON IS NULL THEN 0 ELSE 1 END AS HAS_GEO
  FROM PECO_STATIONS s
  LEFT JOIN V_PECO_TANK_SUPPLY v ON v.STATION_ID = s.ID
 WHERE s.ACTIVE = 1
 GROUP BY s.ID, s.CODE, s.NAME, s.ADDRESS, s.REGION, s.LAT, s.LON,
          s.ROUTE_ZONE, s.ACCESS_NOTE;

-- Нефтебаза: запас по видам топлива и покрытие сети
CREATE OR REPLACE VIEW V_PECO_DEPOT_STOCK AS
SELECT d.ID              AS DEPOT_ID,
       d.CODE            AS DEPOT_CODE,
       d.NAME            AS DEPOT_NAME,
       d.LAT, d.LON, d.LOAD_BAYS,
       dt.ID             AS DEPOT_TANK_ID,
       dt.GRADE_CODE,
       g.NAME            AS GRADE_NAME,
       g.COLOR           AS GRADE_COLOR,
       dt.CAPACITY_L,
       dt.CURRENT_L,
       dt.MIN_STOCK_L,
       ROUND(dt.CURRENT_L / NULLIF(dt.CAPACITY_L, 0) * 100, 1) AS FILL_PCT,
       net.NET_DAILY_L,
       -- Покрытие нефтебазы: на сколько суток её запаса хватит всей сети
       CASE WHEN NVL(net.NET_DAILY_L, 0) > 0
            THEN ROUND(GREATEST(dt.CURRENT_L - dt.MIN_STOCK_L, 0) / net.NET_DAILY_L, 2)
       END AS DAYS_COVER_NET
  FROM PECO_DEPOTS d
  JOIN PECO_DEPOT_TANKS dt      ON dt.DEPOT_ID = d.ID AND dt.ACTIVE = 1
  JOIN PECO_REF_FUEL_GRADES g   ON g.CODE = dt.GRADE_CODE
  LEFT JOIN (
      SELECT GRADE_CODE, ROUND(SUM(NVL(AVG_L_28, 0)), 1) AS NET_DAILY_L
        FROM V_PECO_TANK_SUPPLY GROUP BY GRADE_CODE
  ) net ON net.GRADE_CODE = dt.GRADE_CODE
 WHERE d.ACTIVE = 1;

-- Заказы топлива с контекстом
CREATE OR REPLACE VIEW V_PECO_FUEL_ORDERS AS
SELECT o.ID, o.ORDER_NO, o.RUN_ID,
       o.STATION_ID, s.CODE AS STATION_CODE, s.NAME AS STATION_NAME,
       s.REGION, s.LAT, s.LON,
       o.SOURCE_CODE,
       src.NAME_RU AS SOURCE_NAME_RU, src.NAME_RO AS SOURCE_NAME_RO,
       src.NAME_EN AS SOURCE_NAME_EN, src.IS_IMPORT,
       o.DEPOT_ID, d.NAME AS DEPOT_NAME,
       o.SUPPLIER_ID, sup.NAME AS SUPPLIER_NAME,
       o.STATUS,
       st.NAME_RU AS STATUS_NAME_RU, st.NAME_RO AS STATUS_NAME_RO,
       st.NAME_EN AS STATUS_NAME_EN, st.SORT_ORDER AS STATUS_ORDER,
       o.NEED_BY, o.LITERS_TOTAL, o.AMOUNT, o.TRIP_ID, tr.TRIP_NO,
       o.NOTE, o.CREATED_BY, o.APPROVED_BY, o.APPROVED_AT,
       o.CREATED_AT, o.UPDATED_AT,
       (SELECT COUNT(*) FROM PECO_FUEL_ORDER_ITEMS i WHERE i.ORDER_ID = o.ID) AS ITEM_COUNT,
       (SELECT NVL(SUM(i.IS_DRY_RISK), 0) FROM PECO_FUEL_ORDER_ITEMS i
         WHERE i.ORDER_ID = o.ID) AS DRY_RISK_COUNT,
       (SELECT ROUND(MIN(i.DAYS_TO_DRY), 2) FROM PECO_FUEL_ORDER_ITEMS i
         WHERE i.ORDER_ID = o.ID) AS MIN_DAYS_TO_DRY
  FROM PECO_FUEL_ORDERS o
  JOIN PECO_STATIONS s              ON s.ID = o.STATION_ID
  JOIN PECO_REF_SUPPLY_SOURCES src  ON src.CODE = o.SOURCE_CODE
  JOIN PECO_REF_ORDER_STATUS st     ON st.CODE = o.STATUS
  LEFT JOIN PECO_DEPOTS d           ON d.ID = o.DEPOT_ID
  LEFT JOIN PECO_FUEL_SUPPLIERS sup ON sup.ID = o.SUPPLIER_ID
  LEFT JOIN PECO_TRIPS tr           ON tr.ID = o.TRIP_ID;

CREATE OR REPLACE VIEW V_PECO_FUEL_ORDER_ITEMS AS
SELECT i.ID, i.ORDER_ID, o.ORDER_NO, i.STATION_ID, i.TANK_ID,
       t.CODE AS TANK_CODE, i.GRADE_CODE,
       g.NAME AS GRADE_NAME, g.COLOR AS GRADE_COLOR,
       t.CAPACITY_L, i.CURRENT_L, i.ULLAGE_L,
       i.LITERS_MODEL, i.LITERS_ORDER,
       i.DAILY_RATE_L, i.DAYS_TO_DRY, i.COVER_AFTER_D, i.IS_DRY_RISK, i.ADJ_REASON,
       CASE WHEN i.LITERS_MODEL IS NOT NULL
             AND ABS(NVL(i.LITERS_ORDER, 0) - i.LITERS_MODEL) > 0.5
            THEN 1 ELSE 0 END AS IS_ADJUSTED
  FROM PECO_FUEL_ORDER_ITEMS i
  JOIN PECO_FUEL_ORDERS o     ON o.ID = i.ORDER_ID
  JOIN PECO_TANKS t           ON t.ID = i.TANK_ID
  JOIN PECO_REF_FUEL_GRADES g ON g.CODE = i.GRADE_CODE;

-- Рейсы: загрузка бензовоза и последнее положение по GPS
CREATE OR REPLACE VIEW V_PECO_TRIPS AS
SELECT tr.ID, tr.TRIP_NO, tr.DEPOT_ID, d.NAME AS DEPOT_NAME,
       tr.TRUCK_ID, tk.PLATE_NO, tk.CAPACITY_L AS TRUCK_CAPACITY_L,
       tk.COMP_COUNT, tk.DRIVER_NAME AS TRUCK_DRIVER,
       tr.DRIVER_NAME, tr.STATUS,
       tr.PLAN_DEPART, tr.ACT_DEPART, tr.PLAN_RETURN, tr.ACT_RETURN,
       tr.LITERS_TOTAL, tr.STOPS_COUNT, tr.DISTANCE_KM, tr.NOTE,
       ROUND(tr.LITERS_TOTAL / NULLIF(tk.CAPACITY_L, 0) * 100, 1) AS LOAD_PCT,
       last_ping.TS        AS LAST_PING_AT,
       last_ping.LAT       AS LAST_LAT,
       last_ping.LON       AS LAST_LON,
       last_ping.SPEED_KMH AS LAST_SPEED,
       last_ping.SEAL_CLOSED,
       (SELECT COUNT(*) FROM PECO_GPS_EVENTS e
         WHERE e.TRIP_ID = tr.ID AND e.STATUS = 'new') AS ALERT_COUNT,
       tr.CREATED_AT
  FROM PECO_TRIPS tr
  JOIN PECO_DEPOTS d  ON d.ID = tr.DEPOT_ID
  JOIN PECO_TRUCKS tk ON tk.ID = tr.TRUCK_ID
  LEFT JOIN (
      SELECT p.* FROM PECO_GPS_PINGS p
       WHERE p.TS = (SELECT MAX(p2.TS) FROM PECO_GPS_PINGS p2 WHERE p2.TRUCK_ID = p.TRUCK_ID)
  ) last_ping ON last_ping.TRUCK_ID = tr.TRUCK_ID;

CREATE OR REPLACE VIEW V_PECO_TRIP_STOPS AS
SELECT st.ID, st.TRIP_ID, tr.TRIP_NO, st.STOP_NO,
       st.STATION_ID, s.CODE AS STATION_CODE, s.NAME AS STATION_NAME,
       s.LAT, s.LON,
       st.ORDER_ID, o.ORDER_NO, st.COMP_ID, c.COMP_NO, c.VOLUME_L AS COMP_VOLUME_L,
       st.GRADE_CODE, g.NAME AS GRADE_NAME, g.COLOR AS GRADE_COLOR,
       st.LITERS_PLAN, st.LITERS_FACT,
       st.PLAN_ARRIVE, st.ACT_ARRIVE, st.ACT_DEPART, st.STATUS
  FROM PECO_TRIP_STOPS st
  JOIN PECO_TRIPS tr    ON tr.ID = st.TRIP_ID
  JOIN PECO_STATIONS s  ON s.ID = st.STATION_ID
  LEFT JOIN PECO_FUEL_ORDERS o        ON o.ID = st.ORDER_ID
  LEFT JOIN PECO_TRUCK_COMPARTMENTS c ON c.ID = st.COMP_ID
  LEFT JOIN PECO_REF_FUEL_GRADES g    ON g.CODE = st.GRADE_CODE;

CREATE OR REPLACE VIEW V_PECO_GPS_EVENTS AS
SELECT e.ID, e.TRUCK_ID, tk.PLATE_NO, e.TRIP_ID, tr.TRIP_NO,
       e.EVENT_TYPE, e.SEVERITY, e.TS, e.LAT, e.LON, e.VALUE_NUM,
       e.MESSAGE_RU, e.MESSAGE_RO, e.MESSAGE_EN, e.STATUS, e.CREATED_AT
  FROM PECO_GPS_EVENTS e
  JOIN PECO_TRUCKS tk ON tk.ID = e.TRUCK_ID
  LEFT JOIN PECO_TRIPS tr ON tr.ID = e.TRIP_ID;

CREATE OR REPLACE VIEW V_PECO_TRUCKS AS
SELECT tk.ID, tk.PLATE_NO, tk.MODEL, tk.DEPOT_ID, d.NAME AS DEPOT_NAME,
       tk.CAPACITY_L, tk.COMP_COUNT, tk.DRIVER_NAME, tk.DRIVER_PHONE,
       tk.GPS_PROVIDER_ID, gp.NAME AS GPS_PROVIDER_NAME, tk.GPS_DEVICE_ID,
       tk.ACTIVE,
       (SELECT COUNT(*) FROM PECO_TRIPS t WHERE t.TRUCK_ID = tk.ID
         AND t.STATUS IN ('planned','loading','en_route')) AS ACTIVE_TRIPS,
       lp.TS AS LAST_PING_AT, lp.LAT AS LAST_LAT, lp.LON AS LAST_LON,
       lp.SPEED_KMH AS LAST_SPEED, lp.SEAL_CLOSED
  FROM PECO_TRUCKS tk
  LEFT JOIN PECO_DEPOTS d        ON d.ID = tk.DEPOT_ID
  LEFT JOIN PECO_GPS_PROVIDERS gp ON gp.ID = tk.GPS_PROVIDER_ID
  LEFT JOIN (
      SELECT p.* FROM PECO_GPS_PINGS p
       WHERE p.TS = (SELECT MAX(p2.TS) FROM PECO_GPS_PINGS p2 WHERE p2.TRUCK_ID = p.TRUCK_ID)
  ) lp ON lp.TRUCK_ID = tk.ID;
