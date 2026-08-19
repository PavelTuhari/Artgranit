# PECO Fuel Retail ERP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fuel retail ERP for a 46-station network — four fuel grades, self-service and attendant dispensing, cash and MIA QR payment, tanker delivery intake, and ERP-grade shift close with three-way variance reconciliation.

**Architecture:** Meter-authoritative — the per-nozzle totalizer is the source of truth, not the transaction sum. Business logic lives in pure functions that take and return dicts, so it is unit-testable without a live Oracle. Persistence is isolated in `models/peco_oracle_store.py`; nothing else issues SQL.

**Tech Stack:** Python 3.12, Flask, `oracledb` (thin mode, wallet via `WALLET_DIR`), Jinja2 templates, vanilla JS front end. Tests with `pytest`, Oracle fully mocked.

**Spec:** `docs/superpowers/specs/2026-08-19-peco-fuel-retail-design.md`

## Global Constraints

- Oracle object prefix is `PECO_` — every table, sequence, and view.
- No SQLite, no `data/*.json`, no generic key-value tables. Oracle is the only authoritative store.
- All UI routes live under `/UNA.md/orasldev/`.
- SQL files use numbers `100_`+ (`99_plg_vector.sql` is the current maximum) and must be registered in `deploy_oracle_objects.py`.
- Routes are registered directly in `app.py` — this codebase does not use Flask blueprints.
- Stores use `with DatabaseModel() as db:` and call `db.connection.commit()` explicitly after DML.
- Every store method returns `{"success": bool, ...}` and never raises to the caller.
- Tests never touch a live Oracle. Mock `models.peco_oracle_store.DatabaseModel`.
- Money is `NUMBER(12,2)`; liters and meter readings are `NUMBER(14,3)`.
- Comments and UI copy in Russian, matching the surrounding modules.
- After any remote deploy: `curl -I https://nufarul.eminescu.md/login` must return 200.

---

## File Structure

| File | Responsibility |
|---|---|
| `sql/100_peco_tables.sql` | Refs, sequences, master data, prices |
| `sql/101_peco_ops_tables.sql` | Shifts, shift meters, transactions |
| `sql/102_peco_inventory_tables.sql` | Deliveries, delivery items, tank dips, event log |
| `sql/103_peco_views.sql` | `V_PECO_*` reporting views |
| `sql/104_peco_demo_data.sql` | Reference seed + one demo station |
| `models/peco_oracle_store.py` | All `PECO_*` SQL. No business rules. |
| `models/peco_shift.py` | Shift lifecycle + variance math (pure functions) |
| `models/peco_txn.py` | Dispense state machine (pure functions) |
| `models/peco_inventory.py` | Tank ledger, delivery intake |
| `controllers/peco_controller.py` | Request handling, auth, response shaping |
| `templates/peco_pump.html` | Front office — dispensing |
| `templates/peco_shift.html` | Station operator console |
| `templates/peco_admin.html` | Back office |
| `docs/PECO/TZ.html` | Documentation page with entry buttons |
| `tests/test_peco.py` | Unit tests, Oracle mocked |

**Stages:** A schema (1–4) → B store (5–6) → C shift core (7–9) → D dispensing (10–11) → E inventory (12–13) → F routes (14–15) → G UI (16–18) → H docs (19–20).

Stages C and D are the highest-risk work and are written test-first with complete test code.

---

## Stage A — Oracle Schema

### Task 1: Reference tables, sequences, and master data

**Files:**
- Create: `sql/100_peco_tables.sql`
- Modify: `deploy_oracle_objects.py:190` (append to the `order` list after `"99_plg_vector.sql"`)

**Interfaces:**
- Consumes: nothing.
- Produces: tables `PECO_REF_FUEL_GRADES`, `PECO_REF_PAY_METHODS`, `PECO_REF_SHIFT_STATUS`, `PECO_REF_TXN_STATUS`, `PECO_STATIONS`, `PECO_TANKS`, `PECO_PUMPS`, `PECO_NOZZLES`, `PECO_EMPLOYEES`, `PECO_PRICES`; sequences `PECO_<NAME>_SEQ` for each non-reference table.

- [ ] **Step 1: Create the DDL file**

```sql
-- ============================================================
-- PECO: розничная продажа топлива в сети АЗС.
-- Справочники, мастер-данные, цены.
-- Спецификация: docs/superpowers/specs/2026-08-19-peco-fuel-retail-design.md
-- Префикс объектов: PECO_
-- ============================================================

CREATE SEQUENCE PECO_STATIONS_SEQ  START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_TANKS_SEQ     START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_PUMPS_SEQ     START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_NOZZLES_SEQ   START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_EMPLOYEES_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_PRICES_SEQ    START WITH 1 INCREMENT BY 1 NOCACHE;

-- ==================== Справочники ====================

-- Виды топлива: A92, A95, A98, DIESEL
CREATE TABLE PECO_REF_FUEL_GRADES (
  CODE       VARCHAR2(10)  NOT NULL,
  NAME       VARCHAR2(60)  NOT NULL,
  COLOR      VARCHAR2(20),
  DENSITY    NUMBER(6,4),
  SORT_ORDER NUMBER DEFAULT 0,
  CONSTRAINT PK_PECO_REF_FUEL_GRADES PRIMARY KEY (CODE)
);

-- Способы оплаты: CASH, MIA_QR
CREATE TABLE PECO_REF_PAY_METHODS (
  CODE          VARCHAR2(10)  NOT NULL,
  NAME          VARCHAR2(60)  NOT NULL,
  -- 1 = попадает в кассовую сверку, 0 = безналичный поток
  IS_CASH       NUMBER(1) DEFAULT 0 NOT NULL,
  SORT_ORDER    NUMBER DEFAULT 0,
  CONSTRAINT PK_PECO_REF_PAY_METHODS PRIMARY KEY (CODE)
);

-- Статусы смены: OPEN, CLOSING, CLOSED, DISPUTED
CREATE TABLE PECO_REF_SHIFT_STATUS (
  CODE       VARCHAR2(15)  NOT NULL,
  NAME       VARCHAR2(60)  NOT NULL,
  SORT_ORDER NUMBER DEFAULT 0,
  CONSTRAINT PK_PECO_REF_SHIFT_STATUS PRIMARY KEY (CODE)
);

-- Статусы транзакции: AUTHORIZED, DISPENSING, AWAITING_PAY, PAID, VOIDED
CREATE TABLE PECO_REF_TXN_STATUS (
  CODE       VARCHAR2(15)  NOT NULL,
  NAME       VARCHAR2(60)  NOT NULL,
  SORT_ORDER NUMBER DEFAULT 0,
  CONSTRAINT PK_PECO_REF_TXN_STATUS PRIMARY KEY (CODE)
);

-- ==================== Мастер-данные ====================

CREATE TABLE PECO_STATIONS (
  ID       NUMBER        NOT NULL,
  CODE     VARCHAR2(20)  NOT NULL,
  NAME     VARCHAR2(150) NOT NULL,
  ADDRESS  VARCHAR2(300),
  REGION   VARCHAR2(100),
  TZ_NAME  VARCHAR2(60)  DEFAULT 'Europe/Chisinau',
  ACTIVE   NUMBER(1)     DEFAULT 1 NOT NULL,
  CONSTRAINT PK_PECO_STATIONS PRIMARY KEY (ID),
  CONSTRAINT UQ_PECO_STATIONS_CODE UNIQUE (CODE)
);

-- Резервуар: один на вид топлива на станции
CREATE TABLE PECO_TANKS (
  ID          NUMBER        NOT NULL,
  STATION_ID  NUMBER        NOT NULL,
  GRADE_CODE  VARCHAR2(10)  NOT NULL,
  CODE        VARCHAR2(20)  NOT NULL,
  CAPACITY_L  NUMBER(14,3)  NOT NULL,
  CURRENT_L   NUMBER(14,3)  DEFAULT 0 NOT NULL,
  MIN_ALARM_L NUMBER(14,3)  DEFAULT 0 NOT NULL,
  ACTIVE      NUMBER(1)     DEFAULT 1 NOT NULL,
  CONSTRAINT PK_PECO_TANKS PRIMARY KEY (ID),
  CONSTRAINT UQ_PECO_TANKS UNIQUE (STATION_ID, CODE),
  CONSTRAINT FK_PECO_TANKS_ST FOREIGN KEY (STATION_ID) REFERENCES PECO_STATIONS (ID),
  CONSTRAINT FK_PECO_TANKS_GR FOREIGN KEY (GRADE_CODE) REFERENCES PECO_REF_FUEL_GRADES (CODE)
);

CREATE TABLE PECO_PUMPS (
  ID           NUMBER       NOT NULL,
  STATION_ID   NUMBER       NOT NULL,
  CODE         VARCHAR2(20) NOT NULL,
  SELF_SERVICE NUMBER(1)    DEFAULT 1 NOT NULL,
  ACTIVE       NUMBER(1)    DEFAULT 1 NOT NULL,
  CONSTRAINT PK_PECO_PUMPS PRIMARY KEY (ID),
  CONSTRAINT UQ_PECO_PUMPS UNIQUE (STATION_ID, CODE),
  CONSTRAINT FK_PECO_PUMPS_ST FOREIGN KEY (STATION_ID) REFERENCES PECO_STATIONS (ID)
);

-- Пистолет. Счётчик (тотализатор) живёт ЗДЕСЬ, не на колонке:
-- колонка с несколькими пистолетами иначе теряет разбивку по видам топлива.
CREATE TABLE PECO_NOZZLES (
  ID           NUMBER       NOT NULL,
  PUMP_ID      NUMBER       NOT NULL,
  TANK_ID      NUMBER       NOT NULL,
  GRADE_CODE   VARCHAR2(10) NOT NULL,
  CODE         VARCHAR2(20) NOT NULL,
  METER_TOTAL  NUMBER(14,3) DEFAULT 0 NOT NULL,
  ACTIVE       NUMBER(1)    DEFAULT 1 NOT NULL,
  CONSTRAINT PK_PECO_NOZZLES PRIMARY KEY (ID),
  CONSTRAINT UQ_PECO_NOZZLES UNIQUE (PUMP_ID, CODE),
  CONSTRAINT FK_PECO_NOZZLES_PU FOREIGN KEY (PUMP_ID) REFERENCES PECO_PUMPS (ID),
  CONSTRAINT FK_PECO_NOZZLES_TA FOREIGN KEY (TANK_ID) REFERENCES PECO_TANKS (ID),
  CONSTRAINT FK_PECO_NOZZLES_GR FOREIGN KEY (GRADE_CODE) REFERENCES PECO_REF_FUEL_GRADES (CODE)
);

-- PIN хешируется PBKDF2-HMAC-SHA256 с солью на сотрудника. Голый SHA-256
-- от четырёхзначного PIN подбирается перебором мгновенно, а этот PIN
-- подтверждает расхождение по кассе — то есть закрывает недостачу денег.
CREATE TABLE PECO_EMPLOYEES (
  ID         NUMBER        NOT NULL,
  STATION_ID NUMBER,
  FULL_NAME  VARCHAR2(150) NOT NULL,
  ROLE_CODE  VARCHAR2(15)  DEFAULT 'ATTENDANT' NOT NULL,
  PIN_SALT   VARCHAR2(64)  NOT NULL,
  PIN_HASH   VARCHAR2(128) NOT NULL,
  ACTIVE     NUMBER(1)     DEFAULT 1 NOT NULL,
  CONSTRAINT PK_PECO_EMPLOYEES PRIMARY KEY (ID),
  CONSTRAINT CK_PECO_EMP_ROLE CHECK (ROLE_CODE IN ('ATTENDANT','MANAGER','ADMIN')),
  CONSTRAINT FK_PECO_EMP_ST FOREIGN KEY (STATION_ID) REFERENCES PECO_STATIONS (ID)
);

-- Цена никогда не обновляется на месте: изменение закрывает старую строку
-- (VALID_TO) и вставляет новую. Действующая цена = VALID_TO IS NULL.
CREATE TABLE PECO_PRICES (
  ID          NUMBER        NOT NULL,
  STATION_ID  NUMBER        NOT NULL,
  GRADE_CODE  VARCHAR2(10)  NOT NULL,
  PRICE       NUMBER(12,2)  NOT NULL,
  VALID_FROM  TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
  VALID_TO    TIMESTAMP,
  CONSTRAINT PK_PECO_PRICES PRIMARY KEY (ID),
  CONSTRAINT FK_PECO_PRICES_ST FOREIGN KEY (STATION_ID) REFERENCES PECO_STATIONS (ID),
  CONSTRAINT FK_PECO_PRICES_GR FOREIGN KEY (GRADE_CODE) REFERENCES PECO_REF_FUEL_GRADES (CODE)
);

CREATE INDEX IX_PECO_PRICES_CUR ON PECO_PRICES (STATION_ID, GRADE_CODE, VALID_TO);
CREATE INDEX IX_PECO_TANKS_ST   ON PECO_TANKS (STATION_ID);
CREATE INDEX IX_PECO_NOZ_TANK   ON PECO_NOZZLES (TANK_ID);
```

