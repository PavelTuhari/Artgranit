# AGRO Module — Agricultural Operations

## Overview

The AGRO module manages the full cycle of agricultural product operations:
field harvest → cold storage → quality control → processing → sales/export.

**Oracle prefix:** `AGRO_`
**Tables:** 42 normalized tables + 7 views + 42 auto-ID triggers + 4 audit triggers

## Architecture

```
┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  5 UI Pages  │──▸│  5 Controllers   │──▸│   AgroStore      │──▸ Oracle DB
│              │   │  (validation)    │   │  (3000+ lines)   │   (AGRO_* tables)
└──────────────┘   └──────────────────┘   └──────────────────┘
```

### Controllers
- `AgroAdminController` — 11 reference tables CRUD + item varieties + acceptance profiles
- `AgroFieldController` — barcode, crate, purchase, field requests, batch inspections
- `AgroWarehouseController` — stock, movements, temperature, tasks
- `AgroQaController` — checklists, checks, batch blocks, HACCP
- `AgroSalesController` — sales docs, FIFO allocation, export declarations

### UI Pages
| URL | Purpose |
|-----|---------|
| `/UNA.md/orasldev/agro-admin` | Reference data, settings, reports |
| `/UNA.md/orasldev/agro-field` | Tablet-first field operator (barcode scanner) |
| `/UNA.md/orasldev/agro-warehouse` | Warehouse operator (stock, receiving, temp) |
| `/UNA.md/orasldev/agro-qa` | QA inspector (checklists, HACCP, blocks) |
| `/UNA.md/orasldev/agro-sales` | Sales operator (shipments, export) |

### Print Documents
| Template | Route |
|----------|-------|
| Purchase act | `/UNA.md/orasldev/agro-document/<id>?type=purchase_act` |
| Weight ticket | `?type=weight_ticket` |
| Shipping note | `?type=shipping_note` |
| Invoice | `?type=invoice` |
| Export declaration | `?type=export_decl` |
| QA protocol | `?type=qa_protocol` |
| GMP checklist | `?type=gmp_checklist` |
| HACCP report | `?type=haccp_report` |
| Mass balance | `?type=mass_balance` |

## Oracle Objects

### Tables (AGRO_ prefix)

**Master Data:**
AGRO_SUPPLIERS, AGRO_CUSTOMERS, AGRO_WAREHOUSES, AGRO_STORAGE_CELLS,
AGRO_ITEMS, AGRO_PACKAGING_TYPES, AGRO_VEHICLES, AGRO_CURRENCIES,
AGRO_EXCHANGE_RATES, AGRO_FORMULA_PARAMS, AGRO_MODULE_CONFIG

**Operations:**
AGRO_BARCODES, AGRO_PURCHASES, AGRO_PURCHASE_LINES, AGRO_CRATES,
AGRO_BATCHES, AGRO_STOCK_MOVEMENTS, AGRO_STORAGE_READINGS,
AGRO_STORAGE_ALERTS, AGRO_PROCESSING_TASKS

**Sales:**
AGRO_SALES_DOCS, AGRO_SALES_LINES, AGRO_BATCH_ALLOCATIONS,
AGRO_EXPORT_DECLARATIONS

**QA & HACCP:**
AGRO_QA_CHECKLISTS, AGRO_QA_CHECKLIST_ITEMS, AGRO_QA_CHECKS,
AGRO_QA_CHECK_VALUES, AGRO_BATCH_BLOCKS, AGRO_HACCP_PLANS,
AGRO_HACCP_CCPS, AGRO_HACCP_RECORDS

**Audit:**
AGRO_EVENT_LOG

**Acceptance & Procurement (new):**
AGRO_ITEM_VARIETIES, AGRO_ACCEPTANCE_PROFILES, AGRO_FIELD_REQUESTS,
AGRO_FIELD_REQUEST_LINES, AGRO_BATCH_INSPECTIONS, AGRO_BATCH_INSPECTION_VALUES

