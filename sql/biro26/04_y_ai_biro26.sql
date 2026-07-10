-- =====================================================================
-- Biro26 web-shop: self-registered clients + "cont de plata" documents.
-- RO: Clienti auto-inregistrati (pagina publica Marfa/Stoc) si generarea
--     documentelor "cont de plata" vizibile in VMDB_DOCS_WORK /
--     VMDB_ST201M / VMDB_ST201D (ecranul nativ ST201, SYSFID 12280).
-- EN: Self-registered clients (public Marfa/Stoc page) and generation of
--     "invoice for payment" documents visible through VMDB_DOCS_WORK /
--     VMDB_ST201M / VMDB_ST201D (native ST201 screen, SYSFID 12280).
-- RO/EN comments only (project rule). Target: officeplus (Oracle 11g).
-- Reference document: COD=140 (DT=2214, CT=2171, CTDEP=1, VALUTA=LEI).
-- Run: ./venv/bin/python deploy_biro26_shop.py
-- =====================================================================

CREATE TABLE YBIRO_CLIENT (
  id           NUMBER PRIMARY KEY,          -- via secventa+trigger (11g)
  univers_cod  NUMBER NOT NULL,             -- RO: clientul in TMS_UNIVERS (TIP='O') / EN: client org in TMS_UNIVERS
  email        VARCHAR2(120) NOT NULL,      -- RO: login / EN: login
  full_name    VARCHAR2(160) NOT NULL,
  phone        VARCHAR2(40),
  pwd_hash     VARCHAR2(200) NOT NULL,      -- RO: pbkdf2 din aplicatie / EN: pbkdf2 from the app
  created_at   TIMESTAMP DEFAULT SYSTIMESTAMP,
  CONSTRAINT uq_ybiro_client_email UNIQUE (email)
);

CREATE SEQUENCE YBIRO_CLIENT_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE OR REPLACE TRIGGER YBIRO_CLIENT_BI
  BEFORE INSERT ON YBIRO_CLIENT FOR EACH ROW WHEN (NEW.id IS NULL)
BEGIN
  SELECT YBIRO_CLIENT_SEQ.NEXTVAL INTO :NEW.id FROM dual;
END;
/

-- RO: Setarile modulului (normalizate, prefix YBIRO_): ex. grupa de
--     servicii afisata optional in cosul magazinului public.
-- EN: Module settings (normalized, YBIRO_ prefix): e.g. the services
--     group offered optionally in the public shop cart.
CREATE TABLE YBIRO_SETTINGS (
  skey       VARCHAR2(60) PRIMARY KEY,
  sval       VARCHAR2(400),
  descr      VARCHAR2(200),
  updated_at TIMESTAMP DEFAULT SYSTIMESTAMP
);

-- RO: Diapazoanele de km pentru serviciile de transport tur-retur din cos.
--     Fiecare rand leaga un tarif (pozitie TMS_UNIVERS) de un interval de
--     distanta; TARIF_MODE: 'TUR' = pret fix pe cursa, 'KM' = pret/km
--     (cantitatea liniei din cont = km). Alegerea tarifului in cos este
--     OBLIGATORIE si automata dupa distanta comenzii.
-- EN: Km ranges for the round-trip transport services in the cart. Each
--     row links a tariff (TMS_UNIVERS item) to a distance interval;
--     TARIF_MODE: 'TUR' = flat per trip, 'KM' = price per km (invoice
--     line qty = km). The cart picks the tariff automatically and
--     mandatorily from the order distance.
CREATE TABLE TMS_MPT_DISTANTE (
  cod        NUMBER NOT NULL,      -- TMS_UNIVERS.COD al tarifului / tariff item
  km_min     NUMBER NOT NULL,
  km_max     NUMBER,               -- NULL = nelimitat / unlimited
  tarif_mode VARCHAR2(3) NOT NULL, -- 'TUR' | 'KM'
  CONSTRAINT pk_tms_mpt_distante PRIMARY KEY (cod),
  CONSTRAINT ck_tms_mpt_dist_mode CHECK (tarif_mode IN ('TUR','KM'))
);

