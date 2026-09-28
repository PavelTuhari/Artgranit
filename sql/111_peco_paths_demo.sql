-- ============================================================
-- PECO: демонстрационные пути снабжения и чужая нефтебаза
--
-- Здесь заводятся ВСЕ комбинации, ради которых строился контур:
--
--   развозка сегодня      импорт/рынок → база
--   (distribution)        (replenishment)
--   ─────────────────     ────────────────────
--   своя НБ    → АЗС      импорт RO   → своя НБ
--   чужая НБ   → АЗС      импорт GR   → чужая НБ
--   рынок      → АЗС      рынок опт   → своя НБ
--                         рынок опт   → чужая НБ
--
-- Цены и тарифы — демонстрационные ориентиры для показа механики,
-- а не рыночные котировки: реальные подставляются в справочник путей
-- из контрактов.
-- ============================================================

-- ==================== Чужая нефтебаза ====================

DECLARE
  v_n NUMBER;
  v_id NUMBER;
BEGIN
  -- Своя база: тариф перевалки внутренний, плечо развозки полдня
  UPDATE PECO_DEPOTS
     SET IS_OWN = 1, OPERATOR_NAME = 'Собственная служба',
         HANDLING_FEE_PER_L = 0.12, THROUGHPUT_L_DAY = 220000,
         DELIVERY_LEAD_DAYS = 0.5
   WHERE CODE = 'NB-01';

  SELECT COUNT(*) INTO v_n FROM PECO_DEPOTS WHERE CODE = 'NB-3P';
  IF v_n = 0 THEN
    INSERT INTO PECO_DEPOTS (CODE, NAME, ADDRESS, LAT, LON, LOAD_BAYS,
                             IS_OWN, OPERATOR_NAME, HANDLING_FEE_PER_L,
                             THROUGHPUT_L_DAY, DELIVERY_LEAD_DAYS)
    VALUES ('NB-3P', 'Нефтебаза Бэлць (партнёрская)', 'Бэлць, ул. Индустриальная, 12',
            47.7402, 27.9581, 2, 0, 'Nord-Petrol SRL', 0.48, 90000, 0.8);
    SELECT ID INTO v_id FROM PECO_DEPOTS WHERE CODE = 'NB-3P';
    -- Хранение на чужой базе обычно скромнее: платим за объём
    INSERT INTO PECO_DEPOT_TANKS (DEPOT_ID, GRADE_CODE, CODE, CAPACITY_L, CURRENT_L, MIN_STOCK_L)
      VALUES (v_id, 'A95', 'B3P-T-A95', 180000, 96000, 20000);
    INSERT INTO PECO_DEPOT_TANKS (DEPOT_ID, GRADE_CODE, CODE, CAPACITY_L, CURRENT_L, MIN_STOCK_L)
      VALUES (v_id, 'DIESEL', 'B3P-T-DIESEL', 200000, 88000, 25000);
    INSERT INTO PECO_DEPOT_TANKS (DEPOT_ID, GRADE_CODE, CODE, CAPACITY_L, CURRENT_L, MIN_STOCK_L)
      VALUES (v_id, 'A92', 'B3P-T-A92', 120000, 51000, 15000);
  END IF;
  COMMIT;
END;
/

-- ==================== Пути снабжения ====================

DECLARE
  v_own NUMBER;
  v_3p  NUMBER;

  PROCEDURE upsert_path(
      p_code VARCHAR2, p_kind VARCHAR2, p_ru VARCHAR2, p_ro VARCHAR2, p_en VARCHAR2,
      p_src VARCHAR2, p_depot NUMBER, p_grade VARCHAR2, p_lead NUMBER,
      p_price NUMBER, p_transport NUMBER, p_handling NUMBER, p_duty NUMBER,
      p_avail NUMBER, p_minlot NUMBER, p_note VARCHAR2) IS
  BEGIN
    MERGE INTO PECO_SUPPLY_PATHS t
    USING (SELECT p_code AS CODE FROM dual) s ON (t.CODE = s.CODE)
    WHEN MATCHED THEN UPDATE SET KIND = p_kind, NAME_RU = p_ru, NAME_RO = p_ro,
         NAME_EN = p_en, SOURCE_CODE = p_src, DEPOT_ID = p_depot, GRADE_CODE = p_grade,
         LEAD_DAYS = p_lead, PRICE_PER_L = p_price, TRANSPORT_PER_L = p_transport,
         HANDLING_PER_L = p_handling, DUTY_PER_L = p_duty, AVAILABLE_L = p_avail,
         MIN_LOT_L = p_minlot, NOTE = p_note, UPDATED_AT = SYSTIMESTAMP
    WHEN NOT MATCHED THEN INSERT (CODE, KIND, NAME_RU, NAME_RO, NAME_EN, SOURCE_CODE,
         DEPOT_ID, GRADE_CODE, LEAD_DAYS, PRICE_PER_L, TRANSPORT_PER_L, HANDLING_PER_L,
         DUTY_PER_L, AVAILABLE_L, MIN_LOT_L, NOTE)
         VALUES (p_code, p_kind, p_ru, p_ro, p_en, p_src, p_depot, p_grade, p_lead,
                 p_price, p_transport, p_handling, p_duty, p_avail, p_minlot, p_note);
  END;
