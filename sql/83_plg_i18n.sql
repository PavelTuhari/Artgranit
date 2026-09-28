-- ============================================================
-- Планограммы: словарь строк интерфейса (RU / RO / EN)
--
-- Единственный источник правды для подписей UI. Шаблон
-- templates/planograms.html загружает словарь через
-- GET /api/plg/i18n и рендерит интерфейс уже переведённым.
-- Добавление языка = новая колонка TEXT_<XX> + строка в PLG_REF_LANGS.
-- ============================================================

CREATE TABLE PLG_I18N (
  MSG_KEY    VARCHAR2(80)  NOT NULL,
  SCOPE      VARCHAR2(30)  DEFAULT 'ui',   -- ui / nav / status / message
  TEXT_RU    VARCHAR2(500) NOT NULL,
  TEXT_RO    VARCHAR2(500) NOT NULL,
  TEXT_EN    VARCHAR2(500) NOT NULL,
  UPDATED_AT TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_I18N PRIMARY KEY (MSG_KEY)
);
/

CREATE OR REPLACE TRIGGER PLG_I18N_BU
  BEFORE UPDATE ON PLG_I18N FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/

-- ==================== Навигация ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.home',          'nav', 'Главная',             'Acasă',                  'Home');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.planograms',    'nav', 'Планограммы',         'Planograme',             'Planograms');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.overview',      'nav', 'Обзор',               'Prezentare generală',    'Overview');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.storemap',      'nav', 'План магазина',       'Planul magazinului',     'Store map');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.plglist',       'nav', 'Список планограмм',   'Lista planogramelor',    'Planogram list');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.history',       'nav', 'История изменений',   'Istoricul modificărilor','Change history');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.analytics',     'nav', 'Аналитика',           'Analitică',              'Analytics');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.products',      'nav', 'Товары',              'Produse',                'Products');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.promos',        'nav', 'Акции',               'Promoții',               'Promotions');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.equipment',     'nav', 'Оборудование',        'Echipamente',            'Equipment');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.tasks',         'nav', 'Задачи',              'Sarcini',                'Tasks');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.docs',          'nav', 'Документы',           'Documente',              'Documents');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.notifications', 'nav', 'Уведомления',         'Notificări',             'Notifications');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('nav.settings',      'nav', 'Настройки',           'Setări',                 'Settings');

-- ==================== Шапка и общие элементы ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('app.title',      'ui', 'Планограммы',                   'Planograme',                        'Planograms');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('app.subtitle',   'ui', 'Внутренний портал',             'Portal intern',                     'Internal portal');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.search',      'ui', 'Поиск товаров, планограмм, отчётов…', 'Căutare produse, planograme, rapoarte…', 'Search products, planograms, reports…');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.store',       'ui', 'Магазин',                       'Magazin',                           'Store');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.updated',     'ui', 'Данные обновлены',              'Date actualizate',                  'Data updated');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.refresh',     'ui', 'Обновить данные',               'Actualizează datele',               'Refresh data');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.refreshing',  'ui', 'Обновление…',                   'Se actualizează…',                  'Refreshing…');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.language',    'ui', 'Язык',                          'Limba',                             'Language');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.save',        'ui', 'Сохранить',                     'Salvează',                          'Save');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.cancel',      'ui', 'Отмена',                        'Anulează',                          'Cancel');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.close',       'ui', 'Закрыть',                       'Închide',                           'Close');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.delete',      'ui', 'Удалить',                       'Șterge',                            'Delete');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.edit',        'ui', 'Изменить',                      'Modifică',                          'Edit');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.add',         'ui', 'Добавить',                      'Adaugă',                            'Add');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.saved',       'ui', 'Сохранено',                     'Salvat',                            'Saved');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.deleted',     'ui', 'Удалено',                       'Șters',                             'Deleted');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.confirmDel',  'ui', 'Удалить запись?',               'Ștergeți înregistrarea?',           'Delete this record?');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.empty',       'ui', 'Нет данных',                    'Nu există date',                    'No data');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.loading',     'ui', 'Загрузка…',                     'Se încarcă…',                       'Loading…');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.error',       'ui', 'Ошибка',                        'Eroare',                            'Error');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.all',         'ui', 'Все',                           'Toate',                             'All');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.back',        'ui', 'К списку модулей',              'La lista modulelor',                'Back to modules');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('ui.initDemo',    'ui', 'Загрузить демо-данные',         'Încarcă date demo',                 'Load demo data');

