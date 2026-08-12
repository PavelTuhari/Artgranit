"""
TBC Emulator — эмулятор 10 сценариев TBControl (docs/TBControl/SCENARIOS.md)
и коннектор к реальному Zabbix.

Режим «эмулятор»: по кругу генерирует все виды ситуаций из сценариев —
нечётный цикл создаёт сбои (события, действия персонала, тикеты, UPS/климат,
очереди, потоки), чётный цикл их устраняет (resolve, retry, восстановление).

Режим «zabbix»: опрашивает реальный Zabbix (JSON-RPC API problem.get),
преобразует активные проблемы в события TBC_EVENTS (severity 0-5 → P4-P1,
привязка по имени хоста = коду устройства MD-CHS-001-POS-01) и закрывает
события по исчезнувшим проблемам.

Запуск отдельным приложением:
    venv/bin/python tbc_emulator.py --url http://localhost:3003 --interval 60
    venv/bin/python tbc_emulator.py --mode zabbix --zabbix-url http://zbx/api_jsonrpc.php --zabbix-token XXX
Либо через UI TBControl: кнопка «🧪 Эмулятор» (управляет фоновым потоком).
"""
import argparse
import random
import sys
import threading
import time

import requests


# ============================================================
# HTTP-клиент TBControl API
# ============================================================

class TBCClient:
    def __init__(self, base_url, username, password):
        self.base = base_url.rstrip('/')
        self.s = requests.Session()
        r = self.s.post(self.base + '/login', data={'username': username, 'password': password}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f'TBC login failed: HTTP {r.status_code}')

    def get(self, path, **kw):
        return self.s.get(self.base + '/api/tbc' + path, timeout=60, **kw).json()

    def post(self, path, payload=None):
        return self.s.post(self.base + '/api/tbc' + path, json=payload or {}, timeout=60).json()

    def put(self, path, payload=None):
        return self.s.put(self.base + '/api/tbc' + path, json=payload or {}, timeout=60).json()


# ============================================================
# Эмулятор сценариев
# ============================================================

