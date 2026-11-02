"""Нативное приложение и установщик.

Установщик и точка входа проверяются везде. Окно приложения — только если есть Tkinter и X-дисплей
(на сервере: xvfb-run python -m pytest tests/test_desktop.py); полный прогон со скриншотами —
tools/desktop_e2e.py.
"""
import importlib.util
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop"))
HAS_TK = importlib.util.find_spec("tkinter") is not None and bool(os.environ.get("DISPLAY"))


def load_installer():
    spec = importlib.util.spec_from_file_location("tf_install", os.path.join(ROOT, "install", "install.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ установщик

def test_installer_layout_launchers_shortcuts_uninstall(tmp_path, monkeypatch):
    inst = load_installer()
    home = tmp_path / "home"
    (home / "Desktop").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("TEXFLOW_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(inst, "IS_WIN", False)
    monkeypatch.setattr(inst, "IS_MAC", False)
    dest = str(tmp_path / "app")
    inst.copy_program(dest)
    for p in ("texflow/db.py", "desktop/texflow_desktop/app.py", "texflow_app.py", "install/texflow.png",
              "texflow/templates/base.html", "texflow/schema.sql"):
        assert os.path.exists(os.path.join(dest, p)), p
    assert not any(n.endswith(".db") for _r, _d, fs in os.walk(dest) for n in fs)
    la = inst.launchers(dest)
    body = open(la["app"]).read()
    assert body.startswith("#!/bin/sh") and "texflow_app.py" in body and os.access(la["app"], os.X_OK)
    assert "--web" in open(la["web"]).read() and "--uninstall" in open(la["uninstall"]).read()
    made = inst.shortcuts_linux(dest, la)
    assert len(made) == 3
    entry = open(made[0], encoding="utf-8").read()
    assert "Name=TexFlow" in entry and "Comment[ro]=Recepția" in entry and la["app"] in entry
    os.makedirs(os.path.join(str(tmp_path / "data")), exist_ok=True)
    inst.uninstall(dest, purge=False)
    assert not os.path.exists(dest) and not any(os.path.exists(m) for m in made)
    assert os.path.isdir(tmp_path / "data")                      # данные сохранены


def test_installer_windows_and_mac_scripts(tmp_path, monkeypatch):
    inst = load_installer()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(inst, "IS_WIN", True)
    monkeypatch.setattr(inst, "IS_MAC", False)
    dest = str(tmp_path / "TexFlow")
    os.makedirs(dest)
    la = inst.launchers(dest)
    raw = open(la["app"], "rb").read()
    assert raw.startswith(b"@echo off\r\n") and b"\r\r\n" not in raw and b"pythonw.exe" in raw
    assert la["app"].endswith("TexFlow.bat") and la["uninstall"].endswith("Uninstall-TexFlow.bat")
    monkeypatch.setattr(inst, "IS_WIN", False)
    monkeypatch.setattr(inst, "IS_MAC", True)
    inst.copy_program(dest)
    made = inst.shortcuts_mac(dest, inst.launchers(dest))
    app = made[0]
    assert app.endswith("TexFlow.app")
    plist = open(os.path.join(app, "Contents", "Info.plist")).read()
    assert "<string>TexFlow</string>" in plist and "texflow.icns" in plist
    exe = os.path.join(app, "Contents", "MacOS", "TexFlow")
    assert os.access(exe, os.X_OK) and "texflow_app.py" in open(exe).read()


def test_setup_scripts_present_and_consistent():
    for name in ("Install-TexFlow-Windows.bat", "Install-TexFlow-macOS.command", "install-texflow-linux.sh"):
        text = open(os.path.join(ROOT, name), encoding="utf-8").read()
        assert "install.py" in text and ("3,10" in text or "3.10" in text), name
    assert os.access(os.path.join(ROOT, "Install-TexFlow-macOS.command"), os.X_OK)
    for icon in ("texflow.png", "texflow.ico", "texflow.icns"):
        assert os.path.getsize(os.path.join(ROOT, "install", icon)) > 1000


def test_app_entry_check_runs():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "texflow_app.py"), "--check"], capture_output=True,
                       text=True, timeout=300, env={**os.environ, "TEXFLOW_HOME": os.environ.get("TEXFLOW_HOME", "")
                                                    or os.path.join(ROOT, "instance", "check-home")})
    assert "TexFlow 1.2" in r.stdout and "reportlab:" in r.stdout and "openpyxl:" in r.stdout


def test_desktop_paths_per_os(monkeypatch, tmp_path):
    from texflow_desktop import paths
    monkeypatch.delenv("TEXFLOW_HOME", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "linux")
    assert paths.data_dir() == os.path.join(str(tmp_path), "texflow")
    monkeypatch.setenv("TEXFLOW_HOME", str(tmp_path / "x"))
    assert paths.db_path().endswith(os.path.join("x", "texflow.db"))


# ------------------------------------------------------------------ окно (нужен Tk + дисплей)

@pytest.mark.skipif(not HAS_TK, reason="нет Tkinter или X-дисплея (xvfb-run python -m pytest tests/test_desktop.py)")
def test_desktop_window_core_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXFLOW_HOME", str(tmp_path))
    from texflow_desktop import app as app_mod, widgets, tab_sort
    for m in (widgets, tab_sort):
        monkeypatch.setattr(m, "error", lambda *a, **k: None)
    app = app_mod.App(str(tmp_path / "t.db"), "en")
    try:
        assert app.nb.tab(app.nb.tabs()[0], "text") == "Shipments"
        app.load_demo()
        app.show("sort")
        t = app.tabs["sort"]
        t.open_product(1)
        t.set_qty("800", "M", 3)
        assert t.save() == 3
        app.show("editor")
        ed = app.tabs["editor"]
        n = len(ed.tpl.elements)
        ed.add("line")
        ed.save()
        from texflow import label_templates as LT
        assert len(LT.load(app.con, ed.tpl.id).elements) == n + 1
        app.set_language("ro")
        assert app.nb.tab(app.nb.tabs()[0], "text") == "Livrări"
    finally:
        app.destroy()


@pytest.mark.skipif(not HAS_TK, reason="нет Tkinter или дисплея")
def test_desktop_sample_db_all_tabs(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXFLOW_HOME", str(tmp_path))
    from texflow_desktop import app as app_mod, widgets
    monkeypatch.setattr(widgets, "error", lambda *a, **k: None)
    app = app_mod.App(str(tmp_path / "work.db"), "ro")
    errors = []
    app.report_callback_exception = lambda *a: errors.append(str(a[1]))
    try:
        app.open_sample()
        assert app.db_file.endswith("texflow_sample.db")
        for key in app_mod.TAB_KEYS:
            app.show(key)
            app.update()
        assert not errors
        app.switch_db(str(tmp_path / "work.db"))
        assert app.con.execute("SELECT COUNT(*) FROM shipments").fetchone()[0] == 0
    finally:
        app.destroy()