-- ==================== Обзор / карта ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('map.title',     'ui', 'Карта магазина',                  'Harta magazinului',                'Store map');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('map.subtitle',  'ui', 'Актуальная планограмма и проходимость', 'Planograma actuală și traficul', 'Current planogram and traffic');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('map.legend',    'ui', 'Проходимость',                    'Trafic',                           'Traffic');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('traffic.low',   'ui', 'Низкий',                          'Scăzut',                           'Low');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('traffic.medium','ui', 'Средний',                         'Mediu',                            'Medium');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('traffic.high',  'ui', 'Высокий',                         'Ridicat',                          'High');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('traffic.peak',  'ui', 'Пиковый',                         'Maxim',                            'Peak');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('map.entrance',  'ui', 'ВХОД',                            'INTRARE',                          'ENTRANCE');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('map.checkout',  'ui', '100% ПРОХОДИМОСТЬ',               '100% TRAFIC',                      '100% FOOTFALL');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('map.zoneInfo',  'ui', 'Зона',                            'Zonă',                             'Zone');

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('donut.title',    'ui', 'Проходимость',                   'Trafic',                           'Footfall');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('donut.subtitle', 'ui', 'Текущая проходимость магазина',  'Traficul curent al magazinului',   'Current store footfall');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cat.title',      'ui', 'Топ категории',                  'Top categorii',                    'Top categories');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('cat.subtitle',   'ui', 'По проходимости',                'După trafic',                      'By footfall');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('promo.title',    'ui', 'Активные акции',                 'Promoții active',                  'Active promotions');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('promo.subtitle', 'ui', 'Сейчас в магазине',              'Acum în magazin',                  'Currently in store');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('promo.until',    'ui', 'До',                             'Până la',                          'Until');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('notify.title',   'ui', 'Уведомления',                    'Notificări',                       'Notifications');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('notify.unread',  'ui', 'непрочитанных',                  'necitite',                         'unread');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('notify.viewAll', 'ui', 'Смотреть все уведомления →',     'Vezi toate notificările →',        'View all notifications →');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('notify.markRead','ui', 'Отметить прочитанным',           'Marchează ca citit',               'Mark as read');

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('metrics.title',    'ui', 'Динамика показателей',        'Dinamica indicatorilor',           'Metrics trend');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('metrics.subtitle', 'ui', 'За последние дни',            'În ultimele zile',                 'Over the last days');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('metric.traffic',   'ui', 'Общий трафик',                'Trafic total',                     'Total traffic');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('metric.buyers',    'ui', 'Покупатели',                  'Cumpărători',                      'Buyers');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('metric.conversion','ui', 'Конверсия',                   'Conversie',                        'Conversion');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('metric.avgCheck',  'ui', 'Средний чек',                 'Bon mediu',                        'Average check');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('metric.revenue',   'ui', 'Выручка',                     'Venituri',                         'Revenue');

-- ==================== Планограммы ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.code',       'ui', 'Код',                    'Cod',                    'Code');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.name',       'ui', 'Название',               'Denumire',               'Name');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.zone',       'ui', 'Зона',                   'Zonă',                   'Zone');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.version',    'ui', 'Версия',                 'Versiune',               'Version');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.status',     'ui', 'Статус',                 'Status',                 'Status');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.validFrom',  'ui', 'Действует с',            'Valabil de la',          'Valid from');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.validTo',    'ui', 'Действует до',           'Valabil până la',        'Valid to');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.author',     'ui', 'Автор',                  'Autor',                  'Author');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.approvedBy', 'ui', 'Утвердил',               'Aprobat de',             'Approved by');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.items',      'ui', 'Позиций',                'Poziții',                'Items');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.facings',    'ui', 'Фейсингов',              'Facing-uri',             'Facings');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.sku',        'ui', 'SKU',                    'SKU',                    'SKU');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.shelfShare', 'ui', 'Доля полки, %',          'Cota de raft, %',        'Shelf share, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.new',        'ui', 'Новая планограмма',      'Planogramă nouă',        'New planogram');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.approve',    'ui', 'Утвердить',              'Aprobă',                 'Approve');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.activate',   'ui', 'Ввести в действие',      'Pune în vigoare',        'Activate');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.archive',    'ui', 'В архив',                'Arhivează',              'Archive');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.itemsTitle', 'ui', 'Позиции выкладки',       'Pozițiile expunerii',    'Layout items');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.shelf',      'ui', 'Полка',                  'Raft',                   'Shelf');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.position',   'ui', 'Позиция',                'Poziție',                'Position');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('plg.lastChange', 'ui', 'Последнее изменение',    'Ultima modificare',      'Last change');

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('hist.action',   'ui', 'Действие',      'Acțiune',       'Action');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('hist.field',    'ui', 'Поле',          'Câmp',          'Field');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('hist.oldValue', 'ui', 'Было',          'Anterior',      'Old value');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('hist.newValue', 'ui', 'Стало',         'Actual',        'New value');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('hist.by',       'ui', 'Кто изменил',   'Modificat de',  'Changed by');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('hist.at',       'ui', 'Когда',         'Când',          'Changed at');

