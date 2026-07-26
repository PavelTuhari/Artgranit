-- =====================================================================
-- RO: YBIRO_TEXT_UTIL — utilitare pentru text Unicode intr-o baza CL8MSWIN1251.
--     Ideea: textul ORIGINAL (cu diacritice) se pastreaza in BLOB (octeti UTF-8),
--     pe care baza NU ii converteste. Pentru cautare/indexare se genereaza copii
--     TEXT fara diacritice, folosind charset-ul national AL16UTF16 (NCLOB), care
--     suporta complet Unicode.
-- EN: YBIRO_TEXT_UTIL — Unicode text helpers for a CL8MSWIN1251 database.
--     The ORIGINAL text (with diacritics) lives in a BLOB (UTF-8 bytes) which the
--     DB never transcodes. Search/index copies are derived through the national
--     charset AL16UTF16 (NCLOB), which is full Unicode.
-- =====================================================================
CREATE OR REPLACE PACKAGE YBIRO_TEXT_UTIL IS
  -- RO: BLOB (UTF-8) -> NCLOB (Unicode, cu diacritice) / EN: UTF-8 BLOB -> Unicode NCLOB
  FUNCTION blob_to_nclob(p_blob IN BLOB) RETURN NCLOB;

  -- RO: NCLOB Unicode -> CLOB fara diacritice (pt. cautare/index vectorial)
  -- EN: Unicode NCLOB -> diacritics-free CLOB (for search / vector index)
  FUNCTION strip_diacritics(p_txt IN NCLOB) RETURN CLOB;

  -- RO: scurtatura: BLOB (UTF-8) -> CLOB fara diacritice / EN: shortcut BLOB -> plain CLOB
  FUNCTION blob_to_plain(p_blob IN BLOB) RETURN CLOB;

  -- RO: text (orice) -> BLOB UTF-8 / EN: text -> UTF-8 BLOB
  FUNCTION nclob_to_blob(p_txt IN NCLOB) RETURN BLOB;
END YBIRO_TEXT_UTIL;
/

