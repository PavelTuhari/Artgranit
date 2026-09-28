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
    -- RO: valorile care CONTIN un URL au '?' legitim (separatorul query string) —
    --     ex. "...IdeaCentre?M=F0HM0131RU" (atehno). Aceeasi garda ca in algoritmul 5
    --     de reparare (05_repair_raw_staging). Fara ea, garda bloca importul.
    -- EN: values containing a URL carry a legitimate '?' (query-string separator);
    --     same guard as repair algorithm 5.
    IF REGEXP_LIKE(p_txt, '(https?://|www\.)', 'i') THEN
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
