-- RO: Facturile PRIMITE de la parteneri (partea de cumparator), 13.09.2026.
--     EFA_IN       - o linie per factura primita din SIA e-Factura (antetul,
--                    statutul SFS, statutul nostru, XML-ul complet)
--     EFA_IN_ROW   - pozitiile facturii + rezultatul potrivirii cu una.md
--                    (cod de bare -> marfa, regula TMS_IMPORT_EFACTURA -> cont)
--     EFA_INBOX    - aterizarea in tabela standard TMDB_XML_FACTURA, cu
--                    ACELEASI XPath-uri ca PKG_EDI_XML.blob_to_table (privat
--                    in pachetul lor, de aceea copiat aici), ca aplicatia
--                    nativa una.md sa vada factura ca pe una incarcata de ea
--     Text ASCII: baza OfficePlus e CL8MSWIN1251.
-- EN: inbound e-Factura invoices (buyer side) + landing into TMDB_XML_FACTURA.

CREATE TABLE EFA_IN (
    ID             NUMBER         NOT NULL,
    ENV            VARCHAR2(10)   DEFAULT 'test' NOT NULL,   -- test | prod
    SERIA          VARCHAR2(20),
    NUMBER_        VARCHAR2(40),
    SFS_STATUS     NUMBER,                                   -- InvoiceStatus din SFS
    SFS_QUEUE      VARCHAR2(20),                             -- for_signing | accepted | search
    SUPPLIER_IDNO  VARCHAR2(20),
    SUPPLIER_NAME  VARCHAR2(200),
    BUYER_IDNO     VARCHAR2(20),
    ISSUED_DATE    DATE,
    DELIVERY_DATE  DATE,
    TOTAL          NUMBER(17,2),
    TOTAL_TVA      NUMBER(17,2),
    DOC_TYPE       VARCHAR2(2),
    DOC_FORM       VARCHAR2(2),
    STATUS         VARCHAR2(20)   DEFAULT 'NEW' NOT NULL,    -- NEW | LANDED | ACCEPTED | REJECTED | ERROR
    SUPPLIER_COD   NUMBER,                                   -- TMS_UNIVERS.COD gasit dupa IDNO
    NRDOC          NUMBER,                                   -- NRDOC in TMDB_XML_FACTURA dupa aterizare
    ERR_MSG        VARCHAR2(2000),
    XML            CLOB,
    FETCHED_AT     DATE           DEFAULT SYSDATE NOT NULL,
    UPDATED        DATE           DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_EFA_IN PRIMARY KEY (ID),
    CONSTRAINT UQ_EFA_IN UNIQUE (ENV, SERIA, NUMBER_)
)
/

CREATE SEQUENCE EFA_IN_SEQ START WITH 1 INCREMENT BY 1
/

CREATE OR REPLACE TRIGGER EFA_IN_BI
BEFORE INSERT ON EFA_IN FOR EACH ROW
WHEN (NEW.ID IS NULL)
BEGIN
  SELECT EFA_IN_SEQ.NEXTVAL INTO :NEW.ID FROM dual;
END;
/

CREATE TABLE EFA_IN_ROW (
    ID             NUMBER         NOT NULL,
    IN_ID          NUMBER         NOT NULL,
    ROWN           NUMBER         NOT NULL,
    CODE           VARCHAR2(64),
    NAME           VARCHAR2(400),
    UM             VARCHAR2(20),
    QTY            NUMBER,
    PRICE          NUMBER(17,3),
    TOTAL_NO_TVA   NUMBER(17,3),
    TVA_PCT        NUMBER,
    TOTAL_TVA      NUMBER(17,2),
    TOTAL          NUMBER(17,2),
    BARCODE        VARCHAR2(40),
    MATCH_KIND     VARCHAR2(10),                             -- barcode | rule | none
    MATCH_COD      NUMBER,                                   -- TMS_UNIVERS.COD (marfa sau card serviciu)
    MATCH_DT       NUMBER,                                   -- contul DT din regula
    MATCH_RULE     NUMBER,                                   -- TMS_IMPORT_EFACTURA.IDN
    MATCH_NAME     VARCHAR2(200),                            -- denumirea din nomenclator sau regula
    CONSTRAINT PK_EFA_IN_ROW PRIMARY KEY (ID),
    CONSTRAINT FK_EFA_IN_ROW FOREIGN KEY (IN_ID) REFERENCES EFA_IN (ID) ON DELETE CASCADE
)
/

