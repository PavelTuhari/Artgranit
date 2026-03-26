# AGRO: Supplier Pack Adaptation, Acceptance Program & Sales Weighing Module

**Date:** 2026-03-27
**Status:** Approved
**Approach:** Variant A — extend existing modules

---

## 1. Scope

Three interconnected changes to the AGRO module:

1. **Supplier Pack adaptation** — align `dipp_fruct_supplier_pack.html` with internal AGRO scoring system
2. **Acceptance program enhancement** — add defect coding UI + photo capture to `agro_field.html` inspections
3. **Sales weighing module** — add touchscreen weighing/shipment interface to `agro_sales.html`

---

## 2. Supplier Pack Adaptation

### File: `docs/AGRO/achizitie standard/dipp_fruct_supplier_pack.html`

### 2.1 Defect codes → AGRO scoring alignment

Map D-codes to the 17-point scoring engine in `agro_oracle_store.py`:

| Defect Code | Description | Scoring Check(s) | Weight | Severity |
|-------------|------------|-------------------|--------|----------|
| D01 | Гниль / Rot | SERIOUS_OK | 15 | Critical |
| D02 | Плесень / Mould | SERIOUS_OK | 15 | Critical |
| D03 | Живые вредители / Live pests | SERIOUS_OK | 15 | Critical |
| D04 | Посторонний запах / Foreign odour | SERIOUS_OK | 15 | Critical |
| D05 | Несоответствие классу / Class mismatch | CLASS_OK | 10 | Critical |
| D06 | Температура нарушена / Temp breach | TEMP_OK | 10 | Critical |
| D07 | Нет лаб. отчёта / Missing lab report | LAB_OK | 8 | Critical |
| D08 | Нет фитосанитарного серт. / Missing phyto | PHYTO_OK | 4 | Critical |
| D09 | Нет traceability / Missing traceability | TRACE_OK | 6 | Critical |
| D10 | Нажимы / Bruising | MINOR_OK | 8 | Major |
| D11 | Деформация / Deformation | MINOR_OK | 8 | Major |
| D12 | Ниже мин. калибра / Below min calibre | CALIBRE_OK + BELOW_MIN_OK | 8+5 | Major |
| D13 | Смешение размеров / Mixed sizes | MIXED_OK | 4 | Major |
| D14 | Brix ниже нормы / Low Brix | BRIX_OK | 5 | Major |
| D20 | Пов. дефекты кожицы / Skin defects | MINOR_OK | 8 | Minor |
| D21 | Следы листьев/веточек / Leaves/twigs | MINOR_OK | 8 | Minor |
| D22 | Неполная маркировка / Incomplete label | LABEL_OK | 2 | Minor |
| D23 | Нарушение упаковки / Pack damage | PACK_OK | 3 | Minor |
| D24 | Residue single > MRL | SINGLE_RESIDUE_OK | 2 | Minor |
| D25 | Residue total > limit | TOTAL_RESIDUE_OK | 2 | Minor |
| D26 | Glyphosate > MRL | GLYPHOSATE_OK | 1 | Minor |
| D27 | Кол-во акт. веществ > лимит / Active substances | ACTIVES_OK | 2 | Minor |

### 2.2 Decision thresholds

Synchronize with scoring engine formula:
- **ACCEPT**: all critical checks pass AND total score ≥ 95
- **ACCEPT_WITH_SORTING**: all critical checks pass AND score ≥ accept_min_score (default 85)
- **REJECT**: any critical check fails OR score < accept_min_score

### 2.3 Network comparison table

Add note that parameters match `AGRO_ACCEPTANCE_PROFILES` entries (codes: `KAUFLAND`, `METRO`, `LINELLA`).

---

## 3. Acceptance Program Enhancement

### File: `templates/agro_field.html` (inspections section)

### 3.1 Defect coding panel

Add to the batch inspection UI (after the 17-checkbox section):

- Grid of D-code touch buttons, color-coded by severity:
  - Critical (red): D01–D09
  - Major (orange): D10–D14
  - Minor (yellow): D20–D27
- Tapping a D-code = defect found → auto-unchecks corresponding scoring checkbox
- D-code buttons show toggle state (pressed = defect present)

### 3.2 Photo capture cells

- Grid of photo cells below D-code panel (reuse `.photo-cell` pattern from supplier pack)
- Each cell tied to a D-code
- Tap cell → open device camera → capture photo
- Photo stored in `AGRO_ATTACHMENTS` linked to batch inspection
- No new Oracle tables needed

### 3.3 Live score display

- Progress bar showing current score (0–100), color transitions:
  - Green (≥95): ACCEPT zone
  - Yellow (85–94): SORT zone
  - Red (<85): REJECT zone
- Numeric score value
- Decision badge (ACCEPT / ACCEPT_WITH_SORTING / REJECT) updates in real-time
- All calculation client-side (mirrors `_SCORING_WEIGHTS` from store)

### 3.4 Backend changes

