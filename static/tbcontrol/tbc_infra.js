/* TBControl — панели «Инфраструктура»: сервисы Zabbix (mTLS), Proxmox VE, SSL-сертификаты.
 * Отдельный файл по правилу №2 CLAUDE.md: templates/tbcontrol.html содержит только разметку
 * панелей и подключает этот скрипт после основного (нужны api(), esc(), fmtTs(), toast(),
 * stBadge(), sevBadge(), openModal(), showPanel(), genDossier()).
 * API: GET /api/tbc/services, POST /api/tbc/services/sync, GET /api/tbc/proxmox,
 *      POST /api/tbc/proxmox/sync, GET/POST /api/tbc/certs, POST /api/tbc/certs/check,
 *      DELETE /api/tbc/certs/<id>.  Логика — models/tbc_services.py, tbc_proxmox.py, tbc_certs.py.
 * Восстановлено 02.09.2026: docs/TBControl/INFRA_RESTORE_20260902.md */
(function () {
    'use strict';
    let svcStatusSel = '', pveTypeSel = '';
    const KIND_RU = {server: 'сервер', db: 'БД', web: 'веб', mail: 'почта', network: 'сеть'};
    const PVE_RU = {node: 'нода', qemu: 'VM', lxc: 'LXC', storage: 'хранилище'};
    const HEALTH_CLS = {OK: 'bg-ok', WARN: 'bg-warn', CRIT: 'bg-crit'};
    const SVC_CLS = {OK: 'bg-ok', WARN: 'bg-warn', PROBLEM: 'bg-crit', DISABLED: 'bg-mut'};
    const CERT_CLS = {OK: 'bg-ok', EXPIRING: 'bg-warn', EXPIRED: 'bg-crit', ERROR: 'bg-crit'};
    const pctCell = (v, warn, crit) => v == null ? '—'
        : `<span style="color:${v >= crit ? 'var(--crit)' : v >= warn ? 'var(--warn)' : 'inherit'}">${Number(v).toFixed(0)}%</span>`;
    const badge = (id, n, crit) => { const b = document.getElementById(id); if (!b) return; b.textContent = n || 0; b.className = 'badge' + (crit ? ' crit' : ''); };
    const chip = (el, attr) => { el.parentElement.querySelectorAll('.tab-chip').forEach(c => c.classList.toggle('active', c === el)); return el.dataset[attr]; };
    const syncToast = (r, what) => {
        if (!r.success) return toast(r.error || 'Ошибка', true);
        const ok = (r.data || []).filter(x => x.success), bad = (r.data || []).filter(x => !x.success);
        const d = ok[0] || {};
        toast(`${what}: ${ok.map(x => x.source_code).join(', ') || '—'}${d.hosts != null ? ' · хостов ' + d.hosts : ''}${d.objects != null ? ' · объектов ' + d.objects : ''}` +
              ` · события +${d.events_created || 0}/−${d.events_resolved || 0}${bad.length ? ' · ошибок: ' + bad.map(x => x.error).join('; ') : ''}`, bad.length > 0);
    };

    // ===== Сервисы Zabbix =====
    window.loadServices = async function () {
        const q = [];
        const k = document.getElementById('svcKindFilter').value; if (k) q.push('kind=' + k);
        if (svcStatusSel) q.push('status=' + svcStatusSel);
        const r = await api('/services' + (q.length ? '?' + q.join('&') : ''));
        if (!r.success) return toast(r.error, true);
        const st = r.stats || {}, src = (r.sources || [])[0] || {};
        document.getElementById('svcStatGrid').innerHTML = `
            <div class="stat-card"><div class="stat-label">Хостов</div><div class="stat-value blue">${st.svc_total || 0}</div>
                <div class="stat-sub">групп: ${st.groups_total || 0} · выключено: ${st.svc_disabled || 0}</div></div>
            <div class="stat-card red"><div class="stat-label">Проблемы</div><div class="stat-value ${st.svc_problem > 0 ? 'red' : 'green'}">${st.svc_problem || 0}</div>
                <div class="stat-sub">триггеров: ${st.problems_total || 0} · warn: ${st.svc_warn || 0}</div></div>
            <div class="stat-card yellow"><div class="stat-label">Агенты недоступны</div><div class="stat-value ${st.agents_down > 0 ? 'yellow' : 'green'}">${st.agents_down || 0}</div></div>
            <div class="stat-card"><div class="stat-label">Источник</div><div class="stat-value" style="font-size:15px">${esc(src.code || '—')} ${src.last_status ? stBadge(src.last_status === 'OK' ? 'OK' : 'FAIL') : ''}</div>
                <div class="stat-sub" title="${esc(src.last_error || '')}">опрос: ${fmtTs(src.last_sync_at)}${src.last_error ? ' · ' + esc(src.last_error).substring(0, 60) : ''}</div></div>`;
        badge('badgeSvc', st.svc_problem, st.svc_problem > 0);
        document.getElementById('svcTbody').innerHTML = r.data.map(s => `<tr>
            <td><b>${esc(s.host)}</b>${s.name && s.name !== s.host ? `<div class="muted" style="font-size:11px">${esc(s.name)}</div>` : ''}</td>
            <td class="muted">${esc(KIND_RU[s.service_kind] || s.service_kind || '—')}</td>
            <td class="mono muted">${esc(s.ip_address || '—')}</td>
            <td class="muted" style="max-width:180px">${esc(s.group_name || '—')}</td>
            <td>${s.available === 'available' ? '<span class="badge-st bg-ok">ok</span>' : s.available === 'unavailable' ? '<span class="badge-st bg-crit">down</span>' : '<span class="badge-st bg-mut">?</span>'}</td>
            <td><span class="badge-st ${SVC_CLS[s.status] || 'bg-mut'}">${esc(s.status)}</span> ${s.worst_severity ? sevBadge(s.worst_severity) : ''}</td>
            <td class="muted" style="max-width:360px" title="${esc(s.problem_text || '')}">${s.problems_cnt ? s.problems_cnt + ': ' : ''}${esc((s.problem_text || '').substring(0, 120))}</td>
            <td class="muted">${fmtTs(s.checked_at)}</td>
            <td style="white-space:nowrap"><button class="btn btn-secondary btn-sm" title="AI-досье" onclick="genDossier('service', ${s.id})">🤖</button></td></tr>`).join('')
            || '<tr><td colspan="9" class="empty-note">Нет данных — нажмите «Синхронизировать»</td></tr>';
    };
    window.setSvcStatus = function (el) { svcStatusSel = chip(el, 'ss'); loadServices(); };
    window.syncServices = async function () {
        toast('Опрос Zabbix через mTLS-шлюз…');
        syncToast(await api('/services/sync', 'POST', {}), 'Zabbix');
        loadServices(); if (window.loadSources) loadSources();
    };

    // ===== Proxmox =====
    window.loadProxmox = async function () {
        const q = [];
        if (pveTypeSel) q.push('obj_type=' + pveTypeSel);
        const h = document.getElementById('pveHealthFilter').value; if (h) q.push('health=' + h);
        const r = await api('/proxmox' + (q.length ? '?' + q.join('&') : ''));
        if (!r.success) return toast(r.error, true);
        const st = r.stats || {}, src = (r.sources || [])[0] || {};
        document.getElementById('pveStatGrid').innerHTML = `
            <div class="stat-card"><div class="stat-label">Ноды</div><div class="stat-value blue">${st.nodes_total || 0}</div>
                <div class="stat-sub">хранилищ: ${st.storage_total || 0}</div></div>
            <div class="stat-card green"><div class="stat-label">VM running</div><div class="stat-value green">${st.vm_running || 0}/${st.vm_total || 0}</div></div>
            <div class="stat-card green"><div class="stat-label">LXC running</div><div class="stat-value green">${st.ct_running || 0}/${st.ct_total || 0}</div></div>
            <div class="stat-card red"><div class="stat-label">CRIT / WARN</div><div class="stat-value ${st.crit_total > 0 ? 'red' : st.warn_total > 0 ? 'yellow' : 'green'}">${st.crit_total || 0} / ${st.warn_total || 0}</div>
                <div class="stat-sub" title="${esc(src.last_error || '')}">${esc(src.code || '—')} · опрос ${fmtTs(src.last_sync_at)}${src.last_status === 'ERROR' ? ' · <span style="color:var(--crit)">ошибка</span>' : ''}</div></div>`;
        badge('badgePve', st.crit_total, st.crit_total > 0);
        document.getElementById('pveTbody').innerHTML = r.data.map(o => `<tr>
            <td class="muted">${esc(PVE_RU[o.obj_type] || o.obj_type)}</td>
            <td class="mono">${esc(o.obj_id)}</td>
            <td><b>${esc(o.name)}</b>${o.extra ? `<div class="muted" style="font-size:11px">${esc(o.extra)}</div>` : ''}${o.pve_version ? `<div class="muted" style="font-size:11px">PVE ${esc(o.pve_version)}</div>` : ''}</td>
            <td>${stBadge(o.status === 'online' || o.status === 'running' || o.status === 'active' ? 'online' : (o.status === 'stopped' || o.status === 'unknown' ? 'inactive' : 'offline'))} <span class="muted" style="font-size:11px">${esc(o.status)}</span></td>
            <td><span class="badge-st ${HEALTH_CLS[o.health] || 'bg-mut'}" title="${esc(o.health_reason || '')}">${esc(o.health)}</span></td>
            <td>${pctCell(o.cpu_pct, 75, 90)}</td>
            <td title="${o.mem_used_mb || 0} / ${o.mem_max_mb || 0} MB">${pctCell(o.mem_pct, 90, 97)}</td>
            <td title="${o.disk_used_gb || 0} / ${o.disk_max_gb || 0} GB">${pctCell(o.disk_pct, 85, 95)}</td>
            <td class="muted">${o.uptime_days != null ? o.uptime_days + ' дн' : '—'}</td>
            <td style="white-space:nowrap"><button class="btn btn-secondary btn-sm" title="AI-досье" onclick="genDossier('pve', ${o.id})">🤖</button></td></tr>`).join('')
            || '<tr><td colspan="10" class="empty-note">Нет данных — нажмите «Синхронизировать»</td></tr>';
    };
    window.setPveType = function (el) { pveTypeSel = chip(el, 'pt'); loadProxmox(); };
    window.syncProxmox = async function () {
        toast('Опрос Proxmox через mTLS-шлюз…');
        syncToast(await api('/proxmox/sync', 'POST', {}), 'Proxmox');
        loadProxmox(); if (window.loadSources) loadSources();
    };

    // ===== SSL-сертификаты =====
    window.loadCerts = async function () {
        const r = await api('/certs');
        if (!r.success) return toast(r.error, true);
        const st = r.stats || {};
        const bad = (st.expired_cnt || 0) + (st.error_cnt || 0);
        document.getElementById('certStatGrid').innerHTML = `
            <div class="stat-card"><div class="stat-label">Доменов</div><div class="stat-value blue">${st.total || 0}</div><div class="stat-sub">OK: ${st.ok_cnt || 0}</div></div>
            <div class="stat-card yellow"><div class="stat-label">Истекают ≤ 14 дн</div><div class="stat-value ${st.expiring_cnt > 0 ? 'yellow' : 'green'}">${st.expiring_cnt || 0}</div></div>
            <div class="stat-card red"><div class="stat-label">Истекли / ошибки</div><div class="stat-value ${bad > 0 ? 'red' : 'green'}">${st.expired_cnt || 0} / ${st.error_cnt || 0}</div></div>
            <div class="stat-card"><div class="stat-label">Ближайший срок</div><div class="stat-value ${st.min_days_left != null && st.min_days_left <= 14 ? 'yellow' : 'green'}">${st.min_days_left != null ? st.min_days_left + ' дн' : '—'}</div>
                <div class="stat-sub">проверено ${fmtTs(st.checked_at)}</div></div>`;
        badge('badgeCerts', (st.expiring_cnt || 0) + bad, bad > 0);
        document.getElementById('certTbody').innerHTML = r.data.map(c => `<tr>
            <td><b>${esc(c.domain_name)}</b>${c.port && c.port !== 443 ? `<span class="muted">:${c.port}</span>` : ''}${c.enabled !== 'Y' ? ' <span class="badge-st bg-mut">выкл</span>' : ''}${c.note ? `<div class="muted" style="font-size:11px">${esc(c.note)}</div>` : ''}</td>
            <td class="muted">${esc(c.issuer || '—')}</td><td class="mono muted">${esc(c.subject_cn || '—')}</td>
            <td>${fmtTs(c.valid_to)}</td>
            <td><b style="color:${c.days_left == null ? 'inherit' : c.days_left < 0 ? 'var(--crit)' : c.days_left <= 14 ? 'var(--warn)' : 'var(--ok)'}">${c.days_left != null ? c.days_left : '—'}</b></td>
            <td class="muted">${esc(c.auto_renew || '—')}</td>
            <td><span class="badge-st ${CERT_CLS[c.status] || 'bg-mut'}" title="${esc(c.last_error || '')}">${esc(c.status || '—')}</span></td>
            <td class="muted">${fmtTs(c.checked_at)}</td>
            <td style="white-space:nowrap">
                <button class="btn btn-secondary btn-sm" title="Проверить" onclick="checkCerts(${c.id})">🔌</button>
                <button class="btn btn-secondary btn-sm" onclick='openCertModal(${JSON.stringify({id: c.id, domain_name: c.domain_name, port: c.port, note: c.note, enabled: c.enabled})})'>✎</button>
                <button class="btn btn-danger btn-sm" onclick="delCert(${c.id}, '${esc(c.domain_name)}')">🗑</button></td></tr>`).join('')
            || '<tr><td colspan="9" class="empty-note">Доменов нет — добавьте первый</td></tr>';
    };
    window.checkCerts = async function (id) {
        toast('Проверяем сертификаты…');
        const r = await api('/certs/check', 'POST', id ? {id} : {});
        if (!r.success) return toast(r.error, true);
        toast(`Проверено: ${r.checked} · с проблемами: ${r.problems} · события +${r.events_created}/−${r.events_resolved}`, r.problems > 0);
        loadCerts();
    };
    window.openCertModal = function (c) {
        c = c || {};
        openModal(`<h3>${c.id ? 'Домен ' + esc(c.domain_name) : 'Новый домен'}</h3>
            <div class="form-row">
                <div class="form-group"><label>Домен</label><input class="form-control mono" id="cert_domain" value="${esc(c.domain_name || '')}" ${c.id ? 'readonly' : ''}></div>
                <div class="form-group"><label>Порт</label><input class="form-control mono" id="cert_port" value="${esc(c.port || 443)}" ${c.id ? 'readonly' : ''}></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Заметка</label><input class="form-control" id="cert_note" value="${esc(c.note || '')}"></div>
                <div class="form-group"><label>Проверять</label><select class="form-control" id="cert_enabled">
                    <option value="Y" ${c.enabled !== 'N' ? 'selected' : ''}>да</option><option value="N" ${c.enabled === 'N' ? 'selected' : ''}>нет</option></select></div>
            </div>
            <div class="btn-group"><button class="btn btn-primary" onclick="saveCert()">Сохранить</button>
            <button class="btn btn-secondary" onclick="closeModal()">Отмена</button></div>`);
    };
    window.saveCert = async function () {
        const r = await api('/certs', 'POST', {domain_name: gv('cert_domain'), port: gv('cert_port'), note: gv('cert_note'), enabled: gv('cert_enabled')});
        toast(r.success ? 'Сохранено' : r.error, !r.success);
        if (r.success) { closeModal(); loadCerts(); }
    };
    window.delCert = async function (id, domain) {
        if (!confirm(`Убрать ${domain} из контроля сертификатов?`)) return;
        const r = await api('/certs/' + id, 'DELETE');
        toast(r.success ? 'Удалено' : r.error, !r.success);
        loadCerts();
    };

    // ===== Подключение к навигации: showPanel() основного скрипта не трогаем =====
    const LOADERS = {services: loadServices, proxmox: loadProxmox, certs: loadCerts};
    const origShowPanel = window.showPanel;
    window.showPanel = function (name) { origShowPanel(name); if (LOADERS[name]) LOADERS[name](); };
    // Бейджи в меню при старте (тихо, без тостов)
    Promise.all([api('/services'), api('/proxmox?health=CRIT'), api('/certs')]).then(([s, p, c]) => {
        if (s.success) badge('badgeSvc', (s.stats || {}).svc_problem, (s.stats || {}).svc_problem > 0);
        if (p.success) badge('badgePve', (p.stats || {}).crit_total, (p.stats || {}).crit_total > 0);
        if (c.success) { const st = c.stats || {}; const bad = (st.expired_cnt || 0) + (st.error_cnt || 0); badge('badgeCerts', (st.expiring_cnt || 0) + bad, bad > 0); }
    }).catch(() => {});
    // Deep-link #services/#proxmox/#certs, если панель уже открыта основным скриптом до подключения этого файла
    const h = location.hash.replace('#', '');
    if (LOADERS[h]) LOADERS[h]();
})();
