# Biro26 Import Wizard + AI Mapping + Images — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Biro26 module with (Stage 1) product image viewing, (Stage 2) a wisepim-style 4-step import wizard, and (Stage 3) AI-assisted mapping of any read-only SELECT as an import source (materialized as a DB view).

**Architecture:** Additive to the existing Biro26 module. New stores `models/biro26_sources.py` (SELECT→view source defs) and `models/biro26_ai.py` (wraps `ai_helper.ask_llm_via_selenium` with heuristic fallback). All OfficePlus access stays in the thick subprocess via `Biro26DB`; main Flask app stays thin. UI changes are additions to the existing `templates/biro26/backoffice.html` + `static/biro26/backoffice-tabs.js`.

**Tech Stack:** Python 3.12, Flask, python-oracledb (thick, via subprocess worker), Oracle 11g (officeplus), pytest (mocked), vanilla JS UI.

**Spec:** `docs/superpowers/specs/2026-06-29-biro26-import-wizard-design.md`
**Run unit tests:** `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_biro26.py -v`
**Conventions to imitate:** existing `models/biro26_oracle_store.py` (helpers `_rows`, `_result`, `_q`, `_page`; `Biro26DB` usage), `controllers/biro26_controller.py`, the Biro26 route block in `app.py`, and `static/biro26/backoffice-tabs.js` (load/render patterns, `I18N`, `apiGet/apiPost`, `el()`, `escapeHtml`, modal pattern).

---

## File Structure

| File | Responsibility | Stage |
|---|---|---|
| `models/biro26_oracle_store.py` (modify) | image cols in `get_goods`/card; `source_columns`, `source_sample` | 1,2 |
| `models/biro26_sources.py` (create) | SELECT guard, view name, sample, source-def CRUD + view DDL | 3 |
| `models/biro26_ai.py` (create) | AI md-draft + mapping suggestion + heuristic fallback + JSON parse | 3 |
| `sql/biro26/02_biro26_sources.sql` (create) + `deploy_biro26_sources.py` (create) | `YBIRO_SRC_DEF` (11g seq+trigger) | 3 |
| `controllers/biro26_controller.py` (modify) | handlers for source columns/sample + sources + AI | 2,3 |
| `app.py` (modify) | routes for the above | 2,3 |
| `templates/biro26/backoffice.html` (modify) | lightbox modal; image cells; "Import (asistent)" wizard tab | 1,2,3 |
| `static/biro26/backoffice-tabs.js` (modify) | lightbox, image rendering, wizard logic, AI steps | 1,2,3 |
| `docs/Biro26/sources/` (dir) | AI-drafted source `.md` files | 3 |
| `tests/test_biro26.py` (modify) | unit tests for all testable cores | 1,2,3 |
| `docs/Biro26/README_BIRO26.html`, `README.md` (modify) | document the additions | 3 |

---

# STAGE 1 — Image viewing

## Task 1: Store returns image URLs

**Files:**
- Modify: `models/biro26_oracle_store.py` (`get_goods` inner SELECT; `get_univers_card`)
- Test: `tests/test_biro26.py`

- [ ] **Step 1: Write failing tests** (append to `tests/test_biro26.py`)

```python
# ── stage 1: images ─────────────────────────────────────────────────

def test_get_goods_includes_image_cols():
    cols = ["ID","ARTICOL","DENUMIRE","BRAND","FURNIZOR","ANGRO","IONLINE","RETAIL1",
            "STOC","COD_UNIVERS","PHOTO_URL","IMAGE_LINK","ROW_STATUS"]
    rows = [(1,"A1","N","B","F",1,1,1,1,1001,"http://x/p.jpg","http://x/i.jpg","IN_DICT")]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_goods(limit=10)
    assert r["success"] and r["data"][0]["photo_url"] == "http://x/p.jpg"
    assert "PHOTO_URL" in fake.last_sql and "IMAGE_LINK" in fake.last_sql
```

- [ ] **Step 2: Run → fail**

Run: `./venv/bin/python -m pytest tests/test_biro26.py::test_get_goods_includes_image_cols -v`
Expected: FAIL (KeyError 'photo_url' — column not selected).

- [ ] **Step 3: Implement** — in `get_goods`, add the two columns to the inner SELECT. Change the first line of the `inner` string from:

```python
              SELECT g.ID, g.ARTICOL, g.DENUMIRE, g.BRAND, g.FURNIZOR,
                     g.ANGRO, g.IONLINE, g.RETAIL1, g.STOC, g.COD_UNIVERS,
```
to:
```python
              SELECT g.ID, g.ARTICOL, g.DENUMIRE, g.BRAND, g.FURNIZOR,
                     g.ANGRO, g.IONLINE, g.RETAIL1, g.STOC, g.COD_UNIVERS,
                     g.PHOTO_URL, g.IMAGE_LINK,
```

Then in `get_univers_card`, after fetching `u` and `mpt`, add a best-effort image lookup from the feed and include it in the returned data:

```python
            img = _rows(db.execute_query(
                "SELECT PHOTO_URL, IMAGE_LINK FROM BIRO26_GOODS "
                "WHERE COD_UNIVERS = :c AND ROWNUM = 1", {"c": cod}))
            photo = img[0] if img else {}
            return {"success": True,
                    "data": {"univers": u[0], "mpt": mpt[0] if mpt else None,
                             "photo_url": photo.get("photo_url"),
                             "image_link": photo.get("image_link")}}
```
(Replace the existing `return {"success": True, "data": {"univers": u[0], "mpt": mpt[0] if mpt else None}}`.)

- [ ] **Step 4: Run → pass**

Run: `./venv/bin/python -m pytest tests/test_biro26.py -q`
Expected: all pass.

- [ ] **Step 5: Live check**

Run:
```bash
./venv/bin/python -c "
from models.biro26_oracle_store import Biro26Store
g=Biro26Store.get_goods(limit=3)
print('img urls:', [d.get('photo_url') for d in g['data']])"
```
Expected: at least one real URL printed.

- [ ] **Step 6: Commit**

```bash
git add models/biro26_oracle_store.py tests/test_biro26.py
git commit -m "feat(biro26): expose product image URLs (source grid + dictionary card)"
```

## Task 2: Image thumbnails + lightbox in UI

