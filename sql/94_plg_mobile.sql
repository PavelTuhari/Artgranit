-- ============================================================
-- Планограммы: мобильное приложение и голосовой заказ из зала
--
-- Задача контура: менеджер стоит у полки, видит провал в выкладке и должен
-- заказать товар голосом, не доставая ноутбук и не возвращаясь в кабинет.
--
-- Инженерные решения, зафиксированные в схеме:
--   1. Распознавание речи выполняется НА УСТРОЙСТВЕ (системный ASR iOS/Android),
--      на сервер приходит уже текст. Мы не принимаем аудио: это снимает вопрос
--      хранения голоса сотрудников и требования к каналу.
--   2. Авторизация — по токену устройства, а не по сессии браузера. Токен
--      выдаётся в обмен на код сопряжения, который заводит администратор.
--      В базе хранится SHA-256 токена, не сам токен.
--   3. Голосовой заказ никогда не уходит поставщику напрямую: он создаёт
--      ЧЕРНОВИК, который менеджер подтверждает. Ошибка распознавания не должна
--      превращаться в машину товара.
--   4. Каждая фраза пишется в журнал вместе с разбором — иначе невозможно
--      разобрать спор «я говорил два ящика, приехало двадцать».
--
-- Префикс объектов: PLG_
-- ============================================================

CREATE SEQUENCE PLG_MOB_DEVICE_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_MOB_ORDER_SEQ  START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_MOB_ITEM_SEQ   START WITH 1 INCREMENT BY 1 CACHE 100;
CREATE SEQUENCE PLG_VOICE_LOG_SEQ  START WITH 1 INCREMENT BY 1 CACHE 100;
CREATE SEQUENCE PLG_VOICE_SYN_SEQ  START WITH 1 INCREMENT BY 1 CACHE 100;

-- ==================== Устройства ====================

CREATE TABLE PLG_MOBILE_DEVICES (
  ID           NUMBER        NOT NULL,
  STORE_ID     NUMBER        NOT NULL,
  PAIR_CODE    VARCHAR2(12),                 -- код сопряжения, одноразовый
  TOKEN_HASH   VARCHAR2(64),                 -- SHA-256 токена устройства
  USERNAME     VARCHAR2(150),                -- учётная запись менеджера
  DISPLAY_NAME VARCHAR2(200),
  ROLE_CODE    VARCHAR2(30)  DEFAULT 'manager',  -- manager / merchandiser / viewer
  PLATFORM     VARCHAR2(20),                 -- ios / android
  APP_VERSION  VARCHAR2(20),
  LANG         VARCHAR2(5)   DEFAULT 'ru',
  STATUS       VARCHAR2(20)  DEFAULT 'pending',  -- pending / active / revoked
  ORDER_LIMIT  NUMBER(14,2)  DEFAULT 0,      -- 0 = без лимита суммы заказа
  LAST_SEEN    TIMESTAMP,
  PAIRED_AT    TIMESTAMP,
  CREATED_BY   VARCHAR2(150),
  CREATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_MOBILE_DEVICES PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_MD_PAIR  UNIQUE (PAIR_CODE),
  CONSTRAINT UQ_PLG_MD_TOKEN UNIQUE (TOKEN_HASH),
  CONSTRAINT FK_PLG_MD_STORE FOREIGN KEY (STORE_ID) REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT CHK_PLG_MD_STATUS CHECK (STATUS IN ('pending','active','revoked')),
  CONSTRAINT CHK_PLG_MD_ROLE   CHECK (ROLE_CODE IN ('manager','merchandiser','viewer')),
  CONSTRAINT CHK_PLG_MD_LANG   CHECK (LANG IN ('ru','ro','en'))
);
/

CREATE OR REPLACE TRIGGER PLG_MOBILE_DEVICES_BI
  BEFORE INSERT ON PLG_MOBILE_DEVICES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_MOB_DEVICE_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER PLG_MOBILE_DEVICES_BU
  BEFORE UPDATE ON PLG_MOBILE_DEVICES FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

