-- ============================================================
-- Планограммы: строки интерфейса для генератора тестовых данных
-- и конфигуратора прогноза заказов (RU / RO / EN).
-- Дополняет словарь sql/83_plg_i18n.sql.
-- ============================================================

-- ==================== Навигация ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.testdata', 'nav', 'Генератор данных', 'Generator de date', 'Data generator');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.forecast', 'nav', 'Прогноз заказов',  'Prognoza comenzilor', 'Order forecast');

-- ==================== Наборы данных ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.title',      'ui', 'Наборы тестовых данных', 'Seturi de date de test', 'Test datasets');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.subtitle',   'ui', 'Тестовые данные изолированы в именованных наборах и не смешиваются с боевыми', 'Datele de test sunt izolate în seturi denumite', 'Test data is isolated in named datasets');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.dataset',    'ui', 'Набор данных',    'Set de date',      'Dataset');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.kind',       'ui', 'Тип',             'Tip',              'Kind');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.stores',     'ui', 'Магазинов',       'Magazine',         'Stores');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.sku',        'ui', 'SKU',             'SKU',              'SKUs');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.days',       'ui', 'Глубина, дней',   'Adâncime, zile',   'Depth, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.salesRows',  'ui', 'Строк продаж',    'Rânduri de vânzări','Sales rows');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.period',     'ui', 'Период истории',  'Perioada istoricului','History period');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.seed',       'ui', 'Seed (воспроизводимость)', 'Seed (reproductibilitate)', 'Seed (reproducibility)');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.protected',  'ui', 'Защищён',         'Protejat',         'Protected');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.new',        'ui', 'Сгенерировать сеть', 'Generează rețeaua', 'Generate network');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ds.deleteWarn', 'ui', 'Удалить набор вместе со всеми магазинами, товарами и продажами?', 'Ștergeți setul cu toate magazinele, produsele și vânzările?', 'Delete the dataset with all its stores, products and sales?');

-- ==================== Генерация ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.title',      'ui', 'Алгоритмы генерации', 'Algoritmi de generare', 'Generation algorithms');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.subtitle',   'ui', 'Отметьте этапы: каждый достраивает свой слой данных поверх предыдущего', 'Bifați etapele: fiecare adaugă propriul strat de date', 'Tick the stages: each builds its own data layer on top of the previous one');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.params',     'ui', 'Параметры генерации', 'Parametrii generării', 'Generation parameters');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.run',        'ui', 'Запустить генерацию', 'Pornește generarea', 'Run generation');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.running',    'ui', 'Генерация идёт…',    'Generarea rulează…', 'Generating…');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.runs',       'ui', 'Журнал прогонов',    'Jurnalul rulărilor', 'Run log');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.stage',      'ui', 'Этап',               'Etapă',              'Stage');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.progress',   'ui', 'Прогресс',           'Progres',            'Progress');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.rows',       'ui', 'Строк записано',     'Rânduri scrise',     'Rows written');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.duration',   'ui', 'Длительность, с',    'Durată, s',          'Duration, s');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.cancel',     'ui', 'Остановить',         'Oprește',            'Stop');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.storeCount', 'ui', 'Магазинов в сети',   'Magazine în rețea',  'Stores in network');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.skuCount',   'ui', 'SKU в матрице',      'SKU în matrice',     'SKUs in matrix');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.daysDepth',  'ui', 'История, дней',      'Istoric, zile',      'History, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.noise',      'ui', 'Шум спроса, %',      'Zgomotul cererii, %','Demand noise, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.trend',      'ui', 'Тренд за год, %',    'Trend anual, %',     'Yearly trend, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.weekly',     'ui', 'Недельная амплитуда','Amplitudine săptămânală','Weekly amplitude');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.yearly',     'ui', 'Годовая амплитуда',  'Amplitudine anuală', 'Yearly amplitude');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.oos',        'ui', 'Доля дней out-of-stock', 'Ponderea zilelor fără stoc', 'Out-of-stock day share');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.promoPer',   'ui', 'Акций на магазин / квартал', 'Promoții pe magazin / trimestru', 'Promos per store / quarter');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('gen.estimate',   'ui', 'Оценка объёма',      'Estimarea volumului','Volume estimate');