CREATE INDEX IX_EFA_IN_ROW_IN ON EFA_IN_ROW (IN_ID)
/

CREATE SEQUENCE EFA_IN_ROW_SEQ START WITH 1 INCREMENT BY 1
/

CREATE OR REPLACE TRIGGER EFA_IN_ROW_BI
BEFORE INSERT ON EFA_IN_ROW FOR EACH ROW
WHEN (NEW.ID IS NULL)
BEGIN
  SELECT EFA_IN_ROW_SEQ.NEXTVAL INTO :NEW.ID FROM dual;
END;
/

CREATE OR REPLACE PACKAGE EFA_INBOX AS
  -- RO: XML-ul facturii (Document/SupplierInfo, ambalat in Documents) -> TMDB_XML_FACTURA
  --     sub p_nrdoc: antet ROWN=0 CODE=0, pozitii ROWN=1..n, TIP_DOC=1, FILE_NAME
  --     completat ca export_xml (care ia doar file_name IS NULL) sa nu il atinga
  PROCEDURE land(p_nrdoc IN NUMBER, p_xml IN CLOB, p_file_name IN VARCHAR2);
  FUNCTION  reserve_nrdoc RETURN NUMBER;
  -- RO: publica pentru ca e folosita in SQL (PLS-00231 daca ar fi privata)
  FUNCTION  d(p IN VARCHAR2) RETURN DATE;
END EFA_INBOX;
/