- [ ] **Step 2: Register the file in the deploy script**

In `deploy_oracle_objects.py`, in the `order` list, add after `"99_plg_vector.sql",`:

```python
        "100_peco_tables.sql",
```

- [ ] **Step 3: Verify the SQL parses**

Run: `python -c "p=open('sql/100_peco_tables.sql').read(); assert p.count('CREATE TABLE')==9, p.count('CREATE TABLE'); assert p.count('CREATE SEQUENCE')==6; print('ok')"`

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add sql/100_peco_tables.sql deploy_oracle_objects.py
git commit -m "PECO: справочники, мастер-данные, цены (DDL)"
```

---

### Task 2: Operational tables — shifts, shift meters, transactions

**Files:**
- Create: `sql/101_peco_ops_tables.sql`
- Modify: `deploy_oracle_objects.py` (`order` list, after `"100_peco_tables.sql"`)

**Interfaces:**
- Consumes: `PECO_STATIONS`, `PECO_EMPLOYEES`, `PECO_NOZZLES` from Task 1.
- Produces: `PECO_SHIFTS`, `PECO_SHIFT_METERS`, `PECO_TXN` and their sequences.

- [ ] **Step 1: Create the DDL file**

```sql
-- ============================================================
-- PECO: операционные таблицы — смены, показания счётчиков, транзакции.
-- ============================================================

CREATE SEQUENCE PECO_SHIFTS_SEQ       START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_SHIFT_METERS_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_TXN_SEQ          START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE TABLE PECO_SHIFTS (
  ID              NUMBER       NOT NULL,
  STATION_ID      NUMBER       NOT NULL,
  STATUS_CODE     VARCHAR2(15) DEFAULT 'OPEN' NOT NULL,
  OPENED_AT       TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL,
  CLOSED_AT       TIMESTAMP,
  OPENED_BY       NUMBER       NOT NULL,
  CLOSED_BY       NUMBER,
  -- заполняются при закрытии
  CASH_DECLARED   NUMBER(12,2),
  CASH_EXPECTED   NUMBER(12,2),
  CASH_VARIANCE   NUMBER(12,2),
  LITER_VARIANCE  NUMBER(14,3),
  TANK_VARIANCE   NUMBER(14,3),
  -- PIN менеджера, подтвердившего расхождение выше допуска
  APPROVED_BY     NUMBER,
  NOTE            VARCHAR2(500),
  CONSTRAINT PK_PECO_SHIFTS PRIMARY KEY (ID),
  CONSTRAINT FK_PECO_SHIFTS_ST FOREIGN KEY (STATION_ID) REFERENCES PECO_STATIONS (ID),
  CONSTRAINT FK_PECO_SHIFTS_OB FOREIGN KEY (OPENED_BY)  REFERENCES PECO_EMPLOYEES (ID),
  CONSTRAINT FK_PECO_SHIFTS_CB FOREIGN KEY (CLOSED_BY)  REFERENCES PECO_EMPLOYEES (ID),
  CONSTRAINT FK_PECO_SHIFTS_AB FOREIGN KEY (APPROVED_BY) REFERENCES PECO_EMPLOYEES (ID),
  CONSTRAINT FK_PECO_SHIFTS_SS FOREIGN KEY (STATUS_CODE) REFERENCES PECO_REF_SHIFT_STATUS (CODE)
);

-- Опорная точка сверки: показания счётчика каждого пистолета за смену.
CREATE TABLE PECO_SHIFT_METERS (
  ID          NUMBER       NOT NULL,
  SHIFT_ID    NUMBER       NOT NULL,
  NOZZLE_ID   NUMBER       NOT NULL,
  METER_OPEN  NUMBER(14,3) NOT NULL,
  METER_CLOSE NUMBER(14,3),
  CONSTRAINT PK_PECO_SHIFT_METERS PRIMARY KEY (ID),
  CONSTRAINT UQ_PECO_SHIFT_METERS UNIQUE (SHIFT_ID, NOZZLE_ID),
  CONSTRAINT FK_PECO_SM_SH FOREIGN KEY (SHIFT_ID)  REFERENCES PECO_SHIFTS (ID),
  CONSTRAINT FK_PECO_SM_NO FOREIGN KEY (NOZZLE_ID) REFERENCES PECO_NOZZLES (ID)
);

