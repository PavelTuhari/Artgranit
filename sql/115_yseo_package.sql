-- =====================================================================
-- RO: Pachetele conturului SEOForge. Aici traiesc regulile care nu au
--     voie sa depinda de corectitudinea aplicatiei web.
-- EN: SEOForge contour packages. Here live the rules that must not depend
--     on the web application being correct.
-- =====================================================================

CREATE OR REPLACE PACKAGE PK_SEO_UTIL AS

  -- RO: Data -> perioada in format YYYY-MM. EN: Date -> YYYY-MM period.
  FUNCTION PERIOD_OF(p_date IN DATE) RETURN VARCHAR2;

  -- RO: Valoarea unei setari din YSEO_SETUP; p_default daca lipseste.
  -- EN: A setting value from YSEO_SETUP; p_default when absent.
  FUNCTION GET_SETUP(p_code IN VARCHAR2, p_default IN VARCHAR2 DEFAULT NULL)
    RETURN VARCHAR2;

  -- RO: Suma adusa la valuta de baza. p_date NULL = ultimul curs cunoscut.
  --     Lipsa cursului este eroare, nu curs 1: altfel toate rapoartele mint.
  -- EN: Amount converted to the base currency. p_date NULL = latest known
  --     rate. A missing rate is an error, not a rate of 1: otherwise every
  --     report would lie.
  FUNCTION TO_MDL(p_suma IN NUMBER, p_valuta IN VARCHAR2, p_date IN DATE)
    RETURN NUMBER;

  -- RO: Inregistrare in jurnalul modulului. EN: Module journal entry.
  PROCEDURE LOG_EVENT(p_action      IN VARCHAR2,
                      p_entity_type IN VARCHAR2,
                      p_entity_cod  IN NUMBER,
                      p_details     IN VARCHAR2 DEFAULT NULL,
                      p_username    IN VARCHAR2 DEFAULT NULL);

END PK_SEO_UTIL;
/

CREATE OR REPLACE PACKAGE BODY PK_SEO_UTIL AS

  FUNCTION PERIOD_OF(p_date IN DATE) RETURN VARCHAR2 IS
  BEGIN
    IF p_date IS NULL THEN
      RETURN NULL;
    END IF;
    RETURN TO_CHAR(p_date, 'YYYY-MM');
  END PERIOD_OF;

  FUNCTION GET_SETUP(p_code IN VARCHAR2, p_default IN VARCHAR2 DEFAULT NULL)
    RETURN VARCHAR2 IS
    v_value YSEO_SETUP.PARAM_VALUE%TYPE;
  BEGIN
    SELECT PARAM_VALUE INTO v_value
    FROM   YSEO_SETUP
    WHERE  PARAM_CODE = p_code;
    RETURN NVL(v_value, p_default);
  EXCEPTION
    WHEN NO_DATA_FOUND THEN
      RETURN p_default;
  END GET_SETUP;

  FUNCTION TO_MDL(p_suma IN NUMBER, p_valuta IN VARCHAR2, p_date IN DATE)
    RETURN NUMBER IS
    v_base YSEO_SETUP.PARAM_VALUE%TYPE;
    v_rate YSEO_FX_RATE.RATE%TYPE;
  BEGIN
    IF p_suma IS NULL THEN
      RETURN 0;
    END IF;

    v_base := GET_SETUP('BASE_CURRENCY', 'MDL');

    IF p_valuta IS NULL OR p_valuta = v_base THEN
      RETURN p_suma;
    END IF;

    -- RO: Cursul cel mai apropiat, dar nu ulterior datei cerute.
    -- EN: The closest rate that is not later than the requested date.
    BEGIN
      SELECT RATE INTO v_rate
      FROM   (SELECT RATE
              FROM   YSEO_FX_RATE
              WHERE  VALUTA = p_valuta
                AND  (p_date IS NULL OR RATE_DATE <= p_date)
              ORDER  BY RATE_DATE DESC)
      WHERE  ROWNUM = 1;
    EXCEPTION
      WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(-20102,
          'RO: Lipseste cursul valutar pentru ' || p_valuta
          || '. Introduceti cursul in nomenclatorul de cursuri. / '
          || 'EN: Missing currency rate for ' || p_valuta
          || '. Add the rate to the rates dictionary.');
    END;

    RETURN ROUND(p_suma * v_rate, 2);
  END TO_MDL;

  PROCEDURE LOG_EVENT(p_action      IN VARCHAR2,
                      p_entity_type IN VARCHAR2,
                      p_entity_cod  IN NUMBER,
                      p_details     IN VARCHAR2 DEFAULT NULL,
                      p_username    IN VARCHAR2 DEFAULT NULL) IS
  BEGIN
    INSERT INTO YSEO_EVENT_LOG (ACTION, ENTITY_TYPE, ENTITY_COD, DETAILS, USERNAME)
    VALUES (p_action, p_entity_type, p_entity_cod,
            SUBSTR(p_details, 1, 2000), NVL(p_username, 'system'));
  END LOG_EVENT;

