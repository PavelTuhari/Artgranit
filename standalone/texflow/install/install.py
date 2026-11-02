#!/usr/bin/env python3
"""Установщик TexFlow для Windows, macOS и Linux (без прав администратора).

    python install/install.py                 # установить и создать ярлыки
    python install/install.py --uninstall     # удалить программу и ярлыки (данные остаются)
    python install/install.py --uninstall --purge   # удалить и данные (база, выгрузки)

Что делает:
  1. проверяет Python 3.10+ и Tkinter (подсказывает, как доставить, если нет);
  2. копирует программу в папку пользователя:
       Windows  %LOCALAPPDATA%\\Programs\\TexFlow
       macOS    ~/Applications/TexFlow (+ TexFlow.app)
       Linux    ~/.local/lib/texflow-app
  3. создаёт изолированное окружение venv и ставит в него reportlab, openpyxl, flask;
  4. создаёт ярлыки «TexFlow» (нативное приложение) и «TexFlow Web» на рабочем столе и в меню;
  5. проверяет запуск: texflow_app.py --check.
Данные (база SQLite) лежат отдельно и при переустановке не трогаются.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import textwrap

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # standalone/texflow
APP = "TexFlow"
COPY = ["texflow", "desktop", "texflow_app.py", "run.py", "requirements.txt", "samples", "install",
        "README.md", "README.ro.md", "README.en.md", "docs"]
DEPS = ["reportlab>=4.0", "openpyxl>=3.1", "flask>=3.0"]
IS_WIN, IS_MAC = sys.platform.startswith("win"), sys.platform == "darwin"


# ------------------------------------------------------------------ пути

def home() -> str:
    return os.path.expanduser("~")


def default_dest() -> str:
    if IS_WIN:
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.join(home(), "AppData", "Local")), "Programs", APP)
    if IS_MAC:
        return os.path.join(home(), "Applications", APP)
    return os.path.join(home(), ".local", "lib", "texflow-app")


def desktop_dir() -> str | None:
    if not IS_WIN and not IS_MAC:
        try:
            out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=5).stdout.strip()
            if out and os.path.isdir(out) and out != home():
                return out
        except (OSError, subprocess.SubprocessError):
            pass
    d = os.path.join(home(), "Desktop")
    return d if os.path.isdir(d) else None


def venv_python(dest: str, windowed: bool = False) -> str:
    if IS_WIN:
        return os.path.join(dest, "venv", "Scripts", "pythonw.exe" if windowed else "python.exe")
    return os.path.join(dest, "venv", "bin", "python")


def log(msg: str):
    print(msg, flush=True)


# ------------------------------------------------------------------ проверки

def check_python() -> list[str]:
    problems = []
    if sys.version_info < (3, 10):
        problems.append(f"Нужен Python 3.10+, сейчас {sys.version.split()[0]}. Скачать: https://www.python.org/downloads/")
    try:
        import tkinter  # noqa: F401
    except ImportError:
        if IS_WIN:
            problems.append("Нет Tkinter: переустановите Python с python.org, отметив «tcl/tk and IDLE».")
        elif IS_MAC:
            problems.append("Нет Tkinter: поставьте Python с python.org (Tk входит) или brew install python-tk.")
        else:
            problems.append("Нет Tkinter: sudo apt install python3-tk python3-venv  (Fedora: sudo dnf install python3-tkinter)")
    try:
        import venv  # noqa: F401
        import ensurepip  # noqa: F401
    except ImportError:
        problems.append("Нет модуля venv/ensurepip: sudo apt install python3-venv")
    return problems


# ------------------------------------------------------------------ установка

def copy_program(dest: str):
    os.makedirs(dest, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "instance", "dist", ".cache", "*.db", "*.db-*",
                                    "node_modules", "build")
    for name in COPY:
        src = os.path.join(SRC, name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(dest, name)
        if os.path.isdir(src):
            if os.path.abspath(src) == os.path.abspath(dst):
                continue
            shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)
        elif os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)


def make_venv(dest: str, offline_wheels: str | None = None):
    vpy = venv_python(dest)
    if not os.path.exists(vpy):
        log("· venv …")
        subprocess.run([sys.executable, "-m", "venv", os.path.join(dest, "venv")], check=True)
    log("· pip install " + " ".join(DEPS))
    cmd = [vpy, "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", *DEPS]
    if offline_wheels:
        cmd[4:4] = ["--no-index", "--find-links", offline_wheels]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("pip: " + (r.stderr or r.stdout)[-3000:])


def write(path: str, text: str, mode: int | None = None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n" if not path.endswith((".bat", ".cmd")) else "\r\n") as f:
        f.write(text)
    if mode:
        os.chmod(path, mode)


def launchers(dest: str) -> dict:
    """Скрипты запуска внутри папки программы (на них ссылаются ярлыки)."""
    out = {}
    if IS_WIN:
        out["app"] = os.path.join(dest, "TexFlow.bat")
        write(out["app"], f'@echo off\nstart "" "{venv_python(dest, True)}" "{os.path.join(dest, "texflow_app.py")}" %*\n')
        out["web"] = os.path.join(dest, "TexFlow-Web.bat")
        write(out["web"], f'@echo off\n"{venv_python(dest)}" "{os.path.join(dest, "texflow_app.py")}" --web %*\n')
        out["uninstall"] = os.path.join(dest, "Uninstall-TexFlow.bat")
        write(out["uninstall"], f'@echo off\n"{venv_python(dest)}" "{os.path.join(dest, "install", "install.py")}" '
                                f'--uninstall --dest "{dest}"\npause\n')
    else:
        out["app"] = os.path.join(dest, "texflow-desktop")
        write(out["app"], f'#!/bin/sh\nexec "{venv_python(dest)}" "{os.path.join(dest, "texflow_app.py")}" "$@"\n', 0o755)
        out["web"] = os.path.join(dest, "texflow-web")
        write(out["web"], f'#!/bin/sh\nexec "{venv_python(dest)}" "{os.path.join(dest, "texflow_app.py")}" --web "$@"\n',
              0o755)
        out["uninstall"] = os.path.join(dest, "uninstall-texflow")
        write(out["uninstall"], f'#!/bin/sh\nexec "{venv_python(dest)}" "{os.path.join(dest, "install", "install.py")}" '
                                f'--uninstall --dest "{dest}" "$@"\n', 0o755)
    return out


# ------------------------------------------------------------------ ярлыки

def shortcuts_windows(dest: str, la: dict) -> list[str]:
    start = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", APP)
    os.makedirs(start, exist_ok=True)
    ico = os.path.join(dest, "install", "texflow.ico")
    pyw = venv_python(dest, True)
    app_py = os.path.join(dest, "texflow_app.py")
    items = [(os.path.join(start, "TexFlow.lnk"), pyw, f'"{app_py}"'),
             (os.path.join(start, "TexFlow Web.lnk"), la["web"], ""),
             (os.path.join(start, "Uninstall TexFlow.lnk"), la["uninstall"], "")]
    desk = desktop_dir()
    if desk:
        items.append((os.path.join(desk, "TexFlow.lnk"), pyw, f'"{app_py}"'))
    made = []
    for lnk, target, args in items:
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{l}');$s.TargetPath='{t}';"
              "$s.Arguments='{a}';$s.WorkingDirectory='{w}';$s.IconLocation='{i}';$s.Save()").format(
            l=lnk.replace("'", "''"), t=target.replace("'", "''"), a=args.replace("'", "''"),
            w=dest.replace("'", "''"), i=ico.replace("'", "''"))
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           capture_output=True, text=True)
        if r.returncode == 0:
            made.append(lnk)
    return made


def shortcuts_mac(dest: str, la: dict) -> list[str]:
    app = os.path.join(os.path.dirname(dest), "TexFlow.app")
    macos = os.path.join(app, "Contents", "MacOS")
    res = os.path.join(app, "Contents", "Resources")
    os.makedirs(macos, exist_ok=True)
    os.makedirs(res, exist_ok=True)
    write(os.path.join(macos, "TexFlow"), f'#!/bin/sh\nexec "{venv_python(dest)}" "{os.path.join(dest, "texflow_app.py")}"\n',
          0o755)
    shutil.copy2(os.path.join(dest, "install", "texflow.icns"), os.path.join(res, "texflow.icns"))
    write(os.path.join(app, "Contents", "Info.plist"), textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0"><dict>
          <key>CFBundleName</key><string>TexFlow</string>
          <key>CFBundleDisplayName</key><string>TexFlow</string>
          <key>CFBundleIdentifier</key><string>md.texflow.desktop</string>
          <key>CFBundleVersion</key><string>1.2.0</string>
          <key>CFBundleExecutable</key><string>TexFlow</string>
          <key>CFBundleIconFile</key><string>texflow.icns</string>
          <key>CFBundlePackageType</key><string>APPL</string>
          <key>NSHighResolutionCapable</key><true/>
        </dict></plist>
        """))
    made = [app]
    desk = desktop_dir()
    if desk:
        link = os.path.join(desk, "TexFlow.app")
        if not os.path.lexists(link):
            os.symlink(app, link)
        made.append(link)
    return made


