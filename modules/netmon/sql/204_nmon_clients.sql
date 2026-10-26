-- NMON_CLIENT: справочник клиентов для вкладки «Подключения клиентов».
-- Ставится своим установщиком modules/netmon/scripts/netmon_deploy.py.
-- Без точки с запятой и апострофов в комментариях: общий разборщик режет по ним.
--
-- Тип клиента вкладка определяет сама по тому, кто сейчас подключён к базе
-- (касса и база магазина, настольный UniAcc, сайт). Но клиент без подключений
-- в этот момент так не определится. Здесь тип закрепляется за клиентом
-- вручную, и тогда он стоит в своей группе всегда.
--
-- CLIENT_KEY — схема Oracle без служебного хвоста
-- (SANIX_BK, SANIX_WEB, SANIX_SALES относятся к клиенту SANIX).
-- KIND: shop — магазинник, back — прямой бэк (бухгалтерия или управленческий
-- учёт в настольном UniAcc), web — только сайт и интеграции, internal — наше.

CREATE TABLE NMON_CLIENT (
  CLIENT_KEY  VARCHAR2(60)        NOT NULL,
  KIND        VARCHAR2(10)        NOT NULL,
  TITLE       VARCHAR2(200 CHAR),
  NOTE        VARCHAR2(500 CHAR),
  UPDATED_AT  TIMESTAMP           DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_BY  VARCHAR2(60),
  CONSTRAINT PK_NMON_CLIENT PRIMARY KEY (CLIENT_KEY),
  CONSTRAINT CK_NMON_CLIENT_KIND CHECK (KIND IN ('shop', 'back', 'web', 'internal'))
);

-- Начальные записи от владельца 26.10.2026
INSERT INTO NMON_CLIENT (CLIENT_KEY, KIND, TITLE, NOTE, UPDATED_BY)
VALUES ('BIOHOLDA', 'back', 'Bioholda', 'Бухгалтерия в UniAcc', 'owner');

INSERT INTO NMON_CLIENT (CLIENT_KEY, KIND, TITLE, NOTE, UPDATED_BY)
VALUES ('SANIX', 'back', 'Sanix', 'Управленческий учёт в UniAcc', 'owner');
