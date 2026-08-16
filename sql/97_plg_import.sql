-- ============================================================
-- Планограммы: заказы импорта товара из-за границы
--
-- Импорт отличается от внутреннего заказа не количеством полей, а тем, что
-- между «заказали» и «на полке» стоит десяток шагов с внешними участниками:
-- контракт, проформа, оплата, производство, отгрузка, граница, растаможка,
-- выпуск. Каждый шаг умеет задерживаться, и задержка на таможне из-за
-- неготового сертификата стоит дороже самой пошлины.
--
-- Три решения, зафиксированных в схеме:
--
--   1. Этапы — это ДАННЫЕ (справочник PLG_REF_IMP_STAGES + журнал
--      PLG_IMPORT_STAGE_LOG с плановой и фактической датой). Задержка не
--      вводится руками — она вычисляется как факт минус план, и по журналу
--      видно, на каком этапе теряются дни у какого поставщика.
--
--   2. Документы — УПРЕЖДАЮЩИЙ чек-лист (PLG_IMPORT_DOCS): инвойс, упаковочный,
--      CMR, EUR.1, сертификаты, ЛОКАЛИЗОВАННЫЕ ЭТИКЕТКИ. Чек-лист заводится
--      при создании заказа с дедлайнами ДО прибытия машины на границу:
--      документ, которого хватились на таможне, — это дни простоя и штраф
--      за сверхнормативное хранение.
--
--   3. Позиции несут код ТН ВЭД (HS_CODE) и страну происхождения — без них
--      невозможно ни посчитать пошлину заранее, ни подать декларацию.
--
-- Бизнес-процессы: scripts/gen_plg_processes.py (import-order,
-- customs-clearance, import-docs). Префикс объектов: PLG_
-- ============================================================

CREATE SEQUENCE PLG_IMP_ORDER_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PLG_IMP_ITEM_SEQ  START WITH 1 INCREMENT BY 1 CACHE 100;
CREATE SEQUENCE PLG_IMP_STAGE_SEQ START WITH 1 INCREMENT BY 1 CACHE 100;
CREATE SEQUENCE PLG_IMP_DOC_SEQ   START WITH 1 INCREMENT BY 1 CACHE 100;

-- ==================== Справочник этапов ====================

CREATE TABLE PLG_REF_IMP_STAGES (
  CODE        VARCHAR2(30)  NOT NULL,
  NAME_RU     VARCHAR2(150) NOT NULL,
  NAME_RO     VARCHAR2(150),
  NAME_EN     VARCHAR2(150),
  SORT_ORDER  NUMBER        NOT NULL,
  IS_CUSTOMS  NUMBER(1)     DEFAULT 0,     -- этап таможенного контура
  TYPICAL_DAYS NUMBER       DEFAULT 1,     -- типовая длительность, для плана
  CONSTRAINT PK_PLG_REF_IMP_STAGES PRIMARY KEY (CODE),
  CONSTRAINT CHK_PLG_RIS_CUST CHECK (IS_CUSTOMS IN (0,1))
);

