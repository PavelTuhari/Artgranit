/* =====================================================================
   Biro26 back-office — data loading + actions.
   Depends on globals defined inline in templates/biro26/backoffice.html:
     I18N, LANG, t(), setLang(), renderI18n(), showTab(), currentTab,
     fetchJSON/apiGet/apiPost/apiPut, confirmAction, confirmAndRun,
     renderReport, escapeHtml, toast, setStatus, dispName, badgeStatus,
     gParamNames, selectedUniversCod, selectedProfileId,
     *DebounceTimer vars.
   All endpoints are under /api/biro26 (see controller).
   ===================================================================== */

const API = '/api/biro26';

/* package g_* names that are "identifiers" (vs constants) for the mapping form */
const ID_PARAMS = ['tbl_goods','col_key','col_id','col_brand','col_articol',
                   'col_denumire','col_angro','col_ionline','col_retail','seq_key'];
const NUMERIC_PARAMS = ['len_codvechi','len_denumire','confus_max_cyr','codprice'];
const DATE_PARAMS = ['date_start','date_end'];

let activeProfileName = null;

/* ── small DOM helpers ─────────────────────────────────────────── */
function el(id) { return document.getElementById(id); }
function val(id) { const e = el(id); return e ? e.value : ''; }
function numVal(id, dflt) { const v = parseInt(val(id), 10); return isNaN(v) ? (dflt||0) : v; }
function emptyRow(tbody, cols, key) {
  return '<tr><td colspan="'+cols+'"><div class="empty-state"><p>'+t(key||'no_data')+'</p></div></td></tr>';
}
function fmtNum(v) { return (v === null || v === undefined || v === '') ? '' : v; }

/* =====================================================================
   BOOTSTRAP
   ===================================================================== */
document.addEventListener('DOMContentLoaded', async () => {
  setLang(LANG);
  await loadGParams();
  await refreshActiveProfile();
  showTab('source');
});

async function loadGParams() {
  const r = await apiGet(API + '/mapping/g-params');
  if (r.success) { gParamNames = r.data || []; }
}

async function refreshActiveProfile() {
  const r = await apiGet(API + '/mapping/profiles');
  if (r.success) {
    const active = (r.data || []).find(p => String(p.is_default) === '1');
    activeProfileName = active ? active.name : null;
    renderActiveProfileIndicator();
  }
}

function renderActiveProfileIndicator() {
  const ind = el('active-profile-indicator');
  if (!ind) return;
  if (activeProfileName) {
    ind.style.display = '';
    ind.textContent = t('active_profile') + ': ' + activeProfileName;
  } else {
    ind.style.display = 'none';
  }
}

/* =====================================================================
   TAB 1 — SOURCE FEED (BIRO26_GOODS)
   ===================================================================== */
function debounceLoadGoods() {
  clearTimeout(goodsDebounceTimer);
  goodsDebounceTimer = setTimeout(loadGoods, 350);
}

async function loadBrands() {
  const sel = el('src-brand');
  if (!sel || sel.dataset.loaded) return;
  const r = await apiGet(API + '/goods/brands');
  if (r.success) {
    const cur = sel.value;
    sel.innerHTML = '<option value="">' + t('f_all') + '</option>' +
      (r.data || []).map(b => '<option value="' + escapeHtml(b.brand) + '">' +
        escapeHtml(b.brand) + ' (' + b.cnt + ')</option>').join('');
    sel.value = cur;
    sel.dataset.loaded = '1';
  }
}

async function loadFurnizoriFilter() {
  const sel = el('src-furnizor');
  if (!sel || sel.dataset.loaded) return;
  const r = await apiGet(API + '/suppliers/furnizori');
  if (r.success) {
    const cur = sel.value;
    sel.innerHTML = '<option value="">' + t('f_all') + '</option>' +
      (r.data || []).map(f => '<option value="' + escapeHtml(f.furnizor) + '">' +
        escapeHtml(f.furnizor) + ' (' + f.cnt + ')</option>').join('');
    sel.value = cur;
    sel.dataset.loaded = '1';
  }
}

