-- ============================================================
-- Планограммы: строки интерфейса для логистики, поставщиков,
-- конкурентов и анализа рынков (RU / RO / EN).
-- Дополняет sql/83_plg_i18n.sql и sql/86_plg_i18n_gen.sql.
-- ============================================================

-- ==================== Навигация ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.logistics',   'nav', 'Логистика завоза', 'Logistica livrărilor', 'Inbound logistics');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.suppliers',   'nav', 'Поставщики',       'Furnizori',            'Suppliers');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.competitors', 'nav', 'Конкуренты',       'Concurenți',           'Competitors');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.markets',     'nav', 'Рынки стран',      'Piețe internaționale', 'Country markets');

-- ==================== Логистика и Гант ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.gantt',       'ui', 'График завоза',            'Graficul livrărilor',      'Delivery schedule');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.ganttSub',    'ui', 'Окна разгрузки по машинам: поставщик → РЦ, РЦ → магазин, прямой завоз', 'Ferestre de descărcare pe camioane: furnizor → CD, CD → magazin, livrare directă', 'Unloading windows by vehicle: supplier → DC, DC → store, direct delivery');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.groupBy',     'ui', 'Строки',                   'Rânduri',                  'Rows');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.byVehicle',   'ui', 'По машинам',               'Pe camioane',              'By vehicle');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.byStore',     'ui', 'По магазинам',             'Pe magazine',              'By store');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.byDock',      'ui', 'По докам РЦ',              'Pe docurile CD',           'By DC dock');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.bySupplier',  'ui', 'По поставщикам',           'Pe furnizori',             'By supplier');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.day',         'ui', 'День',                     'Ziua',                     'Day');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.dc',          'ui', 'Логистический центр',      'Centru de distribuție',    'Distribution centre');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.dcs',         'ui', 'Логистические центры',     'Centre de distribuție',    'Distribution centres');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.vehicles',    'ui', 'Транспорт',                'Transport',                'Vehicles');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.vehicle',     'ui', 'Машина',                   'Camion',                   'Vehicle');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.plate',       'ui', 'Госномер',                 'Număr de înmatriculare',   'Plate');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.carrier',     'ui', 'Перевозчик',               'Transportator',            'Carrier');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.driver',      'ui', 'Водитель',                 'Șofer',                    'Driver');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.own',         'ui', 'Свой парк',                'Parc propriu',             'Own fleet');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.shipment',    'ui', 'Рейс',                     'Cursă',                    'Shipment');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.shipments',   'ui', 'Рейсы завоза',             'Curse de livrare',         'Delivery trips');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.window',      'ui', 'Окно разгрузки',           'Fereastră de descărcare',  'Unloading window');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.dock',        'ui', 'Док',                      'Doc',                      'Dock');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.docks',       'ui', 'Ворот разгрузки',          'Docuri de descărcare',     'Unloading docks');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.pallets',     'ui', 'Паллет',                   'Paleți',                   'Pallets');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.weight',      'ui', 'Вес, кг',                  'Greutate, kg',             'Weight, kg');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.temp',        'ui', 'Температурный режим',      'Regim de temperatură',     'Temperature mode');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.ambient',     'ui', 'Сухой',                    'Uscat',                    'Ambient');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.chilled',     'ui', 'Охлаждённый',              'Refrigerat',               'Chilled');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.frozen',      'ui', 'Замороженный',             'Congelat',                 'Frozen');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.delay',       'ui', 'Опоздание, мин',           'Întârziere, min',          'Delay, min');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.onTime',      'ui', 'В окно',                   'În fereastră',             'On time');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.late',        'ui', 'С опозданием',             'Cu întârziere',            'Late');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.distance',    'ui', 'Расстояние, км',           'Distanță, km',             'Distance, km');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.utilization', 'ui', 'Загрузка парка',           'Utilizarea parcului',      'Fleet utilisation');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.trips',       'ui', 'Рейсов',                   'Curse',                    'Trips');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.hours',       'ui', 'Часов в рейсах',           'Ore în curse',             'Hours on the road');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.newShipment', 'ui', 'Новый рейс',               'Cursă nouă',               'New shipment');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.newVehicle',  'ui', 'Новая машина',             'Camion nou',               'New vehicle');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('lg.newDc',       'ui', 'Новый РЦ',                 'CD nou',                   'New DC');

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.in_transit', 'status', 'В пути',      'În tranzit',   'In transit');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.unloading',  'status', 'Разгрузка',   'Descărcare',   'Unloading');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.delayed',    'status', 'Задержан',    'Întârziat',    'Delayed');

