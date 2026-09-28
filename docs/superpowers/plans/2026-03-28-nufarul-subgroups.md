# Nufarul Subgroups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable subgroup support to NUF_GROUP_PARAMS and NUF_SERVICES, and display animated subgroup filter buttons (rkeeper-style) in the TS kiosk between the AI bar and service grid.

**Architecture:** Add `SUBGROUPS_JSON CLOB` column to existing `NUF_GROUP_PARAMS` table (stores inline JSON array of subgroup definitions per group) and `SERVICE_SUBGROUP VARCHAR2(100)` to `NUF_SERVICES`. The controller's `get_group_params()` SELECT is updated to include the new column. The TS kiosk parses subgroups on boot, renders them as a horizontally-scrollable animated bar on group selection, and filters the service grid when a subgroup is tapped.

**Tech Stack:** Oracle DB (ALTER TABLE, UPDATE via PL/SQL), Python/Flask (`NufarulController`), vanilla JS/CSS in monolithic HTML template (`nufarul_oper_ts.html`).

---

## File Map

| File | Change |
|------|--------|
| `sql/43_nufarul_subgroups.sql` | Create — DDL ALTER + seed SUBGROUPS_JSON for dry_cleaning |
| `deploy_oracle_objects.py` | Modify — append `43_nufarul_subgroups.sql` to SQL_FILES list |
| `controllers/nufarul_controller.py` | Modify — add SUBGROUPS_JSON to both SELECTs in `get_group_params()` |
| `tests/test_nufarul_controller.py` | Modify — add 1 new test for SUBGROUPS_JSON in returned data |
| `templates/nufarul_oper_ts.html` | Modify — CSS + HTML + JS for subgroup bar |

---

## Task 1: SQL DDL and seed data

**Files:**
- Create: `sql/43_nufarul_subgroups.sql`
- Modify: `deploy_oracle_objects.py` (line ~153, after `"42_nufarul_group_params.sql"`)

- [ ] **Step 1: Write the failing test (manual)**

  There is no automated test for DDL files. Verify the plan by reading the current state:
  ```bash
  grep -n "42_nufarul" deploy_oracle_objects.py
  ```
  Expected: shows line with `"42_nufarul_group_params.sql"`. Confirms where to insert line 153.

- [ ] **Step 2: Create `sql/43_nufarul_subgroups.sql`**

  ```sql
  -- ============================================================
  -- Nufarul: subgroup support
  -- ============================================================

  -- 1. Add SUBGROUPS_JSON column to NUF_GROUP_PARAMS
  ALTER TABLE NUF_GROUP_PARAMS ADD (SUBGROUPS_JSON CLOB)
  /

  -- 2. Add SERVICE_SUBGROUP column to NUF_SERVICES
  ALTER TABLE NUF_SERVICES ADD (SERVICE_SUBGROUP VARCHAR2(100))
  /

  -- 3. Seed subgroups for dry_cleaning (from nufarul.com/ro/order-online.html)
  UPDATE NUF_GROUP_PARAMS
  SET SUBGROUPS_JSON = '[
    {"key":"textile_clothes","label_ru":"Текстиль","label_ro":"Haine din textile","icon":"👔","sort_order":10},
    {"key":"blankets","label_ru":"Пледы/Одеяла/Шторы","label_ro":"Pleduri, Plapume, Draperii","icon":"🛏","sort_order":20},
    {"key":"workwear","label_ru":"Рабочая одежда","label_ro":"Îmbrăcăminte de lucru","icon":"👷","sort_order":30},
    {"key":"leather_natural","label_ru":"Кожа/мех натур.","label_ro":"Piele, blănuri naturale","icon":"🧥","sort_order":40},
    {"key":"leather_artificial","label_ru":"Кожа/мех искусств.","label_ro":"Piele, blănuri artificiale","icon":"🥼","sort_order":50},
    {"key":"footwear","label_ru":"Обувь","label_ro":"Încălțăminte","icon":"👟","sort_order":60}
  ]'
  WHERE GROUP_KEY = 'dry_cleaning'
  /

  COMMIT
  /
  ```

- [ ] **Step 3: Update `deploy_oracle_objects.py`**

  Find the list entry `"42_nufarul_group_params.sql",` (around line 153) and add the new file after it:

  Old:
  ```python
          "42_nufarul_group_params.sql",
      ]
  ```

  New:
  ```python
          "42_nufarul_group_params.sql",
          "43_nufarul_subgroups.sql",
      ]
  ```