MERGE INTO PLG_REF_IMP_STAGES t USING (
  SELECT 'draft' CODE, 'Черновик заказа' RU, 'Ciornă comandă' RO, 'Draft' EN, 1 SRT, 0 CUST, 1 DAYS FROM DUAL UNION ALL
  SELECT 'contract',  'Контракт и спецификация', 'Contract și specificație', 'Contract & specification', 2, 0, 5 FROM DUAL UNION ALL
  SELECT 'proforma',  'Проформа-инвойс',        'Factură proformă',          'Proforma invoice',          3, 0, 2 FROM DUAL UNION ALL
  SELECT 'payment',   'Оплата / аккредитив',    'Plată / acreditiv',         'Payment / L.C.',            4, 0, 3 FROM DUAL UNION ALL
  SELECT 'production','Производство и подготовка','Producție și pregătire',  'Production & preparation',  5, 0, 10 FROM DUAL UNION ALL
  SELECT 'shipment',  'Отгрузка и транзит',     'Expediere și tranzit',      'Shipment & transit',        6, 0, 4 FROM DUAL UNION ALL
  SELECT 'border',    'Прибытие на границу',    'Sosire la frontieră',       'Border arrival',            7, 1, 1 FROM DUAL UNION ALL
  SELECT 'customs_docs','Подача декларации и документов','Depunerea declarației','Customs declaration filed', 8, 1, 1 FROM DUAL UNION ALL
  SELECT 'customs',   'Таможенный контроль',    'Control vamal',             'Customs control',           9, 1, 2 FROM DUAL UNION ALL
  SELECT 'release',   'Выпуск в свободное обращение','Liber de vamă',        'Customs release',          10, 1, 1 FROM DUAL UNION ALL
  SELECT 'delivered', 'Доставлено на склад',    'Livrat la depozit',         'Delivered to warehouse',   11, 0, 1 FROM DUAL
) s ON (t.CODE = s.CODE)
WHEN MATCHED THEN UPDATE SET NAME_RU = s.RU, NAME_RO = s.RO, NAME_EN = s.EN,
     SORT_ORDER = s.SRT, IS_CUSTOMS = s.CUST, TYPICAL_DAYS = s.DAYS
WHEN NOT MATCHED THEN INSERT (CODE, NAME_RU, NAME_RO, NAME_EN, SORT_ORDER, IS_CUSTOMS, TYPICAL_DAYS)
     VALUES (s.CODE, s.RU, s.RO, s.EN, s.SRT, s.CUST, s.DAYS);

COMMIT;

-- ==================== Справочник документов ====================

CREATE TABLE PLG_REF_IMP_DOCS (
  CODE        VARCHAR2(30)  NOT NULL,
  NAME_RU     VARCHAR2(200) NOT NULL,
  NAME_RO     VARCHAR2(200),
  NAME_EN     VARCHAR2(200),
  SORT_ORDER  NUMBER        NOT NULL,
  IS_CUSTOMS  NUMBER(1)     DEFAULT 1,     -- нужен для растаможки
  LEAD_DAYS   NUMBER        DEFAULT 3,     -- за сколько дней до границы должен быть готов
  CONSTRAINT PK_PLG_REF_IMP_DOCS PRIMARY KEY (CODE)
);

MERGE INTO PLG_REF_IMP_DOCS t USING (
  SELECT 'invoice' CODE, 'Коммерческий инвойс' RU, 'Factură comercială' RO, 'Commercial invoice' EN, 1 SRT, 1 CUST, 5 LEAD FROM DUAL UNION ALL
  SELECT 'packing',    'Упаковочный лист',            'Listă de ambalare',          'Packing list',              2, 1, 5 FROM DUAL UNION ALL
  SELECT 'cmr',        'CMR / транспортная накладная','CMR / scrisoare de trăsură', 'CMR / waybill',             3, 1, 2 FROM DUAL UNION ALL
  SELECT 'eur1',       'EUR.1 (преференциальное происхождение)','EUR.1 (origine preferențială)','EUR.1 (preferential origin)', 4, 1, 4 FROM DUAL UNION ALL
  SELECT 'origin',     'Сертификат происхождения',    'Certificat de origine',      'Certificate of origin',     5, 1, 4 FROM DUAL UNION ALL
  SELECT 'conformity', 'Сертификат соответствия',     'Certificat de conformitate', 'Certificate of conformity', 6, 1, 7 FROM DUAL UNION ALL
  SELECT 'phyto',      'Фитосанитарный / ветеринарный','Fitosanitar / veterinar',   'Phytosanitary / veterinary',7, 1, 4 FROM DUAL UNION ALL
  SELECT 'safety',     'Декларация безопасности',     'Declarație de siguranță',    'Safety declaration',        8, 1, 7 FROM DUAL UNION ALL
  SELECT 'labels_loc', 'Локализованные этикетки (RO/RU)','Etichete localizate (RO/RU)','Localized labels (RO/RU)',9, 0, 10 FROM DUAL UNION ALL
  SELECT 'customs_decl','Таможенная декларация',      'Declarație vamală',          'Customs declaration',      10, 1, 1 FROM DUAL
) s ON (t.CODE = s.CODE)
WHEN MATCHED THEN UPDATE SET NAME_RU = s.RU, NAME_RO = s.RO, NAME_EN = s.EN,
     SORT_ORDER = s.SRT, IS_CUSTOMS = s.CUST, LEAD_DAYS = s.LEAD
