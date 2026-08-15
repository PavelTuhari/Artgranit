-- ============================================================
-- Планограммы: прогнозирование заказов
--
-- Четыре алгоритма (реализация — models/plg_forecast.py):
--   sma          — скользящее / взвешенное скользящее среднее
--   ses          — простое экспоненциальное сглаживание (Brown)
--   holt_winters — тройное экспоненциальное сглаживание (тренд + сезонность)
--   promo_reg    — регрессия по базовой линии с promo-uplift и трафиком зоны
--
-- Модель = алгоритм + сохранённая конфигурация параметров (PLG_FCT_MODELS).
-- Одному алгоритму может соответствовать несколько моделей с разными
-- настройками — их точность сравнивается на backtest по MAPE / MAE / RMSE / bias.
-- Префикс объектов: PLG_
-- ============================================================

CREATE SEQUENCE PLG_FCT_ALGO_SEQ    START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_FCT_MODELS_SEQ  START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_FCT_RUNS_SEQ    START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_FCT_RESULTS_SEQ START WITH 1 INCREMENT BY 1 CACHE 1000;

-- ==================== Реестр алгоритмов прогноза ====================

CREATE TABLE PLG_FCT_ALGORITHMS (
  CODE          VARCHAR2(30)   NOT NULL,
  NAME_RU       VARCHAR2(200)  NOT NULL,
  NAME_RO       VARCHAR2(200),
  NAME_EN       VARCHAR2(200),
  DESCR_RU      VARCHAR2(1500),
  DESCR_RO      VARCHAR2(1500),
  DESCR_EN      VARCHAR2(1500),
  PARAMS_SCHEMA VARCHAR2(4000),          -- описание параметров для конфигуратора админки
  PARAMS_JSON   VARCHAR2(2000),          -- значения по умолчанию
  MIN_HISTORY   NUMBER         DEFAULT 28,  -- минимум дней истории для работы
  SORT_ORDER    NUMBER         DEFAULT 0,
  IS_ACTIVE     NUMBER(1)      DEFAULT 1,
  CONSTRAINT PK_PLG_FCT_ALGORITHMS PRIMARY KEY (CODE),
  CONSTRAINT CHK_PLG_FA_ACTIVE CHECK (IS_ACTIVE IN (0,1))
);

-- ==================== Модели (конфигурации алгоритмов) ====================

CREATE TABLE PLG_FCT_MODELS (
  ID              NUMBER        NOT NULL,
  CODE            VARCHAR2(40)  NOT NULL,
  ALGORITHM       VARCHAR2(30)  NOT NULL,
  NAME_RU         VARCHAR2(200) NOT NULL,
  NAME_RO         VARCHAR2(200),
  NAME_EN         VARCHAR2(200),
  PARAMS_JSON     VARCHAR2(2000),
  HORIZON_DAYS    NUMBER        DEFAULT 7,    -- горизонт прогноза
  SERVICE_LEVEL   NUMBER(5,2)   DEFAULT 95,   -- уровень сервиса для страхового запаса, %
  LEAD_TIME_DAYS  NUMBER        DEFAULT 2,    -- срок поставки по умолчанию
  ROUND_TO_PACK   NUMBER(1)     DEFAULT 1,    -- округлять заказ до кратности короба
  IS_ACTIVE       NUMBER(1)     DEFAULT 1,
  IS_DEFAULT      NUMBER(1)     DEFAULT 0,
  CREATED_BY      VARCHAR2(150),
  CREATED_AT      TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT      TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_FCT_MODELS PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_FM_CODE UNIQUE (CODE),
  CONSTRAINT FK_PLG_FM_ALGO FOREIGN KEY (ALGORITHM) REFERENCES PLG_FCT_ALGORITHMS(CODE),
  CONSTRAINT CHK_PLG_FM_ACTIVE  CHECK (IS_ACTIVE IN (0,1)),
  CONSTRAINT CHK_PLG_FM_DEFAULT CHECK (IS_DEFAULT IN (0,1)),
  CONSTRAINT CHK_PLG_FM_PACK    CHECK (ROUND_TO_PACK IN (0,1)),
  CONSTRAINT CHK_PLG_FM_SL      CHECK (SERVICE_LEVEL BETWEEN 50 AND 99.9),
  CONSTRAINT CHK_PLG_FM_HORIZON CHECK (HORIZON_DAYS BETWEEN 1 AND 90)
);
/

