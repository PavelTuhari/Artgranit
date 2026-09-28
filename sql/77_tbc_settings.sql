-- ============================================================
-- TBControl: настройки модуля (конфигурация эмулятора и Zabbix)
-- ============================================================

CREATE TABLE TBC_SETTINGS (
  PARAM_CODE  VARCHAR2(50)   NOT NULL,
  PARAM_VALUE VARCHAR2(1000),
  UPDATED_AT  TIMESTAMP      DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_TBC_SETTINGS PRIMARY KEY (PARAM_CODE)
);

INSERT INTO TBC_SETTINGS (PARAM_CODE, PARAM_VALUE) VALUES ('emulator_interval', '60');
INSERT INTO TBC_SETTINGS (PARAM_CODE, PARAM_VALUE) VALUES ('zabbix_url', '');
INSERT INTO TBC_SETTINGS (PARAM_CODE, PARAM_VALUE) VALUES ('zabbix_token', '');

COMMIT;