WHEN NOT MATCHED THEN INSERT (CODE, NAME_RU, NAME_RO, NAME_EN, SORT_ORDER, IS_CUSTOMS, LEAD_DAYS)
     VALUES (s.CODE, s.RU, s.RO, s.EN, s.SRT, s.CUST, s.LEAD);

COMMIT;

-- ==================== Заказ импорта ====================

CREATE TABLE PLG_IMPORT_ORDERS (
  ID            NUMBER        NOT NULL,
  ORDER_NO      VARCHAR2(30),
  DATASET_ID    NUMBER,
  SUPPLIER_ID   NUMBER,                        -- зарубежный поставщик
  DC_ID         NUMBER,                        -- куда приходит: РЦ…
  STORE_ID      NUMBER,                        -- …или магазин напрямую
  COUNTRY       VARCHAR2(5),                   -- страна отправления
  INCOTERMS     VARCHAR2(10)  DEFAULT 'FCA',
  TRANSPORT     VARCHAR2(10)  DEFAULT 'truck', -- truck / sea / air / rail
  CURRENCY      VARCHAR2(5)   DEFAULT 'EUR',
  AMOUNT        NUMBER(16,2)  DEFAULT 0,       -- сумма по инвойсу
  DUTY_PCT      NUMBER(6,2),                   -- оценка пошлины, %
  VAT_PCT       NUMBER(6,2)   DEFAULT 20,
  STATUS        VARCHAR2(30)  DEFAULT 'draft', -- текущий этап (код справочника)
  ETD           DATE,                          -- план отгрузки
  ETA           DATE,                          -- план прибытия на склад
  CUSTOMS_POST  VARCHAR2(150),                 -- таможенный пост
  BROKER        VARCHAR2(200),                 -- таможенный представитель
  TOTAL_DELAY_DAYS NUMBER     DEFAULT 0,       -- суммарная задержка по журналу этапов
  NOTES         VARCHAR2(1000),
  CREATED_BY    VARCHAR2(150),
  CREATED_AT    TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT    TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_IMPORT_ORDERS PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_IMP_NO UNIQUE (ORDER_NO),
  CONSTRAINT FK_PLG_IMP_DS    FOREIGN KEY (DATASET_ID)  REFERENCES PLG_DATASETS(ID),
  CONSTRAINT FK_PLG_IMP_SUP   FOREIGN KEY (SUPPLIER_ID) REFERENCES PLG_SUPPLIERS(ID) ON DELETE SET NULL,
  CONSTRAINT FK_PLG_IMP_DC    FOREIGN KEY (DC_ID)       REFERENCES PLG_DC(ID) ON DELETE SET NULL,
  CONSTRAINT FK_PLG_IMP_STORE FOREIGN KEY (STORE_ID)    REFERENCES PLG_STORES(ID) ON DELETE SET NULL,
  CONSTRAINT FK_PLG_IMP_STAGE FOREIGN KEY (STATUS)      REFERENCES PLG_REF_IMP_STAGES(CODE),
  CONSTRAINT CHK_PLG_IMP_TR CHECK (TRANSPORT IN ('truck','sea','air','rail'))
);
/

CREATE OR REPLACE TRIGGER PLG_IMPORT_ORDERS_BI
  BEFORE INSERT ON PLG_IMPORT_ORDERS FOR EACH ROW
