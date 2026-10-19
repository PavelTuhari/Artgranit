-- ============================================================
-- TBControl: Proxmox VE (PROXMOX3) через mTLS-шлюз — TBC_PVE_OBJECTS.
-- Ноды, VM (qemu), контейнеры (lxc), хранилища; HEALTH по порогам
-- models/tbc_proxmox.py (диск 85/95 %, CPU 75/90 %, RAM 90/97 %).
-- Восстановлено 02.09.2026 по фактической схеме ADB.
-- ============================================================

CREATE SEQUENCE TBC_PVE_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/

CREATE TABLE TBC_PVE_OBJECTS (
  ID            NUMBER         NOT NULL,
  SOURCE_CODE   VARCHAR2(30)   NOT NULL,   -- TBC_SOURCES.CODE (kind=proxmox)
  OBJ_TYPE      VARCHAR2(10)   NOT NULL,   -- node | qemu | lxc | storage
  OBJ_ID        VARCHAR2(60)   NOT NULL,   -- имя ноды / vmid / имя хранилища
  NAME          VARCHAR2(200),
  NODE_NAME     VARCHAR2(100),
  STATUS        VARCHAR2(20)   NOT NULL,   -- online/offline, running/stopped, active/inactive/disabled
  HEALTH        VARCHAR2(10)   NOT NULL,   -- OK | WARN | CRIT
  HEALTH_REASON VARCHAR2(500),
  CPU_PCT       NUMBER,
  MEM_PCT       NUMBER,
  MEM_USED_MB   NUMBER,
  MEM_MAX_MB    NUMBER,
  DISK_PCT      NUMBER,
  DISK_USED_GB  NUMBER,
  DISK_MAX_GB   NUMBER,
  UPTIME_DAYS   NUMBER,
  PVE_VERSION   VARCHAR2(40),              -- только для node
  EXTRA         VARCHAR2(1000),            -- «шаблон», тип/контент хранилища, load
  CHECKED_AT    TIMESTAMP      DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_TBC_PVE PRIMARY KEY (ID),
  CONSTRAINT UQ_TBC_PVE UNIQUE (SOURCE_CODE, OBJ_TYPE, OBJ_ID),
  CONSTRAINT CHK_TBC_PVE_TYPE CHECK (OBJ_TYPE IN ('node','qemu','lxc','storage')),
  CONSTRAINT CHK_TBC_PVE_HEALTH CHECK (HEALTH IN ('OK','WARN','CRIT'))
);
/

CREATE OR REPLACE TRIGGER TBC_PVE_BI
  BEFORE INSERT ON TBC_PVE_OBJECTS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := TBC_PVE_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_TBC_PVE_SRC ON TBC_PVE_OBJECTS (SOURCE_CODE, OBJ_TYPE, HEALTH);
/

CREATE OR REPLACE VIEW V_TBC_PVE_STATS AS
SELECT
  (SELECT COUNT(*) FROM TBC_PVE_OBJECTS WHERE OBJ_TYPE = 'node') AS NODES_TOTAL,
  (SELECT COUNT(*) FROM TBC_PVE_OBJECTS WHERE OBJ_TYPE = 'qemu') AS VM_TOTAL,
  (SELECT COUNT(*) FROM TBC_PVE_OBJECTS WHERE OBJ_TYPE = 'qemu' AND STATUS = 'running') AS VM_RUNNING,
  (SELECT COUNT(*) FROM TBC_PVE_OBJECTS WHERE OBJ_TYPE = 'lxc') AS CT_TOTAL,
  (SELECT COUNT(*) FROM TBC_PVE_OBJECTS WHERE OBJ_TYPE = 'lxc' AND STATUS = 'running') AS CT_RUNNING,
  (SELECT COUNT(*) FROM TBC_PVE_OBJECTS WHERE OBJ_TYPE = 'storage') AS STORAGE_TOTAL,
  (SELECT COUNT(*) FROM TBC_PVE_OBJECTS WHERE HEALTH = 'CRIT') AS CRIT_TOTAL,
  (SELECT COUNT(*) FROM TBC_PVE_OBJECTS WHERE HEALTH = 'WARN') AS WARN_TOTAL,
  (SELECT MAX(CHECKED_AT) FROM TBC_PVE_OBJECTS) AS CHECKED_AT
FROM DUAL;
/

-- Источник: шлюз отдаёт /proxmox/ как https://192.168.0.149:8006/api2/json/
INSERT INTO TBC_SOURCES (CODE, NAME, KIND, API_URL, API_USER, ENABLED, SORT_ORDER, NOTE,
                         CERT_PATH, CA_PATH, KEY_KEYCHAIN_SVC, KEY_KEYCHAIN_ACC)
VALUES ('pve-proxmox3', 'Proxmox VE PROXMOX3 (mTLS)', 'proxmox',
        'https://192.168.0.148:8443/proxmox', 'root@pam', 'Y', 26,
        'Гипервизор: ноды, VM, LXC, хранилища. Доступ только по сертификату оператора',
        '/Users/pt/Keys/tbc-zabbix-mtls/client.crt', '/Users/pt/Keys/tbc-zabbix-mtls/ca.crt',
        'tbc-zabbix-client-key', 'tbc-zabbix-mtls');
COMMIT;
