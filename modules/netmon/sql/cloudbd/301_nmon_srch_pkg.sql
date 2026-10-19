-- Поиск по XWiki и OTRS — типы и пакет NMON_SRCH (база cloudbd, схема OTRS).
--
-- Вся логика поиска здесь, на стороне базы:
--   * номер заявки находится сразу, без полнотекстового поиска
--   * каждое слово ищется точно, по основе (принтера = принтер%) и с опечаткой
--   * запрос, набранный не в той раскладке (ghbdtn = привет), исправляется сам
--   * если все слова сразу не встречаются — ищется документ с частью слов
--   * вес выше у совпадений в заголовке, у фразы целиком и у свежих документов
--   * фрагмент текста с подсветкой и оригинальная ссылка на XWiki или OTRS
--
-- В исходнике только символы кодировки базы (CL8MSWIN1251): буквы с
-- румынской диакритикой сюда не попадают — их снимает приложение до запроса.

/
CREATE OR REPLACE TYPE nmon_srch_hit FORCE AS OBJECT (
  source      VARCHAR2(10),
  src_key     VARCHAR2(600),
  title       VARCHAR2(1000),
  url         VARCHAR2(2000),
  snippet     VARCHAR2(4000),
  score       NUMBER,
  rnk         NUMBER,
  tn          VARCHAR2(50),
  queue       VARCHAR2(200),
  state       VARCHAR2(200),
  is_open     NUMBER,
  customer    VARCHAR2(300),
  owner       VARCHAR2(100),
  space       VARCHAR2(300),
  lang        VARCHAR2(10),
  author      VARCHAR2(300),
  parts       NUMBER,
  created_at  DATE,
  changed_at  DATE,
  matched_by  VARCHAR2(30),
  used_query  VARCHAR2(400),
  total       NUMBER
)
/
CREATE OR REPLACE TYPE nmon_srch_hits FORCE AS TABLE OF nmon_srch_hit
/
CREATE OR REPLACE PACKAGE nmon_srch AS

  c_otrs_url   CONSTANT VARCHAR2(100) := 'https://otrs.una.md/otrs/index.pl';
  c_xwiki_url  CONSTANT VARCHAR2(100) := 'https://xwiki.una.md';
  c_index      CONSTANT VARCHAR2(30)  := 'NMON_SRCH_DOC_CTX';

  -- Запрос: нижний регистр, только буквы и цифры, одиночные пробелы.
  FUNCTION normalize(p VARCHAR2) RETURN VARCHAR2;

  -- Текст, набранный в другой раскладке: ghbdtn -> привет, щкфсду -> oracle.
  -- NULL, если в тексте смешаны алфавиты и угадывать нечего.
  FUNCTION fix_layout(p VARCHAR2) RETURN VARCHAR2;

  -- Грубая основа слова для русского, румынского и английского:
  -- срезается самое длинное окончание, основа не короче четырёх букв.
  FUNCTION stem(p VARCHAR2) RETURN VARCHAR2;

  -- Запрос Oracle Text. p_mode: ALL — все слова, ANY — любое из слов.
  -- p_wild = 0 — без поиска по основе (если основ слишком много).
  FUNCTION ctx_query(p_norm VARCHAR2, p_mode VARCHAR2 DEFAULT 'ALL', p_wild NUMBER DEFAULT 1)
    RETURN VARCHAR2;

  -- Разметка XWiki -> обычный текст.
  FUNCTION wiki_text(p CLOB) RETURN CLOB;

  -- Пароли в письмах -> [скрыто].
  FUNCTION mask_secrets(p VARCHAR2) RETURN VARCHAR2;

  -- Оригинальная ссылка на страницу XWiki.
  FUNCTION xwiki_url(p_space VARCHAR2, p_name VARCHAR2, p_lang VARCHAR2 DEFAULT NULL) RETURN VARCHAR2;

  -- 1 — служебный раздел XWiki (шаблоны, код, настройки), в поиск не идёт.
  FUNCTION xwiki_skip(p_space VARCHAR2) RETURN NUMBER;

  -- Поиск. p_source: NULL | OTRS | XWIKI. p_open: NULL | 1 — открытые | 0 — закрытые.
  -- p_order: rank — по точности | date — сначала новые.
  FUNCTION search(p_query  VARCHAR2,
                  p_source VARCHAR2 DEFAULT NULL,
                  p_open   NUMBER   DEFAULT NULL,
                  p_limit  NUMBER   DEFAULT 20,
                  p_offset NUMBER   DEFAULT 0,
                  p_order  VARCHAR2 DEFAULT 'rank') RETURN nmon_srch_hits PIPELINED;

  -- Обновление индекса. p_full = 1 — пересобрать с нуля, иначе только изменения.
  PROCEDURE refresh(p_full NUMBER DEFAULT 0, p_source VARCHAR2 DEFAULT NULL);

  -- Сжатие индекса после большого числа изменений (раз в неделю достаточно).
  PROCEDURE optimize;

