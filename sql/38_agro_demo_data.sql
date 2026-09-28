-- ============================================================
-- AGRO module — Demo / Seed data for reference tables
-- File:   38_agro_demo_data.sql
-- Target: Oracle (PL/SQL compatible)
--
-- Populates: AGRO_CURRENCIES, AGRO_EXCHANGE_RATES, AGRO_ITEMS,
--   AGRO_PACKAGING_TYPES, AGRO_SUPPLIERS, AGRO_CUSTOMERS,
--   AGRO_WAREHOUSES, AGRO_STORAGE_CELLS, AGRO_VEHICLES,
--   AGRO_FORMULA_PARAMS, AGRO_MODULE_CONFIG,
--   AGRO_QA_CHECKLISTS, AGRO_QA_CHECKLIST_ITEMS,
--   AGRO_HACCP_PLANS, AGRO_HACCP_CCPS
--
-- IDs are omitted — auto-populated by BI triggers / sequences.
-- ============================================================

-- ============================================================
-- 1. AGRO_CURRENCIES (3 rows)
-- ============================================================

INSERT INTO AGRO_CURRENCIES (ID, CODE, NAME, SYMBOL, ACTIVE)
VALUES (NULL, 'MDL', 'Leu moldovenesc', 'L', 'Y');

INSERT INTO AGRO_CURRENCIES (ID, CODE, NAME, SYMBOL, ACTIVE)
VALUES (NULL, 'EUR', 'Euro', '€', 'Y');

INSERT INTO AGRO_CURRENCIES (ID, CODE, NAME, SYMBOL, ACTIVE)
VALUES (NULL, 'USD', 'US Dollar', '$', 'Y');

-- ============================================================
-- 2. AGRO_EXCHANGE_RATES (4 rows)
-- ============================================================

INSERT INTO AGRO_EXCHANGE_RATES (ID, FROM_CURRENCY, TO_CURRENCY, RATE, RATE_DATE, SOURCE)
VALUES (NULL, 'MDL', 'EUR', 19.50, TRUNC(SYSDATE), 'BNM');

INSERT INTO AGRO_EXCHANGE_RATES (ID, FROM_CURRENCY, TO_CURRENCY, RATE, RATE_DATE, SOURCE)
VALUES (NULL, 'MDL', 'USD', 17.80, TRUNC(SYSDATE), 'BNM');

INSERT INTO AGRO_EXCHANGE_RATES (ID, FROM_CURRENCY, TO_CURRENCY, RATE, RATE_DATE, SOURCE)
VALUES (NULL, 'EUR', 'MDL', 0.051300, TRUNC(SYSDATE), 'BNM');

INSERT INTO AGRO_EXCHANGE_RATES (ID, FROM_CURRENCY, TO_CURRENCY, RATE, RATE_DATE, SOURCE)
VALUES (NULL, 'USD', 'MDL', 0.056200, TRUNC(SYSDATE), 'BNM');

-- ============================================================
-- 3. AGRO_ITEMS (8 rows)
-- ============================================================

INSERT INTO AGRO_ITEMS (ID, CODE, NAME_RU, NAME_RO, ITEM_GROUP, UNIT, DEFAULT_TARE_KG, SHELF_LIFE_DAYS, OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX, ACTIVE)
VALUES (NULL, 'APPLE', 'Яблоко', 'Măr', 'fruit', 'kg', 0, 90, 0, 4, 'Y');

INSERT INTO AGRO_ITEMS (ID, CODE, NAME_RU, NAME_RO, ITEM_GROUP, UNIT, DEFAULT_TARE_KG, SHELF_LIFE_DAYS, OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX, ACTIVE)
VALUES (NULL, 'PLUM', 'Слива', 'Prună', 'fruit', 'kg', 0, 30, 0, 2, 'Y');

INSERT INTO AGRO_ITEMS (ID, CODE, NAME_RU, NAME_RO, ITEM_GROUP, UNIT, DEFAULT_TARE_KG, SHELF_LIFE_DAYS, OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX, ACTIVE)
VALUES (NULL, 'GRAPE', 'Виноград', 'Struguri', 'fruit', 'kg', 0, 60, -1, 2, 'Y');