BEGIN
  SELECT ID INTO v_own FROM PECO_DEPOTS WHERE CODE = 'NB-01';
  BEGIN
    SELECT ID INTO v_3p FROM PECO_DEPOTS WHERE CODE = 'NB-3P';
  EXCEPTION WHEN NO_DATA_FOUND THEN v_3p := NULL;
  END;

  FOR g IN (SELECT CODE, NAME FROM PECO_REF_FUEL_GRADES ORDER BY SORT_ORDER) LOOP
    -- ---------- Развозка: чем закрыть станцию сегодня ----------
    upsert_path('OWN-' || g.CODE, 'distribution',
      'Своя нефтебаза → АЗС (' || g.NAME || ')',
      'Depozit propriu → stație', 'Own depot → station',
      'depot', v_own, g.CODE, 0.5,
      CASE g.CODE WHEN 'A92' THEN 21.10 WHEN 'A95' THEN 21.60
                  WHEN 'A98' THEN 23.40 ELSE 20.90 END,
      0.30, 0.12, 0, 0, 2000,
      'Остаток своей базы, плечо развозки полдня');

    IF v_3p IS NOT NULL AND g.CODE IN ('A92', 'A95', 'DIESEL') THEN
      upsert_path('3P-' || g.CODE, 'distribution',
        'Партнёрская нефтебаза → АЗС (' || g.NAME || ')',
        'Depozit partener → stație', 'Partner depot → station',
        'depot', v_3p, g.CODE, 0.8,
        CASE g.CODE WHEN 'A92' THEN 21.10 WHEN 'A95' THEN 21.60 ELSE 20.90 END,
        0.42, 0.48, 0, 0, 2000,
        'Хранение на чужой базе: перевалка по тарифу оператора');
    END IF;

    upsert_path('MKT-DIRECT-' || g.CODE, 'distribution',
      'Внутренний рынок → АЗС напрямую (' || g.NAME || ')',
      'Piața internă → stație direct', 'Domestic market → station direct',
      'market', NULL, g.CODE, 1.0,
      CASE g.CODE WHEN 'A92' THEN 22.20 WHEN 'A95' THEN 22.60
                  WHEN 'A98' THEN 24.50 ELSE 21.90 END,
      0.62, 0, 0, 0, 5000,
      'Без перевалки: дороже литр, но приезжает за сутки');

    -- ---------- Пополнение баз ----------
    upsert_path('IMP-RO-' || g.CODE, 'replenishment',
      'Импорт (Румыния) → своя нефтебаза (' || g.NAME || ')',
      'Import (România) → depozit propriu', 'Import (Romania) → own depot',
      'import', v_own, g.CODE, 9,
      CASE g.CODE WHEN 'A92' THEN 19.40 WHEN 'A95' THEN 19.85
                  WHEN 'A98' THEN 21.60 ELSE 19.10 END,
      0.35, 0.12, 1.10, 0, 150000,
      'Дешёвый литр, плечо девять суток, крупная партия');

    IF v_3p IS NOT NULL AND g.CODE IN ('A92', 'A95', 'DIESEL') THEN
      upsert_path('IMP-GR-' || g.CODE, 'replenishment',
        'Импорт (Греция) → партнёрская нефтебаза (' || g.NAME || ')',
        'Import (Grecia) → depozit partener', 'Import (Greece) → partner depot',
        'import', v_3p, g.CODE, 13,
        CASE g.CODE WHEN 'A92' THEN 18.90 WHEN 'A95' THEN 19.20 ELSE 18.70 END,
        0.55, 0.48, 1.10, 0, 200000,
        'Самый дешёвый литр, самое длинное плечо и перевалка по тарифу');
    END IF;

    upsert_path('MKT-BULK-' || g.CODE, 'replenishment',
      'Внутренний рынок оптом → своя нефтебаза (' || g.NAME || ')',
      'Piața internă en-gros → depozit propriu', 'Domestic market bulk → own depot',
      'market', v_own, g.CODE, 2,
      CASE g.CODE WHEN 'A92' THEN 21.70 WHEN 'A95' THEN 22.10
                  WHEN 'A98' THEN 23.80 ELSE 21.40 END,
      0.30, 0.12, 0, 0, 20000,
      'Дороже импорта, но приезжает за двое суток — закрывает провал');

    IF v_3p IS NOT NULL AND g.CODE IN ('A92', 'A95', 'DIESEL') THEN
      -- Без этого пути партнёрская база закрывается ТОЛЬКО импортом
      -- с минимальной партией 200 тысяч литров, и её потребность в
      -- 60-100 тысяч остаётся непокрытой: мелкую срочную потребность
      -- нечем взять. На проверке ровно так и получилось — три строки
      -- «нет источника» при живом внутреннем рынке.
      upsert_path('MKT-BULK-3P-' || g.CODE, 'replenishment',
        'Внутренний рынок оптом → партнёрская нефтебаза (' || g.NAME || ')',
        'Piața internă en-gros → depozit partener',
        'Domestic market bulk → partner depot',
        'market', v_3p, g.CODE, 2,
        CASE g.CODE WHEN 'A92' THEN 21.70 WHEN 'A95' THEN 22.10 ELSE 21.40 END,
        0.45, 0.48, 0, 0, 20000,
        'Тот же рынок, но с перевалкой по тарифу партнёра');
    END IF;
  END LOOP;
  COMMIT;
