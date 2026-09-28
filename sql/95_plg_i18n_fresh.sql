-- ============================================================
-- Планограммы: строки интерфейса разделов «Фреш» и «Заказы из зала» (RU / RO / EN)
--
-- Файл рассчитан на повторный запуск: каждая строка сначала удаляется по ключу.
-- ============================================================

DELETE FROM PLG_I18N WHERE MSG_KEY LIKE 'fr.%' OR MSG_KEY LIKE 'fo.%'
   OR MSG_KEY IN ('nav.fresh', 'nav.floorOrders');

-- ==================== Навигация ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.fresh', 'nav', 'Фреш', 'Fresh', 'Fresh');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.floorOrders', 'nav', 'Заказы из зала', 'Comenzi din sală', 'Floor orders');

-- ==================== Фреш ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.routesTitle', 'ui', 'Маршруты поставки фреш', 'Rutele de livrare fresh', 'Fresh delivery routes');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.routesSub', 'ui', 'Через распределительный центр либо прямой поставкой. Календарь: пн-вс', 'Prin centrul de distribuție sau livrare directă. Calendar: lu-du', 'Via the distribution centre or direct delivery. Calendar: Mon-Sun');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.profilesTitle', 'ui', 'Профили категорий', 'Profilurile categoriilor', 'Category profiles');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.profilesSub', 'ui', 'Срок годности, презентационный минимум и целевой уровень списаний', 'Termen de valabilitate, minim de prezentare și nivelul țintă al rebutului', 'Shelf life, presentation minimum and the target waste level');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.orderTitle', 'ui', 'Рекомендуемый заказ фреш', 'Comanda recomandată fresh', 'Recommended fresh order');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.orderSub', 'ui', 'Покрытие до следующей поставки и ожидаемое списание по каждой позиции', 'Acoperirea până la următoarea livrare și rebutul estimat pe poziție', 'Coverage until the next delivery and the expected waste per line');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.route', 'ui', 'Маршрут', 'Ruta', 'Route');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.dc', 'ui', 'Через РЦ', 'Prin CD', 'Via DC');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.direct', 'ui', 'Прямая', 'Directă', 'Direct');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.partner', 'ui', 'РЦ / поставщик', 'CD / furnizor', 'DC / supplier');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.lead', 'ui', 'Плечо', 'Termen livrare', 'Lead time');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.transit', 'ui', 'Транзит', 'Tranzit', 'Transit');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.orderDays', 'ui', 'Дни заказа', 'Zile de comandă', 'Order days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.deliveryDays', 'ui', 'Дни поставки', 'Zile de livrare', 'Delivery days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.perWeek', 'ui', 'Раз в неделю', 'Pe săptămână', 'Per week');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.cutoff', 'ui', 'Отсечка', 'Cutoff', 'Cutoff');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.moq', 'ui', 'Мин. партия', 'Lot minim', 'Min. order');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.days', 'ui', 'дн.', 'zile', 'd');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.temp', 'ui', 'Режим хранения', 'Regim de temperatură', 'Temperature');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.shelfLife', 'ui', 'Срок годности', 'Valabilitate', 'Shelf life');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.receipt', 'ui', 'Остаток срока при приёмке, %', 'Valabilitate la recepție, %', 'Shelf life left at receipt, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.presentation', 'ui', 'Презентационный минимум', 'Minim de prezentare', 'Presentation minimum');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.salvage', 'ui', 'Возврат уценкой, %', 'Recuperare prin reducere, %', 'Salvage by markdown, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.wasteTarget', 'ui', 'Цель по списаниям', 'Țintă rebut', 'Waste target');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.margin', 'ui', 'Наценка, %', 'Adaos, %', 'Markup, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.step', 'ui', 'Шаг округления', 'Pas de rotunjire', 'Rounding step');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.coverage', 'ui', 'Покрытие, дн.', 'Acoperire, zile', 'Coverage, d');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.nextDelivery', 'ui', 'Ближайшая поставка', 'Următoarea livrare', 'Next delivery');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.waste', 'ui', 'Ожид. списание', 'Rebut estimat', 'Expected waste');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.wasteExpected', 'ui', 'Ожидаемое списание', 'Rebut estimat', 'Expected waste');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.ofOrder', 'ui', 'от заказа', 'din comandă', 'of the order');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.orderQty', 'ui', 'Заказ, единиц', 'Comandă, unități', 'Order, units');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.orderAmount', 'ui', 'Сумма заказа', 'Suma comenzii', 'Order amount');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.shelfLimited', 'ui', 'Урезано сроком', 'Limitat de valabilitate', 'Shelf-life limited');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.shelfLimitedSub', 'ui', 'позиций', 'poziții', 'lines');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.limited', 'ui', 'срок', 'valabilitate', 'shelf');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.shelfLimitedHint', 'ui', 'Партия не доживёт до следующей поставки: заказ урезан по сроку годности', 'Lotul nu ajunge până la următoarea livrare: comanda este limitată de valabilitate', 'The batch will not last until the next delivery: the order is capped by shelf life');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.run', 'ui', 'Прогон', 'Rulare', 'Run');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.noRun', 'ui', 'Прогонов фреш-модели ещё не было — запустите модель FRESH-DC или FRESH-DIRECT в разделе «Прогноз заказов»', 'Nu există rulări ale modelului fresh — porniți FRESH-DC sau FRESH-DIRECT în secțiunea de prognoză', 'No fresh model runs yet — start FRESH-DC or FRESH-DIRECT in the forecast section');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.editRoute', 'ui', 'Маршрут поставки', 'Ruta de livrare', 'Delivery route');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.editProfile', 'ui', 'Профиль категории', 'Profilul categoriei', 'Category profile');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fr.maskHint', 'ui', 'Календарь — семь символов из 0 и 1, понедельник первый. Например 1010100 — поставки по понедельникам, средам и пятницам', 'Calendarul — șapte caractere 0/1, luni primul. De exemplu 1010100 — livrări lunea, miercurea și vinerea', 'The calendar is seven 0/1 characters, Monday first. For example 1010100 means Monday, Wednesday and Friday deliveries');

