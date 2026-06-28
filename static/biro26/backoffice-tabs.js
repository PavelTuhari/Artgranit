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
  tbody.innerHTML = emptyRow(tbody, 11, 'loading');
  const qs = new URLSearchParams();
  if (val('src-search')) qs.set('search', val('src-search'));
  if (val('src-brand')) qs.set('brand', val('src-brand'));
  if (val('src-furnizor')) qs.set('furnizor', val('src-furnizor'));
  if (val('src-status')) qs.set('status', val('src-status'));
  qs.set('limit', '300');
  const r = await apiGet(API + '/goods?' + qs.toString());
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 11, 'no_data'); return; }
  const rows = r.data || [];
  el('src-count').textContent = rows.length;
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 11, 'no_data'); return; }
  tbody.innerHTML = rows.map(g => '<tr>' +
    imgCell(g.photo_url || g.image_link) +
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
  const cardImg = (r.data.photo_url || r.data.image_link)
    ? '<div style="text-align:center;margin-bottom:10px"><img src="' +
      escapeHtml(r.data.photo_url || r.data.image_link) + '" referrerpolicy="no-referrer" ' +
      'style="max-width:100%;max-height:180px;border-radius:8px;cursor:pointer" ' +
      'onclick="openLightbox(this.src)" onerror="this.style.display=\'none\'"></div>'
    : '';
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
  body.innerHTML = cardImg + html;
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
/* master-detail: price lists (VPR0M_PRICES) → groups → item rows (Windows-style) */
async function loadPricelists() {
  const tbody = el('pricelists-body'); if (!tbody) return;
  tbody.innerHTML = emptyRow(tbody, 2, 'loading');
  const r = await apiGet(API + '/prices/lists');
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 2, 'no_data'); return; }
  const rows = r.data || [];
  const cur = numVal('price-codprice', 1);
  tbody.innerHTML = rows.map(p =>
    '<tr onclick="selectPriceList(' + p.codprice + ', this)" style="cursor:pointer"' +
    (p.codprice === cur ? ' class="row-selected"' : '') + '>' +
    '<td class="mono">' + p.codprice + '</td>' +
    '<td>' + escapeHtml(p.pricename || '') + '</td>' +
    '</tr>').join('') || emptyRow(tbody, 2, 'no_data');
}

function selectPriceList(codprice, rowEl) {
  el('price-codprice').value = codprice;
  el('price-codgrp').value = '';
  document.querySelectorAll('#pricelists-body tr').forEach(tr => tr.classList.remove('row-selected'));
  if (rowEl) rowEl.classList.add('row-selected');
  loadPriceGroups();
  loadPrices();
  loadPriceDates();
}

async function loadPriceGroups() {
  const tbody = el('pricegroups-body'); if (!tbody) return;
  tbody.innerHTML = emptyRow(tbody, 2, 'loading');
  const cp = numVal('price-codprice', 1);
  const r = await apiGet(API + '/groups?codprice=' + cp);
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 2, 'no_data'); return; }
  const rows = r.data || [];
  const curg = val('price-codgrp');
  tbody.innerHTML =
    '<tr onclick="selectPriceGroup(\'\', this)" style="cursor:pointer"' + (curg===''?' class="row-selected"':'') + '>' +
    '<td class="mono">—</td><td class="muted">' + t('f_all') + '</td></tr>' +
    rows.map(g =>
      '<tr onclick="selectPriceGroup(' + g.codgrp + ', this)" style="cursor:pointer"' +
      (String(g.codgrp)===curg ? ' class="row-selected"' : '') + '>' +
      '<td class="mono">' + g.codgrp + '</td>' +
      '<td>' + escapeHtml(g.grpname || '') + '</td>' +
      '</tr>').join('');
}

function selectPriceGroup(codgrp, rowEl) {
  el('price-codgrp').value = (codgrp === '' ? '' : codgrp);
  document.querySelectorAll('#pricegroups-body tr').forEach(tr => tr.classList.remove('row-selected'));
  if (rowEl) rowEl.classList.add('row-selected');
  loadPrices();
}

