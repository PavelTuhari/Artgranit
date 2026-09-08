/* CRM — procesul «de la contract la bani» (portul Demo CRM pe web).
 *
 * RO: fisier separat de crm_app.html (regula nr. 2): tabloul de lucru cu 8
 *     etape, kanban cu drag & drop, paginile entitatilor construite din
 *     descrierile serverului (/api/v2/meta), liniile comenzii + contare,
 *     lead -> client, rapoarte + CSV, trei limbi din lang.json (pozitional
 *     pentru enumerari, ca in prototip). Fara ferestre modale: mesajele in
 *     linia de jos (say), stergerea in doi pasi.
 *     Foloseste din crm_app.html: BASE, api(), esc(), num(), say(), SEL,
 *     loadClients()/loadDash()/loadSettings() (beta), setLang() (beta).
 */
(function () {
  'use strict';
  const V2 = 'api/v2/';
  const CAB = window.CRM_CABINET === true;          // pagina clientului din cabinet
  let META = null, LNG = null, LANG2 = 'ro';
  const ENT = {};                                   // key -> descriere
  let CUR = { key: null, id: null, rows: [], filter: {} };   // pagina curenta de entitate
  let DEL2 = null;                                  // stergere in doi pasi: id armat
  let BOARD = 'orders', BOARD_PROJECT = 0, DRAG = null;

  // ── i18n (lang.json al prototipului) ────────────────────────────────────
  const S = (k, ...a) => {
    let s = (LNG && LNG[LANG2] && LNG[LANG2].strings[k]) || (LNG && LNG.ro && LNG.ro.strings[k]) || k;
    a.forEach(v => { s = s.replace(/%[sd]/, v); });
    return s;
  };
  const E = (list, canonical) => {                  // valoarea canonica -> traducerea pozitionala
    if (!LNG || !canonical) return canonical || '';
    const src = (LNG.ru && LNG.ru.enums[list]) || [];
    const dst = (LNG[LANG2] && LNG[LANG2].enums[list]) || src;
    const i = src.indexOf(canonical);
    return i >= 0 && dst[i] ? dst[i] : canonical;
  };
  const EL = list => ((LNG && LNG[LANG2] && LNG[LANG2].enums[list]) || (LNG && LNG.ru.enums[list]) || []);
  const money = v => (v == null || v === '') ? '' : Number(v).toLocaleString('ro-MD', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const today = () => new Date().toISOString().slice(0, 10);
  const daysBetween = d => Math.round((new Date(d) - new Date(today())) / 86400000);

  // RO: cimpurile entitatilor sint canonice (ru); traducerea pozitionala col.* nu exista
  //     in prototip (captiunile Delphi sint in cod), deci le dam aici in ro/en.
  const CAP = {
    ro: { 'Имя': 'Nume', 'Клиент': 'Client', 'Должность': 'Funcție', 'Телефон': 'Telefon', 'Заметки': 'Note', 'Компания': 'Companie',
          'Статус': 'Status', 'Источник': 'Sursă', 'Название': 'Denumire', 'Этап': 'Etapă', 'Сумма, MDL': 'Suma, MDL', 'Закрытие': 'Închidere',
          'Код': 'Cod', 'Наименование': 'Denumire', 'Вид': 'Tip', 'Ед.': 'U.M.', 'Цена, MDL': 'Preț, MDL', 'НДС, %': 'TVA, %', 'Остаток': 'Stoc',
          'Описание': 'Descriere', '№': 'Nr.', 'Дата': 'Data', 'Проект': 'Proiect', 'Итого, MDL': 'Total, MDL', 'Аванс': 'Avans', 'Оплачено': 'Plătit',
          'Срок': 'Termen', 'Отгружен': 'Livrat', 'Примечание': 'Notă', 'Тема': 'Subiect', 'Приоритет': 'Prioritate', 'Исполнитель': 'Executant',
          'Начало': 'Început', 'Часы план': 'Ore plan', 'Часы факт': 'Ore fapt', '№ в проекте': 'Nr. în proiect', 'После задачи №': 'După sarcina nr.',
          'Сделка': 'Ofertă', 'Выполнено': 'Executat', 'Тендер №': 'Licitație nr.', 'Срок тендера': 'Termen licitație', 'Бюджет, MDL': 'Buget, MDL',
          'Аванс, %': 'Avans, %', 'Аванс получен': 'Avans primit', 'Сдача': 'Predare', 'Менеджер': 'Manager', 'Тип': 'Tip', 'Форма': 'Formă',
          'Адрес': 'Adresă', 'Контактное лицо': 'Persoană de contact', 'Руководитель': 'Administrator' },
    en: { 'Имя': 'Name', 'Клиент': 'Client', 'Должность': 'Position', 'Телефон': 'Phone', 'Заметки': 'Notes', 'Компания': 'Company',
          'Статус': 'Status', 'Источник': 'Source', 'Название': 'Title', 'Этап': 'Stage', 'Сумма, MDL': 'Amount, MDL', 'Закрытие': 'Close date',
          'Код': 'Code', 'Наименование': 'Name', 'Вид': 'Kind', 'Ед.': 'Unit', 'Цена, MDL': 'Price, MDL', 'НДС, %': 'VAT, %', 'Остаток': 'Stock',
          'Описание': 'Description', '№': 'No.', 'Дата': 'Date', 'Проект': 'Project', 'Итого, MDL': 'Total, MDL', 'Аванс': 'Advance', 'Оплачено': 'Paid',
          'Срок': 'Due', 'Отгружен': 'Shipped', 'Примечание': 'Note', 'Тема': 'Subject', 'Приоритет': 'Priority', 'Исполнитель': 'Assignee',
          'Начало': 'Start', 'Часы план': 'Hours plan', 'Часы факт': 'Hours fact', '№ в проекте': 'Seq', 'После задачи №': 'After task no.',
          'Сделка': 'Deal', 'Выполнено': 'Done', 'Тендер №': 'Tender no.', 'Срок тендера': 'Tender deadline', 'Бюджет, MDL': 'Budget, MDL',
          'Аванс, %': 'Advance, %', 'Аванс получен': 'Advance received', 'Сдача': 'Delivery', 'Менеджер': 'Manager', 'Тип': 'Type', 'Форма': 'Legal form',
          'Адрес': 'Address', 'Контактное лицо': 'Contact person', 'Руководитель': 'Manager' }
  };
  const cap = c => (CAP[LANG2] && CAP[LANG2][c]) || c;
  const NAV_KEY = { workspace: 'nav.workspace', kanban: 'nav.kanban', clients: 'nav.clients', contacts: 'nav.contacts', leads: 'nav.leads',
                    deals: 'nav.deals', items: 'nav.items', orders: 'nav.orders', projects: 'nav.projects', tasks: 'nav.calendar',
                    reports: 'nav.reports', settings: 'nav.settings' };
  const ENTITY_KEYS = ['contacts', 'leads', 'deals', 'items', 'orders', 'projects', 'tasks'];
  const SECTIONS = ['home', 'workspace', 'kanban', 'clients', ...ENTITY_KEYS, 'reports', 'settings'];

  // ── navigare (inlocuieste show() din beta; sectiunile beta raman) ────────
  window.show = function (sec) {
    if (CAB && sec === 'clients') sec = 'clients2';
    const all = [...SECTIONS, 'clients2'];
    all.forEach(s => {
      const el = document.getElementById('sec-' + s);
      if (el) el.hidden = (s !== sec);
      document.querySelectorAll(`.nav a[data-sec="${s}"]`).forEach(a => a.classList.toggle('active', s === sec));
    });
    location.hash = sec === 'clients2' ? 'clients' : sec;
    if (sec === 'home') loadDash();
    else if (sec === 'clients') loadClients();
    else if (sec === 'settings') loadSettings();
    else if (sec === 'workspace') loadWorkspace();
    else if (sec === 'kanban') loadBoard();
    else if (sec === 'reports') loadReportList();
    else if (sec === 'clients2') openEntity('clients');
    else if (ENTITY_KEYS.includes(sec)) openEntity(sec);
  };

  function applyLang() {
    LANG2 = (typeof LANG !== 'undefined' && LANG) || 'ro';
    document.querySelectorAll('[data-s]').forEach(el => { el.textContent = S(el.dataset.s); });
    if (CUR.key) renderList();
    if (!document.getElementById('sec-kanban').hidden) loadBoard();
    if (!document.getElementById('sec-workspace').hidden) loadWorkspace();
  }
  const oldSetLang = window.setLang;
  window.setLang = function (l) { oldSetLang(l); applyLang(); };

  // ── tabloul de lucru (8 plite) ───────────────────────────────────────────
  async function loadWorkspace() {
    const r = await api(V2 + 'workspace/stages'); if (!r.success) { say('danger', r.error); return; }
    const d = r.data;
    const tile = s => `<div class="tile" onclick="crmOpenStage('${s.stage}')" style="border-top:3px solid ${s.table === 'deals' ? '#2b8fa2' : '#5589ca'}">
        <div class="tt">${esc(E('stage_title', s.title))}</div>
        <div class="tv">${s.count}</div>
        <div class="ts">${money(s.sum)} MDL</div>
        <div class="to ${s.overdue ? 'late' : ''}">${s.overdue ? esc(S('workspace.late', s.overdue, money(s.overdue_sum))) : esc(S('workspace.on_time'))}</div>
        <div class="th">${esc(E('stage_hint', s.hint))}</div></div>`;
    document.getElementById('ws-contract').innerHTML = d.stages.slice(0, 3).map(tile).join('');
    document.getElementById('ws-exec').innerHTML = d.stages.slice(3).map(tile).join('');
    // RO: sirul prototipului are 3 locuri: comenzi, suma neinchisa, cite intirzie
    document.getElementById('ws-summary').textContent = S('workspace.summary', d.orders_total, money(d.orders_overdue_sum), d.orders_overdue);
    document.getElementById('ws-orders').innerHTML = d.last_orders.map(o => `<tr class="r" onclick="crmOpen('orders',${o.id})">
        <td>№${esc(o.number)}</td><td>${esc(o.client_id__disp || S('kanban.no_client'))}</td><td>${esc(E('order_kind', o.kind))}</td>
        <td>${esc(E('order_status', o.status))}</td><td class="num">${money(o.total)}</td><td>${esc(o.due_date || '')}</td></tr>`).join('') || '<tr><td class="muted">—</td></tr>';
    document.getElementById('ws-tasks').innerHTML = d.next_tasks.map(t => `<tr class="r" onclick="crmOpen('tasks',${t.id})">
        <td>${esc(t.due_at || '')}</td><td>${esc(t.subject)}</td><td>${esc(t.assignee || '')}</td><td>${esc(E('task_stage', t.stage))}</td></tr>`).join('') || '<tr><td class="muted">—</td></tr>';
  }
  window.crmOpenStage = function (stage) {
    const key = stage.startsWith('deal_') ? 'deals' : 'orders';
    CUR.filter = { stage };
    show(key);
  };

  // ── pagina generica a entitatii ──────────────────────────────────────────
  async function openEntity(key) {
    const keep = CUR.key === key ? CUR.filter : (CUR.filter.stage || CUR.filter.board ? CUR.filter : {});
    CUR = { key, id: null, rows: [], filter: keep };
    const e = ENT[key];
    const host = document.getElementById('sec-' + (key === 'clients' ? 'clients2' : key));
    host.innerHTML = `<div class="page-head"><h1>${esc(S(NAV_KEY[key] || key))}</h1>
        ${CUR.filter.stage ? `<span class="tag">${esc(E('stage_title', META.stages.find(s => s.stage === CUR.filter.stage).title))} <a href="#" onclick="crmClearFilter();return false">×</a></span>` : ''}
        <button class="btn" onclick="crmReload()">${esc(S('btn.refresh'))}</button>
        <button class="btn btn-primary" onclick="crmNew()">${esc(S('btn.create'))}</button></div>
      <div class="filters"><input id="ef-${key}" placeholder="${esc(S('app.search'))}" onkeydown="if(event.key==='Enter')crmReload()">
        <button class="btn" onclick="crmReload()">${esc(S('btn.refresh'))}</button><span class="muted" id="ecnt-${key}"></span></div>
      <div class="grid"><div class="panel" style="overflow:auto"><table id="et-${key}"><thead><tr>${e.fields.filter(f => f.width).map(f => `<th class="${['money', 'number', 'readonly'].includes(f.kind) ? 'num' : ''}">${esc(cap(f.caption))}</th>`).join('')}</tr></thead><tbody></tbody></table></div>
        <div class="panel ov" id="ed-${key}"><h3>${esc(S('card.client'))}</h3><div class="kv"><div class="muted" style="grid-column:1/-1">${esc(S('msg.select_row'))}</div></div></div></div>`;
    await crmReload();
  }
  window.crmClearFilter = function () { CUR.filter = {}; openEntity(CUR.key); };
  window.crmReload = async function () {
    const key = CUR.key; if (!key) return;
    const q = (document.getElementById('ef-' + key) || {}).value || '';
    const f = CUR.filter;
    let u = `${V2}${key}?q=${encodeURIComponent(q)}`;
    if (f.stage) u += '&stage=' + f.stage;
    if (f.board) u += `&board=${f.board}&col=${f.col}`;
    if (f.project_id) u += '&project_id=' + f.project_id;
    const r = await api(u); if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    CUR.rows = r.data; renderList();
    document.getElementById('ecnt-' + key).textContent = S('msg.refreshed', r.count);
  };
  function cell(f, row) {
    const v = row[f.name];
    if (f.kind === 'enum') return esc(E(f.enum, v));
    if (f.kind.startsWith('lookup')) return esc(row[f.name + '__disp'] || '');
    if (f.kind === 'money' || f.kind === 'readonly') return money(v);
    if (f.kind === 'bool') return v ? '✓' : '';
    if (f.kind === 'number') return v == null ? '' : esc(String(v));
    return esc(v == null ? '' : String(v));
  }
  function renderList() {
    const key = CUR.key, e = ENT[key];
    const tb = document.querySelector(`#et-${key} tbody`); if (!tb) return;
    const cols = e.fields.filter(f => f.width);
    tb.innerHTML = CUR.rows.map(row => `<tr class="r ${CUR.id === row.id ? 'sel' : ''}" id="er-${key}-${row.id}" onclick="crmOpen('${key}',${row.id})">${cols.map(f => `<td class="${['money', 'number', 'readonly'].includes(f.kind) ? 'num' : ''} ${f.kind === 'date' && row[f.name] && row[f.name] < today() && !row.done && (key === 'tasks' || key === 'orders' || key === 'projects') && ['due_at', 'due_date'].includes(f.name) ? 'late' : ''}">${cell(f, row)}</td>`).join('')}</tr>`).join('')
      || `<tr><td colspan="${cols.length}" class="muted">—</td></tr>`;
    if (CUR.id) renderEditor();
  }
  window.crmOpen = async function (key, id) {
    if (CUR.key !== key) { CUR.filter = {}; await openEntity(key); }
    const r = await api(`${V2}${key}/${id}`); if (!r.success) { say('danger', r.error); return; }
    CUR.id = id; CUR.row = r.data; DEL2 = null;
    document.querySelectorAll(`#et-${key} tr.r`).forEach(tr => tr.classList.toggle('sel', tr.id === `er-${key}-${id}`));
    if (!CUR.rows.find(x => x.id === id)) { CUR.rows.unshift(r.data); renderList(); }
    renderEditor();
  };
  window.crmNew = function () { CUR.id = 0; CUR.row = {}; DEL2 = null; renderEditor(); };
  async function lookupOptions(kind, sel) {
    const r = await api(V2 + 'lookup/' + kind.replace('lookup_', ''));
    return `<option value=""></option>` + ((r.success ? r.data : []).map(o => `<option value="${o.id}" ${String(o.id) === String(sel) ? 'selected' : ''}>${esc(o.name)}</option>`).join(''));
  }
  async function renderEditor() {
    const key = CUR.key, e = ENT[key], row = CUR.row || {};
    const host = document.getElementById('ed-' + key); if (!host) return;
    const parts = [];
    for (const f of e.fields) {
      const v = row[f.name] == null ? (CUR.id ? '' : '') : row[f.name];
      let inp;
      if (f.kind === 'readonly') inp = `<div class="num" style="text-align:left"><b>${money(v)}</b></div>`;
      else if (f.kind === 'memo') inp = `<textarea data-f="${f.name}">${esc(v)}</textarea>`;
      else if (f.kind === 'enum') inp = `<select data-f="${f.name}">${f.values.map((c, i) => `<option value="${esc(c)}" ${(v || f.default) === c ? 'selected' : ''}>${esc(EL(f.enum)[i] || c)}</option>`).join('')}</select>`;
      else if (f.kind.startsWith('lookup')) inp = `<select data-f="${f.name}" data-lk="${f.kind}">${await lookupOptions(f.kind, v)}</select>`;
      else if (f.kind === 'bool') inp = `<input type="checkbox" data-f="${f.name}" ${v ? 'checked' : ''}>`;
      else if (f.kind === 'date') inp = `<input type="date" data-f="${f.name}" value="${esc(v || (CUR.id ? '' : (f.default ? resolveDefault(f.default) : '')))}">`;
      else if (f.kind === 'money' || f.kind === 'number') inp = `<input type="number" step="any" data-f="${f.name}" value="${v === '' ? (CUR.id ? '' : f.default) : v}">`;
      else inp = `<input data-f="${f.name}" value="${esc(v)}" ${f.required ? 'required' : ''}>`;
      parts.push(`<label>${esc(cap(f.caption))}${f.required ? ' *' : ''}</label><div>${inp}</div>`);
    }
    let extra = '';
    if (key === 'orders' && CUR.id) extra = renderLines(row);
    if (key === 'projects' && CUR.id && row.summary) {
      const s = row.summary;
      extra = `<div class="sub"><h4>${esc(S('kanban.tasks_of', ''))}</h4><div>${s.done}/${s.total} · ${s.progress}% · ${esc(S('kanban.overdue'))}: ${s.overdue} · ${esc(S('gantt.plan'))} ${s.hours_plan} h / ${esc(S('gantt.run'))} ${s.hours_fact} h</div>
        <div style="margin-top:6px"><button class="btn" onclick="crmProjectTasks(${CUR.id})">${esc(S('kanban.board_project_tasks'))}</button>
        <button class="btn" onclick="crmProjectOrders(${CUR.id})">${esc(S('nav.orders'))}</button></div></div>`;
    }
    const acts = [`<button class="btn btn-primary" onclick="crmSave()">${esc(S('btn.save'))}</button>`];
    if (CUR.id) {
      if (key === 'orders') acts.push(`<button class="btn" onclick="crmPost()">${esc(S('btn.post'))}</button>`);
      if (key === 'leads') acts.push(`<button class="btn" onclick="crmConvert()">${esc(S('btn.to_clients'))}</button>`);
      if (key === 'tasks') acts.push(`<button class="btn" onclick="crmTaskDone()">${esc(S('btn.done'))}</button>`);
      acts.push(`<button class="btn btn-danger" onclick="crmDelete()">${esc(S('btn.delete'))}</button>`);
    }
    host.innerHTML = `<h3>${CUR.id ? esc(row[e.fields[0].name] || '#' + CUR.id) : esc(S('btn.create'))}</h3>
      <div class="kv">${parts.join('')}</div>${extra}<div class="actions">${acts.join('')}</div>`;
    if (key === 'orders' && CUR.id) fillLineItems();
  }
  function resolveDefault(d) {
    if (d.startsWith('today')) { const n = parseInt(d.slice(5) || '0', 10) || 0; const x = new Date(); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10); }
    return d;
  }
  function collect() {
    const out = {};
    document.querySelectorAll(`#ed-${CUR.key} [data-f]`).forEach(el => {
      out[el.dataset.f] = el.type === 'checkbox' ? (el.checked ? 1 : 0) : el.value;
    });
    return out;
  }
  window.crmSave = async function () {
    const key = CUR.key, body = collect();
    const r = CUR.id ? await api(`${V2}${key}/${CUR.id}`, { method: 'PUT', body: JSON.stringify(body) })
                     : await api(`${V2}${key}`, { method: 'POST', body: JSON.stringify(body) });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    const id = CUR.id || r.id;
    say('success', S(CUR.id ? 'msg.saved' : 'msg.added', r.data[ENT[key].fields[0].name] || id));
    await crmReload(); await crmOpen(key, id);
  };
  window.crmDelete = async function () {
    if (!CUR.id) { say('warning', S('msg.select_row')); return; }
    const name = CUR.row[ENT[CUR.key].fields[0].name] || CUR.id;
    if (DEL2 !== CUR.id) { DEL2 = CUR.id; say('warning', S('msg.confirm_delete', name)); return; }
    const r = await api(`${V2}${CUR.key}/${CUR.id}`, { method: 'DELETE' });
    if (!r.success) { say('danger', r.error); return; }
    say('success', S('msg.deleted', name)); CUR.id = null; DEL2 = null;
    await crmReload();
    document.getElementById('ed-' + CUR.key).innerHTML = `<h3>${esc(S('card.client'))}</h3><div class="kv"><div class="muted" style="grid-column:1/-1">${esc(S('msg.select_row'))}</div></div>`;
  };
  window.crmPost = async function () {
    const r = await api(`${V2}orders/${CUR.id}/post`, { method: 'POST' });
    say(r.success ? 'success' : 'warning', r.message || r.error);
    if (r.success) { await crmReload(); await crmOpen('orders', CUR.id); }
  };
  window.crmConvert = async function () {
    const r = await api(`${V2}leads/${CUR.id}/convert`, { method: 'POST' });
    say(r.success ? 'success' : 'warning', r.message || r.error);
    if (r.success) { await crmReload(); await crmOpen('leads', CUR.id); }
  };
  window.crmTaskDone = async function () {
    const r = await api(`${V2}tasks/${CUR.id}/done`, { method: 'POST', body: JSON.stringify({ done: !(CUR.row.done) }) });
    if (!r.success) { say('danger', r.error); return; }
    say('success', S('msg.saved', CUR.row.subject)); await crmReload(); await crmOpen('tasks', CUR.id);
  };
  window.crmProjectTasks = function (pid) { BOARD = 'project_tasks'; BOARD_PROJECT = pid; show('kanban'); };
  window.crmProjectOrders = function (pid) { CUR.filter = { project_id: pid }; show('orders'); };

  // ── liniile comenzii ─────────────────────────────────────────────────────
  function renderLines(row) {
    const lines = row.lines || [];
    return `<div class="sub"><h4>${esc(S('btn.add_line'))}</h4>
      <table>${lines.map(l => `<tr><td>${esc(l.item_name || '')}</td><td class="num">${l.qty} ${esc(l.unit_ || '')}</td><td class="num">${money(l.price)}</td><td class="num"><b>${money(l.sum)}</b></td>
        <td><a href="#" class="btn-danger" onclick="crmDelLine(${l.id});return false" title="${esc(S('btn.del_line'))}">×</a></td></tr>`).join('') || `<tr><td class="muted">—</td></tr>`}</table>
      <div style="display:flex;gap:6px;margin-top:6px;align-items:center;flex-wrap:wrap">
        <select id="ln-item" style="flex:1;min-width:160px"></select>
        <input id="ln-qty" type="number" step="any" value="1" style="width:70px" title="qty">
        <input id="ln-price" type="number" step="any" placeholder="${esc(cap('Цена, MDL'))}" style="width:100px">
        <button class="btn" onclick="crmAddLine()">${esc(S('btn.add_line'))}</button></div></div>`;
  }
  async function fillLineItems() {
    const s = document.getElementById('ln-item'); if (!s) return;
    const r = await api(V2 + 'lookup/item');
    if (r.success) s.innerHTML = r.data.map(o => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
  }
  window.crmAddLine = async function () {
    const body = { item_id: document.getElementById('ln-item').value, qty: document.getElementById('ln-qty').value, price: document.getElementById('ln-price').value };
    const r = await api(`${V2}orders/${CUR.id}/lines`, { method: 'POST', body: JSON.stringify(body) });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    say('success', S('msg.saved', '№' + CUR.row.number)); await crmReload(); await crmOpen('orders', CUR.id);
  };
  window.crmDelLine = async function (lid) {
    const r = await api(`${V2}orders/${CUR.id}/lines/${lid}`, { method: 'DELETE' });
    if (!r.success) { say('danger', r.error); return; }
    await crmReload(); await crmOpen('orders', CUR.id);
  };

  // ── kanban ───────────────────────────────────────────────────────────────
  async function loadBoard() {
    const sel = document.getElementById('kb-kind');
    if (sel) { sel.value = BOARD; sel.querySelectorAll('option').forEach(o => { o.textContent = S('kanban.board_' + o.value); }); }
    const r = await api(`${V2}board/${BOARD}${BOARD === 'project_tasks' && BOARD_PROJECT ? '?project_id=' + BOARD_PROJECT : ''}`);
    if (!r.success) { say('danger', r.error); return; }
    const enumOf = { orders: 'stage_title', deals: 'deal_stage', projects: 'project_status', project_tasks: 'task_stage' }[BOARD];
    const kindEnum = { orders: 'order_kind', deals: 'deal_stage', projects: 'project_kind', project_tasks: 'task_priority', tasks: 'task_kind' }[BOARD];
    const taskCols = S('kanban.task_cols').split(';');
    document.getElementById('kb-title').textContent = S('kanban.board', S('kanban.board_' + BOARD)) + (BOARD_PROJECT && BOARD === 'project_tasks' ? ' · ' + S('kanban.project', '#' + BOARD_PROJECT) : '');
    document.getElementById('kb-hint').textContent = S('kanban.hint');
    document.getElementById('kb').innerHTML = r.data.columns.map(c => {
      const title = BOARD === 'tasks' ? (taskCols[c.col] || c.title) : E(enumOf, c.title);
      const late = c.cards.filter(x => x.due && daysBetween(x.due) < 0 && c.col !== r.data.columns.length - 1).length;
      const sum = c.cards.reduce((a, x) => a + (x.amount || 0), 0);
      return `<div class="kcol" data-col="${c.col}" ondragover="event.preventDefault();this.classList.add('over')" ondragleave="this.classList.remove('over')" ondrop="crmDrop(event,${c.col})">
        <div class="kh" style="border-top:3px solid ${c.color}"><b>${esc(title)}</b><span class="muted">${c.cards.length}${sum ? ' · ' + money(sum) : ''}${late ? ` · <span class="late">${esc(S('kanban.col_late', late))}</span>` : ''}</span></div>
        ${c.cards.map(x => {
          const d = x.due ? daysBetween(x.due) : null;
          const last = c.col === r.data.columns.length - 1;
          const badge = last ? `<span class="kb-badge done">${esc(S('kanban.done_badge'))}</span>` : d == null ? '' : d < 0 ? `<span class="kb-badge late">${esc(S('kanban.days_late', -d))}</span>` : d === 0 ? `<span class="kb-badge today">${esc(S('kanban.today'))}</span>` : `<span class="kb-badge">${esc(S('kanban.days_left', d))}</span>`;
          return `<div class="kcard" draggable="true" ondragstart="crmDrag(${x.id},${c.col})" ondblclick="crmOpenCard(${x.id})" style="border-left:4px solid ${c.color}">
            <div class="kt">${BOARD === 'orders' ? '№' : ''}${esc(x.title)}</div><div class="ks">${esc(x.subtitle || S('kanban.no_client'))}</div>
            <div class="kf"><span class="tag">${esc(E(kindEnum, x.kind) || x.kind)}</span>${x.amount ? `<span>${money(x.amount)} MDL</span>` : ''}${x.paid && x.amount ? `<span class="muted">${esc(S('kanban.paid_pct', Math.round(x.paid * 100 / x.amount)))}</span>` : ''}${x.extra ? `<span class="muted">${esc(x.extra)}</span>` : ''}${badge}</div></div>`;
        }).join('')}</div>`;
    }).join('');
  }
  window.crmBoardKind = function (k) { BOARD = k; if (k !== 'project_tasks') BOARD_PROJECT = 0; loadBoard(); };
  window.crmDrag = function (id, col) { DRAG = { id, col }; };
  window.crmDrop = async function (ev, col) {
    ev.preventDefault(); ev.currentTarget.classList.remove('over');
    if (!DRAG || DRAG.col === col) { DRAG = null; return; }
    const moved = DRAG.id;
    const r = await api(`${V2}board/${BOARD}/move`, { method: 'POST', body: JSON.stringify({ id: DRAG.id, col }) });
    DRAG = null;
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    say('success', S('kanban.moved', '#' + moved, document.querySelectorAll('#kb .kh b')[col].textContent));
    loadBoard();
  };
  window.crmOpenCard = function (id) {
    const key = { orders: 'orders', deals: 'deals', projects: 'projects', tasks: 'tasks', project_tasks: 'tasks' }[BOARD];
    crmOpen(key, id);
  };

  // ── rapoarte ─────────────────────────────────────────────────────────────
  const REPORT_KEY = { process: 'report.process', receivables: 'report.receivables', sales_by_client: 'report.sales', funnel: 'report.funnel', stock: 'report.stock', projects: 'report.projects' };
  function loadReportList() {
    document.getElementById('rp-list').innerHTML = META.reports.map(s => `<a href="#" class="rp" onclick="crmReport('${s}');return false"><b>${esc(S(REPORT_KEY[s]))}</b><br><span class="muted">${esc(S(REPORT_KEY[s] + '.hint'))}</span></a>`).join('');
  }
  window.crmReport = async function (slug) {
    const r = await api(`${V2}reports/${slug}?lang=${LANG2}`); if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    const d = r.data;
    const fmt = v => typeof v === 'number' ? (Number.isInteger(v) ? String(v) : money(v)) : esc(String(v));
    document.getElementById('rp-view').innerHTML = `<div class="page-head"><h1 style="font-size:18px">${esc(d.title)}</h1>
        <a class="btn" href="${BASE}/${V2}reports/${slug}?lang=${LANG2}&format=csv">${esc(S('btn.export_xlsx'))} (CSV)</a></div>
      <p class="muted">${esc(d.subtitle)}</p><div class="panel" style="overflow:auto"><table><thead><tr>${d.columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>
      <tbody>${d.rows.map(row => `<tr>${row.map(v => `<td class="${typeof v === 'number' ? 'num' : ''}">${fmt(v)}</td>`).join('')}</tr>`).join('')}</tbody>
      ${d.totals && d.totals.length ? `<tfoot><tr>${d.totals.map(v => `<th class="${typeof v === 'number' ? 'num' : ''}">${fmt(v)}</th>`).join('')}</tr></tfoot>` : ''}</table></div>`;
  };

  // ── date demo (TEC-03) ───────────────────────────────────────────────────
  window.crmSeed = async function () {
    say('primary', '…');
    const r = await api(V2 + 'seed', { method: 'POST' });
    say(r.success ? 'success' : 'danger', r.success ? r.text : r.error + (r.detail ? ' — ' + r.detail : ''));
    if (r.success) loadWorkspace();
  };

  // ── start ────────────────────────────────────────────────────────────────
  (async function init() {
    const [m, l] = await Promise.all([api(V2 + 'meta'), api(V2 + 'lang')]);
    if (!m.success) { say('danger', m.error); return; }
    META = m.data; LNG = l; Object.assign(ENT, META.entities);
    LANG2 = (typeof LANG !== 'undefined' && LANG) || 'ro';
    // RO: meniul: intrarile prototipului, in ordinea lui
    const nav = document.getElementById('nav-process');
    const ICON = { workspace: '⌂', kanban: '▦', clients: '▤', contacts: '☺', leads: '◎', deals: '$', items: '▣', orders: '☰', projects: '◈', tasks: '▦', reports: '▥' };
    nav.innerHTML = ['workspace', 'kanban', 'clients', 'contacts', 'leads', 'deals', 'items', 'orders', 'projects', 'tasks', 'reports']
      .map(s => `<a href="#${s}" data-sec="${s}"><span class="ic">${ICON[s]}</span><span data-s="${NAV_KEY[s]}">${esc(S(NAV_KEY[s]))}</span></a>`).join('');
    document.querySelectorAll('[data-s]').forEach(el => { el.textContent = S(el.dataset.s); });
    const sec = (location.hash || '#workspace').slice(1);
    if (!new URLSearchParams(location.search).get('cb')) show(SECTIONS.includes(sec) ? sec : 'workspace');
    // RO: linkurile din meniu sint #sectiune — navigarea prin hash (si butonul Inapoi)
    window.addEventListener('hashchange', () => {
      const s = location.hash.slice(1);
      if (SECTIONS.includes(s) && document.getElementById('sec-' + (s === 'clients' && CAB ? 'clients2' : s)).hidden) show(s);
    });
  })();
})();