-- RO: Centrele logistice — transportul tur-retur se calculeaza DE LA
--     centrul logistic (momentan activ doar mun. Balti; Cahul, Comrat si
--     Chisinau sunt pregatite dar inactive). Nume ASCII: charset-ul bazei
--     este CL8MSWIN1251 si nu contine diacritice romanesti.
-- EN: Logistics centers — the round-trip transport is measured FROM the
--     logistics center (currently only mun. Balti is active; Cahul,
--     Comrat and Chisinau are seeded inactive). ASCII names: the DB
--     charset is CL8MSWIN1251 (no Romanian diacritics).
CREATE TABLE TMS_MPT_CENTRE_LOG (
  id       NUMBER PRIMARY KEY,
  denumire VARCHAR2(100) NOT NULL,
  activ    CHAR(1) DEFAULT '1' NOT NULL,   -- '1' activ / '0' inactiv
  nrord    NUMBER DEFAULT 0,
  CONSTRAINT uq_tms_mpt_centre UNIQUE (denumire),
  CONSTRAINT ck_tms_mpt_centre_act CHECK (activ IN ('0','1'))
);
-- seed: INSERT (1,'mun. Balti','1',1), (2,'Cahul','0',2),
--              (3,'Comrat','0',3), (4,'Chisinau','0',4)

