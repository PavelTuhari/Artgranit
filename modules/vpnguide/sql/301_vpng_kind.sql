-- VPNG_: тип ссылки. Кроме OpenVPN ссылкой выдаётся доступ L2TP/IPsec
-- на маршрутизатор MikroTik (06.10.2026). Для него на лету собираются
-- скрипт PowerShell для Windows и профиль .mobileconfig для macOS и iPhone,
-- поэтому в журнале открытий два новых вида.
-- Без точки с запятой в комментариях: общий разборщик режет по ней.

ALTER TABLE VPNG_SHARES ADD (KIND VARCHAR2(10) DEFAULT 'openvpn' NOT NULL);
ALTER TABLE VPNG_SHARES ADD CONSTRAINT CK_VPNG_SHARES_KIND CHECK (KIND IN ('openvpn','l2tp'));
ALTER TABLE VPNG_SHARE_HITS DROP CONSTRAINT CK_VPNG_HITS_KIND;
ALTER TABLE VPNG_SHARE_HITS ADD CONSTRAINT CK_VPNG_HITS_KIND
  CHECK (KIND IN ('page','profile','markdown','windows','apple'));
