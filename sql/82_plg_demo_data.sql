-- ============================================================
-- Планограммы: справочники и демо-данные
-- Демо-магазин воспроизводит макет /Users/pt/Projects.AI/TBControl/Modules/Planograms
-- Координаты зон и оборудования — в системе 780 x 460 (MAP_WIDTH x MAP_HEIGHT).
-- ============================================================

-- ==================== Языки ====================

INSERT INTO PLG_REF_LANGS (CODE, NAME_RU, NAME_RO, NAME_EN, IS_DEFAULT, SORT_ORDER) VALUES ('ru', 'Русский', 'Rusă', 'Russian', 1, 1);
INSERT INTO PLG_REF_LANGS (CODE, NAME_RU, NAME_RO, NAME_EN, IS_DEFAULT, SORT_ORDER) VALUES ('ro', 'Румынский', 'Română', 'Romanian', 0, 2);
INSERT INTO PLG_REF_LANGS (CODE, NAME_RU, NAME_RO, NAME_EN, IS_DEFAULT, SORT_ORDER) VALUES ('en', 'Английский', 'Engleză', 'English', 0, 3);

-- ==================== Типы зон ====================

INSERT INTO PLG_REF_ZONE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, IS_SELLING, SORT_ORDER) VALUES ('dept',         'Отдел',              'Departament',        'Department',   '#2563eb', '▦', 1, 1);
INSERT INTO PLG_REF_ZONE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, IS_SELLING, SORT_ORDER) VALUES ('promo_island', 'Остров акций',       'Insula promoțiilor', 'Promo island', '#c2410c', '◎', 1, 2);
INSERT INTO PLG_REF_ZONE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, IS_SELLING, SORT_ORDER) VALUES ('checkout',     'Кассовая зона',      'Zona de case',       'Checkout',     '#f97316', '⊞', 1, 3);
INSERT INTO PLG_REF_ZONE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, IS_SELLING, SORT_ORDER) VALUES ('entrance',     'Вход',               'Intrare',            'Entrance',     '#16a34a', '⇥', 0, 4);
INSERT INTO PLG_REF_ZONE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, IS_SELLING, SORT_ORDER) VALUES ('storage',      'Склад',              'Depozit',            'Storage',      '#1a2a40', '⊟', 0, 5);
INSERT INTO PLG_REF_ZONE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, IS_SELLING, SORT_ORDER) VALUES ('service',      'Служебное помещение','Încăpere de serviciu','Service room','#1a2a40', '⚙', 0, 6);
INSERT INTO PLG_REF_ZONE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, IS_SELLING, SORT_ORDER) VALUES ('wc',           'Туалет',             'Toaletă',            'Restroom',     '#1a2a40', '⌁', 0, 7);

-- ==================== Типы оборудования ====================

INSERT INTO PLG_REF_FIXTURE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DEFAULT_W_MM, DEFAULT_H_MM, DEFAULT_D_MM, SHELF_COUNT, ICON, SORT_ORDER) VALUES ('shelf',  'Стеллаж',            'Raft',                'Shelving unit', 1000, 1800, 500, 5, '▤', 1);
INSERT INTO PLG_REF_FIXTURE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DEFAULT_W_MM, DEFAULT_H_MM, DEFAULT_D_MM, SHELF_COUNT, ICON, SORT_ORDER) VALUES ('cooler', 'Холодильная витрина','Vitrină frigorifică', 'Cooler',        1250, 2000, 700, 4, '❄', 2);
INSERT INTO PLG_REF_FIXTURE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DEFAULT_W_MM, DEFAULT_H_MM, DEFAULT_D_MM, SHELF_COUNT, ICON, SORT_ORDER) VALUES ('freezer','Морозильный ларь',   'Ladă frigorifică',    'Freezer',       1500, 900,  800, 2, '⛄', 3);
INSERT INTO PLG_REF_FIXTURE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DEFAULT_W_MM, DEFAULT_H_MM, DEFAULT_D_MM, SHELF_COUNT, ICON, SORT_ORDER) VALUES ('pallet', 'Паллета',            'Palet',               'Pallet',        1200, 1200, 800, 1, '▣', 4);
INSERT INTO PLG_REF_FIXTURE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DEFAULT_W_MM, DEFAULT_H_MM, DEFAULT_D_MM, SHELF_COUNT, ICON, SORT_ORDER) VALUES ('island', 'Островная витрина',  'Vitrină insulă',      'Island display',1800, 1000, 900, 2, '◍', 5);
INSERT INTO PLG_REF_FIXTURE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DEFAULT_W_MM, DEFAULT_H_MM, DEFAULT_D_MM, SHELF_COUNT, ICON, SORT_ORDER) VALUES ('endcap', 'Торцевая выкладка',  'Cap de gondolă',      'Endcap',        1000, 1800, 500, 4, '◧', 6);
INSERT INTO PLG_REF_FIXTURE_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, DEFAULT_W_MM, DEFAULT_H_MM, DEFAULT_D_MM, SHELF_COUNT, ICON, SORT_ORDER) VALUES ('rack',   'Навесная стойка',    'Stand suspendat',     'Rack',          600,  1600, 300, 4, '⌸', 7);

-- ==================== Статусы планограмм ====================

INSERT INTO PLG_REF_PLG_STATUSES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, IS_FINAL, SORT_ORDER) VALUES ('draft',    'Черновик',       'Ciornă',    'Draft',    '#7e93a8', 0, 1);
INSERT INTO PLG_REF_PLG_STATUSES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, IS_FINAL, SORT_ORDER) VALUES ('review',   'На согласовании','În avizare','Review',   '#fbab18', 0, 2);
INSERT INTO PLG_REF_PLG_STATUSES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, IS_FINAL, SORT_ORDER) VALUES ('approved', 'Утверждена',     'Aprobată',  'Approved', '#049fd9', 0, 3);
INSERT INTO PLG_REF_PLG_STATUSES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, IS_FINAL, SORT_ORDER) VALUES ('active',   'Действующая',    'În vigoare','Active',   '#6abf4b', 0, 4);
INSERT INTO PLG_REF_PLG_STATUSES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, IS_FINAL, SORT_ORDER) VALUES ('rejected', 'Отклонена',      'Respinsă',  'Rejected', '#e2231a', 1, 5);
INSERT INTO PLG_REF_PLG_STATUSES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, IS_FINAL, SORT_ORDER) VALUES ('archived', 'В архиве',       'Arhivată',  'Archived', '#475569', 1, 6);

-- ==================== Типы задач ====================

