-- RO: Conturul CRM_* partea a treia (08.09.2026) - notificarile Telegram despre
--     tranzactiile nefinisate si datorii (cerinta proprietarului: "de adaugat
--     notificari pe telegram cu tranzactiile nefinisate si cu datorii").
--       CRM_ALERT_CFG   setarile pe chirias (bot, chat, praguri, ora sumarului)
--       CRM_ALERT_SENT  ce s-a trimis deja - ca sa nu se repete zilnic acelasi lucru
--     Ambele poarta OWNER_KIND/OWNER_ID: OfficePlus are botul lui, fiecare client
--     din cabinet - pe al lui.
--     Cheia unei alerte: KIND:REF_ID (ex. debt:1042). Se retrimite doar daca a
--     trecut perioada de liniste sau daca suma s-a schimbat - de aceea pastram
--     AMOUNT linga data trimiterii.
--     Text ASCII: baza OfficePlus e CL8MSWIN1251.
-- EN: Telegram alerts for unfinished transactions and debts, per tenant.

CREATE TABLE CRM_ALERT_CFG (
    OWNER_KIND      VARCHAR2(10)   DEFAULT 'office' NOT NULL,
    OWNER_ID        NUMBER         DEFAULT 0 NOT NULL,
    ENABLED         NUMBER(1)      DEFAULT 0 NOT NULL,
    TG_TOKEN        VARCHAR2(200),
    TG_CHAT         VARCHAR2(60),
    LANG            VARCHAR2(2)    DEFAULT 'ro' NOT NULL,
    KINDS           VARCHAR2(400),               -- lista tipurilor active, separate prin virgula, gol = toate
    DAYS_BEFORE_DUE NUMBER         DEFAULT 3 NOT NULL,   -- avertizare cu N zile inainte de termen
    MIN_DEBT        NUMBER(14,2)   DEFAULT 0 NOT NULL,   -- sub acest prag datoria nu se raporteaza
    QUIET_DAYS      NUMBER         DEFAULT 1 NOT NULL,   -- aceeasi alerta nu se repeta mai des
    SEND_HOUR       NUMBER         DEFAULT 8 NOT NULL,   -- ora sumarului zilnic (Europe/Chisinau)
    LAST_RUN        DATE,
    UPDATED         DATE           DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_CRM_ALERT_CFG PRIMARY KEY (OWNER_KIND, OWNER_ID)
)
/

CREATE TABLE CRM_ALERT_SENT (
    ID          NUMBER         NOT NULL,
    OWNER_KIND  VARCHAR2(10)   DEFAULT 'office' NOT NULL,
    OWNER_ID    NUMBER         DEFAULT 0 NOT NULL,
    ALERT_KEY   VARCHAR2(80)   NOT NULL,        -- KIND:REF_ID
    KIND        VARCHAR2(30)   NOT NULL,
    REF_TABLE   VARCHAR2(30),
    REF_ID      NUMBER,
    AMOUNT      NUMBER(14,2),
    SENT_AT     DATE           DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_CRM_ALERT_SENT PRIMARY KEY (ID),
    CONSTRAINT UQ_CRM_ALERT_SENT UNIQUE (OWNER_KIND, OWNER_ID, ALERT_KEY)
)
/

CREATE INDEX IX_CRM_ALERT_SENT_TS ON CRM_ALERT_SENT (SENT_AT)
/

CREATE SEQUENCE CRM_ALERT_SENT_SEQ START WITH 1 INCREMENT BY 1
/

CREATE OR REPLACE TRIGGER CRM_ALERT_SENT_BI
BEFORE INSERT ON CRM_ALERT_SENT FOR EACH ROW
WHEN (NEW.ID IS NULL)
BEGIN
  SELECT CRM_ALERT_SENT_SEQ.NEXTVAL INTO :NEW.ID FROM dual;
END;
/
