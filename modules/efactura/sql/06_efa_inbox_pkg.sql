-- RO: Importul facturilor primite EXACT ca in celelalte baze de pe cloudbd
--     (BMPUBLIC, FPROIECT, DATACONTROL2025 - 13.09.2026):
--       document 12103 (Pokupka - Paketnaya zagruzka dokumentov (12103)) cu XML-ul
--       pachetului ca atasament OLE -> pkg_edi_xml.import_xml_package_object
--       (parserul si validarile vendorului: TMDB_XML_PACKAGE cu STATUS_DOC)
--       -> documente 1209 (Oprihodovanie tovara (1209)) cu antet (furnizor dupa IDNO,
--       CT 5211, DT 2171, depozitul) si pozitii (ST201D) cu analitica dupa
--       regulile VMS_IMPORT_EFACTURA, codul de bare sau denumirea.
--     Procedurile fill_tmptable_48101_header/detail si create_docs_1209 sint
--     private, respectiv absente, in pachetul vendorului din OFFICEPLUS -
--     de aceea sint portate aici, cu constantele OfficePlus (doc 1209 nr. 4).
-- EN: package-import flow ported from the other cloudbd schemas.

ALTER TABLE EFA_IN ADD (PKG_NRDOC NUMBER, PKG_NRDOC1 NUMBER, PKG_STATUS NUMBER, PKG_COMMENT VARCHAR2(2000), DEST_NRDOC NUMBER)
/

CREATE OR REPLACE PACKAGE EFA_INBOX AS
  PROCEDURE land(p_nrdoc IN NUMBER, p_xml IN CLOB, p_file_name IN VARCHAR2);
  FUNCTION  reserve_nrdoc RETURN NUMBER;
  FUNCTION  d(p IN VARCHAR2) RETURN DATE;
  -- RO: documentul 12103 + XML-ul ca OLE, intoarce COD-ul documentului
  FUNCTION  new_package(p_xml IN CLOB, p_file_name IN VARCHAR2, p_userid IN NUMBER DEFAULT NULL) RETURN NUMBER;
  -- RO: XML-ul unui pachet existent (creat din Delphi) - atasat ca OLE
  PROCEDURE attach(p_nrdoc IN NUMBER, p_xml IN CLOB, p_file_name IN VARCHAR2);
  -- RO: parserul + validarile vendorului
  PROCEDURE import_package(p_nrdoc IN NUMBER);
  -- RO: documentele 1209 din pozitiile valide (STATUS_DOC = 1) ale pachetului
  PROCEDURE create_docs_1209(p_nrdoc IN NUMBER);
  -- RO: analitica pozitiilor: reguli, cod de bare, denumire
  PROCEDURE compl_analitica(p_nrdoc IN NUMBER);
  -- RO: din Delphi: aduce din SFS facturile noi in acest pachet (prin API-ul web)
  FUNCTION  fetch_api(p_nrdoc IN NUMBER) RETURN VARCHAR2;
  PROCEDURE fetch_api_pr(p_nrdoc IN NUMBER);
  FUNCTION  status_text(p_status IN NUMBER) RETURN VARCHAR2;
END EFA_INBOX;
/

