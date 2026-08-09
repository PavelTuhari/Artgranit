-- Y_AI_BIRO26 (OFFICEPLUS, Oracle 11g) — package BODY
-- Выгружено 2026-08-09 (ensure_nrmanual + gen_conturi_pr по COD)
PACKAGE BODY            y_ai_BIRO26 AS

  g_last_cod NUMBER;  -- RO: ultimul COD creat / EN: last created COD

  FUNCTION register_client(p_name IN VARCHAR2) RETURN NUMBER IS
    v_cod NUMBER;
  BEGIN
    SELECT ID_TMS_UNIVERS.NEXTVAL INTO v_cod FROM dual;
    INSERT INTO TMS_UNIVERS (COD, DENUMIREA, TIP, GR1, CACCESS)
    VALUES (v_cod, SUBSTR(p_name, 1, 160), g_client_tip, g_client_gr1, g_caccess);
    RETURN v_cod;
  END register_client;

  FUNCTION next_invoice_nr RETURN NUMBER IS
    v_start NUMBER := 1;
    v_raw   VARCHAR2(400);
    v_max   NUMBER;
  BEGIN
    -- RO: INVOICE_NR_START = urmatorul numar de emis (contor).
    --     Daca lipsete setarea, fallback = max(NRMANUAL)+1 pe SYSFID.
    -- EN: INVOICE_NR_START = next number to issue (counter).
    --     If unset, fallback = max(NRMANUAL)+1 for the form SYSFID.
    BEGIN
      v_raw := get_setting(g_invoice_nr_start_key);
      IF v_raw IS NOT NULL AND REGEXP_LIKE(TRIM(v_raw), '^[0-9]+$') THEN
        RETURN TO_NUMBER(TRIM(v_raw));
      END IF;
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
    SELECT NVL(MAX(
             CASE
               WHEN REGEXP_LIKE(TRIM(NRMANUAL), '^[0-9]+$')
               THEN TO_NUMBER(TRIM(NRMANUAL))
               ELSE NULL
             END
           ), 0) + 1
      INTO v_max
      FROM TMDB_DOCS
     WHERE SYSFID = g_sysfid;
    RETURN NVL(v_max, 1);
  END next_invoice_nr;

  FUNCTION create_invoice(p_client_cod IN NUMBER,
                          p_data       IN DATE DEFAULT TRUNC(SYSDATE))
    RETURN NUMBER IS
    v_cod      NUMBER;
    v_nr_num   NUMBER;
    v_serie    VARCHAR2(4);
    v_nrmanual VARCHAR2(25);
  BEGIN
    SELECT ID_TMDB_DOCS.NEXTVAL INTO v_cod FROM dual;
    -- RO: NRMANUAL = SERIE-NUMAR (ex. 'A-23'): seria incepe cu 'A';
    --     cind numarul trece de 999, seria trece AUTOMAT la litera
    --     urmatoare (B, C, D...) si numerotarea reincepe de la 1.
    --     Contorul numeric: YBIRO_SETTINGS.INVOICE_NR_START (admin web);
    --     seria: YBIRO_SETTINGS.INVOICE_SERIES.
    -- EN: NRMANUAL = SERIES-NUMBER; at >999 the series letter advances
    --     automatically and numbering restarts at 1.
    v_nr_num := next_invoice_nr;
    v_serie  := UPPER(SUBSTR(NVL(get_setting('INVOICE_SERIES'), 'A'), 1, 1));
    IF v_serie IS NULL OR v_serie < 'A' OR v_serie > 'Z' THEN
      v_serie := 'A';
    END IF;
    IF v_nr_num > 999 THEN
      v_serie  := CHR(LEAST(ASCII(v_serie) + 1, ASCII('Z')));
      v_nr_num := 1;
      set_setting('INVOICE_SERIES', v_serie,
        'RO: seria curenta a contului (A..Z) / EN: current invoice series');
    END IF;
    v_nrmanual := v_serie || '-' || TO_CHAR(v_nr_num);

    -- RO: incrementeaza contorul (urmatorul cont va primi nr+1)
    -- EN: bump counter (next invoice gets nr+1)
    set_setting(g_invoice_nr_start_key, TO_CHAR(v_nr_num + 1),
      'RO: urmatorul NRMANUAL de emis / EN: next NRMANUAL to issue');
    IF get_setting('INVOICE_SERIES') IS NULL THEN
      set_setting('INVOICE_SERIES', v_serie,
        'RO: seria curenta a contului (A..Z) / EN: current invoice series');
    END IF;

    INSERT INTO TMDB_DOCS (COD, TIP, SYSFID, USERID, DATAMANUAL, VALUTA,
                           NRMANUAL, NRSET, ISGFC, DOCCOLOR, CODF, AT2, AT3)
    VALUES (v_cod, g_tip, g_sysfid, UID, p_data, g_valuta,
            v_nrmanual, g_nrset_default, 0, g_doccolor, 0, g_at2, 0);

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
    -- RO: compat — numar din NRMANUAL / EN: compat — number from NRMANUAL
    SELECT CASE
             WHEN REGEXP_LIKE(TRIM(NRMANUAL), '^[0-9]+$')
             THEN TO_NUMBER(TRIM(NRMANUAL))
             ELSE NULL
           END
      INTO v
      FROM TMDB_DOCS
     WHERE COD = p_nrdoc;
    RETURN v;
  END get_nrset;

  FUNCTION get_nrmanual(p_nrdoc IN NUMBER) RETURN VARCHAR2 IS
    v VARCHAR2(25);
  BEGIN
    SELECT NRMANUAL INTO v FROM TMDB_DOCS WHERE COD = p_nrdoc;
    RETURN v;
  END get_nrmanual;

  FUNCTION ensure_nrmanual(p_nrdoc IN NUMBER) RETURN VARCHAR2 IS
    PRAGMA AUTONOMOUS_TRANSACTION;
    v_nr     VARCHAR2(25);
    v_nr_num NUMBER;
    v_serie  VARCHAR2(4);
    v_used   NUMBER;
    v_guard  NUMBER := 0;
    v_tmp    VARCHAR2(400);
  BEGIN
    -- RO: documentele venite din ALTE aplicatii pot ramine fara NRMANUAL.
    --     Numarul se atribuie dupa ACELEASI reguli ca la create_invoice:
    --     seria INVOICE_SERIES + contorul INVOICE_NR_START (rollover >999).
    --
    --     TRANZACTIE AUTONOMA cu COMMIT imediat — obligatoriu: numarul
    --     trebuie sa fie VIZIBIL si randul ELIBERAT inainte de apelul HTTP
    --     catre site. Altfel site-ul (alta sesiune) asteapta randul blocat,
    --     iar Oracle asteapta raspunsul HTTP — blocaj reciproc prin retea.
    -- EN: assign by create_invoice's rules in an AUTONOMOUS transaction and
    --     COMMIT at once: the number must be visible and the row unlocked
    --     before the HTTP call, otherwise the site (another session) waits
    --     for the row while Oracle waits for the HTTP reply.
    SELECT NRMANUAL INTO v_nr FROM TMDB_DOCS WHERE COD = p_nrdoc;
    IF TRIM(v_nr) IS NOT NULL THEN
      COMMIT;
      RETURN v_nr;
    END IF;

    -- RO: NOWAIT — daca documentul e deschis in alta sesiune (aplicatia
    --     nativa a altui utilizator), raportam IMEDIAT, fara sa asteptam.
    -- EN: NOWAIT — report at once when the doc is open in another session.
    BEGIN
      SELECT NRMANUAL INTO v_nr FROM TMDB_DOCS
       WHERE COD = p_nrdoc FOR UPDATE NOWAIT;
    EXCEPTION WHEN OTHERS THEN
      ROLLBACK;
      msg('ERR: documentul COD=' || p_nrdoc || ' este deschis in alta sesiune. '
          || 'Salvati / inchideti documentul si repetati generarea.');
      RETURN NULL;
    END;

    v_nr_num := next_invoice_nr;
    v_serie  := UPPER(SUBSTR(NVL(get_setting('INVOICE_SERIES'), 'A'), 1, 1));
    IF v_serie IS NULL OR v_serie < 'A' OR v_serie > 'Z' THEN
      v_serie := 'A';
    END IF;
    IF v_nr_num > 999 THEN
      v_serie  := CHR(LEAST(ASCII(v_serie) + 1, ASCII('Z')));
      v_nr_num := 1;
    END IF;
    -- RO/EN: cautam primul numar LIBER (unicitatea se verifica in documente)
    LOOP
      v_guard := v_guard + 1;
      v_nr := v_serie || '-' || TO_CHAR(v_nr_num);
      SELECT COUNT(*) INTO v_used FROM TMDB_DOCS
       WHERE SYSFID = g_sysfid AND TRIM(NRMANUAL) = v_nr;
      EXIT WHEN v_used = 0 OR v_guard >= 1000;
      v_nr_num := v_nr_num + 1;
      IF v_nr_num > 999 THEN
        v_serie  := CHR(LEAST(ASCII(v_serie) + 1, ASCII('Z')));
        v_nr_num := 1;
      END IF;
    END LOOP;

    -- RO: documentele din alte aplicatii au AT2 IS NULL, iar perioada de
    --     lucru din TPARAMS nu e completata, deci TRIG_BFALL_TMDB_DOCS
    --     interzice UPDATE-ul. Atribuirea numarului e operatiune de SISTEM:
    --     folosim ocolirea prevazuta de trigger (envun4.dont_fire_trigger,
    --     aceeasi pe care o foloseste importul) si o ridicam IMEDIAT.
    -- EN: system-level numbering uses the trigger's own documented bypass.
    BEGIN
      un4public.envun4.envsetvalue('dont_fire_trigger', '1');
      UPDATE TMDB_DOCS SET NRMANUAL = v_nr WHERE COD = p_nrdoc;
      un4public.envun4.envsetvalue('dont_fire_trigger', NULL);
    EXCEPTION
      WHEN OTHERS THEN
        BEGIN
          un4public.envun4.envsetvalue('dont_fire_trigger', NULL);
        EXCEPTION WHEN OTHERS THEN NULL;
        END;
        ROLLBACK;
        RAISE;
    END;

    -- RO/EN: contorul se ridica «pe cit se poate» — unicitatea e deja
    --        asigurata mai sus prin verificarea in TMDB_DOCS.
    BEGIN
      SELECT SVAL INTO v_tmp FROM YBIRO_SETTINGS
       WHERE SKEY = g_invoice_nr_start_key FOR UPDATE NOWAIT;
      set_setting(g_invoice_nr_start_key, TO_CHAR(v_nr_num + 1),
        'RO: urmatorul NRMANUAL de emis / EN: next NRMANUAL to issue');
      set_setting('INVOICE_SERIES', v_serie,
        'RO: seria curenta a contului (A..Z) / EN: current invoice series');
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;

    COMMIT;
    RETURN v_nr;
  EXCEPTION
    WHEN NO_DATA_FOUND THEN
      ROLLBACK;
      RETURN NULL;
  END ensure_nrmanual;

  FUNCTION last_doc RETURN NUMBER IS
  BEGIN
    RETURN g_last_cod;
  END last_doc;

  -- ===================================================================
  -- Preturi pe perioade / price periods
  -- ===================================================================

  -- RO: Grupa articolului in lista de preturi (1 daca articolul e nou).
  -- EN: The item's group inside the price list (1 for brand-new items).
  FUNCTION price_group(p_sc IN NUMBER, p_codprice IN NUMBER) RETURN NUMBER IS
    v_grp NUMBER;
  BEGIN
    SELECT CODGRP INTO v_grp
      FROM (SELECT CODGRP FROM TPR1D_PERPRLIST
             WHERE CODPRICE = p_codprice AND SC = p_sc
             ORDER BY DATASTART DESC)
     WHERE ROWNUM = 1;
    RETURN v_grp;
  EXCEPTION WHEN NO_DATA_FOUND THEN
    RETURN 1;
  END price_group;

  PROCEDURE set_price(p_sc       IN NUMBER,
                      p_data     IN DATE   DEFAULT TRUNC(SYSDATE),
                      p_pretv    IN NUMBER DEFAULT NULL,
                      p_pretv1   IN NUMBER DEFAULT NULL,
                      p_pretv2   IN NUMBER DEFAULT NULL,
                      p_codprice IN NUMBER DEFAULT NULL,
                      p_codgrp   IN NUMBER DEFAULT NULL) IS
    v_cp   NUMBER := NVL(p_codprice, g_codprice);
    v_grp  NUMBER := NVL(p_codgrp, price_group(p_sc, NVL(p_codprice, g_codprice)));
    v_d    DATE   := TRUNC(p_data);
    v_cnt  NUMBER;
    v_pv   NUMBER; v_p1 NUMBER; v_p2 NUMBER; v_p3 NUMBER;
  BEGIN
    -- RO: trigger-ul nativ de INSERT foloseste literalul '31.12.3000';
    --     fixam formatul de sesiune ca sa nu pice sub alt NLS.
    -- EN: the native INSERT trigger uses the '31.12.3000' literal; pin the
    --     session date format so it parses under any client NLS.
    EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''DD.MM.YYYY''';

    SELECT COUNT(*) INTO v_cnt FROM TPR1D_PERPRLIST
     WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATASTART = v_d;

    IF v_cnt > 0 THEN
      -- RO: perioada incepe exact la p_data -> doar actualizare
      -- EN: a period starts exactly at p_data -> plain update
      UPDATE VTPR1D_PERPRLIST
         SET PRETV  = NVL(p_pretv,  PRETV),
             PRETV1 = NVL(p_pretv1, PRETV1),
             PRETV2 = NVL(p_pretv2, PRETV2)
       WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATASTART = v_d;
    ELSE
      -- RO: valorile nespecificate se preiau din perioada in vigoare
      -- EN: unspecified values are carried from the effective period
      BEGIN
        SELECT PRETV, PRETV1, PRETV2, PRETV3 INTO v_pv, v_p1, v_p2, v_p3
          FROM TPR1D_PERPRLIST
         WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc
           AND v_d BETWEEN DATASTART AND DATAEND;
      EXCEPTION WHEN NO_DATA_FOUND THEN
        v_pv := NULL; v_p1 := NULL; v_p2 := NULL; v_p3 := NULL;
      END;
      -- RO: INSERT prin vedere -> trigger-ul nativ DIVIDE perioada
      -- EN: INSERT through the view -> the native trigger SPLITS the period
      INSERT INTO VTPR1D_PERPRLIST
        (CODPRICE, CODGRP, SC, DATASTART, PRETV, PRETV1, PRETV2, PRETV3)
      VALUES
        (v_cp, v_grp, p_sc, v_d,
         NVL(p_pretv, v_pv), NVL(p_pretv1, v_p1), NVL(p_pretv2, v_p2), v_p3);
    END IF;
  END set_price;

  PROCEDURE del_price(p_sc       IN NUMBER,
                      p_data     IN DATE,
                      p_codprice IN NUMBER DEFAULT NULL) IS
    v_cp   NUMBER := NVL(p_codprice, g_codprice);
    v_d    DATE   := TRUNC(p_data);
    v_grp  NUMBER;
    v_de   DATE;
    v_cnt  NUMBER;
    v_prev NUMBER;
  BEGIN
    BEGIN
      SELECT CODGRP, DATAEND INTO v_grp, v_de FROM TPR1D_PERPRLIST
       WHERE CODPRICE = v_cp AND SC = p_sc AND DATASTART = v_d;
    EXCEPTION WHEN NO_DATA_FOUND THEN
      RAISE_APPLICATION_ERROR(-20262,
        'Perioada de pret inexistenta / price period not found');
    END;

    SELECT COUNT(*) INTO v_cnt FROM TPR1D_PERPRLIST
     WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc;
    IF v_cnt <= 1 THEN
      -- RO: regula: ultimul rand ramas nu se sterge
      -- EN: rule: the last remaining row cannot be deleted
      RAISE_APPLICATION_ERROR(-20261,
        'Ultimul rand de pret nu poate fi sters / the last price row cannot be deleted');
    END IF;

    SELECT COUNT(*) INTO v_prev FROM TPR1D_PERPRLIST
     WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATAEND = v_d - 1;

    IF v_prev > 0 THEN
      -- RO: stergere prin vedere -> trigger-ul nativ UNESTE perioadele
      --     (perioada precedenta se extinde pana la DATAEND-ul sters)
      -- EN: delete through the view -> the native trigger MERGES periods
      --     (the previous period extends to the deleted DATAEND)
      DELETE FROM VTPR1D_PERPRLIST
       WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATASTART = v_d;
    ELSE
      -- RO: prima perioada: urmatoarea se extinde INAPOI la DATASTART-ul
      --     sters (stergere directa + update pe tabela de baza, ca sa nu
      --     ramana gol la inceputul diapazonului)
      -- EN: first period: the next one extends BACKWARDS to the deleted
      --     DATASTART (direct base-table delete + update so the start of
      --     the range stays covered)
      DELETE FROM TPR1D_PERPRLIST
       WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATASTART = v_d;
      UPDATE TPR1D_PERPRLIST SET DATASTART = v_d
       WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATASTART = v_de + 1;
    END IF;
  END del_price;

  FUNCTION price_on(p_sc       IN NUMBER,
                    p_data     IN DATE     DEFAULT TRUNC(SYSDATE),
                    p_which    IN VARCHAR2 DEFAULT 'V',
                    p_codprice IN NUMBER   DEFAULT NULL) RETURN NUMBER IS
    v_cp NUMBER := NVL(p_codprice, g_codprice);
    v    NUMBER;
  BEGIN
    SELECT DECODE(p_which, '1', PRETV1, '2', PRETV2, PRETV) INTO v
      FROM TPR1D_PERPRLIST
     WHERE CODPRICE = v_cp AND SC = p_sc
       AND TRUNC(p_data) BETWEEN DATASTART AND DATAEND
       AND ROWNUM = 1;
    RETURN v;
  EXCEPTION WHEN NO_DATA_FOUND THEN
    RETURN NULL;
  END price_on;

  -- ===================================================================
  -- Nomenclator universal / universal product+tree creation
  -- ===================================================================

  FUNCTION add_product(p_denumirea IN VARCHAR2,
                       p_grupa     IN VARCHAR2,
                       p_categorie IN VARCHAR2 DEFAULT NULL,
                       p_retail    IN NUMBER   DEFAULT NULL,
                       p_angro     IN NUMBER   DEFAULT NULL,
                       p_online    IN NUMBER   DEFAULT NULL,
                       p_um        IN VARCHAR2 DEFAULT 'buc.',
                       p_brand     IN VARCHAR2 DEFAULT NULL,
                       p_data      IN DATE     DEFAULT TRUNC(SYSDATE))
    RETURN NUMBER IS
    v_cod NUMBER;
    v_id  NUMBER;
  BEGIN
    IF p_denumirea IS NULL OR p_grupa IS NULL THEN
      RAISE_APPLICATION_ERROR(-20263,
        'Denumirea si grupa sunt obligatorii / name and group are required');
    END IF;
    -- RO: pozitia in nomenclatorul nativ / EN: native nomenclature row
    SELECT ID_TMS_UNIVERS.NEXTVAL INTO v_cod FROM dual;
    INSERT INTO TMS_UNIVERS (COD, DENUMIREA, TIP, UM, GR1, CACCESS)
    VALUES (v_cod, SUBSTR(p_denumirea, 1, 250), 'P',
            SUBSTR(p_um, 1, 10), 'TVR', g_caccess);
    -- RO: randul de feed — GRUPA/CATEGORIE noi creeaza implicit nodul de
    --     arbore / EN: feed row — new GRUPA/CATEGORIE implicitly creates
    --     the tree node (the tree is derived from these columns)
    SELECT NVL(MAX(ID), 0) + 1 INTO v_id FROM BIRO26_GOODS;
    INSERT INTO BIRO26_GOODS (ID, COD_UNIVERS, DENUMIRE, GRUPA, CATEGORIE,
                              UNIT, BRAND, ANGRO, IONLINE, RETAIL1)
    VALUES (v_id, v_cod, SUBSTR(p_denumirea, 1, 500),
            SUBSTR(p_grupa, 1, 200), SUBSTR(p_categorie, 1, 200),
            SUBSTR(p_um, 1, 50), SUBSTR(p_brand, 1, 200),
            NVL(p_angro, p_retail), NVL(p_online, p_retail),
            TO_CHAR(p_retail, 'FM999999990.00'));
    -- RO: perioada de pret in lista (toate trei coloanele)
    -- EN: the price-list period (all three price columns)
    IF p_retail IS NOT NULL THEN
      set_price(p_sc => v_cod, p_data => p_data,
                p_pretv  => p_retail,
                p_pretv1 => NVL(p_angro, p_retail),
                p_pretv2 => NVL(p_online, p_retail));
    END IF;
    RETURN v_cod;
  END add_product;

  PROCEDURE set_setting(p_key IN VARCHAR2, p_val IN VARCHAR2,
                        p_descr IN VARCHAR2 DEFAULT NULL) IS
  BEGIN
    MERGE INTO YBIRO_SETTINGS s USING (SELECT p_key k FROM dual) d
       ON (s.skey = d.k)
     WHEN MATCHED THEN UPDATE SET s.sval = p_val,
          s.descr = NVL(p_descr, s.descr), s.updated_at = SYSTIMESTAMP
     WHEN NOT MATCHED THEN INSERT (skey, sval, descr)
          VALUES (p_key, p_val, p_descr);
  END set_setting;

  FUNCTION get_setting(p_key IN VARCHAR2) RETURN VARCHAR2 IS
    v VARCHAR2(400);
  BEGIN
    SELECT sval INTO v FROM YBIRO_SETTINGS WHERE skey = p_key;
    RETURN v;
  EXCEPTION WHEN NO_DATA_FOUND THEN
    RETURN NULL;
  END get_setting;

  -- RO: contul de plata + comanda pentru un document deja introdus:
  --     Oracle -> UTL_HTTP -> API-ul web -> PDF-urile se ataseaza la
  --     document (VMDB_DOCS_OLE); aplicatia nativa le vede la «Object».
  -- EN: Oracle-side trigger of the web generation for an existing doc.
  FUNCTION gen_conturi(p_nr      IN VARCHAR2,
                       p_formats IN VARCHAR2 DEFAULT 'pdf') RETURN VARCHAR2 IS
    v_key   VARCHAR2(200);
    v_url   VARCHAR2(1000);
    v_req   UTL_HTTP.REQ;
    v_resp  UTL_HTTP.RESP;
    v_chunk VARCHAR2(2000);
    v_out   VARCHAR2(4000) := '';
    v_open  BOOLEAN := FALSE;
  BEGIN
    v_key := get_setting('API_GEN_KEY');
    IF v_key IS NULL THEN
      RETURN 'ERR: lipseste YBIRO_SETTINGS.API_GEN_KEY '
             || '(= BIRO26_API_TOKEN din .env)';
    END IF;
    -- HTTP (nu HTTPS): Oracle 11g nu are wallet TLS pe acest server;
    -- endpoint-ul e protejat de cheia API, iar :80 nu redirecteaza API-ul.
    v_url := 'http://officeplus.md/api/biro26/gen-docs-by-nr/'
             || UTL_URL.ESCAPE(TRIM(REPLACE(p_nr, '#', '')))
             || '?api_key=' || UTL_URL.ESCAPE(v_key, TRUE)
             || '&formats=' || UTL_URL.ESCAPE(NVL(p_formats, 'pdf'), TRUE);
    UTL_HTTP.SET_TRANSFER_TIMEOUT(180);
    v_req  := UTL_HTTP.BEGIN_REQUEST(v_url, 'GET', 'HTTP/1.1');
    UTL_HTTP.SET_HEADER(v_req, 'User-Agent', 'y_ai_BIRO26.gen_conturi');
    v_resp := UTL_HTTP.GET_RESPONSE(v_req);
    v_open := TRUE;
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
      BEGIN UTL_HTTP.END_RESPONSE(v_resp);
      EXCEPTION WHEN OTHERS THEN NULL; END;
    END IF;
    RETURN 'ERR: ' || SUBSTR(SQLERRM, 1, 3900);
  END gen_conturi;
PROCEDURE gen_conturi_pr(
    p_nrdoc       IN number,
    p_formats  IN VARCHAR2 DEFAULT 'pdf'
) IS
    v_key   VARCHAR2(200);
    v_url   VARCHAR2(1000);
    v_req   UTL_HTTP.REQ;
    v_resp  UTL_HTTP.RESP;
    v_chunk VARCHAR2(2000);
    v_out   VARCHAR2(4000) := '';
    v_open  BOOLEAN := FALSE;
    p_result VARCHAR2(4000);
    p_nr     VARCHAR2(200);
BEGIN
  /* Получаем ручной номер документа. */
  begin
  select d.nrmanual into p_nr
   from vmdb_docs d 
  where d.cod = p_nrdoc
   and d.sysfid=12280;
 exception when no_data_found then
   p_result := 'ERR: documentul COD=' || p_nrdoc || ' nu exista';
   msg(p_result);
   return;
  when too_many_rows then
   p_result := 'ERR: pentru COD=' || p_nrdoc ||' au fost gasite mai multe documente';
   msg(p_result);
   return;
  end;
  
  /* RO: documentul fara NRMANUAL primeste AUTOMAT un numar dupa regulile
     existente (serie + contor) — orice aplicatie care apeleaza din interiorul
     Oracle nu mai primeste eroare.
     EN: a document without NRMANUAL gets one assigned automatically. */
  if trim(p_nr) is null then
   p_nr := ensure_nrmanual(p_nrdoc);
   if trim(p_nr) is null then
    p_result := 'ERR: documentul COD=' || p_nrdoc || ' nu exista';
    msg(p_result);
    return;
   end if;
   /* RO/EN: NU raportam prin msg() — msg = RAISE_APPLICATION_ERROR si ar
      opri procedura (numarul atribuit s-ar pierde la rollback). */
  end if;
      
  /* Получаем API-ключ. */
  v_key := get_setting('API_GEN_KEY');
  
  if v_key is null then
   p_result := 'ERR: lipseste YBIRO_SETTINGS.API_GEN_KEY';
   return;
  end if;
  
  /* Формируем URL. Символ # удаляется из NRMANUAL. */
  /* RO: identificam documentul prin COD-ul INTERN (mereu comis), iar
     numarul il trimitem ca parametru: cind aplicatia apelanta inca nu a
     comis tranzactia, site-ul nu ar vedea NRMANUAL-ul proaspat atribuit.
     EN: identify by internal COD (always committed) and pass the number,
     which may still be uncommitted in the caller's transaction. */
  v_url := 'http://officeplus.md/api/biro26/gen-docs-by-nr/'
   || TO_CHAR(p_nrdoc)
   || '?api_key=' || UTL_URL.ESCAPE(v_key, TRUE)
   || '&cod=' || TO_CHAR(p_nrdoc)
   || '&nr=' || UTL_URL.ESCAPE(TRIM(REPLACE(p_nr, '#', '')), TRUE)
   || '&formats=' || UTL_URL.ESCAPE(NVL(p_formats,'pdf'), TRUE);
  
  /* RO: msg() = RAISE_APPLICATION_ERROR (UN4PUBLIC.MSG) — orice apel
     OPRESTE procedura. Afisarea URL-ului era doar depanare si taia
     apelul HTTP inainte sa se produca. EN: msg() aborts; the URL
     debug print killed the request before it ran. */
  -- msg(v_url);
   /* Максимальное ожидание HTTP-операции — 180 секунд. */
  UTL_HTTP.SET_TRANSFER_TIMEOUT(180);
  
  v_req := UTL_HTTP.BEGIN_REQUEST(
       url          => v_url,
       method       => 'GET',
       http_version => 'HTTP/1.1'
   );   
  
  UTL_HTTP.SET_HEADER(
       v_req,
       'User-Agent',
       'y_ai_BIRO26.gen_conturi_pr'
    );

--  UTL_HTTP.SET_HEADER(
--      r     => v_req,
--      name  => 'Accept',
--      value => 'application/json'
--  );
  /* Сохраняем статус до закрытия ответа. */    
  v_resp := UTL_HTTP.GET_RESPONSE(v_req);
  v_open := TRUE;

  begin
   loop utl_http.read_text(v_resp, v_chunk, 2000);
    v_out := substr(v_out || v_chunk,1,3900);
   end loop; 
  exception
   when utl_http.end_of_body then
   null;
  end;

  UTL_HTTP.END_RESPONSE(v_resp);

  p_result := SUBSTR('HTTP ' || v_resp.status_code || ': ' || v_out, 1, 4000 );

  /* RO: raportam DOAR esecul — la succes procedura se incheie in liniste,
     ca aplicatia apelanta sa nu mai afiseze "eroare" pentru un rezultat bun.
     EN: report failures only; a successful run ends silently. */
  IF v_resp.status_code <> 200
     OR INSTR(v_out, '"success": false') > 0
     OR INSTR(v_out, '"success":false') > 0 THEN
    msg(p_result);
  END IF;
EXCEPTION
  WHEN OTHERS THEN
    IF v_open THEN
      BEGIN
        UTL_HTTP.END_RESPONSE(v_resp);
      EXCEPTION WHEN OTHERS THEN NULL;
      END;
    END IF;
    -- RO/EN: mesajele ridicate deliberat de msg() se propaga neschimbate
    IF SQLCODE = -20000 THEN
      RAISE;
    END IF;
    msg('ERR: ' || SUBSTR(SQLERRM, 1, 3900));
END ;
END y_ai_BIRO26;