-- ==================== Заказы из зала ====================

CREATE TABLE PLG_MOBILE_ORDERS (
  ID           NUMBER        NOT NULL,
  ORDER_NO     VARCHAR2(30),
  STORE_ID     NUMBER        NOT NULL,
  DEVICE_ID    NUMBER,
  ZONE_ID      NUMBER,                       -- зона зала, из которой заказывали
  SOURCE       VARCHAR2(20)  DEFAULT 'voice',  -- voice / manual / scan
  STATUS       VARCHAR2(20)  DEFAULT 'draft',  -- draft / submitted / accepted / rejected / cancelled
  LANG         VARCHAR2(5)   DEFAULT 'ru',
  ITEM_COUNT   NUMBER        DEFAULT 0,
  TOTAL_QTY    NUMBER(14,3)  DEFAULT 0,
  TOTAL_AMOUNT NUMBER(16,2)  DEFAULT 0,
  NOTE         VARCHAR2(1000),
  CREATED_BY   VARCHAR2(150),
  REVIEWED_BY  VARCHAR2(150),
  REVIEW_NOTE  VARCHAR2(1000),
  CREATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  SUBMITTED_AT TIMESTAMP,
  REVIEWED_AT  TIMESTAMP,
  CONSTRAINT PK_PLG_MOBILE_ORDERS PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_MO_NO UNIQUE (ORDER_NO),
  CONSTRAINT FK_PLG_MO_STORE  FOREIGN KEY (STORE_ID)  REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_MO_DEVICE FOREIGN KEY (DEVICE_ID) REFERENCES PLG_MOBILE_DEVICES(ID) ON DELETE SET NULL,
  CONSTRAINT FK_PLG_MO_ZONE   FOREIGN KEY (ZONE_ID)   REFERENCES PLG_ZONES(ID) ON DELETE SET NULL,
  CONSTRAINT CHK_PLG_MO_SOURCE CHECK (SOURCE IN ('voice','manual','scan')),
  CONSTRAINT CHK_PLG_MO_STATUS CHECK (STATUS IN ('draft','submitted','accepted','rejected','cancelled'))
);
/

CREATE OR REPLACE TRIGGER PLG_MOBILE_ORDERS_BI
  BEFORE INSERT ON PLG_MOBILE_ORDERS FOR EACH ROW
BEGIN
  IF :NEW.ID IS NULL THEN :NEW.ID := PLG_MOB_ORDER_SEQ.NEXTVAL; END IF;
  IF :NEW.ORDER_NO IS NULL THEN
    :NEW.ORDER_NO := 'MOB-' || TO_CHAR(SYSDATE, 'YYYYMMDD') || '-' || LPAD(:NEW.ID, 6, '0');
  END IF;
END;
/

CREATE INDEX IX_PLG_MOB_ORD_STORE ON PLG_MOBILE_ORDERS (STORE_ID, STATUS, CREATED_AT);

CREATE TABLE PLG_MOBILE_ORDER_ITEMS (
  ID          NUMBER        NOT NULL,
  ORDER_ID    NUMBER        NOT NULL,
  PRODUCT_ID  NUMBER,                        -- NULL = товар не опознан, нужен выбор вручную
  QTY         NUMBER(14,3)  DEFAULT 0,
  UOM         VARCHAR2(20)  DEFAULT 'pcs',
  PACK_QTY    NUMBER(10,3),                  -- если сказали «два ящика» — сколько в ящике
  PRICE       NUMBER(14,2),
  SOURCE_TEXT VARCHAR2(600),                 -- фрагмент фразы, породивший позицию
  MATCH_NAME  VARCHAR2(300),                 -- на что сопоставили
  CONFIDENCE  NUMBER(5,2),                   -- 0..100, уверенность сопоставления
  STATUS      VARCHAR2(20)  DEFAULT 'ok',    -- ok / ambiguous / unmatched / removed
  SORT_ORDER  NUMBER        DEFAULT 0,
  CREATED_AT  TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_MOBILE_ORDER_ITEMS PRIMARY KEY (ID),
  CONSTRAINT FK_PLG_MOI_ORDER FOREIGN KEY (ORDER_ID)   REFERENCES PLG_MOBILE_ORDERS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_MOI_PROD  FOREIGN KEY (PRODUCT_ID) REFERENCES PLG_PRODUCTS(ID) ON DELETE SET NULL,
  CONSTRAINT CHK_PLG_MOI_STATUS CHECK (STATUS IN ('ok','ambiguous','unmatched','removed'))
);
/

