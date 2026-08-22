-- =====================================================================
-- RO: Prelungirea scutirii de TVA pentru clientul 471738 (IURILEN-FLOR SRL).
--     Inregistrarea de 0% acoperea doar doua zile (20-21.08.2026), dupa care
--     se revenea la cota standard 'A'. Intentia fiind "0% de la 20.08.2026
--     inainte", perioada urmatoare primeste si ea cota '0'.
-- EN: Extend the 0% VAT period for client 471738; it covered only two days.
--
-- RO: DE CE prin UPDATE si NU prin DELETE — triggerul TMH_UNIVERS_TRG interzice
--     stergerile ("Удаления из истории изменений запрещены!"): istoricul e un
--     jurnal, se corecteaza, nu se rescrie. Asa ramin vizibile si fereastra
--     initiala de doua zile, si corectia (prin UPDATE_DATE, pus de trigger).
-- EN: WHY an UPDATE and not a DELETE — the trigger forbids deletes; the history
--     is a journal. Both the original two-day window and the fix stay visible.
--
-- RO: Starea INAINTE / EN: state BEFORE
--     ID 827018  'A'  01.01.1900 - 19.08.2026
--     ID 834479  '0'  20.08.2026 - 21.08.2026
--     ID 834478  'A'  22.08.2026 - 01.01.3000   <- devine '0'
--
-- RO: Starea DUPA / EN: state AFTER
--     ID 827018  'A'  01.01.1900 - 19.08.2026
--     ID 834479  '0'  20.08.2026 - 21.08.2026
--     ID 834478  '0'  22.08.2026 - 01.01.3000
--     => cota 0% neintrerupta de la 20.08.2026 inainte, in acord cu cartela
--        (TMS_UNIVERS.CODTVA = '0').
-- =====================================================================

UPDATE tmh_univers
   SET codtva = '0'
 WHERE cod        = 471738
   AND id         = 834478
   AND codtva     = 'A'
   AND start_date = TO_DATE('22.08.2026', 'DD.MM.YYYY');

COMMIT;

-- RO: verificare / EN: check
SELECT id, codtva,
       TO_CHAR(start_date, 'DD.MM.YYYY') de_la,
       TO_CHAR(end_date,   'DD.MM.YYYY') pina_la
  FROM tmh_univers
 WHERE cod = 471738
 ORDER BY start_date;
