-- =====================================================================
-- Biro26: arhivarea saptaminala a SITE-ului (surse + metadate, FARA
-- marfa din ERP si FARA imaginile produselor).
-- RO: destinatii FTP/SFTP pentru copierea automata a arhivelor pe
--     stocari externe + jurnalul rularilor. Prefix YBIRO_. ASCII only.
-- =====================================================================

CREATE TABLE YBIRO_BACKUP_DEST (
  ID         NUMBER NOT NULL,
  NAME       VARCHAR2(100) NOT NULL,       -- eticheta (ex. "NAS birou")
  PROTO      VARCHAR2(10) DEFAULT 'sftp',  -- 'ftp' | 'sftp'
  HOST       VARCHAR2(200) NOT NULL,
  PORT       NUMBER,                       -- NULL = implicit (21/22)
  USERNAME   VARCHAR2(100),
  PASSWD     VARCHAR2(200),
  REMOTE_DIR VARCHAR2(400) DEFAULT '/',
  ENABLED    VARCHAR2(1) DEFAULT '1',
  CONSTRAINT PK_YBIRO_BACKUP_DEST PRIMARY KEY (ID)
);
CREATE SEQUENCE YBIRO_BACKUP_DEST_SEQ START WITH 1 NOCACHE;

CREATE TABLE YBIRO_BACKUP_LOG (
  ID        NUMBER NOT NULL,
  TS        DATE DEFAULT SYSDATE,
  FILE_NAME VARCHAR2(200),
  SIZE_MB   NUMBER,
  STATUS    VARCHAR2(20),                  -- OK | ERROR | UPLOAD_OK | UPLOAD_ERR
  NOTE      VARCHAR2(2000),
  CONSTRAINT PK_YBIRO_BACKUP_LOG PRIMARY KEY (ID)
);
CREATE SEQUENCE YBIRO_BACKUP_LOG_SEQ START WITH 1 NOCACHE;
