-- Поиск по XWiki и OTRS — таблицы и полнотекстовый индекс.
-- База cloudbd (Oracle 11.2, CL8MSWIN1251), схема OTRS, префикс NMON_SRCH_.
-- Устанавливает modules/netmon/scripts/netmon_search_deploy.py.
--
-- Новых учёток и прав не создаём: OTRS уже читает XWIKI (SELECT ANY TABLE)
-- и вызывает Oracle Text (EXECUTE ANY PROCEDURE).
--
-- Индекс Oracle Text стоит на СВОЕЙ копии текстов (NMON_SRCH_DOC), а не на
-- ARTICLE: сломанный доменный индекс запрещает вставку в таблицу, и OTRS
-- перестал бы принимать письма. Таблицы OTRS и XWIKI только читаются.
--
-- Удалить всё: modules/netmon/sql/cloudbd/399_nmon_srch_drop.sql

-- Один документ поиска: заявка OTRS (все письма подряд) или страница XWiki
-- (каждый язык отдельно). Производные данные, источник правды — OTRS и XWIKI.
CREATE TABLE nmon_srch_doc (
  doc_id      NUMBER         NOT NULL,
  source      VARCHAR2(10)   NOT NULL,
  src_key     VARCHAR2(600)  NOT NULL,
  title       VARCHAR2(1000),
  url         VARCHAR2(2000) NOT NULL,
  body        CLOB,
  tn          VARCHAR2(50),
  queue       VARCHAR2(200),
  state       VARCHAR2(200),
  is_open     NUMBER(1)      DEFAULT 0 NOT NULL,
  customer    VARCHAR2(300),
  owner       VARCHAR2(100),
  space       VARCHAR2(300),
  lang        VARCHAR2(10),
  author      VARCHAR2(300),
  parts       NUMBER         DEFAULT 0 NOT NULL,
  created_at  DATE,
  changed_at  DATE,
  indexed_at  DATE           DEFAULT SYSDATE NOT NULL,
  CONSTRAINT nmon_srch_doc_pk PRIMARY KEY (doc_id),
  CONSTRAINT nmon_srch_doc_uk UNIQUE (source, src_key),
  CONSTRAINT nmon_srch_doc_src_ck CHECK (source IN ('OTRS', 'XWIKI'))
) TABLESPACE users;

CREATE SEQUENCE nmon_srch_doc_seq CACHE 100;

CREATE INDEX nmon_srch_doc_tn_ix ON nmon_srch_doc (tn) TABLESPACE users;

CREATE INDEX nmon_srch_doc_chg_ix ON nmon_srch_doc (source, changed_at) TABLESPACE users;

-- Состояние обновления индекса по каждому источнику. Строка источника
-- заодно служит замком: пока идёт обновление, второе не начинается.
CREATE TABLE nmon_srch_sync (
  source        VARCHAR2(10)  NOT NULL,
  last_change   DATE,
  last_id       NUMBER,
  run_started   DATE,
  last_run_at   DATE,
  last_full_at  DATE,
  docs          NUMBER,
  added         NUMBER,
  updated       NUMBER,
  removed       NUMBER,
  seconds       NUMBER,
  status        VARCHAR2(20)  DEFAULT 'new' NOT NULL,
  message       VARCHAR2(1000),
  CONSTRAINT nmon_srch_sync_pk PRIMARY KEY (source),
  CONSTRAINT nmon_srch_sync_st_ck CHECK (status IN ('new', 'running', 'ok', 'error'))
) TABLESPACE users;

INSERT INTO nmon_srch_sync (source) VALUES ('OTRS');

INSERT INTO nmon_srch_sync (source) VALUES ('XWIKI');

-- Журнал запросов — только добавление. По нему видно, что ищут и что не находится.
CREATE TABLE nmon_srch_log (
  log_id      NUMBER         NOT NULL,
  asked_at    DATE           DEFAULT SYSDATE NOT NULL,
  query       VARCHAR2(400),
  used_query  VARCHAR2(400),
  source      VARCHAR2(10),
  matched_by  VARCHAR2(30),
  hits        NUMBER,
  ms          NUMBER,
  CONSTRAINT nmon_srch_log_pk PRIMARY KEY (log_id)
) TABLESPACE users;

CREATE SEQUENCE nmon_srch_log_seq CACHE 20;

CREATE INDEX nmon_srch_log_at_ix ON nmon_srch_log (asked_at) TABLESPACE users;