class TBCEmulator:
    """Каждый вызов run_cycle() прокручивает все 10 сценариев.
    Нечётный цикл — фаза сбоев, чётный — фаза восстановления."""

    SRC = 'emulator'

    def __init__(self, client: TBCClient, log=None, stop_event=None):
        self.c = client
        self.cycle = 0
        self.log = log or (lambda m: print(f'[emu] {m}', flush=True))
        self.stop_event = stop_event
        self.stores = {}
        self.devices = {}
        self.flows = {}

    # ---------- инфраструктура ----------

    def refresh_refs(self):
        self.stores = {s['code']: s for s in (self.c.get('/stores').get('data') or [])}
        self.devices = {d['code']: d for d in (self.c.get('/devices').get('data') or [])}
        self.flows = {f['code']: f for f in (self.c.get('/flows').get('data') or [])}

    def sid(self, store_code):
        return (self.stores.get(store_code) or {}).get('id')

    def did(self, device_code):
        return (self.devices.get(device_code) or {}).get('id')

    def event(self, sev, store_code, device_code, service, problem, corr=None, parent=None, status=None):
        r = self.c.post('/events', {
            'severity': sev, 'store_id': self.sid(store_code),
            'device_id': self.did(device_code) if device_code else None,
            'service_code': service, 'problem': problem, 'source': self.SRC,
            'correlation_id': corr, 'parent_event_id': parent, 'status': status})
        return (r.get('data') or {}).get('id')

    def action(self, store_code, device_code, action_type, who, note, justified='Y', result='fixed', event_id=None):
        self.c.post('/actions', {'store_id': self.sid(store_code),
                                 'device_id': self.did(device_code) if device_code else None,
                                 'event_id': event_id, 'action_type': action_type, 'performed_by': who,
                                 'note': note, 'is_justified': justified, 'result': result})

    def ticket(self, store_code, target, provider, subject, descr, event_id=None):
        self.c.post('/tickets', {'store_id': self.sid(store_code), 'target': target,
                                 'provider_name': provider, 'subject': subject,
                                 'description': descr, 'related_event_id': event_id,
                                 'opened_by': 'эмулятор: админ магазина'})

    def env(self, samples):
        self.c.post('/env/report', {'samples': samples})

    def heartbeat(self, device_code, **kw):
        self.c.post('/agent/heartbeat', {'device_id': device_code, **kw})

    def my_open_events(self, corr=None):
        evs = self.c.get('/events?status=active&limit=500').get('data') or []
        return [e for e in evs if e.get('source') in (self.SRC, 'correlation')
                and (corr is None or e.get('correlation_id') == corr)]

    def resolve_corr(self, corr):
        """Закрывает события эмулятора по correlation id (root первым —
        suppressed-потомки закроются автоматически)."""
        evs = sorted(self.my_open_events(corr), key=lambda e: 0 if not e.get('parent_event_id') else 1)
        for e in evs:
            self.c.post(f"/events/{e['id']}/resolve")

    # ---------- фоновая «жизнь» сети (каждый цикл) ----------

    def baseline_telemetry(self, fault_phase):
        rnd = random.Random(self.cycle)
        for code, d in self.devices.items():
            if self.stop_event is not None and self.stop_event.is_set():
                return
            if d['device_type'] not in ('POS', 'SCO', 'AND'):
                continue
            if d['status'] == 'offline':
                continue
            hour_load = 1 + 0.5 * abs(__import__('math').sin(time.time() / 3600))
            payload = {
                'status': 'OK',
                'cpu': min(97, int(rnd.uniform(15, 40) * hour_load)),
                'ram': min(97, int(rnd.uniform(35, 60))),
                'disk': d.get('disk_pct') or int(rnd.uniform(40, 70)),
                'app_latency': int(rnd.uniform(18, 60)),
                'tx_count': int(rnd.uniform(10, 55)),
                'app_errors': 1 if rnd.random() > 0.93 else 0,
                # Сценарий 8: SCO-02 магазина 001 не работает → очереди выше
                'queue_len': int(rnd.uniform(5, 9)) if code.startswith('MD-CHS-001-POS') and fault_phase
                             else int(rnd.uniform(0, 5)),
            }
            if d['device_type'] == 'AND':
                payload['battery'] = max(5, int((d.get('battery_pct') or 80) - rnd.uniform(0, 3)))
                payload['storage_free_mb'] = d.get('storage_free_mb') or 20000
            if d['device_type'] in ('POS', 'SCO'):
                payload['application'] = 'frontoffice' if d['device_type'] == 'POS' else 'sco_app'
                payload['version'] = '7.4.12' if d['device_type'] == 'POS' else '3.8.4'
            self.heartbeat(code, **payload)

    # ---------- 10 сценариев ----------

    def s1_power_ups(self, fault):
        """Сценарий 1: отключение света, Local Expres на UPS."""
        st = 'MD-CHS-013'
        corr = f'em-pw13-{(self.cycle + 1) // 2}'
        if fault:
            ev = self.event('P2', st, None, 'power',
                            'ЭМУЛЯТОР: отключение электроснабжения — магазин работает на UPS', corr)
            self.action(st, 'MD-CHS-013-POS-01', 'switch_ups', 'админ В.Мунтяну',
                        'Касса и роутер переведены на UPS', 'Y', 'fixed', ev)
            self.ticket(st, 'power_company', 'Premier Energy', 'Отключение электроснабжения',
                        'Магазин на UPS, батареи на ~50 минут', ev)
            batt = 100
            samples = []
            for i in range(6):
                samples += [{'store_code': st, 'metric': 'on_ups', 'value': 1},
                            {'store_code': st, 'metric': 'ups_battery_pct', 'value': batt - i * 12},
                            {'store_code': st, 'metric': 'ups_runtime_min', 'value': max(5, 80 - i * 13)}]
            self.env(samples)
            self.log(f's1: отключение света {st}, UPS активен')
        else:
            self.resolve_corr(corr)
            self.env([{'store_code': st, 'metric': 'on_ups', 'value': 0},
                      {'store_code': st, 'metric': 'ups_battery_pct', 'value': 100}])
            self.log('s1: питание восстановлено, UPS в буфере')

    def s2_power_no_ups(self, fault):
        """Сценарий 2: свет пропал, касса без UPS погасла (Орхей)."""
        st, dev = 'MD-ORH-201', 'MD-ORH-201-POS-02'
        corr = f'em-pw201-{(self.cycle + 1) // 2}'
        if fault:
            self.event('P3', st, dev, 'power',
                       'ЭМУЛЯТОР: POS-02 отключился при пропадании питания (без UPS)', corr)
            self.log(f's2: {dev} погас без UPS')
        else:
            ev = self.my_open_events(corr)
            self.action(st, dev, 'restart_pos', 'админ Е.Кожокару',
                        'Штатный запуск кассы после подачи питания', 'Y', 'fixed',
                        ev[0]['id'] if ev else None)
            self.resolve_corr(corr)
            self.heartbeat(dev, status='OK', cpu=25, ram=40, disk=48)
            self.log('s2: касса запущена после восстановления питания')

    def s3_isp_outage(self, fault):
        """Сценарий 3: авария ISP — корреляция root cause → suppressed."""
        st = 'MD-BLT-102'
        corr = f'em-isp102-{(self.cycle + 1) // 2}'
        if fault:
            root = self.event('P2', st, 'MD-BLT-102-NET-01', 'isp',
                              'ЭМУЛЯТОР: интернет-канал StarNet недоступен', corr)
            self.event('P3', st, 'MD-BLT-102-POS-01', 'bank_pos',
                       'ЭМУЛЯТОР: банковский терминал не авторизует карты (нет связи)', corr,
                       parent=root, status='suppressed')
            self.event('P3', st, 'MD-BLT-102-POS-01', 'mev',
                       'ЭМУЛЯТОР: MEV offline-очередь чеков растёт', corr,
                       parent=root, status='suppressed')
            self.action(st, 'MD-BLT-102-NET-01', 'restart_router', 'админ А.Гуцу',
                        'Перезагрузка роутера — линк не поднялся', 'Y', 'no_effect', root)
            self.ticket(st, 'isp', 'StarNet', 'Пропал интернет-канал',
                        'Роутер перезагружали, линк не поднимается', root)
            self.ticket(st, 'bank', 'MAIB', 'Терминал не авторизует карты',
                        'Ответ банка: процессинг в норме, у магазина нет интернета', root)
            self.log(f's3: авария ISP {st}: root + 2 suppressed')
        else:
            self.resolve_corr(corr)
            self.log('s3: канал ISP восстановлен, suppressed закрыты автоматически')

    def s4_bank_host(self, fault):
        """Сценарий 4: сбой процессинга банка + ненужные перезагрузки касс."""
        st, dev = 'MD-CHS-010', 'MD-CHS-010-POS-02'
        corr = f'em-bnk010-{(self.cycle + 1) // 2}'
        if fault:
            ev = self.event('P2', st, None, 'bank_pos',
                            'ЭМУЛЯТОР: терминалы Victoriabank отказывают (интернет в норме)', corr)
            for i in range(3):
                self.action(st, dev, 'restart_pos', 'кассир М.Руссу',
                            f'Ненужная перезагрузка кассы №{i + 1} — причина на стороне банка',
                            'N', 'no_effect', ev)
            self.action(st, None, 'call_bank', 'админ И.Чобану',
                        'Банк подтвердил сбой процессинга', 'Y', 'escalated', ev)
            self.ticket(st, 'bank', 'Victoriabank', 'Отказ авторизации карт',
                        'Интернет в норме, терминалы получают отказ хоста', ev)
            self.log(f's4: сбой банка {st} + 3 ненужные перезагрузки')
        else:
            self.resolve_corr(corr)
            self.log('s4: банк восстановил процессинг')

    def s5_mev(self, fault):
        """Сценарий 5: деградация MEV (SFS) по сети."""
        st = 'MD-CHS-011'
        corr = f'em-mev-{(self.cycle + 1) // 2}'
        if fault:
            ev = self.event('P2', st, None, 'mev',
                            'ЭМУЛЯТОР: MEV (SFS) массовые таймауты, чеки в offline-очереди', corr)
            self.ticket(st, 'mev', 'MEV (SFS)', 'Таймауты фискализации по сети',
                        'Чеки копятся в offline-очереди', ev)
            self.log('s5: деградация MEV')
        else:
            self.resolve_corr(corr)
            self.log('s5: MEV восстановлен, очереди отправлены')

    def s6_heat(self, fault):
        """Сценарий 6: жара — перегрев серверных + просадки напряжения."""
        st = 'MD-CHS-011'
        corr = f'em-heat-{(self.cycle + 1) // 2}'
        if fault:
            ev = self.event('P2', st, 'MD-CHS-011-SRV-01', 'climate',
                            'ЭМУЛЯТОР: перегрев серверной 34°C (на улице +38°C)', corr)
            self.event('P4', st, None, 'power',
                       'ЭМУЛЯТОР: просадки напряжения до 198V — перегрузка электросети', corr)
            self.env([{'store_code': st, 'metric': 'temp_air', 'value': round(36 + random.uniform(0, 3), 1)},
                      {'store_code': st, 'metric': 'temp_server_room', 'value': round(32 + random.uniform(0, 2.5), 1)},
                      {'store_code': st, 'metric': 'grid_voltage', 'value': int(random.uniform(196, 207))},
                      {'node_code': 'CENTRAL-01', 'metric': 'temp_server_room', 'value': round(29 + random.uniform(0, 2), 1)},
                      {'node_code': 'CENTRAL-01', 'metric': 'ups_load_pct', 'value': int(random.uniform(72, 84))}])
            self.action(st, 'MD-CHS-011-SRV-01', 'other', 'админ Д.Сырбу',
                        'Включён резервный кондиционер серверной', 'Y', 'fixed', ev)
            self.ticket(st, 'network_support', 'Техподдержка сети', 'Перегрев серверной',
                        '34°C и растёт, сервер деградирует', ev)
            self.log('s6: жара, перегрев серверных + просадки напряжения')
        else:
            self.resolve_corr(corr)
            self.env([{'store_code': st, 'metric': 'temp_server_room', 'value': round(26 + random.uniform(0, 2), 1)},
                      {'store_code': st, 'metric': 'grid_voltage', 'value': int(random.uniform(216, 224))},
                      {'node_code': 'CENTRAL-01', 'metric': 'temp_server_room', 'value': round(24 + random.uniform(0, 1.5), 1)},
                      {'node_code': 'CENTRAL-01', 'metric': 'ups_load_pct', 'value': int(random.uniform(55, 65))}])
            self.log('s6: температура и напряжение в норме')

    def s7_frost(self, fault):
        """Сценарий 7: мороз в Орхее."""
        st = 'MD-ORH-201'
        if fault:
            self.env([{'store_code': st, 'metric': 'temp_air', 'value': round(-14 - random.uniform(0, 5), 1)}])
            ev = self.event('P4', st, None, 'climate',
                            'ЭМУЛЯТОР: мороз до -18°C — прогрев оборудования перед включением',
                            f'em-frost-{(self.cycle + 1) // 2}')
            self.c.post(f'/events/{ev}/resolve')  # информационное, сразу закрываем
            self.log('s7: морозный кейс зафиксирован')
        else:
            self.env([{'store_code': st, 'metric': 'temp_air', 'value': round(-4 - random.uniform(0, 3), 1)}])

    def s8_queues(self, fault):
        """Сценарий 8: очереди — генерируются в baseline_telemetry.
        В фазе сбоя SCO-02 магазина 001 «не работает» → очереди растут."""
        dev = 'MD-CHS-001-SCO-02'
        if fault:
            self.log('s8: SCO-02 001 не работает — очереди на POS растут (baseline)')
        else:
            self.heartbeat(dev, status='OK', cpu=20, ram=38, disk=45)
            self.log('s8: SCO-02 запущен — очереди нормализуются')

    def s9_support_delay(self, fault):
        """Сценарий 9: контроль времени реакции поддержки."""
        st = 'MD-CHS-003'
        if fault:
            self.ticket(st, 'network_support', 'Техподдержка сети',
                        'ЭМУЛЯТОР: магазин offline — сеть недоступна',
                        'Ответа нет, время реакции пошло')
            self.log('s9: тикет в техподдержку открыт (ждёт реакции)')
        else:
            tks = self.c.get('/tickets?status=open').get('data') or []
            for t in tks:
                if 'ЭМУЛЯТОР' in (t.get('subject') or ''):
                    self.c.put(f"/tickets/{t['id']}", {'status': 'answered'})
            self.log('s9: техподдержка ответила на открытые тикеты эмулятора')

    def s10_flows_and_dossier(self, fault):
        """Сценарий 10: сбой потока обмена + AI-досье."""
        flow = self.flows.get('F-CENTRAL-BACKOFF')
        if not flow:
            return
        if fault:
            self.c.post(f"/flows/{flow['id']}/report",
                        {'status': 'FAIL', 'batch_code': f'EM-{self.cycle}',
                         'rows_sent': 9000, 'rows_accepted': 0,
                         'pending_rows': 9000, 'error': 'ЭМУЛЯТОР: staging import rejected'})
            d = self.c.post('/ai/dossiers/generate', {'source_type': 'flow', 'ref_id': flow['id']})
            code = (d.get('data') or {}).get('code')
            self.log(f's10: поток центральный→бэк-офис FAIL, AI-досье {code}')
        else:
            self.c.post(f"/flows/{flow['id']}/retry")
            self.log('s10: поток повторён, pending отправлен')

    # ---------- цикл ----------

    def run_cycle(self):
        self.cycle += 1
        fault = (self.cycle % 2 == 1)
        phase = 'СБОИ' if fault else 'ВОССТАНОВЛЕНИЕ'
        self.log(f'===== Цикл {self.cycle} — фаза {phase} =====')
        self.refresh_refs()
        self.baseline_telemetry(fault)
        for fn in (self.s1_power_ups, self.s2_power_no_ups, self.s3_isp_outage,
                   self.s4_bank_host, self.s5_mev, self.s6_heat, self.s7_frost,
                   self.s8_queues, self.s9_support_delay, self.s10_flows_and_dossier):
            if self.stop_event is not None and self.stop_event.is_set():
                self.log('Цикл прерван по запросу остановки')
                break
            try:
                fn(fault)
            except Exception as e:
                self.log(f'{fn.__name__}: ошибка {e}')
        return {'cycle': self.cycle, 'phase': phase}


