-- =====================================================================
-- RO: ANULAREA grupelor aduse de importul 4 (BESTBUY).
-- EN: ROLLBACK of the groups brought by import 4 (BESTBUY).
--     Fisier sursa / source file: Set_data_import/13/all_products bestbuy.xlsx (2026-08-22)
--     Data / date: 2026-08-22
--     Randuri: total 8655, create 0, potrivite 7384, sarite 1271
--
-- RO: ATENTIE — scriptul NU se ruleaza automat. Citeste-l, verifica
--     numarul de marfuri din fiecare grupa (coloana N_PRODUCTS_TOTAL_NOW
--     din CSV-ul alaturat) si ruleaza doar ce vrei sa anulezi.
-- EN: WARNING — this script does not run itself. Read it, check how many
--     goods each group holds NOW, and run only what you mean to undo.
-- =====================================================================

-- RO: 1) marfurile aduse de acest import (le poti arhiva in loc sa le stergi)
-- EN: 1) the goods this import brought (archive rather than delete)
-- UPDATE tms_univers SET isarhiv = '2'
--  WHERE cod IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- RO: 2) grupele CREATE de acest import (doar cele ramase goale)
-- EN: 2) groups CREATED by this import (only the ones left empty)
-- Apple   (acest import: 2 marfuri; acum in total: 2)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Apple')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Gaming   (acest import: 40 marfuri; acum in total: 40)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Gaming')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- PowerBank   (acest import: 156 marfuri; acum in total: 156)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('PowerBank')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- PROMO   (acest import: 7 marfuri; acum in total: 7)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('PROMO')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Tablets &amp; Phones > Phones   (acest import: 37 marfuri; acum in total: 0)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Tablets &amp; Phones')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Phones'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Tablets &amp; Phones > Tablets   (acest import: 15 marfuri; acum in total: 0)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Tablets &amp; Phones')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Tablets'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Авто Товары > Driving recorder   (acest import: 32 marfuri; acum in total: 32)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Авто Товары')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Driving recorder'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Авто Товары > FM-модуляторы / Bluetooth   (acest import: 30 marfuri; acum in total: 30)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Авто Товары')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('FM-модуляторы / Bluetooth'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Авто Товары > Автомобильное беспроводное зарядное устройство   (acest import: 59 marfuri; acum in total: 59)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Авто Товары')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Автомобильное беспроводное зарядное устройство'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Авто Товары > Автомобильное зарядное устройство   (acest import: 122 marfuri; acum in total: 122)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Авто Товары')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Автомобильное зарядное устройство'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Авто Товары > Автомобильные Пылесосы   (acest import: 14 marfuri; acum in total: 14)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Авто Товары')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Автомобильные Пылесосы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Авто Товары > Держатели для телефонов   (acest import: 212 marfuri; acum in total: 212)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Авто Товары')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Держатели для телефонов'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Авто Товары > Насосы   (acest import: 11 marfuri; acum in total: 11)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Авто Товары')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Насосы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Авто Товары   (acest import: 34 marfuri; acum in total: 34)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Авто Товары')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аксессуары для Ноутбуков / Планшета > Mouse Pad   (acest import: 7 marfuri; acum in total: 7)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аксессуары для Ноутбуков / Планшета')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Mouse Pad'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аксессуары для Ноутбуков / Планшета > Stylus / Graphic Pen   (acest import: 7 marfuri; acum in total: 7)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аксессуары для Ноутбуков / Планшета')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Stylus / Graphic Pen'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аксессуары для Ноутбуков / Планшета > Зарядные блоки   (acest import: 26 marfuri; acum in total: 26)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аксессуары для Ноутбуков / Планшета')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Зарядные блоки'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аксессуары для Ноутбуков / Планшета > Клавиатуры   (acest import: 37 marfuri; acum in total: 37)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аксессуары для Ноутбуков / Планшета')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Клавиатуры'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аксессуары для Ноутбуков / Планшета > Мышки   (acest import: 56 marfuri; acum in total: 56)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аксессуары для Ноутбуков / Планшета')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Мышки'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аксессуары для Ноутбуков / Планшета > Подставка для Ноутбука / Планшета   (acest import: 30 marfuri; acum in total: 30)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аксессуары для Ноутбуков / Планшета')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Подставка для Ноутбука / Планшета'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аксессуары для Ноутбуков / Планшета > Сумки / Рюкзаки   (acest import: 130 marfuri; acum in total: 130)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аксессуары для Ноутбуков / Планшета')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сумки / Рюкзаки'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аксессуары для Ноутбуков / Планшета > Хабы / Адапторы   (acest import: 82 marfuri; acum in total: 82)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аксессуары для Ноутбуков / Планшета')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Хабы / Адапторы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аксессуары для Ноутбуков / Планшета   (acest import: 10 marfuri; acum in total: 10)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аксессуары для Ноутбуков / Планшета')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аудио > Bluetooth-наушники   (acest import: 298 marfuri; acum in total: 298)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аудио')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Bluetooth-наушники'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аудио > Гарнитуры   (acest import: 8 marfuri; acum in total: 8)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аудио')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Гарнитуры'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аудио > Колонки   (acest import: 283 marfuri; acum in total: 283)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аудио')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Колонки'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аудио > Микрофоны   (acest import: 41 marfuri; acum in total: 41)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аудио')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Микрофоны'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аудио > Наушники Jack 3,5mm   (acest import: 77 marfuri; acum in total: 77)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аудио')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Наушники Jack 3,5mm'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аудио > Наушники Lightning   (acest import: 5 marfuri; acum in total: 5)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аудио')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Наушники Lightning'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аудио > Наушники USB-C / Type-C   (acest import: 30 marfuri; acum in total: 30)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аудио')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Наушники USB-C / Type-C'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аудио > Переходники для аудио   (acest import: 37 marfuri; acum in total: 37)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аудио')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Переходники для аудио'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Аудио   (acest import: 8 marfuri; acum in total: 8)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Аудио')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Батареи > iPhone   (acest import: 37 marfuri; acum in total: 37)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Батареи')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('iPhone'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Батареи   (acest import: 7 marfuri; acum in total: 7)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Батареи')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Зарядные устройства > Беспроводные Зарядки   (acest import: 85 marfuri; acum in total: 85)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Зарядные устройства')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Беспроводные Зарядки'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Зарядные устройства > Зарядные блоки   (acest import: 391 marfuri; acum in total: 391)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Зарядные устройства')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Зарядные блоки'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Зарядные устройства > Зарядные блоки с кабелем Lightning   (acest import: 1 marfuri; acum in total: 1)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Зарядные устройства')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Зарядные блоки с кабелем Lightning'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Зарядные устройства > Зарядные блоки с кабелем USB-C / Type-C   (acest import: 2 marfuri; acum in total: 2)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Зарядные устройства')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Зарядные блоки с кабелем USB-C / Type-C'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Зарядные устройства > Зарядные устройства для Умных часов   (acest import: 11 marfuri; acum in total: 11)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Зарядные устройства')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Зарядные устройства для Умных часов'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Зарядные устройства   (acest import: 14 marfuri; acum in total: 14)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Зарядные устройства')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Защитные стекла > Apple   (acest import: 337 marfuri; acum in total: 337)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Защитные стекла')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Apple'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Защитные стекла > Oppo   (acest import: 7 marfuri; acum in total: 7)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Защитные стекла')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Oppo'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Защитные стекла > Redmi/Xiaomi   (acest import: 30 marfuri; acum in total: 30)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Защитные стекла')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Redmi/Xiaomi'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Защитные стекла > Samsung   (acest import: 100 marfuri; acum in total: 100)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Защитные стекла')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Samsung'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > AUX   (acest import: 38 marfuri; acum in total: 38)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('AUX'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > HDMI   (acest import: 25 marfuri; acum in total: 25)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('HDMI'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > Lightning (iPhone)   (acest import: 153 marfuri; acum in total: 153)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Lightning (iPhone)'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > Lightning/Micro/Type-C   (acest import: 7 marfuri; acum in total: 7)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Lightning/Micro/Type-C'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > Magsafe   (acest import: 4 marfuri; acum in total: 4)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Magsafe'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > Micro USB   (acest import: 44 marfuri; acum in total: 44)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Micro USB'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > Network   (acest import: 9 marfuri; acum in total: 9)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Network'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > ThunderBolt   (acest import: 1 marfuri; acum in total: 1)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('ThunderBolt'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > Type-C to USB   (acest import: 58 marfuri; acum in total: 58)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Type-C to USB'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > USB B   (acest import: 2 marfuri; acum in total: 2)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('USB B'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > USB male to USB   (acest import: 1 marfuri; acum in total: 1)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('USB male to USB'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля > USB-C / Type-C   (acest import: 154 marfuri; acum in total: 154)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('USB-C / Type-C'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Кабеля   (acest import: 6 marfuri; acum in total: 6)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Кабеля')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Мелкая Бытовая Техника > Видеопроекторы   (acest import: 9 marfuri; acum in total: 9)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Мелкая Бытовая Техника')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Видеопроекторы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Мелкая Бытовая Техника > Другие   (acest import: 233 marfuri; acum in total: 233)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Мелкая Бытовая Техника')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Другие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Мелкая Бытовая Техника > Освещение   (acest import: 50 marfuri; acum in total: 50)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Мелкая Бытовая Техника')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Освещение'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Мелкая Бытовая Техника > Приборы для укладки   (acest import: 47 marfuri; acum in total: 47)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Мелкая Бытовая Техника')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Приборы для укладки'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Мелкая Бытовая Техника > Уличные и домашние камеры   (acest import: 36 marfuri; acum in total: 36)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Мелкая Бытовая Техника')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Уличные и домашние камеры'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Мелкая Бытовая Техника > Электрические зубные щетки и ирригаторы   (acest import: 10 marfuri; acum in total: 10)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Мелкая Бытовая Техника')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Электрические зубные щетки и ирригаторы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Мелкая Бытовая Техника > Электробитва   (acest import: 51 marfuri; acum in total: 51)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Мелкая Бытовая Техника')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Электробитва'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Мелкая Бытовая Техника   (acest import: 10 marfuri; acum in total: 10)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Мелкая Бытовая Техника')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Накопители Информации > Micro SD   (acest import: 14 marfuri; acum in total: 14)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Накопители Информации')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Micro SD'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Накопители Информации > SSD   (acest import: 4 marfuri; acum in total: 4)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Накопители Информации')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('SSD'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Накопители Информации > USB Flash Drive   (acest import: 29 marfuri; acum in total: 29)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Накопители Информации')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('USB Flash Drive'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Стенды для телефонов / Селфи-палки   (acest import: 80 marfuri; acum in total: 80)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Стенды для телефонов / Селфи-палки')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Умные часы / Ремешки > Ремешки для часов   (acest import: 242 marfuri; acum in total: 242)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Умные часы / Ремешки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Ремешки для часов'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Умные часы / Ремешки > Умные часы   (acest import: 98 marfuri; acum in total: 98)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Умные часы / Ремешки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Умные часы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Чехлы > Apple   (acest import: 2074 marfuri; acum in total: 2074)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Чехлы')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Apple'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Чехлы > Oppo   (acest import: 81 marfuri; acum in total: 81)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Чехлы')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Oppo'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Чехлы > Samsung   (acest import: 630 marfuri; acum in total: 630)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Чехлы')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Samsung'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Чехлы > Xiaomi/Redmi   (acest import: 209 marfuri; acum in total: 209)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Чехлы')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Xiaomi/Redmi'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Чехлы > Универсальные водозащитные чехолы   (acest import: 3 marfuri; acum in total: 3)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Чехлы')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Универсальные водозащитные чехолы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- Чехлы   (acest import: 6 marfuri; acum in total: 6)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Чехлы')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 4);