BEGIN
  IF :NEW.ID IS NULL THEN :NEW.ID := PLG_IMP_ORDER_SEQ.NEXTVAL; END IF;
  IF :NEW.ORDER_NO IS NULL THEN
    :NEW.ORDER_NO := 'IMP-' || TO_CHAR(SYSDATE, 'YYYY') || '-' || LPAD(:NEW.ID, 4, '0');
  END IF;
END;
/

CREATE OR REPLACE TRIGGER PLG_IMPORT_ORDERS_BU
  BEFORE UPDATE ON PLG_IMPORT_ORDERS FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

-- ==================== Позиции ====================

CREATE TABLE PLG_IMPORT_ITEMS (
  ID          NUMBER        NOT NULL,
  ORDER_ID    NUMBER        NOT NULL,
  PRODUCT_ID  NUMBER,
  DESCR       VARCHAR2(300),               -- если товара ещё нет в справочнике
  HS_CODE     VARCHAR2(12),                -- код ТН ВЭД
  ORIGIN      VARCHAR2(5),                 -- страна происхождения
  QTY         NUMBER(14,3)  DEFAULT 0,
  UOM         VARCHAR2(20)  DEFAULT 'pcs',
  PRICE       NUMBER(14,4),                -- цена в валюте контракта
  AMOUNT      NUMBER(16,2),
  GROSS_KG    NUMBER(12,2),
  SORT_ORDER  NUMBER        DEFAULT 0,
  CONSTRAINT PK_PLG_IMPORT_ITEMS PRIMARY KEY (ID),
  CONSTRAINT FK_PLG_IMI_ORDER FOREIGN KEY (ORDER_ID)   REFERENCES PLG_IMPORT_ORDERS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_IMI_PROD  FOREIGN KEY (PRODUCT_ID) REFERENCES PLG_PRODUCTS(ID) ON DELETE SET NULL
);
/

CREATE OR REPLACE TRIGGER PLG_IMPORT_ITEMS_BI
  BEFORE INSERT ON PLG_IMPORT_ITEMS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_IMP_ITEM_SEQ.NEXTVAL;
END;
/

CREATE INDEX IX_PLG_IMP_ITEMS ON PLG_IMPORT_ITEMS (ORDER_ID);

-- ==================== Журнал этапов ====================
--
-- План заполняется при создании заказа (типовые длительности справочника),
-- факт — по мере прохождения. DELAY_DAYS = факт − план: задержка не мнение,
-- а вычисленная разница дат.

CREATE TABLE PLG_IMPORT_STAGE_LOG (
  ID           NUMBER        NOT NULL,
  ORDER_ID     NUMBER        NOT NULL,
  STAGE_CODE   VARCHAR2(30)  NOT NULL,
  PLANNED_DATE DATE,
  ACTUAL_DATE  DATE,
  DELAY_DAYS   NUMBER        DEFAULT 0,
  DELAY_REASON VARCHAR2(30),                -- docs / customs / logistics / supplier / payment / other
  NOTE         VARCHAR2(600),
  USERNAME     VARCHAR2(150),
  CREATED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_IMP_STAGE_LOG PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_IMP_STAGE UNIQUE (ORDER_ID, STAGE_CODE),
  CONSTRAINT FK_PLG_ISL_ORDER FOREIGN KEY (ORDER_ID)   REFERENCES PLG_IMPORT_ORDERS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_ISL_STAGE FOREIGN KEY (STAGE_CODE) REFERENCES PLG_REF_IMP_STAGES(CODE),
  CONSTRAINT CHK_PLG_ISL_REASON CHECK (DELAY_REASON IS NULL OR DELAY_REASON IN
    ('docs','customs','logistics','supplier','payment','other'))
);
/

CREATE OR REPLACE TRIGGER PLG_IMP_STAGE_LOG_BI
  BEFORE INSERT ON PLG_IMPORT_STAGE_LOG FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_IMP_STAGE_SEQ.NEXTVAL;
END;
/

-- ==================== Чек-лист документов ====================