INSERT INTO PLG_REF_TASK_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('relayout',   'Перевыкладка',        'Reamplasare',           'Relayout',     '▦', 1);
INSERT INTO PLG_REF_TASK_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('restock',    'Пополнение полки',    'Reaprovizionare raft',  'Restock',      '⊞', 2);
INSERT INTO PLG_REF_TASK_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('promo_setup','Монтаж акции',        'Montare promoție',      'Promo setup',  '◎', 3);
INSERT INTO PLG_REF_TASK_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('audit',      'Аудит выкладки',      'Audit al expunerii',    'Layout audit', '✓', 4);
INSERT INTO PLG_REF_TASK_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('price_tag',  'Замена ценников',     'Schimbare etichete',    'Price tags',   '☰', 5);
INSERT INTO PLG_REF_TASK_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('fix',        'Ремонт оборудования', 'Reparație echipament',  'Equipment fix','⚙', 6);

-- ==================== Типы акций ====================

INSERT INTO PLG_REF_PROMO_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, SORT_ORDER) VALUES ('discount',   'Скидка',            'Reducere',           'Discount',   '#22c55e', 1);
INSERT INTO PLG_REF_PROMO_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, SORT_ORDER) VALUES ('bundle',     'Комплект N+M',      'Pachet N+M',         'Bundle',     '#6366f1', 2);
INSERT INTO PLG_REF_PROMO_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, SORT_ORDER) VALUES ('gift',       'Подарок за покупку','Cadou la cumpărare', 'Free gift',  '#a855f7', 3);
INSERT INTO PLG_REF_PROMO_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, SORT_ORDER) VALUES ('price_lock', 'Фиксация цены',     'Preț fix',           'Price lock', '#f59e0b', 4);
INSERT INTO PLG_REF_PROMO_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, SORT_ORDER) VALUES ('loyalty',    'Для держателей карт','Pentru posesori card','Loyalty',   '#06b6d4', 5);

-- ==================== Типы документов ====================

INSERT INTO PLG_REF_DOC_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('planogram_pdf','Планограмма PDF',   'Planogramă PDF',    'Planogram PDF', '☰', 1);
INSERT INTO PLG_REF_DOC_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('instruction',  'Инструкция',        'Instrucțiune',      'Instruction',   '☰', 2);
INSERT INTO PLG_REF_DOC_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('photo_report', 'Фотоотчёт',         'Raport foto',       'Photo report',  '⊞', 3);
INSERT INTO PLG_REF_DOC_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('act',          'Акт',               'Act',               'Act',           '✓', 4);
INSERT INTO PLG_REF_DOC_TYPES (CODE, NAME_RU, NAME_RO, NAME_EN, ICON, SORT_ORDER) VALUES ('schema',       'Схема зала',        'Schema sălii',      'Floor schema',  '▦', 5);

-- ==================== Настройки модуля ====================

INSERT INTO PLG_SETTINGS (PARAM_CODE, PARAM_VALUE, DESCR_RU, DESCR_RO, DESCR_EN) VALUES ('default_lang',      'ru',  'Язык интерфейса по умолчанию', 'Limba implicită a interfeței', 'Default interface language');
INSERT INTO PLG_SETTINGS (PARAM_CODE, PARAM_VALUE, DESCR_RU, DESCR_RO, DESCR_EN) VALUES ('refresh_interval',  '60',  'Интервал автообновления, сек', 'Interval de reîmprospătare, sec', 'Auto-refresh interval, sec');
INSERT INTO PLG_SETTINGS (PARAM_CODE, PARAM_VALUE, DESCR_RU, DESCR_RO, DESCR_EN) VALUES ('traffic_peak_pct',  '80',  'Порог пиковой проходимости, %', 'Prag de trafic maxim, %', 'Peak traffic threshold, %');
INSERT INTO PLG_SETTINGS (PARAM_CODE, PARAM_VALUE, DESCR_RU, DESCR_RO, DESCR_EN) VALUES ('traffic_high_pct',  '60',  'Порог высокой проходимости, %', 'Prag de trafic ridicat, %', 'High traffic threshold, %');
INSERT INTO PLG_SETTINGS (PARAM_CODE, PARAM_VALUE, DESCR_RU, DESCR_RO, DESCR_EN) VALUES ('traffic_medium_pct','40',  'Порог средней проходимости, %', 'Prag de trafic mediu, %', 'Medium traffic threshold, %');
INSERT INTO PLG_SETTINGS (PARAM_CODE, PARAM_VALUE, DESCR_RU, DESCR_RO, DESCR_EN) VALUES ('currency',          'MDL', 'Валюта показателей', 'Valuta indicatorilor', 'Metrics currency');
INSERT INTO PLG_SETTINGS (PARAM_CODE, PARAM_VALUE, DESCR_RU, DESCR_RO, DESCR_EN) VALUES ('metrics_days',      '30',  'Глубина истории показателей, дней', 'Adâncimea istoricului, zile', 'Metrics history depth, days');

COMMIT;

-- ==================== Категории ====================

INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('produce', 'Овощи и фрукты',      'Legume și fructe',     'Fruits & vegetables', '#16a34a', '◍', 1);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('drinks',  'Напитки',             'Băuturi',              'Beverages',           '#2563eb', '◉', 2);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('snacks',  'Снеки и сладости',    'Gustări și dulciuri',  'Snacks & sweets',     '#d97706', '◈', 3);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('dairy',   'Молочные продукты',   'Produse lactate',      'Dairy',               '#0369a1', '▤', 4);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('grocery', 'Бакалея',             'Băcănie',              'Grocery',             '#7c3aed', '▦', 5);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('health',  'Здоровое питание',    'Alimentație sănătoasă','Healthy food',        '#0d9488', '✦', 6);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('coffee',  'Кофе и чай',          'Cafea și ceai',        'Coffee & tea',        '#854d0e', '☕', 7);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('kids',    'Товары для детей',    'Produse pentru copii', 'Kids',                '#db2777', '⊛', 8);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('chem',    'Бытовая химия',       'Chimie de uz casnic',  'Household chemicals', '#475569', '⌾', 9);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('bakery',  'Пекарня',             'Brutărie',             'Bakery',              '#c2410c', '◐', 10);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('meat',    'Мясо',                'Carne',                'Meat',                '#991b1b', '◆', 11);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('fish',    'Рыба',                'Pește',                'Fish',                '#1d4ed8', '◇', 12);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('frozen',  'Замороженные',        'Produse congelate',    'Frozen',              '#4338ca', '❄', 13);
INSERT INTO PLG_CATEGORIES (CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, SORT_ORDER) VALUES ('alcohol', 'Алкоголь',            'Alcool',               'Alcohol',             '#6d28d9', '◔', 14);

COMMIT;

-- ==================== Магазины ====================

INSERT INTO PLG_STORES (CODE, NAME_RU, NAME_RO, NAME_EN, CITY, ADDRESS_RU, ADDRESS_RO, ADDRESS_EN, AREA_SQM, MAP_WIDTH, MAP_HEIGHT, CHECKOUT_QTY, MANAGER_NAME)
VALUES ('MD-CHS-024', 'Магазин 24', 'Magazin 24', 'Store 24', 'Chișinău',
        'ул. Штефан чел Маре, 15', 'str. Ștefan cel Mare, 15', '15 Stefan cel Mare St.', 1240, 780, 460, 6, 'Иван Петров');

