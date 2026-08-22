-- ============================================================
-- PECO: реестр алгоритмов прогноза топлива и пути снабжения
--
-- Два дополнения к контуру автозаказа.
--
-- 1. РЕЕСТР АЛГОРИТМОВ. Прогноз спроса становится сменным: theta,
--    croston_sba, conformal, gbt (реализация — models/peco_forecast.py).
--    Алгоритмы сравниваются на одном backtest, результат сравнения
--    хранится в PECO_FCT_BACKTESTS — выбор модели должен опираться
--    на измерение, а не на предпочтение.
--
-- 2. ПУТИ СНАБЖЕНИЯ (PECO_SUPPLY_PATHS). Любая комбинация
--    «импорт / внутренний рынок ↔ своя или чужая нефтебаза ↔ АЗС»
--    описывается строкой справочника, а не веткой в коде.
--
--    Пути делятся на два вида (KIND), и это принципиально:
--      distribution  — чем закрыть станцию СЕГОДНЯ (остаток базы,
--                      прямая поставка с рынка). Плечо — часы и сутки.
--      replenishment — чем пополнить базу (импорт, рынок оптом).
--                      Плечо — недели.
--    Смешивать их нельзя: судно из Греции не спасёт станцию,
--    у которой топливо кончится завтра.
--
-- Расчёт: models/peco_sourcing.py (поток минимальной стоимости).
-- Префикс объектов: PECO_
-- ============================================================

-- ==================== Своя и чужая нефтебаза ====================

DECLARE
  PROCEDURE add_col(p_tab VARCHAR2, p_col VARCHAR2, p_def VARCHAR2) IS
    v_n NUMBER;
  BEGIN
    SELECT COUNT(*) INTO v_n FROM USER_TAB_COLUMNS
     WHERE TABLE_NAME = p_tab AND COLUMN_NAME = p_col;
    IF v_n = 0 THEN
      EXECUTE IMMEDIATE 'ALTER TABLE ' || p_tab || ' ADD (' || p_col || ' ' || p_def || ')';
    END IF;
  END;
BEGIN
  -- Чужая база отличается не «галочкой», а экономикой: за хранение
  -- и перевалку платится тариф, и он входит в стоимость литра
  add_col('PECO_DEPOTS', 'IS_OWN',            'NUMBER(1) DEFAULT 1');
  add_col('PECO_DEPOTS', 'OPERATOR_NAME',     'VARCHAR2(200)');
  add_col('PECO_DEPOTS', 'HANDLING_FEE_PER_L','NUMBER(10,4) DEFAULT 0');
  add_col('PECO_DEPOTS', 'THROUGHPUT_L_DAY',  'NUMBER(14,3)');
  add_col('PECO_DEPOTS', 'DELIVERY_LEAD_DAYS','NUMBER(5,2) DEFAULT 0.5');

  -- Чем считали и что получилось — рядом с заказом
  add_col('PECO_ORDER_RUNS', 'ALGORITHM',  'VARCHAR2(30)');
  add_col('PECO_ORDER_RUNS', 'MONEY_RATE', 'NUMBER(6,4)');
  add_col('PECO_ORDER_RUNS', 'PLAN_COST',  'NUMBER(18,2)');

  add_col('PECO_FUEL_ORDER_ITEMS', 'ALGORITHM',       'VARCHAR2(30)');
  add_col('PECO_FUEL_ORDER_ITEMS', 'FORECAST_DAILY_L','NUMBER(14,3)');
  add_col('PECO_FUEL_ORDER_ITEMS', 'SAFETY_L',        'NUMBER(14,3)');
  add_col('PECO_FUEL_ORDER_ITEMS', 'PATH_CODE',       'VARCHAR2(40)');
  add_col('PECO_FUEL_ORDER_ITEMS', 'COST_PER_L',      'NUMBER(10,4)');
END;
/

-- ==================== Реестр алгоритмов ====================