CREATE OR REPLACE TRIGGER PLG_FCT_MODELS_BI
  BEFORE INSERT ON PLG_FCT_MODELS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_FCT_MODELS_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER PLG_FCT_MODELS_BU
  BEFORE UPDATE ON PLG_FCT_MODELS FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

-- ==================== Прогоны прогноза ====================

CREATE TABLE PLG_FCT_RUNS (
  ID            NUMBER        NOT NULL,
  MODEL_ID      NUMBER        NOT NULL,
  DATASET_ID    NUMBER,
  STORE_ID      NUMBER,                       -- NULL = вся сеть набора
  RUN_MODE      VARCHAR2(20)  DEFAULT 'forecast',  -- forecast / backtest
  ORIGIN_DATE   DATE,                         -- точка отсчёта прогноза
  HORIZON_DAYS  NUMBER,
  STATUS        VARCHAR2(20)  DEFAULT 'running',
  STAGE         VARCHAR2(60),
  PROGRESS_PCT  NUMBER        DEFAULT 0,
  SERIES_COUNT  NUMBER        DEFAULT 0,      -- сколько пар «магазин × SKU» посчитано
  SKIPPED_COUNT NUMBER        DEFAULT 0,      -- пропущено из-за нехватки истории
  MAPE          NUMBER(10,4),
  MAE           NUMBER(14,4),
  RMSE          NUMBER(14,4),
  BIAS_PCT      NUMBER(10,4),
  ORDER_QTY_SUM NUMBER(16,3),
  DURATION_SEC  NUMBER,
  MESSAGE       VARCHAR2(2000),
  USERNAME      VARCHAR2(150),
  STARTED_AT    TIMESTAMP     DEFAULT SYSTIMESTAMP,
  FINISHED_AT   TIMESTAMP,
  CONSTRAINT PK_PLG_FCT_RUNS PRIMARY KEY (ID),
  CONSTRAINT FK_PLG_FR_MODEL FOREIGN KEY (MODEL_ID) REFERENCES PLG_FCT_MODELS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_FR_DS    FOREIGN KEY (DATASET_ID) REFERENCES PLG_DATASETS(ID) ON DELETE SET NULL,
  CONSTRAINT FK_PLG_FR_STORE FOREIGN KEY (STORE_ID) REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT CHK_PLG_FR_STATUS CHECK (STATUS IN ('running','done','failed','cancelled')),
  CONSTRAINT CHK_PLG_FR_MODE   CHECK (RUN_MODE IN ('forecast','backtest'))
);
/

CREATE OR REPLACE TRIGGER PLG_FCT_RUNS_BI
  BEFORE INSERT ON PLG_FCT_RUNS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_FCT_RUNS_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_PLG_FCT_RUNS_MODEL ON PLG_FCT_RUNS (MODEL_ID, STARTED_AT);

-- ==================== Результаты прогноза ====================

CREATE TABLE PLG_FCT_RESULTS (
  ID            NUMBER       NOT NULL,
  RUN_ID        NUMBER       NOT NULL,
  STORE_ID      NUMBER       NOT NULL,
  PRODUCT_ID    NUMBER       NOT NULL,
  FCT_DATE      DATE         NOT NULL,
  QTY_FORECAST  NUMBER(14,3),
  QTY_ACTUAL    NUMBER(14,3),               -- заполняется в режиме backtest
  ABS_ERROR     NUMBER(14,3),
  SAFETY_STOCK  NUMBER(14,3),
  STOCK_ON_HAND NUMBER(14,3),
  ORDER_QTY     NUMBER(14,3),               -- рекомендуемый заказ
  CONSTRAINT PK_PLG_FCT_RESULTS PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_FCT_RES UNIQUE (RUN_ID, STORE_ID, PRODUCT_ID, FCT_DATE),
  CONSTRAINT FK_PLG_FRS_RUN   FOREIGN KEY (RUN_ID) REFERENCES PLG_FCT_RUNS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_FRS_STORE FOREIGN KEY (STORE_ID) REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_FRS_PROD  FOREIGN KEY (PRODUCT_ID) REFERENCES PLG_PRODUCTS(ID) ON DELETE CASCADE
);

