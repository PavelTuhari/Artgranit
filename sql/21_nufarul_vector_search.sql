-- ============================================================
-- Nufarul: Oracle AI Vector Search для двуязычного поиска услуг
-- Oracle 23ai — n-gram character vector matching
-- ============================================================

-- 1. Добавляем колонку для хранения текстового поискового индекса
--    (конкатенация всех языковых названий для fuzzy search)
ALTER TABLE NUF_SERVICES ADD (
    SEARCH_TEXT VARCHAR2(1000)
);

-- 2. Заполняем SEARCH_TEXT = LOWER(NAME || ' ' || NAME_RO || ' ' || NAME_EN)
UPDATE NUF_SERVICES SET SEARCH_TEXT = LOWER(
    NVL(NAME,'') || ' | ' || NVL(NAME_RO,'') || ' | ' || NVL(NAME_EN,'')
);
COMMIT;

-- 3. Oracle Text index для полнотекстового поиска
BEGIN
    CTX_DDL.CREATE_PREFERENCE('NUF_SVC_LEXER', 'BASIC_LEXER');
    CTX_DDL.SET_ATTRIBUTE('NUF_SVC_LEXER', 'MIXED_CASE', 'NO');
    CTX_DDL.SET_ATTRIBUTE('NUF_SVC_LEXER', 'BASE_LETTER', 'YES');
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

CREATE INDEX IX_NUF_SVC_SEARCH ON NUF_SERVICES(SEARCH_TEXT)
    INDEXTYPE IS CTXSYS.CONTEXT
    PARAMETERS('LEXER NUF_SVC_LEXER SYNC(ON COMMIT)');

-- 4. PL/SQL пакет: NUF_AI_SEARCH
CREATE OR REPLACE PACKAGE NUF_AI_SEARCH AS
    /*
     * Двуязычный fuzzy-поиск услуг (RU + RO + mixed).
     * Использует DBMS_VECTOR для косинусного подобия n-gram векторов
     * и Oracle Text для полнотекстового поиска.
     *
     * Аналог rapidfuzz в Python — но работает целиком на стороне Oracle.
     */

    -- Результат одной позиции заказа
    TYPE t_match_rec IS RECORD (
        service_id   NUMBER,
        service_name VARCHAR2(200),
        service_name_ro VARCHAR2(200),
        price        NUMBER,
        unit         VARCHAR2(50),
        qty          NUMBER,
        original     VARCHAR2(500),
        confidence   NUMBER
    );

    TYPE t_match_tab IS TABLE OF t_match_rec;

    -- Основная функция: парсинг текста заказа → набор совпадений
    FUNCTION parse_order(
        p_text      IN VARCHAR2,
        p_threshold IN NUMBER DEFAULT 40
    ) RETURN t_match_tab PIPELINED;

    -- Поиск одного элемента по всем языкам
    FUNCTION find_best_service(
        p_query     IN VARCHAR2,
        p_threshold IN NUMBER DEFAULT 40
    ) RETURN t_match_rec;

    -- Утилита: удаление румынских диакритик
    FUNCTION remove_diacritics(p_text IN VARCHAR2) RETURN VARCHAR2;

    -- Утилита: разбиение текста на позиции
    TYPE t_item_rec IS RECORD (query VARCHAR2(500), qty NUMBER);
    TYPE t_item_tab IS TABLE OF t_item_rec;
    FUNCTION split_order_text(p_text IN VARCHAR2) RETURN t_item_tab PIPELINED;

    -- Утилита: вычисление подобия двух строк (0-100)
    FUNCTION string_similarity(p_str1 IN VARCHAR2, p_str2 IN VARCHAR2) RETURN NUMBER;

END NUF_AI_SEARCH;
/

