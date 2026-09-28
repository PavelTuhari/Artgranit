-- ============================================================
-- Colass CRM demo data
-- ============================================================

INSERT INTO CLS_CRM_LEADS (
  ID, LEAD_NO, SOURCE_ID, STAGE_ID, LANG_PREF,
  CONTACT_NAME, COMPANY_NAME, PHONE, EMAIL, LOCATION,
  SUBJECT, NEEDS_TEXT, BUDGET_AMOUNT, CURRENCY, EXPECTED_CLOSE_DATE,
  ASSIGNED_TO, PROJECT_ID, ESTIMATE_ID, EXTERNAL_REF, IS_ACTIVE
)
SELECT
  NULL,
  'LEAD-CLS-2026-0001',
  (SELECT ID FROM CLS_CRM_SOURCES WHERE CODE = 'EMAIL'),
  (SELECT ID FROM CLS_CRM_STAGES WHERE CODE = 'ESTIMATE_PREP'),
  'ro',
  'Ion Ceban',
  'Moldovagaz Contracting',
  '+37360000001',
  'ion.ceban@example.com',
  'Chișinău',
  'Cerere ofertă: extindere rețea gaze',
  'Avem nevoie de ofertă pentru extinderea rețelei de gaze, inclusiv terasamente, țeavă PE100 și montaj.',
  1250000,
  'MDL',
  TRUNC(SYSDATE) + 20,
  'operator.colass',
  (SELECT MIN(ID) FROM CLS_PROJECTS),
  (SELECT MIN(ID) FROM CLS_ESTIMATES),
  'DEMO-RO-001',
  'Y'
FROM dual
WHERE NOT EXISTS (SELECT 1 FROM CLS_CRM_LEADS WHERE LEAD_NO = 'LEAD-CLS-2026-0001');
/

INSERT INTO CLS_CRM_LEADS (
  ID, LEAD_NO, SOURCE_ID, STAGE_ID, LANG_PREF,
  CONTACT_NAME, COMPANY_NAME, PHONE, EMAIL, LOCATION,
  SUBJECT, NEEDS_TEXT, BUDGET_AMOUNT, CURRENCY, EXPECTED_CLOSE_DATE,
  ASSIGNED_TO, PROJECT_ID, ESTIMATE_ID, EXTERNAL_REF, IS_ACTIVE
)
SELECT
  NULL,
  'LEAD-CLS-2026-0002',
  (SELECT ID FROM CLS_CRM_SOURCES WHERE CODE = 'MANUAL'),
  (SELECT ID FROM CLS_CRM_STAGES WHERE CODE = 'QUALIFICATION'),
  'ru',
  'Павел Т.',
  'Artgranit Demo',
  '+37360000002',
  'sales@artgranit.example',
  'Бельцы',
  'Оферта на наружный газопровод',
  'Нужна оферта на объект с узлами врезки, сваркой, испытаниями и исполнительной документацией.',
  870000,
  'MDL',
  TRUNC(SYSDATE) + 12,
  'operator.colass',
  (SELECT MIN(ID) FROM CLS_PROJECTS),
  (SELECT MIN(ID) FROM CLS_ESTIMATES),
  'DEMO-RU-002',
  'Y'
FROM dual
WHERE NOT EXISTS (SELECT 1 FROM CLS_CRM_LEADS WHERE LEAD_NO = 'LEAD-CLS-2026-0002');
/

INSERT INTO CLS_CRM_ACTIVITIES (ID, LEAD_ID, ACTIVITY_TYPE, NOTE_TEXT, PAYLOAD_JSON, CREATED_BY)
SELECT
  NULL,
  l.ID,
  'NOTE',
  'Первичный контакт. Согласованы сроки подготовки оферты по F3/F5.',
  '{"channel":"phone","lang":"ru"}',
  'operator.colass'
FROM CLS_CRM_LEADS l
WHERE l.LEAD_NO = 'LEAD-CLS-2026-0002'
  AND NOT EXISTS (
    SELECT 1 FROM CLS_CRM_ACTIVITIES a
    WHERE a.LEAD_ID = l.ID AND a.ACTIVITY_TYPE = 'NOTE'
  );
/

COMMIT;
/
