-- ============================================================
-- Планограммы: ИИ-мониторинг продаж и корректировка автозаказа
--
-- Три контура в одном файле, потому что они замкнуты друг на друга:
--
--   1. СИГНАЛЫ (PLG_AI_SIGNALS) — детекторы находят аномалии продаж:
--      риск out-of-stock, всплеск/провал спроса, риск списаний фреша,
--      дрейф смещения модели прогноза, мёртвый запас. Каждый сигнал —
--      строка с фактом, базой сравнения и трёхъязычным сообщением.
--
--   2. ПРИЗНАКИ (PLG_AI_FEATURES) — витрина данных по каждой паре
--      «магазин × SKU»: уровни спроса, волатильность, недельный подъём,
--      промо-аплифт, дни OOS, доля списаний, ABC/XYZ. Это тот самый
--      «массив данных для улучшения качества заказа»: он выгружается
--      наружу (CSV/JSON) для обучения моделей и одновременно объясняет
--      человеку, почему система считает так, а не иначе.
--
--   3. КОРРЕКТИРОВКИ (PLG_ORDER_ADJUSTMENTS) — правки автозаказа «на лету».
--      Рекомендация модели не перезаписывается никогда: рядом хранится
--      человеческое решение с причиной. Расхождение этих двух колонок —
--      главный обучающий сигнал будущим моделям: где человек системно
--      правит машину, там модель чего-то не видит.
--
-- Расчёты: models/plg_ai_monitor.py. Префикс объектов: PLG_
-- ============================================================

CREATE SEQUENCE PLG_AI_RUNS_SEQ    START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_AI_SIGNALS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100;
CREATE SEQUENCE PLG_AI_FEAT_SEQ    START WITH 1 INCREMENT BY 1 CACHE 1000;
CREATE SEQUENCE PLG_ORD_ADJ_SEQ    START WITH 1 INCREMENT BY 1 CACHE 100;

-- ==================== Прогоны мониторинга ====================

CREATE TABLE PLG_AI_RUNS (
  ID             NUMBER        NOT NULL,
  DATASET_ID     NUMBER,
  STORE_ID       NUMBER,                          -- NULL = вся сеть
  STATUS         VARCHAR2(20)  DEFAULT 'running', -- running / done / failed / cancelled
  STAGE          VARCHAR2(60),
  PROGRESS_PCT   NUMBER        DEFAULT 0,
  SIGNAL_COUNT   NUMBER        DEFAULT 0,
  FEATURE_COUNT  NUMBER        DEFAULT 0,
  DURATION_SEC   NUMBER,
  MESSAGE        VARCHAR2(2000),
  USERNAME       VARCHAR2(150),
  STARTED_AT     TIMESTAMP     DEFAULT SYSTIMESTAMP,
  FINISHED_AT    TIMESTAMP,
  CONSTRAINT PK_PLG_AI_RUNS PRIMARY KEY (ID),
  CONSTRAINT FK_PLG_AIR_DS    FOREIGN KEY (DATASET_ID) REFERENCES PLG_DATASETS(ID) ON DELETE SET NULL,
  CONSTRAINT FK_PLG_AIR_STORE FOREIGN KEY (STORE_ID)   REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT CHK_PLG_AIR_STATUS CHECK (STATUS IN ('running','done','failed','cancelled'))
);
/

CREATE OR REPLACE TRIGGER PLG_AI_RUNS_BI
  BEFORE INSERT ON PLG_AI_RUNS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_AI_RUNS_SEQ.NEXTVAL;
END;
/

-- ==================== Сигналы детекторов ====================