INSERT INTO PLG_STORES (CODE, NAME_RU, NAME_RO, NAME_EN, CITY, ADDRESS_RU, ADDRESS_RO, ADDRESS_EN, AREA_SQM, MAP_WIDTH, MAP_HEIGHT, CHECKOUT_QTY, MANAGER_NAME)
VALUES ('MD-CHS-012', 'Магазин 12', 'Magazin 12', 'Store 12', 'Chișinău',
        'бул. Дачия, 8', 'bd. Dacia, 8', '8 Dacia Blvd.', 860, 780, 460, 4, 'Мария Урсу');

INSERT INTO PLG_STORES (CODE, NAME_RU, NAME_RO, NAME_EN, CITY, ADDRESS_RU, ADDRESS_RO, ADDRESS_EN, AREA_SQM, MAP_WIDTH, MAP_HEIGHT, CHECKOUT_QTY, MANAGER_NAME)
VALUES ('MD-BLZ-007', 'Магазин 7',  'Magazin 7',  'Store 7',  'Bălți',
        'ул. Индепенденцей, 22', 'str. Independenței, 22', '22 Independentei St.', 640, 780, 460, 3, 'Сергей Ротару');

COMMIT;
/

-- ==================== Зоны демо-магазина (координаты макета) ====================

DECLARE
  v_store NUMBER;
  PROCEDURE add_zone(p_code VARCHAR2, p_type VARCHAR2, p_cat VARCHAR2,
                     p_ru VARCHAR2, p_ro VARCHAR2, p_en VARCHAR2,
                     p_x NUMBER, p_y NUMBER, p_w NUMBER, p_h NUMBER,
                     p_color VARCHAR2, p_sort NUMBER) IS
    v_cat NUMBER := NULL;
  BEGIN
    IF p_cat IS NOT NULL THEN
      SELECT ID INTO v_cat FROM PLG_CATEGORIES WHERE CODE = p_cat;
    END IF;
    INSERT INTO PLG_ZONES (STORE_ID, CODE, ZONE_TYPE, CATEGORY_ID, NAME_RU, NAME_RO, NAME_EN,
                           POS_X, POS_Y, WIDTH, HEIGHT, COLOR, AREA_SQM, SORT_ORDER)
    VALUES (v_store, p_code, p_type, v_cat, p_ru, p_ro, p_en,
            p_x, p_y, p_w, p_h, p_color, ROUND(p_w * p_h / 100, 2), p_sort);
  END;
BEGIN
  SELECT ID INTO v_store FROM PLG_STORES WHERE CODE = 'MD-CHS-024';

  -- Верхний ряд отделов
  add_zone('produce', 'dept', 'produce', 'Овощи и фрукты',    'Legume și fructe',      'Fruits & vegetables', 162,   8,  72, 55, '#16a34a', 1);
  add_zone('drinks',  'dept', 'drinks',  'Напитки',           'Băuturi',               'Beverages',           242,   8,  72, 55, '#2563eb', 2);
  add_zone('snacks',  'dept', 'snacks',  'Снеки',             'Gustări',               'Snacks',              322,   8,  72, 55, '#d97706', 3);
  add_zone('grocery', 'dept', 'grocery', 'Бакалея',           'Băcănie',               'Grocery',             402,   8,  72, 55, '#7c3aed', 4);
  add_zone('health',  'dept', 'health',  'Здоровое питание',  'Alimentație sănătoasă', 'Healthy food',        482,   8,  72, 55, '#0d9488', 5);
  add_zone('coffee',  'dept', 'coffee',  'Кофе и чай',        'Cafea și ceai',         'Coffee & tea',        562,   8,  72, 55, '#854d0e', 6);
  add_zone('kids',    'dept', 'kids',    'Товары для детей',  'Produse pentru copii',  'Kids',                642,   8,  72, 55, '#db2777', 7);
  add_zone('chem',    'dept', 'chem',    'Бытовая химия',     'Chimie de uz casnic',   'Household chem.',     718,   8,  55, 55, '#475569', 8);

  -- Левая стена
  add_zone('bakery',  'dept', 'bakery',  'Пекарня',           'Brutărie',              'Bakery',                8,  90, 130, 52, '#c2410c', 9);
  add_zone('meat',    'dept', 'meat',    'Мясо',              'Carne',                 'Meat',                  8, 152, 130, 52, '#991b1b', 10);
  add_zone('fish',    'dept', 'fish',    'Рыба',              'Pește',                 'Fish',                  8, 214, 130, 52, '#1d4ed8', 11);
  add_zone('dairy',   'dept', 'dairy',   'Молочные продукты', 'Produse lactate',       'Dairy',                 8, 276, 130, 52, '#0369a1', 12);
  add_zone('frozen',  'dept', 'frozen',  'Замороженные',      'Produse congelate',     'Frozen',                8, 338, 130, 52, '#4338ca', 13);

  -- Правая сторона
  add_zone('storage', 'storage', NULL,   'Склад',             'Depozit',               'Storage',             718,  72,  55, 80, '#1a2a40', 14);
  add_zone('service', 'service', NULL,   'Служебное помещение','Încăpere de serviciu', 'Service room',        718, 162,  55, 55, '#1a2a40', 15);
  add_zone('wc',      'wc',      NULL,   'Туалет',            'Toaletă',               'Restroom',            718, 228,  55, 45, '#1a2a40', 16);
  add_zone('alcohol', 'dept',    'alcohol','Алкоголь',        'Alcool',                'Alcohol',             718, 283,  55, 80, '#6d28d9', 17);

  -- Остров акций, касса, вход
  add_zone('promo',    'promo_island', NULL, 'Остров акций',  'Insula promoțiilor',    'Promo island',        162, 356,  70, 50, '#c2410c', 18);
  add_zone('checkout', 'checkout',     NULL, 'Кассовая зона', 'Zona de case',          'Checkout',            460, 348, 250, 100,'#f97316', 19);
  add_zone('entrance', 'entrance',     NULL, 'Вход',          'Intrare',               'Entrance',            176, 435,  42, 22, '#16a34a', 20);

  COMMIT;
END;
/

-- ==================== Оборудование торгового зала ====================

DECLARE
  v_store NUMBER;
  TYPE t_rows IS TABLE OF NUMBER;
  v_y     t_rows := t_rows(82, 154, 226, 298);
  v_zone  NUMBER;
  v_idx   NUMBER := 0;
  v_x     NUMBER;
  v_w     NUMBER;
  v_zcode VARCHAR2(30);