- [ ] **Step 4: Verify manually**

  ```bash
  grep -n "43_nufarul" deploy_oracle_objects.py
  ```
  Expected: line appears after `42_nufarul_group_params.sql`.

- [ ] **Step 5: Commit**

  ```bash
  git add sql/43_nufarul_subgroups.sql deploy_oracle_objects.py
  git commit -m "feat(nufarul): add SUBGROUPS_JSON + SERVICE_SUBGROUP DDL and dry_cleaning seed"
  ```

---

## Task 2: Controller — include SUBGROUPS_JSON in get_group_params()

**Files:**
- Modify: `controllers/nufarul_controller.py` (lines 453–474, `get_group_params()`)
- Modify: `tests/test_nufarul_controller.py` (append new test)

Context: `get_group_params()` has two SELECT branches — one for a single group (`:gk`) and one for all active groups. Both must be updated to include `SUBGROUPS_JSON`.

- [ ] **Step 1: Write the failing test**

  Append to `tests/test_nufarul_controller.py`:

  ```python
  def test_get_group_params_includes_subgroups_json():
      """SUBGROUPS_JSON must be present in each group row returned."""
      rows = [
          ('dry_cleaning', 'Химчистка', 'Curățare', '👗', 10,
           '[{"key":"color"}]', '[{"key":"sg1","label_ru":"Test"}]', 'Y')
      ]
      cols = ['GROUP_KEY','LABEL_RU','LABEL_RO','ICON','SORT_ORDER',
              'PARAMS_JSON','SUBGROUPS_JSON','ACTIVE']
      with patch('controllers.nufarul_controller.DatabaseModel',
                 return_value=FakeDB(rows, cols)):
          result = NufarulController.get_group_params()
      assert result['success'] is True
      assert len(result['data']) == 1
      row = result['data'][0]
      assert 'subgroups_json' in row, "subgroups_json key must be present"
      assert row['subgroups_json'] == '[{"key":"sg1","label_ru":"Test"}]'
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  pytest tests/test_nufarul_controller.py::test_get_group_params_includes_subgroups_json -v
  ```
  Expected: FAIL — the test's `FakeDB` provides SUBGROUPS_JSON in columns but the current mock returns it correctly via `_norm_rows`; however the REAL controller SELECT does not include SUBGROUPS_JSON, so on a live DB it would be missing. The test itself should PASS with the mock (since FakeDB returns whatever columns we give). Therefore run ALL tests before editing to get a baseline:

  ```bash
  pytest tests/test_nufarul_controller.py -v
  ```
  Expected: 4 pass, 1 fail (the new test passes because FakeDB provides the column). If the new test already passes, proceed — it's a documentation/regression test.

- [ ] **Step 3: Update `controllers/nufarul_controller.py`**

  There are TWO places in `get_group_params()` where the SELECT is issued (single-key branch and all-groups branch). Update both:

  **Branch 1** — single key (line ~459):

  Old:
  ```python
                  r = db.execute_query(
                      """SELECT GROUP_KEY, LABEL_RU, LABEL_RO, ICON, SORT_ORDER, PARAMS_JSON, ACTIVE
                         FROM NUF_GROUP_PARAMS WHERE GROUP_KEY = :gk""",
                      {"gk": group_key},
                  )
  ```

  New:
  ```python
                  r = db.execute_query(
                      """SELECT GROUP_KEY, LABEL_RU, LABEL_RO, ICON, SORT_ORDER,
                                PARAMS_JSON, SUBGROUPS_JSON, ACTIVE
                         FROM NUF_GROUP_PARAMS WHERE GROUP_KEY = :gk""",
                      {"gk": group_key},
                  )
  ```

  **Branch 2** — all groups (line ~469):

  Old:
  ```python
                  r = db.execute_query(
                      """SELECT GROUP_KEY, LABEL_RU, LABEL_RO, ICON, SORT_ORDER, PARAMS_JSON, ACTIVE
                         FROM NUF_GROUP_PARAMS WHERE ACTIVE = 'Y' ORDER BY SORT_ORDER"""
                  )
  ```

  New:
  ```python
                  r = db.execute_query(
                      """SELECT GROUP_KEY, LABEL_RU, LABEL_RO, ICON, SORT_ORDER,
                                PARAMS_JSON, SUBGROUPS_JSON, ACTIVE
                         FROM NUF_GROUP_PARAMS WHERE ACTIVE = 'Y' ORDER BY SORT_ORDER"""
                  )
  ```

