# SEOForge — модуль AI-SEO продвижения в бэкофисе

| Параметр | Значение |
|---|---|
| Дата | 2026-08-24 |
| Модуль | `seoforge`, префикс Oracle-объектов `YSEO_` |
| Маршрут | `/UNA.md/orasldev/seoforge` |
| Источник требований | `PavelTuhari/cursor25`, ветка `claude/seo-web-platform-spec-hxdbtj`, каталог `seo-platform/` |
| Объём | Кусок **A + B** (Oracle-контур + UI мастер-данных, бюджета и ROI) |

## 1. Что делаем и чего не делаем

Спека SEOForge описывает целую платформу: web-панель, генератор `.md`-плейбуков,
оркестратор, раннеры AI-сессий, десять MCP-коннекторов, векторную базу знаний,
коннекторы к соцсетям и рекламным кабинетам, плюс полный финансовый
документооборот на базе UNA.md. Это не один модуль, поэтому работа разбита:

| Кусок | Содержание | Статус |
|---|---|---|
| **A** | Oracle-контур `YSEO_*` / `VSEO_*` / `PK_SEO_*` | **этот документ** |
| **B** | Модуль-UI: сайты, кампании, бюджет план/факт, ROI по каналам | **этот документ** |
| C | Approval Inbox, документы и маршрут согласования поверх `TMDB_DOCS` | отложено |
| D | Генератор плейбуков и реестр запусков (Task Run) | отложено |
| E | Коннекторы (GSC, GA4, SERP, соцсети) и раннеры AI-сессий | отложено, отдельный проект |

Из тринадцати экранов ТЗ (§6) в v1 попадают семь. Семантика, Контент-план,
Playbooks, Сессии, Approval Inbox, Техаудит и Ссылки не реализуются — они
принадлежат кускам C, D и E.

## 2. Ключевые решения

### 2.1 Целевая база — облачная Oracle бэкофиса, не боевая ERP

В бэкофисе две базы: собственная облачная (wallet, thin-режим, `models/database.py`
— там живут `DECOR_`, `CRED_`, `DIGI_`) и боевая ERP OfficePlus/UNA
(`orange.una.md:4024/cloudbd.world`, Oracle 11g, thick-режим через subprocess-воркер
`models/biro26_db.py`).

Контур `YSEO_*` ставится в **облачную базу бэкофиса**. Причины:

1. Кусок A+B — это мастер-данные, план бюджета и метрики. Ему не нужны ни
   `TMDB_DOCS`, ни `UN$GFC`, ни разделы `TMS_SYSS` — они нужны только куску C.
2. `seo-platform/db/oracle/README.md` сам перечисляет непроверенные предположения
   о схеме UNA: состав `TMDB_DOCS_ADD` и `TMDB_DOCS_LOG`, выдача `TMDB_DOCS.COD`,
   кодировка `DOCCOLOR`, сигнатура `UN$GFC`, раскладка `TMS_SYSS ('S',3)`.
   Их обязаны сверить с командой UNA до установки в боевую схему.
3. Модель бэкофиса Oracle-first с префиксом модуля выполняется полностью.

Связь с документами ERP заранее предусмотрена таблицей `YSEO_XREF`
(`ENTITY_TYPE`, `ENTITY_COD` → `ERP_DOC_COD`, `ERP_NRMANUAL`): когда кусок C
получит подтверждённый интерфейс UNA, привязка делается без перестройки схемы.

### 2.2 Схема адаптирована, имена сохранены

В спеке таблицы `YSEO_*` — расширения таблиц UNA: `FK` на `TMS_UNIVERS`,
табличные части `*_D` с `FK` на `TMDB_DOCS`, справочники через разделы
`TMS_SYSS ('W', 1..7)`. В автономной базе этих родителей нет, поэтому:

- вместо разделов `TMS_SYSS` — собственный справочник `YSEO_DICT`
  (`SECTION`, `COD1`, `CODE`, `NAME_RU/RO/EN`);
- вместо табличных частей документов — самостоятельные сущности со своими
  последовательностями (`YSEO_CAMPAIGN` вместо `YSEO_TMDB_CAMP_D`,
  `YSEO_BUDGET_PLAN` вместо `YSEO_TMDB_BUDG_D`,
  `YSEO_SPEND_FACT` вместо `YSEO_TMDB_ADSPEND_D`);
- имена колонок и их смысл берутся из спеки без изменений, чтобы перенос
  в контур UNA был механическим.

### 2.3 Инварианты живут в Oracle, Flask тонкий

