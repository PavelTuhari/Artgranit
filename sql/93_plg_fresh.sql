-- ============================================================
-- Планограммы: фреш-контур (скоропортящийся товар)
--
-- Фреш отличается от сухого ассортимента не точностью прогноза, а тем, что
-- ошибка в обе стороны стоит денег СРАЗУ: недозаказ = пустая полка в самой
-- трафиковой зоне, перезаказ = списание через два-три дня. Поэтому заказ
-- считается не «прогноз + страховой запас», а по критическому отношению
-- (newsvendor): сколько теряем на упущенной марже против стоимости списания.
--
-- Второе отличие — маршрут поставки. Один и тот же SKU может идти:
--   dc     — через распределительный центр (консолидация, свой график,
--            но плюс день транзита и минус день остаточного срока годности);
--   direct — прямой поставкой поставщика в магазин (короче плечо и свежее
--            товар, но частые мелкие машины и своё окно приёмки).
-- Маршрут — это ДАННЫЕ (PLG_FRESH_ROUTES), а не два разных алгоритма:
-- различаются плечо, календарь заказа/поставки, cutoff и минимальная партия.
--
-- Префикс объектов: PLG_
-- ============================================================

-- ==================== Температурные режимы ====================

CREATE TABLE PLG_REF_TEMP_REGIMES (
  CODE       VARCHAR2(20)  NOT NULL,
  NAME_RU    VARCHAR2(100) NOT NULL,
  NAME_RO    VARCHAR2(100),
  NAME_EN    VARCHAR2(100),
  TEMP_MIN   NUMBER(5,1),
  TEMP_MAX   NUMBER(5,1),
  COLOR      VARCHAR2(10),
  SORT_ORDER NUMBER        DEFAULT 0,
  CONSTRAINT PK_PLG_REF_TEMP PRIMARY KEY (CODE)
);

INSERT INTO PLG_REF_TEMP_REGIMES (CODE, NAME_RU, NAME_RO, NAME_EN, TEMP_MIN, TEMP_MAX, COLOR, SORT_ORDER)
VALUES ('ambient', 'Сухой склад', 'Depozit uscat', 'Ambient', 10, 25, '#9ca3af', 1);
INSERT INTO PLG_REF_TEMP_REGIMES (CODE, NAME_RU, NAME_RO, NAME_EN, TEMP_MIN, TEMP_MAX, COLOR, SORT_ORDER)
VALUES ('chilled', 'Охлаждённый', 'Refrigerat', 'Chilled', 0, 6, '#3b82f6', 2);
INSERT INTO PLG_REF_TEMP_REGIMES (CODE, NAME_RU, NAME_RO, NAME_EN, TEMP_MIN, TEMP_MAX, COLOR, SORT_ORDER)
VALUES ('ultrafresh', 'Ультрафреш', 'Ultra-proaspăt', 'Ultra-fresh', 0, 4, '#16a34a', 3);
INSERT INTO PLG_REF_TEMP_REGIMES (CODE, NAME_RU, NAME_RO, NAME_EN, TEMP_MIN, TEMP_MAX, COLOR, SORT_ORDER)
VALUES ('frozen', 'Заморозка', 'Congelat', 'Frozen', -24, -18, '#0ea5e9', 4);

COMMIT;

-- ==================== Атрибуты товара для фреш ====================
--
-- SHELF_LIFE_DAYS уже добавлен в 84_plg_testdata.sql. Здесь — экономика
-- (себестоимость нужна, чтобы посчитать стоимость списания) и режим хранения.

-- Файл рассчитан на повторный запуск: DDL-правки товара идут через проверку
-- словаря, иначе второй прогон deploy_oracle_objects.py заваливает лог
-- ошибками «column already exists» и настоящую ошибку в нём не видно.

