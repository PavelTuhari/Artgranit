-- =====================================================================
-- RO: Nomenclatorul livrat cu modulul SEOForge si setarile implicite.
-- EN: The dictionary shipped with the SEOForge module and the defaults.
--
-- RO: Codurile 101..999 sunt fixe si rezervate acestui fisier, ca sa fie
--     aceleasi in orice instalare. Codurile adaugate din interfata incep
--     de la 1001 (secventa YSEO_DICT_SEQ).
-- EN: Codes 101..999 are fixed and reserved for this file so they are the
--     same in every installation. Codes added from the interface start at
--     1001 (the YSEO_DICT_SEQ sequence).
--
-- RO: Totul prin MERGE: reinstalarea nu trebuie sa cada pe duplicate.
-- EN: Everything through MERGE: a re-install must not fail on duplicates.
-- =====================================================================

MERGE INTO YSEO_DICT t
USING (
    SELECT 'CHANNEL' AS SECTION, 101 AS COD1, 'GOOGLE_ORGANIC' AS CODE, 'Google, органика' AS NAME_RU, 'Google, organic' AS NAME_RO, 'Google organic' AS NAME_EN, 10 AS SORT_ORDER FROM DUAL
    UNION ALL SELECT 'CHANNEL', 102, 'GOOGLE_ADS',   'Google Ads',          'Google Ads',           'Google Ads',           20 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 103, 'META_ADS',     'Meta Ads',            'Meta Ads',             'Meta Ads',             30 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 104, 'FACEBOOK',     'Facebook',            'Facebook',             'Facebook',             40 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 105, 'INSTAGRAM',    'Instagram',           'Instagram',            'Instagram',            50 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 106, 'LINKEDIN',     'LinkedIn',            'LinkedIn',             'LinkedIn',             60 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 107, 'TIKTOK',       'TikTok',              'TikTok',               'TikTok',               70 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 108, 'YOUTUBE',      'YouTube',             'YouTube',              'YouTube',              80 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 109, 'TELEGRAM',     'Telegram',            'Telegram',             'Telegram',             90 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 110, 'POINT_MD',     'point.md',            'point.md',             'point.md',            100 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 111, '999_MD',       '999.md',              '999.md',               '999.md',              110 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 112, 'MAKLER_MD',    'makler.md',           'makler.md',            'makler.md',           120 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 113, 'CATALOGS',     'Каталоги и справочники', 'Cataloage si directoare', 'Catalogues and directories', 130 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 114, 'EMAIL',        'E-mail рассылки',     'Campanii e-mail',      'E-mail campaigns',    140 FROM DUAL
    UNION ALL SELECT 'CHANNEL', 115, 'GBP',          'Google Business Profile', 'Google Business Profile', 'Google Business Profile', 150 FROM DUAL

    UNION ALL SELECT 'ARTICLE', 201, 'ADS',          'Реклама',             'Publicitate',          'Advertising',          10 FROM DUAL
    UNION ALL SELECT 'ARTICLE', 202, 'CONTENT',      'Контент',             'Continut',             'Content',              20 FROM DUAL
    UNION ALL SELECT 'ARTICLE', 203, 'LINKBUILDING', 'Ссылочное',           'Linkbuilding',         'Linkbuilding',         30 FROM DUAL
    UNION ALL SELECT 'ARTICLE', 204, 'TOOLS',        'Инструменты и подписки', 'Instrumente si abonamente', 'Tools and subscriptions', 40 FROM DUAL
    UNION ALL SELECT 'ARTICLE', 205, 'AI_TOKENS',    'AI-сессии и токены',  'Sesiuni AI si tokenuri', 'AI sessions and tokens', 50 FROM DUAL
    UNION ALL SELECT 'ARTICLE', 206, 'AGENCY',       'Подрядчики',          'Contractanti',         'Contractors',          60 FROM DUAL
    UNION ALL SELECT 'ARTICLE', 207, 'PRODUCTION',   'Продакшн (фото, видео)', 'Productie (foto, video)', 'Production (photo, video)', 70 FROM DUAL
    UNION ALL SELECT 'ARTICLE', 208, 'OTHER',        'Прочее',              'Altele',               'Other',                90 FROM DUAL

    UNION ALL SELECT 'PROMO_TYPE', 301, 'DISCOUNT',  'Скидка',              'Reducere',             'Discount',             10 FROM DUAL
    UNION ALL SELECT 'PROMO_TYPE', 302, 'PROMO_CODE','Промокод',            'Cod promotional',      'Promo code',           20 FROM DUAL
    UNION ALL SELECT 'PROMO_TYPE', 303, 'BUNDLE',    'Комплект',            'Pachet',               'Bundle',               30 FROM DUAL
    UNION ALL SELECT 'PROMO_TYPE', 304, 'GIFT',      'Подарок',             'Cadou',                'Gift',                 40 FROM DUAL
    UNION ALL SELECT 'PROMO_TYPE', 305, 'CONTENT',   'Контентная кампания', 'Campanie de continut', 'Content campaign',     50 FROM DUAL
    UNION ALL SELECT 'PROMO_TYPE', 306, 'BRAND',     'Имиджевая кампания',  'Campanie de imagine',  'Brand campaign',       60 FROM DUAL

    UNION ALL SELECT 'FORMAT', 401, 'ARTICLE',       'Статья',              'Articol',              'Article',              10 FROM DUAL
    UNION ALL SELECT 'FORMAT', 402, 'POST',          'Пост',                'Postare',              'Post',                 20 FROM DUAL
    UNION ALL SELECT 'FORMAT', 403, 'STORY',         'Сторис',              'Story',                'Story',                30 FROM DUAL
    UNION ALL SELECT 'FORMAT', 404, 'VIDEO',         'Видео',               'Video',                'Video',                40 FROM DUAL
    UNION ALL SELECT 'FORMAT', 405, 'BANNER',        'Баннер',              'Banner',               'Banner',               50 FROM DUAL
    UNION ALL SELECT 'FORMAT', 406, 'SEARCH_AD',     'Поисковое объявление','Anunt in cautare',     'Search ad',            60 FROM DUAL
    UNION ALL SELECT 'FORMAT', 407, 'LISTING',       'Объявление на площадке','Anunt pe platforma', 'Marketplace listing',  70 FROM DUAL
    UNION ALL SELECT 'FORMAT', 408, 'EMAIL',         'Письмо',              'Mesaj e-mail',         'E-mail',               80 FROM DUAL

    UNION ALL SELECT 'BUYUNIT', 501, 'CPC',          'CPC — за клик',       'CPC - pe clic',        'CPC - per click',      10 FROM DUAL
    UNION ALL SELECT 'BUYUNIT', 502, 'CPM',          'CPM — за 1000 показов','CPM - la 1000 afisari','CPM - per 1000 impressions', 20 FROM DUAL
    UNION ALL SELECT 'BUYUNIT', 503, 'CPA',          'CPA — за действие',   'CPA - pe actiune',     'CPA - per action',     30 FROM DUAL
    UNION ALL SELECT 'BUYUNIT', 504, 'FIX',          'Фиксированная цена',  'Pret fix',             'Fixed price',          40 FROM DUAL
    UNION ALL SELECT 'BUYUNIT', 505, 'SUBSCRIPTION', 'Подписка',            'Abonament',            'Subscription',         50 FROM DUAL
    UNION ALL SELECT 'BUYUNIT', 506, 'HOUR',         'Час работы',          'Ora de lucru',         'Work hour',            60 FROM DUAL

    UNION ALL SELECT 'METRIC', 601, 'POSITION_AVG',  'Средняя позиция',     'Pozitia medie',        'Average position',     10 FROM DUAL
    UNION ALL SELECT 'METRIC', 602, 'IMPRESSIONS',   'Показы',              'Afisari',              'Impressions',          20 FROM DUAL
    UNION ALL SELECT 'METRIC', 603, 'CLICKS',        'Клики',               'Clicuri',              'Clicks',               30 FROM DUAL
    UNION ALL SELECT 'METRIC', 604, 'CTR',           'CTR, %',              'CTR, %',               'CTR, %',               40 FROM DUAL
    UNION ALL SELECT 'METRIC', 605, 'SESSIONS',      'Сессии',              'Sesiuni',              'Sessions',             50 FROM DUAL
    UNION ALL SELECT 'METRIC', 606, 'USERS',         'Пользователи',        'Utilizatori',          'Users',                60 FROM DUAL
    UNION ALL SELECT 'METRIC', 607, 'CONVERSIONS',   'Конверсии',           'Conversii',            'Conversions',          70 FROM DUAL
    UNION ALL SELECT 'METRIC', 608, 'REVENUE',       'Выручка',             'Venit',                'Revenue',              80 FROM DUAL
    UNION ALL SELECT 'METRIC', 609, 'INDEXED_PAGES', 'Страниц в индексе',   'Pagini indexate',      'Indexed pages',        90 FROM DUAL
    UNION ALL SELECT 'METRIC', 610, 'BACKLINKS',     'Внешние ссылки',      'Linkuri externe',      'Backlinks',           100 FROM DUAL
    UNION ALL SELECT 'METRIC', 611, 'TOP10_KEYS',    'Ключей в ТОП-10',     'Chei in TOP-10',       'Keys in TOP-10',      110 FROM DUAL
    UNION ALL SELECT 'METRIC', 612, 'CWV_LCP',       'Core Web Vitals: LCP','Core Web Vitals: LCP', 'Core Web Vitals: LCP', 120 FROM DUAL
) s
ON (t.SECTION = s.SECTION AND t.COD1 = s.COD1)
WHEN MATCHED THEN
  UPDATE SET t.CODE = s.CODE, t.NAME_RU = s.NAME_RU, t.NAME_RO = s.NAME_RO,
             t.NAME_EN = s.NAME_EN, t.SORT_ORDER = s.SORT_ORDER
