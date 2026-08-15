-- ============================================================
-- Планограммы: тестовое окружение данных сети магазинов
--
-- Изоляция тестовых данных — через ИМЕНОВАННЫЕ НАБОРЫ (PLG_DATASETS).
-- Набор проставляется на корневых сущностях: PLG_STORES.DATASET_ID и
-- PLG_PRODUCTS.DATASET_ID. Всё остальное (зоны, оборудование, планограммы,
-- акции, задачи, метрики, продажи) достижимо через магазин и удаляется
-- каскадом вместе с ним — отдельный флаг на каждой строке не нужен.
--
-- Боевые данные лежат в наборе DEMO и генератором не затрагиваются.
-- Префикс объектов: PLG_
-- ============================================================

CREATE SEQUENCE PLG_DATASETS_SEQ   START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_SALES_SEQ      START WITH 1 INCREMENT BY 1 CACHE 1000;
CREATE SEQUENCE PLG_GEN_RUNS_SEQ   START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_DATASET_NUM_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- ==================== Наборы данных ====================

CREATE TABLE PLG_DATASETS (
  ID           NUMBER        NOT NULL,
  CODE         VARCHAR2(40)  NOT NULL,   -- DEMO, TEST-2026-001
  KIND         VARCHAR2(20)  DEFAULT 'test',   -- demo / test / sandbox
  NAME_RU      VARCHAR2(200) NOT NULL,
  NAME_RO      VARCHAR2(200),
  NAME_EN      VARCHAR2(200),
  DESCRIPTION  VARCHAR2(1000),
  STATUS       VARCHAR2(20)  DEFAULT 'building',  -- building / ready / failed / archived
  STORE_COUNT  NUMBER        DEFAULT 0,
  SKU_COUNT    NUMBER        DEFAULT 0,
  DAYS_DEPTH   NUMBER        DEFAULT 0,
  SEED         NUMBER        DEFAULT 20260815,    -- воспроизводимость генерации
  ROWS_TOTAL   NUMBER        DEFAULT 0,
  IS_PROTECTED NUMBER(1)     DEFAULT 0,           -- 1 = запрещено удалять генератором
  CREATED_BY   VARCHAR2(150),
  CREATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  FINISHED_AT  TIMESTAMP,
  CONSTRAINT PK_PLG_DATASETS PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_DATASETS_CODE UNIQUE (CODE),
  CONSTRAINT CHK_PLG_DS_KIND   CHECK (KIND IN ('demo','test','sandbox')),
  CONSTRAINT CHK_PLG_DS_STATUS CHECK (STATUS IN ('building','ready','failed','archived')),
  CONSTRAINT CHK_PLG_DS_PROT   CHECK (IS_PROTECTED IN (0,1))
);
/

CREATE OR REPLACE TRIGGER PLG_DATASETS_BI
  BEFORE INSERT ON PLG_DATASETS FOR EACH ROW
BEGIN
  IF :NEW.ID IS NULL THEN
    :NEW.ID := PLG_DATASETS_SEQ.NEXTVAL;
  END IF;
  IF :NEW.CODE IS NULL THEN
    :NEW.CODE := 'TEST-' || TO_CHAR(SYSDATE, 'YYYY') || '-' ||
                 LPAD(TO_CHAR(PLG_DATASET_NUM_SEQ.NEXTVAL), 3, '0');
  END IF;
END;
/

-- Базовый набор: всё, что уже лежит в модуле, относится к нему и защищено
INSERT INTO PLG_DATASETS (CODE, KIND, NAME_RU, NAME_RO, NAME_EN, DESCRIPTION,
                          STATUS, IS_PROTECTED, CREATED_BY, FINISHED_AT)
VALUES ('DEMO', 'demo', 'Демонстрационный набор', 'Set demonstrativ', 'Demo dataset',
        'Исходные демо-данные модуля (Магазин 24 и др.). Генератором не затрагивается.',
        'ready', 1, 'system', SYSTIMESTAMP);

COMMIT;
/

-- ==================== Привязка корневых сущностей к набору ====================

ALTER TABLE PLG_STORES   ADD (DATASET_ID NUMBER);
ALTER TABLE PLG_PRODUCTS ADD (DATASET_ID NUMBER);

UPDATE PLG_STORES   SET DATASET_ID = (SELECT ID FROM PLG_DATASETS WHERE CODE = 'DEMO') WHERE DATASET_ID IS NULL;
UPDATE PLG_PRODUCTS SET DATASET_ID = (SELECT ID FROM PLG_DATASETS WHERE CODE = 'DEMO') WHERE DATASET_ID IS NULL;
COMMIT;