**Files:**
- Modify: `templates/biro26/backoffice.html` (add lightbox modal + an image column header in the source table)
- Modify: `static/biro26/backoffice-tabs.js` (render thumbnails, lightbox open/close, card image)

- [ ] **Step 1: Add the lightbox modal** — in `templates/biro26/backoffice.html`, right after the merge-groups modal (`<div class="modal-backdrop" id="modal-merge">...</div>`), add:

```html
<!-- ── LIGHTBOX (image viewer) ─────────────────────────────── -->
<div class="modal-backdrop" id="modal-image" onclick="closeModal('modal-image')">
  <div class="modal" style="width:auto;max-width:90vw" onclick="event.stopPropagation()">
    <div class="modal-header">
      <span style="font-size:16px">🖼️</span>
      <h3 data-i18n="img_title"></h3>
      <button class="modal-close" onclick="closeModal('modal-image')">×</button>
    </div>
    <div class="modal-body" style="text-align:center">
      <img id="lightbox-img" src="" alt="" style="max-width:80vw;max-height:70vh;border-radius:8px">
      <div style="margin-top:10px"><a id="lightbox-link" href="#" target="_blank" rel="noopener" class="btn" data-i18n="img_open"></a></div>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Add an image column to the source table header** — in the source table `<thead><tr>` (the one with `col_articol`), add as the FIRST `<th>`:

```html
              <th data-i18n="col_image"></th>
```
and bump the loading-row `colspan="10"` to `colspan="11"` in `<tbody id="src-body">`.

- [ ] **Step 3: Add i18n keys** — in `templates/biro26/backoffice.html`, inside each of `I18N.ru`, `I18N.ro`, `I18N.en`, add these keys (use the right language for each block):
  - ru: `col_image: 'Фото', img_title: 'Изображение', img_open: 'Открыть в новой вкладке',`
  - ro: `col_image: 'Foto', img_title: 'Imagine', img_open: 'Deschide în filă nouă',`
  - en: `col_image: 'Photo', img_title: 'Image', img_open: 'Open in new tab',`

- [ ] **Step 4: Render thumbnails + lightbox in JS** — in `static/biro26/backoffice-tabs.js`:

(a) Add helpers near the top (after `const API`):
```javascript
function imgCell(url) {
  if (!url) return '<td></td>';
  const u = escapeHtml(url);
  return '<td><img src="' + u + '" loading="lazy" referrerpolicy="no-referrer" ' +
    'style="width:38px;height:38px;object-fit:cover;border-radius:4px;cursor:pointer" ' +
    'onclick="openLightbox(\'' + u + '\')" ' +
    'onerror="this.style.display=\'none\'"></td>';
}
function openLightbox(url) {
  el('lightbox-img').src = url;
  el('lightbox-link').href = url;
  el('modal-image').classList.add('open');
}
```

(b) In `loadGoods()`, prepend the image cell to each row. Change the row template so the first cell is `imgCell(g.photo_url || g.image_link)` — i.e. update the `tbody.innerHTML = rows.map(g => '<tr>' +` to start with `imgCell(g.photo_url || g.image_link) +` before `'<td class="mono">' + escapeHtml(g.articol)...`. Also change the loading/empty `emptyRow(tbody, 10, ...)` calls in `loadGoods` to `11`.

(c) In `loadUniversCard()`, after building `html`, prepend an image if present. After `const u = r.data.univers || {};` add:
```javascript
  const cardImg = (r.data.photo_url || r.data.image_link)
    ? '<div style="text-align:center;margin-bottom:10px"><img src="' +
      escapeHtml(r.data.photo_url || r.data.image_link) + '" referrerpolicy="no-referrer" ' +
      'style="max-width:100%;max-height:180px;border-radius:8px;cursor:pointer" ' +
      'onclick="openLightbox(this.src)" onerror="this.style.display=\'none\'"></div>'
    : '';
```
and prepend `cardImg` to the `body.innerHTML = ...` assignment (i.e. `body.innerHTML = cardImg + '<div class="detail-section-title">TMS_UNIVERS</div>' + ...`).

- [ ] **Step 5: Verify (browser)**

Start server, log in, open `/UNA.md/orasldev/biro26-backoffice`, Source tab. Confirm thumbnails render and clicking opens the lightbox. (Use the project run pattern: `./venv/bin/python app.py`, port 3003, login ADMIN.)

```bash
./venv/bin/python -c "import app; print('import OK')"
node -c static/biro26/backoffice-tabs.js && echo "js OK"
```

- [ ] **Step 6: Commit**

```bash
git add templates/biro26/backoffice.html static/biro26/backoffice-tabs.js
git commit -m "feat(biro26): image thumbnails + lightbox (source grid + product card)"
```

---

# STAGE 2 — Import wizard (wisepim-style)

## Task 3: Store + API for source columns and sample

**Files:**
- Modify: `models/biro26_oracle_store.py` (add `source_columns`, `source_sample`)
- Modify: `controllers/biro26_controller.py`
- Modify: `app.py`
- Test: `tests/test_biro26.py`

- [ ] **Step 1: Write failing tests**

```python
# ── stage 2: source columns/sample ──────────────────────────────────

def test_source_columns_rejects_bad_name():
    r = Biro26Store.source_columns("BIRO26_GOODS; DROP")
    assert r["success"] is False

def test_source_columns_ok():
    cols = ["ID","ARTICOL","DENUMIRE"]
    fake = _FakeBiro26DB([(1,"a","b")], cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.source_columns("BIRO26_GOODS")
    assert r["success"] and r["data"] == ["ID","ARTICOL","DENUMIRE"]
```

- [ ] **Step 2: Run → fail** (`AttributeError: source_columns`)

Run: `./venv/bin/python -m pytest tests/test_biro26.py::test_source_columns_ok -v`

- [ ] **Step 3: Implement** — add to `Biro26Store` (and a module-level identifier validator near `_q`):

```python
import re as _re
_IDENT_RE = _re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,60}$")

def _is_ident(name: str) -> bool:
    return bool(name and _IDENT_RE.match(name))
```
```python
    @staticmethod
    def source_columns(source: str) -> Dict[str, Any]:
        """Column names of a table/view source (identifier-validated)."""
        if not _is_ident(source):
            return {"success": False, "error": "invalid source name"}
        try:
            r = Biro26DB().execute_query(
                f"SELECT * FROM {source} WHERE ROWNUM = 0")
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True, "data": list(r.get("columns", []))}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def source_sample(source: str, limit: int = 20) -> Dict[str, Any]:
        if not _is_ident(source):
            return {"success": False, "error": "invalid source name"}
        try:
            r = Biro26DB().execute_query(
                f"SELECT * FROM {source} WHERE ROWNUM <= :n", {"n": int(limit)})
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True, "columns": list(r.get("columns", [])),
                    "data": [list(row) for row in r.get("data", [])]}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Controller handlers** — add to `controllers/biro26_controller.py`:

```python
    @staticmethod
    def source_columns() -> Dict[str, Any]:
        return Biro26Store.source_columns(request.args.get("source", "BIRO26_GOODS"))

    @staticmethod
    def source_sample() -> Dict[str, Any]:
        return Biro26Store.source_sample(
            request.args.get("source", "BIRO26_GOODS"),
            request.args.get("limit", 20, type=int))
```

- [ ] **Step 5: Routes** — in the Biro26 API block of `app.py`, add:

```python
@app.route('/api/biro26/source/columns', methods=['GET'])
def api_biro26_source_columns():
    return _b26(Biro26Controller.source_columns)

@app.route('/api/biro26/source/sample', methods=['GET'])
def api_biro26_source_sample():
    return _b26(Biro26Controller.source_sample)
```

- [ ] **Step 6: Run tests + import**

Run: `./venv/bin/python -m pytest tests/test_biro26.py -q && ./venv/bin/python -c "import app; print('ok')"`
Expected: all pass, `ok`.

- [ ] **Step 7: Live check**

```bash
./venv/bin/python -c "
from models.biro26_oracle_store import Biro26Store
print('cols:', Biro26Store.source_columns('BIRO26_GOODS')['data'][:6])
print('sample rows:', len(Biro26Store.source_sample('BIRO26_GOODS',5)['data']))"
```

- [ ] **Step 8: Commit**

```bash
git add models/biro26_oracle_store.py controllers/biro26_controller.py app.py tests/test_biro26.py
git commit -m "feat(biro26): source columns + sample endpoints (wizard backing)"
```

## Task 4: Wizard tab UI (Sursă → Mapare → Verificare → Import)

**Files:**
- Modify: `templates/biro26/backoffice.html` (new tab button + panel + stepper markup + i18n)
- Modify: `static/biro26/backoffice-tabs.js` (wizard state machine + mapping screen)

- [ ] **Step 1: Add the tab button** — in the `.tab-strip`, add after `tab-mapping` (or before it) a new tab:

```html
    <div class="tab-btn" id="tab-wizard" onclick="showTab('wizard')" data-i18n="tab_wizard"></div>
```
Register it in the JS `TABS` array and the `showTab` loader (Step 4 below).

- [ ] **Step 2: Add the wizard panel** — add a new `<div class="panel" id="panel-wizard">` after the mapping panel, containing:
  - a stepper header with 4 step chips (`#wiz-step-1..4`);
  - step 1 body `#wiz-body-1`: source `<select id="wiz-source">` (option `BIRO26_GOODS`), active-profile note, row count, "Înainte";
  - step 2 body `#wiz-body-2`: `<table id="wiz-map-table">` (target field | source column `<select>` | sample preview), "Înapoi/Înainte";
  - step 3 body `#wiz-body-3`: `<button>` "Rulează validarea" + `<div class="report-panel" id="wiz-validate-report">`, "Înapoi/Înainte";
  - step 4 body `#wiz-body-4`: buttons for `import_univers` / full chain + `<div class="report-panel" id="wiz-import-report">`.
  Use existing classes (`.btn`, `.report-panel`, `.data-table`, `.form-group`). Mark all labels with `data-i18n`.

- [ ] **Step 3: Add i18n keys** — add to each language block:
  - keys: `tab_wizard` ('Импорт (мастер)' / 'Import (asistent)' / 'Import (wizard)'), `wiz_s1`,`wiz_s2`,`wiz_s3`,`wiz_s4` (step titles: Источник/Sursă/Source, Сопоставление/Mapare/Mapping, Проверка/Verificare/Validate, Импорт/Import/Import), `wiz_back` (Назад/Înapoi/Back), `wiz_next` (Далее/Înainte/Next), `wiz_run_validate`, `wiz_run_import`, `wiz_col_target` (Целевое поле/Câmp țintă/Target field), `wiz_col_source` (Колонка источника/Coloană sursă/Source column), `wiz_col_sample` (Пример/Exemplu/Sample), `wiz_const` (константа/constantă/constant).

- [ ] **Step 4: Wizard JS** — in `static/biro26/backoffice-tabs.js`:

(a) Register tab: change `const TABS = ['source','dict','groups','prices','mapping'];` to include `'wizard'`, and in `showTab` add `if (id === 'wizard') { wizardInit(); }`.

(b) Define the target→source mapping rows (the g_col_* that map to a source column; constants are handled in the existing Mapping tab):
```javascript
const WIZ_TARGETS = [
  {param:'col_key',      label:'COD_UNIVERS (key)'},
  {param:'col_articol',  label:'CODVECHI ← articol'},
  {param:'col_denumire', label:'DENUMIREA ← denumire'},
  {param:'col_retail',   label:'PRETV ← retail'},
  {param:'col_angro',    label:'PRETV1 ← angro'},
  {param:'col_ionline',  label:'PRETV2 ← ionline'},
  {param:'col_brand',    label:'group ← brand'},
];
let wizState = {step:1, source:'BIRO26_GOODS', columns:[], sample:{columns:[],data:[]}, mapping:{}};
```

(c) `wizardInit()` loads the active profile (`/mapping/profiles` → default id → `/mapping/profiles/<id>`) into `wizState.mapping`, loads columns+sample for the source, then `wizRender()`.
```javascript
async function wizardInit() {
  const src = el('wiz-source') ? el('wiz-source').value : 'BIRO26_GOODS';
  wizState.source = src;
  const pr = await apiGet(API + '/mapping/profiles');
  const active = (pr.data||[]).find(p=>String(p.is_default)==='1');
  if (active) { const d = await apiGet(API+'/mapping/profiles/'+active.id);
                wizState.mapping = (d.data && d.data.params) || {}; wizState.activeId = active.id; }
  const c = await apiGet(API+'/source/columns?source='+encodeURIComponent(src));
  wizState.columns = c.data || [];
  const s = await apiGet(API+'/source/sample?source='+encodeURIComponent(src)+'&limit=10');
  wizState.sample = {columns:s.columns||[], data:s.data||[]};
  wizState.step = 1; wizRender();
}
```

