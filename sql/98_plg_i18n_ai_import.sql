-- ============================================================
-- Планограммы: строки интерфейса разделов «ИИ-мониторинг», «Автозаказ»,
-- «Импорт» (RU / RO / EN). Файл рассчитан на повторный запуск.
-- ============================================================

DELETE FROM PLG_I18N WHERE MSG_KEY LIKE 'ai.%' OR MSG_KEY LIKE 'ao.%'
   OR MSG_KEY LIKE 'io.%'
   OR MSG_KEY IN ('nav.aiMonitor', 'nav.autoOrders', 'nav.imports');

-- ==================== Навигация ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.aiMonitor', 'nav', 'ИИ-мониторинг', 'Monitorizare AI', 'AI monitoring');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.autoOrders', 'nav', 'Автозаказ', 'Comandă automată', 'Auto-order');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.imports', 'nav', 'Импорт', 'Import', 'Imports');

-- ==================== ИИ-мониторинг ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.signalsTitle', 'ui', 'Сигналы мониторинга', 'Semnale de monitorizare', 'Monitoring signals');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.signalsSub', 'ui', 'Детекторы: риск out-of-stock, всплеск и провал спроса, риск списаний, дрейф модели, мёртвый запас', 'Detectoare: risc out-of-stock, salt și cădere de cerere, risc de rebut, derivă de model, stoc mort', 'Detectors: out-of-stock risk, demand spike and drop, waste risk, model drift, dead stock');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.featuresTitle', 'ui', 'Массив признаков для обучения', 'Set de caracteristici pentru antrenare', 'Feature dataset for training');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.featuresSub', 'ui', 'Витрина по каждому SKU: уровни спроса, волатильность, промо-аплифт, OOS, списания. Выгружается для ML', 'Vitrina pe fiecare SKU: niveluri de cerere, volatilitate, uplift promo, OOS, rebut. Se exportă pentru ML', 'Per-SKU mart: demand levels, volatility, promo uplift, OOS, waste. Exportable for ML');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.runsTitle', 'ui', 'Прогоны мониторинга', 'Rulări de monitorizare', 'Monitor runs');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.run', 'ui', 'Запустить мониторинг', 'Pornește monitorizarea', 'Run monitoring');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.started', 'ui', 'Мониторинг запущен', 'Monitorizarea a pornit', 'Monitoring started');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.exportCsv', 'ui', 'Выгрузить CSV', 'Export CSV', 'Export CSV');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.exportJson', 'ui', 'Выгрузить JSON', 'Export JSON', 'Export JSON');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.crit', 'ui', 'Критичные', 'Critice', 'Critical');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.warn', 'ui', 'Предупреждения', 'Avertismente', 'Warnings');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.info', 'ui', 'Информационные', 'Informative', 'Info');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.needAction', 'ui', 'требуют действия', 'necesită acțiune', 'need action');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.lastRun', 'ui', 'последний прогон', 'ultima rulare', 'last run');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.type', 'ui', 'Тип', 'Tip', 'Type');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.message', 'ui', 'Сообщение', 'Mesaj', 'Message');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.value', 'ui', 'Факт', 'Real', 'Actual');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.baseline', 'ui', 'База', 'Bază', 'Baseline');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.signals', 'ui', 'Сигналов', 'Semnale', 'Signals');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.features', 'ui', 'Признаков', 'Caracteristici', 'Features');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.trend', 'ui', 'Тренд', 'Trend', 'Trend');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.weekend', 'ui', 'Выходные', 'Weekend', 'Weekend');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.promoUp', 'ui', 'Промо', 'Promo', 'Promo');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.cover', 'ui', 'Покрытие, дн.', 'Acoperire, zile', 'Cover, d');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.noSignals', 'ui', 'Сигналов нет — запустите мониторинг', 'Nu există semnale — porniți monitorizarea', 'No signals — run the monitor');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.noRun', 'ui', 'Прогонов мониторинга ещё не было', 'Nu există rulări de monitorizare', 'No monitor runs yet');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.t.oos_risk', 'ui', 'Риск OOS', 'Risc OOS', 'OOS risk');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.t.spike', 'ui', 'Всплеск', 'Salt', 'Spike');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.t.drop', 'ui', 'Провал', 'Cădere', 'Drop');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.t.waste_risk', 'ui', 'Риск списания', 'Risc de rebut', 'Waste risk');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.t.bias_drift', 'ui', 'Дрейф модели', 'Derivă de model', 'Model drift');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ai.t.dead_stock', 'ui', 'Мёртвый запас', 'Stoc mort', 'Dead stock');

