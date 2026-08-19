-- ============================================================
-- Планограммы: строки интерфейса раздела «Топливо» (RU / RO / EN).
-- Файл рассчитан на повторный запуск.
-- ============================================================

DELETE FROM PLG_I18N WHERE MSG_KEY LIKE 'fu.%' OR MSG_KEY = 'nav.fuel';

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.fuel', 'nav', 'Топливо', 'Combustibil', 'Fuel');

-- ==================== Карта ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.mapTitle', 'ui', 'Карта сети АЗС', 'Harta rețelei de benzinării', 'Station network map');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.mapSub', 'ui', 'Цвет точки — запас топлива до сухого бака. Режим правки позволяет перетащить станцию или найти её по адресу', 'Culoarea punctului — rezerva până la rezervor gol. Modul de editare permite mutarea sau căutarea după adresă', 'Dot colour shows the fuel cover until a dry tank. Edit mode lets you drag a station or find it by address');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.addrPh', 'ui', 'Адрес станции', 'Adresa stației', 'Station address');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.find', 'ui', 'Найти по адресу', 'Caută după adresă', 'Find by address');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.edit', 'ui', 'Режим правки', 'Mod editare', 'Edit mode');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.editOn', 'ui', 'Правка включена: перетащите маркер станции', 'Editare activă: mutați marcatorul stației', 'Edit mode on: drag the station marker');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.editOff', 'ui', 'Правка выключена', 'Editare oprită', 'Edit mode off');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.needAddr', 'ui', 'Введите адрес', 'Introduceți adresa', 'Enter an address');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.pickStation', 'ui', 'Сначала выберите станцию на карте', 'Selectați mai întâi stația pe hartă', 'Pick a station on the map first');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.notFound', 'ui', 'Адрес не найден', 'Adresa nu a fost găsită', 'Address not found');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.geoError', 'ui', 'Ошибка геокодера', 'Eroare de geocodare', 'Geocoder error');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.geoSaved', 'ui', 'Координаты сохранены', 'Coordonate salvate', 'Coordinates saved');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.noGeo', 'ui', 'без координат', 'fără coordonate', 'without coordinates');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.l1', 'ui', 'меньше суток', 'sub o zi', 'under a day');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.l3', 'ui', '1-3 суток', '1-3 zile', '1-3 days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.l7', 'ui', '3-7 суток', '3-7 zile', '3-7 days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.l7p', 'ui', 'больше недели', 'peste o săptămână', 'over a week');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.depot', 'ui', 'нефтебаза', 'depozit', 'depot');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.bays', 'ui', 'Наливных постов', 'Posturi de încărcare', 'Loading bays');