-- =====================================================================
-- Package y_ai_BIRO26
-- =====================================================================
CREATE OR REPLACE PACKAGE y_ai_BIRO26 AS
  -- RO: Parametri configurabili (valorile implicite copiate din documentul
  --     de referinta COD=140). / EN: Configurable parameters (defaults
  --     copied from the reference document COD=140).
  g_sysfid   NUMBER       := 12280;  -- RO: formularul "cont de plata" / EN: invoice form id
  g_tip      VARCHAR2(1)  := 'H';
  g_dt       NUMBER       := 2214;   -- RO: cont debit (client) / EN: debit account (client)
  g_ct       NUMBER       := 2171;   -- RO: cont credit (vanzari) / EN: credit account (sales)
  g_ctdep    NUMBER       := 1;      -- RO: subdiviziune credit (Magazin 1) / EN: credit dep
  g_valuta   VARCHAR2(6)  := 'LEI';
  -- RO: AT2=2 => trigger-ul TRIG_BFALL_TMDB_DOCS nu verifica perioada de
  --     lucru si documentul ramane mereu vizibil in VMDB_DOCS_WORK.
  -- EN: AT2=2 => TRIG_BFALL_TMDB_DOCS skips the working-period check and
  --     the document stays permanently visible in VMDB_DOCS_WORK.
  g_at2      NUMBER       := 2;
  g_doccolor VARCHAR2(1)  := '`';
  g_client_tip VARCHAR2(1):= 'O';    -- RO: client = organizatie / EN: client = organisation
  g_client_gr1 VARCHAR2(5):= 'E';    -- RO: grupa clientilor / EN: clients group
  g_caccess  VARCHAR2(5)  := '11100';
  g_codprice NUMBER       := 1;      -- RO: lista de preturi implicita (BIRO) / EN: default price list

  -- RO: Inregistreaza un client nou in TMS_UNIVERS (TIP='O'); intoarce COD.
  -- EN: Register a new client in TMS_UNIVERS (TIP='O'); returns COD.
  FUNCTION register_client(p_name IN VARCHAR2) RETURN NUMBER;

  -- RO: Creeaza antetul documentului "cont de plata" (TMDB_DOCS +
  --     VMDB_ST201M + XNRDOC pentru vizibilitate imediata); intoarce COD.
  -- EN: Create the invoice header (TMDB_DOCS + VMDB_ST201M + XNRDOC for
  --     immediate visibility); returns the document COD.
  FUNCTION create_invoice(p_client_cod IN NUMBER,
                          p_data       IN DATE DEFAULT TRUNC(SYSDATE))
    RETURN NUMBER;

  -- RO: Adauga o linie in document (prin VMDB_ST201D, deci prin logica
  --     nativa INSTEAD OF). / EN: Add a document line (through VMDB_ST201D,
  --     hence through the native INSTEAD OF logic).
  PROCEDURE add_line(p_nrdoc  IN NUMBER,
                     p_sc     IN NUMBER,
                     p_cant   IN NUMBER,
                     p_pret   IN NUMBER,
                     p_coment IN VARCHAR2 DEFAULT NULL);

  -- RO: Numarul de ordine (NRSET) al documentului. / EN: document NRSET.
  FUNCTION get_nrset(p_nrdoc IN NUMBER) RETURN NUMBER;

  -- RO: COD-ul ultimului document creat in ACEASTA sesiune (stare pachet).
  -- EN: COD of the last document created in THIS session (package state).
  FUNCTION last_doc RETURN NUMBER;

  -- ===================================================================
  -- Preturi pe perioade (TPR1D_PERPRLIST prin vederea VTPR1D_PERPRLIST)
  -- Price periods (TPR1D_PERPRLIST through the VTPR1D_PERPRLIST view)
  -- ===================================================================

  -- RO: Seteaza pretul valabil de la p_data. Daca exista deja o perioada
  --     care incepe exact la p_data, se actualizeaza; altfel perioada
  --     curenta se DIVIZEAZA (trigger-ul nativ inchide perioada veche la
  --     p_data-1 si insereaza una noua). Parametrii de pret NULL pastreaza
  --     valoarea perioadei in vigoare la p_data.
  -- EN: Set the price effective from p_data. If a period starting exactly
  --     at p_data exists it is updated in place; otherwise the current
  --     period is SPLIT (the native INSTEAD OF trigger closes the old
  --     period at p_data-1 and inserts the new one). NULL price parameters
  --     keep the value of the period effective at p_data.
  PROCEDURE set_price(p_sc       IN NUMBER,
                      p_data     IN DATE   DEFAULT TRUNC(SYSDATE),
                      p_pretv    IN NUMBER DEFAULT NULL,   -- retail
                      p_pretv1   IN NUMBER DEFAULT NULL,   -- angro
                      p_pretv2   IN NUMBER DEFAULT NULL,   -- online
                      p_codprice IN NUMBER DEFAULT NULL,
                      p_codgrp   IN NUMBER DEFAULT NULL);

  -- RO: Sterge perioada care incepe la p_data; perioadele se UNESC
  --     (perioada precedenta se extinde pana la sfarsitul celei sterse;
  --     daca se sterge prima perioada, urmatoarea se extinde inapoi) ca
  --     diapazonul de date sa ramana fara goluri. Ultimul rand ramas NU
  --     poate fi sters (ORA-20261). Rand inexistent -> ORA-20262.
  -- EN: Delete the period starting at p_data; periods are MERGED (the
  --     previous period extends to the deleted one's end; deleting the
  --     first period extends the next one backwards) so the date range
  --     stays gap-free. The LAST remaining row cannot be deleted
  --     (ORA-20261). Missing row -> ORA-20262.
  PROCEDURE del_price(p_sc       IN NUMBER,
                      p_data     IN DATE,
                      p_codprice IN NUMBER DEFAULT NULL);

  -- RO: Pretul in vigoare la p_data (p_which: 'V' retail, '1' angro,
  --     '2' online). / EN: the price effective at p_data.
  FUNCTION price_on(p_sc       IN NUMBER,
                    p_data     IN DATE     DEFAULT TRUNC(SYSDATE),
                    p_which    IN VARCHAR2 DEFAULT 'V',
                    p_codprice IN NUMBER   DEFAULT NULL) RETURN NUMBER;

  -- ===================================================================
  -- Nomenclator: functie UNIVERSALA de creare pozitii + noduri de arbore
  -- Universal product/tree creation
  -- ===================================================================

  -- RO: Creeaza o pozitie noua de nomenclator si, implicit, nodul/subnodul
  --     de arbore: arborele Marfa/Stoc este derivat din valorile distincte
  --     GRUPA -> CATEGORIE din BIRO26_GOODS, deci o GRUPA/CATEGORIE noua
  --     apare in arbore imediat ce prima pozitie o foloseste. Face, in
  --     ordine: TMS_UNIVERS (TIP='P'), BIRO26_GOODS (grupa/categorie/
  --     preturi-feed) si perioada de pret in lista (set_price -> toate
  --     trei coloanele PRETV/PRETV1/PRETV2). Intoarce COD-ul nou.
  -- EN: Create a new nomenclature item and, implicitly, the tree
  --     node/subnode: the Marfa/Stoc tree is derived from the distinct
  --     GRUPA -> CATEGORIE values of BIRO26_GOODS, so a new GRUPA or
  --     CATEGORIE appears in the tree as soon as its first item uses it.
  --     Inserts TMS_UNIVERS (TIP='P'), BIRO26_GOODS and the price-list
  --     period (set_price -> PRETV/PRETV1/PRETV2). Returns the new COD.
  FUNCTION add_product(p_denumirea IN VARCHAR2,
                       p_grupa     IN VARCHAR2,
                       p_categorie IN VARCHAR2 DEFAULT NULL,
                       p_retail    IN NUMBER   DEFAULT NULL,
                       p_angro     IN NUMBER   DEFAULT NULL,
                       p_online    IN NUMBER   DEFAULT NULL,
                       p_um        IN VARCHAR2 DEFAULT 'buc.',
                       p_brand     IN VARCHAR2 DEFAULT NULL,
                       p_data      IN DATE     DEFAULT TRUNC(SYSDATE))
    RETURN NUMBER;

  -- RO: Setarile modulului (YBIRO_SETTINGS) — upsert / citire.
  -- EN: Module settings (YBIRO_SETTINGS) — upsert / read.
  PROCEDURE set_setting(p_key IN VARCHAR2, p_val IN VARCHAR2,
                        p_descr IN VARCHAR2 DEFAULT NULL);
  FUNCTION get_setting(p_key IN VARCHAR2) RETURN VARCHAR2;
