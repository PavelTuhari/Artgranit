-- ============================================================
-- Nufarul: Group parameter schemas + per-item params column
-- ============================================================

-- 1. Parameter schema table (one row per group)
CREATE TABLE NUF_GROUP_PARAMS (
    GROUP_KEY   VARCHAR2(50)  NOT NULL,
    LABEL_RU    VARCHAR2(200),
    LABEL_RO    VARCHAR2(200),
    ICON        VARCHAR2(20),
    SORT_ORDER  NUMBER DEFAULT 0,
    PARAMS_JSON CLOB,
    ACTIVE      CHAR(1) DEFAULT 'Y' NOT NULL,
    UPDATED_AT  TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT PK_NUF_GROUP_PARAMS PRIMARY KEY (GROUP_KEY)
)
/

-- 2. Per-item parameter values (companion to blockchain ledger)
CREATE TABLE NUF_ORDER_ITEM_PARAMS (
    ORDER_ITEM_ID  NUMBER        NOT NULL,
    PARAMS         CLOB          NOT NULL,
    CREATED_AT     TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT PK_NUF_ORDER_ITEM_PARAMS PRIMARY KEY (ORDER_ITEM_ID)
)
/

-- 3. Seed default groups
INSERT INTO NUF_GROUP_PARAMS (GROUP_KEY, LABEL_RU, LABEL_RO, ICON, SORT_ORDER, PARAMS_JSON) VALUES (
  'clothing', 'Одежда', 'Îmbrăcăminte', '👗', 10,
  '[
    {"key":"color","type":"color","label_ru":"Цвет","options":["#111111","#c0392b","#2980b9","#27ae60","#8e4585","#e8c84a","#bdc3c7","#f5f5f5"]},
    {"key":"fabric","type":"chips","label_ru":"Ткань","multi":false,"options":["Шерсть","Кашемир","Хлопок","Кожа","Замша","Синтетика","Шуба","Другое"]},
    {"key":"stains","type":"toggle","label_ru":"Пятна"},
    {"key":"damage","type":"toggle","label_ru":"Повреждения"},
    {"key":"urgent","type":"toggle","label_ru":"Срочно"},
    {"key":"qty","type":"counter","label_ru":"Количество","min":1},
    {"key":"notes","type":"notes","label_ru":"Примечание"}
  ]'
)
/
INSERT INTO NUF_GROUP_PARAMS (GROUP_KEY, LABEL_RU, LABEL_RO, ICON, SORT_ORDER, PARAMS_JSON) VALUES (
  'carpets', 'Ковры', 'Covoare', '🪞', 20,
  '[
    {"key":"color","type":"color","label_ru":"Цвет","options":["#111111","#c0392b","#2980b9","#27ae60","#8e4585","#e8c84a","#bdc3c7","#f5f5f5"]},
    {"key":"material","type":"chips","label_ru":"Материал","multi":false,"options":["Шерсть","Шёлк","Синтетика","Хлопок","Другое"]},
    {"key":"size_m2","type":"numeric","label_ru":"Размер м²","placeholder":"3.5"},
    {"key":"contamination","type":"chips","label_ru":"Загрязнение","multi":true,"options":["Пыль","Пятна","Животные","Плесень","Другое"]},
    {"key":"urgent","type":"toggle","label_ru":"Срочно"},
    {"key":"qty","type":"counter","label_ru":"Количество","min":1},
    {"key":"notes","type":"notes","label_ru":"Примечание"}
  ]'
)
/
INSERT INTO NUF_GROUP_PARAMS (GROUP_KEY, LABEL_RU, LABEL_RO, ICON, SORT_ORDER, PARAMS_JSON) VALUES (
  'pillows', 'Подушки', 'Perne', '🛏', 30,
  '[
    {"key":"filling","type":"chips","label_ru":"Наполнитель","multi":false,"options":["Перо","Синтепон","Силикон","Другое"]},
    {"key":"size","type":"chips","label_ru":"Размер","multi":false,"options":["50×70","70×70","50×50","Другой"]},
    {"key":"replace_cover","type":"toggle","label_ru":"Замена наперника"},
    {"key":"qty","type":"counter","label_ru":"Количество","min":1},
    {"key":"notes","type":"notes","label_ru":"Примечание"}
  ]'
)
/
INSERT INTO NUF_GROUP_PARAMS (GROUP_KEY, LABEL_RU, LABEL_RO, ICON, SORT_ORDER, PARAMS_JSON) VALUES (
  'shoes', 'Обувь', 'Încălțăminte', '👟', 40,
  '[
    {"key":"color","type":"color","label_ru":"Цвет","options":["#111111","#c0392b","#2980b9","#27ae60","#8e4585","#e8c84a","#bdc3c7","#f5f5f5"]},
    {"key":"material","type":"chips","label_ru":"Материал","multi":false,"options":["Кожа","Замша","Текстиль","Синтетика","Другое"]},
    {"key":"shoe_type","type":"chips","label_ru":"Тип","multi":false,"options":["Ботинки","Туфли","Кроссовки","Сапоги","Другое"]},
    {"key":"stains","type":"toggle","label_ru":"Пятна"},
    {"key":"dyeing","type":"toggle","label_ru":"Покраска"},
    {"key":"qty","type":"counter","label_ru":"Пар","min":1},
    {"key":"notes","type":"notes","label_ru":"Примечание"}
  ]'
)
/
COMMIT
/
