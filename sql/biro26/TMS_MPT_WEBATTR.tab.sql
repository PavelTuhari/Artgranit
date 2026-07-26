-- =====================================================================
-- RO: TMS_MPT_WEBATTR — atribute WEB ale marfii (descriere, denumire completa).
--     Tabela-satelit a dictionarului de marfa, cu ACEEASI schema de cheie ca
--     TMS_MPT: COD = cheia primara SI cheia straina catre master-tabelul
--     TMS_UNIVERS (relatie 1:1, optionala — nu orice marfa are atribute web).
-- EN: TMS_MPT_WEBATTR — WEB attributes of goods (description, full name).
--     Satellite table of the goods dictionary, with the SAME key schema as
--     TMS_MPT: COD is both PK and FK to the master table TMS_UNIVERS
--     (1:1, optional — not every product has web attributes).
--
--   TMS_UNIVERS (master, COD)
--        ├── TMS_MPT           (cartela: COD PK/FK)      1:1
--        ├── TMS_MPT_TVR       (imagine, dimensiuni)     1:1
--        ├── TMS_MPT_BARCODE   (COD, BARCODE)            1:N
--        └── TMS_MPT_WEBATTR   (descriere web: COD PK/FK) 1:1   <-- aceasta
-- =====================================================================
CREATE TABLE TMS_MPT_WEBATTR (
  COD            NUMBER         NOT NULL,   -- RO: = TMS_UNIVERS.COD / EN: = TMS_UNIVERS.COD
  DESCRIERE      VARCHAR2(2000),            -- RO: descriere / caracteristici tehnice
  DENUMIRE_FULL  VARCHAR2(1000),            -- RO: denumirea completa a produsului
  SRC            VARCHAR2(60),              -- RO: sursa (furnizor / fisier) / EN: source
  LOAD_ID        NUMBER,                    -- RO: incarcarea care a scris randul
  UPDATED_AT     DATE DEFAULT SYSDATE,
  CONSTRAINT TMS_MPT_WEBATTR_PK PRIMARY KEY (COD),
  CONSTRAINT TMS_MPT_WEBATTR_FK FOREIGN KEY (COD) REFERENCES TMS_UNIVERS (COD)
);

COMMENT ON TABLE  TMS_MPT_WEBATTR IS 'RO: atribute web ale marfii (descriere, denumire completa); COD = TMS_UNIVERS.COD / EN: web attributes of goods';
COMMENT ON COLUMN TMS_MPT_WEBATTR.COD           IS 'RO: cheie = TMS_UNIVERS.COD (ca la TMS_MPT) / EN: key = TMS_UNIVERS.COD';
COMMENT ON COLUMN TMS_MPT_WEBATTR.DESCRIERE     IS 'RO: descriere / caracteristici pentru magazin / EN: shop description';
COMMENT ON COLUMN TMS_MPT_WEBATTR.DENUMIRE_FULL IS 'RO: denumire completa din fisierul furnizorului / EN: full product name from supplier file';
COMMENT ON COLUMN TMS_MPT_WEBATTR.SRC           IS 'RO: furnizor / fisier sursa / EN: supplier / source file';
