# AGRO Module Design Spec

**Module:** Dipp AGRO (prefix `AGRO_`)
**Date:** 2026-03-12
**Status:** Draft
**Source TZ:** `/Users/pt/Projects.AI/Dipp AGRO/Dipp.md`
**Standards:** SKP121 — Принципы переработки фруктов и овощей

## 1. Purpose

Operational and management accounting system for purchase, storage, processing, and sale of fruits/vegetables with quality control and full batch traceability per GMP/HACCP principles. Integrated as a module within the Artgranit platform.

## 2. Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Full MVP (Sprint 0-4) | All roles, QA/HACCP, reports |
| Oracle prefix | `AGRO_` | Short, clear, consistent with DECOR_/CRED_/NUF_ |
| UI interfaces | 5 (admin, field, warehouse, qa, sales) | Max role separation per user request |
| Barcodes | Hybrid (internal + external) | System generates internal codes, also accepts supplier codes |
| Offline | Service Worker + IndexedDB for field operator | Unstable connectivity in the field |
| Currencies | Multi (MDL, EUR, USD) with rate history | International trade requirements |
| Print forms | 9+ documents | Full operational set + QA/HACCP printables |
| Temperature monitoring | Manual now, IoT-ready model | SENSOR_ID + READING_SOURCE prepared for future sensors |
| Languages | RU + RO simultaneously | Business terms in Romanian, UI bilingual. EN deferred to Phase 2 |
| Architecture | Domain sub-controllers + single store | Balance of manageability and Artgranit conventions |

## 3. Architecture

### 3.1 Code Structure

```
controllers/
  agro_admin_controller.py      # References, settings, HACCP plans, reports
  agro_field_controller.py      # Field operator: purchases, barcodes, crates
  agro_warehouse_controller.py  # Warehouse: storage, movements, temperature, tasks
  agro_qa_controller.py         # QA: checklists, checks, HACCP, batch blocks
  agro_sales_controller.py      # Sales: shipments, export, invoices

models/
  agro_oracle_store.py          # Single Oracle store (~60 KB), all AGRO_* tables
                                  # Note: may split into sub-modules during implementation
                                  # if file exceeds maintainability threshold

sql/
  30_agro_tables.sql            # 36 tables + sequences
  31_agro_views.sql             # Views for reports and stock balances
  32_agro_triggers.sql          # Auto-ID triggers + audit triggers

templates/
  agro_admin.html               # Admin: references, settings, KPI dashboard
  agro_field.html               # Field: tablet-first, offline, scanner
  agro_warehouse.html           # Warehouse: stock, movements, temperature
  agro_qa.html                  # QA: checklists, HACCP monitoring
  agro_sales.html               # Sales: shipments, invoices, export
  agro/
    document_purchase_act.html      # Purchase acceptance act
    document_weighing_act.html      # Weighing act
    document_transfer_note.html     # Transfer note
    document_invoice.html           # Invoice
    document_export_decl.html       # Export declaration
    document_qa_protocol.html       # QA inspection protocol
    document_gmp_checklist.html     # GMP checklist printable
    document_haccp_report.html      # HACCP deviations report
    document_mass_balance.html      # Mass balance report

static/agro/
  offline-worker.js             # Service Worker for offline mode
  offline-db.js                 # IndexedDB wrapper for cache
  barcode-scanner.js            # Camera scanning (QuaggaJS/ZXing)
  barcode-generator.js          # Barcode generation for printing

dashboards/
  dashboard_agro.json           # Widgets: stock, temperature, KPI
```

### 3.2 Integration Points with Artgranit

- **app.py**: Add AGRO routes (UI + API) following existing pattern
- **deploy_oracle_objects.py**: Add files 30-32 to execution order
- **config.py**: No changes needed (uses existing Oracle connection)
- **models/database.py**: No changes (reuse DatabaseModel context manager)
- **Flask-Babel**: Add AGRO strings to translations (RU + RO)

