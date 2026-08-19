# PECO Fuel Retail ERP — Implementation Plan, Part 3 (Tasks 15–20)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
>
> **Read Part 1 first:** `docs/superpowers/plans/2026-08-19-peco-fuel-retail.md` — Global Constraints and Tasks 1–8. **Part 2:** `...-part2.md` — Tasks 9–14.

**Covers:** Task 15 (routes), Stage G (templates), Stage H (documentation).

---

### Task 15: Register routes in `app.py`

**Files:**
- Modify: `app.py` — import near line 23 (with the other controller imports), routes appended at the end of the route section

**Interfaces:**
- Consumes: `PecoController` from Task 14; `AuthController.is_authenticated`.
- Produces: page routes `/UNA.md/orasldev/peco-pump`, `peco-shift`, `peco-admin`; JSON API under `/api/peco/...`.

- [ ] **Step 1: Add the import**

In `app.py`, after the existing line `from controllers.tbcontrol_controller import TBControlController`, add:

```python
from controllers.peco_controller import PecoController
```

- [ ] **Step 2: Append the routes**

Add at the end of `app.py`, before any `if __name__ == '__main__':` block:

```python
# ========== PECO (розничная продажа топлива в сети АЗС) Routes ==========

def _peco_station_id():
    """Станция из query-параметра; по умолчанию первая активная."""
    raw = request.args.get('station_id') or request.form.get('station_id')
    if raw:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    stations = PecoController.admin_overview()
    items = stations.get('stations') or []
    return items[0]['id'] if items else None


@app.route('/UNA.md/orasldev/peco-pump')
@app.route('/UNA.md/orasldev/peco-pump/')
def peco_pump():
    """Фронт-офис колонки: самообслуживание и отпуск сотрудником."""
    if not AuthController.is_authenticated():
        return redirect(url_for('login', next=request.path))
    return render_template('peco_pump.html')


@app.route('/UNA.md/orasldev/peco-shift')
@app.route('/UNA.md/orasldev/peco-shift/')
def peco_shift_console():
    """Консоль оператора АЗС: смена, счётчики, приём цистерн, касса."""
    if not AuthController.is_authenticated():
        return redirect(url_for('login', next=request.path))
    return render_template('peco_shift.html')


@app.route('/UNA.md/orasldev/peco-admin')
@app.route('/UNA.md/orasldev/peco-admin/')
def peco_admin():
    """Бэк-офис: сеть АЗС, цены, остатки, расхождения."""
    if not AuthController.is_authenticated():
        return redirect(url_for('login', next=request.path))
    return render_template('peco_admin.html')


@app.route('/UNA.md/orasldev/docs/peco/TZ.html')
@app.route('/UNA.md/orasldev/docs/peco/')
def peco_tz():
    """Страница технического задания PECO с кнопками входа в интерфейсы."""
    from flask import send_file
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'docs', 'PECO', 'TZ.html'))


# ---------- PECO API ----------

@app.route('/api/peco/pump/state')
def api_peco_pump_state():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    station_id = _peco_station_id()
    if station_id is None:
        return jsonify({"success": False, "error": "Нет активных станций"})
    return jsonify(PecoController.pump_state(station_id))


@app.route('/api/peco/txn/authorize', methods=['POST'])
def api_peco_txn_authorize():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.authorize(request.get_json(silent=True) or {}))


@app.route('/api/peco/txn/start', methods=['POST'])
def api_peco_txn_start():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.start(request.get_json(silent=True) or {}))


@app.route('/api/peco/txn/finish', methods=['POST'])
def api_peco_txn_finish():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.finish(request.get_json(silent=True) or {}))


@app.route('/api/peco/txn/pay', methods=['POST'])
def api_peco_txn_pay():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.pay(request.get_json(silent=True) or {}))


@app.route('/api/peco/txn/void', methods=['POST'])
def api_peco_txn_void():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.void(request.get_json(silent=True) or {}))


@app.route('/api/peco/shift/open', methods=['POST'])
def api_peco_shift_open():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_open(request.get_json(silent=True) or {}))


@app.route('/api/peco/shift/<int:shift_id>/meters')
def api_peco_shift_meters(shift_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_meters(shift_id))


@app.route('/api/peco/shift/meter', methods=['POST'])
def api_peco_shift_meter():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_save_meter(request.get_json(silent=True) or {}))


@app.route('/api/peco/shift/close', methods=['POST'])
def api_peco_shift_close():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_close(request.get_json(silent=True) or {}))


@app.route('/api/peco/shift/approve', methods=['POST'])
def api_peco_shift_approve():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_approve(request.get_json(silent=True) or {}))


@app.route('/api/peco/delivery', methods=['POST'])
def api_peco_delivery():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.delivery_receive(request.get_json(silent=True) or {}))


@app.route('/api/peco/tanks')
def api_peco_tanks():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    station_id = _peco_station_id()
    if station_id is None:
        return jsonify({"success": False, "error": "Нет активных станций"})
    return jsonify(PecoController.tank_levels(station_id))


@app.route('/api/peco/admin/overview')
def api_peco_admin_overview():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.admin_overview())


@app.route('/api/peco/admin/price', methods=['POST'])
def api_peco_admin_price():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.set_price(request.get_json(silent=True) or {}))
```

- [ ] **Step 3: Verify the app still imports**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 4: Verify every PECO route is registered**

Run: `python -c "
import re
s = open('app.py').read()
routes = re.findall(r\"@app.route\('(/(?:api/peco|UNA.md/orasldev/peco)[^']*)'\", s)
assert len(routes) >= 18, routes
print(len(routes), 'PECO routes')"`

