# TexFlow — блок-схемы (Mermaid)

**Русский** · [Română](ARCHITECTURE.ro.md) · [English](ARCHITECTURE.en.md)

Схемы ниже рисуются прямо на GitHub, в VS Code с поддержкой Mermaid и на
https://mermaid.live. Первая схема также встроена в страницу «Инструкция»
самого приложения.

## 1. Процесс от мешка до полки

```mermaid
flowchart TD
    A([Поставка пришла:<br/>мешки из Турции / Китая,<br/>всё вперемешку]) --> B[Создать поставку<br/>валюта, курс, фрахт,<br/>таможня, брокер, прочее]
    B --> C[/Примерный упаковочный лист CSV<br/>мешок · категория · описание · кол-во · цена · вес/]
    C --> D[Импорт: строки листа +<br/>мешки создаются сами]
    D --> E{Взять мешок}
    E --> F[Вскрыть мешок<br/>статус: sorting]
    F --> G{Вещь уже<br/>заведена?}
    G -- да, есть EAN/SKU --> H[Сканер: +1 шт]
    G -- нет --> I[Новая модель:<br/>название, категория,<br/>закупка из листа]
    I --> J[Выбрать цвета по группам<br/>Белый / Чёрный / Бежевый...]
    J --> K[Матрица цвет × размер<br/>ввести штуки]
    K --> L[(intake_items<br/>+ варианты SKU/EAN)]
    H --> L
    L --> M{Мешок пуст?}
    M -- нет --> G
    M -- да --> N[Мешок разобран<br/>статус: done]
    N --> O{Все мешки?}
    O -- нет --> E
    O -- да --> P[Сверка с листом<br/>по категориям и мешкам]
    P --> Q{Расхождения?}
    Q -- недостача / излишек --> R[Претензия поставщику<br/>или корректировка −N]
    R --> S
    Q -- нет --> S[Расчёт себестоимости]
    S --> T[Цены по наценкам<br/>красивое округление]
    T --> U[Карточки товара<br/>и каталог, экспорт CSV]
    T --> V{Печать этикеток}
    V --> W1[ZPL → Zebra]
    V --> W2[TSPL → TSC]
    V --> W3[PDF A4 → обычный принтер]
    V --> W4[PDF рулон → виртуальный принтер]
    W1 & W2 & W3 & W4 --> X([Товар на вешалке<br/>со штрихкодом и ценой])
```

## 2. Экран «Разбор мешка»

```mermaid
flowchart LR
    subgraph Вход
      S1[Сканер EAN/SKU]
      S2[Поиск модели]
      S3[Новая модель]
    end
    S1 -- найден --> J[(+1 шт в журнал)]
    S1 -- не найден --> E[Ошибка: создайте модель]
    S2 --> M[Матрица модели]
    S3 --> M
    M -- клик по цвету --> R[Добавить строку цвета]
    R --> M
    M -- Enter / стрелки --> M
    M -- Ctrl+Enter --> V{Вариант есть?}
    V -- нет --> NV[Создать вариант:<br/>SKU = АРТ-ЦВЕТ-РАЗМЕР<br/>EAN-13 = 200 + № + контрольная]
    NV --> J2[(intake_items)]
    V -- да --> J2
    J2 -- «Записать и печатать» --> L[Этикетки только<br/>на эту партию]
```

## 3. Модель данных (ER)