def shortcuts_linux(dest: str, la: dict) -> list[str]:
    apps = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(home(), ".local", "share")), "applications")
    icon = os.path.join(dest, "install", "texflow.png")
    made = []
    comments = {"texflow.desktop": ("Приёмка одежды из мешков", "Recepția îmbrăcămintei din saci",
                                    "Intake of clothing from bags"),
                "texflow-web.desktop": ("TexFlow в браузере", "TexFlow în browser", "TexFlow in the browser")}
    for fname, name, exe in (("texflow.desktop", "TexFlow", la["app"]), ("texflow-web.desktop", "TexFlow Web", la["web"])):
        ru, ro, en = comments[fname]
        text = (f"[Desktop Entry]\nType=Application\nName={name}\nComment={en}\nComment[ru]={ru}\nComment[ro]={ro}\n"
                f"Exec=\"{exe}\"\nIcon={icon}\n"
                f"Terminal={'true' if 'web' in fname else 'false'}\nCategories=Office;\n")
        path = os.path.join(apps, fname)
        write(path, text, 0o755)
        made.append(path)
    desk = desktop_dir()
    if desk:
        p = os.path.join(desk, "texflow.desktop")
        shutil.copy2(os.path.join(apps, "texflow.desktop"), p)
        os.chmod(p, 0o755)
        made.append(p)
    return made


