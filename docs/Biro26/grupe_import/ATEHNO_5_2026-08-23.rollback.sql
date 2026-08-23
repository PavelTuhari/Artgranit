-- =====================================================================
-- RO: ANULAREA grupelor aduse de importul 5 (ATEHNO).
-- EN: ROLLBACK of the groups brought by import 5 (ATEHNO).
--     Fisier sursa / source file: Set_data_import/14/atehno_catalog.xlsx (2026-08-23)
--     Data / date: 2026-08-23
--     Randuri: total 22397, create 21229, potrivite 21733, sarite 664
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
--  WHERE cod IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- RO: 2) grupele CREATE de acest import (doar cele ramase goale)
-- EN: 2) groups CREATED by this import (only the ones left empty)
-- Видеонаблюдение > Видеонаблюдение > Видео-звонки   (acest import: 29 marfuri; acum in total: 489)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Видеонаблюдение')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Видеонаблюдение'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Видеонаблюдение > Видеонаблюдение > Звонки   (acest import: 76 marfuri; acum in total: 489)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Видеонаблюдение')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Видеонаблюдение'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Видеонаблюдение > Видеонаблюдение > Комплекты видеонаблюдение   (acest import: 11 marfuri; acum in total: 489)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Видеонаблюдение')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Видеонаблюдение'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Видеонаблюдение > Видеонаблюдение > Питание   (acest import: 164 marfuri; acum in total: 489)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Видеонаблюдение')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Видеонаблюдение'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Видеонаблюдение > Видеонаблюдение > Смарт-камеры   (acest import: 209 marfuri; acum in total: 489)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Видеонаблюдение')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Видеонаблюдение'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Выключатели, розетки и контакторы > Металлические шкафы   (acest import: 3 marfuri; acum in total: 3)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Выключатели, розетки и контакторы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Освещение > Лампы на солнечной батарее   (acest import: 66 marfuri; acum in total: 492)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Освещение'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Освещение > Ночники   (acest import: 55 marfuri; acum in total: 492)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Освещение'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Освещение > Офисные и настольные лампы   (acest import: 249 marfuri; acum in total: 492)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Освещение'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Освещение > Праздничное освещение   (acest import: 122 marfuri; acum in total: 492)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Освещение'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Сад и огород > Воздуходувки   (acest import: 73 marfuri; acum in total: 381)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сад и огород'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Сад и огород > Мотобуры, мотокультиваторы и культиваторы   (acest import: 56 marfuri; acum in total: 381)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сад и огород'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Сад и огород > Оборудование для полива   (acest import: 228 marfuri; acum in total: 381)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сад и огород'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Сад и огород > Сетки и заборы   (acest import: 24 marfuri; acum in total: 381)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сад и огород'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Садовая мебель   (acest import: 106 marfuri; acum in total: 106)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Садовая мебель'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Дом и сад > Столы,стулья,кресла > Компьютерные столы   (acest import: 1 marfuri; acum in total: 0)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Дом и сад')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Столы,стулья,кресла'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Брендовые ПК > All in One PC   (acest import: 257 marfuri; acum in total: 330)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Брендовые ПК'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Брендовые ПК > Desktop PC   (acest import: 31 marfuri; acum in total: 330)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Брендовые ПК'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Брендовые ПК > Mini PC   (acest import: 42 marfuri; acum in total: 330)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Брендовые ПК'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Диски   (acest import: 62 marfuri; acum in total: 62)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Диски'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Игровые Консоли > Аксессуары для консолей   (acest import: 36 marfuri; acum in total: 118)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Игровые Консоли'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Игровые Консоли > Игры   (acest import: 46 marfuri; acum in total: 118)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Игровые Консоли'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Игровые Консоли   (acest import: 36 marfuri; acum in total: 118)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Игровые Консоли'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Инструмент   (acest import: 9 marfuri; acum in total: 9)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Инструмент'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > DVD-RW-Приводы   (acest import: 13 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > HDD   (acest import: 107 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > SSD   (acest import: 223 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > Блоки питания   (acest import: 152 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > Видеокарты   (acest import: 79 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > Дополнительное Охлаждение   (acest import: 120 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > Звуковые карты   (acest import: 3 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > Контроллеры и адаптеры   (acest import: 9 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > Корпуса   (acest import: 214 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > Материнские платы   (acest import: 198 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > Модули памяти   (acest import: 222 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > Охлаждение Процессора   (acest import: 189 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Комплектующие > Процессоры   (acest import: 105 marfuri; acum in total: 1634)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Комплектующие'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Мониторы   (acest import: 523 marfuri; acum in total: 523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Мониторы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > POS терминалы   (acest import: 5 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > Бумага   (acest import: 136 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > Калькуляторы   (acest import: 5 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > Картриджи   (acest import: 2092 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > Копиры   (acest import: 8 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > Ламинаторы   (acest import: 33 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > МФУ   (acest import: 120 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > Плоттеры   (acest import: 6 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > Принтеры   (acest import: 69 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > Резаки для Бумаги   (acest import: 1 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > Сканеры   (acest import: 31 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Оргтехника > Сканеры штрих кода   (acest import: 4 marfuri; acum in total: 2523)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Оргтехника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Bluetooth Адаптеры   (acest import: 11 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Card Readers   (acest import: 25 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > KVM Switch   (acest import: 4 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > USB Концентраторы   (acest import: 39 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Акустика   (acest import: 156 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Веб-Камеры   (acest import: 83 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Графические Планшеты   (acest import: 40 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Игровые кресла   (acest import: 1056 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Игровые манипуляторы   (acest import: 90 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Кабеля   (acest import: 1059 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Карты памяти   (acest import: 140 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Клавиатуры   (acest import: 493 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Коврики   (acest import: 181 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Мыши   (acest import: 666 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Наушники микрофоны   (acest import: 1108 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Периферия > Флэшки USB   (acest import: 177 marfuri; acum in total: 5327)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Подарочные сертификаты   (acest import: 3 marfuri; acum in total: 3)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Подарочные сертификаты'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Программы   (acest import: 44 marfuri; acum in total: 44)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Программы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Серверы   (acest import: 262 marfuri; acum in total: 262)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Серверы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Сетевое оборудование > ADSL   (acest import: 5 marfuri; acum in total: 1074)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сетевое оборудование'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Сетевое оборудование > Mikrotik   (acest import: 100 marfuri; acum in total: 1074)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сетевое оборудование'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Сетевое оборудование > NAS Серверы   (acest import: 23 marfuri; acum in total: 1074)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сетевое оборудование'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Сетевое оборудование > POE   (acest import: 61 marfuri; acum in total: 1074)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сетевое оборудование'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Сетевое оборудование > Кабеля, Аксессуары   (acest import: 537 marfuri; acum in total: 1074)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сетевое оборудование'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Сетевое оборудование > Оборудование Powerline   (acest import: 10 marfuri; acum in total: 1074)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сетевое оборудование'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Сетевое оборудование > Прочее   (acest import: 14 marfuri; acum in total: 1074)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сетевое оборудование'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Сетевое оборудование > Сетевые адаптеры   (acest import: 28 marfuri; acum in total: 1074)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сетевое оборудование'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Сетевое оборудование > Сетевые коммутаторы   (acest import: 296 marfuri; acum in total: 1074)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Сетевое оборудование'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Собранные ПК   (acest import: 59 marfuri; acum in total: 59)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Собранные ПК'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Чистяющие средства   (acest import: 75 marfuri; acum in total: 75)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Чистяющие средства'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Компьютеры > Электропитание > UPS   (acest import: 912 marfuri; acum in total: 912)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Компьютеры')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Электропитание'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Аксессуары для Ноутбуков > DOCK STATION   (acest import: 112 marfuri; acum in total: 1219)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Аксессуары для Ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Аксессуары для Ноутбуков > Автомобильные Инверторы   (acest import: 13 marfuri; acum in total: 1219)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Аксессуары для Ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Аксессуары для Ноутбуков > Зарядки   (acest import: 105 marfuri; acum in total: 1219)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Аксессуары для Ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Аксессуары для Ноутбуков > Наклейки на клавиатуру   (acest import: 8 marfuri; acum in total: 1219)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Аксессуары для Ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Аксессуары для Ноутбуков > Подставки   (acest import: 35 marfuri; acum in total: 1219)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Аксессуары для Ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Аксессуары для Ноутбуков > Прочее   (acest import: 28 marfuri; acum in total: 1219)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Аксессуары для Ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Аксессуары для Ноутбуков > Сумки для ноутбуков   (acest import: 918 marfuri; acum in total: 1219)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Аксессуары для Ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Все ноутбуки   (acest import: 591 marfuri; acum in total: 591)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Все ноутбуки'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Запчасти для ноутбуков > Батареи для Ноутбуков   (acest import: 142 marfuri; acum in total: 751)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Запчасти для ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Запчасти для ноутбуков > Клавиатуры   (acest import: 198 marfuri; acum in total: 751)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Запчасти для ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Запчасти для ноутбуков > Компоненты   (acest import: 199 marfuri; acum in total: 751)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Запчасти для ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Запчасти для ноутбуков > Системы охлаждения   (acest import: 161 marfuri; acum in total: 751)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Запчасти для ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Запчасти для ноутбуков > Экраны для Ноутбуков   (acest import: 51 marfuri; acum in total: 751)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Запчасти для ноутбуков'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Ноутбуки > Периферия > Портативные зарядки   (acest import: 196 marfuri; acum in total: 196)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Ноутбуки')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Периферия'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Спорт и досуг > БОЕВЫЕ ИСКУССТВА   (acest import: 14 marfuri; acum in total: 14)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Спорт и досуг')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('БОЕВЫЕ ИСКУССТВА'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Спорт и досуг > ВЕЛОСИПЕДЫ И РОЛИКИ   (acest import: 57 marfuri; acum in total: 57)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Спорт и досуг')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('ВЕЛОСИПЕДЫ И РОЛИКИ'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Спорт и досуг > ИГРОВЫЕ ВИДЫ СПОРТА   (acest import: 78 marfuri; acum in total: 78)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Спорт и досуг')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('ИГРОВЫЕ ВИДЫ СПОРТА'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Спорт и досуг > СИЛОВЫЕ ТРЕНИРОВКИ   (acest import: 90 marfuri; acum in total: 90)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Спорт и досуг')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('СИЛОВЫЕ ТРЕНИРОВКИ'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Спорт и досуг > ФИТНЕС   (acest import: 172 marfuri; acum in total: 172)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Спорт и досуг')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('ФИТНЕС'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Подъемные устройства > Аксессуары для подъемников   (acest import: 87 marfuri; acum in total: 269)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Подъемные устройства'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Подъемные устройства > Домкраты   (acest import: 91 marfuri; acum in total: 269)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Подъемные устройства'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Подъемные устройства > Лебедки   (acest import: 12 marfuri; acum in total: 269)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Подъемные устройства'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Подъемные устройства > Лебедки ручные   (acest import: 44 marfuri; acum in total: 269)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Подъемные устройства'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Подъемные устройства > Лебедки электрические   (acest import: 27 marfuri; acum in total: 269)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Подъемные устройства'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Подъемные устройства > Монтажные блоки   (acest import: 8 marfuri; acum in total: 269)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Подъемные устройства'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Ручные инструменты > Горелки   (acest import: 46 marfuri; acum in total: 705)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Ручные инструменты'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Ручные инструменты > Измерительные инструменты   (acest import: 492 marfuri; acum in total: 705)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Ручные инструменты'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Ручные инструменты > Инструменты для нарезания резьбы   (acest import: 81 marfuri; acum in total: 705)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Ручные инструменты'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Ручные инструменты > Пистолеты для монтажа   (acest import: 86 marfuri; acum in total: 705)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Ручные инструменты'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Спецодежда и СИЗ > Защитное снаряжение   (acest import: 200 marfuri; acum in total: 2801)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Спецодежда и СИЗ'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Спецодежда и СИЗ > Обувь   (acest import: 877 marfuri; acum in total: 2801)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Спецодежда и СИЗ'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Спецодежда и СИЗ > Спецодежда   (acest import: 1724 marfuri; acum in total: 2801)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Спецодежда и СИЗ'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Стабилизаторы и трансформаторы > Стабилизаторы   (acest import: 1 marfuri; acum in total: 1)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Стабилизаторы и трансформаторы'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Строительное оборудование и техника > Аксессуары строительного оборудования   (acest import: 25 marfuri; acum in total: 239)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Строительное оборудование и техника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Строительное оборудование и техника > Бетономешалки   (acest import: 7 marfuri; acum in total: 239)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Строительное оборудование и техника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Строительное оборудование и техника > Машины для резки и шлифовки бетона   (acest import: 43 marfuri; acum in total: 239)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Строительное оборудование и техника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Строительное оборудование и техника > Строительные вибраторы   (acest import: 42 marfuri; acum in total: 239)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Строительное оборудование и техника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Строительное оборудование и техника > Строительные леса и лестницы   (acest import: 102 marfuri; acum in total: 239)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Строительное оборудование и техника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Строительное оборудование и техника > Тачки   (acest import: 20 marfuri; acum in total: 239)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Строительное оборудование и техника'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Строительство и ремонт > Электродвигатели   (acest import: 14 marfuri; acum in total: 14)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Строительство и ремонт')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Электродвигатели'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- Телефоны > Мобильные телефоны   (acest import: 121 marfuri; acum in total: 121)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Телефоны')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Мобильные телефоны'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 5);

-- RO: 3) nodurile din arborele nativ ramase fara marfa
-- EN: 3) native-tree nodes left with no goods
-- DELETE FROM tms_sysgrph h WHERE h.id0 = 1
--   AND NOT EXISTS (SELECT 1 FROM tms_sysgrp g WHERE g.id0 = 1 AND g.id1 = h.id1)
--   AND UPPER(TRIM(h.coment)) IN (
--     'ВИДЕОНАБЛЮДЕНИЕ', 'ДОМ И САД', 'КОМПЬЮТЕРЫ', 'НОУТБУКИ', 'СПОРТ И ДОСУГ', 'СТРОИТЕЛЬСТВО И РЕМОНТ', 'ТЕЛЕФОНЫ');

-- RO: 4) marcajele de sursa si evidenta grupelor
-- DELETE FROM tms_mpt_impsrc      WHERE src_import_id = 5;
-- DELETE FROM ybiro_import_groups WHERE import_id     = 5;
-- UPDATE ybiro_import_log SET notes = notes || ' [ANULAT]' WHERE import_id = 5;
