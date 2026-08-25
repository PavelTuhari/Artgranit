"""Маршруты модуля SDA.

Адреса здесь записаны БЕЗ префикса `/UNA.md/orasldev/sda` — его подставляет
ядро при регистрации blueprint'а. Благодаря этому модуль не может занять
чужой адрес, даже если ошибётся в пути.

Соответствие старым адресам из app.py (флет-стиль до переноса):

    /UNA.md/orasldev/sda            -> ''            (хаб документации)
    /UNA.md/orasldev/sda/           -> '/'
    /UNA.md/orasldev/sda/docs       -> '/docs'
    /UNA.md/orasldev/sda/docs/      -> '/docs/'
    /UNA.md/orasldev/sda/docs/<s>   -> '/docs/<slug>'
    /UNA.md/orasldev/sda-console    -> '/console'    (дефисный сосед под
                                                        ядром невозможен —
                                                        становится дочерним
                                                        путём)
    /UNA.md/orasldev/sda/presentation -> '/presentation'
    /api/sda/partic                 -> '/api/partic'
    /api/sda/units                  -> '/api/units'
    /api/sda/units/reclassify       -> '/api/units/reclassify'
    /api/sda/compliance             -> '/api/compliance'
    /api/sda/packs                  -> '/api/packs'
    /api/sda/deposit                -> '/api/deposit'
    /api/sda/dossier                -> '/api/dossier'

Итог: API модуля живёт под /UNA.md/orasldev/sda/api/… — модуль физически
не может занять общий /api/ namespace.

Вся бизнес-логика — в `controller.py`, `store.py` и `rules.py`. Здесь
только разбор запроса и код ответа, как в маршрутах app.py, откуда это
перенесено (см. `.superpowers/sdd/sda-old-routes.py.txt`).
"""
import os

from flask import (Response, jsonify, redirect, render_template, request,
                    session, url_for)

from controllers.auth_controller import AuthController
from models import doc_registry
from modules.sda import blueprint
from modules.sda.docs import docs_md_to_html

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
SDA_DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(MODULE_DIR)),
                            'docs', 'SDA')


def _sda_docs():
    return doc_registry.scan(SDA_DOCS_DIR)


def _sda_doc_by_slug(slug):
    return next((d for d in _sda_docs() if d['slug'] == slug), None)


def _sda_user():
    return session.get('username') or 'anonim'


# ── хаб документации (открыт без входа) ───────────────────────────────

@blueprint.route('')
@blueprint.route('/')
@blueprint.route('/docs')
@blueprint.route('/docs/')
def docs_index():
    """Хаб модуля SDA — открыт без входа."""
    return render_template('sda_docs.html', docs=_sda_docs(), doc=None,
                           page_title='SDA — документация модуля')


@blueprint.route('/docs/<slug>')
def doc(slug):
    """Отдельный документ модуля, отрендеренный из Markdown."""
    found = _sda_doc_by_slug(slug)
    if not found:
        return render_template('sda_docs.html', docs=_sda_docs(), doc=None,
                               page_title='Документ не найден'), 404
    if not found['public'] and not AuthController.is_authenticated():
        return redirect(url_for('login'))

    path = os.path.join(SDA_DOCS_DIR, found['file'])
    if not os.path.isfile(path):
        return render_template('sda_docs.html', docs=_sda_docs(), doc=None,
                               page_title='Документ не найден'), 404
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()

    # Ссылки между файлами переписываем на маршруты модуля.
    for other in _sda_docs():
        source = source.replace(f"]({other['file']})",
                                f"]({url_for('sda.doc', slug=other['slug'])})")
    source = source.replace('](presentation.html)',
                            f"]({url_for('sda.presentation')})")

    return render_template('sda_docs.html', docs=_sda_docs(), doc=found,
                           content=docs_md_to_html(source),
                           page_title=f"{found['title']} — SDA")


@blueprint.route('/console')
def console():
    """Консоль модуля: карта соответствия, сеть, реестр упаковки."""
    if not AuthController.is_authenticated():
        return redirect(url_for('login'))
    return render_template('sda.html', page_title='SDA — consola modulului')


@blueprint.route('/presentation')
def presentation():
    """Досье для клиента — самостоятельная HTML-страница, открыта без входа."""
    path = os.path.join(SDA_DOCS_DIR, 'presentation.html')
    if not os.path.isfile(path):
        return '<h1>Презентация не найдена</h1>', 404
    with open(path, 'r', encoding='utf-8') as f:
        return Response(f.read(), mimetype='text/html; charset=utf-8')


# ── API ────────────────────────────────────────────────────────────────
#
# Реестр упаковки (/packs) и подсказка депозита (/deposit) открыты вместе
# с хабом модуля — это справочные данные, не привязанные к конкретной сети.
# Всё, что описывает СОБСТВЕННУЮ сеть клиента (участники, их точки, карта
# соответствия, досье), требует входа: это данные одного оператора рынка,
# а не публичный справочник.

from modules.sda.controller import SDAController  # noqa: E402


@blueprint.route('/api/partic', methods=['GET'])
def api_partic():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.get_partic(request.args))


@blueprint.route('/api/partic', methods=['POST'])
def api_partic_save():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.save_partic(request.get_json() or {}, _sda_user()))


@blueprint.route('/api/units', methods=['GET'])
def api_units():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.get_units(request.args))


@blueprint.route('/api/units', methods=['POST'])
def api_units_save():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.save_unit(request.get_json() or {}, _sda_user()))


@blueprint.route('/api/units/reclassify', methods=['POST'])
def api_units_reclassify():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.reclassify(_sda_user()))


@blueprint.route('/api/compliance', methods=['GET'])
def api_compliance():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.get_compliance(request.args))


@blueprint.route('/api/packs', methods=['GET'])
def api_packs():
    return jsonify(SDAController.get_packs(request.args))


@blueprint.route('/api/packs', methods=['POST'])
def api_packs_save():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.save_pack(request.get_json() or {}, _sda_user()))


@blueprint.route('/api/deposit', methods=['GET'])
def api_deposit():
    return jsonify(SDAController.get_deposit(request.args))


@blueprint.route('/api/dossier', methods=['GET'])
def api_dossier():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.get_dossier(request.args))


# ── рапорты (PDF / Excel) ─────────────────────────────────────────────
#
# Требуют входа так же, как остальные маршруты сети: документ содержит
# адреса и площади конкретного оператора рынка. Недоступный сервис
# рендера возвращает штатный JSON-отказ модуля, а не битый файл.

from modules.sda.report import SDAReport, XLSX_MIME  # noqa: E402


def _attachment(payload: bytes, mimetype: str, filename: str) -> Response:
    return Response(payload, mimetype=mimetype, headers={
        "Content-Disposition": f'attachment; filename="{filename}"'})


@blueprint.route('/api/report/<kind>.pdf', methods=['GET'])
def api_report_pdf(kind):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    res = SDAReport.render_pdf(kind, request.args.to_dict())
    if not res.get("success"):
        return jsonify(res), 400
    return _attachment(res["pdf"], 'application/pdf',
                       SDAReport.filename(kind, 'pdf'))


@blueprint.route('/api/report/<kind>.xlsx', methods=['GET'])
def api_report_xlsx(kind):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    res = SDAReport.render_xlsx(kind, request.args.to_dict())
    if not res.get("success"):
        return jsonify(res), 400
    return _attachment(res["xlsx"], XLSX_MIME,
                       SDAReport.filename(kind, 'xlsx'))
