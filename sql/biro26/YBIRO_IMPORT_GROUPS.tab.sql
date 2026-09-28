-- =====================================================================
-- RO: Evidenta GRUPELOR aduse de fiecare import — ca sa se stie din ce
--     incarcare a aparut fiecare grupa si ca sa poata fi anulata.
-- EN: Per-import record of the GROUPS a load brought in — so every group's
--     origin is known and can be rolled back.
--
-- ── De ce ── / ── Why ──
-- RO: Grupele intra tacut: un fisier nou aduce zeci de categorii noi in arbore
--     si nimeni nu mai stie, peste o luna, care de unde a venit si ce se
--     intimpla daca le stergi. Tabela raspunde la trei intrebari:
--       1. ce grupe a adus importul N?
--       2. grupa asta era deja acolo sau a creat-o importul?
--       3. cite marfuri atirna de ea acum (deci: se poate sterge?)
-- EN: Groups arrive silently: a new file adds dozens of tree categories and a
--     month later nobody knows which came from where, or what breaks if they
--     are removed. This table answers: what groups did import N bring, was the
--     group already there or created by that import, and how many goods hang
--     off it now (i.e. is it safe to drop).
--
-- RO: Instantaneul se exporta si ca FISIERE (CSV + SQL de anulare) in
--     `grupe_import/`, ca sa fie citibil si in afara bazei — vezi
--     scripts/gen_import_groups.py.
-- EN: The snapshot is also exported as FILES (CSV + rollback SQL) under
--     `grupe_import/`, readable outside the DB.
-- =====================================================================
SET SQLBLANKLINES ON

CREATE TABLE YBIRO_IMPORT_GROUPS (
  IMPORT_ID    NUMBER        NOT NULL,   -- RO: = YBIRO_IMPORT_LOG.IMPORT_ID
  SOURCE_CODE  VARCHAR2(30)  NOT NULL,   -- RO: = TMS_ORG_IMPSRC.SRC_CODE
  GROUP_PATH   VARCHAR2(400) NOT NULL,   -- RO: calea completa: "N1 > N2 > N3"
  GROUP1       VARCHAR2(160),            -- RO: nivelul 1 (= BIRO26_GOODS.GRUPA)
  GROUP2       VARCHAR2(160),            -- RO: nivelul 2 (= BIRO26_GOODS.CATEGORIE)
  GROUP3       VARCHAR2(160),            -- RO: nivelul 3 (doar in PRODUCT_TYPE deocamdata)
  ACTION       VARCHAR2(12)  NOT NULL,   -- RO: CREATED = grupa nu exista inainte; EXISTING = era deja
  N_PRODUCTS   NUMBER,                   -- RO: cite marfuri a pus importul in ea
  TREE_ID1     NUMBER,                   -- RO: nodul din arborele nativ (TMS_SYSGRPH.ID1), daca s-a creat
  CREATED_AT   DATE          DEFAULT SYSDATE,
  CONSTRAINT YBIRO_IMPORT_GROUPS_PK PRIMARY KEY (IMPORT_ID, GROUP_PATH),
  CONSTRAINT YBIRO_IMPORT_GROUPS_CK CHECK (ACTION IN ('CREATED','EXISTING'))
);

CREATE INDEX YBIRO_IMPORT_GROUPS_IX_SRC ON YBIRO_IMPORT_GROUPS (SOURCE_CODE, GROUP1);

COMMENT ON TABLE  YBIRO_IMPORT_GROUPS IS 'RO: ce grupe a adus fiecare import si daca le-a creat el / EN: which groups each import brought and whether it created them';
COMMENT ON COLUMN YBIRO_IMPORT_GROUPS.ACTION     IS 'RO: CREATED = grupa a aparut la acest import (candidata la anulare); EXISTING = exista deja';
COMMENT ON COLUMN YBIRO_IMPORT_GROUPS.N_PRODUCTS IS 'RO: cite marfuri a pus ACEST import in grupa (nu totalul grupei)';