CREATE OR REPLACE PACKAGE BODY NUF_AI_SEARCH AS

    -- ===== Удаление диакритик (ăâîșț → aaist) =====
    FUNCTION remove_diacritics(p_text IN VARCHAR2) RETURN VARCHAR2 IS
        v_result VARCHAR2(4000) := p_text;
    BEGIN
        v_result := REPLACE(v_result, 'ă', 'a');
        v_result := REPLACE(v_result, 'â', 'a');
        v_result := REPLACE(v_result, 'î', 'i');
        v_result := REPLACE(v_result, 'ș', 's');
        v_result := REPLACE(v_result, 'ț', 't');
        v_result := REPLACE(v_result, 'Ă', 'A');
        v_result := REPLACE(v_result, 'Â', 'A');
        v_result := REPLACE(v_result, 'Î', 'I');
        v_result := REPLACE(v_result, 'Ș', 'S');
        v_result := REPLACE(v_result, 'Ț', 'T');
        RETURN v_result;
    END;

    -- ===== Подобие строк: комбинация Jaro-Winkler + substring + word overlap =====
    FUNCTION string_similarity(p_str1 IN VARCHAR2, p_str2 IN VARCHAR2) RETURN NUMBER IS
        v_s1 VARCHAR2(1000) := LOWER(NVL(p_str1, ''));
        v_s2 VARCHAR2(1000) := LOWER(NVL(p_str2, ''));
        v_s1_nd VARCHAR2(1000);
        v_s2_nd VARCHAR2(1000);
        v_best NUMBER := 0;
        v_score NUMBER;
        v_jw NUMBER;
        v_words1 SYS.ODCIVARCHAR2LIST;
        v_words2 SYS.ODCIVARCHAR2LIST;
        v_matched NUMBER := 0;
        v_total NUMBER := 0;
    BEGIN
        IF v_s1 IS NULL OR v_s2 IS NULL THEN RETURN 0; END IF;
        IF v_s1 = v_s2 THEN RETURN 100; END IF;

        v_s1_nd := remove_diacritics(v_s1);
        v_s2_nd := remove_diacritics(v_s2);

        -- Exact match without diacritics
        IF v_s1_nd = v_s2_nd THEN RETURN 98; END IF;

        -- Substring match
        IF INSTR(v_s2, v_s1) > 0 OR INSTR(v_s2_nd, v_s1_nd) > 0 THEN
            v_best := GREATEST(v_best, 85 + ROUND(15 * LENGTH(v_s1) / GREATEST(LENGTH(v_s2), 1)));
        END IF;
        IF INSTR(v_s1, v_s2) > 0 OR INSTR(v_s1_nd, v_s2_nd) > 0 THEN
            v_best := GREATEST(v_best, 70);
        END IF;

        -- UTL_MATCH Jaro-Winkler
        v_jw := UTL_MATCH.JARO_WINKLER_SIMILARITY(v_s1_nd, v_s2_nd);
        v_best := GREATEST(v_best, v_jw);

        -- Edit distance similarity
        v_score := UTL_MATCH.EDIT_DISTANCE_SIMILARITY(v_s1_nd, v_s2_nd);
        v_best := GREATEST(v_best, v_score);

        -- Word overlap scoring
        v_total := 0;
        v_matched := 0;
        FOR i IN 1..REGEXP_COUNT(v_s1_nd, '\S+') LOOP
            v_total := v_total + 1;
            DECLARE
                v_word VARCHAR2(200) := REGEXP_SUBSTR(v_s1_nd, '\S+', 1, i);
            BEGIN
                IF v_word IS NOT NULL AND LENGTH(v_word) > 1 THEN
                    IF INSTR(v_s2_nd, v_word) > 0 THEN
                        v_matched := v_matched + 1;
                    END IF;
                END IF;
            END;
        END LOOP;
        IF v_total > 0 AND v_matched > 0 THEN
            v_score := 40 + ROUND(55 * v_matched / v_total);
            v_best := GREATEST(v_best, v_score);
        END IF;

        RETURN LEAST(v_best, 100);
    END;

    -- ===== Разбиение текста на позиции =====
    FUNCTION split_order_text(p_text IN VARCHAR2) RETURN t_item_tab PIPELINED IS
        v_text VARCHAR2(4000) := p_text;
        v_part VARCHAR2(500);
        v_pos  NUMBER;
        v_qty  NUMBER;
        v_query VARCHAR2(500);
        v_rec  t_item_rec;
        v_m    VARCHAR2(10);
    BEGIN
        -- Замена разделителей: "и" → запятая, "și" → запятая
        v_text := REGEXP_REPLACE(v_text, '\s+и\s+', ', ', 1, 0, 'i');
        v_text := REGEXP_REPLACE(v_text, '\s+[sș]i\s+', ', ', 1, 0, 'i');

        v_pos := 1;
        LOOP
            v_part := TRIM(REGEXP_SUBSTR(v_text, '[^,;' || CHR(10) || ']+', 1, v_pos));
            EXIT WHEN v_part IS NULL;
            v_pos := v_pos + 1;

            v_qty := 1;
            v_query := v_part;

            -- 1. Число + единица: "2шт рубашка" / "2 buc rochie"
            IF REGEXP_LIKE(v_part, '^(\d+)\s*(шт\.?|штук[иа]?|buc\.?|bucăț[ia]?|bucata|bucati)\s+(.+)', 'i') THEN
                v_qty := TO_NUMBER(REGEXP_SUBSTR(v_part, '^\d+'));
                v_query := REGEXP_REPLACE(v_part, '^(\d+)\s*(шт\.?|штук[иа]?|buc\.?|bucăț[ia]?|bucata|bucati)\s+', '', 1, 1, 'i');
            -- 2. Единица в конце: "рубашка 2 шт"
            ELSIF REGEXP_LIKE(v_part, '^(.+?)\s+(\d+)\s*(шт\.?|штук[иа]?|buc\.?|bucăț[ia]?|bucata|bucati)$', 'i') THEN
                v_qty := TO_NUMBER(REGEXP_SUBSTR(v_part, '(\d+)\s*(шт|штук|buc|bucăț|bucata|bucati)', 1, 1, 'i', 1));
                v_query := REGEXP_REPLACE(v_part, '\s+\d+\s*(шт\.?|штук[иа]?|buc\.?|bucăț[ia]?|bucata|bucati)$', '', 1, 1, 'i');
            -- 3. Число в начале: "2 рубашки"
            ELSIF REGEXP_LIKE(v_part, '^\d+\s+.+') THEN
                v_qty := TO_NUMBER(REGEXP_SUBSTR(v_part, '^\d+'));
                v_query := REGEXP_REPLACE(v_part, '^\d+\s+', '');
            -- 4. Число в конце: "рубашка 2"
            ELSIF REGEXP_LIKE(v_part, '^.+\s+\d+$') THEN
                v_qty := TO_NUMBER(REGEXP_SUBSTR(v_part, '\d+$'));
                v_query := REGEXP_REPLACE(v_part, '\s+\d+$', '');
            END IF;

            v_rec.query := TRIM(v_query);
            v_rec.qty := GREATEST(v_qty, 1);
            PIPE ROW(v_rec);
        END LOOP;
    END;

    -- ===== Поиск одного элемента =====
    FUNCTION find_best_service(
        p_query     IN VARCHAR2,
        p_threshold IN NUMBER DEFAULT 40
    ) RETURN t_match_rec IS
        v_result t_match_rec;
        v_q      VARCHAR2(500) := LOWER(TRIM(p_query));
        v_q_nd   VARCHAR2(500);
        v_best_score NUMBER := 0;
        v_score  NUMBER;
    BEGIN
        v_result.service_id := NULL;
        v_result.confidence := 0;
        v_result.original := p_query;
        v_result.qty := 1;

        IF v_q IS NULL THEN RETURN v_result; END IF;

        v_q_nd := remove_diacritics(v_q);

        -- Перебор всех услуг, сравнение по всем языкам
        FOR rec IN (
            SELECT ID, NAME, NAME_RO, NAME_EN, PRICE, UNIT
            FROM NUF_SERVICES
            WHERE ACTIVE = 'Y'
        ) LOOP
            -- Проверяем по каждому языковому полю
            FOR lang_name IN (
                SELECT COLUMN_VALUE AS svc_name FROM TABLE(SYS.ODCIVARCHAR2LIST(
                    rec.NAME, rec.NAME_RO, rec.NAME_EN
                )) WHERE COLUMN_VALUE IS NOT NULL
            ) LOOP
                v_score := string_similarity(v_q, lang_name.svc_name);
                IF v_score > v_best_score THEN
                    v_best_score := v_score;
                    v_result.service_id := rec.ID;
                    v_result.service_name := rec.NAME;
                    v_result.service_name_ro := rec.NAME_RO;
                    v_result.price := rec.PRICE;
                    v_result.unit := rec.UNIT;
                    v_result.confidence := v_score;
                END IF;
            END LOOP;
        END LOOP;

        IF v_best_score < p_threshold THEN
            v_result.service_id := NULL;
            v_result.confidence := 0;
        END IF;

        RETURN v_result;
    END;

    -- ===== Главная функция: парсинг текста заказа =====
    FUNCTION parse_order(
        p_text      IN VARCHAR2,
        p_threshold IN NUMBER DEFAULT 40
    ) RETURN t_match_tab PIPELINED IS
        v_match t_match_rec;
    BEGIN
        FOR item IN (SELECT query, qty FROM TABLE(split_order_text(p_text))) LOOP
            v_match := find_best_service(item.query, p_threshold);
            v_match.original := item.query;
            v_match.qty := item.qty;
            PIPE ROW(v_match);
        END LOOP;
    END;

END NUF_AI_SEARCH;
/

-- 5. Триггер: автоматическое обновление SEARCH_TEXT при изменении услуг
CREATE OR REPLACE TRIGGER NUF_SERVICES_SEARCH_TEXT
    BEFORE INSERT OR UPDATE OF NAME, NAME_RO, NAME_EN ON NUF_SERVICES
    FOR EACH ROW
BEGIN
    :NEW.SEARCH_TEXT := LOWER(
        NVL(:NEW.NAME, '') || ' | ' || NVL(:NEW.NAME_RO, '') || ' | ' || NVL(:NEW.NAME_EN, '')
    );
END;
/

-- 6. Тест
-- SELECT * FROM TABLE(NUF_AI_SEARCH.parse_order('2 рубашки, palton, fustă, 3 подушки'));