CREATE TABLE PLG_IMPORT_DOCS (
  ID          NUMBER        NOT NULL,
  ORDER_ID    NUMBER        NOT NULL,
  DOC_CODE    VARCHAR2(30)  NOT NULL,
  STATUS      VARCHAR2(20)  DEFAULT 'pending',  -- pending / in_progress / ready / approved / rejected
  DUE_DATE    DATE,                         -- дедлайн: граница минус LEAD_DAYS
  READY_DATE  DATE,
  RESPONSIBLE VARCHAR2(150),
  FILE_URL    VARCHAR2(400),
  NOTE        VARCHAR2(600),
  CREATED_AT  TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT  TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_IMPORT_DOCS PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_IMP_DOC UNIQUE (ORDER_ID, DOC_CODE),
  CONSTRAINT FK_PLG_IMD_ORDER FOREIGN KEY (ORDER_ID) REFERENCES PLG_IMPORT_ORDERS(ID) ON DELETE CASCADE,
  CONSTRAINT FK_PLG_IMD_DOC   FOREIGN KEY (DOC_CODE) REFERENCES PLG_REF_IMP_DOCS(CODE),
  CONSTRAINT CHK_PLG_IMD_ST CHECK (STATUS IN ('pending','in_progress','ready','approved','rejected'))
);
/

CREATE OR REPLACE TRIGGER PLG_IMPORT_DOCS_BI
  BEFORE INSERT ON PLG_IMPORT_DOCS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_IMP_DOC_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER PLG_IMPORT_DOCS_BU
  BEFORE UPDATE ON PLG_IMPORT_DOCS FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

-- ==================== Представления ====================

CREATE OR REPLACE VIEW V_PLG_IMPORT_ORDERS AS
SELECT
  o.ID, o.ORDER_NO, o.DATASET_ID,
  o.SUPPLIER_ID, s.NAME_RU AS SUPPLIER_NAME_RU, s.NAME_RO AS SUPPLIER_NAME_RO,
  s.NAME_EN AS SUPPLIER_NAME_EN, s.COUNTRY AS SUPPLIER_COUNTRY,
  o.DC_ID, dc.NAME_RU AS DC_NAME_RU, dc.NAME_RO AS DC_NAME_RO, dc.NAME_EN AS DC_NAME_EN,
  o.STORE_ID, st.NAME_RU AS STORE_NAME_RU, st.NAME_RO AS STORE_NAME_RO,
  st.NAME_EN AS STORE_NAME_EN,
  o.COUNTRY, o.INCOTERMS, o.TRANSPORT, o.CURRENCY, o.AMOUNT, o.DUTY_PCT, o.VAT_PCT,
  o.STATUS, rs.NAME_RU AS STAGE_NAME_RU, rs.NAME_RO AS STAGE_NAME_RO,
  rs.NAME_EN AS STAGE_NAME_EN, rs.SORT_ORDER AS STAGE_ORDER, rs.IS_CUSTOMS,
  o.ETD, o.ETA, o.CUSTOMS_POST, o.BROKER, o.TOTAL_DELAY_DAYS, o.NOTES,
  (SELECT COUNT(*) FROM PLG_IMPORT_ITEMS i WHERE i.ORDER_ID = o.ID) AS ITEM_COUNT,
  (SELECT COUNT(*) FROM PLG_IMPORT_DOCS d
    WHERE d.ORDER_ID = o.ID AND d.STATUS NOT IN ('ready','approved')) AS DOCS_PENDING,
  (SELECT COUNT(*) FROM PLG_IMPORT_DOCS d
    WHERE d.ORDER_ID = o.ID AND d.STATUS NOT IN ('ready','approved')
      AND d.DUE_DATE < SYSDATE) AS DOCS_OVERDUE,
  o.CREATED_BY, o.CREATED_AT, o.UPDATED_AT
