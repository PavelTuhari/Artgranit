MERGE INTO UNA_SHELL_PROJECTS t
USING (
    SELECT
        'decor' AS slug,
        'DECOR' AS name,
        'Стеклянные крыши / веранды / перголы (админка + оператор + ТЗ)' AS description,
        '09' AS dashboard_ids,
        40 AS sort_order
    FROM dual
) s
ON (UPPER(TRIM(t.SLUG)) = UPPER(TRIM(s.slug)))
WHEN MATCHED THEN UPDATE SET
    t.NAME = s.name,
    t.DESCRIPTION = s.description,
    t.DASHBOARD_IDS = s.dashboard_ids,
    t.SORT_ORDER = s.sort_order,
    t.IS_ACTIVE = 'Y',
    t.UPDATED_AT = SYSTIMESTAMP
WHEN NOT MATCHED THEN INSERT (
    ID, SLUG, NAME, DESCRIPTION, DASHBOARD_IDS, SORT_ORDER, IS_ACTIVE, CREATED_AT, UPDATED_AT
) VALUES (
    NVL((SELECT MAX(ID) + 1 FROM UNA_SHELL_PROJECTS), 1),
    s.slug, s.name, s.description, s.dashboard_ids, s.sort_order, 'Y', SYSTIMESTAMP, SYSTIMESTAMP
);
/