```mermaid
erDiagram
    SUPPLIERS ||--o{ SHIPMENTS : "поставляет"
    SUPPLIERS ||--o{ PRODUCTS : "производит"
    SHIPMENTS ||--o{ BAGS : "состоит из"
    SHIPMENTS ||--o{ PACKING_LINES : "лист (примерно)"
    SHIPMENTS ||--o{ INTAKE_ITEMS : "факт приёмки"
    BAGS ||--o{ INTAKE_ITEMS : "достали из"
    CATEGORIES ||--o{ PRODUCTS : "наценка, пошлина"
    CATEGORIES ||--o{ PACKING_LINES : ""
    SIZE_SCALES ||--o{ SIZES : ""
    SIZE_SCALES ||--o{ CATEGORIES : "шкала по умолчанию"
    COLOR_FAMILIES ||--o{ COLORS : "группа"
    PRODUCTS ||--o{ VARIANTS : "цвет × размер"
    COLORS ||--o{ VARIANTS : ""
    SIZES ||--o{ VARIANTS : ""
    VARIANTS ||--o{ INTAKE_ITEMS : "штуки"

    SHIPMENTS {
        int id PK
        text code UK
        text currency
        real fx_rate
        real freight
        real customs
        real broker
        real other_costs
        text alloc_method "value|qty|weight"
        text status "open|sorted|priced|closed"
    }
    BAGS {
        int id PK
        text bag_no
        real weight_kg
        text status "closed|sorting|done"
    }
    PACKING_LINES {
        int id PK
        text bag_no
        int qty
        real unit_price_fx
        real weight_kg
    }
    PRODUCTS {
        int id PK
        text style_code UK
        text name
        real base_cost_fx
        real retail_price
        int price_locked
    }
    VARIANTS {
        int id PK
        text sku UK
        text ean13 UK
    }
    INTAKE_ITEMS {
        int id PK
        int qty
        real unit_cost_fx
        real landed_unit_cost
    }
    CATEGORIES {
        int id PK
        text code UK
        real markup_pct
        real duty_pct
        text hs_code
    }
```

## 4. Расчёт себестоимости и цены

```mermaid
flowchart TD
    A[Строка приёмки:<br/>qty, закупка в валюте] --> B[× курс поставки]
    B --> C[+ пошлина категории %]
    D[Фрахт + таможня + брокер + прочее] --> E{Способ}
    E -- по стоимости --> E1[доля = qty×закупка / Σ]
    E -- по штукам --> E2[доля = qty / Σ qty]
    E -- по весу --> E3[доля = вес мешка × qty / штук в мешке / Σ]
    E1 & E2 & E3 --> F[доля затрат / qty]
    C --> G[Себестоимость за шт]
    F --> G
    G --> H[Средняя по модели в поставке]
    H --> I[× 1 + max наценка категории, мин. наценка]
    I --> J{Цены с НДС?}
    J -- да --> K[× 1 + НДС]
    J -- нет --> L
    K --> L[Округление: вверх до шага − хвост<br/>183 → 189.90]
    L --> M{Цена зафиксирована?}
    M -- да --> N[Не менять]
    M -- нет --> O[products.retail_price]
```

## 5. Печать этикеток

```mermaid
sequenceDiagram
    actor O as Оператор
    participant W as TexFlow (браузер)
    participant S as Flask /labels
    participant G as labels.py
    participant P as printing.py
    participant Z as Zebra / TSC
    O->>W: выбрать поставку, мешок, модель или вариант
    W->>S: POST fmt, action, копии v_<id>
    S->>S: label_rows(): EAN, SKU, цена, состав
    alt ZPL
        S->>G: to_zpl(items, 58×40, 203dpi, шрифт)
    else TSPL
        S->>G: to_tspl(items, ...)
    else PDF A4
        S->>G: to_pdf_sheet(items, 3×8, start_cell)
    else PDF рулон
        S->>G: to_pdf_roll(items, 58×40)
    end
    alt action = view / download
        S-->>W: файл .zpl / .tspl / .pdf
        W-->>O: открыть / печать через драйвер
    else action = print
        S->>P: dispatch(tcp://IP:9100 | cups://очередь | dir://папка)
        P->>Z: сырые байты ZPL/TSPL
        Z-->>P: TCP закрыт
        P-->>S: отправлено N байт
        S->>S: label_jobs (журнал)
        S-->>W: «Печать: N этикеток»
    end
```

## 6. Статусы

```mermaid
stateDiagram-v2
    [*] --> open: поставка создана
    open --> priced: цены записаны
    priced --> priced: повторный пересчёт
    priced --> closed: вручную
    state Мешок {
        [*] --> closed
        closed --> sorting: первая запись приёмки
        sorting --> done: «Мешок разобран»
    }
```