## 4. Data Model

### 4.1 Master Data (11 tables)

**AGRO_SUPPLIERS**
- ID, CODE, NAME, COUNTRY, TAX_ID, CONTACT_PHONE, CONTACT_EMAIL, ADDRESS, ACTIVE, CREATED_AT

**AGRO_CUSTOMERS**
- ID, CODE, NAME, COUNTRY, TAX_ID, CONTACT_PHONE, CONTACT_EMAIL, ADDRESS, CUSTOMER_TYPE (domestic|export), ACTIVE, CREATED_AT

**AGRO_WAREHOUSES**
- ID, CODE, NAME, WAREHOUSE_TYPE (cold_storage|dry|processing), ADDRESS, CAPACITY_KG, ACTIVE

**AGRO_STORAGE_CELLS**
- ID, WAREHOUSE_ID → AGRO_WAREHOUSES, CODE, NAME, CELL_TYPE (chamber|section|zone), TEMP_MIN, TEMP_MAX, HUMIDITY_MIN, HUMIDITY_MAX, CAPACITY_KG, ACTIVE

**AGRO_ITEMS**
- ID, CODE, NAME_RU, NAME_RO, ITEM_GROUP (fruit|vegetable|berry), UNIT (kg), DEFAULT_TARE_KG, SHELF_LIFE_DAYS, OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX, ACTIVE

**AGRO_PACKAGING_TYPES**
- ID, CODE, NAME_RU, NAME_RO, TARE_WEIGHT_KG, CAPACITY_KG, ACTIVE

**AGRO_VEHICLES**
- ID, PLATE_NUMBER, VEHICLE_TYPE (truck|van|refrigerator), DRIVER_NAME, ACTIVE

**AGRO_CURRENCIES**
- ID, CODE (MDL|EUR|USD), NAME, SYMBOL, ACTIVE

**AGRO_EXCHANGE_RATES**
- ID, FROM_CURRENCY, TO_CURRENCY, RATE, RATE_DATE, SOURCE

**AGRO_FORMULA_PARAMS** (typed settings for Q-Net/Suma calculation formulas)
- ID, ITEM_ID → AGRO_ITEMS (nullable, NULL = global default), PARAM_NAME (tare_coefficient|rounding_mode|rounding_precision), PARAM_VALUE, ACTIVE

**AGRO_MODULE_CONFIG** (module-level configuration, not primary business state — distinct from CLAUDE.md-prohibited generic KV)
- ID, CONFIG_KEY, CONFIG_VALUE, CONFIG_GROUP, DESCRIPTION

### 4.2 Barcodes & Crates (3 tables)

> Note: Master data totals 11 tables (AGRO_FORMULA_PARAMS + AGRO_MODULE_CONFIG replace the single AGRO_SETTINGS to comply with CLAUDE.md no-generic-KV rule).

**AGRO_BARCODES**
- ID, BARCODE, BARCODE_TYPE (internal|external|ean13|qr), GENERATED_AT, PRINTED, ASSIGNED, BATCH_ID
- Pool of barcodes: generated in batches, printed as labels, assigned to crates

**AGRO_CRATES**
- ID, BARCODE_ID → AGRO_BARCODES, EXTERNAL_BARCODE, PACKAGING_TYPE_ID → AGRO_PACKAGING_TYPES, GROSS_WEIGHT_KG, TARE_WEIGHT_KG, NET_WEIGHT_KG, STATUS (empty|filled|weighed|accepted|stored|shipped), CREATED_AT

**AGRO_BATCH_CRATES**
- ID, BATCH_ID → AGRO_BATCHES, CRATE_ID → AGRO_CRATES

### 4.3 Purchases (3 tables)

