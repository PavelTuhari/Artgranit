-- =====================================================================
-- RO: Evidenta COMENZILOR pe conturi EXTRABILANTIERE (grupa 9***).
--
--     Sens PASIV pentru comenzi: la emiterea contului de plata comanda se
--     inregistreaza pe CREDITUL contului 9301, deci in raportul universal
--     orice comanda se vede ca cifra POZITIVA in coloana Ct.
--     La livrare (FF 1228) aceeasi suma se trece pe DEBIT — comanda se
--     inchide, soldul contului ramine doar pe comenzile nelivrate.
--
--     Sens ACTIV pentru stocurile furnizorilor: contul 9302 primeste pe
--     DEBIT stocul pus la dispozitie de furnizor, cu analitica pe depozitul
--     lui — in raportul universal se vede imediat cifra pozitiva in Dt.
--
-- EN: off-balance order accounting. Orders are PASSIVE (Ct on 9301, closed
--     by Dt on delivery); supplier stock is ACTIVE (Dt on 9302, analytics
--     per supplier warehouse).
--
-- Legatura comanda <-> livrare: VMDB_ST201M.CTNRDOC al contului tine NRDOC-ul
-- documentului 1228 creat din el (vezi yimc_inventar.create_doc_1228_form_12280).
--
-- Formulele se scriu in VMDB_CMI cu O SINGURA parte — asa se lucreaza cu
-- conturile extrabilantiere (model: Yimc_Tvr_Docs.doc_tvr_return_order_gfc).
-- Charset DB: CL8MSWIN1251 — a se aplica prin python-oracledb.
-- =====================================================================

CREATE OR REPLACE PACKAGE y_ai_BIRO26_comenzi AS

  -- RO: conturile implicite; se pot suprascrie din configuratie (ORDER_CONT)
  c_cont_comenzi CONSTANT INT := 9301;  -- comenzi clienti (pasiv)
  c_cont_stoc_f  CONSTANT INT := 9302;  -- stocuri furnizori (activ)

  -- RO: contul de plata -> comanda pe CREDIT (pasiv)
  PROCEDURE order_gfc(p_nrdoc INT, p_cont INT DEFAULT c_cont_comenzi);

  -- RO: livrarea (FF 1228) -> inchiderea comenzii pe DEBIT (activ)
  PROCEDURE order_close(p_nrdoc INT, p_cont INT DEFAULT c_cont_comenzi);

  -- RO: soldul comenzii — cit a ramas nelivrat (Ct - Dt)
  FUNCTION order_sold(p_nrdoc INT, p_cont INT DEFAULT c_cont_comenzi) RETURN NUMBER;

END y_ai_BIRO26_comenzi;
/

CREATE OR REPLACE PACKAGE BODY y_ai_BIRO26_comenzi AS

  -- RO: NRDOC-ul contului de plata din care s-a creat livrarea p_nrdoc.
  FUNCTION order_of_delivery(p_nrdoc INT) RETURN INT IS
    v INT;
  BEGIN
    SELECT MIN(nrdoc) INTO v FROM VMDB_ST201M WHERE ctnrdoc = p_nrdoc;
    RETURN v;
  END order_of_delivery;

  PROCEDURE order_gfc(p_nrdoc INT, p_cont INT DEFAULT c_cont_comenzi) IS
    v_n INT;
  BEGIN
    -- RO: regenerare curata — stergem doar formulele NOASTRE de pe contul dat,
    --     ca sa nu atingem restul formulelor documentului.
    DELETE FROM VMDB_CMI WHERE nrdoc = p_nrdoc AND ct = p_cont;

    -- RO: comanda pe CREDIT: analitica = marfa (ctsc), subdiviziunea (ctdep),
    --     clientul (ctsc1) si numarul comenzii (ctnrdoc).
    INSERT INTO VMDB_CMI(nrdoc, ct, ctsc, ctdep, ctsc1, ctnrdoc, cant, suma)
    SELECT p_nrdoc, p_cont, d.ctsc, m.ctdep, m.dtdep, p_nrdoc,
           NVL(d.cant, 0), NVL(d.suma, 0)
      FROM VMDB_ST201D d, VMDB_ST201M m
     WHERE d.nrdoc = p_nrdoc AND m.nrdoc = p_nrdoc
       AND NVL(d.cant, 0) <> 0;
    v_n := SQL%ROWCOUNT;

    IF v_n = 0 THEN
      msg('Comanda ('||p_nrdoc||') nu are rinduri — nu s-a generat nicio formula.');
    END IF;
  END order_gfc;

  PROCEDURE order_close(p_nrdoc INT, p_cont INT DEFAULT c_cont_comenzi) IS
    v_order INT := order_of_delivery(p_nrdoc);
    v_n     INT;
  BEGIN
    IF v_order IS NULL THEN
      msg('Livrarea ('||p_nrdoc||') nu este legata de un cont de plata — '
          ||'nu se stie ce comanda sa fie inchisa.');
      RETURN;
    END IF;

    DELETE FROM VMDB_CMI WHERE nrdoc = p_nrdoc AND dt = p_cont;

    -- RO: inchiderea pe DEBIT, cu ACEEASI analitica ca la inregistrare, ca
    --     soldul pe comanda sa se stinga exact. Numarul comenzii ramine in
    --     dtnrdoc — asa se vede in raport care comanda s-a inchis.
    INSERT INTO VMDB_CMI(nrdoc, dt, dtsc, dtdep, dtsc1, dtnrdoc, cant, suma)
    SELECT p_nrdoc, p_cont, d.ctsc, m.ctdep, m.dtdep, v_order,
           NVL(d.cant, 0), NVL(d.suma, 0)
      FROM VMDB_ST201D d, VMDB_ST201M m
     WHERE d.nrdoc = p_nrdoc AND m.nrdoc = p_nrdoc
       AND NVL(d.cant, 0) <> 0;
    v_n := SQL%ROWCOUNT;

    IF v_n = 0 THEN
      msg('Livrarea ('||p_nrdoc||') nu are rinduri — comanda '||v_order
          ||' ramine deschisa.');
    END IF;
  END order_close;

  FUNCTION order_sold(p_nrdoc INT, p_cont INT DEFAULT c_cont_comenzi) RETURN NUMBER IS
    v NUMBER;
  BEGIN
    -- RO: cit a ramas nelivrat din comanda: creditul comenzii minus debitul
    --     livrarilor care o inchid (legate prin dtnrdoc).
    SELECT NVL(SUM(CASE WHEN ct = p_cont AND ctnrdoc = p_nrdoc THEN NVL(suma,0) ELSE 0 END), 0)
         - NVL(SUM(CASE WHEN dt = p_cont AND dtnrdoc = p_nrdoc THEN NVL(suma,0) ELSE 0 END), 0)
      INTO v
      FROM VMDB_CMI
     WHERE (ct = p_cont AND ctnrdoc = p_nrdoc)
        OR (dt = p_cont AND dtnrdoc = p_nrdoc);
    RETURN NVL(v, 0);
  END order_sold;

END y_ai_BIRO26_comenzi;
/
