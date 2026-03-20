-- ============================================================
-- Табло отправлений: триггеры
-- ============================================================

CREATE OR REPLACE TRIGGER TR_BUS_DEPARTURES_BIU
BEFORE INSERT OR UPDATE ON BUS_DEPARTURES
FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/