-- ==================== Товары, оборудование, акции, задачи, документы ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('prod.category',  'ui', 'Категория',        'Categorie',        'Category');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('prod.brand',     'ui', 'Бренд',            'Brand',            'Brand');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('prod.barcode',   'ui', 'Штрихкод',         'Cod de bare',      'Barcode');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('prod.price',     'ui', 'Цена',             'Preț',             'Price');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('prod.size',      'ui', 'Габариты, мм',     'Dimensiuni, mm',   'Dimensions, mm');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('prod.placements','ui', 'Размещений',       'Amplasări',        'Placements');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('prod.new',       'ui', 'Новый товар',      'Produs nou',       'New product');

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('eq.type',     'ui', 'Тип оборудования', 'Tip echipament',  'Fixture type');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('eq.shelves',  'ui', 'Полок',            'Rafturi',         'Shelves');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('eq.serial',   'ui', 'Серийный номер',   'Număr de serie',  'Serial number');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('eq.new',      'ui', 'Новое оборудование','Echipament nou', 'New fixture');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('eq.occupancy','ui', 'Занятость полок',  'Ocuparea rafturilor','Shelf occupancy');

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('pr.type',      'ui', 'Тип акции',   'Tip promoție', 'Promo type');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('pr.discount',  'ui', 'Скидка, %',   'Reducere, %',  'Discount, %');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('pr.period',    'ui', 'Период',      'Perioadă',     'Period');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('pr.daysLeft',  'ui', 'Осталось дней','Zile rămase',  'Days left');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('pr.products',  'ui', 'Товаров',     'Produse',      'Products');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('pr.new',       'ui', 'Новая акция', 'Promoție nouă','New promotion');

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('task.type',     'ui', 'Тип задачи', 'Tip sarcină',  'Task type');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('task.priority', 'ui', 'Приоритет',  'Prioritate',   'Priority');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('task.assignee', 'ui', 'Исполнитель','Responsabil',  'Assignee');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('task.due',      'ui', 'Срок',       'Termen',       'Due date');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('task.overdue',  'ui', 'Просрочена', 'Întârziată',   'Overdue');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('task.new',      'ui', 'Новая задача','Sarcină nouă','New task');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('task.done',     'ui', 'Завершить',  'Finalizează',  'Complete');

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('doc.type',  'ui', 'Тип документа', 'Tip document', 'Document type');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('doc.file',  'ui', 'Файл',          'Fișier',       'File');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('doc.size',  'ui', 'Размер',        'Mărime',       'Size');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('doc.author','ui', 'Загрузил',      'Încărcat de',  'Uploaded by');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('doc.open',  'ui', 'Открыть',       'Deschide',     'Open');

-- ==================== Аналитика и настройки ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('an.title',      'ui', 'Аналитика проходимости',   'Analitica traficului',        'Traffic analytics');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('an.byZone',     'ui', 'Проходимость по зонам',    'Trafic pe zone',              'Traffic by zone');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('an.byCategory', 'ui', 'Показатели по категориям', 'Indicatori pe categorii',     'Category performance');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('an.period',     'ui', 'Период',                   'Perioadă',                    'Period');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('an.visits',     'ui', 'Посещений',                'Vizite',                      'Visits');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('an.sales',      'ui', 'Продажи',                  'Vânzări',                     'Sales');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('an.dwell',      'ui', 'Время в зоне, сек',        'Timp în zonă, sec',           'Dwell time, sec');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('an.pickups',    'ui', 'Взятий с полки',           'Preluări de pe raft',         'Shelf pickups');

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('set.title',    'ui', 'Настройки модуля',        'Setările modulului',         'Module settings');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('set.param',    'ui', 'Параметр',                'Parametru',                  'Parameter');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('set.value',    'ui', 'Значение',                'Valoare',                    'Value');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('set.descr',    'ui', 'Описание',                'Descriere',                  'Description');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('set.audit',    'ui', 'Журнал действий',         'Jurnalul acțiunilor',        'Audit log');

-- ==================== Статусы и приоритеты (для бейджей) ====================

INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.new',         'status', 'Новая',          'Nouă',        'New');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.in_progress', 'status', 'В работе',       'În lucru',    'In progress');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.review',      'status', 'На проверке',    'În verificare','Review');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.done',        'status', 'Выполнена',      'Finalizată',  'Done');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.cancelled',   'status', 'Отменена',       'Anulată',     'Cancelled');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.active',      'status', 'Активна',        'Activă',      'Active');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.planned',     'status', 'Запланирована',  'Planificată', 'Planned');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('st.finished',    'status', 'Завершена',      'Încheiată',   'Finished');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('prio.high',      'status', 'Высокий',        'Ridicată',    'High');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('prio.medium',    'status', 'Средний',        'Medie',       'Medium');
INSERT INTO PLG_I18N (MSG_KEY, SCOPE, TEXT_RU, TEXT_RO, TEXT_EN) VALUES ('prio.low',       'status', 'Низкий',         'Scăzută',     'Low');

COMMIT;
