# ScaleKiosk — Полная спецификация универсального модуля весов

> Детальная техническая документация: архитектура, API, DOM, CSS, события, жизненный цикл
> v1.0, 28.03.2026

---

## Содержание

1. [Назначение и архитектура](#1-назначение-и-архитектура)
2. [Файловая структура](#2-файловая-структура)
3. [Конструктор и конфигурация](#3-конструктор-и-конфигурация)
4. [Публичный API](#4-публичный-api)
5. [Внутреннее состояние](#5-внутреннее-состояние)
6. [DOM-структура модала](#6-dom-структура-модала)
7. [CSS-архитектура](#7-css-архитектура)
8. [Система событий и делегирование](#8-система-событий-и-делегирование)
9. [Левая колонка: Продукция + Паспорт](#9-левая-колонка-продукция--паспорт)
10. [Центральная колонка: Весы + Numpad](#10-центральная-колонка-весы--numpad)
11. [Правая колонка: AI Camera + Эмулятор](#11-правая-колонка-ai-camera--эмулятор)
12. [Polling и связь с весами](#12-polling-и-связь-с-весами)
13. [Авто-эмуляция](#13-авто-эмуляция)
14. [Паспорт продукции (детально)](#14-паспорт-продукции-детально)
15. [Процесс захвата (Capture)](#15-процесс-захвата-capture)
16. [Конфигурация драйвера](#16-конфигурация-драйвера)
17. [Интеграция с шаблонами](#17-интеграция-с-шаблонами)
18. [Scale API: полный справочник](#18-scale-api-полный-справочник)
19. [Product SVG иконки](#19-product-svg-иконки)
20. [Responsive и адаптивность](#20-responsive-и-адаптивность)
21. [Анимации](#21-анимации)
22. [Работа с data-атрибутами](#22-работа-с-data-атрибутами)
23. [Совместимость с legacy-кодом](#23-совместимость-с-legacy-кодом)
24. [Диаграмма жизненного цикла](#24-диаграмма-жизненного-цикла)
25. [Checklist после изменений](#25-checklist-после-изменений)

---

## 1. Назначение и архитектура

### 1.1 Что такое ScaleKiosk

**ScaleKiosk** — это полноэкранный модальный интерфейс, который превращает обычный монитор или планшет в терминал промышленных весов. Компонент спроектирован для работы в условиях склада или полевого пункта приёмки, где оператор взаимодействует с интерфейсом не мышью, а пальцами: крупные кнопки, минимум текстовых полей, высокая контрастность и однозначная визуальная индикация состояния.

Когда оператор нажимает кнопку **⚖ Весы** в строке документа (закупки или продажи), ScaleKiosk перекрывает весь экран и берёт на себя три задачи:

1. **Снятие веса** — связь с физическими весами через REST API, отображение gross/tare/net в реальном времени, ручной ввод через экранную numpad-клавиатуру.
2. **Идентификация продукции** — выбор продукта через тач-грид с SVG-иконками, распознавание через AI-камеру (эмуляция), заполнение паспорта качества (калибр, Brix, температура, дефекты и т.д.).
3. **Передача данных в документ** — по нажатию «Capture» весь собранный пакет (вес, продукт, паспорт) отправляется обратно в строку документа, модал закрывается.

### 1.2 Бизнес-контекст: зачем нужен отдельный модальный интерфейс

В модуле AGRO существуют два фундаментальных процесса, связанных с взвешиванием:

|  | Приёмка (Field) | Отгрузка (Sales) |
|--|-----------------|------------------|
| **What** | Фермер привозит фрукты, оператор взвешивает каждую партию, фиксирует качество | Менеджер формирует отгрузку клиенту, взвешивает паллеты перед экспедицией |
| **Where** | Полевой пункт / рампа склада, часто на солнце, пыль, влажные руки | Зона отгрузки склада, рядом с погрузчиком |
| **Device** | Планшет 10" на штативе рядом с весами | Монитор 15-22" на стойке |
| **Operator** | Оператор без IT-навыков, работает в перчатках | Складской менеджер, работает быстро |
| **Key data** | Gross, tare, net + продукт + паспорт качества (12 полей) | Gross, tare, net + продукт |

Несмотря на различия в контексте, **ядро операции идентично**: подключиться к весам → дождаться стабильного показания → зафиксировать вес → вернуть результат в документ. Именно это позволило создать один универсальный компонент вместо двух отдельных.

### 1.3 Два режима работы

Единственный класс `ScaleKiosk` создаётся с конфигурацией, которая определяет режим. Каждый шаблон создаёт свой экземпляр:

| Параметр | `purchase` (приёмка) | `sale` (отгрузка) |
|----------|---------------------|-------------------|
| **Модуль** | AGRO Field | AGRO Sales |
| **Шаблон** | `agro_field.html` | `agro_sales.html` |
| **Переменная** | `var fieldKiosk` | `var salesKiosk` |
| **Паспорт качества** | Да — 12 полей (сорт, калибр, Brix, температура, свежесть, дефекты, упаковка, маркировка, заметки) | Да — те же 12 полей |
| **Панель эмулятора** | Скрыта — в поле используются реальные весы | Видна — позволяет тестировать без физических весов |
| **Продукты в гриде** | 8 позиций (основные фрукты полевой приёмки) | 10 позиций (полный каталог включая перец, грецкий орех) |
| **Диапазон авто-эмуляции** | 50–500 кг (крупные партии с поля) | 5–200 кг (паллетная отгрузка) |
| **Callback при захвате** | Записывает gross/tare в строку закупки, устанавливает продукт в `<select>`, сохраняет паспорт в `data-passport`, вызывает `recalcPurchaseLine(lineId)` | Записывает gross/tare в строку продажи, вызывает `recalcSalesLine(lineId)` |

Визуально оба режима выглядят практически идентично — три колонки (продукция | весы | камера), одинаковый дизайн. Оператору не нужно переучиваться при переходе между рабочими местами.

### 1.4 Архитектурный паттерн: IIFE + Prototype

ScaleKiosk реализован как JavaScript-класс в стиле ES5 (без `class` ES6), обёрнутый в IIFE. Этот выбор продиктован совместимостью со всеми целевыми устройствами — включая старые Android-планшеты в полевых условиях.

**Паттерн на уровне кода:**

```js
(function() {
    'use strict';

    // Приватные константы (эмодзи-маппинг, продукты)
    var EMOJI_MAP = { APPLE:'🍎', PEAR:'🍐', PEACH:'🍑', ... };

    // Конструктор — единственная экспортируемая сущность
    function ScaleKiosk(config) {
        this.mode = config.mode || 'purchase';
        this.title = config.title || '⚖️ Весы / Cântar';
        // ... ещё 9 параметров конфигурации
        // ... 13 внутренних свойств (_pollTimer, _paused, ...)
        // ... построение карт продуктов
        this._renderModal();   // генерация DOM
        this._bindEvents();    // подключение событий
    }

    // 34 метода на прототипе
    ScaleKiosk.prototype.open = function(lineId) { ... };
    ScaleKiosk.prototype.close = function() { ... };
    ScaleKiosk.prototype.destroy = function() { ... };
    ScaleKiosk.prototype.$ = function(suffix) {
        return this._container.querySelector('[data-sk="' + suffix + '"]');
    };
    // ... _pollScale, _capture, _numpadPress, _selectProduct, ...

    // Глобальный экспорт
    window.ScaleKiosk = ScaleKiosk;
})();
```

**Почему именно так:**

| Решение | Обоснование |
|---------|-------------|
| **IIFE** | Инкапсуляция: `EMOJI_MAP` и другие константы недоступны извне. Нет загрязнения глобального пространства имён — экспортируется только `window.ScaleKiosk` |
| **Prototype** | Все 34 метода на прототипе — экономия памяти при создании нескольких экземпляров. Метод создаётся один раз, а не копируется в каждый объект |
| **ES5 синтаксис** | Не требуется Babel/webpack. Работает на Android 5+ WebView, Internet Explorer 11 (если вдруг), любом планшете старше 2015 года |
| **`this.$(suffix)` helper** | Выбор элементов по `data-sk` атрибуту внутри контейнера. Избегает конфликтов ID при наличии нескольких экземпляров на странице |
| **Dynamic DOM** | Метод `_renderModal()` генерирует всё HTML-дерево модала. Шаблону не нужно содержать modal-разметку — только `<script src>` и конфигурацию |

### 1.5 Трёхколоночная структура интерфейса

Полноэкранный модал разделён на три функциональных зоны, каждая из которых решает свою задачу в операции взвешивания:

```
┌─────────────────────────────────────────────────────────────────┐
│ ⚖️ Весы — Приёмка          ● Stable    Driver: Emu    [⏸] [✕]  │  ← sk-header
├──────────────────┬───────────────────┬──────────────────────────┤
│                  │                   │                          │
│  ЛЕВАЯ КОЛОНКА   │ ЦЕНТРАЛЬНАЯ       │  ПРАВАЯ КОЛОНКА          │
│  ═══════════     │ ═══════════       │  ═══════════             │
│                  │                   │                          │
│  Грид продуктов  │  Дисплей веса     │  AI Camera viewport      │
│  ┌──┬──┬──┐      │  ┌─────────────┐  │  ┌──────────────────┐    │
│  │🍎│🍐│🍑│      │  │  125.500 kg │  │  │ ╱╲  scanning...  │    │
│  ├──┼──┼──┤      │  │ █████████░░ │  │  │╱  ╲             │    │
│  │🍒│🍇│🟠│      │  └─────────────┘  │  └──────────────────┘    │
│  ├──┼──┼──┤      │  Tare: 2.000 kg   │                          │
│  │🌰│🍅│  │      │  Net: 123.500 kg  │  AI результат:           │
│  └──┴──┴──┘      │                   │  «Персик 95.2%»          │
│                  │  [Zero]   [Tare]  │                          │
│  ──────────────  │                   │  ──────────────────       │
│                  │  ┌───────────┐    │                          │
│  ПАСПОРТ         │  │  Numpad   │    │  Эмулятор (sale mode):   │
│  Сорт: Redhaven  │  │ [7][8][9] │    │  ┌──────────────────┐    │
│  Калибр: 65 мм   │  │ [4][5][6] │    │  │ [Поставить]      │    │
│  Brix: 11.5°     │  │ [1][2][3] │    │  │ [Случайный]      │    │
│  t°C: 4          │  │ [0][.][⌫] │    │  │ [Снять]          │    │
│  Свежесть: ★★★★  │  │ [Aplica]  │    │  └──────────────────┘    │
│  Дефекты: Нет    │  └───────────┘    │                          │
│  Упаковка: OK    │                   │                          │
│  Маркировка: OK  │  ┌─────────────┐  │                          │
│                  │  │ ⚖ СНЯТЬ ВЕС │  │                          │
│                  │  └─────────────┘  │                          │
└──────────────────┴───────────────────┴──────────────────────────┘
```

| Колонка | CSS-класс | Ширина | Функция |
|---------|-----------|--------|---------|
| **Левая** | `.sk-products` | `260px` фикс. | Выбор продукта (тач-грид), паспорт качества (12 полей). Оператор работает здесь первым — определяет, что именно на весах |
| **Центральная** | `.sk-scale` | `flex:1` | Дисплей веса (gross/tare/net), управление весами (Zero/Tare), numpad для ручного ввода, кнопка захвата. Ядро операции |
| **Правая** | `.sk-camera` | `280px` фикс. | AI Camera (анимация сканирования, результат распознавания), панель эмулятора (только `sale` mode) |

CSS-сетка: `.sk-body { display: flex; gap: 32px; }`. На экранах уже *900px* раскладка переключается в одну колонку (`flex-direction: column`).

### 1.6 Жизненный цикл операции (обзор)

Полный цикл от нажатия кнопки ⚖ до возврата веса в документ:

```
    Оператор нажимает ⚖ в строке документа
                     │
                     ▼
            ┌─────────────────┐
            │   kiosk.open()  │
            │   lineId → _targetLineId
            │   modal: display:flex
            │   _startPolling() → GET /read каждую 1с
            │   _startAutoEmulation() → цикл 20с
            └────────┬────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   Оператор вручную       Авто-эмуляция (20с)
   выбирает продукт       ─ POST /simulate (случайный вес)
   заполняет паспорт      ─ анимация камеры 3с
   вводит вес numpad      ─ случайный продукт из грида
          │                ─ confidence bar → pictogram
          │                     │
          └──────────┬──────────┘
                     │
                     ▼
            Индикатор: ● Stable (зелёный)
            Кнопка «СНЯТЬ ВЕС» → enabled
                     │
                     ▼
            ┌─────────────────┐
            │  _capture()     │
            │  POST /capture  │
            │  onCapture({    │
            │    lineId,      │
            │    gross, tare, │
            │    net,         │
            │    productKey,  │
            │    passport     │
            │  })             │
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │  kiosk.close()  │
            │  _stopPolling() │
            │  _stopAutoEmulation()
            │  modal: display:none
            │  toast: «Вес снят»
            └─────────────────┘
                     │
                     ▼
       Данные в строке документа обновлены.
       Модал закрыт. Оператор продолжает работу.
```

Среднее время одной операции: **10–30 секунд** (выбор продукта → ожидание стабильного показания → захват). Быстрые операторы выполняют захват за 5–7 секунд при заранее стабилизированных весах.

### 1.7 Архитектурная диаграмма класса

```
┌──────────────────────────────────────────┐
│            ScaleKiosk (class)            │
│    /static/agro/scale-kiosk.js (902 LOC) │
│    /static/agro/scale-kiosk.css (326 LOC)│
├──────────────────────────────────────────┤
│  Конфигурация (11 параметров):           │
│    mode          'purchase' | 'sale'     │
│    title         текст заголовка         │
│    products      [{key, name, svgPath}]  │
│    weightRange   {min, max}              │
│    showPassport  boolean                 │
│    showEmulator  boolean                 │
│    onCapture     function(data)          │
│    toastFn       function(msg)           │
│    scaleId       string                  │
│    emulationInterval  ms                 │
│    loadDriverConfig   boolean            │
├──────────────────────────────────────────┤
│  Публичный API (3 метода):               │
│    .open(lineId)     → показать модал    │
│    .close()          → скрыть модал      │
│    .destroy()        → удалить из DOM    │
├──────────────────────────────────────────┤
│  Внутреннее (31 метод на прототипе):     │
│    DOM:  _renderModal, _bindEvents, $    │
│    Poll: _startPolling, _pollScale, ...  │
│    Emu:  _startAutoEmulation, ...        │
│    Num:  _numpadPress, _numpadApply      │
│    Prod: _selectProduct, _buildGrid      │
│    Pass: _showPassport, _collectPassport │
│    Capt: _capture                        │
└──────────────┬───────────────────────────┘
               │
      ┌────────┴─────────┐
      ▼                  ▼
┌───────────────┐  ┌───────────────┐
│  Purchase     │  │  Sale         │
│  Instance     │  │  Instance     │
│               │  │               │
│  passport: ✓  │  │  passport: ✓  │
│  emulator: ✗  │  │  emulator: ✓  │
│  8 products   │  │  10 products  │
│  50–500 kg    │  │  5–200 kg     │
│  fieldKiosk   │  │  salesKiosk   │
└───────────────┘  └───────────────┘
```

### 1.8 Рефакторинг: до и после (28.03.2026)

**Проблема.** До рефакторинга код весового модала дублировался в двух HTML-шаблонах. Каждый шаблон содержал свою копию CSS, HTML-разметки и JavaScript-логики. Любое изменение (баг-фикс, новая кнопка, исправление анимации) приходилось вносить в оба файла, что приводило к расхождениям и ошибкам.

**Решение.** Весь код весов вынесен в два общих файла (`scale-kiosk.js` + `scale-kiosk.css`). HTML-разметка модала генерируется динамически методом `_renderModal()`. В каждом шаблоне осталось лишь ~30 строк: подключение файлов + конфигурация экземпляра + callback.

**Метрики:**

| Метрика | До рефакторинга | После | Δ |
|---------|-----------------|-------|---|
| JS в `agro_field.html` | ~550 строк | ~30 строк (конфиг) | **−520** |
| CSS в `agro_field.html` | ~300 строк | 0 (shared file) | **−300** |
| HTML модала в `agro_field.html` | ~200 строк | 0 (dynamic DOM) | **−200** |
| JS в `agro_sales.html` | ~340 строк | ~30 строк (конфиг) | **−310** |
| CSS в `agro_sales.html` | ~190 строк | 0 (shared file) | **−190** |
| HTML модала в `agro_sales.html` | ~100 строк | 0 (dynamic DOM) | **−100** |
| Общий файл JS | — | **902 строки** | +902 |
| Общий файл CSS | — | **326 строк** | +326 |

**Итого:** ~1680 строк дублированного кода → 1228 строк общего кода + 60 строк конфигурации. Экономия: ~25% кода, и главное — **единая точка правды** для обоих модулей.

### 1.9 Взаимодействие с внешним миром

ScaleKiosk не существует изолированно. Он встроен в экосистему модуля AGRO и зависит от нескольких внешних компонентов:

```
                    ┌──────────────────┐
                    │  Scale Hardware   │
                    │  (RS-232 / USB)   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Scale Driver    │
                    │  (Python backend)│
                    │  5 REST endpoints│
                    └────────┬─────────┘
                             │ HTTP
┌──────────────┐    ┌────────▼─────────┐    ┌──────────────────┐
│  Document    │◀───│   ScaleKiosk     │───▸│  Product SVGs    │
│  (purchase   │    │   (JS, browser)  │    │  /static/agro/   │
│   or sale    │    │                  │    │  products/*.svg  │
│   line)      │    │  ┌────────────┐  │    └──────────────────┘
│              │    │  │ AI Camera  │  │
│  Callback:   │    │  │ (эмуляция) │  │    ┌──────────────────┐
│  onCapture() │    │  └────────────┘  │───▸│  Admin Config    │
└──────────────┘    └──────────────────┘    │  /api/agro-admin/│
                                            │  module_config   │
                                            └──────────────────┘
```

| Внешний компонент | Тип связи | Endpoint / механизм |
|-------------------|-----------|---------------------|
| **Scale Driver** | REST polling (1с) | `GET /api/agro-scale/read?scale_id=default` |
| **Scale Commands** | REST POST | `/capture`, `/zero`, `/tare`, `/simulate` |
| **Admin Config** | REST GET (при открытии) | `GET /api/agro-admin/module_config` |
| **Product SVGs** | Загрузка `<img>` | `/static/agro/products/{product}.svg` |
| **Document Line** | JS callback | `config.onCapture({ lineId, gross, tare, net, productKey, passport })` |
| **Toast notifications** | JS callback | `config.toastFn('Вес снят: 125.5 кг — Персик')` |

---

## 2. Файловая структура

```
/static/agro/
├── scale-kiosk.css          326 строк  — все CSS-классы .sk-*
├── scale-kiosk.js           902 строки — класс ScaleKiosk (IIFE)
└── products/                SVG-иконки продуктов
    ├── apple.svg
    ├── apricot.svg           (создан 28.03.2026)
    ├── cherry.svg
    ├── grape.svg
    ├── peach.svg
    ├── pear.svg
    ├── pepper.svg
    ├── plum.svg
    ├── tomato.svg
    └── walnut.svg

/templates/
├── agro_field.html          Приёмка — fieldKiosk = new ScaleKiosk({mode:'purchase',...})
└── agro_sales.html          Продажа — salesKiosk = new ScaleKiosk({mode:'sale',...})
```

### 2.1 Порядок подключения в HTML

**КРИТИЧЕСКИ ВАЖНО:** CSS и JS должны подключаться ДО inline-скрипта, создающего экземпляр.

```html
<!-- В <head> -->
<link rel="stylesheet" href="/static/agro/scale-kiosk.css">

<!-- В <body>, ПЕРЕД inline <script> -->
<script src="/static/agro/scale-kiosk.js"></script>
<script>
  // Здесь можно создавать new ScaleKiosk({...})
</script>
```

Ошибка при нарушении порядка: `ReferenceError: ScaleKiosk is not defined`.

---

## 3. Конструктор и конфигурация

### 3.1 Сигнатура

```javascript
var kiosk = new ScaleKiosk(config);
```

### 3.2 Все параметры конфигурации

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `mode` | `string` | `'purchase'` | Идентификатор режима: `'purchase'` или `'sale'`. Влияет на ID контейнера (`sk_purchase_overlay` / `sk_sale_overlay`) |
| `title` | `string` | `'⚖️ Весы / Cântar'` | Текст заголовка модала |
| `products` | `Array<{key,name,svgPath}>` | `[]` | Массив продуктов для грида. `key` — код продукта (APPLE, GRAPE, ...), `name` — отображаемое имя, `svgPath` — путь к SVG-иконке |
| `weightRange` | `{min,max}` | `{min:50, max:500}` | Диапазон случайного веса для авто-эмуляции (кг) |
| `showPassport` | `boolean` | `false` | Показывать панель паспорта продукции (12 полей качества) |
| `showEmulator` | `boolean` | `false` | Показывать панель эмулятора весов (Set/Random/Remove) |
| `onCapture` | `function(data)` | `noop` | Callback при захвате веса. Получает объект `data` (см. §15) |
| `toastFn` | `function(msg, type)` | `noop` | Функция уведомлений. `type`: `'success'`, `'error'`, `'warning'` |
| `scaleId` | `string` | `'default'` | Идентификатор весов для API (поддержка нескольких весов) |
| `emulationInterval` | `number` | `20000` | Интервал авто-эмуляции в миллисекундах |
| `loadDriverConfig` | `boolean` | `true` | Загружать ли конфигурацию драйвера при `.open()` |

### 3.3 Пример: Purchase (приёмка)

```javascript
var fieldKiosk = new ScaleKiosk({
    mode: 'purchase',
    title: '⚖️ Весы — Закупка / Cântar — Achiziție',
    products: [
        {key: 'APPLE',  name: 'Яблоко / Măr',         svgPath: '/static/agro/products/apple.svg'},
        {key: 'GRAPE',  name: 'Виноград / Struguri',   svgPath: '/static/agro/products/grape.svg'},
        {key: 'CHERRY', name: 'Черешня / Cireșe',      svgPath: '/static/agro/products/cherry.svg'},
        {key: 'WALNUT', name: 'Грецкий орех / Nucă',   svgPath: '/static/agro/products/walnut.svg'},
        {key: 'PEPPER', name: 'Перец / Ardei',         svgPath: '/static/agro/products/pepper.svg'},
        {key: 'PEACH',  name: 'Персик / Piersică',     svgPath: '/static/agro/products/peach.svg'},
        {key: 'TOMATO', name: 'Помидор / Roșie',       svgPath: '/static/agro/products/tomato.svg'},
        {key: 'PLUM',   name: 'Слива / Prună',         svgPath: '/static/agro/products/plum.svg'}
    ],
    weightRange: {min: 50, max: 500},
    showPassport: true,
    showEmulator: false,
    toastFn: function(msg, type) { if (typeof showToast === 'function') showToast(msg, type); },
    onCapture: function(data) {
        var line = data.lineId ? document.getElementById(data.lineId) : null;
        if (!line) return;
        line.querySelector('.line-gross').value = data.gross.toFixed(2);
        line.querySelector('.line-tare').value = data.tare.toFixed(2);
        // Match product in select
        var selectedItem = line.querySelector('.line-item');
        if (selectedItem && !selectedItem.value && data.productKey) {
            for (var i = 0; i < selectedItem.options.length; i++) {
                if (selectedItem.options[i].value === data.productKey ||
                    selectedItem.options[i].textContent.trim() === data.productKey) {
                    selectedItem.value = selectedItem.options[i].value;
                    break;
                }
            }
        }
        if (typeof recalcPurchaseLine === 'function') recalcPurchaseLine(data.lineId);
        // Store passport JSON
        if (data.passport) {
            line.setAttribute('data-passport', JSON.stringify(data.passport));
        }
    }
});
// Legacy compat
window.weighPurchaseLine = function(lineId) { fieldKiosk.open(lineId); };
window.closeScaleModal = function() { fieldKiosk.close(); };
```

### 3.4 Пример: Sale (отгрузка)

```javascript
var salesKiosk = new ScaleKiosk({
    mode: 'sale',
    title: '⚖️ Весы — Отгрузка / Cântar — Expediere',
    products: [
        {key: 'APPLE',   name: 'Яблоко / Măr',         svgPath: '/static/agro/products/apple.svg'},
        {key: 'PEAR',    name: 'Груша / Pară',          svgPath: '/static/agro/products/pear.svg'},
        {key: 'PEACH',   name: 'Персик / Piersică',     svgPath: '/static/agro/products/peach.svg'},
        {key: 'PLUM',    name: 'Слива / Prună',         svgPath: '/static/agro/products/plum.svg'},
        {key: 'CHERRY',  name: 'Вишня / Cireșe',        svgPath: '/static/agro/products/cherry.svg'},
        {key: 'GRAPE',   name: 'Виноград / Struguri',   svgPath: '/static/agro/products/grape.svg'},
        {key: 'APRICOT', name: 'Абрикос / Caisă',       svgPath: '/static/agro/products/apricot.svg'},
        {key: 'WALNUT',  name: 'Орех / Nucă',           svgPath: '/static/agro/products/walnut.svg'},
        {key: 'TOMATO',  name: 'Томат / Roșie',         svgPath: '/static/agro/products/tomato.svg'},
        {key: 'PEPPER',  name: 'Перец / Ardei',         svgPath: '/static/agro/products/pepper.svg'}
    ],
    weightRange: {min: 5, max: 200},
    showPassport: true,
    showEmulator: true,
    toastFn: function(msg, type) { if (typeof toast === 'function') toast(msg, type); },
    onCapture: function(data) {
        if (!data.lineId) return;
        var line = document.getElementById(data.lineId);
        if (!line) return;
        line.querySelector('.line-gross').value = data.gross.toFixed(2);
        line.querySelector('.line-tare').value = data.tare.toFixed(2);
        if (typeof recalcSalesLine === 'function') recalcSalesLine(data.lineId);
    }
});
window.weighSalesLine = function(lineId) { salesKiosk.open(lineId); };
window.closeSalesScaleModal = function() { salesKiosk.close(); };
```

### 3.5 Различия конфигурации по режимам

| Параметр | Purchase | Sale |
|----------|---------|------|
| `mode` | `'purchase'` | `'sale'` |
| `title` | Закупка / Achiziție | Отгрузка / Expediere |
| `products` | 8 (без PEAR, APRICOT) | 10 (все) |
| `weightRange` | 50–500 кг | 5–200 кг |
| `showPassport` | `true` | `true` |
| `showEmulator` | `false` | `true` |
| `toastFn` | `showToast()` | `toast()` |
| `onCapture` | Устанавливает gross/tare/product/passport | Устанавливает gross/tare |

---

## 4. Публичный API

### 4.1 `.open(lineId)`

Открывает полноэкранный модал и привязывает его к строке документа.

```javascript
kiosk.open('line_42');
```

**Действия при вызове:**
1. Сохраняет `lineId` в `this._targetLineId`
2. Сбрасывает состояние: `_selectedProduct`, `_selectedVariety`, `_manualWeight`, `_paused`
3. Устанавливает UI в начальное состояние:
   - Вес: `0.000` / `0.000` / `0.000`
   - Статус: `'Запуск... / Pornire...'` (жёлтый индикатор)
   - Capture кнопка: disabled
   - AI Result: hidden
   - Numpad input: очищен
   - Viewport: заставка камеры
   - Pause: выключен
4. Если `showPassport` — скрывает паспорт
5. Если `loadDriverConfig` — загружает конфиг драйвера
6. Строит грид продуктов
7. Показывает модал (`display: flex`)
8. Запускает polling весов
9. Запускает авто-эмуляцию

### 4.2 `.close()`

Закрывает модал и останавливает все процессы.

```javascript
kiosk.close();
```

**Действия:**
1. Скрывает контейнер (`display: none`)
2. Останавливает polling (`clearInterval`)
3. Останавливает авто-эмуляцию (`clearInterval`)
4. Сбрасывает: `_targetLineId`, `_selectedProduct`, `_selectedVariety`, `_paused`
5. Если `showPassport` — скрывает паспорт

### 4.3 `.destroy()`

Полностью удаляет модал из DOM и освобождает ресурсы.

```javascript
kiosk.destroy();
```

**Действия:**
1. Вызывает `.close()`
2. Удаляет DOM-элемент контейнера
3. Обнуляет `this._container`

---

## 5. Внутреннее состояние

| Свойство | Тип | Назначение |
|----------|-----|-----------|
| `_targetLineId` | `string\|null` | ID строки документа, к которой привязан текущий сеанс |
| `_pollTimer` | `number\|null` | ID таймера `setInterval` для polling весов (1с) |
| `_emuTimer` | `number\|null` | ID таймера `setInterval` для авто-эмуляции (20с) |
| `_paused` | `boolean` | Флаг паузы авто-эмуляции |
| `_selectedProduct` | `string\|null` | Ключ выбранного продукта (напр. `'APPLE'`) |
| `_selectedVariety` | `object\|null` | Объект выбранного сорта из `window._agroRefs.varieties` |
| `_manualWeight` | `boolean` | Был ли вес введён вручную через Numpad |
| `_container` | `HTMLElement\|null` | Корневой DOM-элемент модала |
| `_id` | `string` | Уникальный prefix: `'sk_purchase'` или `'sk_sale'` |
| `_productNames` | `Object<string,string>` | Карта `{KEY: 'Отображаемое имя'}` |
| `_productImages` | `Object<string,string>` | Карта `{KEY: '/path/to/svg'}` |
| `_productKeys` | `string[]` | Массив ключей продуктов в порядке конфига |
| `_currentVarieties` | `object[]\|undefined` | Массив сортов текущего продукта (из `_agroRefs`) |

---

## 6. DOM-структура модала

Модал генерируется динамически в `_renderModal()` и добавляется в `document.body`.

```
div.scale-kiosk-overlay (id="sk_{mode}_overlay", display:none)
└── div.scale-kiosk
    ├── div.sk-header
    │   ├── div.sk-title [data-sk="title"]
    │   ├── div.sk-status
    │   │   ├── span.sk-indicator [data-sk="indicator"]
    │   │   └── span [data-sk="statusText"]
    │   ├── div.sk-driver-info [data-sk="driverInfo"]
    │   ├── button.sk-pause-btn [data-sk="pauseBtn"]
    │   └── button.sk-close [data-sk="closeBtn"]
    │
    └── div.sk-body (CSS Grid: 3 колонки)
        ├── div.sk-products (Левая колонка)
        │   ├── div.sk-products-title
        │   ├── div.sk-product-grid [data-sk="productGrid"]
        │   │   └── button.sk-product-btn [data-product="KEY"] (×N)
        │   │       ├── img.sk-product-img | div.sk-product-emoji
        │   │       └── span.sk-product-label
        │   │
        │   └── div.sk-passport [data-sk="passport"] (если showPassport)
        │       ├── div.sk-passport-header
        │       │   ├── span.sk-passport-product-name [data-sk="passportName"]
        │       │   └── span.sk-passport-badge "Паспорт / Pasaport"
        │       ├── div.sk-passport-section
        │       │   ├── div.sk-passport-label
        │       │   └── div.sk-variety-grid [data-sk="varietyGrid"]
        │       │       └── button.sk-variety-btn [data-vidx="N"] (×M)
        │       └── div.sk-passport-all (scrollable)
        │           ├── .sk-field-row: Калибр + Brix
        │           ├── .sk-field-row: Окраска (slider)
        │           ├── .sk-field-row: Температура + Свежесть (rating)
        │           ├── .sk-field-row: Срок хран. + Дефекты
        │           ├── .sk-field-row: % дефектных (hidden by default)
        │           ├── .sk-field-row: Упаковка + Маркировка
        │           └── .sk-field-row: Заметки (textarea)
        │
        ├── div.sk-scale (Центральная колонка)
        │   ├── div.sk-weight-display
        │   │   ├── div.sk-weight-gross [data-sk="gross"]
        │   │   └── div.sk-weight-unit "kg"
        │   ├── div.sk-weight-sub
        │   │   ├── div.sk-sub-item: Tare [data-sk="tare"]
        │   │   └── div.sk-sub-item: Net [data-sk="net"]
        │   ├── div.sk-scale-btns
        │   │   ├── button.sk-btn.sk-btn-zero [data-sk="zeroBtn"]
        │   │   └── button.sk-btn.sk-btn-tare [data-sk="tareBtn"]
        │   ├── div.sk-numpad
        │   │   ├── div.sk-numpad-title
        │   │   ├── input.sk-numpad-input [data-sk="numpadInput"]
        │   │   ├── div.sk-numpad-grid
        │   │   │   └── button.sk-numpad-btn [data-num="N"] (×12)
        │   │   └── button.sk-numpad-apply [data-sk="numpadApply"]
        │   └── button.sk-capture-btn [data-sk="captureBtn"]
        │
        └── div.sk-camera (Правая колонка)
            ├── div.sk-camera-header
            │   ├── span "📷 AI Camera"
            │   └── span.ai-badge "AI"
            ├── div.sk-camera-viewport [data-sk="viewport"]
            ├── div.sk-ai-result [data-sk="aiResult"]
            │   ├── div.sk-ai-label
            │   ├── div.sk-ai-product [data-sk="aiProduct"]
            │   └── div.sk-ai-confidence [data-sk="aiConfidence"]
            └── div.sk-emulator (если showEmulator)
                ├── div.sk-emulator-title
                └── div.sk-emu-btns
                    ├── input [data-sk="emuWeight"]
                    ├── button [data-sk="emuSet"]
                    ├── button [data-sk="emuRandom"]
                    └── button [data-sk="emuRemove"]
```

---

## 7. CSS-архитектура

### 7.1 Файл: `/static/agro/scale-kiosk.css` (326 строк)

Все классы используют префикс `.sk-` для изоляции от остальных стилей.

### 7.2 Основные CSS-секции

| Секция | Строки | Описание |
|--------|--------|----------|
| Overlay + Kiosk | 1–11 | Полноэкранный fixed overlay |
| Header | 14–36 | Flex-контейнер: title + status + driver + pause + close |
| Body grid | 39–43 | `grid-template-columns: 1fr 300px 280px` |
| Products | 46–72 | Левая колонка: грид продуктов, кнопки, SVG/emoji |
| Scale | 75–115 | Центральная: вес, tare/net, кнопки, capture |
| Camera | 118–137 | Правая: viewport, AI result |
| Emulator | 140–154 | Панель эмулятора (sale mode) |
| Passport | 157–241 | 12 полей паспорта: steppers, slider, rating, groups, textarea |
| Numpad | 244–272 | Цифровая клавиатура 3×4 |
| Animations | 275–318 | AI badge, camera idle/scanning/product, scanline, productAppear |
| Responsive | 322–326 | `@media (max-width: 900px)` — вертикальный stack |

### 7.3 Цветовая палитра

| Цвет | Hex | Назначение |
|------|-----|-----------|
| Фон overlay | `#0a0a1a` | Тёмный фон на весь экран |
| Фон header | `#0d0d1a` | Шапка |
| Фон products | `#12122a` | Левая/правая колонки |
| Фон scale | `#0a1628` | Центральная колонка |
| Фон карточек | `#16213e` | Кнопки, поля, группы |
| Фон дисплея | `#060e1a` | Дисплей веса, numpad input |
| Бордер | `#0f3460` | Все бордеры и разделители |
| Акцент (зелёный) | `#53d769` | Stable, active product, net, passport |
| Предупреждение | `#ffc107` | Settling, pause, numpad |
| Опасность | `#e94560` | Capture btn, tare btn, delete, error |
| Teal | `#4ec9b0` | Net значение, reference hints |
| Текст | `#e0e0f0` | Основной текст |
| Текст muted | `#8888aa` | Подписи, labels |
| Текст dimmed | `#6c6c8a` | Самый тусклый текст |
| Текст inputs | `#b0b0c8` | Значения в полях |

### 7.4 3-колоночная сетка

```css
.sk-body {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 300px 280px;
    gap: 0;
    overflow: hidden;
}
```

| Колонка | Ширина | CSS-класс | Содержимое |
|---------|--------|-----------|------------|
| Левая | `1fr` (flexible) | `.sk-products` | Грид продуктов + паспорт |
| Центральная | `300px` (fixed) | `.sk-scale` | Дисплей веса + numpad + capture |
| Правая | `280px` (fixed) | `.sk-camera` | AI camera + emulator |

### 7.5 Тач-оптимизация

Все интерактивные элементы имеют минимальный размер 44×44px:
- `.sk-product-btn` — `min-height: 100px`, `padding: 12px 8px`
- `.sk-step-btn` — `44x44px`
- `.sk-rate-btn` — `44x44px`
- `.sk-opt-btn` — `padding: 10px 14px`, `min-width: 70px`
- `.sk-numpad-btn` — `padding: 10px 0`
- `.sk-capture-btn` — `min-height: 60px`, `font-size: 18px`
- `.sk-emu-btns button` — `min-height: 40px`

---

## 8. Система событий и делегирование

### 8.1 Принцип

Все события привязаны через **event delegation** на корневом контейнере `this._container`. Один обработчик `click` маршрутизирует по `data-*` атрибутам и CSS-классам.

### 8.2 Маршрутизация click-событий

```javascript
this._container.addEventListener('click', function(e) {
    var t = e.target;
    // Маршрутизация по data-sk, data-num, data-step, data-rate, data-opt, data-vidx, data-product
});
```

| Селектор | Действие | Метод |
|----------|----------|-------|
| `[data-sk="closeBtn"]` | Закрыть модал | `close()` |
| `[data-sk="pauseBtn"]` | Пауза/продолжить | `_togglePause()` |
| `[data-sk="zeroBtn"]` | Обнулить весы | `_scaleZero()` |
| `[data-sk="tareBtn"]` | Установить тару | `_scaleTare()` |
| `[data-sk="captureBtn"]` | Захватить вес | `_capture()` |
| `[data-num="N"]` | Нажать цифру numpad | `_numpadPress(val)` |
| `[data-sk="numpadApply"]` | Применить вес numpad | `_numpadApply()` |
| `.sk-product-btn[data-product]` | Выбрать продукт | `_selectProduct(key)` |
| `[data-step][data-delta]` | Stepper ±  | `_stepField(name, delta)` |
| `.sk-rate-btn[data-rate]` | Выбрать рейтинг | `_setRating(group, val)` |
| `.sk-opt-btn[data-opt]` | Выбрать опцию | `_selectOpt(group, btn)` |
| `.sk-variety-btn[data-vidx]` | Выбрать сорт | `_selectVarietyByIndex(idx)` |
| `[data-sk="emuSet"]` | Эмулятор: установить вес | `_emuSet()` |
| `[data-sk="emuRandom"]` | Эмулятор: случайный | `_emuRandom()` |
| `[data-sk="emuRemove"]` | Эмулятор: убрать | `_emuRemove()` |

### 8.3 Input-события

Отдельный обработчик `input` для ползунка `ppColorSlider` (только если `showPassport`):

```javascript
this._container.addEventListener('input', function(e) {
    if (e.target.matches('[data-sk="ppColorSlider"]')) {
        // Обновить ppColorVal
    }
});
```

---

## 9. Левая колонка: Продукция + Паспорт

### 9.1 Грид продуктов

Грид перестраивается при каждом `.open()` вызовом `_buildProductGrid()`.

**CSS:** `grid-template-columns: repeat(auto-fill, minmax(110px, 1fr))`, `gap: 10px`

**Каждая кнопка:**
```html
<button class="sk-product-btn" data-product="APPLE">
  <img src="/static/.../apple.svg" class="sk-product-img" onerror="...">
  <div class="sk-product-emoji" style="display:none;">🍎</div>
  <span class="sk-product-label">Яблоко / Măr</span>
</button>
```

**Fallback:** Если SVG не загрузилось → `onerror` скрывает `<img>` и показывает emoji.

**Emoji карта (EMOJI_MAP):**

| Ключ | Emoji |
|------|-------|
| APPLE | 🍎 |
| PEAR | 🍐 |
| PEACH | 🍑 |
| PLUM | 🟣 |
| CHERRY | 🍒 |
| GRAPE | 🍇 |
| APRICOT | 🟠 |
| WALNUT | 🌰 |
| TOMATO | 🍅 |
| PEPPER | 🌶️ |

### 9.2 Выбор продукта (`_selectProduct`)

1. Сохраняет `_selectedProduct = key`
2. Подсвечивает кнопку (`.active`)
3. Обновляет AI-панель: имя продукта, «Выбрано вручную»
4. Показывает превью в camera viewport
5. Если `showPassport` — вызывает `_showPassport(key)`

---

## 10. Центральная колонка: Весы + Numpad

### 10.1 Дисплей веса

```
┌──────────────────────┐
│      125.500         │  ← .sk-weight-gross (48px monospace)
│        kg            │  ← .sk-weight-unit
└──────────────────────┘
┌──────────┐ ┌──────────┐
│ Tare     │ │ Net      │
│ 0.000    │ │ 125.500  │  ← teal
└──────────┘ └──────────┘
  [Zero]       [Tare]
```

### 10.2 Numpad

Цифровая клавиатура для ручного ввода веса (touchscreen-optimized):

```
┌─────────────────────┐
│ Ручной ввод / Manual│
│ ┌─────────────────┐ │
│ │           125.5 │ │  ← readonly input, monospace, #ffc107
│ └─────────────────┘ │
│  [7] [8] [9]        │
│  [4] [5] [6]        │
│  [1] [2] [3]        │
│  [0] [.] [⌫]        │  ← ⌫ красный (#e94560)
│  [Применить / Aplică]│  ← жёлтый фон
└─────────────────────┘
```

**Логика `_numpadPress(val)`:**
- `del` → удалить последний символ
- `.` → добавить, если нет точки
- `0-9` → добавить, если длина (без точки) < 6

**Логика `_numpadApply()`:**
1. Парсить вес из input
2. Если <= 0 → return
3. Установить `_manualWeight = true`
4. Остановить авто-эмуляцию
5. POST `/api/agro-scale/simulate` с `weight_kg`
6. Обновить дисплей
7. Разблокировать Capture

### 10.3 Capture кнопка

Красная кнопка на всю ширину колонки. Disabled пока вес не стабилен.

---

## 11. Правая колонка: AI Camera + Эмулятор

### 11.1 Camera Viewport

Область отображения с тремя состояниями:

| Состояние | CSS-класс | Описание |
|-----------|-----------|----------|
| Idle | `.camera-idle` | «📷 Запуск...» |
| Scanning | `.camera-scanning` | «🔍 Сканирование...» + scanline animation |
| Product | `.camera-product-preview` | Фото продукта + имя + AI confidence bar |

### 11.2 AI Result панель

```html
<div class="sk-ai-result">
  <div class="sk-ai-label">Распознано / Recunoscut:</div>
  <div class="sk-ai-product">Персик / Piersică</div>
  <div class="sk-ai-confidence">Точность: 95.2% | Вес: 125.50 кг</div>
</div>
```

### 11.3 Панель эмулятора (только sale mode)

```html
<div class="sk-emulator">
  <div class="sk-emulator-title">Эмулятор / Emulator</div>
  <input type="number" data-sk="emuWeight" placeholder="кг">
  <button data-sk="emuSet">Set</button>            → POST simulate {weight_kg}
  <button data-sk="emuRandom">Random</button>      → POST simulate {random:true}
  <button data-sk="emuRemove">Remove</button>      → POST simulate {weight_kg:0}
</div>
```

---

## 12. Polling и связь с весами

### 12.1 Цикл polling

```
.open()
  └── _startPolling()
        └── setInterval(_pollScale, 1000)
              └── GET /api/agro-scale/read?scale_id=default
                    └── Обновить UI: gross, tare, net, indicator, status, captureBtn
```

### 12.2 Логика обновления UI при polling

| Условие | Индикатор | Статус | Capture |
|---------|-----------|--------|---------|
| `status === 'stable' && gross_kg > 0` | 🟢 `#53d769` | `'● Stable / Стабильно'` | enabled |
| `status === 'settling'` | 🟡 `#ffc107` | `'◌ Settling... / Стабилизация...'` | disabled |
| Иное | ⚪ `#666` | `'Idle / Ожидание'` | disabled |
| Ошибка fetch | 🔴 `#e94560` | `'Ошибка связи'` | без изменений |

### 12.3 Пауза

Кнопка `⏸ Пауза / Pauză` переключает `_paused`:
- `true` → текст меняется на `▶ Продолжить / Continuă`, кнопка `.active` (жёлтый фон)
- Polling продолжает работать, но `_runEmulationCycle` пропускает итерации

---

## 13. Авто-эмуляция

### 13.1 Цикл

```
.open()
  └── _startAutoEmulation()
        └── setInterval(_runEmulationCycle, 20000)
```

### 13.2 Шаги одного цикла `_runEmulationCycle()`

1. Если `_paused` → return
2. Показать анимацию сканирования в viewport
3. POST `/api/agro-scale/simulate` → `{random:true, min_kg, max_kg}`
4. Цикл ожидания стабильности (каждые 300мс, до 20 попыток):
   - GET `/api/agro-scale/read`
   - Если `stable` или 20 попыток → продолжить
5. Выбрать случайный продукт
6. Генерировать confidence (85–99%)
7. Обновить UI:
   - Camera viewport: SVG/emoji + имя + confidence bar
   - AI result: имя + «Точность: X% | Вес: Y кг»
   - Product grid: подсветить выбранный
   - Если `showPassport` → показать паспорт
8. Разблокировать Capture

### 13.3 Таймлайн одного цикла (20с)

```
0с          2-3с               4-6с               20с
│           │                  │                   │
▼           ▼                  ▼                   ▼
Simulate    Scanning anim      AI recognizes       Next cycle
POST        🔍 scanline        📷 product + %      ──→
            settling...        ✅ stable
```

---

## 14. Паспорт продукции (детально)

### 14.1 Когда показывается

Паспорт показывается если `showPassport: true` И продукт выбран (вручную или авто-эмуляцией).

### 14.2 Источник данных

Сорта продуктов loadируются из `window._agroRefs.varieties` (массив объектов, заполняемый Flask-шаблоном из Oracle `AGRO_ITEM_VARIETIES`).

```javascript
var allVarieties = window._agroRefs.varieties || [];
this._currentVarieties = allVarieties.filter(function(v) { return v.item_code === productKey; });
```

### 14.3 Поля паспорта

| # | Поле | data-sk | Виджет | Тип значения | Значение по умолчанию |
|---|------|---------|--------|-------------|----------------------|
| 1 | Сорт / Soi | `varietyGrid` | Grid кнопок `sk-variety-btn` | Объект из `_agroRefs.varieties` | Первый сорт |
| 2 | Калибр, мм / Calibru | `ppCalibr` | Stepper (−1/+1) | `number` (int) | от сорта `min_calibre_mm` |
| 3 | Brix, ° | `ppBrix` | Stepper (−0.5/+0.5) | `number` (float) | от сорта `min_brix` |
| 4 | Окраска, % / Colorare | `ppColorSlider` | Range slider 0–100 | `number` (int) | 50% или от сорта `color_coverage_pct` |
| 5 | t °C / Temperatura | `ppTemp` | Stepper (−0.5/+0.5) | `number` (float) | от сорта `optimal_temp_min` |
| 6 | Свежесть / Prospetime | `ppFreshness` | Rating 1–5 (кнопки) | `number` (int 1–5) | 4 |
| 7 | Срок хран. / Termen | `ppShelfLife` | Readonly display | `string` | от сорта `shelf_life_days` + «дн.» |
| 8 | Дефекты / Defecte | `ppDefects` | Btn-group (Нет/Мин./Серьёз.) | `string` (`none\|minor\|serious`) | `none` |
| 9 | % дефектных / % defecte | `ppDefectPct` | Stepper (−1/+1, 0–100) | `number` (int) | 0 |
| 10 | Упаковка / Ambalaj | `ppPackaging` | Btn-group (OK/Поврежд./Нет) | `string` (`ok\|damaged\|missing`) | `ok` |
| 11 | Маркировка / Etichetare | `ppLabel` | Btn-group (OK/Частичн./Нет) | `string` (`ok\|partial\|missing`) | `ok` |
| 12 | Заметки / Note | `ppNotes` | Textarea (2 rows) | `string` | `''` |

### 14.4 Условная видимость

- **Окраска (color):** Показывается только для `APPLE`, `PEACH`, `CHERRY`. Скрыт для остальных.
- **% дефектных:** Показывается только если Дефекты !== `'none'`.

### 14.5 Reference hints

Под полями Калибр, Brix, Окраска, Температура показываются reference-значения из сорта:

| Поле | Reference элемент | Пример |
|------|-------------------|--------|
| Калибр | `ppCalibrRef` | `мин. 65 мм` |
| Brix | `ppBrixRef` | `мин. 11.5°` |
| Окраска | `ppColorRef` | `мин. 50%` |
| Температура | `ppTempRef` | `2…4 °C` |

### 14.6 Выбор сорта (`_selectVarietyByIndex`)

1. Подсветить кнопку сорта
2. Заполнить reference hints из объекта сорта
3. Заполнить поля ввода значениями из сорта (calibre, brix, color, temp)

### 14.7 Сброс паспорта (`_resetPassport`)

Вызывается при каждом открытии паспорта для нового продукта:
- Очистить числовые поля
- Slider → 50%
- Defect % → 0, строка скрыта
- Freshness → 4
- Packaging → ok, Label → ok, Defects → none
- Notes → пусто

### 14.8 Объект паспорта (`_collectPassport`)

При захвате собирается объект:

```javascript
{
    product_key: 'APPLE',
    variety_id: 42,
    variety_code: 'GOLDEN',
    calibre_mm: 70,
    brix: 12.5,
    color_coverage_pct: 65,
    freshness_score: 4,
    temp_c: 3.0,
    packaging: 'ok',
    labeling: 'ok',
    defects: 'none',
    defect_pct: 0,
    notes: 'Партия хорошая'
}
```

---

## 15. Процесс захвата (Capture)

### 15.1 Последовательность `_capture()`

```
1. captureBtn.disabled = true
2. captureBtn.textContent = '⏳ Фиксация...'
3. Остановить авто-эмуляцию
4. POST /api/agro-scale/capture {scale_id}
5. Получить reading: {gross_kg, tare_kg, net_kg}
6. Собрать data = {
       lineId, gross, tare, net,
       productKey, productName,
       passport (если showPassport)
   }
7. Вызвать onCapture(data)
8. Закрыть модал: close()
9. Toast: «Вес снят: X.XX кг — Продукт»
```

### 15.2 Объект data, передаваемый в onCapture

| Поле | Тип | Описание |
|------|-----|----------|
| `lineId` | `string` | ID строки документа (переданный в `.open()`) |
| `gross` | `number` | Брутто, кг |
| `tare` | `number` | Тара, кг |
| `net` | `number` | Нетто, кг |
| `productKey` | `string\|null` | Код продукта (`'APPLE'`, `'GRAPE'`, ...) |
| `productName` | `string` | Отображаемое имя продукта |
| `passport` | `object\|null` | Объект паспорта (если `showPassport`) — см. §14.8 |

### 15.3 Обработка ошибки

При ошибке fetch:
1. Вернуть текст кнопки: `'⚖️ Снять вес / Cântărește'`
2. Разблокировать Capture
3. Перезапустить авто-эмуляцию
4. Toast: `'Ошибка: ...'`

---

## 16. Конфигурация драйвера

### 16.1 `_loadDriverConfig()`

Загружается при `.open()`, если `loadDriverConfig: true`.

```
GET /api/agro-admin/module-config
  → filter config_group === 'scale_driver'
    → parse JSON → find active !== false
      → update title: '⚖️ Весы / Cântar — {brand}'
      → update driverInfo: 'Driver: {brand} | Max: {max_capacity} kg'
```

### 16.2 Fallback

Если API недоступен или нет активного драйвера:
- Title: оставить как в конфиге
- Driver info: `'Driver: Emulator | Max: 600 kg'`

---

## 17. Интеграция с шаблонами

### 17.1 agro_field.html (приёмка)

**Точка входа:** кнопка `⚖` в строке документа закупки → `weighPurchaseLine(lineId)`

```
Кнопка ⚖ → weighPurchaseLine(lineId)
  → fieldKiosk.open(lineId)
    → Полноэкранный модал
      → (работа оператора)
        → Capture
          → onCapture(data)
            → line.querySelector('.line-gross').value = data.gross
            → line.querySelector('.line-tare').value = data.tare
            → line.querySelector('.line-item').value = data.productKey
            → line.setAttribute('data-passport', JSON.stringify(data.passport))
            → recalcPurchaseLine(lineId)
```

**Legacy-обёртки:**
```javascript
window.weighPurchaseLine = function(lineId) { fieldKiosk.open(lineId); };
window.closeScaleModal = function() { fieldKiosk.close(); };
```

### 17.2 agro_sales.html (отгрузка)

**Точка входа:** кнопка `⚖` в строке документа продажи → `weighSalesLine(lineId)`

```
Кнопка ⚖ → weighSalesLine(lineId)
  → salesKiosk.open(lineId)
    → Полноэкранный модал
      → (работа оператора)
        → Capture
          → onCapture(data)
            → line.querySelector('.line-gross').value = data.gross
            → line.querySelector('.line-tare').value = data.tare
            → recalcSalesLine(lineId)
```

**Legacy-обёртки:**
```javascript
window.weighSalesLine = function(lineId) { salesKiosk.open(lineId); };
window.closeSalesScaleModal = function() { salesKiosk.close(); };
```

---

## 18. Scale API: полный справочник

### 18.1 GET `/api/agro-scale/read`

**Параметры:** `?scale_id=default`

**Ответ (200):**
```json
{
  "success": true,
  "data": {
    "gross_kg": 125.500,
    "tare_kg": 0.000,
    "net_kg": 125.500,
    "status": "stable",
    "stable": true,
    "timestamp": "2026-03-28T14:30:00"
  }
}
```

**Значения `status`:**
| Значение | Описание |
|----------|----------|
| `stable` | Вес стабилен, можно захватывать |
| `settling` | Вес стабилизируется |
| `idle` | Нет груза на весах |

### 18.2 POST `/api/agro-scale/capture`

**Body:** `{ "scale_id": "default" }`

**Ответ (200):**
```json
{
  "success": true,
  "reading": {
    "gross_kg": 125.500,
    "tare_kg": 0.000,
    "net_kg": 125.500,
    "captured_at": "2026-03-28T14:30:05"
  }
}
```

### 18.3 POST `/api/agro-scale/zero`

Обнуление весов.

**Body:** `{ "scale_id": "default" }`

### 18.4 POST `/api/agro-scale/tare`

Установка текущего веса как тары.

**Body:** `{ "scale_id": "default" }`

### 18.5 POST `/api/agro-scale/simulate`

Эмулятор для тестирования.

**Body (вариант 1 — установить вес):**
```json
{ "scale_id": "default", "weight_kg": 125.5 }
```

**Body (вариант 2 — случайный вес):**
```json
{ "scale_id": "default", "random": true, "min_kg": 50, "max_kg": 500 }
```

**Body (вариант 3 — убрать вес):**
```json
{ "scale_id": "default", "weight_kg": 0 }
```

### 18.6 GET `/api/agro-admin/module-config`

Используется для загрузки конфигурации драйвера.

**Ответ:** массив config-записей, фильтруется по `config_group === 'scale_driver'`.

---

## 19. Product SVG иконки

### 19.1 Расположение

`/static/agro/products/` — 10 SVG-файлов размером ~48×48px.

### 19.2 Список

| Файл | Продукт | Ключ | Fallback emoji |
|------|---------|------|----------------|
| `apple.svg` | Яблоко | APPLE | 🍎 |
| `apricot.svg` | Абрикос | APRICOT | 🟠 |
| `cherry.svg` | Вишня/Черешня | CHERRY | 🍒 |
| `grape.svg` | Виноград | GRAPE | 🍇 |
| `peach.svg` | Персик | PEACH | 🍑 |
| `pear.svg` | Груша | PEAR | 🍐 |
| `pepper.svg` | Перец | PEPPER | 🌶️ |
| `plum.svg` | Слива | PLUM | 🟣 |
| `tomato.svg` | Томат | TOMATO | 🍅 |
| `walnut.svg` | Грецкий орех | WALNUT | 🌰 |

### 19.3 Fallback-механизм

```html
<img src="apple.svg" onerror="this.style.display='none'">
<div class="sk-product-emoji" style="display:none;">🍎</div>
```

При ошибке загрузки SVG: `img.onerror` скрывает `<img>` и показывает `<div>` с emoji.
В camera viewport используется inline onerror: `this.outerHTML='<div>🍎</div>'`.

---

## 20. Responsive и адаптивность

### 20.1 Breakpoint

```css
@media (max-width: 900px) {
    .sk-body {
        grid-template-columns: 1fr;
        grid-template-rows: auto 1fr auto;
    }
    .sk-products { max-height: 200px; }
    .sk-product-grid {
        grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
    }
}
```

### 20.2 Поведение на маленьких экранах

| Элемент | Desktop (>900px) | Mobile (≤900px) |
|---------|-----------------|-----------------|
| Layout | 3 колонки в ряд | 3 блока в стопку |
| Products | Без ограничения высоты | max-height: 200px |
| Product buttons | minmax(110px, 1fr) | minmax(80px, 1fr) |

---

## 21. Анимации

### 21.1 CSS-анимации

| Анимация | Keyframes | Длительность | Назначение |
|----------|-----------|-------------|-----------|
| `scanline` | 0%→100%: translateY(-60px→+60px) | 2s infinite | Горизонтальная линия сканирования |
| `productAppear` | 0%→60%→100%: scale(0.3→1.1→1) + rotate | 0.5s ease-out | Появление продукта в viewport |
| `skSlideUp` | max-height 0→50vh + opacity 0→1 | 0.2s ease-out | Появление паспорта |

### 21.2 CSS-переходы

| Элемент | Свойство | Длительность |
|---------|----------|-------------|
| `.sk-product-btn` | all | 0.15s |
| `.sk-btn` | all | 0.15s |
| `.sk-close` | all | 0.2s |
| `.sk-pause-btn` | all | 0.2s |
| `.sk-capture-btn` | all | 0.2s |
| `.sk-step-btn` | all | 0.12s |
| `.sk-rate-btn` | all | 0.12s |
| `.sk-opt-btn` | all | 0.12s |
| `.sk-numpad-btn` | all | 0.15s |
| `.sk-variety-btn` | all | 0.15s |
| `.camera-ai-bar-fill` | width | 0.5s ease |

---

## 22. Работа с data-атрибутами

### 22.1 `data-sk` — адресация элементов

Вместо ID используется `data-sk` для изоляции нескольких экземпляров:

```javascript
// Поиск элемента внутри контейнера
this.$ = function(suffix) {
    return this._container.querySelector('[data-sk="' + suffix + '"]');
};
this.$$ = function(suffix) {
    return this._container.querySelectorAll('[data-sk="' + suffix + '"]');
};
```

**Полный список `data-sk` значений:**

| data-sk | Элемент | Тип |
|---------|---------|-----|
| `title` | Заголовок модала | `div` |
| `indicator` | Индикатор статуса (кружок) | `span` |
| `statusText` | Текст статуса | `span` |
| `driverInfo` | Информация о драйвере | `div` |
| `pauseBtn` | Кнопка паузы | `button` |
| `closeBtn` | Кнопка закрытия | `button` |
| `productGrid` | Контейнер грида продуктов | `div` |
| `passport` | Панель паспорта | `div` |
| `passportName` | Имя продукта в паспорте | `span` |
| `varietyGrid` | Грид сортов | `div` |
| `ppCalibr` | input Калибр | `input[number]` |
| `ppCalibrRef` | Ref hint калибр | `div` |
| `ppBrix` | input Brix | `input[number]` |
| `ppBrixRef` | Ref hint brix | `div` |
| `ppColorSlider` | Slider окраска | `input[range]` |
| `ppColorVal` | Значение окраски | `span` |
| `ppColorRow` | Строка окраски (для visibility) | `div` |
| `ppColorRef` | Ref hint окраска | `div` |
| `ppTemp` | input Температура | `input[number]` |
| `ppTempRef` | Ref hint температура | `div` |
| `ppFreshness` | Рейтинг свежести | `div` |
| `ppShelfLife` | Срок хранения (readonly) | `div` |
| `ppDefects` | Btn-group дефекты | `div` |
| `ppDefectPctRow` | Строка % дефекты (hidden) | `div` |
| `ppDefectPct` | input % дефекты | `input[number]` |
| `ppPackaging` | Btn-group упаковка | `div` |
| `ppLabel` | Btn-group маркировка | `div` |
| `ppNotes` | Textarea заметки | `textarea` |
| `gross` | Дисплей Gross | `div` |
| `tare` | Значение Tare | `span` |
| `net` | Значение Net | `span` |
| `zeroBtn` | Кнопка Zero | `button` |
| `tareBtn` | Кнопка Tare | `button` |
| `numpadInput` | Поле numpad | `input` |
| `numpadApply` | Кнопка «Применить» | `button` |
| `captureBtn` | Кнопка захвата | `button` |
| `viewport` | Camera viewport | `div` |
| `aiResult` | Панель AI результата | `div` |
| `aiProduct` | Имя распознанного продукта | `div` |
| `aiConfidence` | Точность + вес | `div` |
| `emuWeight` | input вес эмулятора | `input[number]` |
| `emuSet` | Кнопка Set | `button` |
| `emuRandom` | Кнопка Random | `button` |
| `emuRemove` | Кнопка Remove | `button` |

### 22.2 Другие data-атрибуты

| Атрибут | На элементе | Значение | Использование |
|---------|------------|----------|--------------|
| `data-product` | `.sk-product-btn` | `'APPLE'`, `'GRAPE'`, ... | Выбор продукта |
| `data-num` | `.sk-numpad-btn` | `'0'`–`'9'`, `'.'`, `'del'` | Numpad |
| `data-step` | `.sk-step-btn` | `'ppCalibr'`, `'ppBrix'`, `'ppTemp'`, `'ppDefectPct'` | Stepper target |
| `data-delta` | `.sk-step-btn` | `'-1'`, `'1'`, `'-0.5'`, `'0.5'` | Stepper increment |
| `data-rate` | `.sk-rate-btn` | `'1'`–`'5'` | Rating value |
| `data-opt` | `.sk-opt-btn` | `'none'`, `'minor'`, `'serious'`, `'ok'`, `'damaged'`, `'missing'`, `'partial'` | Option value |
| `data-vidx` | `.sk-variety-btn` | `'0'`, `'1'`, ... | Variety index |
| `data-value` | `.sk-rating`, `.sk-btn-group` | Current selected value | Read by `_collectPassport()` |

---

## 23. Совместимость с legacy-кодом

### 23.1 Обёртки глобальных функций

**agro_field.html:**
```javascript
window.weighPurchaseLine = function(lineId) { fieldKiosk.open(lineId); };
window.closeScaleModal = function() { fieldKiosk.close(); };
```

**agro_sales.html:**
```javascript
window.weighSalesLine = function(lineId) { salesKiosk.open(lineId); };
window.closeSalesScaleModal = function() { salesKiosk.close(); };
```

### 23.2 Что осталось в шаблонах

| Элемент | Остался | Описание |
|---------|---------|----------|
| Standalone scale JS | Да | Автономная страница весов (не модал) — свой polling, capture, эмулятор |
| recalcPurchaseLine / recalcSalesLine | Да | Пересчёт строки документа |
| showToast / toast | Да | Функции уведомлений |
| `window._agroRefs` | Да | Справочники (items, suppliers, varieties, profiles) |

---

## 24. Диаграмма жизненного цикла

```
[Конструктор] ────────────────────────────────────────────────────
    │
    ├── Читает config
    ├── Строит product maps (_productNames, _productImages, _productKeys)
    ├── _renderModal() → DOM добавлен в body (display:none)
    └── _bindEvents() → delegation на container
         │
[.open(lineId)] ─────────────────────────────────────────────────
    │
    ├── Reset state (_targetLineId, _selectedProduct, ...)
    ├── Reset UI (gross=0, status=idle, captureBtn=disabled)
    ├── _hidePassport()
    ├── _loadDriverConfig() → GET /api/agro-admin/module-config
    ├── _buildProductGrid() → render product buttons
    ├── container.style.display = 'flex'
    ├── _startPolling() → setInterval(1000ms)
    │     └── _pollScale() → GET /api/agro-scale/read
    │           └── Update: gross, tare, net, indicator, status, captureBtn
    └── _startAutoEmulation() → setInterval(20000ms)
          └── _runEmulationCycle()
                ├── POST /api/agro-scale/simulate (random)
                ├── Wait for stable (polling 300ms × 20)
                ├── Random product
                ├── Update viewport, AI result
                ├── _highlightProduct()
                └── _showPassport() (if enabled)
         │
[Работа оператора] ──────────────────────────────────────────────
    │
    ├── Click product → _selectProduct()
    │     ├── _highlightProduct()
    │     ├── Update AI panel
    │     └── _showPassport() → _selectVarietyByIndex(0)
    │
    ├── Fill passport → _stepField(), _setRating(), _selectOpt()
    │
    ├── Numpad → _numpadPress() + _numpadApply()
    │     └── POST /api/agro-scale/simulate (manual weight)
    │
    ├── Zero → _scaleZero() → POST /api/agro-scale/zero
    ├── Tare → _scaleTare() → POST /api/agro-scale/tare
    └── Pause → _togglePause()
         │
[Capture] ────────────────────────────────────────────────────────
    │
    ├── captureBtn disabled
    ├── _stopAutoEmulation()
    ├── POST /api/agro-scale/capture
    ├── Collect data = {lineId, gross, tare, net, productKey, productName, passport}
    ├── onCapture(data) → callback в шаблоне
    ├── close()
    └── toastFn('Вес снят: X.XX кг — Продукт', 'success')
         │
[.close()] ───────────────────────────────────────────────────────
    │
    ├── container.style.display = 'none'
    ├── _stopPolling() → clearInterval
    ├── _stopAutoEmulation() → clearInterval
    ├── Reset: _targetLineId, _selectedProduct, _selectedVariety, _paused
    └── _hidePassport()
         │
[.destroy()] ─────────────────────────────────────────────────────
    │
    ├── close()
    ├── Remove DOM element
    └── _container = null
```

---

## 25. Checklist после изменений

При любых изменениях в ScaleKiosk проверить:

- [ ] `scale-kiosk.js` — скомпилирован (нет синтаксических ошибок)
- [ ] `scale-kiosk.css` — нет конфликтов `.sk-*` классов
- [ ] `agro_field.html` — `<script src="scale-kiosk.js">` ДО inline `<script>`
- [ ] `agro_sales.html` — `<script src="scale-kiosk.js">` ДО inline `<script>`
- [ ] Purchase mode: кнопка ⚖ → модал открывается
- [ ] Purchase mode: грид продуктов (8 SVG)
- [ ] Purchase mode: паспорт при выборе продукта (12 полей)
- [ ] Purchase mode: сорта из `_agroRefs.varieties`
- [ ] Purchase mode: capture → gross/tare/product → строка документа
- [ ] Purchase mode: checkout passport JSON → `data-passport`
- [ ] Sale mode: кнопка ⚖ → модал открывается
- [ ] Sale mode: грид продуктов (10 SVG)
- [ ] Sale mode: паспорт при выборе продукта
- [ ] Sale mode: эмулятор (Set/Random/Remove)
- [ ] Sale mode: авто-эмуляция 20с цикл
- [ ] Sale mode: capture → gross/tare → строка документа
- [ ] Numpad: цифры, точка, delete, apply
- [ ] Zero/Tare → API вызовы
- [ ] Pause/Resume → эмуляция останавливается/продолжается
- [ ] Driver config → заголовок обновляется
- [ ] Responsive: <900px → stacked layout
- [ ] SVG fallback: emoji при ошибке загрузки
- [ ] Нет console errors при открытии/закрытии

---

## Полный список внутренних методов

| # | Метод | Тип | Описание |
|---|-------|-----|----------|
| 1 | `$(suffix)` | DOM | Найти элемент по `data-sk` |
| 2 | `$$(suffix)` | DOM | Найти все элементы по `data-sk` |
| 3 | `_renderModal()` | Init | Создать DOM-дерево модала |
| 4 | `_bindEvents()` | Init | Привязать event delegation |
| 5 | `open(lineId)` | Public | Открыть модал |
| 6 | `close()` | Public | Закрыть модал |
| 7 | `destroy()` | Public | Удалить модал из DOM |
| 8 | `_buildProductGrid()` | Products | Построить грид продуктов |
| 9 | `_selectProduct(key)` | Products | Выбрать продукт |
| 10 | `_highlightProduct(key)` | Products | Подсветить кнопку |
| 11 | `_startPolling()` | Scale | Запустить polling 1с |
| 12 | `_stopPolling()` | Scale | Остановить polling |
| 13 | `_pollScale()` | Scale | Один цикл polling |
| 14 | `_scaleZero()` | Scale | POST /zero |
| 15 | `_scaleTare()` | Scale | POST /tare |
| 16 | `_numpadPress(val)` | Numpad | Обработать нажатие |
| 17 | `_numpadApply()` | Numpad | Применить вес |
| 18 | `_startAutoEmulation()` | Emu | Запустить авто-эмуляцию |
| 19 | `_stopAutoEmulation()` | Emu | Остановить авто-эмуляцию |
| 20 | `_togglePause()` | Emu | Переключить паузу |
| 21 | `_runEmulationCycle()` | Emu | Один цикл эмуляции |
| 22 | `_capture()` | Capture | Захватить вес |
| 23 | `_loadDriverConfig()` | Config | Загрузить конфиг драйвера |
| 24 | `_showPassport(key)` | Passport | Показать паспорт |
| 25 | `_selectVarietyByIndex(idx)` | Passport | Выбрать сорт |
| 26 | `_resetPassport()` | Passport | Сброс полей |
| 27 | `_hidePassport()` | Passport | Скрыть паспорт |
| 28 | `_stepField(name, delta)` | Passport | Stepper ± |
| 29 | `_setRating(group, val)` | Passport | Установить рейтинг |
| 30 | `_selectOpt(group, btn)` | Passport | Выбрать опцию |
| 31 | `_collectPassport()` | Passport | Собрать данные паспорта |
| 32 | `_emuSet()` | Emulator | Установить вес |
| 33 | `_emuRandom()` | Emulator | Случайный вес |
| 34 | `_emuRemove()` | Emulator | Убрать вес |

---

*Artgranit AGRO — ScaleKiosk Specification — v1.0 — 28.03.2026*
