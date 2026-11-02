# TexFlow — scheme bloc (Mermaid)

[Русский](ARCHITECTURE.md) · **Română** · [English](ARCHITECTURE.en.md)

Schemele se afișează direct pe GitHub, în VS Code cu suport Mermaid și pe
https://mermaid.live. Prima schemă este inclusă și în pagina „Instrucțiuni” a
aplicației (în limba interfeței).

## 1. Procesul de la sac la raft

```mermaid
flowchart TD
    A([A sosit livrarea:<br/>saci din Turcia / China,<br/>totul amestecat]) --> B[Creează livrarea<br/>valută, curs, transport,<br/>vamă, broker, altele]
    B --> C[/Lista de colete aproximativă CSV<br/>sac · categorie · descriere · cantitate · preț · greutate/]
    C --> D[Import: rândurile listei +<br/>sacii se creează singuri]
    D --> E{Ia un sac}
    E --> F[Deschide sacul<br/>stare: sorting]
    F --> G{Articolul e deja<br/>înregistrat?}
    G -- da, are EAN/SKU --> H[Scaner: +1 buc]
    G -- nu --> I[Model nou:<br/>denumire, categorie,<br/>achiziție din listă]
    I --> J[Alege culorile pe grupe<br/>Alb / Negru / Bej...]
    J --> K[Matrice culoare × mărime<br/>introdu bucățile]
    K --> L[(intake_items<br/>+ variante SKU/EAN)]
    H --> L
    L --> M{Sacul e gol?}
    M -- nu --> G
    M -- da --> N[Sac sortat<br/>stare: done]
    N --> O{Toți sacii?}
    O -- nu --> E
    O -- da --> P[Verificare cu lista<br/>pe categorii și saci]
    P --> Q{Diferențe?}
    Q -- lipsă / surplus --> R[Reclamație la furnizor<br/>sau corecție −N]
    R --> S
    Q -- nu --> S[Calculul costului]
    S --> T[Prețuri după adaosuri<br/>rotunjire frumoasă]
    T --> U[Fișe de produs<br/>și catalog, export CSV]
    T --> V{Tipărirea etichetelor}
    V --> W1[ZPL → Zebra]
    V --> W2[TSPL → TSC]
    V --> W3[PDF A4 → imprimantă obișnuită]
    V --> W4[PDF rolă → imprimantă virtuală]
    W1 & W2 & W3 & W4 --> X([Marfa pe umeraș<br/>cu cod de bare și preț])
```

## 2. Ecranul „Sortarea sacului”

```mermaid
flowchart LR
    subgraph Intrare
      S1[Scaner EAN/SKU]
      S2[Căutare model]
      S3[Model nou]
    end
    S1 -- găsit --> J[(+1 buc în jurnal)]
    S1 -- negăsit --> E[Eroare: creați modelul]
    S2 --> M[Matricea modelului]
    S3 --> M
    M -- click pe culoare --> R[Adaugă rândul culorii]
    R --> M
    M -- Enter / săgeți --> M
    M -- Ctrl+Enter --> V{Varianta există?}
    V -- nu --> NV[Creează varianta:<br/>SKU = ART-CULOARE-MĂRIME<br/>EAN-13 = 200 + nr + control]
    NV --> J2[(intake_items)]
    V -- da --> J2
    J2 -- „Înregistrează și tipărește” --> L[Etichete doar<br/>pentru acest lot]
```

## 3. Modelul de date (ER)

```mermaid
erDiagram
    SUPPLIERS ||--o{ SHIPMENTS : "livrează"
    SUPPLIERS ||--o{ PRODUCTS : "produce"
    SHIPMENTS ||--o{ BAGS : "conține"
    SHIPMENTS ||--o{ PACKING_LINES : "listă aproximativă"
    SHIPMENTS ||--o{ INTAKE_ITEMS : "recepție de fapt"
    BAGS ||--o{ INTAKE_ITEMS : "scos din"
    CATEGORIES ||--o{ PRODUCTS : "adaos, taxă"
    CATEGORIES ||--o{ PACKING_LINES : ""
    SIZE_SCALES ||--o{ SIZES : ""
    SIZE_SCALES ||--o{ CATEGORIES : "grilă implicită"
    COLOR_FAMILIES ||--o{ COLORS : "grupă"
    PRODUCTS ||--o{ VARIANTS : "culoare × mărime"
    COLORS ||--o{ VARIANTS : ""
    SIZES ||--o{ VARIANTS : ""
    VARIANTS ||--o{ INTAKE_ITEMS : "bucăți"

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

Tabelele `categories`, `color_families` și `size_scales` au de asemenea
coloanele `name_ro` și `name_en`.

## 4. Calculul costului și al prețului

```mermaid
flowchart TD
    A[Rând de recepție:<br/>qty, achiziție în valută] --> B[× cursul livrării]
    B --> C[+ taxa vamală a categoriei %]
    D[Transport + vamă + broker + altele] --> E{Metoda}
    E -- după valoare --> E1[cota = qty×achiziție / Σ]
    E -- pe bucăți --> E2[cota = qty / Σ qty]
    E -- după greutate --> E3[cota = greutatea sacului × qty / bucăți în sac / Σ]
    E1 & E2 & E3 --> F[cota cheltuielilor / qty]
    C --> G[Cost pe bucată]
    F --> G
    G --> H[Media pe model în livrare]
    H --> I[× 1 + max adaosul categoriei, adaos minim]
    I --> J{Prețuri cu TVA?}
    J -- da --> K[× 1 + TVA]
    J -- nu --> L
    K --> L[Rotunjire: în sus la pas − terminație<br/>183 → 189.90]
    L --> M{Preț blocat?}
    M -- da --> N[Nu se schimbă]
    M -- nu --> O[products.retail_price]
```

## 5. Tipărirea etichetelor

```mermaid
sequenceDiagram
    actor O as Operator
    participant W as TexFlow (browser)
    participant S as Flask /labels
    participant G as labels.py
    participant P as printing.py
    participant Z as Zebra / TSC
    O->>W: alege livrarea, sacul, modelul sau varianta
    W->>S: POST fmt, action, copii v_<id>
    S->>S: label_rows(): EAN, SKU, preț, culoarea în limba etichetei
    alt ZPL
        S->>G: to_zpl(items, 58×40, 203dpi, font)
    else TSPL
        S->>G: to_tspl(items, ...)
    else PDF A4
        S->>G: to_pdf_sheet(items, 3×8, start_cell)
    else PDF rolă
        S->>G: to_pdf_roll(items, 58×40)
    end
    alt action = view / download
        S-->>W: fișier .zpl / .tspl / .pdf
        W-->>O: deschide / tipărește prin driver
    else action = print
        S->>P: dispatch(tcp://IP:9100 | cups://coadă | dir://dosar)
        P->>Z: octeți ZPL/TSPL bruți
        Z-->>P: TCP închis
        P-->>S: trimis N octeți
        S->>S: label_jobs (jurnal)
        S-->>W: „Tipărire: N etichete”
    end
```

## 6. Alegerea limbii

```mermaid
flowchart LR
    A[Cerere] --> B{?lang=ro/en/ru}
    B -- da --> C[se salvează în sesiune]
    B -- nu --> D{limbă în sesiune?}
    C --> E[i18n.set_lang]
    D -- da --> E
    D -- nu --> F[Setări: ui_lang] --> E
    E --> G[Șabloane: _'text']
    E --> H[SQL: COALESCE name_ro, name]
    I[Setări: label_lang] --> J[Culoarea pe etichetă]
```