CREATE INDEX IX_PLG_FCT_RES_RUN ON PLG_FCT_RESULTS (RUN_ID, STORE_ID, PRODUCT_ID);

-- ==================== Представления ====================

-- Наборы данных со сводкой фактического наполнения
CREATE OR REPLACE VIEW V_PLG_DATASETS AS
SELECT
  d.ID, d.CODE, d.KIND, d.NAME_RU, d.NAME_RO, d.NAME_EN, d.DESCRIPTION,
  d.STATUS, d.SEED, d.IS_PROTECTED, d.CREATED_BY, d.CREATED_AT, d.FINISHED_AT,
  d.STORE_COUNT AS PLANNED_STORES, d.SKU_COUNT AS PLANNED_SKU, d.DAYS_DEPTH, d.ROWS_TOTAL,
  (SELECT COUNT(*) FROM PLG_STORES s WHERE s.DATASET_ID = d.ID)   AS ACTUAL_STORES,
  (SELECT COUNT(*) FROM PLG_PRODUCTS p WHERE p.DATASET_ID = d.ID) AS ACTUAL_SKU,
  (SELECT COUNT(*) FROM PLG_SALES_DAILY sd
     JOIN PLG_STORES s2 ON s2.ID = sd.STORE_ID WHERE s2.DATASET_ID = d.ID) AS SALES_ROWS,
  (SELECT MIN(sd.SALES_DATE) FROM PLG_SALES_DAILY sd
     JOIN PLG_STORES s3 ON s3.ID = sd.STORE_ID WHERE s3.DATASET_ID = d.ID) AS SALES_FROM,
  (SELECT MAX(sd.SALES_DATE) FROM PLG_SALES_DAILY sd
     JOIN PLG_STORES s4 ON s4.ID = sd.STORE_ID WHERE s4.DATASET_ID = d.ID) AS SALES_TO
FROM PLG_DATASETS d;

-- Прогоны генерации с контекстом набора и алгоритма
CREATE OR REPLACE VIEW V_PLG_GEN_RUNS AS
SELECT
  r.ID, r.DATASET_ID, d.CODE AS DATASET_CODE,
  d.NAME_RU AS DATASET_RU, d.NAME_RO AS DATASET_RO, d.NAME_EN AS DATASET_EN,
  r.ALGORITHM,
  NVL(a.NAME_RU, r.ALGORITHM) AS ALGORITHM_NAME_RU,
  NVL(a.NAME_RO, r.ALGORITHM) AS ALGORITHM_NAME_RO,
  NVL(a.NAME_EN, r.ALGORITHM) AS ALGORITHM_NAME_EN,
  r.PARAMS_JSON, r.STATUS, r.STAGE, r.PROGRESS_PCT, r.ROWS_WRITTEN,
  r.DURATION_SEC, r.MESSAGE, r.USERNAME, r.STARTED_AT, r.FINISHED_AT
FROM PLG_GEN_RUNS r
LEFT JOIN PLG_DATASETS d ON d.ID = r.DATASET_ID
LEFT JOIN PLG_GEN_ALGORITHMS a ON a.CODE = r.ALGORITHM;

