#!/usr/bin/env python3
"""TexFlow — запуск нативного приложения (по умолчанию) или веб-версии (--web).

Самоустановка: при первом запуске недостающие библиотеки (reportlab, openpyxl, для веб — flask)
ставятся pip'ом в папку данных приложения (без прав администратора и без влияния на систему).
Ярлыки на рабочем столе и в меню делает установщик: install/install.py.

    python texflow_app.py                 # нативное приложение (Tkinter)
    python texflow_app.py --demo          # с демо-поставкой
    python texflow_app.py --web           # веб-версия в браузере
    python texflow_app.py --check         # проверить окружение и выйти
    python texflow_app.py --verify        # проверить подпись unisim-soft и контрольные суммы своих файлов
    python texflow_app.py --verify-sums SHA256SUMS   # проверить скачанные архивы выпуска
    python texflow_app.py --smoke         # открыть окно, пройти вкладки на 3 языках, закрыть (для CI)

Целостность: в подписанной поставке (архив «-scripts» со сборки GitHub) лежат MANIFEST.sha256 и
MANIFEST.sha256.sig; при каждом запуске программа сверяет свои файлы и подпись unisim-soft.
Изменённые файлы — предупреждение; TEXFLOW_STRICT_INTEGRITY=1 — отказ запускаться.
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


def integrity_status() -> dict:
    from texflow import integrity
    if _frozen():
        return {"status": "binary", "signer": integrity.SIGNER, "files": 0}
    return integrity.check_tree(HERE)


def integrity_line(res: dict) -> str:
    from texflow import integrity
    if res["status"] == "binary":
        return "целостность: собранная программа — проверяйте архив по SHA256SUMS + подписи unisim-soft"
    return integrity.describe(res)


def smoke(argv) -> int:
    """Открыть окно на временной базе, загрузить демо, пройти все вкладки на RU/RO/EN, закрыть."""
    import tempfile
    import time
    os.environ["TEXFLOW_HOME"] = tempfile.mkdtemp(prefix="texflow-smoke-")
    from texflow_desktop import app as app_mod, widgets
    widgets.error = widgets.info = lambda *a, **k: None
    t0 = time.time()
    app = app_mod.App(os.path.join(os.environ["TEXFLOW_HOME"], "smoke.db"), "ru")
    errors = []
    app.report_callback_exception = lambda *a: errors.append(str(a[1]))
    app.load_demo()
    for lang in ("ru", "ro", "en"):
        app.set_language(lang)
        for key in app_mod.TAB_KEYS:
            app.show(key)
            app.update()
    from texflow import store, label_templates as LT
    data, ext, _m = store.render_labels(app.con, store.label_rows(app.con, {1: 2}), "pdf_roll")
    ok = data[:4] == b"%PDF" and not errors and len(LT.list_templates(app.con)) == 3
    app.destroy()
    print(f"SMOKE {'OK' if ok else 'FAIL'} · {len(app_mod.TAB_KEYS)} вкладок × 3 языка · PDF {len(data)} байт · "
          f"{time.time() - t0:.1f} с" + (f" · ошибки: {errors}" if errors else ""))
    return 0 if ok else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if sys.version_info < MIN_PY:
        print(f"TexFlow: нужен Python {MIN_PY[0]}.{MIN_PY[1]}+ (сейчас {sys.version.split()[0]})")
        return 2
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, "desktop"))
    if "--verify-sums" in argv:
        from texflow import integrity
        i = argv.index("--verify-sums")
        path = argv[i + 1] if i + 1 < len(argv) else "SHA256SUMS"
        res = integrity.check_sums_file(path)
        print(f"подпись {integrity.SIGNER}: {res['signature']}")
        for name, st in res["files"].items():
            print(f"  {st:9} {name}")
        return 0 if res["signature"] == "ok" and all(v == "ok" for v in res["files"].values()) else 1
    res = integrity_status()
    if "--verify" in argv:
        print(integrity_line(res))
        return 0 if res["status"] in ("ok", "dev", "binary") else 1
    if res["status"] in ("modified", "bad-signature", "no-key"):
        print("TexFlow ВНИМАНИЕ:", integrity_line(res), file=sys.stderr)
        if os.environ.get("TEXFLOW_STRICT_INTEGRITY") == "1":
            return 3
    os.environ["TEXFLOW_INTEGRITY"] = integrity_line(res)
    web = "--web" in argv
    ensure_deps({**CORE_DEPS, **(WEB_DEPS if web or "--check" in argv else {})})
    if "--check" in argv:
        import platform
        import texflow
        tk_err = check_tk()
        print(f"TexFlow {texflow.__version__} · Python {platform.python_version()} · {platform.system()} "
              f"{platform.release()}")
        print("data:", data_dir())
        print(integrity_line(res))
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
    if "--smoke" in argv:
        return smoke(argv)
    from texflow_desktop.app import main as desktop_main
    desktop_main(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
