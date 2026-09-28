-- NMON_PVE_*: паспорта гостей гипервизора Proxmox для решений о миграции.
-- Текстовые колонки объявлены в СИМВОЛЬНОЙ семантике (N CHAR): по умолчанию
-- Oracle считает VARCHAR2 в байтах, и кириллица «пересоздать на новой ОС»
-- (43 байта) не влезала в VARCHAR2(40) — вставка молча падала.
-- Ставится своим установщиком modules/netmon/scripts/netmon_deploy.py.
-- '/' обязателен и ПЕРЕД, и ПОСЛЕ каждого PL/SQL-блока (CLAUDE.md, §2 п.5).
--
-- Учётные данные в таблицу НЕ попадают: коннектор вычищает их из описаний
-- до записи (modules/netmon/proxmox.py, _strip_secrets).

CREATE TABLE NMON_PVE_GUESTS (
  ID            NUMBER        NOT NULL,
  NODE_NAME     VARCHAR2(64)  NOT NULL,
  VMID          NUMBER        NOT NULL,
  KIND          VARCHAR2(8)   NOT NULL,
  NAME          VARCHAR2(128 CHAR),
  STATUS        VARCHAR2(16),
  CORES         NUMBER,
  MEMORY_MB     NUMBER,
  DISK_GB       NUMBER(10,1),
  OSTYPE        VARCHAR2(32),
  ONBOOT        CHAR(1)       DEFAULT 'N' NOT NULL,
  LEGACY_OS     CHAR(1)       DEFAULT 'N' NOT NULL,
  RISK_LEVEL    VARCHAR2(10)  DEFAULT 'low' NOT NULL,
  DECISION      VARCHAR2(60 CHAR),
  LAST_BACKUP   VARCHAR2(10),
  SNAPSHOTS     NUMBER        DEFAULT 0,
  UPTIME_S      NUMBER        DEFAULT 0,
  IP_HINT       VARCHAR2(64 CHAR),
  ROLE_HINT     VARCHAR2(300 CHAR),
  OS_HINT       VARCHAR2(120 CHAR),
  RISKS         VARCHAR2(1000 CHAR),
  NOTES         VARCHAR2(1000 CHAR),
  DESCR         VARCHAR2(2000 CHAR),
  NETS          VARCHAR2(600 CHAR),
  DISKS         VARCHAR2(600 CHAR),
  SYNCED_AT     TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT PK_NMON_PVE_GUESTS PRIMARY KEY (ID),
  CONSTRAINT UK_NMON_PVE_GUEST UNIQUE (NODE_NAME, VMID),
  CONSTRAINT CK_NMON_PVE_KIND CHECK (KIND IN ('qemu','lxc')),
  CONSTRAINT CK_NMON_PVE_ONBOOT CHECK (ONBOOT IN ('Y','N')),
  CONSTRAINT CK_NMON_PVE_LEGACY CHECK (LEGACY_OS IN ('Y','N')),
  CONSTRAINT CK_NMON_PVE_RISK CHECK (RISK_LEVEL IN ('high','medium','low'))
);

CREATE INDEX IX_NMON_PVE_STATUS ON NMON_PVE_GUESTS (STATUS);
CREATE INDEX IX_NMON_PVE_DECISION ON NMON_PVE_GUESTS (DECISION);

CREATE SEQUENCE NMON_PVE_GUESTS_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/
CREATE OR REPLACE TRIGGER NMON_PVE_GUESTS_BI
BEFORE INSERT ON NMON_PVE_GUESTS FOR EACH ROW
BEGIN
  IF :NEW.ID IS NULL THEN
    SELECT NMON_PVE_GUESTS_SEQ.NEXTVAL INTO :NEW.ID FROM DUAL;
  END IF;
END;
/