-- ==================== Заказы из зала ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.ordersTitle', 'ui', 'Заказы из зала', 'Comenzi din sală', 'Floor orders');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.ordersSub', 'ui', 'Надиктованы с телефона у полки, ждут решения категорийного менеджера', 'Dictate de la telefon lângă raft, așteaptă decizia managerului de categorie', 'Dictated from a phone at the shelf, waiting for the category manager decision');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.devicesTitle', 'ui', 'Устройства', 'Dispozitive', 'Devices');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.devicesSub', 'ui', 'Доступ по токену устройства; отзыв мгновенный', 'Acces prin token de dispozitiv; revocare instantanee', 'Access by device token; revocation is instant');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.voiceTitle', 'ui', 'Журнал распознавания', 'Jurnalul recunoașterii', 'Recognition log');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.voiceSub', 'ui', 'Что сказали у полки и как система это поняла', 'Ce s-a spus lângă raft și cum a înțeles sistemul', 'What was said at the shelf and how the system understood it');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.synTitle', 'ui', 'Речевой словарь', 'Dicționar vocal', 'Speech dictionary');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.synSub', 'ui', 'Как товар называют в зале. Пополняется вручную и из подтверждённых правок', 'Cum se numește marfa în sală. Se completează manual și din corecțiile confirmate', 'How products are called on the floor. Filled manually and from confirmed corrections');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.orders', 'ui', 'Заказов', 'Comenzi', 'Orders');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.forStore', 'ui', 'по магазину', 'pe magazin', 'for the store');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.waiting', 'ui', 'Ждут решения', 'Așteaptă decizia', 'Waiting');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.needDecision', 'ui', 'отправлены', 'trimise', 'submitted');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.attention', 'ui', 'Требуют уточнения', 'Necesită clarificare', 'Need attention');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.unrecognized', 'ui', 'позиций не распознано', 'poziții nerecunoscute', 'unrecognized lines');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.amount', 'ui', 'Сумма заказов', 'Suma comenzilor', 'Orders amount');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.number', 'ui', 'Номер', 'Număr', 'Number');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.device', 'ui', 'Устройство', 'Dispozitiv', 'Device');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.deviceName', 'ui', 'Название устройства', 'Numele dispozitivului', 'Device name');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.source', 'ui', 'Источник', 'Sursă', 'Source');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.src.voice', 'ui', 'голос', 'voce', 'voice');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.src.manual', 'ui', 'вручную', 'manual', 'manual');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.src.scan', 'ui', 'сканер', 'scanare', 'scan');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.draft', 'ui', 'Черновик', 'Ciornă', 'Draft');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.submitted', 'ui', 'Отправлен', 'Trimis', 'Submitted');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.accepted', 'ui', 'Принят', 'Acceptat', 'Accepted');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.rejected', 'ui', 'Отклонён', 'Respins', 'Rejected');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.cancelled', 'ui', 'Отменён', 'Anulat', 'Cancelled');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.items', 'ui', 'Позиций', 'Poziții', 'Lines');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.created', 'ui', 'Создан', 'Creat', 'Created');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.zone', 'ui', 'Зона зала', 'Zona sălii', 'Floor zone');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.phrases', 'ui', 'Сказанные фразы', 'Frazele rostite', 'Spoken phrases');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.phrase', 'ui', 'Фраза', 'Frază', 'Phrase');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.intent', 'ui', 'Намерение', 'Intenție', 'Intent');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.lang', 'ui', 'Язык', 'Limbă', 'Language');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.recognized', 'ui', 'Распознано', 'Recunoscut', 'Recognized');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.confidence', 'ui', 'Уверенность', 'Încredere', 'Confidence');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.user', 'ui', 'Сотрудник', 'Angajat', 'User');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.platform', 'ui', 'Платформа', 'Platformă', 'Platform');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.limit', 'ui', 'Лимит заказа', 'Limita comenzii', 'Order limit');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.lastSeen', 'ui', 'Последняя активность', 'Ultima activitate', 'Last seen');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.newDevice', 'ui', 'Новое устройство', 'Dispozitiv nou', 'New device');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.revoke', 'ui', 'Отозвать', 'Revocă', 'Revoke');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.dev.pending', 'ui', 'Ждёт сопряжения', 'Așteaptă asocierea', 'Pending pairing');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.dev.active', 'ui', 'Активно', 'Activ', 'Active');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.dev.revoked', 'ui', 'Отозвано', 'Revocat', 'Revoked');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.pairCode', 'ui', 'Код сопряжения', 'Cod de asociere', 'Pairing code');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.pairHint', 'ui', 'После сохранения система покажет код сопряжения. Он одноразовый: введите его в приложении на телефоне', 'După salvare sistemul afișează codul de asociere. Este de unică folosință: introduceți-l în aplicația de pe telefon', 'After saving the system shows a pairing code. It is single-use: enter it in the phone app');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.pairCodeHint', 'ui', 'Введите код в приложении. Второй раз он не сработает — если код утерян, заведите устройство заново', 'Introduceți codul în aplicație. A doua oară nu va funcționa — dacă s-a pierdut, creați dispozitivul din nou', 'Enter the code in the app. It will not work twice — if lost, create the device again');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.synSource', 'ui', 'Источник', 'Sursă', 'Source');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.syn.manual', 'ui', 'заведён вручную', 'manual', 'manual');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fo.syn.learned', 'ui', 'выучен из правки', 'învățat din corecție', 'learned from a correction');

COMMIT;