CREATE OR REPLACE PACKAGE BODY YBIRO_TEXT_UTIL IS

  -- RO: TRANSLATE e 1:1 — fiecare bloc din c_from are EXACT aceeasi lungime ca perechea
  --     lui din c_to (lungimile sint notate in dreapta). Cazurile 1:N (² -> 2, ½ -> 1/2)
  --     se rezolva separat, cu REPLACE, in expand_multi.
  -- EN: TRANSLATE is 1:1 — each c_from block has EXACTLY the same length as its c_to
  --     pair (lengths noted on the right). Non-1:1 cases are handled in expand_multi.
  c_from CONSTANT NVARCHAR2(200) :=
    UNISTR('\0103\00E2\00EE\015F\0219\0163\021B') ||               -- ă â î ş ș ţ ț   (7)
    UNISTR('\0102\00C2\00CE\015E\0218\0162\021A') ||               -- Ă Â Î Ş Ș Ţ Ț   (7)
    UNISTR('\00E0\00E1\00E4\00E8\00E9\00EB\00EC\00ED') ||          -- à á ä è é ë ì í (8)
    UNISTR('\00F2\00F3\00F6\00F9\00FA\00FC\00E7\00F1') ||          -- ò ó ö ù ú ü ç ñ (8)
    UNISTR('\00C0\00C1\00C4\00C8\00C9\00CB\00CC\00CD') ||          -- À Á Ä È É Ë Ì Í (8)
    UNISTR('\00D2\00D3\00D6\00D9\00DA\00DC\00C7\00D1') ||          -- Ò Ó Ö Ù Ú Ü Ç Ñ (8)
    UNISTR('\00D7\2212\2010\2011\2013\2014') ||                    -- × − ‐ ‑ – —     (6)
    UNISTR('\2018\2019\201C\201D\00B7\2022\00B0');                 -- ‘ ’ “ ” · • °   (7)
  c_to   CONSTANT NVARCHAR2(200) :=
    UNISTR('aaisstt')  ||                                          -- (7)
    UNISTR('AAISSTT')  ||                                          -- (7)
    UNISTR('aaaeeeii') ||                                          -- (8)
    UNISTR('ooouuucn') ||                                          -- (8)
    UNISTR('AAAEEEII') ||                                          -- (8)
    UNISTR('OOOUUUCN') ||                                          -- (8)
    UNISTR('x-----')   ||                                          -- (6)
    UNISTR('\0027\0027\0022\0022\002E\002A\006F');                 -- ' ' " " . * o   (7)

  -- RO: inlocuiri 1:N (un caracter -> mai multe) / EN: 1:N replacements
  FUNCTION expand_multi(p IN NVARCHAR2) RETURN NVARCHAR2 IS
    v NVARCHAR2(4000) := p;
  BEGIN
    v := REPLACE(v, UNISTR('\00B2'), '2');      -- ²
    v := REPLACE(v, UNISTR('\00B3'), '3');      -- ³
    v := REPLACE(v, UNISTR('\00B9'), '1');      -- ¹
    v := REPLACE(v, UNISTR('\00BD'), '1/2');    -- ½
    v := REPLACE(v, UNISTR('\00BC'), '1/4');    -- ¼
    v := REPLACE(v, UNISTR('\00BE'), '3/4');    -- ¾
    v := REPLACE(v, UNISTR('\2264'), '<=');     -- ≤
    v := REPLACE(v, UNISTR('\2265'), '>=');     -- ≥
    v := REPLACE(v, UNISTR('\2248'), '~');      -- ≈
    v := REPLACE(v, UNISTR('\2260'), '!=');     -- ≠
    v := REPLACE(v, UNISTR('\00DF'), 'ss');     -- ß
    v := REPLACE(v, UNISTR('\00E6'), 'ae');     -- æ
    v := REPLACE(v, UNISTR('\00C6'), 'AE');     -- Æ
    v := REPLACE(v, UNISTR('\0153'), 'oe');     -- œ
    v := REPLACE(v, UNISTR('\0152'), 'OE');     -- Œ
    v := REPLACE(v, UNISTR('\FB01'), 'fi');     -- ﬁ
    v := REPLACE(v, UNISTR('\FB02'), 'fl');     -- ﬂ
    v := REPLACE(v, UNISTR('\2026'), '...');    -- …
    v := REPLACE(v, UNISTR('\00A0'), ' ');      -- nbsp
    v := REPLACE(v, UNISTR('\200B'), '');       -- zero-width space
    v := REPLACE(v, UNISTR('\00AD'), '');       -- soft hyphen
    RETURN v;
  END expand_multi;

  FUNCTION blob_to_nclob(p_blob IN BLOB) RETURN NCLOB IS
    v_out   NCLOB;
    v_dest  INTEGER := 1;
    v_src   INTEGER := 1;
    v_lang  INTEGER := 0;
    v_warn  INTEGER := 0;
  BEGIN
    IF p_blob IS NULL OR DBMS_LOB.GETLENGTH(p_blob) = 0 THEN
      RETURN NULL;
    END IF;
    DBMS_LOB.CREATETEMPORARY(v_out, TRUE);
    -- RO: 873 = AL32UTF8 (octetii sursa) -> NCLOB (AL16UTF16, Unicode complet)
    -- EN: 873 = AL32UTF8 source bytes -> NCLOB (AL16UTF16, full Unicode)
    DBMS_LOB.CONVERTTOCLOB(v_out, p_blob, DBMS_LOB.LOBMAXSIZE,
                           v_dest, v_src, 873, v_lang, v_warn);
    RETURN v_out;
  END blob_to_nclob;

  FUNCTION strip_diacritics(p_txt IN NCLOB) RETURN CLOB IS
    c_chunk CONSTANT PLS_INTEGER := 4000;
    v_len   PLS_INTEGER;
    v_pos   PLS_INTEGER := 1;
    v_piece NVARCHAR2(4000);
    v_out   CLOB;
  BEGIN
    IF p_txt IS NULL THEN RETURN NULL; END IF;
    v_len := DBMS_LOB.GETLENGTH(p_txt);
    IF v_len = 0 THEN RETURN NULL; END IF;
    DBMS_LOB.CREATETEMPORARY(v_out, TRUE);
    WHILE v_pos <= v_len LOOP
      v_piece := DBMS_LOB.SUBSTR(p_txt, LEAST(c_chunk, v_len - v_pos + 1), v_pos);
      -- RO: inlocuieste diacriticele, apoi converteste la charset-ul bazei
      -- EN: replace diacritics, then convert down to the DB charset
      DECLARE
        v_fixed NVARCHAR2(4000) := TRANSLATE(expand_multi(v_piece), c_from, c_to);
      BEGIN
        IF v_fixed IS NOT NULL THEN
          DBMS_LOB.WRITEAPPEND(v_out, LENGTH(v_fixed), v_fixed);
        END IF;
      END;
      v_pos := v_pos + c_chunk;
    END LOOP;
    RETURN v_out;
  END strip_diacritics;

  FUNCTION blob_to_plain(p_blob IN BLOB) RETURN CLOB IS
  BEGIN
    RETURN strip_diacritics(blob_to_nclob(p_blob));
  END blob_to_plain;

  FUNCTION nclob_to_blob(p_txt IN NCLOB) RETURN BLOB IS
    v_out  BLOB;
    v_dest INTEGER := 1;
    v_src  INTEGER := 1;
    v_lang INTEGER := 0;
    v_warn INTEGER := 0;
  BEGIN
    IF p_txt IS NULL THEN RETURN NULL; END IF;
    DBMS_LOB.CREATETEMPORARY(v_out, TRUE);
    DBMS_LOB.CONVERTTOBLOB(v_out, p_txt, DBMS_LOB.LOBMAXSIZE,
                           v_dest, v_src, 873, v_lang, v_warn);
    RETURN v_out;
  END nclob_to_blob;

END YBIRO_TEXT_UTIL;
/
