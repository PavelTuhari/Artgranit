-- Унификация клиентов: один клиент — от заявок OTRS до схем в базе.
-- База cloudbd (Oracle 11.2), схема OTRS, префикс NMON_CLI_.
-- Ставит modules/netmon/scripts/netmon_search_deploy.py, заполняет
-- modules/netmon/unify.py. Таблицы OTRS, UNI и схем клиентов только читаются.
--
-- Зачем. Один и тот же клиент записан по-разному в пяти местах.
-- В заявках OTRS — свободным текстом (FASTSERVICE SRL), у его логина в OTRS —
-- код контрагента COD_UNIV, в нашей бухгалтерии (UNI.TMS_UNIVERS) — юрлицо с
-- фискальным кодом, в базе — одна или несколько схем (SANIX, SANIX_BK,
-- SANIX_WEB), а в подключениях — точки магазинов, кассы, сайт и рабочие места.
-- Здесь всё это сведено к одной строке NMON_CLI.
--
-- ORIGIN auto — заполнено сопоставлением, manual — поправлено человеком.
-- Автоматика строки manual не перезаписывает.

CREATE SEQUENCE nmon_cli_seq;

-- Клиент
CREATE TABLE nmon_cli (
  cli_id      NUMBER         NOT NULL,
  code        VARCHAR2(60)   NOT NULL,
  name        VARCHAR2(300),
  idno        VARCHAR2(30),
  cod_univ    NUMBER,
  kind        VARCHAR2(10)   DEFAULT 'none' NOT NULL,
  status      VARCHAR2(10)   DEFAULT 'active' NOT NULL,
  manager     VARCHAR2(100),
  contract    VARCHAR2(100),
  note        VARCHAR2(500),
  origin      VARCHAR2(10)   DEFAULT 'auto' NOT NULL,
  created_at  DATE           DEFAULT SYSDATE NOT NULL,
  updated_at  DATE           DEFAULT SYSDATE NOT NULL,
  updated_by  VARCHAR2(60),
  CONSTRAINT nmon_cli_pk PRIMARY KEY (cli_id),
  CONSTRAINT nmon_cli_code_uk UNIQUE (code),
  CONSTRAINT nmon_cli_kind_ck CHECK (kind IN ('shop', 'back', 'web', 'internal', 'none')),
  CONSTRAINT nmon_cli_status_ck CHECK (status IN ('active', 'paused', 'archived')),
  CONSTRAINT nmon_cli_origin_ck CHECK (origin IN ('auto', 'manual'))
) TABLESPACE users;

-- Заказчик в заявках OTRS (ticket.customer_id) — свободный текст, вариантов много
CREATE TABLE nmon_cli_otrs (
  otrs_customer_id  VARCHAR2(150)  NOT NULL,
  cli_id            NUMBER         NOT NULL,
  match_by          VARCHAR2(20)   NOT NULL,
  score             NUMBER(3)      DEFAULT 0 NOT NULL,
  origin            VARCHAR2(10)   DEFAULT 'auto' NOT NULL,
  CONSTRAINT nmon_cli_otrs_pk PRIMARY KEY (otrs_customer_id),
  CONSTRAINT nmon_cli_otrs_cli_fk FOREIGN KEY (cli_id) REFERENCES nmon_cli (cli_id)
) TABLESPACE users;

CREATE INDEX nmon_cli_otrs_cli_ix ON nmon_cli_otrs (cli_id) TABLESPACE users;

-- Логин клиента в OTRS (customer_user.login) и его код контрагента
CREATE TABLE nmon_cli_login (
  customer_login  VARCHAR2(100)  NOT NULL,
  cli_id          NUMBER         NOT NULL,
  cod_univ        NUMBER,
  origin          VARCHAR2(10)   DEFAULT 'auto' NOT NULL,
  CONSTRAINT nmon_cli_login_pk PRIMARY KEY (customer_login),
  CONSTRAINT nmon_cli_login_cli_fk FOREIGN KEY (cli_id) REFERENCES nmon_cli (cli_id)
) TABLESPACE users;

-- Схема клиента в базе и её роль
-- ROLE: back — основной бэк-офис, hr — кадры, sales — продажи, web — сайт,
-- scales — весы, pos — кассы, cont — бухгалтерия отдельно, rep — отчёты,
-- bk — резервная копия, test — тестовая, year — база прошлого года, other
CREATE TABLE nmon_cli_schema (
  db           VARCHAR2(20)   NOT NULL,
  schema_name  VARCHAR2(128)  NOT NULL,
  cli_id       NUMBER         NOT NULL,
  role         VARCHAR2(10)   DEFAULT 'back' NOT NULL,
  match_by     VARCHAR2(20),
  logons_30d   NUMBER         DEFAULT 0 NOT NULL,
  last_logon   DATE,
  created      DATE,
  origin       VARCHAR2(10)   DEFAULT 'auto' NOT NULL,
  CONSTRAINT nmon_cli_schema_pk PRIMARY KEY (db, schema_name),
  CONSTRAINT nmon_cli_schema_cli_fk FOREIGN KEY (cli_id) REFERENCES nmon_cli (cli_id),
  CONSTRAINT nmon_cli_schema_role_ck CHECK (role IN ('back', 'hr', 'sales', 'web', 'scales', 'pos', 'cont',
                                                     'rep', 'bk', 'test', 'year', 'other'))
) TABLESPACE users;

