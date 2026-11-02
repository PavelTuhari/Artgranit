# TexFlow — flowcharts (Mermaid)

[Русский](ARCHITECTURE.md) · [Română](ARCHITECTURE.ro.md) · **English**

The diagrams render directly on GitHub, in VS Code with Mermaid support and at
https://mermaid.live. The first one is also built into the app's “Help” page
(in the interface language).

## 1. From bag to shelf

```mermaid
flowchart TD
    A([Shipment arrived:<br/>bags from Turkey / China,<br/>everything mixed]) --> B[Create shipment<br/>currency, rate, freight,<br/>customs, broker, other]
    B --> C[/Rough packing list CSV<br/>bag · category · description · qty · price · weight/]
    C --> D[Import: list lines +<br/>bags created automatically]
    D --> E{Take a bag}
    E --> F[Open the bag<br/>status: sorting]
    F --> G{Item already<br/>in the system?}
    G -- yes, has EAN/SKU --> H[Scanner: +1 pc]
    G -- no --> I[New model:<br/>name, category,<br/>purchase price from list]
    I --> J[Pick colours by group<br/>White / Black / Beige...]
    J --> K[Colour × size matrix<br/>enter pieces]
    K --> L[(intake_items<br/>+ SKU/EAN variants)]
    H --> L
    L --> M{Bag empty?}
    M -- no --> G
    M -- yes --> N[Bag done<br/>status: done]
    N --> O{All bags?}
    O -- no --> E
    O -- yes --> P[Reconcile with list<br/>by category and bag]
    P --> Q{Differences?}
    Q -- shortage / surplus --> R[Claim to supplier<br/>or correction −N]
    R --> S
    Q -- no --> S[Landed cost calculation]
    S --> T[Prices from markups<br/>charm rounding]
    T --> U[Product cards<br/>and catalogue, CSV export]
    T --> V{Label printing}
    V --> W1[ZPL → Zebra]
    V --> W2[TSPL → TSC]
    V --> W3[PDF A4 → office printer]
    V --> W4[PDF roll → virtual printer]
    W1 & W2 & W3 & W4 --> X([Item on the hanger<br/>with barcode and price])
```

## 2. The “Sort bag” screen

```mermaid
flowchart LR
    subgraph Input
      S1[Scanner EAN/SKU]
      S2[Model search]
      S3[New model]
    end
    S1 -- found --> J[(+1 pc to log)]
    S1 -- not found --> E[Error: create the model]
    S2 --> M[Model matrix]
    S3 --> M
    M -- click a colour --> R[Add colour row]
    R --> M
    M -- Enter / arrows --> M
    M -- Ctrl+Enter --> V{Variant exists?}
    V -- no --> NV[Create variant:<br/>SKU = STYLE-COLOUR-SIZE<br/>EAN-13 = 200 + no + check]
    NV --> J2[(intake_items)]
    V -- yes --> J2
    J2 -- “Save and print” --> L[Labels only<br/>for this batch]
```

## 3. Data model (ER)

```mermaid
erDiagram
    SUPPLIERS ||--o{ SHIPMENTS : "supplies"
    SUPPLIERS ||--o{ PRODUCTS : "makes"
    SHIPMENTS ||--o{ BAGS : "consists of"
    SHIPMENTS ||--o{ PACKING_LINES : "rough list"
    SHIPMENTS ||--o{ INTAKE_ITEMS : "actual intake"
    BAGS ||--o{ INTAKE_ITEMS : "taken from"
    CATEGORIES ||--o{ PRODUCTS : "markup, duty"
    CATEGORIES ||--o{ PACKING_LINES : ""
    SIZE_SCALES ||--o{ SIZES : ""
    SIZE_SCALES ||--o{ CATEGORIES : "default scale"
    COLOR_FAMILIES ||--o{ COLORS : "group"
    PRODUCTS ||--o{ VARIANTS : "colour × size"
    COLORS ||--o{ VARIANTS : ""
    SIZES ||--o{ VARIANTS : ""
    VARIANTS ||--o{ INTAKE_ITEMS : "pieces"

    COLORS {
        int id PK
        text code UK
        text name "RU"
        text name_ro "RO"
        text name_en "EN"
        text hex
    }
    SHIPMENTS {
        int id PK
        text code UK
        text currency
        real fx_rate
        real freight
        real customs
        text alloc_method "value|qty|weight"
        text status "open|sorted|priced|closed"
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
```

The `categories`, `color_families` and `size_scales` tables also have
`name_ro` and `name_en`.

## 4. Landed cost and price

```mermaid
flowchart TD
    A[Intake line:<br/>qty, purchase in currency] --> B[× shipment rate]
    B --> C[+ category duty %]
    D[Freight + customs + broker + other] --> E{Method}
    E -- by value --> E1[share = qty×purchase / Σ]
    E -- per piece --> E2[share = qty / Σ qty]
    E -- by weight --> E3[share = bag weight × qty / pcs in bag / Σ]
    E1 & E2 & E3 --> F[cost share / qty]
    C --> G[Landed cost per pc]
    F --> G
    G --> H[Average per model in the shipment]
    H --> I[× 1 + max category markup, min markup]
    I --> J{Prices incl. VAT?}
    J -- yes --> K[× 1 + VAT]
    J -- no --> L
    K --> L[Rounding: up to step − ending<br/>183 → 189.90]
    L --> M{Price locked?}
    M -- yes --> N[Leave unchanged]
    M -- no --> O[products.retail_price]
```

## 5. Label printing

```mermaid
sequenceDiagram
    actor O as Operator
    participant W as TexFlow (browser)
    participant S as Flask /labels
    participant G as labels.py
    participant P as printing.py
    participant Z as Zebra / TSC
    O->>W: choose shipment, bag, model or variant
    W->>S: POST fmt, action, copies v_<id>
    S->>S: label_rows(): EAN, SKU, price, colour in label language
    alt ZPL
        S->>G: to_zpl(items, 58×40, 203dpi, font)
    else TSPL
        S->>G: to_tspl(items, ...)
    else PDF A4
        S->>G: to_pdf_sheet(items, 3×8, start_cell)
    else PDF roll
        S->>G: to_pdf_roll(items, 58×40)
    end
    alt action = view / download
        S-->>W: .zpl / .tspl / .pdf file
        W-->>O: open / print via driver
    else action = print
        S->>P: dispatch(tcp://IP:9100 | cups://queue | dir://folder)
        P->>Z: raw ZPL/TSPL bytes
        Z-->>P: TCP closed
        P-->>S: sent N bytes
        S->>S: label_jobs (log)
        S-->>W: “Print: N labels”
    end
```

## 6. Language selection

```mermaid
flowchart LR
    A[Request] --> B{?lang=ro/en/ru}
    B -- yes --> C[stored in session]
    B -- no --> D{language in session?}
    C --> E[i18n.set_lang]
    D -- yes --> E
    D -- no --> F[Settings: ui_lang] --> E
    E --> G[Templates: _'text']
    E --> H[SQL: COALESCE name_en, name]
    I[Settings: label_lang] --> J[Colour on label]
```
