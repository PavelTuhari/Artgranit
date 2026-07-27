-- =====================================================================
-- RO: Dezactivarea (arhivarea) marfurilor al caror ARTICOL incepe cu
--     "SKU:", "Articol:", "Cod:" — sint dubluri create la import (prefixul
--     din fisier a ajuns in CODVECHI, deci potrivirea n-a gasit originalul).
--     Se arhiveaza DOAR cele care au un ORIGINAL ACTIV (aceeasi denumire sau
--     acelasi articol curatat). Jurnal reversibil: YBIRO_PREFIX_DEDUP.
-- EN: Archive goods whose ARTICLE starts with "SKU:", "Articol:", "Cod:" —
--     duplicates created at import. ONLY those having an ACTIVE ORIGINAL are
--     archived. Reversible journal: YBIRO_PREFIX_DEDUP.
-- =====================================================================
SET SERVEROUTPUT ON
SET SQLBLANKLINES ON

-- RO: jurnal (o singura data) / EN: journal (once)
DECLARE v NUMBER;
BEGIN
  SELECT COUNT(*) INTO v FROM user_tables WHERE table_name='YBIRO_PREFIX_DEDUP';
  IF v = 0 THEN
    EXECUTE IMMEDIATE '
      CREATE TABLE YBIRO_PREFIX_DEDUP (
        DUP_COD      NUMBER,
        DUP_ARTICOL  VARCHAR2(20),
        CLEAN_ARTICOL VARCHAR2(20),
        DENUMIREA    VARCHAR2(160),
        ORIG_COD     NUMBER,
        MATCH_BY     VARCHAR2(10),
        ACTION       VARCHAR2(12),
        TS           DATE DEFAULT SYSDATE)';
  END IF;
END;
/

DECLARE
  v_arch NUMBER := 0;
  v_clean NUMBER := 0;
  v_taken NUMBER;
BEGIN
  -- RO: mecanismul nativ de arhivare: (1) contul trebuie sa fie in grupa
  --     UNIVERS/DEL/ALLOW (triggerul TMS_UNIVERS_DONT_DELETE_2022), (2) flagul
  --     DOC_CHANGE_ISARHIV trebuie setat (triggerul TMS_UNIVERS_DONT_DELETE).
  -- EN: native archiving mechanism: account must be in UNIVERS/DEL/ALLOW and the
  --     DOC_CHANGE_ISARHIV flag must be set.
  SET_ENV('param_userid', '1');
  SET_ENV('DOC_CHANGE_ISARHIV', '1');

  FOR r IN (
    SELECT u.cod, u.codvechi,
           TRIM(REGEXP_REPLACE(u.codvechi,'^(SKU|Articol|Cod)\s*:\s*','',1,1,'i')) clean,
           u.denumirea,
           (SELECT MIN(o.cod) FROM tms_univers o
             WHERE o.tip='P' AND NVL(o.isarhiv,'0')<>'2' AND o.cod<>u.cod
               AND o.codvechi = TRIM(REGEXP_REPLACE(u.codvechi,'^(SKU|Articol|Cod)\s*:\s*','',1,1,'i'))) orig_by_art,
           (SELECT MIN(o.cod) FROM tms_univers o
             WHERE o.tip='P' AND NVL(o.isarhiv,'0')<>'2' AND o.cod<>u.cod
               AND UPPER(TRIM(o.denumirea))=UPPER(TRIM(u.denumirea))) orig_by_name
    FROM tms_univers u
    WHERE u.tip='P' AND NVL(u.isarhiv,'0')<>'2'
      AND REGEXP_LIKE(u.codvechi,'^(SKU|Articol|Cod)\s*:','i')
  ) LOOP
    IF r.orig_by_art IS NOT NULL OR r.orig_by_name IS NOT NULL THEN
      -- RO: DUBLURA -> arhivare / EN: DUPLICATE -> archive
      INSERT INTO ybiro_prefix_dedup(dup_cod,dup_articol,clean_articol,denumirea,orig_cod,match_by,action)
      VALUES (r.cod, r.codvechi, r.clean, SUBSTR(r.denumirea,1,160),
              NVL(r.orig_by_art, r.orig_by_name),
              CASE WHEN r.orig_by_art IS NOT NULL THEN 'ARTICOL' ELSE 'DENUMIRE' END,
              'ARHIVAT');
      UPDATE tms_univers SET isarhiv='2' WHERE cod=r.cod;
      v_arch := v_arch + 1;
    ELSE
      -- RO: NU e dublura (produs unic cu articol murdar) -> doar curatam prefixul
      -- EN: NOT a duplicate (unique product, dirty article) -> just strip the prefix
      v_taken := 0;
      IF r.clean IS NOT NULL AND LENGTH(r.clean) > 0 THEN
        SELECT COUNT(*) INTO v_taken FROM tms_univers o
         WHERE o.tip='P' AND o.codvechi = r.clean;
      END IF;
      IF r.clean IS NOT NULL AND LENGTH(r.clean) > 0 AND v_taken = 0 THEN
        INSERT INTO ybiro_prefix_dedup(dup_cod,dup_articol,clean_articol,denumirea,orig_cod,match_by,action)
        VALUES (r.cod, r.codvechi, r.clean, SUBSTR(r.denumirea,1,160), NULL, 'NONE', 'CURATAT');
        UPDATE tms_univers SET codvechi=r.clean WHERE cod=r.cod;
        v_clean := v_clean + 1;
      END IF;
    END IF;
  END LOOP;
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('RO: dubluri arhivate / EN: duplicates archived: ' || v_arch);
  DBMS_OUTPUT.PUT_LINE('RO: articole curatate de prefix / EN: articles cleaned: ' || v_clean);
END;
/