CREATE TABLE PLG_AI_SIGNALS (
  ID             NUMBER        NOT NULL,
  RUN_ID         NUMBER        NOT NULL,
  SIGNAL_TYPE    VARCHAR2(30)  NOT NULL,   -- oos_risk / spike / drop / waste_risk / bias_drift / dead_stock
  SEVERITY       VARCHAR2(10)  DEFAULT 'warn',   -- info / warn / crit
  STORE_ID       NUMBER        NOT NULL,
  PRODUCT_ID     NUMBER,
  CATEGORY_ID    NUMBER,
  METRIC_VALUE   NUMBER(16,4),             -- фактическое значение
  BASELINE_VALUE NUMBER(16,4),             -- база сравнения
  DELTA_PCT      NUMBER(10,2),             -- отклонение, %
  MESSAGE_RU     VARCHAR2(600),
  MESSAGE_RO     VARCHAR2(600),
  MESSAGE_EN     VARCHAR2(600),
  ACTION_HINT    VARCHAR2(30),             -- раздел модуля, куда вести из сигнала
  STATUS         VARCHAR2(20)  DEFAULT 'new',    -- new / ack / resolved
  ACK_BY         VARCHAR2(150),
  ACK_AT         TIMESTAMP,
  CREATED_AT     TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_AI_SIGNALS PRIMARY KEY (ID),
  CONSTRAINT FK_PLG_AIS_RUN   FOREIGN KEY (RUN_ID)     REFERENCES PLG_AI_RUNS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_AIS_STORE FOREIGN KEY (STORE_ID)   REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_AIS_PROD  FOREIGN KEY (PRODUCT_ID) REFERENCES PLG_PRODUCTS(ID) ON DELETE CASCADE,
  CONSTRAINT CHK_PLG_AIS_TYPE CHECK (SIGNAL_TYPE IN
    ('oos_risk','spike','drop','waste_risk','bias_drift','dead_stock')),
  CONSTRAINT CHK_PLG_AIS_SEV  CHECK (SEVERITY IN ('info','warn','crit')),
  CONSTRAINT CHK_PLG_AIS_ST   CHECK (STATUS IN ('new','ack','resolved'))
);
/

CREATE OR REPLACE TRIGGER PLG_AI_SIGNALS_BI
  BEFORE INSERT ON PLG_AI_SIGNALS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_AI_SIGNALS_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_PLG_AI_SIG_RUN   ON PLG_AI_SIGNALS (RUN_ID, SIGNAL_TYPE);
CREATE INDEX IX_PLG_AI_SIG_STORE ON PLG_AI_SIGNALS (STORE_ID, STATUS, CREATED_AT);

-- ==================== Витрина признаков ====================
--
-- Признаки нормализованы в колонки, а не свалены в JSON: по ним фильтруют
-- и агрегируют SQL-ом, а выгрузка в CSV — прямой SELECT без разбора.

CREATE TABLE PLG_AI_FEATURES (
  ID              NUMBER       NOT NULL,
  RUN_ID          NUMBER       NOT NULL,
  STORE_ID        NUMBER       NOT NULL,
  PRODUCT_ID      NUMBER       NOT NULL,
  SNAPSHOT_DATE   DATE         NOT NULL,
  AVG_QTY_7       NUMBER(14,3),            -- средний дневной спрос, 7 дней
  AVG_QTY_28      NUMBER(14,3),            -- средний дневной спрос, 28 дней
  MEDIAN_QTY_28   NUMBER(14,3),
  SIGMA_28        NUMBER(14,3),            -- сигма дневного спроса
  CV              NUMBER(8,4),             -- коэффициент вариации sigma/mean
  TREND_PCT       NUMBER(10,2),            -- 7 дней против 28, %
  WEEKEND_LIFT    NUMBER(8,4),             -- сб-вс против будней
  PROMO_UPLIFT    NUMBER(8,4),             -- промо-дни против обычных
  PROMO_DAYS_28   NUMBER,
  OOS_DAYS_28     NUMBER,                  -- дней out-of-stock за 28
  STOCK_END       NUMBER(14,3),            -- остаток на последний день
  STOCK_COVER_DAYS NUMBER(8,2),            -- остаток / средний спрос
  WASTE_PCT       NUMBER(8,3),             -- ожидаемое списание из фреш-прогона, %
  FORECAST_BIAS   NUMBER(10,4),            -- смещение модели по последнему backtest
  PRICE           NUMBER(14,2),
  MARGIN_PCT      NUMBER(8,2),
  ABC_CLASS       VARCHAR2(1),
  XYZ_CLASS       VARCHAR2(1),             -- X/Y/Z по коэффициенту вариации
  IS_FRESH        NUMBER(1)    DEFAULT 0,
  CONSTRAINT PK_PLG_AI_FEATURES PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_AI_FEAT UNIQUE (RUN_ID, STORE_ID, PRODUCT_ID),
  CONSTRAINT FK_PLG_AIF_RUN   FOREIGN KEY (RUN_ID)     REFERENCES PLG_AI_RUNS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_AIF_STORE FOREIGN KEY (STORE_ID)   REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_AIF_PROD  FOREIGN KEY (PRODUCT_ID) REFERENCES PLG_PRODUCTS(ID) ON DELETE CASCADE
);
/

