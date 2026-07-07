-- =====================================================================
-- Biro26 web-shop: self-registered clients + "cont de plata" documents.
-- RO: Clienti auto-inregistrati (pagina publica Marfa/Stoc) si generarea
--     documentelor "cont de plata" vizibile in VMDB_DOCS_WORK /
--     VMDB_ST201M / VMDB_ST201D (ecranul nativ ST201, SYSFID 12280).
-- EN: Self-registered clients (public Marfa/Stoc page) and generation of
--     "invoice for payment" documents visible through VMDB_DOCS_WORK /
--     VMDB_ST201M / VMDB_ST201D (native ST201 screen, SYSFID 12280).
-- RO/EN comments only (project rule). Target: officeplus (Oracle 11g).
-- Reference document: COD=140 (DT=2214, CT=2171, CTDEP=1, VALUTA=LEI).
-- Run: ./venv/bin/python deploy_biro26_shop.py
-- =====================================================================

CREATE TABLE YBIRO_CLIENT (
  id           NUMBER PRIMARY KEY,          -- via secventa+trigger (11g)
  univers_cod  NUMBER NOT NULL,             -- RO: clientul in TMS_UNIVERS (TIP='O') / EN: client org in TMS_UNIVERS
  email        VARCHAR2(120) NOT NULL,      -- RO: login / EN: login
  full_name    VARCHAR2(160) NOT NULL,
  phone        VARCHAR2(40),
  pwd_hash     VARCHAR2(200) NOT NULL,      -- RO: pbkdf2 din aplicatie / EN: pbkdf2 from the app
  created_at   TIMESTAMP DEFAULT SYSTIMESTAMP,
  CONSTRAINT uq_ybiro_client_email UNIQUE (email)
);

CREATE SEQUENCE YBIRO_CLIENT_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE OR REPLACE TRIGGER YBIRO_CLIENT_BI
  BEFORE INSERT ON YBIRO_CLIENT FOR EACH ROW WHEN (NEW.id IS NULL)
BEGIN
  SELECT YBIRO_CLIENT_SEQ.NEXTVAL INTO :NEW.id FROM dual;
END;
/

-- =====================================================================
-- Package y_ai_BIRO26
-- =====================================================================
CREATE OR REPLACE PACKAGE y_ai_BIRO26 AS
  -- RO: Parametri configurabili (valorile implicite copiate din documentul
  --     de referinta COD=140). / EN: Configurable parameters (defaults
  --     copied from the reference document COD=140).
  g_sysfid   NUMBER       := 12280;  -- RO: formularul "cont de plata" / EN: invoice form id
  g_tip      VARCHAR2(1)  := 'H';
  g_dt       NUMBER       := 2214;   -- RO: cont debit (client) / EN: debit account (client)
  g_ct       NUMBER       := 2171;   -- RO: cont credit (vanzari) / EN: credit account (sales)
  g_ctdep    NUMBER       := 1;      -- RO: subdiviziune credit (Magazin 1) / EN: credit dep
  g_valuta   VARCHAR2(6)  := 'LEI';
  -- RO: AT2=2 => trigger-ul TRIG_BFALL_TMDB_DOCS nu verifica perioada de
  --     lucru si documentul ramane mereu vizibil in VMDB_DOCS_WORK.
  -- EN: AT2=2 => TRIG_BFALL_TMDB_DOCS skips the working-period check and
  --     the document stays permanently visible in VMDB_DOCS_WORK.
  g_at2      NUMBER       := 2;
  g_doccolor VARCHAR2(1)  := '`';
  g_client_tip VARCHAR2(1):= 'O';    -- RO: client = organizatie / EN: client = organisation
  g_client_gr1 VARCHAR2(5):= 'E';    -- RO: grupa clientilor / EN: clients group
  g_caccess  VARCHAR2(5)  := '11100';

  -- RO: Inregistreaza un client nou in TMS_UNIVERS (TIP='O'); intoarce COD.
  -- EN: Register a new client in TMS_UNIVERS (TIP='O'); returns COD.
  FUNCTION register_client(p_name IN VARCHAR2) RETURN NUMBER;

  -- RO: Creeaza antetul documentului "cont de plata" (TMDB_DOCS +
  --     VMDB_ST201M + XNRDOC pentru vizibilitate imediata); intoarce COD.
  -- EN: Create the invoice header (TMDB_DOCS + VMDB_ST201M + XNRDOC for
  --     immediate visibility); returns the document COD.
  FUNCTION create_invoice(p_client_cod IN NUMBER,
                          p_data       IN DATE DEFAULT TRUNC(SYSDATE))
    RETURN NUMBER;

  -- RO: Adauga o linie in document (prin VMDB_ST201D, deci prin logica
  --     nativa INSTEAD OF). / EN: Add a document line (through VMDB_ST201D,
  --     hence through the native INSTEAD OF logic).
  PROCEDURE add_line(p_nrdoc  IN NUMBER,
                     p_sc     IN NUMBER,
                     p_cant   IN NUMBER,
                     p_pret   IN NUMBER,
                     p_coment IN VARCHAR2 DEFAULT NULL);

  -- RO: Numarul de ordine (NRSET) al documentului. / EN: document NRSET.
  FUNCTION get_nrset(p_nrdoc IN NUMBER) RETURN NUMBER;

  -- RO: COD-ul ultimului document creat in ACEASTA sesiune (stare pachet).
  -- EN: COD of the last document created in THIS session (package state).
  FUNCTION last_doc RETURN NUMBER;
