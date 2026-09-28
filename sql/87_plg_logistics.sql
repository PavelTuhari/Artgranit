-- ============================================================
-- Планограммы: логистика завоза товара
--
-- Схема сети: РЦ + прямые поставки.
--   inbound   поставщик → РЦ        (крупные фуры, паллетный завоз)
--   transfer  РЦ → магазин          (развозка по маршруту)
--   direct    поставщик → магазин   (фреш: хлеб, молоко, мясо)
--
-- Диаграмма Ганта строится по PLG_SHIPMENTS: строка = машина либо док,
-- полоса = окно от PLANNED_START до PLANNED_END, факт — ACTUAL_*.
--
-- Набор данных наследуется от корневых сущностей (PLG_DC, PLG_VEHICLES,
-- PLG_SUPPLIERS), рейсы удаляются каскадом вместе с ними.
-- Префикс объектов: PLG_
-- ============================================================

CREATE SEQUENCE PLG_DC_SEQ            START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_VEHICLES_SEQ      START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_SHIPMENTS_SEQ     START WITH 1 INCREMENT BY 1 CACHE 100;
CREATE SEQUENCE PLG_SHIP_LINES_SEQ    START WITH 1 INCREMENT BY 1 CACHE 1000;
CREATE SEQUENCE PLG_SHIPMENT_NUM_SEQ  START WITH 100001 INCREMENT BY 1 CACHE 100;

-- ==================== Справочники ====================

-- Типы транспорта: от фуры до фургона, с температурным режимом
CREATE TABLE PLG_REF_VEHICLE_TYPES (
  CODE         VARCHAR2(20)  NOT NULL,   -- truck / reefer / van / tautliner
  NAME_RU      VARCHAR2(100) NOT NULL,
  NAME_RO      VARCHAR2(100) NOT NULL,
  NAME_EN      VARCHAR2(100) NOT NULL,
  CAPACITY_KG  NUMBER        DEFAULT 20000,
  VOLUME_M3    NUMBER(8,2)   DEFAULT 82,
  PALLET_SLOTS NUMBER        DEFAULT 33,
  IS_REEFER    NUMBER(1)     DEFAULT 0,  -- рефрижератор
  COLOR        VARCHAR2(20),
  ICON         VARCHAR2(10),
  SORT_ORDER   NUMBER        DEFAULT 0,
  CONSTRAINT PK_PLG_REF_VEHICLE_TYPES PRIMARY KEY (CODE),
  CONSTRAINT CHK_PLG_VT_REEFER CHECK (IS_REEFER IN (0,1))
);

-- Типы рейса: плечо доставки
CREATE TABLE PLG_REF_SHIPMENT_TYPES (
  CODE       VARCHAR2(20)  NOT NULL,     -- inbound / transfer / direct / return
  NAME_RU    VARCHAR2(100) NOT NULL,
  NAME_RO    VARCHAR2(100) NOT NULL,
  NAME_EN    VARCHAR2(100) NOT NULL,
  DESCR_RU   VARCHAR2(400),
  DESCR_RO   VARCHAR2(400),
  DESCR_EN   VARCHAR2(400),
  COLOR      VARCHAR2(20),
  SORT_ORDER NUMBER DEFAULT 0,
  CONSTRAINT PK_PLG_REF_SHIPMENT_TYPES PRIMARY KEY (CODE)
);

-- ==================== Логистические центры ====================

CREATE TABLE PLG_DC (
  ID           NUMBER        NOT NULL,
  DATASET_ID   NUMBER,
  CODE         VARCHAR2(30)  NOT NULL,
  NAME_RU      VARCHAR2(200) NOT NULL,
  NAME_RO      VARCHAR2(200),
  NAME_EN      VARCHAR2(200),
  CITY         VARCHAR2(100),
  ADDRESS_RU   VARCHAR2(400),
  ADDRESS_RO   VARCHAR2(400),
  ADDRESS_EN   VARCHAR2(400),
  AREA_SQM     NUMBER(12,2),
  DOCK_COUNT   NUMBER        DEFAULT 12,  -- число ворот погрузки/разгрузки
  PALLET_SLOTS NUMBER        DEFAULT 8000,
  WORK_FROM    VARCHAR2(5)   DEFAULT '06:00',
  WORK_TO      VARCHAR2(5)   DEFAULT '22:00',
  HAS_FRESH    NUMBER(1)     DEFAULT 1,   -- холодильные камеры
  MANAGER_NAME VARCHAR2(150),
  STATUS       VARCHAR2(20)  DEFAULT 'active',
  CREATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_DC PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_DC_CODE UNIQUE (CODE),
  CONSTRAINT FK_PLG_DC_DS FOREIGN KEY (DATASET_ID) REFERENCES PLG_DATASETS(ID),
  CONSTRAINT CHK_PLG_DC_STATUS CHECK (STATUS IN ('active','inactive','construction')),
  CONSTRAINT CHK_PLG_DC_FRESH  CHECK (HAS_FRESH IN (0,1))
);
/

