-- ============================================================
-- INV: хэш-инвайты для автологина по ссылке
-- Ссылка вида /UNA.md/orasldev/<module>?h=<hash> автоматически
-- аутентифицирует сессию кредами, привязанными к хэшу.
-- ============================================================

CREATE SEQUENCE INV_LINKS_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE TABLE INV_LINKS (
  ID           NUMBER        NOT NULL,
  HASH         VARCHAR2(64)  NOT NULL,   -- секрет из ссылки (?h=...)
  MODULE_CODE  VARCHAR2(50)  NOT NULL,   -- tbcontrol / digi-sm / nufarul-admin / ...
  TARGET_PATH  VARCHAR2(300) NOT NULL,   -- /UNA.md/orasldev/tbcontrol
  LOGIN        VARCHAR2(100) NOT NULL,   -- креды, которыми выполняется автологин
  PASSWD       VARCHAR2(200) NOT NULL,
  STATUS       VARCHAR2(20)  DEFAULT 'active',   -- active / disabled
  EXPIRES_AT   TIMESTAMP,                -- NULL = бессрочно
  MAX_USES     NUMBER,                   -- NULL = без лимита
  USES_COUNT   NUMBER        DEFAULT 0,
  NOTE         VARCHAR2(300),
  CREATED_BY   VARCHAR2(100),
  CREATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  LAST_USED_AT TIMESTAMP,
  CONSTRAINT PK_INV_LINKS PRIMARY KEY (ID),
  CONSTRAINT UQ_INV_LINKS_HASH UNIQUE (HASH),
  CONSTRAINT CHK_INV_LINKS_ST CHECK (STATUS IN ('active','disabled'))
);
/

CREATE OR REPLACE TRIGGER INV_LINKS_BI
  BEFORE INSERT ON INV_LINKS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := INV_LINKS_SEQ.NEXTVAL;
END;
/
