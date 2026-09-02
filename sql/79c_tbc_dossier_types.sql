-- ============================================================
-- TBControl: AI-досье для новых сущностей — service (TBC_SERVICES),
-- cassa (TBC_CASSA_STATE), store, pve (TBC_PVE_OBJECTS).
-- Восстановлено 02.09.2026 по фактическому ограничению в ADB.
-- ============================================================

ALTER TABLE TBC_AI_DOSSIERS DROP CONSTRAINT CHK_TBC_DSR_SRC;
/
ALTER TABLE TBC_AI_DOSSIERS ADD CONSTRAINT CHK_TBC_DSR_SRC
  CHECK (SOURCE_TYPE IN ('event','incident','flow','node','device',
                         'service','cassa','store','pve'));
/