-- Модели прогноза с алгоритмом и последним результатом точности
CREATE OR REPLACE VIEW V_PLG_FCT_MODELS AS
SELECT
  m.ID, m.CODE, m.ALGORITHM,
  a.NAME_RU AS ALGORITHM_NAME_RU, a.NAME_RO AS ALGORITHM_NAME_RO, a.NAME_EN AS ALGORITHM_NAME_EN,
  a.DESCR_RU AS ALGORITHM_DESCR_RU, a.DESCR_RO AS ALGORITHM_DESCR_RO, a.DESCR_EN AS ALGORITHM_DESCR_EN,
  a.PARAMS_SCHEMA, a.MIN_HISTORY,
  m.NAME_RU, m.NAME_RO, m.NAME_EN, m.PARAMS_JSON,
  m.HORIZON_DAYS, m.SERVICE_LEVEL, m.LEAD_TIME_DAYS, m.ROUND_TO_PACK,
  m.IS_ACTIVE, m.IS_DEFAULT, m.CREATED_BY, m.CREATED_AT, m.UPDATED_AT,
  (SELECT COUNT(*) FROM PLG_FCT_RUNS r WHERE r.MODEL_ID = m.ID) AS RUN_COUNT,
  last_run.ID       AS LAST_RUN_ID,
  last_run.STATUS   AS LAST_RUN_STATUS,
  last_run.RUN_MODE AS LAST_RUN_MODE,
  last_run.MAPE     AS LAST_MAPE,
  last_run.MAE      AS LAST_MAE,
  last_run.RMSE     AS LAST_RMSE,
  last_run.BIAS_PCT AS LAST_BIAS_PCT,
  last_run.STARTED_AT AS LAST_RUN_AT
FROM PLG_FCT_MODELS m
JOIN PLG_FCT_ALGORITHMS a ON a.CODE = m.ALGORITHM
LEFT JOIN (
  SELECT r2.* FROM PLG_FCT_RUNS r2
  WHERE r2.STARTED_AT = (SELECT MAX(r3.STARTED_AT) FROM PLG_FCT_RUNS r3 WHERE r3.MODEL_ID = r2.MODEL_ID)
) last_run ON last_run.MODEL_ID = m.ID;

-- Прогоны прогноза с контекстом модели и магазина
CREATE OR REPLACE VIEW V_PLG_FCT_RUNS AS
SELECT
  r.ID, r.MODEL_ID, m.CODE AS MODEL_CODE,
  m.NAME_RU AS MODEL_RU, m.NAME_RO AS MODEL_RO, m.NAME_EN AS MODEL_EN,
  m.ALGORITHM,
  a.NAME_RU AS ALGORITHM_NAME_RU, a.NAME_RO AS ALGORITHM_NAME_RO, a.NAME_EN AS ALGORITHM_NAME_EN,
  r.DATASET_ID, d.CODE AS DATASET_CODE,
  r.STORE_ID, s.CODE AS STORE_CODE,
  s.NAME_RU AS STORE_RU, s.NAME_RO AS STORE_RO, s.NAME_EN AS STORE_EN,
  r.RUN_MODE, r.ORIGIN_DATE, r.HORIZON_DAYS, r.STATUS, r.STAGE, r.PROGRESS_PCT,
  r.SERIES_COUNT, r.SKIPPED_COUNT, r.MAPE, r.MAE, r.RMSE, r.BIAS_PCT, r.ORDER_QTY_SUM,
  r.DURATION_SEC, r.MESSAGE, r.USERNAME, r.STARTED_AT, r.FINISHED_AT
FROM PLG_FCT_RUNS r
JOIN PLG_FCT_MODELS m ON m.ID = r.MODEL_ID
JOIN PLG_FCT_ALGORITHMS a ON a.CODE = m.ALGORITHM
LEFT JOIN PLG_DATASETS d ON d.ID = r.DATASET_ID
LEFT JOIN PLG_STORES s ON s.ID = r.STORE_ID;

