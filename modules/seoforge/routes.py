"""Маршруты модуля SEOForge.

Адреса здесь записаны БЕЗ префикса `/UNA.md/orasldev/seoforge` — его
подставляет ядро при регистрации blueprint'а. Благодаря этому модуль не
может занять чужой адрес, даже если ошибётся в пути.

Вся бизнес-логика — в `controller.py` и в пакетах `PK_SEO_*` контура
`YSEO_*`. Здесь только разбор запроса и код ответа.
"""
from flask import jsonify, redirect, render_template, request, url_for

from controllers.auth_controller import AuthController
from modules.seoforge import blueprint
from modules.seoforge.controller import SeoController

def _reply(reply):
    """(payload, status) от контроллера -> ответ Flask."""
    payload, status = reply
    return jsonify(payload), status


def _guard():
    """Общая проверка входа для JSON-маршрутов модуля."""
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "data": None,
                    "message": "Требуется вход в систему"}), 401


def _json_body():
    return request.get_json(silent=True) or {}


def _int(name):
    value = request.args.get(name)
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


@blueprint.route('')
@blueprint.route('/')
def page():
    """Страница модуля SEOForge."""
    if not AuthController.is_authenticated():
        return redirect(url_for('login'))
    return render_template('seoforge.html')


@blueprint.route('/api/sites', methods=['GET', 'POST'])
def api_sites():
    denied = _guard()
    if denied:
        return denied
    if request.method == 'POST':
        return _reply(SeoController.save_site(_json_body()))
    return _reply(SeoController.sites(
        include_archived=request.args.get('archived') == '1'))


@blueprint.route('/api/sites/<int:cod>/archive', methods=['POST'])
def api_site_archive(cod):
    denied = _guard()
    if denied:
        return denied
    return _reply(SeoController.archive_site(cod))


@blueprint.route('/api/platforms', methods=['GET', 'POST'])
def api_platforms():
    denied = _guard()
    if denied:
        return denied
    if request.method == 'POST':
        return _reply(SeoController.save_platform(_json_body()))
    return _reply(SeoController.platforms(
        include_archived=request.args.get('archived') == '1'))


@blueprint.route('/api/platforms/<int:cod>/archive', methods=['POST'])
def api_platform_archive(cod):
    denied = _guard()
    if denied:
        return denied
    return _reply(SeoController.archive_platform(cod))


@blueprint.route('/api/dict', methods=['GET'])
@blueprint.route('/api/dict/<section>', methods=['GET', 'POST'])
def api_dict(section=None):
    denied = _guard()
    if denied:
        return denied
    if request.method == 'POST':
        return _reply(SeoController.save_dictionary(section, _json_body()))
    return _reply(SeoController.dictionary(section))


@blueprint.route('/api/fx', methods=['GET', 'POST'])
def api_fx():
    denied = _guard()
    if denied:
        return denied
    if request.method == 'POST':
        return _reply(SeoController.save_fx(_json_body()))
    return _reply(SeoController.fx())


@blueprint.route('/api/campaigns', methods=['GET', 'POST'])
def api_campaigns():
    denied = _guard()
    if denied:
        return denied
    if request.method == 'POST':
        return _reply(SeoController.save_campaign(_json_body()))
    return _reply(SeoController.campaigns(
        site_cod=_int('site'),
        include_archived=request.args.get('archived') == '1'))


@blueprint.route('/api/campaigns/<int:cod>/status', methods=['POST'])
def api_campaign_status(cod):
    denied = _guard()
    if denied:
        return denied
    return _reply(SeoController.set_campaign_status(
        cod, _json_body().get('status')))


@blueprint.route('/api/campaigns/<int:cod>/archive', methods=['POST'])
def api_campaign_archive(cod):
    denied = _guard()
    if denied:
        return denied
    return _reply(SeoController.archive_campaign(cod))


@blueprint.route('/api/budget/plan', methods=['POST'])
def api_budget_plan():
    denied = _guard()
    if denied:
        return denied
    return _reply(SeoController.plan_save(_json_body()))


@blueprint.route('/api/budget/planfact', methods=['GET'])
def api_budget_planfact():
    denied = _guard()
    if denied:
        return denied
    return _reply(SeoController.planfact(
        period=request.args.get('period'), site_cod=_int('site')))


@blueprint.route('/api/spend', methods=['GET', 'POST'])
def api_spend():
    denied = _guard()
    if denied:
        return denied
    if request.method == 'POST':
        return _reply(SeoController.add_spend(_json_body()))
    return _reply(SeoController.spend(
        period=request.args.get('period'), site_cod=_int('site')))


@blueprint.route('/api/metrics', methods=['GET', 'POST'])
def api_metrics():
    denied = _guard()
    if denied:
        return denied
    if request.method == 'POST':
        return _reply(SeoController.add_metrics(_json_body()))
    return _reply(SeoController.metrics(
        period=request.args.get('period'), site_cod=_int('site')))


def _upload_text():
    """Текст загруженного файла и его имя.

    Файл приходит либо multipart-загрузкой, либо телом JSON — второй путь
    нужен интерфейсу, который уже прочитал файл в браузере.
    """
    uploaded = request.files.get('file')
    if uploaded is not None:
        raw = uploaded.read()
        for encoding in ('utf-8-sig', 'cp1251'):
            try:
                return raw.decode(encoding), uploaded.filename
            except UnicodeDecodeError:
                continue
        return raw.decode('utf-8', errors='replace'), uploaded.filename
    body = _json_body()
    return body.get('text', ''), body.get('file_name', 'upload.csv')


@blueprint.route('/api/import/<kind>/preview', methods=['POST'])
def api_import_preview(kind):
    denied = _guard()
    if denied:
        return denied
    text, file_name = _upload_text()
    return _reply(SeoController.import_preview(
        (kind or '').upper(), file_name, text))


@blueprint.route('/api/import/<kind>/commit', methods=['POST'])
def api_import_commit(kind):
    denied = _guard()
    if denied:
        return denied
    text, file_name = _upload_text()
    return _reply(SeoController.import_commit(
        (kind or '').upper(), file_name, text))


@blueprint.route('/api/imports', methods=['GET'])
def api_imports():
    denied = _guard()
    if denied:
        return denied
    return _reply(SeoController.imports())


@blueprint.route('/api/roi', methods=['GET'])
def api_roi():
    denied = _guard()
    if denied:
        return denied
    return _reply(SeoController.roi(
        period_from=request.args.get('period_from'),
        period_to=request.args.get('period_to'),
        site_cod=_int('site')))


@blueprint.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    denied = _guard()
    if denied:
        return denied
    if request.method == 'POST':
        return _reply(SeoController.save_settings(_json_body()))
    return _reply(SeoController.settings())


@blueprint.route('/api/events', methods=['GET'])
def api_events():
    denied = _guard()
    if denied:
        return denied
    return _reply(SeoController.events())