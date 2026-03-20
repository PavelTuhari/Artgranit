-- ============================================================
-- Удаление объектов (для переразвёртывания)
-- Выполнять перед 01..10 при необходимости чистой установки
-- ============================================================

BEGIN
  FOR r IN (SELECT object_name, object_type FROM user_objects
            WHERE object_type IN ('PACKAGE BODY','PACKAGE') AND object_name IN ('BUS_PKG','CRED_ADMIN_PKG','CRED_OPERATOR_PKG','CRED_REPORTS_PKG','CRED_REPORT_LOGIC_PKG')
            ORDER BY CASE object_type WHEN 'PACKAGE BODY' THEN 1 WHEN 'PACKAGE' THEN 2 END) LOOP
    EXECUTE IMMEDIATE 'DROP ' || r.object_type || ' ' || r.object_name;
  END LOOP;
END;
/

BEGIN
  FOR r IN (SELECT object_name FROM user_objects WHERE object_type = 'TRIGGER'
            AND object_name IN ('TR_BUS_DEPARTURES_BIU','TR_CRED_PROGRAMS_BIU','TR_CRED_APPLICATIONS_BIU',
                               'BUS_DEPARTURES_BI','CRED_BANKS_BI','CRED_CATEGORIES_BI','CRED_BRANDS_BI',
                               'CRED_PROGRAMS_BI','CRED_PRODUCTS_BI','CRED_APPLICATIONS_BI','CRED_REPORTS_BI','CRED_REPORT_PARAMS_BI')) LOOP
    EXECUTE IMMEDIATE 'DROP TRIGGER ' || r.object_name;
  END LOOP;
END;
/

BEGIN
  FOR r IN (SELECT view_name FROM user_views
            WHERE view_name IN ('V_BUS_DEPARTURES_TODAY','V_CRED_PROGRAMS','V_CRED_MATRIX','V_CRED_PRODUCTS','V_CRED_APPLICATIONS_RECENT')) LOOP
    EXECUTE IMMEDIATE 'DROP VIEW ' || r.view_name;
  END LOOP;
END;
/

BEGIN
  FOR r IN (SELECT table_name FROM user_tables WHERE table_name = 'UNA_SHELL_PROJECTS') LOOP
    EXECUTE IMMEDIATE 'DROP TABLE UNA_SHELL_PROJECTS CASCADE CONSTRAINTS';
  END LOOP;
  FOR r IN (SELECT table_name FROM user_tables WHERE table_name = 'CRED_REPORT_PARAMS') LOOP
    EXECUTE IMMEDIATE 'DROP TABLE CRED_REPORT_PARAMS CASCADE CONSTRAINTS';
  END LOOP;
  FOR r IN (SELECT table_name FROM user_tables WHERE table_name = 'CRED_REPORTS') LOOP
    EXECUTE IMMEDIATE 'DROP TABLE CRED_REPORTS CASCADE CONSTRAINTS';
  END LOOP;
  FOR r IN (SELECT table_name FROM user_tables
            WHERE table_name IN ('CRED_APPLICATIONS','CRED_PRODUCTS','CRED_PROGRAM_PRODUCTS','CRED_PROGRAM_EXCLUDED_BRANDS','CRED_PROGRAM_CATEGORIES',
                                'CRED_PROGRAMS','CRED_BRANDS','CRED_CATEGORIES','CRED_BANKS','BUS_DEPARTURES','BUS_ROUTES')) LOOP
    EXECUTE IMMEDIATE 'DROP TABLE ' || r.table_name || ' CASCADE CONSTRAINTS';
  END LOOP;
END;
/

BEGIN
  FOR r IN (SELECT sequence_name FROM user_sequences
            WHERE sequence_name IN ('BUS_DEPARTURES_SEQ','CRED_BANKS_SEQ','CRED_CATEGORIES_SEQ','CRED_BRANDS_SEQ',
                                    'CRED_PROGRAMS_SEQ','CRED_PRODUCTS_SEQ','CRED_APPLICATIONS_SEQ','CRED_REPORTS_SEQ','CRED_REPORT_PARAMS_SEQ','UNA_SHELL_PROJECTS_SEQ')) LOOP
    EXECUTE IMMEDIATE 'DROP SEQUENCE ' || r.sequence_name;
  END LOOP;
END;
/