BEGIN
  SELECT ID INTO v_store FROM PLG_STORES WHERE CODE = 'MD-CHS-024';

  -- Четыре ряда стеллажей центральной части (макет: 5 модулей в ряду, 4-й ряд короче)
  FOR r IN 1 .. v_y.COUNT LOOP
    FOR c IN 1 .. CASE WHEN r = 4 THEN 4 ELSE 5 END LOOP
      v_x := 170 + (c - 1) * 110;
      v_w := CASE WHEN c = 5 THEN 90 ELSE 80 END;
      v_zcode := CASE c WHEN 1 THEN 'produce' WHEN 2 THEN 'drinks' WHEN 3 THEN 'grocery'
                        WHEN 4 THEN 'snacks'  ELSE 'coffee' END;
      SELECT ID INTO v_zone FROM PLG_ZONES WHERE STORE_ID = v_store AND CODE = v_zcode;
      v_idx := v_idx + 1;
      INSERT INTO PLG_FIXTURES (STORE_ID, ZONE_ID, CODE, FIXTURE_TYPE, NAME_RU, NAME_RO, NAME_EN,
                                POS_X, POS_Y, WIDTH, HEIGHT, ORIENTATION, SHELF_COUNT,
                                WIDTH_MM, HEIGHT_MM, DEPTH_MM, SERIAL_NUMBER)
      VALUES (v_store, v_zone, 'ST-24-' || CHR(64 + r) || LPAD(c, 2, '0'), 'shelf',
              'Стеллаж ряд ' || r || ' модуль ' || c,
              'Raft rând ' || r || ' modul ' || c,
              'Shelving row ' || r || ' unit ' || c,
              v_x, v_y(r), v_w, 42, 'H', 5, v_w * 12, 1800, 500,
              'SN-ST-' || LPAD(v_idx, 4, '0'));
    END LOOP;
  END LOOP;

  -- Пристенное холодильное оборудование
  FOR z IN (SELECT ID, CODE, POS_X, POS_Y, WIDTH, HEIGHT FROM PLG_ZONES
             WHERE STORE_ID = v_store AND CODE IN ('bakery','meat','fish','dairy','frozen')) LOOP
    v_idx := v_idx + 1;
    INSERT INTO PLG_FIXTURES (STORE_ID, ZONE_ID, CODE, FIXTURE_TYPE, NAME_RU, NAME_RO, NAME_EN,
                              POS_X, POS_Y, WIDTH, HEIGHT, ORIENTATION, SHELF_COUNT,
                              WIDTH_MM, HEIGHT_MM, DEPTH_MM, SERIAL_NUMBER)
    VALUES (v_store, z.ID, 'CL-24-' || UPPER(SUBSTR(z.CODE, 1, 3)),
            CASE z.CODE WHEN 'frozen' THEN 'freezer' ELSE 'cooler' END,
            'Витрина ' || z.CODE, 'Vitrină ' || z.CODE, 'Display ' || z.CODE,
            z.POS_X, z.POS_Y, z.WIDTH, z.HEIGHT, 'V', 4, 1250, 2000, 700,
            'SN-CL-' || LPAD(v_idx, 4, '0'));
  END LOOP;

  -- Островная витрина акций
  SELECT ID INTO v_zone FROM PLG_ZONES WHERE STORE_ID = v_store AND CODE = 'promo';
  INSERT INTO PLG_FIXTURES (STORE_ID, ZONE_ID, CODE, FIXTURE_TYPE, NAME_RU, NAME_RO, NAME_EN,
                            POS_X, POS_Y, WIDTH, HEIGHT, ORIENTATION, SHELF_COUNT,
                            WIDTH_MM, HEIGHT_MM, DEPTH_MM, SERIAL_NUMBER)
  VALUES (v_store, v_zone, 'IS-24-PR1', 'island', 'Остров акций', 'Insula promoțiilor', 'Promo island',
          162, 356, 70, 50, 'H', 2, 1800, 1000, 900, 'SN-IS-0001');

  COMMIT;
END;
/

-- ==================== Товары ====================

DECLARE
  PROCEDURE add_product(p_code VARCHAR2, p_cat VARCHAR2, p_ru VARCHAR2, p_ro VARCHAR2, p_en VARCHAR2,
                        p_brand VARCHAR2, p_price NUMBER, p_w NUMBER, p_h NUMBER, p_d NUMBER) IS
    v_cat NUMBER;
  BEGIN
    SELECT ID INTO v_cat FROM PLG_CATEGORIES WHERE CODE = p_cat;
    INSERT INTO PLG_PRODUCTS (CODE, CATEGORY_ID, NAME_RU, NAME_RO, NAME_EN, BARCODE, BRAND,
                              UOM, PRICE, CURRENCY, WIDTH_MM, HEIGHT_MM, DEPTH_MM, MIN_FACINGS)
    VALUES (p_code, v_cat, p_ru, p_ro, p_en,
            '484' || LPAD(ABS(DBMS_RANDOM.RANDOM) MOD 10000000, 10, '0'), p_brand,
            'pcs', p_price, 'MDL', p_w, p_h, p_d, 2);
  END;
