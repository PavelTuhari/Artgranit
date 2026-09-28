-- =====================================================================
-- TMS_MUNC_ADDFILES — documentele PERSONALE ale clientului (1:N la
-- TMS_UNIVERS, unde ajung TOTI clientii: persoane fizice si juridice).
--
-- RO: clientul incarca in cabinet copiile actelor (buletin fata/verso,
--     alte documente cerute de creditor). Fisierele pleaca apoi catre
--     creditor (Microinvest nu are API — cererea o depune operatorul).
-- EN: client's personal documents (ID card scans etc.), 1:N to TMS_UNIVERS.
--
-- GDPR (Legea 133/2011): date cu caracter personal — pastrare limitata,
-- acces doar pentru client (ale sale) si operatorul back-office, stergere
-- la cerere (DELETE fizic), fiecare acces se scrie in jurnal.
-- =====================================================================

CREATE TABLE TMS_MUNC_ADDFILES (
  ID           NUMBER            NOT NULL,
  UNIVERS_COD  NUMBER            NOT NULL,   -- master: TMS_UNIVERS.COD
  DOC_KIND     VARCHAR2(30)      NOT NULL,   -- buletin_fata|buletin_verso|extras_venit|other
  FILE_NAME    VARCHAR2(260)     NOT NULL,
  MIME_TYPE    VARCHAR2(100),
  FILE_SIZE    NUMBER,
  SHA256       VARCHAR2(64),                 -- control integritate / anti-duplicat
  CONTENT      BLOB,
  UPLOADED_BY  VARCHAR2(100),                -- 'client' sau utilizatorul back-office
  NOTE         VARCHAR2(400),
  CREATED_AT   DATE DEFAULT SYSDATE,
  CONSTRAINT TMS_MUNC_ADDFILES_PK PRIMARY KEY (ID),
  CONSTRAINT TMS_MUNC_ADDFILES_FK FOREIGN KEY (UNIVERS_COD)
    REFERENCES TMS_UNIVERS (COD)
);

CREATE INDEX TMS_MUNC_ADDFILES_IX1 ON TMS_MUNC_ADDFILES (UNIVERS_COD, DOC_KIND);
CREATE SEQUENCE TMS_MUNC_ADDFILES_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- jurnal de acces: cine si cind a incarcat / vazut / sters un document
CREATE TABLE TMS_MUNC_ADDFILES_LOG (
  ID        NUMBER        NOT NULL,
  FILE_ID   NUMBER,
  ACTION    VARCHAR2(20)  NOT NULL,          -- upload|view|download|delete|send
  WHO       VARCHAR2(100),
  IP_ADDR   VARCHAR2(45),
  NOTE      VARCHAR2(400),
  CREATED_AT DATE DEFAULT SYSDATE,
  CONSTRAINT TMS_MUNC_ADDFILES_LOG_PK PRIMARY KEY (ID)
);

CREATE INDEX TMS_MUNC_ADDFILES_LOG_IX1 ON TMS_MUNC_ADDFILES_LOG (FILE_ID, CREATED_AT);
CREATE SEQUENCE TMS_MUNC_ADDFILES_LOG_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
