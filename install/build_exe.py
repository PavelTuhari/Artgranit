#!/usr/bin/env python3
"""Сборка TexFlow в готовую программу без установленного Python (PyInstaller).

Собирать нужно на той ОС, для которой программа: Windows → TexFlow.exe, macOS → TexFlow.app,
Linux → бинарник. (PyInstaller не умеет собирать под другую ОС.) Для всех трёх сразу —
GitHub Actions: .github/workflows/texflow-desktop.yml (на каждый push).

    python install/build_exe.py              # dist/TexFlow-<версия>-<ос>-<arch>.zip
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = ";" if sys.platform.startswith("win") else ":"


def main() -> int:
    sys.path.insert(0, ROOT)
    import texflow
    ver = texflow.__version__
    osname = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    arch = platform.machine().lower().replace("amd64", "x86_64")
    for mod in ("PyInstaller", "reportlab", "openpyxl", "flask", "tkinter"):
        try:
            __import__(mod)
        except ImportError:
            print(f"нет модуля {mod}: pip install pyinstaller reportlab openpyxl flask (и Tk в Python)")
            return 2
    icon = {"windows": "texflow.ico", "macos": "texflow.icns"}.get(osname, "texflow.png")
    data = [("texflow/templates", "texflow/templates"), ("texflow/static", "texflow/static"),
            ("texflow/schema.sql", "texflow"), ("samples", "samples"), ("install/texflow.png", "install"),
            ("install/texflow.ico", "install"), ("install/texflow.icns", "install")]
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--name", "TexFlow", "--windowed",
            "--icon", os.path.join("install", icon), "--paths", "desktop", "--paths", ".",
            "--collect-submodules", "texflow", "--collect-submodules", "texflow_desktop",
            "--collect-submodules", "reportlab", "--hidden-import", "openpyxl",
            "--distpath", os.path.join("dist", "pyinstaller"), "--workpath", os.path.join("build", "pyinstaller")]
    for src, dst in data:
        args += ["--add-data", f"{src}{SEP}{dst}"]
    args.append("texflow_app.py")
    print(" ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)
    out_dir = os.path.join(ROOT, "dist", "pyinstaller")
    target = "TexFlow.app" if osname == "macos" and os.path.isdir(os.path.join(out_dir, "TexFlow.app")) else "TexFlow"
    zpath = os.path.join(ROOT, "dist", f"TexFlow-{ver}-{osname}-{arch}.zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    if osname == "macos":
        app = os.path.join(out_dir, target)
        ident = os.environ.get("TEXFLOW_CODESIGN_IDENTITY", "-")       # «-» = ad-hoc подпись без сертификата
        subprocess.run(["codesign", "--force", "--deep", "--sign", ident, app], check=True)
        subprocess.run(["codesign", "--verify", "--deep", "--strict", app], check=True)
        # ditto сохраняет символические ссылки и подпись пакета .app
        subprocess.run(["ditto", "-c", "-k", "--keepParent", app, zpath], check=True)
    else:
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            base = os.path.join(out_dir, target)
            for dirpath, dirs, files in os.walk(base):
                for f in files + [d for d in dirs if os.path.islink(os.path.join(dirpath, d))]:
                    full = os.path.join(dirpath, f)
                    arc = os.path.relpath(full, out_dir)
                    if os.path.islink(full):                       # символическая ссылка — как ссылка
                        info = zipfile.ZipInfo(arc)
                        info.create_system = 3
                        info.external_attr = (0o120777 << 16)
                        z.writestr(info, os.readlink(full))
                        continue
                    info = zipfile.ZipInfo.from_file(full, arc)    # сохраняет права (исполняемый файл)
                    with open(full, "rb") as fh:
                        z.writestr(info, fh.read(), zipfile.ZIP_DEFLATED)
    print("✓", zpath, f"{os.path.getsize(zpath) / 1e6:.1f} MB")
    shutil.rmtree(os.path.join(ROOT, "build", "pyinstaller"), ignore_errors=True)
    for leftover in (os.path.join(ROOT, "TexFlow.spec"),):
        if os.path.exists(leftover):
            os.remove(leftover)
    return 0


if __name__ == "__main__":
    sys.exit(main())