CREATE OR REPLACE TRIGGER PLG_AI_FEATURES_BI
  BEFORE INSERT ON PLG_AI_FEATURES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_AI_FEAT_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_PLG_AI_FEAT_RUN ON PLG_AI_FEATURES (RUN_ID, STORE_ID);

-- ==================== Корректировки автозаказа ====================

CREATE TABLE PLG_ORDER_ADJUSTMENTS (
  ID           NUMBER        NOT NULL,
  RUN_ID       NUMBER        NOT NULL,   -- прогон прогноза, к которому правка
  STORE_ID     NUMBER        NOT NULL,
  PRODUCT_ID   NUMBER        NOT NULL,
  QTY_ORIGINAL NUMBER(14,3),             -- что предложила модель (фиксируется при правке)
  QTY_ADJUSTED NUMBER(14,3)  NOT NULL,   -- что решил человек
  REASON       VARCHAR2(30)  DEFAULT 'manual',  -- manual / promo / event / supply / quality / other
  NOTE         VARCHAR2(600),
  STATUS       VARCHAR2(20)  DEFAULT 'active',  -- active / cancelled
  USERNAME     VARCHAR2(150),
  CREATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_ORDER_ADJ PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_ORD_ADJ UNIQUE (RUN_ID, STORE_ID, PRODUCT_ID),
  CONSTRAINT FK_PLG_OA_RUN   FOREIGN KEY (RUN_ID)     REFERENCES PLG_FCT_RUNS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_OA_STORE FOREIGN KEY (STORE_ID)   REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_OA_PROD  FOREIGN KEY (PRODUCT_ID) REFERENCES PLG_PRODUCTS(ID) ON DELETE CASCADE,
  CONSTRAINT CHK_PLG_OA_REASON CHECK (REASON IN ('manual','promo','event','supply','quality','other')),
  CONSTRAINT CHK_PLG_OA_STATUS CHECK (STATUS IN ('active','cancelled'))
);
/

CREATE OR REPLACE TRIGGER PLG_ORDER_ADJ_BI
  BEFORE INSERT ON PLG_ORDER_ADJUSTMENTS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_ORD_ADJ_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER PLG_ORDER_ADJ_BU
  BEFORE UPDATE ON PLG_ORDER_ADJUSTMENTS FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

-- ==================== Представления ====================

CREATE OR REPLACE VIEW V_PLG_AI_SIGNALS AS
SELECT
  s.ID, s.RUN_ID, s.SIGNAL_TYPE, s.SEVERITY,
  s.STORE_ID, st.CODE AS STORE_CODE,
  st.NAME_RU AS STORE_NAME_RU, st.NAME_RO AS STORE_NAME_RO, st.NAME_EN AS STORE_NAME_EN,
  s.PRODUCT_ID, p.CODE AS PRODUCT_CODE,
  p.NAME_RU AS PRODUCT_NAME_RU, p.NAME_RO AS PRODUCT_NAME_RO, p.NAME_EN AS PRODUCT_NAME_EN,
  s.CATEGORY_ID, c.NAME_RU AS CATEGORY_NAME_RU, c.NAME_RO AS CATEGORY_NAME_RO,
  c.NAME_EN AS CATEGORY_NAME_EN, c.COLOR AS CATEGORY_COLOR,
  s.METRIC_VALUE, s.BASELINE_VALUE, s.DELTA_PCT,
  s.MESSAGE_RU, s.MESSAGE_RO, s.MESSAGE_EN,
  s.ACTION_HINT, s.STATUS, s.ACK_BY, s.ACK_AT, s.CREATED_AT
FROM PLG_AI_SIGNALS s
JOIN PLG_STORES st ON st.ID = s.STORE_ID
LEFT JOIN PLG_PRODUCTS p   ON p.ID = s.PRODUCT_ID
LEFT JOIN PLG_CATEGORIES c ON c.ID = s.CATEGORY_ID;

