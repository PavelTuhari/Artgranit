-- ============================================================
-- TBControl: источники мониторинга (Monitoring Sources)
-- По образцу UaMenu Dashboard (unisim-dashboard.una.md):
-- несколько Oracle-источников, каждый читает ybmb_dif_cassa
-- и резолвит DB Links касс (tms_init_params@<LINK>.WORLD).
-- Плюс источники Zabbix и встроенный эмулятор.
-- ============================================================

CREATE SEQUENCE TBC_SOURCES_SEQ  START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE TBC_CASSA_SEQ    START WITH 1 INCREMENT BY 1 NOCACHE;

-- Реестр источников мониторинга
CREATE TABLE TBC_SOURCES (
  ID           NUMBER        NOT NULL,
  CODE         VARCHAR2(30)  NOT NULL,   -- cuptorf26 / cvartalov / bioholda / zabbix34 / emulator
  NAME         VARCHAR2(120) NOT NULL,   -- Cuptorul Fermecat / Cvartalov / Wine / Zabbix Unisim
  KIND         VARCHAR2(20)  NOT NULL,   -- unisim_cassa | zabbix | emulator
  DB_USER      VARCHAR2(100),            -- для unisim_cassa: Oracle-схема источника
  DB_PASSWORD  VARCHAR2(200),
  DB_DSN       VARCHAR2(300),            -- host:port/service
  API_URL      VARCHAR2(300),            -- для zabbix: api_jsonrpc.php
  API_USER     VARCHAR2(100),
  API_SECRET   VARCHAR2(300),            -- пароль или API-token
  ENABLED      CHAR(1)       DEFAULT 'Y',
  SORT_ORDER   NUMBER        DEFAULT 100,
  NOTE         VARCHAR2(300),
  LAST_SYNC_AT TIMESTAMP,
  LAST_STATUS  VARCHAR2(20),             -- OK / ERROR
  LAST_ERROR   VARCHAR2(500),
  CREATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_TBC_SOURCES PRIMARY KEY (ID),
  CONSTRAINT UQ_TBC_SOURCES_CODE UNIQUE (CODE),
  CONSTRAINT CHK_TBC_SRC_KIND CHECK (KIND IN ('unisim_cassa','zabbix','emulator')),
  CONSTRAINT CHK_TBC_SRC_ENABLED CHECK (ENABLED IN ('Y','N'))
);
/

CREATE OR REPLACE TRIGGER TBC_SOURCES_BI
  BEFORE INSERT ON TBC_SOURCES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := TBC_SOURCES_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER TBC_SOURCES_BU
  BEFORE UPDATE ON TBC_SOURCES FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

-- Снимок состояния касс источника (upsert по SOURCE_CODE+DB_LINK)
CREATE TABLE TBC_CASSA_STATE (
  ID            NUMBER        NOT NULL,
  SOURCE_CODE   VARCHAR2(30)  NOT NULL,
  SOURCE_NAME   VARCHAR2(120),
  COD_UNIV      VARCHAR2(30),            -- код родителя (магазина) в tms_univers
  STORE_NAME    VARCHAR2(200),           -- tms_univers.denumirea
  DB_LINK       VARCHAR2(100) NOT NULL,  -- pos1.world
  DB_LINK_PREFIX VARCHAR2(60),
  SHEMA         VARCHAR2(60),
  IN_PROCESS    VARCHAR2(10),
  OFF_LINE      NUMBER,
  SERVER_ID     VARCHAR2(60),            -- ServerID из tms_init_params по DB Link
  STATUS        VARCHAR2(15)  NOT NULL,  -- ONLINE | OFFLINE | SHUTDOWN
  STATUS_REASON VARCHAR2(500),
  LINK_ERROR    VARCHAR2(500),
  CHECKED_AT    TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_TBC_CASSA_STATE PRIMARY KEY (ID),
  CONSTRAINT UQ_TBC_CASSA UNIQUE (SOURCE_CODE, DB_LINK),
  CONSTRAINT CHK_TBC_CASSA_ST CHECK (STATUS IN ('ONLINE','OFFLINE','SHUTDOWN'))
);
/

CREATE OR REPLACE TRIGGER TBC_CASSA_BI
  BEFORE INSERT ON TBC_CASSA_STATE FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := TBC_CASSA_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_TBC_CASSA_SRC ON TBC_CASSA_STATE (SOURCE_CODE, STATUS);

