#!/usr/bin/env python3
"""Запуск TexFlow локально: python run.py [--host 0.0.0.0] [--port 5077] [--db путь] [--demo]"""
import argparse
import webbrowser

from texflow import create_app

ap = argparse.ArgumentParser(description="TexFlow — приёмка одежды из мешков")
ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 — открыть для планшетов/ПК в локальной сети")
ap.add_argument("--port", type=int, default=5077)
ap.add_argument("--db", default=None, help="файл SQLite (по умолчанию instance/texflow.db)")
ap.add_argument("--demo", action="store_true", help="заполнить демо-поставкой при первом запуске")
ap.add_argument("--no-browser", action="store_true")
a = ap.parse_args()

app = create_app(a.db)
if a.demo:
    from texflow.demo import load_demo
    with app.app_context():
        print(load_demo(app.get_db()))
if not a.no_browser:
    webbrowser.open(f"http://127.0.0.1:{a.port}/")
app.run(host=a.host, port=a.port, debug=False)