CREATE TABLE PECO_TXN (
  ID              NUMBER       NOT NULL,
  SHIFT_ID        NUMBER       NOT NULL,
  NOZZLE_ID       NUMBER       NOT NULL,
  GRADE_CODE      VARCHAR2(10) NOT NULL,
  STATUS_CODE     VARCHAR2(15) DEFAULT 'AUTHORIZED' NOT NULL,
  LITERS          NUMBER(14,3) DEFAULT 0 NOT NULL,
  -- цена, по которой транзакция ФАКТИЧЕСКИ проведена; смена цены
  -- посреди смены не переписывает историю
  PRICE           NUMBER(12,2) NOT NULL,
  AMOUNT          NUMBER(12,2) DEFAULT 0 NOT NULL,
  PAY_METHOD      VARCHAR2(10),
  IS_SELF_SERVICE NUMBER(1)    DEFAULT 0 NOT NULL,
  AUTHORIZED_BY   NUMBER,
  MIA_REF         VARCHAR2(100),
  METER_START     NUMBER(14,3) NOT NULL,
  METER_END       NUMBER(14,3),
  STARTED_AT      TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL,
  PAID_AT         TIMESTAMP,
  CONSTRAINT PK_PECO_TXN PRIMARY KEY (ID),
  CONSTRAINT FK_PECO_TXN_SH FOREIGN KEY (SHIFT_ID)    REFERENCES PECO_SHIFTS (ID),
  CONSTRAINT FK_PECO_TXN_NO FOREIGN KEY (NOZZLE_ID)   REFERENCES PECO_NOZZLES (ID),
  CONSTRAINT FK_PECO_TXN_GR FOREIGN KEY (GRADE_CODE)  REFERENCES PECO_REF_FUEL_GRADES (CODE),
  CONSTRAINT FK_PECO_TXN_TS FOREIGN KEY (STATUS_CODE) REFERENCES PECO_REF_TXN_STATUS (CODE),
  CONSTRAINT FK_PECO_TXN_PM FOREIGN KEY (PAY_METHOD)  REFERENCES PECO_REF_PAY_METHODS (CODE),
  CONSTRAINT FK_PECO_TXN_AB FOREIGN KEY (AUTHORIZED_BY) REFERENCES PECO_EMPLOYEES (ID)
);

CREATE INDEX IX_PECO_TXN_SHIFT  ON PECO_TXN (SHIFT_ID, STATUS_CODE);
CREATE INDEX IX_PECO_TXN_NOZZLE ON PECO_TXN (NOZZLE_ID);
CREATE INDEX IX_PECO_SHIFTS_ST  ON PECO_SHIFTS (STATION_ID, STATUS_CODE);
```

- [ ] **Step 2: Register in the deploy script**

Add after `"100_peco_tables.sql",`:

```python
        "101_peco_ops_tables.sql",
```

- [ ] **Step 3: Verify**

Run: `python -c "p=open('sql/101_peco_ops_tables.sql').read(); assert p.count('CREATE TABLE')==3; assert 'METER_CLOSE' in p and 'IS_SELF_SERVICE' in p; print('ok')"`

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add sql/101_peco_ops_tables.sql deploy_oracle_objects.py
git commit -m "PECO: смены, показания счётчиков, транзакции (DDL)"
```

---

### Task 3: Inventory tables and event log

**Files:**
- Create: `sql/102_peco_inventory_tables.sql`
- Modify: `deploy_oracle_objects.py`

**Interfaces:**
- Consumes: `PECO_STATIONS`, `PECO_TANKS`, `PECO_EMPLOYEES`, `PECO_SHIFTS`.
- Produces: `PECO_DELIVERIES`, `PECO_DELIVERY_ITEMS`, `PECO_TANK_DIPS`, `PECO_EVENT_LOG`.

- [ ] **Step 1: Create the DDL file**

```sql
-- ============================================================
-- PECO: складской контур — приход цистерн, замеры, журнал событий.
-- ============================================================

CREATE SEQUENCE PECO_DELIVERIES_SEQ      START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_DELIVERY_ITEMS_SEQ  START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_TANK_DIPS_SEQ       START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_EVENT_LOG_SEQ       START WITH 1 INCREMENT BY 1 NOCACHE;

-- Шапка прихода цистерны. Одна цистерна имеет несколько отсеков и
-- заполняет несколько резервуаров за один визит — отсюда разделение
-- на шапку и строки.
CREATE TABLE PECO_DELIVERIES (
  ID           NUMBER        NOT NULL,
  STATION_ID   NUMBER        NOT NULL,
  SUPPLIER     VARCHAR2(150) NOT NULL,
  WAYBILL_NO   VARCHAR2(60)  NOT NULL,
  DRIVER_NAME  VARCHAR2(150),
  VEHICLE_NO   VARCHAR2(30),
  ARRIVED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
  ACCEPTED_AT  TIMESTAMP,
  ACCEPTED_BY  NUMBER,
  NOTE         VARCHAR2(500),
  CONSTRAINT PK_PECO_DELIVERIES PRIMARY KEY (ID),
  CONSTRAINT UQ_PECO_DELIV_WB UNIQUE (STATION_ID, WAYBILL_NO),
  CONSTRAINT FK_PECO_DELIV_ST FOREIGN KEY (STATION_ID)  REFERENCES PECO_STATIONS (ID),
  CONSTRAINT FK_PECO_DELIV_AB FOREIGN KEY (ACCEPTED_BY) REFERENCES PECO_EMPLOYEES (ID)
);

-- Строка прихода по одному резервуару. Хранятся и заявленный, и
-- фактически принятый объём — недолив проявляется немедленно.
CREATE TABLE PECO_DELIVERY_ITEMS (
  ID            NUMBER       NOT NULL,
  DELIVERY_ID   NUMBER       NOT NULL,
  TANK_ID       NUMBER       NOT NULL,
  GRADE_CODE    VARCHAR2(10) NOT NULL,
  LITERS_DOC    NUMBER(14,3) NOT NULL,
  LITERS_RECV   NUMBER(14,3) NOT NULL,
  TEMPERATURE_C NUMBER(6,2),
  DIP_BEFORE_L  NUMBER(14,3),
  DIP_AFTER_L   NUMBER(14,3),
  CONSTRAINT PK_PECO_DELIVERY_ITEMS PRIMARY KEY (ID),
  CONSTRAINT FK_PECO_DI_DE FOREIGN KEY (DELIVERY_ID) REFERENCES PECO_DELIVERIES (ID),
  CONSTRAINT FK_PECO_DI_TA FOREIGN KEY (TANK_ID)     REFERENCES PECO_TANKS (ID),
  CONSTRAINT FK_PECO_DI_GR FOREIGN KEY (GRADE_CODE)  REFERENCES PECO_REF_FUEL_GRADES (CODE)
);

-- Ручной замер уровня (метршток/щуп) — корректировка складского реестра.
CREATE TABLE PECO_TANK_DIPS (
  ID          NUMBER       NOT NULL,
  TANK_ID     NUMBER       NOT NULL,
  SHIFT_ID    NUMBER,
  MEASURED_L  NUMBER(14,3) NOT NULL,
  MEASURED_AT TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL,
  MEASURED_BY NUMBER,
  -- OPEN | CLOSE | DELIVERY | CONTROL
  DIP_KIND    VARCHAR2(15) DEFAULT 'CONTROL' NOT NULL,
  CONSTRAINT PK_PECO_TANK_DIPS PRIMARY KEY (ID),
  CONSTRAINT CK_PECO_DIP_KIND CHECK (DIP_KIND IN ('OPEN','CLOSE','DELIVERY','CONTROL')),
  CONSTRAINT FK_PECO_DIP_TA FOREIGN KEY (TANK_ID)     REFERENCES PECO_TANKS (ID),
  CONSTRAINT FK_PECO_DIP_SH FOREIGN KEY (SHIFT_ID)    REFERENCES PECO_SHIFTS (ID),
  CONSTRAINT FK_PECO_DIP_MB FOREIGN KEY (MEASURED_BY) REFERENCES PECO_EMPLOYEES (ID)
);

-- Append-only журнал событий модуля. НЕ хранилище состояния.
CREATE TABLE PECO_EVENT_LOG (
  ID          NUMBER        NOT NULL,
  STATION_ID  NUMBER,
  SHIFT_ID    NUMBER,
  EVENT_TYPE  VARCHAR2(40)  NOT NULL,
  ENTITY_TYPE VARCHAR2(30),
  ENTITY_ID   NUMBER,
  EMPLOYEE_ID NUMBER,
  PAYLOAD     VARCHAR2(2000),
  CREATED_AT  TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT PK_PECO_EVENT_LOG PRIMARY KEY (ID)
);

CREATE INDEX IX_PECO_EVL_ST  ON PECO_EVENT_LOG (STATION_ID, CREATED_AT);
CREATE INDEX IX_PECO_DIP_TA  ON PECO_TANK_DIPS (TANK_ID, MEASURED_AT);
CREATE INDEX IX_PECO_DI_DE   ON PECO_DELIVERY_ITEMS (DELIVERY_ID);
```

- [ ] **Step 2: Register in the deploy script**

Add after `"101_peco_ops_tables.sql",`:

```python
        "102_peco_inventory_tables.sql",
```

- [ ] **Step 3: Verify**