-- Настройки Oracle Text. Повторный запуск пересоздаёт их, готовый индекс
-- держит свою копию настроек и от этого не страдает.
/
BEGIN
  FOR p IN (SELECT pre_name FROM ctx_user_preferences
             WHERE pre_name IN ('NMON_SRCH_LEXER', 'NMON_SRCH_WL')) LOOP
    ctx_ddl.drop_preference(p.pre_name);
  END LOOP;
  FOR s IN (SELECT spl_name FROM ctx_user_stoplists WHERE spl_name = 'NMON_SRCH_STOP') LOOP
    ctx_ddl.drop_stoplist(s.spl_name);
  END LOOP;
  FOR g IN (SELECT sgp_name FROM ctx_user_section_groups WHERE sgp_name = 'NMON_SRCH_SG') LOOP
    ctx_ddl.drop_section_group(g.sgp_name);
  END LOOP;

  -- Регистр не важен, буквы с диакритикой равны базовым (ё = е, ă = a).
  ctx_ddl.create_preference('NMON_SRCH_LEXER', 'BASIC_LEXER');
  ctx_ddl.set_attribute('NMON_SRCH_LEXER', 'MIXED_CASE', 'NO');
  ctx_ddl.set_attribute('NMON_SRCH_LEXER', 'BASE_LETTER', 'YES');

  -- Префиксный индекс — быстрый поиск по основе слова (принтер%),
  -- нечёткое сравнение — опечатки.
  ctx_ddl.create_preference('NMON_SRCH_WL', 'BASIC_WORDLIST');
  ctx_ddl.set_attribute('NMON_SRCH_WL', 'PREFIX_INDEX', 'TRUE');
  ctx_ddl.set_attribute('NMON_SRCH_WL', 'PREFIX_MIN_LENGTH', '3');
  ctx_ddl.set_attribute('NMON_SRCH_WL', 'PREFIX_MAX_LENGTH', '9');
  ctx_ddl.set_attribute('NMON_SRCH_WL', 'FUZZY_MATCH', 'GENERIC');
  ctx_ddl.set_attribute('NMON_SRCH_WL', 'FUZZY_SCORE', '60');
  ctx_ddl.set_attribute('NMON_SRCH_WL', 'FUZZY_NUMRESULTS', '40');
  ctx_ddl.set_attribute('NMON_SRCH_WL', 'WILDCARD_MAXTERMS', '15000');

  -- Служебные слова русского, румынского и английского.
  ctx_ddl.create_stoplist('NMON_SRCH_STOP', 'BASIC_STOPLIST');
  FOR w IN (SELECT column_value w FROM TABLE(sys.odcivarchar2list(
      'и', 'в', 'во', 'не', 'что', 'на', 'с', 'со', 'как', 'а', 'то', 'все', 'так', 'его', 'но',
      'да', 'к', 'у', 'же', 'за', 'бы', 'по', 'ее', 'было', 'от', 'о', 'из', 'ему', 'ли', 'если',
      'уже', 'или', 'ни', 'быть', 'был', 'до', 'вам', 'там', 'для', 'мы', 'их', 'чем', 'была',
      'без', 'под', 'будет', 'тогда', 'кто', 'этот', 'того', 'этого', 'при', 'об', 'это', 'эти',
      'при', 'над', 'через', 'про', 'вы', 'мне', 'нам', 'вас',
      'si', 'in', 'la', 'de', 'cu', 'pe', 'din', 'care', 'este', 'sa', 'nu', 'un', 'o',
      'pentru', 'ca', 'ai', 'al', 'ale', 'se', 'mai', 'sau', 'ce',
      'the', 'an', 'and', 'or', 'of', 'to', 'is', 'for', 'on', 'with', 're', 'fw', 'fwd'))) LOOP
    BEGIN
      ctx_ddl.add_stopword('NMON_SRCH_STOP', w.w);
    EXCEPTION WHEN OTHERS THEN NULL;  -- дубль в списке
    END;
  END LOOP;

  -- Разделы документа: T — заголовок, M — реквизиты (номер, клиент,
  -- очередь, раздел вики, файлы), B — текст. По ним поднимается вес.
  ctx_ddl.create_section_group('NMON_SRCH_SG', 'BASIC_SECTION_GROUP');
  ctx_ddl.add_zone_section('NMON_SRCH_SG', 'T', 'T');
  ctx_ddl.add_zone_section('NMON_SRCH_SG', 'M', 'M');
  ctx_ddl.add_zone_section('NMON_SRCH_SG', 'B', 'B');
END;
/

-- Синхронизация ручная: её делает nmon_srch.refresh после загрузки пачки.
CREATE INDEX nmon_srch_doc_ctx ON nmon_srch_doc (body) INDEXTYPE IS ctxsys.context
  PARAMETERS ('lexer nmon_srch_lexer wordlist nmon_srch_wl stoplist nmon_srch_stop section group nmon_srch_sg memory 200M');