**AGRO_PURCHASE_DOCS**
- ID, DOC_NUMBER, DOC_DATE, SUPPLIER_ID → AGRO_SUPPLIERS, WAREHOUSE_ID → AGRO_WAREHOUSES, VEHICLE_ID → AGRO_VEHICLES, CURRENCY_ID, STATUS (draft|confirmed|closed|cancelled), TOTAL_GROSS_KG, TOTAL_NET_KG, TOTAL_AMOUNT, ADVANCE_AMOUNT, TRANSFER_AMOUNT, E_FACTURA_REF, ADDITIONAL_COSTS, NOTES, CREATED_BY, CREATED_AT, CONFIRMED_AT

**AGRO_PURCHASE_LINES**
- ID, PURCHASE_DOC_ID → AGRO_PURCHASE_DOCS, ITEM_ID → AGRO_ITEMS, PALLETS, CRATES_COUNT, GROSS_WEIGHT_KG, TARE_WEIGHT_KG, NET_WEIGHT_KG, PRICE_PER_KG, AMOUNT, NOTES

**AGRO_BATCHES** (central traceability entity)
- ID, BATCH_NUMBER (auto), PURCHASE_LINE_ID → AGRO_PURCHASE_LINES, ITEM_ID, WAREHOUSE_ID, CELL_ID, INITIAL_QTY_KG, CURRENT_QTY_KG, STATUS (active|blocked|depleted|expired), RECEIVED_AT, EXPIRY_DATE, BLOCKED_BY, BLOCK_REASON, NOTES

### 4.4 Warehouse & Storage (4 tables)

**AGRO_STOCK_MOVEMENTS**
- ID, BATCH_ID → AGRO_BATCHES, MOVEMENT_TYPE (receipt|transfer|processing|shipment|adjustment|loss), FROM_WAREHOUSE_ID, FROM_CELL_ID, TO_WAREHOUSE_ID, TO_CELL_ID, QTY_KG, REASON, DOC_REF, CREATED_BY, CREATED_AT

**AGRO_STORAGE_READINGS**
- ID, CELL_ID → AGRO_STORAGE_CELLS, TEMPERATURE_C, HUMIDITY_PCT, O2_PCT, CO2_PCT, READING_SOURCE (manual|sensor), SENSOR_ID, RECORDED_BY, RECORDED_AT
- IoT-ready: SENSOR_ID + READING_SOURCE for automated sensors

**AGRO_STORAGE_ALERTS**
- ID, CELL_ID, READING_ID → AGRO_STORAGE_READINGS, ALERT_TYPE (temp_high|temp_low|humidity|o2|co2), THRESHOLD_VALUE, ACTUAL_VALUE, ACKNOWLEDGED, ACKNOWLEDGED_BY, ACKNOWLEDGED_AT, CREATED_AT

**AGRO_PROCESSING_TASKS**
- ID, BATCH_ID → AGRO_BATCHES, TASK_TYPE (sorting|washing|packing|labeling|other), DESCRIPTION, ASSIGNED_TO, STATUS (pending|in_progress|completed|cancelled), INPUT_QTY_KG, OUTPUT_QTY_KG, WASTE_QTY_KG, STARTED_AT, COMPLETED_AT, NOTES

### 4.5 Quality & HACCP (8 tables)

**AGRO_QA_CHECKLISTS**
- ID, CODE, NAME_RU, NAME_RO, CHECKLIST_TYPE (incoming|gmp|sanitary|packaging), ACTIVE

**AGRO_QA_CHECKLIST_ITEMS**
- ID, CHECKLIST_ID → AGRO_QA_CHECKLISTS, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO, VALUE_TYPE (boolean|numeric|text|choice), MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL

**AGRO_QA_CHECKS**
- ID, BATCH_ID → AGRO_BATCHES, CHECKLIST_ID → AGRO_QA_CHECKLISTS, CHECK_DATE, RESULT (pass|fail|conditional), INSPECTOR, NOTES, CREATED_AT

**AGRO_QA_CHECK_VALUES**
- ID, CHECK_ID → AGRO_QA_CHECKS, CHECKLIST_ITEM_ID → AGRO_QA_CHECKLIST_ITEMS, VALUE, IS_COMPLIANT

