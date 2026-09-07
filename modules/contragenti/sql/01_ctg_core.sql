-- RO: Jurnalul puntii Contragenti -> una.md (07.09.2026). Fiecare pas al
--     lantului de preluare a datelor din registrul de stat se scrie aici:
--     health / search / pick_* (din browser), card_received, match_*,
--     univers_updated, org_updated, client_created, conflict, error.
--     Append-only. Text ASCII (baza OfficePlus e CL8MSWIN1251).
-- EN: CTG_EVENT_LOG - full chain log for the Contragenti bridge.

CREATE TABLE CTG_EVENT_LOG (
    ID           NUMBER          NOT NULL,
    TS           DATE            DEFAULT SYSDATE NOT NULL,
    USERNAME     VARCHAR2(120),
    PAGE         VARCHAR2(60),                 -- biro26-clients | crm | backfill | api
    STEP         VARCHAR2(40)    NOT NULL,
    Q            VARCHAR2(400),                -- filtrul cautat
    IDNO         VARCHAR2(20),
    UNIVERS_COD  NUMBER,
    RESULT       VARCHAR2(20),                 -- ok | repaired | created | unchanged | conflict | error | skip
    DETAIL       VARCHAR2(2000),
    PAYLOAD      CLOB,
    CONSTRAINT PK_CTG_EVENT_LOG PRIMARY KEY (ID)
)
/

CREATE INDEX IX_CTG_EVENT_LOG_TS ON CTG_EVENT_LOG (TS)
/

CREATE INDEX IX_CTG_EVENT_LOG_IDNO ON CTG_EVENT_LOG (IDNO)
/

CREATE SEQUENCE CTG_EVENT_LOG_SEQ START WITH 1 INCREMENT BY 1
/

CREATE OR REPLACE TRIGGER CTG_EVENT_LOG_BI
BEFORE INSERT ON CTG_EVENT_LOG FOR EACH ROW
WHEN (NEW.ID IS NULL)
BEGIN
  SELECT CTG_EVENT_LOG_SEQ.NEXTVAL INTO :NEW.ID FROM dual;
END;
/
