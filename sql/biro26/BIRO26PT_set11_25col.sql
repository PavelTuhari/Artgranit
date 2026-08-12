-- =====================================================================
-- RO: Adaptare pentru fisiere LARGI (export de site) — set 11, birovits.md.
--     1) Stagin brut extins de la 16 la 32 de coloane. Fisierul are 25 de coloane,
--        iar cimpurile importante (image_main = c22, description = c24) cadeau
--        peste limita veche si se pierdeau TACUT.
--     2) Dictionar completat cu antetele in engleza ale exportului de site.
-- EN: Support for WIDE files (site exports) — set 11, birovits.md.
--     1) Raw staging widened from 16 to 32 columns; the file has 25 and the
--        important fields (image_main = c22, description = c24) silently fell
--        outside the old limit.
--     2) Dictionary extended with the site export's English headers.
--
-- RO: A se rula IMPREUNA cu versiunea noua a pachetului (g_max_cols = 32)
--     si a loader-ului (MAXCOL = 32).
-- EN: Run TOGETHER with the new package (g_max_cols = 32) and loader (MAXCOL = 32).
-- =====================================================================

ALTER TABLE biro26pt_raw ADD (
  c16 VARCHAR2(1000), c17 VARCHAR2(1000), c18 VARCHAR2(1000), c19 VARCHAR2(1000),
  c20 VARCHAR2(1000), c21 VARCHAR2(1000), c22 VARCHAR2(1000), c23 VARCHAR2(1000),
  c24 VARCHAR2(1000), c25 VARCHAR2(1000), c26 VARCHAR2(1000), c27 VARCHAR2(1000),
  c28 VARCHAR2(1000), c29 VARCHAR2(1000), c30 VARCHAR2(1000), c31 VARCHAR2(1000)
);

-- RO: antetele exportului de site / EN: the site export's headers
--     (prioritate mica = cistiga / lowest prio wins)
DECLARE
  TYPE t_rec IS RECORD (pat VARCHAR2(100), fld VARCHAR2(30), prio NUMBER);
  TYPE t_tab IS TABLE OF t_rec;
  v t_tab := t_tab(
    t_rec('name',                 'DENUMIRE',  12),
    t_rec('price',                'RETAIL',    12),
    t_rec('wholesale_price',      'ANGRO',      7),
    t_rec('image_main',           'URL',        8),
    t_rec('group2',               'CATEG',     10),
    -- RO: zgomot din export — explicit ignorat, ca sa nu fie luat drept altceva
    -- EN: export noise — explicitly ignored so it is not mistaken for something else
    t_rec('old_price',            'IGNORE',    10),
    t_rec('is_new',               'IGNORE',    10),
    t_rec('product_url',          'IGNORE',     9),
    t_rec('images_all',           'IGNORE',     9),
    t_rec('category_path',        'IGNORE',     9),
    t_rec('group3',               'IGNORE',    12),
    t_rec('page',                 'IGNORE',    10),
    t_rec('unit',                 'IGNORE',    10),
    t_rec('availability',         'IGNORE',    10),
    t_rec('in_stock',             'IGNORE',    10),
    t_rec('min_quantity',         'IGNORE',    10),
    t_rec('quantity_in_box',      'IGNORE',    10),
    t_rec('quantity_per_package', 'IGNORE',    10),
    t_rec('is_hit',               'IGNORE',    10),
    t_rec('is_promo',             'IGNORE',    10)
  );
BEGIN
  FOR i IN 1 .. v.COUNT LOOP
    DELETE FROM BIRO26PT_COLMAP WHERE pattern = v(i).pat;
    INSERT INTO BIRO26PT_COLMAP(pattern, logical_field, prio)
      VALUES (v(i).pat, v(i).fld, v(i).prio);
  END LOOP;
  COMMIT;
END;
/

-- RO: verificare / EN: check
SELECT pattern, logical_field, prio FROM BIRO26PT_COLMAP
 WHERE pattern IN ('name','price','wholesale_price','image_main','group2','description')
 ORDER BY prio;