CREATE INDEX nmon_cli_schema_cli_ix ON nmon_cli_schema (cli_id) TABLESPACE users;

-- Точка клиента: магазин (своя база), касса, весы, сайт, рабочее место офиса
-- HOST — имя компьютера, как его видит база, OS_USER — пользователь Windows
CREATE TABLE nmon_cli_point (
  point_id    NUMBER         NOT NULL,
  cli_id      NUMBER         NOT NULL,
  kind        VARCHAR2(10)   NOT NULL,
  host        VARCHAR2(255)  NOT NULL,
  os_user     VARCHAR2(255),
  name        VARCHAR2(200),
  address     VARCHAR2(300),
  first_seen  DATE,
  last_seen   DATE,
  days_30d    NUMBER         DEFAULT 0 NOT NULL,
  logons_30d  NUMBER         DEFAULT 0 NOT NULL,
  origin      VARCHAR2(10)   DEFAULT 'auto' NOT NULL,
  CONSTRAINT nmon_cli_point_pk PRIMARY KEY (point_id),
  CONSTRAINT nmon_cli_point_uk UNIQUE (cli_id, kind, host),
  CONSTRAINT nmon_cli_point_cli_fk FOREIGN KEY (cli_id) REFERENCES nmon_cli (cli_id),
  CONSTRAINT nmon_cli_point_kind_ck CHECK (kind IN ('shop', 'pos', 'scales', 'office', 'web', 'server'))
) TABLESPACE users;

CREATE SEQUENCE nmon_cli_point_seq;

-- Продукты и модули, которыми пользуется клиент, и откуда это известно
CREATE TABLE nmon_cli_product (
  cli_id      NUMBER         NOT NULL,
  product     VARCHAR2(60)   NOT NULL,
  evidence    VARCHAR2(300),
  first_seen  DATE,
  last_seen   DATE,
  origin      VARCHAR2(10)   DEFAULT 'auto' NOT NULL,
  CONSTRAINT nmon_cli_product_pk PRIMARY KEY (cli_id, product),
  CONSTRAINT nmon_cli_product_cli_fk FOREIGN KEY (cli_id) REFERENCES nmon_cli (cli_id)
) TABLESPACE users;

-- Несостыковки, найденные при сопоставлении: что поправить в OTRS или в учёте
CREATE TABLE nmon_cli_issue (
  issue_id    NUMBER         NOT NULL,
  cli_id      NUMBER,
  kind        VARCHAR2(30)   NOT NULL,
  subject     VARCHAR2(200)  NOT NULL,
  detail      VARCHAR2(1000),
  found_at    DATE           DEFAULT SYSDATE NOT NULL,
  resolved    NUMBER(1)      DEFAULT 0 NOT NULL,
  CONSTRAINT nmon_cli_issue_pk PRIMARY KEY (issue_id),
  CONSTRAINT nmon_cli_issue_uk UNIQUE (kind, subject)
) TABLESPACE users;

CREATE SEQUENCE nmon_cli_issue_seq;

-- Клиент одной строкой с заявками OTRS — для отчётов в самом OTRS
CREATE OR REPLACE VIEW nmon_cli_v AS
SELECT c.cli_id, c.code, c.name, c.idno, c.cod_univ, c.kind, c.status, c.manager, c.contract,
       (SELECT COUNT(*) FROM nmon_cli_schema s WHERE s.cli_id = c.cli_id) schemas,
       (SELECT COUNT(*) FROM nmon_cli_point p WHERE p.cli_id = c.cli_id AND p.kind IN ('shop', 'pos', 'scales')) shop_points,
       (SELECT COUNT(*) FROM nmon_cli_point p WHERE p.cli_id = c.cli_id AND p.kind = 'office') workplaces,
       (SELECT COUNT(*) FROM ticket t, nmon_cli_otrs o WHERE o.cli_id = c.cli_id AND t.customer_id = o.otrs_customer_id) tickets,
       (SELECT COUNT(*) FROM ticket t, nmon_cli_otrs o, ticket_state ts, ticket_state_type st
         WHERE o.cli_id = c.cli_id AND t.customer_id = o.otrs_customer_id AND ts.id = t.ticket_state_id
           AND st.id = ts.type_id AND st.name IN ('new', 'open', 'pending reminder', 'pending auto')) tickets_open,
       (SELECT MAX(t.create_time) FROM ticket t, nmon_cli_otrs o
         WHERE o.cli_id = c.cli_id AND t.customer_id = o.otrs_customer_id) last_ticket
  FROM nmon_cli c;