BEGIN
  add_product('P-APL-01', 'produce', 'Яблоки Голден, кг',      'Mere Golden, kg',           'Golden apples, kg',      'Local',      24.90, 100, 120, 100);
  add_product('P-BAN-01', 'produce', 'Бананы, кг',             'Banane, kg',                'Bananas, kg',            'Chiquita',   32.50, 120, 100, 120);
  add_product('P-TOM-01', 'produce', 'Томаты черри, 250 г',    'Roșii cherry, 250 g',       'Cherry tomatoes, 250 g', 'Local',      28.00,  90,  70,  90);
  add_product('P-WAT-01', 'drinks',  'Вода негаз., 1.5 л',     'Apă plată, 1.5 l',          'Still water, 1.5 l',     'Gura Cainar', 9.90,  90, 320,  90);
  add_product('P-COL-01', 'drinks',  'Кола, 2 л',              'Cola, 2 l',                 'Cola, 2 l',              'Coca-Cola',  29.90, 105, 340, 105);
  add_product('P-JUI-01', 'drinks',  'Сок яблочный, 1 л',      'Suc de mere, 1 l',          'Apple juice, 1 l',       'Orhei-Vit',  21.50,  80, 240,  80);
  add_product('P-CHP-01', 'snacks',  'Чипсы паприка, 130 г',   'Chipsuri paprika, 130 g',   'Paprika chips, 130 g',   'Lays',       27.90, 160, 250,  70);
  add_product('P-CHO-01', 'snacks',  'Шоколад молочный, 90 г', 'Ciocolată cu lapte, 90 g',  'Milk chocolate, 90 g',   'Bucuria',    18.40,  85, 160,  20);
  add_product('P-MLK-01', 'dairy',   'Молоко 2.5%, 1 л',       'Lapte 2.5%, 1 l',           'Milk 2.5%, 1 l',         'JLC',        16.90,  75, 220,  75);
  add_product('P-YOG-01', 'dairy',   'Йогурт клубника, 330 г', 'Iaurt căpșuni, 330 g',      'Strawberry yogurt, 330 g','JLC',       14.20,  70, 130,  70);
  add_product('P-CHE-01', 'dairy',   'Сыр Гауда, 200 г',       'Cașcaval Gouda, 200 g',     'Gouda cheese, 200 g',    'Hochland',   42.00, 130,  40, 100);
  add_product('P-PAS-01', 'grocery', 'Макароны спагетти, 500 г','Paste spaghetti, 500 g',   'Spaghetti, 500 g',       'Barilla',    19.90,  90, 260,  50);
  add_product('P-RIC-01', 'grocery', 'Рис длиннозёрный, 1 кг', 'Orez cu bob lung, 1 kg',    'Long grain rice, 1 kg',  'Bunge',      27.30, 140, 200,  70);
  add_product('P-OIL-01', 'grocery', 'Масло подсолн., 1 л',    'Ulei de floarea-soarelui, 1 l','Sunflower oil, 1 l',  'Floris',     34.80,  85, 300,  85);
  add_product('P-MUE-01', 'health',  'Мюсли с орехами, 400 г', 'Muesli cu nuci, 400 g',     'Nut muesli, 400 g',      'Verde',      45.00, 160, 230,  70);
  add_product('P-COF-01', 'coffee',  'Кофе зерновой, 1 кг',    'Cafea boabe, 1 kg',         'Coffee beans, 1 kg',     'Lavazza',   189.00, 150, 320, 100);
  add_product('P-TEA-01', 'coffee',  'Чай чёрный, 100 пак.',   'Ceai negru, 100 pl.',       'Black tea, 100 bags',    'Ahmad',      52.00, 150, 120, 100);
  add_product('P-DIA-01', 'kids',    'Подгузники, 44 шт.',     'Scutece, 44 buc.',          'Diapers, 44 pcs',        'Pampers',   219.00, 300, 250, 180);
  add_product('P-DET-01', 'chem',    'Гель для стирки, 2 л',   'Detergent lichid, 2 l',     'Laundry gel, 2 l',       'Ariel',     119.00, 180, 300, 110);
  add_product('P-BRD-01', 'bakery',  'Хлеб белый, 500 г',      'Pâine albă, 500 g',         'White bread, 500 g',     'Franzeluța', 11.50, 200, 110, 120);
  add_product('P-CHK-01', 'meat',    'Филе куриное, кг',       'Piept de pui, kg',          'Chicken breast, kg',     'Local',      89.00, 200,  60, 150);
  add_product('P-SAL-01', 'fish',    'Сёмга с/с, 200 г',       'Somon sărat, 200 g',        'Salted salmon, 200 g',   'Nord',       98.00, 180,  40, 120);
  add_product('P-PIZ-01', 'frozen',  'Пицца заморож., 350 г',  'Pizza congelată, 350 g',    'Frozen pizza, 350 g',    'Dr. Oetker', 54.00, 260,  30, 260);
  add_product('P-WIN-01', 'alcohol', 'Вино красное сухое, 0.75','Vin roșu sec, 0.75',       'Dry red wine, 0.75',     'Cricova',    89.00,  80, 320,  80);

  COMMIT;
END;
/

-- ==================== Планограммы и позиции ====================

DECLARE
  v_store NUMBER;
  v_plg   NUMBER;
  v_zone  NUMBER;
  v_fixt  NUMBER;
  v_pos   NUMBER;

  PROCEDURE new_planogram(p_zcode VARCHAR2, p_ru VARCHAR2, p_ro VARCHAR2, p_en VARCHAR2,
                          p_status VARCHAR2, p_ver NUMBER, p_author VARCHAR2, p_share NUMBER,
                          o_id OUT NUMBER) IS
    v_z NUMBER;
  BEGIN
    SELECT ID INTO v_z FROM PLG_ZONES WHERE STORE_ID = v_store AND CODE = p_zcode;
    INSERT INTO PLG_PLANOGRAMS (STORE_ID, ZONE_ID, NAME_RU, NAME_RO, NAME_EN, VERSION_NO, STATUS,
                                VALID_FROM, VALID_TO, AUTHOR, APPROVED_BY, APPROVED_AT,
                                SHELF_SHARE_PCT, NOTES)
    VALUES (v_store, v_z, p_ru, p_ro, p_en, p_ver, p_status,
            TRUNC(SYSDATE) - 30, TRUNC(SYSDATE) + 60, p_author,
            CASE WHEN p_status IN ('approved','active','archived') THEN 'Иван Петров' END,
            CASE WHEN p_status IN ('approved','active','archived') THEN SYSTIMESTAMP - 5 END,
            p_share, NULL)
    RETURNING ID INTO o_id;
  END;

  PROCEDURE add_item(p_plg NUMBER, p_fixt NUMBER, p_prod VARCHAR2,
                     p_shelf NUMBER, p_pos NUMBER, p_facings NUMBER, p_promo NUMBER) IS
    v_p NUMBER;
  BEGIN
    SELECT ID INTO v_p FROM PLG_PRODUCTS WHERE CODE = p_prod;
    INSERT INTO PLG_PLANOGRAM_ITEMS (PLANOGRAM_ID, FIXTURE_ID, PRODUCT_ID, SHELF_NO, POSITION_NO,
                                     FACINGS, DEPTH_QTY, IS_PROMO)
    VALUES (p_plg, p_fixt, v_p, p_shelf, p_pos, p_facings, 3, p_promo);
  END;
