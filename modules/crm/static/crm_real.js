/* CRM — date reale din ERP si comutatorul «real / demo» (10.09.2026).
   RO: fisier separat (regula nr. 2). crm_process.js il apeleaza in doua
   locuri: bara de sus (comutatorul) si pagina entitatii (panoul ERP).
   In OfficePlus nomenclatorul si clientii sint cei reali din Oracle; setul
   demonstrativ traieste la chiriasul 'demo' si se vede doar cu comutatorul. */
(function () {
  'use strict';
  // RO: BASE, api(), esc(), say() vin din pagina (crm_app.html), ca la
  //     celelalte fisiere ale modulului — adresa portalului nu se scrie de mina.
  const V2 = 'api/v2/';
  const T = {
    ro: { real: 'Date reale', demo: 'Demo', mode: 'Regim', erp: 'Adaugă din ERP',
          search: 'Caută în nomenclatorul ERP: denumire, articol, cod de bare',
          find: 'Caută', add: 'Adaugă', added: 'Adăugat: %s', refresh: 'Reîmprospătează prețurile',
          refreshed: 'Reîmprospătate: %d poziții', sync: 'Sincronizează din ERP',
          synced: 'Contragenți: %d noi, %d actualizați', code: 'Articol', name: 'Denumire',
          price: 'Preț, MDL', stock: 'Stoc', group: 'Grupă', nothing: 'Nimic găsit',
          hint: 'Poziția adusă rămâne legată de ERP (cod %s) — prețul se poate reîmprospăta.',
          switched: 'Regim: %s', demo_on: 'Ați trecut în regimul demonstrativ. Datele reale rămân neatinse.' },
    ru: { real: 'Реальные данные', demo: 'Демо', mode: 'Режим', erp: 'Добавить из ERP',
          search: 'Поиск в номенклатуре ERP: название, артикул, штрих-код',
          find: 'Найти', add: 'Добавить', added: 'Добавлено: %s', refresh: 'Обновить цены',
          refreshed: 'Обновлено: %d позиций', sync: 'Синхронизировать из ERP',
          synced: 'Контрагенты: %d новых, %d обновлено', code: 'Артикул', name: 'Наименование',
          price: 'Цена, MDL', stock: 'Остаток', group: 'Группа', nothing: 'Ничего не найдено',
          hint: 'Позиция остаётся связанной с ERP (код %s) — цену можно обновить.',
          switched: 'Режим: %s', demo_on: 'Включён демонстрационный режим. Реальные данные не тронуты.' },
    en: { real: 'Real data', demo: 'Demo', mode: 'Mode', erp: 'Add from ERP',
          search: 'Search the ERP dictionary: name, article, barcode',
          find: 'Search', add: 'Add', added: 'Added: %s', refresh: 'Refresh prices',
          refreshed: 'Refreshed: %d items', sync: 'Sync from ERP',
          synced: 'Clients: %d new, %d updated', code: 'Article', name: 'Name',
          price: 'Price, MDL', stock: 'Stock', group: 'Group', nothing: 'Nothing found',
          hint: 'The imported item stays linked to the ERP (code %s) — prices can be refreshed.',
          switched: 'Mode: %s', demo_on: 'Demo mode is on. Real data is untouched.' }
  };
  const L = () => T[(window.crmLang ? window.crmLang() : 'ro')] || T.ro;
  const t = (k, ...a) => { let s = L()[k] || k; a.forEach(v => { s = s.replace(/%[sd]/, v); }); return s; };

  // ── comutatorul din bara de sus ─────────────────────────────────────────
  window.crmModeBadge = function (kind) {
    const demo = kind === 'demo';
    return `<span id="crm-mode" class="tag" style="cursor:pointer;background:${demo ? '#fff4d6' : '#e8f5e9'};
      border-color:${demo ? '#e0b64a' : '#9ccc9c'}" onclick="crmModeSet(${demo ? 'false' : 'true'})"
      title="${esc(t('mode'))}">${demo ? '⚗ ' : '● '}${esc(demo ? t('demo') : t('real'))}</span>`;
  };
  window.crmModeSet = async function (demo) {
    const r = await api(V2 + 'mode', { method: 'POST', body: JSON.stringify({ demo: !!demo }) });
    if (!r.success) { say('danger', r.error); return; }
    say('primary', t('switched', r.data.demo ? t('demo') : t('real')));
    location.reload();                        // datele se incarca ale chiriasului nou
  };

  // ── panoul ERP din nomenclator si din clienti ───────────────────────────
  window.crmErpPanelHtml = function (key, real) {
    if (!real) return '';
    if (key === 'items') {
      return `<div class="panel" id="erp-panel" style="margin-bottom:12px;padding:10px 12px">
        <b>${esc(t('erp'))}</b>
        <div class="filters" style="padding:8px 0 0">
          <input id="erp-q" style="width:360px" placeholder="${esc(t('search'))}"
                 onkeydown="if(event.key==='Enter')crmErpSearch()">
          <button class="btn" onclick="crmErpSearch()">${esc(t('find'))}</button>
          <button class="btn" onclick="crmErpRefresh()">${esc(t('refresh'))}</button>
          <span class="muted" id="erp-cnt"></span></div>
        <div id="erp-res" style="max-height:260px;overflow:auto"></div></div>`;
    }
    if (key === 'clients') {
      return `<div class="panel" id="erp-panel" style="margin-bottom:12px;padding:10px 12px">
        <button class="btn" onclick="crmErpSyncClients()">${esc(t('sync'))}</button>
        <span class="muted" id="erp-cnt"></span></div>`;
    }
    return '';
  };

  window.crmErpSearch = async function () {
    const q = (document.getElementById('erp-q') || {}).value || '';
    document.getElementById('erp-cnt').textContent = '…';
    const r = await api(V2 + 'erp/goods?limit=50&q=' + encodeURIComponent(q));
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    document.getElementById('erp-cnt').textContent = r.count;
    document.getElementById('erp-res').innerHTML = r.data.length
      ? `<table><thead><tr><th>${esc(t('code'))}</th><th>${esc(t('name'))}</th><th>${esc(t('group'))}</th>
           <th class="num">${esc(t('price'))}</th><th class="num">${esc(t('stock'))}</th><th></th></tr></thead>
         <tbody>${r.data.map(g => `<tr><td>${esc(g.code)}</td><td>${esc(g.name)}</td><td>${esc(g.group)}</td>
           <td class="num">${Number(g.price || 0).toFixed(2)}</td><td class="num">${Number(g.stock || 0)}</td>
           <td><button class="btn" onclick="crmErpImport(${g.erp_cod})">${esc(t('add'))}</button></td></tr>`).join('')}</tbody></table>`
      : `<div class="muted" style="padding:8px 0">${esc(t('nothing'))}</div>`;
  };

  window.crmErpImport = async function (cod) {
    const r = await api(V2 + 'erp/items', { method: 'POST', body: JSON.stringify({ cod: cod }) });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    say('success', t('added', (r.data[0] || {}).name || cod));
    if (window.crmReload) window.crmReload();
    // RO: dupa aducere pozitia are rind propriu in CRM — deschidem fisa lui
    const id = (r.data[0] || {}).id;
    if (id && window.crmOpen) window.crmOpen('items', id);
  };

  window.crmErpRefresh = async function () {
    say('primary', '…');
    const r = await api(V2 + 'erp/items/refresh', { method: 'POST' });
    if (!r.success) { say('danger', r.error); return; }
    say('success', t('refreshed', r.count));
    if (window.crmReload) window.crmReload();
  };

  window.crmErpSyncClients = async function () {
    say('primary', '…');
    const r = await api(V2 + 'erp/clients/sync', { method: 'POST' });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    say('success', t('synced', r.data.nou, r.data.actualizat));
    // RO: in portal lista clientilor e pagina puntii Contragenti (loadClients),
    //     in cabinet — pagina generica a entitatii (crmReload).
    if (window.loadClients) window.loadClients();
    else if (window.crmReload) window.crmReload();
  };
})();