async function loadGoods() {
  const tbody = el('src-body');
  tbody.innerHTML = emptyRow(tbody, 10, 'loading');
  const qs = new URLSearchParams();
  if (val('src-search')) qs.set('search', val('src-search'));
  if (val('src-brand')) qs.set('brand', val('src-brand'));
  if (val('src-furnizor')) qs.set('furnizor', val('src-furnizor'));
  if (val('src-status')) qs.set('status', val('src-status'));
  qs.set('limit', '300');
  const r = await apiGet(API + '/goods?' + qs.toString());
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 10, 'no_data'); return; }
  const rows = r.data || [];
  el('src-count').textContent = rows.length;
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 10, 'no_data'); return; }
  tbody.innerHTML = rows.map(g => '<tr>' +
    '<td class="mono">' + escapeHtml(g.articol) + '</td>' +
    '<td>' + escapeHtml(g.denumire || '') + '</td>' +
    '<td>' + escapeHtml(g.brand || '') + '</td>' +
    '<td>' + escapeHtml(g.furnizor || '') + '</td>' +
    '<td class="num">' + fmtNum(g.angro) + '</td>' +
    '<td class="num">' + fmtNum(g.ionline) + '</td>' +
    '<td class="num">' + fmtNum(g.retail1) + '</td>' +
    '<td class="num">' + fmtNum(g.stoc) + '</td>' +
    '<td class="mono">' + fmtNum(g.cod_univers) + '</td>' +
    '<td>' + badgeStatus(g.row_status) + '</td>' +
    '</tr>').join('');
}

async function runGoodsAction(action) {
  const map = {
    'validate':    {url: API + '/goods/validate',    confirm: null},
    'prepare':     {url: API + '/goods/prepare',     confirm: 'act_prepare'},
    'assign-keys': {url: API + '/goods/assign-keys', confirm: 'act_assignkeys'},
  };
  const cfg = map[action];
  if (!cfg) return;
  if (cfg.confirm && !window.confirm(t(cfg.confirm) + ' — ' + t('confirm_univers_import'))) return;
  setStatus(t('loading'));
  const r = await apiPost(cfg.url, {});
  renderReport('src-report', r);
  setStatus(r.success ? t('ok_generic') : t('err_generic'));
  if (r.success && action !== 'validate') loadGoods();
}

/* =====================================================================
   TAB 2 — DICTIONARY (TMS_UNIVERS / TMS_MPT)
   ===================================================================== */
function debounceLoadUnivers() {
  clearTimeout(universDebounceTimer);
  universDebounceTimer = setTimeout(loadUnivers, 350);
}

async function loadUnivers() {
  const tbody = el('dict-body');
  tbody.innerHTML = emptyRow(tbody, 6, 'loading');
  const qs = new URLSearchParams();
  if (val('dict-search')) qs.set('search', val('dict-search'));
  if (val('dict-gr1')) qs.set('gr1', val('dict-gr1'));
  if (val('dict-arhiv')) qs.set('arhiv', val('dict-arhiv'));
  qs.set('limit', '300');
  const r = await apiGet(API + '/univers?' + qs.toString());
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 6, 'no_data'); return; }
  const rows = r.data || [];
  el('dict-count').textContent = rows.length;
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 6, 'no_data'); return; }
  tbody.innerHTML = rows.map(u =>
    '<tr onclick="loadUniversCard(' + u.cod + ', this)" style="cursor:pointer">' +
    '<td class="mono">' + u.cod + '</td>' +
    '<td class="mono">' + escapeHtml(u.codvechi || '') + '</td>' +
    '<td>' + escapeHtml(dispName(u) || u.denumirea || '') + '</td>' +
    '<td>' + escapeHtml(u.gr1 || '') + '</td>' +
    '<td>' + escapeHtml(u.um || '') + '</td>' +
    '<td>' + escapeHtml(u.isarhiv || '') + '</td>' +
    '</tr>').join('');
}