DECLARE
  PROCEDURE add_col(p_col VARCHAR2, p_def VARCHAR2) IS
    v_n NUMBER;
  BEGIN
    SELECT COUNT(*) INTO v_n FROM USER_TAB_COLUMNS
     WHERE TABLE_NAME = 'PLG_PRODUCTS' AND COLUMN_NAME = p_col;
    IF v_n = 0 THEN
      EXECUTE IMMEDIATE 'ALTER TABLE PLG_PRODUCTS ADD (' || p_col || ' ' || p_def || ')';
    END IF;
  END;
  PROCEDURE add_con(p_name VARCHAR2, p_body VARCHAR2) IS
    v_n NUMBER;
  BEGIN
    SELECT COUNT(*) INTO v_n FROM USER_CONSTRAINTS WHERE CONSTRAINT_NAME = p_name;
    IF v_n = 0 THEN
      EXECUTE IMMEDIATE 'ALTER TABLE PLG_PRODUCTS ADD CONSTRAINT ' || p_name || ' ' || p_body;
    END IF;
  END;
BEGIN
  add_col('IS_FRESH',       'NUMBER(1) DEFAULT 0');       -- участвует в фреш-контуре
  add_col('TEMP_REGIME',    'VARCHAR2(20) DEFAULT ''ambient''');
  add_col('COST_PRICE',     'NUMBER(14,2)');              -- для стоимости списания
  add_col('SALVAGE_PCT',    'NUMBER(5,2) DEFAULT 0');     -- возврат стоимости уценкой
  add_col('CASE_WEIGHT_KG', 'NUMBER(10,3)');              -- вес короба, расчёт машин
  add_con('CHK_PLG_PROD_FRESH', 'CHECK (IS_FRESH IN (0,1))');
  add_con('FK_PLG_PROD_TEMP',
          'FOREIGN KEY (TEMP_REGIME) REFERENCES PLG_REF_TEMP_REGIMES(CODE)');
END;
/

-- ==================== Профиль фреш-категории ====================
--
-- Экономика и правила выкладки задаются на уровне категории, а не SKU:
-- у категорийного менеджера нет ресурса вести 400 карточек вручную.
-- Значение на SKU (если заполнено) перекрывает категорийное.