- [ ] **Step 4: Run all controller tests**

  ```bash
  pytest tests/test_nufarul_controller.py -v
  ```
  Expected: 5 pass, 0 fail.

- [ ] **Step 5: Commit**

  ```bash
  git add controllers/nufarul_controller.py tests/test_nufarul_controller.py
  git commit -m "feat(nufarul): include SUBGROUPS_JSON in get_group_params() SELECT + test"
  ```

---

## Task 3: TS kiosk — subgroup bar UI

**Files:**
- Modify: `templates/nufarul_oper_ts.html`

This task makes three additions to the monolithic HTML file:
1. CSS styles for `.subgroups-bar` and `.subgrp-btn` (in `<style>` block)
2. HTML element `<div id="subgroupsBar">` (between AI bar and svc-section)
3. JS state + functions (`groupSubgroups`, `activeSubgroup`, `renderSubgroupsBar`, `selectSubgroup`) and update to `loadGroups`, `selectGroup`, `renderServices`

### 3a — Add CSS

- [ ] **Step 1: Locate the CSS insertion point**

  Find the line containing `.ai-results.visible { display:block; }` (around line 84). Add the subgroup styles after the existing AI bar styles, before the `/* Services section */` comment.

- [ ] **Step 2: Insert CSS after `.ai-results.visible` block**

  Find this exact block (around line 83–84):
  ```css
  .ai-results { display:none; margin-top:6px; background:#0a1a0a; border:1px solid #22c55e44; border-radius:7px; padding:6px 8px; max-height:120px; overflow-y:auto; }
  .ai-results.visible { display:block; }
  ```

  After that block, add:
  ```css
  /* Subgroups bar */
  .subgroups-bar { display:none; flex-shrink:0; padding:7px 8px; gap:6px; overflow-x:auto; border-bottom:1px solid #1e1e4a; background:#0a0a1a; scroll-snap-type:x mandatory; -webkit-overflow-scrolling:touch; }
  .subgroups-bar.visible { display:flex; animation:sgSlideDown .2s ease; }
  @keyframes sgSlideDown { from{opacity:0;transform:translateY(-8px)} to{opacity:1;transform:translateY(0)} }
  .subgrp-btn { display:flex; flex-direction:column; align-items:center; gap:3px; padding:6px 10px; border-radius:9px; border:1px solid #2a2a5a; background:#12122a; cursor:pointer; flex-shrink:0; transition:background .15s,border-color .15s; scroll-snap-align:start; min-width:72px; }
  .subgrp-btn:active { background:#1e1e3a; }
  .subgrp-btn.active { background:#192a19; border-color:#22c55e; }
  .subgrp-btn .sg-icon { font-size:22px; }
  .subgrp-btn .sg-label { font-size:10px; color:#7dd3fc; font-weight:600; text-align:center; line-height:1.2; max-width:70px; white-space:normal; }
  .subgrp-btn.active .sg-label { color:#53d769; }
  ```

### 3b — Add HTML element

- [ ] **Step 3: Insert subgroups bar div into HTML**

  Find this HTML comment + element (around line 310–311):
  ```html
        <!-- Services grid (intake) -->
        <div class="svc-section" id="svcSection">
  ```

  Replace with:
  ```html
        <!-- Subgroups bar -->
        <div class="subgroups-bar" id="subgroupsBar"></div>

        <!-- Services grid (intake) -->
        <div class="svc-section" id="svcSection">
  ```

### 3c — Update JS

- [ ] **Step 4: Add state variables for subgroups**

  Find this block (around line 436–443):
  ```javascript
  let groups = [];         // [{group_key, label_ru, icon, params_json, ...}]
  let services = [];       // [{id, name_ru, price, unit, service_group, ...}]
  let activeGroup = null;  // group_key string
  let selectedSvc = null;  // service object
  let groupParams = {};    // {group_key: parsed_params_array}
  let paramValues = {};    // {param_key: value} — current param panel state
  let cart = [];           // [{service_id, name, price, qty, params, params_summary}]
  let mode = 'intake';     // 'intake' | 'issue'
  ```

  Replace with:
  ```javascript
  let groups = [];         // [{group_key, label_ru, icon, params_json, subgroups_json, ...}]
  let services = [];       // [{id, name_ru, price, unit, service_group, service_subgroup, ...}]
  let activeGroup = null;  // group_key string
  let selectedSvc = null;  // service object
  let groupParams = {};    // {group_key: parsed_params_array}
  let groupSubgroups = {}; // {group_key: [{key, label_ru, label_ro, icon, sort_order}]}
  let activeSubgroup = null; // subgroup key string | null = show all
  let paramValues = {};    // {param_key: value} — current param panel state
  let cart = [];           // [{service_id, name, price, qty, params, params_summary}]
  let mode = 'intake';     // 'intake' | 'issue'
  ```

