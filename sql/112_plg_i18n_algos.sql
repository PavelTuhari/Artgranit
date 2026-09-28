-- ============================================================
-- Планограммы: строки интерфейса для алгоритмов прогноза топлива
-- и путей снабжения (RU / RO / EN).
-- Файл рассчитан на повторный запуск.
-- ============================================================

DELETE FROM PLG_I18N WHERE MSG_KEY LIKE 'fa.%' OR MSG_KEY LIKE 'fp.%';

-- ==================== Алгоритмы прогноза ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.title', 'ui', 'Алгоритмы прогноза отпуска', 'Algoritmi de prognoză a livrărilor', 'Dispensing forecast algorithms');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.sub', 'ui', 'Четыре модели на чистом Python. Выбор делается не спором, а измерением: сравнение идёт на реальной истории отпуска по накопленному спросу за горизонт завоза', 'Patru modele în Python pur. Alegerea se face prin măsurare pe istoricul real al livrărilor, pe cererea cumulată pe orizontul de aprovizionare', 'Four pure-Python models. The choice is measured, not argued: compared on real dispensing history over cumulative demand for the delivery horizon');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.compare', 'ui', 'Сравнить на истории', 'Compară pe istoric', 'Compare on history');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.algorithm', 'ui', 'Алгоритм', 'Algoritm', 'Algorithm');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.bestFor', 'ui', 'Когда применять', 'Când se aplică', 'When to use');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.minHistory', 'ui', 'Мин. история, сут', 'Istoric minim, zile', 'Min. history, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.mape', 'ui', 'MAPE', 'MAPE', 'MAPE');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.mae', 'ui', 'MAE, л', 'MAE, l', 'MAE, l');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.bias', 'ui', 'Смещение', 'Deviere', 'Bias');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.tanks', 'ui', 'Баков в тесте', 'Rezervoare testate', 'Tanks tested');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.horizon', 'ui', 'Горизонт, суток', 'Orizont, zile', 'Horizon, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.noBacktest', 'ui', 'Сравнение ещё не запускалось', 'Comparația nu a fost rulată', 'Comparison has not been run yet');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.best', 'ui', 'Лучший по MAPE', 'Cel mai bun după MAPE', 'Best by MAPE');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.running', 'ui', 'Считаю на истории, это занимает несколько секунд', 'Calculez pe istoric, durează câteva secunde', 'Running on history, this takes a few seconds');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.baseline', 'ui', 'Базовый расчёт (среднее за 28/7 суток)', 'Calcul de bază (media 28/7 zile)', 'Baseline (28/7-day average)');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.usedIn', 'ui', 'Прогноз применён к бакам', 'Prognoza aplicată rezervoarelor', 'Forecast applied to tanks');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fa.safety', 'ui', 'Страховой запас, л', 'Stoc de siguranță, l', 'Safety stock, l');

-- ==================== Пути снабжения и план ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.title', 'ui', 'Пути снабжения', 'Rute de aprovizionare', 'Supply paths');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.sub', 'ui', 'Импорт и внутренний рынок, своя и партнёрская нефтебаза, прямая поставка на станцию. Цена литра «до бака» включает транспорт, перевалку, пошлину и стоимость денег на плече', 'Import și piață internă, depozit propriu și partener, livrare directă la stație. Costul litrului include transport, manipulare, taxe și costul banilor pe termen', 'Import and domestic market, own and partner depot, direct delivery. Landed cost per litre includes transport, handling, duty and the cost of money over the lead time');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.planTitle', 'ui', 'План снабжения', 'Plan de aprovizionare', 'Supply plan');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.planSub', 'ui', 'Поток минимальной стоимости по двум слоям: развозка сегодня и пополнение баз. Развозку смотрит диспетчер, пополнение — закупщик', 'Flux de cost minim pe două niveluri: distribuția de azi și reaprovizionarea depozitelor', 'Minimum-cost flow over two layers: today''s distribution and depot replenishment. Dispatcher reads the first, buyer the second');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.recalc', 'ui', 'Пересчитать план', 'Recalculează planul', 'Recalculate plan');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.distribution', 'ui', 'Развозка сегодня', 'Distribuția de azi', 'Distribution today');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.replenishment', 'ui', 'Пополнение нефтебаз', 'Reaprovizionarea depozitelor', 'Depot replenishment');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.path', 'ui', 'Путь', 'Rută', 'Path');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.target', 'ui', 'Куда', 'Destinație', 'Destination');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.lead', 'ui', 'Плечо, сут', 'Termen, zile', 'Lead, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.costPerL', 'ui', 'Цена до бака, лей/л', 'Cost la rezervor, lei/l', 'Landed cost, MDL/l');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.perL', 'ui', 'лей/л', 'lei/l', 'MDL/l');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.amount', 'ui', 'Сумма, лей', 'Sumă, lei', 'Amount, MDL');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.available', 'ui', 'Доступно, л', 'Disponibil, l', 'Available, l');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.minLot', 'ui', 'Мин. партия, л', 'Lot minim, l', 'Min. lot, l');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.late', 'ui', 'опоздание', 'întârziere', 'late');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.lateHint', 'ui', 'Опоздание не запрещает поставку, а удорожает путь: станции у сухого бака везут в первую очередь, но всё равно везут', 'Întârzierea nu interzice livrarea, ci scumpește ruta: stațiile aproape de gol sunt servite primele', 'Lateness does not forbid a delivery, it makes the path costlier: near-dry stations are served first, but still served');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.import', 'ui', 'импорт', 'import', 'import');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.urgent', 'ui', 'срочная часть', 'parte urgentă', 'urgent part');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.base', 'ui', 'основной объём', 'volum de bază', 'base volume');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.totalPlan', 'ui', 'Стоимость плана', 'Costul planului', 'Plan cost');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.uncovered', 'ui', 'Не закрыто', 'Neacoperit', 'Uncovered');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.explain', 'ui', 'Почему этот путь', 'De ce această rută', 'Why this path');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.blocked', 'ui', 'Не подходит', 'Nu se potrivește', 'Not applicable');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.moneyRate', 'ui', 'Стоимость денег, годовых', 'Costul banilor, anual', 'Cost of money, annual');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.kind', 'ui', 'Слой', 'Nivel', 'Layer');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.editPath', 'ui', 'Условия пути', 'Condițiile rutei', 'Path terms');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.price', 'ui', 'Цена литра', 'Prețul litrului', 'Price per litre');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.transport', 'ui', 'Транспорт, лей/л', 'Transport, lei/l', 'Transport, MDL/l');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.handling', 'ui', 'Перевалка, лей/л', 'Manipulare, lei/l', 'Handling, MDL/l');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fp.duty', 'ui', 'Пошлина и акциз, лей/л', 'Taxe și accize, lei/l', 'Duty and excise, MDL/l');

COMMIT;