(d) `wizGoto(step)` sets `wizState.step` (1..4) and calls `wizRender()`. `wizRender()` toggles `#wiz-body-N` visibility and active chip classes, and for step 2 builds the mapping table:
```javascript
function wizSampleFor(colName) {
  const i = wizState.sample.columns.indexOf(colName);
  if (i < 0) return '';
  const vals = wizState.sample.data.slice(0,3).map(r => r[i]).filter(v=>v!=null);
  return escapeHtml(vals.join(', '));
}
function wizRenderMapTable() {
  const opts = ['<option value=""></option>'].concat(
    wizState.columns.map(c=>'<option value="'+escapeHtml(c)+'">'+escapeHtml(c)+'</option>')).join('');
  el('wiz-map-table').querySelector('tbody').innerHTML = WIZ_TARGETS.map(tg => {
    const cur = wizState.mapping[tg.param] || '';
    const sel = opts.replace('value="'+escapeHtml(cur)+'"','value="'+escapeHtml(cur)+'" selected');
    return '<tr><td>'+escapeHtml(tg.label)+'</td>'+
      '<td><select class="f-select" data-param="'+tg.param+'" onchange="wizOnMap(this)">'+sel+'</select></td>'+
      '<td class="muted">'+wizSampleFor(cur)+'</td></tr>';
  }).join('');
}
function wizOnMap(selEl){ wizState.mapping[selEl.dataset.param]=selEl.value;
  selEl.closest('tr').lastElementChild.textContent = wizSampleFor(selEl.value); }
```

(e) Step 2 "Înainte" saves the mapping to the active profile before advancing:
```javascript
async function wizSaveMapping() {
  if (!wizState.activeId) { toast(t('err_generic'),'err'); return; }
  const params = {}; WIZ_TARGETS.forEach(tg=>{ if(wizState.mapping[tg.param]) params[tg.param]=wizState.mapping[tg.param]; });
  const r = await apiPut(API+'/mapping/profiles/'+wizState.activeId, {params});
  if (r.success){ toast(t('saved'),'ok'); wizGoto(3); }
}
```

(f) Step 3 validate → `confirmAndRun`-free read-only POST:
```javascript
async function wizValidate(){ const r=await apiPost(API+'/goods/validate',{}); renderReport('wiz-validate-report', r); }
```

(g) Step 4 import (confirmed):
```javascript
async function wizImport(){ if(!confirmAction('confirm_univers_import')) return;
  const r=await apiPost(API+'/univers/import',{}); renderReport('wiz-import-report', r); }
```
Wire the panel's buttons to `wizGoto(n)`, `wizSaveMapping()`, `wizValidate()`, `wizImport()`, and `#wiz-source` `onchange="wizardInit()"`.

- [ ] **Step 5: Verify (browser + static checks)**

```bash
./venv/bin/python -c "import app; print('ok')" && node -c static/biro26/backoffice-tabs.js && echo "js OK"
```
Then in browser: open wizard tab, confirm 4 steps navigate, mapping dropdowns list source columns with sample previews, validate shows the RO/EN report.

- [ ] **Step 6: Commit**

```bash
git add templates/biro26/backoffice.html static/biro26/backoffice-tabs.js
git commit -m "feat(biro26): wisepim-style 4-step import wizard tab"
```

---

# STAGE 3 — AI + any SELECT

## Task 5: YBIRO_SRC_DEF table + deploy

**Files:**
- Create: `sql/biro26/02_biro26_sources.sql`
- Create: `deploy_biro26_sources.py`

- [ ] **Step 1: Write the DDL** — `sql/biro26/02_biro26_sources.sql`:

```sql
-- Biro26 source definitions (any SELECT -> view). Oracle 11g (seq+trigger, no IDENTITY).
-- RO/EN comments only. Target: officeplus.
CREATE TABLE YBIRO_SRC_DEF (
  id          NUMBER PRIMARY KEY,
  name        VARCHAR2(60) NOT NULL,     -- RO: nume sursa / EN: source name
  select_sql  CLOB,                       -- RO: interogarea / EN: the query
  view_name   VARCHAR2(40),              -- RO: vederea creata / EN: created view
  md_path     VARCHAR2(200),             -- RO: fisier descriere / EN: description file
  created_at  TIMESTAMP DEFAULT SYSTIMESTAMP,
  created_by  VARCHAR2(60) DEFAULT USER,
  CONSTRAINT uq_ybiro_src_def_name UNIQUE (name)
);
CREATE SEQUENCE YBIRO_SRC_DEF_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER YBIRO_SRC_DEF_BI
  BEFORE INSERT ON YBIRO_SRC_DEF FOR EACH ROW WHEN (NEW.id IS NULL)
BEGIN
  SELECT YBIRO_SRC_DEF_SEQ.NEXTVAL INTO :NEW.id FROM dual;
END;
/
```

- [ ] **Step 2: Write the deploy script** — `deploy_biro26_sources.py` (mirror `deploy_biro26_app_tables.py`: idempotent, runs the 3 statements via `Biro26DB().execute_dml`/`call_proc`; checks `all_objects` for `YBIRO_SRC_DEF` first; also probes `CREATE VIEW` privilege by creating+dropping a throwaway view `V_BIRO26_SRC__PRIV` and reports clearly if it fails).

