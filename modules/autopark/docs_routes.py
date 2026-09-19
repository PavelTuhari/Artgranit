"""Autopark — собственный хаб документации модуля.

Отдельный файл маршрутов, как и остальные части модуля: документы сети
(дорожная карта, коммерческое предложение, руководства пользователя)
должны открываться по живой ссылке, а не лежать в репозитории.

Реестр документов собирается из самой папки `docs/Autopark`
(`models.doc_registry`): положили файл — он появился в хабе. Флаг
`public` в `docs/Autopark/docs.json` решает, нужен ли вход. По умолчанию
документ виден в списке, но закрыт входом: в папке лежат и технические
описания с путями на сервере.
"""
from __future__ import annotations

import os

from flask import Response, redirect, render_template, url_for

from controllers.auth_controller import AuthController
from models import doc_registry
from modules.autopark import blueprint
from modules.autopark.docs_md import docs_md_to_html

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(MODULE_DIR)),
                        "docs", "Autopark")


def _docs():
    return doc_registry.scan(DOCS_DIR)


def _doc_by_slug(slug):
    return next((d for d in _docs() if d["slug"] == slug), None)


@blueprint.route("/docs")
@blueprint.route("/docs/")
def docs_index():
    """Хаб документации модуля."""
    return render_template("autopark_docs.html", docs=_docs(), doc=None,
                           page_title="Автопарк BEMOL — документация")


@blueprint.route("/docs/<slug>")
def doc(slug):
    found = _doc_by_slug(slug)
    if not found:
        return render_template("autopark_docs.html", docs=_docs(), doc=None,
                               page_title="Документ не найден"), 404
    if not found["public"] and not AuthController.is_authenticated():
        return redirect(url_for("login"))

    path = os.path.join(DOCS_DIR, found["file"])
    if not os.path.isfile(path):
        return render_template("autopark_docs.html", docs=_docs(), doc=None,
                               page_title="Документ не найден"), 404
    with open(path, encoding="utf-8") as fh:
        source = fh.read()

    # Ссылки между файлами переписываем на маршруты модуля: в репозитории
    # они указывают на соседний файл, в браузере должны вести на страницу.
    for other in _docs():
        source = source.replace(f"]({other['file']})",
                                f"]({url_for('autopark.doc', slug=other['slug'])})")
    source = source.replace("](presentation_bemol.html)",
                            f"]({url_for('autopark.presentation')})")

    return render_template("autopark_docs.html", docs=_docs(), doc=found,
                           content=docs_md_to_html(source),
                           page_title=f"{found['title']} — Автопарк BEMOL")


@blueprint.route("/presentation")
def presentation():
    """Презентация для совета директоров — самостоятельная страница."""
    path = os.path.join(DOCS_DIR, "presentation_bemol.html")
    if not os.path.isfile(path):
        return "<h1>Презентация не найдена</h1>", 404
    with open(path, encoding="utf-8") as fh:
        return Response(fh.read(), mimetype="text/html; charset=utf-8")