CREATE OR REPLACE TRIGGER PLG_MOBILE_ORDER_ITEMS_BI
  BEFORE INSERT ON PLG_MOBILE_ORDER_ITEMS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_MOB_ITEM_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_PLG_MOB_ITEMS_ORD ON PLG_MOBILE_ORDER_ITEMS (ORDER_ID);

-- ==================== Журнал распознавания ====================

CREATE TABLE PLG_VOICE_LOG (
  ID           NUMBER        NOT NULL,
  DEVICE_ID    NUMBER,
  STORE_ID     NUMBER,
  ORDER_ID     NUMBER,
  LANG         VARCHAR2(5),
  RAW_TEXT     VARCHAR2(2000)  NOT NULL,     -- что распознало устройство
  INTENT       VARCHAR2(30),                 -- add / remove / set / submit / cancel / query / unknown
  PARSED_JSON  CLOB,                         -- разбор целиком, для разбора споров
  ITEM_COUNT   NUMBER        DEFAULT 0,
  MATCHED      NUMBER        DEFAULT 0,
  UNMATCHED    NUMBER        DEFAULT 0,
  CONFIDENCE   NUMBER(5,2),
  ASR_CONF     NUMBER(5,2),                  -- уверенность распознавания на устройстве
  DURATION_MS  NUMBER,
  USERNAME     VARCHAR2(150),
  CREATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_VOICE_LOG PRIMARY KEY (ID),
  CONSTRAINT FK_PLG_VL_DEVICE FOREIGN KEY (DEVICE_ID) REFERENCES PLG_MOBILE_DEVICES(ID) ON DELETE SET NULL,
  CONSTRAINT FK_PLG_VL_STORE  FOREIGN KEY (STORE_ID)  REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_VL_ORDER  FOREIGN KEY (ORDER_ID)  REFERENCES PLG_MOBILE_ORDERS(ID) ON DELETE SET NULL
);
/

CREATE OR REPLACE TRIGGER PLG_VOICE_LOG_BI
  BEFORE INSERT ON PLG_VOICE_LOG FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_VOICE_LOG_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_PLG_VOICE_LOG_ST ON PLG_VOICE_LOG (STORE_ID, CREATED_AT);

-- ==================== Речевые синонимы ====================
--
-- В зале говорят не так, как записано в карточке: «помидоры» вместо
-- «Томаты грунтовые, кг», «полторашка» вместо «Вода 1.5 л». Словарь
-- пополняется оператором и автоматически — из подтверждённых разборов.

CREATE TABLE PLG_VOICE_SYNONYMS (
  ID          NUMBER        NOT NULL,
  PRODUCT_ID  NUMBER,
  CATEGORY_ID NUMBER,
  LANG        VARCHAR2(5)   DEFAULT 'ru',
  PHRASE      VARCHAR2(200) NOT NULL,        -- нормализованная фраза
  WEIGHT      NUMBER(5,2)   DEFAULT 1,       -- вклад в уверенность сопоставления
  HIT_COUNT   NUMBER        DEFAULT 0,
  SOURCE      VARCHAR2(20)  DEFAULT 'manual',  -- manual / learned
  CREATED_BY  VARCHAR2(150),
  CREATED_AT  TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_VOICE_SYNONYMS PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_VS UNIQUE (LANG, PHRASE, PRODUCT_ID, CATEGORY_ID),
  CONSTRAINT FK_PLG_VS_PROD FOREIGN KEY (PRODUCT_ID)  REFERENCES PLG_PRODUCTS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_VS_CAT  FOREIGN KEY (CATEGORY_ID) REFERENCES PLG_CATEGORIES(ID) ON DELETE CASCADE,
  CONSTRAINT CHK_PLG_VS_LANG CHECK (LANG IN ('ru','ro','en')),
  CONSTRAINT CHK_PLG_VS_SRC  CHECK (SOURCE IN ('manual','learned'))
);
/