WHEN NOT MATCHED THEN
  INSERT (SECTION, COD1, CODE, NAME_RU, NAME_RO, NAME_EN, SORT_ORDER, ISARHIV)
  VALUES (s.SECTION, s.COD1, s.CODE, s.NAME_RU, s.NAME_RO, s.NAME_EN, s.SORT_ORDER, 0);

-- ---------------------------------------------------------------------
-- RO: Setarile implicite. BUDGET_OVERRUN_MODE = WARN la instalare: la
--     pornire depasirea se marcheaza si se analizeaza, nu opreste lucrul.
--     Trecerea pe BLOCK se face cand planul este completat cu adevarat.
-- EN: Default settings. BUDGET_OVERRUN_MODE = WARN on install: at the
--     start an overrun is flagged and reviewed rather than blocking work.
--     Switch to BLOCK once the plan is genuinely filled in.
-- ---------------------------------------------------------------------
MERGE INTO YSEO_SETUP t
USING (
    SELECT 'BASE_CURRENCY' AS PARAM_CODE, 'MDL' AS PARAM_VALUE,
           'RO: Valuta de baza a rapoartelor / EN: Base reporting currency' AS DESCR FROM DUAL
    UNION ALL SELECT 'BUDGET_OVERRUN_MODE', 'WARN',
           'RO: BLOCK opreste cheltuiala peste plan, WARN o marcheaza / EN: BLOCK stops over-plan spend, WARN flags it' FROM DUAL
) s
ON (t.PARAM_CODE = s.PARAM_CODE)
WHEN NOT MATCHED THEN
  INSERT (PARAM_CODE, PARAM_VALUE, DESCR)
  VALUES (s.PARAM_CODE, s.PARAM_VALUE, s.DESCR);