async function loadPrices() {
  const tbody = el('price-body');
  tbody.innerHTML = emptyRow(tbody, 9, 'loading');
  const cp = numVal('price-codprice', 1);
  const qs = new URLSearchParams();
  qs.set('codprice', cp);
  if (val('price-codgrp')) qs.set('codgrp', val('price-codgrp'));
  qs.set('limit', '500');
  const r = await apiGet(API + '/prices?' + qs.toString());
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 9, 'no_data'); return; }
  const rows = r.data || [];
  el('price-count').textContent = rows.length;
  if (el('price-sel-info')) el('price-sel-info').textContent =
    'codprice=' + cp + (val('price-codgrp') ? (' · codgrp=' + val('price-codgrp')) : '');
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 9, 'no_data'); return; }
  tbody.innerHTML = rows.map((p, i) => {
    const k = 'price-' + i;
    return '<tr>' +
      imgCell(p.image) +
      '<td class="mono">' + p.codgrp + '</td>' +
      '<td class="mono" style="cursor:pointer" onclick="showItemCard(' + p.sc + ')">' + p.sc + '</td>' +
      '<td style="cursor:pointer" onclick="showItemCard(' + p.sc + ')">' + escapeHtml(p.denumirea || '') + '</td>' +
      '<td>' + escapeHtml(p.datastart || '') + '</td>' +
      '<td class="num"><input class="edit-input" id="' + k + '-pretv" value="' + fmtNum(p.pretv) + '" style="width:78px"></td>' +
      '<td class="num"><input class="edit-input" id="' + k + '-pretv1" value="' + fmtNum(p.pretv1) + '" style="width:78px"></td>' +
      '<td class="num"><input class="edit-input" id="' + k + '-pretv2" value="' + fmtNum(p.pretv2) + '" style="width:78px"></td>' +
      '<td class="td-actions"><button class="btn-sm" onclick="savePrice(' + p.codprice + ',' + p.codgrp + ',' + p.sc + ',\'' + escapeHtml(p.datastart) + '\',\'' + k + '\')">' + t('btn_save') + '</button></td>' +
      '</tr>';
  }).join('');
}