CREATE OR REPLACE TRIGGER PLG_VOICE_SYNONYMS_BI
  BEFORE INSERT ON PLG_VOICE_SYNONYMS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_VOICE_SYN_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_PLG_VOICE_SYN_PH ON PLG_VOICE_SYNONYMS (LANG, PHRASE);

-- ==================== Представления ====================

CREATE OR REPLACE VIEW V_PLG_MOBILE_DEVICES AS
SELECT
  d.ID, d.STORE_ID, s.CODE AS STORE_CODE,
  s.NAME_RU AS STORE_NAME_RU, s.NAME_RO AS STORE_NAME_RO, s.NAME_EN AS STORE_NAME_EN,
  d.PAIR_CODE, d.USERNAME, d.DISPLAY_NAME, d.ROLE_CODE, d.PLATFORM, d.APP_VERSION,
  d.LANG, d.STATUS, d.ORDER_LIMIT, d.LAST_SEEN, d.PAIRED_AT, d.CREATED_BY, d.CREATED_AT,
  CASE WHEN d.TOKEN_HASH IS NULL THEN 0 ELSE 1 END AS IS_PAIRED,
  (SELECT COUNT(*) FROM PLG_MOBILE_ORDERS o WHERE o.DEVICE_ID = d.ID) AS ORDER_COUNT,
  (SELECT COUNT(*) FROM PLG_VOICE_LOG v WHERE v.DEVICE_ID = d.ID)     AS VOICE_COUNT
FROM PLG_MOBILE_DEVICES d
JOIN PLG_STORES s ON s.ID = d.STORE_ID;

CREATE OR REPLACE VIEW V_PLG_MOBILE_ORDERS AS
SELECT
  o.ID, o.ORDER_NO, o.STORE_ID, s.CODE AS STORE_CODE,
  s.NAME_RU AS STORE_NAME_RU, s.NAME_RO AS STORE_NAME_RO, s.NAME_EN AS STORE_NAME_EN,
  o.DEVICE_ID, d.DISPLAY_NAME AS DEVICE_NAME, d.PLATFORM,
  o.ZONE_ID, z.NAME_RU AS ZONE_NAME_RU, z.NAME_RO AS ZONE_NAME_RO, z.NAME_EN AS ZONE_NAME_EN,
  o.SOURCE, o.STATUS, o.LANG, o.ITEM_COUNT, o.TOTAL_QTY, o.TOTAL_AMOUNT, o.NOTE,
  o.CREATED_BY, o.REVIEWED_BY, o.REVIEW_NOTE,
  o.CREATED_AT, o.SUBMITTED_AT, o.REVIEWED_AT,
  (SELECT COUNT(*) FROM PLG_MOBILE_ORDER_ITEMS i
    WHERE i.ORDER_ID = o.ID AND i.STATUS IN ('unmatched','ambiguous')) AS NEEDS_ATTENTION
FROM PLG_MOBILE_ORDERS o
JOIN PLG_STORES s ON s.ID = o.STORE_ID
LEFT JOIN PLG_MOBILE_DEVICES d ON d.ID = o.DEVICE_ID
LEFT JOIN PLG_ZONES z ON z.ID = o.ZONE_ID;