Run: `python -c "p=open('sql/102_peco_inventory_tables.sql').read(); assert p.count('CREATE TABLE')==4; assert 'LITERS_DOC' in p and 'LITERS_RECV' in p; print('ok')"`

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add sql/102_peco_inventory_tables.sql deploy_oracle_objects.py
git commit -m "PECO: приход цистерн, замеры, журнал событий (DDL)"
```

---

### Task 4: Views and seed data

**Files:**
- Create: `sql/103_peco_views.sql`, `sql/104_peco_demo_data.sql`
- Modify: `deploy_oracle_objects.py`

**Interfaces:**
- Consumes: all tables from Tasks 1–3.
- Produces: views `V_PECO_TANK_LEVELS`, `V_PECO_SHIFT_SUMMARY`, `V_PECO_STATION_DAILY`, `V_PECO_VARIANCE`; seeded reference rows and one demo station with 4 tanks, 2 pumps, 4 nozzles, 2 employees, 4 prices.

- [ ] **Step 1: Create the views file**

```sql
-- ============================================================
-- PECO: представления (V_PECO_*)
-- ============================================================

CREATE OR REPLACE VIEW V_PECO_TANK_LEVELS AS
SELECT t.ID            AS TANK_ID,
       t.STATION_ID,
       s.CODE          AS STATION_CODE,
       s.NAME          AS STATION_NAME,
       t.CODE          AS TANK_CODE,
       t.GRADE_CODE,
       g.NAME          AS GRADE_NAME,
       t.CAPACITY_L,
       t.CURRENT_L,
       t.MIN_ALARM_L,
       ROUND(t.CURRENT_L / NULLIF(t.CAPACITY_L, 0) * 100, 1) AS FILL_PCT,
       CASE WHEN t.CURRENT_L <= t.MIN_ALARM_L THEN 1 ELSE 0 END AS IS_LOW
  FROM PECO_TANKS t
  JOIN PECO_STATIONS s          ON s.ID = t.STATION_ID
  JOIN PECO_REF_FUEL_GRADES g   ON g.CODE = t.GRADE_CODE
 WHERE t.ACTIVE = 1;

-- Сводка смены: литры по счётчику, литры по транзакциям, деньги по
-- способам оплаты. MIA QR отделён от наличных намеренно.
CREATE OR REPLACE VIEW V_PECO_SHIFT_SUMMARY AS
SELECT sh.ID              AS SHIFT_ID,
       sh.STATION_ID,
       st.NAME            AS STATION_NAME,
       sh.STATUS_CODE,
       sh.OPENED_AT,
       sh.CLOSED_AT,
       (SELECT NVL(SUM(sm.METER_CLOSE - sm.METER_OPEN), 0)
          FROM PECO_SHIFT_METERS sm
         WHERE sm.SHIFT_ID = sh.ID
           AND sm.METER_CLOSE IS NOT NULL)              AS METER_DELTA,
       (SELECT NVL(SUM(t.LITERS), 0) FROM PECO_TXN t
         WHERE t.SHIFT_ID = sh.ID AND t.STATUS_CODE = 'PAID')  AS TXN_LITERS,
       (SELECT NVL(SUM(t.AMOUNT), 0) FROM PECO_TXN t
         WHERE t.SHIFT_ID = sh.ID AND t.STATUS_CODE = 'PAID'
           AND t.PAY_METHOD = 'CASH')                   AS CASH_AMOUNT,
       (SELECT NVL(SUM(t.AMOUNT), 0) FROM PECO_TXN t
         WHERE t.SHIFT_ID = sh.ID AND t.STATUS_CODE = 'PAID'
           AND t.PAY_METHOD = 'MIA_QR')                 AS MIA_AMOUNT,
       (SELECT COUNT(*) FROM PECO_TXN t
         WHERE t.SHIFT_ID = sh.ID
           AND t.STATUS_CODE IN ('DISPENSING','AWAITING_PAY')) AS OPEN_TXN_COUNT,
       sh.CASH_DECLARED,
       sh.CASH_EXPECTED,
       sh.CASH_VARIANCE,
       sh.LITER_VARIANCE,
       sh.TANK_VARIANCE
  FROM PECO_SHIFTS sh
  JOIN PECO_STATIONS st ON st.ID = sh.STATION_ID;

CREATE OR REPLACE VIEW V_PECO_STATION_DAILY AS
SELECT t.GRADE_CODE,
       sh.STATION_ID,
       st.NAME                     AS STATION_NAME,
       TRUNC(t.PAID_AT)            AS SALE_DAY,
       COUNT(*)                    AS TXN_COUNT,
       SUM(t.LITERS)               AS LITERS,
       SUM(t.AMOUNT)               AS AMOUNT,
       SUM(CASE WHEN t.IS_SELF_SERVICE = 1 THEN t.LITERS ELSE 0 END) AS SELF_LITERS
  FROM PECO_TXN t
  JOIN PECO_SHIFTS sh   ON sh.ID = t.SHIFT_ID
  JOIN PECO_STATIONS st ON st.ID = sh.STATION_ID
 WHERE t.STATUS_CODE = 'PAID'
 GROUP BY t.GRADE_CODE, sh.STATION_ID, st.NAME, TRUNC(t.PAID_AT);

-- Расхождения закрытых смен: три независимых показателя.
CREATE OR REPLACE VIEW V_PECO_VARIANCE AS
SELECT sh.ID           AS SHIFT_ID,
       sh.STATION_ID,
       st.NAME         AS STATION_NAME,
       sh.CLOSED_AT,
       sh.STATUS_CODE,
       sh.LITER_VARIANCE,
       sh.CASH_VARIANCE,
       sh.TANK_VARIANCE,
       e.FULL_NAME     AS CLOSED_BY_NAME
  FROM PECO_SHIFTS sh
  JOIN PECO_STATIONS st  ON st.ID = sh.STATION_ID
  LEFT JOIN PECO_EMPLOYEES e ON e.ID = sh.CLOSED_BY
 WHERE sh.STATUS_CODE IN ('CLOSED','DISPUTED');
```

- [ ] **Step 2: Create the seed data file**

```sql
-- ============================================================
-- PECO: справочные значения + одна демо-станция.
-- ============================================================

INSERT INTO PECO_REF_FUEL_GRADES (CODE, NAME, COLOR, DENSITY, SORT_ORDER) VALUES ('A92',    'Бензин А-92', '#16a34a', 0.7350, 1);
INSERT INTO PECO_REF_FUEL_GRADES (CODE, NAME, COLOR, DENSITY, SORT_ORDER) VALUES ('A95',    'Бензин А-95', '#2563eb', 0.7500, 2);
INSERT INTO PECO_REF_FUEL_GRADES (CODE, NAME, COLOR, DENSITY, SORT_ORDER) VALUES ('A98',    'Бензин А-98', '#9333ea', 0.7600, 3);
INSERT INTO PECO_REF_FUEL_GRADES (CODE, NAME, COLOR, DENSITY, SORT_ORDER) VALUES ('DIESEL', 'Дизель',      '#ca8a04', 0.8400, 4);

INSERT INTO PECO_REF_PAY_METHODS (CODE, NAME, IS_CASH, SORT_ORDER) VALUES ('CASH',   'Наличные на кассе', 1, 1);
INSERT INTO PECO_REF_PAY_METHODS (CODE, NAME, IS_CASH, SORT_ORDER) VALUES ('MIA_QR', 'MIA QR-код',        0, 2);

INSERT INTO PECO_REF_SHIFT_STATUS (CODE, NAME, SORT_ORDER) VALUES ('OPEN',     'Открыта',            1);
INSERT INTO PECO_REF_SHIFT_STATUS (CODE, NAME, SORT_ORDER) VALUES ('CLOSING',  'Закрывается',        2);
INSERT INTO PECO_REF_SHIFT_STATUS (CODE, NAME, SORT_ORDER) VALUES ('CLOSED',   'Закрыта',            3);
INSERT INTO PECO_REF_SHIFT_STATUS (CODE, NAME, SORT_ORDER) VALUES ('DISPUTED', 'Расхождение',        4);

INSERT INTO PECO_REF_TXN_STATUS (CODE, NAME, SORT_ORDER) VALUES ('AUTHORIZED',   'Авторизована',      1);
INSERT INTO PECO_REF_TXN_STATUS (CODE, NAME, SORT_ORDER) VALUES ('DISPENSING',   'Идёт налив',        2);
INSERT INTO PECO_REF_TXN_STATUS (CODE, NAME, SORT_ORDER) VALUES ('AWAITING_PAY', 'Ожидает оплаты',    3);
INSERT INTO PECO_REF_TXN_STATUS (CODE, NAME, SORT_ORDER) VALUES ('PAID',         'Оплачена',          4);
INSERT INTO PECO_REF_TXN_STATUS (CODE, NAME, SORT_ORDER) VALUES ('VOIDED',       'Аннулирована',      5);