**AGRO_BATCH_BLOCKS**
- ID, BATCH_ID → AGRO_BATCHES, REASON, BLOCKED_BY, BLOCKED_AT, UNBLOCKED_BY, UNBLOCKED_AT, RESOLUTION_NOTES

**AGRO_HACCP_PLANS**
- ID, CODE, NAME_RU, NAME_RO, PROCESS_STAGE, ACTIVE

**AGRO_HACCP_CCPS**
- ID, PLAN_ID → AGRO_HACCP_PLANS, CCP_NUMBER, HAZARD_TYPE (biological|chemical|physical), HAZARD_DESCRIPTION, CRITICAL_LIMIT_MIN, CRITICAL_LIMIT_MAX, MONITORING_FREQUENCY, CORRECTIVE_ACTION

**AGRO_HACCP_RECORDS**
- ID, CCP_ID → AGRO_HACCP_CCPS, BATCH_ID → AGRO_BATCHES, MEASURED_VALUE, IS_WITHIN_LIMITS, DEVIATION_NOTES, CORRECTIVE_ACTION_TAKEN, RECORDED_BY, RECORDED_AT

### 4.6 Sales & Export (4 tables)

**AGRO_SALES_DOCS**
- ID, DOC_NUMBER, DOC_DATE, CUSTOMER_ID → AGRO_CUSTOMERS, WAREHOUSE_ID, VEHICLE_ID, SALE_TYPE (domestic|export), CURRENCY_ID, STATUS (draft|confirmed|shipped|closed|cancelled), TOTAL_GROSS_KG, TOTAL_NET_KG, TOTAL_AMOUNT, INVOICE_NUMBER, NOTES, CREATED_BY, CREATED_AT

**AGRO_SALES_LINES**
- ID, SALES_DOC_ID → AGRO_SALES_DOCS, ITEM_ID → AGRO_ITEMS, BATCH_ID → AGRO_BATCHES, PALLETS, CRATES_COUNT, GROSS_WEIGHT_KG, NET_WEIGHT_KG, PRICE_PER_KG, AMOUNT

**AGRO_EXPORT_DECLS**
- ID, SALES_DOC_ID → AGRO_SALES_DOCS, DECL_NUMBER, DECL_DATE, CUSTOMS_WEIGHT_KG, DESTINATION_COUNTRY, CUSTOMS_CODE, STATUS, NOTES

**AGRO_BATCH_ALLOCATIONS**
- ID, SALES_LINE_ID → AGRO_SALES_LINES, BATCH_ID → AGRO_BATCHES, ALLOCATED_QTY_KG, ALLOCATION_METHOD (fifo|manual)

### 4.7 Audit & Attachments (3 tables)

**AGRO_AUDIT_LOG** (append-only, undeletable by users)
- ID, TABLE_NAME, RECORD_ID, ACTION (insert|update|delete), FIELD_NAME, OLD_VALUE, NEW_VALUE, CHANGED_BY, CHANGED_AT

**AGRO_ATTACHMENTS**
- ID, ENTITY_TYPE (purchase|sale|batch|qa_check), ENTITY_ID, FILE_NAME, FILE_TYPE, FILE_SIZE, FILE_DATA (BLOB), UPLOADED_BY, UPLOADED_AT

**AGRO_EVENT_LOG** (module-specific event log, per CLAUDE.md convention)
- ID, EVENT_TYPE, ENTITY_TYPE, ENTITY_ID, PAYLOAD (CLOB/JSON), CREATED_BY, CREATED_AT

### 4.8 Key Relationships