END PK_SEO_UTIL;
/

CREATE OR REPLACE PACKAGE PK_SEO_BUDGET AS

  -- RO: Cheia de buget: perioada, articol, canal, site.
  -- EN: The budget key: period, article, channel, site.
  TYPE T_KEY IS RECORD (
    PERIOD       VARCHAR2(10),
    ARTICLE_COD1 NUMBER,
    CHANNEL_COD1 NUMBER,
    SITE_COD     NUMBER
  );
  TYPE T_KEYS IS TABLE OF T_KEY INDEX BY PLS_INTEGER;

  FUNCTION MAKE_KEY(p_period  IN VARCHAR2,
                    p_article IN NUMBER,
                    p_channel IN NUMBER,
                    p_site    IN NUMBER) RETURN T_KEY;

  -- RO: Adevarat cat timp pachetul insusi rescrie steagurile de depasire:
  --     opreste reintrarea in declansator. EN: True while the package is
  --     rewriting the overrun flags: stops trigger re-entry.
  FUNCTION IS_FLAGGING RETURN BOOLEAN;

  -- RO: Restul planului dupa adaugarea sumei. Negativ = depasire.
  -- EN: Plan remainder after adding the amount. Negative = overrun.
  FUNCTION CHECK_LIMIT(p_period   IN VARCHAR2,
                       p_article  IN NUMBER,
                       p_channel  IN NUMBER,
                       p_site     IN NUMBER,
                       p_add_suma IN NUMBER DEFAULT 0) RETURN NUMBER;

  -- RO: Verifica limitele pentru cheile atinse de instructiune si fie
  --     opreste operatia, fie marcheaza randurile ca depasire.
  -- EN: Checks the limits for the keys touched by the statement and either
  --     stops the operation or marks the rows as an overrun.
  PROCEDURE ENFORCE_KEYS(p_keys IN T_KEYS);

  PROCEDURE PLAN_UPSERT(p_period   IN VARCHAR2,
                        p_article  IN NUMBER,
                        p_channel  IN NUMBER,
                        p_site     IN NUMBER,
                        p_suma     IN NUMBER,
                        p_valuta   IN VARCHAR2 DEFAULT 'MDL',
                        p_note     IN VARCHAR2 DEFAULT NULL,
                        p_username IN VARCHAR2 DEFAULT NULL);

  -- RO: Recalculeaza steagurile dupa ce planul a fost modificat.
  -- EN: Recomputes the flags after the plan has been changed.
  PROCEDURE RECALC_OVERBUDGET(p_period IN VARCHAR2);

END PK_SEO_BUDGET;
/