-- ==================== Поставщики ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.title',      'ui', 'Взаимоотношения с поставщиками', 'Relațiile cu furnizorii', 'Supplier relationships');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.graphSub',   'ui', 'Толщина связи — годовой оборот по товарной группе', 'Grosimea legăturii — rulajul anual pe grupa de produse', 'Link thickness is the annual turnover in that product group');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.supplier',   'ui', 'Поставщик',        'Furnizor',           'Supplier');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.type',       'ui', 'Тип',              'Tip',                'Type');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.rating',     'ui', 'Рейтинг',          'Rating',             'Rating');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.otif',       'ui', 'OTIF, %',          'OTIF, %',            'OTIF, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.turnover',   'ui', 'Годовой оборот',   'Rulaj anual',        'Annual turnover');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.key',        'ui', 'Ключевой',         'Cheie',              'Key');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.deliversTo', 'ui', 'Завозит на',       'Livrează la',        'Delivers to');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.contacts',   'ui', 'Контакты',         'Contacte',           'Contacts');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.contact',    'ui', 'Контактное лицо',  'Persoană de contact','Contact person');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.role',       'ui', 'Роль',             'Rol',                'Role');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.phone',      'ui', 'Телефон',          'Telefon',            'Phone');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.email',      'ui', 'E-mail',           'E-mail',             'E-mail');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.primary',    'ui', 'Основной',         'Principal',          'Primary');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.contracts',  'ui', 'Контракты',        'Contracte',          'Contracts');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.contract',   'ui', 'Контракт',         'Contract',           'Contract');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.payment',    'ui', 'Отсрочка, дней',   'Termen de plată, zile','Payment terms, days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.retro',      'ui', 'Ретро-бонус, %',   'Retro-bonus, %',     'Retro bonus, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.marketing',  'ui', 'Маркетинговый взнос','Taxă de marketing','Marketing fee');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.incoterms',  'ui', 'Условия поставки', 'Condiții de livrare','Incoterms');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.minOrder',   'ui', 'Мин. заказ',       'Comandă minimă',     'Min. order');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.expiring',   'ui', 'Истекает',         'Expiră',             'Expiring');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.daysLeft',   'ui', 'Дней до конца',    'Zile rămase',        'Days left');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.groups',     'ui', 'Товарные группы',  'Grupe de produse',   'Product groups');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.share',      'ui', 'Доля в закупке, %','Cotă în achiziții, %','Share of purchasing, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.margin',     'ui', 'Маржа, %',         'Marjă, %',           'Margin, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.newSupplier','ui', 'Новый поставщик',  'Furnizor nou',       'New supplier');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.newContact', 'ui', 'Новый контакт',    'Contact nou',        'New contact');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.newContract','ui', 'Новый контракт',   'Contract nou',       'New contract');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('sp.card',       'ui', 'Карточка поставщика','Fișa furnizorului','Supplier card');

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.on_hold',    'status', 'Приостановлен', 'Suspendat',   'On hold');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.terminated', 'status', 'Расторгнут',    'Reziliat',    'Terminated');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.prospect',   'status', 'Потенциальный', 'Potențial',   'Prospect');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.expired',    'status', 'Истёк',         'Expirat',     'Expired');