-- Рекомендуемый заказ: свод по SKU за горизонт прогона
CREATE OR REPLACE VIEW V_PLG_ORDER_PROPOSAL AS
SELECT
  res.RUN_ID, res.STORE_ID, s.CODE AS STORE_CODE,
  s.NAME_RU AS STORE_RU, s.NAME_RO AS STORE_RO, s.NAME_EN AS STORE_EN,
  res.PRODUCT_ID, p.CODE AS PRODUCT_CODE,
  p.NAME_RU AS PRODUCT_RU, p.NAME_RO AS PRODUCT_RO, p.NAME_EN AS PRODUCT_EN,
  p.ABC_CLASS, p.ORDER_MULTIPLE, p.LEAD_TIME_DAYS, p.PRICE, p.CURRENCY,
  c.NAME_RU AS CATEGORY_RU, c.NAME_RO AS CATEGORY_RO, c.NAME_EN AS CATEGORY_EN,
  MIN(res.FCT_DATE) AS DATE_FROM,
  MAX(res.FCT_DATE) AS DATE_TO,
  ROUND(SUM(res.QTY_FORECAST), 3) AS QTY_FORECAST,
  ROUND(SUM(res.QTY_ACTUAL), 3)   AS QTY_ACTUAL,
  ROUND(MAX(res.SAFETY_STOCK), 3) AS SAFETY_STOCK,
  ROUND(MAX(res.STOCK_ON_HAND), 3) AS STOCK_ON_HAND,
  ROUND(SUM(res.ORDER_QTY), 3)    AS ORDER_QTY,
  ROUND(SUM(res.ORDER_QTY) * p.PRICE, 2) AS ORDER_AMOUNT
FROM PLG_FCT_RESULTS res
JOIN PLG_STORES s   ON s.ID = res.STORE_ID
JOIN PLG_PRODUCTS p ON p.ID = res.PRODUCT_ID
LEFT JOIN PLG_CATEGORIES c ON c.ID = p.CATEGORY_ID
GROUP BY res.RUN_ID, res.STORE_ID, s.CODE, s.NAME_RU, s.NAME_RO, s.NAME_EN,
         res.PRODUCT_ID, p.CODE, p.NAME_RU, p.NAME_RO, p.NAME_EN,
         p.ABC_CLASS, p.ORDER_MULTIPLE, p.LEAD_TIME_DAYS, p.PRICE, p.CURRENCY,
         c.NAME_RU, c.NAME_RO, c.NAME_EN;

-- ==================== Реестр алгоритмов прогноза ====================

INSERT INTO PLG_FCT_ALGORITHMS (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN,
                                PARAMS_SCHEMA, PARAMS_JSON, MIN_HISTORY, SORT_ORDER) VALUES
('sma', 'Скользящее среднее (SMA/WMA)', 'Media mobilă (SMA/WMA)', 'Moving average (SMA/WMA)',
 'Прогноз = среднее продаж за последние N дней. При weighted=1 свежие дни весят больше (линейные веса). Базовая линия отрасли: устойчив к шуму, но запаздывает на тренде и не видит сезонности.',
 'Prognoza = media vânzărilor din ultimele N zile. Cu weighted=1 zilele recente au pondere mai mare. Rezistent la zgomot, dar întârzie pe trend.',
 'Forecast equals the mean of the last N days. With weighted=1 recent days get linear weights. Robust to noise, but lags on trend and ignores seasonality.',
 '[{"key":"window","type":"int","min":3,"max":90,"default":14,"label_ru":"Окно, дней","label_ro":"Fereastră, zile","label_en":"Window, days"},{"key":"weighted","type":"bool","default":1,"label_ru":"Взвешенное (WMA)","label_ro":"Ponderat (WMA)","label_en":"Weighted (WMA)"},{"key":"exclude_oos","type":"bool","default":1,"label_ru":"Исключать дни out-of-stock","label_ro":"Exclude zilele fără stoc","label_en":"Exclude out-of-stock days"}]',
 '{"window": 14, "weighted": 1, "exclude_oos": 1}', 21, 1);

INSERT INTO PLG_FCT_ALGORITHMS (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN,
                                PARAMS_SCHEMA, PARAMS_JSON, MIN_HISTORY, SORT_ORDER) VALUES
