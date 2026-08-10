-- =====================================================================
-- RO: Corectie dictionar de coloane — ANGRO este pretul de achizitie CU TVA.
--     Inainte, antetul "Цена закупки с НДС" era mapat pe IGNORE, deci la
--     fisierele care au DOAR coloana cu TVA (ex. CRAFTI, set 10) pretul de
--     achizitie nu se importa deloc — tacut, fara nicio eroare.
--     Varianta "fara TVA" ramine, dar retrogradata: daca fisierul are ambele
--     coloane cistiga cea CU TVA; daca are doar varianta fara TVA, se importa
--     ea, ca sa nu ramina cimpul gol.
-- EN: Column-dictionary fix — ANGRO is the purchase price INCLUDING VAT.
--     The "with VAT" header used to map to IGNORE, so files carrying ONLY that
--     column silently imported no purchase price at all. The "without VAT"
--     pattern is kept as a lower-priority fallback.
--
-- RO: In detect_columns cistiga prioritatea MINIMA / EN: lowest prio wins.
-- =====================================================================

UPDATE BIRO26PT_COLMAP SET logical_field = 'ANGRO', prio = 5
 WHERE pattern = '%цена закупки с ндс%';

UPDATE BIRO26PT_COLMAP SET logical_field = 'ANGRO', prio = 6
 WHERE pattern = '%закупки с ндс%';

UPDATE BIRO26PT_COLMAP SET prio = 30
 WHERE pattern IN ('%цена закупки без%', '%закупки без ндс%');

COMMIT;

-- RO: verificare / EN: check
SELECT pattern, logical_field, prio
  FROM BIRO26PT_COLMAP
 WHERE logical_field = 'ANGRO'
 ORDER BY prio;
