# Модуль «Планограммы» (Planograms)

Управление выкладкой товара, зонами торгового зала, проходимостью, акциями,
задачами мерчандайзинга и версионированием планограмм.

Макет-источник: `/Users/pt/Projects.AI/TBControl/Modules/Planograms` (React + Vite).
Реализация в Artgranit выполнена по правилам `CLAUDE.md`: Oracle-first, normalized-first,
собственный префикс объектов, отдельный DDL-деплой.

| | |
|---|---|
| Префикс Oracle-объектов | `PLG_` |
| UI-маршрут | `/UNA.md/orasldev/planograms` |
| API-префикс | `/api/plg/*` |
| Контроллер | [controllers/planogram_controller.py](../../controllers/planogram_controller.py) |
| Шаблон | [templates/planograms.html](../../templates/planograms.html) |
| DDL | `sql/80_plg_tables.sql`, `81_plg_views.sql`, `82_plg_demo_data.sql`, `83_plg_i18n.sql` |
| Языки | **RU / RO / EN** |

---

## 1. Мультиязычность

Модуль спроектирован трёхъязычным с первого релиза. Схема хранения:

1. **Справочники и master-data** — три колонки на сущность:
   `NAME_RU` / `NAME_RO` / `NAME_EN` (для задач и документов — `TITLE_*`,
   для уведомлений — `TEXT_*`, для истории — `SUMMARY_*`, для настроек — `DESCR_*`).
2. **Строки интерфейса** — словарь `PLG_I18N` (`MSG_KEY`, `SCOPE`, `TEXT_RU`, `TEXT_RO`, `TEXT_EN`).
   Это единственный источник правды для подписей UI; в шаблоне нет захардкоженных переводов.
3. **Реестр языков** — `PLG_REF_LANGS` (`ru` / `ro` / `en`, флаг `IS_DEFAULT`).

Контроллер получает язык параметром `?lang=ru|ro|en` (неизвестный код → `ru`) и методом
`_localize()` добавляет к каждой строке сводный ключ без суффикса: `name_ru/name_ro/name_en`
→ `name` на выбранном языке (fallback на русский, если перевод пуст). Исходные языковые
колонки **сохраняются в ответе** — они нужны формам, где оператор правит все три языка сразу.

Во избежание коллизий представления отдают локализуемые названия справочников под
именами `*_NAME_RU/RO/EN` (`STATUS_NAME_*`, `ZONE_TYPE_NAME_*`, `FIXTURE_TYPE_NAME_*`,
`PROMO_TYPE_NAME_*`, `TASK_TYPE_NAME_*`, `DOC_TYPE_NAME_*`), чтобы не затирать колонку-код
(`STATUS`, `ZONE_TYPE`, …).

**Как добавить четвёртый язык:**
1. `ALTER TABLE` — добавить `NAME_XX` / `TEXT_XX` / `TITLE_XX` / `SUMMARY_XX` / `DESCR_XX`.
2. Добавить колонку в представления `V_PLG_*`.
3. `INSERT INTO PLG_REF_LANGS`.
4. В контроллере расширить `PlanogramController.LANGS`.
Шаблон подхватит новый язык автоматически: переключатель строится из `PLG_REF_LANGS`.

---

## 2. Oracle-модель данных

### Справочники

| Таблица | Назначение |
|---|---|
| `PLG_REF_LANGS` | Поддерживаемые языки модуля |
| `PLG_REF_ZONE_TYPES` | Типы зон: `dept`, `promo_island`, `checkout`, `entrance`, `storage`, `service`, `wc` |
| `PLG_REF_FIXTURE_TYPES` | Типы оборудования: `shelf`, `cooler`, `freezer`, `pallet`, `island`, `endcap`, `rack` |
| `PLG_REF_PLG_STATUSES` | Жизненный цикл планограммы: `draft` → `review` → `approved` → `active` → `archived` / `rejected` |
| `PLG_REF_TASK_TYPES` | Типы задач мерчандайзинга |
| `PLG_REF_PROMO_TYPES` | Типы акций |
| `PLG_REF_DOC_TYPES` | Типы документов |

### Master-data

| Таблица | Назначение |
|---|---|
| `PLG_STORES` | Магазины: габариты зала, координатная сетка карты (`MAP_WIDTH` × `MAP_HEIGHT`), число касс |
| `PLG_CATEGORIES` | Иерархический справочник категорий товара |
| `PLG_ZONES` | Зоны зала с координатами `POS_X/POS_Y/WIDTH/HEIGHT` в системе карты магазина |
| `PLG_FIXTURES` | Торговое оборудование внутри зоны (координаты карты + реальные габариты в мм) |
| `PLG_PRODUCTS` | Карточка товара для выкладки: габариты фейсинга, штрихкод, цена |

### Документы