-- ==================== Автозаказ ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.orderTitle', 'ui', 'Автозаказ топлива', 'Comandă automată de combustibil', 'Fuel auto-order');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.orderSub', 'ui', 'Объём подбирается комбинацией секций бензовоза и ограничен свободной ёмкостью резервуара на момент прихода', 'Volumul se compune din secțiile cisternei și este limitat de spațiul liber al rezervorului la sosire', 'The volume is composed of tanker compartments and capped by the tank ullage at arrival');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.run', 'ui', 'Рассчитать заказ', 'Calculează comanda', 'Calculate order');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.calculated', 'ui', 'Заказов рассчитано', 'Comenzi calculate', 'Orders calculated');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.params', 'ui', 'Параметры', 'Parametri', 'Parameters');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.paramsHint', 'ui', 'Расчёт запускается с этими значениями и не сохраняет их: параметры подбираются на прогонах, а не правятся вслепую', 'Calculul pornește cu aceste valori fără a le salva: parametrii se aleg pe rulări', 'The run uses these values without storing them: parameters are chosen by comparing runs');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.p.maxFill', 'ui', 'Потолок налива, % ёмкости', 'Plafon de umplere, % capacitate', 'Fill cap, % of capacity');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.p.targetFill', 'ui', 'Целевой уровень, %', 'Nivel țintă, %', 'Target level, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.p.trigger', 'ui', 'Порог заказа, суток покрытия', 'Prag de comandă, zile de acoperire', 'Order trigger, days of cover');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.p.maxCover', 'ui', 'Потолок запаса, суток', 'Plafon de stoc, zile', 'Stock cap, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.p.lead', 'ui', 'Плечо поставки, суток', 'Termen de livrare, zile', 'Lead time, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.p.service', 'ui', 'Уровень сервиса, %', 'Nivel de serviciu, %', 'Service level, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.p.minDrop', 'ui', 'Минимальный завоз, л', 'Livrare minimă, l', 'Minimum drop, l');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.station', 'ui', 'Станция', 'Stație', 'Station');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.source', 'ui', 'Источник', 'Sursă', 'Source');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.grades', 'ui', 'Виды топлива', 'Tipuri de combustibil', 'Fuel grades');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.grade', 'ui', 'Вид топлива', 'Tip de combustibil', 'Fuel grade');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.liters', 'ui', 'литров', 'litri', 'litres');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.lPerDay', 'ui', 'л/сут', 'l/zi', 'l/day');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.minCover', 'ui', 'До сухого бака, сут', 'Până la rezervor gol, zile', 'Days to dry');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.toDry', 'ui', 'До сухого', 'Până la gol', 'To dry');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.coverAfter', 'ui', 'Хватит на, сут', 'Ajunge, zile', 'Cover after, d');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.toFill', 'ui', 'К наливу', 'De încărcat', 'To fill');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.ullage', 'ui', 'Свободно', 'Spațiu liber', 'Ullage');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.ullageHint', 'ui', 'Больше свободной ёмкости залить нельзя — это не предупреждение, а физика: слив остановится на середине, остаток вернётся на нефтебазу', 'Nu se poate încărca peste spațiul liber — descărcarea se oprește la mijloc, restul se întoarce la depozit', 'You cannot load beyond the ullage — the discharge stops midway and the rest returns to the depot');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.tank', 'ui', 'Резервуар', 'Rezervor', 'Tank');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.tanks', 'ui', 'резервуаров', 'rezervoare', 'tanks');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.dailyRate', 'ui', 'Отпуск', 'Consum', 'Daily rate');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.needBy', 'ui', 'Нужно к', 'Necesar până la', 'Needed by');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.toDeliver', 'ui', 'К завозу', 'De livrat', 'To deliver');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.orders', 'ui', 'заказов', 'comenzi', 'orders');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.dryRisk', 'ui', 'Риск сухого бака', 'Risc de rezervor gol', 'Dry tank risk');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.noOrders', 'ui', 'Заказов нет — нажмите «Рассчитать заказ»', 'Nu există comenzi — apăsați «Calculează comanda»', 'No orders — press “Calculate order”');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.s.draft', 'ui', 'Черновик', 'Ciornă', 'Draft');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.s.approved', 'ui', 'Утверждён', 'Aprobat', 'Approved');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.s.planned', 'ui', 'В рейсе', 'În cursă', 'On trip');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.s.delivered', 'ui', 'Доставлен', 'Livrat', 'Delivered');

-- ==================== Нефтебаза ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.depotTitle', 'ui', 'Нефтебаза и импорт', 'Depozit și import', 'Depot and import');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.depotSub', 'ui', 'Второй эшелон: запас базы против суточной потребности всей сети и плеча импорта', 'Al doilea eșalon: stocul depozitului față de consumul zilnic al rețelei și termenul de import', 'Second echelon: depot stock against the network daily demand and the import lead time');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.fill', 'ui', 'Заполнение', 'Umplere', 'Fill');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.netDaily', 'ui', 'Сеть, л/сут', 'Rețea, l/zi', 'Network, l/day');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.coverNet', 'ui', 'Покрытие сети, сут', 'Acoperirea rețelei, zile', 'Network cover, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.deficit', 'ui', 'Дефицит, л', 'Deficit, l', 'Deficit, l');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.importDue', 'ui', 'Импорт', 'Import', 'Import');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.orderImport', 'ui', 'размещать сейчас', 'de plasat acum', 'place now');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.enough', 'ui', 'хватает', 'suficient', 'sufficient');

