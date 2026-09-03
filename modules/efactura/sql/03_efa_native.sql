-- RO: pachetul pentru back-office-ul NATIV una.md — actiunea «Выгрузить в
--     e-Factura». Acelasi mecanism ca y_ai_BIRO26.gen_conturi («Contul de
--     plata»): Oracle -> UTL_HTTP -> API-ul web -> SFS; rezultatul ramine in
--     EFA_DOC si se citeste cu doc_status. HTTP simplu, nu HTTPS: Oracle 11g de
--     aici nu are wallet TLS (ORA-29024); adresa e sub /api/biro26/, singura
--     care trece de redirectul la HTTPS al intrarii officeplus.md.
--     Cheia: YBIRO_SETTINGS.API_GEN_KEY (= BIRO26_API_TOKEN din .env).
-- EN: Oracle-side entry point for the native back-office action.
--
--   SELECT EFA_NATIVE.send_doc(268) FROM dual;            -- raspunsul intreg
--   BEGIN EFA_NATIVE.send_doc_pr(268); END;               -- ORA-20000 la eroare
--   SELECT EFA_NATIVE.doc_status(268) FROM dual;          -- SENT / ERROR / … + mesaj
--   SELECT EFA_NATIVE.send_doc(268, '2026-09-02') FROM dual;  -- DOAR probe: data fortata

CREATE OR REPLACE PACKAGE EFA_NATIVE AS
  FUNCTION  send_doc(p_doc IN NUMBER, p_date IN VARCHAR2 DEFAULT NULL)
    RETURN VARCHAR2;
  PROCEDURE send_doc_pr(p_doc IN NUMBER, p_date IN VARCHAR2 DEFAULT NULL);
  FUNCTION  doc_status(p_doc IN NUMBER) RETURN VARCHAR2;
END EFA_NATIVE;
/

CREATE OR REPLACE PACKAGE BODY EFA_NATIVE AS

  c_base CONSTANT VARCHAR2(200) := 'http://officeplus.md/api/biro26/efactura';

  FUNCTION api_key RETURN VARCHAR2 IS
    v VARCHAR2(400);
  BEGIN
    SELECT sval INTO v FROM YBIRO_SETTINGS WHERE skey = 'API_GEN_KEY';
    RETURN v;
  EXCEPTION WHEN NO_DATA_FOUND THEN RETURN NULL;
  END api_key;

  -- RO: GET pe web, corpul raspunsului (JSON) ca text; erorile ca 'ERR: …'
  FUNCTION http_get(p_url IN VARCHAR2) RETURN VARCHAR2 IS
    v_req   UTL_HTTP.REQ;
    v_resp  UTL_HTTP.RESP;
    v_chunk VARCHAR2(2000);
    v_out   VARCHAR2(4000) := '';
    v_open  BOOLEAN := FALSE;
  BEGIN
    UTL_HTTP.SET_TRANSFER_TIMEOUT(180);
    v_req  := UTL_HTTP.BEGIN_REQUEST(p_url, 'GET', 'HTTP/1.1');
    UTL_HTTP.SET_HEADER(v_req, 'User-Agent', 'EFA_NATIVE');
    v_resp := UTL_HTTP.GET_RESPONSE(v_req);
    v_open := TRUE;
    -- RO: corpul vine UTF-8; fara asta Oracle il citeste ca CL8MSWIN1251 si
    --     «—», «…», ghilimelele ajung mojibake in fereastra aplicatiei.
    UTL_HTTP.SET_BODY_CHARSET(v_resp, 'UTF-8');
    BEGIN
      LOOP
        UTL_HTTP.READ_TEXT(v_resp, v_chunk, 2000);
        v_out := SUBSTR(v_out || v_chunk, 1, 3900);
      END LOOP;
    EXCEPTION WHEN UTL_HTTP.END_OF_BODY THEN NULL;
    END;
    UTL_HTTP.END_RESPONSE(v_resp);
    RETURN SUBSTR('HTTP ' || v_resp.status_code || ': ' || v_out, 1, 4000);
  EXCEPTION WHEN OTHERS THEN
    IF v_open THEN
      BEGIN UTL_HTTP.END_RESPONSE(v_resp); EXCEPTION WHEN OTHERS THEN NULL; END;
    END IF;
    RETURN 'ERR: ' || SUBSTR(SQLERRM, 1, 3900);
  END http_get;

  FUNCTION send_doc(p_doc IN NUMBER, p_date IN VARCHAR2 DEFAULT NULL)
    RETURN VARCHAR2 IS
    v_key VARCHAR2(400) := api_key;
    v_url VARCHAR2(1000);
  BEGIN
    IF v_key IS NULL THEN
      RETURN 'ERR: lipseste YBIRO_SETTINGS.API_GEN_KEY (= BIRO26_API_TOKEN din .env)';
    END IF;
    v_url := c_base || '/send/' || TO_CHAR(p_doc)
             || '?api_key=' || UTL_URL.ESCAPE(v_key, TRUE);
    IF p_date IS NOT NULL THEN
      v_url := v_url || '&override_date=' || UTL_URL.ESCAPE(p_date, TRUE);
    END IF;
    RETURN http_get(v_url);
  END send_doc;

  -- RO: pentru aplicatia nativa — arunca eroarea ca sa apara in fereastra
  PROCEDURE send_doc_pr(p_doc IN NUMBER, p_date IN VARCHAR2 DEFAULT NULL) IS
    v   VARCHAR2(4000) := send_doc(p_doc, p_date);
    msg VARCHAR2(4000);
  BEGIN
    IF v LIKE 'HTTP 200%' AND INSTR(v, '"success": true') + INSTR(v, '"success":true') > 0 THEN
      RETURN;
    END IF;
    -- RO: doar textul erorii (cimpul "error" din JSON), nu tot raspunsul;
    --     ghilimelele escapate (\") din interior fac parte din text
    msg := REGEXP_SUBSTR(v, '"error": ?"((\\"|[^"])*)"', 1, 1, NULL, 1);
    msg := REPLACE(msg, '\"', '"');
    RAISE_APPLICATION_ERROR(-20000, SUBSTR('e-Factura: ' || NVL(msg, v), 1, 2000));
  END send_doc_pr;

  -- RO: starea din EFA_DOC (fara apel la SFS): STATUS + mesaj + numarul SFS
  FUNCTION doc_status(p_doc IN NUMBER) RETURN VARCHAR2 IS
    v_st  VARCHAR2(20);
    v_msg VARCHAR2(2000);
    v_nr  VARCHAR2(120);
  BEGIN
    SELECT status, SUBSTR(err_msg, 1, 1900),
           NVL2(sfs_number, sfs_seria || ' ' || sfs_number, NULL)
      INTO v_st, v_msg, v_nr
      FROM EFA_DOC WHERE doc_cod = p_doc;
    RETURN v_st
           || CASE WHEN v_nr  IS NOT NULL THEN ' nr. SFS ' || v_nr END
           || CASE WHEN v_msg IS NOT NULL THEN ': ' || v_msg END;
  EXCEPTION WHEN NO_DATA_FOUND THEN
    RETURN 'NEW: documentul nu a fost trimis niciodata in e-Factura';
  END doc_status;

END EFA_NATIVE;
/