-- Демо-станция
INSERT INTO PECO_STATIONS (ID, CODE, NAME, ADDRESS, REGION)
VALUES (PECO_STATIONS_SEQ.NEXTVAL, 'AZS-001', 'АЗС №1 Кишинёв-Центр', 'бул. Штефан чел Маре 1', 'Кишинёв');

INSERT INTO PECO_TANKS (ID, STATION_ID, GRADE_CODE, CODE, CAPACITY_L, CURRENT_L, MIN_ALARM_L)
SELECT PECO_TANKS_SEQ.NEXTVAL, s.ID, g.CODE, 'T-' || g.CODE, 20000, 12000, 2000
  FROM PECO_STATIONS s CROSS JOIN PECO_REF_FUEL_GRADES g
 WHERE s.CODE = 'AZS-001';

INSERT INTO PECO_PUMPS (ID, STATION_ID, CODE, SELF_SERVICE)
SELECT PECO_PUMPS_SEQ.NEXTVAL, ID, 'P-1', 1 FROM PECO_STATIONS WHERE CODE = 'AZS-001';
INSERT INTO PECO_PUMPS (ID, STATION_ID, CODE, SELF_SERVICE)
SELECT PECO_PUMPS_SEQ.NEXTVAL, ID, 'P-2', 0 FROM PECO_STATIONS WHERE CODE = 'AZS-001';

-- По одному пистолету каждого вида топлива на первой колонке
INSERT INTO PECO_NOZZLES (ID, PUMP_ID, TANK_ID, GRADE_CODE, CODE, METER_TOTAL)
SELECT PECO_NOZZLES_SEQ.NEXTVAL, p.ID, t.ID, t.GRADE_CODE, 'N-' || t.GRADE_CODE, 0
  FROM PECO_PUMPS p
  JOIN PECO_TANKS t ON t.STATION_ID = p.STATION_ID
 WHERE p.CODE = 'P-1';

INSERT INTO PECO_EMPLOYEES (ID, STATION_ID, FULL_NAME, ROLE_CODE, PIN_HASH)
SELECT PECO_EMPLOYEES_SEQ.NEXTVAL, ID, 'Оператор Демо', 'ATTENDANT', 'demo-not-a-real-hash'
  FROM PECO_STATIONS WHERE CODE = 'AZS-001';
INSERT INTO PECO_EMPLOYEES (ID, STATION_ID, FULL_NAME, ROLE_CODE, PIN_HASH)
SELECT PECO_EMPLOYEES_SEQ.NEXTVAL, ID, 'Менеджер Демо', 'MANAGER', 'demo-not-a-real-hash'
  FROM PECO_STATIONS WHERE CODE = 'AZS-001';

INSERT INTO PECO_PRICES (ID, STATION_ID, GRADE_CODE, PRICE)
SELECT PECO_PRICES_SEQ.NEXTVAL, s.ID, g.CODE,
       CASE g.CODE WHEN 'A92' THEN 22.50 WHEN 'A95' THEN 23.90
                   WHEN 'A98' THEN 26.40 ELSE 21.80 END
  FROM PECO_STATIONS s CROSS JOIN PECO_REF_FUEL_GRADES g
 WHERE s.CODE = 'AZS-001';

COMMIT;
```

- [ ] **Step 3: Register both files in the deploy script**

Add after `"102_peco_inventory_tables.sql",`:

```python
        "103_peco_views.sql",
        "104_peco_demo_data.sql",
```

- [ ] **Step 4: Verify**

Run: `python -c "v=open('sql/103_peco_views.sql').read(); d=open('sql/104_peco_demo_data.sql').read(); assert v.count('CREATE OR REPLACE VIEW')==4; assert d.count('INSERT INTO PECO_REF_FUEL_GRADES')==4; print('ok')"`

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add sql/103_peco_views.sql sql/104_peco_demo_data.sql deploy_oracle_objects.py
git commit -m "PECO: представления и демо-данные"
```

---

## Stage B — Store Layer

### Task 5: Store — references, master data, current prices

**Files:**
- Create: `models/peco_oracle_store.py`
- Test: `tests/test_peco.py`

**Interfaces:**
- Consumes: `models.database.DatabaseModel`; tables from Tasks 1–4.
- Produces:
  - `_norm_rows(result: dict) -> list[dict]` — lowercase-keyed row dicts
  - `PecoStore.list_grades() -> dict`
  - `PecoStore.list_stations(active_only: bool = True) -> dict`
  - `PecoStore.list_nozzles(station_id: int) -> dict`
  - `PecoStore.current_price(station_id: int, grade_code: str) -> dict` → `{"success": True, "price": float}`
  - `PecoStore.set_price(station_id: int, grade_code: str, price: float) -> dict`
  - `PecoStore.log_event(event_type: str, **kw) -> dict`

  Every method returns a dict with a `success` key and never raises.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_peco.py`:

```python
"""PECO module — unit tests (Oracle fully mocked)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock

from models.peco_oracle_store import PecoStore, _norm_rows


def _fake_db(query_result):
    """Context manager yielding a db whose execute_query returns query_result."""
    db = MagicMock()
    db.execute_query.return_value = query_result
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = False
    return cm, db


def test_norm_rows_lowercases_columns():
    r = {"success": True, "columns": ["ID", "GRADE_CODE"], "data": [(1, "A95")]}
    assert _norm_rows(r) == [{"id": 1, "grade_code": "A95"}]


def test_norm_rows_empty_on_failure():
    assert _norm_rows({"success": False, "columns": [], "data": []}) == []


def test_current_price_returns_open_ended_row():
    cm, db = _fake_db({"success": True, "columns": ["PRICE"], "data": [(23.90,)]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.current_price(1, "A95")
    assert r["success"] is True
    assert r["price"] == 23.90
    sql = db.execute_query.call_args[0][0]
    assert "VALID_TO IS NULL" in sql  # действующая цена, а не любая


def test_current_price_missing_is_not_success():
    cm, _ = _fake_db({"success": True, "columns": ["PRICE"], "data": []})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.current_price(1, "A95")
    assert r["success"] is False


def test_set_price_closes_previous_then_inserts():
    cm, db = _fake_db({"success": True, "columns": [], "data": []})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.set_price(1, "A95", 24.50)
    assert r["success"] is True
    statements = [c[0][0] for c in db.execute_query.call_args_list]
    assert any("UPDATE PECO_PRICES" in s for s in statements)
    assert any("INSERT INTO PECO_PRICES" in s for s in statements)
    db.connection.commit.assert_called_once()


def test_store_never_raises_on_db_error():
    cm = MagicMock()
    cm.__enter__.side_effect = Exception("ORA-12541")
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.list_stations()
    assert r["success"] is False and "ORA-12541" in r["error"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_peco.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.peco_oracle_store'`

- [ ] **Step 3: Write the store**

Create `models/peco_oracle_store.py`:

```python
"""PECO module Oracle store — все операции с таблицами PECO_*.

Только persistence. Бизнес-правила живут в models/peco_shift.py,
models/peco_txn.py и models/peco_inventory.py.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from models.database import DatabaseModel


def _norm_rows(r: Dict[str, Any]) -> List[Dict[str, Any]]:
    """{success, columns, data} -> список словарей с ключами в нижнем регистре."""
    if not r.get("success") or not r.get("data"):
        return []
    cols = [c.lower() for c in r["columns"]]
    return [dict(zip(cols, row)) for row in r["data"]]