Minimal. Existing API endpoints and scoring engine are sufficient:
- `POST /api/agro-field/inspections` — already accepts check values
- `perform_batch_inspection()` in store — already computes weighted score
- `AGRO_BATCH_INSPECTIONS` + `AGRO_BATCH_INSPECTION_VALUES` — already store results
- `AGRO_ATTACHMENTS` — already exists for file storage

**Required DDL change:** `ALTER TABLE AGRO_ATTACHMENTS` to add `'batch_inspection'` to the `CK_AGRO_ATT_ETYPE` CHECK constraint (currently allows: `'purchase','sale','batch','qa_check'`).

### 3.5 Client-side scoring weights

Scoring weights are served via `GET /api/agro-field/scoring-config` (new endpoint) to maintain a single source of truth. Returns `_SCORING_WEIGHTS` and `_CRITICAL_CHECKS` from store. Avoids hardcoding in JS.

### 3.6 Notes

- D-code numbering gap D15–D19 is intentional — reserved for future Major-category codes
- D12 maps to two scoring checks simultaneously (`CALIBRE_OK` + `BELOW_MIN_OK`); tapping D12 toggles both

---

## 4. Sales Weighing Module

### File: `templates/agro_sales.html`

### 4.1 New sidebar sections

```
Отгрузки / Livrari
  ├── Документы / Documente      (existing)
  ├── + Новый / Nou              (existing)
  ├── Остатки / Stoc             (existing)
───────────────────
Отгрузка / Expediere             (NEW)
  ├── Взвешивание / Cântărire   (NEW — touchscreen)
  ├── Акты / Acte               (NEW — weight ticket journal)
───────────────────
Экспорт / Export
  ├── Декларации / Declaratii    (existing)
```

### 4.2 Weighing page — touchscreen layout

Reuses UI patterns from `agro_field.html`:

**Top section:**
- Sales document selector (dropdown, loads draft/confirmed docs)
- Customer + warehouse info display

**Scanner section:**
- Barcode input field + manual entry (reuse `barcode-scanner.js`)
- Scan resolves crate → batch → item

**Scale section:**
- Three `weight-box` blocks: Gross / Tare / Net (font-size: 28px)
- `btn-weigh` button → calls `/api/agro-scale/read` for auto-capture
- Tare auto-filled from `AGRO_PACKAGING_TYPES`

**Lines grid:**
- Each scanned crate appears as a row
- Columns: #, Barcode, Item, Gross, Tare, Net, ⚖️ button, ✕ remove
- Running total at bottom

**Action buttons (btn-lg, 60px height):**
- «Сформировать акт / Generează act» — creates weight ticket
- «Печать / Tipărește» — prints weight ticket (A4)

### 4.3 Weight ticket journal page

Master-detail layout (same pattern as purchases-list in field):
- **Master**: table of weight tickets (number, date, sales doc, customer, status, total net kg)
- **Detail**: ticket header + lines table + print button
- Filters: date range, status (draft/finalized)

### 4.4 Weight ticket print

Uses existing `agro-document/<id>` route with type `weight_ticket`:
- Header: ticket number, date, operator
- Client + warehouse info
- Lines table: item, crate count, gross, tare, net
- Footer: total net weight, signatures (operator, driver)

### 4.5 New Oracle objects

```sql
-- Sequences (existing AGRO convention)
CREATE SEQUENCE AGRO_WEIGHT_TICKETS_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE AGRO_WEIGHT_TICKET_LINES_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- AGRO_WEIGHT_TICKETS — header
CREATE TABLE AGRO_WEIGHT_TICKETS (
    ID              NUMBER PRIMARY KEY,
    TICKET_NUMBER   VARCHAR2(30) NOT NULL,
    SALES_DOC_ID    NUMBER REFERENCES AGRO_SALES_DOCS(ID),
    CUSTOMER_ID     NUMBER REFERENCES AGRO_CUSTOMERS(ID),
    WAREHOUSE_ID    NUMBER REFERENCES AGRO_WAREHOUSES(ID),
    TICKET_DATE     DATE DEFAULT SYSDATE,
    STATUS          VARCHAR2(20) DEFAULT 'draft',   -- draft / finalized
    OPERATOR        VARCHAR2(100),
    NOTES           VARCHAR2(500),
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    UPDATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP
);

-- AGRO_WEIGHT_TICKET_LINES — line items
CREATE TABLE AGRO_WEIGHT_TICKET_LINES (
    ID              NUMBER PRIMARY KEY,
    TICKET_ID       NUMBER NOT NULL REFERENCES AGRO_WEIGHT_TICKETS(ID),
    LINE_NO         NUMBER,
    BATCH_ID        NUMBER REFERENCES AGRO_BATCHES(ID),
    CRATE_CODE      VARCHAR2(50),
    ITEM_ID         NUMBER REFERENCES AGRO_ITEMS(ID),
    GROSS_KG        NUMBER(12,3),
    TARE_KG         NUMBER(12,3),
    NET_KG          NUMBER(12,3),
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP
);

-- Auto-ID triggers (existing AGRO convention)
CREATE OR REPLACE TRIGGER AGRO_WEIGHT_TICKETS_BI
  BEFORE INSERT ON AGRO_WEIGHT_TICKETS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN :NEW.ID := AGRO_WEIGHT_TICKETS_SEQ.NEXTVAL; END;
/

CREATE OR REPLACE TRIGGER AGRO_WEIGHT_TICKET_LINES_BI
  BEFORE INSERT ON AGRO_WEIGHT_TICKET_LINES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN :NEW.ID := AGRO_WEIGHT_TICKET_LINES_SEQ.NEXTVAL; END;
/

-- Indexes on FK columns (existing AGRO convention)
CREATE INDEX IX_AGRO_WT_SALESDOC ON AGRO_WEIGHT_TICKETS(SALES_DOC_ID);
CREATE INDEX IX_AGRO_WT_CUSTOMER ON AGRO_WEIGHT_TICKETS(CUSTOMER_ID);
CREATE INDEX IX_AGRO_WT_WAREHOUSE ON AGRO_WEIGHT_TICKETS(WAREHOUSE_ID);
CREATE INDEX IX_AGRO_WTL_TICKET ON AGRO_WEIGHT_TICKET_LINES(TICKET_ID);
CREATE INDEX IX_AGRO_WTL_BATCH ON AGRO_WEIGHT_TICKET_LINES(BATCH_ID);
CREATE INDEX IX_AGRO_WTL_ITEM ON AGRO_WEIGHT_TICKET_LINES(ITEM_ID);

-- ALTER AGRO_ATTACHMENTS to allow batch_inspection entity type
ALTER TABLE AGRO_ATTACHMENTS DROP CONSTRAINT CK_AGRO_ATT_ETYPE;
ALTER TABLE AGRO_ATTACHMENTS ADD CONSTRAINT CK_AGRO_ATT_ETYPE
  CHECK (ENTITY_TYPE IN ('purchase','sale','batch','qa_check','batch_inspection'));
```

