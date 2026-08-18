CREATE OR REPLACE PACKAGE BIRO26PT_importData IS
  -- RO: configurare / EN: configuration
  g_tip           VARCHAR2(1)  := 'P';
  g_len_codvechi  PLS_INTEGER  := 20;
  g_len_denumire  PLS_INTEGER  := 160;
  g_max_cols      PLS_INTEGER  := 32;       -- c0..c31
  -- RO: articol prea SLAB ca sa fie cheie: sub atitea caractere SAU pur numeric.
  --     Codurile scurte/numerice se ciocnesc intre furnizori ("248", "670", "2917"
  --     inseamna produse diferite la fiecare) — vezi incidentul officeshop / load 285.
  -- EN: article too WEAK to be a key: shorter than this OR purely numeric. Short and
  --     numeric codes collide across suppliers — see the officeshop incident (load 285).
  g_min_articol_len PLS_INTEGER := 6;
  g_sample_rows   PLS_INTEGER  := 80;       -- RO: randuri pt. analiza continut / EN: rows for content analysis
  g_min_anchor    PLS_INTEGER  := 3;        -- RO: minim potriviri produs pt. ancora / EN: min product hits for anchor
  g_default_grupa VARCHAR2(60) := 'IMPORT PT';
  g_codprice      NUMBER       := 1;
  g_impkg         VARCHAR2(30) := 'YBIRO_IMPORT_MARFA'; -- RO: pachet de import reutilizat / EN: reused import pkg
  -- RO: functii "produse noi": marcaj MATGR1, grupa in arbore, generare cod de bare EAN-13
  -- EN: "new products" features: MATGR1 marker, tree group, EAN-13 barcode generation
  g_new_matgr     NUMBER       := 1;            -- RO: TMS_MPT.MATGR1=1 => produs NOU / EN: MATGR1=1 => NEW product
  g_new_group     VARCHAR2(60) := 'PRODUSE NOI';-- RO: nod nou in arbore / EN: new tree node
  g_ean_prefix    VARCHAR2(4)  := '20';         -- RO: prefix EAN intern (uz in-store) / EN: internal EAN prefix
  -- RO: PAZA anti-dubluri (incidentul GOG, load 164): un fisier FARA coloana de cod
  --     de bare, potrivit doar dupa ARTICOL, a creat ~37,7k carduri-dublura.
  --     Daca fisierul n-are BARCODE si ar crea mai mult de g_max_new_nobc pozitii
  --     NOI, importul se OPRESTE (se poate forta explicit cu p_force => TRUE).
  -- EN: anti-duplicate GUARD (GOG incident, load 164): a file WITHOUT a barcode
  --     column, matched by ARTICLE only, created ~37.7k duplicate cards. If a file
  --     has no BARCODE and would create more than g_max_new_nobc NEW positions the
  --     import STOPS (override explicitly with p_force => TRUE).
  g_max_new_nobc  PLS_INTEGER  := 200;         -- RO: prag pozitii NOI fara barcode / EN: NEW-rows threshold w/o barcode

  -- RO: load_id-ul incarcarii curente — folosit de view-ul BIRO26PT_STG_CUR ca sa
  --     limiteze importul DOAR la fisierul curent (altfel YBIRO_Import_Marfa ar lua
  --     TOATE randurile din stagin, inclusiv ale altor incarcari!).
  -- EN: current load id — used by the BIRO26PT_STG_CUR view to scope the import to
  --     the CURRENT file only (otherwise YBIRO_Import_Marfa would take ALL staging rows).
  FUNCTION  cur_load RETURN NUMBER;

  -- RO: detecteaza coloanele pentru un fisier (load_id) / EN: detect columns for a file (load_id)
  PROCEDURE detect_columns(p_load_id IN NUMBER, p_verbose IN BOOLEAN DEFAULT TRUE);

  -- RO: coloana fizica (cNN) pentru un camp logic / EN: physical column (cNN) for a logical field
  FUNCTION  col_of(p_load_id IN NUMBER, p_field IN VARCHAR2) RETURN VARCHAR2;

  -- RO: proiecteaza RAW -> BIRO26PT_STG dupa maparea detectata / EN: project RAW -> STG per mapping
  -- RO: p_sheet_group => numele FOII Excel devine GRUPA (foile = grupe de marfa).
  --     Coloana GRUPA din fisier, daca exista, are prioritate.
  -- EN: p_sheet_group => the Excel SHEET name becomes the GROUP; a GRUPA column
  --     in the file still wins.
  PROCEDURE build_stg(p_load_id IN NUMBER, p_grupa IN VARCHAR2 DEFAULT NULL,
                      p_sheet_group IN BOOLEAN DEFAULT FALSE);

  -- RO: clasifica randurile (NOU/EXISTENT/AMBIGUU) + raport / EN: classify rows + report
  PROCEDURE classify(p_load_id IN NUMBER);

  -- RO: PREFIXAREA articolelor slabe. Un cod scurt sau pur numeric ("248") inseamna
  --     produse diferite la fiecare furnizor. Il facem unic adaugind un prefix, ales
  --     in ordinea: BRAND-ul randului -> ART_PREFIX-ul sursei (TMS_ORG_IMPSRC).
  --     Rezultat: "248" -> "ARK-248", iar daca randul n-are brand -> "OS-248".
  -- EN: PREFIX weak articles. A short or purely numeric code means a different product
  --     at each supplier; a prefix makes it unique. Prefix priority: the row's BRAND,
  --     then the source's ART_PREFIX (TMS_ORG_IMPSRC).
  PROCEDURE apply_article_prefix(p_load_id IN NUMBER, p_src IN VARCHAR2 DEFAULT NULL);

  -- RO: proceseaza un fisier (dry-run implicit) / EN: process one file (dry-run by default)
  --   p_mark_all_new: TRUE => toate randurile fisierului -> MATGR1=1 (produse noi);
  --                   FALSE => doar pozitiile NOI. / EN: TRUE => all rows flagged NEW; FALSE => only new positions.
  --   p_date: data intrarii in vigoare a pretului nou; NULL => data incarcarii (azi).
  --           EN: new-price effective date; NULL => load date (today).
  PROCEDURE import_file(p_load_id     IN NUMBER,
                        p_grupa       IN VARCHAR2 DEFAULT NULL,
                        p_codprice    IN NUMBER   DEFAULT NULL,
                        p_commit      IN BOOLEAN  DEFAULT FALSE,
                        p_mark_all_new IN BOOLEAN DEFAULT TRUE,
                        p_date        IN DATE     DEFAULT NULL,
                        p_force       IN BOOLEAN  DEFAULT FALSE,
                        p_src         IN VARCHAR2 DEFAULT NULL,
                        p_algo        IN VARCHAR2 DEFAULT NULL);

  -- RO: proceseaza toate fisierele neimportate / EN: process all not-yet-imported files
  PROCEDURE import_folder(p_grupa       IN VARCHAR2 DEFAULT NULL,
                          p_codprice    IN NUMBER   DEFAULT NULL,
                          p_commit      IN BOOLEAN  DEFAULT FALSE,
                          p_mark_all_new IN BOOLEAN DEFAULT TRUE,
                          p_date        IN DATE     DEFAULT NULL,
                          p_force       IN BOOLEAN  DEFAULT FALSE,
                          p_src         IN VARCHAR2 DEFAULT NULL,
                          p_algo        IN VARCHAR2 DEFAULT NULL);

  -- RO: importa IMAGINILE SUPLIMENTARE (galeria) dintr-o foaie de tip "Images":
  --     coloanele articul + image_index + image_url -> TMS_MPT_WEBIMG.
  --     Marfa se identifica dupa ARTICOL (nu creeaza marfa noua niciodata).
  --     Imaginea principala (index 1) se sare — ea sta in TMS_MPT_TVR.IE_LINKADRES.
  -- EN: imports ADDITIONAL (gallery) images from an "Images"-style sheet:
  --     articul + image_index + image_url -> TMS_MPT_WEBIMG. Goods are matched by
  --     ARTICLE only (never creates goods). Index 1 (main image) is skipped — it
  --     lives in TMS_MPT_TVR.IE_LINKADRES.
  PROCEDURE import_images(p_load_id IN NUMBER,
                          p_src     IN VARCHAR2 DEFAULT NULL,
                          p_commit  IN BOOLEAN  DEFAULT FALSE);

  -- RO: descrierea algoritmului in Markdown (RO+EN) / EN: algorithm description in Markdown (RO+EN)
  FUNCTION  algo_md RETURN CLOB;
END BIRO26PT_importData;
/