DECLARE
  v_n NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_n FROM USER_TABLES WHERE TABLE_NAME = 'PECO_FCT_ALGORITHMS';
  IF v_n = 0 THEN
    EXECUTE IMMEDIATE q'[
      CREATE TABLE PECO_FCT_ALGORITHMS (
        CODE        VARCHAR2(30)   NOT NULL,
        NAME_RU     VARCHAR2(200)  NOT NULL,
        NAME_RO     VARCHAR2(200),
        NAME_EN     VARCHAR2(200),
        DESCR_RU    VARCHAR2(2000),
        DESCR_RO    VARCHAR2(2000),
        DESCR_EN    VARCHAR2(2000),
        BEST_FOR_RU VARCHAR2(600),
        BEST_FOR_RO VARCHAR2(600),
        BEST_FOR_EN VARCHAR2(600),
        PARAMS_JSON VARCHAR2(1000),
        MIN_HISTORY NUMBER DEFAULT 28,
        SORT_ORDER  NUMBER DEFAULT 0,
        IS_ACTIVE   NUMBER(1) DEFAULT 1,
        CONSTRAINT PK_PECO_FCT_ALGO PRIMARY KEY (CODE),
        CONSTRAINT CK_PECO_FA_ACT CHECK (IS_ACTIVE IN (0,1))
      )]';
  END IF;

  SELECT COUNT(*) INTO v_n FROM USER_TABLES WHERE TABLE_NAME = 'PECO_SUPPLY_PATHS';
  IF v_n = 0 THEN
    EXECUTE IMMEDIATE 'CREATE SEQUENCE PECO_PATH_SEQ START WITH 1 INCREMENT BY 1 NOCACHE';
    EXECUTE IMMEDIATE q'[
      CREATE TABLE PECO_SUPPLY_PATHS (
        ID              NUMBER        NOT NULL,
        CODE            VARCHAR2(40)  NOT NULL,
        KIND            VARCHAR2(20)  DEFAULT 'distribution' NOT NULL,
        NAME_RU         VARCHAR2(200),
        NAME_RO         VARCHAR2(200),
        NAME_EN         VARCHAR2(200),
        SOURCE_CODE     VARCHAR2(20)  NOT NULL,
        SUPPLIER_ID     NUMBER,
        DEPOT_ID        NUMBER,
        STATION_ID      NUMBER,
        GRADE_CODE      VARCHAR2(10),
        LEAD_DAYS       NUMBER(6,2)   DEFAULT 1,
        PRICE_PER_L     NUMBER(10,4)  DEFAULT 0,
        TRANSPORT_PER_L NUMBER(10,4)  DEFAULT 0,
        HANDLING_PER_L  NUMBER(10,4)  DEFAULT 0,
        DUTY_PER_L      NUMBER(10,4)  DEFAULT 0,
        AVAILABLE_L     NUMBER(16,3)  DEFAULT 0,
        MIN_LOT_L       NUMBER(14,3)  DEFAULT 0,
        IS_ACTIVE       NUMBER(1)     DEFAULT 1,
        NOTE            VARCHAR2(600),
        CREATED_AT      TIMESTAMP     DEFAULT SYSTIMESTAMP,
        UPDATED_AT      TIMESTAMP     DEFAULT SYSTIMESTAMP,
        CONSTRAINT PK_PECO_SUPPLY_PATHS PRIMARY KEY (ID),
        CONSTRAINT UQ_PECO_PATH_CODE UNIQUE (CODE),
        CONSTRAINT FK_PECO_PATH_SRC FOREIGN KEY (SOURCE_CODE) REFERENCES PECO_REF_SUPPLY_SOURCES (CODE),
        CONSTRAINT FK_PECO_PATH_SUP FOREIGN KEY (SUPPLIER_ID) REFERENCES PECO_FUEL_SUPPLIERS (ID),
        CONSTRAINT FK_PECO_PATH_DEP FOREIGN KEY (DEPOT_ID)    REFERENCES PECO_DEPOTS (ID),
        CONSTRAINT FK_PECO_PATH_ST  FOREIGN KEY (STATION_ID)  REFERENCES PECO_STATIONS (ID),
        CONSTRAINT FK_PECO_PATH_GR  FOREIGN KEY (GRADE_CODE)  REFERENCES PECO_REF_FUEL_GRADES (CODE),
        CONSTRAINT CK_PECO_PATH_KIND CHECK (KIND IN ('distribution','replenishment')),
        CONSTRAINT CK_PECO_PATH_ACT  CHECK (IS_ACTIVE IN (0,1))
      )]';
    EXECUTE IMMEDIATE q'[
      CREATE OR REPLACE TRIGGER PECO_SUPPLY_PATHS_BI
        BEFORE INSERT ON PECO_SUPPLY_PATHS FOR EACH ROW
        WHEN (NEW.ID IS NULL)
      BEGIN
        :NEW.ID := PECO_PATH_SEQ.NEXTVAL;
      END;]';
  END IF;

  SELECT COUNT(*) INTO v_n FROM USER_TABLES WHERE TABLE_NAME = 'PECO_FCT_BACKTESTS';
  IF v_n = 0 THEN
    EXECUTE IMMEDIATE 'CREATE SEQUENCE PECO_BT_SEQ START WITH 1 INCREMENT BY 1 NOCACHE';
    EXECUTE IMMEDIATE q'[
      CREATE TABLE PECO_FCT_BACKTESTS (
        ID          NUMBER        NOT NULL,
        ALGORITHM   VARCHAR2(30)  NOT NULL,
        GRADE_CODE  VARCHAR2(10),
        HORIZON     NUMBER        DEFAULT 3,
        FOLDS       NUMBER,
        TANK_COUNT  NUMBER,
        MAPE        NUMBER(10,4),
        MAE         NUMBER(14,4),
        RMSE        NUMBER(14,4),
        BIAS_PCT    NUMBER(10,4),
        DURATION_SEC NUMBER,
        USERNAME    VARCHAR2(150),
        CREATED_AT  TIMESTAMP     DEFAULT SYSTIMESTAMP,
        CONSTRAINT PK_PECO_FCT_BT PRIMARY KEY (ID)
      )]';
    EXECUTE IMMEDIATE q'[
      CREATE OR REPLACE TRIGGER PECO_FCT_BACKTESTS_BI
        BEFORE INSERT ON PECO_FCT_BACKTESTS FOR EACH ROW
        WHEN (NEW.ID IS NULL)
      BEGIN
        :NEW.ID := PECO_BT_SEQ.NEXTVAL;
      END;]';
  END IF;