```python
#!/usr/bin/env python3
"""Deploy Biro26 source-definition table + verify CREATE VIEW privilege (officeplus 11g)."""
import sys
from models.biro26_db import Biro26DB

DDL_TABLE = """CREATE TABLE YBIRO_SRC_DEF (
  id NUMBER PRIMARY KEY, name VARCHAR2(60) NOT NULL, select_sql CLOB,
  view_name VARCHAR2(40), md_path VARCHAR2(200),
  created_at TIMESTAMP DEFAULT SYSTIMESTAMP, created_by VARCHAR2(60) DEFAULT USER,
  CONSTRAINT uq_ybiro_src_def_name UNIQUE (name))"""
DDL_SEQ = "CREATE SEQUENCE YBIRO_SRC_DEF_SEQ START WITH 1 INCREMENT BY 1 NOCACHE"
DDL_TRG = """CREATE OR REPLACE TRIGGER YBIRO_SRC_DEF_BI
  BEFORE INSERT ON YBIRO_SRC_DEF FOR EACH ROW WHEN (NEW.id IS NULL)
BEGIN SELECT YBIRO_SRC_DEF_SEQ.NEXTVAL INTO :NEW.id FROM dual; END;"""

def main() -> int:
    db = Biro26DB()
    # privilege probe
    pv = db.execute_dml("CREATE VIEW V_BIRO26_SRC__PRIV AS SELECT 1 X FROM dual")
    if pv.get("success"):
        db.execute_dml("DROP VIEW V_BIRO26_SRC__PRIV")
        print("[priv] CREATE VIEW: OK")
    else:
        print("[priv] CREATE VIEW FAILED:", pv.get("message"))
        return 1
    ex = db.execute_query("SELECT COUNT(*) FROM all_objects WHERE object_name='YBIRO_SRC_DEF'")
    if ex["success"] and ex["data"] and ex["data"][0][0] > 0:
        print("YBIRO_SRC_DEF already exists."); return 0
    for label, sql, cap in [("table",DDL_TABLE,False),("seq",DDL_SEQ,False),("trigger",DDL_TRG,True)]:
        r = db.call_proc(sql+";") if cap else db.execute_dml(sql)
        print(f"  [{'OK' if r.get('success') else 'ERR'}] {label}", "" if r.get('success') else r.get('message'))
        if not r.get("success"): return 1
    print("Done."); return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run it live**

Run: `./venv/bin/python deploy_biro26_sources.py`
Expected: `[priv] CREATE VIEW: OK`, table/seq/trigger created (or already exists). **If CREATE VIEW fails, stop and report** — Stage 3's view materialization can't work without it; the user must grant the privilege.

- [ ] **Step 4: Commit**

```bash
git add sql/biro26/02_biro26_sources.sql deploy_biro26_sources.py
git commit -m "feat(biro26): YBIRO_SRC_DEF table + deploy (11g) with CREATE VIEW probe"
```

## Task 6: `biro26_sources` — SELECT guard, view, source CRUD

**Files:**
- Create: `models/biro26_sources.py`
- Test: `tests/test_biro26.py`

- [ ] **Step 1: Write failing tests**

```python
# ── stage 3: sources ────────────────────────────────────────────────
from models.biro26_sources import is_safe_select, view_name_for, Biro26Sources

def test_is_safe_select_accepts_plain_select():
    assert is_safe_select("SELECT a, b FROM t WHERE x=1")
    assert is_safe_select("  with q as (select 1 a from dual) select * from q")

def test_is_safe_select_rejects_dml_and_multi():
    assert not is_safe_select("SELECT 1; DROP TABLE t")
    assert not is_safe_select("UPDATE t SET x=1")
    assert not is_safe_select("select * from t; delete from t")
    assert not is_safe_select("")

def test_view_name_for_sanitizes():
    assert view_name_for("My Feed!") == "V_BIRO26_SRC_MY_FEED"
    assert view_name_for("abc") == "V_BIRO26_SRC_ABC"
