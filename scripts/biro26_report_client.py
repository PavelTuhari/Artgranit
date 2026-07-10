#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""biro26_report_client — прослойка для десктоп-приложений (una.md/desktop).

RO: Client Python (doar stdlib — merge pe Windows cu Python standard, fara
    pip) care descarca "Cont de plata" si "Comanda cumparatorului" in PDF
    (si datele documentului in JSON) prin API-ul platformei, cu token
    X-API-Key. Are si GUI (tkinter), si mod CLI pentru integrare.
EN: Python layer (stdlib only — runs on stock Windows Python, no pip) that
    downloads the invoice/order PDFs (and the document JSON) through the
    platform API using an X-API-Key token. Ships both a tkinter GUI and a
    CLI mode for integration into desktop apps.

CLI:
    python biro26_report_client.py 174                      # оба PDF
    python biro26_report_client.py 174 --kind invoice       # только счёт
    python biro26_report_client.py 174 --json               # данные JSON
    python biro26_report_client.py 174 --out C:/docs --open # скачать и открыть
    python biro26_report_client.py --gui                    # окно GUI

Конфигурация (приоритет: аргументы > переменные окружения > ini):
    --server / BIRO26_SERVER / ini   (напр. https://nufarul.eminescu.md)
    --token  / BIRO26_API_TOKEN / ini
    ini-файл: ~/.biro26_client.ini (создаётся кнопкой «Сохранить» в GUI)

Использование из своего кода (как библиотека):
    from biro26_report_client import Biro26Api
    api = Biro26Api("https://nufarul.eminescu.md", "TOKEN")
    pdf_bytes = api.report(174, "invoice")       # bytes PDF
    info      = api.doc(174)                     # dict документа
    path      = api.save(174, "order", "C:/docs")  # скачать в файл
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

INI_PATH = os.path.join(os.path.expanduser("~"), ".biro26_client.ini")
KINDS = ("invoice", "order")
FILE_NAMES = {"invoice": "Cont_de_plata", "order": "Comanda"}


class Biro26Api:
    """Тонкий клиент API платформы (X-API-Key)."""

    def __init__(self, server: str, token: str, timeout: int = 120):
        self.server = (server or "").rstrip("/")
        self.token = token or ""
        self.timeout = timeout

    def _get(self, path: str) -> bytes:
        req = urllib.request.Request(self.server + path,
                                     headers={"X-API-Key": self.token})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            raise RuntimeError(f"HTTP {e.code}: {body}") from None

    def report(self, cod: int, kind: str) -> bytes:
        """PDF документа (kind: invoice | order)."""
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        data = self._get(f"/api/biro26/shop/report/{kind}/{int(cod)}")
        if not data.startswith(b"%PDF"):
            raise RuntimeError("not a PDF: " + data[:200].decode("utf-8", "replace"))
        return data

    def doc(self, cod: int) -> dict:
        """Данные документа (номер, клиент, строки, суммы) как dict."""
        b = json.loads(self._get(f"/api/biro26/doc/{int(cod)}"))
        if not b.get("success"):
            raise RuntimeError(b.get("error") or "unknown error")
        return b["data"]

    def save(self, cod: int, kind: str, out_dir: str = ".") -> str:
        """Скачать PDF в файл; возвращает путь."""
        pdf = self.report(cod, kind)
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{FILE_NAMES[kind]}_{int(cod)}.pdf")
        with open(path, "wb") as f:
            f.write(pdf)
        return path


# ── конфигурация ────────────────────────────────────────────────────

def load_ini() -> dict:
    cp = configparser.ConfigParser()
    if os.path.exists(INI_PATH):
        cp.read(INI_PATH, encoding="utf-8")
    return dict(cp["biro26"]) if cp.has_section("biro26") else {}


def save_ini(server: str, token: str) -> None:
    cp = configparser.ConfigParser()
    cp["biro26"] = {"server": server, "token": token}
    with open(INI_PATH, "w", encoding="utf-8") as f:
        cp.write(f)
    try:
        os.chmod(INI_PATH, 0o600)
    except OSError:
        pass


def resolve_conf(args) -> tuple:
    ini = load_ini()
    server = (args.server or os.environ.get("BIRO26_SERVER")
              or ini.get("server") or "https://nufarul.eminescu.md")
    token = (args.token or os.environ.get("BIRO26_API_TOKEN")
             or ini.get("token") or "")
    return server, token


def open_file(path: str) -> None:
    """Открыть PDF системным просмотрщиком (Windows/macOS/Linux)."""
    if sys.platform.startswith("win"):
        os.startfile(path)                       # noqa — Windows only
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ── GUI (tkinter, в стандартной поставке Python на Windows) ─────────

def run_gui(server: str, token: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        print("ERROR: tkinter недоступен в этой сборке Python.\n"
              "  Windows: установите Python с python.org (tkinter входит в комплект).\n"
              "  macOS (homebrew): brew install python-tk\n"
              "  Либо используйте CLI-режим: biro26_report_client.py <COD> --token ...",
              file=sys.stderr)
        sys.exit(2)

    root = tk.Tk()
    root.title("Biro26 / OfficePlus — documente PDF")
    root.geometry("560x360")
    frm = ttk.Frame(root, padding=14)
    frm.pack(fill="both", expand=True)

    def row(r, label):
        ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=3)
        e = ttk.Entry(frm, width=52)
        e.grid(row=r, column=1, columnspan=2, sticky="we", pady=3)
        return e

    e_server = row(0, "Server:"); e_server.insert(0, server)
    e_token = row(1, "API token:"); e_token.config(show="•"); e_token.insert(0, token)
    e_cod = row(2, "COD document:")

    v_inv = tk.BooleanVar(value=True)
    v_ord = tk.BooleanVar(value=True)
    v_open = tk.BooleanVar(value=True)
    ttk.Checkbutton(frm, text="Cont de plată · Счёт", variable=v_inv).grid(row=3, column=1, sticky="w")
    ttk.Checkbutton(frm, text="Comanda · Заказ", variable=v_ord).grid(row=4, column=1, sticky="w")
    ttk.Checkbutton(frm, text="Deschide după descărcare · Открыть после скачивания",
                    variable=v_open).grid(row=5, column=1, sticky="w")

    out = tk.Text(frm, height=7, width=64, state="disabled", font=("Consolas", 9))
    out.grid(row=7, column=0, columnspan=3, pady=8, sticky="we")

    def log(msg):
        out.config(state="normal"); out.insert("end", msg + "\n")
        out.see("end"); out.config(state="disabled"); root.update()

    def do_download():
        try:
            cod = int(e_cod.get().strip())
        except ValueError:
            messagebox.showerror("Biro26", "Introduceți COD numeric · COD документа — число")
            return
        api = Biro26Api(e_server.get().strip(), e_token.get().strip())
        try:
            info = api.doc(cod)
            log(f"Document № {info['number']} · {info['client']['name']} · "
                f"{info['total']:.2f} LEI · {len(info['items'])} poziții")
            for kind, on in (("invoice", v_inv.get()), ("order", v_ord.get())):
                if not on:
                    continue
                path = api.save(cod, kind, os.path.join(os.path.expanduser("~"), "Downloads"))
                log("✔ " + path)
                if v_open.get():
                    open_file(path)
        except Exception as e:
            log("✖ " + str(e))
            messagebox.showerror("Biro26", str(e))

    def do_save_conf():
        save_ini(e_server.get().strip(), e_token.get().strip())
        log("Config salvat în " + INI_PATH)

    ttk.Button(frm, text="⬇ Descarcă · Скачать", command=do_download).grid(row=6, column=1, sticky="w", pady=6)
    ttk.Button(frm, text="💾 Salvează config", command=do_save_conf).grid(row=6, column=2, sticky="e", pady=6)
    frm.columnconfigure(1, weight=1)
    e_cod.focus()
    root.mainloop()


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Biro26/OfficePlus document layer for desktop apps")
    ap.add_argument("cod", nargs="?", type=int, help="COD документа (из создания счёта)")
    ap.add_argument("--kind", choices=["invoice", "order", "both"], default="both")
    ap.add_argument("--json", action="store_true", help="вывести данные документа JSON вместо PDF")
    ap.add_argument("--out", default=".", help="папка для PDF (по умолчанию текущая)")
    ap.add_argument("--open", action="store_true", help="открыть PDF после скачивания")
    ap.add_argument("--server", help="URL сервера (или BIRO26_SERVER / ini)")
    ap.add_argument("--token", help="API token (или BIRO26_API_TOKEN / ini)")
    ap.add_argument("--gui", action="store_true", help="открыть окно GUI")
    args = ap.parse_args()

    server, token = resolve_conf(args)
    if args.gui or args.cod is None:
        run_gui(server, token)
        return 0
    if not token:
        print("ERROR: нет токена (--token / BIRO26_API_TOKEN / ~/.biro26_client.ini)",
              file=sys.stderr)
        return 2

    api = Biro26Api(server, token)
    try:
        if args.json:
            print(json.dumps(api.doc(args.cod), ensure_ascii=False, indent=2))
            return 0
        kinds = KINDS if args.kind == "both" else (args.kind,)
        for kind in kinds:
            path = api.save(args.cod, kind, args.out)
            print(path)
            if args.open:
                open_file(path)
        return 0
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
