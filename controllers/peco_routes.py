"""RO: rutele modulului PECO (statie de alimentare: pompa, tura, admin) — scoase
din app.py la imbinarea ramurii feat/peco in main (19.10.2026), ca blueprint
inregistrat cu o singura linie (regula nr. 2). Logica ramine in
controllers/peco_controller.py si models/peco_*.py; aici sint doar rutele,
exact cum erau in app.py al ramurii (comit 2be2222c).
EN: PECO fuel-station routes as a blueprint; one-line registration in app.py."""
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from controllers.auth_controller import AuthController
from controllers.peco_controller import PecoController

peco_bp = Blueprint("peco_station", __name__)


def _login_redirect():
    nxt = (request.full_path or request.path or "").strip()
    if nxt and not nxt.startswith("/login"):
        return redirect(url_for("login", next=nxt))
    return redirect(url_for("login"))


def _peco_station_id():
    """Станция из query-параметра; по умолчанию первая активная."""
    raw = request.args.get('station_id') or request.form.get('station_id')
    if raw:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    res = PecoController.default_station_id()
    return res.get('station_id') if res.get('success') else None


@peco_bp.route('/UNA.md/orasldev/peco-pump')
@peco_bp.route('/UNA.md/orasldev/peco-pump/')
def peco_pump():
    """Фронт-офис колонки: самообслуживание и отпуск сотрудником."""
    if not AuthController.is_authenticated():
        return redirect(url_for('login', next=request.path))
    return render_template('peco_pump.html')


@peco_bp.route('/UNA.md/orasldev/peco-shift')
@peco_bp.route('/UNA.md/orasldev/peco-shift/')
def peco_shift_console():
    """Консоль оператора АЗС: смена, счётчики, приём цистерн, касса."""
    if not AuthController.is_authenticated():
        return redirect(url_for('login', next=request.path))
    return render_template('peco_shift.html')


@peco_bp.route('/UNA.md/orasldev/peco-admin')
@peco_bp.route('/UNA.md/orasldev/peco-admin/')
def peco_admin():
    """Бэк-офис: сеть АЗС, цены, остатки, расхождения."""
    if not AuthController.is_authenticated():
        return redirect(url_for('login', next=request.path))
    return render_template('peco_admin.html')


@peco_bp.route('/UNA.md/orasldev/peco')
@peco_bp.route('/UNA.md/orasldev/peco/')
def peco_index():
    """Главная страница PECO — единая точка доступа со ссылками на все функции."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    p = Path(os.path.dirname(os.path.abspath(__file__))) / 'docs' / 'PECO' / 'index.html'
    if not p.is_file():
        return "<h1>Не найдено</h1><p><a href='/UNA.md/orasldev/docs'>Назад</a></p>", 404
    from flask import send_file
    return send_file(str(p))


@peco_bp.route('/UNA.md/orasldev/docs/peco/TZ.html')
@peco_bp.route('/UNA.md/orasldev/docs/peco/')
def peco_tz():
    """Страница технического задания PECO с кнопками входа в интерфейсы."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    p = Path(os.path.dirname(os.path.abspath(__file__))) / 'docs' / 'PECO' / 'TZ.html'
    if not p.is_file():
        return "<h1>Не найдено</h1><p><a href='/UNA.md/orasldev/docs'>Назад</a></p>", 404
    from flask import send_file
    return send_file(str(p))


# ---------- PECO API ----------

@peco_bp.route('/api/peco/pump/state')
def api_peco_pump_state():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    station_id = _peco_station_id()
    if station_id is None:
        return jsonify({"success": False, "error": "Нет активных станций"})
    return jsonify(PecoController.pump_state(station_id))


@peco_bp.route('/api/peco/txn/authorize', methods=['POST'])
def api_peco_txn_authorize():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.authorize(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/txn/start', methods=['POST'])
def api_peco_txn_start():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.start(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/txn/finish', methods=['POST'])
def api_peco_txn_finish():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.finish(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/txn/pay', methods=['POST'])
def api_peco_txn_pay():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.pay(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/txn/void', methods=['POST'])
def api_peco_txn_void():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.void(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/shift/open', methods=['POST'])
def api_peco_shift_open():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_open(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/shift/<int:shift_id>/meters')
def api_peco_shift_meters(shift_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_meters(shift_id))


@peco_bp.route('/api/peco/shift/meter', methods=['POST'])
def api_peco_shift_meter():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_save_meter(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/shift/close', methods=['POST'])
def api_peco_shift_close():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_close(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/shift/approve', methods=['POST'])
def api_peco_shift_approve():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_approve(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/delivery', methods=['POST'])
def api_peco_delivery():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.delivery_receive(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/tanks')
def api_peco_tanks():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    station_id = _peco_station_id()
    if station_id is None:
        return jsonify({"success": False, "error": "Нет активных станций"})
    return jsonify(PecoController.tank_levels(station_id))


@peco_bp.route('/api/peco/prices')
def api_peco_prices():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    station_id = _peco_station_id()
    if station_id is None:
        return jsonify({"success": False, "error": "Нет активных станций"})
    return jsonify(PecoController.prices(station_id))


@peco_bp.route('/api/peco/admin/overview')
def api_peco_admin_overview():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.admin_overview())


@peco_bp.route('/api/peco/admin/price', methods=['POST'])
def api_peco_admin_price():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.set_price(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/employees')
def api_peco_employees():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    station_id = _peco_station_id() if request.args.get('station_id') else None
    return jsonify(PecoController.employees(station_id))


@peco_bp.route('/api/peco/employee/pin', methods=['POST'])
def api_peco_employee_pin():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.set_pin(request.get_json(silent=True) or {}))


@peco_bp.route('/api/peco/shifts/disputed')
def api_peco_shifts_disputed():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    station_id = _peco_station_id() if request.args.get('station_id') else None
    return jsonify(PecoController.disputed_shifts(station_id))


@peco_bp.route('/api/peco/shift/<int:shift_id>/summary')
def api_peco_shift_summary(shift_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Требуется авторизация"}), 401
    return jsonify(PecoController.shift_summary(shift_id))


