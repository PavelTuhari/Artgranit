-- ============================================================
-- Nufarul: subgroup support
-- ============================================================

-- 1. Add SUBGROUPS_JSON column to NUF_GROUP_PARAMS
ALTER TABLE NUF_GROUP_PARAMS ADD (SUBGROUPS_JSON CLOB)
/

-- 2. Add SERVICE_SUBGROUP column to NUF_SERVICES
ALTER TABLE NUF_SERVICES ADD (SERVICE_SUBGROUP VARCHAR2(100))
/

-- 3. Index for subgroup filter queries
CREATE INDEX IX_NUF_SERVICES_SUBGROUP ON NUF_SERVICES (SERVICE_SUBGROUP)
/

-- 4. Ensure dry_cleaning group row exists (seed files use wrong keys)
MERGE INTO NUF_GROUP_PARAMS tgt
USING (SELECT 'dry_cleaning' AS gk FROM DUAL) src
ON (tgt.GROUP_KEY = src.gk)
WHEN NOT MATCHED THEN INSERT (GROUP_KEY, LABEL_RU, LABEL_RO, ICON, SORT_ORDER, ACTIVE)
     VALUES ('dry_cleaning', 'Химчистка одежды', 'Curățare chimică', '👗', 10, 'Y')
/

-- 5. Seed subgroups for dry_cleaning (from nufarul.com/ro/order-online.html)
UPDATE NUF_GROUP_PARAMS
SET SUBGROUPS_JSON = '[
  {"key":"textile_clothes","label_ru":"Текстиль","label_ro":"Haine din textile","icon":"👔","sort_order":10},
  {"key":"blankets","label_ru":"Пледы/Одеяла/Шторы","label_ro":"Pleduri, Plapume, Draperii","icon":"🛏","sort_order":20},
  {"key":"workwear","label_ru":"Рабочая одежда","label_ro":"Îmbrăcăminte de lucru","icon":"👷","sort_order":30},
  {"key":"leather_natural","label_ru":"Кожа/мех натур.","label_ro":"Piele, blănuri naturale","icon":"🧥","sort_order":40},
  {"key":"leather_artificial","label_ru":"Кожа/мех искусств.","label_ro":"Piele, blănuri artificiale","icon":"🥼","sort_order":50},
  {"key":"footwear","label_ru":"Обувь","label_ro":"Încălțăminte","icon":"🥾","sort_order":60}
]'
WHERE GROUP_KEY = 'dry_cleaning'
/

COMMIT
/