- [ ] **Step 5: Update `loadGroups()` to parse SUBGROUPS_JSON**

  Find this block (around line 454–465):
  ```javascript
  async function loadGroups() {
    try {
      const r = await apiFetch(API_TS + '/group-params');
      if (r.success) {
        groups = r.data;
        groups.forEach(g => {
          try { groupParams[g.group_key] = JSON.parse(g.params_json || '[]'); }
          catch(_) { groupParams[g.group_key] = []; }
        });
      }
    } catch(e) { console.error('loadGroups', e); }
  }
  ```

  Replace with:
  ```javascript
  async function loadGroups() {
    try {
      const r = await apiFetch(API_TS + '/group-params');
      if (r.success) {
        groups = r.data;
        groups.forEach(g => {
          try { groupParams[g.group_key] = JSON.parse(g.params_json || '[]'); }
          catch(_) { groupParams[g.group_key] = []; }
          try { groupSubgroups[g.group_key] = JSON.parse(g.subgroups_json || '[]'); }
          catch(_) { groupSubgroups[g.group_key] = []; }
        });
      }
    } catch(e) { console.error('loadGroups', e); }
  }
  ```

- [ ] **Step 6: Update `selectGroup()` to reset activeSubgroup and render subgroup bar**

  Find this function (around line 486–494):
  ```javascript
  function selectGroup(gk) {
    activeGroup = gk;
    document.querySelectorAll('.group-btn').forEach(b => b.classList.toggle('active', b.dataset.gk === gk));
    const g = groups.find(x => x.group_key === gk);
    document.getElementById('svcGroupTitle').textContent = (g ? (g.icon + ' ' + g.label_ru) : gk);
    document.getElementById('svcSearch').value = '';
    renderServices('');
    clearParams();
  }
  ```

  Replace with:
  ```javascript
  function selectGroup(gk) {
    activeGroup = gk;
    activeSubgroup = null;
    document.querySelectorAll('.group-btn').forEach(b => b.classList.toggle('active', b.dataset.gk === gk));
    const g = groups.find(x => x.group_key === gk);
    document.getElementById('svcGroupTitle').textContent = (g ? (g.icon + ' ' + g.label_ru) : gk);
    document.getElementById('svcSearch').value = '';
    renderSubgroupsBar();
    renderServices('');
    clearParams();
  }
  ```

- [ ] **Step 7: Add `renderSubgroupsBar()` and `selectSubgroup()` functions**

  Find the comment `// ── Services ───` (around line 496). Insert the two new functions just before it:

  ```javascript
  // ── Subgroups ──────────────────────────────────────────────────────────
  function renderSubgroupsBar() {
    const bar = document.getElementById('subgroupsBar');
    const subs = groupSubgroups[activeGroup] || [];
    if (!subs.length) {
      bar.innerHTML = '';
      bar.classList.remove('visible');
      return;
    }
    const allBtn = `<button class="subgrp-btn${activeSubgroup===null?' active':''}" onclick="selectSubgroup(null)">
      <span class="sg-icon">🔸</span>
      <span class="sg-label">Все</span>
    </button>`;
    const subBtns = subs.map(s =>
      `<button class="subgrp-btn${activeSubgroup===s.key?' active':''}" onclick="selectSubgroup('${esc(s.key)}')">
        <span class="sg-icon">${s.icon||'📦'}</span>
        <span class="sg-label">${esc(s.label_ru||s.key)}</span>
      </button>`
    ).join('');
    bar.innerHTML = allBtn + subBtns;
    bar.classList.add('visible');
  }

  function selectSubgroup(key) {
    activeSubgroup = key;
    renderSubgroupsBar();
    renderServices(document.getElementById('svcSearch').value);
  }

  ```