CREATE OR REPLACE PACKAGE BODY EFA_INBOX AS
  g_userid_set BOOLEAN := FALSE;

  c_base CONSTANT VARCHAR2(200) := 'http://officeplus.md/api/biro26/efactura';

  FUNCTION setting(p_key IN VARCHAR2, p_default IN VARCHAR2) RETURN VARCHAR2 IS
    v VARCHAR2(2000);
  BEGIN
    SELECT SVALUE INTO v FROM EFA_SETTING WHERE SKEY = p_key;
    RETURN NVL(v, p_default);
  EXCEPTION WHEN NO_DATA_FOUND THEN RETURN p_default;
  END setting;

  FUNCTION d(p IN VARCHAR2) RETURN DATE IS
  BEGIN
    IF p IS NULL THEN RETURN NULL; END IF;
    RETURN TRUNC(TO_DATE(SUBSTR(p, 1, 19), 'YYYY-MM-DD"T"HH24:MI:SS'));
  EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
  END d;

  FUNCTION reserve_nrdoc RETURN NUMBER IS
    v NUMBER;
  BEGIN
    SELECT ID_TMDB_DOCS.NEXTVAL INTO v FROM dual;
    RETURN v;
  END reserve_nrdoc;

  FUNCTION status_text(p_status IN NUMBER) RETURN VARCHAR2 IS
  BEGIN
    RETURN CASE p_status
      WHEN 1 THEN 'valida'
      WHEN 3 THEN 'DocumentType/DocumentForm neacceptat'
      WHEN 4 THEN 'seria trebuie sa aiba doar litere latine mari'
      WHEN 5 THEN 'numarul trebuie sa aiba doar cifre / exista deja in ST201D'
      WHEN 6 THEN 'data facturii in afara intervalului permis'
      WHEN 7 THEN 'furnizorul (IDNO) nu exista in nomenclator'
      WHEN 8 THEN 'subdiviziunea cumparatorului nu exista'
      WHEN 9 THEN 'dublura in documente'
      WHEN 10 THEN 'dublura in XML'
      WHEN 12 THEN 'exista deja in CST3A'
      WHEN 13 THEN 'exista deja in alt pachet'
      WHEN 14 THEN 'dublura in VINZ (seria+nr)'
      WHEN 15 THEN 'eroare la crearea documentului'
      ELSE 'statut ' || p_status END;
  END status_text;

  -- -- OLE --------------------------------------------------------------
  PROCEDURE attach(p_nrdoc IN NUMBER, p_xml IN CLOB, p_file_name IN VARCHAR2) IS
    v_n1   NUMBER;
    v_blob BLOB;
    v_dest INTEGER := 1; v_src INTEGER := 1;
    v_lang INTEGER := DBMS_LOB.DEFAULT_LANG_CTX; v_warn INTEGER;
  BEGIN
    SELECT ID_TMDB_CM.NEXTVAL INTO v_n1 FROM dual;
    INSERT INTO TMDB_DOCS_OLE (NRDOC, NRDOC1, TXTCOMMENT, PFILE, OLEOBJ)
    VALUES (p_nrdoc, v_n1, 'e-Factura (API SFS)', p_file_name, EMPTY_BLOB());
    SELECT OLEOBJ INTO v_blob FROM TMDB_DOCS_OLE WHERE NRDOC = p_nrdoc AND NRDOC1 = v_n1 FOR UPDATE;
    -- RO: CLOB -> BLOB in setul de caractere al bazei (blob_to_clob al vendorului il citeste inapoi la fel)
    DBMS_LOB.CONVERTTOBLOB(v_blob, p_xml, DBMS_LOB.LOBMAXSIZE, v_dest, v_src, DBMS_LOB.DEFAULT_CSID, v_lang, v_warn);
  END attach;

  -- RO: perioada de lucru (TPARAMS) e goala in sesiunile de sistem (API, job), deci
  --     TRIG_BFALL_TMDB_DOCS ar refuza orice document. Folosim ocolirea prevazuta de
  --     trigger (envun4.dont_fire_trigger), ca Y_AI_BIRO26, si o ridicam imediat.
  --     Tot aici dam sesiunii de sistem un PARAM_USERID (setarea in_userid, implicit 1):
  --     triggerele TMDB_DOCS inlocuiesc USERID cu acest context, altfel ramine gol.
  PROCEDURE sys_guard(p_on IN BOOLEAN) IS
  BEGIN
    IF p_on THEN
      un4public.envun4.envsetvalue('dont_fire_trigger', '1');
      IF SYS_CONTEXT('envun4', 'param_userid') IS NULL THEN
        un4public.envun4.envsetvalue('param_userid', setting('in_userid', '1'));
        g_userid_set := TRUE;
      END IF;
    ELSE
      un4public.envun4.envsetvalue('dont_fire_trigger', NULL);
      IF g_userid_set THEN
        un4public.envun4.envsetvalue('param_userid', NULL);
        g_userid_set := FALSE;
      END IF;
    END IF;
  END sys_guard;

  FUNCTION new_package(p_xml IN CLOB, p_file_name IN VARCHAR2, p_userid IN NUMBER DEFAULT NULL) RETURN NUMBER IS
    v_cod   NUMBER;
    v_nrset NUMBER := TO_NUMBER(setting('in_nrset', '201'));
  BEGIN
    SELECT ID_TMDB_DOCS.NEXTVAL INTO v_cod FROM dual;
    -- RO: ca in BMPUBLIC (doc 9140): TIP P, SYSFID 12103, NRSET, LEI, AT3 1, CODF 0
    sys_guard(TRUE);
    BEGIN
      INSERT INTO TMDB_DOCS (COD, TIP, SYSFID, USERID, DATAMANUAL, VALUTA, NRSET, ISGFC, DOCCOLOR, CODF, AT3)
      VALUES (v_cod, 'P', 12103, NVL(p_userid, UID), TRUNC(SYSDATE), 'LEI', v_nrset, 0, '`', 0, 1);
      sys_guard(FALSE);
    EXCEPTION WHEN OTHERS THEN sys_guard(FALSE); RAISE;
    END;
    attach(v_cod, p_xml, p_file_name);
    RETURN v_cod;
  END new_package;

  PROCEDURE import_package(p_nrdoc IN NUMBER) IS
  BEGIN
    -- RO: vendorul doar adauga rinduri, iar la o reluare stergem pozitiile fara document creat,
    --     ca sa nu se dubleze (Delphi face acelasi lucru inainte de re-import)
    DELETE FROM TMDB_XML_PACKAGE WHERE NRDOC = p_nrdoc AND NRDOC_DEST IS NULL;
    pkg_edi_xml.import_xml_package_object(p_nrdoc);
  END import_package;

  -- -- copiile procedurilor private ale vendorului (fill_tmptable_48101_*) --
  PROCEDURE hdr_1209(p_nrdoc INTEGER, p_clob CLOB, p_nrdoc_dest INTEGER, p_nrdoc1 INTEGER) IS
  BEGIN
    INSERT INTO TMDB_XML_FACTURA
      (NRDOC, ROWN, CODE, TIP_DOC, DOCUMENTTYPE, DOCUMENTFORM, FACTURASERIA, FACTURANUMBER, ISSUEDDATE, DELIVERYDATE,
       BRANCHACCOUNT, BRANCHTITLE, BRANCHCODE, IDNO, TITLE, CODTVA, ADDRESS, TAXPAYERTYPE,
       BUYER_BRANCHACCOUNT, BUYER_BRANCHTITLE, BUYER_BRANCHCODE, BUYER_IDNO, BUYER_TITLE, BUYER_ADDRESS, BUYER_TAXPAYERTYPE, BUYER_CODTVA,
       TRANSPORTER_BRANCHACCOUNT, TRANSPORTER_BRANCHTITLE, TRANSPORTER_BRANCHCODE, TRANSPORTER_IDNO, TRANSPORTER_TITLE, TRANSPORTER_ADDRESS,
       TRANSPORTER_TAXPAYERTYPE, TRANSPORTER_CODTVA, ATTACHEDDOCUMENTS, NOTES, DELEGATESERIA, DELEGATENUMBER, DELEGATENAME, DELEGATEDATE,
       VEHICLELOGBOOK_ISSUEDDATE, VEHICLELOGBOOK_SERIA, VEHICLELOGBOOK_NUMBER, LOADINGPOINT, LOADINGPOINTCODE, UNLOADINGPOINT, UNLOADINGPOINTCODE,
       REDIRECTIONS, TOTAL, TTOTALTVA, ADDITIONALINFORMATION, FILE_NAME)
    SELECT p_nrdoc_dest, 0, '0',
       NVL(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/@DocumentForm'), 0) + 1,
       EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/@DocumentType'), EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/@DocumentForm'),
       EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Seria'), EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Number'),
       NVL(d(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/IssuedDate')), d(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/DeliveryDate'))),
       d(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/DeliveryDate')),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Supplier/BankAccount/@Account'), 1, 29),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Supplier/BankAccount/@BranchTitle'), 1, 160),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Supplier/BankAccount/@BranchCode'), 1, 20),
       EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Supplier/@IDNO'), SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Supplier/@Title'), 1, 160),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Supplier/@CodTVA'), 1, 20), SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Supplier/@Address'), 1, 150),
       EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Supplier/@TaxpayerType'),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Buyer/BankAccount/@Account'), 1, 29),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Buyer/BankAccount/@BranchTitle'), 1, 160),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Buyer/BankAccount/@BranchCode'), 1, 20),
       EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Buyer/@IDNO'), SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Buyer/@Title'), 1, 160),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Buyer/@Address'), 1, 150), EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Buyer/@TaxpayerType'),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Buyer/@CodTVA'), 1, 20),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Transporter/BankAccount/@Account'), 1, 29),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Transporter/BankAccount/@BranchTitle'), 1, 160),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Transporter/BankAccount/@BranchCode'), 1, 20),
       EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Transporter/@IDNO'), SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Transporter/@Title'), 1, 160),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Transporter/@Address'), 1, 150), EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Transporter/@TaxpayerType'),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Transporter/@CodTVA'), 1, 20),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/AttachedDocuments'), 1, 160), SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Notes'), 1, 160),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/DelegateSeria'), 1, 10), SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/DelegateNumber'), 1, 50),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/DelegateName'), 1, 50), d(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/DelegateDate')),
       d(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/VehicleLogbook/@IssuedDate')),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/VehicleLogbook/@Seria'), 1, 10), SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/VehicleLogbook/@Number'), 1, 50),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/LoadingPoint'), 1, 250), SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/LoadingPointCode'), 1, 10),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/UnloadingPoint'), 1, 250), SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/UnloadingPointCode'), 1, 10),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Redirections'), 1, 250),
       EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Total'), EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/TotalTVA'),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Document/AdditionalInformation/field'), 1, 160),
       'EFACTURA_IN_' || TO_CHAR(p_nrdoc) || '.xml'
    FROM TABLE(XMLSEQUENCE(XMLTYPE(p_clob).EXTRACT('//Documents/Document'))) t
    WHERE NVL(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Seria'), '-') || NVL(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Number'), '-') IN
          (SELECT NVL(FACTURA_SERIA, '-') || NVL(FACTURA_NR, '-') FROM TMDB_XML_PACKAGE WHERE NRDOC = p_nrdoc AND NRDOC1 = p_nrdoc1)
      AND ROWNUM = 1;
  END hdr_1209;

  PROCEDURE det_1209(p_nrdoc INTEGER, p_clob CLOB, p_nrdoc_dest INTEGER, p_nrdoc1 INTEGER) IS
    v_seria  VARCHAR2(10);
    v_nr     VARCHAR2(50);
  BEGIN
    -- RO: pozitiile facturii (seria+nr ale pachetului p_nrdoc1), ROWN din ID_TMDB_XML_PACKAGE,
    --     IDNO = NRDOC1 al pachetului, CODE = marfa dupa cod de bare sau 1 (conventia vendorului)
    SELECT FACTURA_SERIA, FACTURA_NR INTO v_seria, v_nr FROM TMDB_XML_PACKAGE WHERE NRDOC = p_nrdoc AND NRDOC1 = p_nrdoc1;
    INSERT INTO TMDB_XML_FACTURA
      (NRDOC, IDNO, FACTURASERIA, FACTURANUMBER, ROWN, TIP_DOC, REFERRALDOCUMENT_SERIA, REFERRALDOCUMENT_NUMBER, BARCODE, CODE, NNAME,
       UNITOFMEASURE, QUANTITY, UNITPRICEWITHOUTTVA, TOTALPRICEWITHOUTTVA, TVA, TOTALTVA, TOTALPRICE, OTHERINFO, PACKAGETYPE,
       NUMBEROFPLACES, GROSSWEIGHT, VOLUME, FILE_NAME)
    SELECT p_nrdoc_dest, p_nrdoc1, v_seria, v_nr, ID_TMDB_XML_PACKAGE.NEXTVAL, 1,
       SUBSTR(EXTRACTVALUE(VALUE(r), 'Row/@RefDocSeria'), 1, 10), SUBSTR(EXTRACTVALUE(VALUE(r), 'Row/@RefDocNumber'), 1, 50),
       NVL(SUBSTR(EXTRACTVALUE(VALUE(r), 'Row/@BarCode'), 1, 15), ' '),
       NVL((SELECT MIN(COD) FROM VMS_MPT_BARCODE WHERE BARCODE = EXTRACTVALUE(VALUE(r), 'Row/@BarCode')), 1),
       SUBSTR(EXTRACTVALUE(VALUE(r), 'Row/@Name'), 1, 160), SUBSTR(EXTRACTVALUE(VALUE(r), 'Row/@UnitOfMeasure'), 1, 10),
       EXTRACTVALUE(VALUE(r), 'Row/@Quantity'),
       NVL(EXTRACTVALUE(VALUE(r), 'Row/@UnitPriceWithoutTVA'), EXTRACTVALUE(VALUE(r), 'Row/@UnitPrice')),
       NVL(EXTRACTVALUE(VALUE(r), 'Row/@TotalPriceWithoutTVA'), EXTRACTVALUE(VALUE(r), 'Row/@TotalCost')),
       EXTRACTVALUE(VALUE(r), 'Row/@TVA'), EXTRACTVALUE(VALUE(r), 'Row/@TotalTVA'), EXTRACTVALUE(VALUE(r), 'Row/@TotalPrice'),
       SUBSTR(EXTRACTVALUE(VALUE(r), 'Row/@OtherInfo'), 1, 128), SUBSTR(EXTRACTVALUE(VALUE(r), 'Row/@PackageType'), 1, 16),
       SUBSTR(EXTRACTVALUE(VALUE(r), 'Row/@NumberOfPlaces'), 1, 16), SUBSTR(EXTRACTVALUE(VALUE(r), 'Row/@GrossWeight'), 1, 8),
       SUBSTR(EXTRACTVALUE(VALUE(r), 'Row/@Volume'), 1, 64), 'EFACTURA_IN_' || TO_CHAR(p_nrdoc) || '.xml'
    FROM TABLE(XMLSEQUENCE(XMLTYPE(p_clob).EXTRACT('//Documents/Document'))) t,
         TABLE(XMLSEQUENCE(VALUE(t).EXTRACT('Document/SupplierInfo/Merchandises/Row'))) r
    WHERE NVL(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Seria'), '-') = NVL(v_seria, '-')
      AND NVL(EXTRACTVALUE(VALUE(t), 'Document/SupplierInfo/Number'), '-') = NVL(v_nr, '-');
  END det_1209;

  PROCEDURE compl_analitica(p_nrdoc IN NUMBER) IS
    vdt NUMBER; vdt1 NUMBER; vdtsc NUMBER; vbar NUMBER;
  BEGIN
    -- RO: portat din FPROIECT.compl_analitica_serv + codul de bare (ca fill_doc_1231):
    --     1) regula VMS_IMPORT_EFACTURA (LIKE pe denumire) -> DT, DT1, DTSC
    --     2) codul de bare -> marfa (DTSC), contul dupa GR1 (TVR 2171, MBP 2131, altfel 2111)
    --     3) denumirea identica in VMS_UNIVERS
    FOR i IN (SELECT d1.RROWID, f1.NNAME, f1.BARCODE FROM VMDB_ST201D d1, TMDB_XML_FACTURA f1
              WHERE d1.NRDOC = p_nrdoc AND f1.NRDOC = p_nrdoc AND f1.ROWN = d1.RROWID AND NVL(d1.DTSC, 0) = 0) LOOP
      vdt := NULL; vdt1 := NULL; vdtsc := NULL;
      BEGIN
        SELECT DT, DT1, DTSC INTO vdt, vdt1, vdtsc FROM (
          SELECT a.DT, a.DT1, a.DTSC FROM VMS_IMPORT_EFACTURA a
          WHERE UPPER(i.NNAME) LIKE UPPER(a.TEXT1) ORDER BY a.PRIORITET, a.IDN) WHERE ROWNUM = 1;
      EXCEPTION WHEN NO_DATA_FOUND THEN NULL;
      END;
      IF vdtsc IS NULL AND i.BARCODE IS NOT NULL AND i.BARCODE <> ' ' THEN
        BEGIN
          SELECT u.COD, DECODE(u.GR1, 'TVR', 2171, 'MBP', 2131, 2111) INTO vdtsc, vdt
          FROM VMS_MPT_BARCODE b JOIN VMS_UNIVERS u ON u.COD = b.COD WHERE b.BARCODE = i.BARCODE AND ROWNUM = 1;
        EXCEPTION WHEN NO_DATA_FOUND THEN NULL;
        END;
      END IF;
      IF vdtsc IS NULL THEN
        BEGIN
          SELECT COD, DECODE(GR1, 'TVR', 2171, 'MBP', 2131, 2111) INTO vdtsc, vdt
          FROM VMS_UNIVERS u WHERE ISARHIV IS NULL AND UPPER(u.DENUMIREA) LIKE UPPER(i.NNAME) AND ROWNUM = 1;
        EXCEPTION WHEN NO_DATA_FOUND THEN NULL;
        END;
      END IF;
      IF vdt > 0 OR vdtsc IS NOT NULL THEN
        UPDATE VMDB_ST201D d SET DT = NVL(vdt, DT), DT1 = NVL(vdt1, DT1), DTSC = NVL(vdtsc, DTSC)
        WHERE NRDOC = p_nrdoc AND d.RROWID = i.RROWID;
      END IF;
    END LOOP;
  END compl_analitica;

  PROCEDURE create_docs_1209(p_nrdoc IN NUMBER) IS
    CURSOR c_ff IS
      SELECT NRDOC1, FACTURA_ISSUEDDATE, FACTURA_SERIA, FACTURA_NR, SUPPLIER_DIV FROM TMDB_XML_PACKAGE
      WHERE NRDOC = p_nrdoc AND STATUS_DOC = 1 AND NVL(DOCUMENT_FORM, 0) = 0 AND NRDOC_DEST IS NULL;
    v_nrdoc   NUMBER;
    v_ole     NUMBER;
    v_blob    BLOB;
    v_clob    CLOB;
    v_dest    INTEGER := 1; v_src INTEGER := 1; v_lang INTEGER := DBMS_LOB.DEFAULT_LANG_CTX; v_warn INTEGER;
    v_ctdep   NUMBER;
    v_nrset   NUMBER := TO_NUMBER(setting('in_nrset', '201'));
    v_dt      NUMBER := TO_NUMBER(setting('in_dt', '2171'));
    v_ct      NUMBER := TO_NUMBER(setting('in_ct', '5211'));
    v_dtdep   NUMBER := TO_NUMBER(setting('in_dtdep', '1'));
    v_dt_row  NUMBER := TO_NUMBER(setting('in_dt_row', '2171'));
    v_err     VARCHAR2(2000);
  BEGIN
    SELECT MAX(NRDOC1) INTO v_ole FROM TMDB_DOCS_OLE WHERE NRDOC = p_nrdoc;
    IF v_ole IS NULL THEN
      RAISE_APPLICATION_ERROR(-20000, 'e-Factura: pachetul ' || p_nrdoc || ' nu are XML atasat');
    END IF;
    SELECT OLEOBJ INTO v_blob FROM TMDB_DOCS_OLE WHERE NRDOC = p_nrdoc AND NRDOC1 = v_ole;
    DBMS_LOB.CREATETEMPORARY(v_clob, TRUE);
    DBMS_LOB.CONVERTTOCLOB(v_clob, v_blob, DBMS_LOB.LOBMAXSIZE, v_dest, v_src, DBMS_LOB.DEFAULT_CSID, v_lang, v_warn);

    -- RO: totul sub ocolirea de sistem: triggerele VMDB_ST201M/D (UN$GFC) actualizeaza TMDB_DOCS
    --     si ar reactiva verificarea perioadei de lucru la fiecare rind
    sys_guard(TRUE);
    BEGIN
    FOR b IN c_ff LOOP
      -- RO: furnizorul dupa IDNO (VMS_ORG.CODFISCAL sau CODVECHI), ca fill_doc_12103
      BEGIN
        SELECT COD INTO v_ctdep FROM (
          SELECT o.COD FROM VMS_ORG o WHERE o.CODFISCAL = b.SUPPLIER_DIV
          UNION ALL SELECT u.COD FROM VMS_UNIVERS u WHERE TRIM(u.CODVECHI) = b.SUPPLIER_DIV AND u.TIP = 'O'
          UNION ALL SELECT TO_NUMBER(b.SUPPLIER_DIV) FROM dual WHERE REGEXP_LIKE(b.SUPPLIER_DIV, '^[0-9]{1,9}$')) WHERE ROWNUM = 1;
      EXCEPTION WHEN OTHERS THEN v_ctdep := NULL;
      END;
      IF v_ctdep IS NULL THEN
        UPDATE TMDB_XML_PACKAGE SET STATUS_DOC = 7, COMMENTS = 'furnizor negasit: ' || b.SUPPLIER_DIV
        WHERE NRDOC = p_nrdoc AND NRDOC1 = b.NRDOC1;
        CONTINUE;
      END IF;
      SELECT ID_TMDB_DOCS.NEXTVAL INTO v_nrdoc FROM dual;
      -- RO: ca documentul 1209 nr. 4 din OfficePlus: TIP P, NRSET 201, LEI, data = data facturii
      INSERT INTO TMDB_DOCS (COD, TIP, SYSFID, USERID, DATAMANUAL, VALUTA, NRSET, ISGFC, CODF, AT3, NRMANUAL)
      VALUES (v_nrdoc, 'P', 1209, UID, NVL(b.FACTURA_ISSUEDDATE, TRUNC(SYSDATE)), 'LEI', v_nrset, 0, 0, 1,
              SUBSTR(b.FACTURA_SERIA || b.FACTURA_NR, 1, 25));
      UPDATE TMDB_XML_PACKAGE SET NRDOC_DEST = v_nrdoc, DOC_CREATE_DATE = b.FACTURA_ISSUEDDATE
      WHERE NRDOC = p_nrdoc AND NRDOC1 = b.NRDOC1;
      DELETE FROM TMDB_XML_FACTURA WHERE NRDOC = v_nrdoc;
      BEGIN
        hdr_1209(p_nrdoc, v_clob, v_nrdoc, b.NRDOC1);
        det_1209(p_nrdoc, v_clob, v_nrdoc, b.NRDOC1);
      EXCEPTION WHEN OTHERS THEN
        v_err := SUBSTR(v_nrdoc || ', ' || SQLERRM, 1, 2000);
        UPDATE TMDB_XML_PACKAGE SET STATUS_DOC = 15, COMMENTS = v_err WHERE NRDOC = p_nrdoc AND NRDOC1 = b.NRDOC1;
        CONTINUE;
      END;
      -- antetul: DT 2171 / CT 5211, depozitul, furnizorul, datele (ca doc 4)
      INSERT INTO VMDB_ST201M (NRDOC, DT, CT, DTDEP, CTDEP, DTDATA, CTDATA)
      VALUES (v_nrdoc, v_dt, v_ct, v_dtdep, v_ctdep, b.FACTURA_ISSUEDDATE, b.FACTURA_ISSUEDDATE);
      -- seria si numarul facturii fiscale (ca in celelalte baze)
      INSERT INTO VMDB01M_VINZ (COD, PRTVA_SERIA, PRTVA_NR, SCOMMENT)
      SELECT v_nrdoc, b.FACTURA_SERIA, b.FACTURA_NR, x.NOTES FROM TMDB_XML_FACTURA x
      WHERE x.NRDOC = v_nrdoc AND NVL(x.CODE, '0') = '0';
      -- pozitiile: cantitate, pret fara TVA, suma cu TVA, suma fara TVA, TVA
      INSERT INTO VMDB_ST201D (NRDOC, RROWID, DT, DTSC, CANT, PRET, SUMA, SUMAGAAP, SUMAVALCT)
      SELECT NRDOC, ROW_NUMBER() OVER (ORDER BY ROWN), v_dt_row, CASE WHEN CODE > '1' THEN TO_NUMBER(CODE) END,
             ABS(QUANTITY), UNITPRICEWITHOUTTVA, TOTALPRICE, TOTALPRICEWITHOUTTVA, TOTALTVA
      FROM TMDB_XML_FACTURA WHERE NRDOC = v_nrdoc AND NVL(CODE, '0') > '0' AND IDNO = TO_CHAR(b.NRDOC1);
      compl_analitica(v_nrdoc);
    END LOOP;
    sys_guard(FALSE);
    EXCEPTION WHEN OTHERS THEN sys_guard(FALSE); RAISE;
    END;
  END create_docs_1209;

  -- -- din Delphi: prin API-ul web (UTL_HTTP, HTTP simplu, ca EFA_NATIVE) --
  FUNCTION api_key RETURN VARCHAR2 IS
    v VARCHAR2(400);
  BEGIN
    SELECT sval INTO v FROM YBIRO_SETTINGS WHERE skey = 'API_GEN_KEY';
    RETURN v;
  EXCEPTION WHEN NO_DATA_FOUND THEN RETURN NULL;
  END api_key;

  FUNCTION fetch_api(p_nrdoc IN NUMBER) RETURN VARCHAR2 IS
    v_req   UTL_HTTP.REQ;
    v_resp  UTL_HTTP.RESP;
    v_chunk VARCHAR2(2000);
    v_out   VARCHAR2(4000) := '';
    v_open  BOOLEAN := FALSE;
    v_url   VARCHAR2(1000);
  BEGIN
    IF api_key IS NULL THEN
      RETURN 'ERR: lipseste YBIRO_SETTINGS.API_GEN_KEY';
    END IF;
    v_url := c_base || '/inbox/package/' || TO_CHAR(p_nrdoc) || '?api_key=' || api_key;
    UTL_HTTP.SET_TRANSFER_TIMEOUT(300);
    v_req  := UTL_HTTP.BEGIN_REQUEST(v_url, 'GET', 'HTTP/1.1');
    UTL_HTTP.SET_HEADER(v_req, 'User-Agent', 'EFA_INBOX');
    v_resp := UTL_HTTP.GET_RESPONSE(v_req);
    v_open := TRUE;
    UTL_HTTP.SET_BODY_CHARSET(v_resp, 'UTF-8');
    BEGIN
      LOOP
        UTL_HTTP.READ_TEXT(v_resp, v_chunk, 2000);
        v_out := SUBSTR(v_out || v_chunk, 1, 3900);
      END LOOP;
    EXCEPTION WHEN UTL_HTTP.END_OF_BODY THEN NULL;
    END;
    UTL_HTTP.END_RESPONSE(v_resp);
    RETURN SUBSTR('HTTP ' || v_resp.status_code || ': ' || v_out, 1, 4000);
  EXCEPTION WHEN OTHERS THEN
    IF v_open THEN
      BEGIN UTL_HTTP.END_RESPONSE(v_resp); EXCEPTION WHEN OTHERS THEN NULL; END;
    END IF;
    RETURN 'ERR: ' || SUBSTR(SQLERRM, 1, 3900);
  END fetch_api;

  PROCEDURE fetch_api_pr(p_nrdoc IN NUMBER) IS
    v VARCHAR2(4000);
  BEGIN
    v := fetch_api(p_nrdoc);
    IF v LIKE 'ERR:%' OR v NOT LIKE 'HTTP 200:%' THEN
      RAISE_APPLICATION_ERROR(-20000, 'e-Factura: ' || SUBSTR(v, 1, 1900));
    END IF;
    -- RO: mesajul (numar de facturi noi / statutul lor) in istoria documentului
    BEGIN
      DOCLOG('e-Factura: ' || SUBSTR(REPLACE(REPLACE(v, '{', ''), '}', ''), 11, 1900), p_nrdoc, 'EFA');
    EXCEPTION WHEN OTHERS THEN NULL;
    END;
  END fetch_api_pr;

  -- -- aterizarea simpla (pastrata pentru compatibilitate cu prima versiune) --
  PROCEDURE land(p_nrdoc IN NUMBER, p_xml IN CLOB, p_file_name IN VARCHAR2) IS
    x XMLTYPE := XMLTYPE(p_xml);
    r VARCHAR2(60) := '//Documents/Document/SupplierInfo/';
  BEGIN
    DELETE FROM TMDB_XML_FACTURA WHERE NRDOC = p_nrdoc;
    INSERT INTO TMDB_XML_FACTURA (NRDOC, ROWN, CODE, TIP_DOC, DATA_CREATE, FILE_NAME, FACTURASERIA, FACTURANUMBER,
       ISSUEDDATE, DELIVERYDATE, IDNO, TITLE, ADDRESS, BUYER_IDNO, BUYER_TITLE, TOTAL, TTOTALTVA)
    SELECT p_nrdoc, 0, '0', 1, SYSDATE, p_file_name, EXTRACTVALUE(x, r || 'Seria'), EXTRACTVALUE(x, r || 'Number'),
       d(EXTRACTVALUE(x, r || 'IssuedDate')), d(EXTRACTVALUE(x, r || 'DeliveryDate')),
       EXTRACTVALUE(x, r || 'Supplier/@IDNO'), SUBSTR(EXTRACTVALUE(x, r || 'Supplier/@Title'), 1, 160),
       SUBSTR(EXTRACTVALUE(x, r || 'Supplier/@Address'), 1, 150), EXTRACTVALUE(x, r || 'Buyer/@IDNO'),
       SUBSTR(EXTRACTVALUE(x, r || 'Buyer/@Title'), 1, 160), EXTRACTVALUE(x, r || 'Total'), EXTRACTVALUE(x, r || 'TotalTVA')
    FROM dual;
    INSERT INTO TMDB_XML_FACTURA (NRDOC, ROWN, TIP_DOC, DATA_CREATE, FILE_NAME, BARCODE, CODE, NNAME, UNITOFMEASURE, QUANTITY,
       UNITPRICEWITHOUTTVA, TOTALPRICEWITHOUTTVA, TVA, TOTALTVA, TOTALPRICE)
    SELECT p_nrdoc, ROWNUM, 1, SYSDATE, p_file_name, SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@BarCode'), 1, 15),
       SUBSTR(NVL(EXTRACTVALUE(VALUE(t), 'Row/@Code'), TO_CHAR(ROWNUM)), 1, 64), SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@Name'), 1, 160),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@UnitOfMeasure'), 1, 10), EXTRACTVALUE(VALUE(t), 'Row/@Quantity'),
       EXTRACTVALUE(VALUE(t), 'Row/@UnitPriceWithoutTVA'), EXTRACTVALUE(VALUE(t), 'Row/@TotalPriceWithoutTVA'),
       EXTRACTVALUE(VALUE(t), 'Row/@TVA'), EXTRACTVALUE(VALUE(t), 'Row/@TotalTVA'), EXTRACTVALUE(VALUE(t), 'Row/@TotalPrice')
    FROM TABLE(XMLSEQUENCE(x.EXTRACT(r || 'Merchandises/Row'))) t;
  END land;

END EFA_INBOX;
/