async function showItemCard(cod) {
  const body = el('item-card-body');
  body.innerHTML = '<div class="empty-state"><p>' + t('loading') + '</p></div>';
  el('modal-item').classList.add('open');
  const r = await apiGet(API + '/univers/' + cod);
  if (!r.success || !r.data) { body.innerHTML = '<div class="empty-state"><p>' + t('no_data') + '</p></div>'; return; }
  const u = r.data.univers || {}, mpt = r.data.mpt;
  const imgUrl = r.data.photo_url || r.data.image_link;
  const cardImg = imgUrl
    ? '<div style="text-align:center;margin-bottom:12px"><img src="' + escapeHtml(imgUrl) +
      '" referrerpolicy="no-referrer" style="max-width:100%;max-height:240px;border-radius:8px;cursor:pointer" ' +
      'onclick="openLightbox(this.src)" onerror="this.style.display=\'none\'"></div>'
    : '';
  function fields(obj) {
    return '<div class="detail-grid">' + Object.keys(obj).map(kk =>
      '<div class="detail-field"><div class="df-label">' + escapeHtml(kk) + '</div><div class="df-val">' +
      escapeHtml(obj[kk] === null || obj[kk] === undefined ? '—' : obj[kk]) + '</div></div>').join('') + '</div>';
  }
  body.innerHTML = cardImg +
    '<div class="detail-section-title">TMS_UNIVERS</div>' + fields(u) +
    (mpt ? '<div class="detail-section-title">TMS_MPT</div>' + fields(mpt)
         : '<div class="detail-section-title">TMS_MPT</div><p class="muted">' + t('no_data') + '</p>');
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

/* =====================================================================
   IMPORT WIZARD
   ===================================================================== */
const WIZ_TARGETS = [
  {param:'col_key',      label:'COD_UNIVERS (key)'},
  {param:'col_articol',  label:'CODVECHI ← articol'},
  {param:'col_denumire', label:'DENUMIREA ← denumire'},
  {param:'col_retail',   label:'PRETV ← retail'},
  {param:'col_angro',    label:'PRETV1 ← angro'},
  {param:'col_ionline',  label:'PRETV2 ← ionline'},
  {param:'col_brand',    label:'group ← brand'},
];
let wizState = {step:1, source:'BIRO26_GOODS', activeId:null, columns:[], sample:{columns:[],data:[]}, mapping:{}};

async function wizardInit() {
  if (el('wiz-source')) {
    const srcList = await apiGet(API + '/sources');
    const saved = (srcList.data||[]).map(s=>'<option value="'+escapeHtml(s.view_name)+'">'+escapeHtml(s.name)+' ('+escapeHtml(s.view_name)+')</option>').join('');
    const keep = el('wiz-source').value;
    el('wiz-source').innerHTML = '<option value="BIRO26_GOODS">BIRO26_GOODS</option>' + saved;
    if (keep) el('wiz-source').value = keep;
  }
  const src = el('wiz-source') ? el('wiz-source').value : 'BIRO26_GOODS';
  wizState.source = src;
  const pr = await apiGet(API + '/mapping/profiles');
  const active = (pr.data||[]).find(p=>String(p.is_default)==='1');
  if (active) {
    wizState.activeId = active.id;
    const d = await apiGet(API+'/mapping/profiles/'+active.id);
    wizState.mapping = (d.data && d.data.params) || {};
  }
  const c = await apiGet(API+'/source/columns?source='+encodeURIComponent(src));
  wizState.columns = c.data || [];
  const s = await apiGet(API+'/source/sample?source='+encodeURIComponent(src)+'&limit=10');
  wizState.sample = {columns:s.columns||[], data:s.data||[]};
  if (el('wiz-src-info')) el('wiz-src-info').textContent =
    (wizState.columns.length) + ' cols · ' + (wizState.sample.data.length) + ' sample rows' +
    (active ? (' · profile: ' + active.name) : '');
  wizState.step = 1; wizRender();
}

function wizGoto(step){ wizState.step = step; wizRender(); if (step===2) wizRenderMapTable(); }

function wizRender(){
  for (let i=1;i<=4;i++){
    const body = el('wiz-body-'+i); if (body) body.style.display = (i===wizState.step)?'':'none';
    const chip = el('wiz-step-'+i);
    if (chip) chip.className = 'badge ' + (i===wizState.step ? 'badge-indict' : 'badge-default');
  }
}

function wizSampleFor(colName){
  const i = wizState.sample.columns.indexOf(colName);
  if (i < 0) return '';
  const vals = wizState.sample.data.slice(0,3).map(r => r[i]).filter(v=>v!=null);
  return escapeHtml(vals.join(', '));
}

function wizRenderMapTable(){
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

function wizOnMap(selEl){
  wizState.mapping[selEl.dataset.param] = selEl.value;
  selEl.closest('tr').lastElementChild.textContent = wizSampleFor(selEl.value);
}

async function wizSaveMapping(){
  if (!wizState.activeId){ toast(t('err_generic'),'err'); return; }
  const params = {};
  WIZ_TARGETS.forEach(tg=>{ if (wizState.mapping[tg.param]) params[tg.param]=wizState.mapping[tg.param]; });
  const r = await apiPut(API+'/mapping/profiles/'+wizState.activeId, {params});
  if (r.success){ toast(t('saved'),'ok'); wizGoto(3); }
}

async function wizValidate(){
  const r = await apiPost(API + '/goods/validate', {});
  renderReport('wiz-validate-report', r);
}

async function wizImport(){
  if (!confirmAction('confirm_univers_import')) return;
  setStatus(t('loading'));
  const r = await apiPost(API + '/univers/import', {});
  renderReport('wiz-import-report', r);
  // chain image-link import so picture links land automatically with each import
  if (r.success) {
    const im = await apiPost(API + '/images/import', {});
    const el2 = el('wiz-import-report');
    if (el2) el2.innerHTML += '<div class="ln-ok">images: ' +
      (im.success ? ((im.rows||0) + ' linked') : escapeHtml(im.error||'err')) + '</div>';
  }
  setStatus(r.success ? t('ok_generic') : t('err_generic'));
}

async function wizImportImages(){
  setStatus(t('loading'));
  const r = await apiPost(API + '/images/import', {});
  renderReport('wiz-import-report',
    r.success ? {success:true, output:['images: ' + (r.rows||0) + ' linked']} : r);
  setStatus(r.success ? t('ok_generic') : t('err_generic'));
}

/* ── wizard: new SELECT source (AI draft / map / save) ──────────────── */
async function wizAiDraft() {
  const sql = val('wiz-sql'); if (!sql) { toast(t('validation_required'),'err'); return; }
  setStatus(t('loading'));
  const r = await apiPost(API+'/sources/ai-draft-md', {name: val('wiz-newname')||'source', sql});
  setStatus('—');
  if (r.success) el('wiz-md').value = r.data.md;
}
async function wizAiMap() {
  const sql = val('wiz-sql'); if (!sql) { toast(t('validation_required'),'err'); return; }
  setStatus(t('loading'));
  const r = await apiPost(API+'/sources/ai-suggest-mapping', {sql, md: val('wiz-md')});
  setStatus('—');
  if (r.success) {
    wizState.columns = r.columns || wizState.columns;
    Object.assign(wizState.mapping, r.mapping || {});
    if (r.source === 'heuristic') toast(t('wiz_ai_unavailable'),'ok');
    wizGoto(2);
  }
}
async function wizSaveSource() {
  const name = val('wiz-newname'), sql = val('wiz-sql');
  if (!name || !sql) { toast(t('validation_required'),'err'); return; }
  const r = await apiPost(API+'/sources', {name, sql, md: val('wiz-md')});
  if (r.success) {
    toast(t('saved'),'ok');
    await wizardInit();
    if (el('wiz-source')) { el('wiz-source').value = r.data.view_name; await wizardInit(); }
  }
}
