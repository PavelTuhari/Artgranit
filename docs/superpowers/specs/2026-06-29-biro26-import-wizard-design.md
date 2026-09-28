# Biro26 — AI-маппинг любого источника + wisepim-визард + просмотр изображений

**Дата:** 2026-06-29 · **Версия:** 1.0
**Расширяет:** `docs/superpowers/specs/2026-06-28-biro26-module-design.md` (модуль Biro26, фазы 1–5)
**Целевая СУБД:** officeplus `orange.una.md:4024/cloudbd.world` (Oracle 11g) через subprocess-воркер.

---

## 1. Решения (зафиксировано с заказчиком)
- **AI-провайдер:** переиспользуем существующий `ai_helper.ask_llm_via_selenium` (браузерный LLM). При недоступности (`is_ai_available()==False`) — детерминированный fallback по схожести имён/типов колонок.
- **«Любой SELECT»:** становится реальным источником импорта. Из SELECT создаётся **VIEW** `V_BIRO26_SRC_<name>`; пакет импортирует из неё (`g_tbl_goods` → view). Изменений пакета `YBIRO_Import_Marfa` не требуется (он уже конфигурируем через `g_tbl_goods`/`g_col_*`).
- **Порядок — поэтапно**, каждый этап — рабочий инкремент: (1) изображения, (2) wisepim-визард маппинга, (3) AI + любой SELECT.
- **MD-описание источника:** AI генерирует черновик (по сэмплу SELECT), пользователь правит в UI; хранится в `docs/Biro26/sources/<name>.md`.
- **Визард — новая вкладка** «Import (asistent)»; существующая «Mapare/Setări» остаётся для ручного/расширенного редактирования и подключения.

---

## 2. Архитектура (аддитивно к модулю)
```
models/biro26_ai.py        — AI-помощник: промпты, вызов ask_llm_via_selenium, разбор JSON,
                              эвристический fallback (соответствие имён/типов).
models/biro26_sources.py   — стор определений источников: валидация SELECT (read-only),
                              сэмплирование, создание/удаление VIEW, persist в YBIRO_SRC_DEF.
sql/biro26/02_biro26_sources.sql — таблица YBIRO_SRC_DEF (+ seq+trigger, 11g).
docs/Biro26/sources/<name>.md    — описания источников (AI-черновик + ручная правка).
static/biro26/backoffice-tabs.js — + логика визарда, лайтбокса, AI-шагов.
templates/biro26/backoffice.html — + вкладка «Import (asistent)», лайтбокс-модал, превью-картинки.
```
Слои сохраняются: всё обращение к officeplus — через `Biro26DB` (subprocess, thick). Весь SQL — в сторах. Контроллер тонкий. Основной Flask остаётся thin (production-инвариант не нарушается).

---

## 3. Этап 1 — Просмотр изображений
**Данные:** `BIRO26_GOODS.PHOTO_URL`, `BIRO26_GOODS.IMAGE_LINK` — внешние https-URL (напр. `papirus.md`).
**Store:** `get_goods` добавляет `PHOTO_URL`, `IMAGE_LINK` в выборку. Карточка справочника (`get_univers_card`) дополнительно подтягивает изображение из `BIRO26_GOODS` по `COD_UNIVERS = COD` (LEFT JOIN/доп. запрос).
**UI:**
- В гриде «Sursă» — колонка-превью: `<img loading="lazy">` (≈40px), пустой URL → плейсхолдер.
- Клик по превью → **лайтбокс** (переиспользуем модал-паттерн): крупное изображение + URL + кнопка «открыть в новой вкладке».
- В карточке товара — превью изображения (если есть).
**Риски:** внешние URL могут не грузиться (битые/пустые) — `onerror` скрывает img/показывает плейсхолдер. Mixed-content нет (https). Чисто аддитивно.

---

## 4. Этап 2 — Визард импорта (стиль wisepim)
Новая вкладка **«Import (asistent)»** — 4 шага поверх текущего источника.

### Шаг 1 — Sursă
Выбор источника (сейчас `BIRO26_GOODS`; сохранённые определения — этап 3) и активного профиля маппинга. Показ числа строк, сэмпла.

### Шаг 2 — Mapare (ключевой экран)
Таблица соответствий в стиле column-importer:
- строки = **целевые поля**: `COD`(ключ, seq), `CODVECHI ← articol`, `DENUMIREA ← denumire`, `PRETV ← retail1`, `PRETV1 ← angro`, `PRETV2 ← ionline`, группа ← brand, и константы (`UM`,`GR1`,`TIP`,`CACCESS`,`CODTVA`,…);
- для каждого целевого поля — **выпадающий список колонок источника** (автоподбор подсвечен) ИЛИ ввод константы;
- колонка **«пример данных»** — живой сэмпл из источника по выбранной колонке;
- индикаторы правил: обрезка (`len_codvechi`/`len_denumire`), парсинг цены, NOT NULL.
Соответствует переменным пакета `g_col_*`/`g_*`; сохраняется в существующий профиль `YBIRO_MAP_*` (через store этапа 1 модуля).