-- ==================== Конкуренты ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.title',      'ui', 'Анализ конкурентов',  'Analiza concurenților',  'Competitor analysis');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.indexSub',   'ui', 'Ценовой индекс: 100 = цена конкурента равна нашей. Ниже 100 — конкурент дешевле', 'Indice de preț: 100 = prețul concurentului este egal cu al nostru', 'Price index: 100 means the competitor matches our price; below 100 they are cheaper');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.competitor', 'ui', 'Конкурент',           'Concurent',              'Competitor');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.positioning','ui', 'Позиционирование',    'Poziționare',            'Positioning');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.discount',   'ui', 'Дискаунтер',          'Discounter',             'Discounter');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.mid',        'ui', 'Средний сегмент',     'Segment mediu',          'Mid-market');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.premium',    'ui', 'Премиум',             'Premium',                'Premium');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.priceIndex', 'ui', 'Ценовой индекс',      'Indice de preț',         'Price index');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.ourPrice',   'ui', 'Наша цена',           'Prețul nostru',          'Our price');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.theirPrice', 'ui', 'Цена конкурента',     'Prețul concurentului',   'Competitor price');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.diff',       'ui', 'Разница',             'Diferență',              'Difference');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.weExpensive','ui', 'Мы дороже',           'Noi mai scump',          'We are pricier');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.weCheap',    'ui', 'Мы дешевле',          'Noi mai ieftin',         'We are cheaper');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.parity',     'ui', 'Паритет',             'Paritate',               'Parity');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.monitored',  'ui', 'SKU в мониторинге',   'SKU monitorizate',       'SKUs monitored');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.lastCheck',  'ui', 'Последний замер',     'Ultima verificare',      'Last check');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.source',     'ui', 'Источник',            'Sursă',                  'Source');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.theirSuppliers','ui','Поставщики конкурента','Furnizorii concurentului','Competitor suppliers');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.shared',     'ui', 'Общий с нами',        'Comun cu noi',           'Shared with us');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.exclusive',  'ui', 'Эксклюзив конкурента','Exclusiv concurentului', 'Competitor exclusive');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.storeCount', 'ui', 'Магазинов',           'Magazine',               'Stores');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.share',      'ui', 'Доля рынка, %',       'Cotă de piață, %',       'Market share, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.privateLabel','ui','СТМ, %',              'Marcă proprie, %',       'Private label, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.newCompetitor','ui','Новый конкурент',    'Concurent nou',          'New competitor');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.importPrices','ui', 'Импорт замеров цен', 'Import verificări preț', 'Import price checks');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.importHint', 'ui', 'CSV: код_конкурента;код_товара;дата;цена;промо', 'CSV: cod_concurent;cod_produs;dată;preț;promo', 'CSV: competitor_code;product_code;date;price;promo');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cp.imported',   'ui', 'Загружено замеров',   'Verificări încărcate',   'Price checks imported');

-- ==================== Рынки стран ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.title',       'ui', 'Рынки других стран',  'Piețele altor țări',    'International markets');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.bubbleSub',   'ui', 'Сети на карте: по горизонтали — число магазинов, по вертикали — средний чек, размер — выручка', 'Rețele: orizontal — număr de magazine, vertical — bon mediu, mărimea — venituri', 'Chains plotted by store count (x), average check (y) and revenue (bubble size)');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.market',      'ui', 'Рынок',               'Piață',                 'Market');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.country',     'ui', 'Страна',              'Țară',                  'Country');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.population',  'ui', 'Население, млн',      'Populație, mil.',       'Population, mln');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.gdp',         'ui', 'ВВП на душу',         'PIB pe cap de locuitor','GDP per capita');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.retailVolume','ui', 'Объём ритейла, млн',  'Volumul retailului, mil.','Retail volume, mln');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.modernTrade', 'ui', 'Современная торговля, %','Comerț modern, %',    'Modern trade, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.top5',        'ui', 'Доля топ-5 сетей, %', 'Cota top-5 rețele, %',  'Top-5 concentration, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.avgCheckEur', 'ui', 'Средний чек, €',      'Bon mediu, €',          'Average check, €');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.storesPer',   'ui', 'Магазинов на 100 тыс.','Magazine la 100 mii',  'Stores per 100k');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.chain',       'ui', 'Торговая сеть',       'Rețea comercială',      'Retail chain');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.chains',      'ui', 'Схожие сети',         'Rețele similare',       'Comparable chains');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.owner',       'ui', 'Владелец',            'Proprietar',            'Owner group');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.revenue',     'ui', 'Выручка, млн',        'Venituri, mil.',        'Revenue, mln');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.revPerStore', 'ui', 'Выручка на магазин',  'Venituri pe magazin',   'Revenue per store');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.revPerSqm',   'ui', 'Выручка с м²',        'Venituri pe m²',        'Revenue per sqm');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.avgSqm',      'ui', 'Средняя площадь, м²', 'Suprafață medie, m²',   'Average area, sqm');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.online',      'ui', 'Онлайн, %',           'Online, %',             'Online, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.benchmark',   'ui', 'Эталон',              'Etalon',                'Benchmark');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.leader',      'ui', 'Лидер рынка',         'Liderul pieței',        'Market leader');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.newMarket',   'ui', 'Новый рынок',         'Piață nouă',            'New market');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.newChain',    'ui', 'Новая сеть',          'Rețea nouă',            'New chain');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('mk.ourNetwork',  'ui', 'Наша сеть',           'Rețeaua noastră',       'Our network');

COMMIT;