ALTER TABLE PLG_STORES   ADD CONSTRAINT FK_PLG_STORES_DS   FOREIGN KEY (DATASET_ID) REFERENCES PLG_DATASETS(ID);
ALTER TABLE PLG_PRODUCTS ADD CONSTRAINT FK_PLG_PRODUCTS_DS FOREIGN KEY (DATASET_ID) REFERENCES PLG_DATASETS(ID);

CREATE INDEX IX_PLG_STORES_DS   ON PLG_STORES (DATASET_ID);
CREATE INDEX IX_PLG_PRODUCTS_DS ON PLG_PRODUCTS (DATASET_ID);

-- Формат магазина нужен генератору сети (гипер / супер / дискаунтер / у дома)
ALTER TABLE PLG_STORES ADD (STORE_FORMAT VARCHAR2(20) DEFAULT 'super');

-- ==================== Факт продаж (основа прогноза заказов) ====================

CREATE TABLE PLG_SALES_DAILY (
  ID           NUMBER       NOT NULL,
  STORE_ID     NUMBER       NOT NULL,
  PRODUCT_ID   NUMBER       NOT NULL,
  SALES_DATE   DATE         NOT NULL,
  QTY          NUMBER(12,3) DEFAULT 0,
  AMOUNT       NUMBER(16,2) DEFAULT 0,
  PRICE        NUMBER(14,2),
  PROMO_ID     NUMBER,                      -- акция, действовавшая в этот день
  STOCK_END    NUMBER(12,3),                -- остаток на конец дня
  IS_OOS       NUMBER(1)    DEFAULT 0,      -- out of stock: спрос был, товара не было
  CONSTRAINT PK_PLG_SALES_DAILY PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_SALES UNIQUE (STORE_ID, PRODUCT_ID, SALES_DATE),
  CONSTRAINT FK_PLG_SALES_STORE FOREIGN KEY (STORE_ID) REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_SALES_PROD  FOREIGN KEY (PRODUCT_ID) REFERENCES PLG_PRODUCTS(ID) ON DELETE CASCADE,
  CONSTRAINT CHK_PLG_SALES_OOS  CHECK (IS_OOS IN (0,1))
);

CREATE INDEX IX_PLG_SALES_SKU  ON PLG_SALES_DAILY (PRODUCT_ID, STORE_ID, SALES_DATE);
CREATE INDEX IX_PLG_SALES_DATE ON PLG_SALES_DAILY (SALES_DATE);

-- ==================== Реестр алгоритмов генерации ====================

CREATE TABLE PLG_GEN_ALGORITHMS (
  CODE        VARCHAR2(30)   NOT NULL,
  NAME_RU     VARCHAR2(200)  NOT NULL,
  NAME_RO     VARCHAR2(200),
  NAME_EN     VARCHAR2(200),
  DESCR_RU    VARCHAR2(1000),
  DESCR_RO    VARCHAR2(1000),
  DESCR_EN    VARCHAR2(1000),
  PARAMS_JSON VARCHAR2(2000),               -- значения параметров по умолчанию
  STAGE_ORDER NUMBER         DEFAULT 0,     -- порядок в полном прогоне
  IS_ACTIVE   NUMBER(1)      DEFAULT 1,
  CONSTRAINT PK_PLG_GEN_ALGORITHMS PRIMARY KEY (CODE),
  CONSTRAINT CHK_PLG_GA_ACTIVE CHECK (IS_ACTIVE IN (0,1))
);

-- ==================== Журнал прогонов генерации ====================

CREATE TABLE PLG_GEN_RUNS (
  ID           NUMBER        NOT NULL,
  DATASET_ID   NUMBER,
  ALGORITHM    VARCHAR2(30)  NOT NULL,      -- код алгоритма либо 'full' (полный прогон)
  PARAMS_JSON  VARCHAR2(2000),
  STATUS       VARCHAR2(20)  DEFAULT 'running',  -- running / done / failed / cancelled
  STAGE        VARCHAR2(60),                -- текущий этап (для прогресса в админке)
  PROGRESS_PCT NUMBER        DEFAULT 0,
  ROWS_WRITTEN NUMBER        DEFAULT 0,
  DURATION_SEC NUMBER,
  MESSAGE      VARCHAR2(2000),
  USERNAME     VARCHAR2(150),
  STARTED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  FINISHED_AT  TIMESTAMP,
  CONSTRAINT PK_PLG_GEN_RUNS PRIMARY KEY (ID),
  CONSTRAINT FK_PLG_GR_DS FOREIGN KEY (DATASET_ID) REFERENCES PLG_DATASETS(ID) ON DELETE SET NULL,
  CONSTRAINT CHK_PLG_GR_PROGRESS CHECK (PROGRESS_PCT BETWEEN 0 AND 100),
  CONSTRAINT CHK_PLG_GR_STATUS CHECK (STATUS IN ('running','done','failed','cancelled'))
);
/