INSERT INTO AGRO_ITEMS (ID, CODE, NAME_RU, NAME_RO, ITEM_GROUP, UNIT, DEFAULT_TARE_KG, SHELF_LIFE_DAYS, OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX, ACTIVE)
VALUES (NULL, 'CHERRY', 'Вишня', 'Vișină', 'fruit', 'kg', 0, 14, 0, 2, 'Y');

INSERT INTO AGRO_ITEMS (ID, CODE, NAME_RU, NAME_RO, ITEM_GROUP, UNIT, DEFAULT_TARE_KG, SHELF_LIFE_DAYS, OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX, ACTIVE)
VALUES (NULL, 'PEACH', 'Персик', 'Piersică', 'fruit', 'kg', 0, 21, 0, 2, 'Y');

INSERT INTO AGRO_ITEMS (ID, CODE, NAME_RU, NAME_RO, ITEM_GROUP, UNIT, DEFAULT_TARE_KG, SHELF_LIFE_DAYS, OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX, ACTIVE)
VALUES (NULL, 'WALNUT', 'Грецкий орех', 'Nucă', 'fruit', 'kg', 0, 365, 10, 15, 'Y');

INSERT INTO AGRO_ITEMS (ID, CODE, NAME_RU, NAME_RO, ITEM_GROUP, UNIT, DEFAULT_TARE_KG, SHELF_LIFE_DAYS, OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX, ACTIVE)
VALUES (NULL, 'TOMATO', 'Помидор', 'Roșie', 'vegetable', 'kg', 0, 14, 8, 12, 'Y');

INSERT INTO AGRO_ITEMS (ID, CODE, NAME_RU, NAME_RO, ITEM_GROUP, UNIT, DEFAULT_TARE_KG, SHELF_LIFE_DAYS, OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX, ACTIVE)
VALUES (NULL, 'PEPPER', 'Перец', 'Ardei', 'vegetable', 'kg', 0, 21, 7, 10, 'Y');

-- ============================================================
-- 4. AGRO_PACKAGING_TYPES (4 rows)
-- ============================================================

INSERT INTO AGRO_PACKAGING_TYPES (ID, CODE, NAME_RU, NAME_RO, TARE_WEIGHT_KG, CAPACITY_KG, ACTIVE)
VALUES (NULL, 'CRATE_WOOD', 'Ящик деревянный', 'Ladă din lemn', 2.500, 20.00, 'Y');

INSERT INTO AGRO_PACKAGING_TYPES (ID, CODE, NAME_RU, NAME_RO, TARE_WEIGHT_KG, CAPACITY_KG, ACTIVE)
VALUES (NULL, 'CRATE_PLASTIC', 'Ящик пластик', 'Ladă din plastic', 1.200, 25.00, 'Y');

INSERT INTO AGRO_PACKAGING_TYPES (ID, CODE, NAME_RU, NAME_RO, TARE_WEIGHT_KG, CAPACITY_KG, ACTIVE)
VALUES (NULL, 'BOX_CARDBOARD', 'Коробка картон', 'Cutie carton', 0.500, 10.00, 'Y');

INSERT INTO AGRO_PACKAGING_TYPES (ID, CODE, NAME_RU, NAME_RO, TARE_WEIGHT_KG, CAPACITY_KG, ACTIVE)
VALUES (NULL, 'BIN_LARGE', 'Бин большой', 'Bin mare', 25.000, 300.00, 'Y');

-- ============================================================
-- 5. AGRO_SUPPLIERS (3 rows)
-- ============================================================

INSERT INTO AGRO_SUPPLIERS (ID, CODE, NAME, COUNTRY, TAX_ID, CONTACT_PHONE, CONTACT_EMAIL, ADDRESS, ACTIVE)
VALUES (NULL, 'SUP001', 'Agrofruct SRL', 'Moldova', '1234567890', '+373 22 123456', 'office@agrofruct.md', 'mun. Chișinău, str. Calea Ieșilor 10', 'Y');

