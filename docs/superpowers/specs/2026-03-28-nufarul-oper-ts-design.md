# Design: nufarul-oper-ts — Touchscreen Kiosk for Nufarul

**Date:** 2026-03-28
**Route:** `/UNA.md/orasldev/nufarul-oper-ts`
**Status:** Approved, ready for implementation

---

## 1. Overview

`nufarul-oper-ts` is a full-screen touchscreen kiosk for the Nufarul dry-cleaning module. It uses the same Oracle tables and `NufarulController` as `nufarul-operator`, but is optimised for a physical touchscreen terminal at the reception desk.

Key differences from `nufarul-operator`:
- Full-screen 4-column layout (no scrolling)
- Per-item configurable parameters (fabric, colour, stains, etc.) stored as JSON in Oracle
- Built-in AI input bar: text, microphone (Web Speech API), camera
- Cart visible as a grid in the bottom half of the centre column
- Optional second customer-facing display via `window.open`
- Mode toggle: INTAKE / ISSUE in header

---

## 2. Screen Layout

```
┌──────────┬────────────────────────────┬──────────────┬──────────────┐
│ Col 1    │ Col 2 (centre)             │ Col 3        │ Col 4        │
│ Groups   │ AI bar                     │ Params       │ Customer     │
│ sidebar  ├────────────────────────────│ panel        │ screen       │
│          │ Service grid (top half)    │              │ (optional)   │
│          ├────────────────────────────│              │              │
│          │ Cart grid (bottom half)    │              │              │
└──────────┴────────────────────────────┴──────────────┴──────────────┘
```

### Column widths (approximate)
- Col 1 Groups: ~155px fixed
- Col 2 Centre: flex 1fr
- Col 3 Params: ~260px fixed
- Col 4 Customer: ~300px fixed, hidden when disabled

### Header
- Logo + title
- INTAKE / ISSUE mode toggle (always visible)
- Client name + phone inputs
- "Customer Screen 🖥️" toggle button (right)

---

## 3. Mode: INTAKE

### Col 1 — Groups sidebar
Groups loaded from Oracle, each with icon and service count. Tapping activates the group and loads its services in Col 2.

Default groups (matching `NUF_GROUP_PARAMS` keys):
| Key | Label | Icon |
|-----|-------|------|
| `clothing` | Одежда | 👗 |
| `carpets` | Ковры | 🪞 |
| `pillows` | Подушки | 🛏 |
| `shoes` | Обувь | 👟 |

Group list and labels are configurable. Services are filtered from `NUF_SERVICES` by `SERVICE_GROUP`.

### Col 2 — Centre: AI bar + Services + Cart

**AI input bar (top, always visible):**
- Text input field: free-form order entry ("2 пальто, шуба, 3 рубашки")
- 🎙 Microphone button: Web Speech API, toggles recording state (red pulse animation)
- 📷 Camera button: opens camera modal (re-uses existing camera modal pattern from `nufarul_operator.html`)
- Send button ➜: calls `/api/nufarul-operator/ai-parse` or Oracle backend
- Backend selector: rapidfuzz (local) / Oracle AI (PL/SQL vector)
- Results appear below as a list: service name × qty, price, "+ Add" button per item

**Service grid (upper half of centre):**
- Cards: service name, price, unit
- Tapping a card selects it and populates Col 3 params panel
- Search input filters by name (client-side, no API call)

**Cart grid (lower half of centre):**
- Visible at all times (collapsible via header tap)
- Cards show: service name, param summary (colour dot + fabric + flags), price × qty
- Last card in grid = checkout card:
  - Amber/gold colour (`#f59e0b`)
  - Shows order total
  - Animated: shimmer sweep + border pulse every 10 seconds
  - Only appears when cart has ≥ 1 item
- Delete (✕) per card

### Col 3 — Parameters panel

Shown when a service card is selected. Parameters are loaded from `NUF_GROUP_PARAMS` for the active group.

**Parameter control types:**

| Type | UI | Used for |
|------|----|----------|
| `color` | Colour circles (tap to select) | Clothing colour, carpet colour, shoe colour |
| `chips` | Tag chips (single or multi) | Fabric, material, contamination type, pillow type |
| `toggle` | YES / NO button pair | Stains, damage, urgency, pillowcase replacement |
| `counter` | − / value / + | Quantity of items |
| `numeric` | Tappable field → numpad | Carpet size in m² |
| `notes` | Textarea | Operator comment |

**Add to cart button** at bottom of Col 3. Tapping adds the selected service + current parameter values as a JSON blob to the cart, and clears param selections.

### Col 4 — Customer screen (optional)

Opened via `window.open('/UNA.md/orasldev/nufarul-customer-screen', '_blank')` targeting a second monitor. The operator window pushes cart state to the customer window via `localStorage` events (same origin). Customer screen shows:
- Welcome / logo
- "Currently being added" highlighted card
- Full order list with param summaries
- Running total

---

## 4. Mode: ISSUE

When ISSUE mode is active:
- Col 2 service grid is replaced by a search panel
- Two input methods:
  1. Barcode scanner field (auto-focus, triggers on Enter / scan)
  2. Manual order number text input with numeric keypad
- On match: shows order summary (client, items, status, total)
- Button: "Mark as ISSUED" → calls `update_order_status` with status `issued`
- Col 3 shows order detail (read-only)
- Cart grid hides in ISSUE mode

---

## 5. Data Model

### New Oracle objects