BEGIN
  SELECT ID INTO v_store FROM PLG_STORES WHERE CODE = 'MD-CHS-024';

  -- Действующая планограмма отдела «Напитки»
  new_planogram('drinks', 'Напитки — основная выкладка', 'Băuturi — expunere principală',
                'Beverages — main layout', 'active', 3, 'Мария Урсу', 18.5, v_plg);
  SELECT ID INTO v_fixt FROM PLG_FIXTURES WHERE STORE_ID = v_store AND CODE = 'ST-24-A02';
  add_item(v_plg, v_fixt, 'P-WAT-01', 1, 1, 6, 0);
  add_item(v_plg, v_fixt, 'P-COL-01', 1, 2, 4, 1);
  add_item(v_plg, v_fixt, 'P-JUI-01', 2, 1, 5, 0);

  -- Действующая планограмма молочного отдела
  new_planogram('dairy', 'Молочные продукты — пристенная витрина', 'Produse lactate — vitrină de perete',
                'Dairy — wall cooler', 'active', 2, 'Мария Урсу', 12.0, v_plg);
  SELECT ID INTO v_fixt FROM PLG_FIXTURES WHERE STORE_ID = v_store AND CODE = 'CL-24-DAI';
  add_item(v_plg, v_fixt, 'P-MLK-01', 1, 1, 8, 0);
  add_item(v_plg, v_fixt, 'P-YOG-01', 2, 1, 6, 0);
  add_item(v_plg, v_fixt, 'P-CHE-01', 3, 1, 4, 0);

  -- На согласовании: перевыкладка бакалеи
  new_planogram('grocery', 'Бакалея — перевыкладка Q3', 'Băcănie — reamplasare Q3',
                'Grocery — Q3 relayout', 'review', 1, 'Сергей Ротару', 15.2, v_plg);
  SELECT ID INTO v_fixt FROM PLG_FIXTURES WHERE STORE_ID = v_store AND CODE = 'ST-24-A03';
  add_item(v_plg, v_fixt, 'P-PAS-01', 1, 1, 5, 0);
  add_item(v_plg, v_fixt, 'P-RIC-01', 1, 2, 4, 0);
  add_item(v_plg, v_fixt, 'P-OIL-01', 2, 1, 4, 0);

  -- Черновик: остров акций
  new_planogram('promo', 'Остров акций — августовская кампания', 'Insula promoțiilor — campania august',
                'Promo island — August campaign', 'draft', 1, 'Иван Петров', 4.0, v_plg);
  SELECT ID INTO v_fixt FROM PLG_FIXTURES WHERE STORE_ID = v_store AND CODE = 'IS-24-PR1';
  add_item(v_plg, v_fixt, 'P-CHP-01', 1, 1, 8, 1);
  add_item(v_plg, v_fixt, 'P-CHO-01', 1, 2, 10, 1);

  -- Архивная версия выкладки снеков
  new_planogram('snacks', 'Снеки — выкладка Q2 (архив)', 'Gustări — expunere Q2 (arhivă)',
                'Snacks — Q2 layout (archived)', 'archived', 4, 'Мария Урсу', 9.8, v_plg);
  SELECT ID INTO v_fixt FROM PLG_FIXTURES WHERE STORE_ID = v_store AND CODE = 'ST-24-B02';
  add_item(v_plg, v_fixt, 'P-CHP-01', 1, 1, 6, 0);
  add_item(v_plg, v_fixt, 'P-CHO-01', 2, 1, 8, 0);

  COMMIT;
END;
/

-- ==================== История изменений ====================

DECLARE
  v_id NUMBER;
BEGIN
  FOR p IN (SELECT ID, CODE, VERSION_NO, STATUS FROM PLG_PLANOGRAMS ORDER BY ID) LOOP
    INSERT INTO PLG_PLANOGRAM_HISTORY (PLANOGRAM_ID, VERSION_NO, ACTION, SUMMARY_RU, SUMMARY_RO, SUMMARY_EN, CHANGED_BY, CHANGED_AT)
    VALUES (p.ID, 1, 'created', 'Планограмма создана', 'Planogramă creată', 'Planogram created', 'Мария Урсу', SYSTIMESTAMP - 30);

    IF p.VERSION_NO > 1 THEN
      FOR v IN 2 .. p.VERSION_NO LOOP
        INSERT INTO PLG_PLANOGRAM_HISTORY (PLANOGRAM_ID, VERSION_NO, ACTION, FIELD_NAME, OLD_VALUE, NEW_VALUE,
                                           SUMMARY_RU, SUMMARY_RO, SUMMARY_EN, CHANGED_BY, CHANGED_AT)
        VALUES (p.ID, v, 'updated', 'FACINGS', TO_CHAR(v + 2), TO_CHAR(v + 4),
                'Изменено количество фейсингов', 'Număr de facing-uri modificat', 'Facing count changed',
                'Сергей Ротару', SYSTIMESTAMP - (30 - v * 6));
      END LOOP;
    END IF;

    IF p.STATUS IN ('active','approved','archived') THEN
      INSERT INTO PLG_PLANOGRAM_HISTORY (PLANOGRAM_ID, VERSION_NO, ACTION, FIELD_NAME, OLD_VALUE, NEW_VALUE,
                                         SUMMARY_RU, SUMMARY_RO, SUMMARY_EN, CHANGED_BY, CHANGED_AT)
      VALUES (p.ID, p.VERSION_NO, 'status_change', 'STATUS', 'review', p.STATUS,
              'Планограмма утверждена', 'Planogramă aprobată', 'Planogram approved',
              'Иван Петров', SYSTIMESTAMP - 5);
    END IF;
  END LOOP;
  COMMIT;
END;
/

-- ==================== Акции ====================

DECLARE
  v_store NUMBER;
  v_promo NUMBER;
  PROCEDURE add_promo(p_code VARCHAR2, p_type VARCHAR2, p_ru VARCHAR2, p_ro VARCHAR2, p_en VARCHAR2,
                      p_label VARCHAR2, p_disc NUMBER, p_from NUMBER, p_to NUMBER,
                      p_color VARCHAR2, p_status VARCHAR2, o_id OUT NUMBER) IS
  BEGIN
    INSERT INTO PLG_PROMOS (CODE, STORE_ID, PROMO_TYPE, NAME_RU, NAME_RO, NAME_EN, LABEL,
                            DISCOUNT_PCT, DATE_FROM, DATE_TO, COLOR, STATUS)
    VALUES (p_code, v_store, p_type, p_ru, p_ro, p_en, p_label, p_disc,
            TRUNC(SYSDATE) + p_from, TRUNC(SYSDATE) + p_to, p_color, p_status)
    RETURNING ID INTO o_id;
  END;

  PROCEDURE link_zone(p_promo NUMBER, p_zcode VARCHAR2) IS
    v_z NUMBER;
  BEGIN
    SELECT ID INTO v_z FROM PLG_ZONES WHERE STORE_ID = v_store AND CODE = p_zcode;
    INSERT INTO PLG_PROMO_ZONES (PROMO_ID, ZONE_ID) VALUES (p_promo, v_z);
  END;

  PROCEDURE link_prod(p_promo NUMBER, p_prod VARCHAR2, p_price NUMBER) IS
    v_p NUMBER;
  BEGIN
    SELECT ID INTO v_p FROM PLG_PRODUCTS WHERE CODE = p_prod;
    INSERT INTO PLG_PROMO_PRODUCTS (PROMO_ID, PRODUCT_ID, PROMO_PRICE) VALUES (p_promo, v_p, p_price);
  END;