CREATE OR REPLACE VIEW V_PLG_MOBILE_ORDER_ITEMS AS
SELECT
  i.ID, i.ORDER_ID, i.PRODUCT_ID,
  p.CODE AS PRODUCT_CODE, p.NAME_RU AS PRODUCT_NAME_RU,
  p.NAME_RO AS PRODUCT_NAME_RO, p.NAME_EN AS PRODUCT_NAME_EN,
  p.BARCODE, p.ORDER_MULTIPLE, NVL(p.IS_FRESH, 0) AS IS_FRESH,
  c.NAME_RU AS CATEGORY_NAME_RU, c.NAME_RO AS CATEGORY_NAME_RO, c.NAME_EN AS CATEGORY_NAME_EN,
  i.QTY, i.UOM, i.PACK_QTY, i.PRICE, ROUND(i.QTY * NVL(i.PRICE, p.PRICE), 2) AS AMOUNT,
  i.SOURCE_TEXT, i.MATCH_NAME, i.CONFIDENCE, i.STATUS, i.SORT_ORDER, i.CREATED_AT
FROM PLG_MOBILE_ORDER_ITEMS i
LEFT JOIN PLG_PRODUCTS p   ON p.ID = i.PRODUCT_ID
LEFT JOIN PLG_CATEGORIES c ON c.ID = p.CATEGORY_ID;

CREATE OR REPLACE VIEW V_PLG_VOICE_LOG AS
SELECT
  v.ID, v.DEVICE_ID, d.DISPLAY_NAME AS DEVICE_NAME, d.PLATFORM,
  v.STORE_ID, s.CODE AS STORE_CODE,
  s.NAME_RU AS STORE_NAME_RU, s.NAME_RO AS STORE_NAME_RO, s.NAME_EN AS STORE_NAME_EN,
  v.ORDER_ID, o.ORDER_NO, o.STATUS AS ORDER_STATUS,
  v.LANG, v.RAW_TEXT, v.INTENT, v.ITEM_COUNT, v.MATCHED, v.UNMATCHED,
  v.CONFIDENCE, v.ASR_CONF, v.DURATION_MS, v.USERNAME, v.CREATED_AT
FROM PLG_VOICE_LOG v
LEFT JOIN PLG_MOBILE_DEVICES d ON d.ID = v.DEVICE_ID
LEFT JOIN PLG_STORES s         ON s.ID = v.STORE_ID
LEFT JOIN PLG_MOBILE_ORDERS o  ON o.ID = v.ORDER_ID;
/

-- ==================== Базовые речевые синонимы ====================
--
-- Заводятся на КАТЕГОРИЮ, а не на SKU: они работают как подсказка, куда
-- смотреть, когда точного совпадения по названию товара нет.

DECLARE
  PROCEDURE syn(p_cat VARCHAR2, p_lang VARCHAR2, p_phrase VARCHAR2) IS
    v_cat NUMBER;
  BEGIN
    SELECT ID INTO v_cat FROM PLG_CATEGORIES WHERE CODE = p_cat;
    INSERT INTO PLG_VOICE_SYNONYMS (CATEGORY_ID, LANG, PHRASE, SOURCE, CREATED_BY)
    VALUES (v_cat, p_lang, p_phrase, 'manual', 'system');
  EXCEPTION WHEN OTHERS THEN NULL;   -- дубль или отсутствующая категория — не повод падать
  END;
BEGIN
  syn('produce', 'ru', 'овощи');       syn('produce', 'ru', 'фрукты');
  syn('produce', 'ru', 'зелень');      syn('produce', 'ro', 'legume');
  syn('produce', 'ro', 'fructe');      syn('produce', 'en', 'produce');
  syn('bakery',  'ru', 'хлеб');        syn('bakery',  'ru', 'выпечка');
  syn('bakery',  'ro', 'paine');       syn('bakery',  'en', 'bread');
  syn('dairy',   'ru', 'молочка');     syn('dairy',   'ru', 'молочные');
  syn('dairy',   'ro', 'lactate');     syn('dairy',   'en', 'dairy');
  syn('meat',    'ru', 'мясо');        syn('meat',    'ro', 'carne');
  syn('meat',    'en', 'meat');        syn('fish',    'ru', 'рыба');
  syn('fish',    'ro', 'peste');       syn('fish',    'en', 'fish');
  syn('drinks',  'ru', 'вода');        syn('drinks',  'ru', 'напитки');
  syn('drinks',  'ro', 'bauturi');     syn('drinks',  'en', 'drinks');
  COMMIT;
END;
/