-- ==================== Рейсы и телеметрия ====================
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.tripsTitle', 'ui', 'Рейсы бензовозов', 'Curse cisterne', 'Tanker trips');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.tripsSub', 'ui', 'Одна секция — один вид топлива и один резервуар. GPS-датчики на аутсорсе', 'O secție — un tip de combustibil și un rezervor. Senzorii GPS sunt externalizați', 'One compartment — one grade and one tank. GPS sensors are outsourced');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.plan', 'ui', 'Спланировать рейсы', 'Planifică cursele', 'Plan trips');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.planned', 'ui', 'Рейсов создано', 'Curse create', 'Trips created');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.noTrips', 'ui', 'Рейсов нет — утвердите заказы и нажмите «Спланировать рейсы»', 'Nu există curse — aprobați comenzile și planificați', 'No trips — approve the orders and press “Plan trips”');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.trip', 'ui', 'Рейс', 'Cursă', 'Trip');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.truck', 'ui', 'Бензовоз', 'Cisternă', 'Tanker');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.trucks', 'ui', 'в работе', 'în lucru', 'in progress');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.driver', 'ui', 'Водитель', 'Șofer', 'Driver');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.load', 'ui', 'Загрузка', 'Încărcare', 'Load');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.stops', 'ui', 'Точек', 'Puncte', 'Stops');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.stopsTitle', 'ui', 'Слив по секциям', 'Descărcare pe secții', 'Discharge by compartment');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.comp', 'ui', 'Секция', 'Secție', 'Compartment');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.comps', 'ui', 'секций', 'secții', 'compartments');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.eta', 'ui', 'Прибытие', 'Sosire', 'ETA');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.lastPing', 'ui', 'Последний сигнал', 'Ultimul semnal', 'Last ping');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.points', 'ui', 'точек трека', 'puncte de traseu', 'track points');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.depart', 'ui', 'Выехал', 'A plecat', 'Departed');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.finish', 'ui', 'Завершить рейс', 'Încheie cursa', 'Finish trip');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.t.planned', 'ui', 'Запланирован', 'Planificat', 'Planned');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.t.loading', 'ui', 'Налив', 'Încărcare', 'Loading');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.t.en_route', 'ui', 'В пути', 'În drum', 'En route');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.t.done', 'ui', 'Завершён', 'Încheiat', 'Done');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.t.cancelled', 'ui', 'Отменён', 'Anulat', 'Cancelled');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.gpsTitle', 'ui', 'События телеметрии', 'Evenimente de telemetrie', 'Telemetry events');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.gpsSub', 'ui', 'Стоянки вне маршрута, отклонения, срыв пломбы, превышение скорости', 'Opriri în afara traseului, abateri, sigiliu rupt, viteză excesivă', 'Stops off route, deviations, broken seal, speeding');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.gpsAlerts', 'ui', 'Сигналы GPS', 'Semnale GPS', 'GPS alerts');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.analyze', 'ui', 'Разобрать треки', 'Analizează traseele', 'Analyze tracks');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.gpsAnalyzed', 'ui', 'Событий найдено', 'Evenimente găsite', 'Events found');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.noEvents', 'ui', 'Событий нет', 'Nu există evenimente', 'No events');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.activeTrips', 'ui', 'Рейсов в работе', 'Curse active', 'Active trips');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.e.unplanned_stop', 'ui', 'Стоянка вне маршрута', 'Oprire în afara traseului', 'Unplanned stop');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.e.seal_open', 'ui', 'Срыв пломбы', 'Sigiliu deschis', 'Seal open');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.e.route_deviation', 'ui', 'Отклонение от маршрута', 'Abatere de la traseu', 'Route deviation');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.e.speeding', 'ui', 'Превышение скорости', 'Viteză excesivă', 'Speeding');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('fu.e.long_idle', 'ui', 'Долгий простой', 'Staționare lungă', 'Long idle');

COMMIT;