INSERT INTO AGRO_SUPPLIERS (ID, CODE, NAME, COUNTRY, TAX_ID, CONTACT_PHONE, CONTACT_EMAIL, ADDRESS, ACTIVE)
VALUES (NULL, 'SUP002', 'VitaGarden SA', 'Moldova', '9876543210', '+373 22 654321', 'info@vitagarden.md', 'or. Bălți, str. Independenței 25', 'Y');

INSERT INTO AGRO_SUPPLIERS (ID, CODE, NAME, COUNTRY, TAX_ID, CONTACT_PHONE, CONTACT_EMAIL, ADDRESS, ACTIVE)
VALUES (NULL, 'SUP003', 'GreenField Cooperative', 'Moldova', '5555555555', '+373 22 555555', 'contact@greenfield.md', 'r-nul Orhei, s. Peresecina', 'Y');

-- ============================================================
-- 6. AGRO_CUSTOMERS (4 rows)
-- ============================================================

INSERT INTO AGRO_CUSTOMERS (ID, CODE, NAME, COUNTRY, TAX_ID, CONTACT_PHONE, CONTACT_EMAIL, ADDRESS, CUSTOMER_TYPE, ACTIVE)
VALUES (NULL, 'CUS001', 'FreshMarket SRL', 'Moldova', '1111111111', '+373 22 111111', 'sales@freshmarket.md', 'mun. Chișinău, bd. Dacia 27', 'domestic', 'Y');

INSERT INTO AGRO_CUSTOMERS (ID, CODE, NAME, COUNTRY, TAX_ID, CONTACT_PHONE, CONTACT_EMAIL, ADDRESS, CUSTOMER_TYPE, ACTIVE)
VALUES (NULL, 'CUS002', 'EuroFruit GmbH', 'Germany', 'DE123456789', '+49 30 1234567', 'import@eurofruit.de', 'Berlin, Friedrichstraße 100', 'export', 'Y');

INSERT INTO AGRO_CUSTOMERS (ID, CODE, NAME, COUNTRY, TAX_ID, CONTACT_PHONE, CONTACT_EMAIL, ADDRESS, CUSTOMER_TYPE, ACTIVE)
VALUES (NULL, 'CUS003', 'PrimFruct SA', 'Moldova', '2222222222', '+373 22 222222', 'office@primfruct.md', 'mun. Chișinău, str. Columna 170', 'domestic', 'Y');

INSERT INTO AGRO_CUSTOMERS (ID, CODE, NAME, COUNTRY, TAX_ID, CONTACT_PHONE, CONTACT_EMAIL, ADDRESS, CUSTOMER_TYPE, ACTIVE)
VALUES (NULL, 'CUS004', 'Baltic Fresh OÜ', 'Estonia', 'EE987654321', '+372 600 1234', 'purchase@balticfresh.ee', 'Tallinn, Pärnu mnt 15', 'export', 'Y');

-- ============================================================
-- 7. AGRO_WAREHOUSES (3 rows)
-- ============================================================

INSERT INTO AGRO_WAREHOUSES (ID, CODE, NAME, WAREHOUSE_TYPE, ADDRESS, CAPACITY_KG, ACTIVE)
VALUES (NULL, 'WH01', 'Склад-холодильник №1 / Depozit frigorific nr.1', 'cold_storage', 'mun. Chișinău, str. Industrială 5', 50000.00, 'Y');

INSERT INTO AGRO_WAREHOUSES (ID, CODE, NAME, WAREHOUSE_TYPE, ADDRESS, CAPACITY_KG, ACTIVE)
VALUES (NULL, 'WH02', 'Склад сухой / Depozit uscat', 'dry', 'mun. Chișinău, str. Industrială 7', 30000.00, 'Y');

INSERT INTO AGRO_WAREHOUSES (ID, CODE, NAME, WAREHOUSE_TYPE, ADDRESS, CAPACITY_KG, ACTIVE)
VALUES (NULL, 'WH03', 'Цех переработки / Secția de procesare', 'processing', 'mun. Chișinău, str. Industrială 9', 20000.00, 'Y');