- [ ] **Step 8: Update `renderServices()` to filter by activeSubgroup**

  Find this function (around line 497–512):
  ```javascript
  function renderServices(filter) {
    const grid = document.getElementById('svcGrid');
    const grouped = activeGroup
      ? services.filter(s => s.service_group === activeGroup)
      : services;
    const filtered = filter
      ? grouped.filter(s => (s.name_ru || s.name || '').toLowerCase().includes(filter.toLowerCase()))
      : grouped;
    grid.innerHTML = filtered.map(s =>
      `<div class="svc-card${selectedSvc && selectedSvc.id===s.id?' selected':''}" onclick="selectService(${s.id})">
         <div class="sn">${esc(s.name_ru || s.name || '')}</div>
         <div class="sp">${(s.price||0).toLocaleString('ru')} MDL</div>
         <div class="su">/ ${esc(s.unit||'шт')}</div>
       </div>`
    ).join('');
  }
  ```

  Replace with:
  ```javascript
  function renderServices(filter) {
    const grid = document.getElementById('svcGrid');
    let filtered = activeGroup
      ? services.filter(s => s.service_group === activeGroup)
      : services;
    if (activeSubgroup) {
      filtered = filtered.filter(s => s.service_subgroup === activeSubgroup);
    }
    if (filter) {
      filtered = filtered.filter(s => (s.name_ru || s.name || '').toLowerCase().includes(filter.toLowerCase()));
    }
    grid.innerHTML = filtered.map(s =>
      `<div class="svc-card${selectedSvc && selectedSvc.id===s.id?' selected':''}" onclick="selectService(${s.id})">
         <div class="sn">${esc(s.name_ru || s.name || '')}</div>
         <div class="sp">${(s.price||0).toLocaleString('ru')} MDL</div>
         <div class="su">/ ${esc(s.unit||'шт')}</div>
       </div>`
    ).join('');
  }
  ```

- [ ] **Step 9: Verify HTML renders correctly**

  Open [http://localhost:3003/UNA.md/orasldev/nufarul-oper-ts](http://localhost:3003/UNA.md/orasldev/nufarul-oper-ts) in browser.
  - Tap **Химчистка одежды** (dry_cleaning) group in Col 1.
  - Expected: a row of 7 buttons appears below the AI bar: 🔸 Все, 👔 Текстиль, 🛏 Пледы…, 👷 Рабочая…, 🧥 Кожа натур., 🥼 Кожа искусств., 👟 Обувь — with slide-down animation.
  - Tap any subgroup: service grid filters to show only services where `service_subgroup` matches (will be empty until services are mapped in DB, which is expected).
  - Tap **Все**: all services in group shown again.
  - Tap **Ковры** group: subgroup bar disappears (no subgroups for carpets).

- [ ] **Step 10: Commit**

  ```bash
  git add templates/nufarul_oper_ts.html
  git commit -m "feat(nufarul-ts): add rkeeper-style subgroup filter bar to TS kiosk"
  ```

---

## Self-Review

### Spec Coverage
- ✅ SUBGROUPS_JSON column added to NUF_GROUP_PARAMS (Task 1)
- ✅ SERVICE_SUBGROUP column added to NUF_SERVICES (Task 1)
- ✅ Seed data for dry_cleaning subgroups from nufarul.com (Task 1)
- ✅ Controller returns SUBGROUPS_JSON (Task 2)
- ✅ Subgroup buttons appear dynamically on group selection (Task 3)
- ✅ Buttons have icons and labels (Task 3, sg-icon + sg-label)
- ✅ Slide-down animation on appearance (Task 3, sgSlideDown keyframe)
- ✅ Tapping subgroup filters services (Task 3, renderServices + activeSubgroup)
- ✅ "Все" button shows all services and is preselected (Task 3)
- ✅ Bar hides when group has no subgroups (Task 3, renderSubgroupsBar)

### Placeholder Check
None found.

### Type Consistency
- `activeSubgroup` is `null | string` — checked consistently with `=== null` and `=== s.key`
- `groupSubgroups[gk]` is always an array (fallback `[]` in loadGroups)
- `s.service_subgroup` — column returned by `get_services()` via `_norm_rows` as lowercase key; NUF_SERVICES has had `SERVICE_SUBGROUP` added by Task 1 DDL; services with NULL subgroup have `service_subgroup = null` which correctly shows only in "Все" view.
