"""Rutele vizualizatorului de documentatie."""
from __future__ import annotations

import os

from flask import abort, render_template, request

from controllers.auth_controller import AuthController
from models import doc_registry

from modules.b26docs import blueprint

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(ROOT, "docs")
# RO: doar folderele proiectului care au documentatie de citit din portal.
#     Lista albila, nu «orice folder din docs» — vizualizatorul nu trebuie sa
#     poata scoate un fisier de altundeva.
FOLDERS = ("Biro26", "Partner")
EXT = (".md", ".html", ".htm")


def _guard():
    return None if AuthController.is_authenticated() else abort(401)


def _safe(folder: str, name: str):
    """RO: calea ceruta, verificata: folder din lista, extensie permisa si
    fisierul chiar sub docs/<folder> (fara ../)."""
    if folder not in FOLDERS:
        abort(404)
    base = os.path.realpath(os.path.join(DOCS, folder))
    full = os.path.realpath(os.path.join(base, name))
    if not full.startswith(base + os.sep) or not full.lower().endswith(EXT):
        abort(404)
    if not os.path.isfile(full):
        abort(404)
    return full


@blueprint.route("/")
def index():
    """RO: indexul TUTUROR documentelor proiectului, pe foldere."""
    _guard()
    groups = []
    for folder in FOLDERS:
        path = os.path.join(DOCS, folder)
        if not os.path.isdir(path):
            continue
        items = []
        for d in doc_registry.scan(path):
            fn = d.get("file") or d.get("name") or ""
            if not fn.lower().endswith(EXT):
                continue
            items.append({
                "file": fn,
                "title": (d.get("title") or {}).get("ro") if isinstance(
                    d.get("title"), dict) else (d.get("title") or fn),
                "descr": (d.get("descr") or {}).get("ro") if isinstance(
                    d.get("descr"), dict) else (d.get("descr") or ""),
                "size": os.path.getsize(os.path.join(path, fn))
                if os.path.isfile(os.path.join(path, fn)) else 0,
            })
        groups.append({"folder": folder, "items": items})
    return render_template("b26docs_index.html", groups=groups,
                           q=request.args.get("q", ""))


@blueprint.route("/<folder>/<path:name>")
def view(folder, name):
    """RO: un document — markdown randat sau HTML servit ca atare."""
    _guard()
    full = _safe(folder, name)
    raw = open(full, encoding="utf-8", errors="replace").read()
    if full.lower().endswith((".html", ".htm")):
        return raw
    try:
        import markdown
        html = markdown.markdown(
            raw, extensions=["tables", "fenced_code", "toc", "sane_lists"])
    except Exception:                                        # noqa: BLE001
        # RO: fara biblioteca — tot se poate citi, doar fara formatare
        from html import escape
        html = "<pre>" + escape(raw) + "</pre>"
    return render_template("b26docs_view.html", html=html,
                           folder=folder, name=name)
