-- CRM: date reale din ERP (OfficePlus 11g) si separarea regimului demo.
-- Cerinta proprietarului 10.09.2026: in OfficePlus totul lucreaza pe Oracle,
-- marfa si clientii sint cei reali; regimul demo ramine separat.
--
-- Ideea: nomenclatorul REAL nu se copiaza in CRM (232 mii de pozitii in
-- TMS_UNIVERS ar fi o copie moarta a doua zi). Cautarea merge direct in
-- dictionarul ERP, iar pozitia folosita intr-o comanda se aduce in CRM_ITEM
-- o singura data, legata prin ERP_COD de TMS_UNIVERS.COD. Preturile si
-- stocul se reimprospateaza la cerere din TPR1D_PERPRLIST si BIRO26_GOODS.
--
-- Chiriasi: ('office',0) = datele reale OfficePlus, ('demo',0) = setul
-- demonstrativ, ('client',N) = cabinetul clientului. Nimic nu se amesteca.

ALTER TABLE CRM_ITEM ADD (
    SRC     VARCHAR2(10) DEFAULT 'crm' NOT NULL,
    ERP_COD NUMBER,
    SYNCED  DATE
)
/

-- RO: unic doar pentru pozitiile aduse din ERP. Cu coloanele simple,
-- rindurile proprii (ERP_COD gol) ar fi toate duplicate: OWNER_KIND si
-- OWNER_ID nu sint niciodata nule, deci cheia nu ar fi ignorata (ORA-01452).
CREATE UNIQUE INDEX UQ_CRM_ITEM_ERP ON CRM_ITEM (
    CASE WHEN ERP_COD IS NULL THEN NULL ELSE OWNER_KIND END,
    CASE WHEN ERP_COD IS NULL THEN NULL ELSE OWNER_ID END,
    ERP_COD)
/

ALTER TABLE CRM_CLIENT ADD (ERP_COD NUMBER)
/

CREATE INDEX IX_CRM_CLIENT_ERP ON CRM_CLIENT (OWNER_KIND, OWNER_ID, ERP_COD)
/
