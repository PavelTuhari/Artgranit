-- ============================================================================
-- YServOuts_BP — logica de business ServOuts26 (schema UNITEST, Oracle 11g)
-- YServOuts_BP — ServOuts26 business logic (UNITEST schema, Oracle 11g)
--
-- RO: import configurabil feed -> TMS_UNIVERS / TPR01M_GROUPS / TPR1D_PRDATE /
--     VTPR1D_PERPRLIST; mapare prin variabile publice g_*; jurnalizare in XLOG
--     prin tranzactie autonoma. NU se ocolesc trigger-ele ERP (stergerea din
--     TMS_UNIVERS e interzisa -> doar arhivare).
-- EN: configurable import feed -> TMS_UNIVERS / TPR01M_GROUPS / TPR1D_PRDATE /
--     VTPR1D_PERPRLIST; mapping via public g_* variables; logging into XLOG
--     via autonomous transaction. ERP triggers are NOT bypassed (deleting from
--     TMS_UNIVERS is forbidden -> archive only).
-- ============================================================================

CREATE OR REPLACE PACKAGE YServOuts_BP AS

  -- ------------------------------------------------------------------
  -- RO: identificatori configurabili (tabel sursa + coloane + secventa)
  -- EN: configurable identifiers (source table + columns + sequence)
  -- ------------------------------------------------------------------
  g_tbl_goods    VARCHAR2(61) := 'SRVO_INPUT_GOODS';
  g_col_key      VARCHAR2(30) := 'COD_UNIVERS';
  g_col_id       VARCHAR2(30) := 'ID';
  g_col_brand    VARCHAR2(30) := 'BRAND';
  g_col_articol  VARCHAR2(30) := 'ARTICOL';
  g_col_denumire VARCHAR2(30) := 'DENUMIRE';
  g_col_angro    VARCHAR2(30) := 'ANGRO';
  g_col_ionline  VARCHAR2(30) := 'IONLINE';
  g_col_retail   VARCHAR2(30) := 'RETAIL1';
  g_seq_key      VARCHAR2(30) := 'ID_TMS_UNIVERS';

  -- ------------------------------------------------------------------
  -- RO: constante configurabile de import
  --     (CODPRICE 1/2/4/6 sunt folosite de datele native -> modulul
  --     foloseste implicit 26, liber)
  -- EN: configurable import constants
  --     (CODPRICE 1/2/4/6 are used by native data -> the module defaults
  --     to the free 26)
  -- ------------------------------------------------------------------
  g_codprice       NUMBER       := 26;
  g_pricename      VARCHAR2(25) := 'ServOuts26';
  g_currency       VARCHAR2(3)  := 'LEI';
  g_um             VARCHAR2(15) := 'buc.';
  g_gr1            VARCHAR2(5)  := 'TVR';
  g_tip            VARCHAR2(1)  := 'P';
  g_caccess        VARCHAR2(5)  := '11100';
  g_codtva         VARCHAR2(1)  := 'A';
  g_date_start     DATE         := TRUNC(SYSDATE);
  g_date_end       DATE         := TO_DATE('01.01.3000','DD.MM.YYYY');
  g_group_type     VARCHAR2(25) := 'P,M';
  g_empty_brand    VARCHAR2(64) := 'FARA BRAND';
  g_len_codvechi   PLS_INTEGER  := 20;
  g_len_denumire   PLS_INTEGER  := 160;
  g_isarhiv_arc    VARCHAR2(1)  := '1';
  g_isarhiv_lock   VARCHAR2(1)  := '2';
  g_confus_max_cyr PLS_INTEGER  := 3;

  -- RO: jurnalizare in XLOG (tranzactie autonoma — supravietuieste rollback-ului)
  -- EN: XLOG logging (autonomous transaction — survives the caller's rollback)
  PROCEDURE log(p_property VARCHAR2, p_event VARCHAR2,
                p_coment VARCHAR2, p_nrrec NUMBER DEFAULT NULL);

  -- RO: parsare pret din text (formate '1.013.00', '1 013,00' etc.)
  -- EN: parse a price from text (formats like '1.013.00', '1 013,00')
  FUNCTION parse_price(p_txt VARCHAR2) RETURN NUMBER;

  -- RO: inlocuieste literele chirilice "confundabile" cu latine (С->C, А->A...)
  -- EN: replace Cyrillic look-alike letters with Latin ones (С->C, А->A...)
  FUNCTION fix_confusables(p_txt VARCHAR2) RETURN VARCHAR2;

  -- RO: numarul de caractere chirilice din text
  -- EN: number of Cyrillic characters in the text
  FUNCTION cyr_count(p_txt VARCHAR2) RETURN PLS_INTEGER;

  -- RO: citire/scriere configuratie g_* dupa nume (profil de mapare)
  -- EN: read/write g_* configuration by name (mapping profile)
  PROCEDURE set_conf(p_name VARCHAR2, p_value VARCHAR2);
  FUNCTION  get_conf(p_name VARCHAR2) RETURN VARCHAR2;

  -- RO: pasii importului (idempotenti — NOT EXISTS peste chei)
  -- EN: import steps (idempotent — NOT EXISTS on keys)
  PROCEDURE prepare_input;
  PROCEDURE validate_input;
  PROCEDURE assign_keys;
  PROCEDURE import_univers;
  PROCEDURE import_groups;
  PROCEDURE import_dates;
  PROCEDURE import_prices;
  PROCEDURE import_all;

  -- RO: rollback complet al unui pricelist (preturi -> date -> grupe cu nume)
  -- EN: full pricelist rollback (prices -> dates -> named groups)
  PROCEDURE rollback_pricelist(p_codprice NUMBER DEFAULT NULL);

  -- RO: unificarea a doua grupe (muta preturile+datele, sterge grupa sursa)
  -- EN: merge two groups (moves prices+dates, drops the source group)
  PROCEDURE merge_groups(p_src NUMBER, p_dst NUMBER, p_codprice NUMBER DEFAULT NULL);

  -- RO: arhivare in loc de stergere (stergerea e blocata de trigger ERP)
  -- EN: archive instead of delete (deletion is blocked by an ERP trigger)
  PROCEDURE archive_univers(p_cod NUMBER, p_isarhiv VARCHAR2 DEFAULT NULL);

  -- RO: curata denumirile cu putine litere chirilice (<= g_confus_max_cyr)
  -- EN: clean names having few Cyrillic letters (<= g_confus_max_cyr)
  PROCEDURE fix_denumirea_confusables;

END YServOuts_BP;
/

CREATE OR REPLACE PACKAGE BODY YServOuts_BP AS

  -- RO: alfabet chirilic complet (pentru cyr_count)
  -- EN: full Cyrillic alphabet (for cyr_count)
  c_cyr_all CONSTANT VARCHAR2(200) :=
    'АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯЁабвгдежзийклмнопрстуфхцчшщъыьэюяё';
  -- RO: perechi confundabile chirilic -> latin
  -- EN: Cyrillic -> Latin look-alike pairs
  c_conf_cyr CONSTANT VARCHAR2(100) := 'АВЕКМНОРСТУХаеорсух';
  c_conf_lat CONSTANT VARCHAR2(100) := 'ABEKMHOPCTYXaeopcyx';

  -- RO: valideaza un identificator SQL (protectie pentru SQL dinamic)
  -- EN: validate a SQL identifier (guard for dynamic SQL)
  FUNCTION valid_ident(p VARCHAR2) RETURN BOOLEAN IS
  BEGIN
    RETURN p IS NOT NULL AND REGEXP_LIKE(p, '^[A-Za-z][A-Za-z0-9_$#]*$');
  END valid_ident;

  PROCEDURE assert_idents IS
  BEGIN
    IF NOT (valid_ident(g_tbl_goods) AND valid_ident(g_col_key)
        AND valid_ident(g_col_brand) AND valid_ident(g_col_articol)
        AND valid_ident(g_col_denumire) AND valid_ident(g_col_angro)
        AND valid_ident(g_col_ionline) AND valid_ident(g_col_retail)
        AND valid_ident(g_seq_key)) THEN
      RAISE_APPLICATION_ERROR(-20601,
        'Identificator invalid in configuratie / invalid identifier in configuration');
    END IF;
  END assert_idents;

  PROCEDURE log(p_property VARCHAR2, p_event VARCHAR2,
                p_coment VARCHAR2, p_nrrec NUMBER DEFAULT NULL) IS
    PRAGMA AUTONOMOUS_TRANSACTION;
  BEGIN
    INSERT INTO XLOG (IOBJECT, IPROPERTY, IEVENT, ITIME, USERID, NRREC, COMENT,
                      TERMINAL, MACHINE, OS_USER, IP_ADDR, MODULE)
    VALUES ('SERVOUTS', SUBSTR(p_property,1,50), SUBSTR(p_event,1,10), SYSDATE,
            UID, p_nrrec, SUBSTR(p_coment,1,4000),
            SUBSTR(SYS_CONTEXT('USERENV','TERMINAL'),1,16),
            SUBSTR(SYS_CONTEXT('USERENV','HOST'),1,64),
            SUBSTR(SYS_CONTEXT('USERENV','OS_USER'),1,30),
            SUBSTR(SYS_CONTEXT('USERENV','IP_ADDRESS'),1,15),
            'YSERVOUTS_BP');
    COMMIT;
  EXCEPTION WHEN OTHERS THEN ROLLBACK;
  END log;

  FUNCTION parse_price(p_txt VARCHAR2) RETURN NUMBER IS
    v VARCHAR2(64);
    n PLS_INTEGER;
  BEGIN
    v := REPLACE(REPLACE(REPLACE(TRIM(p_txt), ' ', ''), CHR(160), ''), '''', '');
    IF v IS NULL THEN RETURN NULL; END IF;
    v := REPLACE(v, ',', '.');
    -- RO: ultimul punct = separator zecimal; celelalte = separatori de mii
    -- EN: the last dot is the decimal separator; the rest are thousands marks
    n := LENGTH(v) - NVL(LENGTH(REPLACE(v, '.', '')), 0);
    WHILE n > 1 LOOP
      v := SUBSTR(v, 1, INSTR(v, '.') - 1) || SUBSTR(v, INSTR(v, '.') + 1);
      n := n - 1;
    END LOOP;
    RETURN TO_NUMBER(v, '999999999999999D999999',
                     'NLS_NUMERIC_CHARACTERS=''. ''');
  EXCEPTION WHEN OTHERS THEN RETURN NULL;
  END parse_price;

  FUNCTION fix_confusables(p_txt VARCHAR2) RETURN VARCHAR2 IS
  BEGIN
    RETURN TRANSLATE(p_txt, c_conf_cyr, c_conf_lat);
  END fix_confusables;

  FUNCTION cyr_count(p_txt VARCHAR2) RETURN PLS_INTEGER IS
  BEGIN
    IF p_txt IS NULL THEN RETURN 0; END IF;
    RETURN NVL(LENGTH(p_txt),0)
         - NVL(LENGTH(TRANSLATE(p_txt, '_' || c_cyr_all, '_')),0);
  END cyr_count;

  PROCEDURE set_conf(p_name VARCHAR2, p_value VARCHAR2) IS
    v_name VARCHAR2(64) := LOWER(TRIM(p_name));
  BEGIN
    CASE v_name
      WHEN 'tbl_goods'      THEN g_tbl_goods      := p_value;
      WHEN 'col_key'        THEN g_col_key        := p_value;
      WHEN 'col_id'         THEN g_col_id         := p_value;
      WHEN 'col_brand'      THEN g_col_brand      := p_value;
      WHEN 'col_articol'    THEN g_col_articol    := p_value;
      WHEN 'col_denumire'   THEN g_col_denumire   := p_value;
      WHEN 'col_angro'      THEN g_col_angro      := p_value;
      WHEN 'col_ionline'    THEN g_col_ionline    := p_value;
      WHEN 'col_retail'     THEN g_col_retail     := p_value;
      WHEN 'seq_key'        THEN g_seq_key        := p_value;
      WHEN 'codprice'       THEN g_codprice       := TO_NUMBER(p_value);
      WHEN 'pricename'      THEN g_pricename      := p_value;
      WHEN 'currency'       THEN g_currency       := p_value;
      WHEN 'um'             THEN g_um             := p_value;
      WHEN 'gr1'            THEN g_gr1            := p_value;
      WHEN 'tip'            THEN g_tip            := p_value;
      WHEN 'caccess'        THEN g_caccess        := p_value;
      WHEN 'codtva'         THEN g_codtva         := p_value;
      WHEN 'date_start'     THEN g_date_start     := TO_DATE(p_value,'DD.MM.YYYY');
      WHEN 'date_end'       THEN g_date_end       := TO_DATE(p_value,'DD.MM.YYYY');
      WHEN 'group_type'     THEN g_group_type     := p_value;
      WHEN 'empty_brand'    THEN g_empty_brand    := p_value;
      WHEN 'len_codvechi'   THEN g_len_codvechi   := TO_NUMBER(p_value);
      WHEN 'len_denumire'   THEN g_len_denumire   := TO_NUMBER(p_value);
      WHEN 'isarhiv_arc'    THEN g_isarhiv_arc    := p_value;
      WHEN 'isarhiv_lock'   THEN g_isarhiv_lock   := p_value;
      WHEN 'confus_max_cyr' THEN g_confus_max_cyr := TO_NUMBER(p_value);
      ELSE RAISE_APPLICATION_ERROR(-20602,
        'Parametru necunoscut / unknown parameter: ' || v_name);
    END CASE;
  END set_conf;

  FUNCTION get_conf(p_name VARCHAR2) RETURN VARCHAR2 IS
    v_name VARCHAR2(64) := LOWER(TRIM(p_name));
  BEGIN
    CASE v_name
      WHEN 'tbl_goods'      THEN RETURN g_tbl_goods;
      WHEN 'col_key'        THEN RETURN g_col_key;
      WHEN 'col_id'         THEN RETURN g_col_id;
      WHEN 'col_brand'      THEN RETURN g_col_brand;
      WHEN 'col_articol'    THEN RETURN g_col_articol;
      WHEN 'col_denumire'   THEN RETURN g_col_denumire;
      WHEN 'col_angro'      THEN RETURN g_col_angro;
      WHEN 'col_ionline'    THEN RETURN g_col_ionline;
      WHEN 'col_retail'     THEN RETURN g_col_retail;
      WHEN 'seq_key'        THEN RETURN g_seq_key;
      WHEN 'codprice'       THEN RETURN TO_CHAR(g_codprice);
      WHEN 'pricename'      THEN RETURN g_pricename;
      WHEN 'currency'       THEN RETURN g_currency;
      WHEN 'um'             THEN RETURN g_um;
      WHEN 'gr1'            THEN RETURN g_gr1;
      WHEN 'tip'            THEN RETURN g_tip;
      WHEN 'caccess'        THEN RETURN g_caccess;
      WHEN 'codtva'         THEN RETURN g_codtva;
      WHEN 'date_start'     THEN RETURN TO_CHAR(g_date_start,'DD.MM.YYYY');
      WHEN 'date_end'       THEN RETURN TO_CHAR(g_date_end,'DD.MM.YYYY');
      WHEN 'group_type'     THEN RETURN g_group_type;
      WHEN 'empty_brand'    THEN RETURN g_empty_brand;
      WHEN 'len_codvechi'   THEN RETURN TO_CHAR(g_len_codvechi);
      WHEN 'len_denumire'   THEN RETURN TO_CHAR(g_len_denumire);
      WHEN 'isarhiv_arc'    THEN RETURN g_isarhiv_arc;
      WHEN 'isarhiv_lock'   THEN RETURN g_isarhiv_lock;
      WHEN 'confus_max_cyr' THEN RETURN TO_CHAR(g_confus_max_cyr);
      ELSE RAISE_APPLICATION_ERROR(-20602,
        'Parametru necunoscut / unknown parameter: ' || v_name);
    END CASE;
  END get_conf;

  PROCEDURE prepare_input IS
    v_cnt PLS_INTEGER;
  BEGIN
    assert_idents;
    log('prepare_input','START','Pregatire sursa / preparing input: ' || g_tbl_goods);
    EXECUTE IMMEDIATE
      'UPDATE ' || g_tbl_goods || ' SET '
      || g_col_articol  || ' = TRIM(' || g_col_articol  || '), '
      || g_col_denumire || ' = TRIM(' || g_col_denumire || '), '
      || g_col_brand    || ' = NVL(TRIM(' || g_col_brand || '), :b)'
      USING g_empty_brand;
    v_cnt := SQL%ROWCOUNT;
    log('prepare_input','OK','Randuri pregatite / rows prepared', v_cnt);
  EXCEPTION WHEN OTHERS THEN
    log('prepare_input','ERROR', SUBSTR(SQLERRM,1,3900)); RAISE;
  END prepare_input;

  PROCEDURE validate_input IS
    v_null_den  PLS_INTEGER;
    v_bad_price PLS_INTEGER;
    v_has_st    PLS_INTEGER;
  BEGIN
    assert_idents;
    log('validate_input','START','Validare sursa / validating input');
    EXECUTE IMMEDIATE
      'SELECT COUNT(*) FROM ' || g_tbl_goods
      || ' WHERE ' || g_col_denumire || ' IS NULL'
      INTO v_null_den;
    EXECUTE IMMEDIATE
      'SELECT COUNT(*) FROM ' || g_tbl_goods
      || ' WHERE ' || g_col_retail || ' IS NOT NULL'
      || ' AND YSERVOUTS_BP.PARSE_PRICE(' || g_col_retail || ') IS NULL'
      INTO v_bad_price;
    -- RO: marcheaza STATUS/ERR_MSG doar daca tabelul sursa are aceste coloane
    -- EN: set STATUS/ERR_MSG only if the source table has those columns
    SELECT COUNT(*) INTO v_has_st FROM user_tab_columns
     WHERE table_name = UPPER(g_tbl_goods) AND column_name = 'STATUS';
    IF v_has_st > 0 THEN
      EXECUTE IMMEDIATE
        'UPDATE ' || g_tbl_goods || ' SET STATUS = CASE WHEN '
        || g_col_denumire || ' IS NULL THEN ''ERR'' ELSE ''OK'' END,'
        || ' ERR_MSG = CASE WHEN ' || g_col_denumire
        || ' IS NULL THEN ''Denumire lipsa / missing name'' END';
    END IF;
    IF v_null_den > 0 THEN
      log('validate_input','WARN','Denumiri lipsa / missing names', v_null_den);
    END IF;
    IF v_bad_price > 0 THEN
      log('validate_input','WARN','Preturi neconvertibile / unparsable prices', v_bad_price);
    END IF;
    log('validate_input','OK','Validare incheiata / validation done');
  EXCEPTION WHEN OTHERS THEN
    log('validate_input','ERROR', SUBSTR(SQLERRM,1,3900)); RAISE;
  END validate_input;

  PROCEDURE assign_keys IS
    v_cnt PLS_INTEGER;
  BEGIN
    assert_idents;
    log('assign_keys','START','Alocare chei / assigning keys: ' || g_seq_key);
    EXECUTE IMMEDIATE
      'UPDATE ' || g_tbl_goods || ' SET ' || g_col_key || ' = '
      || g_seq_key || '.NEXTVAL WHERE ' || g_col_key || ' IS NULL';
    v_cnt := SQL%ROWCOUNT;
    log('assign_keys','OK','Chei alocate / keys assigned', v_cnt);
  EXCEPTION WHEN OTHERS THEN
    log('assign_keys','ERROR', SUBSTR(SQLERRM,1,3900)); RAISE;
  END assign_keys;

  PROCEDURE import_univers IS
    v_cnt PLS_INTEGER;
  BEGIN
    assert_idents;
    log('import_univers','START','Import in TMS_UNIVERS din / from ' || g_tbl_goods);
    EXECUTE IMMEDIATE
      'INSERT INTO TMS_UNIVERS (COD, CODVECHI, DENUMIREA, UM, GR1, TIP, CACCESS, CODTVA) '
      || 'SELECT s.' || g_col_key || ', SUBSTR(s.' || g_col_articol || ',1,'
      || g_len_codvechi || '), '
      || 'SUBSTR(YSERVOUTS_BP.FIX_CONFUSABLES(s.' || g_col_denumire || '),1,'
      || g_len_denumire || '), '
      || ':um, :gr1, :tip, :cac, :tva FROM ' || g_tbl_goods || ' s '
      || 'WHERE s.' || g_col_key || ' IS NOT NULL '
      || 'AND s.' || g_col_denumire || ' IS NOT NULL '
      || 'AND NOT EXISTS (SELECT 1 FROM TMS_UNIVERS u WHERE u.COD = s.' || g_col_key || ')'
      USING g_um, g_gr1, g_tip, g_caccess, g_codtva;
    v_cnt := SQL%ROWCOUNT;
    log('import_univers','OK','Pozitii noi in TMS_UNIVERS / new TMS_UNIVERS rows', v_cnt);
  EXCEPTION WHEN OTHERS THEN
    log('import_univers','ERROR', SUBSTR(SQLERRM,1,3900)); RAISE;
  END import_univers;

  PROCEDURE import_groups IS
    v_cnt PLS_INTEGER;
    v_max NUMBER;
    v_hdr PLS_INTEGER;
  BEGIN
    assert_idents;
    log('import_groups','START','Grupe din brand-uri / groups from brands, CODPRICE=' || g_codprice);
    -- RO: capul pricelist-ului (TPR0M_PRICES) trebuie sa existe — FK-ul
    --     TPR01M_GROUPS_FK; se creeaza automat daca lipseste.
    -- EN: the pricelist header (TPR0M_PRICES) must exist — FK
    --     TPR01M_GROUPS_FK; it is auto-created when missing.
    SELECT COUNT(*) INTO v_hdr FROM TPR0M_PRICES WHERE CODPRICE = g_codprice;
    IF v_hdr = 0 THEN
      INSERT INTO TPR0M_PRICES (CODPRICE, PRICENAME, TYPE_SC, VAL)
      VALUES (g_codprice, SUBSTR(g_pricename,1,25), g_group_type, g_currency);
      log('import_groups','INFO','Cap pricelist creat / pricelist header created: '
          || g_codprice || ' ' || g_pricename);
    END IF;
    -- RO: numerotarea CODGRP continua de la maximul existent (global)
    -- EN: CODGRP numbering continues from the existing (global) maximum
    SELECT NVL(MAX(CODGRP),0) INTO v_max FROM TPR01M_GROUPS;
    EXECUTE IMMEDIATE
      'INSERT INTO VPR01M_GROUPS (CODPRICE, CODGRP, GRPNAME, TYPE_SC) '
      || 'SELECT :cp, :mx + ROWNUM, b, :ts FROM ('
      ||   'SELECT DISTINCT NVL(s.' || g_col_brand || ', :eb) b FROM '
      ||   g_tbl_goods || ' s '
      ||   'MINUS SELECT g.GRPNAME FROM TPR01M_GROUPS g WHERE g.CODPRICE = :cp2)'
      USING g_codprice, v_max, g_group_type, g_empty_brand, g_codprice;
    v_cnt := SQL%ROWCOUNT;
    log('import_groups','OK','Grupe noi / new groups', v_cnt);
  EXCEPTION WHEN OTHERS THEN
    log('import_groups','ERROR', SUBSTR(SQLERRM,1,3900)); RAISE;
  END import_groups;

  PROCEDURE import_dates IS
    v_cnt PLS_INTEGER;
  BEGIN
    log('import_dates','START','Perioade pricelist / pricelist periods, CODPRICE=' || g_codprice);
    -- RO: sfarsitul deschis (01.01.3000) e derivat de view prin LEAD — se
    --     insereaza doar data de start.
    -- EN: the open end (01.01.3000) is derived by the view via LEAD — only
    --     the start date is inserted.
    -- RO: doar grupele cu nume (cele importate) — grupele native fara
    --     GRPNAME nu primesc perioade noi.
    -- EN: named groups only (the imported ones) — native no-name groups
    --     do not get new periods.
    INSERT INTO VPR1D_PRDATE (CODPRICE, CODGRP, DATA, NRDOC)
    SELECT g.CODPRICE, g.CODGRP, g_date_start, NULL
      FROM TPR01M_GROUPS g
     WHERE g.CODPRICE = g_codprice
       AND g.GRPNAME IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM TPR1D_PRDATE d
                        WHERE d.CODPRICE = g.CODPRICE
                          AND d.CODGRP   = g.CODGRP
                          AND d.DATA     = g_date_start);
    v_cnt := SQL%ROWCOUNT;
    log('import_dates','OK','Perioade noi / new periods', v_cnt);
  EXCEPTION WHEN OTHERS THEN
    log('import_dates','ERROR', SUBSTR(SQLERRM,1,3900)); RAISE;
  END import_dates;

  PROCEDURE import_prices IS
    v_cnt PLS_INTEGER;
  BEGIN
    assert_idents;
    log('import_prices','START','Import preturi / importing prices, CODPRICE=' || g_codprice);
    -- RO: o singura linie de pret per SC (la dubluri — retail maxim);
    --     scrierea trece prin trigger-ul INSTEAD OF al view-ului.
    -- EN: a single price row per SC (on duplicates — max retail);
    --     writes go through the view's INSTEAD OF trigger.
    EXECUTE IMMEDIATE
      'INSERT INTO VTPR1D_PERPRLIST (CODPRICE, CODGRP, SC, DATASTART, DATAEND, PRETV, PRETV1, PRETV2) '
      || 'SELECT :cp, g.CODGRP, x.k, :ds, :de, x.p_ret, x.p_ang, x.p_onl FROM ('
      ||   'SELECT s.' || g_col_key || ' k, NVL(s.' || g_col_brand || ', :eb) b, '
      ||   'YSERVOUTS_BP.PARSE_PRICE(s.' || g_col_retail  || ') p_ret, '
      ||   'YSERVOUTS_BP.PARSE_PRICE(s.' || g_col_angro   || ') p_ang, '
      ||   'YSERVOUTS_BP.PARSE_PRICE(s.' || g_col_ionline || ') p_onl, '
      ||   'ROW_NUMBER() OVER (PARTITION BY s.' || g_col_key || ' ORDER BY '
      ||   'YSERVOUTS_BP.PARSE_PRICE(s.' || g_col_retail || ') DESC NULLS LAST) rn '
      ||   'FROM ' || g_tbl_goods || ' s WHERE s.' || g_col_key || ' IS NOT NULL) x '
      || 'JOIN TPR01M_GROUPS g ON g.CODPRICE = :cp2 AND g.GRPNAME = x.b '
      || 'WHERE x.rn = 1 AND NOT EXISTS (SELECT 1 FROM TPR1D_PERPRLIST t '
      || 'WHERE t.CODPRICE = :cp3 AND t.CODGRP = g.CODGRP AND t.SC = x.k '
      || 'AND t.DATASTART = :ds2)'
      USING g_codprice, g_date_start, g_date_end, g_empty_brand,
            g_codprice, g_codprice, g_date_start;
    v_cnt := SQL%ROWCOUNT;
    log('import_prices','OK','Preturi importate / prices imported', v_cnt);
  EXCEPTION WHEN OTHERS THEN
    log('import_prices','ERROR', SUBSTR(SQLERRM,1,3900)); RAISE;
  END import_prices;

  PROCEDURE import_all IS
  BEGIN
    log('import_all','START','Import complet / full import: ' || g_tbl_goods
        || ' -> CODPRICE=' || g_codprice);
    prepare_input;
    validate_input;
    assign_keys;
    import_univers;
    import_groups;
    import_dates;
    import_prices;
    log('import_all','OK','Import complet incheiat / full import done');
  EXCEPTION WHEN OTHERS THEN
    ROLLBACK;
    log('import_all','ERROR', SUBSTR(SQLERRM,1,3900));
    RAISE;
  END import_all;

  PROCEDURE rollback_pricelist(p_codprice NUMBER DEFAULT NULL) IS
    v_cp NUMBER := NVL(p_codprice, g_codprice);
    v1 PLS_INTEGER; v2 PLS_INTEGER; v3 PLS_INTEGER;
  BEGIN
    log('rollback_pricelist','START','Rollback pricelist CODPRICE=' || v_cp);
    -- RO: se atinge DOAR ce a creat importul — grupele cu nume; preturile,
    --     perioadele si grupele native (GRPNAME NULL) raman neatinse.
    -- EN: touches ONLY what the import created — named groups; native
    --     prices, periods and no-name groups are left untouched.
    DELETE FROM TPR1D_PERPRLIST t
     WHERE t.CODPRICE = v_cp
       AND EXISTS (SELECT 1 FROM TPR01M_GROUPS g
                    WHERE g.CODPRICE = v_cp AND g.CODGRP = t.CODGRP
                      AND g.GRPNAME IS NOT NULL);
    v1 := SQL%ROWCOUNT;
    DELETE FROM TPR1D_PRDATE d
     WHERE d.CODPRICE = v_cp
       AND EXISTS (SELECT 1 FROM TPR01M_GROUPS g
                    WHERE g.CODPRICE = v_cp AND g.CODGRP = d.CODGRP
                      AND g.GRPNAME IS NOT NULL);
    v2 := SQL%ROWCOUNT;
    DELETE FROM TPR01M_GROUPS
     WHERE CODPRICE = v_cp AND GRPNAME IS NOT NULL;
    v3 := SQL%ROWCOUNT;
    log('rollback_pricelist','OK',
        'Sterse / removed: preturi/prices=' || v1 || ', perioade/periods=' || v2
        || ', grupe/groups=' || v3, v1 + v2 + v3);
  EXCEPTION WHEN OTHERS THEN
    log('rollback_pricelist','ERROR', SUBSTR(SQLERRM,1,3900)); RAISE;
  END rollback_pricelist;

  PROCEDURE merge_groups(p_src NUMBER, p_dst NUMBER, p_codprice NUMBER DEFAULT NULL) IS
    v_cp NUMBER := NVL(p_codprice, g_codprice);
    v_moved PLS_INTEGER;
  BEGIN
    log('merge_groups','START','Unificare grupe / merging groups '
        || p_src || ' -> ' || p_dst || ', CODPRICE=' || v_cp);
    -- RO: elimina liniile sursa deja prezente la destinatie (PK protejat)
    -- EN: drop source rows already present at the destination (PK-safe)
    DELETE FROM TPR1D_PERPRLIST s
     WHERE s.CODPRICE = v_cp AND s.CODGRP = p_src
       AND EXISTS (SELECT 1 FROM TPR1D_PERPRLIST d
                    WHERE d.CODPRICE = v_cp AND d.CODGRP = p_dst
                      AND d.SC = s.SC AND d.DATASTART = s.DATASTART);
    UPDATE TPR1D_PERPRLIST SET CODGRP = p_dst
     WHERE CODPRICE = v_cp AND CODGRP = p_src;
    v_moved := SQL%ROWCOUNT;
    DELETE FROM TPR1D_PRDATE s
     WHERE s.CODPRICE = v_cp AND s.CODGRP = p_src
       AND EXISTS (SELECT 1 FROM TPR1D_PRDATE d
                    WHERE d.CODPRICE = v_cp AND d.CODGRP = p_dst
                      AND d.DATA = s.DATA);
    UPDATE TPR1D_PRDATE SET CODGRP = p_dst
     WHERE CODPRICE = v_cp AND CODGRP = p_src;
    DELETE FROM TPR01M_GROUPS
     WHERE CODPRICE = v_cp AND CODGRP = p_src;
    log('merge_groups','OK','Preturi mutate / prices moved', v_moved);
  EXCEPTION WHEN OTHERS THEN
    log('merge_groups','ERROR', SUBSTR(SQLERRM,1,3900)); RAISE;
  END merge_groups;

  PROCEDURE archive_univers(p_cod NUMBER, p_isarhiv VARCHAR2 DEFAULT NULL) IS
    v_val VARCHAR2(1) := NVL(p_isarhiv, g_isarhiv_arc);
    v_cnt PLS_INTEGER;
  BEGIN
    -- RO: valoarea de blocare ('2') e respinsa de trigger-ul ERP — eroarea
    --     se propaga la apelant.
    -- EN: the lock value ('2') is rejected by the ERP trigger — the error
    --     propagates to the caller.
    UPDATE TMS_UNIVERS SET ISARHIV = v_val WHERE COD = p_cod;
    v_cnt := SQL%ROWCOUNT;
    log('archive_univers','OK','COD=' || p_cod || ' ISARHIV=' || v_val, v_cnt);
  EXCEPTION WHEN OTHERS THEN
    log('archive_univers','ERROR','COD=' || p_cod || ': ' || SUBSTR(SQLERRM,1,3800));
    RAISE;
  END archive_univers;

  PROCEDURE fix_denumirea_confusables IS
    v_cnt PLS_INTEGER := 0;
  BEGIN
    log('fix_confus','START',
        'Curatare denumiri (max ' || g_confus_max_cyr
        || ' litere chirilice) / cleaning names');
    FOR r IN (SELECT COD, DENUMIREA FROM TMS_UNIVERS
               WHERE DENUMIREA IS NOT NULL) LOOP
      IF cyr_count(r.DENUMIREA) BETWEEN 1 AND g_confus_max_cyr
         AND fix_confusables(r.DENUMIREA) <> r.DENUMIREA THEN
        UPDATE TMS_UNIVERS
           SET DENUMIREA = fix_confusables(r.DENUMIREA)
         WHERE COD = r.COD;
        v_cnt := v_cnt + 1;
      END IF;
    END LOOP;
    log('fix_confus','OK','Denumiri corectate / names fixed', v_cnt);
  EXCEPTION WHEN OTHERS THEN
    log('fix_confus','ERROR', SUBSTR(SQLERRM,1,3900)); RAISE;
  END fix_denumirea_confusables;

END YServOuts_BP;
/