END;
/

-- ==================== Доступные объёмы ====================
--
-- Для путей развозки «доступно» — это фактический остаток базы сверх
-- неснижаемого. Пересчитывается при каждом прогоне автозаказа,
-- здесь ставится стартовое значение.

UPDATE PECO_SUPPLY_PATHS p
   SET AVAILABLE_L = NVL((SELECT GREATEST(dt.CURRENT_L - dt.MIN_STOCK_L, 0)
                            FROM PECO_DEPOT_TANKS dt
                           WHERE dt.DEPOT_ID = p.DEPOT_ID
                             AND dt.GRADE_CODE = p.GRADE_CODE), 0)
 WHERE p.KIND = 'distribution' AND p.DEPOT_ID IS NOT NULL;

-- Прямая поставка с рынка: суточный лимит поставщика
UPDATE PECO_SUPPLY_PATHS SET AVAILABLE_L = 60000
 WHERE KIND = 'distribution' AND DEPOT_ID IS NULL;

-- Пополнение: AVAILABLE_L — это объём, который может отгрузить ПОСТАВЩИК,
-- а не свободная ёмкость базы.
--
-- Сначала здесь стояла именно ёмкость, и это была ошибка модели: ограничение
-- ёмкости принадлежит стороне ПОТРЕБНОСТИ (сколько влезет в базу), а не
-- стороне источника (сколько готов отгрузить импортёр). Из-за подмены
-- импорт с минимальной партией 150 тысяч отсекался всякий раз, когда база
-- была заполнена больше чем наполовину, — то есть почти всегда.
-- Ёмкость теперь считается в models/peco_plan.py:depot_demands(),
-- причём на МОМЕНТ ПРИХОДА партии: пока судно идёт, база продолжает
-- отгружать, и места становится больше.

UPDATE PECO_SUPPLY_PATHS SET AVAILABLE_L = 600000
 WHERE KIND = 'replenishment' AND SOURCE_CODE = 'import';

UPDATE PECO_SUPPLY_PATHS SET AVAILABLE_L = 250000
 WHERE KIND = 'replenishment' AND SOURCE_CODE = 'market';

COMMIT;
