-- ============================================================
-- Табло отправлений: представления
-- ============================================================

CREATE OR REPLACE VIEW V_BUS_DEPARTURES_TODAY AS
SELECT
  d.ID,
  d.ROUTE_CODE       AS ROUTE,
  r.DESTINATION,
  TO_CHAR(d.DEPARTURE_DT, 'HH24:MI') AS DEPARTURE_TIME,
  d.PLATFORM,
  NVL(d.GATE, '-')   AS GATE,
  d.STATUS,
  d.DEPARTURE_DT
FROM BUS_DEPARTURES d
JOIN BUS_ROUTES r ON r.ROUTE_CODE = d.ROUTE_CODE
WHERE TRUNC(d.DEPARTURE_DT) = TRUNC(SYSDATE)
  AND d.STATUS <> 'Отменен'
ORDER BY d.DEPARTURE_DT;

/