Расчёты план/факт, ROI и контроль лимита бюджета — во вьюшках `VSEO_*` и
пакетах `PK_SEO_*`. Контроллер маршрутизирует, валидирует ввод и разбирает CSV.
Это прямо следует требованию спеки: ошибка в приложении не должна приводить
к бесконтрольным деньгам. Альтернатива — вся логика в Python — отвергнута:
лимит бюджета тогда обходится мимо UI.

### 2.4 Факт вводится руками и грузится CSV

Коннекторов в v1 нет (кусок E). Расход рекламы и метрики сайтов вводятся
через форму либо грузятся CSV-выгрузками из рекламных кабинетов и Google Search
Console. Дедуп по `EXT_ID`: повторная заливка того же файла не создаёт дублей.
Когда появятся коннекторы, они пишут в те же таблицы тем же контрактом.

## 3. Модель данных

### 3.1 Таблицы

| Таблица | Назначение | Ключевое |
|---|---|---|
| `YSEO_DICT` | справочник разделов: `CHANNEL`, `ARTICLE`, `PROMO_TYPE`, `FORMAT`, `BUYUNIT`, `METRIC` | PK `(SECTION, COD1)`, UK `(SECTION, CODE)`, `NAME_RU/RO/EN`, `SORT_ORDER`, `ISARHIV` |
| `YSEO_SITE` | Site Profile | PK `COD`, UK `DOMAIN`; `LOCALES`, `GEO`, `NICHE`, `DIV`, `TONE_OF_VOICE`, `GUARDRAILS`, `KPI_TARGET`, `ISARHIV` |
| `YSEO_PLATFORM` | площадки размещения | PK `COD`, UK `PLATFORM_CODE`; `NAME`, `URL`, `CHANNEL_COD1`, `GEO`, `HAS_API`, `MANUAL_PUBLISH`, `QUALITY_SCORE`, `RATE_LIMIT_DAY`, `POSTING_RULES`, `ISARHIV` |
| `YSEO_CAMPAIGN` | кампания / акция | PK `COD`, UK `CAMP_CODE` (= `utm_campaign`); `SITE_COD`, `NAME_RU/RO/EN`, `PROMO_TYPE_COD1`, `DISCOUNT_VALUE`, `PROMO_CODE`, `SCOPE_KIND`, `DATE_START`, `DATE_END`, `LIMIT_QTY`, `LIMIT_SUM`, `BUDGET_PLAN`, `KPI_TARGET`, `LEGAL_TEXT_REF`, `STATUS`, `ISARHIV` |
| `YSEO_BUDGET_PLAN` | план бюджета | PK `COD`, UK `(PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD)`; `PLAN_SUMA`, `VALUTA`, `NOTE` |
| `YSEO_SPEND_FACT` | факт расхода рекламы | PK `COD`, UK `EXT_ID`; `SITE_COD`, `CAMP_COD`, `CHANNEL_COD1`, `PLATFORM_COD`, `ARTICLE_COD1`, `SPEND_DATE`, `PERIOD`, `SUMA`, `VALUTA`, `SUMA_MDL`, `CLICKS`, `IMPRESSIONS`, `CONVERSIONS`, `REVENUE`, `IS_OVERBUDGET`, `SOURCE`, `IMPORT_COD` |
| `YSEO_METRICS_FACT` | метрики сайта | PK `COD`, UK `EXT_ID`; `SITE_COD`, `METRIC_COD1`, `CHANNEL_COD1`, `FACT_DATE`, `PERIOD`, `VALUE`, `SOURCE`, `IMPORT_COD` |
| `YSEO_IMPORT` | партии CSV-импорта | PK `COD`; `KIND` (`SPEND`/`METRICS`), `FILE_NAME`, `USERNAME`, `LOADED_AT`, `ROWS_TOTAL`, `ROWS_LOADED`, `ROWS_SKIPPED`, `STATUS` |
| `YSEO_FX_RATE` | курс валюты на дату | PK `(VALUTA, RATE_DATE)`; `RATE` |
| `YSEO_SETUP` | настройки контура | PK `PARAM_CODE`; `PARAM_VALUE`, `DESCR`. Параметры: `BASE_CURRENCY` (по умолчанию `MDL`), `BUDGET_OVERRUN_MODE` (`BLOCK`/`WARN`) |
| `YSEO_XREF` | связь с документами ERP | PK `COD`, UK `(ENTITY_TYPE, ENTITY_COD)`; `ERP_DOC_COD`, `ERP_NRMANUAL`, `NOTE`, `CREATED_AT` |
| `YSEO_EVENT_LOG` | append-only журнал модуля | PK `COD`; `ACTION`, `ENTITY_TYPE`, `ENTITY_COD`, `DETAILS`, `USERNAME`, `CREATED_AT` |

