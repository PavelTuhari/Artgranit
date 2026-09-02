-- RO: jurnalul COMPLET al apelurilor catre SIA e-Factura (02.09.2026).
--     EFA_LOG tine doar un rezumat de 2000 de caractere; cind prima proba a
--     fost respinsa («Validation failed: The 'Invoices' element is not
--     declared…») textul intreg al erorii nu incapea si operatorul nu a
--     inteles ce s-a intimplat. Aici se pastreaza, pentru fiecare apel:
--     plicul trimis (parola mascata), raspunsul brut, statutul HTTP, durata
--     si un verdict scurt. Pagina probei le arata jos, ca un jurnal.
-- EN: full request/response journal of every SFS call, shown on the test page.
CREATE TABLE EFA_CALL (
    ID          NUMBER         NOT NULL,
    TS          DATE           DEFAULT SYSDATE NOT NULL,
    SRC         VARCHAR2(20),                 -- test-page | api | backoffice | cabinet
    USERNAME    VARCHAR2(120),                -- contul API folosit (fara parola)
    ENDPOINT    VARCHAR2(400),
    METHOD      VARCHAR2(60),                 -- Test, PostInvoices, GetInvoicesForSigning…
    HTTP_STATUS NUMBER,
    DURATION_MS NUMBER,
    RESULT      VARCHAR2(20),                 -- ok | rejected | fault | html | network
    SUMMARY     VARCHAR2(4000),               -- o fraza: ce a raspuns SFS
    REQUEST_XML CLOB,                         -- plicul SOAP, parola = ******
    RESPONSE_XML CLOB,                        -- raspunsul brut (SOAP sau HTML)
    CONSTRAINT PK_EFA_CALL PRIMARY KEY (ID)
)
/

CREATE INDEX IX_EFA_CALL_TS ON EFA_CALL (TS)
/

CREATE SEQUENCE EFA_CALL_SEQ START WITH 1 INCREMENT BY 1
/

CREATE OR REPLACE TRIGGER EFA_CALL_BI
BEFORE INSERT ON EFA_CALL FOR EACH ROW
WHEN (NEW.ID IS NULL)
BEGIN
  SELECT EFA_CALL_SEQ.NEXTVAL INTO :NEW.ID FROM dual;
END;
/
