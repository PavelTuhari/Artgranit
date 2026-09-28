-- =====================================================================
-- RO: Indecsi FUNCTIONALI pentru pazele din BIRO26PT_importData.classify().
--     Fara ei, fiecare rand al fisierului scaneaza integral TMS_UNIVERS
--     (~460 000 de randuri): un fisier de 8 655 de randuri rula 25+ minute
--     fara sa se termine. Cu ei — sub un minut.
-- EN: FUNCTION-BASED indexes for the classify() guards. Without them every
--     file row full-scans TMS_UNIVERS; an 8 655-row file ran 25+ minutes.
--
-- RO: Regula generala: daca o paza compara o EXPRESIE (nu coloana bruta),
--     are nevoie de un index pe exact acea expresie. Altfel functioneaza la
--     fisiere mici si devine inutilizabila exact cind ai nevoie de ea.
-- EN: If a guard compares an EXPRESSION, it needs an index on that exact
--     expression — otherwise it only works on small files.
-- =====================================================================
SET SQLBLANKLINES ON

-- RO: paza 4 — numele exista deja pe o cartela activa? / EN: guard 4 — name already used?
CREATE INDEX TMS_UNIVERS_UP_DENUMIREA
    ON TMS_UNIVERS (UPPER(TRIM(DENUMIREA)));

-- RO: prioritatea 3 — articol normalizat (fara spatii/puncte)
-- EN: priority 3 — normalized article (spaces/dots removed)
CREATE INDEX TMS_UNIVERS_NORM_CODVECHI
    ON TMS_UNIVERS (REPLACE(REPLACE(UPPER(CODVECHI), ' ', ''), '.', ''));
