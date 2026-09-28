-- RO: conturul Oracle al modulului e-Factura (prefix EFA_), Oracle 11g.
--     Trei tabele normalizate: setarile integrarii, starea fiecarui document
--     trimis si jurnalul append-only al apelurilor catre SFS.
-- EN: e-Factura schema (EFA_ prefix): settings, per-document state,
--     append-only call log.

-- RO: setarile se tin AICI, nu in tabela comuna de setari a magazinului:
--     modulul isi poarta propriul contur (regula nr. 1). Parola si
--     certificatul stau in aceleasi rinduri, dar se citesc doar din server.
CREATE TABLE EFA_SETTING (
    SKEY        VARCHAR2(60)   NOT NULL,
    SVALUE      VARCHAR2(2000),
    UPDATED     DATE           DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_EFA_SETTING PRIMARY KEY (SKEY)
)
/

-- RO: o linie per document trimis (sau incercat). DOC_COD = TMDB_DOCS.COD,
--     adica exact documentul din care se tipareste si contul de plata.
CREATE TABLE EFA_DOC (
    ID          NUMBER         NOT NULL,
    DOC_COD     NUMBER         NOT NULL,
    NRMANUAL    VARCHAR2(40),
    CLIENT_COD  NUMBER,
    CLIENT_IDNO VARCHAR2(20),
    TOTAL       NUMBER(14,2),
    STATUS      VARCHAR2(20)   DEFAULT 'NEW' NOT NULL,
    -- NEW | SENT | ACCEPTED | REJECTED | CANCELED | ERROR
    SFS_SERIA   VARCHAR2(20),
    SFS_NUMBER  VARCHAR2(40),
    SFS_UUID    VARCHAR2(80),
    REQUEST_ID  VARCHAR2(80),
    ERR_MSG     VARCHAR2(1000),
    SENT_AT     DATE,
    UPDATED     DATE           DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_EFA_DOC PRIMARY KEY (ID),
    CONSTRAINT UQ_EFA_DOC_DOC UNIQUE (DOC_COD)
)
/

CREATE INDEX IX_EFA_DOC_STATUS ON EFA_DOC (STATUS, UPDATED)
/

CREATE SEQUENCE EFA_DOC_SEQ START WITH 1 INCREMENT BY 1
/

CREATE OR REPLACE TRIGGER EFA_DOC_BI
BEFORE INSERT ON EFA_DOC FOR EACH ROW
WHEN (NEW.ID IS NULL)
BEGIN
  SELECT EFA_DOC_SEQ.NEXTVAL INTO :NEW.ID FROM dual;
END;
/

-- RO: jurnalul apelurilor — pentru audit fiscal si pentru cautarea cauzei
--     cind SFS respinge o factura. Append-only, nu se sterge din aplicatie.
CREATE TABLE EFA_LOG (
    ID        NUMBER        NOT NULL,
    TS        DATE          DEFAULT SYSDATE NOT NULL,
    DOC_COD   NUMBER,
    EVENT     VARCHAR2(40)  NOT NULL,
    DETAIL    VARCHAR2(2000),
    SRC       VARCHAR2(20),          -- backoffice | cabinet | api
    CONSTRAINT PK_EFA_LOG PRIMARY KEY (ID)
)
/

CREATE INDEX IX_EFA_LOG_TS ON EFA_LOG (TS)
/

CREATE SEQUENCE EFA_LOG_SEQ START WITH 1 INCREMENT BY 1
/

CREATE OR REPLACE TRIGGER EFA_LOG_BI
BEFORE INSERT ON EFA_LOG FOR EACH ROW
WHEN (NEW.ID IS NULL)
BEGIN
  SELECT EFA_LOG_SEQ.NEXTVAL INTO :NEW.ID FROM dual;
END;
/