```

- [ ] **Step 2: Run → fail** (`ModuleNotFoundError`)

Run: `./venv/bin/python -m pytest tests/test_biro26.py::test_is_safe_select_accepts_plain_select -v`

- [ ] **Step 3: Implement `models/biro26_sources.py`**

```python
"""Biro26 source definitions — register any read-only SELECT as an import source.

The SELECT is materialized as a view V_BIRO26_SRC_<name> that the YBIRO package
imports from (g_tbl_goods -> view). All access via the thick subprocess Biro26DB.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows, _result

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|"
    r"begin|declare|call|execute|exec|comment|rename|lock)\b", re.IGNORECASE)


def is_safe_select(sql: str) -> bool:
    if not sql or not sql.strip():
        return False
    s = sql.strip().rstrip(";").strip()
    if ";" in s:                      # only a single statement
        return False
    low = s.lower()
    if not (low.startswith("select") or low.startswith("with")):
        return False
    if _FORBIDDEN.search(s):
        return False
    return True


def view_name_for(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return "V_BIRO26_SRC_" + slug


class Biro26Sources:
    @staticmethod
    def sample(sql: str, limit: int = 20) -> Dict[str, Any]:
        if not is_safe_select(sql):
            return {"success": False, "error": "only a single read-only SELECT is allowed"}
        inner = sql.strip().rstrip(";")
        r = Biro26DB().execute_query(
            f"SELECT * FROM ({inner}) WHERE ROWNUM <= :n", {"n": int(limit)})
        if not r.get("success"):
            return {"success": False, "error": r.get("message")}
        return {"success": True, "columns": list(r.get("columns", [])),
                "data": [list(row) for row in r.get("data", [])]}

    @staticmethod
    def list_sources() -> Dict[str, Any]:
        return _result(Biro26DB().execute_query(
            "SELECT id, name, view_name, md_path, "
            "TO_CHAR(created_at,'DD.MM.YYYY HH24:MI') created_at FROM YBIRO_SRC_DEF ORDER BY name"))

    @staticmethod
    def get_source(name: str) -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT id, name, view_name, md_path, select_sql FROM YBIRO_SRC_DEF WHERE name=:n",
            {"n": name}))
        return {"success": True, "data": rows[0]} if rows else {"success": False, "error": "not found"}

    @staticmethod
    def create_source(name: str, sql: str, md_path: Optional[str] = None) -> Dict[str, Any]:
        if not is_safe_select(sql):
            return {"success": False, "error": "only a single read-only SELECT is allowed"}
        from models.biro26_oracle_store import _is_ident
        if not _is_ident(name):
            return {"success": False, "error": "invalid source name (use letters/digits/_)"}
        view = view_name_for(name)
        inner = sql.strip().rstrip(";")
        db = Biro26DB()
        # create or replace the view
        cv = db.execute_dml(f"CREATE OR REPLACE VIEW {view} AS {inner}")
        if not cv.get("success"):
            return {"success": False, "error": cv.get("message")}
        # upsert the definition (one tx)
        res = db.execute_script([
            {"sql": "DELETE FROM YBIRO_SRC_DEF WHERE name=:n", "params": {"n": name}, "kind": "dml"},
            {"sql": "INSERT INTO YBIRO_SRC_DEF(name, select_sql, view_name, md_path) "
                    "VALUES(:n, :s, :v, :m)",
             "params": {"n": name, "s": inner, "v": view, "m": md_path}, "kind": "dml"},
        ])
        if not res.get("success"):
            return {"success": False, "error": res.get("message")}
        return {"success": True, "data": {"name": name, "view_name": view}}

    @staticmethod
    def drop_source(name: str) -> Dict[str, Any]:
        view = view_name_for(name)
        db = Biro26DB()
        db.execute_dml(f"DROP VIEW {view}")  # ignore if missing
        return db.execute_dml("DELETE FROM YBIRO_SRC_DEF WHERE name=:n", {"n": name})
```

- [ ] **Step 4: Run → pass**

Run: `./venv/bin/python -m pytest tests/test_biro26.py -q`
Expected: all pass.

- [ ] **Step 5: Live check (create/sample/drop a trivial source)**

```bash
./venv/bin/python -c "
from models.biro26_sources import Biro26Sources as S
print('sample:', S.sample('SELECT 1 AS A, 2 AS B FROM dual')['columns'])
print('create:', S.create_source('selftest','SELECT 1 AS A FROM dual'))
print('list:', [x['name'] for x in S.list_sources()['data']])
print('drop:', S.drop_source('selftest')['success'])"
```
Expected: columns `['A','B']`, create success with view name, listed, dropped.

- [ ] **Step 6: Commit**

```bash
git add models/biro26_sources.py tests/test_biro26.py
git commit -m "feat(biro26): source-def store — SELECT guard, view materialization, CRUD"
```

## Task 7: `biro26_ai` — md draft + mapping suggestion + heuristic fallback

**Files:**
- Create: `models/biro26_ai.py`
- Test: `tests/test_biro26.py`

- [ ] **Step 1: Write failing tests**

```python
# ── stage 3: AI helper ──────────────────────────────────────────────
from models.biro26_ai import heuristic_mapping, extract_json, suggest_mapping

def test_heuristic_mapping_matches_common_names():
    cols = ["ARTICOL","DENUMIRE","RETAIL1","ANGRO","IONLINE","BRAND","COD_UNIVERS"]
    m = heuristic_mapping(cols)
    assert m["col_articol"] == "ARTICOL"
    assert m["col_denumire"] == "DENUMIRE"
    assert m["col_retail"] == "RETAIL1"
    assert m["col_brand"] == "BRAND"
    assert m["col_key"] == "COD_UNIVERS"

def test_extract_json_from_noisy_text():
    assert extract_json('blah {"col_articol": "ART"} tail')["col_articol"] == "ART"
    assert extract_json("no json here") is None

def test_suggest_mapping_falls_back_when_ai_unavailable():
    cols = ["ART","NAME","PRICE"]
    with patch("models.biro26_ai.is_available", return_value=False):
        r = suggest_mapping(cols, [], "")
    assert r["success"] and r["source"] == "heuristic"
```

- [ ] **Step 2: Run → fail** (`ModuleNotFoundError`)

Run: `./venv/bin/python -m pytest tests/test_biro26.py::test_heuristic_mapping_matches_common_names -v`

- [ ] **Step 3: Implement `models/biro26_ai.py`**

```python
"""Biro26 AI helper — draft source descriptions and suggest column mappings.

Wraps ai_helper.ask_llm_via_selenium (browser LLM). Any failure/timeout/absence
falls back to a deterministic name-similarity heuristic so the wizard always works.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

try:
    from ai_helper import ask_llm_via_selenium, is_ai_available
except Exception:  # ai_helper optional
    ask_llm_via_selenium = None
    def is_ai_available() -> bool:  # type: ignore
        return False

# target g_col_* params that bind to a SOURCE column (constants handled elsewhere)
_TARGET_PARAMS = ["col_key", "col_articol", "col_denumire",
                  "col_retail", "col_angro", "col_ionline", "col_brand"]

# heuristic keyword hints per target param (first match wins)
_HINTS = {
    "col_key":      ["cod_univers", "cod_un", "key", "guid", "id"],
    "col_articol":  ["articol", "artic", "sku", "mpn", "cod", "code", "art"],
    "col_denumire": ["denumire", "denum", "name", "nume", "title", "titlu"],
    "col_retail":   ["retail", "pret", "price", "raft"],
    "col_angro":    ["angro", "whole", "opt"],
    "col_ionline":  ["ionline", "online", "web", "internet"],
    "col_brand":    ["brand", "marca", "marka", "producator"],
}


def is_available() -> bool:
    try:
        return bool(is_ai_available())
    except Exception:
        return False


def heuristic_mapping(columns: List[str]) -> Dict[str, str]:
    low = {c.lower(): c for c in columns}
    used = set()
    out: Dict[str, str] = {}
    for param, hints in _HINTS.items():
        for h in hints:
            hit = next((orig for lc, orig in low.items()
                        if h in lc and orig not in used), None)
            if hit:
                out[param] = hit
                used.add(hit)
                break
    return out


def extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _ask(prompt: str, timeout: int = 40) -> Optional[str]:
    if not (is_available() and ask_llm_via_selenium):
        return None
    try:
        return ask_llm_via_selenium(prompt, timeout=timeout)
    except Exception:
        return None


def draft_source_md(name: str, columns: List[str], samples: List[List[Any]]) -> str:
    sample_md = "\n".join(
        "| " + " | ".join(str(v) for v in row[:len(columns)]) + " |"
        for row in samples[:5])
    header = "| " + " | ".join(columns) + " |\n| " + " | ".join("---" for _ in columns) + " |"
    table = header + ("\n" + sample_md if sample_md else "")
    prompt = (f"Source '{name}'. Columns: {columns}. Sample rows:\n{table}\n"
              "Write a short Markdown description: for each column give its likely "
              "business meaning and type. RO + EN only, no Russian. Output Markdown only.")
    ai = _ask(prompt)
    if ai:
        return ai
    # fallback: plain column table
    return (f"# Source: {name}\n\n## Columns / Coloane\n\n{table}\n")