Expected: `18 PECO routes` (or more)

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "PECO: маршруты фронт-офиса, консоли смены, бэк-офиса и API"
```

---

## Stage G — Templates

Templates in this codebase are self-contained monolithic HTML with no base template. Follow that convention.

### Task 16: Pump front office

**Files:**
- Create: `templates/peco_pump.html`

**Interfaces:**
- Consumes: `GET /api/peco/pump/state`, `POST /api/peco/txn/{authorize,start,finish,pay}`.
- Produces: no server-side interface.

- [ ] **Step 1: Create the template**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PECO — Колонка</title>
<style>
:root{--bg:#0b1220;--card:#111c30;--line:#1e2d47;--text:#e7eefc;--muted:#8fa3c4;
      --accent:#f59e0b;--ok:#22c55e;--danger:#ef4444;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);
     padding:20px;min-height:100vh;}
header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;
       flex-wrap:wrap;gap:12px;}
h1{font-size:22px;}
.badge{font-size:13px;color:var(--muted);}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;}
.nozzle{background:var(--card);border:2px solid var(--line);border-radius:16px;padding:20px;
        cursor:pointer;transition:border-color .15s;}
.nozzle:hover{border-color:var(--accent);}
.nozzle.sel{border-color:var(--accent);}
.nozzle .g{font-size:24px;font-weight:700;}
.nozzle .p{font-size:28px;margin-top:8px;}
.nozzle .m{font-size:12px;color:var(--muted);margin-top:8px;}
.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;
       margin-top:20px;}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:12px;}
label{font-size:13px;color:var(--muted);display:block;margin-bottom:4px;}
input{background:#0a1526;border:1px solid var(--line);border-radius:10px;padding:12px;
      color:var(--text);font-size:18px;width:180px;}
button{border:0;border-radius:10px;padding:14px 22px;font-size:16px;font-weight:600;
       cursor:pointer;background:var(--accent);color:#1a1205;}
button.ghost{background:transparent;border:1px solid var(--line);color:var(--text);}
button.ok{background:var(--ok);color:#052e13;}
button:disabled{opacity:.45;cursor:not-allowed;}
.total{font-size:36px;font-weight:700;margin:12px 0;}
.msg{padding:12px 16px;border-radius:10px;margin-top:12px;font-size:14px;}
.msg.err{background:#3b1114;color:#fca5a5;}
.msg.ok{background:#0d2b18;color:#86efac;}
.hidden{display:none;}
</style>
</head>
<body>
<header>
  <h1>⛽ Колонка — отпуск топлива</h1>
  <div class="badge" id="shiftBadge">загрузка…</div>
</header>

<div class="grid" id="nozzles"></div>

<div class="panel hidden" id="panel">
  <div class="row">
    <div>
      <label>Режим</label>
      <button class="ghost" id="modeBtn" onclick="toggleMode()">Самообслуживание</button>
    </div>
    <div>
      <label>Показание счётчика на старте</label>
      <input id="meterStart" type="number" step="0.001" readonly>
    </div>
  </div>

  <div class="row" id="authRow">
    <button id="authBtn" onclick="doAuthorize()">Авторизовать налив</button>
  </div>

  <div class="row hidden" id="dispRow">
    <div>
      <label>Показание счётчика на финише</label>
      <input id="meterEnd" type="number" step="0.001">
    </div>
    <button class="ok" onclick="doFinish()">Завершить налив</button>
  </div>

  <div class="hidden" id="payBlock">
    <div class="total" id="totalTxt">—</div>
    <div class="row">
      <button onclick="doPay('CASH')">Оплата наличными на кассе</button>
      <button onclick="doPay('MIA_QR')">Оплата MIA QR</button>
      <button class="ghost" onclick="doVoid()">Аннулировать</button>
    </div>
  </div>

  <div id="msg"></div>
</div>

<script>
var state = null, sel = null, txn = null, selfService = true;

function api(url, body) {
  var opt = body ? {method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify(body)} : {};
  return fetch(url, opt).then(function(r){ return r.json(); });
}

function say(text, kind) {
  document.getElementById('msg').innerHTML =
    text ? '<div class="msg ' + (kind||'ok') + '">' + text + '</div>' : '';
}

function load() {
  api('/api/peco/pump/state').then(function(r){
    if (!r.success) { document.getElementById('shiftBadge').textContent = r.error; return; }
    state = r;
    document.getElementById('shiftBadge').textContent = 'Смена №' + r.shift_id;
    var html = '';
    r.nozzles.forEach(function(n){
      var price = r.prices[n.grade_code];
      html += '<div class="nozzle" data-id="' + n.id + '" onclick="pick(' + n.id + ')">' +
              '<div class="g">' + n.grade_code + '</div>' +
              '<div class="p">' + (price !== undefined ? price.toFixed(2) + ' л/лей' : 'нет цены') + '</div>' +
              '<div class="m">' + n.pump_code + ' · ' + n.code +
              ' · счётчик ' + Number(n.meter_total).toFixed(3) + '</div></div>';
    });
    document.getElementById('nozzles').innerHTML = html;
  });
}

function pick(id) {
  sel = state.nozzles.filter(function(n){ return n.id === id; })[0];
  document.querySelectorAll('.nozzle').forEach(function(el){
    el.classList.toggle('sel', Number(el.dataset.id) === id);
  });
  document.getElementById('panel').classList.remove('hidden');
  document.getElementById('meterStart').value = Number(sel.meter_total).toFixed(3);
  resetFlow();
}

function resetFlow() {
  txn = null;
  document.getElementById('authRow').classList.remove('hidden');
  document.getElementById('dispRow').classList.add('hidden');
  document.getElementById('payBlock').classList.add('hidden');
  say('');
}

function toggleMode() {
  selfService = !selfService;
  document.getElementById('modeBtn').textContent =
    selfService ? 'Самообслуживание' : 'Отпуск сотрудником';
}

function doAuthorize() {
  if (!sel) return;
  api('/api/peco/txn/authorize', {
    station_id: state.station_id, shift_id: state.shift_id,
    nozzle_id: sel.id, grade_code: sel.grade_code,
    meter_start: Number(document.getElementById('meterStart').value),
    is_self_service: selfService
  }).then(function(r){
    if (!r.success) { say(r.error, 'err'); return; }
    txn = r.txn_id;
    return api('/api/peco/txn/start', {txn_id: txn});
  }).then(function(r){
    if (!r || !r.success) { if (r) say(r.error, 'err'); return; }
    document.getElementById('authRow').classList.add('hidden');
    document.getElementById('dispRow').classList.remove('hidden');
    say('Налив разрешён. Введите показание счётчика по окончании.');
  });
}

function doFinish() {
  api('/api/peco/txn/finish', {
    txn_id: txn, meter_end: Number(document.getElementById('meterEnd').value)
  }).then(function(r){
    if (!r.success) { say(r.error, 'err'); return; }
    document.getElementById('dispRow').classList.add('hidden');
    document.getElementById('totalTxt').textContent =
      r.liters.toFixed(3) + ' л · ' + r.amount.toFixed(2) + ' лей';
    if (r.status === 'PAID') {
      say('Оплачено по MIA QR (предавторизация самообслуживания).');
      setTimeout(load, 1200);
    } else {
      document.getElementById('payBlock').classList.remove('hidden');
      say('Ожидает оплаты на кассе.');
    }
  });
}

function doPay(method) {
  var ref = null;
  if (method === 'MIA_QR') {
    ref = prompt('Ссылка платежа MIA:');
    if (!ref) { say('Не указана ссылка платежа MIA', 'err'); return; }
  }
  api('/api/peco/txn/pay', {txn_id: txn, pay_method: method, mia_ref: ref})
    .then(function(r){
      if (!r.success) { say(r.error, 'err'); return; }
      say('Транзакция оплачена.');
      setTimeout(load, 1000);
      resetFlow();
    });
}

function doVoid() {
  var reason = prompt('Причина аннулирования:') || 'не указана';
  api('/api/peco/txn/void', {txn_id: txn, reason: reason}).then(function(r){
    if (!r.success) { say(r.error, 'err'); return; }
    say('Транзакция аннулирована.');
    resetFlow(); load();
  });
}

load();
</script>
</body>
</html>
```

