# AGRO: Sales Weighing, Acceptance Program & Supplier Pack — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add touchscreen weighing interface to sales module, enhance field inspections with D-code defect panel + photo capture, and align supplier pack document with internal AGRO scoring system.

**Architecture:** Extend existing `agro_sales.html` with new sidebar pages (weighing + ticket journal), backed by 2 new Oracle tables + AgroStore/Controller methods. Enhance `agro_field.html` inspection section with D-code buttons that auto-toggle scoring checkboxes. Rewrite defect table in `dipp_fruct_supplier_pack.html` to match AGRO scoring weights.

**Tech Stack:** Python/Flask, Oracle (ADB), vanilla JS, HTML/CSS (dark theme, touchscreen-first)

**Spec:** `docs/superpowers/specs/2026-03-27-agro-sales-weighing-acceptance-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `sql/41_agro_weight_tickets.sql` | CREATE | DDL: 2 tables, 2 sequences, 2 triggers, 6 indexes, ALTER ATTACHMENTS |
| `deploy_oracle_objects.py` | MODIFY (line 151) | Register new SQL file in execution order |
| `models/agro_oracle_store.py` | MODIFY (after line 3178) | Weight ticket CRUD + scoring-config endpoint |
| `controllers/agro_sales_controller.py` | MODIFY (after line 66) | Weight ticket controller methods |
| `app.py` | MODIFY (after line 4545) | 8 new API routes |
| `templates/agro_sales.html` | MODIFY | Weighing page + ticket journal + touchscreen CSS |
| `templates/agro_field.html` | MODIFY (lines 1214-1278) | D-code panel, photo cells, enhanced live score |
| `docs/AGRO/achizitie standard/dipp_fruct_supplier_pack.html` | MODIFY | Rewrite defect table, sync thresholds |

---

## Task 1: Oracle DDL — Weight Ticket Tables

**Files:**
- Create: `sql/41_agro_weight_tickets.sql`
- Modify: `deploy_oracle_objects.py:151`

- [ ] **Step 1: Create SQL file with tables, sequences, triggers, indexes**

```sql
-- sql/41_agro_weight_tickets.sql
-- Weight tickets for sales weighing module

-- Sequences
CREATE SEQUENCE AGRO_WEIGHT_TICKETS_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/
CREATE SEQUENCE AGRO_WEIGHT_TICKET_LINES_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/

-- Header table
CREATE TABLE AGRO_WEIGHT_TICKETS (
    ID              NUMBER PRIMARY KEY,
    TICKET_NUMBER   VARCHAR2(30) NOT NULL,
    SALES_DOC_ID    NUMBER REFERENCES AGRO_SALES_DOCS(ID),
    CUSTOMER_ID     NUMBER REFERENCES AGRO_CUSTOMERS(ID),
    WAREHOUSE_ID    NUMBER REFERENCES AGRO_WAREHOUSES(ID),
    TICKET_DATE     DATE DEFAULT SYSDATE,
    STATUS          VARCHAR2(20) DEFAULT 'draft',
    OPERATOR        VARCHAR2(100),
    NOTES           VARCHAR2(500),
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP,
    UPDATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP
);
/

-- Lines table
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
/

-- Auto-ID triggers
CREATE OR REPLACE TRIGGER AGRO_WEIGHT_TICKETS_BI
  BEFORE INSERT ON AGRO_WEIGHT_TICKETS FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := AGRO_WEIGHT_TICKETS_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER AGRO_WEIGHT_TICKET_LINES_BI
  BEFORE INSERT ON AGRO_WEIGHT_TICKET_LINES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := AGRO_WEIGHT_TICKET_LINES_SEQ.NEXTVAL;
END;
/

-- Indexes on FK columns
CREATE INDEX IX_AGRO_WT_SALESDOC ON AGRO_WEIGHT_TICKETS(SALES_DOC_ID);
/
CREATE INDEX IX_AGRO_WT_CUSTOMER ON AGRO_WEIGHT_TICKETS(CUSTOMER_ID);
/
CREATE INDEX IX_AGRO_WT_WAREHOUSE ON AGRO_WEIGHT_TICKETS(WAREHOUSE_ID);
/
CREATE INDEX IX_AGRO_WTL_TICKET ON AGRO_WEIGHT_TICKET_LINES(TICKET_ID);
/
CREATE INDEX IX_AGRO_WTL_BATCH ON AGRO_WEIGHT_TICKET_LINES(BATCH_ID);
/
CREATE INDEX IX_AGRO_WTL_ITEM ON AGRO_WEIGHT_TICKET_LINES(ITEM_ID);
/

-- Extend AGRO_ATTACHMENTS CHECK constraint for batch_inspection
ALTER TABLE AGRO_ATTACHMENTS DROP CONSTRAINT CK_AGRO_ATT_ETYPE;
/
ALTER TABLE AGRO_ATTACHMENTS ADD CONSTRAINT CK_AGRO_ATT_ETYPE
  CHECK (ENTITY_TYPE IN ('purchase','sale','batch','qa_check','batch_inspection'));
/
```

- [ ] **Step 2: Register in deploy_oracle_objects.py**

In `deploy_oracle_objects.py`, after line 151 (`"40_agro_acceptance_demo.sql",`), add:

```python
        "41_agro_weight_tickets.sql",
```

- [ ] **Step 3: Commit**

```
git add sql/41_agro_weight_tickets.sql deploy_oracle_objects.py
git commit -m "feat(agro): add weight ticket DDL — 2 tables, sequences, triggers, indexes"
```

---

## Task 2: AgroStore — Weight Ticket CRUD + Scoring Config

**Files:**
- Modify: `models/agro_oracle_store.py` (insert after line 3178, before QA section at line 3180)

- [ ] **Step 1: Add scoring config endpoint method**

Insert after the `update_export_decl` method (line 3178), before the QA section comment (line 3180):

```python
    # ------------------------------------------------------------------
    # Weight Tickets (Sales Weighing)
    # ------------------------------------------------------------------

    @staticmethod
    def get_scoring_config() -> Dict[str, Any]:
        """Return scoring weights and critical checks for client-side calculation."""
        return {
            "success": True,
            "data": {
                "weights": dict(AgroStore._SCORING_WEIGHTS),
                "critical": list(AgroStore._CRITICAL_CHECKS),
            },
        }
