-- =====================================================================
-- RO: ANULAREA grupelor aduse de importul 2 (IMPRESO).
-- EN: ROLLBACK of the groups brought by import 2 (IMPRESO).
--     Fisier sursa / source file: impreso.md / all_products 2.SVERKA.xlsx (2026-08-14)
--     Data / date: 2026-08-14
--     Randuri: total 2662, create 2643, potrivite 19, sarite 0
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
--  WHERE cod IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- RO: 2) grupele CREATE de acest import (doar cele ramase goale)
-- EN: 2) groups CREATED by this import (only the ones left empty)
-- Cartus Cerneala / Banda > Cartus Matricial > Banda de Transfer   (acest import: 308 marfuri; acum in total: 317)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartus Cerneala / Banda')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cartus Matricial'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Cartus Cerneala / Banda > Cartus Matricial   (acest import: 9 marfuri; acum in total: 317)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartus Cerneala / Banda')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cartus Matricial'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Cartus Toner > Cartus Monochrom > Cartus Color   (acest import: 294 marfuri; acum in total: 525)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartus Toner')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cartus Monochrom'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Cartus Toner > Cartus Monochrom > HP   (acest import: 69 marfuri; acum in total: 525)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartus Toner')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cartus Monochrom'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Cartus Toner > Cartus Monochrom   (acest import: 162 marfuri; acum in total: 525)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartus Toner')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cartus Monochrom'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Cartus Toner   (acest import: 1 marfuri; acum in total: 1)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartus Toner')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Cerneala > Universala > Pigment   (acest import: 131 marfuri; acum in total: 149)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Universala'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Cerneala > Universala   (acest import: 18 marfuri; acum in total: 149)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Universala'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Hirtie Foto > Mata > Lucioasa   (acest import: 42 marfuri; acum in total: 52)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie Foto')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Mata'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Hirtie Foto > Mata   (acest import: 2 marfuri; acum in total: 52)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie Foto')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Mata'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Imprimanta > Laser Monochrome > Cu jet de cerneala   (acest import: 7 marfuri; acum in total: 11)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimanta')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Laser Monochrome'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Imprimanta > Laser Monochrome   (acest import: 4 marfuri; acum in total: 11)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimanta')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Laser Monochrome'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Multifunctionala > Laser Monochrome > Cu jet de cerneala   (acest import: 17 marfuri; acum in total: 24)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Multifunctionala')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Laser Monochrome'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Multifunctionala > Laser Monochrome   (acest import: 5 marfuri; acum in total: 24)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Multifunctionala')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Laser Monochrome'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Piese Cartus > Cip > Lamela de curatare   (acest import: 311 marfuri; acum in total: 952)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Piese Cartus')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cip'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Piese Cartus > Cip   (acest import: 641 marfuri; acum in total: 952)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Piese Cartus')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cip'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Piese Imprimanta > Piese > Canon   (acest import: 133 marfuri; acum in total: 521)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Piese Imprimanta')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Piese'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Piese Imprimanta > Piese > Diverse   (acest import: 374 marfuri; acum in total: 521)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Piese Imprimanta')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Piese'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Piese Imprimanta > Piese   (acest import: 14 marfuri; acum in total: 521)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Piese Imprimanta')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Piese'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- SACC > Canon > Epson   (acest import: 11 marfuri; acum in total: 14)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('SACC')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Canon'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- SACC > Canon   (acest import: 3 marfuri; acum in total: 14)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('SACC')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Canon'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Toner > Toner Color > Toner Monochrom   (acest import: 39 marfuri; acum in total: 97)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Toner')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Toner Color'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Toner > Toner Color   (acest import: 58 marfuri; acum in total: 97)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Toner')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Toner Color'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- Toner   (acest import: 9 marfuri; acum in total: 9)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Toner')) AND categorie IS NULL
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 2);

-- RO: 3) nodurile din arborele nativ ramase fara marfa
-- EN: 3) native-tree nodes left with no goods
-- DELETE FROM tms_sysgrph h WHERE h.id0 = 1
--   AND NOT EXISTS (SELECT 1 FROM tms_sysgrp g WHERE g.id0 = 1 AND g.id1 = h.id1)
--   AND UPPER(TRIM(h.coment)) IN (
--     'CARTUS CERNEALA / BANDA', 'CARTUS TONER', 'CERNEALA', 'HIRTIE FOTO', 'IMPRIMANTA', 'MULTIFUNCTIONALA', 'PIESE CARTUS', 'PIESE IMPRIMANTA', 'SACC', 'TONER');

-- RO: 4) marcajele de sursa si evidenta grupelor
-- DELETE FROM tms_mpt_impsrc      WHERE src_import_id = 2;
-- DELETE FROM ybiro_import_groups WHERE import_id     = 2;
-- UPDATE ybiro_import_log SET notes = notes || ' [ANULAT]' WHERE import_id = 2;