def suggest_mapping(columns: List[str], samples: List[List[Any]], md: str) -> Dict[str, Any]:
    if is_available():
        prompt = (
            "Map source columns to target import params. "
            f"Target params: {_TARGET_PARAMS}. Source columns: {columns}. "
            f"Description:\n{md[:1500]}\n"
            "Return ONLY a JSON object mapping each target param to the best source "
            "column name (or omit if none). Example: "
            '{"col_articol":"ART","col_denumire":"NAME"}')
        parsed = extract_json(_ask(prompt) or "")
        if parsed:
            mapping = {k: v for k, v in parsed.items()
                       if k in _TARGET_PARAMS and v in columns}
            if mapping:
                return {"success": True, "mapping": mapping, "source": "ai"}
    return {"success": True, "mapping": heuristic_mapping(columns), "source": "heuristic"}
```

- [ ] **Step 4: Run → pass**

Run: `./venv/bin/python -m pytest tests/test_biro26.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add models/biro26_ai.py tests/test_biro26.py
git commit -m "feat(biro26): AI helper (md draft + mapping suggestion, heuristic fallback)"
```

## Task 8: Controller + routes for sources & AI

**Files:**
- Modify: `controllers/biro26_controller.py`
- Modify: `app.py`
- Modify: `tests/test_biro26.py`

- [ ] **Step 1: Write failing test**

```python
def test_controller_create_source_requires_select():
    from controllers.biro26_controller import Biro26Controller
    with _app.test_request_context(json={"name":"x","sql":"DELETE FROM t"}):
        with patch("controllers.biro26_controller.Biro26Sources") as S:
            S.create_source.return_value = {"success": False, "error": "only a single read-only SELECT is allowed"}
            r = Biro26Controller.create_source()
    assert r["success"] is False
```

- [ ] **Step 2: Run → fail** (`AttributeError: create_source`)

- [ ] **Step 3: Implement controller** — add imports and handlers to `controllers/biro26_controller.py`:

```python
from models.biro26_sources import Biro26Sources
from models import biro26_ai
from models.biro26_oracle_store import G_PARAMS  # already imported; keep single import
import os
```
```python
    # -- sources (any SELECT) ----------------------------------------
    @staticmethod
    def list_sources() -> Dict[str, Any]:
        return Biro26Sources.list_sources()

    @staticmethod
    def sample_select() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Sources.sample(d.get("sql", ""), d.get("limit", 20))

    @staticmethod
    def create_source() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("name") or not d.get("sql"):
            return {"success": False, "error": "name and sql are required"}
        md = d.get("md")
        md_path = None
        if md:
            import os as _os
            sd = _os.path.join(_os.path.dirname(__file__), "..", "docs", "Biro26", "sources")
            _os.makedirs(sd, exist_ok=True)
            md_path = f"docs/Biro26/sources/{d['name']}.md"
            with open(_os.path.join(sd, f"{d['name']}.md"), "w", encoding="utf-8") as f:
                f.write(md)
        return Biro26Sources.create_source(d["name"], d["sql"], md_path)

    @staticmethod
    def ai_draft_md() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        s = Biro26Sources.sample(d.get("sql", ""), 10)
        if not s.get("success"):
            return s
        md = biro26_ai.draft_source_md(d.get("name", "source"), s["columns"], s["data"])
        return {"success": True, "data": {"md": md, "columns": s["columns"]}}

    @staticmethod
    def ai_suggest_mapping() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        s = Biro26Sources.sample(d.get("sql", ""), 10)
        if not s.get("success"):
            return s
        r = biro26_ai.suggest_mapping(s["columns"], s["data"], d.get("md", ""))
        r["columns"] = s["columns"]
        return r
```

- [ ] **Step 4: Routes** — add to `app.py` Biro26 API block:

```python
@app.route('/api/biro26/sources', methods=['GET'])
def api_biro26_sources_list():
    return _b26(Biro26Controller.list_sources)

@app.route('/api/biro26/sources', methods=['POST'])
def api_biro26_sources_create():
    return _b26(Biro26Controller.create_source)

@app.route('/api/biro26/sources/sample', methods=['POST'])
def api_biro26_sources_sample():
    return _b26(Biro26Controller.sample_select)

@app.route('/api/biro26/sources/ai-draft-md', methods=['POST'])
def api_biro26_sources_ai_md():
    return _b26(Biro26Controller.ai_draft_md)

@app.route('/api/biro26/sources/ai-suggest-mapping', methods=['POST'])
def api_biro26_sources_ai_map():
    return _b26(Biro26Controller.ai_suggest_mapping)
```

- [ ] **Step 5: Run tests + import**

Run: `./venv/bin/python -m pytest tests/test_biro26.py -q && ./venv/bin/python -c "import app; print('routes', len([r for r in app.app.url_map.iter_rules() if 'biro26' in r.rule]))"`
Expected: pass; route count increased.

- [ ] **Step 6: Commit**

```bash
git add controllers/biro26_controller.py app.py tests/test_biro26.py
git commit -m "feat(biro26): controller+routes for SELECT sources and AI mapping"
```

## Task 9: Wizard Step-1 "Sursă nouă (SELECT)" + AI prefill + md editor

**Files:**
- Modify: `templates/biro26/backoffice.html` (Step-1 source UI: SELECT textarea, source dropdown of saved sources, md editor, AI buttons; i18n)
- Modify: `static/biro26/backoffice-tabs.js` (load saved sources into `#wiz-source`; new-source flow)

- [ ] **Step 1: Extend Step-1 markup** — in `#wiz-body-1`, add below the existing source `<select>`:
  - a collapsible "Sursă nouă (SELECT)" block: `<textarea id="wiz-sql">`, buttons "AI: descriere" (`onclick="wizAiDraft()"`) and "AI: mapare" (`onclick="wizAiMap()"`), a `<textarea id="wiz-md">` (editable description), name input `#wiz-newname`, and "Salvează sursa" (`onclick="wizSaveSource()"`).
  - Mark labels with `data-i18n`. Add keys to all 3 languages: `wiz_new_source` (Новый источник (SELECT) / Sursă nouă (SELECT) / New source (SELECT)), `wiz_ai_desc` (AI: описание / AI: descriere / AI: describe), `wiz_ai_map` (AI: маппинг / AI: mapare / AI: map), `wiz_save_source` (Сохранить источник / Salvează sursa / Save source), `wiz_src_name` (Имя / Nume / Name), `wiz_ai_unavailable` ('AI недоступен — эвристика' / 'AI indisponibil — euristică' / 'AI unavailable — heuristic').