Первичные ключи выдаются последовательностями `YSEO_*_SEQ` через триггеры
`BEFORE INSERT` — так сделано во всех соседних модулях (`CLS_*`, `DIGI_*`),
и это же оставляет схему переносимой в контур UNA на Oracle 11g.

Удалений нет. Справочные сущности (`YSEO_SITE`, `YSEO_PLATFORM`,
`YSEO_CAMPAIGN`, `YSEO_DICT`) архивируются флагом `ISARHIV = 1` с записью
в `YSEO_EVENT_LOG`.

### 3.2 Вьюшки

| Вьюшка | Содержание |
|---|---|
| `VSEO_SITE` | сайт + число активных кампаний + расход текущего периода + отклонение от плана |
| `VSEO_CAMPAIGN` | кампания + план, факт, остаток |
| `VSEO_BUDGET_PLANFACT` | период × статья × канал × сайт: `PLAN_SUMA`, `FACT_SUMA`, отклонение, процент выполнения |
| `VSEO_CHANNEL_ROI` | канал × период: расход, клики, показы, конверсии, выручка, ROI, CPC, CPA |

Все суммы во вьюшках приведены к базовой валюте через `PK_SEO_UTIL.TO_MDL`.

### 3.3 Пакеты

**`PK_SEO_UTIL`**
- `TO_MDL(p_suma, p_valuta, p_date)` — приведение к базовой валюте по `YSEO_FX_RATE`;
- `PERIOD_OF(p_date)` — дата → `YYYY-MM`;
- `GET_SETUP(p_code)` — значение параметра из `YSEO_SETUP`;
- `LOG_EVENT(p_action, p_entity_type, p_entity_cod, p_details, p_username)`.

**`PK_SEO_BUDGET`**
- `PLAN_UPSERT(...)` — вставка или обновление строки плана по естественному ключу;
- `CHECK_LIMIT(p_period, p_article, p_channel, p_site, p_add_suma)` — остаток плана;
- `RECALC_OVERBUDGET(p_period)` — пересчёт флагов после правки плана.

Инвариант перерасхода держит триггер на `YSEO_SPEND_FACT`:
при `BUDGET_OVERRUN_MODE = 'BLOCK'` вставка сверх плана отклоняется
исключением `ORA-20xxx`, при `'WARN'` — проходит с `IS_OVERBUDGET = 1`.

### 3.4 Язык кода

Комментарии в SQL и сообщения исключений — в формате `RO: <текст> / EN: <text>`
по правилу проекта. Идентификаторы — английские. Заголовки UI — ru/ro/en
через существующий каталог `translations/`.

## 4. Раскладка файлов

```
sql/113_yseo_tables.sql        таблицы, последовательности, триггеры-нумераторы, триггер перерасхода
sql/114_yseo_views.sql         VSEO_SITE, VSEO_CAMPAIGN, VSEO_BUDGET_PLANFACT, VSEO_CHANNEL_ROI
sql/115_yseo_package.sql       PK_SEO_UTIL, PK_SEO_BUDGET
sql/116_yseo_dict_seed.sql     наполнение YSEO_DICT и YSEO_SETUP
deploy_oracle_objects.py       + четыре файла в порядок выполнения
models/seo_oracle_store.py     хранилище: CRUD поверх нормализованных таблиц
controllers/seo_controller.py  маршрутизация, валидация, разбор CSV
templates/seoforge.html        SPA с панелями
modules/seoforge/module.json   манифест меню
docs/SEOForge/*.md + docs.json документация модуля
tests/test_seoforge.py         юнит-тесты с замоканным DatabaseModel
scripts/seoforge_smoke.py      живой smoke по инвариантам контура
```

Хранилище держит контракт соседних модулей:
`{success, data, columns, rowcount, message}`.

## 5. Экраны

SPA по образцу `templates/digi_marketing.html`: панели `.panel#panel-*`,
навигация подхватывается автоматически.

| Панель | Экран ТЗ | Содержание |
|---|---|---|
| `portfolio` | S1 | плитки сайтов из `VSEO_SITE`; клик ведёт в профиль |
| `sites` | S3 | CRUD Site Profile |
| `campaigns` | D2 | CRUD кампаний, колонки план/факт/остаток |
| `budget` | D1 | сетка план/факт, редактирование плана на месте, подсветка перерасхода |
| `facts` | — | две вкладки: расходы рекламы и метрики; ручной ввод, CSV-импорт, журнал партий |
| `roi` | S12-lite | `VSEO_CHANNEL_ROI` таблицей и графиком по периодам |
| `refs` | S13-lite | справочники, площадки, курсы валют, настройки, журнал событий |

## 6. Маршруты

Страница — `/UNA.md/orasldev/seoforge`, охрана `AuthController.is_authenticated()`
как в соседних модулях. JSON-API под `/UNA.md/orasldev/seoforge/api/`:

