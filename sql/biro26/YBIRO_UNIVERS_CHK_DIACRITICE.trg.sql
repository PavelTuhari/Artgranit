-- =====================================================================
-- RO: Trigger de protectie: NU permite scrierea in TMS_UNIVERS a textelor cu
--     diacritice romanesti (sau alte caractere) STRICATE de charset-ul bazei.
--     Baza e CL8MSWIN1251 (chirilic) si NU are 'ă â î ș ț' sau '× ² ‑ …' —
--     Oracle le converteste tacit in '?' ("Foto și Video" -> "Foto ?i Video").
--     Aplicatiile trebuie sa transliteze INAINTE de scriere (vezi cp1251_safe()
--     din biro26pt_loader.py).
-- EN: Guard trigger: rejects writes to TMS_UNIVERS whose text carries Romanian
--     diacritics (or other chars) MANGLED by the DB charset. The DB is
--     CL8MSWIN1251 and silently turns them into '?'. Applications must
--     transliterate BEFORE writing (see cp1251_safe() in biro26pt_loader.py).
--
-- RO: Detecteaza DOAR tiparele sigure de stricare, ca sa NU blocheze semnele de
--     intrebare REALE (care stau la sfirsit de cuvint: "Кто испек пирог?"):
--       1) '?' intre litere/cifre        -> "car?i", "22?10?32"
--       2) '?' la inceput de cuvint      -> "?coala", "?i", "?tampila"
-- EN: Only unambiguous mangling patterns, so REAL question marks (always at the
--     end of a word) are never blocked.
--
-- RO: Se declanseaza doar cind textul chiar se schimba (randurile vechi cu '?'
--     pot fi actualizate pe alte cimpuri). Dezactivare de urgenta:
--       ALTER TRIGGER YBIRO_UNIVERS_CHK_DIACRITICE DISABLE;
-- EN: Fires only when the text actually changes. Emergency off: see above.
-- =====================================================================
CREATE OR REPLACE TRIGGER YBIRO_UNIVERS_CHK_DIACRITICE
  BEFORE INSERT OR UPDATE OF DENUMIREA, NAMERUS, GR2 ON TMS_UNIVERS
  FOR EACH ROW
DECLARE
  -- RO: '?' intre litere/cifre / EN: '?' between alphanumerics
  c_pat_inner CONSTANT VARCHAR2(40) := '[[:alnum:]]\?[[:alnum:]]';
  -- RO: '?' la inceput de cuvint / EN: '?' starting a word
  c_pat_start CONSTANT VARCHAR2(40) := '(^|[[:space:]([{"''/-])\?[[:alnum:]]';

  FUNCTION is_mangled(p_txt IN VARCHAR2) RETURN BOOLEAN IS
  BEGIN
    IF p_txt IS NULL OR INSTR(p_txt, '?') = 0 THEN
      RETURN FALSE;
    END IF;
    RETURN REGEXP_LIKE(p_txt, c_pat_inner) OR REGEXP_LIKE(p_txt, c_pat_start);
  END;

  PROCEDURE check_col(p_col IN VARCHAR2, p_new IN VARCHAR2, p_old IN VARCHAR2) IS
  BEGIN
    -- RO: doar daca valoarea chiar se schimba / EN: only when the value really changes
    IF INSERTING OR NVL(p_new, '~') <> NVL(p_old, '~') THEN
      IF is_mangled(p_new) THEN
        RAISE_APPLICATION_ERROR(-20077,
          'RO: Text cu diacritice STRICATE in ' || p_col || ' (baza e CL8MSWIN1251, ' ||
          'nu accepta a-breve/i-circumflex/s-virgula/t-virgula). Transliterati inainte ' ||
          'de scriere (a a i s t). Valoare: "' || SUBSTR(p_new, 1, 80) || '" / ' ||
          'EN: MANGLED diacritics in ' || p_col || ' - the DB charset is CL8MSWIN1251; ' ||
          'transliterate before writing.');
      END IF;
    END IF;
  END;
BEGIN
  check_col('DENUMIREA', :NEW.denumirea, :OLD.denumirea);
  check_col('NAMERUS',   :NEW.namerus,   :OLD.namerus);
  check_col('GR2',       :NEW.gr2,       :OLD.gr2);
END;
/
