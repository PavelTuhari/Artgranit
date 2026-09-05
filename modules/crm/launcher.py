"""Scriptul de pornire a Contragenti, generat de CRM pentru calculatorul utilizatorului.

RO: cind API-ul local (127.0.0.1:9393) nu raspunde, pagina ofera un script
care — lansat pe Mac, Windows sau Linux — gaseste instalarea Contragenti
(sau o descarca din GitHub), o porneste si intoarce browserul in CRM.
Trei ambalaje ale ACELUIASI cod Python (doar biblioteca standard):
  .py       universal (python3 start_contragenti.py)
  .command  macOS: `bash ~/Downloads/start_contragenti.command` in Terminal
            (descarcarea din browser nu da drept de executie, iar Gatekeeper
            blocheaza dublu-click-ul — 05.09.2026)
  .bat      Windows: dublu-click; prima linie e batch, restul Python (`-x`)
EN: generates the cross-platform Contragenti starter script.
"""
from __future__ import annotations

KINDS = {"py": "text/x-python", "command": "text/x-shellscript", "bat": "application/x-bat"}

SCRIPT = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""start_contragenti — porneste utilitarul Contragenti pe acest calculator.

Generat de CRM (beta) Artgranit la __GENERATED__. Doar biblioteca standard.
Ce face: 1) daca API-ul local raspunde, doar ridica fereastra; 2) altfel cauta
instalarea Contragenti (Mac / Windows / Linux), iar daca nu exista o descarca
din GitHub (__REPO__) si pregateste mediul Python; 3) porneste utilitarul,
asteapta /health si intoarce browserul in CRM.
"""
import io, os, platform, shutil, subprocess, sys, time, venv, webbrowser, zipfile
from urllib.request import urlopen, Request

PORT = __PORT__
LANG = "__LANG__"
RETURN_URL = "__RETURN_URL__"
REPO = "__REPO__"
BASE = "http://127.0.0.1:%d" % PORT
HOME = os.path.expanduser("~")
OS = platform.system()          # Darwin | Windows | Linux
PIP_PKGS = ["selenium==4.47.0", "openpyxl==3.1.5", "pillow==12.3.0", "pystray==0.19.5"]


def say(msg):
    print("[Contragenti] " + msg, flush=True)


def alive(timeout=2.0):
    try:
        with urlopen(BASE + "/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def raise_window():
    try:
        urlopen(BASE + "/open?q=&lang=" + LANG, timeout=3).read()
    except Exception:
        pass


def candidates():
    """Locurile in care poate fi Contragenti pe acest calculator."""
    c = []
    if OS == "Darwin":
        c += ["/Applications/Contragenti.app", os.path.join(HOME, "Applications", "Contragenti.app"),
              os.path.join(HOME, "Projects.AI", "DATE.gov", "Contragenti")]
    if OS == "Windows":
        for root in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", ""),
                     os.environ.get("ProgramFiles(x86)", ""), os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
            if root:
                c.append(os.path.join(root, "Contragenti", "Contragenti.exe"))
    c += [os.path.join(HOME, "Contragenti"), os.path.join(HOME, ".local", "share", "contragenti"),
          "/opt/contragenti", os.path.dirname(os.path.abspath(__file__))]
    return c


def find_install():
    """-> ('app', path) | ('exe', path) | ('src', dir) | None"""
    for p in candidates():
        if p.endswith(".app") and os.path.isdir(p):
            return ("app", p)
        if p.lower().endswith(".exe") and os.path.isfile(p):
            return ("exe", p)
        if os.path.isfile(os.path.join(p, "company_search.py")):
            return ("src", p)
    return None


def download_source():
    dest = os.path.join(HOME, "Contragenti")
    say("Nu am gasit Contragenti; il descarc din " + REPO + " in " + dest)
    if shutil.which("git"):
        r = subprocess.run(["git", "clone", "--depth", "1", REPO + ".git", dest])
        if r.returncode == 0:
            return dest
    data = urlopen(Request(REPO + "/archive/refs/heads/main.zip", headers={"User-Agent": "crm-starter"}), timeout=120).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        top = z.namelist()[0].split("/")[0]
        z.extractall(HOME)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.rename(os.path.join(HOME, top), dest)
    return dest


def venv_python(d):
    return os.path.join(d, ".venv", "Scripts" if OS == "Windows" else "bin",
                        "python.exe" if OS == "Windows" else "python")


def ensure_env(d):
    py = venv_python(d)
    if not os.path.isfile(py):
        say("Pregatesc mediul Python (.venv) — o singura data, poate dura un minut")
        venv.create(os.path.join(d, ".venv"), with_pip=True)
    chk = subprocess.run([py, "-c", "import selenium, openpyxl, PIL, pystray"], capture_output=True)
    if chk.returncode != 0:
        subprocess.run([py, "-m", "pip", "install", "-q"] + PIP_PKGS, check=False)
    tk = subprocess.run([py, "-c", "import tkinter"], capture_output=True)
    if tk.returncode != 0:
        hint = {"Darwin": "brew install python-tk", "Linux": "sudo apt install python3-tk"}.get(OS, "reinstalati Python cu optiunea tcl/tk")
        say("ATENTIE: Python-ul din .venv nu are Tkinter (fereastra). Remediu: " + hint)
    return py


def launch(kind, path):
    say("Pornesc Contragenti (%s): %s" % (kind, path))
    if kind == "app":
        subprocess.Popen(["open", "-a", path])
        return
    if kind == "exe":
        subprocess.Popen([path], cwd=os.path.dirname(path), creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return
    py = ensure_env(path)
    kw = {"cwd": path, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if OS == "Windows":
        kw["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kw["start_new_session"] = True
    subprocess.Popen([py, "company_search.py", "--lang", LANG], **kw)


def main():
    say("Sistem: %s, port %d" % (OS, PORT))
    if alive():
        say("Contragenti ruleaza deja — ridic fereastra.")
        raise_window()
    else:
        found = find_install()
        if not found:
            found = ("src", download_source())
        launch(*found)
        say("Astept API-ul local pe " + BASE + " …")
        for _ in range(60):
            if alive():
                break
            time.sleep(1)
        if not alive():
            say("Contragenti nu a raspuns in 60 s. Verificati fereastra utilitarului sau jurnalul lui.")
            return 2
        say("Contragenti raspunde.")
    if RETURN_URL:
        say("Revin in CRM: " + RETURN_URL)
        webbrowser.open(RETURN_URL)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:                                   # noqa: BLE001
        say("Eroare: %s" % e)
        code = 1
    if code and OS == "Windows":
        input("Apasati Enter pentru a inchide…")
    sys.exit(code)
'''


def render(kind: str, *, lang: str = "ro", port: int = 9393, return_url: str = "",
           generated: str = "") -> str:
    """RO: codul Python cu valorile paginii, ambalat pentru .py / .command / .bat."""
    if kind not in KINDS:
        raise ValueError("kind necunoscut: %s" % kind)
    body = (SCRIPT.replace("__PORT__", str(int(port)))
            .replace("__LANG__", lang if lang in ("ro", "ru", "en") else "ro")
            .replace("__RETURN_URL__", return_url.replace('"', ""))
            .replace("__REPO__", "https://github.com/PavelTuhari/Contragenti")
            .replace("__GENERATED__", generated))
    if kind == "py":
        return body
    if kind == "command":
        # RO: macOS — dublu-click deschide Terminal; python3 vine cu Xcode CLT / Homebrew
        return ("#!/bin/bash\n# start_contragenti.command — in Terminal: bash ~/Downloads/start_contragenti.command\n"
                "command -v python3 >/dev/null || { echo 'Instalati Python 3: https://www.python.org/downloads/macos/'; read -r; exit 1; }\n"
                "python3 - <<'PYEOF'\n" + body + "\nPYEOF\n")
    # bat: prima linie e batch (ruleaza acelasi fisier cu python -x, care sare peste linia 1)
    return ('@(python -x "%~f0" %* || py -3 -x "%~f0" %*) & goto :eof\r\n'
            + body.replace("\n", "\r\n"))


def file_name(kind: str) -> str:
    return "start_contragenti." + kind