### Шаг 3 — Verificare
Запуск `validate_input` (read-only), вывод отчёта RO/EN с подсветкой проблем (пустые имена, длинные `ARTICOL/DENUMIRE`, нет ключа, непарсируемые цены) + счётчики.

### Шаг 4 — Import
Запуск цепочки (`prepare_input`→`assign_keys`→`import_univers`→…→`import_prices`) или отдельных шагов; прогресс/итог из DBMS_OUTPUT; сводка. Деструктив — с подтверждением.

UI: горизонтальный степпер (1·2·3·4), кнопки «Înapoi/Înainte», состояние шага в JS. Существующая вкладка «Mapare/Setări» сохраняется.

---

## 5. Этап 3 — AI + любой SELECT
В Шаг 1 визарда добавляется **«Sursă nouă (SELECT)»**.

### 5.1 Поток
1. Пользователь вводит **SELECT**. **Read-only guard** (`models/biro26_sources.py`): один оператор, начинается с `SELECT`/`WITH`, без `;` в конце-разделителе, запрет ключевых слов `INSERT/UPDATE/DELETE/MERGE/DROP/ALTER/CREATE/TRUNCATE/GRANT/BEGIN/CALL/EXECUTE`. Сэмпл = `SELECT * FROM (<sql>) WHERE ROWNUM <= :n`.
2. Сэмплирование → колонки (имена/типы из `cursor.description`) + N строк примера.
3. **AI-черновик описания**: `biro26_ai.draft_source_md(columns, samples)` → Markdown (колонка, тип, предполагаемый смысл, пример). Сохраняется в `docs/Biro26/sources/<name>.md`, редактируется в UI.
4. **Создание VIEW**: `CREATE VIEW V_BIRO26_SRC_<name> AS <sql>` (имя из `[A-Za-z0-9_]`, префикс `V_BIRO26_SRC_`). Persist в `YBIRO_SRC_DEF(name, select_sql, view_name, md_path, created_*)`.
5. **AI-маппинг колонок**: `biro26_ai.suggest_mapping(view_columns, samples, md, target_schema)` → JSON `{ g_col_key, g_col_articol, g_col_denumire, g_col_retail, g_col_angro, g_col_ionline, g_col_brand, … }` + константы. Предзаполняет Шаг 2 для проверки/правки. Fallback — эвристика по именам (`denumire~denumirea`, `articol~codvechi`, `pret/retail~retail`, …).
6. Сохранение профиля с `g_tbl_goods = V_BIRO26_SRC_<name>` → импорт идёт обычной цепочкой из любого источника.

### 5.2 biro26_ai (контракт)
- `is_available() -> bool` (обёртка `ai_helper.is_ai_available`).
- `draft_source_md(columns, samples) -> str` (Markdown; при отсутствии AI — таблица колонок без «смысла»).
- `suggest_mapping(columns, samples, md, target) -> {success, mapping:{param:source_or_const}, source:'ai'|'heuristic'}`.
- Внутри: строит текстовый промпт, зовёт `ask_llm_via_selenium(prompt, timeout)`, извлекает первый JSON-блок, валидирует ключи по `G_PARAMS`. Любая ошибка/таймаут → эвристика.

### 5.3 YBIRO_SRC_DEF (DDL, 11g)
```
id NUMBER PK (seq+trigger), name VARCHAR2(60) UNIQUE, select_sql CLOB,
view_name VARCHAR2(40), md_path VARCHAR2(200), created_at TIMESTAMP, created_by VARCHAR2(60)
```
Деплой отдельным `deploy`-скриптом против officeplus (как `YBIRO_MAP_*`).

### 5.4 Безопасность
- Только bind-переменные в прикладном SQL; SELECT-guard для пользовательского запроса; имя источника/вью — whitelistized `[A-Za-z0-9_]`.
- AI получает только имена колонок + небольшой сэмпл; не отправляются пароли/секреты.
- Создание VIEW требует привилегии `CREATE VIEW` у officeplus — проверяется первым шагом плана (пользователь уже создавал таблицы `YBIRO_*`).

---

## 6. Тестирование
- **Unit (mocked):** SELECT-guard (валид/невалид), эвристический маппер, парсер AI-JSON (валид/мусор→fallback), билдер DDL вью и имён, source-store CRUD, расширение `get_goods` полями изображений.
- **Live smoke:** create/sample/drop вью; `YBIRO_SRC_DEF` доступна; `get_goods` отдаёт PHOTO_URL.
- **Браузер:** лайтбокс открывается; визард проходит 4 шага; автоподбор колонок виден.
- AI-шаги time-boxed; при отсутствии AI всё работает на эвристике.

---

## 7. Вне объёма
- Загрузка CSV/XLSX как источника (источник — SQL/официальный фид; CSV-импорт — отдельная история).
- Кэш/хранение изображений локально (показываем по внешнему URL).
- Тонкая настройка AI-провайдера/ключей (используем существующий ai_helper как есть).
