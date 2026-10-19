/* CRM — «Angajati»: conturile reale ale ERP-ului, administrate din OfficePlus.
 *
 * RO: fisier separat (regula nr. 2). Lista cu data inregistrarii, dezactivare,
 *     parola standard cu recuperare, e-mail si telefon. Omul e nodul din
 *     arborele UNA (uniConf), nu o copie: parola trece prin a$util.set_passwd,
 *     blocarea prin proprietatea Enabled, verificarea prin a$util.login.
 *     Parola generata se arata O SINGURA DATA — nicaieri nu o pastram.
 *     Fara ferestre modale: mesajele in linia de jos, stergerea/blocarea in
 *     doi pasi, ca in Demo CRM.
 */
(function () {
  'use strict';
  const V2 = 'api/v2/';
  let DATA = null, SEL = null, ARM = null, LAST_PWD = null;

  const L = () => (window.crmLang ? window.crmLang() : 'ro');
  const T = {
    ro: { title: 'Angajați', add: 'Înregistrează angajat', sync: 'Sincronizează cu ERP',
          user: 'Utilizator', name: 'Nume, prenume', email: 'E-mail', phone: 'Telefon',
          group: 'Grupa', reg: 'Înregistrat', state: 'Cont', id: 'ID', act: 'Acțiuni',
          active: 'activ', disabled: 'dezactivat', admin: 'admin',
          all: 'Toți', only_active: 'Doar activi', only_off: 'Doar dezactivați',
          search: 'Căutare: utilizator / nume / e-mail / telefon',
          total: 'Total', with_mail: 'cu e-mail', with_tel: 'cu telefon',
          save: 'Salvează', disable: 'Dezactivează', enable: 'Activează',
          newpwd: 'Parolă nouă', check: 'Verifică parola', card: 'Fișa angajatului',
          pick: 'Alegeți un angajat din listă.', pwd_title: 'Parola standard',
          pwd_hint: 'Scrieți-o acum: nu se mai poate arăta a doua oară.',
          copy: 'Copiază', copied: 'copiat', pwd_for: 'Parola pentru',
          arm_off: 'Apăsați «Dezactivează» încă o dată pentru confirmare',
          created: 'Angajat înregistrat', saved: 'Salvat', synced: 'Sincronizat cu arborele ERP',
          on: 'Cont activat', off: 'Cont dezactivat', pwd_ok: 'Parola pusă în ERP',
          check_ok: 'Parola este corectă (a$util.login)', check_bad: 'ERP: parola nu trece',
          check_ask: 'Introduceți parola de verificat', notes: 'Notițe',
          erp_hint: 'Contul e nodul din arborele UNA: aceleași date le vede uniConf și UniacCLNT.',
          last_pass: 'Parola schimbată', locked: 'Blocat automat', from: 'Sursa' },
    ru: { title: 'Сотрудники', add: 'Зарегистрировать сотрудника', sync: 'Синхронизировать с ERP',
          user: 'Пользователь', name: 'Фамилия, имя', email: 'E-mail', phone: 'Телефон',
          group: 'Группа', reg: 'Зарегистрирован', state: 'Учётная запись', id: 'ID', act: 'Действия',
          active: 'активна', disabled: 'отключена', admin: 'админ',
          all: 'Все', only_active: 'Только активные', only_off: 'Только отключённые',
          search: 'Поиск: пользователь / имя / e-mail / телефон',
          total: 'Всего', with_mail: 'с e-mail', with_tel: 'с телефоном',
          save: 'Сохранить', disable: 'Отключить', enable: 'Включить',
          newpwd: 'Новый пароль', check: 'Проверить пароль', card: 'Карточка сотрудника',
          pick: 'Выберите сотрудника в списке.', pwd_title: 'Стандартный пароль',
          pwd_hint: 'Запишите сейчас: второй раз показать нельзя.',
          copy: 'Копировать', copied: 'скопировано', pwd_for: 'Пароль для',
          arm_off: 'Нажмите «Отключить» ещё раз для подтверждения',
          created: 'Сотрудник зарегистрирован', saved: 'Сохранено', synced: 'Синхронизировано с деревом ERP',
          on: 'Учётная запись включена', off: 'Учётная запись отключена', pwd_ok: 'Пароль записан в ERP',
          check_ok: 'Пароль верный (a$util.login)', check_bad: 'ERP: пароль не проходит',
          check_ask: 'Введите пароль для проверки', notes: 'Заметки',
          erp_hint: 'Учётка — это узел дерева UNA: те же данные видят uniConf и UniacCLNT.',
          last_pass: 'Пароль сменён', locked: 'Заблокирован автоматически', from: 'Источник' },
    en: { title: 'Employees', add: 'Register employee', sync: 'Sync with ERP',
          user: 'User', name: 'Full name', email: 'E-mail', phone: 'Phone',
          group: 'Group', reg: 'Registered', state: 'Account', id: 'ID', act: 'Actions',
          active: 'active', disabled: 'disabled', admin: 'admin',
          all: 'All', only_active: 'Active only', only_off: 'Disabled only',
          search: 'Search: user / name / e-mail / phone',
          total: 'Total', with_mail: 'with e-mail', with_tel: 'with phone',
          save: 'Save', disable: 'Disable', enable: 'Enable',
          newpwd: 'New password', check: 'Check password', card: 'Employee card',
          pick: 'Pick an employee from the list.', pwd_title: 'Standard password',
          pwd_hint: 'Write it down now: it cannot be shown again.',
          copy: 'Copy', copied: 'copied', pwd_for: 'Password for',
          arm_off: 'Press "Disable" again to confirm',
          created: 'Employee registered', saved: 'Saved', synced: 'Synced with the ERP tree',
          on: 'Account enabled', off: 'Account disabled', pwd_ok: 'Password stored in the ERP',
          check_ok: 'Password is correct (a$util.login)', check_bad: 'ERP: password rejected',
          check_ask: 'Enter the password to check', notes: 'Notes',
          erp_hint: 'The account is a node of the UNA tree: uniConf and UniacCLNT see the same data.',
          last_pass: 'Password changed', locked: 'Auto-locked', from: 'Source' }
  };
  const t = k => (T[L()] || T.ro)[k] || k;

  window.crmEmployeesShow = async function () {
    document.getElementById('emp-title').textContent = t('title');
    document.getElementById('emp-add').textContent = t('add');
    document.getElementById('emp-sync').textContent = t('sync');
    const f = document.getElementById('emp-filter');
    f.innerHTML = `<option value="all">${esc(t('all'))}</option><option value="active">${esc(t('only_active'))}</option><option value="disabled">${esc(t('only_off'))}</option>`;
    document.getElementById('emp-q').placeholder = t('search');
    [['emp-h-user','user'],['emp-h-name','name'],['emp-h-mail','email'],['emp-h-tel','phone'],
     ['emp-h-group','group'],['emp-h-reg','reg'],['emp-h-state','state']].forEach(([id,k]) => {
      const el = document.getElementById(id); if (el) el.textContent = t(k);
    });
    await crmEmployeesLoad();
  };

  window.crmEmployeesLoad = async function () {
    const r = await api(`${V2}employees?q=${encodeURIComponent(document.getElementById('emp-q').value || '')}` +
                        `&only=${document.getElementById('emp-filter').value}`);
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    DATA = r;
    const s = r.summary;
    document.getElementById('emp-dash').innerHTML =
      [[t('total'), s.total, '#333'], [t('active'), s.active, '#2a9a4c'], [t('disabled'), s.disabled, '#d9534f'],
       [t('admin'), s.admins, '#5589ca'], [t('with_mail'), s.with_email, '#7f8c8d'], [t('with_tel'), s.with_phone, '#7f8c8d']]
      .map(([lbl, v, c]) => `<div class="panel"><b style="color:${c}">${v}</b><span>${esc(lbl)}</span></div>`).join('');
    document.querySelector('#emp-tab tbody').innerHTML = r.data.map(e => `<tr class="r ${SEL && SEL.obj_id === e.obj_id ? 'sel' : ''}" onclick="crmEmployeeOpen(${e.obj_id})">
        <td><b>${esc(e.username)}</b>${e.is_admin ? ` <span class="tag" style="background:#5589ca;color:#fff">${esc(t('admin'))}</span>` : ''}</td>
        <td>${esc(e.full_name || '')}</td><td>${esc(e.email || '')}</td><td>${esc(e.phone || '')}</td>
        <td class="muted">${esc(e.group_name || '')}</td><td>${esc(e.reg_date || '')}</td>
        <td><span class="tag" style="background:${e.enabled ? '#d1e7dd' : '#f8d7da'};color:${e.enabled ? '#0f5132' : '#842029'}">${esc(e.enabled ? t('active') : t('disabled'))}</span></td></tr>`).join('')
      || `<tr><td colspan="7" class="muted">—</td></tr>`;
    if (SEL) { const f = r.data.find(x => x.obj_id === SEL.obj_id); if (f) { SEL = f; renderCard(); } }
  };

  window.crmEmployeeOpen = async function (id) {
    const r = await api(`${V2}employees/${id}`);
    if (!r.success) { say('danger', r.error); return; }
    SEL = r.data; ARM = null; LAST_PWD = null;
    document.querySelectorAll('#emp-tab tr.r').forEach(tr => tr.classList.remove('sel'));
    renderCard(); crmEmployeesLoad();
  };

  function renderCard() {
    const e = SEL;
    document.getElementById('emp-card').innerHTML = `
      <h3>${esc(e.full_name || e.username)}</h3>
      <div class="kv">
        <label>${esc(t('user'))}</label><div><b>${esc(e.username)}</b> <span class="muted">${esc(t('id'))} ${e.user_id || ''}</span></div>
        <label>${esc(t('name'))}</label><input id="ec-full_name" value="${esc(e.full_name || '')}">
        <label>${esc(t('email'))}</label><input id="ec-email" value="${esc(e.email || '')}" placeholder="nume@officeplus.md">
        <label>${esc(t('phone'))}</label><input id="ec-phone" value="${esc(e.phone || '')}" placeholder="+373 ...">
        <label>${esc(t('notes'))}</label><textarea id="ec-notes">${esc(e.notes || '')}</textarea>
        <label>${esc(t('group'))}</label><div class="muted">${esc(e.group_name || '')}</div>
        <label>${esc(t('reg'))}</label><div>${esc(e.reg_date || '')} <span class="muted">(${esc(t('from'))}: ${esc(e.src)})</span></div>
        <label>${esc(t('last_pass'))}</label><div class="muted">${esc(e.pass_date || '—')}</div>
        ${e.locked_date ? `<label>${esc(t('locked'))}</label><div class="late">${esc(e.locked_date)}</div>` : ''}
        <label>${esc(t('state'))}</label><div><span class="tag" style="background:${e.enabled ? '#d1e7dd' : '#f8d7da'};color:${e.enabled ? '#0f5132' : '#842029'}">${esc(e.enabled ? t('active') : t('disabled'))}</span></div>
      </div>
      ${LAST_PWD ? `<div class="sub"><div class="panel" style="padding:10px;border-color:#f0ad4e;background:#fff8ec">
        <b>${esc(t('pwd_title'))}</b> — ${esc(t('pwd_for'))} <b>${esc(e.username)}</b>
        <div style="display:flex;gap:8px;align-items:center;margin:6px 0">
          <code style="font-size:15px;letter-spacing:1px">${esc(LAST_PWD)}</code>
          <button class="btn" onclick="crmEmpCopy(this)">${esc(t('copy'))}</button></div>
        <span class="muted">${esc(t('pwd_hint'))}</span></div></div>` : ''}
      <div class="actions">
        <button class="btn btn-primary" onclick="crmEmpSave()">${esc(t('save'))}</button>
        <button class="btn" onclick="crmEmpPassword()">${esc(t('newpwd'))}</button>
        <button class="btn" onclick="crmEmpCheck()">${esc(t('check'))}</button>
        <button class="btn ${e.enabled ? 'btn-danger' : ''}" onclick="crmEmpToggle()">${esc(e.enabled ? t('disable') : t('enable'))}</button>
      </div>
      <div class="sub"><span class="muted" style="font-size:11.5px">${esc(t('erp_hint'))}</span>
        <table style="margin-top:6px">${(e.events || []).slice(0, 8).map(x => `<tr><td class="muted">${esc(x.ts)}</td><td>${esc(x.action)}</td><td class="muted">${esc(x.actor || '')}</td></tr>`).join('')}</table></div>`;
  }

  window.crmEmpCopy = function (btn) {
    if (!LAST_PWD) return;
    navigator.clipboard.writeText(LAST_PWD); btn.textContent = '✓ ' + t('copied');
  };

  window.crmEmpSave = async function () {
    const body = {}; ['full_name', 'email', 'phone', 'notes'].forEach(k => body[k] = document.getElementById('ec-' + k).value);
    const r = await api(`${V2}employees/${SEL.obj_id}`, { method: 'PUT', body: JSON.stringify(body) });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    SEL = Object.assign(SEL, r.data); say('success', t('saved')); renderCard(); crmEmployeesLoad();
  };

  window.crmEmpToggle = async function () {
    const off = SEL.enabled;
    if (off && ARM !== SEL.obj_id) { ARM = SEL.obj_id; say('warning', t('arm_off') + ': ' + SEL.username); return; }
    const r = await api(`${V2}employees/${SEL.obj_id}/enabled`, { method: 'POST', body: JSON.stringify({ enabled: !off }) });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    SEL = Object.assign(SEL, r.data); ARM = null;
    say(off ? 'warning' : 'success', off ? t('off') : t('on')); renderCard(); crmEmployeesLoad();
  };

  window.crmEmpPassword = async function () {
    const r = await api(`${V2}employees/${SEL.obj_id}/password`, { method: 'POST', body: JSON.stringify({}) });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    LAST_PWD = r.password; SEL = Object.assign(SEL, r.data);
    say('success', t('pwd_ok')); renderCard();
  };

  window.crmEmpCheck = async function () {
    // RO: fara fereastra modala — cimpul de verificare apare in fisa
    const box = document.getElementById('emp-check');
    if (!box.value) { box.hidden = false; box.focus(); say('primary', t('check_ask')); return; }
    const r = await api(`${V2}employees/${SEL.obj_id}/check`, { method: 'POST', body: JSON.stringify({ password: box.value }) });
    box.value = '';
    if (!r.success) { say('danger', r.error); return; }
    say(r.data.ok ? 'success' : 'warning', r.data.ok ? t('check_ok') : (t('check_bad') + ': ' + (r.data.error || '').split('\n')[0]));
  };

  window.crmEmpSync = async function () {
    const r = await api(V2 + 'employees/sync', { method: 'POST', body: JSON.stringify({}) });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    say('success', `${t('synced')}: ${r.data.total} (+${r.data.added})`); crmEmployeesLoad();
  };

  // ── inregistrarea unui angajat nou: panou in pagina, nu fereastra ──────
  window.crmEmpNew = function () {
    const box = document.getElementById('emp-new');
    box.hidden = !box.hidden;
    if (box.hidden) return;
    box.innerHTML = `<div class="kv">
      <label>${esc(t('user'))} *</label><input id="en-username" placeholder="ipopescu">
      <label>${esc(t('name'))}</label><input id="en-full_name" placeholder="Ion Popescu">
      <label>${esc(t('email'))}</label><input id="en-email" placeholder="ion@officeplus.md">
      <label>${esc(t('phone'))}</label><input id="en-phone" placeholder="+373 ...">
      <label>${esc(t('group'))} *</label><select id="en-group">${(DATA.groups || []).map(g => `<option value="${g.obj_id}">${esc(g.name0)} (${g.cnt})</option>`).join('')}</select>
      <label>${esc(t('admin'))}</label><div><input type="checkbox" id="en-admin" style="width:auto"></div>
      <div></div><div style="display:flex;gap:8px;align-items:center">
        <button class="btn btn-primary" onclick="crmEmpCreate()">${esc(t('add'))}</button>
        <span class="muted" style="font-size:11.5px">${esc(t('pwd_hint'))}</span></div></div>`;
  };

  window.crmEmpCreate = async function () {
    const body = {
      username: document.getElementById('en-username').value.trim(),
      full_name: document.getElementById('en-full_name').value.trim(),
      email: document.getElementById('en-email').value.trim(),
      phone: document.getElementById('en-phone').value.trim(),
      group_id: document.getElementById('en-group').value,
      is_admin: document.getElementById('en-admin').checked
    };
    const r = await api(V2 + 'employees', { method: 'POST', body: JSON.stringify(body) });
    if (!r.success) { say('danger', r.error + (r.detail ? ' — ' + r.detail : '')); return; }
    document.getElementById('emp-new').hidden = true;
    SEL = r.data; LAST_PWD = r.password; ARM = null;
    say('success', `${t('created')}: ${r.data.username}`);
    await crmEmployeesLoad(); renderCard();
  };
})();
