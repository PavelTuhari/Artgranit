-- Y_AI_BIRO26 (OFFICEPLUS, Oracle 11g) — package SPEC
-- Выгружено 2026-08-09. Разворачивать: CREATE OR REPLACE <содержимое>
PACKAGE            y_ai_BIRO26 AS
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
  -- RO: NRSET implicit pe cont de plata (subset ca la alte documente).
  -- EN: default NRSET for invoices (subset like other documents).
  g_nrset_default NUMBER  := 201;
  -- RO: cheia YBIRO_SETTINGS pentru numarul de start (NRMANUAL).
  -- EN: YBIRO_SETTINGS key for invoice start number (NRMANUAL).
  g_invoice_nr_start_key VARCHAR2(60) := 'INVOICE_NR_START';

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

  -- RO: Numarul documentului din NRMANUAL (numeric). Compat: numele get_nrset.
  -- EN: Document number from NRMANUAL (numeric). Compat name get_nrset.
  FUNCTION get_nrset(p_nrdoc IN NUMBER) RETURN NUMBER;

  -- RO: Numarul afisat (TMDB_DOCS.NRMANUAL).
  -- EN: Display document number (TMDB_DOCS.NRMANUAL).
  FUNCTION get_nrmanual(p_nrdoc IN NUMBER) RETURN VARCHAR2;

  -- RO: NRMANUAL GARANTAT: intoarce numarul documentului, iar daca acesta
  --     lipseste il ATRIBUIE automat dupa ACELEASI reguli ca la emiterea
  --     unui cont nou (serie INVOICE_SERIES + contorul INVOICE_NR_START,
  --     rollover peste 999). Tranzactie autonoma: numarul se salveaza
  --     imediat, deci e vizibil si din alte sesiuni (site, aplicatii).
  -- EN: guaranteed NRMANUAL — assigns one by create_invoice's own rules
  --     when missing; autonomous transaction, visible to other sessions.
  FUNCTION ensure_nrmanual(p_nrdoc IN NUMBER) RETURN VARCHAR2;

  -- RO: Urmatorul NRMANUAL = contorul YBIRO_SETTINGS.INVOICE_NR_START
  --     (dupa emitere se incrementeaza automat).
  -- EN: Next NRMANUAL = counter YBIRO_SETTINGS.INVOICE_NR_START
  --     (auto-incremented after each invoice).
  FUNCTION next_invoice_nr RETURN NUMBER;

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

  -- RO: genereaza SI ataseaza la documentul EXISTENT (ecranul «Object» /
  --     VMDB_DOCS_OLE) contul de plata + comanda cumparatorului: functia
  --     apeleaza DIN INTERIORUL Oracle (UTL_HTTP) API-ul web
  --     http://officeplus.md/api/biro26/gen-docs-by-nr/<nr>.
  --     p_nr = NUMARUL documentului (NRMANUAL, cu sau fara '#').
  --     Cheia API se citeste din YBIRO_SETTINGS('API_GEN_KEY')
  --     (= BIRO26_API_TOKEN din .env-ul aplicatiei web).
  --     Intoarce raspunsul serverului ('HTTP 200: {..."invoice":"OK"...}').
  --     p_formats = ORICE combinatie din 'pdf,html,xlsx' (implicit 'pdf'):
  --       pdf/html -> ambele formulare; xlsx -> echivalentul Excel al
  --       contului (tabel real + formule). Toate se ataseaza la document.
  --     Exemple: SELECT y_ai_BIRO26.gen_conturi('21') FROM dual;
  --              SELECT y_ai_BIRO26.gen_conturi('A-25','pdf,html,xlsx') FROM dual;
  -- EN: render + attach the requested format set for an existing document,
  --     called from INSIDE Oracle via UTL_HTTP against the web API.
  FUNCTION gen_conturi(p_nr      IN VARCHAR2,
                       p_formats IN VARCHAR2 DEFAULT 'pdf') RETURN VARCHAR2;
PROCEDURE gen_conturi_pr(
    p_nrdoc       IN number,
    p_formats  IN VARCHAR2 DEFAULT 'pdf'
);
END y_ai_BIRO26;