def make_shortcuts(dest: str, la: dict) -> list[str]:
    if IS_WIN:
        return shortcuts_windows(dest, la)
    if IS_MAC:
        return shortcuts_mac(dest, la)
    return shortcuts_linux(dest, la)


# ------------------------------------------------------------------ удаление

def shortcut_paths(dest: str) -> list[str]:
    desk = desktop_dir() or ""
    if IS_WIN:
        start = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", APP)
        return [start, os.path.join(desk, "TexFlow.lnk")]
    if IS_MAC:
        return [os.path.join(os.path.dirname(dest), "TexFlow.app"), os.path.join(desk, "TexFlow.app")]
    apps = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(home(), ".local", "share")), "applications")
    return [os.path.join(apps, "texflow.desktop"), os.path.join(apps, "texflow-web.desktop"),
            os.path.join(desk, "texflow.desktop")]


def uninstall(dest: str, purge: bool) -> None:
    for p in shortcut_paths(dest):
        if os.path.islink(p) or os.path.isfile(p):
            os.remove(p)
        elif os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
    if os.path.isdir(dest):
        shutil.rmtree(dest, ignore_errors=True)
    log(f"✓ удалено: {dest}")
    if purge:
        sys.path.insert(0, os.path.join(SRC, "desktop"))
        from texflow_desktop.paths import data_dir
        shutil.rmtree(data_dir(), ignore_errors=True)
        log("✓ данные удалены")
    else:
        log("  данные (база) сохранены — для удаления: --uninstall --purge")


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="TexFlow installer (Windows / macOS / Linux)")
    ap.add_argument("--dest", default=default_dest(), help="папка программы")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--purge", action="store_true", help="при удалении стереть и данные")
    ap.add_argument("--no-shortcuts", action="store_true")
    ap.add_argument("--wheels", default=None, help="папка с .whl для установки без интернета")
    ap.add_argument("--no-launch", action="store_true", help="не запускать после установки")
    a = ap.parse_args(argv)
    dest = os.path.abspath(a.dest)
    if a.uninstall:
        uninstall(dest, a.purge)
        return 0
    log(f"TexFlow — установка в {dest}")
    problems = check_python()
    if problems:
        for p in problems:
            log("✗ " + p)
        return 2
    log("· копирование программы …")
    copy_program(dest)
    make_venv(dest, a.wheels)
    la = launchers(dest)
    made = [] if a.no_shortcuts else make_shortcuts(dest, la)
    for m in made:
        log("· ярлык: " + m)
    r = subprocess.run([venv_python(dest), os.path.join(dest, "texflow_app.py"), "--check"], capture_output=True,
                       text=True)
    log(r.stdout.strip())
    if r.returncode:
        log("✗ проверка не прошла:\n" + r.stderr[-2000:])
        return 1
    log("✓ TexFlow установлен. Запуск: ярлык «TexFlow» или " + la["app"])
    if not a.no_launch and os.environ.get("TEXFLOW_NO_LAUNCH") != "1":
        subprocess.Popen([venv_python(dest, True), os.path.join(dest, "texflow_app.py")], cwd=dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