-- ============================================================
-- 8. AGRO_STORAGE_CELLS (6 rows)
--    FK references use sub-selects on AGRO_WAREHOUSES.CODE
-- ============================================================

INSERT INTO AGRO_STORAGE_CELLS (ID, WAREHOUSE_ID, CODE, NAME, CELL_TYPE, TEMP_MIN, TEMP_MAX, HUMIDITY_MIN, HUMIDITY_MAX, CAPACITY_KG, ACTIVE)
VALUES (NULL, (SELECT ID FROM AGRO_WAREHOUSES WHERE CODE = 'WH01'), 'WH01-A', 'Камера А / Camera A', 'chamber', -1, 4, 85, 95, 10000.00, 'Y');

INSERT INTO AGRO_STORAGE_CELLS (ID, WAREHOUSE_ID, CODE, NAME, CELL_TYPE, TEMP_MIN, TEMP_MAX, HUMIDITY_MIN, HUMIDITY_MAX, CAPACITY_KG, ACTIVE)
VALUES (NULL, (SELECT ID FROM AGRO_WAREHOUSES WHERE CODE = 'WH01'), 'WH01-B', 'Камера Б / Camera B', 'chamber', 0, 2, 90, 95, 10000.00, 'Y');

INSERT INTO AGRO_STORAGE_CELLS (ID, WAREHOUSE_ID, CODE, NAME, CELL_TYPE, TEMP_MIN, TEMP_MAX, HUMIDITY_MIN, HUMIDITY_MAX, CAPACITY_KG, ACTIVE)
VALUES (NULL, (SELECT ID FROM AGRO_WAREHOUSES WHERE CODE = 'WH01'), 'WH01-C', 'Камера В / Camera C', 'chamber', 2, 8, 85, 90, 15000.00, 'Y');

INSERT INTO AGRO_STORAGE_CELLS (ID, WAREHOUSE_ID, CODE, NAME, CELL_TYPE, TEMP_MIN, TEMP_MAX, HUMIDITY_MIN, HUMIDITY_MAX, CAPACITY_KG, ACTIVE)
VALUES (NULL, (SELECT ID FROM AGRO_WAREHOUSES WHERE CODE = 'WH02'), 'WH02-A', 'Зона А / Zona A', 'zone', 10, 20, NULL, NULL, 15000.00, 'Y');

INSERT INTO AGRO_STORAGE_CELLS (ID, WAREHOUSE_ID, CODE, NAME, CELL_TYPE, TEMP_MIN, TEMP_MAX, HUMIDITY_MIN, HUMIDITY_MAX, CAPACITY_KG, ACTIVE)
VALUES (NULL, (SELECT ID FROM AGRO_WAREHOUSES WHERE CODE = 'WH02'), 'WH02-B', 'Зона Б / Zona B', 'zone', 10, 20, NULL, NULL, 15000.00, 'Y');

INSERT INTO AGRO_STORAGE_CELLS (ID, WAREHOUSE_ID, CODE, NAME, CELL_TYPE, TEMP_MIN, TEMP_MAX, HUMIDITY_MIN, HUMIDITY_MAX, CAPACITY_KG, ACTIVE)
VALUES (NULL, (SELECT ID FROM AGRO_WAREHOUSES WHERE CODE = 'WH03'), 'WH03-A', 'Линия 1 / Linia 1', 'section', 15, 25, NULL, NULL, 20000.00, 'Y');

-- ============================================================
-- 9. AGRO_VEHICLES (3 rows)
-- ============================================================

INSERT INTO AGRO_VEHICLES (ID, PLATE_NUMBER, VEHICLE_TYPE, DRIVER_NAME, ACTIVE)
VALUES (NULL, 'C 123 ABC', 'refrigerator', 'Ion Popescu', 'Y');

INSERT INTO AGRO_VEHICLES (ID, PLATE_NUMBER, VEHICLE_TYPE, DRIVER_NAME, ACTIVE)
VALUES (NULL, 'C 456 DEF', 'truck', 'Vasile Rusu', 'Y');