CREATE OR REPLACE PACKAGE BODY PK_SEO_BUDGET AS

  g_flagging BOOLEAN := FALSE;

  FUNCTION MAKE_KEY(p_period  IN VARCHAR2,
                    p_article IN NUMBER,
                    p_channel IN NUMBER,
                    p_site    IN NUMBER) RETURN T_KEY IS
    v_key T_KEY;
  BEGIN
    v_key.PERIOD       := p_period;
    v_key.ARTICLE_COD1 := p_article;
    v_key.CHANNEL_COD1 := p_channel;
    v_key.SITE_COD     := p_site;
    RETURN v_key;
  END MAKE_KEY;

  FUNCTION IS_FLAGGING RETURN BOOLEAN IS
  BEGIN
    RETURN g_flagging;
  END IS_FLAGGING;

  FUNCTION CHECK_LIMIT(p_period   IN VARCHAR2,
                       p_article  IN NUMBER,
                       p_channel  IN NUMBER,
                       p_site     IN NUMBER,
                       p_add_suma IN NUMBER DEFAULT 0) RETURN NUMBER IS
    v_plan NUMBER := 0;
    v_fact NUMBER := 0;
  BEGIN
    SELECT NVL(SUM(PK_SEO_UTIL.TO_MDL(PLAN_SUMA, VALUTA, NULL)), 0)
    INTO   v_plan
    FROM   YSEO_BUDGET_PLAN
    WHERE  PERIOD = p_period
      AND  ARTICLE_COD1 = p_article
      AND  NVL(CHANNEL_COD1, -1) = NVL(p_channel, -1)
      AND  NVL(SITE_COD, -1) = NVL(p_site, -1);

    SELECT NVL(SUM(SUMA_MDL), 0)
    INTO   v_fact
    FROM   YSEO_SPEND_FACT
    WHERE  PERIOD = p_period
      AND  ARTICLE_COD1 = p_article
      AND  NVL(CHANNEL_COD1, -1) = NVL(p_channel, -1)
      AND  NVL(SITE_COD, -1) = NVL(p_site, -1);

    RETURN v_plan - v_fact - NVL(p_add_suma, 0);
  END CHECK_LIMIT;

  PROCEDURE MARK_KEY(p_key IN T_KEY, p_flag IN NUMBER) IS
  BEGIN
    g_flagging := TRUE;
    UPDATE YSEO_SPEND_FACT
    SET    IS_OVERBUDGET = p_flag
    WHERE  PERIOD = p_key.PERIOD
      AND  ARTICLE_COD1 = p_key.ARTICLE_COD1
      AND  NVL(CHANNEL_COD1, -1) = NVL(p_key.CHANNEL_COD1, -1)
      AND  NVL(SITE_COD, -1) = NVL(p_key.SITE_COD, -1)
      AND  IS_OVERBUDGET <> p_flag;
    g_flagging := FALSE;
  EXCEPTION
    WHEN OTHERS THEN
      g_flagging := FALSE;
      RAISE;
  END MARK_KEY;

  PROCEDURE ENFORCE_KEYS(p_keys IN T_KEYS) IS
    TYPE t_seen IS TABLE OF T_KEY INDEX BY VARCHAR2(200);
    v_seen t_seen;
    v_sig  VARCHAR2(200);
    v_mode VARCHAR2(20);
    v_rest NUMBER;
    v_key  T_KEY;
  BEGIN
    IF p_keys.COUNT = 0 THEN
      RETURN;
    END IF;

    v_mode := NVL(PK_SEO_UTIL.GET_SETUP('BUDGET_OVERRUN_MODE', 'WARN'), 'WARN');

    -- RO: Aceeasi cheie poate veni de mai multe ori intr-o instructiune.
    -- EN: The same key may arrive several times within one statement.
    FOR i IN 1 .. p_keys.COUNT LOOP
      v_sig := p_keys(i).PERIOD || '|' || p_keys(i).ARTICLE_COD1 || '|'
               || NVL(TO_CHAR(p_keys(i).CHANNEL_COD1), '-') || '|'
               || NVL(TO_CHAR(p_keys(i).SITE_COD), '-');
      v_seen(v_sig) := p_keys(i);
    END LOOP;

    v_sig := v_seen.FIRST;
    WHILE v_sig IS NOT NULL LOOP
      v_key  := v_seen(v_sig);
      v_rest := CHECK_LIMIT(v_key.PERIOD, v_key.ARTICLE_COD1,
                            v_key.CHANNEL_COD1, v_key.SITE_COD, 0);

      IF v_rest < 0 THEN
        IF v_mode = 'BLOCK' THEN
          RAISE_APPLICATION_ERROR(-20101,
            'RO: Cheltuiala depaseste bugetul planificat pentru perioada '
            || v_key.PERIOD || '. / '
            || 'EN: Spend exceeds the planned budget for period '
            || v_key.PERIOD || '.');
        END IF;
        MARK_KEY(v_key, 1);
      ELSE
        MARK_KEY(v_key, 0);
      END IF;

      v_sig := v_seen.NEXT(v_sig);
    END LOOP;
  END ENFORCE_KEYS;

  PROCEDURE PLAN_UPSERT(p_period   IN VARCHAR2,
                        p_article  IN NUMBER,
                        p_channel  IN NUMBER,
                        p_site     IN NUMBER,
                        p_suma     IN NUMBER,
                        p_valuta   IN VARCHAR2 DEFAULT 'MDL',
                        p_note     IN VARCHAR2 DEFAULT NULL,
                        p_username IN VARCHAR2 DEFAULT NULL) IS
    v_check NUMBER;
  BEGIN
    IF p_period IS NULL OR NOT REGEXP_LIKE(p_period, '^[0-9]{4}-[0-9]{2}$') THEN
      RAISE_APPLICATION_ERROR(-20104,
        'RO: Perioada trebuie sa fie in format YYYY-MM. / '
        || 'EN: The period must be in YYYY-MM format.');
    END IF;

    IF NVL(p_suma, 0) < 0 THEN
      RAISE_APPLICATION_ERROR(-20105,
        'RO: Suma planificata nu poate fi negativa. / '
        || 'EN: The planned amount cannot be negative.');
    END IF;

    -- RO: Verificam cursul acum, ca sa nu ajunga in tabel un plan care
    --     mai tarziu ar face vederile sa cada. EN: Check the rate now so a
    --     plan that would later break the views never reaches the table.
    v_check := PK_SEO_UTIL.TO_MDL(NVL(p_suma, 0), p_valuta, NULL);

    MERGE INTO YSEO_BUDGET_PLAN t
    USING (SELECT p_period  AS PERIOD,
                  p_article AS ARTICLE_COD1,
                  p_channel AS CHANNEL_COD1,
                  p_site    AS SITE_COD
           FROM   DUAL) s
    ON    (t.PERIOD = s.PERIOD
       AND t.ARTICLE_COD1 = s.ARTICLE_COD1
       AND NVL(t.CHANNEL_COD1, -1) = NVL(s.CHANNEL_COD1, -1)
       AND NVL(t.SITE_COD, -1) = NVL(s.SITE_COD, -1))
    WHEN MATCHED THEN
      UPDATE SET t.PLAN_SUMA = NVL(p_suma, 0),
                 t.VALUTA    = NVL(p_valuta, 'MDL'),
                 t.NOTE      = p_note
    WHEN NOT MATCHED THEN
      INSERT (PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD,
              PLAN_SUMA, VALUTA, NOTE)
      VALUES (s.PERIOD, s.ARTICLE_COD1, s.CHANNEL_COD1, s.SITE_COD,
              NVL(p_suma, 0), NVL(p_valuta, 'MDL'), p_note);

    PK_SEO_UTIL.LOG_EVENT('PLAN_UPSERT', 'BUDGET_PLAN', NULL,
      p_period || ' article=' || p_article
      || ' channel=' || NVL(TO_CHAR(p_channel), '-')
      || ' site=' || NVL(TO_CHAR(p_site), '-')
      || ' suma=' || TO_CHAR(NVL(p_suma, 0)) || ' ' || NVL(p_valuta, 'MDL'),
      p_username);

    RECALC_OVERBUDGET(p_period);
  END PLAN_UPSERT;

  PROCEDURE RECALC_OVERBUDGET(p_period IN VARCHAR2) IS
    v_mode VARCHAR2(20);
    v_rest NUMBER;
    v_key  T_KEY;
  BEGIN
    v_mode := NVL(PK_SEO_UTIL.GET_SETUP('BUDGET_OVERRUN_MODE', 'WARN'), 'WARN');

    FOR r IN (SELECT DISTINCT PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD
              FROM   YSEO_SPEND_FACT
              WHERE  PERIOD = p_period) LOOP
      v_key  := MAKE_KEY(r.PERIOD, r.ARTICLE_COD1, r.CHANNEL_COD1, r.SITE_COD);
      v_rest := CHECK_LIMIT(r.PERIOD, r.ARTICLE_COD1,
                            r.CHANNEL_COD1, r.SITE_COD, 0);
      -- RO: Recalculul nu opreste operatia nici in regim BLOCK: faptul
      --     este deja inregistrat, planul a fost micsorat ulterior.
      -- EN: The recalculation does not stop the operation even in BLOCK
      --     mode: the fact is already recorded, the plan was cut later.
      MARK_KEY(v_key, CASE WHEN v_rest < 0 THEN 1 ELSE 0 END);
    END LOOP;
  END RECALC_OVERBUDGET;

END PK_SEO_BUDGET;
/
