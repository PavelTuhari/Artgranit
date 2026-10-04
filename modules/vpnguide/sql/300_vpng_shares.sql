-- VPNG_: Oracle-объекты модуля vpnguide (инструкция OpenVPN и ссылки для получателя).
-- Ставится ТОЛЬКО своим установщиком modules/vpnguide/scripts/vpnguide_deploy.py.
-- '/' обязателен и ПЕРЕД, и ПОСЛЕ каждого PL/SQL-блока (CLAUDE.md, §2 п.5).
--
-- Сроки — TIMESTAMP WITH TIME ZONE, а не TIMESTAMP. Ссылку создаёт машина
-- администратора (Europe/Chisinau), а открывает публичный сервер (UTC). Обычный
-- TIMESTAMP Oracle сравнивает с SYSTIMESTAMP в часовом поясе СЕССИИ, и
-- 15-минутная ссылка жила бы на часы дольше или умирала сразу.

-- Ссылка для получателя доступа. Профиль хранится ТОЛЬКО зашифрованным
-- ключом, выведенным из токена ссылки, а сам токен в базе не хранится — только
-- его SHA-256. После истечения или отзыва PAYLOAD стирается, строка остаётся
-- для истории: кому, кто и когда выдавал.
CREATE TABLE VPNG_SHARES (
  ID            NUMBER          NOT NULL,
  CLIENT_NAME   VARCHAR2(64)    NOT NULL,
  TOKEN_HASH    VARCHAR2(64)    NOT NULL,
  PAYLOAD       CLOB,
  TTL_MIN       NUMBER(5)       NOT NULL,
  LANG          VARCHAR2(2)     DEFAULT 'ru' NOT NULL,
  CREATED_AT    TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  EXPIRES_AT    TIMESTAMP WITH TIME ZONE NOT NULL,
  CREATED_BY    VARCHAR2(100),
  REVOKED_AT    TIMESTAMP WITH TIME ZONE,
  REVOKE_REASON VARCHAR2(200),
  CONSTRAINT PK_VPNG_SHARES PRIMARY KEY (ID),
  CONSTRAINT UK_VPNG_SHARES_TOKEN UNIQUE (TOKEN_HASH),
  CONSTRAINT CK_VPNG_SHARES_TTL CHECK (TTL_MIN BETWEEN 1 AND 1440),
  CONSTRAINT CK_VPNG_SHARES_LANG CHECK (LANG IN ('ru','ro','en'))
);

CREATE INDEX IX_VPNG_SHARES_CLIENT ON VPNG_SHARES (CLIENT_NAME);
CREATE INDEX IX_VPNG_SHARES_EXPIRES ON VPNG_SHARES (EXPIRES_AT);

-- Журнал открытий ссылки, только добавление: видно, открыл ли получатель
-- инструкцию и скачал ли файл, и не открывал ли её кто-то ещё.
CREATE TABLE VPNG_SHARE_HITS (
  ID          NUMBER          NOT NULL,
  SHARE_ID    NUMBER          NOT NULL,
  HIT_AT      TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  KIND        VARCHAR2(10)    NOT NULL,
  CLIENT_IP   VARCHAR2(45),
  USER_AGENT  VARCHAR2(300),
  CONSTRAINT PK_VPNG_SHARE_HITS PRIMARY KEY (ID),
  CONSTRAINT FK_VPNG_HITS_SHARE FOREIGN KEY (SHARE_ID) REFERENCES VPNG_SHARES (ID),
  CONSTRAINT CK_VPNG_HITS_KIND CHECK (KIND IN ('page','profile','markdown'))
);

CREATE INDEX IX_VPNG_HITS_SHARE ON VPNG_SHARE_HITS (SHARE_ID);

CREATE SEQUENCE VPNG_SHARES_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE VPNG_SHARE_HITS_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/
CREATE OR REPLACE TRIGGER VPNG_SHARES_BI
BEFORE INSERT ON VPNG_SHARES FOR EACH ROW
BEGIN
  IF :NEW.ID IS NULL THEN
    SELECT VPNG_SHARES_SEQ.NEXTVAL INTO :NEW.ID FROM DUAL;
  END IF;
END;
/
CREATE OR REPLACE TRIGGER VPNG_SHARE_HITS_BI
BEFORE INSERT ON VPNG_SHARE_HITS FOR EACH ROW
BEGIN
  IF :NEW.ID IS NULL THEN
    SELECT VPNG_SHARE_HITS_SEQ.NEXTVAL INTO :NEW.ID FROM DUAL;
  END IF;
END;
/
