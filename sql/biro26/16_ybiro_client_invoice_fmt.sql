-- =====================================================================
-- Biro26: preferinta PERSONALA a clientului pentru formatele contului
-- de plata (pdf/html/xlsx, lista separata prin virgula).
-- RO: implicit NULL = 'pdf' (toti clientii pornesc cu PDF); alegerea din
--     cos / cabinetul personal se salveaza si se refoloseste data
--     viitoare. Disponibilitatea HTML/XLSX o decide adminul
--     (YBIRO_SETTINGS: SHOP_FMT_HTML / SHOP_FMT_XLSX).
-- =====================================================================
ALTER TABLE YBIRO_CLIENT ADD (INVOICE_FMT VARCHAR2(20))
