-- =====================================================================
-- RO: Documentele de marketing in arhitectura de documente UNA.
-- EN: Marketing documents in the UNA document architecture.
--
-- =====================================================================
-- RO: DE CE RANDURILE STAU IN TMDB_CST3A SI NU INTR-UN TABEL PROPRIU
-- EN: WHY THE ROWS LIVE IN TMDB_CST3A AND NOT IN AN OWN TABLE
-- =====================================================================
--
-- RO: Tipurile proprii de documente 60001 si 60002 sunt copiate de la
--     documentele de achizitie servicii, iar impreuna cu ele au preluat
--     designul de grid din configurator. Gridul se numeste
--     :fRegistru:grCST3a, formatul SDBG, si contine un SmartQuery
--     explicit:
--
--         SELECT ... FROM VMDB_CST3A WHERE NRDOC = :COD ORDER BY NRDOC1
--
--     Adica clientul nativ UNA citeste si scrie randurile acestor
--     documente prin vederea VMDB_CST3A. Un tabel propriu de randuri ar
--     fi al doilea depozit, invizibil clientului: aceleasi documente ar
--     arata diferit in web si in client. De aceea randurile stau acolo
--     unde le asteapta clientul.
--
-- EN: The own document types 60001 and 60002 are copied from the service
--     purchase documents, and together with them they inherited the grid
--     design from the configurator. The grid is named :fRegistru:grCST3a,
--     format SDBG, and carries an explicit SmartQuery:
--
--         SELECT ... FROM VMDB_CST3A WHERE NRDOC = :COD ORDER BY NRDOC1
--
--     That is, the native UNA client reads and writes the rows of these
--     documents through the VMDB_CST3A view. An own row table would be a
--     second store, invisible to the client: the same documents would
--     look different in the web and in the client. Hence the rows live
--     where the client expects them.
--
-- RO: TMDB_CST3A este un tabel universal de randuri: NRDOC + NRDOC1 si un
--     set de sloturi tipizate. Fiecare tip de document isi aseaza campurile
--     pe sloturi, iar o vedere le da nume de business. Maparea de aici:
-- EN: TMDB_CST3A is a universal row table: NRDOC + NRDOC1 plus a set of
--     typed slots. Each document type maps its fields onto slots, and a
--     view gives them business names. The mapping used here:
--
--     CONT   -> contul de cheltuieli      SC    -> pozitia din TMS_UNIVERS
--     DEP    -> contragentul              SC1   -> platforma
--     CANT1  -> cantitatea                PRET1 -> pretul
--     SUMA1  -> suma fara TVA             SUMA2 -> TVA
--     SUMA3  -> total                     PRM1  -> canalul de promovare
--     DATA1  -> inceputul plasarii        DATA2 -> sfarsitul plasarii
--     STR1   -> nota
--
-- RO: Antetul propriu TMDB_YSEO1M ramane: el pastreaza legatura cu
--     campania si cu perioada de buget, adica ce nu are unde sa stea in
--     TMDB_DOCS. Clientul nativ nu il cere, foloseste modulul web.
-- EN: The own header TMDB_YSEO1M stays: it keeps the link to the campaign
--     and to the budget period, that is what has nowhere to live in
--     TMDB_DOCS. The native client does not need it, the web module does.
-- =====================================================================

