-- Удаление поиска по XWiki и OTRS из схемы OTRS базы cloudbd.
-- Запускать вручную и только намеренно:
--   python modules/netmon/scripts/netmon_search_deploy.py --drop
-- Таблицы OTRS и XWIKI не затрагиваются: удаляются только объекты NMON_SRCH_.

DROP PACKAGE nmon_srch;

DROP TYPE nmon_srch_hits FORCE;

DROP TYPE nmon_srch_hit FORCE;

DROP INDEX nmon_srch_doc_ctx FORCE;

DROP TABLE nmon_srch_doc PURGE;

DROP TABLE nmon_srch_sync PURGE;

DROP TABLE nmon_srch_log PURGE;

DROP SEQUENCE nmon_srch_doc_seq;

DROP SEQUENCE nmon_srch_log_seq;
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
END;
/
