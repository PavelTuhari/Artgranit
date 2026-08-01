-- =====================================================================
-- RO: Pachetul care creeaza DOCUMENTUL de credit — acelasi principiu ca
--     y_ai_BIRO26.create_invoice, dar separat, cum a cerut proprietarul.
--     Documentul se inregistreaza in TMDB_DOCS (NRSET = 201) si tine in
--     DOC_COD_ORDER legatura cu comanda/contul deja existent.
-- EN: package creating the credit document; registers it in TMDB_DOCS
--     (NRSET = 201) and links it to the existing order document.
-- =====================================================================

CREATE OR REPLACE PACKAGE y_ai_BIRO26_credite AS
  -- RO: creeaza documentul de credit si intoarce COD-ul lui
  FUNCTION create_credit(
      p_doc_cod_order NUMBER,
      p_client_cod    NUMBER,
      p_nnp           VARCHAR2,
      p_idnp          VARCHAR2,
      p_phone         VARCHAR2,
      p_adresa        VARCHAR2,
      p_birth_date    DATE,
      p_org_id        NUMBER,
      p_org_name      VARCHAR2,
      p_plan_id       NUMBER,
      p_plan_name     VARCHAR2,
      p_months        NUMBER,
      p_avans         NUMBER,
      p_amount        NUMBER,
      p_credit_price  NUMBER,
      p_monthly       NUMBER,
      p_provider_code VARCHAR2,
      p_ext_ref       VARCHAR2,
      p_api_status    VARCHAR2,
      p_req_id        NUMBER) RETURN NUMBER;

  PROCEDURE add_line(
      p_cod         NUMBER,
      p_sc          NUMBER,
      p_denumirea   VARCHAR2,
      p_um          VARCHAR2,
      p_cant        NUMBER,
      p_pret        NUMBER,
      p_pret_credit NUMBER);

  PROCEDURE set_status(p_cod NUMBER, p_ext_ref VARCHAR2, p_api_status VARCHAR2);

  FUNCTION last_doc RETURN NUMBER;
END y_ai_BIRO26_credite;
/

CREATE OR REPLACE PACKAGE BODY y_ai_BIRO26_credite AS

  g_last_doc NUMBER;

  FUNCTION create_credit(
      p_doc_cod_order NUMBER, p_client_cod NUMBER, p_nnp VARCHAR2,
      p_idnp VARCHAR2, p_phone VARCHAR2, p_adresa VARCHAR2, p_birth_date DATE,
      p_org_id NUMBER, p_org_name VARCHAR2, p_plan_id NUMBER,
      p_plan_name VARCHAR2, p_months NUMBER, p_avans NUMBER, p_amount NUMBER,
      p_credit_price NUMBER, p_monthly NUMBER, p_provider_code VARCHAR2,
      p_ext_ref VARCHAR2, p_api_status VARCHAR2, p_req_id NUMBER) RETURN NUMBER
  IS
    v_cod NUMBER;
    v_nr  NUMBER;
  BEGIN
    -- RO: COD-ul documentului — urmatorul liber in TMDB_DOCS
    SELECT NVL(MAX(COD), 0) + 1 INTO v_cod FROM TMDB_DOCS;
    -- RO: numarul documentului de credit, propriu seriei CR
    SELECT NVL(MAX(TO_NUMBER(REGEXP_SUBSTR(NRMANUAL, '\d+'))), 0) + 1
      INTO v_nr FROM TMDB_DOCS
     WHERE NRSET = 201 AND NRMANUAL LIKE 'CR-%'
       AND REGEXP_LIKE(NRMANUAL, '^CR-\d+$');

    INSERT INTO TMDB_DOCS (COD, TIP, TIPDOC, DATAMANUAL, NRMANUAL, NRSET, STATUS)
    VALUES (v_cod, 'D', 0, SYSDATE, 'CR-' || v_nr, 201, 0);

    INSERT INTO TMDB_CREDITE_M (
      COD, DOC_COD_ORDER, CLIENT_COD, NNP, IDNP, PHONE, ADRESA, BIRTH_DATE,
      ORG_ID, ORG_NAME, PLAN_ID, PLAN_NAME, MONTHS, AVANS, AMOUNT,
      CREDIT_PRICE, MONTHLY, PROVIDER_CODE, EXT_REF, API_STATUS, REQ_ID)
    VALUES (
      v_cod, p_doc_cod_order, p_client_cod, p_nnp, p_idnp, p_phone, p_adresa,
      p_birth_date, p_org_id, p_org_name, p_plan_id, p_plan_name, p_months,
      p_avans, p_amount, p_credit_price, p_monthly, p_provider_code,
      p_ext_ref, p_api_status, p_req_id);

    g_last_doc := v_cod;
    RETURN v_cod;
  END create_credit;

  PROCEDURE add_line(
      p_cod NUMBER, p_sc NUMBER, p_denumirea VARCHAR2, p_um VARCHAR2,
      p_cant NUMBER, p_pret NUMBER, p_pret_credit NUMBER)
  IS
    v_n NUMBER;
  BEGIN
    SELECT NVL(MAX(COD1), 0) + 1 INTO v_n FROM TMDB_CREDITE_D WHERE COD = p_cod;
    INSERT INTO TMDB_CREDITE_D (COD, COD1, SC, DENUMIREA, UM, CANT, PRET,
                                PRET_CREDIT, SUMA)
    VALUES (p_cod, v_n, p_sc, p_denumirea, p_um, p_cant, p_pret, p_pret_credit,
            ROUND(NVL(p_cant, 0) * NVL(p_pret_credit, p_pret), 2));
  END add_line;

  PROCEDURE set_status(p_cod NUMBER, p_ext_ref VARCHAR2, p_api_status VARCHAR2)
  IS
  BEGIN
    UPDATE TMDB_CREDITE_M
       SET EXT_REF    = NVL(p_ext_ref, EXT_REF),
           API_STATUS = NVL(p_api_status, API_STATUS)
     WHERE COD = p_cod;
  END set_status;

  FUNCTION last_doc RETURN NUMBER IS
  BEGIN
    RETURN g_last_doc;
  END last_doc;

END y_ai_BIRO26_credite;
/