INSERT INTO AGRO_VEHICLES (ID, PLATE_NUMBER, VEHICLE_TYPE, DRIVER_NAME, ACTIVE)
VALUES (NULL, 'C 789 GHI', 'van', 'Andrei Cojocaru', 'Y');

-- ============================================================
-- 10. AGRO_FORMULA_PARAMS (3 rows — global, ITEM_ID = NULL)
-- ============================================================

INSERT INTO AGRO_FORMULA_PARAMS (ID, ITEM_ID, PARAM_NAME, PARAM_VALUE, ACTIVE)
VALUES (NULL, NULL, 'tare_coefficient', '1.0', 'Y');

INSERT INTO AGRO_FORMULA_PARAMS (ID, ITEM_ID, PARAM_NAME, PARAM_VALUE, ACTIVE)
VALUES (NULL, NULL, 'rounding_mode', 'half_up', 'Y');

INSERT INTO AGRO_FORMULA_PARAMS (ID, ITEM_ID, PARAM_NAME, PARAM_VALUE, ACTIVE)
VALUES (NULL, NULL, 'rounding_precision', '2', 'Y');

-- ============================================================
-- 11. AGRO_MODULE_CONFIG (4 rows)
-- ============================================================

INSERT INTO AGRO_MODULE_CONFIG (ID, CONFIG_KEY, CONFIG_VALUE, CONFIG_GROUP, DESCRIPTION)
VALUES (NULL, 'barcode_prefix', 'AGRO', 'barcodes', 'Prefix for internally generated barcodes');

INSERT INTO AGRO_MODULE_CONFIG (ID, CONFIG_KEY, CONFIG_VALUE, CONFIG_GROUP, DESCRIPTION)
VALUES (NULL, 'barcode_format', 'CODE128', 'barcodes', 'Barcode symbology format');

INSERT INTO AGRO_MODULE_CONFIG (ID, CONFIG_KEY, CONFIG_VALUE, CONFIG_GROUP, DESCRIPTION)
VALUES (NULL, 'default_currency', 'MDL', 'finance', 'Default currency for new documents');

INSERT INTO AGRO_MODULE_CONFIG (ID, CONFIG_KEY, CONFIG_VALUE, CONFIG_GROUP, DESCRIPTION)
VALUES (NULL, 'fifo_allocation', 'true', 'sales', 'Use FIFO method for batch allocation on sales');

-- ============================================================
-- 12. AGRO_QA_CHECKLISTS (2 rows)
-- ============================================================

INSERT INTO AGRO_QA_CHECKLISTS (ID, CODE, NAME_RU, NAME_RO, CHECKLIST_TYPE, ACTIVE)
VALUES (NULL, 'QC-INC', 'Входной контроль', 'Control la recepție', 'incoming', 'Y');

INSERT INTO AGRO_QA_CHECKLISTS (ID, CODE, NAME_RU, NAME_RO, CHECKLIST_TYPE, ACTIVE)
VALUES (NULL, 'QC-GMP', 'GMP проверка', 'Verificare GMP', 'gmp', 'Y');

-- ============================================================
-- 13. AGRO_QA_CHECKLIST_ITEMS
--     QC-INC: 7 items, QC-GMP: 5 items
--     FK references use sub-selects on AGRO_QA_CHECKLISTS.CODE
-- ============================================================

-- QC-INC items (incoming inspection)

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-INC'), 1, 'Внешний вид', 'Aspect exterior', 'boolean', NULL, NULL, NULL, 'N');

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-INC'), 2, 'Запах', 'Miros', 'boolean', NULL, NULL, NULL, 'N');

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-INC'), 3, 'Наличие гнили', 'Prezența putregaiului', 'boolean', NULL, NULL, NULL, 'Y');

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-INC'), 4, 'Температура при приёмке', 'Temperatura la recepție', 'numeric', 0, 25, NULL, 'Y');

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-INC'), 5, 'Механические повреждения', 'Deteriorări mecanice', 'choice', NULL, NULL, 'нет|незначительные|значительные', 'N');

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-INC'), 6, 'Содержание сахара (Brix)', 'Conținut de zahăr (Brix)', 'numeric', 8, 25, NULL, 'N');

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-INC'), 7, 'Наличие вредителей', 'Prezența dăunătorilor', 'boolean', NULL, NULL, NULL, 'Y');

