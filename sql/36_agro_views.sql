-- ============================================================
-- AGRO module — report views
-- File:   36_agro_views.sql
-- Views:  5
--
--   1. AGRO_V_STOCK_BALANCE   — stock balance per batch/warehouse/item
--   2. AGRO_V_PURCHASES       — purchase document summary
--   3. AGRO_V_SALES           — sales document summary
--   4. AGRO_V_MASS_BALANCE    — mass balance per item
--   5. AGRO_V_CELL_READINGS   — latest temperature/humidity per cell
-- ============================================================

-- ------------------------------------------------------------
-- 1. AGRO_V_STOCK_BALANCE
--    Stock balance per batch/warehouse/item.
--    Only active and blocked batches.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW AGRO_V_STOCK_BALANCE AS
SELECT
    b.ID                AS BATCH_ID,
    b.BATCH_NUMBER,
    b.ITEM_ID,
    i.NAME_RU           AS ITEM_NAME_RU,
    i.NAME_RO           AS ITEM_NAME_RO,
    i.ITEM_GROUP,
    b.WAREHOUSE_ID,
    w.NAME              AS WAREHOUSE_NAME,
    b.CELL_ID,
    c.NAME              AS CELL_NAME,
    b.CURRENT_QTY_KG,
    b.STATUS            AS BATCH_STATUS,
    b.RECEIVED_AT,
    b.EXPIRY_DATE,
    CASE WHEN b.EXPIRY_DATE < TRUNC(SYSDATE) THEN 'Y' ELSE 'N' END  AS IS_EXPIRED,
    CASE WHEN b.STATUS = 'blocked'            THEN 'Y' ELSE 'N' END  AS IS_BLOCKED
FROM AGRO_BATCHES b
JOIN AGRO_ITEMS           i ON i.ID = b.ITEM_ID
LEFT JOIN AGRO_WAREHOUSES w ON w.ID = b.WAREHOUSE_ID
LEFT JOIN AGRO_STORAGE_CELLS c ON c.ID = b.CELL_ID
WHERE b.STATUS IN ('active', 'blocked');
/

-- ------------------------------------------------------------
-- 2. AGRO_V_PURCHASES
--    Purchase document summary with supplier and currency.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW AGRO_V_PURCHASES AS
SELECT
    pd.ID               AS DOC_ID,
    pd.DOC_NUMBER,
    pd.DOC_DATE,
    s.NAME              AS SUPPLIER_NAME,
    w.NAME              AS WAREHOUSE_NAME,
    pd.STATUS,
    pd.TOTAL_GROSS_KG,
    pd.TOTAL_NET_KG,
    pd.TOTAL_AMOUNT,
    cur.CODE            AS CURRENCY_CODE,
    pd.CREATED_BY,
    pd.CREATED_AT
FROM AGRO_PURCHASE_DOCS pd
JOIN AGRO_SUPPLIERS       s   ON s.ID   = pd.SUPPLIER_ID
JOIN AGRO_WAREHOUSES      w   ON w.ID   = pd.WAREHOUSE_ID
LEFT JOIN AGRO_CURRENCIES cur ON cur.ID = pd.CURRENCY_ID;
/

-- ------------------------------------------------------------
-- 3. AGRO_V_SALES
--    Sales document summary with customer and currency.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW AGRO_V_SALES AS
SELECT
    sd.ID               AS DOC_ID,
    sd.DOC_NUMBER,
    sd.DOC_DATE,
    c.NAME              AS CUSTOMER_NAME,
    c.CUSTOMER_TYPE,
    w.NAME              AS WAREHOUSE_NAME,
    sd.SALE_TYPE,
    sd.STATUS,
    sd.TOTAL_GROSS_KG,
    sd.TOTAL_NET_KG,
    sd.TOTAL_AMOUNT,
    cur.CODE            AS CURRENCY_CODE,
    sd.CREATED_BY,
    sd.CREATED_AT
FROM AGRO_SALES_DOCS sd
JOIN AGRO_CUSTOMERS       c   ON c.ID   = sd.CUSTOMER_ID
LEFT JOIN AGRO_WAREHOUSES w   ON w.ID   = sd.WAREHOUSE_ID
LEFT JOIN AGRO_CURRENCIES cur ON cur.ID = sd.CURRENCY_ID;
/