CREATE SEQUENCE PLG_FRESH_PROFILE_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE TABLE PLG_FRESH_PROFILES (
  ID               NUMBER        NOT NULL,
  CATEGORY_ID      NUMBER        NOT NULL,
  TEMP_REGIME      VARCHAR2(20)  DEFAULT 'chilled',
  SHELF_LIFE_DAYS  NUMBER        DEFAULT 5,     -- срок годности по умолчанию
  RECEIPT_SHELF_PCT NUMBER(5,2)  DEFAULT 80,    -- % срока, остающийся при приёмке
  PRESENTATION_MIN NUMBER(10,3)  DEFAULT 0,     -- минимальная выкладка, ед.
  SALVAGE_PCT      NUMBER(5,2)   DEFAULT 20,    -- возврат стоимости уценкой
  WASTE_TARGET_PCT NUMBER(5,2)   DEFAULT 3,     -- целевой уровень списаний
  MARGIN_PCT       NUMBER(5,2)   DEFAULT 28,    -- наценка, если нет COST_PRICE
  ROUND_STEP       NUMBER(10,3)  DEFAULT 1,     -- шаг округления (0.1 для весового)
  IS_ACTIVE        NUMBER(1)     DEFAULT 1,
  CREATED_AT       TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT       TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_FRESH_PROFILES PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_FP_CAT UNIQUE (CATEGORY_ID),
  CONSTRAINT FK_PLG_FP_CAT  FOREIGN KEY (CATEGORY_ID) REFERENCES PLG_CATEGORIES(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_FP_TEMP FOREIGN KEY (TEMP_REGIME) REFERENCES PLG_REF_TEMP_REGIMES(CODE),
  CONSTRAINT CHK_PLG_FP_ACTIVE CHECK (IS_ACTIVE IN (0,1)),
  CONSTRAINT CHK_PLG_FP_SHELF  CHECK (SHELF_LIFE_DAYS BETWEEN 1 AND 90),
  CONSTRAINT CHK_PLG_FP_RECEIPT CHECK (RECEIPT_SHELF_PCT BETWEEN 10 AND 100)
);
/

CREATE OR REPLACE TRIGGER PLG_FRESH_PROFILES_BI
  BEFORE INSERT ON PLG_FRESH_PROFILES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_FRESH_PROFILE_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER PLG_FRESH_PROFILES_BU
  BEFORE UPDATE ON PLG_FRESH_PROFILES FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

-- ==================== Маршрут поставки ====================
--
-- Календари хранятся строкой из семи символов, понедельник первый:
-- '1111100' — заказ принимается с понедельника по пятницу.
-- Строка выбрана вместо семи колонок сознательно: её видно глазами в любом
-- клиенте SQL и она читается одинаково в Python и в PL/SQL.

CREATE SEQUENCE PLG_FRESH_ROUTE_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE TABLE PLG_FRESH_ROUTES (
  ID                NUMBER        NOT NULL,
  DATASET_ID        NUMBER,
  STORE_ID          NUMBER        NOT NULL,
  CATEGORY_ID       NUMBER,                        -- NULL = все фреш-категории магазина
  SUPPLIER_ID       NUMBER,                        -- для прямой поставки
  DC_ID             NUMBER,                        -- для маршрута через РЦ
  ROUTE             VARCHAR2(10)  DEFAULT 'dc',    -- dc / direct
  LEAD_TIME_DAYS    NUMBER(4,1)   DEFAULT 1,       -- от отсечки заказа до приёмки
  TRANSIT_DAYS      NUMBER(4,1)   DEFAULT 0,       -- время в пути (съедает срок годности)
  ORDER_DAYS        VARCHAR2(7)   DEFAULT '1111110',
  DELIVERY_DAYS     VARCHAR2(7)   DEFAULT '1111110',
  CUTOFF_TIME       VARCHAR2(5)   DEFAULT '11:00', -- отсечка приёма заказа
  MIN_ORDER_QTY     NUMBER(12,3)  DEFAULT 0,
  MIN_ORDER_AMOUNT  NUMBER(14,2)  DEFAULT 0,
  RECEIPT_SHELF_PCT NUMBER(5,2),                   -- перекрывает профиль категории
  PRIORITY          NUMBER        DEFAULT 100,     -- меньше = важнее при конфликте
  IS_ACTIVE         NUMBER(1)     DEFAULT 1,
  NOTES             VARCHAR2(600),
  CREATED_AT        TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT        TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_FRESH_ROUTES PRIMARY KEY (ID),
  CONSTRAINT FK_PLG_FRT_DS    FOREIGN KEY (DATASET_ID)  REFERENCES PLG_DATASETS(ID),
  CONSTRAINT FK_PLG_FRT_STORE FOREIGN KEY (STORE_ID)    REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_FRT_CAT   FOREIGN KEY (CATEGORY_ID) REFERENCES PLG_CATEGORIES(ID),
  CONSTRAINT FK_PLG_FRT_SUP   FOREIGN KEY (SUPPLIER_ID) REFERENCES PLG_SUPPLIERS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_FRT_DC    FOREIGN KEY (DC_ID)       REFERENCES PLG_DC(ID) ON DELETE CASCADE,
  CONSTRAINT CHK_PLG_FRT_ROUTE  CHECK (ROUTE IN ('dc','direct')),
  CONSTRAINT CHK_PLG_FRT_ACTIVE CHECK (IS_ACTIVE IN (0,1)),
  CONSTRAINT CHK_PLG_FRT_LEAD   CHECK (LEAD_TIME_DAYS BETWEEN 0 AND 30)
);
/

CREATE OR REPLACE TRIGGER PLG_FRESH_ROUTES_BI
  BEFORE INSERT ON PLG_FRESH_ROUTES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_FRESH_ROUTE_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER PLG_FRESH_ROUTES_BU
  BEFORE UPDATE ON PLG_FRESH_ROUTES FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

CREATE INDEX IX_PLG_FRESH_ROUTES_ST ON PLG_FRESH_ROUTES (STORE_ID, CATEGORY_ID, IS_ACTIVE);

-- ==================== Результат расчёта: фреш-поля ====================
--
-- Заказ фреш нельзя объяснить одной цифрой: менеджер должен видеть, каким
-- маршрутом считалось, на сколько дней хватит и сколько из этого, по расчёту,
-- уйдёт в списание. Иначе рекомендация не проверяется и ей не доверяют.

ALTER TABLE PLG_FCT_RESULTS ADD (
  ROUTE          VARCHAR2(10),
  COVERAGE_DAYS  NUMBER(6,2),      -- на сколько дней рассчитан заказ
  WASTE_FORECAST NUMBER(14,3),     -- ожидаемое списание из этой партии
  SHELF_LIMITED  NUMBER(1) DEFAULT 0,  -- заказ урезан сроком годности, а не спросом
  NEXT_DELIVERY  DATE              -- ближайшая дата поставки по календарю маршрута
);

-- ==================== Представления ====================

CREATE OR REPLACE VIEW V_PLG_FRESH_ROUTES AS
SELECT
  r.ID, r.DATASET_ID, r.STORE_ID,
  s.CODE AS STORE_CODE, s.NAME_RU AS STORE_NAME_RU, s.NAME_RO AS STORE_NAME_RO,
  s.NAME_EN AS STORE_NAME_EN,
  r.CATEGORY_ID, c.NAME_RU AS CATEGORY_NAME_RU, c.NAME_RO AS CATEGORY_NAME_RO,
  c.NAME_EN AS CATEGORY_NAME_EN, c.COLOR AS CATEGORY_COLOR,
  r.SUPPLIER_ID, sup.NAME_RU AS SUPPLIER_NAME_RU, sup.NAME_RO AS SUPPLIER_NAME_RO,
  sup.NAME_EN AS SUPPLIER_NAME_EN,
  r.DC_ID, dc.NAME_RU AS DC_NAME_RU, dc.NAME_RO AS DC_NAME_RO, dc.NAME_EN AS DC_NAME_EN,
  r.ROUTE, r.LEAD_TIME_DAYS, r.TRANSIT_DAYS, r.ORDER_DAYS, r.DELIVERY_DAYS,
  r.CUTOFF_TIME, r.MIN_ORDER_QTY, r.MIN_ORDER_AMOUNT, r.RECEIPT_SHELF_PCT,
  r.PRIORITY, r.IS_ACTIVE, r.NOTES,
  -- Сколько поставок в неделю — главный вход в расчёт покрытия
  (LENGTH(REPLACE(r.DELIVERY_DAYS, '0', ''))) AS DELIVERIES_PER_WEEK,
  r.CREATED_AT, r.UPDATED_AT
FROM PLG_FRESH_ROUTES r
JOIN PLG_STORES s ON s.ID = r.STORE_ID
LEFT JOIN PLG_CATEGORIES c  ON c.ID = r.CATEGORY_ID
LEFT JOIN PLG_SUPPLIERS sup ON sup.ID = r.SUPPLIER_ID
LEFT JOIN PLG_DC dc         ON dc.ID = r.DC_ID;

CREATE OR REPLACE VIEW V_PLG_FRESH_PROFILES AS
SELECT
  fp.ID, fp.CATEGORY_ID,
  c.CODE AS CATEGORY_CODE, c.NAME_RU AS CATEGORY_NAME_RU,
  c.NAME_RO AS CATEGORY_NAME_RO, c.NAME_EN AS CATEGORY_NAME_EN, c.COLOR AS CATEGORY_COLOR,
  fp.TEMP_REGIME,
  tr.NAME_RU AS TEMP_NAME_RU, tr.NAME_RO AS TEMP_NAME_RO, tr.NAME_EN AS TEMP_NAME_EN,
  tr.TEMP_MIN, tr.TEMP_MAX, tr.COLOR AS TEMP_COLOR,
  fp.SHELF_LIFE_DAYS, fp.RECEIPT_SHELF_PCT, fp.PRESENTATION_MIN, fp.SALVAGE_PCT,
  fp.WASTE_TARGET_PCT, fp.MARGIN_PCT, fp.ROUND_STEP, fp.IS_ACTIVE,
  (SELECT COUNT(*) FROM PLG_PRODUCTS p
    WHERE p.CATEGORY_ID = fp.CATEGORY_ID AND NVL(p.IS_FRESH,0) = 1) AS SKU_COUNT,
  fp.CREATED_AT, fp.UPDATED_AT
FROM PLG_FRESH_PROFILES fp
JOIN PLG_CATEGORIES c ON c.ID = fp.CATEGORY_ID
LEFT JOIN PLG_REF_TEMP_REGIMES tr ON tr.CODE = fp.TEMP_REGIME;

-- Заказ фреш: маршрут, покрытие, ожидаемое списание рядом с количеством
CREATE OR REPLACE VIEW V_PLG_FRESH_ORDER AS
SELECT
  res.RUN_ID, res.STORE_ID, s.CODE AS STORE_CODE,
  s.NAME_RU AS STORE_NAME_RU, s.NAME_RO AS STORE_NAME_RO, s.NAME_EN AS STORE_NAME_EN,
  res.PRODUCT_ID, p.CODE AS PRODUCT_CODE,
  p.NAME_RU AS PRODUCT_NAME_RU, p.NAME_RO AS PRODUCT_NAME_RO, p.NAME_EN AS PRODUCT_NAME_EN,
  p.UOM, p.PRICE, p.COST_PRICE, p.CURRENCY, p.SHELF_LIFE_DAYS, p.TEMP_REGIME,
  p.ORDER_MULTIPLE,
  c.ID AS CATEGORY_ID, c.NAME_RU AS CATEGORY_NAME_RU,
  c.NAME_RO AS CATEGORY_NAME_RO, c.NAME_EN AS CATEGORY_NAME_EN, c.COLOR AS CATEGORY_COLOR,
  MIN(res.FCT_DATE) AS DATE_FROM,
  MAX(res.FCT_DATE) AS DATE_TO,
  MAX(res.ROUTE)          AS ROUTE,
  MAX(res.COVERAGE_DAYS)  AS COVERAGE_DAYS,
  MAX(res.NEXT_DELIVERY)  AS NEXT_DELIVERY,
  MAX(res.SHELF_LIMITED)  AS SHELF_LIMITED,
  ROUND(SUM(res.QTY_FORECAST), 3)  AS QTY_FORECAST,
  ROUND(MAX(res.SAFETY_STOCK), 3)  AS SAFETY_STOCK,
  ROUND(MAX(res.STOCK_ON_HAND), 3) AS STOCK_ON_HAND,
  ROUND(SUM(res.ORDER_QTY), 3)     AS ORDER_QTY,
  ROUND(SUM(res.WASTE_FORECAST), 3) AS WASTE_FORECAST,
  ROUND(SUM(res.ORDER_QTY) * p.PRICE, 2) AS ORDER_AMOUNT,
  ROUND(SUM(res.WASTE_FORECAST) * NVL(p.COST_PRICE, p.PRICE * 0.72), 2) AS WASTE_AMOUNT
FROM PLG_FCT_RESULTS res
JOIN PLG_STORES s   ON s.ID = res.STORE_ID
JOIN PLG_PRODUCTS p ON p.ID = res.PRODUCT_ID
LEFT JOIN PLG_CATEGORIES c ON c.ID = p.CATEGORY_ID
WHERE NVL(p.IS_FRESH, 0) = 1
GROUP BY res.RUN_ID, res.STORE_ID, s.CODE, s.NAME_RU, s.NAME_RO, s.NAME_EN,
         res.PRODUCT_ID, p.CODE, p.NAME_RU, p.NAME_RO, p.NAME_EN,
         p.UOM, p.PRICE, p.COST_PRICE, p.CURRENCY, p.SHELF_LIFE_DAYS, p.TEMP_REGIME,
         p.ORDER_MULTIPLE,
         c.ID, c.NAME_RU, c.NAME_RO, c.NAME_EN, c.COLOR;

-- ==================== Алгоритм заказа фреш ====================

INSERT INTO PLG_FCT_ALGORITHMS (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN,
                                PARAMS_SCHEMA, PARAMS_JSON, MIN_HISTORY, SORT_ORDER) VALUES
('fresh', 'Фреш: заказ по критическому отношению', 'Fresh: comandă după raportul critic',
 'Fresh: critical-ratio ordering',
 'Спрос считается по медианному недельному профилю за короткое окно (фреш меняет уровень быстрее сухого ассортимента), с поправкой на свежий уровень последних дней и плановые акции. Заказ определяется не уровнем сервиса, а критическим отношением newsvendor: упущенная маржа против стоимости списания. Покрытие = интервал между поставками по календарю маршрута + плечо, но не больше остаточного срока годности на полке. Учитываются презентационный минимум выкладки, минимальная партия и кратность короба. Работает для обоих маршрутов: через распределительный центр и прямой поставкой.',
 'Cererea se calculează după profilul săptămânal median pe o fereastră scurtă, cu corecție de nivel recent și promoții planificate. Comanda se determină prin raportul critic newsvendor: marja pierdută față de costul rebutului. Acoperirea = intervalul dintre livrări + termenul de livrare, limitat de termenul de valabilitate rămas.',
 'Demand uses a median weekly profile over a short window, corrected for the recent level and planned promotions. The order quantity follows the newsvendor critical ratio — lost margin versus waste cost — rather than a flat service level. Coverage equals the interval between deliveries plus lead time, capped by the remaining shelf life. Supports both DC and direct-delivery routes.',
 '[{"key":"window","type":"int","min":14,"max":120,"default":35,"label_ru":"Окно профиля, дней","label_ro":"Fereastra profilului, zile","label_en":"Profile window, days"},{"key":"level_window","type":"int","min":3,"max":21,"default":7,"label_ru":"Окно свежего уровня, дней","label_ro":"Fereastra nivelului recent, zile","label_en":"Recent level window, days"},{"key":"route","type":"select","options":["auto","dc","direct"],"default":"auto","label_ru":"Маршрут поставки","label_ro":"Ruta de livrare","label_en":"Delivery route"},{"key":"waste_cost_pct","type":"float","min":0,"max":100,"step":1,"default":100,"label_ru":"Стоимость списания, % себестоимости","label_ro":"Costul rebutului, % din cost","label_en":"Waste cost, % of cost"},{"key":"min_cr","type":"float","min":0.5,"max":0.99,"step":0.01,"default":0.7,"label_ru":"Нижняя граница критического отношения","label_ro":"Limita inferioară a raportului critic","label_en":"Critical ratio floor"},{"key":"max_cr","type":"float","min":0.6,"max":0.999,"step":0.005,"default":0.97,"label_ru":"Верхняя граница критического отношения","label_ro":"Limita superioară a raportului critic","label_en":"Critical ratio cap"},{"key":"use_presentation","type":"bool","default":1,"label_ru":"Держать презентационный минимум","label_ro":"Menține minimul de prezentare","label_en":"Keep presentation minimum"},{"key":"use_promo","type":"bool","default":1,"label_ru":"Учитывать плановые акции","label_ro":"Ia în calcul promoțiile planificate","label_en":"Use planned promotions"},{"key":"exclude_oos","type":"bool","default":1,"label_ru":"Исключать дни out-of-stock","label_ro":"Exclude zilele fără stoc","label_en":"Exclude out-of-stock days"}]',
 '{"window": 35, "level_window": 7, "route": "auto", "waste_cost_pct": 100, "min_cr": 0.7, "max_cr": 0.97, "use_presentation": 1, "use_promo": 1, "exclude_oos": 1}',
 28, 5);

COMMIT;

-- Две модели по умолчанию: маршрут задан явно, чтобы их точность и уровень
-- списаний можно было сравнить на одних и тех же данных.
INSERT INTO PLG_FCT_MODELS (CODE, ALGORITHM, NAME_RU, NAME_RO, NAME_EN, PARAMS_JSON,
                            HORIZON_DAYS, SERVICE_LEVEL, LEAD_TIME_DAYS, IS_DEFAULT, CREATED_BY)
VALUES ('FRESH-DC', 'fresh', 'Фреш через распределительный центр', 'Fresh prin centrul de distribuție',
        'Fresh via distribution centre',
        '{"window": 35, "level_window": 7, "route": "dc", "waste_cost_pct": 100, "min_cr": 0.7, "max_cr": 0.97, "use_presentation": 1, "use_promo": 1, "exclude_oos": 1}',
        7, 97, 1, 0, 'system');

INSERT INTO PLG_FCT_MODELS (CODE, ALGORITHM, NAME_RU, NAME_RO, NAME_EN, PARAMS_JSON,
                            HORIZON_DAYS, SERVICE_LEVEL, LEAD_TIME_DAYS, IS_DEFAULT, CREATED_BY)
VALUES ('FRESH-DIRECT', 'fresh', 'Фреш прямой поставкой', 'Fresh prin livrare directă',
        'Fresh via direct delivery',
        '{"window": 35, "level_window": 7, "route": "direct", "waste_cost_pct": 100, "min_cr": 0.72, "max_cr": 0.97, "use_presentation": 1, "use_promo": 1, "exclude_oos": 1}',
        7, 97, 1, 0, 'system');

COMMIT;

-- ==================== Профили фреш-категорий ====================
--
-- Сроки годности и целевые списания взяты как отраслевые ориентиры для
-- продовольственной розницы; менеджер меняет их в разделе «Фреш» под свою сеть.

DECLARE
  PROCEDURE upsert_profile(p_code VARCHAR2, p_temp VARCHAR2, p_shelf NUMBER,
                           p_receipt NUMBER, p_present NUMBER, p_salvage NUMBER,
                           p_waste NUMBER, p_margin NUMBER, p_step NUMBER) IS
    v_cat NUMBER;
  BEGIN
    SELECT ID INTO v_cat FROM PLG_CATEGORIES WHERE CODE = p_code;
    MERGE INTO PLG_FRESH_PROFILES t
    USING (SELECT v_cat AS CATEGORY_ID FROM DUAL) src ON (t.CATEGORY_ID = src.CATEGORY_ID)
    WHEN MATCHED THEN UPDATE SET TEMP_REGIME = p_temp, SHELF_LIFE_DAYS = p_shelf,
         RECEIPT_SHELF_PCT = p_receipt, PRESENTATION_MIN = p_present,
         SALVAGE_PCT = p_salvage, WASTE_TARGET_PCT = p_waste,
         MARGIN_PCT = p_margin, ROUND_STEP = p_step
    WHEN NOT MATCHED THEN INSERT (CATEGORY_ID, TEMP_REGIME, SHELF_LIFE_DAYS, RECEIPT_SHELF_PCT,
                                  PRESENTATION_MIN, SALVAGE_PCT, WASTE_TARGET_PCT, MARGIN_PCT, ROUND_STEP)
         VALUES (v_cat, p_temp, p_shelf, p_receipt, p_present, p_salvage, p_waste, p_margin, p_step);
  EXCEPTION WHEN NO_DATA_FOUND THEN NULL;
  END;
BEGIN
  --              код       режим        срок приёмка выкладка уценка списание маржа шаг
  upsert_profile('bakery',  'ultrafresh',   1,   90,     6,      10,     6,      42,  1);
  upsert_profile('produce', 'chilled',      4,   80,     8,      25,     5,      32,  0.1);
  upsert_profile('dairy',   'chilled',      9,   75,     6,      15,     2.5,    26,  1);
  upsert_profile('meat',    'ultrafresh',   3,   80,     4,      20,     4,      30,  0.1);
  upsert_profile('fish',    'ultrafresh',   2,   85,     3,      15,     5.5,    34,  0.1);
  upsert_profile('frozen',  'frozen',      90,   85,     4,       0,     0.6,    24,  1);
  COMMIT;
END;
/

-- ==================== Разметка фреш-товаров ====================
--
-- Товар считается фреш, если его категория заведена в профилях, кроме
-- заморозки: у неё длинный срок, обычная логика заказа справляется лучше.

UPDATE PLG_PRODUCTS p
   SET IS_FRESH = 1,
       TEMP_REGIME = (SELECT fp.TEMP_REGIME FROM PLG_FRESH_PROFILES fp
                       WHERE fp.CATEGORY_ID = p.CATEGORY_ID),
       SHELF_LIFE_DAYS = NVL(p.SHELF_LIFE_DAYS,
                             (SELECT fp.SHELF_LIFE_DAYS FROM PLG_FRESH_PROFILES fp
                               WHERE fp.CATEGORY_ID = p.CATEGORY_ID)),
       SALVAGE_PCT = (SELECT fp.SALVAGE_PCT FROM PLG_FRESH_PROFILES fp
                       WHERE fp.CATEGORY_ID = p.CATEGORY_ID)
 WHERE p.CATEGORY_ID IN (SELECT fp.CATEGORY_ID FROM PLG_FRESH_PROFILES fp
                          JOIN PLG_CATEGORIES c ON c.ID = fp.CATEGORY_ID
                          WHERE c.CODE <> 'frozen');

-- Себестоимость: из наценки категории, если её не принесли из учётной системы
UPDATE PLG_PRODUCTS p
   SET COST_PRICE = ROUND(p.PRICE / (1 + NVL((SELECT fp.MARGIN_PCT FROM PLG_FRESH_PROFILES fp
                                               WHERE fp.CATEGORY_ID = p.CATEGORY_ID), 28) / 100), 2)
 WHERE p.COST_PRICE IS NULL AND p.PRICE IS NOT NULL;

COMMIT;

-- ==================== Маршруты поставки для существующих наборов ====================
--
-- Разделение отражает практику продовольственной розницы: хлеб и молоко везут
-- прямой поставкой (короткий срок, ежедневный завоз), овощи-фрукты и мясо-рыбу
-- консолидируют через РЦ. Дальше маршрут правится руками в разделе «Фреш».

DECLARE
  v_dc NUMBER;
BEGIN
  FOR st IN (SELECT s.ID AS STORE_ID, s.DATASET_ID FROM PLG_STORES s) LOOP
    BEGIN
      SELECT MIN(d.ID) INTO v_dc FROM PLG_DC d
       WHERE (d.DATASET_ID = st.DATASET_ID OR st.DATASET_ID IS NULL)
         AND NVL(d.HAS_FRESH, 0) = 1;
    EXCEPTION WHEN NO_DATA_FOUND THEN v_dc := NULL;
    END;

    FOR cat IN (SELECT fp.CATEGORY_ID, c.CODE FROM PLG_FRESH_PROFILES fp
                  JOIN PLG_CATEGORIES c ON c.ID = fp.CATEGORY_ID
                 WHERE c.CODE <> 'frozen' ORDER BY fp.CATEGORY_ID) LOOP

      MERGE INTO PLG_FRESH_ROUTES t
      USING (SELECT st.STORE_ID AS STORE_ID, cat.CATEGORY_ID AS CATEGORY_ID FROM DUAL) src
         ON (t.STORE_ID = src.STORE_ID AND t.CATEGORY_ID = src.CATEGORY_ID)
      WHEN NOT MATCHED THEN
        INSERT (DATASET_ID, STORE_ID, CATEGORY_ID, DC_ID, ROUTE,
                LEAD_TIME_DAYS, TRANSIT_DAYS, ORDER_DAYS, DELIVERY_DAYS, CUTOFF_TIME,
                MIN_ORDER_QTY, MIN_ORDER_AMOUNT, NOTES)
        VALUES (st.DATASET_ID, st.STORE_ID, cat.CATEGORY_ID,
                CASE WHEN cat.CODE IN ('bakery','dairy') THEN NULL ELSE v_dc END,
                CASE WHEN cat.CODE IN ('bakery','dairy') THEN 'direct' ELSE 'dc' END,
                CASE WHEN cat.CODE = 'bakery' THEN 0.5
                     WHEN cat.CODE = 'dairy'  THEN 1
                     ELSE 1.5 END,
                CASE WHEN cat.CODE IN ('bakery','dairy') THEN 0 ELSE 0.5 END,
                '1111111',
                CASE WHEN cat.CODE = 'bakery' THEN '1111111'
                     WHEN cat.CODE = 'fish'   THEN '1010100'
                     WHEN cat.CODE = 'meat'   THEN '1101010'
                     ELSE '1111110' END,
                CASE WHEN cat.CODE = 'bakery' THEN '16:00' ELSE '11:00' END,
                0, 0,
                CASE WHEN cat.CODE IN ('bakery','dairy')
                     THEN 'Прямая поставка: короткий срок годности, ежедневный завоз'
                     ELSE 'Через РЦ: консолидация объёма, транзит 0.5 дня' END);
    END LOOP;
  END LOOP;
  COMMIT;
END;
/

-- ==================== Перекомпиляция представлений ====================
--
-- ALTER TABLE выше инвалидирует всё, что смотрит на PLG_PRODUCTS и
-- PLG_FCT_RESULTS. Без этого блока модуль поднимется с невалидными вьюхами.

DECLARE
  v_sql VARCHAR2(400);
BEGIN
  FOR v IN (SELECT OBJECT_NAME FROM USER_OBJECTS
             WHERE OBJECT_TYPE = 'VIEW' AND STATUS = 'INVALID'
               AND OBJECT_NAME LIKE 'V_PLG%') LOOP
    v_sql := 'ALTER VIEW ' || v.OBJECT_NAME || ' COMPILE';
    BEGIN
      EXECUTE IMMEDIATE v_sql;
    EXCEPTION WHEN OTHERS THEN NULL;
    END;
  END LOOP;
END;
/