('ses', 'Экспоненциальное сглаживание', 'Netezire exponențială', 'Exponential smoothing',
 'Простое экспоненциальное сглаживание: level = alpha × факт + (1 − alpha) × level. Чем выше alpha, тем быстрее модель реагирует на смену уровня спроса и тем чувствительнее к выбросам. Тренд и сезонность не моделируются.',
 'Netezire exponențială simplă: level = alpha × real + (1 − alpha) × level. Alpha mai mare — reacție mai rapidă la schimbări.',
 'Simple exponential smoothing: level = alpha × actual + (1 − alpha) × level. Higher alpha reacts faster to level shifts but is noisier.',
 '[{"key":"alpha","type":"float","min":0.01,"max":0.95,"step":0.01,"default":0.3,"label_ru":"Alpha (сглаживание уровня)","label_ro":"Alpha (nivel)","label_en":"Alpha (level smoothing)"},{"key":"exclude_oos","type":"bool","default":1,"label_ru":"Исключать дни out-of-stock","label_ro":"Exclude zilele fără stoc","label_en":"Exclude out-of-stock days"}]',
 '{"alpha": 0.3, "exclude_oos": 1}', 28, 2);

INSERT INTO PLG_FCT_ALGORITHMS (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN,
                                PARAMS_SCHEMA, PARAMS_JSON, MIN_HISTORY, SORT_ORDER) VALUES
('holt_winters', 'Holt-Winters (тренд + сезонность)', 'Holt-Winters (trend + sezonalitate)', 'Holt-Winters (trend + seasonality)',
 'Тройное экспоненциальное сглаживание: уровень (alpha), тренд (beta) и сезонный профиль (gamma) с периодом season (по умолчанию 7 дней — недельный профиль торговли). Самая точная из классических моделей при наличии стабильной недельной сезонности; требует минимум двух полных периодов истории.',
 'Netezire exponențială triplă: nivel (alpha), trend (beta) și profil sezonier (gamma) cu perioada season. Necesită minimum două perioade complete.',
 'Triple exponential smoothing: level (alpha), trend (beta) and seasonal profile (gamma) with the given season length. Needs at least two full seasons of history.',
 '[{"key":"alpha","type":"float","min":0.01,"max":0.95,"step":0.01,"default":0.3,"label_ru":"Alpha (уровень)","label_ro":"Alpha (nivel)","label_en":"Alpha (level)"},{"key":"beta","type":"float","min":0.0,"max":0.95,"step":0.01,"default":0.1,"label_ru":"Beta (тренд)","label_ro":"Beta (trend)","label_en":"Beta (trend)"},{"key":"gamma","type":"float","min":0.0,"max":0.95,"step":0.01,"default":0.2,"label_ru":"Gamma (сезонность)","label_ro":"Gamma (sezonalitate)","label_en":"Gamma (seasonality)"},{"key":"season","type":"int","min":2,"max":30,"default":7,"label_ru":"Период сезонности, дней","label_ro":"Perioada sezonieră, zile","label_en":"Season length, days"},{"key":"damped","type":"bool","default":1,"label_ru":"Затухающий тренд","label_ro":"Trend amortizat","label_en":"Damped trend"},{"key":"exclude_oos","type":"bool","default":1,"label_ru":"Исключать дни out-of-stock","label_ro":"Exclude zilele fără stoc","label_en":"Exclude out-of-stock days"}]',
 '{"alpha": 0.3, "beta": 0.1, "gamma": 0.2, "season": 7, "damped": 1, "exclude_oos": 1}', 42, 3);

INSERT INTO PLG_FCT_ALGORITHMS (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN,
                                PARAMS_SCHEMA, PARAMS_JSON, MIN_HISTORY, SORT_ORDER) VALUES
