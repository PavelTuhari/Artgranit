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