**Table `NUF_GROUP_PARAMS`**
```sql
CREATE TABLE NUF_GROUP_PARAMS (
  GROUP_KEY   VARCHAR2(50)  NOT NULL PRIMARY KEY,
  LABEL_RU    VARCHAR2(200),
  LABEL_RO    VARCHAR2(200),
  ICON        VARCHAR2(20),
  SORT_ORDER  NUMBER DEFAULT 0,
  PARAMS_JSON CLOB,           -- JSON schema: array of param definitions
  ACTIVE      CHAR(1) DEFAULT 'Y',
  UPDATED_AT  TIMESTAMP DEFAULT SYSTIMESTAMP
);
```

`PARAMS_JSON` schema per group (array of param definitions):
```json
[
  { "key": "color",   "type": "color",   "label_ru": "Цвет",  "options": ["#111","#c0392b","#2980b9","#27ae60","#8e4585","#e8c84a","#bdc3c7","#f5f5f5"] },
  { "key": "fabric",  "type": "chips",   "label_ru": "Ткань", "multi": false, "options": ["Шерсть","Кашемир","Хлопок","Кожа","Синтетика","Другое"] },
  { "key": "stains",  "type": "toggle",  "label_ru": "Пятна" },
  { "key": "damage",  "type": "toggle",  "label_ru": "Повреждения" },
  { "key": "urgent",  "type": "toggle",  "label_ru": "Срочно" },
  { "key": "qty",     "type": "counter", "label_ru": "Количество", "min": 1 },
  { "key": "notes",   "type": "notes",   "label_ru": "Примечание" }
]
```

**New column `NUF_ORDER_ITEMS_LEDGER.PARAMS`**
```sql
ALTER TABLE NUF_ORDER_ITEMS_LEDGER ADD (PARAMS CLOB);
```

Stores per-item parameter values as JSON at order creation time:
```json
{ "color": "#c0392b", "fabric": "Шерсть", "stains": true, "damage": false, "urgent": false, "notes": "" }
```

### Existing tables used (unchanged)
- `NUF_SERVICES` — services catalogue
- `NUF_ORDERS_LEDGER` — orders (blockchain append-only)
- `NUF_ORDER_ITEMS_LEDGER` — order items (+ new PARAMS column)
- `NUF_ORDER_STATUS_LOG` — status changes
- `V_NUF_ORDERS_BLOCKCHAIN` — orders view
- `NUF_AI_SEARCH` PL/SQL package — Oracle vector/fuzzy search

---

## 6. New Files

| File | Purpose |
|------|---------|
| `templates/nufarul_oper_ts.html` | Main kiosk template (self-contained monolithic HTML) |
| `templates/nufarul_customer_screen.html` | Customer-facing second display (minimal, reads localStorage) |
| `sql/23_nufarul_group_params.sql` | DDL: `NUF_GROUP_PARAMS` + ALTER for `NUF_ORDER_ITEMS_LEDGER.PARAMS` |

---

## 7. New Routes & API endpoints

### Flask routes (app.py)

```python
GET  /UNA.md/orasldev/nufarul-oper-ts          → nufarul_oper_ts.html
GET  /UNA.md/orasldev/nufarul-customer-screen   → nufarul_customer_screen.html
```

### API endpoints

```
GET  /api/nufarul-ts/group-params               → list all NUF_GROUP_PARAMS
GET  /api/nufarul-ts/group-params/<group_key>   → single group params JSON
POST /api/nufarul-ts/order                      → create order (same as /api/nufarul-operator/order but with PARAMS per item)
```

Remaining API calls re-use existing `/api/nufarul-operator/*` endpoints unchanged.

---

## 8. Controller changes

`NufarulController` gets two new static methods:

- `get_group_params(group_key=None)` — reads `NUF_GROUP_PARAMS`
- `create_order_with_params(client_name, client_phone, items, notes)` — same as existing `create_order` but writes `PARAMS` CLOB per item

---

## 9. AI input behaviour

Matches existing `nufarul-operator` AI bar:
- Text → POST `/api/nufarul-operator/ai-parse` (rapidfuzz or Oracle backend)
- Results appear as a list; "+ Add" per result pre-fills service + qty in cart (without triggering param panel — params default to empty)
- Microphone: Web Speech API `SpeechRecognition`, fills text input, auto-sends
- Camera: opens existing camera modal pattern, captures frame, sends to AI parse endpoint as recognised text (OCR not in scope — camera used for photo attachment to order, same as nufarul-operator)

---

## 10. Customer screen sync

```
nufarul_oper_ts.html  ──localStorage.setItem('nuf_cart', JSON)──►  nufarul_customer_screen.html
                                                                     (window.addEventListener 'storage')
```

Customer screen polls / listens for `storage` events and re-renders cart. No backend call needed — same-origin tab communication.

---

## 11. Deploy checklist

1. Run `sql/23_nufarul_group_params.sql` via `deploy_oracle_objects.py` (DDL deploy, not code deploy)
2. Seed `NUF_GROUP_PARAMS` with default rows for clothing / carpets / pillows / shoes
3. Deploy code via `deploy_to_remote.sh`
4. Verify routes at `/UNA.md/orasldev/nufarul-oper-ts`
5. Verify `NUF_GROUP_PARAMS` visible in `USER_OBJECTS`
6. Verify `NUF_ORDER_ITEMS_LEDGER.PARAMS` column exists

---

## 12. Out of scope

- Printing barcodes from the TS kiosk (remains in nufarul-operator / admin)
- Photo BLOB capture from the TS kiosk camera (camera button is for AI text recognition assist only, not photo storage — can be added later)
- Admin UI for editing `NUF_GROUP_PARAMS` JSON (use Oracle admin or existing nufarul-admin page in a later iteration)