CREATE OR REPLACE TRIGGER PLG_DC_BI
  BEFORE INSERT ON PLG_DC FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_DC_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER PLG_DC_BU
  BEFORE UPDATE ON PLG_DC FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

-- Зона обслуживания: какие магазины закреплены за РЦ
CREATE TABLE PLG_DC_STORES (
  DC_ID        NUMBER NOT NULL,
  STORE_ID     NUMBER NOT NULL,
  DISTANCE_KM  NUMBER(8,2),
  DRIVE_MIN    NUMBER,
  DELIVERY_DOW VARCHAR2(20),   -- дни развозки: '1,3,5'
  CONSTRAINT PK_PLG_DC_STORES PRIMARY KEY (DC_ID, STORE_ID),
  CONSTRAINT FK_PLG_DCS_DC    FOREIGN KEY (DC_ID) REFERENCES PLG_DC(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_DCS_STORE FOREIGN KEY (STORE_ID) REFERENCES PLG_STORES(ID) ON DELETE CASCADE
);

-- ==================== Транспорт ====================

CREATE TABLE PLG_VEHICLES (
  ID           NUMBER        NOT NULL,
  DATASET_ID   NUMBER,
  CODE         VARCHAR2(30)  NOT NULL,
  PLATE_NO     VARCHAR2(20),               -- госномер
  VEHICLE_TYPE VARCHAR2(20)  NOT NULL,
  CARRIER      VARCHAR2(150),              -- перевозчик (свой парк или подрядчик)
  IS_OWN       NUMBER(1)     DEFAULT 1,
  CAPACITY_KG  NUMBER,
  VOLUME_M3    NUMBER(8,2),
  PALLET_SLOTS NUMBER,
  DRIVER_NAME  VARCHAR2(150),
  HOME_DC_ID   NUMBER,                     -- базовый РЦ
  STATUS       VARCHAR2(20)  DEFAULT 'active',
  CREATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_VEHICLES PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_VEH_CODE UNIQUE (CODE),
  CONSTRAINT FK_PLG_VEH_DS   FOREIGN KEY (DATASET_ID) REFERENCES PLG_DATASETS(ID),
  CONSTRAINT FK_PLG_VEH_TYPE FOREIGN KEY (VEHICLE_TYPE) REFERENCES PLG_REF_VEHICLE_TYPES(CODE),
  CONSTRAINT FK_PLG_VEH_DC   FOREIGN KEY (HOME_DC_ID) REFERENCES PLG_DC(ID) ON DELETE SET NULL,
  CONSTRAINT CHK_PLG_VEH_OWN    CHECK (IS_OWN IN (0,1)),
  CONSTRAINT CHK_PLG_VEH_STATUS CHECK (STATUS IN ('active','repair','decommissioned'))
);
/

CREATE OR REPLACE TRIGGER PLG_VEHICLES_BI
  BEFORE INSERT ON PLG_VEHICLES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_VEHICLES_SEQ.NEXTVAL;
END;
/

-- ==================== Рейсы завоза ====================

CREATE TABLE PLG_SHIPMENTS (
  ID             NUMBER        NOT NULL,
  CODE           VARCHAR2(30)  NOT NULL,   -- SHP-2026-100001
  SHIPMENT_TYPE  VARCHAR2(20)  NOT NULL,
  SUPPLIER_ID    NUMBER,                   -- источник для inbound / direct
  DC_ID          NUMBER,                   -- РЦ: приёмник (inbound) или отправитель (transfer)
  STORE_ID       NUMBER,                   -- приёмник для transfer / direct
  VEHICLE_ID     NUMBER,
  DOCK_NO        NUMBER,                   -- ворота разгрузки
  PLANNED_START  TIMESTAMP     NOT NULL,
  PLANNED_END    TIMESTAMP     NOT NULL,
  ACTUAL_START   TIMESTAMP,
  ACTUAL_END     TIMESTAMP,
  STATUS         VARCHAR2(20)  DEFAULT 'planned',
  TEMP_MODE      VARCHAR2(20)  DEFAULT 'ambient',  -- ambient / chilled / frozen
  PALLETS        NUMBER        DEFAULT 0,
  WEIGHT_KG      NUMBER(12,2)  DEFAULT 0,
  VOLUME_M3      NUMBER(10,2)  DEFAULT 0,
  AMOUNT         NUMBER(16,2)  DEFAULT 0,
  DISTANCE_KM    NUMBER(8,2),
  DELAY_MIN      NUMBER        DEFAULT 0,  -- фактическое опоздание к окну
  NOTES          VARCHAR2(1000),
  CREATED_AT     TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT     TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_SHIPMENTS PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_SHP_CODE UNIQUE (CODE),
  CONSTRAINT FK_PLG_SHP_TYPE  FOREIGN KEY (SHIPMENT_TYPE) REFERENCES PLG_REF_SHIPMENT_TYPES(CODE),
  CONSTRAINT FK_PLG_SHP_DC    FOREIGN KEY (DC_ID) REFERENCES PLG_DC(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_SHP_STORE FOREIGN KEY (STORE_ID) REFERENCES PLG_STORES(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_SHP_VEH   FOREIGN KEY (VEHICLE_ID) REFERENCES PLG_VEHICLES(ID) ON DELETE SET NULL,
  CONSTRAINT CHK_PLG_SHP_STATUS CHECK (STATUS IN ('planned','in_transit','unloading','done','delayed','cancelled')),
  CONSTRAINT CHK_PLG_SHP_TEMP   CHECK (TEMP_MODE IN ('ambient','chilled','frozen')),
  CONSTRAINT CHK_PLG_SHP_WINDOW CHECK (PLANNED_END > PLANNED_START)
);
/

CREATE OR REPLACE TRIGGER PLG_SHIPMENTS_BI
  BEFORE INSERT ON PLG_SHIPMENTS FOR EACH ROW
BEGIN
  IF :NEW.ID IS NULL THEN
    :NEW.ID := PLG_SHIPMENTS_SEQ.NEXTVAL;
  END IF;
  IF :NEW.CODE IS NULL THEN
    :NEW.CODE := 'SHP-' || TO_CHAR(SYSDATE, 'YYYY') || '-' ||
                 TO_CHAR(PLG_SHIPMENT_NUM_SEQ.NEXTVAL);
  END IF;
END;
/

CREATE OR REPLACE TRIGGER PLG_SHIPMENTS_BU
  BEFORE UPDATE ON PLG_SHIPMENTS FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

CREATE INDEX IX_PLG_SHP_WINDOW ON PLG_SHIPMENTS (PLANNED_START, PLANNED_END);
CREATE INDEX IX_PLG_SHP_STORE  ON PLG_SHIPMENTS (STORE_ID, PLANNED_START);
CREATE INDEX IX_PLG_SHP_DC     ON PLG_SHIPMENTS (DC_ID, PLANNED_START);
CREATE INDEX IX_PLG_SHP_VEH    ON PLG_SHIPMENTS (VEHICLE_ID, PLANNED_START);

-- Состав рейса
CREATE TABLE PLG_SHIPMENT_LINES (
  ID          NUMBER       NOT NULL,
  SHIPMENT_ID NUMBER       NOT NULL,
  PRODUCT_ID  NUMBER       NOT NULL,
  QTY         NUMBER(12,3) DEFAULT 0,
  PALLETS     NUMBER(8,2)  DEFAULT 0,
  AMOUNT      NUMBER(14,2) DEFAULT 0,
  CONSTRAINT PK_PLG_SHIPMENT_LINES PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_SHL UNIQUE (SHIPMENT_ID, PRODUCT_ID),
  CONSTRAINT FK_PLG_SHL_SHP  FOREIGN KEY (SHIPMENT_ID) REFERENCES PLG_SHIPMENTS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_SHL_PROD FOREIGN KEY (PRODUCT_ID) REFERENCES PLG_PRODUCTS(ID) ON DELETE CASCADE
);
/

CREATE OR REPLACE TRIGGER PLG_SHIP_LINES_BI
  BEFORE INSERT ON PLG_SHIPMENT_LINES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_SHIP_LINES_SEQ.NEXTVAL;
END;
/

-- ==================== Наполнение справочников ====================

INSERT INTO PLG_REF_VEHICLE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, CAPACITY_KG, VOLUME_M3, PALLET_SLOTS, IS_REEFER, COLOR, ICON, SORT_ORDER) VALUES
('truck',     'Фура (тент)',        'Camion (prelată)',    'Tautliner truck', 20000, 86, 33, 0, '#2563eb', '▬', 1);
INSERT INTO PLG_REF_VEHICLE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, CAPACITY_KG, VOLUME_M3, PALLET_SLOTS, IS_REEFER, COLOR, ICON, SORT_ORDER) VALUES
('reefer',    'Рефрижератор',       'Camion frigorific',   'Reefer truck',    18000, 78, 32, 1, '#0891b2', '❄', 2);
INSERT INTO PLG_REF_VEHICLE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, CAPACITY_KG, VOLUME_M3, PALLET_SLOTS, IS_REEFER, COLOR, ICON, SORT_ORDER) VALUES
('midi',      'Среднетоннажник',    'Camion mediu',        'Midi truck',       8000, 40, 16, 0, '#7c3aed', '▭', 3);
INSERT INTO PLG_REF_VEHICLE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, CAPACITY_KG, VOLUME_M3, PALLET_SLOTS, IS_REEFER, COLOR, ICON, SORT_ORDER) VALUES
('van',       'Фургон',             'Furgonetă',           'Van',              1500, 14,  6, 0, '#16a34a', '▫', 4);
INSERT INTO PLG_REF_VEHICLE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, CAPACITY_KG, VOLUME_M3, PALLET_SLOTS, IS_REEFER, COLOR, ICON, SORT_ORDER) VALUES
('van_fresh', 'Фургон-рефрижератор','Furgonetă frigorifică','Fresh van',        1200, 12,  5, 1, '#f59e0b', '❅', 5);

