-- Добавить дашборд 03 (Табло отправлений) в проект gara
UPDATE UNA_SHELL_PROJECTS
SET DASHBOARD_IDS = '00,01,02,03',
    UPDATED_AT = CURRENT_TIMESTAMP
WHERE SLUG = 'gara';
COMMIT;
/