-- Агрегат по магазинам источника (логика UaMenu describeAggregateStatus)
CREATE OR REPLACE VIEW V_TBC_CASSA_STORES AS
SELECT
  c.SOURCE_CODE, c.SOURCE_NAME, c.COD_UNIV, c.STORE_NAME,
  COUNT(*)                                                   AS REG_TOTAL,
  SUM(CASE WHEN c.STATUS = 'ONLINE'   THEN 1 ELSE 0 END)     AS REG_ONLINE,
  SUM(CASE WHEN c.STATUS = 'OFFLINE'  THEN 1 ELSE 0 END)     AS REG_OFFLINE,
  SUM(CASE WHEN c.STATUS = 'SHUTDOWN' THEN 1 ELSE 0 END)     AS REG_SHUTDOWN,
  MAX(c.CHECKED_AT)                                          AS CHECKED_AT,
  CASE
    WHEN SUM(CASE WHEN c.STATUS = 'ONLINE' THEN 1 ELSE 0 END) > 0
     AND SUM(CASE WHEN c.STATUS <> 'ONLINE' THEN 1 ELSE 0 END) > 0
     AND SUM(CASE WHEN c.STATUS = 'ONLINE' THEN 1 ELSE 0 END) / COUNT(*) >= 0.6
      THEN 'FUNCTIONAL'
    WHEN SUM(CASE WHEN c.STATUS = 'OFFLINE' THEN 1 ELSE 0 END) > 0 THEN 'OFFLINE'
    WHEN SUM(CASE WHEN c.STATUS = 'ONLINE' THEN 1 ELSE 0 END) > 0
     AND SUM(CASE WHEN c.STATUS = 'SHUTDOWN' THEN 1 ELSE 0 END) > 0 THEN 'WORKING'
    WHEN SUM(CASE WHEN c.STATUS = 'ONLINE' THEN 1 ELSE 0 END) > 0 THEN 'ONLINE'
    WHEN SUM(CASE WHEN c.STATUS = 'SHUTDOWN' THEN 1 ELSE 0 END) > 0 THEN 'SHUTDOWN'
    ELSE 'OFFLINE'
  END AS STATUS
FROM TBC_CASSA_STATE c
GROUP BY c.SOURCE_CODE, c.SOURCE_NAME, c.COD_UNIV, c.STORE_NAME;

-- Сводка касс по всем источникам
CREATE OR REPLACE VIEW V_TBC_CASSA_STATS AS
SELECT
  (SELECT COUNT(*) FROM TBC_SOURCES WHERE KIND = 'unisim_cassa' AND ENABLED = 'Y') AS SOURCES_TOTAL,
  (SELECT COUNT(*) FROM TBC_SOURCES WHERE KIND = 'unisim_cassa' AND LAST_STATUS = 'ERROR') AS SOURCES_ERROR,
  (SELECT COUNT(*) FROM V_TBC_CASSA_STORES) AS STORES_TOTAL,
  (SELECT COUNT(*) FROM V_TBC_CASSA_STORES WHERE STATUS IN ('ONLINE','FUNCTIONAL','WORKING')) AS STORES_ONLINE,
  (SELECT COUNT(*) FROM V_TBC_CASSA_STORES WHERE STATUS = 'OFFLINE') AS STORES_OFFLINE,
  (SELECT COUNT(*) FROM V_TBC_CASSA_STORES WHERE STATUS = 'SHUTDOWN') AS STORES_SHUTDOWN,
  (SELECT COUNT(*) FROM TBC_CASSA_STATE) AS REG_TOTAL,
  (SELECT COUNT(*) FROM TBC_CASSA_STATE WHERE STATUS = 'ONLINE') AS REG_ONLINE,
  (SELECT COUNT(*) FROM TBC_CASSA_STATE WHERE STATUS = 'OFFLINE') AS REG_OFFLINE,
  (SELECT COUNT(*) FROM TBC_CASSA_STATE WHERE STATUS = 'SHUTDOWN') AS REG_SHUTDOWN,
  (SELECT MAX(CHECKED_AT) FROM TBC_CASSA_STATE) AS CHECKED_AT
FROM DUAL;

-- Источники по умолчанию (креды вводятся в админке модуля)
INSERT INTO TBC_SOURCES (CODE, NAME, KIND, ENABLED, SORT_ORDER, NOTE)
VALUES ('emulator', 'Встроенный эмулятор сценариев', 'emulator', 'Y', 10,
        'Генерирует 10 сценариев из docs/TBControl/SCENARIOS.md по кругу');

INSERT INTO TBC_SOURCES (CODE, NAME, KIND, API_URL, API_USER, ENABLED, SORT_ORDER, NOTE)
VALUES ('zabbix34', 'Zabbix Unisim (3.4.15)', 'zabbix',
        'http://192.168.0.110/zabbix/api_jsonrpc.php', 'Admin', 'N', 20,
        'LXC CT 101 на PROXMOX3, доступен только из LAN 192.168.0.0/24');

INSERT INTO TBC_SOURCES (CODE, NAME, KIND, DB_USER, DB_DSN, ENABLED, SORT_ORDER, NOTE)
VALUES ('cuptorf26', 'Cuptorul Fermecat', 'unisim_cassa', 'cuptorf26',
        'orange.una.md:4024/cloudbd.world', 'N', 30, 'Источник UaMenu Dashboard');

INSERT INTO TBC_SOURCES (CODE, NAME, KIND, DB_USER, DB_DSN, ENABLED, SORT_ORDER, NOTE)
VALUES ('cvartalov', 'Cvartalov', 'unisim_cassa', 'cvartalov',
        'orange.una.md:4024/cloudbd.world', 'N', 40, 'Источник UaMenu Dashboard');

INSERT INTO TBC_SOURCES (CODE, NAME, KIND, DB_USER, DB_DSN, ENABLED, SORT_ORDER, NOTE)
VALUES ('bioholda', 'Wine', 'unisim_cassa', 'bioholda',
        'orange.una.md:4024/cloudbd.world', 'N', 50, 'Источник UaMenu Dashboard');

COMMIT;