**Notes:**
- `CUSTOMER_ID` is a direct column for flexibility (operator can start weighing before sales doc exists)
- `TICKET_DATE` (DATE) is separate from `CREATED_AT` (TIMESTAMP) for business document filtering
- `SALES_DOC_ID` is nullable — ticket can be created first, linked to sales doc later

### 4.6 New API endpoints

```
POST   /api/agro-sales/weight-tickets              — create ticket
GET    /api/agro-sales/weight-tickets               — list tickets (with filters)
GET    /api/agro-sales/weight-tickets/<id>           — get ticket + lines
PUT    /api/agro-sales/weight-tickets/<id>           — update ticket header (notes, operator, sales_doc_id)
POST   /api/agro-sales/weight-tickets/<id>/lines     — add line (barcode, gross_kg)
DELETE /api/agro-sales/weight-tickets/<id>/lines/<lid> — remove line
POST   /api/agro-sales/weight-tickets/<id>/finalize  — finalize ticket
GET    /api/agro-field/scoring-config                — get scoring weights + critical checks (new)
```

### 4.7 Controller additions

Extend `AgroSalesController` with:
- `create_weight_ticket(data)` — customer_id, warehouse_id, optional sales_doc_id
- `update_weight_ticket(ticket_id, data)` — notes, operator, sales_doc_id
- `add_weight_line(ticket_id, barcode, gross_kg)`
- `remove_weight_line(ticket_id, line_id)`
- `finalize_weight_ticket(ticket_id)`
- `get_weight_tickets(filters)`
- `get_weight_ticket_by_id(ticket_id)`

### 4.8 Store additions

Extend `AgroStore` with corresponding Oracle operations. Finalization should:
1. Sum net weights per item
2. Validate against sales doc line quantities (if sales_doc_id linked)
3. Update ticket status to 'finalized'
4. If sales_doc_id linked, optionally update sales doc status to 'shipped'
5. Log event to `AGRO_EVENT_LOG`

---

## 5. CSS Strategy

Each template is self-contained. Copy touchscreen styles from `agro_field.html` into `agro_sales.html`:
- `input-weight` (36px font, centered)
- `weight-box`, `weight-display` (gross/tare/net blocks)
- `btn-weigh` (48px scale button with animation)
- `btn-lg` (60px touch buttons)
- `pkg-selector` (packaging type selector)

---

## 6. Files changed

| File | Change |
|------|--------|
| `docs/AGRO/achizitie standard/dipp_fruct_supplier_pack.html` | Rewrite defect table, sync thresholds, add scoring references |
| `templates/agro_field.html` | Add D-code panel, photo cells, live score to inspections |
| `templates/agro_sales.html` | Add weighing page, weight ticket journal, touchscreen styles |
| `controllers/agro_sales_controller.py` | Add weight ticket methods |
| `models/agro_oracle_store.py` | Add weight ticket CRUD + finalization logic |
| `app.py` | Add 6 weight ticket API routes |
| `sql/41_agro_weight_tickets.sql` | DDL for 2 new tables + sequences + triggers |
| `deploy_oracle_objects.py` | Register new SQL file |

---

## 7. What does NOT change

- `agro_oracle_store.py` scoring engine (already correct)
- Existing sales document workflow
- Existing field purchase/barcode/crate workflows
- Oracle schema for existing tables
- Other templates (admin, warehouse, qa)