-- ---------------------------------------------------------------------
-- RO: Cursul valutei de baza fata de ea insasi nu se pastreaza. Pentru
--     restul valutelor cursul se introduce din interfata. Aici punem doar
--     un reper de pornire pentru EUR si USD, ca modulul sa fie utilizabil
--     imediat dupa instalare.
-- EN: The base currency has no rate against itself. Other currencies get
--     their rates from the interface. Here we only seed a starting point
--     for EUR and USD so the module is usable right after installation.
-- ---------------------------------------------------------------------
MERGE INTO YSEO_FX_RATE t
USING (
    SELECT 'EUR' AS VALUTA, DATE '2026-01-01' AS RATE_DATE, 19.500000 AS RATE FROM DUAL
    UNION ALL SELECT 'USD', DATE '2026-01-01', 17.800000 FROM DUAL
) s
ON (t.VALUTA = s.VALUTA AND t.RATE_DATE = s.RATE_DATE)
WHEN NOT MATCHED THEN
  INSERT (VALUTA, RATE_DATE, RATE) VALUES (s.VALUTA, s.RATE_DATE, s.RATE);

-- ---------------------------------------------------------------------
-- RO: Declansatorul de buget din 113 depinde de pachetele din 115 si la
--     prima instalare ramane invalid. Recompilarea explicita lasa schema
--     valida la sfarsitul instalarii, nu la prima folosire.
-- EN: The budget trigger from 113 depends on the packages from 115 and
--     stays invalid on first install. An explicit recompile leaves the
--     schema valid at the end of the install, not at first use.
-- ---------------------------------------------------------------------
ALTER TRIGGER TRG_YSEO_SPEND_BUDGET COMPILE;