FROM PLG_IMPORT_ORDERS o
LEFT JOIN PLG_SUPPLIERS s ON s.ID = o.SUPPLIER_ID
LEFT JOIN PLG_DC dc       ON dc.ID = o.DC_ID
LEFT JOIN PLG_STORES st   ON st.ID = o.STORE_ID
LEFT JOIN PLG_REF_IMP_STAGES rs ON rs.CODE = o.STATUS;

CREATE OR REPLACE VIEW V_PLG_IMPORT_STAGES AS
SELECT
  l.ID, l.ORDER_ID, o.ORDER_NO, l.STAGE_CODE,
  rs.NAME_RU AS STAGE_NAME_RU, rs.NAME_RO AS STAGE_NAME_RO, rs.NAME_EN AS STAGE_NAME_EN,
  rs.SORT_ORDER, rs.IS_CUSTOMS,
  l.PLANNED_DATE, l.ACTUAL_DATE, l.DELAY_DAYS, l.DELAY_REASON, l.NOTE,
  l.USERNAME, l.CREATED_AT
FROM PLG_IMPORT_STAGE_LOG l
JOIN PLG_IMPORT_ORDERS o ON o.ID = l.ORDER_ID
JOIN PLG_REF_IMP_STAGES rs ON rs.CODE = l.STAGE_CODE;

CREATE OR REPLACE VIEW V_PLG_IMPORT_DOCS AS
SELECT
  d.ID, d.ORDER_ID, o.ORDER_NO, d.DOC_CODE,
  rd.NAME_RU AS DOC_NAME_RU, rd.NAME_RO AS DOC_NAME_RO, rd.NAME_EN AS DOC_NAME_EN,
  rd.SORT_ORDER, rd.IS_CUSTOMS, rd.LEAD_DAYS,
  d.STATUS, d.DUE_DATE, d.READY_DATE, d.RESPONSIBLE, d.FILE_URL, d.NOTE,
  CASE WHEN d.STATUS NOT IN ('ready','approved') AND d.DUE_DATE < SYSDATE
       THEN 1 ELSE 0 END AS IS_OVERDUE,
  d.CREATED_AT, d.UPDATED_AT
FROM PLG_IMPORT_DOCS d
JOIN PLG_IMPORT_ORDERS o ON o.ID = d.ORDER_ID
JOIN PLG_REF_IMP_DOCS rd ON rd.CODE = d.DOC_CODE;

CREATE OR REPLACE VIEW V_PLG_IMPORT_ITEMS AS
SELECT
  i.ID, i.ORDER_ID, i.PRODUCT_ID,
  NVL(p.NAME_RU, i.DESCR) AS PRODUCT_NAME_RU,
  NVL(p.NAME_RO, i.DESCR) AS PRODUCT_NAME_RO,
  NVL(p.NAME_EN, i.DESCR) AS PRODUCT_NAME_EN,
  p.CODE AS PRODUCT_CODE, p.BARCODE,
  i.HS_CODE, i.ORIGIN, i.QTY, i.UOM, i.PRICE,
  NVL(i.AMOUNT, ROUND(i.QTY * i.PRICE, 2)) AS AMOUNT,
  i.GROSS_KG, i.SORT_ORDER
FROM PLG_IMPORT_ITEMS i
LEFT JOIN PLG_PRODUCTS p ON p.ID = i.PRODUCT_ID;

-- ==================== Демо-данные ====================
--
-- Три заказа в разных состояниях: один в пути с готовыми документами,
-- один на таможне с просроченным сертификатом (показывает, ради чего
-- построен упреждающий чек-лист), один завершён с зафиксированными
-- задержками. Создаются только если импортных заказов ещё нет.