### Views
- `AGRO_V_STOCK_BALANCE` — current stock by batch/warehouse/cell
- `AGRO_V_PURCHASES` — purchase documents with supplier/item details
- `AGRO_V_SALES` — sales documents with customer details
- `AGRO_V_MASS_BALANCE` — mass balance by item
- `AGRO_V_CELL_READINGS` — storage readings with cell/warehouse info
- `AGRO_V_FIELD_REQUESTS` — field requests with supplier/warehouse/profile/line counts
- `AGRO_V_BATCH_INSPECTIONS` — batch inspection results with item/profile info

## API Endpoints

### Admin API (`/api/agro-admin/`)
- `GET/POST` — suppliers, customers, warehouses, storage_cells, items, packaging_types, vehicles, currencies, exchange_rates, formula_params, module_config
- `PUT/DELETE` — `/<entity>/<id>`
- `GET/POST /item-varieties`, `DELETE /item-varieties/<id>` — product varieties (calibre, brix, shelf life)
- `GET/POST /acceptance-profiles`, `DELETE /acceptance-profiles/<id>` — retailer acceptance threshold profiles
- `GET /api/agro-admin/reports/<type>` — purchases, sales, mass_balance, stock, expiry
- `GET /api/agro-admin/reports/export/<type>?format=xlsx|csv`

### Field API (`/api/agro-field/`)
- `POST /barcodes/generate` — generate barcode batch
- `GET /barcodes/print-batch` — get barcodes for printing
- `POST /crates/scan`, `POST /crates/register` — crate operations
- `GET/POST /purchases`, `GET /purchases/<id>`, `PUT /purchases/<id>/confirm`
- `GET /sync/references`, `POST /sync/offline-queue`

### Warehouse API (`/api/agro-warehouse/`)
- `GET /stock`, `GET /batches/<id>`, `GET /batches/<id>/history`
- `POST /movements`, `POST /receive`
- `GET/POST /readings`, `GET /alerts`, `PUT /alerts/<id>/ack`
- `GET/POST /tasks`, `PUT /tasks/<id>/status`

### Sales API (`/api/agro-sales/`)
- `GET/POST /documents`, `GET /documents/<id>`, `PUT /documents/<id>/confirm`
- `POST /allocate`, `GET /available-stock`
- `POST /export-decl`, `GET/PUT /export-decl/<id>`

### QA API (`/api/agro-qa/`)
- `GET/POST /checklists`, `GET/DELETE /checklists/<id>`
- `GET/POST /checks`, `GET /checks/<id>`
- `POST /batches/<id>/block`, `POST /batches/<id>/unblock`, `GET /blocks`
- `GET/POST /haccp/plans`, `GET /haccp/plans/<id>/ccps`, `POST /haccp/ccps`
- `POST /haccp/records`, `GET /haccp/deviations`

## Local Setup

1. Ensure Oracle wallet is configured in `.env`:
   ```
   WALLET_DIR=/path/to/wallet
   ```

2. Deploy DDL:
   ```bash
   python deploy_oracle_objects.py
   ```
   This executes `sql/35_agro_tables.sql`, `sql/36_agro_views.sql`,
   `sql/37_agro_triggers.sql`, `sql/38_agro_demo_data.sql`.

3. Run the application:
   ```bash
   python app.py
   ```

4. Navigate to `http://localhost:5000/UNA.md/orasldev/agro-admin`

## Remote Deploy

1. `deploy_to_remote.sh` transfers code to `/home/ubuntu/artgranit`
2. Oracle wallet stays at `/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q`
3. For schema changes, run: `DEPLOY_ORACLE_ON_REMOTE=1 python deploy_oracle_objects.py`

## Post-deploy Verification

- [ ] Oracle objects visible in `USER_OBJECTS` with prefix `AGRO_`
- [ ] All 5 UI pages load at `/UNA.md/orasldev/agro-*`
- [ ] Admin CRUD works for all 11 reference tables
- [ ] Barcode generation and scanning functional
- [ ] Purchase document creation and confirmation
- [ ] Stock balance updates after movements
- [ ] Temperature readings generate alerts on threshold breach
- [ ] QA check auto-blocks batch on critical failure
- [ ] Sales doc confirmation performs FIFO allocation
- [ ] Reports render data and export to XLSX/CSV
- [ ] Print documents render with proper A4 layout
- [ ] Dashboard `dashboard_10.json` loads in shell