-- QC-GMP items (GMP inspection)

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-GMP'), 1, 'Чистота рабочей зоны', 'Curățenia zonei de lucru', 'boolean', NULL, NULL, NULL, 'N');

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-GMP'), 2, 'Наличие средств защиты', 'Echipament de protecție', 'boolean', NULL, NULL, NULL, 'Y');

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-GMP'), 3, 'Температура помещения', 'Temperatura încăperii', 'numeric', 10, 25, NULL, 'N');

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-GMP'), 4, 'Документация в порядке', 'Documentația în ordine', 'boolean', NULL, NULL, NULL, 'N');

INSERT INTO AGRO_QA_CHECKLIST_ITEMS (ID, CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
VALUES (NULL, (SELECT ID FROM AGRO_QA_CHECKLISTS WHERE CODE = 'QC-GMP'), 5, 'Санитарная обработка проведена', 'Tratament sanitar efectuat', 'boolean', NULL, NULL, NULL, 'Y');

-- ============================================================
-- 14. AGRO_HACCP_PLANS (1 row)
-- ============================================================

INSERT INTO AGRO_HACCP_PLANS (ID, CODE, NAME_RU, NAME_RO, PROCESS_STAGE, ACTIVE)
VALUES (NULL, 'HACCP-01', 'План HACCP фрукты', 'Plan HACCP fructe', 'reception_to_storage', 'Y');

-- ============================================================
-- 15. AGRO_HACCP_CCPS (3 rows for HACCP-01)
--     FK references use sub-select on AGRO_HACCP_PLANS.CODE
-- ============================================================

INSERT INTO AGRO_HACCP_CCPS (ID, PLAN_ID, CCP_NUMBER, HAZARD_TYPE, HAZARD_DESCRIPTION, CRITICAL_LIMIT_MIN, CRITICAL_LIMIT_MAX, MONITORING_FREQUENCY, CORRECTIVE_ACTION)
VALUES (NULL, (SELECT ID FROM AGRO_HACCP_PLANS WHERE CODE = 'HACCP-01'), 'CCP-1', 'biological', 'Температура хранения / Temperatura de depozitare', -1, 4, 'каждые 4 часа / la fiecare 4 ore', 'снизить температуру / ajustare temperatură');

INSERT INTO AGRO_HACCP_CCPS (ID, PLAN_ID, CCP_NUMBER, HAZARD_TYPE, HAZARD_DESCRIPTION, CRITICAL_LIMIT_MIN, CRITICAL_LIMIT_MAX, MONITORING_FREQUENCY, CORRECTIVE_ACTION)
VALUES (NULL, (SELECT ID FROM AGRO_HACCP_PLANS WHERE CODE = 'HACCP-01'), 'CCP-2', 'chemical', 'pH раствора мойки / pH soluției de spălare', 6.5, 7.5, 'перед каждой сменой / înainte de fiecare schimb', 'заменить раствор / înlocuire soluție');

INSERT INTO AGRO_HACCP_CCPS (ID, PLAN_ID, CCP_NUMBER, HAZARD_TYPE, HAZARD_DESCRIPTION, CRITICAL_LIMIT_MIN, CRITICAL_LIMIT_MAX, MONITORING_FREQUENCY, CORRECTIVE_ACTION)
VALUES (NULL, (SELECT ID FROM AGRO_HACCP_PLANS WHERE CODE = 'HACCP-01'), 'CCP-3', 'physical', 'Детектор металла / Detector de metale', 0, 0.5, 'непрерывно / continuu', 'остановить линию и проверить / oprire linie și verificare');

-- ============================================================
-- End of AGRO demo data
-- ============================================================

COMMIT;
