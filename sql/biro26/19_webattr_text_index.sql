-- RO: index Oracle Text pe descrierile produselor (cautarea din magazin).
--     Fara el fiecare cautare citea toate cele 49.276 de descrieri CLOB
--     (DBMS_LOB.INSTR): 2,2-2,8 s la fiecare cerere. Cu index: 0,02-0,18 s,
--     rezultat IDENTIC (verificat pe hp/toner/ergonomic/creion/plastic/
--     birou/a4 — aceleasi multimi de COD-uri).
-- EN: Oracle Text index on product descriptions; without it every search
--     scanned all 49k description CLOBs (2.2-2.8 s), with it 0.02-0.18 s.
--
-- RO: SYNC (ON COMMIT) — indexul se actualizeaza singur dupa fiecare commit.
--     Alternativa (CTX_DDL.SYNC_INDEX periodic) NU e disponibila: utilizatorul
--     aplicatiei nu are rolul CTXAPP, iar pachetul CTXSYS.CTX_DDL nu se vede.
--     Indexul se creeaza insa fara acel rol, cu parametrii impliciti.
-- EN: SYNC (ON COMMIT) because CTX_DDL is not granted to the app user.
--
-- RO: dimensiune 25 MB pentru 18,6 MB de text; creare ~4 s.
-- EN: 25 MB index for 18.6 MB of text; built in ~4 s.
CREATE INDEX IX_WEBATTR_DESCR_RO ON TMS_MPT_WEBATTR (DESCRIERE_NON_DIACR_RO)
  INDEXTYPE IS CTXSYS.CONTEXT PARAMETERS ('SYNC (ON COMMIT)');

-- RO: verificare / EN: check
--   SELECT STATUS, DOMIDX_STATUS FROM USER_INDEXES
--    WHERE INDEX_NAME = 'IX_WEBATTR_DESCR_RO';   -- VALID / VALID
-- RO: stergere (revenire la scanare — codul o face automat) / EN: rollback
--   DROP INDEX IX_WEBATTR_DESCR_RO;
