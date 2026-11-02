#!/usr/bin/env python3
"""TexFlow — запуск нативного приложения (по умолчанию) или веб-версии (--web).

Самоустановка: при первом запуске недостающие библиотеки (reportlab, openpyxl, для веб — flask)
ставятся pip'ом в папку данных приложения (без прав администратора и без влияния на систему).
Ярлыки на рабочем столе и в меню делает установщик: install/install.py.

    python texflow_app.py                 # нативное приложение (Tkinter)
    python texflow_app.py --demo          # с демо-поставкой
    python texflow_app.py --web           # веб-версия в браузере
    python texflow_app.py --check         # проверить окружение и выйти
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_PY = (3, 10)
CORE_DEPS = {"reportlab": "reportlab>=4.0", "openpyxl": "openpyxl>=3.1"}
WEB_DEPS = {"flask": "flask>=3.0"}


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def data_dir() -> str:
    sys.path.insert(0, os.path.join(HERE, "desktop"))
    from texflow_desktop.paths import data_dir as dd
    return dd()


def vendor_dir() -> str:
    return os.path.join(data_dir(), f"pylib{sys.version_info[0]}{sys.version_info[1]}")


def ensure_deps(deps: dict, quiet: bool = False) -> list[str]:
    """Доставить недостающие пакеты в папку данных. Возвращает список установленных."""
    if _frozen():
        return []
    vd = vendor_dir()
    if os.path.isdir(vd) and vd not in sys.path:
        sys.path.insert(0, vd)
    missing = []
    for mod, spec in deps.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(spec)
    if not missing:
        return []
    if not quiet:
        print("TexFlow: первая установка библиотек:", ", ".join(missing), "→", vd, flush=True)
    os.makedirs(vd, exist_ok=True)
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location",
           "--upgrade", "--target", vd, *missing]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("TexFlow: не удалось установить библиотеки:\n" + (r.stderr or r.stdout)[-2000:])
    if vd not in sys.path:
        sys.path.insert(0, vd)
    importlib.invalidate_caches()
    return missing


def check_tk() -> str | None:
    try:
        import tkinter  # noqa: F401
        return None
    except ImportError:
        if sys.platform.startswith("linux"):
            return "Tkinter не установлен. Ubuntu/Debian: sudo apt install python3-tk · Fedora: sudo dnf install python3-tkinter"
        if sys.platform == "darwin":
            return "Tkinter не найден. Установите Python с python.org (в него входит Tk) или: brew install python-tk"
        return "Tkinter не найден. Переустановите Python с python.org, отметив «tcl/tk and IDLE»."


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if sys.version_info < MIN_PY:
        print(f"TexFlow: нужен Python {MIN_PY[0]}.{MIN_PY[1]}+ (сейчас {sys.version.split()[0]})")
        return 2
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, "desktop"))
    web = "--web" in argv
    ensure_deps({**CORE_DEPS, **(WEB_DEPS if web or "--check" in argv else {})})
    if "--check" in argv:
        import platform
        import texflow
        tk_err = check_tk()
        print(f"TexFlow {texflow.__version__} · Python {platform.python_version()} · {platform.system()} "
              f"{platform.release()}")
        print("data:", data_dir())
        print("tkinter:", "ok" if not tk_err else tk_err)
        from importlib import metadata
        for m in ("reportlab", "openpyxl", "flask"):
            try:
                mod = importlib.import_module(m)
            except ImportError:
                print(f"{m}: нет")
                continue
            try:
                v = metadata.version(m)
            except metadata.PackageNotFoundError:          # в сборке PyInstaller нет dist-info
                v = getattr(mod, "Version", None) or getattr(mod, "__version__", "ok")
            print(f"{m}: {v}")
        return 0 if not tk_err else 1
    if web:
        argv.remove("--web")
        from texflow import create_app
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--host", default="127.0.0.1")
        ap.add_argument("--port", type=int, default=5077)
        ap.add_argument("--db", default=None)
        ap.add_argument("--demo", action="store_true")
        a = ap.parse_args(argv)
        from texflow_desktop.paths import db_path
        app = create_app(a.db or db_path())
        if a.demo:
            from texflow.demo import load_demo
            with app.app_context():
                print(load_demo(app.get_db()))
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{a.port}/")
        app.run(host=a.host, port=a.port, debug=False)
        return 0
    err = check_tk()
    if err:
        print("TexFlow:", err)
        return 1
    from texflow_desktop.app import main as desktop_main
    desktop_main(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