CREATE OR REPLACE PACKAGE BODY BIRO26PT_importData IS

  -- RO: incarcarea curenta (vezi cur_load) / EN: current load (see cur_load)
  g_cur_load NUMBER := -1;

  FUNCTION cur_load RETURN NUMBER IS
  BEGIN RETURN g_cur_load; END;

  PROCEDURE say(p IN VARCHAR2) IS
  BEGIN DBMS_OUTPUT.PUT_LINE(p); END;

  PROCEDURE logrow(p_load_id NUMBER, p_file VARCHAR2, p_phase VARCHAR2,
                   p_col NUMBER, p_field VARCHAR2, p_strat VARCHAR2,
                   p_conf NUMBER, p_note VARCHAR2) IS
    PRAGMA AUTONOMOUS_TRANSACTION;
  BEGIN
    INSERT INTO biro26pt_log(log_id, load_id, src_file, phase, col_idx, logical_field, strategy, confidence, note)
    VALUES (biro26pt_log_seq.NEXTVAL, p_load_id, p_file, p_phase, p_col, p_field, p_strat, p_conf, SUBSTR(p_note,1,1000));
    COMMIT;
  END;

  FUNCTION col_of(p_load_id IN NUMBER, p_field IN VARCHAR2) RETURN VARCHAR2 IS
    v NUMBER;
  BEGIN
    SELECT MIN(col_idx) INTO v FROM biro26pt_map
     WHERE load_id = p_load_id AND logical_field = p_field;
    IF v IS NULL THEN RETURN NULL; END IF;
    RETURN 'c' || v;
  END;

  -- RO: expresie SQL numerica sigura pentru o coloana text / EN: safe numeric SQL expr for a text column
  FUNCTION num_expr(p_col VARCHAR2) RETURN VARCHAR2 IS
  BEGIN
    RETURN 'CASE WHEN REGEXP_LIKE(' || p_col || ', ''^[0-9]+([.,][0-9]+)?$'')' ||
           ' THEN TO_NUMBER(REPLACE(' || p_col || ', '','', ''.'')) END';
  END;

  PROCEDURE detect_columns(p_load_id IN NUMBER, p_verbose IN BOOLEAN DEFAULT TRUE) IS
    v_file  biro26pt_file.src_file%TYPE;
    v_ncols NUMBER;
    v_missing NUMBER;
  BEGIN
    SELECT src_file, n_cols INTO v_file, v_ncols FROM biro26pt_file WHERE load_id = p_load_id;
    -- RO: maparea MANUALA a operatorului se PASTREAZA — detectarea automata nu o
    --     poate sterge. Altfel, orice reanaliza ar arunca ce a corectat omul, iar
    --     fisierele cu antet stricat (PRINTERRA: 4 foi din 6) n-ar putea fi importate.
    -- EN: the operator's MANUAL mapping is KEPT — auto-detection must not wipe it,
    --     otherwise every re-analysis would discard the human's fix.
    DELETE FROM biro26pt_map WHERE load_id = p_load_id AND NVL(strategy,'?') <> 'MANUAL';
    COMMIT;

    -- ============ STRATEGIA 1: dupa numele coloanei / STRATEGY 1: by header name ============
    INSERT INTO biro26pt_map (load_id, logical_field, col_idx, strategy, confidence)
    WITH cand AS (
      SELECT h.col_idx, m.logical_field, m.prio
      FROM biro26pt_header h
      JOIN biro26pt_colmap m ON LOWER(h.header_text) LIKE m.pattern
      WHERE h.load_id = p_load_id AND h.header_text IS NOT NULL
    ),
    col_best AS ( -- RO: fiecare coloana isi alege un singur camp / EN: each column picks one field
      SELECT col_idx, logical_field, prio FROM (
        SELECT col_idx, logical_field, prio,
               ROW_NUMBER() OVER (PARTITION BY col_idx ORDER BY prio, LENGTH(logical_field)) rn
        FROM cand
      ) WHERE rn = 1
    ),
    field_best AS ( -- RO: fiecare camp isi alege o singura coloana / EN: each field picks one column
      SELECT col_idx, logical_field, prio FROM (
        SELECT col_idx, logical_field, prio,
               ROW_NUMBER() OVER (PARTITION BY logical_field ORDER BY prio, col_idx) rn
        FROM col_best
      ) WHERE rn = 1
    )
    SELECT p_load_id, logical_field, col_idx, 'HEADER', 1
    FROM field_best fb
    WHERE NOT EXISTS (SELECT 1 FROM biro26pt_map m
                       WHERE m.load_id = p_load_id AND m.strategy = 'MANUAL'
                         AND (m.logical_field = fb.logical_field OR m.col_idx = fb.col_idx))
      AND logical_field IN ('ARTICOL','DENUMIRE','BARCODE','ANGRO','ONLINE','RETAIL','VAT','URL',
                            'GRUPA','CATEG','FURNIZOR','DESCRIERE','DENUM_FULL');
    COMMIT;

    -- RO: URL imagine dupa continut (daca antetul nu l-a gasit): coloana
    --     nemapata unde majoritatea valorilor incep cu http(s)://
    -- EN: image URL by content (if the header missed it): unmapped column
    --     where most values start with http(s)://
    IF col_of(p_load_id,'URL') IS NULL THEN
      DECLARE
        v_tot NUMBER; v_hit NUMBER; v_taken NUMBER;
        v_best_col NUMBER := NULL; v_best NUMBER := -1;
      BEGIN
        FOR i IN 0 .. v_ncols - 1 LOOP
          SELECT COUNT(*) INTO v_taken FROM biro26pt_map WHERE load_id = p_load_id AND col_idx = i;
          IF v_taken > 0 THEN CONTINUE; END IF;
          EXECUTE IMMEDIATE
            'SELECT COUNT(c' || i || '),' ||
            ' SUM(CASE WHEN REGEXP_LIKE(c' || i || ', ''^https?://'') THEN 1 ELSE 0 END)' ||
            ' FROM biro26pt_raw WHERE load_id=:l AND row_no<=:s AND c' || i || ' IS NOT NULL'
            INTO v_tot, v_hit USING p_load_id, g_sample_rows;
          IF NVL(v_tot,0) > 0 AND v_hit >= v_tot*0.7 AND v_hit > v_best THEN
            v_best := v_hit; v_best_col := i;
          END IF;
        END LOOP;
        IF v_best_col IS NOT NULL THEN
          INSERT INTO biro26pt_map VALUES(p_load_id,'URL', v_best_col,'CONTENT', v_best);
          COMMIT;
        END IF;
      END;
    END IF;

    -- RO: cate campuri de baza raman nedetectate? / EN: how many core fields still unresolved?
    SELECT 2 - (SELECT COUNT(DISTINCT logical_field) FROM biro26pt_map
                 WHERE load_id = p_load_id AND logical_field IN ('ARTICOL','DENUMIRE'))
      INTO v_missing FROM dual;

    -- ============ STRATEGIA 3: dupa continut / STRATEGY 3: by content (fallback) ============
    -- RO: ruleaza doar daca ARTICOL sau DENUMIRE lipsesc / EN: run only if ARTICOL or DENUMIRE missing
    IF v_missing > 0 THEN
      DECLARE
        v_col   VARCHAR2(8);
        v_tot   NUMBER; v_art NUMBER; v_name NUMBER; v_bc NUMBER; v_num NUMBER; v_med NUMBER; v_len NUMBER;
        v_best_art_col NUMBER := NULL; v_best_art NUMBER := -1;
        v_best_name_col NUMBER := NULL; v_best_name NUMBER := -1;
        v_best_bc_col NUMBER := NULL;  v_best_bc NUMBER := -1;
        TYPE t_num IS TABLE OF NUMBER INDEX BY PLS_INTEGER;
        v_price_med t_num; v_price_free t_num; v_pf PLS_INTEGER := 0;
      BEGIN
        FOR i IN 0 .. v_ncols - 1 LOOP
          -- RO: sari coloanele deja atribuite prin antet / EN: skip columns already taken by header
          DECLARE v_taken NUMBER;
          BEGIN
            SELECT COUNT(*) INTO v_taken FROM biro26pt_map WHERE load_id = p_load_id AND col_idx = i;
            IF v_taken > 0 THEN CONTINUE; END IF;
          END;
          v_col := 'c' || i;
          EXECUTE IMMEDIATE
            'SELECT COUNT(' || v_col || '),' ||
            ' SUM(CASE WHEN EXISTS(SELECT 1 FROM tms_univers u WHERE u.tip=''P'' AND u.codvechi=SUBSTR(r.' || v_col || ',1,' || g_len_codvechi || ')) THEN 1 ELSE 0 END),' ||
            ' SUM(CASE WHEN EXISTS(SELECT 1 FROM tms_univers u WHERE u.tip=''P'' AND UPPER(TRIM(u.denumirea))=UPPER(TRIM(SUBSTR(r.' || v_col || ',1,' || g_len_denumire || '))) ) THEN 1 ELSE 0 END),' ||
            ' SUM(CASE WHEN REGEXP_LIKE(r.' || v_col || ',''^[0-9]{8,14}$'') THEN 1 ELSE 0 END),' ||
            ' SUM(CASE WHEN REGEXP_LIKE(r.' || v_col || ',''^[0-9]+([.,][0-9]+)?$'') THEN 1 ELSE 0 END),' ||
            ' MEDIAN(' || num_expr('r.' || v_col) || '),' ||
            ' MEDIAN(LENGTH(r.' || v_col || '))' ||
            ' FROM biro26pt_raw r WHERE r.load_id=:l AND r.row_no<=:s AND r.' || v_col || ' IS NOT NULL'
            INTO v_tot, v_art, v_name, v_bc, v_num, v_med, v_len
            USING p_load_id, g_sample_rows;
          IF NVL(v_tot,0) = 0 THEN CONTINUE; END IF;
          -- RO: ancore produs / EN: product anchors
          IF v_art > v_best_art AND v_art >= g_min_anchor THEN v_best_art := v_art; v_best_art_col := i; END IF;
          IF v_name > v_best_name AND v_name >= 1 THEN v_best_name := v_name; v_best_name_col := i; END IF;
          IF v_bc > v_best_bc AND v_bc >= v_tot*0.5 THEN v_best_bc := v_bc; v_best_bc_col := i; END IF;
          -- RO: coloane numerice libere = candidati pret / EN: free numeric columns = price candidates
          IF v_num >= v_tot*0.7 AND v_art < v_tot*0.5 AND v_bc < v_tot*0.5 THEN
            v_pf := v_pf + 1; v_price_free(v_pf) := i; v_price_med(v_pf) := NVL(v_med,0);
          END IF;
        END LOOP;

        -- RO: atribuie ancore (daca lipsesc din antet) / EN: assign anchors (if header missed them)
        IF col_of(p_load_id,'ARTICOL')  IS NULL AND v_best_art_col  IS NOT NULL THEN
          INSERT INTO biro26pt_map VALUES(p_load_id,'ARTICOL', v_best_art_col,'CONTENT', v_best_art); END IF;
        IF col_of(p_load_id,'DENUMIRE') IS NULL AND v_best_name_col IS NOT NULL THEN
          INSERT INTO biro26pt_map VALUES(p_load_id,'DENUMIRE',v_best_name_col,'CONTENT', v_best_name); END IF;
        IF col_of(p_load_id,'BARCODE')  IS NULL AND v_best_bc_col   IS NOT NULL THEN
          INSERT INTO biro26pt_map VALUES(p_load_id,'BARCODE', v_best_bc_col,'CONTENT', v_best_bc); END IF;
        -- RO: preturi dupa mediana crescator: angro < online <= retail / EN: prices by ascending median
        DECLARE
          TYPE t_ord IS TABLE OF PLS_INTEGER INDEX BY PLS_INTEGER;
          v_order t_ord; v_tmp PLS_INTEGER; v_flds SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST('ANGRO','ONLINE','RETAIL');
          v_k PLS_INTEGER := 0;
        BEGIN
          -- RO: sortare simpla dupa mediana / EN: simple sort by median
          FOR a IN 1 .. v_pf LOOP v_order(a) := a; END LOOP;
          FOR a IN 1 .. v_pf-1 LOOP
            FOR b IN a+1 .. v_pf LOOP
              IF v_price_med(v_order(b)) < v_price_med(v_order(a)) THEN
                v_tmp := v_order(a); v_order(a) := v_order(b); v_order(b) := v_tmp;
              END IF;
            END LOOP;
          END LOOP;
          FOR a IN 1 .. LEAST(v_pf,3) LOOP
            IF col_of(p_load_id, v_flds(a)) IS NULL THEN
              INSERT INTO biro26pt_map VALUES(p_load_id, v_flds(a), v_price_free(v_order(a)), 'CONTENT', v_price_med(v_order(a)));
            END IF;
          END LOOP;
        END;
        COMMIT;
      END;
    END IF;

    -- ============ STRATEGIA 2: dupa layout cunoscut / STRATEGY 2: by known layout ============
    -- RO: doar daca ARTICOL si DENUMIRE tot lipsesc / EN: only if ARTICOL and DENUMIRE still missing
    IF col_of(p_load_id,'ARTICOL') IS NULL AND col_of(p_load_id,'DENUMIRE') IS NULL THEN
      DECLARE v_sig VARCHAR2(40);
      BEGIN
        SELECT MAX(sig_name) INTO v_sig FROM biro26pt_layout l
         WHERE (SELECT MAX(col_idx) FROM biro26pt_layout l2 WHERE l2.sig_name=l.sig_name) < v_ncols;
        IF v_sig IS NOT NULL THEN
          INSERT INTO biro26pt_map (load_id, logical_field, col_idx, strategy, confidence)
          SELECT p_load_id, logical_field, col_idx, 'LAYOUT', 1 FROM biro26pt_layout WHERE sig_name = v_sig;
          COMMIT;
        END IF;
      END;
    END IF;

    -- ============ raport / report ============
    FOR r IN (SELECT logical_field, col_idx, strategy, confidence FROM biro26pt_map
               WHERE load_id = p_load_id ORDER BY col_idx) LOOP
      logrow(p_load_id, v_file, 'DETECT', r.col_idx, r.logical_field, r.strategy, r.confidence, NULL);
    END LOOP;
    IF p_verbose THEN
      say('=== RO: Detectie coloane / EN: column detection: ' || v_file || ' (cols=' || v_ncols || ') ===');
      FOR r IN (SELECT m.logical_field, m.col_idx, m.strategy,
                       (SELECT h.header_text FROM biro26pt_header h
                         WHERE h.load_id=p_load_id AND h.col_idx=m.col_idx) hdr
                FROM biro26pt_map m WHERE m.load_id=p_load_id ORDER BY m.col_idx) LOOP
        say('  c' || r.col_idx || ' -> ' || RPAD(r.logical_field,9) || ' [' || r.strategy || ']  "' || SUBSTR(r.hdr,1,40) || '"');
      END LOOP;
      IF col_of(p_load_id,'ARTICOL') IS NULL AND col_of(p_load_id,'DENUMIRE') IS NULL THEN
        say('  RO: ATENTIE - nici articol nici denumire detectate (fisier nerecunoscut)' ||
            ' / EN: WARNING - neither article nor name detected (unrecognized file)');
      END IF;
    END IF;
  END detect_columns;

  PROCEDURE build_stg(p_load_id IN NUMBER, p_grupa IN VARCHAR2 DEFAULT NULL,
                      p_sheet_group IN BOOLEAN DEFAULT FALSE) IS
    v_art VARCHAR2(8); v_den VARCHAR2(8); v_bc VARCHAR2(8);
    v_ang VARCHAR2(8); v_onl VARCHAR2(8); v_ret VARCHAR2(8); v_vat VARCHAR2(8); v_grp VARCHAR2(8);
    v_url VARCHAR2(8); v_cat VARCHAR2(8); v_fz VARCHAR2(8);
    v_desc VARCHAR2(8); v_dfull VARCHAR2(8);
    -- RO: GRUPA (grupa de marfa, plina) pt. arbore/BIRO26_GOODS; grupa_pret trunchiata la 25
    --     (nume grup de pret TPR01M_GROUPS.GRPNAME, max 25).
    -- EN: GRUPA (full goods group) for tree/BIRO26_GOODS; grupa_pret truncated to 25 (price-group name).
    v_grupa VARCHAR2(60) := SUBSTR(NVL(p_grupa, g_default_grupa), 1, 60);
    v_grupp VARCHAR2(25) := SUBSTR(NVL(p_grupa, g_default_grupa), 1, 25);
    v_sql   VARCHAR2(4000);
    -- RO: rezerva pentru GRUPA: numele foii (foile = grupe) sau grupa implicita.
    -- EN: GRUPA fallback: the sheet name (sheets = groups) or the default group.
    v_gfb   VARCHAR2(60) := CASE WHEN p_sheet_group THEN 'SUBSTR(r.sheet,1,60)' ELSE ':grp'  END;
    v_gfbp  VARCHAR2(60) := CASE WHEN p_sheet_group THEN 'SUBSTR(r.sheet,1,25)' ELSE ':grpp' END;
    FUNCTION e(p_col VARCHAR2, p_num BOOLEAN DEFAULT FALSE) RETURN VARCHAR2 IS
    BEGIN
      IF p_col IS NULL THEN RETURN 'NULL'; END IF;
      IF p_num THEN RETURN num_expr('r.' || p_col); END IF;
      RETURN 'r.' || p_col;
    END;
  BEGIN
    v_art := col_of(p_load_id,'ARTICOL'); v_den := col_of(p_load_id,'DENUMIRE'); v_bc := col_of(p_load_id,'BARCODE');
    v_ang := col_of(p_load_id,'ANGRO');   v_onl := col_of(p_load_id,'ONLINE');   v_ret := col_of(p_load_id,'RETAIL');
    v_vat := col_of(p_load_id,'VAT');     v_grp := col_of(p_load_id,'GRUPA');
    v_url := col_of(p_load_id,'URL');     v_cat := col_of(p_load_id,'CATEG');     v_fz := col_of(p_load_id,'FURNIZOR');
    v_desc := col_of(p_load_id,'DESCRIERE'); v_dfull := col_of(p_load_id,'DENUM_FULL');
    DELETE FROM biro26pt_stg WHERE load_id = p_load_id;
    v_sql :=
      'INSERT INTO biro26pt_stg (id, load_id, src_file, row_no, cod_univers, articol, denumire, grupa, grupa_pret, categ, furnizor, angro, ionline, retail1, barcode, vat, img_url, descriere, denumire_full, cod_univ_producer, status)' ||
      ' SELECT r.row_no, r.load_id, r.src_file, r.row_no, NULL,' ||
      -- RO: CURATA prefixele din articol ("SKU: X", "Articol: X", "Cod: X").
      --     Fisierele furnizorilor le pun uneori in celula; daca ajung in CODVECHI,
      --     potrivirea nu gaseste produsul existent si se creeaza DUBLURI
      --     (5 113 carduri arhivate din acest motiv - vezi YBIRO_PREFIX_DEDUP).
      -- EN: STRIP article prefixes; if they reach CODVECHI the match fails and
      --     duplicates are created (5,113 cards had to be archived).
      '  SUBSTR(TRIM(REGEXP_REPLACE(' || e(v_art) ||
      '    , ''^(SKU|Articol|Article|Cod|Code|Art)[[:space:]]*:[[:space:]]*'', '''', 1, 1, ''i'')),1,60),' ||
      '  SUBSTR(' || e(v_den) || ',1,400),' ||
      '  NVL(SUBSTR(' || e(v_grp) || ',1,60), ' || v_gfb  || '),' ||   -- grupa plina / full grupa
      '  NVL(SUBSTR(' || e(v_grp) || ',1,25), ' || v_gfbp || '),' ||   -- grupa_pret <=25
      '  SUBSTR(' || e(v_cat) || ',1,260),' ||                   -- categorie
      '  SUBSTR(' || e(v_fz)  || ',1,260),' ||                   -- furnizor/producator
      '  ' || e(v_ang, TRUE) || ', ' || e(v_onl, TRUE) || ',' ||
      -- RO: pretul de raft ramine TEXT (parse_price il converteste mai tirziu), dar
      --     normalizam separatorul: "69,66" -> "69.66". parse_price NU intelege virgula
      --     si intoarce NULL => preturile nu s-ar actualiza deloc (set 10: 6 600 randuri).
      --     Daca valoarea are DEJA punct, o lasam asa (poate fi separator de mii).
      -- EN: keep retail as TEXT but normalize the decimal separator: parse_price does not
      --     understand a comma and returns NULL, so prices would silently not update.
      '  SUBSTR(CASE WHEN INSTR(' || e(v_ret) || ', ''.'') = 0' ||
      '              THEN REPLACE(' || e(v_ret) || ', '','', ''.'')' ||
      '              ELSE ' || e(v_ret) || ' END, 1, 60),' ||
      '  SUBSTR(' || e(v_bc)  || ',1,30),' ||
      '  SUBSTR(' || e(v_vat) || ',1,20),' ||
      '  SUBSTR(' || e(v_url) || ',1,1000),' ||
      '  SUBSTR(' || e(v_desc)  || ',1,2000),' ||          -- descriere / caracteristici
      '  SUBSTR(' || e(v_dfull) || ',1,1000), NULL, NULL' ||
      ' FROM biro26pt_raw r WHERE r.load_id = :l' ||
      '   AND (' || e(v_art) || ' IS NOT NULL OR ' || e(v_den) || ' IS NOT NULL)';
    -- RO: cind foaia da grupa, :grp/:grpp nu mai apar in SQL — se leaga doar load_id.
    -- EN: with sheet-as-group the :grp/:grpp binds are gone; only load_id remains.
    IF p_sheet_group THEN
      EXECUTE IMMEDIATE v_sql USING p_load_id;
    ELSE
      EXECUTE IMMEDIATE v_sql USING v_grupa, v_grupp, p_load_id;
    END IF;
    COMMIT;
  END build_stg;

  PROCEDURE classify(p_load_id IN NUMBER) IS
    v_new NUMBER; v_exist NUMBER; v_amb NUMBER; v_noart NUMBER; v_pchg NUMBER; v_bc NUMBER;
  BEGIN
    -- RO: PRIORITATE 1 — potrivirea dupa BARCODE (cod de bare REAL din
    --     fisier, un singur card ACTIV in baza). Fara aceasta prioritate,
    --     un fisier fara barcode a creat ~39.7k dubluri GOG* (load 164):
    --     articolul nou nu se gasea si totul devenea NEW; incarcarile
    --     urmatoare CU barcode se lipeau tot de dublura (articolul
    --     cistiga). EN: PRIORITY 1 — match by real file BARCODE first
    --     (single ACTIVE card); prevents duplicate cards when the article
    --     is new but the product already exists under another article.
    UPDATE biro26pt_stg s
       SET s.status = 'EXISTING',
           s.cod_univers = (SELECT MIN(b.cod)
                              FROM tms_mpt_barcode b
                              JOIN tms_univers u ON u.cod = b.cod AND u.tip = g_tip
                             WHERE b.barcode = s.barcode
                               AND NVL(u.isarhiv,'0') <> '2')
     WHERE s.load_id = p_load_id
       AND s.barcode IS NOT NULL
       AND (SELECT COUNT(DISTINCT b.cod)
              FROM tms_mpt_barcode b
              JOIN tms_univers u ON u.cod = b.cod AND u.tip = g_tip
             WHERE b.barcode = s.barcode
               AND NVL(u.isarhiv,'0') <> '2') = 1;
    -- RO: PRIORITATE 2 — dupa ARTICOL (doar rindurile nepotrivite mai sus)
    -- EN: PRIORITY 2 — by article, only for rows not matched by barcode
    UPDATE biro26pt_stg s SET s.status =
      CASE
        WHEN s.articol IS NULL THEN 'NOARTICOL'
        WHEN (SELECT COUNT(*) FROM tms_univers u WHERE u.tip=g_tip AND u.codvechi=SUBSTR(s.articol,1,g_len_codvechi) AND NVL(u.isarhiv,'0')<>'2') = 0 THEN 'NEW'
        WHEN (SELECT COUNT(*) FROM tms_univers u WHERE u.tip=g_tip AND u.codvechi=SUBSTR(s.articol,1,g_len_codvechi) AND NVL(u.isarhiv,'0')<>'2') = 1 THEN 'EXISTING'
        ELSE 'AMBIGUOUS'
      END
    WHERE s.load_id = p_load_id AND s.cod_univers IS NULL;
    -- RO: PRIORITATE 3 — ARTICOL NORMALIZAT (fara spatii/puncte). Furnizorii schimba
    --     uneori formatul: in fisier "T4gr120 12476", in catalog "T4gr12012476".
    --     Fara acest pas s-ar crea dubluri (251 la setul CRAFTI). Se aplica DOAR cind
    --     potrivirea normalizata e UNICA si cardul e activ.
    -- EN: PRIORITY 3 — NORMALIZED article (spaces/dots removed). Suppliers sometimes
    --     change formatting ("T4gr120 12476" vs "T4gr12012476"); without this we would
    --     create duplicates. Applied only when the normalized match is UNIQUE and active.
    UPDATE biro26pt_stg s
       SET s.status = 'EXISTING',
           s.cod_univers = (SELECT MIN(u.cod) FROM tms_univers u
                             WHERE u.tip = g_tip AND NVL(u.isarhiv,'0') <> '2'
                               AND TRANSLATE(UPPER(u.codvechi), ' .-', '   ') IS NOT NULL
                               AND REPLACE(REPLACE(UPPER(u.codvechi),' ',''),'.','')
                                 = REPLACE(REPLACE(UPPER(SUBSTR(s.articol,1,g_len_codvechi)),' ',''),'.',''))
     WHERE s.load_id = p_load_id AND s.status = 'NEW' AND s.articol IS NOT NULL
       AND (SELECT COUNT(*) FROM tms_univers u
             WHERE u.tip = g_tip AND NVL(u.isarhiv,'0') <> '2'
               AND REPLACE(REPLACE(UPPER(u.codvechi),' ',''),'.','')
                 = REPLACE(REPLACE(UPPER(SUBSTR(s.articol,1,g_len_codvechi)),' ',''),'.','')) = 1;

    -- RO: PAZA 5 — ARTICOL PREA SLAB ca sa fie cheie. Un cod scurt sau pur numeric
    --     ("248", "670", "1841", "2917") inseamna produse DIFERITE la fiecare furnizor:
    --     la load 285 (officeshop) 629 de randuri s-au potrivit astfel cu marfuri
    --     complet nelegate ("Joc de masa Octopus Party" -> "Carnet A6 40 foi").
    --     Astfel de randuri nu se potrivesc SI nu se creeaza — se sar.
    -- EN: GUARD 5 — ARTICLE TOO WEAK to be a key. A short or purely numeric code means
    --     a DIFFERENT product at each supplier; on load 285 (officeshop) 629 rows matched
    --     completely unrelated goods this way. Such rows are neither matched nor created.
    UPDATE biro26pt_stg s
       SET s.status = 'AMBIGUOUS', s.cod_univers = NULL
     WHERE s.load_id = p_load_id
       AND s.status IN ('NEW', 'EXISTING')
       AND s.articol IS NOT NULL
       AND (   LENGTH(TRIM(s.articol)) < g_min_articol_len
            OR REGEXP_LIKE(TRIM(s.articol), '^[0-9]+$') );
    COMMIT;

    -- RO: PAZA 4 — pozitie "noua" al carei NUME exista deja pe o cartela ACTIVA.
    --     Furnizorul schimba uneori articolul ("DLEH379" in loc de "DLEH378",
    --     "DLE38144-BL" in loc de "DLE5001-03"); daca am crea-o, ar aparea o dublura
    --     perfecta pe nume. Nu putem decide automat care cartela e cea buna, deci o
    --     marcam AMBIGUA (se sare) si ramine pentru revizie manuala.
    -- EN: GUARD 4 — a "new" row whose NAME already exists on an ACTIVE card. Suppliers
    --     sometimes change the article code; creating the row would make a perfect
    --     name duplicate. We cannot pick the right card automatically, so the row is
    --     marked AMBIGUOUS (skipped) and left for manual review.
    UPDATE biro26pt_stg s
       SET s.status = 'AMBIGUOUS'
     WHERE s.load_id = p_load_id AND s.status = 'NEW' AND s.denumire IS NOT NULL
       AND EXISTS (SELECT 1 FROM tms_univers u
                    WHERE u.tip = g_tip AND NVL(u.isarhiv,'0') <> '2'
                      AND UPPER(TRIM(u.denumirea)) = UPPER(TRIM(s.denumire)));
    COMMIT;

    -- RO: leaga codul pentru cele existente / EN: bind cod for existing ones
    UPDATE biro26pt_stg s
       SET s.cod_univers = (SELECT MIN(u.cod) FROM tms_univers u WHERE u.tip=g_tip AND u.codvechi=SUBSTR(s.articol,1,g_len_codvechi) AND NVL(u.isarhiv,'0')<>'2')
     WHERE s.load_id = p_load_id AND s.status = 'EXISTING'
       AND s.cod_univers IS NULL;
    COMMIT;

    SELECT
      SUM(CASE WHEN status='NEW' THEN 1 ELSE 0 END),
      SUM(CASE WHEN status='EXISTING' THEN 1 ELSE 0 END),
      SUM(CASE WHEN status='AMBIGUOUS' THEN 1 ELSE 0 END),
      SUM(CASE WHEN status='NOARTICOL' THEN 1 ELSE 0 END),
      SUM(CASE WHEN barcode IS NOT NULL THEN 1 ELSE 0 END)
      INTO v_new, v_exist, v_amb, v_noart, v_bc
    FROM biro26pt_stg WHERE load_id = p_load_id;

    -- RO: preturi de raft schimbate fata de pretul curent / EN: retail prices changed vs current price
    SELECT COUNT(*) INTO v_pchg FROM biro26pt_stg s
     WHERE s.load_id=p_load_id AND s.status='EXISTING' AND s.retail1 IS NOT NULL
       AND EXISTS (
         SELECT 1 FROM vtpr1d_perprlist p
          WHERE p.sc = s.cod_univers AND p.codprice = g_codprice
            AND NVL(p.pretv,-1) <> NVL(YBIRO_Import_Marfa.parse_price(s.retail1),-2)
            AND p.datastart = (SELECT MAX(p2.datastart) FROM vtpr1d_perprlist p2 WHERE p2.sc=p.sc AND p2.codprice=g_codprice));

    say('=== RO: Clasificare / EN: classification (load_id=' || p_load_id || ') ===');
    say('  RO: pozitii NOI / EN: NEW positions          : ' || NVL(v_new,0));
    say('  RO: EXISTENTE (upd. pret) / EN: EXISTING      : ' || NVL(v_exist,0) || '  (RO: cu pret schimbat / EN: price changed: ' || NVL(v_pchg,0) || ')');
    say('  RO: AMBIGUE (sarite) / EN: AMBIGUOUS (skipped): ' || NVL(v_amb,0));
    say('  RO: fara articol / EN: NO ARTICLE             : ' || NVL(v_noart,0));
    say('  RO: randuri cu cod de bare / EN: rows w/barcode: ' || NVL(v_bc,0));
  END classify;

  -- RO: genereaza un cod EAN-13 valid din corpul secvential (prefix + secventa + cifra control)
  -- EN: build a valid EAN-13 from the sequential body (prefix + sequence + check digit)
  FUNCTION gen_ean13(p_seq IN NUMBER) RETURN VARCHAR2 IS
    v12 VARCHAR2(12); s PLS_INTEGER := 0; d PLS_INTEGER; chk PLS_INTEGER;
  BEGIN
    v12 := g_ean_prefix || LPAD(TO_CHAR(p_seq), 12 - LENGTH(g_ean_prefix), '0');
    FOR i IN 1 .. 12 LOOP
      d := TO_NUMBER(SUBSTR(v12, i, 1));
      IF MOD(i, 2) = 1 THEN s := s + d; ELSE s := s + d * 3; END IF;   -- RO: pozitii impare*1, pare*3
    END LOOP;
    chk := MOD(10 - MOD(s, 10), 10);
    RETURN v12 || TO_CHAR(chk);
  END gen_ean13;

  -- RO: asigura un nod REAL de arbore dupa nume (id0=1) si intoarce group1.
  --     "PRODUSE NOI" ramine un nod VIRTUAL = filtrul MATGR1, nu un nod fizic.
  -- EN: ensure a REAL tree node by name (id0=1) and return group1.
  --     "PRODUSE NOI" stays a VIRTUAL node = the MATGR1 filter, never physical.
  FUNCTION ensure_group(p_name IN VARCHAR2) RETURN NUMBER IS
    -- RO: cauta nodul dupa nume la ORICE nivel al arborelui; daca numele
    --     exista in mai multe locuri, alege nodul cel mai populat (apoi
    --     id1 minim). Daca nu exista deloc — creeaza nod de nivel 1.
    --     Intoarce ID1 al nodului.
    -- EN: find the node by name at ANY tree level; on multiple matches
    --     prefer the most populated node (then lowest id1). If the name
    --     does not exist at all, create a top-level node. Returns ID1.
    v_g1 NUMBER; v_id1 NUMBER;
  BEGIN
    BEGIN
      SELECT id1 INTO v_id1 FROM (
        SELECT h.id1,
               (SELECT COUNT(*) FROM tms_sysgrp g
                 WHERE g.id0 = 1 AND g.id1 = h.id1) cnt
        FROM tms_sysgrph h
        WHERE h.id0 = 1 AND UPPER(TRIM(h.coment)) = UPPER(TRIM(p_name))
        ORDER BY cnt DESC, h.id1)
      WHERE ROWNUM = 1;
      RETURN v_id1;
    EXCEPTION WHEN NO_DATA_FOUND THEN NULL; END;
    SELECT NVL(MAX(group1), 0) + 1, NVL(MAX(id1), 0) + 1 INTO v_g1, v_id1 FROM tms_sysgrph;
    INSERT INTO tms_sysgrph (group1, group2, group3, group4, group5, coment, id0, id1)
    VALUES (v_g1, 0, 0, 0, 0, TRIM(p_name), 1, v_id1);
    COMMIT;
    RETURN v_id1;
  END ensure_group;

  PROCEDURE do_writes(p_load_id IN NUMBER, p_codprice IN NUMBER,
                      p_mark_all_new IN BOOLEAN, p_ds IN DATE) IS
    v_ds   DATE := NVL(p_ds, TRUNC(SYSDATE));
    v_has_bc NUMBER; v_g1 NUMBER; v_nid1 NUMBER; v_ean NUMBER := 0; v_cnt NUMBER;
    v_bc   VARCHAR2(15);
  BEGIN
    -- RO: forteaza formatul de data al sesiunii. Triggerul de pret TRG_VTPR1D_PERPRLIST_M_ALL
    --     converteste implicit un literal text ('31.12.3000') dupa NLS_DATE_FORMAT; sesiunile
    --     cu format luna-nume (ex. aplicatia web) dau ORA-01843 "luna invalida".
    -- EN: force session date format. The price trigger implicitly converts a text literal
    --     ('31.12.3000') per NLS_DATE_FORMAT; month-name sessions (e.g. the web app) raise ORA-01843.
    EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''DD.MM.YYYY''';
    -- RO: aloca cod nou pozitiilor NOI / EN: assign new cod to NEW positions
    -- RO: NU dam cod randurilor fara denumire — import_univers le sare (DENUMIREA e
    --     obligatorie), iar apoi pasii urmatori ar referi un COD inexistent (ORA-02291).
    -- EN: do NOT assign a COD to rows without a name — import_univers skips them and the
    --     later steps would reference a non-existent COD (ORA-02291).
    UPDATE biro26pt_stg SET cod_univers = ID_TMS_UNIVERS.NEXTVAL
     WHERE load_id = p_load_id AND status = 'NEW' AND denumire IS NOT NULL;
    COMMIT;
    -- RO: pointeaza pachetul reutilizat catre STG / EN: point the reused package to STG
    -- RO: IMPORTANT — pachetul reutilizat citeste TOATA tabela indicata. Il legam la
    --     view-ul filtrat pe incarcarea curenta, altfel ar insera randuri din ALTE
    --     fisiere ramase in stagin (73k randuri straine la un moment dat!).
    -- EN: IMPORTANT — the reused package reads the WHOLE table it is pointed at. We bind
    --     it to the view scoped to the current load, otherwise rows from OTHER files
    --     still sitting in staging would be imported too.
    g_cur_load := p_load_id;
    YBIRO_Import_Marfa.g_tbl_goods  := 'BIRO26PT_STG_CUR';
    YBIRO_Import_Marfa.g_col_key    := 'COD_UNIVERS';
    YBIRO_Import_Marfa.g_col_articol:= 'ARTICOL';
    YBIRO_Import_Marfa.g_col_denumire := 'DENUMIRE';
    YBIRO_Import_Marfa.g_col_group  := 'GRUPA_PRET';   -- RO: grup de pret <=25 / EN: price group <=25
    YBIRO_Import_Marfa.g_col_angro  := 'ANGRO';
    YBIRO_Import_Marfa.g_col_ionline:= 'IONLINE';
    YBIRO_Import_Marfa.g_col_retail := 'RETAIL1';
    -- RO: pozitii noi + cartele / EN: new positions + cards
    YBIRO_Import_Marfa.import_univers;
    YBIRO_Import_Marfa.import_mpt;
    -- RO: grupe + date de pret (perioada noua = v_ds) / EN: price groups + dates (new period)
    YBIRO_Import_Marfa.import_groups(p_codprice);
    YBIRO_Import_Marfa.import_dates (p_codprice, v_ds);

    -- RO: PRETURI cu actualizare AUTOMATA: NOU = pret initial; EXISTENT = perioada noua
    --     ori de cite ori pretul de raft din fisier DIFERA de cel curent (mai mare SAU mai mic).
    --     Daca exista deja o perioada cu acelasi datastart, valorile ei se ACTUALIZEAZA.
    -- EN: PRICES auto-update: NEW = initial; EXISTING = a new period whenever the file
    --     retail DIFFERS from the current one (higher OR lower). If a period with the
    --     same datastart already exists, its values are UPDATED in place.
    INSERT INTO vtpr1d_perprlist (CODPRICE, CODGRP, SC, DATASTART, DATAEND, PRETV, PRETV1, PRETV2, PRETV3)
    SELECT p_codprice, d.codgrp, d.sc, v_ds, DATE '3000-01-01', d.pv, d.pv1, d.pv2, NULL
    FROM (
      SELECT vg.codgrp codgrp, s.cod_univers sc,
             YBIRO_Import_Marfa.parse_price(s.retail1) pv, s.angro pv1, s.ionline pv2,
             ROW_NUMBER() OVER (PARTITION BY s.cod_univers
                 ORDER BY YBIRO_Import_Marfa.parse_price(s.retail1) DESC NULLS LAST, s.id) rn
      FROM biro26pt_stg s
      -- RO: legatura se face pe GRUPA_PRET (trunchiata la 25), pentru ca exact asa a fost
      --     creat VPR01M_GROUPS.GRPNAME (max 25). Pe s.grupa (numele COMPLET, pina la 60)
      --     orice grupa cu nume peste 25 de caractere nu se potrivea si pretul se pierdea
      --     TACUT — vezi PRINTERRA: 2 387 din 5 147 de produse fara pret.
      -- EN: join on GRUPA_PRET (truncated to 25) — that is how GRPNAME was created.
      --     Joining on the FULL name silently dropped prices for any group over 25 chars.
      JOIN vpr01m_groups vg ON vg.codprice = p_codprice AND vg.grpname = s.grupa_pret
      WHERE s.load_id = p_load_id AND s.cod_univers IS NOT NULL AND s.status IN ('NEW','EXISTING')
        AND ( s.status = 'NEW'
              OR ( YBIRO_Import_Marfa.parse_price(s.retail1) IS NOT NULL
                   AND YBIRO_Import_Marfa.parse_price(s.retail1) <>
                       NVL( (SELECT MAX(p.pretv) KEEP (DENSE_RANK LAST ORDER BY p.datastart)
                               FROM tpr1d_perprlist p WHERE p.sc = s.cod_univers AND p.codprice = p_codprice), -1) ) )
    ) d
    WHERE d.rn = 1
      AND NOT EXISTS (SELECT 1 FROM tpr1d_perprlist p2
                       WHERE p2.codprice = p_codprice AND p2.sc = d.sc AND p2.datastart = v_ds);
    say('RO: preturi noi inserate (perioada noua) / EN: new prices inserted (new period): ' || SQL%ROWCOUNT);
    COMMIT;

    -- RO: perioada cu acelasi datastart exista deja (ex. reimport in aceeasi zi):
    --     actualizeaza valorile in loc (INSERT-ul de mai sus a sarit aceste rinduri).
    -- EN: a period with the same datastart already exists (e.g. same-day re-import):
    --     update its values in place (the INSERT above skipped these rows).
    MERGE INTO tpr1d_perprlist t
    USING (
      SELECT d.sc, d.pv, d.pv1, d.pv2 FROM (
        SELECT s.cod_univers sc,
               YBIRO_Import_Marfa.parse_price(s.retail1) pv, s.angro pv1, s.ionline pv2,
               ROW_NUMBER() OVER (PARTITION BY s.cod_univers
                   ORDER BY YBIRO_Import_Marfa.parse_price(s.retail1) DESC NULLS LAST, s.id) rn
        FROM biro26pt_stg s
        WHERE s.load_id = p_load_id AND s.cod_univers IS NOT NULL
          AND s.status IN ('NEW','EXISTING')
          AND YBIRO_Import_Marfa.parse_price(s.retail1) IS NOT NULL
      ) d WHERE d.rn = 1
    ) u
    ON (t.codprice = p_codprice AND t.sc = u.sc AND t.datastart = v_ds)
    WHEN MATCHED THEN UPDATE SET
      t.pretv  = u.pv,
      t.pretv1 = NVL(u.pv1, t.pretv1),
      t.pretv2 = NVL(u.pv2, t.pretv2)
    WHERE NVL(t.pretv,-1) <> NVL(u.pv,-1)
       OR NVL(t.pretv1,-1) <> NVL(NVL(u.pv1, t.pretv1),-1)
       OR NVL(t.pretv2,-1) <> NVL(NVL(u.pv2, t.pretv2),-1);
    say('RO: perioade existente actualizate (aceeasi zi) / EN: same-day periods updated: ' || SQL%ROWCOUNT);
    COMMIT;

    -- RO: inchide perioadele anterioare: DATAEND = start_nou - 1 (regula LEAD per codprice, sc)
    -- EN: close prior periods: DATAEND = new_start - 1 (LEAD rule per codprice, sc)
    MERGE INTO tpr1d_perprlist t
    USING (
      SELECT ROWID rid,
             NVL(LEAD(datastart) OVER (PARTITION BY codprice, sc ORDER BY datastart) - 1, DATE '3000-01-01') new_end
      FROM tpr1d_perprlist
      WHERE codprice = p_codprice
        AND sc IN (SELECT cod_univers FROM biro26pt_stg WHERE load_id = p_load_id AND cod_univers IS NOT NULL)
    ) u ON (t.ROWID = u.rid)
    WHEN MATCHED THEN UPDATE SET t.dataend = u.new_end WHERE t.dataend <> u.new_end;
    say('RO: perioade anterioare inchise / EN: prior periods closed: ' || SQL%ROWCOUNT);
    COMMIT;

    -- RO: MARCAJ "produse noi" = MATGR1 (in VMS_MPT). p_mark_all_new: toate randurile vs doar NOI.
    -- EN: "new products" flag = MATGR1. p_mark_all_new: all rows vs only new positions.
    IF p_mark_all_new THEN
      UPDATE tms_mpt SET matgr1 = g_new_matgr
       WHERE cod IN (SELECT cod_univers FROM biro26pt_stg
                      WHERE load_id = p_load_id AND cod_univers IS NOT NULL AND status IN ('NEW','EXISTING'))
         AND NVL(matgr1, -1) <> g_new_matgr;
    ELSE
      UPDATE tms_mpt SET matgr1 = g_new_matgr
       WHERE cod IN (SELECT cod_univers FROM biro26pt_stg WHERE load_id = p_load_id AND status = 'NEW')
         AND NVL(matgr1, -1) <> g_new_matgr;
    END IF;
    say('RO: produse marcate NOU (MATGR1=1) / EN: products flagged NEW: ' || SQL%ROWCOUNT);
    COMMIT;

    -- RO: plaseaza pozitiile NOI in nodurile lor REALE (dupa GRUPA din fisier);
    --     "PRODUSE NOI" e doar virtual (MATGR1=1), nu se creeaza nod fizic.
    -- EN: place NEW positions into their REAL tree nodes (by the file GRUPA);
    --     "PRODUSE NOI" is virtual only (MATGR1=1), no physical node is made.
    v_cnt := 0;
    FOR g IN (SELECT DISTINCT NVL(TRIM(s.grupa), 'IMPORT PT') grupa
                FROM biro26pt_stg s
               WHERE s.load_id = p_load_id AND s.status = 'NEW'
                 AND s.cod_univers IS NOT NULL) LOOP
      v_nid1 := ensure_group(g.grupa);
      INSERT INTO tms_sysgrp (group1, group2, group3, group4, group5, sc, id0, id1)
      SELECT h.group1, h.group2, h.group3, h.group4, h.group5, s.cod_univers, 1, h.id1
      FROM tms_sysgrph h, biro26pt_stg s
      WHERE h.id0 = 1 AND h.id1 = v_nid1
        AND s.load_id = p_load_id AND s.status = 'NEW' AND s.cod_univers IS NOT NULL
        AND NVL(TRIM(s.grupa), 'IMPORT PT') = g.grupa
        AND EXISTS (SELECT 1 FROM tms_univers u2 WHERE u2.cod = s.cod_univers)
        AND NOT EXISTS (SELECT 1 FROM tms_sysgrp x WHERE x.id0 = 1 AND x.sc = s.cod_univers);
      v_cnt := v_cnt + SQL%ROWCOUNT;
    END LOOP;
    say('RO: pozitii noi plasate in nodurile REALE (dupa grupa) / EN: new positions placed into their REAL nodes: ' || v_cnt);
    COMMIT;

    -- RO: IMAGINI din URL -> TMS_MPT_TVR.IE_LINKADRES (sursa cartelei de produs).
    --     NOU: se scrie intotdeauna; EXISTENT: doar daca nu are deja imagine
    --     (nu suprascriem imaginile puse manual).
    -- EN: IMAGES from URL -> TMS_MPT_TVR.IE_LINKADRES (product-card source).
    --     NEW: always written; EXISTING: only filled when empty
    --     (never overwrite manually set images).
    MERGE INTO tms_mpt_tvr t
    USING (
      SELECT d.cod, d.url, d.st FROM (
        SELECT s.cod_univers cod, s.img_url url, s.status st,
               ROW_NUMBER() OVER (PARTITION BY s.cod_univers ORDER BY s.id) rn
        FROM biro26pt_stg s
        WHERE s.load_id = p_load_id AND s.cod_univers IS NOT NULL
          AND s.status IN ('NEW','EXISTING')
          AND REGEXP_LIKE(s.img_url, '^https?://')
      ) d WHERE d.rn = 1
    ) u
    ON (t.cod = u.cod)
    WHEN MATCHED THEN UPDATE SET t.ie_linkadres = u.url
      WHERE t.ie_linkadres IS NULL OR u.st = 'NEW'
    WHEN NOT MATCHED THEN INSERT (cod, ie_linkadres) VALUES (u.cod, u.url);
    say('RO: imagini importate din URL (IE_LINKADRES) / EN: image URLs imported: ' || SQL%ROWCOUNT);
    COMMIT;

    -- RO: 1) coduri de bare DIN FISIER - doar rinduri cu cod NE-NUL, pt. produse potrivite
    --     univoc dupa articol; protejat de duplicate si de unicitatea globala. NU folosim
    --     import_barcodes (care insereaza si NULL -> ORA-01400 pe fisiere cu coloana partial goala).
    -- EN: 1) barcodes FROM FILE - only NON-NULL rows, for products matched unambiguously by
    --     article; guarded against duplicates and global uniqueness. We do NOT use import_barcodes
    --     (which would insert NULLs -> ORA-01400 on files with a partially empty barcode column).
    INSERT INTO tms_mpt_barcode (cod, barcode, coment)
    SELECT c.cod, c.bc, 'RO: cod de bare din fisier / EN: barcode from file'
    FROM (
      SELECT u.cod cod, SUBSTR(s.barcode, 1, 15) bc,
             COUNT(*) OVER (PARTITION BY s.id) cnt
      FROM biro26pt_stg s
      JOIN tms_univers u ON u.tip = g_tip AND u.codvechi = SUBSTR(s.articol, 1, g_len_codvechi)
      WHERE s.load_id = p_load_id AND s.barcode IS NOT NULL
    ) c
    WHERE c.cnt = 1
      AND EXISTS (SELECT 1 FROM tms_mpt m WHERE m.cod = c.cod)
      AND NOT EXISTS (SELECT 1 FROM tms_mpt_barcode x WHERE x.cod = c.cod AND x.barcode = c.bc)
      AND NOT EXISTS (SELECT 1 FROM tms_barcode_uniq y WHERE y.barcode = c.bc AND y.cod <> c.cod);
    say('RO: coduri de bare din fisier inserate / EN: file barcodes inserted: ' || SQL%ROWCOUNT);
    COMMIT;

    -- RO: 2) GENEREAZA EAN-13 DOAR pentru pozitiile NOI ramase fara niciun cod de bare
    --     (nici din fisier, nici existent). / EN: 2) generate EAN-13 ONLY for NEW positions that
    --     still have no barcode at all (neither from file nor pre-existing).
    FOR r IN (SELECT s.cod_univers cod FROM biro26pt_stg s
               WHERE s.load_id = p_load_id AND s.status = 'NEW' AND s.cod_univers IS NOT NULL
                 AND NOT EXISTS (SELECT 1 FROM tms_mpt_barcode b WHERE b.cod = s.cod_univers)) LOOP
      v_bc := gen_ean13(BIRO26PT_EAN_SEQ.NEXTVAL);
      INSERT INTO tms_mpt_barcode (cod, barcode, coment)
      VALUES (r.cod, v_bc, 'RO: EAN generat produs nou / EN: generated EAN new product');
      v_ean := v_ean + 1;
    END LOOP;
    say('RO: coduri de bare EAN-13 generate / EN: EAN-13 barcodes generated: ' || v_ean);
    COMMIT;

    -- RO: ATRIBUTE WEB -> TMS_MPT_WEBATTR (satelit 1:1, cheia ca la TMS_MPT).
    --     ORIGINALUL cu diacritice se ia din BIRO26PT_RAW_BLOB (octeti UTF-8, pe care
    --     baza CL8MSWIN1251 nu-i strica); daca celula n-avea caractere speciale,
    --     originalul == textul din STG si se converteste la BLOB pe loc.
    --     Copiile de cautare (CLOB/VARCHAR2 fara diacritice) le face triggerul
    --     TMS_MPT_WEBATTR_BIU — nu le scriem aici.
    -- EN: WEB attributes -> TMS_MPT_WEBATTR (1:1 satellite, TMS_MPT key schema).
    --     The ORIGINAL with diacritics comes from BIRO26PT_RAW_BLOB (UTF-8 bytes the
    --     CL8MSWIN1251 DB cannot mangle); when the cell had no special chars the STG
    --     text IS the original and is converted to BLOB inline. Search copies are
    --     produced by the TMS_MPT_WEBATTR_BIU trigger.
    DECLARE
      v_col_desc  NUMBER := TO_NUMBER(SUBSTR(NVL(col_of(p_load_id,'DESCRIERE'),'c-1'), 2));
      v_col_dfull NUMBER := TO_NUMBER(SUBSTR(NVL(col_of(p_load_id,'DENUM_FULL'),'c-1'), 2));
      v_cnt NUMBER := 0;
    BEGIN
      IF v_col_desc >= 0 OR v_col_dfull >= 0 THEN
        MERGE INTO tms_mpt_webattr t
        USING (
          SELECT d.cod, d.descr_blob, d.dfull_blob, d.src FROM (
            SELECT s.cod_univers cod,
                   NVL( (SELECT b.val_blob FROM biro26pt_raw_blob b
                          WHERE b.load_id = s.load_id AND b.row_no = s.row_no
                            AND b.col_idx = v_col_desc),
                        YBIRO_TEXT_UTIL.nclob_to_blob(TO_NCLOB(s.descriere)) ) descr_blob,
                   NVL( (SELECT b.val_blob FROM biro26pt_raw_blob b
                          WHERE b.load_id = s.load_id AND b.row_no = s.row_no
                            AND b.col_idx = v_col_dfull),
                        YBIRO_TEXT_UTIL.nclob_to_blob(TO_NCLOB(s.denumire_full)) ) dfull_blob,
                   NVL(s.furnizor, s.src_file) src,
                   -- RO: ATENTIE - acelasi articol poate aparea in fisier la produse
                   --     DIFERITE (eroare a furnizorului: pe o foaie "Smartphone", pe alta
                   --     "Imprimanta"). Alegem randul a carui DENUMIRE se potriveste cu
                   --     numele din catalog; altfel am scrie descrierea altui produs.
                   -- EN: CAREFUL - the same article may appear for DIFFERENT products in the
                   --     file (supplier error). Pick the row whose NAME matches the catalog
                   --     name, otherwise we would attach another product's description.
                   ROW_NUMBER() OVER (PARTITION BY s.cod_univers
                     ORDER BY CASE WHEN UPPER(TRIM(SUBSTR(s.denumire,1,60)))
                                        = UPPER(TRIM(SUBSTR(u.denumirea,1,60))) THEN 0
                                   WHEN UPPER(TRIM(SUBSTR(s.denumire,1,25)))
                                        = UPPER(TRIM(SUBSTR(u.denumirea,1,25))) THEN 1
                                   ELSE 2 END, s.id) rn,
                   CASE WHEN UPPER(TRIM(SUBSTR(s.denumire,1,25)))
                             = UPPER(TRIM(SUBSTR(u.denumirea,1,25))) THEN 1 ELSE 0 END name_ok
            FROM biro26pt_stg s
            JOIN tms_univers u ON u.cod = s.cod_univers
            WHERE s.load_id = p_load_id AND s.cod_univers IS NOT NULL
              AND s.status IN ('NEW','EXISTING')
              AND (s.descriere IS NOT NULL OR s.denumire_full IS NOT NULL)
          ) d WHERE d.rn = 1 AND d.name_ok = 1   -- RO: doar potriviri sigure / EN: safe matches only
        ) u ON (t.cod = u.cod)
        WHEN MATCHED THEN UPDATE SET
          t.descriere_ro          = NVL(u.descr_blob, t.descriere_ro),
          t.denumire_full_blob_ro = NVL(u.dfull_blob, t.denumire_full_blob_ro),
          t.src                   = NVL(u.src, t.src),
          t.load_id               = p_load_id
        WHEN NOT MATCHED THEN
          INSERT (cod, descriere_ro, denumire_full_blob_ro, src, load_id)
          VALUES (u.cod, u.descr_blob, u.dfull_blob, u.src, p_load_id);
        v_cnt := SQL%ROWCOUNT;
      END IF;
      say('RO: atribute web scrise (TMS_MPT_WEBATTR) / EN: web attributes written: ' || v_cnt);
    END;
    COMMIT;

    -- RO: SINCRONIZARE BIRO26_GOODS - sursa arborelui "Grupe de marfa" + magazin (grupa/categorie).
    --     Fara aceste randuri produsele NU apar in navigarea pe grupe (back-office citeste de aici).
    -- EN: SYNC BIRO26_GOODS - the source of the "Grupe de marfa" tree + shop (grupa/categorie).
    --     Without these rows products do NOT appear in the group navigation (back-office reads here).
    MERGE INTO biro26_goods t
    USING (
      SELECT s.cod_univers cod, MAX(s.articol) art, MAX(s.denumire) den,
             MAX(s.grupa) grupa, MAX(s.categ) categ, MAX(s.furnizor) fz,
             MAX(s.angro) an, MAX(s.ionline) io, MAX(s.retail1) rt
      FROM biro26pt_stg s
      WHERE s.load_id = p_load_id AND s.cod_univers IS NOT NULL AND s.status IN ('NEW','EXISTING')
      GROUP BY s.cod_univers
    ) u ON (t.cod_univers = u.cod)
    WHEN MATCHED THEN UPDATE SET
      t.articol=u.art, t.denumire=u.den, t.grupa=u.grupa, t.categorie=u.categ,
      t.furnizor=NVL(u.fz, t.furnizor), t.angro=u.an, t.ionline=u.io, t.retail1=u.rt
    WHEN NOT MATCHED THEN INSERT (id, cod_univers, articol, denumire, grupa, categorie, furnizor, angro, ionline, retail1, unit)
      VALUES (u.cod, u.cod, u.art, u.den, u.grupa, u.categ, u.fz, u.an, u.io, u.rt, 'buc.');
    say('RO: randuri sincronizate in BIRO26_GOODS / EN: rows synced to BIRO26_GOODS: ' || SQL%ROWCOUNT);
    COMMIT;

    -- RO: PRODUCATOR/FURNIZOR: creeaza org (TIP='O', GR1='E') per furnizor si leaga cartela (DEP_PRODUCER).
    -- EN: PRODUCER/SUPPLIER: ensure org (TIP='O', GR1='E') per supplier and link the card (DEP_PRODUCER).
    FOR fz IN (SELECT UPPER(TRIM(furnizor)) fzu, MAX(TRIM(furnizor)) fzname
                 FROM biro26pt_stg
                WHERE load_id=p_load_id AND furnizor IS NOT NULL AND cod_univers IS NOT NULL
                GROUP BY UPPER(TRIM(furnizor))) LOOP
      DECLARE v_org NUMBER;
      BEGIN
        SELECT MIN(cod) INTO v_org FROM tms_univers WHERE tip='O' AND gr1='E' AND UPPER(TRIM(denumirea))=fz.fzu;
        IF v_org IS NULL THEN
          v_org := ID_TMS_UNIVERS.NEXTVAL;
          INSERT INTO tms_univers(cod,denumirea,gr1,tip,caccess,codtva,nrset)
          VALUES(v_org, SUBSTR(fz.fzname,1,160), 'E','O','11100','A',0);
        END IF;
        UPDATE tms_mpt m SET m.dep_producer=v_org
         WHERE m.cod IN (SELECT cod_univers FROM biro26pt_stg
                          WHERE load_id=p_load_id AND cod_univers IS NOT NULL AND UPPER(TRIM(furnizor))=fz.fzu)
           AND NVL(m.dep_producer,-1)<>v_org;
      END;
    END LOOP;
    say('RO: producator/furnizor legat (DEP_PRODUCER) / EN: producer/supplier linked');
    COMMIT;
  END do_writes;

  -- =================================================================
  -- RO: PREFIXAREA articolelor slabe (scurte sau pur numerice)
  -- EN: PREFIXING weak articles (short or purely numeric)
  -- =================================================================
  PROCEDURE apply_article_prefix(p_load_id IN NUMBER, p_src IN VARCHAR2 DEFAULT NULL) IS
    v_prefix   VARCHAR2(10);
    v_min_len  NUMBER := g_min_articol_len;
    v_cnt      NUMBER;
  BEGIN
    IF p_src IS NOT NULL THEN
      BEGIN
        SELECT art_prefix, NVL(art_min_len, g_min_articol_len)
          INTO v_prefix, v_min_len
          FROM tms_org_impsrc WHERE src_code = UPPER(p_src);
      EXCEPTION WHEN NO_DATA_FOUND THEN
        say('  RO: sursa necunoscuta in TMS_ORG_IMPSRC: ' || p_src ||
            ' / EN: unknown source, prefix skipped');
      END;
    END IF;

    -- RO: prefixul randului: BRAND-ul (curatat, max 6 caractere) daca exista,
    --     altfel prefixul sursei. Fara niciunul, randul ramine neatins si va fi
    --     oprit mai tirziu de paza 5.
    -- EN: row prefix: the BRAND (cleaned, max 6 chars) if present, else the source
    --     prefix. With neither, the row is left alone and guard 5 will stop it.
    UPDATE biro26pt_stg s
       SET s.articol =
             NVL( NULLIF(SUBSTR(REGEXP_REPLACE(UPPER(TRIM(s.furnizor)), '[^A-Z0-9]', ''), 1, 6), ''),
                  v_prefix ) || '-' || TRIM(s.articol)
     WHERE s.load_id = p_load_id
       AND s.articol IS NOT NULL
       AND (   LENGTH(TRIM(s.articol)) < v_min_len
            OR REGEXP_LIKE(TRIM(s.articol), '^[0-9]+$') )
       AND (   TRIM(s.furnizor) IS NOT NULL OR v_prefix IS NOT NULL );
    v_cnt := SQL%ROWCOUNT;
    COMMIT;

    IF v_cnt > 0 THEN
      say('  RO: articole slabe prefixate / EN: weak articles prefixed: ' || v_cnt ||
          CASE WHEN v_prefix IS NOT NULL THEN ' (prefix sursa: ' || v_prefix || ')' END);
    END IF;
  END apply_article_prefix;

  PROCEDURE import_file(p_load_id     IN NUMBER,
                        p_grupa       IN VARCHAR2 DEFAULT NULL,
                        p_codprice    IN NUMBER   DEFAULT NULL,
                        p_commit      IN BOOLEAN  DEFAULT FALSE,
                        p_mark_all_new IN BOOLEAN DEFAULT TRUE,
                        p_date        IN DATE     DEFAULT NULL,
                        p_force       IN BOOLEAN  DEFAULT FALSE,
                        p_src         IN VARCHAR2 DEFAULT NULL,
                        p_algo        IN VARCHAR2 DEFAULT NULL) IS
    v_cp   NUMBER := NVL(p_codprice, g_codprice);
    v_new  NUMBER;
    v_bc_filled NUMBER;
    -- RO: algoritmul: explicit (p_algo) > cel al sursei > UNIVERSAL.
    -- EN: algorithm: explicit > the source's own > UNIVERSAL.
    v_algo VARCHAR2(30) := UPPER(p_algo);
    v_sheet_group BOOLEAN := FALSE;
    v_sg_num NUMBER;
  BEGIN
    IF v_algo IS NULL AND p_src IS NOT NULL THEN
      BEGIN
        SELECT algo_code INTO v_algo FROM tms_org_impsrc WHERE src_code = UPPER(p_src);
      EXCEPTION WHEN NO_DATA_FOUND THEN NULL; END;
    END IF;
    v_algo := NVL(v_algo, 'UNIVERSAL');
    BEGIN
      -- RO: SQL-ul nu cunoaste BOOLEAN — citim numarul si convertim in PL/SQL.
      -- EN: SQL has no BOOLEAN — read the number and convert in PL/SQL.
      SELECT sheet_group INTO v_sg_num FROM ybiro_import_algo WHERE algo_code = v_algo;
      v_sheet_group := (NVL(v_sg_num, 0) = 1);
    EXCEPTION WHEN NO_DATA_FOUND THEN
      say('  RO: algoritm necunoscut: ' || v_algo || ' — se foloseste UNIVERSAL' ||
          ' / EN: unknown algorithm, falling back to UNIVERSAL');
      v_algo := 'UNIVERSAL';
    END;
    say('  RO: algoritm / EN: algorithm: ' || v_algo ||
        CASE WHEN v_sheet_group THEN '  (foile = grupe / sheets = groups)' END);
    detect_columns(p_load_id, TRUE);
    IF col_of(p_load_id,'ARTICOL') IS NULL AND col_of(p_load_id,'DENUMIRE') IS NULL THEN
      say('  RO: fisier nerecunoscut - se sare / EN: unrecognized file - skipped'); RETURN;
    END IF;
    build_stg(p_load_id, p_grupa, v_sheet_group);
    -- RO: prefixarea articolelor slabe TREBUIE sa se faca INAINTE de clasificare,
    --     altfel potrivirea s-ar face pe codul scurt si ar da dubluri/false.
    -- EN: weak-article prefixing MUST run BEFORE classification, otherwise matching
    --     would still use the short code and produce false matches.
    apply_article_prefix(p_load_id, p_src);
    classify(p_load_id);

    -- RO: PAZA anti-dubluri: fisier fara coloana de cod de bare + multe pozitii NOI.
    --     Asa s-au nascut cele ~37,7k dubluri GOG (load 164): potrivirea mergea doar
    --     dupa ARTICOL, cardurile vechi n-aveau articol, deci totul a devenit NOU.
    -- EN: anti-duplicate GUARD: no barcode column + many NEW rows. This is exactly how
    --     the ~37.7k GOG duplicates appeared (load 164).
    SELECT COUNT(*) INTO v_new FROM biro26pt_stg
     WHERE load_id = p_load_id AND status = 'NEW';
    -- RO: nu e destul ca ANTETUL sa aiba coloana de cod de bare — conteaza sa fie si
    --     DATE in ea. Un fisier cu coloana goala e la fel de periculos ca unul fara.
    -- EN: having the barcode COLUMN is not enough — it must actually contain DATA.
    --     An empty barcode column is just as dangerous as a missing one.
    SELECT COUNT(*) INTO v_bc_filled FROM biro26pt_stg
     WHERE load_id = p_load_id AND barcode IS NOT NULL;
    IF v_bc_filled = 0 AND v_new > g_max_new_nobc AND NOT p_force THEN
      say('  RO: *** OPRIT *** fisierul nu are coduri de bare (coloana lipsa sau GOALA) si ar crea ' || v_new ||
          ' pozitii NOI (prag ' || g_max_new_nobc || ').');
      say('  RO: Riscul: dubluri de marfa (vezi incidentul GOG / load 164). Cereti furnizorului');
      say('      coloana de coduri de bare, SAU rulati explicit cu p_force => TRUE daca sinteti sigur.');
      say('  EN: *** STOPPED *** no barcode DATA (missing or empty column) and ' || v_new || ' NEW rows;');
      say('      ask the supplier for barcodes, or re-run with p_force => TRUE.');
      RETURN;
    END IF;

    IF p_commit THEN
      say('  RO: >>> COMMIT: se scrie in productie / EN: >>> COMMIT: writing to production');
      do_writes(p_load_id, v_cp, p_mark_all_new, p_date);
      say('  RO: gata (scris) / EN: done (written)');
    ELSE
      say('  RO: DRY-RUN: nimic nu s-a scris in productie (doar analiza)' ||
          ' / EN: DRY-RUN: nothing written to production (analysis only)');
    END IF;
  END import_file;

  PROCEDURE import_folder(p_grupa       IN VARCHAR2 DEFAULT NULL,
                          p_codprice    IN NUMBER   DEFAULT NULL,
                          p_commit      IN BOOLEAN  DEFAULT FALSE,
                          p_mark_all_new IN BOOLEAN DEFAULT TRUE,
                          p_date        IN DATE     DEFAULT NULL,
                          p_force       IN BOOLEAN  DEFAULT FALSE,
                          p_src         IN VARCHAR2 DEFAULT NULL,
                          p_algo        IN VARCHAR2 DEFAULT NULL) IS
  BEGIN
    FOR r IN (SELECT load_id FROM biro26pt_file ORDER BY load_id) LOOP
      import_file(r.load_id, p_grupa, p_codprice, p_commit, p_mark_all_new, p_date, p_force, p_src, p_algo);
    END LOOP;
  END import_folder;

  -- =================================================================
  -- RO: IMAGINI SUPLIMENTARE (galerie) -> TMS_MPT_WEBIMG
  -- EN: ADDITIONAL (gallery) images -> TMS_MPT_WEBIMG
  -- =================================================================
  PROCEDURE import_images(p_load_id IN NUMBER,
                          p_src     IN VARCHAR2 DEFAULT NULL,
                          p_commit  IN BOOLEAN  DEFAULT FALSE) IS
    v_art   VARCHAR2(10);
    v_idx   VARCHAR2(10);
    v_url   VARCHAR2(10);
    v_src   VARCHAR2(60) := NVL(p_src, 'site');
    v_rows  NUMBER := 0;
    v_ok    NUMBER := 0;
  BEGIN
    detect_columns(p_load_id, FALSE);
    -- RO: foaia de imagini nu are antete "logice" — le luam direct dupa nume.
    -- EN: the images sheet has no "logical" headers — take them by raw name.
    BEGIN
      SELECT MAX(CASE WHEN LOWER(header_text) LIKE '%artic%'      THEN 'c'||col_idx END),
             MAX(CASE WHEN LOWER(header_text) LIKE '%image_index%' THEN 'c'||col_idx END),
             MAX(CASE WHEN LOWER(header_text) LIKE '%image_url%'   THEN 'c'||col_idx END)
        INTO v_art, v_idx, v_url
        FROM biro26pt_header WHERE load_id = p_load_id;
    EXCEPTION WHEN NO_DATA_FOUND THEN NULL;
    END;

    IF v_art IS NULL OR v_idx IS NULL OR v_url IS NULL THEN
      say('RO: foaia nu are coloanele articul/image_index/image_url — se sare.');
      say('EN: sheet lacks articul/image_index/image_url columns — skipped.');
      RETURN;
    END IF;

    SELECT COUNT(*) INTO v_rows FROM biro26pt_raw WHERE load_id = p_load_id;
    say('=== RO: Imagini suplimentare / EN: additional images (load_id=' || p_load_id || ') ===');
    say('  RO: randuri in foaie / EN: rows in sheet: ' || v_rows);

    IF NOT p_commit THEN
      -- RO: dry-run: doar cite s-ar potrivi / EN: dry-run: how many would match
      EXECUTE IMMEDIATE '
        SELECT COUNT(*) FROM biro26pt_raw r
         WHERE r.load_id = :1 AND TO_NUMBER(REGEXP_SUBSTR(r.' || v_idx || ', ''^\d+$'')) > 1
           AND EXISTS (SELECT 1 FROM tms_univers u
                        WHERE u.tip = ''' || g_tip || ''' AND NVL(u.isarhiv,''0'') <> ''2''
                          AND u.codvechi = SUBSTR(r.' || v_art || ', 1, ' || g_len_codvechi || '))'
        INTO v_ok USING p_load_id;
      say('  RO: s-ar importa / EN: would import: ' || v_ok || ' (dry-run)');
      RETURN;
    END IF;

    -- RO: MERGE dupa (COD, IMAGE_INDEX): reincarcarea aceluiasi export nu dubleaza.
    -- EN: MERGE on (COD, IMAGE_INDEX): re-loading the same export does not duplicate.
    EXECUTE IMMEDIATE '
      MERGE INTO tms_mpt_webimg t
      USING (
        SELECT u.cod,
               TO_NUMBER(REGEXP_SUBSTR(r.' || v_idx || ', ''^\d+$'')) image_index,
               MIN(SUBSTR(r.' || v_url || ', 1, 1000)) image_url
          FROM biro26pt_raw r
          JOIN tms_univers u
            ON u.tip = ''' || g_tip || ''' AND NVL(u.isarhiv,''0'') <> ''2''
           AND u.codvechi = SUBSTR(r.' || v_art || ', 1, ' || g_len_codvechi || ')
         WHERE r.load_id = :1
           AND TO_NUMBER(REGEXP_SUBSTR(r.' || v_idx || ', ''^\d+$'')) > 1
           AND r.' || v_url || ' IS NOT NULL
         GROUP BY u.cod, TO_NUMBER(REGEXP_SUBSTR(r.' || v_idx || ', ''^\d+$''))
      ) s
      ON (t.cod = s.cod AND t.image_index = s.image_index)
      WHEN MATCHED THEN UPDATE SET t.image_url = s.image_url,
                                   t.src = :2, t.load_id = :3, t.updated_at = SYSDATE
      WHEN NOT MATCHED THEN
        INSERT (cod, image_index, image_url, src, load_id)
        VALUES (s.cod, s.image_index, s.image_url, :4, :5)'
      USING p_load_id, v_src, p_load_id, v_src, p_load_id;
    v_ok := SQL%ROWCOUNT;
    COMMIT;
    say('RO: imagini suplimentare scrise (TMS_MPT_WEBIMG) / EN: gallery images written: ' || v_ok);
  END import_images;

  FUNCTION algo_md RETURN CLOB IS
    c CLOB;
    PROCEDURE a(p VARCHAR2) IS BEGIN c := c || p || CHR(10); END;
  BEGIN
    DBMS_LOB.CREATETEMPORARY(c, TRUE);
    a('# BIRO26PT_importData — universal import / import universal');
    a('');
    a('RO: Import de fisiere cu structura necunoscuta in dictionarul OfficePlus');
    a('(`TMS_UNIVERS`), lista de preturi si codurile de bare.');
    a('EN: Import of files with unknown structure into the OfficePlus dictionary');
    a('(`TMS_UNIVERS`), price list and barcodes.');
    a('');
    a('## 1. Arhitectura / Architecture');
    a('RO: 2 straturi. EN: 2 layers.');
    a('- **Loader (Python)** `biro26pt_loader.py`: RO: incarca orice xlsx/csv in stagin brut');
    a('  `BIRO26PT_RAW(c0..c15)` + `BIRO26PT_HEADER` + `BIRO26PT_FILE`, fara interpretare.');
    a('  EN: loads any xlsx/csv into raw staging, no interpretation.');
    a('- **PL/SQL `BIRO26PT_importData`**: RO: detectia coloanelor + import. EN: column detection + import.');
    a('');
    a('## 2. Detectia coloanelor (3 strategii) / Column detection (3 strategies)');
    a('RO: rezultat = `BIRO26PT_MAP(logical_field -> cNN)`. EN: result = mapping table.');
    a('1. **RO: dupa numele coloanei / EN: by header name** — `BIRO26PT_COLMAP` (sinonime RO/RU/EN,');
    a('   `LOWER(header) LIKE pattern`, prioritate minima castiga). RO: acopera integral batch-3.');
    a('2. **RO: dupa ordinea cunoscuta / EN: by known order** — `BIRO26PT_LAYOUT` (semnaturi pozitionale,');
    a('   ex. fisier coduri de bare `[1]=BARCODE,[2]=ARTICOL,[3]=DENUMIRE`).');
    a('3. **RO: dupa continut / macar un produs cunoscut / EN: by content / one known product** —');
    a('   RO: esantion de randuri; per coloana se masoara potrivirea cu `CODVECHI` (->ARTICOL),');
    a('   cu `DENUMIREA` (->DENUMIRE, ancora "produs cunoscut"), regex cod de bare `^\d{8,14}$`,');
    a('   numeric (->pret; angro<online<=retail dupa mediana). EN: content-based anchoring.');
    a('');
    a('RO: Prioritate: antet > continut > layout; campurile lipsa se completeaza in ordine.');
    a('EN: Priority: header > content > layout; missing fields filled in order.');
    a('');
    a('## 3. Pipeline import / Import pipeline');
    a('RO: proiectie `RAW -> BIRO26PT_STG` (forma "goods"); apoi:');
    a('EN: project RAW -> STG (goods shape); then:');
    a('- **RO: clasificare / EN: classify** vs `TMS_UNIVERS.CODVECHI`: `NEW` / `EXISTING` / `AMBIGUOUS` / `NOARTICOL`.');
    a('- **RO: pozitii noi / EN: new positions**: `COD` din `ID_TMS_UNIVERS`, apoi');
    a('  `YBIRO_Import_Marfa.import_univers` + `import_mpt`.');
    a('- **RO: preturi (actualizare AUTOMATA) / EN: prices (AUTO-UPDATE)**: NOU = pret initial;');
    a('  RO: EXISTENT = perioada noua (datastart = data incarcarii sau p_date) ori de cite ori');
    a('  pretul din fisier DIFERA de cel curent (mai mare sau mai mic). Reimport in aceeasi zi');
    a('  actualizeaza valorile perioadei existente. Perioada anterioara se inchide');
    a('  (DATAEND = start_nou - 1). EN: EXISTING = new period whenever the file price differs');
    a('  (higher or lower); same-day re-import updates the period in place.');
    a('- **RO: imagini din URL / EN: images from URL**: coloana URL (antet sau continut');
    a('  `^https?://`) -> `TMS_MPT_TVR.IE_LINKADRES` (imaginea cartelei de produs).');
    a('  RO: NOU = intotdeauna; EXISTENT = doar daca nu are imagine (nu se suprascrie).');
    a('  EN: NEW = always; EXISTING = only filled when empty (never overwritten).');
    a('- **RO: produse noi / EN: new products**: marcaj `TMS_MPT.MATGR1=1` (filtru "produse noi",');
    a('  vizibil in VMS_MPT; nod VIRTUAL, nu fizic), plasare in nodul REAL de arbore (dupa GRUPA), si generare cod de bare');
    a('  **EAN-13** (prefix 20 + secventa + cifra de control). EN: MATGR1 flag + tree node + EAN-13.');
    a('- **RO: coduri de bare din fisier / EN: file barcodes**: `import_barcodes` daca exista coloana.');
    a('');
    a('## 4. Siguranta / Safety');
    a('- RO: **dry-run implicit** (`p_commit=FALSE`) — nimic nu se scrie. EN: dry-run by default.');
    a('- RO: toate insert-urile sub `NOT EXISTS`; fara stergeri; preturi pe perioade; coduri de bare aditive.');
    a('  EN: all inserts NOT EXISTS-guarded; no deletes; period prices; additive barcodes.');
    a('- RO: detectia se jurnalizeaza in `BIRO26PT_LOG`. EN: detection logged in BIRO26PT_LOG.');
    a('');
    a('## 5. Utilizare / Usage');
    a('```sql');
    a('-- RO: 1) incarca fisierele (shell) / EN: load files (shell):');
    a('--    python biro26pt_loader.py /path/to/folder');
    a('-- RO: 2) dry-run (analiza) / EN: dry-run (analysis):');
    a('SET SERVEROUTPUT ON');
    a('BEGIN BIRO26PT_importData.import_folder(p_commit => FALSE); END;');
    a('/');
    a('-- RO: 3) import real / EN: real import:');
    a('BEGIN BIRO26PT_importData.import_file(p_load_id => 1, p_grupa => ''Hartie'', p_commit => TRUE); END;');
    a('/');
    a('```');
    RETURN c;
  END algo_md;

END BIRO26PT_importData;
/