# ============================================================
# Zabbix-коннектор (реальные события)
# ============================================================

class ZabbixConnector:
    """Опрашивает реальный Zabbix и синхронизирует проблемы в TBControl.

    Поддерживает Zabbix 3.x–7.x:
      - аутентификация: API-token (Bearer, 5.4+) ИЛИ логин/пароль
        (user.login → session auth, обязательно для 3.x/4.x);
      - выборка проблем: problem.get (4.0+, есть severity) ИЛИ
        trigger.get value=1 (3.x, severity = priority триггера).

    severity Zabbix → приоритет TBC: 5 Disaster→P1, 4 High→P2,
    3 Average→P3, 2 Warning→P3, 1 Info/0→P4.
    Привязка: имя хоста Zabbix == код устройства TBC (MD-CHS-001-POS-01);
    неизвестный хост — событие без устройства, хост в тексте.
    Correlation ID = 'zbx-<eventid|t<triggerid>>' — по нему закрываем решённые."""

    SEV_MAP = {5: 'P1', 4: 'P2', 3: 'P3', 2: 'P3', 1: 'P4', 0: 'P4'}

    def __init__(self, client: TBCClient, zabbix_url, zabbix_token=None,
                 zabbix_user=None, zabbix_password=None, log=None):
        self.c = client
        self.url = zabbix_url
        self.token = (zabbix_token or '').strip() or None
        self.user = (zabbix_user or '').strip() or None
        self.password = zabbix_password or None
        self.log = log or (lambda m: print(f'[zbx] {m}', flush=True))
        self.version = (0, 0)
        self._auth = None       # session token (user.login) либо API-token через auth-параметр
        self._bearer = False    # токен через заголовок Authorization (5.4+)

    def _rpc(self, method, params, with_auth=True):
        body = {'jsonrpc': '2.0', 'method': method, 'params': params, 'id': 1}
        headers = {'Content-Type': 'application/json-rpc'}
        if with_auth:
            if self._bearer and self.token:
                headers['Authorization'] = f'Bearer {self.token}'
            elif self._auth:
                body['auth'] = self._auth
        r = requests.post(self.url, json=body, headers=headers, timeout=30)
        data = r.json()
        if 'error' in data:
            raise RuntimeError(f"Zabbix API: {data['error'].get('data') or data['error'].get('message')}")
        return data['result']

    def connect(self):
        """Определяет версию и аутентифицируется. Возвращает строку версии."""
        ver = self._rpc('apiinfo.version', {}, with_auth=False)
        try:
            self.version = tuple(int(x) for x in ver.split('.')[:2])
        except ValueError:
            self.version = (0, 0)
        if self.user and self.password:
            # user.login: параметр 'user' до 5.4, 'username' с 5.4 (в 6.4 'user' удалён)
            try:
                self._auth = self._rpc('user.login', {'user': self.user, 'password': self.password},
                                       with_auth=False)
            except RuntimeError:
                self._auth = self._rpc('user.login', {'username': self.user, 'password': self.password},
                                       with_auth=False)
        elif self.token:
            if self.version >= (5, 4):
                self._bearer = True
            else:
                raise RuntimeError(f'Zabbix {ver}: API-токенов нет — укажите логин/пароль')
        else:
            raise RuntimeError('Не заданы ни API-token, ни логин/пароль Zabbix')
        return ver

    def fetch_problems(self):
        """Список активных проблем в едином виде:
        [{corr, name, severity(int), host}]"""
        out = []
        if self.version >= (4, 0):
            problems = self._rpc('problem.get', {
                'output': ['eventid', 'name', 'severity', 'clock'],
                'recent': False, 'limit': 500})
            ev_ids = [p['eventid'] for p in problems]
            hosts_by_event = {}
            if ev_ids:
                events = self._rpc('event.get', {'eventids': ev_ids, 'output': ['eventid'],
                                                 'selectHosts': ['host']})
                for e in events:
                    hs = e.get('hosts') or []
                    if hs:
                        hosts_by_event[e['eventid']] = hs[0]['host']
            for p in problems:
                out.append({'corr': f"zbx-{p['eventid']}", 'name': p['name'],
                            'severity': int(p.get('severity', 0)),
                            'host': hosts_by_event.get(p['eventid'], '')})
        else:
            # Zabbix 3.x: активные проблемы = триггеры в состоянии PROBLEM
            triggers = self._rpc('trigger.get', {
                'output': ['triggerid', 'description', 'priority'],
                'filter': {'value': 1}, 'monitored': True, 'active': True,
                'expandDescription': True, 'selectHosts': ['host'], 'limit': 500})
            for t in triggers:
                hs = t.get('hosts') or []
                out.append({'corr': f"zbx-t{t['triggerid']}", 'name': t['description'],
                            'severity': int(t.get('priority', 0)),
                            'host': hs[0]['host'] if hs else ''})
        return out

    def sync(self):
        """Один проход синхронизации. Возвращает (created, resolved)."""
        problems = self.fetch_problems()
        devices = {d['code']: d for d in (self.c.get('/devices').get('data') or [])}
        active = {e.get('correlation_id'): e for e in
                  (self.c.get('/events?status=active&limit=500').get('data') or [])
                  if (e.get('correlation_id') or '').startswith('zbx-')}

        created = resolved = 0
        seen = set()
        for p in problems:
            corr = p['corr']
            seen.add(corr)
            if corr in active:
                continue
            dev = devices.get(p['host'])
            sev = self.SEV_MAP.get(p['severity'], 'P4')
            self.c.post('/events', {
                'severity': sev,
                'store_id': dev.get('store_id') if dev else None,
                'device_id': dev.get('id') if dev else None,
                'service_code': None,
                'problem': f"Zabbix: {p['name']}" + (f" [{p['host']}]" if p['host'] and not dev else ''),
                'source': 'zabbix', 'correlation_id': corr})
            created += 1
        # Закрываем события, которых больше нет среди проблем Zabbix
        for corr, e in active.items():
            if corr not in seen:
                self.c.post(f"/events/{e['id']}/resolve")
                resolved += 1
        if created or resolved:
            self.log(f'sync: создано {created}, закрыто {resolved} (активных проблем: {len(problems)})')
        return created, resolved