| Таблица | Назначение |
|---|---|
| `PLG_PLANOGRAMS` | Заголовок планограммы: зона, версия, статус, срок действия, автор, утвердивший |
| `PLG_PLANOGRAM_ITEMS` | Позиции выкладки: товар на полке оборудования (`SHELF_NO`, `POSITION_NO`, `FACINGS`) |
| `PLG_PLANOGRAM_HISTORY` | Append-only история изменений (создание, правки, смена статуса) |
| `PLG_PROMOS` + `PLG_PROMO_ZONES` + `PLG_PROMO_PRODUCTS` | Акции и их привязка к зонам и товарам |
| `PLG_TASKS` | Задачи мерчандайзинга |
| `PLG_DOCUMENTS` | Документы модуля (PDF планограмм, инструкции, фотоотчёты) |

### Метрики (append-only факты)

| Таблица | Назначение |
|---|---|
| `PLG_ZONE_TRAFFIC` | Проходимость зон по дням/часам — источник тепловой карты |
| `PLG_STORE_METRICS` | Дневные показатели магазина: трафик, покупатели, конверсия, средний чек, выручка |
| `PLG_CATEGORY_METRICS` | Показатели по категориям: посещения, продажи |

### Служебные

| Таблица | Назначение |
|---|---|
| `PLG_I18N` | Словарь строк интерфейса |
| `PLG_NOTIFICATIONS` | Уведомления модуля (уровень `info` / `warn` / `alert`) |
| `PLG_SETTINGS` | Настройки модуля (пороги проходимости, валюта, интервал обновления) |
| `PLG_EVENT_LOG` | Append-only аудит действий пользователя |

> Колонка уровня уведомления названа `LEVEL_CODE`, а не `LEVEL` — `LEVEL` зарезервировано Oracle.

### Представления

`V_PLG_ZONES`, `V_PLG_FIXTURES`, `V_PLG_PRODUCTS`, `V_PLG_PLANOGRAMS`,
`V_PLG_PLANOGRAM_ITEMS`, `V_PLG_HISTORY`, `V_PLG_PROMOS`, `V_PLG_TOP_CATEGORIES`,
`V_PLG_STORE_METRICS`, `V_PLG_TASKS`, `V_PLG_DOCUMENTS`, `V_PLG_DASHBOARD_STATS`.

Представления вычисляют то, что не должно дублироваться в коде: уровень проходимости зоны
(`TRAFFIC_LEVEL`), фактический статус акции по датам (`EFFECTIVE_STATUS`), долю и прирост
категории (`SHARE_PCT`, `DELTA_PCT`), дельты показателей день-к-дню, признак просрочки задачи
(`IS_OVERDUE`), сводку дашборда по магазину.

---

## 3. UI-маршруты и разделы

Единственный HTTP-маршрут страницы: **`/UNA.md/orasldev/planograms`** (требует аутентификации).
Внутри — SPA-навигация по 12 разделам, полностью повторяющая структуру макета:

| Раздел | Что показывает |
|---|---|
| Главная / Обзор | SVG-карта зала с тепловой картой, донат проходимости, топ-5 категорий, активные акции, уведомления, 5 карточек показателей со спарклайнами (7/14/30 дней) |
| Планограммы → План магазина | Полноразмерная карта + таблица проходимости по зонам |
| Планограммы → Список планограмм | Реестр с фильтром по статусу, карточка планограммы (позиции + история), переходы по статусам |
| Планограммы → История изменений | Полный журнал версий планограмм магазина |
| Аналитика | Показатели дня, проходимость по зонам (бары), сводка по категориям |
| Товары | Реестр товаров с фильтром по категории и поиском, CRUD |
| Акции | Реестр акций с фактическим статусом и остатком дней, CRUD |
| Оборудование | Реестр стеллажей/витрин с заполненностью полок, CRUD |
| Задачи | Задачи мерчандайзинга с приоритетом и просрочкой, CRUD |
| Документы | Документы модуля со ссылками на файлы |
| Уведомления | Лента с отметкой прочтения |
| Настройки | Параметры модуля + журнал действий (`PLG_EVENT_LOG`) |

Карта магазина рисуется **из данных Oracle**, а не захардкожена: зоны и оборудование
позиционируются по `POS_X/POS_Y/WIDTH/HEIGHT` в координатной сетке `MAP_WIDTH × MAP_HEIGHT`
магазина. Цвет заливки зоны — из `PLG_ZONES.COLOR` (fallback — цвет типа зоны), затемнение
и полоса снизу — из актуальной `TRAFFIC_PCT`.

---

## 4. API

Все методы принимают `?lang=ru|ro|en`. Ответ: `{"success": bool, "data": …, "lang": "…"}`
или `{"success": false, "error": "…"}`.

### Язык и справочники
```
GET  /api/plg/langs
GET  /api/plg/i18n                     → {msg_key: text}
GET  /api/plg/refs                     → langs, zone_types, fixture_types, plg_statuses,
                                          task_types, promo_types, doc_types, categories
GET  /api/plg/stores
```

### Дашборд, карта, аналитика
```
GET  /api/plg/dashboard?store_id=&days=      → stats, metrics, categories, promos, notifications
GET  /api/plg/map?store_id=                  → store, zones, fixtures
GET  /api/plg/analytics?store_id=&days=      → zones, categories, metrics
```