BEGIN
  SELECT ID INTO v_store FROM PLG_STORES WHERE CODE = 'MD-CHS-024';

  add_promo('PR-2026-001', 'discount', 'Скидка на фрукты', 'Reducere la fructe', 'Discount on fruits',
            '-20%', 20, -7, 5, '#22c55e', 'active', v_promo);
  link_zone(v_promo, 'produce');
  link_prod(v_promo, 'P-APL-01', 19.90);
  link_prod(v_promo, 'P-BAN-01', 26.00);

  add_promo('PR-2026-002', 'bundle', 'Напитки 2+1', 'Băuturi 2+1', 'Beverages 2+1',
            '2+1', 33, -3, 10, '#6366f1', 'active', v_promo);
  link_zone(v_promo, 'drinks');
  link_prod(v_promo, 'P-COL-01', 29.90);
  link_prod(v_promo, 'P-JUI-01', 21.50);

  add_promo('PR-2026-003', 'discount', 'Скидка на молочку', 'Reducere la lactate', 'Discount on dairy',
            '-15%', 15, -5, 8, '#f59e0b', 'active', v_promo);
  link_zone(v_promo, 'dairy');
  link_prod(v_promo, 'P-MLK-01', 14.40);
  link_prod(v_promo, 'P-YOG-01', 12.10);

  add_promo('PR-2026-004', 'gift', 'Подарок к кофе', 'Cadou la cafea', 'Gift with coffee',
            'GIFT', 0, 3, 20, '#a855f7', 'planned', v_promo);
  link_zone(v_promo, 'coffee');
  link_prod(v_promo, 'P-COF-01', 189.00);

  add_promo('PR-2026-005', 'price_lock', 'Фиксация цены на хлеб', 'Preț fix la pâine', 'Bread price lock',
            'FIX', 0, -40, -10, '#f97316', 'finished', v_promo);
  link_zone(v_promo, 'bakery');
  link_prod(v_promo, 'P-BRD-01', 10.90);

  COMMIT;
END;
/

-- ==================== Метрики: 30 дней ====================

DECLARE
  v_store    NUMBER;
  v_traffic  NUMBER;
  v_buyers   NUMBER;
  v_check    NUMBER;
  v_conv     NUMBER;
  v_visits   NUMBER;
  v_base     NUMBER;
BEGIN
  FOR s IN (SELECT ID, AREA_SQM FROM PLG_STORES) LOOP
    v_store := s.ID;
    v_base  := GREATEST(NVL(s.AREA_SQM, 800), 400) / 1240;

    FOR d IN 0 .. 29 LOOP
      -- Показатели магазина
      v_traffic := ROUND((18900 + DBMS_RANDOM.VALUE(0, 1900) + d * 12) * v_base);
      v_buyers  := ROUND(v_traffic * DBMS_RANDOM.VALUE(0.170, 0.190));
      v_check   := ROUND(820 + DBMS_RANDOM.VALUE(0, 80), 2);
      v_conv    := ROUND(v_buyers / v_traffic * 100, 2);

      INSERT INTO PLG_STORE_METRICS (STORE_ID, METRIC_DATE, TRAFFIC, BUYERS, CONVERSION_PCT, AVG_CHECK, REVENUE, CURRENCY)
      VALUES (v_store, TRUNC(SYSDATE) - d, v_traffic, v_buyers, v_conv, v_check,
              ROUND(v_buyers * v_check, 2), 'MDL');

      -- Показатели категорий
      FOR c IN (SELECT ID, SORT_ORDER FROM PLG_CATEGORIES ORDER BY SORT_ORDER) LOOP
        v_visits := ROUND((950 - c.SORT_ORDER * 55 + DBMS_RANDOM.VALUE(-40, 40)) * v_base);
        IF v_visits < 20 THEN v_visits := 20 + ROUND(DBMS_RANDOM.VALUE(0, 30)); END IF;
        INSERT INTO PLG_CATEGORY_METRICS (STORE_ID, CATEGORY_ID, METRIC_DATE, VISITS, SALES_QTY, SALES_AMT)
        VALUES (v_store, c.ID, TRUNC(SYSDATE) - d, v_visits,
                ROUND(v_visits * DBMS_RANDOM.VALUE(0.4, 0.8)),
                ROUND(v_visits * DBMS_RANDOM.VALUE(18, 65), 2));
      END LOOP;
    END LOOP;
  END LOOP;

  -- Проходимость зон: 14 дней, суточный агрегат
  FOR z IN (SELECT ID, ZONE_TYPE, SORT_ORDER FROM PLG_ZONES) LOOP
    FOR d IN 0 .. 13 LOOP
      INSERT INTO PLG_ZONE_TRAFFIC (ZONE_ID, METRIC_DATE, METRIC_HOUR, TRAFFIC_PCT, VISITORS, DWELL_SEC, PICKUPS)
      VALUES (z.ID, TRUNC(SYSDATE) - d, NULL,
              CASE z.ZONE_TYPE
                WHEN 'checkout' THEN 100
                WHEN 'entrance' THEN 100
                WHEN 'storage'  THEN ROUND(DBMS_RANDOM.VALUE(3, 12), 2)
                WHEN 'service'  THEN ROUND(DBMS_RANDOM.VALUE(2, 10), 2)
                WHEN 'wc'       THEN ROUND(DBMS_RANDOM.VALUE(8, 22), 2)
                ELSE GREATEST(20, LEAST(98, ROUND(95 - z.SORT_ORDER * 3.2 + DBMS_RANDOM.VALUE(-12, 12), 2)))
              END,
              ROUND(DBMS_RANDOM.VALUE(400, 2900)),
              ROUND(DBMS_RANDOM.VALUE(20, 240)),
              ROUND(DBMS_RANDOM.VALUE(50, 900)));
    END LOOP;
  END LOOP;

  COMMIT;
END;
/

-- ==================== Задачи ====================

DECLARE
  v_store NUMBER;
  v_zone  NUMBER;
  v_plg   NUMBER;
  PROCEDURE add_task(p_zcode VARCHAR2, p_type VARCHAR2, p_ru VARCHAR2, p_ro VARCHAR2, p_en VARCHAR2,
                     p_prio VARCHAR2, p_status VARCHAR2, p_assignee VARCHAR2, p_due NUMBER) IS
    v_z NUMBER;
  BEGIN
    SELECT ID INTO v_z FROM PLG_ZONES WHERE STORE_ID = v_store AND CODE = p_zcode;
    INSERT INTO PLG_TASKS (STORE_ID, ZONE_ID, TASK_TYPE, TITLE_RU, TITLE_RO, TITLE_EN,
                           PRIORITY, STATUS, ASSIGNEE, DUE_DATE, CREATED_BY,
                           DONE_AT, DESCRIPTION)
    VALUES (v_store, v_z, p_type, p_ru, p_ro, p_en, p_prio, p_status, p_assignee,
            TRUNC(SYSDATE) + p_due, 'Иван Петров',
            CASE WHEN p_status = 'done' THEN SYSTIMESTAMP - 1 END,
            NULL);
  END;