```

- [ ] **Step 2: Add weight ticket CRUD methods**

Continue inserting after the scoring config method:

```python
    @staticmethod
    def get_weight_tickets(filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """List weight tickets with optional filters."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT wt.ID, wt.TICKET_NUMBER, wt.TICKET_DATE, wt.STATUS,
                           wt.OPERATOR, wt.NOTES, wt.SALES_DOC_ID, wt.CREATED_AT,
                           c.NAME AS CUSTOMER_NAME, w.NAME AS WAREHOUSE_NAME,
                           sd.DOC_NUMBER AS SALES_DOC_NUMBER,
                           (SELECT NVL(SUM(wtl.NET_KG), 0) FROM AGRO_WEIGHT_TICKET_LINES wtl
                            WHERE wtl.TICKET_ID = wt.ID) AS TOTAL_NET_KG
                    FROM AGRO_WEIGHT_TICKETS wt
                    LEFT JOIN AGRO_CUSTOMERS c ON c.ID = wt.CUSTOMER_ID
                    LEFT JOIN AGRO_WAREHOUSES w ON w.ID = wt.WAREHOUSE_ID
                    LEFT JOIN AGRO_SALES_DOCS sd ON sd.ID = wt.SALES_DOC_ID
                    WHERE 1=1
                """
                params: Dict[str, Any] = {}
                f = filters or {}
                if f.get("status"):
                    sql += " AND wt.STATUS = :status"
                    params["status"] = f["status"]
                if f.get("date_from"):
                    sql += " AND wt.TICKET_DATE >= TO_DATE(:dfrom, 'YYYY-MM-DD')"
                    params["dfrom"] = f["date_from"]
                if f.get("date_to"):
                    sql += " AND wt.TICKET_DATE <= TO_DATE(:dto, 'YYYY-MM-DD')"
                    params["dto"] = f["date_to"]
                sql += " ORDER BY wt.CREATED_AT DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_weight_ticket_by_id(ticket_id: int) -> Dict[str, Any]:
        """Get weight ticket header + lines."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT wt.*, c.NAME AS CUSTOMER_NAME, w.NAME AS WAREHOUSE_NAME,
                              sd.DOC_NUMBER AS SALES_DOC_NUMBER
                       FROM AGRO_WEIGHT_TICKETS wt
                       LEFT JOIN AGRO_CUSTOMERS c ON c.ID = wt.CUSTOMER_ID
                       LEFT JOIN AGRO_WAREHOUSES w ON w.ID = wt.WAREHOUSE_ID
                       LEFT JOIN AGRO_SALES_DOCS sd ON sd.ID = wt.SALES_DOC_ID
                       WHERE wt.ID = :tid""",
                    {"tid": ticket_id},
                )
                tickets = _norm_rows(r)
                if not tickets:
                    return {"success": False, "error": "Ticket not found"}
                ticket = tickets[0]

                rl = db.execute_query(
                    """SELECT wtl.*, i.NAME_RU AS ITEM_NAME
                       FROM AGRO_WEIGHT_TICKET_LINES wtl
                       LEFT JOIN AGRO_ITEMS i ON i.ID = wtl.ITEM_ID
                       WHERE wtl.TICKET_ID = :tid
                       ORDER BY wtl.LINE_NO""",
                    {"tid": ticket_id},
                )
                ticket["lines"] = _norm_rows(rl)
                return {"success": True, "data": ticket}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_weight_ticket(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new weight ticket (draft)."""
        try:
            with DatabaseModel() as db:
                r_seq = db.execute_query(
                    "SELECT AGRO_WEIGHT_TICKETS_SEQ.NEXTVAL AS NID FROM DUAL", {}
                )
                new_id = _norm_rows(r_seq)[0]["nid"]
                today = datetime.now().strftime("%Y%m%d")
                ticket_number = f"WT-{today}-{int(new_id):04d}"

                db.execute_query(
                    """INSERT INTO AGRO_WEIGHT_TICKETS
                       (ID, TICKET_NUMBER, SALES_DOC_ID, CUSTOMER_ID, WAREHOUSE_ID,
                        TICKET_DATE, STATUS, OPERATOR, NOTES)
                       VALUES (:id, :tnum, :sdid, :cid, :wid,
                               TRUNC(SYSDATE), 'draft', :op, :notes)""",
                    {
                        "id": new_id, "tnum": ticket_number,
                        "sdid": data.get("sales_doc_id"),
                        "cid": data.get("customer_id"),
                        "wid": data.get("warehouse_id"),
                        "op": data.get("operator"),
                        "notes": data.get("notes"),
                    },
                )
                db.connection.commit()
                return {"success": True, "id": int(new_id), "ticket_number": ticket_number}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_weight_ticket(ticket_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update weight ticket header fields."""
        try:
            with DatabaseModel() as db:
                fields = []
                params: Dict[str, Any] = {"tid": ticket_id}
                for col in ("sales_doc_id", "customer_id", "warehouse_id",
                            "operator", "notes"):
                    if col in data:
                        fields.append(f"{col.upper()} = :{col}")
                        params[col] = data[col]
                if not fields:
                    return {"success": False, "error": "No fields to update"}
                fields.append("UPDATED_AT = SYSTIMESTAMP")
                sql = f"UPDATE AGRO_WEIGHT_TICKETS SET {', '.join(fields)} WHERE ID = :tid AND STATUS = 'draft'"
                db.execute_query(sql, params)
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def add_weight_ticket_line(ticket_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a weighing line to a draft ticket."""
        try:
            with DatabaseModel() as db:
                # Verify ticket is draft
                rt = db.execute_query(
                    "SELECT STATUS FROM AGRO_WEIGHT_TICKETS WHERE ID = :tid",
                    {"tid": ticket_id},
                )
                rows = _norm_rows(rt)
                if not rows:
                    return {"success": False, "error": "Ticket not found"}
                if rows[0].get("status") != "draft":
                    return {"success": False, "error": "Ticket is not in draft status"}

                # Get next line number
                rl = db.execute_query(
                    "SELECT NVL(MAX(LINE_NO), 0) + 1 AS NEXT_NO FROM AGRO_WEIGHT_TICKET_LINES WHERE TICKET_ID = :tid",
                    {"tid": ticket_id},
                )
                next_no = _norm_rows(rl)[0]["next_no"]

                gross_kg = float(data.get("gross_kg", 0))
                tare_kg = float(data.get("tare_kg", 0))
                net_kg = gross_kg - tare_kg

                db.execute_query(
                    """INSERT INTO AGRO_WEIGHT_TICKET_LINES
                       (ID, TICKET_ID, LINE_NO, BATCH_ID, CRATE_CODE, ITEM_ID,
                        GROSS_KG, TARE_KG, NET_KG)
                       VALUES (AGRO_WEIGHT_TICKET_LINES_SEQ.NEXTVAL,
                               :tid, :lno, :bid, :ccode, :iid,
                               :gross, :tare, :net)""",
                    {
                        "tid": ticket_id, "lno": int(next_no),
                        "bid": data.get("batch_id"), "ccode": data.get("crate_code"),
                        "iid": data.get("item_id"),
                        "gross": gross_kg, "tare": tare_kg, "net": net_kg,
                    },
                )
                db.connection.commit()
                return {"success": True, "line_no": int(next_no), "net_kg": net_kg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def remove_weight_ticket_line(ticket_id: int, line_id: int) -> Dict[str, Any]:
        """Remove a line from a draft ticket."""
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """DELETE FROM AGRO_WEIGHT_TICKET_LINES
                       WHERE ID = :lid AND TICKET_ID = :tid
                       AND EXISTS (SELECT 1 FROM AGRO_WEIGHT_TICKETS WHERE ID = :tid AND STATUS = 'draft')""",
                    {"lid": line_id, "tid": ticket_id},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def finalize_weight_ticket(ticket_id: int) -> Dict[str, Any]:
        """Finalize a weight ticket: validate, update status, log event."""
        try:
            with DatabaseModel() as db:
                rt = db.execute_query(
                    "SELECT * FROM AGRO_WEIGHT_TICKETS WHERE ID = :tid",
                    {"tid": ticket_id},
                )
                tickets = _norm_rows(rt)
                if not tickets:
                    return {"success": False, "error": "Ticket not found"}
                ticket = tickets[0]
                if ticket.get("status") != "draft":
                    return {"success": False, "error": "Ticket already finalized"}

                # Check has lines
                rl = db.execute_query(
                    "SELECT COUNT(*) AS CNT FROM AGRO_WEIGHT_TICKET_LINES WHERE TICKET_ID = :tid",
                    {"tid": ticket_id},
                )
                if _norm_rows(rl)[0]["cnt"] == 0:
                    return {"success": False, "error": "No lines in ticket"}

                # Finalize
                db.execute_query(
                    "UPDATE AGRO_WEIGHT_TICKETS SET STATUS = 'finalized', UPDATED_AT = SYSTIMESTAMP WHERE ID = :tid",
                    {"tid": ticket_id},
                )

                # Log event
                db.execute_query(
                    """INSERT INTO AGRO_EVENT_LOG
                       (ID, EVENT_TYPE, ENTITY_TYPE, ENTITY_ID, CHANGE_DATA, CREATED_AT)
                       VALUES (AGRO_EVENT_LOG_SEQ.NEXTVAL,
                               'weight_ticket_finalized', 'weight_ticket', :tid,
                               :data, SYSTIMESTAMP)""",
                    {"tid": ticket_id, "data": f'{{"ticket_number":"{ticket.get("ticket_number")}"}}'},
                )

                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

- [ ] **Step 3: Commit**

```
git add models/agro_oracle_store.py
git commit -m "feat(agro): add weight ticket store methods + scoring config endpoint"
```

---

## Task 3: AgroSalesController — Weight Ticket Methods

**Files:**
- Modify: `controllers/agro_sales_controller.py` (after line 66)

- [ ] **Step 1: Add controller methods**

Append after `update_export_decl` method (line 66):

```python
    # --- Weight Tickets ---

    @staticmethod
    def get_weight_tickets(filters: Dict[str, Any] = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_weight_tickets, filters)

    @staticmethod
    def get_weight_ticket_by_id(ticket_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_weight_ticket_by_id, ticket_id)

    @staticmethod
    def create_weight_ticket(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('customer_id') and not data.get('sales_doc_id'):
            return {"success": False, "error": "customer_id or sales_doc_id required"}
        return _safe_call(AgroStore.create_weight_ticket, data)

    @staticmethod
    def update_weight_ticket(ticket_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.update_weight_ticket, ticket_id, data)

    @staticmethod
    def add_weight_line(ticket_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('item_id'):
            return {"success": False, "error": "item_id required"}
        return _safe_call(AgroStore.add_weight_ticket_line, ticket_id, data)

    @staticmethod
    def remove_weight_line(ticket_id: int, line_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.remove_weight_ticket_line, ticket_id, line_id)

    @staticmethod
    def finalize_weight_ticket(ticket_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.finalize_weight_ticket, ticket_id)

    @staticmethod
    def get_scoring_config() -> Dict[str, Any]:
        return _safe_call(AgroStore.get_scoring_config)
```

- [ ] **Step 2: Commit**

```
git add controllers/agro_sales_controller.py
git commit -m "feat(agro): add weight ticket controller methods"
```

---

## Task 4: Flask Routes — Weight Ticket API

**Files:**
- Modify: `app.py` (insert after line 4545, before the AGRO QA section at line 4548)

- [ ] **Step 1: Add 8 API routes**

Insert after the `api_agro_sales_export_update` function (line 4545):

```python

# --- Weight Tickets ---

@app.route('/api/agro-sales/weight-tickets', methods=['GET'])
def api_agro_sales_wt_list():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Auth required"}), 401
    filters = {}
    for k in ('status', 'date_from', 'date_to'):
        if request.args.get(k):
            filters[k] = request.args[k]
    return jsonify(AgroSalesController.get_weight_tickets(filters or None))

@app.route('/api/agro-sales/weight-tickets', methods=['POST'])
def api_agro_sales_wt_create():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Auth required"}), 401
    return jsonify(AgroSalesController.create_weight_ticket(request.json))

@app.route('/api/agro-sales/weight-tickets/<int:tid>', methods=['GET'])
def api_agro_sales_wt_get(tid):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Auth required"}), 401
    return jsonify(AgroSalesController.get_weight_ticket_by_id(tid))

@app.route('/api/agro-sales/weight-tickets/<int:tid>', methods=['PUT'])
def api_agro_sales_wt_update(tid):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Auth required"}), 401
    return jsonify(AgroSalesController.update_weight_ticket(tid, request.json))

@app.route('/api/agro-sales/weight-tickets/<int:tid>/lines', methods=['POST'])
def api_agro_sales_wt_add_line(tid):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Auth required"}), 401
    return jsonify(AgroSalesController.add_weight_line(tid, request.json))

@app.route('/api/agro-sales/weight-tickets/<int:tid>/lines/<int:lid>', methods=['DELETE'])
def api_agro_sales_wt_del_line(tid, lid):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Auth required"}), 401
    return jsonify(AgroSalesController.remove_weight_line(tid, lid))

@app.route('/api/agro-sales/weight-tickets/<int:tid>/finalize', methods=['POST'])
def api_agro_sales_wt_finalize(tid):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Auth required"}), 401
    return jsonify(AgroSalesController.finalize_weight_ticket(tid))

@app.route('/api/agro-field/scoring-config', methods=['GET'])
def api_agro_field_scoring_config():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Auth required"}), 401
    return jsonify(AgroSalesController.get_scoring_config())
```

- [ ] **Step 2: Commit**

```
git add app.py
git commit -m "feat(agro): add weight ticket + scoring config API routes"
```

---

## Task 5: Sales Template — Weighing Page + Ticket Journal

**Files:**
- Modify: `templates/agro_sales.html`

This is the largest task. The sales template is currently 739 lines. We add:
1. New sidebar entries for "Отгрузка / Expediere"
2. Two new pages: weighing (touchscreen) + ticket journal
3. Touchscreen CSS (copied from agro_field.html patterns)
4. JavaScript for weighing workflow + ticket management

- [ ] **Step 1: Add touchscreen CSS to `<style>` block**

After the existing `.empty` rule (around line 88), before the closing `</style>`, add:

```css
/* ---------- Touchscreen Weighing (from field patterns) ---------- */
.input-weight {
    font-size: 36px; font-weight: 700; text-align: center;
    padding: 20px; min-height: 80px; letter-spacing: 2px; color: var(--text);
}
.weight-display { display: flex; gap: 16px; margin: 16px 0; }
.weight-box {
    flex: 1; background: #1a1a2e; border: 2px solid var(--border);
    border-radius: 12px; padding: 16px; text-align: center;
}
.weight-box.net { border-color: var(--primary); background: #2a0f1e; }
.weight-box .wlabel { font-size: 13px; color: var(--text-muted); margin-bottom: 4px; }
.weight-box .wvalue { font-size: 28px; font-weight: 700; color: var(--text); }
.btn-lg {
    padding: 18px 36px; font-size: 20px; border-radius: 14px;
    min-height: 60px; width: 100%; touch-action: manipulation;
}
.btn-weigh {
    width: 48px; height: 48px; border: 2px solid var(--accent);
    background: rgba(83,215,105,.1); color: #53d769; border-radius: 8px;
    font-size: 20px; cursor: pointer; transition: all .2s;
}
.btn-weigh:hover { background: rgba(83,215,105,.25); transform: scale(1.05); }
.btn-weigh:active { transform: scale(.95); }
.btn-weigh.weighing { animation: weigh-pulse 1s infinite; border-color: #ffc107; }
@keyframes weigh-pulse { 0%,100%{opacity:1;} 50%{opacity:.5;} }
.wt-line-row {
    display: grid; grid-template-columns: 40px 1.5fr 2fr 1fr 1fr 1fr 48px 40px;
    gap: 8px; padding: 10px 0; border-bottom: 1px solid var(--border);
    align-items: center; font-size: 15px;
}
.wt-line-header { font-weight: 600; font-size: 12px; color: var(--text-muted); text-transform: uppercase; }
```

- [ ] **Step 2: Add new sidebar sections**

In the `<nav class="sidebar">` section (around line 103-111), replace/extend:

```html
<nav class="sidebar">
    <div class="sidebar-section">Отгрузки / Livrari</div>
    <a href="#documents" class="nav-link active" data-page="documents">Документы / Documente</a>
    <a href="#new-doc" class="nav-link" data-page="new-doc">+ Новый / Nou</a>
    <a href="#stock" class="nav-link" data-page="stock">Остатки / Stoc</a>
    <div class="sidebar-divider"></div>
    <div class="sidebar-section">Отгрузка / Expediere</div>
    <a href="#weighing" class="nav-link" data-page="weighing">⚖ Взвешивание / Cântărire</a>
    <a href="#tickets" class="nav-link" data-page="tickets">Акты / Acte</a>
    <div class="sidebar-divider"></div>
    <div class="sidebar-section">Экспорт / Export</div>
    <a href="#export" class="nav-link" data-page="export">Декларации / Declaratii</a>
</nav>
```

- [ ] **Step 3: Add weighing page HTML**

After the export declarations page (`</div>` closing `page-export`, around line 205), insert:

```html
<!-- ==================== WEIGHING / ВЗВЕШИВАНИЕ ==================== -->
<div id="page-weighing" class="page">
    <div class="page-header">
        <div><h1>⚖ Взвешивание при отгрузке / Cântărire la expediere</h1>
        <div class="subtitle">Interfata touchscreen pentru cantarire si formare acte</div></div>
    </div>

    <!-- Ticket header -->
    <div class="card">
        <div class="field-row">
            <div class="field"><label>Документ продажи / Document vânzare</label>
                <select id="wtSalesDoc" onchange="wtSalesDocChanged()">
                    <option value="">-- Без привязки --</option>
                </select></div>
            <div class="field"><label>Клиент / Client</label>
                <select id="wtCustomer"></select></div>
            <div class="field"><label>Склад / Depozit</label>
                <select id="wtWarehouse"></select></div>
        </div>
    </div>

    <!-- Scanner + Scale -->
    <div class="card">
        <h3 style="margin-bottom:12px;">Сканер + Весы / Scanner + Cântar</h3>
        <div class="field-row">
            <div class="field" style="flex:2;">
                <label>Штрихкод ящика / Cod de bare lada</label>
                <div style="display:flex;gap:10px;">
                    <input type="text" id="wtBarcode" placeholder="Сканируйте или введите..." style="flex:1;font-size:18px;padding:14px 16px;">
                    <button class="btn btn-accent" onclick="wtLookupCrate()" style="min-width:100px;">Найти</button>
                </div>
            </div>
            <div class="field" style="flex:1;">
                <label>Продукт / Produs</label>
                <select id="wtItem"></select>
            </div>
        </div>

        <div class="weight-display">
            <div class="weight-box">
                <div class="wlabel">Брутто / Brut, кг</div>
                <input type="number" class="input-weight" id="wtGross" placeholder="0.00" step="0.01" min="0" oninput="wtCalcNet()">
            </div>
            <div class="weight-box">
                <div class="wlabel">Тара / Tara, кг</div>
                <div class="wvalue" id="wtTare">0.00</div>
            </div>
            <div class="weight-box net">
                <div class="wlabel">Нетто / Net, кг</div>
                <div class="wvalue" id="wtNet">0.00</div>
            </div>
        </div>

        <div style="display:flex;gap:10px;">
            <button class="btn btn-accent btn-lg" style="flex:1;" onclick="wtReadScale()">⚖ Взвесить / Cântărește</button>
            <button class="btn btn-primary btn-lg" style="flex:1;" onclick="wtAddLine()">+ Добавить / Adaugă</button>
        </div>
    </div>

    <!-- Weighed lines -->
    <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <h3>Позиции акта / Liniile actului</h3>
            <span style="font-size:13px;color:var(--text-muted);" id="wtLineCount">0 позиций</span>
        </div>

        <div class="wt-line-row wt-line-header">
            <div>#</div><div>Штрихкод</div><div>Продукт</div>
            <div>Брутто</div><div>Тара</div><div>Нетто</div><div>⚖</div><div></div>
        </div>
        <div id="wtLinesBody"><div style="text-align:center;padding:20px;color:var(--text-muted);">Сканируйте ящик и взвесьте</div></div>

        <div style="margin-top:16px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
            <div style="font-size:22px;font-weight:700;color:var(--accent);">
                Итого нетто: <span id="wtTotalNet">0.00</span> кг
            </div>
            <button class="btn btn-primary btn-lg" style="width:auto;padding:18px 40px;" onclick="wtCreateTicket()">
                Сформировать акт / Generează act
            </button>
        </div>
    </div>
</div>

<!-- ==================== TICKET JOURNAL / АКТЫ ==================== -->
<div id="page-tickets" class="page">
    <div class="page-header">
        <div><h1>Акты взвешивания / Acte de cântărire</h1>
        <div class="subtitle">Jurnal acte cu detalii si tiparire</div></div>
        <div style="display:flex;gap:8px;">
            <select id="wtFilterStatus" onchange="loadTickets()" style="padding:8px;border:1px solid var(--border);border-radius:8px;font-size:14px;background:#1e2a45;color:var(--text);">
                <option value="">Все статусы</option>
                <option value="draft">Draft</option>
                <option value="finalized">Finalized</option>
            </select>
        </div>
    </div>
    <div class="stat-cards" id="wtStats">
        <div class="stat-card"><div class="val" id="wtStatTotal">0</div><div class="lbl">Всего / Total</div></div>
        <div class="stat-card"><div class="val" id="wtStatDraft">0</div><div class="lbl">Черновики / Ciorne</div></div>
        <div class="stat-card"><div class="val" id="wtStatFinal">0</div><div class="lbl">Финализированы</div></div>
        <div class="stat-card"><div class="val" id="wtStatTotalKg">0</div><div class="lbl">Всего кг / Total kg</div></div>
    </div>
    <div class="card"><div class="table-wrap">
        <table><thead><tr>
            <th>Номер / Nr.</th><th>Дата</th><th>Клиент / Client</th><th>Склад</th>
            <th>Док. продажи</th><th>Статус</th><th>Нетто кг</th><th>Действия</th>
        </tr></thead><tbody id="wtTicketsBody"><tr><td colspan="8" class="empty">Загрузка...</td></tr></tbody></table>
    </div></div>
</div>
```

- [ ] **Step 4: Add ticket detail modal**

Before the closing `</main>` or after the export detail modal, insert:

```html
<!-- ==================== TICKET DETAIL MODAL ==================== -->
<div class="modal-overlay" id="wtDetailModal">
    <div class="modal" style="max-width:800px;">
        <h2>Акт взвешивания / Act de cântărire</h2>
        <div id="wtDetailContent"><p class="empty">Загрузка...</p></div>
        <div class="modal-actions">
            <button class="btn btn-ghost" onclick="closeModal('wtDetailModal')">Закрыть / Închide</button>
            <button class="btn btn-info btn-sm" id="btnWtPrint" onclick="wtPrint()" style="display:none;">🖨 Печать / Tipărește</button>
            <button class="btn btn-primary" id="btnWtFinalize" onclick="wtFinalize()" style="display:none;">Финализировать / Finalizează</button>
        </div>
    </div>
</div>
```

- [ ] **Step 5: Add JavaScript for weighing workflow**

In the `<script>` section, add weighing functions. The key functions are:

- `wtSalesDocChanged()` — auto-fill customer/warehouse from selected sales doc
- `wtLookupCrate()` — resolve barcode via `/api/agro-field/crates/<barcode>` lookup
- `wtReadScale()` — call `/api/agro-scale/read` to capture weight from connected scale
- `wtCalcNet()` — gross - tare calculation
- `wtAddLine()` — add line to local array, render in grid
- `wtCreateTicket()` — POST ticket + POST each line, then navigate to tickets journal
- `loadTickets()` — fetch and render ticket list
- `viewTicket(id)` — open detail modal
- `wtFinalize()` — POST finalize, refresh list
- `wtPrint()` — `window.open('/UNA.md/orasldev/agro-document/' + ticketId + '?type=weight_ticket')`

The JS follows the exact same `api()` helper pattern as existing sales code. Add to the existing IIFE after the export declaration functions.

Full JS implementation (~200 lines) — insert before the closing `})();`:

```javascript
/* ==================== WEIGHT TICKETS ==================== */
var wtLines = [];
var wtCurrentTicketId = null;

function wtSalesDocChanged() {
    var docId = document.getElementById('wtSalesDoc').value;
    if (!docId) return;
    api('GET', '/api/agro-sales/documents/' + docId).then(function(d) {
        var doc = (d.data || d).doc || d.data || d;
        if (doc.customer_id) document.getElementById('wtCustomer').value = doc.customer_id;
        if (doc.warehouse_id) document.getElementById('wtWarehouse').value = doc.warehouse_id;
    });
}

function wtLookupCrate() {
    var bc = document.getElementById('wtBarcode').value.trim();
    if (!bc) return toast('Введите штрихкод', 'warning');
    // Try to resolve crate from field API
    api('GET', '/api/agro-field/crates?barcode=' + encodeURIComponent(bc)).then(function(d) {
        if (d.success && d.data) {
            var crate = Array.isArray(d.data) ? d.data[0] : d.data;
            if (crate && crate.item_id) {
                document.getElementById('wtItem').value = crate.item_id;
                if (crate.net_weight_kg) {
                    document.getElementById('wtGross').value = parseFloat(crate.gross_weight_kg || 0).toFixed(2);
                    wtCalcNet();
                }
                toast('Ящик найден: ' + (crate.crate_code || bc), 'success');
            }
        }
    }).catch(function() {});
}

window.wtReadScale = function() {
    api('GET', '/api/agro-scale/read').then(function(d) {
        if (d.success && d.data && d.data.weight !== undefined) {
            document.getElementById('wtGross').value = parseFloat(d.data.weight).toFixed(2);
            wtCalcNet();
            toast('Вес захвачен: ' + d.data.weight + ' кг', 'success');
        } else {
            toast('Весы не ответили', 'warning');
        }
    }).catch(function() { toast('Ошибка весов', 'error'); });
};

window.wtCalcNet = function() {
    var gross = parseFloat(document.getElementById('wtGross').value) || 0;
    // Get tare from selected packaging type or default
    var tare = 0;
    var pkgSel = document.getElementById('wtItem');
    if (pkgSel && pkgSel.value) {
        var item = refs.items.find(function(i) { return String(i.id) === String(pkgSel.value); });
        if (item && item.default_tare_kg) tare = parseFloat(item.default_tare_kg);
    }
    document.getElementById('wtTare').textContent = tare.toFixed(2);
    document.getElementById('wtNet').textContent = (gross - tare).toFixed(2);
};

window.wtAddLine = function() {
    var bc = document.getElementById('wtBarcode').value.trim();
    var itemId = document.getElementById('wtItem').value;
    var gross = parseFloat(document.getElementById('wtGross').value) || 0;
    if (!itemId) return toast('Выберите продукт', 'warning');
    if (gross <= 0) return toast('Взвесьте ящик', 'warning');

    var tare = parseFloat(document.getElementById('wtTare').textContent) || 0;
    var net = gross - tare;
    var itemName = '';
    var item = refs.items.find(function(i) { return String(i.id) === String(itemId); });
    if (item) itemName = item.name || item.name_ru || item.code;

    wtLines.push({
        crate_code: bc, item_id: parseInt(itemId), item_name: itemName,
        gross_kg: gross, tare_kg: tare, net_kg: net
    });
    wtRenderLines();
    // Clear inputs
    document.getElementById('wtBarcode').value = '';
    document.getElementById('wtGross').value = '';
    document.getElementById('wtNet').textContent = '0.00';
    document.getElementById('wtTare').textContent = '0.00';
    document.getElementById('wtBarcode').focus();
};

function wtRenderLines() {
    var body = document.getElementById('wtLinesBody');
    if (!wtLines.length) {
        body.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted);">Сканируйте ящик и взвесьте</div>';
        document.getElementById('wtLineCount').textContent = '0 позиций';
        document.getElementById('wtTotalNet').textContent = '0.00';
        return;
    }
    var totalNet = 0;
    body.innerHTML = wtLines.map(function(l, i) {
        totalNet += l.net_kg;
        return '<div class="wt-line-row">' +
            '<div>' + (i + 1) + '</div>' +
            '<div style="font-family:monospace;">' + (l.crate_code || '-') + '</div>' +
            '<div>' + l.item_name + '</div>' +
            '<div style="font-weight:600;">' + l.gross_kg.toFixed(2) + '</div>' +
            '<div>' + l.tare_kg.toFixed(2) + '</div>' +
            '<div style="font-weight:700;color:var(--accent);">' + l.net_kg.toFixed(2) + '</div>' +
            '<div></div>' +
            '<div><button class="btn btn-sm btn-danger" onclick="wtRemoveLine(' + i + ')" style="padding:4px 8px;">✕</button></div>' +
            '</div>';
    }).join('');
    document.getElementById('wtLineCount').textContent = wtLines.length + ' позиций';
    document.getElementById('wtTotalNet').textContent = totalNet.toFixed(2);
}

window.wtRemoveLine = function(idx) {
    wtLines.splice(idx, 1);
    wtRenderLines();
};

window.wtCreateTicket = function() {
    if (!wtLines.length) return toast('Нет позиций', 'warning');
    var custId = document.getElementById('wtCustomer').value;
    var whId = document.getElementById('wtWarehouse').value;
    var sdId = document.getElementById('wtSalesDoc').value;
    if (!custId) return toast('Выберите клиента', 'warning');

    api('POST', '/api/agro-sales/weight-tickets', {
        customer_id: parseInt(custId),
        warehouse_id: whId ? parseInt(whId) : null,
        sales_doc_id: sdId ? parseInt(sdId) : null
    }).then(function(d) {
        if (!d.success) return toast(d.error || 'Ошибка', 'error');
        var ticketId = d.id;
        // Add lines sequentially
        var chain = Promise.resolve();
        wtLines.forEach(function(line) {
            chain = chain.then(function() {
                return api('POST', '/api/agro-sales/weight-tickets/' + ticketId + '/lines', {
                    crate_code: line.crate_code, item_id: line.item_id,
                    gross_kg: line.gross_kg, tare_kg: line.tare_kg
                });
            });
        });
        chain.then(function() {
            toast('Акт ' + d.ticket_number + ' создан!', 'success');
            wtLines = [];
            wtRenderLines();
            // Navigate to tickets page
            document.querySelectorAll('.nav-link').forEach(function(n) { n.classList.remove('active'); });
            document.querySelectorAll('.page').forEach(function(p) { p.classList.remove('active'); });
            var ticketsLink = document.querySelector('[data-page="tickets"]');
            if (ticketsLink) ticketsLink.classList.add('active');
            var ticketsPage = document.getElementById('page-tickets');
            if (ticketsPage) ticketsPage.classList.add('active');
            loadTickets();
        });
    });
};

/* ==================== TICKET JOURNAL ==================== */
window.loadTickets = function() {
    var status = document.getElementById('wtFilterStatus').value;
    var url = '/api/agro-sales/weight-tickets';
    if (status) url += '?status=' + status;
    api('GET', url).then(function(d) {
        var rows = d.data || [];
        var total = rows.length, drafts = 0, finals = 0, totalKg = 0;
        rows.forEach(function(r) {
            if (r.status === 'draft') drafts++;
            else if (r.status === 'finalized') finals++;
            totalKg += parseFloat(r.total_net_kg || 0);
        });
        document.getElementById('wtStatTotal').textContent = total;
        document.getElementById('wtStatDraft').textContent = drafts;
        document.getElementById('wtStatFinal').textContent = finals;
        document.getElementById('wtStatTotalKg').textContent = totalKg.toFixed(0);

        var tb = document.getElementById('wtTicketsBody');
        if (!rows.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">Нет актов</td></tr>'; return; }
        tb.innerHTML = rows.map(function(r) {
            var bc = r.status === 'finalized' ? 'badge-confirmed' : 'badge-draft';
            return '<tr>' +
                '<td style="font-weight:600;">' + (r.ticket_number || '-') + '</td>' +
                '<td>' + (r.ticket_date || '-') + '</td>' +
                '<td>' + (r.customer_name || '-') + '</td>' +
                '<td>' + (r.warehouse_name || '-') + '</td>' +
                '<td>' + (r.sales_doc_number || '-') + '</td>' +
                '<td><span class="badge ' + bc + '">' + (r.status || '-') + '</span></td>' +
                '<td style="font-weight:700;color:var(--accent);">' + parseFloat(r.total_net_kg || 0).toFixed(2) + '</td>' +
                '<td><button class="btn btn-sm btn-ghost" onclick="viewTicket(' + r.id + ')">Открыть</button></td></tr>';
        }).join('');
    });
};

window.viewTicket = function(tid) {
    wtCurrentTicketId = tid;
    document.getElementById('wtDetailContent').innerHTML = '<p class="empty">Загрузка...</p>';
    document.getElementById('btnWtFinalize').style.display = 'none';
    document.getElementById('btnWtPrint').style.display = 'none';
    document.getElementById('wtDetailModal').classList.add('open');

    api('GET', '/api/agro-sales/weight-tickets/' + tid).then(function(d) {
        if (!d.success) { document.getElementById('wtDetailContent').innerHTML = '<p class="empty">Ошибка</p>'; return; }
        var t = d.data;
        var lines = t.lines || [];

        var html = '<div class="doc-detail">' +
            '<div class="doc-num">' + (t.ticket_number || '-') + '</div>' +
            '<div class="doc-info">Клиент: <strong>' + (t.customer_name || '-') + '</strong> | ' +
            'Склад: <strong>' + (t.warehouse_name || '-') + '</strong> | ' +
            'Дата: ' + (t.ticket_date || '-') + ' | ' +
            'Статус: <span class="badge badge-' + (t.status === 'finalized' ? 'confirmed' : 'draft') + '">' + (t.status || '-') + '</span>' +
            '</div></div>';

        if (lines.length) {
            html += '<div class="table-wrap"><table><thead><tr><th>#</th><th>Штрихкод</th><th>Продукт</th><th>Брутто</th><th>Тара</th><th>Нетто</th></tr></thead><tbody>';
            var totalNet = 0;
            lines.forEach(function(l) {
                totalNet += parseFloat(l.net_kg || 0);
                html += '<tr><td>' + (l.line_no || '-') + '</td><td style="font-family:monospace;">' + (l.crate_code || '-') + '</td>' +
                    '<td>' + (l.item_name || '-') + '</td>' +
                    '<td>' + parseFloat(l.gross_kg || 0).toFixed(2) + '</td>' +
                    '<td>' + parseFloat(l.tare_kg || 0).toFixed(2) + '</td>' +
                    '<td style="font-weight:700;color:var(--accent);">' + parseFloat(l.net_kg || 0).toFixed(2) + '</td></tr>';
            });
            html += '</tbody></table></div>';
            html += '<div style="text-align:right;margin-top:12px;font-size:20px;font-weight:700;color:var(--accent);">Итого нетто: ' + totalNet.toFixed(2) + ' кг</div>';
        }

        document.getElementById('wtDetailContent').innerHTML = html;
        if (t.status === 'draft') document.getElementById('btnWtFinalize').style.display = '';
        document.getElementById('btnWtPrint').style.display = '';
    });
};

window.wtFinalize = function() {
    if (!wtCurrentTicketId) return;
    if (!confirm('Финализировать акт? Изменения будут невозможны.')) return;
    api('POST', '/api/agro-sales/weight-tickets/' + wtCurrentTicketId + '/finalize').then(function(d) {
        if (d.success) {
            toast('Акт финализирован', 'success');
            closeModal('wtDetailModal');
            loadTickets();
        } else {
            toast(d.error || 'Ошибка', 'error');
        }
    });
};

window.wtPrint = function() {
    if (!wtCurrentTicketId) return;
    window.open('/UNA.md/orasldev/agro-document/' + wtCurrentTicketId + '?type=weight_ticket', '_blank');
};
```

- [ ] **Step 6: Update loadRefs to populate weighing selects**

In the existing `loadRefs` function, after loading customers/warehouses/items, add:

```javascript
// Also fill weighing selects
fillSel('wtCustomer', refs.customers, 'id', 'name', 'Выбрать клиента');
fillSel('wtWarehouse', refs.warehouses, 'id', 'name', 'Выбрать склад');
fillSel('wtItem', refs.items, 'id', 'name', 'Выбрать продукт');
```

And in the initial `loadRefs` callback, add `loadTickets()`:

```javascript
loadRefs(function() {
    loadDocs();
    loadAvailStock();
    loadTickets();
    // Fill sales docs in weighing selector
    api('GET', '/api/agro-sales/documents').then(function(d) {
        var docs = (d.data || []).filter(function(r) { return r.status === 'draft' || r.status === 'confirmed'; });
        fillSel('wtSalesDoc', docs, 'id', 'doc_number', '-- Без привязки --');
    });
});
```

- [ ] **Step 7: Commit**

```
git add templates/agro_sales.html
git commit -m "feat(agro): add weighing touchscreen + ticket journal to sales module"
```

---

## Task 6: Field Template — D-Code Panel + Photo Cells + Enhanced Scoring

**Files:**
- Modify: `templates/agro_field.html` (inspection section, lines 1214-1278)

- [ ] **Step 1: Add D-code CSS**

In the `<style>` block (before `</style>`), add:

```css
/* ---------- D-Code Defect Panel ---------- */
.dcode-panel { margin: 16px 0; }
.dcode-group { margin-bottom: 12px; }
.dcode-group-title { font-size: 11px; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 6px; font-weight: 700; }
.dcode-group-title.critical { color: #e94560; }
.dcode-group-title.major { color: #f59e0b; }
.dcode-group-title.minor { color: #a3a3a3; }
.dcode-btns { display: flex; flex-wrap: wrap; gap: 6px; }
.dcode-btn {
    padding: 8px 12px; border-radius: 8px; border: 2px solid #333366;
    background: #1a1a2e; color: #b0b0c8; font-size: 12px; font-weight: 600;
    cursor: pointer; transition: all .15s; touch-action: manipulation; min-height: 40px;
}
.dcode-btn:hover { border-color: #555; }
.dcode-btn.active.critical { border-color: #e94560; background: #e9456030; color: #ff8fa3; }
.dcode-btn.active.major { border-color: #f59e0b; background: #f59e0b22; color: #fcd34d; }
.dcode-btn.active.minor { border-color: #a3a3a3; background: #a3a3a322; color: #d4d4d4; }
/* Photo cells */
.photo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; margin: 12px 0; }
.photo-cell {
    border: 1px dashed #333366; border-radius: 8px; padding: 8px; text-align: center;
    font-size: 11px; color: #8888aa; min-height: 80px; cursor: pointer;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    transition: border-color .15s;
}
.photo-cell:hover { border-color: var(--accent); }
.photo-cell.has-photo { border-color: var(--accent); border-style: solid; }
.photo-cell img { max-width: 100%; max-height: 60px; border-radius: 4px; }
/* Score progress bar */
.score-bar { height: 12px; background: #333; border-radius: 6px; overflow: hidden; flex: 1; }
.score-bar-fill { height: 100%; border-radius: 6px; transition: width .3s, background .3s; }
```

- [ ] **Step 2: Add D-code panel + photo cells to inspection form**

Replace the inspection form content between the closing `</div>` of the 4-grid checklist (after line 1258) and the comment field (line 1261). Insert after the pesticide card's closing `</div></div>` (line 1258-1259):

```html
        </div><!-- /grid -->

        <!-- D-Code Defect Panel -->
        <div class="card" style="background:var(--bg);padding:14px;margin-top:12px;">
            <h4 style="font-size:12px;color:var(--text-muted);margin-bottom:10px;text-transform:uppercase;">Шкала дефектов / Scala defecte (D-коды)</h4>
            <div class="dcode-panel">
                <div class="dcode-group">
                    <div class="dcode-group-title critical">Критические / Critice</div>
                    <div class="dcode-btns">
                        <button class="dcode-btn critical" data-dcode="D01" data-checks="serious_ok" onclick="toggleDcode(this)">D01 Гниль</button>
                        <button class="dcode-btn critical" data-dcode="D02" data-checks="serious_ok" onclick="toggleDcode(this)">D02 Плесень</button>
                        <button class="dcode-btn critical" data-dcode="D03" data-checks="serious_ok" onclick="toggleDcode(this)">D03 Вредители</button>
                        <button class="dcode-btn critical" data-dcode="D04" data-checks="serious_ok" onclick="toggleDcode(this)">D04 Запах</button>
                        <button class="dcode-btn critical" data-dcode="D05" data-checks="class_ok" onclick="toggleDcode(this)">D05 Класс</button>
                        <button class="dcode-btn critical" data-dcode="D06" data-checks="temp_ok" onclick="toggleDcode(this)">D06 Темп.</button>
                        <button class="dcode-btn critical" data-dcode="D07" data-checks="lab_ok" onclick="toggleDcode(this)">D07 Лаб.</button>
                        <button class="dcode-btn critical" data-dcode="D08" data-checks="phyto_ok" onclick="toggleDcode(this)">D08 Фито</button>
                        <button class="dcode-btn critical" data-dcode="D09" data-checks="trace_ok" onclick="toggleDcode(this)">D09 Трассир.</button>
                    </div>
                </div>
                <div class="dcode-group">
                    <div class="dcode-group-title major">Значительные / Majore</div>
                    <div class="dcode-btns">
                        <button class="dcode-btn major" data-dcode="D10" data-checks="minor_ok" onclick="toggleDcode(this)">D10 Нажимы</button>
                        <button class="dcode-btn major" data-dcode="D11" data-checks="minor_ok" onclick="toggleDcode(this)">D11 Деформ.</button>
                        <button class="dcode-btn major" data-dcode="D12" data-checks="calibre_ok,below_min_ok" onclick="toggleDcode(this)">D12 Калибр</button>
                        <button class="dcode-btn major" data-dcode="D13" data-checks="mixed_ok" onclick="toggleDcode(this)">D13 Разнокал.</button>
                        <button class="dcode-btn major" data-dcode="D14" data-checks="brix_ok" onclick="toggleDcode(this)">D14 Brix</button>
                    </div>
                </div>
                <div class="dcode-group">
                    <div class="dcode-group-title minor">Незначительные / Minore</div>
                    <div class="dcode-btns">
                        <button class="dcode-btn minor" data-dcode="D20" data-checks="minor_ok" onclick="toggleDcode(this)">D20 Кожица</button>
                        <button class="dcode-btn minor" data-dcode="D21" data-checks="minor_ok" onclick="toggleDcode(this)">D21 Листья</button>
                        <button class="dcode-btn minor" data-dcode="D22" data-checks="label_ok" onclick="toggleDcode(this)">D22 Маркир.</button>
                        <button class="dcode-btn minor" data-dcode="D23" data-checks="pack_ok" onclick="toggleDcode(this)">D23 Упаковка</button>
                        <button class="dcode-btn minor" data-dcode="D24" data-checks="single_residue_ok" onclick="toggleDcode(this)">D24 Резид.1</button>
                        <button class="dcode-btn minor" data-dcode="D25" data-checks="total_residue_ok" onclick="toggleDcode(this)">D25 Резид.∑</button>
                        <button class="dcode-btn minor" data-dcode="D26" data-checks="glyphosate_ok" onclick="toggleDcode(this)">D26 Глифос.</button>
                        <button class="dcode-btn minor" data-dcode="D27" data-checks="actives_ok" onclick="toggleDcode(this)">D27 В.в.</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Photo cells for defect evidence -->
        <div class="card" style="background:var(--bg);padding:14px;margin-top:8px;">
            <h4 style="font-size:12px;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase;">Фото дефектов / Foto defecte</h4>
            <div class="photo-grid" id="inspPhotoGrid">
                <!-- Populated dynamically when D-codes are activated -->
                <div class="photo-cell" style="border-style:dashed;color:#555;">Нажмите D-код для фото</div>
            </div>
            <input type="file" id="inspPhotoInput" accept="image/*" capture="environment" style="display:none;" onchange="inspPhotoCapture(this)">
        </div>
```

- [ ] **Step 3: Enhance live score display**

Replace the existing `inspScorePreview` div (lines 1264-1273) with:

```html
        <div id="inspScorePreview" style="margin-top:16px;padding:16px;border-radius:10px;background:var(--bg);display:flex;align-items:center;gap:20px;">
            <div style="text-align:center;min-width:80px;">
                <div style="font-size:42px;font-weight:800;" id="inspScoreValue">--</div>
                <div style="font-size:11px;color:var(--text-muted);">БАЛЛ / SCOR</div>
            </div>
            <div style="flex:1;">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
                    <div class="score-bar"><div class="score-bar-fill" id="inspScoreBar" style="width:0%;background:#333;"></div></div>
                </div>
                <div id="inspDecisionBadge" style="font-size:16px;font-weight:700;padding:8px 16px;border-radius:8px;display:inline-block;background:#333;color:#888;">Заполните чек-лист</div>
                <div id="inspCriticalWarning" style="font-size:12px;color:var(--danger);margin-top:6px;display:none;"></div>
                <div id="inspDcodesSummary" style="font-size:12px;color:var(--text-muted);margin-top:6px;"></div>
            </div>
        </div>
```

- [ ] **Step 4: Add D-code JavaScript functions**

In the `<script>` section, add:

```javascript
/* ==================== D-CODE DEFECT PANEL ==================== */
var activeDcodes = {};
var inspPhotos = {};
var inspPhotoTarget = null;

// Scoring weights (loaded from API)
var scoringWeights = {};
var criticalChecks = [];
(function loadScoringConfig() {
    fetch('/api/agro-field/scoring-config')
        .then(function(r) { return r.json(); })
        .then(function(d) {
            if (d.success && d.data) {
                scoringWeights = d.data.weights || {};
                criticalChecks = d.data.critical || [];
            }
        }).catch(function() {
            // Fallback hardcoded
            scoringWeights = {CLASS_OK:10,CALIBRE_OK:8,BELOW_MIN_OK:5,MINOR_OK:8,SERIOUS_OK:15,MIXED_OK:4,BRIX_OK:5,TEMP_OK:10,LAB_OK:8,PHYTO_OK:4,TRACE_OK:6,PACK_OK:3,LABEL_OK:2,ACTIVES_OK:2,SINGLE_RESIDUE_OK:2,TOTAL_RESIDUE_OK:2,GLYPHOSATE_OK:1};
            criticalChecks = ['CLASS_OK','SERIOUS_OK','TEMP_OK','LAB_OK','PHYTO_OK','TRACE_OK'];
        });
})();

window.toggleDcode = function(btn) {
    var dcode = btn.getAttribute('data-dcode');
    var checks = btn.getAttribute('data-checks').split(',');
    var isActive = btn.classList.toggle('active');
    activeDcodes[dcode] = isActive;

    // Auto-uncheck corresponding scoring checkboxes
    checks.forEach(function(chk) {
        var cb = document.getElementById('chk-' + chk);
        if (cb) {
            if (isActive) cb.checked = false;
            // Don't auto-check when deactivating — let operator decide
        }
    });

    updateInspPhotoGrid();
    recalcScore();
};

function updateInspPhotoGrid() {
    var grid = document.getElementById('inspPhotoGrid');
    var activeList = Object.keys(activeDcodes).filter(function(k) { return activeDcodes[k]; });
    if (!activeList.length) {
        grid.innerHTML = '<div class="photo-cell" style="border-style:dashed;color:#555;">Нажмите D-код для фото</div>';
        return;
    }
    grid.innerHTML = activeList.map(function(dc) {
        var hasPhoto = inspPhotos[dc];
        var content = hasPhoto
            ? '<img src="' + inspPhotos[dc] + '" alt="' + dc + '">'
            : '<span style="font-size:24px;">📷</span>';
        return '<div class="photo-cell ' + (hasPhoto ? 'has-photo' : '') + '" onclick="inspStartPhoto(\'' + dc + '\')">' +
            '<div style="font-weight:700;font-size:11px;margin-bottom:4px;">' + dc + '</div>' +
            content + '</div>';
    }).join('');
}

window.inspStartPhoto = function(dcode) {
    inspPhotoTarget = dcode;
    document.getElementById('inspPhotoInput').click();
};

window.inspPhotoCapture = function(input) {
    if (input.files && input.files[0] && inspPhotoTarget) {
        var reader = new FileReader();
        reader.onload = function(e) {
            inspPhotos[inspPhotoTarget] = e.target.result;
            updateInspPhotoGrid();
        };
        reader.readAsDataURL(input.files[0]);
    }
};

function recalcScore() {
    var totalWeight = 0, earned = 0;
    var critFail = false, failedCritical = [];

    Object.keys(scoringWeights).forEach(function(code) {
        var w = scoringWeights[code];
        totalWeight += w;
        var cb = document.getElementById('chk-' + code.toLowerCase());
        var isPass = cb ? cb.checked : false;
        if (isPass) earned += w;
        if (!isPass && criticalChecks.indexOf(code) !== -1) {
            critFail = true;
            failedCritical.push(code);
        }
    });

    var freshness = parseFloat(document.getElementById('insp-freshness_score').value) || 0;
    var score = totalWeight > 0 ? Math.round((earned / totalWeight) * 100 + freshness) : 0;
    if (score > 100) score = 100;

    // Update display
    document.getElementById('inspScoreValue').textContent = score;
    var bar = document.getElementById('inspScoreBar');
    bar.style.width = score + '%';

    var badge = document.getElementById('inspDecisionBadge');
    var warn = document.getElementById('inspCriticalWarning');
    var summary = document.getElementById('inspDcodesSummary');

    if (critFail) {
        badge.textContent = 'REJECT / ОТКАЗ';
        badge.style.background = '#e9456040'; badge.style.color = '#ff8fa3';
        bar.style.background = '#e94560';
        warn.style.display = ''; warn.textContent = 'Критические: ' + failedCritical.join(', ');
    } else if (score >= 95) {
        badge.textContent = 'ACCEPT / ПРИНЯТО';
        badge.style.background = '#53d76930'; badge.style.color = '#53d769';
        bar.style.background = '#53d769';
        warn.style.display = 'none';
    } else if (score >= 85) {
        badge.textContent = 'ACCEPT WITH SORTING / С СОРТИРОВКОЙ';
        badge.style.background = '#f59e0b30'; badge.style.color = '#fcd34d';
        bar.style.background = '#f59e0b';
        warn.style.display = 'none';
    } else {
        badge.textContent = 'REJECT / ОТКАЗ';
        badge.style.background = '#e9456040'; badge.style.color = '#ff8fa3';
        bar.style.background = '#e94560';
        warn.style.display = 'none';
    }

    // D-codes summary
    var activeList = Object.keys(activeDcodes).filter(function(k) { return activeDcodes[k]; });
    summary.textContent = activeList.length ? 'Дефекты: ' + activeList.join(', ') : '';
}

// Hook recalcScore to all checkboxes
document.querySelectorAll('[id^="chk-"]').forEach(function(cb) {
    cb.addEventListener('change', recalcScore);
});
document.getElementById('insp-freshness_score').addEventListener('input', recalcScore);
```

- [ ] **Step 5: Commit**

```
git add templates/agro_field.html
git commit -m "feat(agro): add D-code defect panel, photo cells, enhanced scoring to field inspections"
```

---

## Task 7: Supplier Pack — Align with AGRO Scoring System

**Files:**
- Modify: `docs/AGRO/achizitie standard/dipp_fruct_supplier_pack.html`

- [ ] **Step 1: Rewrite defect coding table**

Replace the existing defect coding section with the expanded D01–D27 table aligned with AGRO scoring weights (see spec section 2.1 for full mapping). Update the decision thresholds to match:

- ACCEPT: score ≥ 95, all critical pass
- ACCEPT_WITH_SORTING: score ≥ 85 (accept_min_score), all critical pass
- REJECT: any critical fail OR score < 85

Add note: "Коды дефектов D01–D27 синхронизированы с системой скоринга AGRO модуля (17-точечная взвешенная оценка). Профили приёмки настраиваются в Admin → Acceptance Profiles для каждой торговой сети."

- [ ] **Step 2: Add AGRO scoring reference section**

Add a new section "Связь с системой AGRO / Legătura cu sistemul AGRO" explaining:
- D-codes map to scoring checks in the acceptance module
- Scoring weights total 95 + freshness (0-5) = max 100
- Critical checks (6): auto-reject on fail
- Profiles `KAUFLAND`, `METRO`, `LINELLA` in `AGRO_ACCEPTANCE_PROFILES`

- [ ] **Step 3: Commit**

```
git add "docs/AGRO/achizitie standard/dipp_fruct_supplier_pack.html"
git commit -m "feat(agro): align supplier pack defect codes with AGRO scoring system"
```

---

## Task 8: Deploy and Verify

- [ ] **Step 1: Verify localhost**

```bash
# Check sales weighing page loads
curl -s -o /dev/null -w "%{http_code}" "http://localhost:3003/UNA.md/orasldev/agro-sales" -b "session=test"
# Expected: 302 (auth redirect = route works)

# Check scoring config API
curl -s -o /dev/null -w "%{http_code}" "http://localhost:3003/api/agro-field/scoring-config" -b "session=test"
# Expected: 302 or 200

# Check weight ticket API
curl -s -o /dev/null -w "%{http_code}" "http://localhost:3003/api/agro-sales/weight-tickets" -b "session=test"
# Expected: 302 or 200
```

- [ ] **Step 2: Deploy changed files to remote**

```bash
SSH_KEY=~/Downloads/ssh-key-2024-10-06.key
REMOTE=ubuntu@92.5.3.187

scp -i $SSH_KEY models/agro_oracle_store.py $REMOTE:/home/ubuntu/artgranit/models/
scp -i $SSH_KEY controllers/agro_sales_controller.py $REMOTE:/home/ubuntu/artgranit/controllers/
scp -i $SSH_KEY app.py $REMOTE:/home/ubuntu/artgranit/
scp -i $SSH_KEY templates/agro_sales.html $REMOTE:/home/ubuntu/artgranit/templates/
scp -i $SSH_KEY templates/agro_field.html $REMOTE:/home/ubuntu/artgranit/templates/
scp -i $SSH_KEY sql/41_agro_weight_tickets.sql $REMOTE:/home/ubuntu/artgranit/sql/
scp -i $SSH_KEY deploy_oracle_objects.py $REMOTE:/home/ubuntu/artgranit/
scp -i $SSH_KEY "docs/AGRO/achizitie standard/dipp_fruct_supplier_pack.html" $REMOTE:"/home/ubuntu/artgranit/docs/AGRO/achizitie standard/"
```

- [ ] **Step 3: Restart remote app**

```bash
ssh -i $SSH_KEY $REMOTE "cd /home/ubuntu/artgranit && sudo kill \$(pgrep -f 'python3 app.py') 2>/dev/null; sleep 2; source venv/bin/activate && nohup python3 app.py > app.log 2>&1 &"
```

- [ ] **Step 4: Verify remote**

```bash
curl -s -o /dev/null -w "%{http_code}" "http://92.5.3.187:8000/UNA.md/orasldev/agro-sales"
# Expected: 302
```

- [ ] **Step 5: Push to git**

```bash
git push origin feature/agro-module
```

- [ ] **Step 6: Commit final**

```
git commit --allow-empty -m "deploy: AGRO sales weighing module + field D-codes + supplier pack alignment"
```
