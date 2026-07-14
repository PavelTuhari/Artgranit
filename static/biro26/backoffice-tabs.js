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
  cartUpdateBadge();
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
  tbody.innerHTML = emptyRow(tbody, 7, 'loading');
  const qs = new URLSearchParams();
  if (val('dict-search')) qs.set('search', val('dict-search'));
  if (val('dict-gr1')) qs.set('gr1', val('dict-gr1'));
  if (val('dict-arhiv')) qs.set('arhiv', val('dict-arhiv'));
  qs.set('limit', '300');
  const r = await apiGet(API + '/univers?' + qs.toString());
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 7, 'no_data'); return; }
  const rows = r.data || [];
  el('dict-count').textContent = rows.length;
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 7, 'no_data'); return; }
  tbody.innerHTML = rows.map(u =>
    '<tr onclick="loadUniversCard(' + u.cod + ', this)" style="cursor:pointer">' +
    '<td class="mono">' + u.cod + '</td>' +
    '<td class="mono">' + escapeHtml(u.codvechi || '') + '</td>' +
    '<td>' + escapeHtml(dispName(u) || u.denumirea || '') + '</td>' +
    '<td>' + escapeHtml(u.gr1 || '') + '</td>' +
    '<td>' + escapeHtml(u.um || '') + '</td>' +
    '<td>' + escapeHtml(u.isarhiv || '') + '</td>' +
    qtyCell('dict', u.cod, dispName(u) || u.denumirea, u.um, '') +
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
  let html = barcodesHtml(r.data.barcodes) +
             '<div class="detail-section-title">TMS_UNIVERS</div>' +
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
  tbody.innerHTML = emptyRow(tbody, 7, 'loading');
  const cp = numVal('grp-codprice', 1);
  const r = await apiGet(API + '/groups?codprice=' + cp);
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 7, 'no_data'); return; }
  const rows = r.data || [];
  el('grp-count').textContent = rows.length;
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 7, 'no_data'); return; }
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

/* Listă de prețuri grid — infinite scroll (same pattern as Marfă/Stoc):
   the first page loads on open, the rest streams in while scrolling. */
const priceState = { offset: 0, limit: 200, hasMore: true, loading: false, seq: 0 };
let priceScrollBound = false;

function bindPricesScroll() {
  if (priceScrollBound) return;
  const wrap = el('price-table-wrap');
  if (!wrap) return;
  wrap.addEventListener('scroll', () => {
    if (wrap.scrollTop + wrap.clientHeight >= wrap.scrollHeight - 200) {
      loadPrices(false);
    }
  });
  priceScrollBound = true;
}

function priceRowHtml(p, i) {
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
}

async function loadPrices(reset = true) {
  bindPricesScroll();
  if (!reset && (priceState.loading || !priceState.hasMore)) return;
  const my = ++priceState.seq;              // a newer filter click wins
  const tbody = el('price-body');
  if (reset) {
    priceState.offset = 0;
    priceState.hasMore = true;
    tbody.innerHTML = emptyRow(tbody, 9, 'loading');
    if (el('price-end-row')) el('price-end-row').style.display = 'none';
  }
  priceState.loading = true;
  if (el('price-more-row')) el('price-more-row').style.display = reset ? 'none' : '';

  const cp = numVal('price-codprice', 1);
  const qs = new URLSearchParams();
  qs.set('codprice', cp);
  if (val('price-codgrp')) qs.set('codgrp', val('price-codgrp'));
  qs.set('limit', String(priceState.limit));
  qs.set('offset', String(priceState.offset));
  const r = await apiGet(API + '/prices?' + qs.toString());
  if (my !== priceState.seq) return;        // superseded
  priceState.loading = false;
  if (el('price-more-row')) el('price-more-row').style.display = 'none';
  if (!r.success) {
    if (reset) tbody.innerHTML = emptyRow(tbody, 9, 'no_data');
    return;
  }
  const rows = r.data || [];
  priceState.hasMore = rows.length === priceState.limit;
  const base = priceState.offset;           // unique input ids across pages
  priceState.offset += rows.length;
  el('price-count').textContent = priceState.offset;
  if (el('price-sel-info')) el('price-sel-info').textContent =
    'codprice=' + cp + (val('price-codgrp') ? (' · codgrp=' + val('price-codgrp')) : '');
  if (reset) {
    tbody.innerHTML = rows.length
      ? rows.map((p, i) => priceRowHtml(p, base + i)).join('')
      : emptyRow(tbody, 9, 'no_data');
  } else if (rows.length) {
    tbody.insertAdjacentHTML('beforeend', rows.map((p, i) => priceRowHtml(p, base + i)).join(''));
  }
  if (el('price-end-row')) el('price-end-row').style.display =
    (!priceState.hasMore && priceState.offset) ? '' : 'none';
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
    '<div class="btn-row"><button class="btn primary" onclick="editItemCard(' + cod + ')">\u270e ' +
    t('card_edit') + '</button></div>' +
    barcodesHtml(r.data.barcodes) +
    '<div id="card-variants"></div>' +
    '<div id="card-prodinfo"></div>' +
    '<div class="detail-section-title">TMS_UNIVERS</div>' + fields(u) +
    (mpt ? '<div class="detail-section-title">TMS_MPT</div>' + fields(mpt)
         : '<div class="detail-section-title">TMS_MPT</div><p class="muted">' + t('no_data') + '</p>');
  loadCardVariants(cod);
  loadCardProdInfo(cod);
}

/* ── RO: descrierea produsului (YBIRO_PROD_INFO) + comentariile
        clientilor (YBIRO_PROD_COMMENTS) in fisa — descrierea apare in
        fereastra mare de produs din magazin.
   ── EN: product description + client comments in the card — the
        description feeds the shop's large product window. ── */