# ============================================================
# Фоновый рантайм (используется из Flask-приложения)
# ============================================================

class EmulatorRuntime:
    """Один фоновый поток: режим 'emulator' или 'zabbix'."""

    def __init__(self):
        self._thread = None
        self._stop = threading.Event()
        self.state = {'running': False, 'mode': None, 'cycle': 0, 'log': [], 'error': None}
        self._lock = threading.Lock()

    def _log(self, msg):
        with self._lock:
            self.state['log'] = (self.state['log'] + [f"{time.strftime('%H:%M:%S')} {msg}"])[-40:]

    def start(self, mode, base_url, username, password, interval=60,
              zabbix_url=None, zabbix_token=None):
        if self._thread and self._thread.is_alive():
            if self._stop.is_set():
                # Остановка запрошена — даём потоку дозавершить текущий цикл
                self._thread.join(timeout=10)
            if self._thread.is_alive():
                return {'success': False,
                        'error': 'Предыдущий запуск ещё завершается — повторите через несколько секунд'
                                 if self._stop.is_set() else 'Уже запущен — сначала остановите'}
        self._stop.clear()
        self.state.update({'running': True, 'mode': mode, 'cycle': 0, 'log': [], 'error': None})

        def worker():
            try:
                client = TBCClient(base_url, username, password)
                if mode == 'zabbix':
                    conn = ZabbixConnector(client, zabbix_url, zabbix_token, log=self._log)
                    ver = conn.test()
                    self._log(f'Zabbix API {ver}: подключение установлено')
                    while not self._stop.is_set():
                        try:
                            conn.sync()
                            self.state['cycle'] += 1
                        except Exception as e:
                            self._log(f'ошибка sync: {e}')
                        self._stop.wait(interval)
                else:
                    emu = TBCEmulator(client, log=self._log, stop_event=self._stop)
                    while not self._stop.is_set():
                        emu.run_cycle()
                        self.state['cycle'] = emu.cycle
                        self._stop.wait(interval)
            except Exception as e:
                self.state['error'] = str(e)
                self._log(f'ФАТАЛЬНО: {e}')
            finally:
                self.state['running'] = False

        self._thread = threading.Thread(target=worker, daemon=True, name='tbc-emulator')
        self._thread.start()
        return {'success': True}

    def stop(self):
        self._stop.set()
        self.state['running'] = False
        self._log('Остановлено пользователем')
        return {'success': True}

    def status(self):
        with self._lock:
            return dict(self.state)


