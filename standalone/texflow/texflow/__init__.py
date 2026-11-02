"""TexFlow — автономная приёмка и каталогизация одежды из мешков (Турция/Китай).

Ядро (db, rules, store, labels, label_templates, exchange, printing, i18n) не зависит от Flask:
его используют и веб-версия (``python run.py``), и нативное приложение (``python texflow_app.py``).
"""
from __future__ import annotations

import os

from . import db

__version__ = "1.2.0"


def create_app(db_path: str | None = None, testing: bool = False):
    from flask import Flask, g          # Flask нужен только веб-версии

    app = Flask(__name__)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app.config.update(
        DB_PATH=db_path or os.environ.get("TEXFLOW_DB", os.path.join(base, "instance", "texflow.db")),
        SECRET_KEY=os.environ.get("TEXFLOW_SECRET", "texflow-local"),
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        TESTING=testing,
    )
    shared = {}

    def get_db():
        if "db" not in g:
            if app.config["DB_PATH"] == ":memory:":       # тесты: одно соединение на приложение
                if "con" not in shared:
                    shared["con"] = db.connect(":memory:")
                    db.init_db(shared["con"])
                g.db = shared["con"]
            else:
                g.db = db.connect(app.config["DB_PATH"])
        return g.db

    @app.teardown_appcontext
    def _close(_exc):
        con = g.pop("db", None)
        if con is not None and app.config["DB_PATH"] != ":memory:":
            con.close()

    app.get_db = get_db
    if app.config["DB_PATH"] != ":memory:":
        con = db.connect(app.config["DB_PATH"])
        db.init_db(con)
        con.close()

    from .routes import bp
    app.register_blueprint(bp)

    from flask import request, session
    from urllib.parse import urlencode

    from . import i18n

    @app.before_request
    def _pick_lang():
        lang = request.args.get("lang")
        if lang in i18n.LANGS:
            session["lang"] = lang
        lang = session.get("lang")
        if lang not in i18n.LANGS:
            r = get_db().execute("SELECT value FROM settings WHERE key = 'ui_lang'").fetchone()
            lang = r[0] if r else "ru"
        i18n.set_lang(lang)

    @app.teardown_request
    def _reset_lang(_exc):
        i18n.set_lang("ru")          # язык не «протекает» в код вне запроса (CLI, демо, тесты)

    def lang_url(code):
        args = {k: v for k, v in request.args.items() if k != "lang"}
        args["lang"] = code
        return request.path + "?" + urlencode(args)

    @app.context_processor
    def _ctx():
        return {"version": __version__, "_": i18n.gettext, "lang": i18n.current_lang(),
                "langs": i18n.LANGS, "lang_names": i18n.LANG_NAMES, "lang_url": lang_url,
                "status_name": i18n.status_name, "gender_name": i18n.gender_name,
                "js_i18n": i18n.js_strings()}

    return app