### Зоны, оборудование, товары
```
GET|POST          /api/plg/zones
PUT|DELETE        /api/plg/zones/<id>
GET|POST          /api/plg/fixtures            (GET: ?store_id=&zone_id=)
PUT|DELETE        /api/plg/fixtures/<id>
GET|POST          /api/plg/products            (GET: ?category_id=&q=)
PUT|DELETE        /api/plg/products/<id>
```

### Планограммы
```
GET               /api/plg/planograms?store_id=&status=&zone_id=
GET               /api/plg/planograms/<id>            → заголовок + items + history
POST              /api/plg/planograms
PUT|DELETE        /api/plg/planograms/<id>
POST              /api/plg/planograms/<id>/status     {"status": "approved"}
POST              /api/plg/planograms/<id>/items
PUT               /api/plg/planograms/<id>/items/<item_id>
DELETE            /api/plg/items/<item_id>
GET               /api/plg/history?store_id=&planogram_id=&limit=
```

### Акции, задачи, документы, уведомления
```
GET|POST          /api/plg/promos                (GET: ?store_id=&active=1)
PUT|DELETE        /api/plg/promos/<id>
GET|POST          /api/plg/tasks                 (GET: ?store_id=&status=open|new|…)
PUT|DELETE        /api/plg/tasks/<id>
GET|POST          /api/plg/documents             (GET: ?store_id=&planogram_id=)
PUT|DELETE        /api/plg/documents/<id>
GET               /api/plg/notifications?store_id=&unread=1
POST              /api/plg/notifications/<id>/read
POST              /api/plg/notifications/read-all?store_id=
```

### Настройки и аудит
```
GET               /api/plg/settings
POST              /api/plg/settings         {"param_code": "...", "param_value": "..."}
GET               /api/plg/audit?limit=
```

Многоязычные поля в теле запроса принимаются как `name_ru` / `name_ro` / `name_en`
(для задач и документов — `title_*`). Если передано только `name`, оно записывается в русскую колонку.

---

## 5. Локальный запуск

```bash
cd /Users/pt/Projects.AI/Artgranit
venv/bin/python app.py
```

Открыть `http://localhost:3003/UNA.md/orasldev/planograms` (после `/login`).

---

## 6. Развёртывание Oracle-объектов

`deploy_to_remote.sh` переносит только код. Схему модуля нужно ставить отдельно.
В `deploy_oracle_objects.py` добавлен фильтр `--only`, чтобы не перезапускать демо-данные
других модулей:

```bash
venv/bin/python deploy_oracle_objects.py --only plg_ --dry-run
```

```bash
venv/bin/python deploy_oracle_objects.py --only plg_
```

Порядок файлов: `80_plg_tables.sql` → `81_plg_views.sql` → `82_plg_demo_data.sql` → `83_plg_i18n.sql`.
Файлы включены и в общий порядок `deploy_oracle_objects.py`.

Remote-деплой кода (контур nufarul):

```bash
cd /Users/pt/Projects.AI/Artgranit && ./deploy_to_remote.sh
```

Для установки схемы на remote — `DEPLOY_ORACLE_ON_REMOTE=1` либо запуск
`deploy_oracle_objects.py --only plg_` на сервере.

---

## 7. Checklist верификации после релиза

```bash
# 1. Объекты модуля существуют
venv/bin/python -c "
from models.database import DatabaseModel
with DatabaseModel() as db:
    r = db.execute_query(\"SELECT OBJECT_TYPE, COUNT(*) FROM USER_OBJECTS WHERE OBJECT_NAME LIKE 'PLG%' OR OBJECT_NAME LIKE 'V_PLG%' GROUP BY OBJECT_TYPE\")
    print(r['data'])"
```

```bash
# 2. Страница модуля отвечает 200 (локально)
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3003/UNA.md/orasldev/planograms
```

```bash
# 3. Production-инвариант после ЛЮБОГО деплоя
curl -I https://nufarul.eminescu.md/login
```

Ручная проверка в UI:

1. Переключатель `RU / RO / EN` меняет навигацию, подписи, названия зон, категорий, акций и задач.
2. Карта магазина рисует зоны и оборудование, тепловая карта соответствует колонке
   «Проходимость по зонам».
3. Смена статуса планограммы добавляет запись в «Историю изменений».
4. Все действия записи видны в журнале действий раздела «Настройки».

---

## 8. Демо-данные

`82_plg_demo_data.sql` создаёт три магазина; полностью размечен `MD-CHS-024` («Магазин 24»),
координаты зон и оборудования взяты из макета:

* 20 зон (13 отделов, алкоголь, склад, служебное, туалет, остров акций, касса, вход);
* 25 единиц оборудования (4 ряда центральных стеллажей, 5 пристенных витрин, остров);
* 24 товара в 14 категориях;
* 5 планограмм в разных статусах с позициями и историей версий;
* 5 акций (3 активные);
* 7 задач мерчандайзинга, 8 документов, 5 уведомлений;
* 30 дней показателей магазина и категорий, 14 дней проходимости зон.

Метрики генерируются с разбросом относительно площади магазина, поэтому графики динамики
выглядят правдоподобно для всех трёх магазинов, а карта — только для «Магазина 24».
Магазин по умолчанию выбирается тот, у которого размечены зоны.