```
AGRO_SUPPLIERS ──┐
AGRO_ITEMS ──────┤
AGRO_WAREHOUSES ─┤──→ AGRO_PURCHASE_DOCS ──→ AGRO_PURCHASE_LINES ──→ AGRO_BATCHES
AGRO_VEHICLES ───┘         │                                              │
AGRO_PACKAGING_TYPES ──────┘                                              │
                                                                          ├──→ AGRO_STOCK_MOVEMENTS
AGRO_BARCODES ──→ AGRO_CRATES ──→ AGRO_BATCH_CRATES                      │
                                                                          ├──→ AGRO_QA_CHECKS
AGRO_STORAGE_CELLS ──→ AGRO_STORAGE_READINGS                              │
                                                                          ├──→ AGRO_BATCH_BLOCKS
AGRO_HACCP_PLANS ──→ AGRO_HACCP_CCPS ──→ AGRO_HACCP_RECORDS              │
                                                                          │
AGRO_CUSTOMERS ──→ AGRO_SALES_DOCS ──→ AGRO_SALES_LINES ─────────────────┘
                        │                     │
                        └──→ AGRO_EXPORT_DECLS └──→ AGRO_BATCH_ALLOCATIONS
```

**Total: 36 tables + sequences + triggers + indexes**
(11 master data + 3 barcodes/crates + 3 purchases + 4 warehouse + 8 QA/HACCP + 4 sales + 3 audit)

## 5. UI Routes

### 5.1 Pages

| Route | Template | Role |
|---|---|---|
| `/UNA.md/orasldev/agro-admin` | agro_admin.html | Administrator |
| `/UNA.md/orasldev/agro-field` | agro_field.html | Field operator |
| `/UNA.md/orasldev/agro-warehouse` | agro_warehouse.html | Warehouse operator |
| `/UNA.md/orasldev/agro-qa` | agro_qa.html | QA / Technologist |
| `/UNA.md/orasldev/agro-sales` | agro_sales.html | Sales / Export manager |

### 5.2 Document Routes

| Route | Document |
|---|---|
| `/UNA.md/orasldev/agro-field/document/<id>` | Purchase act, weighing act |
| `/UNA.md/orasldev/agro-warehouse/document/<id>` | Transfer note |
| `/UNA.md/orasldev/agro-sales/document/<id>` | Invoice, export declaration |
| `/UNA.md/orasldev/agro-qa/document/<id>` | QA protocol, GMP checklist, HACCP report |

## 6. API Routes (~55 endpoints)

### 6.1 Admin (`/api/agro-admin/`)

- `GET/POST` suppliers, customers, warehouses, items, packaging-types, vehicles
- `DELETE` suppliers/<id>, customers/<id>, etc.
- `GET/POST` settings, exchange-rates
- `GET` reports/<type> (purchases, sales, mass-balance, losses, finance)
- `GET` reports/export/<type> (xlsx/csv/pdf)

### 6.2 Field (`/api/agro-field/`)

- `GET` barcodes/generate — generate barcode pool
- `GET` barcodes/print-batch — printable barcode sheet
- `POST` crates/scan — scan crate by barcode
- `POST` crates/weigh — record crate weight
- `GET/POST` purchases — list/create purchase documents
- `PUT` purchases/<id>/confirm — confirm purchase
- `POST` sync — sync offline queue
- `GET` sync/references — download reference data for offline

### 6.3 Warehouse (`/api/agro-warehouse/`)

- `GET` stock — balances by warehouse/cell/batch
- `GET` batches, batches/<id>/history
- `POST` movements — create transfer
- `GET/POST` readings — temperature/humidity records
- `GET` alerts, `PUT` alerts/<id>/ack
- `GET/POST` tasks, `PUT` tasks/<id>/status
- `POST` receive — receive crates at warehouse

### 6.4 QA (`/api/agro-qa/`)

- `GET/POST` checklists — templates
- `GET/POST` checks — perform inspections
- `POST` batches/<id>/block, batches/<id>/unblock
- `GET/POST` haccp/plans
- `POST` haccp/records — record CCP measurement
- `GET` haccp/deviations — deviations and CAPA

### 6.5 Sales (`/api/agro-sales/`)