class PecoStore:
    """CRUD по справочникам, мастер-данным и ценам PECO."""

    # ---------------- справочники ----------------

    @staticmethod
    def list_grades() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT CODE, NAME, COLOR, DENSITY
                         FROM PECO_REF_FUEL_GRADES
                        ORDER BY SORT_ORDER"""
                )
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------------- мастер-данные ----------------

    @staticmethod
    def list_stations(active_only: bool = True) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """SELECT ID, CODE, NAME, ADDRESS, REGION, ACTIVE
                           FROM PECO_STATIONS"""
                if active_only:
                    sql += " WHERE ACTIVE = 1"
                sql += " ORDER BY CODE"
                r = db.execute_query(sql)
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def list_nozzles(station_id: int) -> Dict[str, Any]:
        """Активные пистолеты станции с колонкой, резервуаром и счётчиком."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT n.ID, n.CODE, n.GRADE_CODE, n.METER_TOTAL,
                              n.TANK_ID, p.ID AS PUMP_ID, p.CODE AS PUMP_CODE,
                              p.SELF_SERVICE
                         FROM PECO_NOZZLES n
                         JOIN PECO_PUMPS p ON p.ID = n.PUMP_ID
                        WHERE p.STATION_ID = :station_id
                          AND n.ACTIVE = 1 AND p.ACTIVE = 1
                        ORDER BY p.CODE, n.CODE""",
                    {"station_id": station_id},
                )
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------------- цены ----------------

    @staticmethod
    def current_price(station_id: int, grade_code: str) -> Dict[str, Any]:
        """Действующая цена = строка с VALID_TO IS NULL."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT PRICE FROM PECO_PRICES
                        WHERE STATION_ID = :station_id
                          AND GRADE_CODE = :grade_code
                          AND VALID_TO IS NULL""",
                    {"station_id": station_id, "grade_code": grade_code},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False,
                            "error": f"Нет действующей цены: {grade_code}"}
                return {"success": True, "price": float(rows[0]["price"])}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def set_price(station_id: int, grade_code: str, price: float) -> Dict[str, Any]:
        """Закрывает предыдущую цену и вставляет новую. In-place не обновляем:
        транзакции хранят цену проведения, история должна оставаться верной."""
        params = {"station_id": station_id, "grade_code": grade_code}
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE PECO_PRICES SET VALID_TO = SYSTIMESTAMP
                        WHERE STATION_ID = :station_id
                          AND GRADE_CODE = :grade_code
                          AND VALID_TO IS NULL""",
                    params,
                )
                db.execute_query(
                    """INSERT INTO PECO_PRICES
                              (ID, STATION_ID, GRADE_CODE, PRICE)
                       VALUES (PECO_PRICES_SEQ.NEXTVAL, :station_id,
                               :grade_code, :price)""",
                    dict(params, price=price),
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------------- журнал событий ----------------

    @staticmethod
    def log_event(
        event_type: str,
        station_id: Optional[int] = None,
        shift_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        employee_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append-only запись в PECO_EVENT_LOG."""
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO PECO_EVENT_LOG
                              (ID, STATION_ID, SHIFT_ID, EVENT_TYPE,
                               ENTITY_TYPE, ENTITY_ID, EMPLOYEE_ID, PAYLOAD)
                       VALUES (PECO_EVENT_LOG_SEQ.NEXTVAL, :station_id, :shift_id,
                               :event_type, :entity_type, :entity_id,
                               :employee_id, :payload)""",
                    {
                        "station_id": station_id,
                        "shift_id": shift_id,
                        "event_type": event_type,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "employee_id": employee_id,
                        "payload": json.dumps(payload or {}, ensure_ascii=False)[:2000],
                    },
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add models/peco_oracle_store.py tests/test_peco.py
git commit -m "PECO: store — справочники, мастер-данные, версионные цены"
```

---

### Task 6: Store — shift, meter, and transaction persistence

**Files:**
- Modify: `models/peco_oracle_store.py` (append methods to `PecoStore`)
- Modify: `tests/test_peco.py` (append tests)

**Interfaces:**
- Consumes: `_norm_rows`, `DatabaseModel`.
- Produces:
  - `PecoStore.open_shift(station_id: int, employee_id: int) -> dict` → `{"success": True, "shift_id": int}`
  - `PecoStore.get_open_shift(station_id: int) -> dict` → `{"success": bool, "shift": dict}`
  - `PecoStore.get_shift_meters(shift_id: int) -> dict` → `{"success": True, "items": [...]}` with keys `nozzle_id`, `meter_open`, `meter_close`
  - `PecoStore.save_meter_close(shift_id: int, nozzle_id: int, meter_close: float) -> dict`
  - `PecoStore.shift_paid_liters(shift_id: int) -> dict` → `{"success": True, "liters": float, "cash": float, "mia": float}`
  - `PecoStore.count_unresolved_txn(shift_id: int) -> dict` → `{"success": True, "count": int}`
  - `PecoStore.finalize_shift(shift_id: int, employee_id: int, status: str, totals: dict) -> dict`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_peco.py`:

```python
def test_open_shift_creates_meter_rows_from_nozzles():
    cm, db = _fake_db({"success": True, "columns": ["ID"], "data": [(77,)]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.open_shift(station_id=1, employee_id=5)
    assert r["success"] is True and r["shift_id"] == 77
    statements = [c[0][0] for c in db.execute_query.call_args_list]
    assert any("INSERT INTO PECO_SHIFTS" in s for s in statements)
    # показания открытия берутся из текущих счётчиков пистолетов
    assert any("INSERT INTO PECO_SHIFT_METERS" in s for s in statements)
    assert any("METER_TOTAL" in s for s in statements)
    db.connection.commit.assert_called_once()


def test_count_unresolved_txn_covers_both_open_states():
    cm, db = _fake_db({"success": True, "columns": ["C"], "data": [(3,)]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.count_unresolved_txn(77)
    assert r["success"] is True and r["count"] == 3
    sql = db.execute_query.call_args[0][0]
    assert "DISPENSING" in sql and "AWAITING_PAY" in sql


def test_shift_paid_liters_separates_cash_from_mia():
    cm, db = _fake_db({
        "success": True,
        "columns": ["LITERS", "CASH_AMT", "MIA_AMT"],
        "data": [(120.5, 2400.00, 900.00)],
    })
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.shift_paid_liters(77)
    assert r["liters"] == 120.5
    assert r["cash"] == 2400.00
    assert r["mia"] == 900.00
    sql = db.execute_query.call_args[0][0]
    assert "'CASH'" in sql and "'MIA_QR'" in sql


def test_finalize_shift_writes_all_three_variances():
    cm, db = _fake_db({"success": True, "columns": [], "data": []})
    totals = {"cash_declared": 2390.0, "cash_expected": 2400.0,
              "cash_variance": -10.0, "liter_variance": 0.4,
              "tank_variance": -1.2}
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.finalize_shift(77, employee_id=5, status="DISPUTED", totals=totals)
    assert r["success"] is True
    sql = db.execute_query.call_args[0][0]
    for col in ("CASH_VARIANCE", "LITER_VARIANCE", "TANK_VARIANCE", "STATUS_CODE"):
        assert col in sql
    db.connection.commit.assert_called_once()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_peco.py -v -k "shift or unresolved or paid_liters"`
Expected: FAIL — `AttributeError: type object 'PecoStore' has no attribute 'open_shift'`

- [ ] **Step 3: Append the methods to `PecoStore`**

Add inside `class PecoStore`, after `set_price`:

```python
    # ---------------- смены ----------------

    @staticmethod
    def open_shift(station_id: int, employee_id: int) -> Dict[str, Any]:
        """Создаёт смену и строки показаний по всем активным пистолетам.

        Показание открытия = текущий тотализатор пистолета. Это связывает
        новую смену с закрывающими показаниями предыдущей и не даёт
        разорвать цепочку незаметно.
        """
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO PECO_SHIFTS
                              (ID, STATION_ID, STATUS_CODE, OPENED_BY)
                       VALUES (PECO_SHIFTS_SEQ.NEXTVAL, :station_id, 'OPEN',
                               :employee_id)""",
                    {"station_id": station_id, "employee_id": employee_id},
                )
                r = db.execute_query(
                    "SELECT PECO_SHIFTS_SEQ.CURRVAL AS ID FROM dual"
                )
                rows = _norm_rows(r)
                shift_id = int(rows[0]["id"]) if rows else None

                db.execute_query(
                    """INSERT INTO PECO_SHIFT_METERS
                              (ID, SHIFT_ID, NOZZLE_ID, METER_OPEN)
                       SELECT PECO_SHIFT_METERS_SEQ.NEXTVAL, :shift_id,
                              n.ID, n.METER_TOTAL
                         FROM PECO_NOZZLES n
                         JOIN PECO_PUMPS p ON p.ID = n.PUMP_ID
                        WHERE p.STATION_ID = :station_id
                          AND n.ACTIVE = 1 AND p.ACTIVE = 1""",
                    {"shift_id": shift_id, "station_id": station_id},
                )
                db.connection.commit()
                return {"success": True, "shift_id": shift_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_open_shift(station_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT ID, STATION_ID, STATUS_CODE, OPENED_AT, OPENED_BY
                         FROM PECO_SHIFTS
                        WHERE STATION_ID = :station_id
                          AND STATUS_CODE IN ('OPEN', 'CLOSING')
                        ORDER BY OPENED_AT DESC
                        FETCH FIRST 1 ROWS ONLY""",
                    {"station_id": station_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Нет открытой смены"}
                return {"success": True, "shift": rows[0]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_shift_meters(shift_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT sm.NOZZLE_ID, sm.METER_OPEN, sm.METER_CLOSE,
                              n.CODE AS NOZZLE_CODE, n.GRADE_CODE, n.TANK_ID
                         FROM PECO_SHIFT_METERS sm
                         JOIN PECO_NOZZLES n ON n.ID = sm.NOZZLE_ID
                        WHERE sm.SHIFT_ID = :shift_id
                        ORDER BY n.CODE""",
                    {"shift_id": shift_id},
                )
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_meter_close(shift_id: int, nozzle_id: int,
                         meter_close: float) -> Dict[str, Any]:
        """Записывает закрывающее показание и синхронно двигает тотализатор."""
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE PECO_SHIFT_METERS SET METER_CLOSE = :meter_close
                        WHERE SHIFT_ID = :shift_id AND NOZZLE_ID = :nozzle_id""",
                    {"shift_id": shift_id, "nozzle_id": nozzle_id,
                     "meter_close": meter_close},
                )
                db.execute_query(
                    """UPDATE PECO_NOZZLES SET METER_TOTAL = :meter_close
                        WHERE ID = :nozzle_id""",
                    {"nozzle_id": nozzle_id, "meter_close": meter_close},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shift_paid_liters(shift_id: int) -> Dict[str, Any]:
        """Литры и деньги по оплаченным транзакциям смены.

        Наличные и MIA QR разделены: MIA не попадает в кассовую сверку,
        иначе cash_variance теряет смысл.
        """
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT NVL(SUM(LITERS), 0) AS LITERS,
                              NVL(SUM(CASE WHEN PAY_METHOD = 'CASH'
                                           THEN AMOUNT ELSE 0 END), 0) AS CASH_AMT,
                              NVL(SUM(CASE WHEN PAY_METHOD = 'MIA_QR'
                                           THEN AMOUNT ELSE 0 END), 0) AS MIA_AMT
                         FROM PECO_TXN
                        WHERE SHIFT_ID = :shift_id AND STATUS_CODE = 'PAID'""",
                    {"shift_id": shift_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": True, "liters": 0.0, "cash": 0.0, "mia": 0.0}
                row = rows[0]
                return {
                    "success": True,
                    "liters": float(row["liters"]),
                    "cash": float(row["cash_amt"]),
                    "mia": float(row["mia_amt"]),
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def count_unresolved_txn(shift_id: int) -> Dict[str, Any]:
        """Транзакции, мешающие закрыть смену: налив идёт или ждёт оплаты."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT COUNT(*) AS C FROM PECO_TXN
                        WHERE SHIFT_ID = :shift_id
                          AND STATUS_CODE IN ('DISPENSING', 'AWAITING_PAY')""",
                    {"shift_id": shift_id},
                )
                rows = _norm_rows(r)
                return {"success": True, "count": int(rows[0]["c"]) if rows else 0}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def finalize_shift(shift_id: int, employee_id: int, status: str,
                       totals: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE PECO_SHIFTS
                          SET STATUS_CODE    = :status,
                              CLOSED_AT      = SYSTIMESTAMP,
                              CLOSED_BY      = :employee_id,
                              CASH_DECLARED  = :cash_declared,
                              CASH_EXPECTED  = :cash_expected,
                              CASH_VARIANCE  = :cash_variance,
                              LITER_VARIANCE = :liter_variance,
                              TANK_VARIANCE  = :tank_variance
                        WHERE ID = :shift_id""",
                    {
                        "shift_id": shift_id,
                        "employee_id": employee_id,
                        "status": status,
                        "cash_declared": totals.get("cash_declared"),
                        "cash_expected": totals.get("cash_expected"),
                        "cash_variance": totals.get("cash_variance"),
                        "liter_variance": totals.get("liter_variance"),
                        "tank_variance": totals.get("tank_variance"),
                    },
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 10 passed

- [ ] **Step 5: Commit**

```bash
git add models/peco_oracle_store.py tests/test_peco.py
git commit -m "PECO: store — смены, показания счётчиков, агрегаты транзакций"
```

---

## Stage C — Shift Core

### Task 7: Variance math (pure functions)

This is the heart of the system. Pure functions, no database, fully unit-tested.

**Files:**
- Create: `models/peco_shift.py`
- Modify: `tests/test_peco.py`

**Interfaces:**
- Consumes: nothing (pure).
- Produces:
  - `meter_delta(meters: list[dict]) -> float` — sums `meter_close - meter_open`, skipping rows where `meter_close` is `None`
  - `compute_variances(meters, txn_liters, cash_declared, cash_expected, tank_open=None, delivered=0.0, dip_close=None) -> dict` → keys `meter_delta`, `liter_variance`, `cash_variance`, `tank_variance` (the last is `None` when `tank_open` or `dip_close` is absent)
  - `TOLERANCE_LITERS: float = 0.5`, `TOLERANCE_CASH: float = 1.0`
  - `exceeds_tolerance(variances: dict) -> bool`
  - `resolve_status(variances: dict) -> str` → `"CLOSED"` or `"DISPUTED"`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_peco.py`:

```python
from models import peco_shift


def test_meter_delta_sums_closed_nozzles_only():
    meters = [
        {"nozzle_id": 1, "meter_open": 1000.0, "meter_close": 1120.5},
        {"nozzle_id": 2, "meter_open": 500.0,  "meter_close": 560.0},
        {"nozzle_id": 3, "meter_open": 200.0,  "meter_close": None},  # не снят
    ]
    assert peco_shift.meter_delta(meters) == 180.5


def test_liter_variance_is_meter_minus_paid():
    """Топливо вышло из пистолета, но не оплачено — это и есть недостача."""
    meters = [{"nozzle_id": 1, "meter_open": 0.0, "meter_close": 100.0}]
    v = peco_shift.compute_variances(meters, txn_liters=98.0,
                                     cash_declared=0.0, cash_expected=0.0)
    assert v["meter_delta"] == 100.0
    assert v["liter_variance"] == 2.0


def test_cash_variance_is_declared_minus_expected():
    v = peco_shift.compute_variances([], txn_liters=0.0,
                                     cash_declared=2390.0, cash_expected=2400.0)
    assert v["cash_variance"] == -10.0  # недостача кассы


def test_tank_variance_uses_ledger_identity():
    """tank_expected = открытие + приход − отпуск по счётчику."""
    meters = [{"nozzle_id": 1, "meter_open": 0.0, "meter_close": 1000.0}]
    v = peco_shift.compute_variances(
        meters, txn_liters=1000.0, cash_declared=0.0, cash_expected=0.0,
        tank_open=12000.0, delivered=5000.0, dip_close=15950.0,
    )
    # ожидалось 12000 + 5000 - 1000 = 16000; замер 15950 -> -50 (утечка)
    assert v["tank_variance"] == -50.0


def test_tank_variance_is_none_without_dip():
    v = peco_shift.compute_variances([], 0.0, 0.0, 0.0, tank_open=100.0)
    assert v["tank_variance"] is None


def test_variances_are_rounded_to_three_decimals():
    meters = [{"nozzle_id": 1, "meter_open": 0.0, "meter_close": 10.0}]
    v = peco_shift.compute_variances(meters, txn_liters=9.9999,
                                     cash_declared=0.0, cash_expected=0.0)
    assert v["liter_variance"] == 0.0


def test_status_is_closed_within_tolerance():
    v = {"liter_variance": 0.2, "cash_variance": 0.5, "tank_variance": None}
    assert peco_shift.exceeds_tolerance(v) is False
    assert peco_shift.resolve_status(v) == "CLOSED"


def test_status_is_disputed_when_liters_exceed_tolerance():
    v = {"liter_variance": 3.0, "cash_variance": 0.0, "tank_variance": None}
    assert peco_shift.exceeds_tolerance(v) is True
    assert peco_shift.resolve_status(v) == "DISPUTED"


def test_status_is_disputed_on_negative_cash_beyond_tolerance():
    """Излишек тоже расхождение — проверяется модуль, а не знак."""
    v = {"liter_variance": 0.0, "cash_variance": -25.0, "tank_variance": None}
    assert peco_shift.resolve_status(v) == "DISPUTED"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_peco.py -v -k "variance or meter_delta or status or tolerance"`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.peco_shift'`

- [ ] **Step 3: Write the module**

Create `models/peco_shift.py`:

```python
"""PECO: жизненный цикл смены и расчёт расхождений.

Функции расчёта — чистые: принимают и возвращают словари, к базе не
обращаются. Это делает главную бизнес-логику модуля тестируемой без Oracle.

Три расхождения соответствуют трём разным типам отказа и намеренно
не сводятся в одно число:

  liter_variance -- топливо вышло из пистолета, но не оплачено
  cash_variance  -- недостача или излишек денежного ящика
  tank_variance  -- утечка либо уход калибровки резервуара
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Допуски. Выход за пределы переводит смену в DISPUTED и требует PIN менеджера.
TOLERANCE_LITERS: float = 0.5
TOLERANCE_CASH: float = 1.0


def meter_delta(meters: List[Dict[str, Any]]) -> float:
    """Сумма (METER_CLOSE - METER_OPEN) по пистолетам со снятым показанием."""
    total = 0.0
    for m in meters:
        close = m.get("meter_close")
        if close is None:
            continue
        total += float(close) - float(m.get("meter_open") or 0.0)
    return round(total, 3)


def compute_variances(
    meters: List[Dict[str, Any]],
    txn_liters: float,
    cash_declared: float,
    cash_expected: float,
    tank_open: Optional[float] = None,
    delivered: float = 0.0,
    dip_close: Optional[float] = None,
) -> Dict[str, Any]:
    """Считает все три расхождения смены.

    tank_variance возвращается как None, если нет замера закрытия или
    остатка на открытие — считать его «нулевым» в этом случае значило бы
    выдавать отсутствие данных за отсутствие проблемы.
    """
    delta = meter_delta(meters)

    liter_variance = round(delta - float(txn_liters), 3)
    cash_variance = round(float(cash_declared) - float(cash_expected), 2)

    tank_variance: Optional[float] = None
    if tank_open is not None and dip_close is not None:
        tank_expected = float(tank_open) + float(delivered) - delta
        tank_variance = round(float(dip_close) - tank_expected, 3)

    return {
        "meter_delta": delta,
        "liter_variance": liter_variance,
        "cash_variance": cash_variance,
        "tank_variance": tank_variance,
    }


def exceeds_tolerance(variances: Dict[str, Any]) -> bool:
    """Проверяется модуль отклонения: излишек — такое же расхождение."""
    if abs(float(variances.get("liter_variance") or 0.0)) > TOLERANCE_LITERS:
        return True
    if abs(float(variances.get("cash_variance") or 0.0)) > TOLERANCE_CASH:
        return True
    tank = variances.get("tank_variance")
    if tank is not None and abs(float(tank)) > TOLERANCE_LITERS:
        return True
    return False


def resolve_status(variances: Dict[str, Any]) -> str:
    """Итоговый статус смены по расхождениям."""
    return "DISPUTED" if exceeds_tolerance(variances) else "CLOSED"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 19 passed

- [ ] **Step 5: Commit**

```bash
git add models/peco_shift.py tests/test_peco.py
git commit -m "PECO: расчёт расхождений смены (чистые функции + тесты)"
```

---

### Task 8: Shift open and close orchestration

**Files:**
- Modify: `models/peco_shift.py` (append orchestration functions)
- Modify: `tests/test_peco.py`

**Interfaces:**
- Consumes: `PecoStore.open_shift`, `get_open_shift`, `get_shift_meters`, `shift_paid_liters`, `count_unresolved_txn`, `finalize_shift`, `log_event`; `compute_variances`, `resolve_status` from Task 7.
- Produces:
  - `open_shift(station_id: int, employee_id: int) -> dict` — refuses if a shift is already open
  - `close_shift(shift_id, employee_id, cash_declared, tank_readings=None) -> dict` → on success `{"success": True, "status": str, "variances": dict}`; on unresolved transactions `{"success": False, "error": ..., "unresolved": int}`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_peco.py`:

```python
def test_open_shift_refuses_when_one_is_already_open():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_open_shift.return_value = {"success": True, "shift": {"id": 42}}
        r = peco_shift.open_shift(station_id=1, employee_id=5)
    assert r["success"] is False
    assert "уже открыта" in r["error"]
    store.open_shift.assert_not_called()


def test_open_shift_creates_when_none_open():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_open_shift.return_value = {"success": False, "error": "Нет открытой смены"}
        store.open_shift.return_value = {"success": True, "shift_id": 43}
        r = peco_shift.open_shift(station_id=1, employee_id=5)
    assert r["success"] is True and r["shift_id"] == 43
    store.log_event.assert_called_once()


def test_close_shift_blocked_by_unresolved_transactions():
    """Смена не закрывается, пока налив идёт или ждёт оплаты — ничего
    не должно исчезать молча."""
    with patch("models.peco_shift.PecoStore") as store:
        store.count_unresolved_txn.return_value = {"success": True, "count": 2}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=100.0)
    assert r["success"] is False
    assert r["unresolved"] == 2
    store.finalize_shift.assert_not_called()


def test_close_shift_computes_and_persists_variances():
    with patch("models.peco_shift.PecoStore") as store:
        store.count_unresolved_txn.return_value = {"success": True, "count": 0}
        store.get_shift_meters.return_value = {"success": True, "items": [
            {"nozzle_id": 1, "meter_open": 0.0, "meter_close": 100.0},
        ]}
        store.shift_paid_liters.return_value = {
            "success": True, "liters": 100.0, "cash": 2400.0, "mia": 500.0}
        store.finalize_shift.return_value = {"success": True}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=2400.0)
    assert r["success"] is True
    assert r["status"] == "CLOSED"
    assert r["variances"]["liter_variance"] == 0.0
    assert r["variances"]["cash_variance"] == 0.0
    # ожидаемая наличность — только CASH, без MIA QR
    totals = store.finalize_shift.call_args.kwargs["totals"]
    assert totals["cash_expected"] == 2400.0


def test_close_shift_marks_disputed_on_shortfall():
    with patch("models.peco_shift.PecoStore") as store:
        store.count_unresolved_txn.return_value = {"success": True, "count": 0}
        store.get_shift_meters.return_value = {"success": True, "items": [
            {"nozzle_id": 1, "meter_open": 0.0, "meter_close": 100.0},
        ]}
        store.shift_paid_liters.return_value = {
            "success": True, "liters": 90.0, "cash": 2000.0, "mia": 0.0}
        store.finalize_shift.return_value = {"success": True}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=2000.0)
    assert r["status"] == "DISPUTED"
    assert r["variances"]["liter_variance"] == 10.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_peco.py -v -k "open_shift or close_shift"`
Expected: FAIL — `AttributeError: module 'models.peco_shift' has no attribute 'open_shift'`

- [ ] **Step 3: Append the orchestration functions**

At the top of `models/peco_shift.py`, add the import below the existing `typing` import:

```python
from models.peco_oracle_store import PecoStore
```

Then append to the end of the file:

```python
# ------------------------------------------------------------------
# Оркестрация (обращается к store, но не пишет SQL сама)
# ------------------------------------------------------------------


def open_shift(station_id: int, employee_id: int) -> Dict[str, Any]:
    """Открывает смену. На станции может быть только одна открытая смена."""
    existing = PecoStore.get_open_shift(station_id)
    if existing.get("success"):
        return {"success": False,
                "error": "На станции уже открыта смена",
                "shift_id": existing["shift"].get("id")}

    created = PecoStore.open_shift(station_id, employee_id)
    if not created.get("success"):
        return created

    PecoStore.log_event(
        "SHIFT_OPENED",
        station_id=station_id,
        shift_id=created["shift_id"],
        entity_type="SHIFT",
        entity_id=created["shift_id"],
        employee_id=employee_id,
    )
    return created


def close_shift(
    shift_id: int,
    employee_id: int,
    cash_declared: float,
    tank_readings: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Закрывает смену со сверкой.

    tank_readings — список словарей вида
    {"tank_open": float, "delivered": float, "dip_close": float};
    суммируется по станции. Если не передан, tank_variance = None.
    """
    unresolved = PecoStore.count_unresolved_txn(shift_id)
    if not unresolved.get("success"):
        return unresolved
    if unresolved["count"] > 0:
        return {
            "success": False,
            "error": "Есть неразобранные транзакции: оплатите или аннулируйте",
            "unresolved": unresolved["count"],
        }

    meters_r = PecoStore.get_shift_meters(shift_id)
    if not meters_r.get("success"):
        return meters_r
    meters = meters_r["items"]

    paid = PecoStore.shift_paid_liters(shift_id)
    if not paid.get("success"):
        return paid

    tank_open = delivered = dip_close = None
    if tank_readings:
        tank_open = sum(float(t.get("tank_open") or 0.0) for t in tank_readings)
        delivered = sum(float(t.get("delivered") or 0.0) for t in tank_readings)
        dip_close = sum(float(t.get("dip_close") or 0.0) for t in tank_readings)

    variances = compute_variances(
        meters,
        txn_liters=paid["liters"],
        cash_declared=cash_declared,
        cash_expected=paid["cash"],
        tank_open=tank_open,
        delivered=delivered or 0.0,
        dip_close=dip_close,
    )

    status = resolve_status(variances)
    totals = {
        "cash_declared": cash_declared,
        "cash_expected": paid["cash"],
        "cash_variance": variances["cash_variance"],
        "liter_variance": variances["liter_variance"],
        "tank_variance": variances["tank_variance"],
    }

    saved = PecoStore.finalize_shift(
        shift_id, employee_id=employee_id, status=status, totals=totals
    )
    if not saved.get("success"):
        return saved

    PecoStore.log_event(
        "SHIFT_CLOSED",
        shift_id=shift_id,
        entity_type="SHIFT",
        entity_id=shift_id,
        employee_id=employee_id,
        payload={"status": status, **variances},
    )
    return {"success": True, "status": status, "variances": variances,
            "mia_amount": paid["mia"]}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 24 passed

- [ ] **Step 5: Commit**

```bash
git add models/peco_shift.py tests/test_peco.py
git commit -m "PECO: открытие и закрытие смены со сверкой"
```

---

## Continued

The plan is split across three files so each stays readable. Execute them in order.

| File | Tasks | Contents |
|---|---|---|
| This file | 1–8 | Stage A schema, Stage B store, Stage C shift core |
| [part 2](2026-08-19-peco-fuel-retail-part2.md) | 9–14 | Manager approval, Stage D dispensing, Stage E inventory, controller |
| [part 3](2026-08-19-peco-fuel-retail-part3.md) | 15–20 | Routes, Stage G templates, Stage H documentation |

The Global Constraints above apply to every task in all three files.
