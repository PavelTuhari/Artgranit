"""Папки данных по ОС: база, выгрузки, журнал."""
from __future__ import annotations

import os
import platform
import subprocess
import sys


def data_dir() -> str:
    env = os.environ.get("TEXFLOW_HOME")
    if env:
        path = env
    elif sys.platform.startswith("win"):
        path = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "TexFlow")
    elif sys.platform == "darwin":
        path = os.path.expanduser("~/Library/Application Support/TexFlow")
    else:
        path = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "texflow")
    os.makedirs(path, exist_ok=True)
    return path


def db_path() -> str:
    return os.environ.get("TEXFLOW_DB") or os.path.join(data_dir(), "texflow.db")


def documents_dir() -> str:
    for p in (os.path.expanduser("~/Documents"), os.path.expanduser("~")):
        if os.path.isdir(p):
            return p
    return data_dir()


def open_path(path: str) -> None:
    """Открыть файл программой по умолчанию (PDF, Excel, папка)."""
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def system_print(path: str) -> str:
    """Печать файла (PDF) на системный принтер по умолчанию."""
    if sys.platform.startswith("win"):
        os.startfile(path, "print")  # type: ignore[attr-defined]  # noqa: S606
        return "Windows: print"
    r = subprocess.run(["lp", path], capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "lp")
    return r.stdout.strip()


def platform_name() -> str:
    return f"{platform.system()} {platform.release()} · Python {platform.python_version()}"