- `GET/POST` documents — shipment documents
- `PUT` documents/<id>/confirm
- `POST` allocate — distribute batches (FIFO/manual)
- `GET` available-stock
- `POST` export-decl
- `GET` calculate — calculate amounts

## 7. Offline Architecture

### 7.1 Components

- **Service Worker** (`static/agro/offline-worker.js`): Cache HTML/JS/CSS, intercept API calls, queue failed POSTs, retry on reconnect
- **IndexedDB** (`static/agro/offline-db.js`): Stores — references, purchases, crates, sync_queue
- **Sync endpoint** (`/api/agro-field/sync`): Accepts batch of queued operations, deduplicates by `client_uuid`, returns `{synced, conflicts}`

### 7.2 Sync Flow

1. Online: `GET /sync/references` downloads all reference data to IndexedDB
2. Offline: UI served from Service Worker cache; new records saved to `sync_queue` with `client_uuid`
3. Reconnect: `online` event triggers `POST /sync` with full queue
4. Server deduplicates by `client_uuid` (idempotent), applies to Oracle, returns results
5. UI shows: synced count + conflict list (e.g., barcode already used by another operator)

### 7.3 Conflict Resolution

- Barcode already assigned → return conflict, operator re-scans or uses different barcode
- Purchase doc number collision → server assigns next available number
- Weight discrepancy → flag for warehouse operator review

## 8. Business Rules

1. Cannot confirm purchase without mandatory fields: Data, Furnizor, Depozitare, Marfa, Q-Brut
2. `Q-Net = Q-Brut - (Crates × Tare)` — formula configurable via AGRO_FORMULA_PARAMS
3. `Suma = Q-Net × Price` — with configurable rounding
4. Cannot ship batch with status `blocked` (QA block)
5. Cannot ship more than `current_qty_kg` available
6. FIFO allocation by default (oldest batches first), manual override available
7. All mass/amount corrections logged to AGRO_AUDIT_LOG
8. Temperature alerts created when readings exceed AGRO_STORAGE_CELLS.TEMP_MIN/MAX
9. HACCP deviation requires mandatory corrective action before record can be closed
10. Blocked batch requires explicit unblock by authorized person with resolution notes

## 9. Data Flows

### 9.1 Purchase → Batch → Warehouse

Field: scan crate → assign supplier/item → weigh → create purchase doc
Warehouse: receive crates → verify weight → confirm → create AGRO_BATCHES → place in cell
Oracle: AGRO_CRATES, AGRO_PURCHASE_DOCS/LINES, AGRO_BATCHES, AGRO_STOCK_MOVEMENTS (receipt)

### 9.2 QA Control

Inspector selects batch → performs checklist → auto-evaluate pass/fail
FAIL on critical parameter → AGRO_BATCH_BLOCKS created → AGRO_BATCHES.STATUS = 'blocked'
Blocked batch unavailable for shipment until explicit unblock

### 9.3 Warehouse → Processing → Shipment

Create processing task → sort/wash/pack → record input/output/waste
Transfer between cells/warehouses → AGRO_STOCK_MOVEMENTS
Shipment: select customer → select batches (FIFO) → verify stock & QA → confirm → generate docs

### 9.4 Traceability

Forward: Batch → where is it now? → STOCK_MOVEMENTS + BATCH_ALLOCATIONS → SALES_DOCS
Reverse: Customer complaint → SALES_LINES → BATCH_ALLOCATIONS → BATCHES → PURCHASE_LINES → supplier

## 10. Print Documents (9 forms)

| Document | Template | Generated From |
|---|---|---|
| Purchase acceptance act | document_purchase_act.html | AGRO_PURCHASE_DOCS |
| Weighing act | document_weighing_act.html | AGRO_CRATES aggregate |
| Transfer note | document_transfer_note.html | AGRO_STOCK_MOVEMENTS |
| Invoice | document_invoice.html | AGRO_SALES_DOCS + LINES |
| Export declaration | document_export_decl.html | AGRO_EXPORT_DECLS |
| QA inspection protocol | document_qa_protocol.html | AGRO_QA_CHECKS + VALUES |
| GMP checklist | document_gmp_checklist.html | AGRO_QA_CHECKS (type=gmp) |
| HACCP deviations report | document_haccp_report.html | AGRO_HACCP_RECORDS |
| Mass balance report | document_mass_balance.html | Aggregated view |

