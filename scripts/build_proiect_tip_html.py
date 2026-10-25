#!/usr/bin/env python3
"""RO: construieste versiunile HTML ale pachetului «Proiect tip» din Markdown.

Sursa de adevar sint fisierele docs/ProiectTip/*.md — HTML-ul se regenereaza cu:

    python scripts/build_proiect_tip_html.py

Rezultat:
  - docs/ProiectTip/<nume>.html   — pentru hub-ul de documentatie (dupa logare);
  - static/proiect-tip/<nume>.html — copii PUBLICE doar pentru documentele fara
    date interne (index, marketing, instructiunea cumparatorului).
Fiecare pagina e autonoma (CSS inclus, fara scripturi externe), cu navigatie intre
documentele pachetului si stil pentru tiparire.
EN: build standalone HTML for the template-project documentation pack.
"""
import html
import os
import re
import sys

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "ProiectTip")
PUB = os.path.join(ROOT, "static", "proiect-tip")
HUB = "https://nufarul.eminescu.md/UNA.md/orasldev/b26docs/ProiectTip/"

DOCS = [
    ("00_INDEX", "Пакет документов", True),
    ("01_MARKETING", "1. Маркетинг", True),
    ("02_GHID_PROPRIETAR", "2. Собственнику", False),
    ("03_REPLICARE", "3. Тиражирование", False),
    ("04_INSTRUCTIUNI_CUMPARATOR", "4a. Покупателю", True),
    ("05_INSTRUCTIUNI_OPERATOR", "4b. Сотруднику", False),
    ("06_ISTORIA_PROIECTULUI", "6. История", False),
]
PUBLIC = {name for name, _, pub in DOCS if pub}

CSS = """
:root{--b:#194681;--o:#e8632c;--t:#1f2937;--m:#6b7280;--line:#e5e7eb;--bg:#f6f8fb}
*{box-sizing:border-box}
body{margin:0;font:16px/1.6 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--t);background:#fff}
header{background:linear-gradient(135deg,var(--b),#0f325f);color:#fff;padding:14px 20px}
header .w{max-width:1040px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
header .brand{font-weight:800;font-size:18px;margin-right:auto}
header .brand span{color:var(--o)}
header a{color:#fff;text-decoration:none;font-size:14px;padding:5px 10px;border-radius:8px;opacity:.9}
header a.on,header a:hover{background:rgba(255,255,255,.16);opacity:1}
main{max-width:1040px;margin:0 auto;padding:26px 20px 60px}
h1{color:var(--b);font-size:30px;line-height:1.2;margin:.2em 0 .5em}
h2{color:var(--b);font-size:22px;margin:1.8em 0 .6em;padding-bottom:6px;border-bottom:2px solid var(--line)}
h3{font-size:18px;margin:1.4em 0 .5em}
a{color:var(--b)}
table{width:100%;border-collapse:collapse;margin:12px 0 20px;font-size:14.5px;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:#eef3fa;color:var(--b)}
tr:nth-child(even) td{background:#fbfcfe}
code{font:13.5px ui-monospace,Menlo,Consolas,monospace;background:#eef2f7;padding:1px 5px;border-radius:4px}
pre{background:#0f172a;color:#e2e8f0;padding:14px 16px;border-radius:10px;overflow:auto;font-size:13px;line-height:1.45}
pre code{background:none;padding:0;color:inherit}
blockquote{margin:14px 0;padding:12px 16px;background:var(--bg);border-left:4px solid var(--o);border-radius:0 10px 10px 0}
blockquote table{font-size:14px}
hr{border:0;border-top:1px solid var(--line);margin:30px 0}
footer{max-width:1040px;margin:0 auto;padding:18px 20px 40px;color:var(--m);font-size:13px;border-top:1px solid var(--line)}
@media print{header{background:none;color:#000;border-bottom:2px solid #000}header a{display:none}
  header .brand{color:#000}main{padding-top:10px}pre{white-space:pre-wrap}a{color:#000}}
"""


def _title(md_text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", md_text, re.M)
    return m.group(1).strip() if m else fallback


def _links(body: str, public: bool) -> str:
    """RO: legaturile intre documentele pachetului: .md -> .html; in copiile publice,
    documentele interne trimit spre hub (cer logare)."""
    def rep(m):
        name = m.group(1)
        if public and name not in PUBLIC:
            return 'href="%s%s.html"' % (HUB, name)
        return 'href="%s.html"' % name
    return re.sub(r'href="(\d\d_[A-Z_]+)\.md"', rep, body)


def page(name: str, label: str, md_text: str, public: bool) -> str:
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists", "toc"])
    body = _links(body, public)
    nav = []
    for n, lbl, pub in DOCS:
        href = (n + ".html") if (not public or pub) else (HUB + n + ".html")
        nav.append('<a href="%s"%s>%s</a>' % (href, ' class="on"' if n == name else "", html.escape(lbl)))
    title = _title(md_text, label)
    return """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="robots" content="%s">
<style>%s</style>
</head>
<body>
<header><div class="w"><div class="brand">Proiect <span>tip</span> · Artgranit</div>%s</div></header>
<main>
%s
</main>
<footer>Сгенерировано из <code>docs/ProiectTip/%s.md</code> скриптом
<code>scripts/build_proiect_tip_html.py</code>. Правки — только в Markdown.</footer>
</body>
</html>
""" % (html.escape(re.sub(r"[*`]", "", title)), "index,follow" if public else "noindex",
       CSS, "".join(nav), body, name)


def main() -> int:
    os.makedirs(PUB, exist_ok=True)
    made = []
    for name, label, pub in DOCS:
        src = os.path.join(SRC, name + ".md")
        if not os.path.isfile(src):
            print("LIPSA:", src)
            return 1
        md_text = open(src, encoding="utf-8").read()
        with open(os.path.join(SRC, name + ".html"), "w", encoding="utf-8") as fh:
            fh.write(page(name, label, md_text, public=False))
        made.append("docs/ProiectTip/%s.html" % name)
        if pub:
            with open(os.path.join(PUB, name + ".html"), "w", encoding="utf-8") as fh:
                fh.write(page(name, label, md_text, public=True))
            made.append("static/proiect-tip/%s.html" % name)
    idx = open(os.path.join(PUB, "00_INDEX.html"), encoding="utf-8").read()
    with open(os.path.join(PUB, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(idx)
    made.append("static/proiect-tip/index.html")
    print("\n".join(made))
    return 0


if __name__ == "__main__":
    sys.exit(main())