-- ------------------------------------------------------------
-- 4. AGRO_V_MASS_BALANCE
--    Mass balance per active item:
--      purchased  — NET_WEIGHT_KG from confirmed/closed purchase lines
--      stock      — CURRENT_QTY_KG from active/blocked batches
--      sold       — NET_WEIGHT_KG from confirmed+ sales lines
--      losses     — QTY_KG from stock movements of type 'loss'
--      waste      — WASTE_QTY_KG from completed processing tasks
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW AGRO_V_MASS_BALANCE AS
SELECT
    i.ID                AS ITEM_ID,
    i.NAME_RU           AS ITEM_NAME_RU,
    i.ITEM_GROUP,
    NVL(pur.PURCHASED_KG, 0)     AS PURCHASED_KG,
    NVL(stk.CURRENT_STOCK_KG, 0) AS CURRENT_STOCK_KG,
    NVL(sld.SOLD_KG, 0)          AS SOLD_KG,
    NVL(los.LOSS_KG, 0)          AS LOSS_KG,
    NVL(wst.WASTE_KG, 0)         AS WASTE_KG
FROM AGRO_ITEMS i
-- purchased
LEFT JOIN (
    SELECT pl.ITEM_ID,
           SUM(pl.NET_WEIGHT_KG) AS PURCHASED_KG
    FROM AGRO_PURCHASE_LINES pl
    JOIN AGRO_PURCHASE_DOCS  pd ON pd.ID = pl.PURCHASE_DOC_ID
    WHERE pd.STATUS IN ('confirmed', 'closed')
    GROUP BY pl.ITEM_ID
) pur ON pur.ITEM_ID = i.ID
-- current stock
LEFT JOIN (
    SELECT b.ITEM_ID,
           SUM(b.CURRENT_QTY_KG) AS CURRENT_STOCK_KG
    FROM AGRO_BATCHES b
    WHERE b.STATUS IN ('active', 'blocked')
    GROUP BY b.ITEM_ID
) stk ON stk.ITEM_ID = i.ID
-- sold
LEFT JOIN (
    SELECT sl.ITEM_ID,
           SUM(sl.NET_WEIGHT_KG) AS SOLD_KG
    FROM AGRO_SALES_LINES sl
    JOIN AGRO_SALES_DOCS  sd ON sd.ID = sl.SALES_DOC_ID
    WHERE sd.STATUS IN ('confirmed', 'shipped', 'closed')
    GROUP BY sl.ITEM_ID
) sld ON sld.ITEM_ID = i.ID
-- losses
LEFT JOIN (
    SELECT b.ITEM_ID,
           SUM(sm.QTY_KG) AS LOSS_KG
    FROM AGRO_STOCK_MOVEMENTS sm
    JOIN AGRO_BATCHES         b ON b.ID = sm.BATCH_ID
    WHERE sm.MOVEMENT_TYPE = 'loss'
    GROUP BY b.ITEM_ID
) los ON los.ITEM_ID = i.ID
-- waste
LEFT JOIN (
    SELECT b.ITEM_ID,
           SUM(pt.WASTE_QTY_KG) AS WASTE_KG
    FROM AGRO_PROCESSING_TASKS pt
    JOIN AGRO_BATCHES           b ON b.ID = pt.BATCH_ID
    WHERE pt.STATUS = 'completed'
    GROUP BY b.ITEM_ID
) wst ON wst.ITEM_ID = i.ID
WHERE i.ACTIVE = 'Y';
/

-- ------------------------------------------------------------
-- 5. AGRO_V_CELL_READINGS
--    Latest sensor/manual reading per storage cell with
--    out-of-range flags for temperature and humidity.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW AGRO_V_CELL_READINGS AS
SELECT
    r.ID                AS READING_ID,
    r.CELL_ID,
    sc.CODE             AS CELL_CODE,
    sc.NAME             AS CELL_NAME,
    w.NAME              AS WAREHOUSE_NAME,
    r.TEMPERATURE_C,
    r.HUMIDITY_PCT,
    r.O2_PCT,
    r.CO2_PCT,
    r.READING_SOURCE,
    r.SENSOR_ID,
    r.RECORDED_BY,
    r.RECORDED_AT,
    sc.TEMP_MIN,
    sc.TEMP_MAX,
    sc.HUMIDITY_MIN,
    sc.HUMIDITY_MAX,
    CASE
        WHEN r.TEMPERATURE_C < sc.TEMP_MIN OR r.TEMPERATURE_C > sc.TEMP_MAX
        THEN 'Y' ELSE 'N'
    END AS TEMP_OUT_OF_RANGE,
    CASE
        WHEN r.HUMIDITY_PCT < sc.HUMIDITY_MIN OR r.HUMIDITY_PCT > sc.HUMIDITY_MAX
        THEN 'Y' ELSE 'N'
    END AS HUMIDITY_OUT_OF_RANGE