## 11. Reports

| Report | Filters | Export |
|---|---|---|
| Purchases by supplier/period/item | Date range, supplier, item | xlsx, csv, pdf |
| Sales by customer/period/item | Date range, customer, item | xlsx, csv, pdf |
| Mass balance (Q-Brut → Q-Net → stock → shipped) | Date range, warehouse, item | xlsx, csv, pdf |
| Financial (purchase/sale amounts, advances, transfers) | Date range | xlsx, csv, pdf |
| Losses by storage/processing | Date range, warehouse | xlsx, csv, pdf |
| Quality (deviations, blocked batches, HACCP compliance) | Date range | xlsx, csv, pdf |

## 12. Non-Functional Requirements

- **Languages:** RU + RO (Flask-Babel), bilingual field names. EN deferred to Phase 2 (explicit decision per REQ-NF-005)
- **Responsiveness:** Adaptive for tablet (min 768px); field UI touch-first with large buttons
- **Performance:** < 2s response for typical operations
- **Offline:** Field operator works without connectivity, syncs when online. Max offline duration: ~8 hours / 500 operations before forced sync recommended
- **Audit:** Append-only AGRO_AUDIT_LOG, not deletable by end users
- **Backup:** Daily Oracle backups (existing Artgranit infrastructure), 30-day retention (REQ-NF-004)
- **RBAC:** Role-based access per interface (admin, field, warehouse, qa, sales)

### 12.1 Notifications (FR-10)

In-app notification system for critical events:
- **Storage alerts:** Temperature/humidity out of range → real-time notification via Socket.io to warehouse UI
- **QA blocks:** Batch blocked → notification to warehouse and sales UIs
- **Missing data:** Draft documents with missing mandatory fields → periodic reminder in relevant UI
- **HACCP deviations:** CCP out of limits → immediate notification to QA UI

Implementation: Socket.io events pushed to connected clients by role. No email/SMS in MVP (deferred to Phase 2 integrations).

### 12.2 Role Mapping (TZ Section 4)

| TZ Role | UI Interface | Notes |
|---|---|---|
| Administrator | agro-admin | Full access to all references, settings, HACCP plans |
| Purchaser (Закупщик) | agro-field | Purchase document creation |
| Warehouse operator | agro-warehouse | Storage, movements, temperature |
| Technologist / QA specialist | agro-qa | Checklists, HACCP, batch blocks |
| Sales / Export manager | agro-sales | Shipments, invoices, export declarations |
| Bookkeeper / Financial controller | agro-admin (reports tab) | Access to financial reports, amount verification, advance/transfer tracking |
| Director / Manager | agro-admin (KPI tab) | Analytics dashboards, aggregated KPI, all reports |

### 12.3 Deferred Items

- EN language support → Phase 2
- Email/SMS notifications → Phase 2
- Historical data import from xlsx → Phase 2 (TZ Section 10)
- Integration with e-factura/customs → Phase 2
- Mobile native app → not in scope

## 13. DDL Deployment

- Files: `sql/35_agro_tables.sql`, `sql/36_agro_views.sql`, `sql/37_agro_triggers.sql`, `sql/38_agro_demo_data.sql`
- Add to `deploy_oracle_objects.py` execution order after existing entries
- Remote deploy: `DEPLOY_ORACLE_ON_REMOTE=1` to include DDL
- Oracle wallet: external path, not in code repo (per CLAUDE.md)

## 14. Technology Stack