DECLARE
  v_cnt   NUMBER;
  v_sup   NUMBER;
  v_dc    NUMBER;
  v_id    NUMBER;

  PROCEDURE seed_stages(p_order NUMBER, p_start DATE, p_upto VARCHAR2,
                        p_delay_stage VARCHAR2 DEFAULT NULL,
                        p_delay_days NUMBER DEFAULT 0,
                        p_delay_reason VARCHAR2 DEFAULT NULL) IS
    v_plan DATE := p_start;
    v_done NUMBER := 1;
    v_upto_ord NUMBER;
  BEGIN
    SELECT SORT_ORDER INTO v_upto_ord FROM PLG_REF_IMP_STAGES WHERE CODE = p_upto;
    FOR st IN (SELECT CODE, SORT_ORDER, TYPICAL_DAYS FROM PLG_REF_IMP_STAGES ORDER BY SORT_ORDER) LOOP
      v_plan := v_plan + st.TYPICAL_DAYS;
      INSERT INTO PLG_IMPORT_STAGE_LOG (ORDER_ID, STAGE_CODE, PLANNED_DATE, ACTUAL_DATE,
                                        DELAY_DAYS, DELAY_REASON, USERNAME)
      VALUES (p_order, st.CODE, v_plan,
              CASE WHEN st.SORT_ORDER <= v_upto_ord THEN
                v_plan + CASE WHEN st.CODE = p_delay_stage THEN p_delay_days ELSE 0 END
              END,
              CASE WHEN st.SORT_ORDER <= v_upto_ord AND st.CODE = p_delay_stage
                   THEN p_delay_days ELSE 0 END,
              CASE WHEN st.SORT_ORDER <= v_upto_ord AND st.CODE = p_delay_stage
                   THEN p_delay_reason END,
              'system');
      IF st.CODE = p_delay_stage AND st.SORT_ORDER <= v_upto_ord THEN
        v_plan := v_plan + p_delay_days;   -- задержка сдвигает всё, что после
      END IF;
    END LOOP;
    UPDATE PLG_IMPORT_ORDERS
       SET TOTAL_DELAY_DAYS = NVL((SELECT SUM(DELAY_DAYS) FROM PLG_IMPORT_STAGE_LOG
                                    WHERE ORDER_ID = p_order), 0)
     WHERE ID = p_order;
  END;

  PROCEDURE seed_docs(p_order NUMBER, p_border DATE, p_ready_pct NUMBER) IS
    v_n NUMBER := 0;
  BEGIN
    FOR d IN (SELECT CODE, LEAD_DAYS, SORT_ORDER FROM PLG_REF_IMP_DOCS ORDER BY SORT_ORDER) LOOP
      v_n := v_n + 1;
      INSERT INTO PLG_IMPORT_DOCS (ORDER_ID, DOC_CODE, STATUS, DUE_DATE, READY_DATE, RESPONSIBLE)
      VALUES (p_order, d.CODE,
              CASE WHEN v_n <= p_ready_pct THEN 'ready' ELSE 'in_progress' END,
              p_border - d.LEAD_DAYS,
              CASE WHEN v_n <= p_ready_pct THEN p_border - d.LEAD_DAYS - 1 END,
              CASE WHEN d.CODE IN ('conformity','phyto','safety') THEN 'Отдел качества'
                   WHEN d.CODE = 'labels_loc' THEN 'Категорийный менеджер'
                   WHEN d.CODE = 'customs_decl' THEN 'Таможенный брокер'
                   ELSE 'Отдел ВЭД' END);
    END LOOP;
  END;

  PROCEDURE seed_items(p_order NUMBER, p_n NUMBER) IS
    v_i NUMBER := 0;
  BEGIN
    FOR p IN (SELECT ID, NAME_RU, PRICE FROM PLG_PRODUCTS
               WHERE STATUS = 'active' AND PRICE IS NOT NULL ORDER BY ID) LOOP
      EXIT WHEN v_i >= p_n;
      v_i := v_i + 1;
      INSERT INTO PLG_IMPORT_ITEMS (ORDER_ID, PRODUCT_ID, HS_CODE, ORIGIN, QTY, UOM,
                                    PRICE, GROSS_KG, SORT_ORDER)
      VALUES (p_order, p.ID,
              '0' || TO_CHAR(400 + v_i * 17) || '9000' || TO_CHAR(v_i),
              CASE MOD(v_i, 3) WHEN 0 THEN 'PL' WHEN 1 THEN 'RO' ELSE 'TR' END,
              120 * v_i, 'pcs', ROUND(p.PRICE * 0.42, 2), 90 * v_i, v_i);
    END LOOP;
    UPDATE PLG_IMPORT_ORDERS o
       SET AMOUNT = (SELECT NVL(SUM(QTY * PRICE), 0) FROM PLG_IMPORT_ITEMS
                      WHERE ORDER_ID = p_order)
     WHERE o.ID = p_order;
  END;