-- ---------------------------------------------------------------------
-- RO: Antet. Un rand pe document, subordonat lui TMDB_DOCS 1 la 1.
-- EN: Header. One row per document, subordinate to TMDB_DOCS 1 to 1.
-- ---------------------------------------------------------------------
CREATE TABLE TMDB_YSEO1M (
    NRDOC           NUMBER          NOT NULL,
    SITE_COD        NUMBER,
    CAMP_COD        NUMBER,
    ARTICLE_COD1    NUMBER,
    CHANNEL_COD1    NUMBER,
    PLATFORM_COD    NUMBER,
    -- RO: Perioada de buget in format YYYY-MM. EN: Budget period YYYY-MM.
    PERIOD          VARCHAR2(10),
    NOTE            VARCHAR2(2000),
    CONSTRAINT TMDB_YSEO1M_PK PRIMARY KEY (NRDOC),
    CONSTRAINT TMDB_YSEO1M_FK FOREIGN KEY (NRDOC)
        REFERENCES TMDB_DOCS (COD) ON DELETE CASCADE
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT TMDB_YSEO1M_FK_SITE FOREIGN KEY (SITE_COD)
        REFERENCES YSEO_SITE (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT TMDB_YSEO1M_FK_CAMP FOREIGN KEY (CAMP_COD)
        REFERENCES YSEO_CAMPAIGN (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT TMDB_YSEO1M_FK_ART FOREIGN KEY (ARTICLE_COD1)
        REFERENCES YSEO_DICT (COD1) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT TMDB_YSEO1M_FK_CHAN FOREIGN KEY (CHANNEL_COD1)
        REFERENCES YSEO_DICT (COD1) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT TMDB_YSEO1M_FK_PLAT FOREIGN KEY (PLATFORM_COD)
        REFERENCES YSEO_PLATFORM (COD) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT TMDB_YSEO1M_CK_PERIOD CHECK (
        PERIOD IS NULL OR REGEXP_LIKE(PERIOD, '^[0-9]{4}-[0-9]{2}$'))
);
COMMENT ON TABLE TMDB_YSEO1M IS 'RO: Antetul documentului de marketing / EN: Marketing document header';

CREATE INDEX TMDB_YSEO1M_I_SITE ON TMDB_YSEO1M (SITE_COD);
CREATE INDEX TMDB_YSEO1M_I_CAMP ON TMDB_YSEO1M (CAMP_COD);
CREATE INDEX TMDB_YSEO1M_I_ART ON TMDB_YSEO1M (ARTICLE_COD1);
CREATE INDEX TMDB_YSEO1M_I_CHAN ON TMDB_YSEO1M (CHANNEL_COD1);
CREATE INDEX TMDB_YSEO1M_I_PLAT ON TMDB_YSEO1M (PLATFORM_COD);
/

-- =====================================================================
-- RO: Declansatoare pe tabele. EN: Table triggers.
-- =====================================================================

-- RO: Antetul de marketing poate apartine doar documentelor proprii.
--     Fara verificare o eroare de cod l-ar lega de un document strain.
-- EN: The marketing header may belong only to own documents. Without the
--     check a code error would attach it to a foreign document.
CREATE OR REPLACE TRIGGER TMDB_YSEO1M_TRG_OWN
BEFORE INSERT OR UPDATE ON TMDB_YSEO1M FOR EACH ROW
DECLARE
  v_sysfid NUMBER;
BEGIN
  SELECT SYSFID INTO v_sysfid FROM TMDB_DOCS WHERE COD = :NEW.NRDOC;
  IF v_sysfid IS NULL OR v_sysfid NOT BETWEEN 60000 AND 60099 THEN
    RAISE_APPLICATION_ERROR(-20110,
      'RO: Antetul de marketing poate fi legat doar de documentele '
      || 'proprii ale modulului. / '
      || 'EN: The marketing header may only be attached to the module '
      || 'own documents.');
  END IF;
EXCEPTION
  WHEN NO_DATA_FOUND THEN
    RAISE_APPLICATION_ERROR(-20111,
      'RO: Documentul indicat nu exista. / '
      || 'EN: The referenced document does not exist.');
END;
/

-- =====================================================================
-- RO: Vederi. Antetul isi primeste descifrarile CLC ca in familia CST3,
--     iar randurile sunt aceleasi randuri CST3A, doar cu nume de business.
-- EN: Views. The header gets its CLC lookups as in the CST3 family, and
--     the rows are the same CST3A rows, only under business names.
-- =====================================================================

CREATE OR REPLACE VIEW VMDB_YSEO1M AS
SELECT a.NRDOC, a.SITE_COD, a.CAMP_COD, a.ARTICLE_COD1, a.CHANNEL_COD1,
       a.PLATFORM_COD, a.PERIOD, a.NOTE,
       (SELECT s.DOMAIN FROM YSEO_SITE s WHERE s.COD = a.SITE_COD) CLCSITET,
       (SELECT c.CAMP_CODE FROM YSEO_CAMPAIGN c WHERE c.COD = a.CAMP_COD) CLCCAMPT,
       (SELECT d.NAME_RU FROM YSEO_DICT d WHERE d.COD1 = a.ARTICLE_COD1) CLCARTT,
       (SELECT d.NAME_RU FROM YSEO_DICT d WHERE d.COD1 = a.CHANNEL_COD1) CLCCHANT,
       (SELECT p.NAME FROM YSEO_PLATFORM p WHERE p.COD = a.PLATFORM_COD) CLCPLATT
FROM   TMDB_YSEO1M a;

-- RO: Randurile documentelor proprii peste acelasi TMDB_CST3A pe care il
--     citeste clientul nativ. Filtrul dupa tipul documentului este
--     obligatoriu: tabelul este comun tuturor tipurilor, si fara filtru
--     vederea ar arata randuri straine.
-- EN: The rows of own documents over the same TMDB_CST3A the native
--     client reads. The filter by document type is mandatory: the table
--     is shared by all types, and without the filter the view would show
--     foreign rows.
CREATE OR REPLACE VIEW VMDB_YSEO1D AS
SELECT a.NRDOC, a.NRDOC1,
       a.CONT        AS CONT,
       a.DEP         AS PARTNER_COD,
       a.SC          AS SC,
       a.SC1         AS PLATFORM_COD,
       a.PRM1        AS CHANNEL_COD1,
       a.CANT1       AS CANT,
       a.PRET1       AS PRET,
       a.SUMA1       AS SUMA,
       a.SUMA2       AS SUMA_TVA,
       a.SUMA3       AS SUMA_TOTAL,
       a.DATA1       AS DATE_START,
       a.DATA2       AS DATE_END,
       a.STR1        AS NOTE,
       (SELECT u.DENUMIREA FROM TMS_UNIVERS u WHERE u.COD = a.SC) CLCSCT,
       (SELECT u.UM FROM TMS_UNIVERS u WHERE u.COD = a.SC) CLCUMT,
       (SELECT u.DENUMIREA FROM TMS_UNIVERS u WHERE u.COD = a.DEP) CLCDEPT,
       (SELECT d.NAME_RU FROM YSEO_DICT d WHERE d.COD1 = a.PRM1) CLCCHANT,
       (SELECT p.NAME FROM YSEO_PLATFORM p WHERE p.COD = a.SC1) CLCPLATT
FROM   TMDB_CST3A a
WHERE  EXISTS (SELECT 1 FROM TMDB_DOCS d
               WHERE d.COD = a.NRDOC
                 AND d.SYSFID BETWEEN 60000 AND 60099);
/

-- =====================================================================
-- RO: Declansator pe vedere. Vederea are filtru si subinterogari, deci
--     nu este actualizabila direct. Declansatorul o face scriibila si in
--     acelasi timp pazeste doua lucruri: randul merge doar la un document
--     propriu, iar totalul se calculeaza daca nu a fost dat.
-- EN: View trigger. The view has a filter and subqueries, so it is not
--     directly updatable. The trigger makes it writable and at the same
--     time guards two things: the row goes only to an own document, and
--     the total is derived when it was not given.
-- =====================================================================
CREATE OR REPLACE TRIGGER TRIG_VMDB_YSEO1D
INSTEAD OF INSERT OR UPDATE OR DELETE ON VMDB_YSEO1D
DECLARE
  v_sysfid NUMBER;
  v_suma   NUMBER;
  v_total  NUMBER;
BEGIN
  IF DELETING THEN
    DELETE FROM TMDB_CST3A
    WHERE NRDOC = :OLD.NRDOC AND NRDOC1 = :OLD.NRDOC1;
    RETURN;
  END IF;

  BEGIN
    SELECT SYSFID INTO v_sysfid FROM TMDB_DOCS WHERE COD = :NEW.NRDOC;
  EXCEPTION
    WHEN NO_DATA_FOUND THEN
      RAISE_APPLICATION_ERROR(-20111,
        'RO: Documentul indicat nu exista. / '
        || 'EN: The referenced document does not exist.');
  END;

  IF v_sysfid IS NULL OR v_sysfid NOT BETWEEN 60000 AND 60099 THEN
    RAISE_APPLICATION_ERROR(-20110,
      'RO: Randurile de marketing pot fi legate doar de documentele '
      || 'proprii ale modulului. / '
      || 'EN: Marketing rows may only be attached to the module own '
      || 'documents.');
  END IF;

  v_suma := NVL(:NEW.SUMA, ROUND(NVL(:NEW.CANT, 0) * NVL(:NEW.PRET, 0), 2));
  v_total := NVL(:NEW.SUMA_TOTAL, v_suma + NVL(:NEW.SUMA_TVA, 0));

  IF INSERTING THEN
    INSERT INTO TMDB_CST3A (NRDOC, NRDOC1, CONT, DEP, SC, SC1, PRM1,
                            CANT1, PRET1, SUMA1, SUMA2, SUMA3,
                            DATA1, DATA2, STR1)
    VALUES (:NEW.NRDOC,
            NVL(:NEW.NRDOC1, ID_TMDB_CM.NEXTVAL),
            :NEW.CONT, :NEW.PARTNER_COD, :NEW.SC, :NEW.PLATFORM_COD,
            :NEW.CHANNEL_COD1, NVL(:NEW.CANT, 1), NVL(:NEW.PRET, 0),
            v_suma, :NEW.SUMA_TVA, v_total,
            :NEW.DATE_START, :NEW.DATE_END, :NEW.NOTE);
  ELSE
    UPDATE TMDB_CST3A
    SET    CONT = :NEW.CONT, DEP = :NEW.PARTNER_COD, SC = :NEW.SC,
           SC1 = :NEW.PLATFORM_COD, PRM1 = :NEW.CHANNEL_COD1,
           CANT1 = :NEW.CANT, PRET1 = :NEW.PRET,
           SUMA1 = v_suma, SUMA2 = :NEW.SUMA_TVA, SUMA3 = v_total,
           DATA1 = :NEW.DATE_START, DATA2 = :NEW.DATE_END, STR1 = :NEW.NOTE
    WHERE  NRDOC = :OLD.NRDOC AND NRDOC1 = :OLD.NRDOC1;
  END IF;
END;
/