async function loadUniversCard(cod, rowEl) {
  selectedUniversCod = cod;
  document.querySelectorAll('#dict-body tr').forEach(tr => tr.classList.remove('row-selected'));
  if (rowEl) rowEl.classList.add('row-selected');
  const body = el('dict-detail-body');
  body.innerHTML = '<div class="empty-state"><p>' + t('loading') + '</p></div>';
  const r = await apiGet(API + '/univers/' + cod);
  if (!r.success || !r.data) { body.innerHTML = '<div class="empty-state"><p>' + t('no_data') + '</p></div>'; return; }
  const u = r.data.univers || {};
  const mpt = r.data.mpt;
  function fields(obj) {
    return Object.keys(obj).map(k =>
      '<div class="detail-field"><div class="df-label">' + escapeHtml(k) + '</div>' +
      '<div class="df-val">' + escapeHtml(obj[k] === null || obj[k] === undefined ? '—' : obj[k]) + '</div></div>'
    ).join('');
  }
  let html = '<div class="detail-section-title">TMS_UNIVERS</div>' +
             '<div class="detail-grid">' + fields(u) + '</div>';
  if (mpt) {
    html += '<div class="detail-section-title">TMS_MPT</div>' +
            '<div class="detail-grid">' + fields(mpt) + '</div>';
  } else {
    html += '<div class="detail-section-title">TMS_MPT</div><p class="muted">' + t('no_data') + '</p>';
  }
  body.innerHTML = html;
}

async function archiveSelectedUnivers() {
  if (!confirmAction('confirm_univers_archive')) return;
  setStatus(t('loading'));
  const r = await apiPost(API + '/univers/archive', {isarhiv: '1'});
  renderReport('dict-report', r);
  setStatus(r.success ? t('ok_generic') : t('err_generic'));
  if (r.success) loadUnivers();
}

/* =====================================================================
   TAB 3 — GROUPS / SUPPLIERS / CATEGORIES
   ===================================================================== */
async function loadGroups() {
  const tbody = el('grp-body');
  tbody.innerHTML = emptyRow(tbody, 6, 'loading');
  const cp = numVal('grp-codprice', 1);
  const r = await apiGet(API + '/groups?codprice=' + cp);
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 6, 'no_data'); return; }
  const rows = r.data || [];
  el('grp-count').textContent = rows.length;
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 6, 'no_data'); return; }
  tbody.innerHTML = rows.map(g => {
    const inputId = 'grpname-' + g.codprice + '-' + g.codgrp;
    return '<tr>' +
      '<td class="mono">' + g.codprice + '</td>' +
      '<td class="mono">' + g.codgrp + '</td>' +
      '<td><input class="edit-input" id="' + inputId + '" value="' + escapeHtml(g.grpname || '') + '"></td>' +
      '<td>' + escapeHtml(g.type_sc || '') + '</td>' +
      '<td>' + escapeHtml(g.gr1_sc || '') + '</td>' +
      '<td class="td-actions"><button class="btn-sm" onclick="saveGroup(' + g.codprice + ',' + g.codgrp + ',\'' + inputId + '\')">' + t('btn_save') + '</button></td>' +
      '</tr>';
  }).join('');
}

async function saveGroup(codprice, codgrp, inputId) {
  const grpname = val(inputId);
  setStatus(t('loading'));
  const r = await apiPut(API + '/groups', {codprice, codgrp, grpname});
  if (r.success) toast(t('saved'), 'ok');
  setStatus(r.success ? t('saved') : t('err_generic'));
}