CREATE OR REPLACE PACKAGE BODY EFA_INBOX AS

  FUNCTION d(p IN VARCHAR2) RETURN DATE IS
  BEGIN
    -- RO: 2020-06-11T16:17:09.8985986+03:00 -> doar primele 19 caractere (fara fractiuni si fus)
    IF p IS NULL THEN RETURN NULL; END IF;
    RETURN TRUNC(TO_DATE(SUBSTR(p, 1, 19), 'YYYY-MM-DD"T"HH24:MI:SS'));
  EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
  END d;

  FUNCTION reserve_nrdoc RETURN NUMBER IS
    v NUMBER;
  BEGIN
    -- RO: din secventa documentelor, ca sa nu se ciocneasca niciodata cu un COD real
    SELECT ID_TMDB_DOCS.NEXTVAL INTO v FROM dual;
    RETURN v;
  END reserve_nrdoc;

  PROCEDURE land(p_nrdoc IN NUMBER, p_xml IN CLOB, p_file_name IN VARCHAR2) IS
    x XMLTYPE := XMLTYPE(p_xml);
    r VARCHAR2(60) := '//Documents/Document/SupplierInfo/';
  BEGIN
    DELETE FROM TMDB_XML_FACTURA WHERE NRDOC = p_nrdoc;

    INSERT INTO TMDB_XML_FACTURA
      (NRDOC, ROWN, CODE, TIP_DOC, DATA_CREATE, FILE_NAME, DOCUMENTTYPE, DOCUMENTFORM,
       FACTURASERIA, FACTURANUMBER, ISSUEDDATE, DELIVERYDATE,
       BRANCHACCOUNT, BRANCHTITLE, BRANCHCODE, IDNO, TITLE, CODTVA, ADDRESS, TAXPAYERTYPE,
       BUYER_BRANCHACCOUNT, BUYER_BRANCHTITLE, BUYER_BRANCHCODE, BUYER_IDNO, BUYER_TITLE,
       BUYER_ADDRESS, BUYER_TAXPAYERTYPE, BUYER_CODTVA,
       TRANSPORTER_BRANCHACCOUNT, TRANSPORTER_BRANCHTITLE, TRANSPORTER_BRANCHCODE,
       TRANSPORTER_IDNO, TRANSPORTER_TITLE, TRANSPORTER_ADDRESS, TRANSPORTER_TAXPAYERTYPE,
       TRANSPORTER_CODTVA, ATTACHEDDOCUMENTS, NOTES, DELEGATESERIA, DELEGATENUMBER,
       DELEGATENAME, DELEGATEDATE, VEHICLELOGBOOK_ISSUEDDATE, VEHICLELOGBOOK_SERIA,
       VEHICLELOGBOOK_NUMBER, LOADINGPOINT, LOADINGPOINTCODE, UNLOADINGPOINT,
       UNLOADINGPOINTCODE, REDIRECTIONS, TOTAL, TTOTALTVA, ADDITIONALINFORMATION, CREATIONMOTIV)
    SELECT p_nrdoc, 0, '0', 1, SYSDATE, p_file_name,
       EXTRACTVALUE(x, r || '@DocumentType'), EXTRACTVALUE(x, r || '@DocumentForm'),
       EXTRACTVALUE(x, r || 'Seria'), EXTRACTVALUE(x, r || 'Number'),
       d(EXTRACTVALUE(x, r || 'IssuedDate')), d(EXTRACTVALUE(x, r || 'DeliveryDate')),
       SUBSTR(EXTRACTVALUE(x, r || 'Supplier/BankAccount/@Account'), 1, 29),
       SUBSTR(EXTRACTVALUE(x, r || 'Supplier/BankAccount/@BranchTitle'), 1, 160),
       SUBSTR(EXTRACTVALUE(x, r || 'Supplier/BankAccount/@BranchCode'), 1, 20),
       EXTRACTVALUE(x, r || 'Supplier/@IDNO'), SUBSTR(EXTRACTVALUE(x, r || 'Supplier/@Title'), 1, 160),
       SUBSTR(EXTRACTVALUE(x, r || 'Supplier/@CodTVA'), 1, 20),
       SUBSTR(EXTRACTVALUE(x, r || 'Supplier/@Address'), 1, 150),
       EXTRACTVALUE(x, r || 'Supplier/@TaxpayerType'),
       SUBSTR(EXTRACTVALUE(x, r || 'Buyer/BankAccount/@Account'), 1, 29),
       SUBSTR(EXTRACTVALUE(x, r || 'Buyer/BankAccount/@BranchTitle'), 1, 160),
       SUBSTR(EXTRACTVALUE(x, r || 'Buyer/BankAccount/@BranchCode'), 1, 20),
       EXTRACTVALUE(x, r || 'Buyer/@IDNO'), SUBSTR(EXTRACTVALUE(x, r || 'Buyer/@Title'), 1, 160),
       SUBSTR(EXTRACTVALUE(x, r || 'Buyer/@Address'), 1, 150),
       EXTRACTVALUE(x, r || 'Buyer/@TaxpayerType'), SUBSTR(EXTRACTVALUE(x, r || 'Buyer/@CodTVA'), 1, 20),
       SUBSTR(EXTRACTVALUE(x, r || 'Transporter/BankAccount/@Account'), 1, 29),
       SUBSTR(EXTRACTVALUE(x, r || 'Transporter/BankAccount/@BranchTitle'), 1, 160),
       SUBSTR(EXTRACTVALUE(x, r || 'Transporter/BankAccount/@BranchCode'), 1, 20),
       EXTRACTVALUE(x, r || 'Transporter/@IDNO'), SUBSTR(EXTRACTVALUE(x, r || 'Transporter/@Title'), 1, 160),
       SUBSTR(EXTRACTVALUE(x, r || 'Transporter/@Address'), 1, 150),
       EXTRACTVALUE(x, r || 'Transporter/@TaxpayerType'),
       SUBSTR(EXTRACTVALUE(x, r || 'Transporter/@CodTVA'), 1, 20),
       SUBSTR(EXTRACTVALUE(x, r || 'AttachedDocuments'), 1, 160), SUBSTR(EXTRACTVALUE(x, r || 'Notes'), 1, 160),
       SUBSTR(EXTRACTVALUE(x, r || 'DelegateSeria'), 1, 10), SUBSTR(EXTRACTVALUE(x, r || 'DelegateNumber'), 1, 50),
       SUBSTR(EXTRACTVALUE(x, r || 'DelegateName'), 1, 50), d(EXTRACTVALUE(x, r || 'DelegateDate')),
       d(EXTRACTVALUE(x, r || 'VehicleLogbook/@IssuedDate')),
       SUBSTR(EXTRACTVALUE(x, r || 'VehicleLogbook/@Seria'), 1, 10),
       SUBSTR(EXTRACTVALUE(x, r || 'VehicleLogbook/@Number'), 1, 50),
       SUBSTR(EXTRACTVALUE(x, r || 'LoadingPoint'), 1, 250), SUBSTR(EXTRACTVALUE(x, r || 'LoadingPointCode'), 1, 10),
       SUBSTR(EXTRACTVALUE(x, r || 'UnloadingPoint'), 1, 250), SUBSTR(EXTRACTVALUE(x, r || 'UnloadingPointCode'), 1, 10),
       SUBSTR(EXTRACTVALUE(x, r || 'Redirections'), 1, 250),
       EXTRACTVALUE(x, r || 'Total'), EXTRACTVALUE(x, r || 'TotalTVA'),
       SUBSTR(EXTRACTVALUE(x, '//Documents/Document/AdditionalInformation/field'), 1, 160),
       EXTRACTVALUE(x, r || 'CreationMotiv')
    FROM dual;

    INSERT INTO TMDB_XML_FACTURA
      (NRDOC, ROWN, TIP_DOC, DATA_CREATE, FILE_NAME, REFERRALDOCUMENT_SERIA, REFERRALDOCUMENT_NUMBER,
       BARCODE, CODE, NNAME, UNITOFMEASURE, QUANTITY, UNITPRICEWITHOUTTVA, TOTALPRICEWITHOUTTVA,
       TVA, TOTALTVA, TOTALPRICE, OTHERINFO, PACKAGETYPE, NUMBEROFPLACES, GROSSWEIGHT)
    SELECT p_nrdoc, ROWNUM, 1, SYSDATE, p_file_name,
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@RefDocSeria'), 1, 10),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@RefDocNumber'), 1, 50),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@BarCode'), 1, 15),
       SUBSTR(NVL(EXTRACTVALUE(VALUE(t), 'Row/@Code'), TO_CHAR(ROWNUM)), 1, 64),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@Name'), 1, 160),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@UnitOfMeasure'), 1, 10),
       EXTRACTVALUE(VALUE(t), 'Row/@Quantity'),
       EXTRACTVALUE(VALUE(t), 'Row/@UnitPriceWithoutTVA'),
       EXTRACTVALUE(VALUE(t), 'Row/@TotalPriceWithoutTVA'),
       EXTRACTVALUE(VALUE(t), 'Row/@TVA'), EXTRACTVALUE(VALUE(t), 'Row/@TotalTVA'),
       EXTRACTVALUE(VALUE(t), 'Row/@TotalPrice'),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@OtherInfo'), 1, 128),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@PackageType'), 1, 16),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@NumberOfPlaces'), 1, 16),
       SUBSTR(EXTRACTVALUE(VALUE(t), 'Row/@GrossWeight'), 1, 8)
    FROM TABLE(XMLSEQUENCE(x.EXTRACT(r || 'Merchandises/Row'))) t;
  END land;

END EFA_INBOX;
/
