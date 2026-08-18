-- =====================================================================
-- RO: ANULAREA grupelor aduse de importul 3 (PRINTERRA).
-- EN: ROLLBACK of the groups brought by import 3 (PRINTERRA).
--     Fisier sursa / source file: Set_data_import/12/PRINTERRA.xlsx (2026-08-18)
--     Data / date: 2026-08-18
--     Randuri: total 5147, create 5147, potrivite 0, sarite 0
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
--  WHERE cod IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- RO: 2) grupele CREATE de acest import (doar cele ramase goale)
-- EN: 2) groups CREATED by this import (only the ones left empty)
-- Accesorii si piese IMPRIMANTE > Aspirator   (acest import: 6 marfuri; acum in total: 6)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Aspirator'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Bucse lfr   (acest import: 22 marfuri; acum in total: 22)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Bucse lfr'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Bucse ufr   (acest import: 14 marfuri; acum in total: 14)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Bucse ufr'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Capuri de imprimare   (acest import: 21 marfuri; acum in total: 21)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Capuri de imprimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Chip   (acest import: 138 marfuri; acum in total: 138)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Chip'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Componente pentru imprimantele matriceale   (acest import: 31 marfuri; acum in total: 31)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Componente pentru imprimantele matriceale'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Cuptor complet   (acest import: 33 marfuri; acum in total: 33)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cuptor complet'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Developer   (acest import: 19 marfuri; acum in total: 19)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Developer'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Filamente pentru imprimanta 3d   (acest import: 391 marfuri; acum in total: 391)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Filamente pentru imprimanta 3d'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Lamele de curatare   (acest import: 47 marfuri; acum in total: 47)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Lamele de curatare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Lamele de dozare   (acest import: 16 marfuri; acum in total: 16)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Lamele de dozare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Magnetic roller   (acest import: 17 marfuri; acum in total: 17)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Magnetic roller'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Mecanica   (acest import: 199 marfuri; acum in total: 199)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Mecanica'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Opc fotoreceptori   (acest import: 98 marfuri; acum in total: 98)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Opc fotoreceptori'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Optiuni pentru copiatoare   (acest import: 43 marfuri; acum in total: 43)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Optiuni pentru copiatoare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Pad de separare   (acest import: 23 marfuri; acum in total: 23)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Pad de separare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Pcr   (acest import: 23 marfuri; acum in total: 23)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Pcr'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Pelicula termica   (acest import: 13 marfuri; acum in total: 13)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Pelicula termica'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Placi de alimentare   (acest import: 15 marfuri; acum in total: 15)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Placi de alimentare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Placi de control   (acest import: 16 marfuri; acum in total: 16)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Placi de control'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Rola de calibrare   (acest import: 3 marfuri; acum in total: 3)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Rola de calibrare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Rola presoare cuptor lfr   (acest import: 41 marfuri; acum in total: 41)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Rola presoare cuptor lfr'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Role de preluare   (acest import: 89 marfuri; acum in total: 89)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Role de preluare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Sacc   (acest import: 75 marfuri; acum in total: 75)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Sacc'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Spray curatare role de imprimante   (acest import: 3 marfuri; acum in total: 3)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Spray curatare role de imprimante'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Statii de alimentare   (acest import: 5 marfuri; acum in total: 5)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Statii de alimentare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Toner   (acest import: 136 marfuri; acum in total: 136)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Toner'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Ufr   (acest import: 32 marfuri; acum in total: 32)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Ufr'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Upper picker finger   (acest import: 6 marfuri; acum in total: 6)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Upper picker finger'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Zip pentru plottere de taiere   (acest import: 93 marfuri; acum in total: 93)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Zip pentru plottere de taiere'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Accesorii si piese IMPRIMANTE > Zip pentru termoprese   (acest import: 14 marfuri; acum in total: 14)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Accesorii si piese IMPRIMANTE')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Zip pentru termoprese'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > BROTHER   (acest import: 124 marfuri; acum in total: 124)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('BROTHER'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > CANON   (acest import: 458 marfuri; acum in total: 458)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('CANON'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > DYMO   (acest import: 9 marfuri; acum in total: 9)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('DYMO'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > EPSON   (acest import: 382 marfuri; acum in total: 382)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('EPSON'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > HP   (acest import: 329 marfuri; acum in total: 329)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('HP'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > KONICA MINOLTA   (acest import: 93 marfuri; acum in total: 93)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('KONICA MINOLTA'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > KYOCERA   (acest import: 170 marfuri; acum in total: 170)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('KYOCERA'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > LEXMARK   (acest import: 14 marfuri; acum in total: 14)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('LEXMARK'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > OKI   (acest import: 18 marfuri; acum in total: 18)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('OKI'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > PANASONIC   (acest import: 17 marfuri; acum in total: 17)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('PANASONIC'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > PANTUM   (acest import: 19 marfuri; acum in total: 19)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('PANTUM'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > RICOH   (acest import: 95 marfuri; acum in total: 95)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('RICOH'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > SAMSUNG   (acest import: 41 marfuri; acum in total: 41)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('SAMSUNG'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > SHARP   (acest import: 38 marfuri; acum in total: 38)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('SHARP'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > TOSHIBA   (acest import: 23 marfuri; acum in total: 23)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('TOSHIBA'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cartuse pentru imprimante > XEROX   (acest import: 57 marfuri; acum in total: 57)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cartuse pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('XEROX'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cerneala pentru imprimante > Cerneala comestibila   (acest import: 5 marfuri; acum in total: 5)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cerneala comestibila'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cerneala pentru imprimante > Cerneala eco-solvent   (acest import: 9 marfuri; acum in total: 9)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cerneala eco-solvent'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cerneala pentru imprimante > Cerneala inkmate   (acest import: 57 marfuri; acum in total: 57)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cerneala inkmate'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cerneala pentru imprimante > Cerneala inktec   (acest import: 39 marfuri; acum in total: 39)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cerneala inktec'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cerneala pentru imprimante > Cerneala ocbestjet/imagine   (acest import: 99 marfuri; acum in total: 99)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cerneala ocbestjet/imagine'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cerneala pentru imprimante > Cerneala originala pentru imprimante   (acest import: 124 marfuri; acum in total: 124)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cerneala originala pentru imprimante'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cerneala pentru imprimante > Cerneala pentru imprimante de format mare   (acest import: 45 marfuri; acum in total: 45)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cerneala pentru imprimante de format mare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cerneala pentru imprimante > Cerneala pentru imprimante dtf/dtg   (acest import: 12 marfuri; acum in total: 12)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cerneala pentru imprimante dtf/dtg'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cerneala pentru imprimante > Cerneala pentru imprimante uv   (acest import: 22 marfuri; acum in total: 22)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cerneala pentru imprimante uv'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Cerneala pentru imprimante > Cerneala pentru sublimare   (acest import: 15 marfuri; acum in total: 15)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Cerneala pentru imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cerneala pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > File protectie pentru documente   (acest import: 4 marfuri; acum in total: 4)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('File protectie pentru documente'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Hartie foto   (acest import: 121 marfuri; acum in total: 121)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Hartie foto'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Hartie foto rulou   (acest import: 77 marfuri; acum in total: 77)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Hartie foto rulou'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Hartie pentru oficiu   (acest import: 5 marfuri; acum in total: 5)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Hartie pentru oficiu'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Hartie втз   (acest import: 3 marfuri; acum in total: 3)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Hartie втз'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Materiale pentru brosatare   (acest import: 26 marfuri; acum in total: 26)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Materiale pentru brosatare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Pelicula pentru dtf   (acest import: 10 marfuri; acum in total: 10)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Pelicula pentru dtf'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Pelicula pentru laminare   (acest import: 16 marfuri; acum in total: 16)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Pelicula pentru laminare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Pelicula pentru uv dtf   (acest import: 3 marfuri; acum in total: 3)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Pelicula pentru uv dtf'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Pudra pentru dtf   (acest import: 3 marfuri; acum in total: 3)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Pudra pentru dtf'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Riboane   (acest import: 1 marfuri; acum in total: 1)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Riboane'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Saci de hartie   (acest import: 6 marfuri; acum in total: 6)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Saci de hartie'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Hirtie si baza pentru imprimare > Software pentru dtf si uv dtf imprimante   (acest import: 3 marfuri; acum in total: 3)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Hirtie si baza pentru imprimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Software pentru dtf si uv dtf imprimante'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Copiatoare   (acest import: 77 marfuri; acum in total: 77)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Copiatoare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Imprimante cu banda   (acest import: 12 marfuri; acum in total: 12)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Imprimante cu banda'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Imprimante de etichete   (acest import: 11 marfuri; acum in total: 11)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Imprimante de etichete'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Imprimante inkjet   (acest import: 35 marfuri; acum in total: 35)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Imprimante inkjet'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Imprimante laser   (acest import: 85 marfuri; acum in total: 85)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Imprimante laser'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Imprimante matriciale   (acest import: 7 marfuri; acum in total: 7)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Imprimante matriciale'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Imprimante pentru textile   (acest import: 4 marfuri; acum in total: 4)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Imprimante pentru textile'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Imprimante portative   (acest import: 7 marfuri; acum in total: 7)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Imprimante portative'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Imprimante si multifunctionale pentru sublimare   (acest import: 13 marfuri; acum in total: 13)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Imprimante si multifunctionale pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Multifunctionale inkjet   (acest import: 160 marfuri; acum in total: 160)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Multifunctionale inkjet'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Multifunctionale laser   (acest import: 141 marfuri; acum in total: 141)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Multifunctionale laser'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > Plottere   (acest import: 27 marfuri; acum in total: 27)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Plottere'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Imprimante > 3d imprimante   (acest import: 33 marfuri; acum in total: 33)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Imprimante')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('3d imprimante'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Bibelouri pentru sublimare   (acest import: 15 marfuri; acum in total: 15)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Bibelouri pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Cani pentru sublimare   (acest import: 73 marfuri; acum in total: 73)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cani pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Cani termice si termosuri   (acest import: 21 marfuri; acum in total: 21)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Cani termice si termosuri'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Ceasuri pentru sublimare   (acest import: 7 marfuri; acum in total: 7)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Ceasuri pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Farfurii pentru sublimare   (acest import: 9 marfuri; acum in total: 9)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Farfurii pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Fata de perna   (acest import: 18 marfuri; acum in total: 18)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Fata de perna'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Fotocristale pentru sublimare   (acest import: 5 marfuri; acum in total: 5)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Fotocristale pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Hartie pentru sublimare   (acest import: 6 marfuri; acum in total: 6)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Hartie pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Mouse si covorase pentru sublimare   (acest import: 10 marfuri; acum in total: 10)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Mouse si covorase pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Pietre foto pentru sublimare   (acest import: 5 marfuri; acum in total: 5)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Pietre foto pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Pix   (acest import: 50 marfuri; acum in total: 50)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Pix'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Plancute, placi din aluminiu   (acest import: 11 marfuri; acum in total: 11)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Plancute, placi din aluminiu'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Puzzle   (acest import: 3 marfuri; acum in total: 3)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Puzzle'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Rame foto pentru sublimare   (acest import: 8 marfuri; acum in total: 8)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Rame foto pentru sublimare'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- Sublimare > Sticele   (acest import: 20 marfuri; acum in total: 20)
-- DELETE FROM biro26_goods WHERE UPPER(TRIM(grupa)) = UPPER(TRIM('Sublimare')) AND UPPER(TRIM(categorie)) = UPPER(TRIM('Sticele'))
--    AND cod_univers IN (SELECT cod FROM tms_mpt_impsrc WHERE src_import_id = 3);

-- RO: 3) nodurile din arborele nativ ramase fara marfa
-- EN: 3) native-tree nodes left with no goods
-- DELETE FROM tms_sysgrph h WHERE h.id0 = 1
--   AND NOT EXISTS (SELECT 1 FROM tms_sysgrp g WHERE g.id0 = 1 AND g.id1 = h.id1)
--   AND UPPER(TRIM(h.coment)) IN (
--     'ACCESORII SI PIESE IMPRIMANTE', 'CARTUSE PENTRU IMPRIMANTE', 'CERNEALA PENTRU IMPRIMANTE', 'HIRTIE SI BAZA PENTRU IMPRIMARE', 'IMPRIMANTE', 'SUBLIMARE');

-- RO: 4) marcajele de sursa si evidenta grupelor
-- DELETE FROM tms_mpt_impsrc      WHERE src_import_id = 3;
-- DELETE FROM ybiro_import_groups WHERE import_id     = 3;
-- UPDATE ybiro_import_log SET notes = notes || ' [ANULAT]' WHERE import_id = 3;