- [ ] **Step 2: JS — load saved sources into the dropdown** — in `wizardInit()`, before reading `el('wiz-source').value`, populate it:
```javascript
  const srcList = await apiGet(API + '/sources');
  if (el('wiz-source')) {
    const saved = (srcList.data||[]).map(s=>'<option value="'+escapeHtml(s.view_name)+'">'+escapeHtml(s.name)+' ('+escapeHtml(s.view_name)+')</option>').join('');
    el('wiz-source').innerHTML = '<option value="BIRO26_GOODS">BIRO26_GOODS</option>' + saved;
  }
```

- [ ] **Step 3: JS — new-source flow**
```javascript
async function wizAiDraft() {
  const sql = val('wiz-sql'); if (!sql) return;
  setStatus(t('loading'));
  const r = await apiPost(API+'/sources/ai-draft-md', {name: val('wiz-newname')||'source', sql});
  setStatus('—');
  if (r.success) el('wiz-md').value = r.data.md;
}
async function wizAiMap() {
  const sql = val('wiz-sql'); if (!sql) return;
  setStatus(t('loading'));
  const r = await apiPost(API+'/sources/ai-suggest-mapping', {sql, md: val('wiz-md')});
  setStatus('—');
  if (r.success) {
    wizState.columns = r.columns || wizState.columns;
    Object.assign(wizState.mapping, r.mapping || {});
    if (r.source === 'heuristic') toast(t('wiz_ai_unavailable'), 'ok');
    wizGoto(2); wizRenderMapTable();
  }
}
async function wizSaveSource() {
  const name = val('wiz-newname'), sql = val('wiz-sql');
  if (!name || !sql) { toast(t('validation_required'),'err'); return; }
  const r = await apiPost(API+'/sources', {name, sql, md: val('wiz-md')});
  if (r.success) { toast(t('saved'),'ok'); await wizardInit();
    if (el('wiz-source')) el('wiz-source').value = r.data.view_name; wizardInit(); }
}
```

- [ ] **Step 4: Verify (static + browser)**

```bash
./venv/bin/python -c "import app; print('ok')" && node -c static/biro26/backoffice-tabs.js && echo "js OK"
```
Browser: paste `SELECT ARTICOL, DENUMIRE, RETAIL1 FROM BIRO26_GOODS WHERE ROWNUM<=50`, click "AI: mapare" → mapping prefilled (heuristic if AI off); "Salvează sursa" → appears in source dropdown.

- [ ] **Step 5: Commit**

```bash
git add templates/biro26/backoffice.html static/biro26/backoffice-tabs.js
git commit -m "feat(biro26): wizard new-SELECT source step with AI draft+mapping"
```

## Task 10: Docs + final verification

**Files:**
- Modify: `docs/Biro26/README_BIRO26.html` (sections for images, wizard, AI sources)
- Modify: `README.md` (extend the Biro26 entry)

- [ ] **Step 1: Update `docs/Biro26/README_BIRO26.html`** — add a section "Image viewing / Wizard / AI sources" describing: image columns + lightbox; the 4-step wizard tab; SELECT→view sources, `YBIRO_SRC_DEF`, `deploy_biro26_sources.py`, the read-only SELECT guard, and that AI uses `ai_helper` (Selenium) with heuristic fallback. List new endpoints (`/source/columns`, `/source/sample`, `/sources*`).

- [ ] **Step 2: Update `README.md`** — extend the Biro26 bullet: "просмотр изображений, мастер импорта (wisepim-стиль), AI-маппинг любого SELECT (через VIEW), таблица `YBIRO_SRC_DEF`".

- [ ] **Step 3: Full verification**

```bash
cd /Users/pt/Projects.AI/Artgranit
./venv/bin/python -m pytest tests/test_biro26.py -q          # all green
./venv/bin/python test_biro26_smoke.py | tail -3            # objects OK
./venv/bin/python -c "import app; print('biro26 routes:', len([r for r in app.app.url_map.iter_rules() if 'biro26' in r.rule]))"
node -c static/biro26/backoffice-tabs.js && echo "js OK"
grep -c init_oracle_client app.py models/biro26_db.py        # must be 0 0 (thin main app)
git diff --name-only main...HEAD                              # only biro26-related files
```
Expected: tests pass; routes increased; thin invariant holds; only module files changed.

- [ ] **Step 4: Commit**

```bash
git add docs/Biro26/README_BIRO26.html README.md
git commit -m "docs(biro26): document images, import wizard, AI SELECT sources"
```

---

## Self-Review (plan author)

**Spec coverage:**
- §3 images → Tasks 1–2 ✓
- §4 wizard (4 steps, mapping w/ sample preview) → Tasks 3–4 ✓
- §5 AI + any SELECT (guard, sample, md draft, view, mapping, persist) → Tasks 5–9 ✓ (guard=Task6, md/mapping=Task7, view/CRUD=Task6, table=Task5, UI=Task9)
- §5.2 biro26_ai contract (`is_available`, `draft_source_md`, `suggest_mapping`) → Task 7 ✓
- §5.3 YBIRO_SRC_DEF → Task 5 ✓
- §5.4 security (SELECT guard, identifier whitelist, binds, no secrets to AI) → Tasks 6,7,8 ✓
- §6 testing (guard, heuristic, JSON parse, view DDL/name, source store, image cols) → Tasks 1,3,6,7,8 ✓

**Placeholder scan:** no TBD/TODO; every code step has real code. UI tasks give concrete element IDs, i18n keys, and JS function bodies (targeted additions to existing files, since full re-listing of the 1000-line files is not warranted).

**Type/name consistency:** `is_safe_select`, `view_name_for`, `Biro26Sources.{sample,list_sources,get_source,create_source,drop_source}`, `biro26_ai.{is_available,heuristic_mapping,extract_json,draft_source_md,suggest_mapping}`, store `source_columns/source_sample`, controller `list_sources/sample_select/create_source/ai_draft_md/ai_suggest_mapping`, `_TARGET_PARAMS` ⊂ `G_PARAMS`, and the JS `wizState`/`WIZ_TARGETS`/`wiz*` names are used consistently across tasks. `_is_ident` is defined in Task 3 (store) and reused in Task 6.