INSERT INTO PLG_REF_SHIPMENT_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, COLOR, SORT_ORDER) VALUES
('inbound',  'Поставщик → РЦ',      'Furnizor → CD',      'Supplier → DC',
 'Приёмка на распределительный центр: паллетный завоз крупными машинами.',
 'Recepție la centrul de distribuție: livrare paletizată cu camioane mari.',
 'Inbound to the distribution centre: palletised delivery by large trucks.',
 '#2563eb', 1);
INSERT INTO PLG_REF_SHIPMENT_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, COLOR, SORT_ORDER) VALUES
('transfer', 'РЦ → магазин',        'CD → magazin',       'DC → store',
 'Развозка по магазинам сети со склада РЦ по расписанию маршрута.',
 'Distribuție către magazine din depozitul CD conform rutei.',
 'Distribution to stores from the DC warehouse along the route schedule.',
 '#16a34a', 2);
INSERT INTO PLG_REF_SHIPMENT_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, COLOR, SORT_ORDER) VALUES
('direct',   'Поставщик → магазин', 'Furnizor → magazin', 'Supplier → store',
 'Прямой завоз минуя РЦ: скоропортящееся (хлеб, молоко, мясо) и локальные поставщики.',
 'Livrare directă, ocolind CD: produse perisabile și furnizori locali.',
 'Direct delivery bypassing the DC: perishables and local suppliers.',
 '#d97706', 3);
INSERT INTO PLG_REF_SHIPMENT_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, COLOR, SORT_ORDER) VALUES
('return',   'Возврат',             'Retur',              'Return',
 'Обратный рейс: возврат тары, брака и просроченного товара поставщику или на РЦ.',
 'Cursă de retur: ambalaje, marfă defectă și expirată.',
 'Return trip: packaging, damaged and expired goods.',
 '#94a3b8', 4);

COMMIT;