-- ==================== Автозаказ ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.title', 'ui', 'Автозаказ с корректировкой', 'Comandă automată cu ajustare', 'Auto-order with adjustments');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.sub', 'ui', 'Рекомендация модели и решение закупщика рядом. Правка сохраняется сразу, модельная цифра не перезаписывается', 'Recomandarea modelului și decizia achizitorului alături. Ajustarea se salvează imediat, cifra modelului nu se suprascrie', 'Model recommendation next to the buyer decision. Edits save instantly; the model figure is never overwritten');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.package', 'ui', 'Пакет документов', 'Pachet de documente', 'Document package');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.positions', 'ui', 'Позиций к заказу', 'Poziții de comandat', 'Lines to order');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.adjusted', 'ui', 'Скорректировано', 'Ajustate', 'Adjusted');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.byBuyer', 'ui', 'закупщиком', 'de achizitor', 'by the buyer');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.supplier', 'ui', 'Поставщик', 'Furnizor', 'Supplier');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.model', 'ui', 'Модель', 'Model', 'Model');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.final', 'ui', 'К заказу', 'De comandat', 'Final');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.reason', 'ui', 'Правка', 'Ajustare', 'Adjustment');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.reset', 'ui', 'Вернуть модельное значение', 'Revino la valoarea modelului', 'Restore model value');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.badQty', 'ui', 'Количество должно быть числом не меньше нуля', 'Cantitatea trebuie să fie un număr nenegativ', 'Quantity must be a non-negative number');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.r.manual', 'ui', 'вручную', 'manual', 'manual');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.r.promo', 'ui', 'акция', 'promoție', 'promo');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.r.event', 'ui', 'событие', 'eveniment', 'event');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.r.supply', 'ui', 'поставка', 'aprovizionare', 'supply');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.r.quality', 'ui', 'качество', 'calitate', 'quality');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ao.r.other', 'ui', 'прочее', 'altele', 'other');