async function loadSuppliers() {
  const tbody = el('sup-body');
  tbody.innerHTML = emptyRow(tbody, 3, 'loading');
  const qs = new URLSearchParams();
  if (val('sup-search')) qs.set('search', val('sup-search'));
  qs.set('limit', '200');
  const r = await apiGet(API + '/suppliers?' + qs.toString());
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 3, 'no_data'); return; }
  const rows = r.data || [];
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 3, 'no_data'); return; }
  tbody.innerHTML = rows.map(s => '<tr>' +
    '<td class="mono">' + s.cod + '</td>' +
    '<td>' + escapeHtml(s.name || '') + '</td>' +
    '<td>' + escapeHtml(s.gr1 || '') + '</td>' +
    '</tr>').join('');
}
function debounceLoadSuppliers() {
  clearTimeout(suppliersDebounceTimer);
  suppliersDebounceTimer = setTimeout(loadSuppliers, 350);
}

async function loadFurnizori() {
  const tbody = el('furn-body');
  tbody.innerHTML = emptyRow(tbody, 2, 'loading');
  const r = await apiGet(API + '/suppliers/furnizori');
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 2, 'no_data'); return; }
  const rows = r.data || [];
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 2, 'no_data'); return; }
  tbody.innerHTML = rows.map(f => '<tr>' +
    '<td>' + escapeHtml(f.furnizor) + '</td>' +
    '<td class="num">' + f.cnt + '</td>' +
    '</tr>').join('');
}

async function loadCategories() {
  const tbody = el('cat-body');
  tbody.innerHTML = emptyRow(tbody, 3, 'loading');
  const r = await apiGet(API + '/categories');
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 3, 'no_data'); return; }
  const rows = r.data || [];
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 3, 'no_data'); return; }
  tbody.innerHTML = rows.map(c => '<tr>' +
    '<td class="mono">' + c.id0 + '</td>' +
    '<td>' + escapeHtml(c.label || '') + '</td>' +
    '<td>' + escapeHtml(c.tip || '') + '</td>' +
    '</tr>').join('');
}

/* merge groups modal */
function openMergeModal() {
  el('merge-codprice').value = numVal('grp-codprice', 1);
  el('merge-src').value = '';
  el('merge-dst').value = '';
  el('modal-merge').classList.add('open');
}
function closeModal(id) { el(id).classList.remove('open'); }

async function mergeGroups() {
  const codprice = numVal('merge-codprice', 1);
  const src = parseInt(val('merge-src'), 10);
  const dst = parseInt(val('merge-dst'), 10);
  if (isNaN(src) || isNaN(dst)) { toast(t('validation_required'), 'err'); return; }
  if (!confirmAction('confirm_grp_merge')) return;
  const r = await apiPost(API + '/groups/merge', {codprice, src_codgrp: src, dst_codgrp: dst});
  if (r.success) { toast(t('ok_generic'), 'ok'); closeModal('modal-merge'); loadGroups(); }
}

/* =====================================================================
   TAB 4 — PRICE LIST
   ===================================================================== */
async function loadPrices() {
  const tbody = el('price-body');
  tbody.innerHTML = emptyRow(tbody, 9, 'loading');
  const cp = numVal('price-codprice', 1);
  const qs = new URLSearchParams();
  qs.set('codprice', cp);
  if (val('price-codgrp')) qs.set('codgrp', val('price-codgrp'));
  qs.set('limit', '300');
  const r = await apiGet(API + '/prices?' + qs.toString());
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 9, 'no_data'); return; }
  const rows = r.data || [];
  el('price-count').textContent = rows.length;
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 9, 'no_data'); return; }
  tbody.innerHTML = rows.map((p, i) => {
    const k = 'price-' + i;
    return '<tr>' +
      '<td class="mono">' + p.codprice + '</td>' +
      '<td class="mono">' + p.codgrp + '</td>' +
      '<td class="mono">' + p.sc + '</td>' +
      '<td>' + escapeHtml(p.datastart || '') + '</td>' +
      '<td class="num"><input class="edit-input" id="' + k + '-pretv" value="' + fmtNum(p.pretv) + '" style="width:80px"></td>' +
      '<td class="num"><input class="edit-input" id="' + k + '-pretv1" value="' + fmtNum(p.pretv1) + '" style="width:80px"></td>' +
      '<td class="num"><input class="edit-input" id="' + k + '-pretv2" value="' + fmtNum(p.pretv2) + '" style="width:80px"></td>' +
      '<td class="num">' + fmtNum(p.pretv3) + '</td>' +
      '<td class="td-actions"><button class="btn-sm" onclick="savePrice(' + p.codprice + ',' + p.codgrp + ',' + p.sc + ',\'' + escapeHtml(p.datastart) + '\',\'' + k + '\')">' + t('btn_save') + '</button></td>' +
      '</tr>';
  }).join('');
}