- [ ] **Step 2: Verify the template renders as valid HTML**

Run: `python -c "
s = open('templates/peco_pump.html').read()
assert '/api/peco/txn/authorize' in s and '/api/peco/txn/pay' in s
assert s.count('<script>') == s.count('</script>')
print('ok')"`

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add templates/peco_pump.html
git commit -m "PECO: фронт-офис колонки"
```

---

### Task 17: Shift console

**Files:**
- Create: `templates/peco_shift.html`

**Interfaces:**
- Consumes: `/api/peco/pump/state`, `/api/peco/shift/*`, `/api/peco/tanks`, `/api/peco/delivery`.

- [ ] **Step 1: Create the template**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PECO — Смена</title>
<style>
:root{--bg:#f6f8fc;--card:#fff;--line:#dbe3f0;--text:#132038;--muted:#64748b;
      --accent:#1d4ed8;--ok:#16a34a;--warn:#d97706;--danger:#dc2626;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);
     padding:24px;max-width:1100px;margin:0 auto;}
h1{font-size:24px;margin-bottom:4px;}
.sub{color:var(--muted);font-size:14px;margin-bottom:20px;}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;
      margin-bottom:20px;}
h2{font-size:17px;margin-bottom:14px;color:var(--accent);}
table{width:100%;border-collapse:collapse;font-size:14px;}
th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left;}
th{color:var(--muted);font-weight:600;font-size:13px;}
input{border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:14px;width:140px;}
button{border:0;border-radius:9px;padding:10px 18px;font-weight:600;cursor:pointer;
       background:var(--accent);color:#fff;font-size:14px;}
button.ghost{background:transparent;border:1px solid var(--line);color:var(--text);}
button.warn{background:var(--warn);}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;}
label{display:block;font-size:12px;color:var(--muted);margin-bottom:4px;}
.msg{padding:12px 16px;border-radius:10px;margin-top:14px;font-size:14px;}
.msg.err{background:#fee2e2;color:#991b1b;}
.msg.ok{background:#dcfce7;color:#14532d;}
.msg.warn{background:#fef3c7;color:#78350f;}
.vgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;}
.vbox{border:1px solid var(--line);border-radius:12px;padding:14px;}
.vbox .n{font-size:24px;font-weight:700;}
.vbox .l{font-size:12px;color:var(--muted);}
.low{color:var(--danger);font-weight:600;}
</style>
</head>
<body>
<h1>Консоль смены</h1>
<div class="sub" id="sub">загрузка…</div>

<div class="card">
  <h2>Смена</h2>
  <div class="row">
    <div><label>ID сотрудника</label><input id="empId" type="number" value="1"></div>
    <button onclick="openShift()">Открыть смену</button>
  </div>
  <div id="shiftMsg"></div>
</div>

<div class="card">
  <h2>Показания счётчиков</h2>
  <table id="metersTbl">
    <thead><tr><th>Пистолет</th><th>Топливо</th><th>Открытие</th>
      <th>Закрытие</th><th></th></tr></thead>
    <tbody></tbody>
  </table>
</div>

<div class="card">
  <h2>Остатки резервуаров</h2>
  <table id="tanksTbl">
    <thead><tr><th>Резервуар</th><th>Топливо</th><th>Остаток, л</th>
      <th>Ёмкость, л</th><th>Заполнение</th></tr></thead>
    <tbody></tbody>
  </table>
</div>

<div class="card">
  <h2>Закрытие смены</h2>
  <div class="row">
    <div><label>Наличность в кассе, лей</label><input id="cash" type="number" step="0.01"></div>
    <button class="warn" onclick="closeShift()">Закрыть смену со сверкой</button>
  </div>
  <div class="vgrid" id="variances" style="margin-top:16px;"></div>
  <div id="closeMsg"></div>
</div>

<script>
var state = null;

function api(url, body) {
  var opt = body ? {method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify(body)} : {};
  return fetch(url, opt).then(function(r){ return r.json(); });
}

function say(id, text, kind) {
  document.getElementById(id).innerHTML =
    text ? '<div class="msg ' + (kind||'ok') + '">' + text + '</div>' : '';
}

function load() {
  api('/api/peco/pump/state').then(function(r){
    state = r;
    document.getElementById('sub').textContent = r.success
      ? 'Станция ' + r.station_id + ' · смена №' + r.shift_id
      : r.error;
    if (r.success) loadMeters(r.shift_id);
  });
  api('/api/peco/tanks').then(function(r){
    if (!r.success) return;
    var h = '';
    r.items.forEach(function(t){
      h += '<tr><td>' + t.tank_code + '</td><td>' + t.grade_name + '</td>' +
           '<td' + (t.is_low ? ' class="low"' : '') + '>' +
           Number(t.current_l).toFixed(1) + '</td>' +
           '<td>' + Number(t.capacity_l).toFixed(0) + '</td>' +
           '<td>' + Number(t.fill_pct).toFixed(1) + '%</td></tr>';
    });
    document.querySelector('#tanksTbl tbody').innerHTML = h;
  });
}

function loadMeters(shiftId) {
  api('/api/peco/shift/' + shiftId + '/meters').then(function(r){
    if (!r.success) return;
    var h = '';
    r.items.forEach(function(m){
      h += '<tr><td>' + m.nozzle_code + '</td><td>' + m.grade_code + '</td>' +
           '<td>' + Number(m.meter_open).toFixed(3) + '</td>' +
           '<td><input type="number" step="0.001" id="mc' + m.nozzle_id + '" value="' +
           (m.meter_close !== null ? Number(m.meter_close).toFixed(3) : '') + '"></td>' +
           '<td><button class="ghost" onclick="saveMeter(' + m.nozzle_id +
           ')">Сохранить</button></td></tr>';
    });
    document.querySelector('#metersTbl tbody').innerHTML = h;
  });
}

function openShift() {
  api('/api/peco/shift/open', {
    station_id: state ? state.station_id : 1,
    employee_id: Number(document.getElementById('empId').value)
  }).then(function(r){
    say('shiftMsg', r.success ? 'Смена №' + r.shift_id + ' открыта' : r.error,
        r.success ? 'ok' : 'err');
    load();
  });
}

function saveMeter(nozzleId) {
  api('/api/peco/shift/meter', {
    shift_id: state.shift_id, nozzle_id: nozzleId,
    meter_close: Number(document.getElementById('mc' + nozzleId).value)
  }).then(function(r){
    say('shiftMsg', r.success ? 'Показание сохранено' : r.error,
        r.success ? 'ok' : 'err');
  });
}

function closeShift() {
  api('/api/peco/shift/close', {
    shift_id: state.shift_id,
    employee_id: Number(document.getElementById('empId').value),
    cash_declared: Number(document.getElementById('cash').value)
  }).then(function(r){
    if (!r.success) {
      var extra = r.unresolved ? ' (' + r.unresolved + ' шт.)' : '';
      say('closeMsg', r.error + extra, 'err');
      return;
    }
    var v = r.variances;
    document.getElementById('variances').innerHTML =
      box('Литры по счётчику', v.meter_delta, '') +
      box('Расхождение по литрам', v.liter_variance, ' л') +
      box('Расхождение по кассе', v.cash_variance, ' лей') +
      box('Расхождение по резервуару',
          v.tank_variance === null ? '—' : v.tank_variance, ' л');
    say('closeMsg',
        r.status === 'DISPUTED'
          ? 'Смена закрыта с расхождением — требуется подтверждение менеджера'
          : 'Смена закрыта, расхождения в пределах допуска',
        r.status === 'DISPUTED' ? 'warn' : 'ok');
  });
}

function box(label, value, unit) {
  var txt = (value === '—') ? '—' : Number(value).toFixed(3) + unit;
  return '<div class="vbox"><div class="n">' + txt +
         '</div><div class="l">' + label + '</div></div>';
}

load();
</script>
</body>
</html>
```

- [ ] **Step 2: Verify**

Run: `python -c "
s = open('templates/peco_shift.html').read()
assert '/api/peco/shift/close' in s and '/api/peco/shift/meter' in s
assert s.count('<script>') == s.count('</script>')
print('ok')"`

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add templates/peco_shift.html
git commit -m "PECO: консоль смены оператора АЗС"
```

---

### Task 18: Back office

**Files:**
- Create: `templates/peco_admin.html`

**Interfaces:**
- Consumes: `/api/peco/admin/overview`, `/api/peco/admin/price`, `/api/peco/tanks`.

- [ ] **Step 1: Create the template**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PECO — Бэк-офис</title>
<style>
:root{--bg:#f6f8fc;--card:#fff;--line:#dbe3f0;--text:#132038;--muted:#64748b;
      --accent:#1d4ed8;--danger:#dc2626;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);
     padding:24px;max-width:1200px;margin:0 auto;}
h1{font-size:24px;margin-bottom:4px;}
.sub{color:var(--muted);font-size:14px;margin-bottom:20px;}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;
      margin-bottom:20px;}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;}
.kpi .n{font-size:30px;font-weight:700;}
.kpi .l{font-size:13px;color:var(--muted);margin-top:4px;}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;
      margin-bottom:20px;}
h2{font-size:17px;margin-bottom:14px;color:var(--accent);}
table{width:100%;border-collapse:collapse;font-size:14px;}
th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left;}
th{color:var(--muted);font-weight:600;font-size:13px;}
.low{color:var(--danger);font-weight:600;}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;}
label{display:block;font-size:12px;color:var(--muted);margin-bottom:4px;}
input,select{border:1px solid var(--line);border-radius:8px;padding:9px 10px;font-size:14px;}
button{border:0;border-radius:9px;padding:10px 18px;font-weight:600;cursor:pointer;
       background:var(--accent);color:#fff;font-size:14px;}
.msg{padding:12px 16px;border-radius:10px;margin-top:14px;font-size:14px;}
.msg.err{background:#fee2e2;color:#991b1b;}
.msg.ok{background:#dcfce7;color:#14532d;}
</style>
</head>
<body>
<h1>Бэк-офис сети АЗС</h1>
<div class="sub">Станции, цены, остатки резервуаров, расхождения смен</div>

<div class="kpis" id="kpis"></div>

<div class="card">
  <h2>Станции сети</h2>
  <table id="stTbl">
    <thead><tr><th>Код</th><th>Наименование</th><th>Регион</th><th>Адрес</th></tr></thead>
    <tbody></tbody>
  </table>
</div>

<div class="card">
  <h2>Резервуары с низким уровнем</h2>
  <table id="lowTbl">
    <thead><tr><th>Станция</th><th>Резервуар</th><th>Топливо</th>
      <th>Остаток, л</th><th>Порог, л</th></tr></thead>
    <tbody></tbody>
  </table>
</div>

<div class="card">
  <h2>Изменение цены</h2>
  <div class="row">
    <div><label>Станция</label><select id="stSel"></select></div>
    <div><label>Топливо</label>
      <select id="grSel">
        <option value="A92">A92</option><option value="A95">A95</option>
        <option value="A98">A98</option><option value="DIESEL">DIESEL</option>
      </select></div>
    <div><label>Новая цена, лей/л</label><input id="price" type="number" step="0.01"></div>
    <button onclick="setPrice()">Применить</button>
  </div>
  <div class="sub" style="margin-top:10px;">
    Прежняя цена закрывается, новая вступает в силу немедленно.
    Уже проведённые транзакции сохраняют свою цену.
  </div>
  <div id="priceMsg"></div>
</div>

<script>
function api(url, body) {
  var opt = body ? {method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify(body)} : {};
  return fetch(url, opt).then(function(r){ return r.json(); });
}

function load() {
  api('/api/peco/admin/overview').then(function(r){
    if (!r.success) return;
    document.getElementById('kpis').innerHTML =
      kpi(r.stations.length, 'Станций в сети') +
      kpi(r.low_tanks.length, 'Резервуаров ниже порога');

    var h = '', sel = '';
    r.stations.forEach(function(s){
      h += '<tr><td>' + s.code + '</td><td>' + s.name + '</td><td>' +
           (s.region || '—') + '</td><td>' + (s.address || '—') + '</td></tr>';
      sel += '<option value="' + s.id + '">' + s.code + ' — ' + s.name + '</option>';
    });
    document.querySelector('#stTbl tbody').innerHTML = h;
    document.getElementById('stSel').innerHTML = sel;

    var lh = '';
    r.low_tanks.forEach(function(t){
      lh += '<tr><td>' + t.station_name + '</td><td>' + t.tank_code + '</td><td>' +
            t.grade_name + '</td><td class="low">' + Number(t.current_l).toFixed(1) +
            '</td><td>' + Number(t.min_alarm_l).toFixed(0) + '</td></tr>';
    });
    document.querySelector('#lowTbl tbody').innerHTML =
      lh || '<tr><td colspan="5">Все резервуары выше порога</td></tr>';
  });
}

function kpi(n, label) {
  return '<div class="kpi"><div class="n">' + n + '</div><div class="l">' +
         label + '</div></div>';
}

function setPrice() {
  api('/api/peco/admin/price', {
    station_id: Number(document.getElementById('stSel').value),
    grade_code: document.getElementById('grSel').value,
    price: Number(document.getElementById('price').value)
  }).then(function(r){
    document.getElementById('priceMsg').innerHTML =
      '<div class="msg ' + (r.success ? 'ok' : 'err') + '">' +
      (r.success ? 'Цена обновлена' : r.error) + '</div>';
  });
}

load();
</script>
</body>
</html>
```

- [ ] **Step 2: Verify**

Run: `python -c "
s = open('templates/peco_admin.html').read()
assert '/api/peco/admin/overview' in s and '/api/peco/admin/price' in s
assert s.count('<script>') == s.count('</script>')
print('ok')"`

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add templates/peco_admin.html
git commit -m "PECO: бэк-офис сети АЗС"
```

---

## Stage H — Documentation

### Task 19: TZ page with entry buttons

Mirrors `docs/Nufarul/TZ.html`: a choice block at the top (read the spec / go to work), then the full text by section.

**Files:**
- Create: `docs/PECO/TZ.html`

**Interfaces:**
- Consumes: routes from Task 15.
- Produces: served at `/UNA.md/orasldev/docs/peco/TZ.html`.

- [ ] **Step 1: Create the page**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Техническое задание — PECO</title>
<style>
:root{--primary:#b45309;--bg:#fffbeb;--card:#fff;--text:#451a03;--muted:#78716c;
      --border:#fcd34d;--accent:#92400e;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);
     line-height:1.6;padding:24px;max-width:920px;margin:0 auto;}
.lead{font-size:17px;margin-bottom:28px;padding:20px 24px;
      background:linear-gradient(135deg,#fef3c7 0%,#fde68a 100%);
      border-radius:16px;border-left:4px solid var(--primary);}
.choice{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:32px;}
@media (max-width:640px){.choice{grid-template-columns:1fr;}}
.choice-card{background:var(--card);border-radius:16px;padding:24px;
             box-shadow:0 4px 16px rgba(0,0,0,.08);border:2px solid var(--border);
             transition:border-color .2s,box-shadow .2s;}
.choice-card:hover{border-color:var(--primary);box-shadow:0 6px 20px rgba(180,83,9,.15);}
.choice-card h2{font-size:18px;margin-bottom:10px;color:var(--primary);}
.choice-card p{font-size:14px;color:var(--muted);margin-bottom:16px;}
.links{display:flex;flex-direction:column;gap:10px;}
.btn{display:inline-block;padding:12px 20px;border-radius:10px;font-weight:600;
     text-decoration:none;text-align:center;transition:opacity .2s,transform .05s;}
.btn:active{transform:scale(.98);}
.btn-primary{background:var(--primary);color:#fff;}
.btn-primary:hover{opacity:.92;}
.btn-ghost{background:var(--bg);color:var(--accent);border:1px solid var(--border);}
.btn-ghost:hover{background:#fef3c7;}
.btn-block{width:100%;}
h1{font-size:28px;margin-bottom:8px;}
h2{font-size:20px;margin-top:28px;margin-bottom:12px;color:var(--primary);
   border-bottom:1px solid var(--border);padding-bottom:6px;}
h3{font-size:16px;margin-top:16px;margin-bottom:8px;}
p{margin-bottom:12px;}
ul,ol{margin:0 0 12px 24px;}
li{margin-bottom:6px;}
.meta{font-size:14px;color:var(--muted);margin-bottom:24px;}
.card{background:var(--card);border-radius:12px;padding:20px;margin-bottom:20px;
      box-shadow:0 2px 8px rgba(0,0,0,.06);}
table{width:100%;border-collapse:collapse;font-size:14px;margin:12px 0;}
th,td{padding:10px 12px;text-align:left;border:1px solid var(--border);}
th{background:var(--bg);font-weight:600;color:var(--muted);}
code{background:#fef3c7;padding:2px 6px;border-radius:4px;font-size:13px;}
pre{background:#451a03;color:#fde68a;padding:16px;border-radius:10px;overflow-x:auto;
    font-size:13px;margin:12px 0;}
pre code{background:none;color:inherit;padding:0;}
.section-read{margin-top:40px;}
.section-label{font-size:12px;text-transform:uppercase;letter-spacing:.05em;
               color:var(--muted);margin-bottom:12px;}
.sub-link{font-size:13px;margin-top:6px;color:var(--muted);}
</style>
</head>
<body>
<h1>PECO — Техническое задание</h1>
<p class="meta">Управление розничной продажей топлива в региональной сети АЗС.
46 станций · 4 вида топлива · 2–3 пересменки в сутки.</p>

<p class="lead">
<strong>На этой странице можно:</strong> читать полный текст технического задания
(требования, модель данных, интерфейсы) <strong>или сразу перейти к работе с
системой</strong> — отпускать топливо на колонке, вести смену на консоли оператора
либо управлять сетью в бэк-офисе.
</p>

<div class="choice">
  <div class="choice-card">
    <h2>📄 Читать ТЗ</h2>
    <p>Описание проекта, архитектурное решение, модель данных и интерфейсы.
       Ниже на странице — полный текст по разделам.</p>
    <div class="links">
      <a href="#intro" class="btn btn-ghost btn-block">1. Общие сведения</a>
      <a href="#arch" class="btn btn-ghost btn-block">2. Учёт по счётчику</a>
      <a href="#data" class="btn btn-ghost btn-block">3. Модель данных</a>
      <a href="#flows" class="btn btn-ghost btn-block">4. Потоки и интерфейсы</a>
      <a href="#tech" class="btn btn-ghost btn-block">5. Техническая реализация</a>
      <a href="#deliverables" class="btn btn-ghost btn-block">6. Состав поставки</a>
    </div>
  </div>
  <div class="choice-card">
    <h2>⛽ Работать с системой</h2>
    <p>Отпуск топлива, ведение смены и управление сетью. Все ссылки ведут
       в рабочие интерфейсы.</p>
    <div class="links">
      <a href="/UNA.md/orasldev/peco-pump" class="btn btn-primary btn-block">
        Фронт-офис — колонка</a>
      <p class="sub-link">Выбор вида топлива, авторизация налива, завершение по счётчику,
         оплата наличными на кассе или по MIA QR. Самообслуживание и отпуск сотрудником.</p>
      <a href="/UNA.md/orasldev/peco-admin" class="btn btn-primary btn-block">
        Бэк-офис — управление сетью</a>
      <p class="sub-link">46 станций, остатки резервуаров, изменение цен,
         отчёты по расхождениям смен.</p>
      <a href="/UNA.md/orasldev/peco-shift" class="btn btn-ghost btn-block">
        Консоль смены оператора</a>
      <p class="sub-link">Открытие смены, снятие показаний счётчиков, приём цистерн,
         закрытие смены со сверкой.</p>
    </div>
  </div>
</div>

<div class="section-read"><p class="section-label">Текст технического задания</p></div>

<div class="card">
<h2 id="intro">1. Общие сведения</h2>
<p><strong>Предмет:</strong> система управления розничной продажей топлива
в региональной сети АЗС.</p>
<table>
<tr><th>Параметр</th><th>Значение</th></tr>
<tr><td>Количество АЗС</td><td>46</td></tr>
<tr><td>Виды топлива</td><td>A92, A95, A98, Дизель</td></tr>
<tr><td>Прокачка на АЗС в сутки</td><td>около 1000 л</td></tr>
<tr><td>Пересменок в сутки</td><td>2–3 по графику</td></tr>
</table>
<p><strong>Режимы отпуска:</strong> самообслуживание клиентом и отпуск сотрудником АЗС.</p>
<p><strong>Оплата:</strong> наличные на кассе, MIA QR-код.</p>
<p><strong>Уровень функциональности:</strong> полный ERP — приём цистерн, складской
учёт по резервуарам, закрытие смены со сверкой, расчёт расхождений, бэк-офис
по всей сети.</p>
</div>

<div class="card">
<h2 id="arch">2. Ключевое решение: учёт по счётчику</h2>
<p>Источником истины является <strong>тотализатор раздаточного пистолета</strong>,
а не сумма транзакций. Каждая транзакция фиксирует показание счётчика на старте
и на финише; при закрытии смены показания сверяются с суммой транзакций
и с фактически собранными деньгами.</p>
<p><strong>Обоснование.</strong> При учёте «по транзакциям» отпуск топлива,
не попавший в систему, не оставляет следов вообще. При учёте по счётчику такой
отпуск автоматически проявляется как расхождение.</p>
<h3>Три независимых расхождения</h3>
<pre><code>meter_delta    = Σ (METER_CLOSE − METER_OPEN)   по каждому пистолету
txn_liters     = Σ литров транзакций в статусе PAID
liter_variance = meter_delta − txn_liters        -- отпущено, но не оплачено

cash_expected  = Σ сумм, где способ оплаты = CASH
cash_variance  = cash_declared − cash_expected   -- недостача/излишек кассы

tank_expected  = tank_open + delivered − meter_delta
tank_variance  = dip_close − tank_expected       -- утечка/уход калибровки</code></pre>
<p>Три показателя соответствуют трём разным типам отказа и намеренно не сводятся
в одно число. <strong>MIA QR исключён из кассовой сверки</strong>: оплата приходит
на счёт, а не в денежный ящик.</p>
</div>

<div class="card">
<h2 id="data">3. Модель данных</h2>
<p>Префикс всех Oracle-объектов — <code>PECO_</code>. Схема нормализована,
generic key-value таблиц и JSON-blob нет.</p>
<h3>Справочники</h3>
<ul>
<li><code>PECO_REF_FUEL_GRADES</code> — A92, A95, A98, DIESEL</li>
<li><code>PECO_REF_PAY_METHODS</code> — CASH, MIA_QR</li>
<li><code>PECO_REF_SHIFT_STATUS</code> — OPEN, CLOSING, CLOSED, DISPUTED</li>
<li><code>PECO_REF_TXN_STATUS</code> — AUTHORIZED, DISPENSING, AWAITING_PAY, PAID, VOIDED</li>
</ul>
<h3>Мастер-данные</h3>
<ul>
<li><code>PECO_STATIONS</code> — 46 станций</li>
<li><code>PECO_TANKS</code> — резервуар на вид топлива на станции</li>
<li><code>PECO_PUMPS</code> — колонки</li>
<li><code>PECO_NOZZLES</code> — пистолеты; <strong>счётчик хранится здесь</strong>,
    а не на колонке</li>
<li><code>PECO_EMPLOYEES</code> — сотрудники, роли ATTENDANT / MANAGER / ADMIN</li>
<li><code>PECO_PRICES</code> — версионные цены с VALID_FROM / VALID_TO</li>
</ul>
<h3>Операционные таблицы</h3>
<ul>
<li><code>PECO_SHIFTS</code> — смены с расхождениями</li>
<li><code>PECO_SHIFT_METERS</code> — показания по каждому пистолету за смену</li>
<li><code>PECO_TXN</code> — продажи топлива</li>
<li><code>PECO_DELIVERIES</code> + <code>PECO_DELIVERY_ITEMS</code> — приход цистерн</li>
<li><code>PECO_TANK_DIPS</code> — ручные замеры уровня</li>
<li><code>PECO_EVENT_LOG</code> — append-only журнал событий</li>
</ul>
<h3>Представления</h3>
<p><code>V_PECO_TANK_LEVELS</code>, <code>V_PECO_SHIFT_SUMMARY</code>,
<code>V_PECO_STATION_DAILY</code>, <code>V_PECO_VARIANCE</code>.</p>
</div>

<div class="card">
<h2 id="flows">4. Потоки и интерфейсы</h2>
<h3>Отпуск топлива</h3>
<pre><code>AUTHORIZED → DISPENSING → AWAITING_PAY → PAID
                  ↓             ↓
               VOIDED        VOIDED</code></pre>
<p>Один конечный автомат обслуживает оба режима. Самообслуживание
предавторизовано по MIA QR и закрывается сразу при возврате пистолета;
отпуск сотрудником остаётся в <code>AWAITING_PAY</code> до закрытия кассиром.</p>
<h3>Пересменка</h3>
<ol>
<li>Сдающий оператор вводит закрывающие показания по каждому пистолету.</li>
<li>Система рассчитывает все три расхождения.</li>
<li>Оператор объявляет наличность в кассе.</li>
<li>При превышении допуска смена переходит в <code>DISPUTED</code>
    и требует PIN менеджера.</li>
<li>Открывающие показания следующей смены копируются из закрывающих
    показаний предыдущей.</li>
</ol>
<p>Пункт 5 исключает незаметный разрыв цепочки показаний.</p>
<h3>Приём цистерны</h3>
<p>Замер до → приём по строкам накладной по каждому резервуару → замер после.
Хранятся и заявленный, и фактически принятый объём — недолив проявляется
немедленно. Остаток резервуара растёт на фактически принятый объём.</p>
<h3>Обработка ошибок</h3>
<p>Налив, потерявший связь, остаётся в статусе <code>DISPENSING</code>
и попадает в закрытие смены как неразобранная транзакция. Смена не закроется,
пока она не будет оплачена либо аннулирована.</p>
<h3>Интерфейсы</h3>
<table>
<tr><th>Маршрут</th><th>Назначение</th></tr>
<tr><td><code>/UNA.md/orasldev/peco-pump</code></td>
    <td>Фронт-офис колонки, touch-first</td></tr>
<tr><td><code>/UNA.md/orasldev/peco-shift</code></td>
    <td>Консоль оператора АЗС</td></tr>
<tr><td><code>/UNA.md/orasldev/peco-admin</code></td>
    <td>Бэк-офис сети</td></tr>
</table>
</div>

<div class="card">
<h2 id="tech">5. Техническая реализация</h2>
<ul>
<li>Python 3.12, Flask, Oracle через <code>oracledb</code> (wallet по <code>WALLET_DIR</code>)</li>
<li>Одна схема Oracle на всю сеть; строки помечаются <code>STATION_ID</code>,
    отдельных БД по станциям нет</li>
<li>Бизнес-логика — чистые функции в <code>models/peco_shift.py</code>
    и <code>models/peco_txn.py</code>, тестируются без базы</li>
<li>Весь SQL изолирован в <code>models/peco_oracle_store.py</code></li>
<li>DDL: <code>sql/100_peco_tables.sql</code> … <code>104_peco_demo_data.sql</code>,
    развёртывание — <code>python deploy_oracle_objects.py</code></li>
</ul>
</div>

<div class="card">
<h2 id="deliverables">6. Состав поставки</h2>
<ol>
<li>Oracle-схема <code>PECO_</code>: 16 таблиц, 4 представления, справочники и демо-данные.</li>
<li>Слой хранения, изолированный от бизнес-логики.</li>
<li>Расчёт трёх расхождений смены с покрытием юнит-тестами.</li>
<li>Конечный автомат отпуска топлива для обоих режимов.</li>
<li>Складской контур: приём цистерн, замеры, остатки резервуаров.</li>
<li>Три рабочих интерфейса под <code>/UNA.md/orasldev/</code>.</li>
<li>Настоящая страница ТЗ с кнопками входа.</li>
</ol>
<h3>Не входит в первую версию</h3>
<ul>
<li>Очередь разбора расхождений с workflow-согласованием.</li>
<li>Прямая интеграция с контроллерами колонок: показания вводятся оператором
    и принимаются через API, протокол конкретного оборудования подключается
    отдельной задачей.</li>
<li>Программа лояльности и топливные карты.</li>
<li>Мобильное приложение клиента.</li>
</ul>
</div>

<div class="card">
<h2>Ссылки</h2>
<ul>
<li><a href="/UNA.md/orasldev/peco-pump">Фронт-офис колонки</a></li>
<li><a href="/UNA.md/orasldev/peco-shift">Консоль смены</a></li>
<li><a href="/UNA.md/orasldev/peco-admin">Бэк-офис</a></li>
<li><a href="/login">Вход в систему</a> · <a href="/UNA.md/orasldev/docs">Документация</a></li>
</ul>
</div>
</body>
</html>
```

- [ ] **Step 2: Verify the entry buttons point at real routes**

Run: `python -c "
import re
s = open('docs/PECO/TZ.html').read()
for r in ('/UNA.md/orasldev/peco-pump', '/UNA.md/orasldev/peco-shift',
          '/UNA.md/orasldev/peco-admin'):
    assert r in s, r
a = open('app.py').read()
for r in ('peco-pump', 'peco-shift', 'peco-admin'):
    assert r in a, r
print('ok')"`

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add docs/PECO/TZ.html
git commit -m "PECO: страница ТЗ с кнопками входа во фронт-офис и бэк-офис"
```

---

### Task 20: Module documentation and README

**Files:**
- Create: `docs/PECO/README.md`
- Modify: `README.md` (add a PECO section)

**Interfaces:**
- Consumes: everything built in Tasks 1–19.
- Produces: no code interface.

- [ ] **Step 1: Create the module documentation**

Create `docs/PECO/README.md`:

```markdown
# PECO — розничная продажа топлива в сети АЗС

46 станций · 4 вида топлива (A92, A95, A98, Дизель) · 2–3 пересменки в сутки.

**ТЗ:** [TZ.html](TZ.html) — открывается по адресу `/UNA.md/orasldev/docs/peco/TZ.html`
**Проектное решение:** `docs/superpowers/specs/2026-08-19-peco-fuel-retail-design.md`

## Ключевое решение

Источник истины — тотализатор раздаточного пистолета, а не сумма транзакций.
Топливо, вышедшее из пистолета без оплаты, проявляется как расхождение
и не может исчезнуть незаметно.

## Oracle-объекты (префикс `PECO_`)

| Группа | Объекты |
|---|---|
| Справочники | `PECO_REF_FUEL_GRADES`, `PECO_REF_PAY_METHODS`, `PECO_REF_SHIFT_STATUS`, `PECO_REF_TXN_STATUS` |
| Мастер-данные | `PECO_STATIONS`, `PECO_TANKS`, `PECO_PUMPS`, `PECO_NOZZLES`, `PECO_EMPLOYEES` |
| Цены | `PECO_PRICES` (версионные, `VALID_FROM`/`VALID_TO`) |
| Операции | `PECO_SHIFTS`, `PECO_SHIFT_METERS`, `PECO_TXN` |
| Склад | `PECO_DELIVERIES`, `PECO_DELIVERY_ITEMS`, `PECO_TANK_DIPS` |
| Журнал | `PECO_EVENT_LOG` (append-only) |
| Представления | `V_PECO_TANK_LEVELS`, `V_PECO_SHIFT_SUMMARY`, `V_PECO_STATION_DAILY`, `V_PECO_VARIANCE` |

Счётчик хранится в `PECO_NOZZLES.METER_TOTAL` — на уровне пистолета, не колонки.
Колонка с несколькими пистолетами и одним счётчиком теряет разбивку по видам топлива.

## UI-маршруты

| Маршрут | Назначение |
|---|---|
| `/UNA.md/orasldev/peco-pump` | Фронт-офис колонки |
| `/UNA.md/orasldev/peco-shift` | Консоль оператора АЗС |
| `/UNA.md/orasldev/peco-admin` | Бэк-офис сети |
| `/UNA.md/orasldev/docs/peco/TZ.html` | Страница ТЗ |

## API

| Метод | Маршрут | Назначение |
|---|---|---|
| GET | `/api/peco/pump/state` | Смена, пистолеты, действующие цены |
| POST | `/api/peco/txn/authorize` | Авторизация налива |
| POST | `/api/peco/txn/start` | Начало налива |
| POST | `/api/peco/txn/finish` | Завершение налива по счётчику |
| POST | `/api/peco/txn/pay` | Оплата (`CASH` / `MIA_QR`) |
| POST | `/api/peco/txn/void` | Аннулирование |
| POST | `/api/peco/shift/open` | Открытие смены |
| GET | `/api/peco/shift/<id>/meters` | Показания счётчиков смены |
| POST | `/api/peco/shift/meter` | Сохранение закрывающего показания |
| POST | `/api/peco/shift/close` | Закрытие смены со сверкой |
| POST | `/api/peco/shift/approve` | Подтверждение расхождения менеджером |
| POST | `/api/peco/delivery` | Приём цистерны |
| GET | `/api/peco/tanks` | Остатки резервуаров станции |
| GET | `/api/peco/admin/overview` | Сводка по сети |
| POST | `/api/peco/admin/price` | Изменение цены |

## Структура кода

| Файл | Ответственность |
|---|---|
| `models/peco_oracle_store.py` | Весь SQL. Бизнес-правил нет. |
| `models/peco_shift.py` | Смена и расчёт расхождений (чистые функции) |
| `models/peco_txn.py` | Конечный автомат отпуска (чистые функции) |
| `models/peco_inventory.py` | Приём цистерн, замеры, остатки |
| `controllers/peco_controller.py` | Маршрутная логика |

## Локальный запуск

```bash
python app.py
# затем открыть http://127.0.0.1:3003/UNA.md/orasldev/docs/peco/TZ.html
```

## Развёртывание Oracle-объектов

`deploy_to_remote.sh` переносит код, но **не** выполняет DDL. Для схемы отдельно:

```bash
python deploy_oracle_objects.py --only peco
```

## Тесты

```bash
python -m pytest tests/test_peco.py -v
```

Oracle полностью замокан — живая база не нужна.

## Чек-лист верификации после релиза

1. Объекты `PECO_*` присутствуют в `USER_OBJECTS`.
2. Открытие смены создаёт строки `PECO_SHIFT_METERS` по всем активным пистолетам.
3. Налив в режиме самообслуживания доходит до `PAID` без участия оператора.
4. Налив сотрудником остаётся в `AWAITING_PAY` до закрытия кассиром.
5. Закрытие смены с расхождением выше допуска переводит смену в `DISPUTED`.
6. Открывающие показания новой смены равны закрывающим показаниям предыдущей.
7. Приём цистерны на несколько резервуаров создаёт одну шапку и несколько строк.
8. `cash_variance` не включает оплаты MIA QR.
9. Смена не закрывается при транзакциях в статусе `DISPENSING`.
10. `/UNA.md/orasldev/docs/peco/TZ.html` открывается, кнопки ведут в интерфейсы.
11. `curl -I https://nufarul.eminescu.md/login` → 200.
```

- [ ] **Step 2: Add a PECO section to the project README**

Append to `README.md`:

```markdown
## PECO — розничная продажа топлива

Управление сетью из 46 АЗС: 4 вида топлива, самообслуживание и отпуск сотрудником,
оплата наличными или по MIA QR, приём цистерн, закрытие смены со сверкой
по трём независимым расхождениям.

Учёт ведётся по тотализатору раздаточного пистолета, а не по сумме транзакций:
топливо, отпущенное без оплаты, проявляется как расхождение.

- Документация модуля: [docs/PECO/README.md](docs/PECO/README.md)
- ТЗ: `/UNA.md/orasldev/docs/peco/TZ.html`
- Интерфейсы: `/UNA.md/orasldev/peco-pump`, `peco-shift`, `peco-admin`
- Oracle-объекты: префикс `PECO_` (`sql/100_peco_tables.sql` … `104_peco_demo_data.sql`)
- Тесты: `python -m pytest tests/test_peco.py -v`
```

- [ ] **Step 3: Verify the full test suite still passes**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 58 passed

- [ ] **Step 4: Commit**

```bash
git add docs/PECO/README.md README.md
git commit -m "PECO: документация модуля и раздел в README"
```

---

## Final verification

After Task 20, confirm the whole module:

- [ ] `python -m pytest tests/test_peco.py -v` → 58 passed
- [ ] `python -c "import ast; ast.parse(open('app.py').read())"` → no error
- [ ] `python deploy_oracle_objects.py --only peco` → all five SQL files applied
- [ ] `python app.py`, then open `/UNA.md/orasldev/docs/peco/TZ.html` and click each of the three entry buttons
- [ ] Open a shift, dispense self-service, confirm it reaches `PAID` without operator action
- [ ] Dispense as attendant, confirm it stops at `AWAITING_PAY`
- [ ] Try to close the shift with an unpaid transaction — must be refused
- [ ] Pay it, close the shift, confirm all three variances appear
