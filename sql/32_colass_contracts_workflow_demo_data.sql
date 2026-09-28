-- ============================================================
-- Colass contracts workflow demo data
-- ============================================================

INSERT INTO CLS_CONTRACT_ATTACHMENTS (
  ID, CONTRACT_ID, TYPE_CODE, TYPE_NAME_RU, TYPE_NAME_RO,
  FILE_NAME, MIME_TYPE, FILE_SIZE, FILE_BLOB, IS_ACTIVE, UPLOADED_BY
)
SELECT
  NULL,
  c.ID,
  'FINANCIAL_TERMS',
  'Финансовые условия',
  'Conditii financiare',
  'financial_terms_demo.txt',
  'text/plain',
  32,
  UTL_RAW.CAST_TO_RAW('Demo financial terms for contract'),
  'Y',
  'demo'
FROM CLS_CONTRACTS c
WHERE c.CONTRACT_NO = 'CLS-CON-DEMO-2026-0001'
  AND NOT EXISTS (
    SELECT 1 FROM CLS_CONTRACT_ATTACHMENTS a
    WHERE a.CONTRACT_ID = c.ID AND a.TYPE_CODE = 'FINANCIAL_TERMS' AND a.IS_ACTIVE = 'Y'
  );
/

INSERT INTO CLS_CONTRACT_ATTACHMENTS (
  ID, CONTRACT_ID, TYPE_CODE, TYPE_NAME_RU, TYPE_NAME_RO,
  FILE_NAME, MIME_TYPE, FILE_SIZE, FILE_BLOB, IS_ACTIVE, UPLOADED_BY
)
SELECT
  NULL,
  c.ID,
  'ESTIMATE_TERMS',
  'Сметные условия',
  'Conditii de deviz',
  'estimate_terms_demo.txt',
  'text/plain',
  30,
  UTL_RAW.CAST_TO_RAW('Demo estimate terms for contract'),
  'Y',
  'demo'
FROM CLS_CONTRACTS c
WHERE c.CONTRACT_NO = 'CLS-CON-DEMO-2026-0001'
  AND NOT EXISTS (
    SELECT 1 FROM CLS_CONTRACT_ATTACHMENTS a
    WHERE a.CONTRACT_ID = c.ID AND a.TYPE_CODE = 'ESTIMATE_TERMS' AND a.IS_ACTIVE = 'Y'
  );
/

INSERT INTO CLS_CONTRACT_ATTACHMENTS (
  ID, CONTRACT_ID, TYPE_CODE, TYPE_NAME_RU, TYPE_NAME_RO,
  FILE_NAME, MIME_TYPE, FILE_SIZE, FILE_BLOB, IS_ACTIVE, UPLOADED_BY
)
SELECT
  NULL,
  c.ID,
  'PRICE_LIST',
  'Общий прайс-лист',
  'Pricelist general',
  'price_list_demo.txt',
  'text/plain',
  24,
  UTL_RAW.CAST_TO_RAW('Demo common price list'),
  'Y',
  'demo'
FROM CLS_CONTRACTS c
WHERE c.CONTRACT_NO = 'CLS-CON-DEMO-2026-0001'
  AND NOT EXISTS (
    SELECT 1 FROM CLS_CONTRACT_ATTACHMENTS a
    WHERE a.CONTRACT_ID = c.ID AND a.TYPE_CODE = 'PRICE_LIST' AND a.IS_ACTIVE = 'Y'
  );
/

COMMIT;
/