async function savePrice(codprice, codgrp, sc, datastart, k) {
  const body = {
    codprice, codgrp, sc, datastart,
    pretv: parseFloat(val(k + '-pretv')) || 0,
    pretv1: parseFloat(val(k + '-pretv1')) || 0,
    pretv2: parseFloat(val(k + '-pretv2')) || 0,
  };
  const r = await apiPut(API + '/prices', body);
  if (r.success) toast(t('saved'), 'ok');
}

async function loadPriceDates() {
  const tbody = el('price-dates-body');
  tbody.innerHTML = emptyRow(tbody, 4, 'loading');
  const cp = numVal('price-codprice', 1);
  const r = await apiGet(API + '/prices/dates?codprice=' + cp);
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 4, 'no_data'); return; }
  const rows = r.data || [];
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 4, 'no_data'); return; }
  tbody.innerHTML = rows.map(d => '<tr>' +
    '<td class="mono">' + d.codprice + '</td>' +
    '<td class="mono">' + d.codgrp + '</td>' +
    '<td>' + escapeHtml(d.data || '') + '</td>' +
    '<td>' + fmtNum(d.nrdoc) + '</td>' +
    '</tr>').join('');
}

async function rollbackPriceList() {
  if (!confirmAction('confirm_price_rollback')) return;
  const cp = numVal('price-codprice', 1);
  setStatus(t('loading'));
  const r = await apiPost(API + '/prices/rollback', {codprice: cp});
  renderReport('price-report', r);
  setStatus(r.success ? t('ok_generic') : t('err_generic'));
  if (r.success) { loadPrices(); loadPriceDates(); }
}

/* =====================================================================
   TAB 5 — MAPPING / SETTINGS
   ===================================================================== */
async function testConnection() {
  const out = el('conn-result');
  out.textContent = t('loading');
  const r = await apiGet(API + '/connection/test');
  if (r.success) {
    out.innerHTML = '<span style="color:var(--c-green)">✓ ' + escapeHtml(r.version || 'OK') + '</span>';
  } else {
    out.innerHTML = '<span style="color:var(--c-red)">✗ ' + escapeHtml(r.error || t('err_generic')) + '</span>';
  }
}

async function loadProfiles() {
  const tbody = el('profiles-body');
  tbody.innerHTML = emptyRow(tbody, 4, 'loading');
  const r = await apiGet(API + '/mapping/profiles');
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 4, 'no_data'); return; }
  const rows = r.data || [];
  const active = rows.find(p => String(p.is_default) === '1');
  activeProfileName = active ? active.name : null;
  renderActiveProfileIndicator();
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 4, 'no_data'); return; }
  tbody.innerHTML = rows.map(p => '<tr>' +
    '<td>' + escapeHtml(p.name) + '</td>' +
    '<td class="mono">' + fmtNum(p.codprice) + '</td>' +
    '<td>' + (String(p.is_default) === '1' ? '★' : '') + '</td>' +
    '<td class="td-actions">' +
      '<button class="btn-sm" onclick="selectProfile(' + p.id + ')">' + t('btn_view') + '</button> ' +
      '<button class="btn-sm" onclick="activateProfile(' + p.id + ')">' + t('btn_activate') + '</button>' +
    '</td></tr>').join('');
}