-- ==================== Импорт ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.title', 'ui', 'Заказы импорта', 'Comenzi de import', 'Import orders');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.sub', 'ui', 'Контракт → отгрузка → граница → растаможка → выпуск. Задержки считаются как факт минус план', 'Contract → expediere → frontieră → vămuire → liber de vamă. Întârzierile = real minus plan', 'Contract → shipment → border → customs → release. Delays are actual minus plan');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.new', 'ui', 'Новый импортный заказ', 'Comandă de import nouă', 'New import order');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.newHint', 'ui', 'При сохранении система построит план этапов по типовым срокам и заведёт чек-лист документов с дедлайнами от плановой даты границы', 'La salvare sistemul construiește planul etapelor și lista documentelor cu termene calculate de la data planificată a frontierei', 'On save the system builds the stage plan and the document checklist with deadlines counted back from the planned border date');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.orders', 'ui', 'Заказов', 'Comenzi', 'Orders');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.inCustoms', 'ui', 'На таможне', 'În vamă', 'In customs');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.now', 'ui', 'сейчас', 'acum', 'now');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.docsOverdue', 'ui', 'Просрочено документов', 'Documente întârziate', 'Overdue documents');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.docs', 'ui', 'по чек-листам', 'în liste', 'in checklists');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.totalDelay', 'ui', 'Суммарная задержка', 'Întârziere totală', 'Total delay');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.supplier', 'ui', 'Поставщик', 'Furnizor', 'Supplier');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.route', 'ui', 'Маршрут', 'Rută', 'Route');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.stage', 'ui', 'Этап', 'Etapă', 'Stage');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.stages', 'ui', 'Прохождение этапов', 'Parcurgerea etapelor', 'Stage progress');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.docsCol', 'ui', 'Документы', 'Documente', 'Documents');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.docsChecklist', 'ui', 'Чек-лист документов', 'Lista documentelor', 'Document checklist');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.doc', 'ui', 'Документ', 'Document', 'Document');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.amount', 'ui', 'Сумма', 'Sumă', 'Amount');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.delay', 'ui', 'Задержка, дн.', 'Întârziere, zile', 'Delay, d');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.overdue', 'ui', 'просрочен', 'întârziat', 'overdue');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.pending', 'ui', 'в работе', 'în lucru', 'pending');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.ready', 'ui', 'готовы', 'gata', 'ready');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.plan', 'ui', 'План', 'Plan', 'Plan');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.fact', 'ui', 'Факт', 'Real', 'Actual');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.reason', 'ui', 'Причина', 'Cauză', 'Reason');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.due', 'ui', 'Срок', 'Termen', 'Due');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.responsible', 'ui', 'Ответственный', 'Responsabil', 'Responsible');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.post', 'ui', 'Таможенный пост', 'Post vamal', 'Customs post');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.broker', 'ui', 'Брокер', 'Broker', 'Broker');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.package', 'ui', 'Печатный пакет', 'Pachet tipărit', 'Print package');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.country', 'ui', 'Страна отправления', 'Țara de expediere', 'Country of dispatch');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.transport', 'ui', 'Транспорт', 'Transport', 'Transport');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.currency', 'ui', 'Валюта', 'Valută', 'Currency');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.etd', 'ui', 'Плановая отгрузка', 'Expediere planificată', 'Planned shipment');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.delaysTitle', 'ui', 'Где теряются дни', 'Unde se pierd zilele', 'Where the days are lost');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.delaysSub', 'ui', 'Задержки по этапам и причинам за все заказы — статистика для выбора поста и брокера', 'Întârzieri pe etape și cauze — statistică pentru alegerea postului și brokerului', 'Delays by stage and reason — statistics for choosing the post and the broker');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.askReason', 'ui', 'Этап пройден с задержкой. Причина: docs / customs / logistics / supplier / payment / other', 'Etapa a trecut cu întârziere. Cauza: docs / customs / logistics / supplier / payment / other', 'Stage passed late. Reason: docs / customs / logistics / supplier / payment / other');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.tr.truck', 'ui', 'Автомобиль', 'Camion', 'Truck');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.tr.sea', 'ui', 'Море', 'Maritim', 'Sea');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.tr.air', 'ui', 'Авиа', 'Aerian', 'Air');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.tr.rail', 'ui', 'Ж/д', 'Feroviar', 'Rail');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.d.pending', 'ui', 'ожидает', 'în așteptare', 'pending');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.d.in_progress', 'ui', 'в работе', 'în lucru', 'in progress');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.d.ready', 'ui', 'готов', 'gata', 'ready');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.d.approved', 'ui', 'принят', 'acceptat', 'approved');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.d.rejected', 'ui', 'отклонён', 'respins', 'rejected');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.dr.docs', 'ui', 'документы', 'documente', 'documents');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.dr.customs', 'ui', 'таможня', 'vamă', 'customs');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.dr.logistics', 'ui', 'логистика', 'logistică', 'logistics');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.dr.supplier', 'ui', 'поставщик', 'furnizor', 'supplier');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.dr.payment', 'ui', 'оплата', 'plată', 'payment');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('io.dr.other', 'ui', 'прочее', 'altele', 'other');

COMMIT;
