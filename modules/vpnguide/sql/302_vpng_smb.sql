-- VPNG_: третий тип ссылки — сетевые диски файлового сервера 192.168.0.21
-- (06.10.2026). Получатель скачивает файл .cmd, который подключает диски
-- его роли, поэтому в журнале открытий новый вид cmd.
-- Без точки с запятой в комментариях: общий разборщик режет по ней.

ALTER TABLE VPNG_SHARES DROP CONSTRAINT CK_VPNG_SHARES_KIND;
ALTER TABLE VPNG_SHARES ADD CONSTRAINT CK_VPNG_SHARES_KIND CHECK (KIND IN ('openvpn','l2tp','smb'));
ALTER TABLE VPNG_SHARE_HITS DROP CONSTRAINT CK_VPNG_HITS_KIND;
ALTER TABLE VPNG_SHARE_HITS ADD CONSTRAINT CK_VPNG_HITS_KIND
  CHECK (KIND IN ('page','profile','markdown','windows','apple','cmd'));