END;
/

-- ==================== Наполнение реестра алгоритмов ====================

MERGE INTO PECO_FCT_ALGORITHMS t USING (
  SELECT 'theta' CODE,
    'Theta-метод (победитель M3)' RU, 'Metoda Theta (câștigător M3)' RO, 'Theta method (M3 winner)' EN,
    'Ряд раскладывается на две тета-линии: чистый линейный тренд (долгая память) и усиленную кривизну (короткая память), которая сглаживается экспоненциально. Прогноз — среднее двух линий с затухающим трендом. Затухание обязательно: у резервуара есть физический потолок, и переоценка тренда сразу превращается в перелив.' DRU,
    'Seria se descompune în două linii theta: trend liniar și curbură amplificată, netezită exponențial.' DRO,
    'The series is split into two theta lines: a linear trend and an amplified curvature smoothed exponentially.' DEN,
    'Стабильный поток городской и трассовой АЗС: А-92, А-95, дизель с ровным недельным ритмом.' BRU,
    'Flux stabil al stațiilor urbane și de traseu.' BRO,
    'Stable urban and highway station flow.' BEN,
    '{"alpha": 0.3, "damped": 0.92, "use_profile": 1}' PJ, 28 MH, 1 SRT FROM dual
  UNION ALL SELECT 'croston_sba',
    'Croston + SBA (перемежающийся спрос)', 'Croston + SBA (cerere intermitentă)', 'Croston + SBA (intermittent demand)',
    'Размер продажи и интервал между ненулевыми днями сглаживаются ОТДЕЛЬНО, прогноз = размер / интервал. Поправка Syntetos-Boylan снимает известное смещение Croston вверх (множитель 1 − alpha/2): без неё медленные позиции систематически перезаказываются.',
    'Mărimea vânzării și intervalul dintre zilele nenule se netezesc separat.',
    'Sale size and the interval between non-zero days are smoothed separately.',
    'Медленные грейды: А-98 на сельской станции, премиальный дизель, редкие продажи три дня из семи.',
    'Sortimente lente: A-98 la stații rurale, motorină premium.',
    'Slow grades: A-98 at rural stations, premium diesel.',
    '{"alpha": 0.15, "sba": 1}', 21, 2 FROM dual
  UNION ALL SELECT 'conformal',
    'Конформный запас (без гипотезы нормальности)', 'Rezervă conformală (fără ipoteza normalității)', 'Conformal safety stock (distribution-free)',
    'Страховой запас берётся не из z-квантиля нормального распределения, а из эмпирического квантиля ошибок скользящего backtest с конечно-выборочной поправкой. На синтетике с тяжёлым правым хвостом при заявленных 99 % нормальное приближение давало 93.2 % реального покрытия, конформное — 97.8 %.',
    'Rezerva se ia din cuantila empirică a erorilor, nu din cuantila normală.',
    'The buffer comes from an empirical error quantile, not a Gaussian z-score.',
    'Станции с тяжёлым правым хвостом спроса: транзитные трассы, соседство с закрывающимся конкурентом, праздничные пики.',
    'Stații cu coadă grea a cererii: trasee de tranzit, vârfuri de sărbători.',
    'Stations with a heavy right tail: transit highways, holiday peaks.',
    '{"alpha": 0.3, "coverage": 0.99, "protect_days": 2}', 35, 3 FROM dual
  UNION ALL SELECT 'gbt',
    'Градиентный бустинг (деревья по признакам)', 'Gradient boosting (arbori pe caracteristici)', 'Gradient boosting (feature trees)',
    'Деревья глубины 3 на квадратичной ошибке по календарным и лаговым признакам: день недели, выходной, лаги 1/7/14, скользящие средние 7/28, тренд. Ловит взаимодействия, недоступные сглаживанию: «пятница после недели роста» ведёт себя иначе, чем просто пятница. Прогноз рекурсивный, поэтому горизонт ограничен неделей.',
    'Arbori de adâncime 3 pe caracteristici calendaristice și de lag.',
    'Depth-3 trees over calendar and lag features.',
    'Станции со сложным профилем: рядом с рынком или стадионом, где день недели взаимодействует с уровнем спроса.',
    'Stații cu profil complex, unde ziua interacționează cu nivelul cererii.',
    'Stations with a complex profile where weekday interacts with demand level.',
    '{"rounds": 60, "depth": 3, "lr": 0.1, "min_history": 30}', 45, 4 FROM dual
) s ON (t.CODE = s.CODE)
WHEN MATCHED THEN UPDATE SET NAME_RU = s.RU, NAME_RO = s.RO, NAME_EN = s.EN,
     DESCR_RU = s.DRU, DESCR_RO = s.DRO, DESCR_EN = s.DEN,
     BEST_FOR_RU = s.BRU, BEST_FOR_RO = s.BRO, BEST_FOR_EN = s.BEN,
     PARAMS_JSON = s.PJ, MIN_HISTORY = s.MH, SORT_ORDER = s.SRT
