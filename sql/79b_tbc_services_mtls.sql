-- ============================================================
-- TBControl: сервисы Zabbix через mTLS-шлюз (TBC_SERVICES)
-- + mTLS-колонки источника (TBC_SOURCES). Восстановлено 02.09.2026
-- по фактической схеме ADB (USER_TAB_COLUMNS) — объекты в ADB уже есть,
-- файл нужен для новой БД и как документация. Код: models/tbc_services.py
-- ============================================================

-- Источник хранит только пути к публичным файлам и адрес ключа в Keychain
ALTER TABLE TBC_SOURCES ADD (
  CERT_PATH         VARCHAR2(300),   -- клиентский сертификат (PEM)
  CA_PATH           VARCHAR2(300),   -- CA шлюза для проверки сервера
  CERT_FINGERPRINT  VARCHAR2(120),   -- SHA-256 клиентского сертификата
  KEY_KEYCHAIN_SVC  VARCHAR2(120),   -- security find-generic-password -s
  KEY_KEYCHAIN_ACC  VARCHAR2(120)    --                                  -a
);
/

ALTER TABLE TBC_SOURCES DROP CONSTRAINT CHK_TBC_SRC_KIND;
/
ALTER TABLE TBC_SOURCES ADD CONSTRAINT CHK_TBC_SRC_KIND
  CHECK (KIND IN ('unisim_cassa','zabbix','emulator','zabbix_svc','proxmox'));
/

CREATE SEQUENCE TBC_SERVICES_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/

-- Хост Zabbix как сервис: сервер / БД / веб / почта / сеть
CREATE TABLE TBC_SERVICES (
  ID             NUMBER         NOT NULL,
  SOURCE_CODE    VARCHAR2(30)   NOT NULL,   -- TBC_SOURCES.CODE (kind=zabbix_svc)
  ZBX_HOSTID     VARCHAR2(20)   NOT NULL,
  HOST           VARCHAR2(200)  NOT NULL,   -- техническое имя хоста
  NAME           VARCHAR2(200),             -- видимое имя
  GROUP_NAME     VARCHAR2(200),             -- группы через запятую
  SERVICE_KIND   VARCHAR2(20),              -- server | db | web | mail | network
  IP_ADDRESS     VARCHAR2(60),
  AVAILABLE      VARCHAR2(15),              -- available | unavailable | unknown
  STATUS         VARCHAR2(15)   NOT NULL,   -- OK | WARN | PROBLEM | DISABLED
  WORST_SEVERITY VARCHAR2(5),               -- P1..P4 худшей активной проблемы
  PROBLEMS_CNT   NUMBER         DEFAULT 0,
  PROBLEM_TEXT   VARCHAR2(1000),            -- описания триггеров через ' | '
  TEMPLATES      VARCHAR2(500),
  CHECKED_AT     TIMESTAMP      DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_TBC_SERVICES PRIMARY KEY (ID),
  CONSTRAINT UQ_TBC_SERVICES UNIQUE (SOURCE_CODE, ZBX_HOSTID),
  CONSTRAINT CHK_TBC_SVC_ST CHECK (STATUS IN ('OK','WARN','PROBLEM','DISABLED'))
);
/

CREATE OR REPLACE TRIGGER TBC_SERVICES_BI
  BEFORE INSERT ON TBC_SERVICES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := TBC_SERVICES_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_TBC_SERVICES_SRC ON TBC_SERVICES (SOURCE_CODE, STATUS);
/

CREATE OR REPLACE VIEW V_TBC_SERVICES_STATS AS
SELECT
  (SELECT COUNT(*) FROM TBC_SERVICES) AS SVC_TOTAL,
  (SELECT COUNT(*) FROM TBC_SERVICES WHERE STATUS = 'OK') AS SVC_OK,
  (SELECT COUNT(*) FROM TBC_SERVICES WHERE STATUS = 'WARN') AS SVC_WARN,
  (SELECT COUNT(*) FROM TBC_SERVICES WHERE STATUS = 'PROBLEM') AS SVC_PROBLEM,
  (SELECT COUNT(*) FROM TBC_SERVICES WHERE STATUS = 'DISABLED') AS SVC_DISABLED,
  (SELECT COUNT(DISTINCT GROUP_NAME) FROM TBC_SERVICES) AS GROUPS_TOTAL,
  (SELECT COUNT(*) FROM TBC_SERVICES WHERE AVAILABLE = 'unavailable') AS AGENTS_DOWN,
  (SELECT NVL(SUM(PROBLEMS_CNT), 0) FROM TBC_SERVICES) AS PROBLEMS_TOTAL,
  (SELECT MAX(CHECKED_AT) FROM TBC_SERVICES) AS CHECKED_AT
FROM DUAL;
/

CREATE OR REPLACE VIEW V_TBC_SERVICES_BY_KIND AS
SELECT SERVICE_KIND,
       COUNT(*) AS TOTAL,
       SUM(CASE WHEN STATUS = 'OK' THEN 1 ELSE 0 END) AS OK_CNT,
       SUM(CASE WHEN STATUS = 'PROBLEM' THEN 1 ELSE 0 END) AS PROBLEM_CNT,
       SUM(CASE WHEN STATUS = 'WARN' THEN 1 ELSE 0 END) AS WARN_CNT
FROM TBC_SERVICES GROUP BY SERVICE_KIND;
/

-- Источник: Zabbix unisim-soft.com за mTLS-шлюзом nginx (192.168.0.148:8443).
-- Пароль вводится в админке модуля или ссылкой keychain:<svc>/<acct>.
INSERT INTO TBC_SOURCES (CODE, NAME, KIND, API_URL, API_USER, ENABLED, SORT_ORDER, NOTE,
                         CERT_PATH, CA_PATH, KEY_KEYCHAIN_SVC, KEY_KEYCHAIN_ACC)
VALUES ('zbx-svc-unisim', 'Сервисы Zabbix Unisim (mTLS)', 'zabbix_svc',
        'https://192.168.0.148:8443/api_jsonrpc.php', 'Admin', 'Y', 25,
        'Доступ строго по клиентскому сертификату этого компьютера (ключ в Keychain)',
        '/Users/pt/Keys/tbc-zabbix-mtls/client.crt', '/Users/pt/Keys/tbc-zabbix-mtls/ca.crt',
        'tbc-zabbix-client-key', 'tbc-zabbix-mtls');
COMMIT;