CREATE OR REPLACE VIEW V_PLG_AI_FEATURES AS
SELECT
  f.ID, f.RUN_ID, f.SNAPSHOT_DATE,
  f.STORE_ID, st.CODE AS STORE_CODE,
  f.PRODUCT_ID, p.CODE AS PRODUCT_CODE,
  p.NAME_RU AS PRODUCT_NAME_RU, p.NAME_RO AS PRODUCT_NAME_RO, p.NAME_EN AS PRODUCT_NAME_EN,
  c.CODE AS CATEGORY_CODE, c.NAME_RU AS CATEGORY_NAME_RU,
  c.NAME_RO AS CATEGORY_NAME_RO, c.NAME_EN AS CATEGORY_NAME_EN,
  f.AVG_QTY_7, f.AVG_QTY_28, f.MEDIAN_QTY_28, f.SIGMA_28, f.CV, f.TREND_PCT,
  f.WEEKEND_LIFT, f.PROMO_UPLIFT, f.PROMO_DAYS_28, f.OOS_DAYS_28,
  f.STOCK_END, f.STOCK_COVER_DAYS, f.WASTE_PCT, f.FORECAST_BIAS,
  f.PRICE, f.MARGIN_PCT, f.ABC_CLASS, f.XYZ_CLASS, f.IS_FRESH
FROM PLG_AI_FEATURES f
JOIN PLG_STORES st ON st.ID = f.STORE_ID
JOIN PLG_PRODUCTS p ON p.ID = f.PRODUCT_ID
LEFT JOIN PLG_CATEGORIES c ON c.ID = p.CATEGORY_ID;

-- Автозаказ с корректировками: рекомендация модели и решение человека рядом
CREATE OR REPLACE VIEW V_PLG_ORDER_ADJUSTED AS
SELECT
  o.RUN_ID, o.STORE_ID, o.STORE_CODE,
  o.STORE_RU AS STORE_NAME_RU, o.STORE_RO AS STORE_NAME_RO, o.STORE_EN AS STORE_NAME_EN,
  o.PRODUCT_ID, o.PRODUCT_CODE,
  o.PRODUCT_RU AS PRODUCT_NAME_RU, o.PRODUCT_RO AS PRODUCT_NAME_RO,
  o.PRODUCT_EN AS PRODUCT_NAME_EN,
  o.CATEGORY_RU AS CATEGORY_NAME_RU, o.CATEGORY_RO AS CATEGORY_NAME_RO,
  o.CATEGORY_EN AS CATEGORY_NAME_EN,
  o.ABC_CLASS, o.ORDER_MULTIPLE, o.PRICE, o.CURRENCY,
  o.QTY_FORECAST, o.SAFETY_STOCK, o.STOCK_ON_HAND,
  o.ORDER_QTY   AS QTY_MODEL,
  a.QTY_ADJUSTED, a.REASON AS ADJ_REASON, a.NOTE AS ADJ_NOTE,
  a.USERNAME AS ADJ_BY, a.UPDATED_AT AS ADJ_AT,
  NVL(a.QTY_ADJUSTED, o.ORDER_QTY) AS QTY_FINAL,
  ROUND(NVL(a.QTY_ADJUSTED, o.ORDER_QTY) * o.PRICE, 2) AS AMOUNT_FINAL,
  CASE WHEN a.ID IS NOT NULL THEN 1 ELSE 0 END AS IS_ADJUSTED,
  sup.ID AS SUPPLIER_ID, sup.NAME_RU AS SUPPLIER_NAME_RU,
  sup.NAME_RO AS SUPPLIER_NAME_RO, sup.NAME_EN AS SUPPLIER_NAME_EN
FROM V_PLG_ORDER_PROPOSAL o
LEFT JOIN PLG_ORDER_ADJUSTMENTS a
       ON a.RUN_ID = o.RUN_ID AND a.STORE_ID = o.STORE_ID
      AND a.PRODUCT_ID = o.PRODUCT_ID AND a.STATUS = 'active'
LEFT JOIN PLG_PRODUCTS pp ON pp.ID = o.PRODUCT_ID
LEFT JOIN PLG_SUPPLIERS sup ON sup.ID = pp.SUPPLIER_ID;