FROM AGRO_STORAGE_READINGS r
JOIN (
    SELECT CELL_ID,
           MAX(RECORDED_AT) AS MAX_RECORDED_AT
    FROM AGRO_STORAGE_READINGS
    GROUP BY CELL_ID
) latest ON latest.CELL_ID = r.CELL_ID AND latest.MAX_RECORDED_AT = r.RECORDED_AT
JOIN AGRO_STORAGE_CELLS sc ON sc.ID = r.CELL_ID
JOIN AGRO_WAREHOUSES     w ON w.ID  = sc.WAREHOUSE_ID;
/

-- ============================================================
-- 6. AGRO_V_FIELD_REQUESTS — field request summary with line counts
-- ============================================================

CREATE OR REPLACE VIEW AGRO_V_FIELD_REQUESTS AS
SELECT
    fr.ID,
    fr.REQUEST_NUMBER,
    fr.SUPPLIER_ID,
    s.NAME AS SUPPLIER_NAME,
    fr.WAREHOUSE_ID,
    w.NAME AS WAREHOUSE_NAME,
    fr.EXPECTED_DATE,
    fr.PROFILE_ID,
    ap.NAME_RU AS PROFILE_NAME,
    fr.STATUS,
    fr.APPROVED_BY,
    fr.APPROVED_AT,
    fr.NOTES,
    fr.CREATED_AT,
    NVL(lc.LINE_COUNT, 0) AS LINE_COUNT,
    NVL(lc.TOTAL_EXPECTED_KG, 0) AS TOTAL_EXPECTED_KG
FROM AGRO_FIELD_REQUESTS fr
LEFT JOIN AGRO_SUPPLIERS s ON s.ID = fr.SUPPLIER_ID
LEFT JOIN AGRO_WAREHOUSES w ON w.ID = fr.WAREHOUSE_ID
LEFT JOIN AGRO_ACCEPTANCE_PROFILES ap ON ap.ID = fr.PROFILE_ID
LEFT JOIN (
    SELECT FIELD_REQUEST_ID,
           COUNT(*) AS LINE_COUNT,
           SUM(EXPECTED_QTY_KG) AS TOTAL_EXPECTED_KG
    FROM AGRO_FIELD_REQUEST_LINES
    GROUP BY FIELD_REQUEST_ID
) lc ON lc.FIELD_REQUEST_ID = fr.ID;
/

-- ============================================================
-- 7. AGRO_V_BATCH_INSPECTIONS — inspection results with item/profile info
-- ============================================================

CREATE OR REPLACE VIEW AGRO_V_BATCH_INSPECTIONS AS
SELECT
    bi.ID,
    bi.BATCH_ID,
    b.BATCH_NUMBER,
    b.ITEM_ID,
    i.NAME_RU AS ITEM_NAME,
    i.CODE AS ITEM_CODE,
    bi.PROFILE_ID,
    ap.NAME_RU AS PROFILE_NAME,
    bi.INSPECTION_DATE,
    bi.INSPECTED_BY,
    bi.TOTAL_SCORE,
    bi.CRITICAL_FAILS,
    bi.DECISION,
    bi.NOTES,
    bi.CREATED_AT
FROM AGRO_BATCH_INSPECTIONS bi
JOIN AGRO_BATCHES b ON b.ID = bi.BATCH_ID
JOIN AGRO_ITEMS i ON i.ID = b.ITEM_ID
JOIN AGRO_ACCEPTANCE_PROFILES ap ON ap.ID = bi.PROFILE_ID;
/

-- ============================================================
-- End of AGRO module views
-- ============================================================