-- RO: 3) nodurile din arborele nativ ramase fara marfa
-- EN: 3) native-tree nodes left with no goods
-- DELETE FROM tms_sysgrph h WHERE h.id0 = 1
--   AND NOT EXISTS (SELECT 1 FROM tms_sysgrp g WHERE g.id0 = 1 AND g.id1 = h.id1)
--   AND UPPER(TRIM(h.coment)) IN (
--     'APPLE', 'GAMING', 'POWERBANK', 'PROMO', 'TABLETS &AMP; PHONES', 'АВТО ТОВАРЫ', 'АКСЕССУАРЫ ДЛЯ НОУТБУКОВ / ПЛАНШЕТА', 'АУДИО', 'БАТАРЕИ', 'ЗАРЯДНЫЕ УСТРОЙСТВА', 'ЗАЩИТНЫЕ СТЕКЛА', 'КАБЕЛЯ', 'МЕЛКАЯ БЫТОВАЯ ТЕХНИКА', 'НАКОПИТЕЛИ ИНФОРМАЦИИ', 'СТЕНДЫ ДЛЯ ТЕЛЕФОНОВ / СЕЛФИ-ПАЛКИ', 'УМНЫЕ ЧАСЫ / РЕМЕШКИ', 'ЧЕХЛЫ');

-- RO: 4) marcajele de sursa si evidenta grupelor
-- DELETE FROM tms_mpt_impsrc      WHERE src_import_id = 4;
-- DELETE FROM ybiro_import_groups WHERE import_id     = 4;
-- UPDATE ybiro_import_log SET notes = notes || ' [ANULAT]' WHERE import_id = 4;