- **Backend:** Python/Flask (existing Artgranit stack)
- **Database:** Oracle Autonomous DB via oracledb driver
- **Frontend:** Vanilla JS, AJAX, Socket.io for real-time updates
- **Offline:** Service Worker + IndexedDB
- **Barcode scanning:** QuaggaJS or ZXing-js (camera-based)
- **Barcode generation:** JsBarcode (for printing labels)
- **Templates:** Jinja2
- **i18n:** Flask-Babel (RU + RO)

## 15. Files Created/Modified

### New Files (~28)

| File | Size Est. | Purpose |
|---|---|---|
| controllers/agro_admin_controller.py | ~25 KB | Admin CRUD + reports |
| controllers/agro_field_controller.py | ~20 KB | Field operations + sync |
| controllers/agro_warehouse_controller.py | ~30 KB | Warehouse operations |
| controllers/agro_qa_controller.py | ~25 KB | QA + HACCP |
| controllers/agro_sales_controller.py | ~25 KB | Sales + export |
| models/agro_oracle_store.py | ~60 KB | Oracle persistence layer |
| sql/30_agro_tables.sql | ~15 KB | 36 tables + sequences |
| sql/31_agro_views.sql | ~5 KB | Report views |
| sql/32_agro_triggers.sql | ~8 KB | Auto-ID + audit triggers |
| templates/agro_admin.html | ~50 KB | Admin UI |
| templates/agro_field.html | ~35 KB | Field UI (tablet) |
| templates/agro_warehouse.html | ~45 KB | Warehouse UI |
| templates/agro_qa.html | ~40 KB | QA UI |
| templates/agro_sales.html | ~45 KB | Sales UI |
| templates/agro/document_*.html (9) | ~10 KB ea | Print documents |
| static/agro/offline-worker.js | ~5 KB | Service Worker |
| static/agro/offline-db.js | ~3 KB | IndexedDB wrapper |
| static/agro/barcode-scanner.js | ~4 KB | Camera scanning |
| static/agro/barcode-generator.js | ~3 KB | Label generation |
| dashboards/dashboard_agro.json | ~3 KB | Dashboard widgets |

### Modified Files (2)

| File | Changes |
|---|---|
| app.py | Add AGRO UI routes + API routes (~200 lines) |
| deploy_oracle_objects.py | Add 30-32 to execution order |

## 16. Sprint Mapping (from TZ)

| Sprint | Scope | Tables | Controllers |
|---|---|---|---|
| Sprint 0 | DB design, seed data, base setup | All DDL | Store skeleton |
| Sprint 1 | References + purchases + Q-Net calc | Master data + Purchase + Barcode/Crate | admin + field |
| Sprint 2 | Warehouse + sales + print forms | Warehouse + Sales | warehouse + sales |
| Sprint 3 | QA + HACCP + batch blocks | QA + HACCP | qa |
| Sprint 4 | Reports + offline + stabilization | Views | All (reports + offline-worker) |

## 17. Verification Checklist

Post-deployment verification:

- [ ] All 36 AGRO_* tables visible in USER_OBJECTS
- [ ] Sequences and triggers created
- [ ] All 5 UI pages accessible at /UNA.md/orasldev/agro-*
- [ ] All ~55 API endpoints responding
- [ ] CRUD operations work on all reference tables
- [ ] Purchase document creation with Q-Net/Suma calculation
- [ ] Batch creation from confirmed purchase
- [ ] Stock balance updates after movements
- [ ] QA check with batch blocking on FAIL
- [ ] Blocked batch cannot be shipped
- [ ] Sales document with FIFO batch allocation
- [ ] All 9 print forms render correctly
- [ ] Offline mode: UI loads, data cached, sync works
- [ ] Barcode scanning via camera
- [ ] Temperature alerts generated on threshold breach
- [ ] Audit log records all changes
- [ ] Reports export to xlsx/csv/pdf
- [ ] RU/RO language switching works
- [ ] Dashboard widgets show live data
- [ ] Remote deploy preserves .env and wallet