WHEN NOT MATCHED THEN INSERT (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO,
     DESCR_EN, BEST_FOR_RU, BEST_FOR_RO, BEST_FOR_EN, PARAMS_JSON, MIN_HISTORY, SORT_ORDER)
     VALUES (s.CODE, s.RU, s.RO, s.EN, s.DRU, s.DRO, s.DEN, s.BRU, s.BRO, s.BEN,
             s.PJ, s.MH, s.SRT);

COMMIT;

-- ==================== Представления ====================

CREATE OR REPLACE VIEW V_PECO_SUPPLY_PATHS AS
SELECT p.ID, p.CODE, p.KIND,
       p.NAME_RU, p.NAME_RO, p.NAME_EN,
       p.SOURCE_CODE,
       src.NAME_RU AS SOURCE_NAME_RU, src.NAME_RO AS SOURCE_NAME_RO,
       src.NAME_EN AS SOURCE_NAME_EN, src.IS_IMPORT,
       p.SUPPLIER_ID, sup.NAME AS SUPPLIER_NAME,
       p.DEPOT_ID, d.NAME AS DEPOT_NAME, d.IS_OWN AS DEPOT_IS_OWN,
       d.OPERATOR_NAME AS DEPOT_OPERATOR, d.DELIVERY_LEAD_DAYS,
       p.STATION_ID, st.NAME AS STATION_NAME,
       p.GRADE_CODE, g.NAME AS GRADE_NAME, g.COLOR AS GRADE_COLOR,
       p.LEAD_DAYS, p.PRICE_PER_L, p.TRANSPORT_PER_L, p.HANDLING_PER_L,
       p.DUTY_PER_L, p.AVAILABLE_L, p.MIN_LOT_L, p.IS_ACTIVE, p.NOTE,
       ROUND(p.PRICE_PER_L + p.TRANSPORT_PER_L + p.HANDLING_PER_L + p.DUTY_PER_L, 4)
         AS COST_PER_L_BASE
  FROM PECO_SUPPLY_PATHS p
  JOIN PECO_REF_SUPPLY_SOURCES src ON src.CODE = p.SOURCE_CODE
  LEFT JOIN PECO_FUEL_SUPPLIERS sup ON sup.ID = p.SUPPLIER_ID
  LEFT JOIN PECO_DEPOTS d           ON d.ID = p.DEPOT_ID
  LEFT JOIN PECO_STATIONS st        ON st.ID = p.STATION_ID
  LEFT JOIN PECO_REF_FUEL_GRADES g  ON g.CODE = p.GRADE_CODE;

CREATE OR REPLACE VIEW V_PECO_FCT_BACKTESTS AS
SELECT b.ID, b.ALGORITHM,
       a.NAME_RU AS ALGO_NAME_RU, a.NAME_RO AS ALGO_NAME_RO, a.NAME_EN AS ALGO_NAME_EN,
       a.BEST_FOR_RU, a.BEST_FOR_RO, a.BEST_FOR_EN,
       b.GRADE_CODE, g.NAME AS GRADE_NAME, g.COLOR AS GRADE_COLOR,
       b.HORIZON, b.FOLDS, b.TANK_COUNT, b.MAPE, b.MAE, b.RMSE, b.BIAS_PCT,
       b.DURATION_SEC, b.USERNAME, b.CREATED_AT
  FROM PECO_FCT_BACKTESTS b
  LEFT JOIN PECO_FCT_ALGORITHMS a  ON a.CODE = b.ALGORITHM
  LEFT JOIN PECO_REF_FUEL_GRADES g ON g.CODE = b.GRADE_CODE;