RUNTIME = EmulatorRuntime()


# ============================================================
# CLI
# ============================================================

def main():
    ap = argparse.ArgumentParser(description='TBC Emulator / Zabbix connector')
    ap.add_argument('--url', default='http://localhost:3003', help='База TBControl (Flask)')
    ap.add_argument('--username', default=None)
    ap.add_argument('--password', default=None)
    ap.add_argument('--mode', choices=['emulator', 'zabbix'], default='emulator')
    ap.add_argument('--interval', type=int, default=60, help='Пауза между циклами, сек')
    ap.add_argument('--cycles', type=int, default=0, help='Число циклов (0 = бесконечно)')
    ap.add_argument('--zabbix-url', default=None, help='Zabbix api_jsonrpc.php')
    ap.add_argument('--zabbix-token', default=None, help='Zabbix API token')
    args = ap.parse_args()

    user, pwd = args.username, args.password
    if not user or not pwd:
        try:
            from dotenv import dotenv_values
            vals = dotenv_values('.env')
            user = user or vals.get('DEFAULT_USERNAME') or vals.get('DB_USER')
            pwd = pwd or vals.get('DEFAULT_PASSWORD') or vals.get('DB_PASSWORD')
        except Exception:
            pass
    if not user or not pwd:
        print('Нужны --username/--password (или .env)', file=sys.stderr)
        sys.exit(2)

    client = TBCClient(args.url, user, pwd)
    if args.mode == 'zabbix':
        if not args.zabbix_url or not args.zabbix_token:
            print('Для режима zabbix нужны --zabbix-url и --zabbix-token', file=sys.stderr)
            sys.exit(2)
        conn = ZabbixConnector(client, args.zabbix_url, args.zabbix_token)
        print(f'Zabbix API version: {conn.test()}')
        n = 0
        while args.cycles == 0 or n < args.cycles:
            conn.sync()
            n += 1
            if args.cycles == 0 or n < args.cycles:
                time.sleep(args.interval)
    else:
        emu = TBCEmulator(client)
        n = 0
        while args.cycles == 0 or n < args.cycles:
            emu.run_cycle()
            n += 1
            if args.cycles == 0 or n < args.cycles:
                time.sleep(args.interval)


if __name__ == '__main__':
    main()
