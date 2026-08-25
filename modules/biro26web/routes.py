"""Маршруты модуля «Бэк-офис UNA в вебе».

Адреса без префикса `/UNA.md/orasldev/biro26web` — его ставит ядро.
"""
from flask import jsonify, redirect, render_template, request, url_for

from controllers.auth_controller import AuthController
from modules.biro26web import blueprint
from modules.biro26web.controller import Biro26WebController


def _reply(reply):
    payload, status = reply
    return jsonify(payload), status


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "data": None,
                    "message": "Требуется вход в систему"}), 401


@blueprint.route('')
@blueprint.route('/')
def page():
    """Страница модуля."""
    if not AuthController.is_authenticated():
        return redirect(url_for('login'))
    return render_template('biro26web.html')


@blueprint.route('/api/journals', methods=['GET'])
def api_journals():
    denied = _guard()
    if denied:
        return denied
    return _reply(Biro26WebController.journals())


@blueprint.route('/api/journals/<int:journal_id>', methods=['GET'])
def api_journal(journal_id):
    denied = _guard()
    if denied:
        return denied
    return _reply(Biro26WebController.journal(journal_id))


@blueprint.route('/api/journals/<int:journal_id>/documents', methods=['GET'])
def api_journal_documents(journal_id):
    denied = _guard()
    if denied:
        return denied
    return _reply(Biro26WebController.documents(
        journal_id,
        limit=request.args.get('limit', 200),
        date_from=request.args.get('from'),
        date_to=request.args.get('to')))


@blueprint.route('/api/documents/<int:cod>', methods=['GET'])
def api_document(cod):
    denied = _guard()
    if denied:
        return denied
    return _reply(Biro26WebController.document(cod))


@blueprint.route('/api/document-types', methods=['GET'])
def api_document_types():
    denied = _guard()
    if denied:
        return denied
    return _reply(Biro26WebController.document_types())


@blueprint.route('/api/goods/roots', methods=['GET'])
def api_goods_roots():
    denied = _guard()
    if denied:
        return denied
    return _reply(Biro26WebController.goods_roots())


@blueprint.route('/api/goods/groups', methods=['GET'])
def api_goods_groups():
    denied = _guard()
    if denied:
        return denied
    return _reply(Biro26WebController.goods_groups(
        root=request.args.get('root', 1),
        parent=request.args.get('parent')))


@blueprint.route('/api/goods/items', methods=['GET'])
def api_goods_items():
    denied = _guard()
    if denied:
        return denied
    return _reply(Biro26WebController.goods_items(
        group1=request.args.get('group1'),
        group2=request.args.get('group2'),
        search=request.args.get('q'),
        limit=request.args.get('limit', 200)))


@blueprint.route('/api/goods/items/<int:cod>', methods=['GET'])
def api_goods_item(cod):
    denied = _guard()
    if denied:
        return denied
    return _reply(Biro26WebController.goods_item(cod))


@blueprint.route('/api/documents', methods=['POST'])
def api_create_document():
    denied = _guard()
    if denied:
        return denied
    from flask import session
    return _reply(Biro26WebController.create_document(
        request.get_json(silent=True) or {},
        username=session.get('username', 'system')))


@blueprint.route('/api/documents/<int:cod>/post', methods=['POST'])
def api_post_document(cod):
    denied = _guard()
    if denied:
        return denied
    return _reply(Biro26WebController.post_document(cod))