async function loadCardProdInfo(cod) {
  const box = el('card-prodinfo');
  if (!box) return;
  const r = await apiGet('/api/biro26/shop/product/' + cod);
  const d = (r.success && r.data) || {descriere: '', comments: []};
  box.innerHTML =
    '<div class="detail-section-title">Descriere (magazin) · Описание (магазин)</div>' +
    '<textarea id="pd-desc-' + cod + '" style="width:100%;min-height:90px;padding:8px;' +
    'border:1px solid #e2e8f0;border-radius:8px;font:inherit;font-size:13px">' +
    escapeHtml(d.descriere || '') + '</textarea>' +
    '<div class="btn-row" style="margin:6px 0 10px"><button class="btn primary" ' +
    'onclick="saveProdDesc(' + cod + ')">💾 Salvează descrierea</button></div>' +
    '<div class="detail-section-title">Comentarii clienți (' + (d.comments || []).length + ')</div>' +
    ((d.comments || []).length
      ? d.comments.map(c =>
          '<div style="background:#f8fafc;border:1px solid #eef2f7;border-radius:8px;' +
          'padding:7px 10px;margin-bottom:5px;font-size:12.5px">' +
          '<b>' + escapeHtml(c.autor || '—') + '</b> <span class="muted" style="font-size:11px">' +
          escapeHtml(c.created || '') + '</span>' +
          '<button class="btn-sm" style="float:right" title="Șterge" ' +
          'onclick="delProdComment(' + c.id + ',' + cod + ')">🗑</button>' +
          '<div>' + escapeHtml(c.txt || '') + '</div></div>').join('')
      : '<p class="muted" style="font-size:12px">Fără comentarii · Нет комментариев</p>');
}

async function saveProdDesc(cod) {
  const ta = el('pd-desc-' + cod);
  const r = await apiPut('/api/biro26/product-desc/' + cod, {descriere: ta ? ta.value : ''});
  if (r.success) toast(t('saved'), 'ok');
}

async function delProdComment(id, cod) {
  if (!confirm('Ștergeți comentariul? · Удалить комментарий?')) return;
  const r = await apiDelete('/api/biro26/product-comment/' + id);
  if (r.success) { toast(t('saved'), 'ok'); loadCardProdInfo(cod); }
}

/* \u2500\u2500 variants (BIRO26_VARIANTS): editable family detail in the card \u2500\u2500
   Group = MASTER_COD; the price belongs to the group (master row);
   VARIANT edits also refresh TMS_MPT_BARCODE.COMENT server-side. */
async function loadCardVariants(cod) {
  const box = el('card-variants');
  if (!box) return;
  const r = await apiGet(API + '/univers/' + cod + '/variants');
  if (!r.success || !(r.data || []).length) { box.innerHTML = ''; return; }
  const rows = r.data;
  const base = rows[0].base_name || '';
  box.innerHTML =
    '<div class="detail-section-title">' + t('card_variants') + ' (' + rows.length + ')</div>' +
    (base ? '<p class="muted" style="margin:0 0 6px;font-size:12px">' + escapeHtml(base) +
            ' \u2014 ' + t('var_group_hint') + '</p>' : '') +
    '<div class="data-table-wrap" style="max-height:240px;margin-bottom:10px"><table class="data-table"><thead><tr>' +
    '<th>COD</th><th data-i18n="col_articol">' + t('col_articol') + '</th>' +
    '<th>' + t('var_variant') + '</th><th>' + t('var_furnizor') + '</th>' +
    '<th data-i18n="col_barcode">' + t('col_barcode') + '</th><th></th>' +
    '</tr></thead><tbody>' + rows.map(v => {
      const me = v.cod_univers === cod ? ' style="background:#eff6ff"' : '';
      return '<tr' + me + '>' +
        '<td class="mono" style="cursor:pointer" onclick="showItemCard(' + v.cod_univers + ')">' + v.cod_univers + '</td>' +
        '<td>' + _peInput('vr-' + v.cod_univers + '-articol', v.articol, '90px') + '</td>' +
        '<td>' + _peInput('vr-' + v.cod_univers + '-variant', v.variant, '150px') + '</td>' +
        '<td>' + _peInput('vr-' + v.cod_univers + '-furnizor', v.furnizor, '110px') + '</td>' +
        '<td class="mono" style="font-size:11px">' + escapeHtml(v.barcodes || '') + '</td>' +
        '<td class="td-actions"><button class="btn-sm" title="' + t('btn_save') + '" ' +
        'onclick="saveVariantRow(' + v.cod_univers + ')">\ud83d\udcbe</button></td>' +
        '</tr>';
    }).join('') + '</tbody></table></div>';
}

async function saveVariantRow(vcod) {
  const g = f => val('vr-' + vcod + '-' + f);
  const r = await apiPut(API + '/variants/' + vcod,
    { variant: g('variant'), articol: g('articol'), furnizor: g('furnizor') });
  if (r.success) toast(t('saved'), 'ok');
}