| Метод и путь | Назначение |
|---|---|
| `GET/POST/PUT sites`, `POST sites/<cod>/archive` | Site Profile |
| `GET/POST/PUT platforms`, `POST platforms/<cod>/archive` | площадки |
| `GET/POST/PUT dict/<section>` | справочники |
| `GET/POST fx` | курсы валют |
| `GET/POST/PUT campaigns`, `POST campaigns/<cod>/status` | кампании |
| `GET/POST budget/plan` | план бюджета (upsert по естественному ключу) |
| `GET budget/planfact?period=&site=` | сетка план/факт |
| `GET/POST spend`, `POST spend/import/preview`, `POST spend/import/commit` | расход рекламы |
| `GET/POST metrics`, `POST metrics/import/preview`, `POST metrics/import/commit` | метрики |
| `GET roi?period_from=&period_to=&site=` | ROI по каналам |
| `GET/PUT settings`, `GET events` | настройки и журнал |

### 6.1 Контракт CSV-импорта

Импорт в два шага, чтобы мусор не попадал в базу:

1. `POST …/import/preview` — разбирает файл, возвращает разобранные строки,
   найденные дубли по `EXT_ID` и ошибки валидации. **Ничего не пишет.**
2. `POST …/import/commit` — создаёт партию в `YSEO_IMPORT` и пишет строки.
   Дубли пропускаются молча, их число попадает в `ROWS_SKIPPED`.

Заголовки колонок фиксированы и описаны в `docs/SEOForge/`. `EXT_ID`
берётся из выгрузки, а при отсутствии собирается детерминированно из
источника, даты, кампании и канала — чтобы повторная заливка совпала сама с собой.

## 7. Ошибки

Бизнес-правила бросают `ORA-20xxx` с готовым сообщением `RO: … / EN: …` —
контроллер отдаёт его в UI как есть. Прочие ошибки (потеря соединения,
синтаксис, таймаут) пишутся в лог приложения, наружу уходит общее сообщение
без деталей базы. HTTP-коды: `400` — ошибка валидации ввода,
`409` — нарушение бизнес-инварианта (перерасход, дубль кода),
`500` — непредвиденная ошибка.

## 8. Тесты

**`tests/test_seoforge.py`** — юнит-тесты с замоканным `DatabaseModel`
по образцу `tests/test_biro26.py`, живая база не нужна:

- разбор CSV: корректные строки, битые числа, пустые обязательные поля;
- вывод периода из даты (`PERIOD_OF` на стороне Python для предпросмотра);
- генерация `EXT_ID` детерминирована и стабильна между запусками;
- предпросмотр помечает дубли и не пишет в базу;
- валидация сущностей: домен непустой, `DATE_END >= DATE_START`, суммы неотрицательны;
- маппинг исключений в HTTP-коды.

**`scripts/seoforge_smoke.py`** — живой smoke после установки DDL,
проверяет то, что нельзя проверить моком:

1. создать сайт, план на период, расход в пределах плана — проходит;
2. расход сверх плана при `BUDGET_OVERRUN_MODE = BLOCK` — отклонён;
3. тот же расход при `WARN` — записан с `IS_OVERBUDGET = 1`;
4. повторный импорт того же файла не создаёт дублей;
5. архивирование вместо удаления, запись в `YSEO_EVENT_LOG`;
6. `VSEO_BUDGET_PLANFACT` и `VSEO_CHANNEL_ROI` дают ожидаемые суммы.

## 9. Деплой

1. `sql/113…116` добавляются в порядок выполнения в `deploy_oracle_objects.py`.
2. `deploy_to_remote.sh` переносит код, но DDL не выполняет — установка контура
   делается отдельным запуском `python deploy_oracle_objects.py`
   либо remote deploy с `DEPLOY_ORACLE_ON_REMOTE=1`.
3. Выкатка на боевой сервер — только по отдельной команде. После любой
   операции на сервере обязательна проверка `curl -I https://nufarul.eminescu.md/login`.
4. Модуль попадает в меню сам через `models/module_registry.py`, от автора
   требуется только `modules/seoforge/module.json`.

## 10. Что остаётся открытым

- Кусок C (документы и согласование) заблокирован до сверки с командой UNA
  структур `TMDB_DOCS_ADD`, `TMDB_DOCS_LOG`, выдачи `TMDB_DOCS.COD`,
  кодировки `DOCCOLOR` и сигнатуры `UN$GFC` — список в
  `seo-platform/db/oracle/README.md`.
- Куски D и E проектируются отдельно после того, как A+B отработает
  на реальных данных пилотных сайтов (`una.md`, `unisim-soft`, `officeplus.md`).
