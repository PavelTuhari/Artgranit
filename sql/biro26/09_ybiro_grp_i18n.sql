-- =====================================================================
-- RO: Biro26/OfficePlus — traducerile RU/EN ale GRUPARII catalogului
--     (grupa/categorie din BIRO26_GOODS) ca DATE EDITABILE, dupa
--     principiul una-shops (unisimNginx/una-shops-translations-guide):
--     dictionar separat + fallback pe romana cind traducerea lipseste.
--     Cheia = textul romanesc (gruparea e pe siruri, fara id-uri).
-- EN: RU/EN translations of the catalog GROUPING as editable data
--     (una-shops guide principle): dictionary table + RO fallback.
-- Charset DB: CL8MSWIN1251 — kirilica DOAR prin python-oracledb.
-- Editare ulterioara (date, nu cod):
--   UPDATE YBIRO_GRP_I18N SET NAME_RU='...' WHERE KIND='categorie' AND NAME_RO='...';
--   INSERT INTO YBIRO_GRP_I18N (KIND,NAME_RO,NAME_RU,NAME_EN) VALUES ('categorie','<ro>','<ru>','<en>');
-- =====================================================================

CREATE TABLE YBIRO_GRP_I18N (
  KIND     VARCHAR2(10) NOT NULL,     -- 'grupa' | 'categorie'
  NAME_RO  VARCHAR2(200) NOT NULL,    -- cheia: textul RO din BIRO26_GOODS
  NAME_RU  VARCHAR2(200),
  NAME_EN  VARCHAR2(200),
  CONSTRAINT PK_YBIRO_GRP_I18N PRIMARY KEY (KIND, NAME_RO)
);