BEGIN
  SELECT COUNT(*) INTO v_cnt FROM PLG_IMPORT_ORDERS;
  IF v_cnt > 0 THEN
    RETURN;
  END IF;
  SELECT MIN(ID) INTO v_sup FROM PLG_SUPPLIERS WHERE COUNTRY <> 'MD';
  IF v_sup IS NULL THEN
    SELECT MIN(ID) INTO v_sup FROM PLG_SUPPLIERS;
  END IF;
  SELECT MIN(ID) INTO v_dc FROM PLG_DC;

  -- 1. В транзите: документы готовы заранее, задержек нет
  INSERT INTO PLG_IMPORT_ORDERS (SUPPLIER_ID, DC_ID, COUNTRY, INCOTERMS, TRANSPORT,
                                 CURRENCY, DUTY_PCT, STATUS, ETD, ETA, CUSTOMS_POST,
                                 BROKER, CREATED_BY, NOTES)
  VALUES (v_sup, v_dc, 'PL', 'FCA', 'truck', 'EUR', 8.5, 'shipment',
          SYSDATE - 6, SYSDATE + 4, 'Leușeni', 'BrokExpert SRL', 'system',
          'Документы поданы заранее, машина в транзите')
  RETURNING ID INTO v_id;
  seed_items(v_id, 4);
  seed_stages(v_id, SYSDATE - 26, 'shipment');
  seed_docs(v_id, SYSDATE + 2, 9);

  -- 2. На таможне: сертификат соответствия не готов — просрочен, стоим
  INSERT INTO PLG_IMPORT_ORDERS (SUPPLIER_ID, DC_ID, COUNTRY, INCOTERMS, TRANSPORT,
                                 CURRENCY, DUTY_PCT, STATUS, ETD, ETA, CUSTOMS_POST,
                                 BROKER, CREATED_BY, NOTES)
  VALUES (v_sup, v_dc, 'TR', 'CPT', 'truck', 'USD', 12, 'customs',
          SYSDATE - 14, SYSDATE - 1, 'Giurgiulești', 'BrokExpert SRL', 'system',
          'Машина на СВХ: не готов сертификат соответствия')
  RETURNING ID INTO v_id;
  seed_items(v_id, 6);
  seed_stages(v_id, SYSDATE - 33, 'customs', 'customs', 3, 'docs');
  seed_docs(v_id, SYSDATE - 2, 7);

  -- 3. Завершён: задержка логистики на границе, зафиксирована в журнале
  INSERT INTO PLG_IMPORT_ORDERS (SUPPLIER_ID, DC_ID, COUNTRY, INCOTERMS, TRANSPORT,
                                 CURRENCY, DUTY_PCT, STATUS, ETD, ETA, CUSTOMS_POST,
                                 BROKER, CREATED_BY, NOTES)
  VALUES (v_sup, v_dc, 'RO', 'DAP', 'truck', 'EUR', 0, 'delivered',
          SYSDATE - 40, SYSDATE - 28, 'Leușeni', 'BrokExpert SRL', 'system',
          'Закрыт. Очередь на границе +2 дня — учтена в статистике поста')
  RETURNING ID INTO v_id;
  seed_items(v_id, 5);
  seed_stages(v_id, SYSDATE - 62, 'delivered', 'border', 2, 'logistics');
  seed_docs(v_id, SYSDATE - 32, 10);

  COMMIT;
END;
/
