-- ============================================================
-- Nufarul: lead_days per group + ready_date on order
-- ============================================================

-- 1. Add execution term (working days) to each group
ALTER TABLE NUF_GROUP_PARAMS ADD LEAD_DAYS NUMBER DEFAULT NULL
/

-- 2. Seed default lead_days per group (working days)
UPDATE NUF_GROUP_PARAMS SET LEAD_DAYS = 4 WHERE GROUP_KEY = 'dry_cleaning'
/
UPDATE NUF_GROUP_PARAMS SET LEAD_DAYS = 3 WHERE GROUP_KEY = 'clothing'
/
UPDATE NUF_GROUP_PARAMS SET LEAD_DAYS = 5 WHERE GROUP_KEY = 'carpets'
/
UPDATE NUF_GROUP_PARAMS SET LEAD_DAYS = 2 WHERE GROUP_KEY = 'pillows'
/
UPDATE NUF_GROUP_PARAMS SET LEAD_DAYS = 2 WHERE GROUP_KEY = 'shoes'
/
UPDATE NUF_GROUP_PARAMS SET LEAD_DAYS = 3 WHERE GROUP_KEY = 'laundry'
/
COMMIT
/

-- 3. Add READY_DATE column to order header
ALTER TABLE NUF_ORDERS_LEDGER ADD READY_DATE DATE
/
COMMIT
/
