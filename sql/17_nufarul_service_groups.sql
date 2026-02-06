-- ============================================================
-- Nufarul: добавление группировки услуг (как на странице заказов)
-- ============================================================

ALTER TABLE NUF_SERVICES ADD SERVICE_GROUP VARCHAR2(80);
COMMENT ON COLUMN NUF_SERVICES.SERVICE_GROUP IS 'Код группы: delivery, dry_cleaning, carpets, pillows_cleaning, laundry, leather_dyeing, conditions, silicone_pillows';

CREATE INDEX IX_NUF_SERVICES_GROUP ON NUF_SERVICES (SERVICE_GROUP);