BEGIN
  SELECT ID INTO v_store FROM PLG_STORES WHERE CODE = 'MD-CHS-024';

  add_task('drinks',  'relayout',   'Перевыкладка стеллажа напитков', 'Reamplasarea raftului de băuturi', 'Beverage shelf relayout',      'high',   'in_progress', 'Андрей Кожокару', 2);
  add_task('promo',   'promo_setup','Монтаж острова акций',           'Montarea insulei promoționale',    'Promo island setup',           'high',   'new',         'Виктория Мунтяну', 1);
  add_task('dairy',   'restock',    'Пополнение молочной витрины',    'Reaprovizionarea vitrinei lactate','Dairy cooler restock',         'medium', 'new',         'Андрей Кожокару', 0);
  add_task('grocery', 'audit',      'Аудит выкладки бакалеи',         'Auditul expunerii băcăniei',       'Grocery layout audit',         'medium', 'review',      'Сергей Ротару',   4);
  add_task('snacks',  'price_tag',  'Замена ценников в снеках',       'Schimbarea etichetelor la gustări','Snack price tag replacement',   'low',    'done',        'Виктория Мунтяну', -2);
  add_task('frozen',  'fix',        'Ремонт морозильного ларя',       'Reparația lăzii frigorifice',      'Freezer repair',               'high',   'in_progress', 'Тех. служба',     -1);
  add_task('bakery',  'relayout',   'Перевыкладка хлебного отдела',   'Reamplasarea raionului de pâine',  'Bakery section relayout',      'low',    'new',         'Андрей Кожокару', 7);

  COMMIT;
END;
/

-- ==================== Документы ====================

DECLARE
  v_store NUMBER;
BEGIN
  SELECT ID INTO v_store FROM PLG_STORES WHERE CODE = 'MD-CHS-024';

  FOR p IN (SELECT ID, CODE, NAME_RU, NAME_RO, NAME_EN FROM PLG_PLANOGRAMS WHERE STORE_ID = v_store) LOOP
    INSERT INTO PLG_DOCUMENTS (STORE_ID, PLANOGRAM_ID, DOC_TYPE, TITLE_RU, TITLE_RO, TITLE_EN,
                               FILE_NAME, MIME_TYPE, FILE_URL, FILE_SIZE_KB, VERSION_NO, CREATED_BY)
    VALUES (v_store, p.ID, 'planogram_pdf',
            p.NAME_RU || ' (PDF)', p.NAME_RO || ' (PDF)', p.NAME_EN || ' (PDF)',
            LOWER(p.CODE) || '.pdf', 'application/pdf', '/static/planograms/' || LOWER(p.CODE) || '.pdf',
            ROUND(DBMS_RANDOM.VALUE(180, 1400)), 1, 'Мария Урсу');
  END LOOP;

  INSERT INTO PLG_DOCUMENTS (STORE_ID, DOC_TYPE, TITLE_RU, TITLE_RO, TITLE_EN, FILE_NAME, MIME_TYPE, FILE_URL, FILE_SIZE_KB, CREATED_BY)
  VALUES (v_store, 'schema', 'Схема торгового зала 2026', 'Schema sălii comerciale 2026', 'Sales floor schema 2026',
          'floor-2026.svg', 'image/svg+xml', '/static/planograms/floor-2026.svg', 96, 'Иван Петров');

  INSERT INTO PLG_DOCUMENTS (STORE_ID, DOC_TYPE, TITLE_RU, TITLE_RO, TITLE_EN, FILE_NAME, MIME_TYPE, FILE_URL, FILE_SIZE_KB, CREATED_BY)
  VALUES (v_store, 'instruction', 'Стандарт выкладки товара', 'Standardul de expunere a mărfii', 'Merchandising standard',
          'merch-standard.pdf', 'application/pdf', '/static/planograms/merch-standard.pdf', 512, 'Иван Петров');

  INSERT INTO PLG_DOCUMENTS (STORE_ID, DOC_TYPE, TITLE_RU, TITLE_RO, TITLE_EN, FILE_NAME, MIME_TYPE, FILE_URL, FILE_SIZE_KB, CREATED_BY)
  VALUES (v_store, 'photo_report', 'Фотоотчёт: зона акций', 'Raport foto: zona promoțiilor', 'Photo report: promo zone',
          'promo-2026-08.jpg', 'image/jpeg', '/static/planograms/promo-2026-08.jpg', 2240, 'Виктория Мунтяну');

  COMMIT;
END;
/

-- ==================== Уведомления ====================

DECLARE
  v_store NUMBER;
BEGIN
  SELECT ID INTO v_store FROM PLG_STORES WHERE CODE = 'MD-CHS-024';

  INSERT INTO PLG_NOTIFICATIONS (STORE_ID, LEVEL_CODE, ENTITY_TYPE, TEXT_RU, TEXT_RO, TEXT_EN, IS_READ, CREATED_AT)
  VALUES (v_store, 'warn', 'planogram', 'Изменение планограммы в отделе «Напитки»',
          'Modificarea planogramei la raionul „Băuturi"', 'Planogram change in the Beverages department', 0, SYSTIMESTAMP - INTERVAL '5' MINUTE);

  INSERT INTO PLG_NOTIFICATIONS (STORE_ID, LEVEL_CODE, ENTITY_TYPE, TEXT_RU, TEXT_RO, TEXT_EN, IS_READ, CREATED_AT)
  VALUES (v_store, 'alert', 'product', 'Низкий остаток: Молоко 2.5%',
          'Stoc redus: Lapte 2.5%', 'Low stock: Milk 2.5%', 0, SYSTIMESTAMP - INTERVAL '15' MINUTE);

  INSERT INTO PLG_NOTIFICATIONS (STORE_ID, LEVEL_CODE, ENTITY_TYPE, TEXT_RU, TEXT_RO, TEXT_EN, IS_READ, CREATED_AT)
  VALUES (v_store, 'info', 'promo', 'Новая акция «Скидка на фрукты»',
          'Promoție nouă „Reducere la fructe"', 'New promotion "Discount on fruits"', 0, SYSTIMESTAMP - INTERVAL '1' HOUR);

  INSERT INTO PLG_NOTIFICATIONS (STORE_ID, LEVEL_CODE, ENTITY_TYPE, TEXT_RU, TEXT_RO, TEXT_EN, IS_READ, CREATED_AT)
  VALUES (v_store, 'warn', 'task', 'Задача «Ремонт морозильного ларя» просрочена',
          'Sarcina „Reparația lăzii frigorifice" este întârziată', 'Task "Freezer repair" is overdue', 0, SYSTIMESTAMP - INTERVAL '3' HOUR);

  INSERT INTO PLG_NOTIFICATIONS (STORE_ID, LEVEL_CODE, ENTITY_TYPE, TEXT_RU, TEXT_RO, TEXT_EN, IS_READ, CREATED_AT)
  VALUES (v_store, 'info', 'planogram', 'Планограмма бакалеи отправлена на согласование',
          'Planograma băcăniei a fost trimisă spre avizare', 'Grocery planogram submitted for review', 0, SYSTIMESTAMP - INTERVAL '6' HOUR);

  COMMIT;
END;
/