-- ==================== Прогноз заказов ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.title',       'ui', 'Модели прогноза заказов', 'Modele de prognoză a comenzilor', 'Order forecast models');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.subtitle',    'ui', 'Модель = алгоритм + конфигурация. Точность моделей сравнивается на backtest', 'Model = algoritm + configurație. Precizia se compară pe backtest', 'A model is an algorithm plus its configuration; accuracy is compared on backtest');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.algorithm',   'ui', 'Алгоритм',        'Algoritm',        'Algorithm');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.model',       'ui', 'Модель',          'Model',           'Model');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.newModel',    'ui', 'Новая модель',    'Model nou',       'New model');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.horizon',     'ui', 'Горизонт, дней',  'Orizont, zile',   'Horizon, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.serviceLevel','ui', 'Уровень сервиса, %', 'Nivel de serviciu, %', 'Service level, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.leadTime',    'ui', 'Срок поставки, дней', 'Termen de livrare, zile', 'Lead time, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.roundToPack', 'ui', 'Округлять до короба', 'Rotunjire la bax', 'Round to pack');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.isDefault',   'ui', 'По умолчанию',    'Implicit',        'Default');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.params',      'ui', 'Параметры алгоритма', 'Parametrii algoritmului', 'Algorithm parameters');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.minHistory',  'ui', 'Минимум истории, дней', 'Istoric minim, zile', 'Minimum history, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.run',         'ui', 'Прогноз',         'Prognoză',        'Forecast');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.backtest',    'ui', 'Backtest',        'Backtest',        'Backtest');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.runs',        'ui', 'Прогоны прогноза','Rulări de prognoză','Forecast runs');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.mode',        'ui', 'Режим',           'Mod',             'Mode');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.origin',      'ui', 'Точка отсчёта',   'Punct de referință','Origin');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.series',      'ui', 'Рядов',           'Serii',           'Series');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.skipped',     'ui', 'Пропущено',       'Omise',           'Skipped');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.mape',        'ui', 'MAPE, %',         'MAPE, %',         'MAPE, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.mae',         'ui', 'MAE',             'MAE',             'MAE');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.rmse',        'ui', 'RMSE',            'RMSE',            'RMSE');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.bias',        'ui', 'Смещение, %',     'Deviație, %',     'Bias, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.accuracy',    'ui', 'Точность',        'Precizie',        'Accuracy');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.compare',     'ui', 'Сравнить модели на backtest', 'Compară modelele pe backtest', 'Compare models on backtest');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fct.lastRun',     'ui', 'Последний прогон','Ultima rulare',   'Last run');

-- ==================== Рекомендуемый заказ ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ord.title',      'ui', 'Рекомендуемый заказ', 'Comanda recomandată', 'Recommended order');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ord.qty',        'ui', 'К заказу',        'De comandat',     'Order qty');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ord.forecast',   'ui', 'Прогноз спроса',  'Cererea prognozată','Forecast demand');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ord.safety',     'ui', 'Страховой запас', 'Stoc de siguranță','Safety stock');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ord.stock',      'ui', 'Остаток',         'Stoc curent',     'On hand');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ord.amount',     'ui', 'Сумма заказа',    'Suma comenzii',   'Order amount');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ord.abc',        'ui', 'ABC',             'ABC',             'ABC');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ord.pack',       'ui', 'Кратность',       'Multiplu',        'Pack');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ord.total',      'ui', 'Итого по заказу', 'Total comandă',   'Order total');

-- ==================== Статусы прогонов ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.running',  'status', 'Выполняется', 'În execuție', 'Running');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.failed',   'status', 'Ошибка',      'Eroare',      'Failed');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.building', 'status', 'Строится',    'Se creează',  'Building');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.ready',    'status', 'Готов',       'Gata',        'Ready');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.archived', 'status', 'В архиве',    'Arhivat',     'Archived');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.demo',     'status', 'Демо',        'Demo',        'Demo');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.test',     'status', 'Тест',        'Test',        'Test');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.sandbox',  'status', 'Песочница',   'Sandbox',     'Sandbox');

COMMIT;