async function selectProfile(id) {
  selectedProfileId = id;
  const body = el('profile-detail-body');
  body.innerHTML = '<div class="empty-state"><p>' + t('loading') + '</p></div>';
  const r = await apiGet(API + '/mapping/profiles/' + id);
  if (!r.success || !r.data) { body.innerHTML = '<div class="empty-state"><p>' + t('no_data') + '</p></div>'; return; }
  const d = r.data;
  el('profile-detail-title').textContent = d.name;
  const params = d.params || {};
  const names = (gParamNames && gParamNames.length) ? gParamNames : Object.keys(params);
  const ids = names.filter(n => ID_PARAMS.includes(n));
  const consts = names.filter(n => !ID_PARAMS.includes(n));
  function fieldHtml(n) {
    const v = params[n] === undefined || params[n] === null ? '' : params[n];
    return '<div class="form-group"><label>' + escapeHtml(n) + '</label>' +
      '<input id="pf-' + n + '" value="' + escapeHtml(v) + '"></div>';
  }
  body.innerHTML =
    '<div class="form-group" style="margin-bottom:10px"><label>codprice</label>' +
      '<input id="pf-codprice-head" type="number" value="' + fmtNum(d.codprice) + '"></div>' +
    '<div class="detail-section-title">' + t('group_ids') + '</div>' +
    '<div class="form-grid">' + ids.map(fieldHtml).join('') + '</div>' +
    '<div class="detail-section-title">' + t('group_const') + '</div>' +
    '<div class="form-grid">' + consts.map(fieldHtml).join('') + '</div>' +
    '<div class="form-actions">' +
      '<button class="btn primary" onclick="saveProfile()">' + t('btn_save') + '</button>' +
      '<button class="btn success" onclick="activateProfile(' + id + ')">' + t('btn_activate') + '</button>' +
    '</div>';
}

function validateProfileForm(names) {
  let ok = true;
  names.forEach(n => {
    const inp = el('pf-' + n);
    if (!inp) return;
    inp.classList.remove('invalid');
    const v = inp.value.trim();
    if (NUMERIC_PARAMS.includes(n) && v !== '' && isNaN(Number(v))) { inp.classList.add('invalid'); ok = false; }
    if (n === 'caccess' && v === '') { inp.classList.add('invalid'); ok = false; }
    if (DATE_PARAMS.includes(n) && v !== '' && !/^\d{4}-\d{2}-\d{2}$/.test(v)) { inp.classList.add('invalid'); ok = false; }
  });
  return ok;
}

async function saveProfile() {
  if (!selectedProfileId) return;
  const names = (gParamNames && gParamNames.length) ? gParamNames : [];
  if (!validateProfileForm(names)) { toast(t('validation_numeric'), 'err'); return; }
  const params = {};
  names.forEach(n => { const inp = el('pf-' + n); if (inp) params[n] = inp.value; });
  const codprice = parseInt(val('pf-codprice-head'), 10);
  const r = await apiPut(API + '/mapping/profiles/' + selectedProfileId,
    {codprice: isNaN(codprice) ? undefined : codprice, params});
  if (r.success) { toast(t('saved'), 'ok'); loadProfiles(); }
}

async function activateProfile(id) {
  if (!confirmAction('confirm_profile_activate')) return;
  const r = await apiPost(API + '/mapping/profiles/' + id + '/activate', {});
  if (r.success) { toast(t('ok_generic'), 'ok'); loadProfiles(); }
}

async function createNewProfile() {
  const name = window.prompt(t('prompt_profile_name'));
  if (!name) return;
  const cpStr = window.prompt(t('prompt_codprice'), '1');
  const codprice = parseInt(cpStr, 10) || 1;
  const r = await apiPost(API + '/mapping/profiles', {name, codprice, params: {}});
  if (r.success) { toast(t('ok_generic'), 'ok'); loadProfiles(); }
}
