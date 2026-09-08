/* CRM — pagina «Alerte»: tranzactii nefinisate si datorii in Telegram.
 *
 * RO: fisier separat (regula nr. 2). Arata ce e deschis acum, textul care
 *     pleaca in Telegram si setarile chiriasului (bot, praguri, ora).
 *     Fara ferestre modale — mesajele in linia de jos (say), ca in Demo CRM.
 *     Foloseste din crm_app.html / crm_process.js: api(), esc(), say(),
 *     crmMoney(), crmLang().
 */
(function () {
  'use strict';
  const V2 = 'api/v2/';
  let CFG = null, DATA = null;

  const L = () => (window.crmLang ? window.crmLang() : 'ro');
  const money = v => (window.crmMoney ? window.crmMoney(v) : String(v));

  // RO: alertele nu exista in prototipul Delphi -> traducerile stau aici, in trei limbi
  const T = {
    ro: { title: 'Alerte: tranzacții nefinisate și datorii', refresh: 'Actualizează', send: 'Trimite acum',
          kind: 'Tip', doc: 'Document', client: 'Client', amount: 'Sumă, MDL', due: 'Termen', days: 'Zile',
          preview: 'Mesajul care pleacă în Telegram', settings: 'Setări', enabled: 'Alerte pornite',
          chat: 'Telegram chat ID', token: 'Token bot (opțional)', token_inh: 'se folosește botul OfficePlus',
          token_own: 'bot propriu configurat', lang: 'Limba mesajului', kinds: 'Tipuri incluse',
          days_before: 'Avertizare cu N zile înainte de termen', min_debt: 'Prag datorie, MDL',
          quiet: 'Nu repeta aceeași alertă (zile)', hour: 'Ora sumarului zilnic', save: 'Salvează',
          last: 'Ultimul sumar', never: 'niciodată', off: 'oprite', on: 'pornite', nochat: 'chat ID lipsește',
          total: 'De încasat', open: 'Alerte deschise', newc: 'Noi (netrimise)', sent: 'Trimis în Telegram',
          nothing: 'Nimic nou de trimis', saved: 'Setări salvate', empty: 'Nicio alertă deschisă — totul e la zi.',
          hint: 'Chat ID: scrieți botului un mesaj, apoi luați id-ul din @userinfobot. Sumarul zilnic pleacă la ora indicată.' },
    ru: { title: 'Оповещения: незавершённые сделки и долги', refresh: 'Обновить', send: 'Отправить сейчас',
          kind: 'Тип', doc: 'Документ', client: 'Клиент', amount: 'Сумма, MDL', due: 'Срок', days: 'Дней',
          preview: 'Сообщение, которое уйдёт в Telegram', settings: 'Настройки', enabled: 'Оповещения включены',
          chat: 'Telegram chat ID', token: 'Токен бота (необязательно)', token_inh: 'используется бот OfficePlus',
          token_own: 'настроен свой бот', lang: 'Язык сообщения', kinds: 'Какие типы включать',
          days_before: 'Предупреждать за N дней до срока', min_debt: 'Порог долга, MDL',
          quiet: 'Не повторять одно и то же (дней)', hour: 'Час ежедневной сводки', save: 'Сохранить',
          last: 'Последняя сводка', never: 'никогда', off: 'выключены', on: 'включены', nochat: 'не указан chat ID',
          total: 'К получению', open: 'Открытых оповещений', newc: 'Новых (не отправлено)', sent: 'Отправлено в Telegram',
          nothing: 'Нового отправлять нечего', saved: 'Настройки сохранены', empty: 'Открытых оповещений нет — всё в порядке.',
          hint: 'Chat ID: напишите боту сообщение и возьмите id у @userinfobot. Ежедневная сводка уходит в указанный час.' },
    en: { title: 'Alerts: unfinished transactions and debts', refresh: 'Refresh', send: 'Send now',
          kind: 'Kind', doc: 'Document', client: 'Client', amount: 'Amount, MDL', due: 'Due', days: 'Days',
          preview: 'The message that goes to Telegram', settings: 'Settings', enabled: 'Alerts enabled',
          chat: 'Telegram chat ID', token: 'Bot token (optional)', token_inh: 'using the OfficePlus bot',
          token_own: 'own bot configured', lang: 'Message language', kinds: 'Included kinds',
          days_before: 'Warn N days before due', min_debt: 'Debt threshold, MDL',
          quiet: 'Do not repeat the same alert (days)', hour: 'Daily digest hour', save: 'Save',
          last: 'Last digest', never: 'never', off: 'off', on: 'on', nochat: 'chat ID missing',
          total: 'Receivable', open: 'Open alerts', newc: 'New (unsent)', sent: 'Sent to Telegram',
          nothing: 'Nothing new to send', saved: 'Settings saved', empty: 'No open alerts — everything is up to date.',
          hint: 'Chat ID: message the bot, then take the id from @userinfobot. The daily digest goes out at the given hour.' }
  };
  const t = k => (T[L()] || T.ro)[k] || k;
  const KIND_T = {
    ro: { debt: 'Datorie', overdue_work: 'Termen depășit', await_advance: 'Așteaptă avans', ready_to_ship: 'Gata, nelivrată',
          unposted: 'Necontabilizată', project_debt: 'Proiect neacoperit', deal_stale: 'Ofertă fără mișcare', due_soon: 'Termen apropiat' },
    ru: { debt: 'Долг', overdue_work: 'Просрочен срок', await_advance: 'Ожидает аванс', ready_to_ship: 'Готов, не отгружен',
          unposted: 'Не проведён', project_debt: 'Проект без покрытия', deal_stale: 'Сделка без движения', due_soon: 'Близкий срок' },
    en: { debt: 'Debt', overdue_work: 'Overdue', await_advance: 'Awaiting advance', ready_to_ship: 'Ready, not shipped',
          unposted: 'Not posted', project_debt: 'Project uncovered', deal_stale: 'Stale deal', due_soon: 'Due soon' }
  };
  const kindName = k => (KIND_T[L()] || KIND_T.ro)[k] || k;
  const SEV_COLOR = { 2: '#d9534f', 1: '#f0ad4e', 0: '#7f8c8d' };

  window.crmAlertsShow = async function () {
    ['al-title', 'al-refresh', 'al-send', 'al-preview-title'].forEach((id, i) => {
      const el = document.getElementById(id);
      if (el) el.textContent = [t('title'), t('refresh'), t('send'), t('preview')][i];
    });
    [['al-h-kind', 'kind'], ['al-h-doc', 'doc'], ['al-h-client', 'client'], ['al-h-amount', 'amount'],
     ['al-h-due', 'due'], ['al-h-days', 'days']].forEach(([id, k]) => {
      const el = document.getElementById(id); if (el) el.textContent = t(k);
    });
    await crmAlertsPreview();
  };

  window.crmAlertsPreview = async function () {
    const r = await api(V2 + 'alerts');
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    DATA = r.data; CFG = r.data.cfg;
    document.getElementById('al-text').textContent = DATA.text;
    document.getElementById('al-state').textContent =
      (CFG.enabled ? t('on') : t('off')) + ' · ' + (CFG.tg_chat ? 'chat ' + CFG.tg_chat : t('nochat')) +
      ' · ' + t('last') + ': ' + (CFG.last_run || t('never'));
    const bySev = s => DATA.open.filter(a => a.sev === s).length;
    document.getElementById('al-dash').innerHTML =
      [[t('total'), money(DATA.money) + ' MDL', '#d9534f'], [t('open'), DATA.open.length, '#333'],
       [t('newc'), DATA.new, '#5589ca'], ['!!', bySev(2) + ' / ! ' + bySev(1), '#7f8c8d']]
      .map(([lbl, v, c]) => `<div class="panel"><b style="color:${c}">${esc(String(v))}</b><span>${esc(lbl)}</span></div>`).join('');
    const tb = document.querySelector('#al-tab tbody');
    tb.innerHTML = DATA.open.map(a => `<tr class="r" onclick="crmOpen('${a.table}',${a.ref_id})">
        <td><span class="tag" style="background:${SEV_COLOR[a.sev]};color:#fff">${esc(kindName(a.kind))}</span></td>
        <td>${esc(a.title)}</td><td>${esc(a.client)}</td>
        <td class="num">${money(a.amount || a.total)}</td>
        <td class="${a.days > 0 ? 'late' : ''}">${esc(a.due || '—')}</td>
        <td class="num ${a.days > 0 ? 'late' : ''}">${a.days > 0 ? '+' + a.days : (a.days < 0 ? a.days : '')}</td></tr>`).join('')
      || `<tr><td colspan="6" class="muted">${esc(t('empty'))}</td></tr>`;
    renderCfg();
  };

  function renderCfg() {
    const kinds = Object.keys(DATA.kinds || {});
    const on = String(CFG.kinds || '').split(',').map(s => s.trim()).filter(Boolean);
    document.getElementById('al-cfg').innerHTML = `<div class="kv">
      <label>${esc(t('enabled'))}</label><div><input type="checkbox" id="ac-enabled" ${CFG.enabled ? 'checked' : ''}></div>
      <label>${esc(t('chat'))}</label><input id="ac-tg_chat" value="${esc(CFG.tg_chat || '')}" placeholder="-1001234567890">
      <label>${esc(t('token'))}</label><div><input id="ac-tg_token" type="password" placeholder="${esc(CFG.tg_token_own ? t('token_own') : t('token_inh'))}">
        <span class="muted" style="font-size:11.5px">${esc(CFG.tg_token_own ? t('token_own') : t('token_inh'))}</span></div>
      <label>${esc(t('lang'))}</label><select id="ac-lang">${['ro', 'ru', 'en'].map(l => `<option value="${l}" ${CFG.lang === l ? 'selected' : ''}>${l.toUpperCase()}</option>`).join('')}</select>
      <label>${esc(t('kinds'))}</label><div style="display:flex;flex-wrap:wrap;gap:8px">${kinds.map(k => `<label style="font-weight:400"><input type="checkbox" class="ac-kind" value="${k}" ${(!on.length || on.includes(k)) ? 'checked' : ''}> ${esc(kindName(k))}</label>`).join('')}</div>
      <label>${esc(t('days_before'))}</label><input id="ac-days_before_due" type="number" min="0" max="60" value="${CFG.days_before_due}">
      <label>${esc(t('min_debt'))}</label><input id="ac-min_debt" type="number" step="any" min="0" value="${CFG.min_debt}">
      <label>${esc(t('quiet'))}</label><input id="ac-quiet_days" type="number" min="0" max="30" value="${CFG.quiet_days}">
      <label>${esc(t('hour'))}</label><input id="ac-send_hour" type="number" min="0" max="23" value="${CFG.send_hour}">
      <div></div><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <button class="btn btn-primary" onclick="crmAlertsSave()">${esc(t('save'))}</button>
        <span class="muted" style="font-size:11.5px">${esc(t('hint'))}</span></div></div>`;
  }

  window.crmAlertsSave = async function () {
    const kinds = [...document.querySelectorAll('.ac-kind')];
    const all = kinds.every(c => c.checked);
    const body = {
      enabled: document.getElementById('ac-enabled').checked ? 1 : 0,
      tg_chat: document.getElementById('ac-tg_chat').value.trim(),
      lang: document.getElementById('ac-lang').value,
      kinds: all ? '' : kinds.filter(c => c.checked).map(c => c.value).join(','),
      days_before_due: document.getElementById('ac-days_before_due').value,
      min_debt: document.getElementById('ac-min_debt').value,
      quiet_days: document.getElementById('ac-quiet_days').value,
      send_hour: document.getElementById('ac-send_hour').value
    };
    const tok = document.getElementById('ac-tg_token').value.trim();
    if (tok) body.tg_token = tok;
    const r = await api(V2 + 'alerts/settings', { method: 'POST', body: JSON.stringify(body) });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    say('success', t('saved')); await crmAlertsPreview();
  };

  window.crmAlertsSend = async function () {
    say('primary', '…');
    const r = await api(V2 + 'alerts/send', { method: 'POST', body: JSON.stringify({ force: true }) });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    const d = r.data;
    say('success', d.sent ? `${t('sent')}: ${d.alerts} / ${d.open}` : t('nothing'));
    await crmAlertsPreview();
  };
})();
