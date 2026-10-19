-- ============================================================
-- PECO: представления (V_PECO_*)
-- ============================================================

CREATE OR REPLACE VIEW V_PECO_TANK_LEVELS AS
SELECT t.ID            AS TANK_ID,
       t.STATION_ID,
       s.CODE          AS STATION_CODE,
       s.NAME          AS STATION_NAME,
       t.CODE          AS TANK_CODE,
       t.GRADE_CODE,
       g.NAME          AS GRADE_NAME,
       t.CAPACITY_L,
       t.CURRENT_L,
       t.MIN_ALARM_L,
       ROUND(t.CURRENT_L / NULLIF(t.CAPACITY_L, 0) * 100, 1) AS FILL_PCT,
       CASE WHEN t.CURRENT_L <= t.MIN_ALARM_L THEN 1 ELSE 0 END AS IS_LOW
  FROM PECO_TANKS t
  JOIN PECO_STATIONS s          ON s.ID = t.STATION_ID
  JOIN PECO_REF_FUEL_GRADES g   ON g.CODE = t.GRADE_CODE
 WHERE t.ACTIVE = 1;

-- Сводка смены: литры по счётчику, литры по транзакциям, деньги по
-- способам оплаты. MIA QR отделён от наличных намеренно.
CREATE OR REPLACE VIEW V_PECO_SHIFT_SUMMARY AS
SELECT sh.ID              AS SHIFT_ID,
       sh.STATION_ID,
       st.NAME            AS STATION_NAME,
       sh.STATUS_CODE,
       sh.OPENED_AT,
       sh.CLOSED_AT,
       (SELECT NVL(SUM(sm.METER_CLOSE - sm.METER_OPEN), 0)
          FROM PECO_SHIFT_METERS sm
         WHERE sm.SHIFT_ID = sh.ID
           AND sm.METER_CLOSE IS NOT NULL)              AS METER_DELTA,
       (SELECT NVL(SUM(t.LITERS), 0) FROM PECO_TXN t
         WHERE t.SHIFT_ID = sh.ID AND t.STATUS_CODE = 'PAID')  AS TXN_LITERS,
       (SELECT NVL(SUM(t.AMOUNT), 0) FROM PECO_TXN t
         WHERE t.SHIFT_ID = sh.ID AND t.STATUS_CODE = 'PAID'
           AND t.PAY_METHOD = 'CASH')                   AS CASH_AMOUNT,
       (SELECT NVL(SUM(t.AMOUNT), 0) FROM PECO_TXN t
         WHERE t.SHIFT_ID = sh.ID AND t.STATUS_CODE = 'PAID'
           AND t.PAY_METHOD = 'MIA_QR')                 AS MIA_AMOUNT,
       (SELECT COUNT(*) FROM PECO_TXN t
         WHERE t.SHIFT_ID = sh.ID
           AND t.STATUS_CODE IN ('DISPENSING','AWAITING_PAY')) AS OPEN_TXN_COUNT,
       sh.CASH_DECLARED,
       sh.CASH_EXPECTED,
       sh.CASH_VARIANCE,
       sh.LITER_VARIANCE,
       sh.TANK_VARIANCE
  FROM PECO_SHIFTS sh
  JOIN PECO_STATIONS st ON st.ID = sh.STATION_ID;

CREATE OR REPLACE VIEW V_PECO_STATION_DAILY AS
SELECT t.GRADE_CODE,
       sh.STATION_ID,
       st.NAME                     AS STATION_NAME,
       TRUNC(t.PAID_AT)            AS SALE_DAY,
       COUNT(*)                    AS TXN_COUNT,
       SUM(t.LITERS)               AS LITERS,
       SUM(t.AMOUNT)               AS AMOUNT,
       SUM(CASE WHEN t.IS_SELF_SERVICE = 1 THEN t.LITERS ELSE 0 END) AS SELF_LITERS
  FROM PECO_TXN t
  JOIN PECO_SHIFTS sh   ON sh.ID = t.SHIFT_ID
  JOIN PECO_STATIONS st ON st.ID = sh.STATION_ID
 WHERE t.STATUS_CODE = 'PAID'
 GROUP BY t.GRADE_CODE, sh.STATION_ID, st.NAME, TRUNC(t.PAID_AT);

-- Расхождения закрытых смен: три независимых показателя.
CREATE OR REPLACE VIEW V_PECO_VARIANCE AS
SELECT sh.ID           AS SHIFT_ID,
       sh.STATION_ID,
       st.NAME         AS STATION_NAME,
       sh.CLOSED_AT,
       sh.STATUS_CODE,
       sh.LITER_VARIANCE,
       sh.CASH_VARIANCE,
       sh.TANK_VARIANCE,
       e.FULL_NAME     AS CLOSED_BY_NAME
  FROM PECO_SHIFTS sh
  JOIN PECO_STATIONS st  ON st.ID = sh.STATION_ID
  LEFT JOIN PECO_EMPLOYEES e ON e.ID = sh.CLOSED_BY
 WHERE sh.STATUS_CODE IN ('CLOSED','DISPUTED');