END y_ai_BIRO26;
/

CREATE OR REPLACE PACKAGE BODY y_ai_BIRO26 AS

  g_last_cod NUMBER;  -- RO: ultimul COD creat / EN: last created COD

  FUNCTION register_client(p_name IN VARCHAR2) RETURN NUMBER IS
    v_cod NUMBER;
  BEGIN
    SELECT ID_TMS_UNIVERS.NEXTVAL INTO v_cod FROM dual;
    INSERT INTO TMS_UNIVERS (COD, DENUMIREA, TIP, GR1, CACCESS)
    VALUES (v_cod, SUBSTR(p_name, 1, 160), g_client_tip, g_client_gr1, g_caccess);
    RETURN v_cod;
  END register_client;

  FUNCTION create_invoice(p_client_cod IN NUMBER,
                          p_data       IN DATE DEFAULT TRUNC(SYSDATE))
    RETURN NUMBER IS
    v_cod   NUMBER;
    v_nrset NUMBER;
  BEGIN
    SELECT ID_TMDB_DOCS.NEXTVAL INTO v_cod FROM dual;
    -- RO: numerotare per formular (suficient la volumul curent)
    -- EN: per-form numbering (adequate at current volume)
    SELECT NVL(MAX(NRSET), 0) + 1 INTO v_nrset
      FROM TMDB_DOCS WHERE SYSFID = g_sysfid;

    INSERT INTO TMDB_DOCS (COD, TIP, SYSFID, USERID, DATAMANUAL, VALUTA,
                           NRSET, ISGFC, DOCCOLOR, CODF, AT2, AT3)
    VALUES (v_cod, g_tip, g_sysfid, UID, p_data, g_valuta,
            v_nrset, 0, g_doccolor, 0, g_at2, 0);

    -- RO: antetul contabil, prin vederea nativa / EN: posting header via the native view
    INSERT INTO VMDB_ST201M (NRDOC, DT, CT, DTDEP, CTDEP,
                             VALUTADT, VALUTACT, CTDATA)
    VALUES (v_cod, g_dt, g_ct, p_client_cod, g_ctdep,
            g_valuta, g_valuta, p_data);

    -- RO: vizibil imediat in VMDB_DOCS_WORK / EN: immediately visible in VMDB_DOCS_WORK
    INSERT INTO XNRDOC (COD)
    SELECT v_cod FROM dual
     WHERE NOT EXISTS (SELECT 1 FROM XNRDOC WHERE COD = v_cod);

    g_last_cod := v_cod;
    RETURN v_cod;
  END create_invoice;

  PROCEDURE add_line(p_nrdoc  IN NUMBER,
                     p_sc     IN NUMBER,
                     p_cant   IN NUMBER,
                     p_pret   IN NUMBER,
                     p_coment IN VARCHAR2 DEFAULT NULL) IS
  BEGIN
    INSERT INTO VMDB_ST201D (NRDOC, DT, CT, CTSC, CANT, SUMA, TXTCOMENT)
    VALUES (p_nrdoc, g_dt, g_ct, p_sc, p_cant,
            ROUND(NVL(p_cant, 0) * NVL(p_pret, 0), 2),
            SUBSTR(p_coment, 1, 200));
  END add_line;

  FUNCTION get_nrset(p_nrdoc IN NUMBER) RETURN NUMBER IS
    v NUMBER;
  BEGIN
    SELECT NRSET INTO v FROM TMDB_DOCS WHERE COD = p_nrdoc;
    RETURN v;
  END get_nrset;

  FUNCTION last_doc RETURN NUMBER IS
  BEGIN
    RETURN g_last_cod;
  END last_doc;

  -- ===================================================================
  -- Preturi pe perioade / price periods
  -- ===================================================================

  -- RO: Grupa articolului in lista de preturi (1 daca articolul e nou).
  -- EN: The item's group inside the price list (1 for brand-new items).
  FUNCTION price_group(p_sc IN NUMBER, p_codprice IN NUMBER) RETURN NUMBER IS
    v_grp NUMBER;
  BEGIN
    SELECT CODGRP INTO v_grp
      FROM (SELECT CODGRP FROM TPR1D_PERPRLIST
             WHERE CODPRICE = p_codprice AND SC = p_sc
             ORDER BY DATASTART DESC)
     WHERE ROWNUM = 1;
    RETURN v_grp;
  EXCEPTION WHEN NO_DATA_FOUND THEN
    RETURN 1;
  END price_group;

  PROCEDURE set_price(p_sc       IN NUMBER,
                      p_data     IN DATE   DEFAULT TRUNC(SYSDATE),
                      p_pretv    IN NUMBER DEFAULT NULL,
                      p_pretv1   IN NUMBER DEFAULT NULL,
                      p_pretv2   IN NUMBER DEFAULT NULL,
                      p_codprice IN NUMBER DEFAULT NULL,
                      p_codgrp   IN NUMBER DEFAULT NULL) IS
    v_cp   NUMBER := NVL(p_codprice, g_codprice);
    v_grp  NUMBER := NVL(p_codgrp, price_group(p_sc, NVL(p_codprice, g_codprice)));
    v_d    DATE   := TRUNC(p_data);
    v_cnt  NUMBER;
    v_pv   NUMBER; v_p1 NUMBER; v_p2 NUMBER; v_p3 NUMBER;
  BEGIN
    -- RO: trigger-ul nativ de INSERT foloseste literalul '31.12.3000';
    --     fixam formatul de sesiune ca sa nu pice sub alt NLS.
    -- EN: the native INSERT trigger uses the '31.12.3000' literal; pin the
    --     session date format so it parses under any client NLS.
    EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''DD.MM.YYYY''';

    SELECT COUNT(*) INTO v_cnt FROM TPR1D_PERPRLIST
     WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATASTART = v_d;

    IF v_cnt > 0 THEN
      -- RO: perioada incepe exact la p_data -> doar actualizare
      -- EN: a period starts exactly at p_data -> plain update
      UPDATE VTPR1D_PERPRLIST
         SET PRETV  = NVL(p_pretv,  PRETV),
             PRETV1 = NVL(p_pretv1, PRETV1),
             PRETV2 = NVL(p_pretv2, PRETV2)
       WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATASTART = v_d;
    ELSE
      -- RO: valorile nespecificate se preiau din perioada in vigoare
      -- EN: unspecified values are carried from the effective period
      BEGIN
        SELECT PRETV, PRETV1, PRETV2, PRETV3 INTO v_pv, v_p1, v_p2, v_p3
          FROM TPR1D_PERPRLIST
         WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc
           AND v_d BETWEEN DATASTART AND DATAEND;
      EXCEPTION WHEN NO_DATA_FOUND THEN
        v_pv := NULL; v_p1 := NULL; v_p2 := NULL; v_p3 := NULL;
      END;
      -- RO: INSERT prin vedere -> trigger-ul nativ DIVIDE perioada
      -- EN: INSERT through the view -> the native trigger SPLITS the period
      INSERT INTO VTPR1D_PERPRLIST
        (CODPRICE, CODGRP, SC, DATASTART, PRETV, PRETV1, PRETV2, PRETV3)
      VALUES
        (v_cp, v_grp, p_sc, v_d,
         NVL(p_pretv, v_pv), NVL(p_pretv1, v_p1), NVL(p_pretv2, v_p2), v_p3);
    END IF;
  END set_price;

  PROCEDURE del_price(p_sc       IN NUMBER,
                      p_data     IN DATE,
                      p_codprice IN NUMBER DEFAULT NULL) IS
    v_cp   NUMBER := NVL(p_codprice, g_codprice);
    v_d    DATE   := TRUNC(p_data);
    v_grp  NUMBER;
    v_de   DATE;
    v_cnt  NUMBER;
    v_prev NUMBER;
  BEGIN
    BEGIN
      SELECT CODGRP, DATAEND INTO v_grp, v_de FROM TPR1D_PERPRLIST
       WHERE CODPRICE = v_cp AND SC = p_sc AND DATASTART = v_d;
    EXCEPTION WHEN NO_DATA_FOUND THEN
      RAISE_APPLICATION_ERROR(-20262,
        'Perioada de pret inexistenta / price period not found');
    END;

    SELECT COUNT(*) INTO v_cnt FROM TPR1D_PERPRLIST
     WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc;
    IF v_cnt <= 1 THEN
      -- RO: regula: ultimul rand ramas nu se sterge
      -- EN: rule: the last remaining row cannot be deleted
      RAISE_APPLICATION_ERROR(-20261,
        'Ultimul rand de pret nu poate fi sters / the last price row cannot be deleted');
    END IF;

    SELECT COUNT(*) INTO v_prev FROM TPR1D_PERPRLIST
     WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATAEND = v_d - 1;

    IF v_prev > 0 THEN
      -- RO: stergere prin vedere -> trigger-ul nativ UNESTE perioadele
      --     (perioada precedenta se extinde pana la DATAEND-ul sters)
      -- EN: delete through the view -> the native trigger MERGES periods
      --     (the previous period extends to the deleted DATAEND)
      DELETE FROM VTPR1D_PERPRLIST
       WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATASTART = v_d;
    ELSE
      -- RO: prima perioada: urmatoarea se extinde INAPOI la DATASTART-ul
      --     sters (stergere directa + update pe tabela de baza, ca sa nu
      --     ramana gol la inceputul diapazonului)
      -- EN: first period: the next one extends BACKWARDS to the deleted
      --     DATASTART (direct base-table delete + update so the start of
      --     the range stays covered)
      DELETE FROM TPR1D_PERPRLIST
       WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATASTART = v_d;
      UPDATE TPR1D_PERPRLIST SET DATASTART = v_d
       WHERE CODPRICE = v_cp AND CODGRP = v_grp AND SC = p_sc AND DATASTART = v_de + 1;
    END IF;
  END del_price;

  FUNCTION price_on(p_sc       IN NUMBER,
                    p_data     IN DATE     DEFAULT TRUNC(SYSDATE),
                    p_which    IN VARCHAR2 DEFAULT 'V',
                    p_codprice IN NUMBER   DEFAULT NULL) RETURN NUMBER IS
    v_cp NUMBER := NVL(p_codprice, g_codprice);
    v    NUMBER;
  BEGIN
    SELECT DECODE(p_which, '1', PRETV1, '2', PRETV2, PRETV) INTO v
      FROM TPR1D_PERPRLIST
     WHERE CODPRICE = v_cp AND SC = p_sc
       AND TRUNC(p_data) BETWEEN DATASTART AND DATAEND
       AND ROWNUM = 1;
    RETURN v;
  EXCEPTION WHEN NO_DATA_FOUND THEN
    RETURN NULL;
  END price_on;

  -- ===================================================================
  -- Nomenclator universal / universal product+tree creation
  -- ===================================================================

  FUNCTION add_product(p_denumirea IN VARCHAR2,
                       p_grupa     IN VARCHAR2,
                       p_categorie IN VARCHAR2 DEFAULT NULL,
                       p_retail    IN NUMBER   DEFAULT NULL,
                       p_angro     IN NUMBER   DEFAULT NULL,
                       p_online    IN NUMBER   DEFAULT NULL,
                       p_um        IN VARCHAR2 DEFAULT 'buc.',
                       p_brand     IN VARCHAR2 DEFAULT NULL,
                       p_data      IN DATE     DEFAULT TRUNC(SYSDATE))
    RETURN NUMBER IS
    v_cod NUMBER;
    v_id  NUMBER;
  BEGIN
    IF p_denumirea IS NULL OR p_grupa IS NULL THEN
      RAISE_APPLICATION_ERROR(-20263,
        'Denumirea si grupa sunt obligatorii / name and group are required');
    END IF;
    -- RO: pozitia in nomenclatorul nativ / EN: native nomenclature row
    SELECT ID_TMS_UNIVERS.NEXTVAL INTO v_cod FROM dual;
    INSERT INTO TMS_UNIVERS (COD, DENUMIREA, TIP, UM, GR1, CACCESS)
    VALUES (v_cod, SUBSTR(p_denumirea, 1, 250), 'P',
            SUBSTR(p_um, 1, 10), 'TVR', g_caccess);
    -- RO: randul de feed — GRUPA/CATEGORIE noi creeaza implicit nodul de
    --     arbore / EN: feed row — new GRUPA/CATEGORIE implicitly creates
    --     the tree node (the tree is derived from these columns)
    SELECT NVL(MAX(ID), 0) + 1 INTO v_id FROM BIRO26_GOODS;
    INSERT INTO BIRO26_GOODS (ID, COD_UNIVERS, DENUMIRE, GRUPA, CATEGORIE,
                              UNIT, BRAND, ANGRO, IONLINE, RETAIL1)
    VALUES (v_id, v_cod, SUBSTR(p_denumirea, 1, 500),
            SUBSTR(p_grupa, 1, 200), SUBSTR(p_categorie, 1, 200),
            SUBSTR(p_um, 1, 50), SUBSTR(p_brand, 1, 200),
            NVL(p_angro, p_retail), NVL(p_online, p_retail),
            TO_CHAR(p_retail, 'FM999999990.00'));
    -- RO: perioada de pret in lista (toate trei coloanele)
    -- EN: the price-list period (all three price columns)
    IF p_retail IS NOT NULL THEN
      set_price(p_sc => v_cod, p_data => p_data,
                p_pretv  => p_retail,
                p_pretv1 => NVL(p_angro, p_retail),
                p_pretv2 => NVL(p_online, p_retail));
    END IF;
    RETURN v_cod;
  END add_product;

  PROCEDURE set_setting(p_key IN VARCHAR2, p_val IN VARCHAR2,
                        p_descr IN VARCHAR2 DEFAULT NULL) IS
  BEGIN
    MERGE INTO YBIRO_SETTINGS s USING (SELECT p_key k FROM dual) d
       ON (s.skey = d.k)
     WHEN MATCHED THEN UPDATE SET s.sval = p_val,
          s.descr = NVL(p_descr, s.descr), s.updated_at = SYSTIMESTAMP
     WHEN NOT MATCHED THEN INSERT (skey, sval, descr)
          VALUES (p_key, p_val, p_descr);
  END set_setting;

  FUNCTION get_setting(p_key IN VARCHAR2) RETURN VARCHAR2 IS
    v VARCHAR2(400);
  BEGIN
    SELECT sval INTO v FROM YBIRO_SETTINGS WHERE skey = p_key;
    RETURN v;
  EXCEPTION WHEN NO_DATA_FOUND THEN
    RETURN NULL;
  END get_setting;

END y_ai_BIRO26;
/