CREATE OR REPLACE TRIGGER PLG_GEN_RUNS_BI
  BEFORE INSERT ON PLG_GEN_RUNS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_GEN_RUNS_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_PLG_GEN_RUNS_DS ON PLG_GEN_RUNS (DATASET_ID, STARTED_AT);

-- ==================== Наполнение реестра алгоритмов ====================

INSERT INTO PLG_GEN_ALGORITHMS (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, PARAMS_JSON, STAGE_ORDER) VALUES
('network', 'Сеть магазинов', 'Rețeaua de magazine', 'Store network',
 'Создаёт магазины четырёх форматов (гипермаркет, супермаркет, дискаунтер, магазин у дома) с торговым залом: зоны по формату, стеллажи и холодильное оборудование, координаты карты.',
 'Creează magazine de patru formate cu sala comercială: zone, rafturi și echipament frigorific, coordonatele hărții.',
 'Creates stores of four formats with a sales floor: zones, shelving and cooling equipment, map coordinates.',
 '{"store_count": 10, "formats": ["hyper","super","discounter","convenience"], "cities": ["Chisinau","Balti","Cahul","Orhei","Ungheni"]}', 1);

INSERT INTO PLG_GEN_ALGORITHMS (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, PARAMS_JSON, STAGE_ORDER) VALUES
('assortment', 'Ассортиментная матрица', 'Matricea sortimentală', 'Assortment matrix',
 'Генерирует SKU по категориям с ценами, габаритами упаковки, кратностью заказа и ABC-классом. Доля категорий соответствует реальной структуре продуктового ритейла.',
 'Generează SKU pe categorii cu prețuri, dimensiuni, multiplu de comandă și clasa ABC.',
 'Generates SKUs per category with prices, pack sizes, order multiples and ABC class.',
 '{"sku_count": 400, "abc_split": [0.2, 0.3, 0.5], "price_min": 5, "price_max": 350}', 2);

INSERT INTO PLG_GEN_ALGORITHMS (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, PARAMS_JSON, STAGE_ORDER) VALUES
('demand', 'История спроса', 'Istoricul cererii', 'Demand history',
 'Ядро тестового окружения: суточные продажи по каждому SKU в каждом магазине. Модель = базовый уровень × годовая сезонность × недельный профиль × тренд × промо-аплифт × шум, поверх — события out-of-stock и остатки.',
 'Nucleul mediului de test: vânzări zilnice pe SKU și magazin. Model = nivel de bază × sezonalitate anuală × profil săptămânal × trend × uplift promoțional × zgomot.',
 'Core of the test environment: daily sales per SKU and store. Model = base level × yearly seasonality × weekly profile × trend × promo uplift × noise.',
 '{"days": 365, "weekly_amplitude": 0.35, "yearly_amplitude": 0.20, "trend_pct_year": 6, "noise_pct": 18, "oos_rate": 0.015, "promo_uplift": 1.9}', 3);

INSERT INTO PLG_GEN_ALGORITHMS (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, PARAMS_JSON, STAGE_ORDER) VALUES
('traffic', 'Трафик и показатели', 'Trafic și indicatori', 'Traffic and metrics',
 'Считает проходимость зон и дневные показатели магазина (трафик, покупатели, конверсия, средний чек, выручка) СОГЛАСОВАННО с уже сгенерированными продажами, а не независимым шумом.',
 'Calculează traficul pe zone și indicatorii zilnici ai magazinului în concordanță cu vânzările generate.',
 'Computes zone traffic and daily store metrics consistently with the generated sales.',
 '{"conversion_min": 16, "conversion_max": 21}', 4);

INSERT INTO PLG_GEN_ALGORITHMS (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, PARAMS_JSON, STAGE_ORDER) VALUES
('events', 'Акции, планограммы, задачи', 'Promoții, planograme, sarcini', 'Promos, planograms, tasks',
 'Достраивает операционный слой: промо-кампании с привязкой к товарам и зонам, планограммы по зонам с позициями выкладки, задачи мерчандайзинга и уведомления.',
 'Completează stratul operațional: campanii promoționale, planograme cu poziții, sarcini și notificări.',
 'Builds the operational layer: promo campaigns, planograms with layout items, tasks and notifications.',
 '{"promo_per_store": 6, "planogram_per_store": 5, "task_per_store": 8}', 5);

COMMIT;
