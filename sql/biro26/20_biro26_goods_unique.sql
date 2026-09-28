-- ============================================================================
-- BIRO26_GOODS: un singur rind per COD_UNIVERS (01.09.2026)
--
-- RO: feed-ul de marfa avea duplicate — 3.632 de coduri cu 2 rinduri (rar 3),
--     ~3.834 de rinduri in plus, toate din vechile importuri Excel (coloana
--     SHEET difera intre copii). Catalogul le ocolea cu
--       ROW_NUMBER() OVER (PARTITION BY COD_UNIVERS ORDER BY ID) = 1
--     adica sorta toata tabela (235k rinduri) la fiecare cerere.
--     Importatorul curent (BIRO26PT_IMPORTDATA) face deja MERGE ... ON
--     (t.cod_univers = u.cod), deci NU mai produce duplicate; indexul unic
--     de mai jos garanteaza ca nu mai apar pe nicio alta cale.
--
--     Rindul pastrat = cel cu ID-ul cel mai mic (NULL la urma) — EXACT rindul
--     pe care il arata site-ul si pina acum, deci nimic vizibil nu se schimba.
--     Copiile sterse se pastreaza in BIRO26_GOODS_DUP_BAK.
--
--     COD_UNIVERS NULL (34.437 de rinduri — staging-ul Ultra) NU intra in
--     index: Oracle nu indexeaza cheile complet NULL, deci indexul unic le
--     permite oricite.
--
--     Rulare: scripts/biro26_goods_dedupe.py --dry-run, apoi --go
--     (scriptul face aceiasi pasi, cu verificari si numaratori).
-- EN: dedupe BIRO26_GOODS by COD_UNIVERS (keep lowest ID = what the shop
--     already showed), back up the removed copies, enforce with a unique
--     index. Run through scripts/biro26_goods_dedupe.py.
-- ============================================================================

-- 1. copiile care pleaca (acelasi criteriu ca in interogarea catalogului)
CREATE TABLE BIRO26_GOODS_DUP_BAK AS
SELECT g.*, SYSDATE BAK_AT
  FROM BIRO26_GOODS g
 WHERE ROWID IN (SELECT rid FROM (
         SELECT ROWID rid,
                ROW_NUMBER() OVER (PARTITION BY COD_UNIVERS ORDER BY ID) rn
           FROM BIRO26_GOODS WHERE COD_UNIVERS IS NOT NULL)
        WHERE rn > 1);

-- 2. stergerea lor
DELETE FROM BIRO26_GOODS
 WHERE ROWID IN (SELECT rid FROM (
         SELECT ROWID rid,
                ROW_NUMBER() OVER (PARTITION BY COD_UNIVERS ORDER BY ID) rn
           FROM BIRO26_GOODS WHERE COD_UNIVERS IS NOT NULL)
        WHERE rn > 1);
COMMIT;

-- 3. indexul unic in locul celui simplu (creat in 19_webattr_text_index.sql)
DROP INDEX IX_BIRO26_GOODS_CODUNIV;
CREATE UNIQUE INDEX UX_BIRO26_GOODS_CODUNIV ON BIRO26_GOODS (COD_UNIVERS);

-- 4. verificare: trebuie 0
SELECT COUNT(*) FROM (SELECT COD_UNIVERS FROM BIRO26_GOODS
                       WHERE COD_UNIVERS IS NOT NULL
                       GROUP BY COD_UNIVERS HAVING COUNT(*) > 1);
