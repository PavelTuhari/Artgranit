"""TexFlow — автономная приёмка и каталогизация одежды из мешков (Турция/Китай).

Python + Flask + SQLite. Запуск: ``python run.py`` → http://127.0.0.1:5077
"""
from __future__ import annotations

import os

from flask import Flask, g

from . import db

__version__ = "1.0.0"


def create_app(db_path: str | None = None, testing: bool = False) -> Flask:
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

    @app.context_processor
    def _ctx():
        return {"version": __version__}

    return app