('promo_reg', 'Регрессия с promo-uplift', 'Regresie cu uplift promoțional', 'Promo-uplift regression',
 'Базовая линия строится по дням БЕЗ акций (медиана недельного профиля), затем умножается на коэффициенты: promo-аплифт, посчитанный по фактической истории акций этого SKU, и индекс проходимости зоны выкладки. Единственная модель, которая заранее учитывает ЗАПЛАНИРОВАННЫЕ акции из PLG_PROMOS.',
 'Linia de bază se calculează pe zilele fără promoții, apoi se înmulțește cu upliftul promoțional real al SKU-ului și indicele de trafic al zonei.',
 'The baseline is built from non-promo days (weekly-profile median), then multiplied by the SKU historical promo uplift and the zone traffic index. The only model that anticipates planned promotions from PLG_PROMOS.',
 '[{"key":"baseline_window","type":"int","min":14,"max":180,"default":56,"label_ru":"Окно базовой линии, дней","label_ro":"Fereastra liniei de bază, zile","label_en":"Baseline window, days"},{"key":"use_promo","type":"bool","default":1,"label_ru":"Учитывать плановые акции","label_ro":"Ia în calcul promoțiile planificate","label_en":"Use planned promotions"},{"key":"use_traffic","type":"bool","default":1,"label_ru":"Учитывать трафик зоны","label_ro":"Ia în calcul traficul zonei","label_en":"Use zone traffic"},{"key":"uplift_cap","type":"float","min":1.0,"max":6.0,"step":0.1,"default":3.5,"label_ru":"Ограничение аплифта","label_ro":"Plafon uplift","label_en":"Uplift cap"},{"key":"exclude_oos","type":"bool","default":1,"label_ru":"Исключать дни out-of-stock","label_ro":"Exclude zilele fără stoc","label_en":"Exclude out-of-stock days"}]',
 '{"baseline_window": 56, "use_promo": 1, "use_traffic": 1, "uplift_cap": 3.5, "exclude_oos": 1}', 35, 4);

COMMIT;
/

-- ==================== Модели по умолчанию (по одной на алгоритм) ====================

INSERT INTO PLG_FCT_MODELS (CODE, ALGORITHM, NAME_RU, NAME_RO, NAME_EN, PARAMS_JSON,
                            HORIZON_DAYS, SERVICE_LEVEL, LEAD_TIME_DAYS, IS_DEFAULT, CREATED_BY)
VALUES ('SMA-14', 'sma', 'Скользящее среднее, 14 дней', 'Media mobilă, 14 zile', 'Moving average, 14 days',
        '{"window": 14, "weighted": 1, "exclude_oos": 1}', 7, 95, 2, 0, 'system');

INSERT INTO PLG_FCT_MODELS (CODE, ALGORITHM, NAME_RU, NAME_RO, NAME_EN, PARAMS_JSON,
                            HORIZON_DAYS, SERVICE_LEVEL, LEAD_TIME_DAYS, IS_DEFAULT, CREATED_BY)
VALUES ('SES-03', 'ses', 'Экспоненциальное сглаживание, alpha 0.3', 'Netezire exponențială, alpha 0.3',
        'Exponential smoothing, alpha 0.3',
        '{"alpha": 0.3, "exclude_oos": 1}', 7, 95, 2, 0, 'system');

INSERT INTO PLG_FCT_MODELS (CODE, ALGORITHM, NAME_RU, NAME_RO, NAME_EN, PARAMS_JSON,
                            HORIZON_DAYS, SERVICE_LEVEL, LEAD_TIME_DAYS, IS_DEFAULT, CREATED_BY)
VALUES ('HW-W7', 'holt_winters', 'Holt-Winters, недельная сезонность', 'Holt-Winters, sezonalitate săptămânală',
        'Holt-Winters, weekly seasonality',
        '{"alpha": 0.3, "beta": 0.1, "gamma": 0.2, "season": 7, "damped": 1, "exclude_oos": 1}', 7, 97, 2, 1, 'system');

INSERT INTO PLG_FCT_MODELS (CODE, ALGORITHM, NAME_RU, NAME_RO, NAME_EN, PARAMS_JSON,
                            HORIZON_DAYS, SERVICE_LEVEL, LEAD_TIME_DAYS, IS_DEFAULT, CREATED_BY)
VALUES ('PROMO-REG', 'promo_reg', 'Регрессия с учётом акций', 'Regresie cu promoții', 'Promo-aware regression',
        '{"baseline_window": 56, "use_promo": 1, "use_traffic": 1, "uplift_cap": 3.5, "exclude_oos": 1}',
        7, 97, 2, 0, 'system');

COMMIT;
