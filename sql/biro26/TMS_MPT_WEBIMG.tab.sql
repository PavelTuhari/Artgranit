-- =====================================================================
-- RO: TMS_MPT_WEBIMG — imaginile SUPLIMENTARE ale marfii (galeria din magazin).
--     Tabela-satelit 1:N a dictionarului de marfa, aceeasi schema de cheie ca
--     TMS_MPT_BARCODE: COD este cheie STRAINA catre TMS_UNIVERS, iar unicitatea
--     e pe (COD, IMAGE_INDEX).
-- EN: TMS_MPT_WEBIMG — ADDITIONAL product images (shop gallery).
--     1:N satellite of the goods dictionary, same key schema as TMS_MPT_BARCODE:
--     COD is a FOREIGN key to TMS_UNIVERS, uniqueness is on (COD, IMAGE_INDEX).
--
-- ── De ce o tabela separata ── / ── Why a separate table ──
-- RO: TMS_MPT_TVR.IE_LINKADRES tine o SINGURA imagine (cea principala). Exporturile
--     de site dau si o galerie (officeshop: foaia "Images_2", 2 961 de randuri;
--     birovits: coloana "images_all", separator " | "). Fara aceasta tabela,
--     imaginile suplimentare nu au unde sa fie pastrate si se pierd la import.
-- EN: TMS_MPT_TVR.IE_LINKADRES holds a SINGLE (main) image. Site exports also carry
--     a gallery (officeshop: sheet "Images_2"; birovits: "images_all" column,
--     " | " separated). Without this table the extra images have nowhere to go.
--
-- RO: Imaginea PRINCIPALA ramine unde a fost — TMS_MPT_TVR.IE_LINKADRES. Aici intra
--     doar suplimentarele (IMAGE_INDEX >= 2), ca sa nu se dubleze.
-- EN: The MAIN image stays in TMS_MPT_TVR.IE_LINKADRES; only extras (IMAGE_INDEX >= 2)
--     go here, to avoid duplication.
--
--   TMS_UNIVERS (master, COD)
--        ├── TMS_MPT           (cartela: COD PK/FK)         1:1
--        ├── TMS_MPT_TVR       (imagine principala)         1:1
--        ├── TMS_MPT_WEBATTR   (atribute web)               1:1
--        ├── TMS_MPT_BARCODE   (coduri de bare)             1:N
--        └── TMS_MPT_WEBIMG    (imagini suplimentare)       1:N   <-- aceasta
-- =====================================================================
SET SQLBLANKLINES ON

CREATE TABLE TMS_MPT_WEBIMG (
  COD          NUMBER         NOT NULL,   -- RO: = TMS_UNIVERS.COD
  IMAGE_INDEX  NUMBER         NOT NULL,   -- RO: ordinea in galerie (2, 3, 4 ...)
  IMAGE_URL    VARCHAR2(1000) NOT NULL,   -- RO: adresa imaginii
  SRC          VARCHAR2(60),              -- RO: sursa: 'officeshop' / 'birovits'
  LOAD_ID      NUMBER,
  UPDATED_AT   DATE DEFAULT SYSDATE,
  CONSTRAINT TMS_MPT_WEBIMG_PK PRIMARY KEY (COD, IMAGE_INDEX),
  CONSTRAINT TMS_MPT_WEBIMG_FK FOREIGN KEY (COD) REFERENCES TMS_UNIVERS (COD)
);

CREATE INDEX TMS_MPT_WEBIMG_IX_COD ON TMS_MPT_WEBIMG (COD);

COMMENT ON TABLE  TMS_MPT_WEBIMG IS 'RO: imagini suplimentare (galerie) legate de TMS_UNIVERS.COD; imaginea principala ramine in TMS_MPT_TVR.IE_LINKADRES / EN: additional gallery images; the main image stays in TMS_MPT_TVR.IE_LINKADRES';
COMMENT ON COLUMN TMS_MPT_WEBIMG.COD         IS 'RO: cheie = TMS_UNIVERS.COD (ca la TMS_MPT_BARCODE)';
COMMENT ON COLUMN TMS_MPT_WEBIMG.IMAGE_INDEX IS 'RO: ordinea in galerie; 1 = principala (nu se stocheaza aici)';
COMMENT ON COLUMN TMS_MPT_WEBIMG.SRC         IS 'RO: site-ul sursa al exportului';