END nmon_srch;
/
CREATE OR REPLACE PACKAGE BODY nmon_srch AS

  c_lat CONSTANT VARCHAR2(40) := 'qwertyuiop[]asdfghjkl;''zxcvbnm,.`';
  c_cyr CONSTANT VARCHAR2(40) := 'йцукенгшщзхъфывапролджэячсмитьбюё';

  TYPE t_words IS TABLE OF VARCHAR2(20);

  -- Окончания: сначала длинные, чтобы «ами» не срезалось как «и».
  c_ru_end CONSTANT t_words := t_words(
    'иями', 'ями', 'ами', 'иях', 'ией', 'ого', 'его', 'ому', 'ему', 'ыми', 'ими', 'ешь', 'ишь',
    'ете', 'ите', 'ают', 'яют', 'ует', 'юет', 'ться', 'тся', 'ать', 'ять', 'ить', 'еть',
    'ов', 'ев', 'ей', 'ой', 'ий', 'ый', 'ая', 'яя', 'ое', 'ее', 'ие', 'ые', 'ую', 'юю',
    'ом', 'ем', 'ам', 'ям', 'ах', 'ях', 'ию', 'ия', 'ии', 'ье', 'ья', 'ть',
    'а', 'я', 'о', 'е', 'ы', 'и', 'у', 'ю', 'ь', 'й');
  c_lat_end CONSTANT t_words := t_words(
    'ilor', 'elor', 'ului', 'ile', 'lor', 'ing', 'ul', 'ea', 'ii',
    'le', 'ed', 'es', 's', 'e', 'i', 'a', 'u');
  -- Слова языка запросов Oracle Text: перед ними нельзя ставить * и %.
  c_reserved CONSTANT t_words := t_words(
    'about', 'accum', 'and', 'bt', 'btg', 'bti', 'btp', 'equiv', 'fuzzy', 'haspath', 'inpath',
    'minus', 'near', 'not', 'nt', 'ntg', 'nti', 'ntp', 'or', 'pt', 'rt', 'sqe', 'syn', 'tr',
    'trsyn', 'tt', 'within');

  -- ------------------------------------------------------------------ текст

  FUNCTION normalize(p VARCHAR2) RETURN VARCHAR2 IS
    v VARCHAR2(4000) := LOWER(SUBSTR(p, 1, 400));
  BEGIN
    v := REPLACE(v, 'ё', 'е');
    v := REGEXP_REPLACE(v, '[^0-9a-zа-я]+', ' ');
    v := TRIM(REGEXP_REPLACE(v, ' {2,}', ' '));
    RETURN v;
  END normalize;

  FUNCTION fix_layout(p VARCHAR2) RETURN VARCHAR2 IS
    v VARCHAR2(4000) := LOWER(SUBSTR(p, 1, 400));
  BEGIN
    IF REGEXP_LIKE(v, '[a-z]') AND NOT REGEXP_LIKE(v, '[а-яё]') THEN
      RETURN TRANSLATE(v, c_lat, c_cyr);
    ELSIF REGEXP_LIKE(v, '[а-яё]') AND NOT REGEXP_LIKE(v, '[a-z]') THEN
      RETURN TRANSLATE(v, c_cyr, c_lat);
    END IF;
    RETURN NULL;
  END fix_layout;

  FUNCTION stem(p VARCHAR2) RETURN VARCHAR2 IS
    v    VARCHAR2(100) := LOWER(p);
    ends t_words;
  BEGIN
    IF v IS NULL OR LENGTH(v) <= 4 OR REGEXP_LIKE(v, '[0-9]') THEN
      RETURN v;
    END IF;
    IF REGEXP_LIKE(v, '[а-я]') THEN
      ends := c_ru_end;
    ELSE
      ends := c_lat_end;
    END IF;
    FOR i IN 1 .. ends.COUNT LOOP
      IF LENGTH(v) - LENGTH(ends(i)) >= 4 AND SUBSTR(v, -LENGTH(ends(i))) = ends(i) THEN
        RETURN SUBSTR(v, 1, LENGTH(v) - LENGTH(ends(i)));
      END IF;
    END LOOP;
    RETURN v;
  END stem;

  FUNCTION is_reserved(p VARCHAR2) RETURN BOOLEAN IS
  BEGIN
    FOR i IN 1 .. c_reserved.COUNT LOOP
      IF c_reserved(i) = p THEN
        RETURN TRUE;
      END IF;
    END LOOP;
    RETURN FALSE;
  END is_reserved;

  FUNCTION is_stopword(p VARCHAR2) RETURN BOOLEAN IS
    n NUMBER;
  BEGIN
    SELECT COUNT(*) INTO n FROM ctx_user_stopwords
     WHERE spw_stoplist = 'NMON_SRCH_STOP' AND spw_word = p;
    RETURN n > 0;
  END is_stopword;

  FUNCTION term_expr(t VARCHAR2, p_wild NUMBER) RETURN VARCHAR2 IS
    s VARCHAR2(100);
    e VARCHAR2(1000);
  BEGIN
    IF REGEXP_LIKE(t, '^[0-9]+$') OR LENGTH(t) <= 3 THEN
      RETURN '{' || t || '}';
    END IF;
    e := '({' || t || '}*3';
    s := stem(t);
    IF p_wild = 1 AND LENGTH(s) >= 4 AND NOT is_reserved(s) THEN
      e := e || ' OR ' || s || '%';
    END IF;
    IF LENGTH(t) >= 5 AND NOT REGEXP_LIKE(t, '[0-9]') THEN
      e := e || ' OR fuzzy({' || t || '}, 60, 40, weight)';
    END IF;
    RETURN e || ')';
  END term_expr;

  FUNCTION ctx_query(p_norm VARCHAR2, p_mode VARCHAR2 DEFAULT 'ALL', p_wild NUMBER DEFAULT 1)
    RETURN VARCHAR2
  IS
    v_terms  VARCHAR2(4000);
    v_phrase VARCHAR2(4000);
    v_tok    VARCHAR2(400);
    v_n      PLS_INTEGER := 0;
    v_sep    VARCHAR2(10) := CASE WHEN p_mode = 'ANY' THEN ' ACCUM ' ELSE ' AND ' END;
  BEGIN
    FOR i IN 1 .. 8 LOOP
      v_tok := REGEXP_SUBSTR(p_norm, '[^ ]+', 1, i);
      EXIT WHEN v_tok IS NULL;
      IF NOT is_stopword(v_tok) AND (LENGTH(v_tok) >= 2 OR REGEXP_LIKE(v_tok, '^[0-9]+$')) THEN
        v_terms  := v_terms || CASE WHEN v_n > 0 THEN v_sep END || term_expr(v_tok, p_wild);
        v_phrase := v_phrase || CASE WHEN v_n > 0 THEN ' ' END || v_tok;
        v_n := v_n + 1;
      END IF;
    END LOOP;
    IF v_n = 0 THEN
      RETURN NULL;
    END IF;
    -- Совпадение в заголовке весит вдвое, фраза целиком — ещё вдвое.
    RETURN '(' || v_terms || ') ACCUM ((' || v_terms || ') WITHIN T)*2'
        || CASE WHEN v_n > 1 THEN ' ACCUM ({' || v_phrase || '})*2' END;
  END ctx_query;

  FUNCTION wiki_text(p CLOB) RETURN CLOB IS
    v CLOB := p;
  BEGIN
    IF v IS NULL THEN
      RETURN NULL;
    END IF;
    -- код скриптов не текст страницы
    v := REGEXP_REPLACE(v, '\{\{(velocity|groovy|python)[^}]*\}\}.*?\{\{/\1\}\}', ' ', 1, 0, 'n');
    v := REGEXP_REPLACE(v, '\{(velocity|groovy)[^}]*\}.*?\{\1\}', ' ', 1, 0, 'n');
    v := REGEXP_REPLACE(v, '(^|' || CHR(10) || ')[ ]*#(set|if|elseif|else|end|foreach|macro|include)[^' || CHR(10) || ']*', ' ');
    -- ссылки: [[подпись>>адрес]] -> подпись
    v := REGEXP_REPLACE(v, '\[\[([^]>]*)>>[^]]*\]\]', '\1');
    v := REGEXP_REPLACE(v, '\[\[([^]]*)\]\]', '\1');
    v := REGEXP_REPLACE(v, '\{\{[^}]*\}\}', ' ');
    v := REGEXP_REPLACE(v, '<[^>]*>', ' ');
    v := REGEXP_REPLACE(v, '&(nbsp|amp|lt|gt|quot|laquo|raquo|mdash|ndash);', ' ');
    v := REGEXP_REPLACE(v, '(\*\*|//|__|~~|==+|\|=|\||\(%[^)]*%\))', ' ');
    -- TRANSLATE для CLOB длиннее 32 КБ даёт ORA-06502, REGEXP_REPLACE — нет.
    v := REGEXP_REPLACE(v, '[<>]', ' ');
    v := REGEXP_REPLACE(v, '[ ' || CHR(9) || CHR(13) || ']+', ' ');
    v := REGEXP_REPLACE(v, '(' || CHR(10) || ' ?)+', CHR(10));
    RETURN v;
  END wiki_text;

  FUNCTION mask_secrets(p VARCHAR2) RETURN VARCHAR2 IS
  BEGIN
    RETURN REGEXP_REPLACE(p,
      '(([Пп][Аа][Рр][Оо][Лл][ЬьЯяИиЕе]?|[Pp][Aa][Ss][Ss]([Ww][Oo]?[Rr][Dd])?|[Pp][Ww][Dd]|[Pp][Aa][Rr][Oo][Ll][Aa])'
      || '([ ]*[:=][ ]*|[ ]+))[^ ' || CHR(9) || CHR(10) || CHR(13) || ']+',
      '\1[скрыто]');
  END mask_secrets;

  FUNCTION esc_url(p VARCHAR2) RETURN VARCHAR2 IS
  BEGIN
    RETURN UTL_URL.ESCAPE(p, TRUE, 'AL32UTF8');
  END esc_url;

  FUNCTION xwiki_url(p_space VARCHAR2, p_name VARCHAR2, p_lang VARCHAR2 DEFAULT NULL) RETURN VARCHAR2 IS
  BEGIN
    RETURN c_xwiki_url || '/bin/view/' || esc_url(p_space) || '/' || esc_url(p_name)
        || CASE WHEN p_lang IS NOT NULL THEN '?language=' || p_lang END;
  END xwiki_url;

  FUNCTION xwiki_skip(p_space VARCHAR2) RETURN NUMBER IS
  BEGIN
    IF p_space IN ('XWiki', 'Panels', 'Scheduler', 'Stats', 'BBCode', 'ColorThemes', 'GWT',
                   'Invitation', 'MultiPageExport', 'SavedList', 'Sandbox', 'XAppManager', 'XAppResources')
       OR REGEXP_LIKE(p_space, '(Code|Classes|Sheets|Templates)$') THEN
      RETURN 1;
    END IF;
    RETURN 0;
  END xwiki_skip;

  -- Текст для зоны документа: угловые скобки — разделители зон, их убираем.
  FUNCTION clean(p VARCHAR2) RETURN VARCHAR2 IS
  BEGIN
    RETURN TRANSLATE(p, '<>', '  ');
  END clean;

  -- Письмо без цитаты предыдущих писем (строки с >) и без паролей.
  FUNCTION mail_text(p VARCHAR2) RETURN VARCHAR2 IS
    v VARCHAR2(32767) := p;
  BEGIN
    v := REGEXP_REPLACE(v, '(^|' || CHR(10) || ')[ ]*>[^' || CHR(10) || ']*', '\1');
    v := REGEXP_REPLACE(v, '[' || CHR(13) || ']', '');
    v := REGEXP_REPLACE(v, '(' || CHR(10) || '[ ' || CHR(9) || ']*){2,}', CHR(10));
    RETURN clean(mask_secrets(v));
  END mail_text;

  PROCEDURE app(io IN OUT NOCOPY CLOB, p VARCHAR2) IS
  BEGIN
    IF p IS NOT NULL THEN
      DBMS_LOB.WRITEAPPEND(io, LENGTH(p), p);
    END IF;
  END app;

  -- ------------------------------------------------------------- журнал

  PROCEDURE log_query(p_query VARCHAR2, p_used VARCHAR2, p_source VARCHAR2, p_by VARCHAR2,
                      p_hits NUMBER, p_ms NUMBER) IS
    PRAGMA AUTONOMOUS_TRANSACTION;
  BEGIN
    INSERT INTO nmon_srch_log (log_id, query, used_query, source, matched_by, hits, ms)
    VALUES (nmon_srch_log_seq.NEXTVAL, SUBSTR(p_query, 1, 400), SUBSTR(p_used, 1, 400),
            p_source, p_by, p_hits, p_ms);
    COMMIT;
  END log_query;

  -- -------------------------------------------------------------- поиск

  FUNCTION hit_count(p_q VARCHAR2, p_source VARCHAR2, p_open NUMBER) RETURN NUMBER IS
    n NUMBER;
  BEGIN
    IF p_q IS NULL THEN
      RETURN 0;
    END IF;
    SELECT COUNT(*) INTO n FROM nmon_srch_doc d
     WHERE CONTAINS(d.body, p_q, 1) > 0
       AND (p_source IS NULL OR d.source = p_source)
       AND (p_open IS NULL OR d.is_open = p_open);
    RETURN n;
  EXCEPTION
    WHEN OTHERS THEN
      RETURN -1;   -- слишком много основ слова (DRG-51030) или разбор запроса
  END hit_count;

  FUNCTION snippet(p_rid ROWID, p_q VARCHAR2) RETURN VARCHAR2 IS
    s VARCHAR2(32767);
  BEGIN
    s := CTX_DOC.SNIPPET(c_index, ROWIDTOCHAR(p_rid), p_q, CHR(1), CHR(2), FALSE, ' ... ');
    s := REGEXP_REPLACE(s, '[ ' || CHR(9) || CHR(10) || CHR(13) || ']+', ' ');
    RETURN SUBSTR(TRIM(s), 1, 1200);
  EXCEPTION
    WHEN OTHERS THEN
      RETURN NULL;
  END snippet;

  FUNCTION search(p_query  VARCHAR2,
                  p_source VARCHAR2 DEFAULT NULL,
                  p_open   NUMBER   DEFAULT NULL,
                  p_limit  NUMBER   DEFAULT 20,
                  p_offset NUMBER   DEFAULT 0,
                  p_order  VARCHAR2 DEFAULT 'rank') RETURN nmon_srch_hits PIPELINED
  IS
    v_t0    PLS_INTEGER := DBMS_UTILITY.GET_TIME;
    v_raw   VARCHAR2(4000) := LOWER(SUBSTR(TRIM(p_query), 1, 400));
    v_norm  VARCHAR2(4000) := normalize(v_raw);
    v_src   VARCHAR2(10) := CASE WHEN UPPER(p_source) IN ('OTRS', 'XWIKI') THEN UPPER(p_source) END;
    v_lim   NUMBER := LEAST(GREATEST(NVL(p_limit, 20), 1), 100);
    v_off   NUMBER := GREATEST(NVL(p_offset, 0), 0);
    v_tn    VARCHAR2(50) := REGEXP_SUBSTR(v_raw, '[0-9]{8,20}');
    v_alt   VARCHAR2(4000);
    v_q     VARCHAR2(4000);
    v_used  VARCHAR2(400) := SUBSTR(v_norm, 1, 400);
    v_by    VARCHAR2(30);
    v_total NUMBER := 0;
    v_exact NUMBER := 0;

    PROCEDURE try_query(p_norm VARCHAR2, p_mode VARCHAR2, p_by VARCHAR2) IS
      q VARCHAR2(4000);
      n NUMBER;
    BEGIN
      q := ctx_query(p_norm, p_mode, 1);
      n := hit_count(q, v_src, p_open);
      IF n < 0 THEN                       -- без поиска по основе
        q := ctx_query(p_norm, p_mode, 0);
        n := GREATEST(hit_count(q, v_src, p_open), 0);
      END IF;
      IF n > 0 AND v_total = 0 THEN
        v_q := q;
        v_total := n;
        v_by := p_by;
        v_used := SUBSTR(p_norm, 1, 400);
      END IF;
    END try_query;
  BEGIN
    IF v_norm IS NULL THEN
      RETURN;
    END IF;
    CTX_DOC.SET_KEY_TYPE('ROWID');

    -- 1. Номер заявки — точное совпадение, первым в списке.
    IF v_tn IS NOT NULL AND NVL(v_src, 'OTRS') = 'OTRS' THEN
      FOR r IN (SELECT d.* FROM nmon_srch_doc d WHERE d.tn = v_tn AND d.source = 'OTRS') LOOP
        v_exact := v_exact + 1;
        IF v_off = 0 THEN
          PIPE ROW (nmon_srch_hit(r.source, r.src_key, r.title, r.url, NULL, 100, 1000, r.tn, r.queue,
                                  r.state, r.is_open, r.customer, r.owner, r.space, r.lang, r.author,
                                  r.parts, r.created_at, r.changed_at, 'номер заявки', v_tn, 1));
        END IF;
      END LOOP;
      IF v_exact > 0 AND v_norm = v_tn THEN
        log_query(p_query, v_tn, v_src, 'номер заявки', v_exact, (DBMS_UTILITY.GET_TIME - v_t0) * 10);
        RETURN;
      END IF;
    END IF;

    -- 2. Все слова: точно, по основе, с опечаткой.
    try_query(v_norm, 'ALL', 'все слова');

    -- 3. Не та раскладка клавиатуры.
    IF v_total = 0 THEN
      v_alt := normalize(fix_layout(v_raw));
      IF v_alt IS NOT NULL AND v_alt <> v_norm THEN
        try_query(v_alt, 'ALL', 'раскладка');
      END IF;
    END IF;

    -- 4. Хотя бы часть слов.
    IF v_total = 0 AND INSTR(v_norm, ' ') > 0 THEN
      try_query(v_norm, 'ANY', 'часть слов');
    END IF;

    IF v_total > 0 THEN
      FOR r IN (
        SELECT *
          FROM (SELECT x.*, ROWNUM rn
                  FROM (SELECT d.ROWID rid, d.source, d.src_key, d.title, d.url, d.tn, d.queue, d.state,
                               d.is_open, d.customer, d.owner, d.space, d.lang, d.author, d.parts,
                               d.created_at, d.changed_at, SCORE(1) sc,
                               SCORE(1)
                               + CASE WHEN d.changed_at > SYSDATE - 30 THEN 8
                                      WHEN d.changed_at > SYSDATE - 365 THEN 4 ELSE 0 END
                               + CASE WHEN d.source = 'XWIKI' THEN 6 ELSE 0 END
                               + CASE WHEN d.is_open = 1 THEN 2 ELSE 0 END rk
                          FROM nmon_srch_doc d
                         WHERE CONTAINS(d.body, v_q, 1) > 0
                           AND (v_src IS NULL OR d.source = v_src)
                           AND (p_open IS NULL OR d.is_open = p_open)
                           AND (v_tn IS NULL OR d.tn IS NULL OR d.tn <> v_tn)
                         ORDER BY CASE WHEN p_order = 'date' THEN d.changed_at END DESC NULLS LAST,
                                  rk DESC, d.changed_at DESC) x
                 WHERE ROWNUM <= v_off + v_lim)
         WHERE rn > v_off)
      LOOP
        PIPE ROW (nmon_srch_hit(r.source, r.src_key, r.title, r.url, snippet(r.rid, v_q), r.sc, r.rk,
                                r.tn, r.queue, r.state, r.is_open, r.customer, r.owner, r.space, r.lang,
                                r.author, r.parts, r.created_at, r.changed_at, v_by, v_used,
                                v_total + v_exact));
      END LOOP;
    END IF;

    log_query(p_query, v_used, v_src, NVL(v_by, CASE WHEN v_exact > 0 THEN 'номер заявки' ELSE 'ничего' END),
              v_total + v_exact, (DBMS_UTILITY.GET_TIME - v_t0) * 10);
    RETURN;
  END search;

  -- ---------------------------------------------------------- обновление

  -- Замок на источник: второе обновление не начнётся, пока идёт первое.
  -- Зависшее дольше двух часов считается упавшим.
  FUNCTION take(p_source VARCHAR2) RETURN BOOLEAN IS
    PRAGMA AUTONOMOUS_TRANSACTION;
    n NUMBER;
  BEGIN
    UPDATE nmon_srch_sync
       SET status = 'running', run_started = SYSDATE, message = NULL
     WHERE source = p_source
       AND (status <> 'running' OR run_started < SYSDATE - 2 / 24);
    n := SQL%ROWCOUNT;
    COMMIT;
    RETURN n = 1;
  END take;

  PROCEDURE done(p_source VARCHAR2, p_status VARCHAR2, p_msg VARCHAR2, p_added NUMBER,
                 p_updated NUMBER, p_removed NUMBER, p_last_change DATE, p_last_id NUMBER,
                 p_full NUMBER) IS
    PRAGMA AUTONOMOUS_TRANSACTION;
    v_docs NUMBER;
  BEGIN
    SELECT COUNT(*) INTO v_docs FROM nmon_srch_doc WHERE source = p_source;
    UPDATE nmon_srch_sync
       SET status       = p_status,
           message      = SUBSTR(p_msg, 1, 1000),
           last_run_at  = SYSDATE,
           seconds      = ROUND((SYSDATE - run_started) * 86400),
           last_full_at = CASE WHEN p_full = 1 AND p_status = 'ok' THEN SYSDATE ELSE last_full_at END,
           last_change  = CASE WHEN p_status = 'ok' THEN NVL(p_last_change, last_change) ELSE last_change END,
           last_id      = CASE WHEN p_status = 'ok' THEN NVL(p_last_id, last_id) ELSE last_id END,
           added = p_added, updated = p_updated, removed = p_removed, docs = v_docs
     WHERE source = p_source;
    COMMIT;
  END done;

  PROCEDURE put_doc(p_source VARCHAR2, p_key VARCHAR2, p_title VARCHAR2, p_url VARCHAR2, p_body CLOB,
                    p_tn VARCHAR2, p_queue VARCHAR2, p_state VARCHAR2, p_open NUMBER,
                    p_customer VARCHAR2, p_owner VARCHAR2, p_space VARCHAR2, p_lang VARCHAR2,
                    p_author VARCHAR2, p_parts NUMBER, p_created DATE, p_changed DATE,
                    io_added IN OUT NUMBER, io_updated IN OUT NUMBER) IS
  BEGIN
    UPDATE nmon_srch_doc
       SET title = SUBSTR(p_title, 1, 1000), url = p_url, body = p_body, tn = p_tn, queue = p_queue,
           state = p_state, is_open = p_open, customer = SUBSTR(p_customer, 1, 300), owner = p_owner,
           space = SUBSTR(p_space, 1, 300), lang = p_lang, author = SUBSTR(p_author, 1, 300),
           parts = p_parts, created_at = p_created, changed_at = p_changed, indexed_at = SYSDATE
     WHERE source = p_source AND src_key = p_key;
    IF SQL%ROWCOUNT = 0 THEN
      INSERT INTO nmon_srch_doc (doc_id, source, src_key, title, url, body, tn, queue, state, is_open,
                                 customer, owner, space, lang, author, parts, created_at, changed_at)
      VALUES (nmon_srch_doc_seq.NEXTVAL, p_source, p_key, SUBSTR(p_title, 1, 1000), p_url, p_body,
              p_tn, p_queue, p_state, p_open, SUBSTR(p_customer, 1, 300), p_owner,
              SUBSTR(p_space, 1, 300), p_lang, SUBSTR(p_author, 1, 300), p_parts, p_created, p_changed);
      io_added := io_added + 1;
    ELSE
      io_updated := io_updated + 1;
    END IF;
  END put_doc;

  PROCEDURE refresh_xwiki(p_full NUMBER) IS
    v_since   DATE;
    v_max     DATE;
    v_body    CLOB;
    v_title   VARCHAR2(1000);
    v_files   VARCHAR2(4000);
    v_lang    VARCHAR2(10);
    v_added   NUMBER := 0;
    v_updated NUMBER := 0;
    v_removed NUMBER := 0;
  BEGIN
    IF NOT take('XWIKI') THEN
      RETURN;
    END IF;
    SELECT CASE WHEN p_full = 1 THEN NULL ELSE last_change END INTO v_since
      FROM nmon_srch_sync WHERE source = 'XWIKI';
    v_max := v_since;

    FOR d IN (SELECT x.xwd_id, x.xwd_fullname, x.xwd_web, x.xwd_name, x.xwd_title, x.xwd_language,
                     x.xwd_translation, x.xwd_author, CAST(x.xwd_creation_date AS DATE) created_at,
                     CAST(x.xwd_date AS DATE) changed_at, x.xwd_content
                FROM xwiki.xwikidoc x
               WHERE NVL(x.xwd_hidden, 0) = 0
                 AND nmon_srch.xwiki_skip(x.xwd_web) = 0
                 AND (v_since IS NULL OR x.xwd_date > CAST(v_since - 1 / 24 AS TIMESTAMP))) LOOP
      v_lang := CASE WHEN d.xwd_translation = 1 THEN d.xwd_language END;
      v_title := CASE WHEN TRIM(d.xwd_title) IS NULL OR INSTR(d.xwd_title, '$') > 0
                        OR INSTR(d.xwd_title, '#') > 0 THEN d.xwd_name ELSE TRIM(d.xwd_title) END;
      SELECT SUBSTR(LISTAGG(f, ' ') WITHIN GROUP (ORDER BY f), 1, 3000) INTO v_files
        FROM (SELECT SUBSTR(a.xwa_filename, 1, 200) f FROM xwiki.xwikiattachment a
               WHERE a.xwa_doc_id = d.xwd_id AND ROWNUM <= 15);

      DBMS_LOB.CREATETEMPORARY(v_body, TRUE, DBMS_LOB.CALL);
      app(v_body, '<T>' || clean(v_title) || '</T><M>' || clean(d.xwd_web) || ' ' || clean(d.xwd_name)
                  || ' ' || clean(v_files) || '</M><B>');
      IF d.xwd_content IS NOT NULL THEN
        DBMS_LOB.APPEND(v_body, wiki_text(d.xwd_content));
      END IF;
      app(v_body, '</B>');

      put_doc('XWIKI', d.xwd_fullname || CASE WHEN v_lang IS NOT NULL THEN ':' || v_lang END,
              v_title, xwiki_url(d.xwd_web, d.xwd_name, v_lang), v_body,
              NULL, NULL, NULL, 0, NULL, NULL, d.xwd_web, NVL(v_lang, d.xwd_language),
              REGEXP_REPLACE(d.xwd_author, '^XWiki\.', ''), 1, d.created_at, d.changed_at,
              v_added, v_updated);
      DBMS_LOB.FREETEMPORARY(v_body);
      v_max := GREATEST(NVL(v_max, d.changed_at), NVL(d.changed_at, v_max));
    END LOOP;

    -- Страницы, которых больше нет (удалены, переименованы, скрыты).
    DELETE FROM nmon_srch_doc s
     WHERE s.source = 'XWIKI'
       AND NOT EXISTS (SELECT 1 FROM xwiki.xwikidoc x
                        WHERE x.xwd_fullname || CASE WHEN x.xwd_translation = 1 THEN ':' || x.xwd_language END
                              = s.src_key
                          AND NVL(x.xwd_hidden, 0) = 0
                          AND nmon_srch.xwiki_skip(x.xwd_web) = 0);
    v_removed := SQL%ROWCOUNT;
    COMMIT;
    CTX_DDL.SYNC_INDEX(c_index, '200M');
    done('XWIKI', 'ok', NULL, v_added, v_updated, v_removed, v_max, NULL, p_full);
  EXCEPTION
    WHEN OTHERS THEN
      ROLLBACK;
      done('XWIKI', 'error', SQLERRM || ' ' || DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
           v_added, v_updated, v_removed, NULL, NULL, p_full);
      RAISE;
  END refresh_xwiki;

  PROCEDURE refresh_otrs(p_full NUMBER) IS
    v_since   DATE;
    v_last_id NUMBER;
    v_max_id  NUMBER;
    v_max     DATE;
    v_body    CLOB;
    v_parts   NUMBER;
    v_added   NUMBER := 0;
    v_updated NUMBER := 0;
    v_removed NUMBER := 0;
    v_n       NUMBER := 0;
  BEGIN
    IF NOT take('OTRS') THEN
      RETURN;
    END IF;
    SELECT CASE WHEN p_full = 1 THEN NULL ELSE last_change END,
           CASE WHEN p_full = 1 THEN NULL ELSE last_id END
      INTO v_since, v_last_id
      FROM nmon_srch_sync WHERE source = 'OTRS';
    SELECT MAX(id) INTO v_max_id FROM otrs.article;
    v_max := v_since;

    -- Заявка попадает в обновление, если изменилась сама или в ней появилось
    -- новое письмо (по номеру письма — индекс ARTICLE_PK, без полного просмотра).
    FOR t IN (SELECT t.id, t.tn, t.title, t.customer_id, t.create_time, t.change_time,
                     q.name queue, s.name state, st.name state_type, u.login owner
                FROM otrs.ticket t
                JOIN otrs.queue q ON q.id = t.queue_id
                JOIN otrs.ticket_state s ON s.id = t.ticket_state_id
                JOIN otrs.ticket_state_type st ON st.id = s.type_id
                LEFT JOIN otrs.system_user u ON u.id = t.user_id
               WHERE st.name NOT IN ('removed', 'merged')
                 AND (v_since IS NULL
                      OR t.change_time > v_since - 1 / 24
                      OR t.id IN (SELECT a.ticket_id FROM otrs.article a WHERE a.id > NVL(v_last_id, 0))))
    LOOP
      DBMS_LOB.CREATETEMPORARY(v_body, TRUE, DBMS_LOB.CALL);
      app(v_body, '<T>' || clean(t.title) || '</T><M>' || t.tn || ' ' || clean(t.customer_id) || ' '
                  || clean(t.queue) || ' ' || t.state || ' ' || t.owner || '</M><B>');
      v_parts := 0;
      -- Текст письма режем в PL/SQL: DBMS_LOB.SUBSTR в самом SQL ограничен 4000 байт.
      FOR a IN (SELECT a.a_subject, a.a_body
                  FROM otrs.article a WHERE a.ticket_id = t.id ORDER BY a.id) LOOP
        v_parts := v_parts + 1;
        IF v_parts <= 200 THEN
          app(v_body, clean(a.a_subject) || CHR(10)
                      || mail_text(DBMS_LOB.SUBSTR(a.a_body, 8000, 1)) || CHR(10));
        END IF;
      END LOOP;
      app(v_body, '</B>');

      put_doc('OTRS', TO_CHAR(t.id), t.title, c_otrs_url || '?Action=AgentTicketZoom;TicketID=' || t.id,
              v_body, t.tn, t.queue, t.state,
              CASE WHEN t.state_type IN ('new', 'open', 'pending reminder', 'pending auto') THEN 1 ELSE 0 END,
              t.customer_id, t.owner, NULL, NULL, NULL, v_parts, t.create_time, t.change_time,
              v_added, v_updated);
      DBMS_LOB.FREETEMPORARY(v_body);
      v_max := GREATEST(NVL(v_max, t.change_time), t.change_time);
      v_n := v_n + 1;
      IF MOD(v_n, 500) = 0 THEN
        COMMIT;
      END IF;
      IF MOD(v_n, 5000) = 0 THEN
        CTX_DDL.SYNC_INDEX(c_index, '200M');
      END IF;
    END LOOP;

    -- Удалённые и объединённые заявки уходят из поиска.
    DELETE FROM nmon_srch_doc s
     WHERE s.source = 'OTRS'
       AND EXISTS (SELECT 1 FROM otrs.ticket t, otrs.ticket_state ts, otrs.ticket_state_type st
                    WHERE t.id = TO_NUMBER(s.src_key) AND ts.id = t.ticket_state_id
                      AND st.id = ts.type_id AND st.name IN ('removed', 'merged'));
    v_removed := SQL%ROWCOUNT;
    COMMIT;
    CTX_DDL.SYNC_INDEX(c_index, '200M');
    done('OTRS', 'ok', NULL, v_added, v_updated, v_removed, v_max, v_max_id, p_full);
  EXCEPTION
    WHEN OTHERS THEN
      ROLLBACK;
      done('OTRS', 'error', SQLERRM || ' ' || DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
           v_added, v_updated, 0, NULL, NULL, p_full);
      RAISE;
  END refresh_otrs;

  PROCEDURE refresh(p_full NUMBER DEFAULT 0, p_source VARCHAR2 DEFAULT NULL) IS
  BEGIN
    IF p_source IS NULL OR UPPER(p_source) = 'XWIKI' THEN
      refresh_xwiki(NVL(p_full, 0));
    END IF;
    IF p_source IS NULL OR UPPER(p_source) = 'OTRS' THEN
      refresh_otrs(NVL(p_full, 0));
    END IF;
  END refresh;

  PROCEDURE optimize IS
  BEGIN
    CTX_DDL.OPTIMIZE_INDEX(c_index, 'FULL', maxtime => 30);
  END optimize;

END nmon_srch;
/