END y_ai_BIRO26;
/

CREATE OR REPLACE PACKAGE BODY y_ai_BIRO26 AS

  g_last_cod NUMBER;  -- RO: ultimul COD creat / EN: last created COD

  FUNCTION register_client(p_name IN VARCHAR2) RETURN NUMBER IS
    v_cod NUMBER;
  BEGIN
    SELECT ID_TMS_UNIVERS.NEXTVAL INTO v_cod FROM dual;
    INSERT INTO TMS_UNIVERS (COD, DENUMIREA, TIP, GR1, CACCESS)
    VALUES (v_cod, SUBSTR(p_name, 1, 160), g_client_tip, g_client_gr1, g_caccess);
    RETURN v_cod;
  END register_client;

  FUNCTION create_invoice(p_client_cod IN NUMBER,
                          p_data       IN DATE DEFAULT TRUNC(SYSDATE))
    RETURN NUMBER IS
    v_cod   NUMBER;
    v_nrset NUMBER;
  BEGIN
    SELECT ID_TMDB_DOCS.NEXTVAL INTO v_cod FROM dual;
    -- RO: numerotare per formular (suficient la volumul curent)
    -- EN: per-form numbering (adequate at current volume)
    SELECT NVL(MAX(NRSET), 0) + 1 INTO v_nrset
      FROM TMDB_DOCS WHERE SYSFID = g_sysfid;

    INSERT INTO TMDB_DOCS (COD, TIP, SYSFID, USERID, DATAMANUAL, VALUTA,
                           NRSET, ISGFC, DOCCOLOR, CODF, AT2, AT3)
    VALUES (v_cod, g_tip, g_sysfid, UID, p_data, g_valuta,
            v_nrset, 0, g_doccolor, 0, g_at2, 0);

    -- RO: antetul contabil, prin vederea nativa / EN: posting header via the native view
    INSERT INTO VMDB_ST201M (NRDOC, DT, CT, DTDEP, CTDEP,
                             VALUTADT, VALUTACT, CTDATA)
    VALUES (v_cod, g_dt, g_ct, p_client_cod, g_ctdep,
            g_valuta, g_valuta, p_data);

    -- RO: vizibil imediat in VMDB_DOCS_WORK / EN: immediately visible in VMDB_DOCS_WORK
    INSERT INTO XNRDOC (COD)
    SELECT v_cod FROM dual
     WHERE NOT EXISTS (SELECT 1 FROM XNRDOC WHERE COD = v_cod);

    g_last_cod := v_cod;
    RETURN v_cod;
  END create_invoice;

  PROCEDURE add_line(p_nrdoc  IN NUMBER,
                     p_sc     IN NUMBER,
                     p_cant   IN NUMBER,
                     p_pret   IN NUMBER,
                     p_coment IN VARCHAR2 DEFAULT NULL) IS
  BEGIN
    INSERT INTO VMDB_ST201D (NRDOC, DT, CT, CTSC, CANT, SUMA, TXTCOMENT)
    VALUES (p_nrdoc, g_dt, g_ct, p_sc, p_cant,
            ROUND(NVL(p_cant, 0) * NVL(p_pret, 0), 2),
            SUBSTR(p_coment, 1, 200));
  END add_line;

  FUNCTION get_nrset(p_nrdoc IN NUMBER) RETURN NUMBER IS
    v NUMBER;
  BEGIN
    SELECT NRSET INTO v FROM TMDB_DOCS WHERE COD = p_nrdoc;
    RETURN v;
  END get_nrset;

  FUNCTION last_doc RETURN NUMBER IS
  BEGIN
    RETURN g_last_cod;
  END last_doc;

END y_ai_BIRO26;
/