/* barcodes chips block for product cards (TMS_MPT_BARCODE) */
function barcodesHtml(list) {
  if (!list || !list.length) return '';
  return '<div class="detail-section-title">' + t('card_barcodes') + ' (' + list.length + ')</div>' +
    '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px">' +
    list.map(b => '<span class="badge badge-default mono" style="font-size:11.5px">' +
      escapeHtml(b) + '</span>').join('') + '</div>';
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

/* =====================================================================
   TAB 6 — PRODUCT + STOCK GRID (Excel-style, infinite scroll + BI filters)
   ===================================================================== */
function debounceLoadProductsStock() {
  clearTimeout(productsDebounceTimer);
  productsDebounceTimer = setTimeout(() => loadProductsStock(true), 350);
}

function loadStockConst() {
  const el2 = el('prod-const');
  if (!el2) return;
  const saved = localStorage.getItem('biro26_stock_const');
  if (saved !== null) el2.value = saved;
}

function onStockConstChange() {
  const v = el('prod-const');
  if (v) localStorage.setItem('biro26_stock_const', v.value);
  // re-render every already-loaded row with the new constant (no re-fetch)
  const tbody = el('prod-body');
  if (tbody) tbody.innerHTML = prodState.rows.map(productRowHtml).join('') ||
    emptyRow(tbody, 15, 'no_data');
}

/* infinite-scroll state for the product+stock grid */
const prodState = { offset: 0, limit: 100, hasMore: true, loading: false, rows: [] };
let prodScrollBound = false;

async function loadProductBrandsFilter() {
  const sel = el('prod-brand');
  if (!sel || sel.dataset.loaded) return;
  const r = await apiGet(API + '/products/brands');
  if (r.success) {
    const cur = sel.value;
    sel.innerHTML = '<option value="">' + t('f_all') + '</option>' +
      (r.data || []).map(b => '<option value="' + escapeHtml(b.brand) + '">' +
        escapeHtml(b.brand) + ' (' + b.cnt + ')</option>').join('');
    sel.value = cur;
    sel.dataset.loaded = '1';
  }
}

/* ── GRUPA → CATEGORIE tree (left panel, BI-style dimension filter) ── */
let prodTreeData = null;   // [{grupa, categorie, cnt}]

async function loadProductTree() {
  const box = el('prod-tree');
  if (!box || box.dataset.loaded) return;
  const r = await apiGet(API + '/products/tree');
  if (!r.success) { box.innerHTML = '<div class="empty-state"><p>' + t('no_data') + '</p></div>'; return; }
  prodTreeData = r.data || [];
  box.dataset.loaded = '1';
  renderProductTree();
}

function renderProductTree() {
  const box = el('prod-tree');
  if (!box || !prodTreeData) return;
  const selG = val('prod-grupa'), selC = val('prod-categorie');
  // group rows into grupa -> [{categorie,cnt}]
  const groups = {};
  let total = 0;
  prodTreeData.forEach(r => {
    (groups[r.grupa] = groups[r.grupa] || []).push(r);
    total += r.cnt;
  });
  const nodeStyle = 'padding:5px 12px;cursor:pointer;display:flex;justify-content:space-between;gap:8px';
  const selBg = 'background:#eff6ff;color:#1d4ed8;font-weight:600';
  let html = '<div style="' + nodeStyle + (!selG && !selC ? ';' + selBg : '') + '" ' +
    'onclick="selectTreeNode(\'\',\'\')"><span>📦 ' + t('prod_tree_all') + '</span>' +
    '<span class="muted">' + total + '</span></div>';
  Object.keys(groups).sort().forEach(g => {
    const kids = groups[g];
    const gCnt = kids.reduce((a, k) => a + k.cnt, 0);
    const open = selG === g;
    const gEsc = escapeHtml(g).replace(/'/g, "\\'");
    html += '<div style="' + nodeStyle + (open && !selC ? ';' + selBg : '') + '" ' +
      'onclick="selectTreeNode(\'' + gEsc + '\',\'\')">' +
      '<span>' + (open ? '▾' : '▸') + ' ' + escapeHtml(g) + '</span>' +
      '<span class="muted" style="white-space:nowrap">' + gCnt +
      ' <a href="#" title="' + t('tree_rename') + '" style="text-decoration:none" ' +
      'onclick="event.preventDefault();event.stopPropagation();' +
      'treeRenameNode(\'grupa\',\'\',\'' + gEsc + '\',' + gCnt + ')">\u270e</a></span></div>';
    if (open) {
      kids.forEach(k => {
        const cEsc = escapeHtml(k.categorie || '').replace(/'/g, "\\'");
        html += '<div style="' + nodeStyle + ';padding-left:30px' +
          (selC === (k.categorie || '') ? ';' + selBg : '') + '" ' +
          'onclick="selectTreeNode(\'' + gEsc + '\',\'' + cEsc + '\')">' +
          '<span>' + escapeHtml(k.categorie || '—') + '</span>' +
          '<span class="muted" style="white-space:nowrap">' + k.cnt +
          ' <a href="#" title="' + t('tree_rename') + '" style="text-decoration:none" ' +
          'onclick="event.preventDefault();event.stopPropagation();' +
          'treeRenameNode(\'categorie\',\'' + gEsc + '\',\'' + cEsc + '\',' + k.cnt + ')">\u270e</a>' +
          ' <a href="#" title="' + t('tree_move') + '" style="text-decoration:none" ' +
          'onclick="event.preventDefault();event.stopPropagation();' +
          'treeMoveCategorie(\'' + gEsc + '\',\'' + cEsc + '\',' + k.cnt + ')">\u21c4</a></span></div>';
      });
    }
  });
  box.innerHTML = html;
}

function selectTreeNode(grupa, categorie) {
  el('prod-grupa').value = grupa;
  el('prod-categorie').value = categorie;
  renderProductTree();
  loadProductsStock(true);
}

function clearProductFilters() {
  if (el('prod-search')) el('prod-search').value = '';
  if (el('prod-brand')) el('prod-brand').value = '';
  if (el('prod-grupa')) el('prod-grupa').value = '';
  if (el('prod-categorie')) el('prod-categorie').value = '';
  renderProductTree();
  loadProductsStock(true);
}

function bindProductsScroll() {
  if (prodScrollBound) return;
  const wrap = el('prod-table-wrap');
  if (!wrap) return;
  wrap.addEventListener('scroll', () => {
    if (wrap.scrollTop + wrap.clientHeight >= wrap.scrollHeight - 200) {
      loadProductsStock(false);
    }
  });
  prodScrollBound = true;
}

/* reset=true: new search/filter (clears + reloads from offset 0)
   reset=false: infinite-scroll continuation (appends the next page) */
async function loadProductsStock(reset = true) {
  bindProductsScroll();
  if (prodState.loading) return;
  if (!reset && !prodState.hasMore) return;

  if (reset) {
    prodState.offset = 0;
    prodState.hasMore = true;
    prodState.rows = [];
    const tbody = el('prod-body');
    tbody.innerHTML = emptyRow(tbody, 15, 'loading');
    if (el('prod-end-row')) el('prod-end-row').style.display = 'none';
  }

  prodState.loading = true;
  if (el('prod-more-row')) el('prod-more-row').style.display = reset ? 'none' : '';

  const qs = new URLSearchParams();
  if (val('prod-search')) qs.set('search', val('prod-search'));
  if (val('prod-brand')) qs.set('brand', val('prod-brand'));
  if (val('prod-grupa')) qs.set('grupa', val('prod-grupa'));
  if (val('prod-categorie')) qs.set('categorie', val('prod-categorie'));
  qs.set('price_date', prodPriceDate());
  if (el('prod-only-new') && el('prod-only-new').checked) qs.set('only_new', '1');
  // RO: filtrul special "Vizualizare marfa dezactivata" (ISARHIV=2)
  // EN: the special "view deactivated goods" filter (native soft-delete)
  if (el('prod-show-arhiv') && el('prod-show-arhiv').checked) qs.set('archived', '1');
  qs.set('limit', String(prodState.limit));
  qs.set('offset', String(prodState.offset));

  const r = await apiGet(API + '/products?' + qs.toString());
  prodState.loading = false;
  if (el('prod-more-row')) el('prod-more-row').style.display = 'none';

  if (!r.success) {
    if (reset) el('prod-body').innerHTML = emptyRow(el('prod-body'), 15, 'no_data');
    return;
  }
  const batch = r.data || [];
  prodState.hasMore = batch.length === prodState.limit;
  prodState.offset += batch.length;
  prodState.rows = prodState.rows.concat(batch);
  el('prod-count').textContent = prodState.rows.length;

  const tbody = el('prod-body');
  if (reset) {
    tbody.innerHTML = batch.length ? batch.map(productRowHtml).join('') : emptyRow(tbody, 15, 'no_data');
  } else if (batch.length) {
    tbody.insertAdjacentHTML('beforeend', batch.map(productRowHtml).join(''));
  }
  if (el('prod-end-row')) el('prod-end-row').style.display = (!prodState.hasMore && prodState.rows.length) ? '' : 'none';
}

function productRowHtml(p) {
  const constVal = parseFloat(val('prod-const')) || 0;
  const real = p.real_cant;
  const hasReal = real !== null && real !== undefined && Number(real) !== 0;
  const qty = hasReal ? real : constVal;
  // NB: named qtyDisplayCell — a local `qtyCell` would shadow the global
  // cart qtyCell() function called below (broke the grid: "not a function")
  const qtyDisplayCell = hasReal
    ? '<td class="num">' + fmtNum(qty) + '</td>'
    : '<td class="num muted" style="font-style:italic" title="' + escapeHtml(t('prod_const_label')) + '">' + fmtNum(qty) + '</td>';
  const bcCell = p.barcode
    ? '<td class="mono">' + escapeHtml(p.barcode) +
      (p.bc_cnt > 1 ? ' <span class="badge badge-default" title="' + p.bc_cnt + '">+' + (p.bc_cnt - 1) + '</span>' : '') + '</td>'
    : '<td></td>';
  return '<tr id="prow-' + p.cod + '" onclick="selectProdForHistory(' + p.cod + ')">' +
    imgCell(p.image) +
    '<td class="mono">' + escapeHtml(p.codvechi || '') + '</td>' +
    bcCell +
    '<td style="cursor:pointer" onclick="showItemCard(' + p.cod + ')">' +
      (p.matgr1 == 1 ? '<span class="badge" style="background:#dcfce7;color:#166534;margin-right:4px">NOU</span>' : '') +
      escapeHtml(dispName(p) || '') + '</td>' +
    '<td>' + escapeHtml(p.grupa || '') + '</td>' +
    '<td>' + escapeHtml(p.categorie || '') + '</td>' +
    '<td>' + escapeHtml(p.um || '') + '</td>' +
    qtyDisplayCell +
    '<td class="num">' + fmtNum(p.angro_fara_tva) + '</td>' +
    '<td class="num">' + fmtNum(p.angro) + '</td>' +
    '<td class="num">' + fmtNum(p.ionline) + '</td>' +
    '<td class="num">' + fmtNum(p.retail1) + '</td>' +
    '<td>' + escapeHtml(p.brand || '') + '</td>' +
    '<td class="num">20</td>' +
    qtyCell('prod', p.cod, dispName(p), p.um, p.barcode)
      .replace('</td>', ' <button class="btn-sm" title="' + t('edit_row') + '" ' +
               'onclick="editProductRow(' + p.cod + ')">\u270e</button>' +
               (el('prod-show-arhiv') && el('prod-show-arhiv').checked
                 ? ' <button class="btn-sm" title="Reactiveaz\u0103 \u00b7 \u0412\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c" ' +
                   'onclick="event.stopPropagation();archiveProduct(' + p.cod + ',false)">\u267b</button>'
                 : ' <button class="btn-sm" title="Dezactiveaz\u0103 (\u0219tergere ca \u00een aplica\u021bia de baz\u0103) \u00b7 \u0414\u0435\u0430\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u0442\u044c" ' +
                   'onclick="event.stopPropagation();archiveProduct(' + p.cod + ',true)">\ud83d\uddd1</button>') +
               '</td>') +
    '</tr>';
}

/* RO: "stergerea" pozitiei = soft-delete nativ OfficePlus (ISARHIV=2);
   implicit gridul si magazinul arata doar marfa ACTIVA. Reactivarea se
   face din filtrul "Vizualizare marfa dezactivata".
   EN: deleting a position = the native OfficePlus soft-delete (ISARHIV=2);
   by default only ACTIVE goods are listed; restore from the archive view. */
async function archiveProduct(cod, archive) {
  const q = archive
    ? 'Dezactiva\u021bi pozi\u021bia (cartela se marcheaz\u0103 ca \u0219tears\u0103, ca \u00een aplica\u021bia de baz\u0103)? \u00b7 \u0414\u0435\u0430\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043f\u043e\u0437\u0438\u0446\u0438\u044e?'
    : 'Reactiva\u021bi pozi\u021bia? \u00b7 \u0412\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c \u043f\u043e\u0437\u0438\u0446\u0438\u044e?';
  if (!confirm(q)) return;
  const r = await apiPut(API + '/products/' + cod + '/archive', {archived: archive});
  if (r.success) { toast(archive ? 'Dezactivat \u2713' : 'Reactivat \u2713', 'ok'); loadProductsStock(true); }
}

/* =====================================================================
   TAB 7 — STOCK CALCULATION (UN$SOLD.GET_SOLDT)
   ===================================================================== */
async function loadLatestStockCalc() {
  const r = await apiGet(API + '/stock/latest');
  const info = el('stock-last-info');
  if (!info) return;
  if (r.success && r.data) {
    const d = r.data;
    info.textContent = t('stock_last_run') + ': ' + d.run_at + ' — ' +
      d.data_doc + ' / dep="' + (d.dep_filter || '') + '" — ' + d.row_count + ' ' + t('prod_col_qty').toLowerCase();
  } else {
    info.textContent = t('stock_no_calc');
  }
}

async function loadStockItems() {
  const tbody = el('stock-items-body');
  if (!tbody) return;
  tbody.innerHTML = emptyRow(tbody, 4, 'loading');
  const r = await apiGet(API + '/stock/items?limit=300');
  if (!r.success) { tbody.innerHTML = emptyRow(tbody, 4, 'no_data'); return; }
  const rows = r.data || [];
  if (!rows.length) { tbody.innerHTML = emptyRow(tbody, 4, 'no_data'); return; }
  tbody.innerHTML = rows.map(it => '<tr>' +
    '<td class="mono">' + it.sc + '</td>' +
    '<td>' + escapeHtml(it.denumirea || '') + '</td>' +
    '<td class="num">' + fmtNum(it.cant) + '</td>' +
    qtyCell('stock', it.sc, it.denumirea, 'buc.', '') +
    '</tr>').join('');
}

async function runStockCalc() {
  if (!confirmAction('confirm_stock_calc')) return;
  const dataDoc = val('stock-datadoc');
  if (!dataDoc) { toast(t('validation_required'), 'err'); return; }
  setStatus(t('loading'));
  const r = await apiPost(API + '/stock/calculate', {
    data_doc: dataDoc,
    dep_filter: val('stock-dep'),
    cont_filter: val('stock-cont') || undefined,
  });
  renderReport('stock-report', r.success
    ? {success: true, output: ['run_id=' + r.data.id + ', rows=' + r.data.row_count + ', ' + r.data.run_at]}
    : r);
  setStatus(r.success ? t('ok_generic') : t('err_generic'));
  if (r.success) {
    await loadLatestStockCalc();
    await loadStockItems();
  }
}

/* =====================================================================
   CART — universal basket (localStorage), copy as CSV / ADO-rowset XML.
   Items: {cod, name, um, barcode, qty}. Rows in the Marfă/Stoc,
   Nomenclator and Stoc(calcul) grids carry a qty input (class cart-qty,
   data-tab/-cod/-name/-um/-barcode); a value > 0 acts as the "selected"
   checkbox, and collectQtyAdd(tab) adds all selected rows in one shot.
   ===================================================================== */
const CART_KEY = 'biro26_cart';

function cartLoad() {
  try { return JSON.parse(localStorage.getItem(CART_KEY) || '[]'); }
  catch (e) { return []; }
}
function cartSave(items) {
  localStorage.setItem(CART_KEY, JSON.stringify(items));
  cartUpdateBadge(items);
}
function cartUpdateBadge(items) {
  const b = el('cart-count');
  if (b) b.textContent = (items || cartLoad()).length;
}

/* qty input cell shared by the three grids */
function qtyCell(tab, cod, name, um, barcode) {
  return '<td class="num"><input type="number" min="0" step="any" placeholder="0" ' +
    'class="edit-input cart-qty" style="width:64px" ' +
    'data-tab="' + tab + '" data-cod="' + cod + '" ' +
    'data-name="' + escapeHtml(name || '') + '" data-um="' + escapeHtml(um || '') + '" ' +
    'data-barcode="' + escapeHtml(barcode || '') + '" ' +
    'onclick="event.stopPropagation()"></td>';
}

/* one-shot add of every row with qty > 0 on the given tab */
function collectQtyAdd(tab) {
  const inputs = document.querySelectorAll('input.cart-qty[data-tab="' + tab + '"]');
  const sel = [];
  inputs.forEach(inp => {
    const q = parseFloat(inp.value);
    if (q > 0) sel.push({ cod: Number(inp.dataset.cod), name: inp.dataset.name || '',
                          um: inp.dataset.um || 'buc.', barcode: inp.dataset.barcode || '',
                          qty: q });
  });
  if (!sel.length) { toast(t('cart_nothing'), 'err'); return; }
  const items = cartLoad();
  sel.forEach(n => {
    const ex = items.find(i => i.cod === n.cod);
    if (ex) ex.qty += n.qty; else items.push(n);
  });
  cartSave(items);
  inputs.forEach(inp => { if (parseFloat(inp.value) > 0) inp.value = ''; });
  toast(t('cart_added').replace('{n}', sel.length), 'ok');
}

function openCart() { renderCart(); el('modal-cart').classList.add('open'); }

function renderCart() {
  const items = cartLoad();
  el('cart-total').textContent = items.length;
  cartUpdateBadge(items);
  const tbody = el('cart-body');
  if (!items.length) { tbody.innerHTML = emptyRow(tbody, 6, 'cart_empty'); return; }
  tbody.innerHTML = items.map(i => '<tr>' +
    '<td class="mono">' + i.cod + '</td>' +
    '<td>' + escapeHtml(i.name || '') + '</td>' +
    '<td>' + escapeHtml(i.um || '') + '</td>' +
    '<td class="mono">' + escapeHtml(i.barcode || '') + '</td>' +
    '<td class="num"><input type="number" min="0" step="any" class="edit-input" style="width:72px" ' +
      'value="' + (i.qty || 0) + '" onchange="cartSetQty(' + i.cod + ', this.value)"></td>' +
    '<td class="td-actions"><button class="btn-sm" onclick="cartRemove(' + i.cod + ')">×</button></td>' +
    '</tr>').join('');
}

function cartSetQty(cod, v) {
  const items = cartLoad();
  const it = items.find(i => i.cod === cod);
  if (it) { it.qty = parseFloat(v) || 0; cartSave(items); }
}
function cartRemove(cod) { cartSave(cartLoad().filter(i => i.cod !== cod)); renderCart(); }
function cartClear() {
  if (!confirmAction('cart_confirm_clear')) return;
  cartSave([]); renderCart();
}

/* CSV: COD;DENUMIRE;UM;BARCODE;CANT */
function cartCsvText(items) {
  return 'COD;DENUMIRE;UM;BARCODE;CANT\n' + items.map(i =>
    [i.cod, '"' + String(i.name || '').replace(/"/g, '""') + '"',
     i.um || '', i.barcode || '', i.qty || 0].join(';')).join('\n');
}

/* XML: exact ADO-rowset shape of the native UNA.md app (quantity -> PARAM) */
const CART_XML_HEAD =
"<xml xmlns:s='uuid:BDC6E3F0-6DA3-11d1-A2A3-00AA00C14882'\n" +
" xmlns:dt='uuid:C2F41010-65B3-11d1-A29F-00AA00C14882'\n" +
" xmlns:rs='urn:schemas-microsoft-com:rowset'\n" +
" xmlns:z='#RowsetSchema'>\n" +
"<s:Schema id='RowsetSchema'>\n" +
"<s:ElementType name='row' content='eltOnly' rs:updatable='true'>\n" +
"<s:AttributeType name='NRSET' rs:number='1' rs:write='true'>\n" +
"<s:datatype dt:type='float' dt:maxLength='10' rs:precision='15'/>\n" +
"</s:AttributeType>\n" +
"<s:AttributeType name='COD' rs:number='2' rs:write='true'>\n" +
"<s:datatype dt:type='float' dt:maxLength='10' rs:precision='15'/>\n" +
"</s:AttributeType>\n" +
"<s:AttributeType name='NRORD' rs:number='3' rs:write='true'>\n" +
"<s:datatype dt:type='float' dt:maxLength='10' rs:precision='15'/>\n" +
"</s:AttributeType>\n" +
"<s:AttributeType name='MARK' rs:number='4' rs:write='true'>\n" +
"<s:datatype dt:type='string' dt:maxLength='1'/>\n" +
"</s:AttributeType>\n" +
"<s:AttributeType name='PARAM' rs:number='5' rs:write='true'>\n" +
"<s:datatype dt:type='float' dt:maxLength='10' rs:precision='15'/>\n" +
"</s:AttributeType>\n" +
"<s:AttributeType name='UM' rs:number='8' rs:write='true'>\n" +
"<s:datatype dt:type='string' dt:maxLength='15'/>\n" +
"</s:AttributeType>\n" +
"<s:AttributeType name='BARCODE' rs:number='9' rs:write='true'>\n" +
"<s:datatype dt:type='string' dt:maxLength='20'/>\n" +
"</s:AttributeType>\n" +
"<s:extends type='rs:rowbase'/>\n" +
"</s:ElementType>\n" +
"</s:Schema>\n" +
"<rs:data>\n";
const CART_XML_TAIL = "</rs:data>\n</xml>\n";

function cartXmlText(items) {
  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/'/g, '&#39;');
  return CART_XML_HEAD + items.map((i, ix) =>
    "<z:row NRSET='0' COD='" + i.cod + "' NRORD='" + (ix + 1) + "' MARK='1' " +
    "PARAM='" + (i.qty || 0) + "' UM='" + esc(i.um || 'buc.') + "' " +
    "BARCODE='" + esc(i.barcode || '') + "'/>").join('\n') + '\n' + CART_XML_TAIL;
}

async function cartCopy(fmt) {
  const items = cartLoad();
  if (!items.length) { toast(t('cart_empty'), 'err'); return; }
  const txt = fmt === 'xml' ? cartXmlText(items) : cartCsvText(items);
  try {
    await navigator.clipboard.writeText(txt);
  } catch (e) {  // clipboard API blocked (http / permissions) — fallback
    const ta = document.createElement('textarea');
    ta.value = txt; document.body.appendChild(ta);
    ta.select(); document.execCommand('copy'); ta.remove();
  }
  toast(t('cart_copied'), 'ok');
}

/* Admin path of the shop invoice API: same y_ai_BIRO26 package, but the
   operator supplies the client COD (TMS_UNIVERS) instead of a shop session. */
async function cartInvoice() {
  const items = cartLoad().filter(i => (i.qty || 0) > 0);
  if (!items.length) { toast(t('cart_empty'), 'err'); return; }
  const clientCod = prompt(t('cart_invoice_client'));
  if (!clientCod || !/^\d+$/.test(clientCod.trim())) return;
  try {
    const r = await fetch('/api/biro26/shop/invoice', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        client_cod: parseInt(clientCod.trim(), 10),
        items: items.map(i => ({cod: i.cod, qty: i.qty, name: i.name}))
      })
    });
    const b = await r.json();
    if (b.success) {
      toast(t('cart_invoice_ok') + ': NRSET ' + b.data.nrset + ' (COD ' + b.data.cod + ')', 'ok');
      // printable PDFs via the jsReport sidecar (invoice + order forms)
      window.open('/api/biro26/shop/report/invoice/' + b.data.cod, '_blank');
      window.open('/api/biro26/shop/report/order/' + b.data.cod, '_blank');
    } else {
      toast(t('cart_invoice_err') + ': ' + (b.error || ''), 'err');
    }
  } catch (e) {
    toast(t('cart_invoice_err') + ': ' + e, 'err');
  }
}

/* =====================================================================
   PRODUCT EDITING — inline row edit (Marfă/Stoc grid), full attribute
   form in the product card, and product-tree editing (rename/move).
   Writes go through PUT /api/biro26/products/<cod> (atomic) and
   POST /api/biro26/products/tree/rename|move.
   ===================================================================== */

function _peInput(id, value, width) {
  return '<input class="edit-input" id="' + id + '" value="' + escapeHtml(value == null ? '' : value) + '"' +
         (width ? ' style="width:' + width + '"' : '') + '>';
}

function editProductRow(cod) {
  const p = prodState.rows.find(r => r.cod === cod);
  const tr = el('prow-' + cod);
  if (!p || !tr) return;
  tr.innerHTML =
    imgCell(p.image) +
    '<td class="mono">' + escapeHtml(p.codvechi || '') + '</td>' +
    '<td class="mono">' + escapeHtml(p.barcode || '') + '</td>' +
    '<td>' + _peInput('pe-' + cod + '-denumirea', p.denumirea, '98%') + '</td>' +
    '<td>' + _peInput('pe-' + cod + '-grupa', p.grupa, '110px') + '</td>' +
    '<td>' + _peInput('pe-' + cod + '-categorie', p.categorie, '110px') + '</td>' +
    '<td>' + _peInput('pe-' + cod + '-um', p.um, '52px') + '</td>' +
    '<td class="num muted">' + fmtNum(p.real_cant) + '</td>' +
    '<td class="num muted">' + fmtNum(p.angro_fara_tva) + '</td>' +
    '<td class="num">' + _peInput('pe-' + cod + '-angro', p.angro, '70px') + '</td>' +
    '<td class="num">' + _peInput('pe-' + cod + '-ionline', p.ionline, '70px') + '</td>' +
    '<td class="num">' + _peInput('pe-' + cod + '-retail1', p.retail1, '70px') + '</td>' +
    '<td>' + _peInput('pe-' + cod + '-brand', p.brand, '90px') + '</td>' +
    '<td class="num">20</td>' +
    '<td class="td-actions" style="white-space:nowrap">' +
      '<button class="btn-sm" onclick="saveProductRow(' + cod + ')">💾</button> ' +
      '<button class="btn-sm" onclick="cancelEditProductRow(' + cod + ')">✖</button></td>';
}

function cancelEditProductRow(cod) {
  const p = prodState.rows.find(r => r.cod === cod);
  const tr = el('prow-' + cod);
  if (p && tr) tr.outerHTML = productRowHtml(p);
}

async function saveProductRow(cod) {
  const g = f => val('pe-' + cod + '-' + f);
  const body = {
    univers: { denumirea: g('denumirea'), um: g('um') },
    goods: { grupa: g('grupa'), categorie: g('categorie'), brand: g('brand') },
  };
  setStatus(t('loading'));
  const r = await apiPut(API + '/products/' + cod, body);
  if (!r.success) { setStatus('—'); return; } // fetchJSON already toasted the error
  // prices go through the period price list (split at the as-of date),
  // same principle as the Listă de prețuri tab
  const pr = await savePricePeriod(cod, g('retail1'), g('angro'), g('ionline'));
  setStatus('—');
  if (!pr) return;
  const p = prodState.rows.find(x => x.cod === cod);
  if (p) Object.assign(p, { denumirea: body.univers.denumirea, um: body.univers.um,
                            grupa: body.goods.grupa, categorie: body.goods.categorie,
                            brand: body.goods.brand, angro: numOrNull(g('angro')),
                            ionline: numOrNull(g('ionline')), retail1: numOrNull(g('retail1')),
                            angro_fara_tva: g('angro') ? Math.round(parseFloat(g('angro')) / 1.2 * 100) / 100 : p.angro_fara_tva });
  const tr = el('prow-' + cod);
  if (p && tr) tr.outerHTML = productRowHtml(p);
  toast(t('saved'), 'ok');
  invalidateProductTree();                    // grupa/categorie counts may have shifted
}

function numOrNull(v) {
  const n = parseFloat(v);
  return isNaN(n) ? null : n;
}

/* write prices via y_ai_BIRO26.set_price as of the grid's price date:
   an existing period is split at that date; empty inputs keep the current
   column value. Refreshes the bottom history panel when it shows this item. */
async function savePricePeriod(cod, retail1, angro, ionline) {
  if (retail1 === '' && angro === '' && ionline === '') return true; // nothing to write
  const r = await apiPost(API + '/products/price', {
    sc: cod, date: prodPriceDate(),
    retail1: numOrNull(retail1), angro: numOrNull(angro), ionline: numOrNull(ionline),
  });
  if (r.success && phState.sc === cod) renderPriceHistory(r.data || []);
  return r.success;
}

/* ── product card: attribute edit form ─────────────────────────────── */
let itemCardCod = null;

async function editItemCard(cod) {
  const body = el('item-card-body');
  body.innerHTML = '<div class="empty-state"><p>' + t('loading') + '</p></div>';
  const r = await apiGet(API + '/univers/' + cod);
  if (!r.success || !r.data) { body.innerHTML = '<div class="empty-state"><p>' + t('no_data') + '</p></div>'; return; }
  const u = r.data.univers || {}, gd = r.data.goods || {};
  // prices in the form come from the period price list as shown in the grid
  // (as of #prod-price-date); BIRO26_GOODS is only the fallback
  const gridRow = prodState.rows.find(x => x.cod === cod);
  if (gridRow) { gd.angro = gridRow.angro; gd.ionline = gridRow.ionline; gd.retail1 = gridRow.retail1; }
  const fld = (label, id, value) =>
    '<div class="form-group"><label>' + escapeHtml(label) + '</label>' + _peInput(id, value) + '</div>';
  body.innerHTML =
    '<div class="detail-section-title">TMS_UNIVERS</div>' +
    '<div class="form-grid">' +
      fld('DENUMIREA (RO)', 'ic-denumirea', u.denumirea) +
      fld('NAMERUS (RU)', 'ic-namerus', u.namerus) +
      fld('CODVECHI', 'ic-codvechi', u.codvechi) +
      fld('UM', 'ic-um', u.um) +
    '</div>' +
    '<div class="detail-section-title">BIRO26_GOODS</div>' +
    '<div class="form-grid">' +
      fld('BRAND', 'ic-brand', gd.brand) +
      fld('GRUPA', 'ic-grupa', gd.grupa) +
      fld('CATEGORIE', 'ic-categorie', gd.categorie) +
      fld('ANGRO', 'ic-angro', gd.angro) +
      fld('IONLINE', 'ic-ionline', gd.ionline) +
      fld('RETAIL1', 'ic-retail1', gd.retail1) +
    '</div>' +
    '<div class="detail-section-title">' + t('attr_image') + '</div>' +
    '<div class="form-group full">' + _peInput('ic-image', r.data.ie_linkadres || r.data.photo_url, '100%') + '</div>' +
    '<div class="detail-section-title">' + t('card_barcodes') + '</div>' +
    '<div id="ic-bc-list" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">' +
      (r.data.barcodes || []).map(b =>
        '<span class="badge badge-default mono">' + escapeHtml(b) +
        ' <a href="#" style="color:var(--c-red);text-decoration:none" ' +
        'onclick="event.preventDefault(); icRemoveBarcode(' + cod + ', \'' + escapeHtml(b) + '\')">×</a></span>').join('') +
    '</div>' +
    '<div class="form-grid"><div class="form-group">' +
      '<input class="edit-input" id="ic-bc-new" placeholder="' + t('bc_add_ph') + '" maxlength="15"></div>' +
      '<div class="form-group"><button class="btn" onclick="icAddBarcode(' + cod + ')">+ ' + t('card_barcodes') + '</button></div>' +
    '</div>' +
    '<div class="form-actions">' +
      '<button class="btn primary" onclick="saveItemCard(' + cod + ')">' + t('btn_save') + '</button>' +
      '<button class="btn" onclick="showItemCard(' + cod + ')">' + t('btn_cancel') + '</button>' +
    '</div>';
}

async function saveItemCard(cod) {
  const body = {
    univers: { denumirea: val('ic-denumirea'), namerus: val('ic-namerus'),
               codvechi: val('ic-codvechi'), um: val('ic-um') },
    goods: { brand: val('ic-brand'), grupa: val('ic-grupa'), categorie: val('ic-categorie') },
    image: val('ic-image') || null,
  };
  setStatus(t('loading'));
  const r = await apiPut(API + '/products/' + cod, body);
  if (!r.success) { setStatus('—'); return; }
  const pr = await savePricePeriod(cod, val('ic-retail1'), val('ic-angro'), val('ic-ionline'));
  setStatus('—');
  if (!pr) return;
  toast(t('saved'), 'ok');
  showItemCard(cod);
  refreshProductRowFromServer(cod);
  invalidateProductTree();
}

async function icAddBarcode(cod) {
  const b = val('ic-bc-new').trim();
  if (!b) return;
  const r = await apiPut(API + '/products/' + cod, { bc_add: [b] });
  if (r.success) { toast(t('saved'), 'ok'); editItemCard(cod); refreshProductRowFromServer(cod); }
}

async function icRemoveBarcode(cod, b) {
  const r = await apiPut(API + '/products/' + cod, { bc_remove: [b] });
  if (r.success) { toast(t('saved'), 'ok'); editItemCard(cod); refreshProductRowFromServer(cod); }
}

/* refresh a single grid row after card edits (denumire/barcodes/image) */
async function refreshProductRowFromServer(cod) {
  const idx = prodState.rows.findIndex(x => x.cod === cod);
  if (idx < 0) return;
  const r = await apiGet(API + '/univers/' + cod);
  if (!r.success || !r.data) return;
  const u = r.data.univers || {}, gd = r.data.goods || {};
  const bcs = r.data.barcodes || [];
  // NB: prices intentionally NOT taken from BIRO26_GOODS here — the grid
  // shows the period price list as of #prod-price-date (savePricePeriod
  // already updated the local row)
  Object.assign(prodState.rows[idx], {
    denumirea: u.denumirea, namerus: u.namerus, codvechi: u.codvechi, um: u.um,
    brand: gd.brand, grupa: gd.grupa, categorie: gd.categorie,
    image: r.data.ie_linkadres || r.data.photo_url,
    barcode: bcs[0] || null, bc_cnt: bcs.length,
  });
  const tr = el('prow-' + cod);
  if (tr) tr.outerHTML = productRowHtml(prodState.rows[idx]);
}

/* ── price-period history panel (bottom of Marfă/Stoc) ──────────────
   Rules (mirrored in y_ai_BIRO26): a price change SPLITS the period at
   the chosen date; deleting a row MERGES neighbouring periods so the
   date range stays gap-free; the last row cannot be deleted. */
const phState = { sc: null, name: '' };

/* as-of date for the grid prices; defaults to today on first use */
function prodPriceDate() {
  const inp = el('prod-price-date');
  if (inp && !inp.value) inp.value = new Date().toISOString().slice(0, 10);
  return inp ? inp.value : new Date().toISOString().slice(0, 10);
}

function selectProdForHistory(cod) {
  const p = prodState.rows.find(x => x.cod === cod);
  phState.sc = cod;
  phState.name = p ? (dispName(p) || '') : '';
  document.querySelectorAll('#prod-body tr').forEach(tr => tr.classList.remove('row-selected'));
  const tr = el('prow-' + cod);
  if (tr) tr.classList.add('row-selected');
  loadPriceHistory();
}

async function loadPriceHistory() {
  if (!phState.sc) return;
  const box = el('ph-body');
  if (!box) return;
  el('ph-item').textContent = '— ' + phState.sc + ' · ' + phState.name;
  box.innerHTML = emptyRow(box, 6, 'loading');
  const r = await apiGet(API + '/products/price-history?sc=' + phState.sc);
  if (!r.success) { box.innerHTML = emptyRow(box, 6, 'no_data'); return; }
  renderPriceHistory(r.data || []);
}

function renderPriceHistory(rows) {
  const box = el('ph-body');
  if (!box) return;
  if (!rows.length) { box.innerHTML = emptyRow(box, 6, 'no_data'); return; }
  const single = rows.length === 1;   // the last row must not be deletable
  box.innerHTML = rows.map(h => '<tr>' +
    '<td class="mono">' + escapeHtml(h.datastart || '') + '</td>' +
    '<td class="mono">' + escapeHtml(h.dataend || '') + '</td>' +
    '<td class="num">' + fmtNum(h.pretv) + '</td>' +
    '<td class="num">' + fmtNum(h.pretv1) + '</td>' +
    '<td class="num">' + fmtNum(h.pretv2) + '</td>' +
    '<td class="td-actions">' + (single ? '' :
      '<button class="btn-sm" title="' + t('ph_del') + '" ' +
      'onclick="phDelete(\'' + escapeHtml(h.datastart) + '\')">🗑</button>') + '</td>' +
    '</tr>').join('');
}

async function phDelete(datastart) {
  if (!phState.sc) return;
  if (!window.confirm(t('ph_confirm_del'))) return;
  const r = await apiPost(API + '/products/price/delete', { sc: phState.sc, date: datastart });
  if (!r.success) return;                     // error already toasted
  toast(t('saved'), 'ok');
  renderPriceHistory(r.data || []);
  refreshRowPricesFromHistory(phState.sc, r.data || []);
}

/* after a merge the as-of price may change — update the grid row locally
   from the returned history instead of reloading the whole grid */
function refreshRowPricesFromHistory(cod, hist) {
  const p = prodState.rows.find(x => x.cod === cod);
  if (!p) return;
  const d = prodPriceDate();                  // YYYY-MM-DD
  const iso = s => s ? s.split('.').reverse().join('-') : '';   // DD.MM.YYYY -> ISO
  const h = hist.find(x => iso(x.datastart) <= d && d <= iso(x.dataend));
  if (h) {
    p.retail1 = h.pretv; p.angro = h.pretv1; p.ionline = h.pretv2;
    p.angro_fara_tva = h.pretv1 != null ? Math.round(h.pretv1 / 1.2 * 100) / 100 : null;
  }
  const tr = el('prow-' + cod);
  if (tr) { tr.outerHTML = productRowHtml(p); const nt = el('prow-' + cod); if (nt) nt.classList.add('row-selected'); }
}

/* ── product tree editing (rename grupa/categorie, move categorie) ── */
function invalidateProductTree() {
  const box = el('prod-tree');
  if (box) delete box.dataset.loaded;
  prodTreeData = null;
  loadProductTree();
}

async function treeRenameNode(level, grupa, oldName, cnt) {
  const nn = window.prompt(t('tree_rename_prompt'), oldName);
  if (!nn || nn === oldName) return;
  if (!window.confirm(t('tree_confirm').replace('{n}', cnt))) return;
  setStatus(t('loading'));
  const r = await apiPost(API + '/products/tree/rename',
    { level: level, old: oldName, new: nn, grupa: grupa });
  setStatus('—');
  if (!r.success) return;
  toast(t('saved') + ' (' + (r.rows || 0) + ')', 'ok');
  // keep an active filter pointing at the renamed node valid
  if (level === 'grupa' && val('prod-grupa') === oldName) el('prod-grupa').value = nn;
  if (level === 'categorie' && val('prod-categorie') === oldName) el('prod-categorie').value = nn;
  invalidateProductTree();
  loadProductsStock(true);
}

async function treeMoveCategorie(grupa, categorie, cnt) {
  const ng = window.prompt(t('tree_move_prompt'), grupa);
  if (!ng || ng === grupa) return;
  if (!window.confirm(t('tree_confirm').replace('{n}', cnt))) return;
  setStatus(t('loading'));
  const r = await apiPost(API + '/products/tree/move',
    { grupa: grupa, categorie: categorie, new_grupa: ng });
  setStatus('—');
  if (!r.success) return;
  toast(t('saved') + ' (' + (r.rows || 0) + ')', 'ok');
  if (val('prod-grupa') === grupa && val('prod-categorie') === categorie)
    el('prod-grupa').value = ng;
  invalidateProductTree();
  loadProductsStock(true);
}
