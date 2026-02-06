-- Nufarul: колонка NAME_EN для поддержки английского названия услуги (RU/RO/EN).
-- Выполнить вручную для существующей БД, если таблица создана без NAME_EN.
-- Новые установки (14_nufarul_tables.sql) уже содержат NAME_EN — этот скрипт не нужен.
ALTER TABLE NUF_SERVICES ADD NAME_EN VARCHAR2(200);
COMMENT ON COLUMN NUF_SERVICES.NAME_EN IS 'Название услуги на английском (EN)';
