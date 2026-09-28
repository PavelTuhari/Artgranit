-- ============================================================
-- Nufarul: system settings table (UI-configurable params)
-- ============================================================

-- 1. Create settings table
CREATE TABLE NUF_SYSTEM_SETTINGS (
  SETTING_KEY   VARCHAR2(100) PRIMARY KEY,
  SETTING_VALUE VARCHAR2(1000),
  LABEL_RU      VARCHAR2(200),
  UPDATED_AT    DATE DEFAULT SYSDATE
)
/

-- 2. Seed default values
INSERT INTO NUF_SYSTEM_SETTINGS (SETTING_KEY, SETTING_VALUE, LABEL_RU, UPDATED_AT)
VALUES ('param_modal_width', '1000', 'Ширина окна параметров (px)', SYSDATE)
/
COMMIT
/
