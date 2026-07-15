-- =====================================================================
-- RO: Biro26/OfficePlus — metadatele documentului web (contul de plata):
--     modul TVA ales la generare: 'inclus' (TVA 20% inclus in pret,
--     implicit) / '0' (TVA 0%) / 'fara' (fara TVA). Formularele PDF
--     citesc modul si afiseaza rindul TVA corespunzator.
-- EN: web-document metadata: the VAT mode chosen at invoice generation
--     ('inclus' default / '0' / 'fara'); the PDF forms render the VAT
--     row accordingly.
-- Prefix: YBIRO_. Charset DB: CL8MSWIN1251 — apply via python-oracledb.
-- =====================================================================

CREATE TABLE YBIRO_DOC_META (
  DOC_COD   NUMBER NOT NULL,           -- TMDB_DOCS.COD
  TVA_MODE  VARCHAR2(10) DEFAULT 'inclus',
  CREATED   DATE DEFAULT SYSDATE,
  CONSTRAINT PK_YBIRO_DOC_META PRIMARY KEY (DOC_COD)
);
