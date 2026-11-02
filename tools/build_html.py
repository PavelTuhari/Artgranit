#!/usr/bin/env python3
"""Сборка HTML-материалов TexFlow в docs/html/.

    python tools/build_html.py            # всё: документация RU/RO/EN, галереи, акт, презентация

Источники:
  README*.md, docs/*.md               → docs/html/<lang>/*.html (Mermaid → встроенный SVG, без интернета)
  docs/html/e2e_results.json          → акт и галереи (пишет tools/e2e.js)
  docs/html/pytest_results.xml        → акт (pytest --junitxml)
Mermaid рендерится через tools/render_mermaid.js, если заданы MERMAID_JS и доступен node;
иначе страница подключает mermaid с CDN (нужен интернет при просмотре).
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import platform
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "html")
LANGS = ("ru", "ro", "en")
LANG_NAMES = {"ru": "Русский", "ro": "Română", "en": "English"}
DOCS = ["README", "DESKTOP", "OPERATOR_GUIDE", "LABELS", "ARCHITECTURE"]
DOC_TITLES = {
    "README": {"ru": "Обзор и установка", "ro": "Prezentare și instalare", "en": "Overview & install"},
    "DESKTOP": {"ru": "Нативное приложение", "ro": "Aplicația nativă", "en": "Native app"},
    "OPERATOR_GUIDE": {"ru": "Инструкция оператора", "ro": "Instrucțiuni operator", "en": "Operator guide"},
    "LABELS": {"ru": "Этикетки и принтеры", "ro": "Etichete și imprimante", "en": "Labels & printers"},
    "ARCHITECTURE": {"ru": "Блок-схемы", "ro": "Scheme bloc", "en": "Flowcharts"},
    "gallery": {"ru": "Галерея экранов", "ro": "Galerie ecrane", "en": "Screen gallery"},
}
UI = {
    "docs": {"ru": "Документация", "ro": "Documentație", "en": "Documentation"},
    "act": {"ru": "Акт тестирования", "ro": "Act de testare", "en": "Test report"},
    "pres": {"ru": "Презентация", "ro": "Prezentare", "en": "Presentation"},
    "home": {"ru": "Все материалы", "ro": "Toate materialele", "en": "All materials"},
    "contents": {"ru": "Содержание", "ro": "Cuprins", "en": "Contents"},
}


def src_path(doc: str, lang: str) -> str:
    suffix = "" if lang == "ru" else f".{lang}"
    return os.path.join(ROOT, f"{doc}{suffix}.md") if doc == "README" else \
        os.path.join(ROOT, "docs", f"{doc}{suffix}.md")


# ------------------------------------------------------------------ Mermaid

def render_mermaid(sources: list[str]) -> list[str | None]:
    js = os.environ.get("MERMAID_JS")
    if not sources or not js or not os.path.exists(js):
        return [None] * len(sources)
    env = dict(os.environ)
    try:
        r = subprocess.run(["node", os.path.join(ROOT, "tools", "render_mermaid.js")],
                           input=json.dumps(sources).encode(), capture_output=True, env=env, timeout=180)
        return json.loads(r.stdout.decode()) if r.returncode == 0 else [None] * len(sources)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return [None] * len(sources)


def mermaid_block(svg: str | None, src: str) -> str:
    if svg:
        return f'<figure class="diagram">{svg}</figure>'
    return f'<pre class="mermaid">{html.escape(src)}</pre>'


# ------------------------------------------------------------------ оболочка страницы

CSS = """
:root{--ink:#111;--mut:#666;--line:#e3e3df;--bg:#f7f7f5;--card:#fff;--ok:#1e7a3c;--bad:#b3202a;--acc:#111}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;font:15px/1.6 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
a{color:#1f4fa0}header.top{background:#111;color:#fff;padding:12px 24px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
header.top .logo{font-weight:800;letter-spacing:.18em}header.top a{color:#ddd;text-decoration:none;font-size:13px;text-transform:uppercase;letter-spacing:.06em}
header.top a:hover,header.top a.on{color:#fff}header.top .langs{margin-left:auto;display:flex;gap:3px}
header.top .langs a{border:1px solid #555;padding:2px 8px;font-size:11px}header.top .langs a.on{background:#fff;color:#111}
.wrap{display:grid;grid-template-columns:260px 1fr;gap:28px;max-width:1320px;margin:0 auto;padding:24px}
nav.side{position:sticky;top:12px;align-self:start;font-size:13px;background:var(--card);border:1px solid var(--line);padding:14px;max-height:calc(100vh - 24px);overflow:auto}
nav.side b{display:block;text-transform:uppercase;font-size:11px;letter-spacing:.08em;color:var(--mut);margin:10px 0 4px}
nav.side a{display:block;color:var(--ink);text-decoration:none;padding:2px 0}nav.side a.on{font-weight:700}
nav.side .toc a{padding-left:10px;color:var(--mut);font-size:12px}
main.doc{background:var(--card);border:1px solid var(--line);padding:28px 36px;min-width:0}
main.doc h1{font-size:26px;margin-top:0}main.doc h2{margin-top:34px;border-bottom:1px solid var(--line);padding-bottom:4px}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:#f1f1ee}code{background:#f1f1ee;padding:1px 4px;font-size:13px}pre{background:#111;color:#eee;padding:12px;overflow:auto;font-size:12.5px}
pre code{background:none;padding:0}figure.diagram{margin:16px 0;text-align:center;overflow:auto;border:1px solid var(--line);padding:10px;background:#fff}
figure.diagram,figure.diagram *{line-height:normal}figure.diagram{font-size:16px}
figure.diagram svg{max-width:100%;height:auto}
.shots{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.shots figure{margin:0;background:#fff;border:1px solid var(--line);padding:8px}.shots img{width:100%;display:block;border:1px solid var(--line)}
.shots figcaption{font-size:13px;margin-top:6px}.mut{color:var(--mut)}
.pass{color:var(--ok);font-weight:700}.fail{color:var(--bad);font-weight:700}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:16px 0}
.kpis div{border:1px solid var(--line);padding:12px;background:#fafaf8}.kpis b{display:block;font-size:28px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.tiles section{background:var(--card);border:1px solid var(--line);padding:16px}.tiles h3{margin-top:0}
.thumbs img{width:160px;border:1px solid var(--line);margin:2px}
@media (max-width:900px){.wrap{grid-template-columns:1fr}nav.side{position:static;max-height:none}main.doc{padding:18px}}
@media print{header.top,nav.side{display:none}.wrap{display:block;padding:0}main.doc{border:none;padding:0}a{color:inherit}}
"""


def nav(lang: str, current: str, prefix: str, toc: str = "") -> str:
    items = []
    items.append(f'<b>{UI["docs"][lang]}</b>')
    for d in DOCS + ["gallery"]:
        cls = ' class="on"' if d == current else ""
        items.append(f'<a{cls} href="{prefix}{lang}/{d}.html">{DOC_TITLES[d][lang]}</a>')
        if d == current and toc:
            items.append(f'<div class="toc">{toc}</div>')
    items.append(f'<b>{UI["act"][lang]} · {UI["pres"][lang]}</b>')
    items.append(f'<a href="{prefix}test_act.html">{UI["act"][lang]} (RU)</a>')
    items.append(f'<a href="{prefix}presentation.html">{UI["pres"][lang]} (RU)</a>')
    items.append(f'<a href="{prefix}index.html">{UI["home"][lang]}</a>')
    return '<nav class="side">' + "".join(items) + "</nav>"


def page(title: str, body: str, lang: str = "ru", prefix: str = "", nav_html: str = "",
         lang_links: dict | None = None, extra_head: str = "", needs_mermaid_cdn: bool = False) -> str:
    langs = ""
    if lang_links:
        langs = '<span class="langs">' + "".join(
            f'<a class="{"on" if l == lang else ""}" href="{u}">{l.upper()}</a>' for l, u in lang_links.items()
        ) + "</span>"
    mm = ('<script type="module">try{const m=await import("https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/'
          'mermaid.esm.min.mjs");m.default.initialize({startOnLoad:true});m.default.run();}catch(e){}</script>'
          if needs_mermaid_cdn else "")
    layout = f'<div class="wrap">{nav_html}<main class="doc">{body}</main></div>' if nav_html else \
        f'<div class="wrap" style="grid-template-columns:1fr"><main class="doc">{body}</main></div>'
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · TexFlow</title><link rel="stylesheet" href="{prefix}assets/docs.css">{extra_head}</head>
<body><header class="top"><span class="logo">TEXFLOW</span><a href="{prefix}index.html">{UI["home"][lang]}</a>
<a href="{prefix}test_act.html">{UI["act"][lang]}</a><a href="{prefix}presentation.html">{UI["pres"][lang]}</a>{langs}</header>
{layout}{mm}</body></html>"""


# ------------------------------------------------------------------ Markdown → HTML

FENCE = re.compile(r"```mermaid\n(.*?)```", re.S)


def link_rewriter(src_file: str, out_file: str):
    def fix(m):
        href = m.group(2)
        if re.match(r"^(https?:|mailto:|#)", href):
            return m.group(0)
        target, _, anchor = href.partition("#")
        base = os.path.basename(target)
        mm = re.match(r"^(README|DESKTOP|OPERATOR_GUIDE|LABELS|ARCHITECTURE)(?:\.(ro|en))?\.md$", base)
        if mm:
            new = os.path.relpath(os.path.join(OUT, mm.group(2) or "ru", mm.group(1) + ".html"),
                                  os.path.dirname(out_file))
        else:
            abs_t = os.path.normpath(os.path.join(os.path.dirname(src_file), target))
            new = os.path.relpath(abs_t, os.path.dirname(out_file))
        return f'{m.group(1)}"{new}{"#" + anchor if anchor else ""}"'
    return fix


def convert_md(src_file: str, out_file: str) -> tuple[str, str, str]:
    text = open(src_file, encoding="utf-8").read()
    blocks = FENCE.findall(text)
    text = FENCE.sub(lambda m: f"\n\nMERMAIDBLOCK{FENCE.findall(text).index(m.group(1))}\n\n", text)
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"],
                           extension_configs={"toc": {"toc_depth": "2-2"}})
    body = md.convert(text)
    svgs = render_mermaid(blocks)
    for i, src in enumerate(blocks):
        body = body.replace(f"<p>MERMAIDBLOCK{i}</p>", mermaid_block(svgs[i], src))
    body = re.sub(r'((?:href|src)=)"([^"]+)"', link_rewriter(src_file, out_file), body)
    title = re.search(r"<h1[^>]*>(.*?)</h1>", body)
    toc = "".join(f'<a href="#{t["id"]}">{t["name"]}</a>' for t in md.toc_tokens[0]["children"]) \
        if md.toc_tokens and md.toc_tokens[0].get("children") else ""
    need_cdn = any(s is None for s in svgs)
    return (re.sub("<.*?>", "", title.group(1)) if title else os.path.basename(src_file)), body, toc + \
        ("<!--cdn-->" if need_cdn else "")


# ------------------------------------------------------------------ e2e / pytest

def load_e2e() -> dict:
    p = os.path.join(OUT, "e2e_results.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"meta": {}, "results": []}


def load_json(name: str) -> dict:
    p = os.path.join(OUT, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"meta": {}, "results": []}


def load_pytest() -> list[dict]:
    p = os.path.join(OUT, "pytest_results.xml")
    if not os.path.exists(p):
        return []
    rows = []
    for tc in ET.parse(p).getroot().iter("testcase"):
        status = "PASS"
        msg = ""
        for tag in ("failure", "error"):
            el = tc.find(tag)
            if el is not None:
                status, msg = "FAIL", (el.get("message") or "")[:300]
        if tc.find("skipped") is not None:
            status = "SKIP"
        rows.append({"file": tc.get("classname", "").replace("tests.", ""), "name": tc.get("name"),
                     "time": float(tc.get("time") or 0), "status": status, "msg": msg})
    return rows


SCREEN_NAMES = {
    "home": {"ro": "Pagina principală", "en": "Home"},
    "shipment": {"ro": "Livrare: cheltuieli, listă de colete, saci, verificare",
                 "en": "Shipment: costs, packing list, bags, reconciliation"},
    "sort": {"ro": "Sortarea sacului: scaner, model nou, matrice culoare × mărime",
             "en": "Sorting a bag: scanner, new model, colour × size matrix"},
    "pricing": {"ro": "Formarea prețurilor", "en": "Pricing"},
    "catalog": {"ro": "Catalog", "en": "Catalogue"},
    "product": {"ro": "Fișa modelului", "en": "Model card"},
    "labels": {"ro": "Etichete", "en": "Labels"},
    "settings": {"ro": "Setări", "en": "Settings"},
    "refs": {"ro": "Nomenclatoare", "en": "Reference data"},
    "help": {"ro": "Instrucțiuni cu schema procesului", "en": "Help with the process diagram"},
}


def gallery_items(e2e: dict, lang: str) -> list[tuple[str, str]]:
    items = []
    for r in e2e["results"]:
        for img in r["images"]:
            if "_fail" in img:
                continue
            m = re.match(r"e2e_\d+_(ro|en)_(\w+)\.jpg", img)
            if lang == "ru" and r["lang"] == "ru":
                items.append((img, f'{r["id"]}. {r["title"]}'))
            elif m and m.group(1) == lang:
                items.append((img, SCREEN_NAMES.get(m.group(2), {}).get(lang, m.group(2))))
    if lang != "ru":
        for img, cap in gallery_items(e2e, "ru"):
            if img.startswith("e2e_label"):
                items.append((img, cap))
    return items


DESK_NAMES = {
    "shipments": {"ro": "Livrări", "en": "Shipments"}, "sort": {"ro": "Sortare", "en": "Sort"},
    "pricing": {"ro": "Prețuri", "en": "Prices"}, "catalog": {"ro": "Catalog", "en": "Catalogue"},
    "labels": {"ro": "Etichete", "en": "Labels"}, "editor": {"ro": "Editor de etichete", "en": "Label editor"},
    "exchange": {"ro": "Excel / CSV", "en": "Excel / CSV"}, "settings": {"ro": "Setări", "en": "Settings"},
}


def desktop_gallery(desk: dict, lang: str) -> list[tuple[str, str]]:
    items = []
    for r in desk.get("results", []):
        for img in r["images"]:
            if "_fail" in img:
                continue
            m = re.match(r"desk_\d+_(ro|en)_(\w+)\.jpg", img)
            if lang == "ru" and r["lang"] == "ru":
                items.append((img, f'{r["id"]}. {r["title"]}'))
            elif m and m.group(1) == lang:
                items.append((img, DESK_NAMES.get(m.group(2), {}).get(lang, m.group(2))))
    if lang != "ru":
        items += [(i, c) for i, c in desktop_gallery(desk, "ru") if i.endswith(".png")]
    return items


# ------------------------------------------------------------------ сборка документации

def build_docs(e2e: dict) -> list[str]:
    written = []
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    open(os.path.join(OUT, "assets", "docs.css"), "w", encoding="utf-8").write(CSS)
    for lang in LANGS:
        os.makedirs(os.path.join(OUT, lang), exist_ok=True)
        for doc in DOCS:
            out = os.path.join(OUT, lang, f"{doc}.html")
            title, body, toc = convert_md(src_path(doc, lang), out)
            cdn = toc.endswith("<!--cdn-->")
            links = {l: f"../{l}/{doc}.html" for l in LANGS}
            open(out, "w", encoding="utf-8").write(page(title, body, lang, "../", nav(lang, doc, "../", toc.replace("<!--cdn-->", "")),
                                                        links, needs_mermaid_cdn=cdn))
            written.append(out)
        # галерея экранов
        def figs_of(items):
            return "".join(f'<figure><a href="../img/{i}"><img loading="lazy" src="../img/{i}" alt=""></a>'
                           f'<figcaption>{html.escape(c)}</figcaption></figure>' for i, c in items)
        sec = {"ru": ("Нативное приложение (Windows · macOS · Linux)", "Веб-версия"),
               "ro": ("Aplicația nativă (Windows · macOS · Linux)", "Versiunea web"),
               "en": ("Native app (Windows · macOS · Linux)", "Web version")}[lang]
        figs = (f'<h2>{sec[0]}</h2><div class="shots">{figs_of(desktop_gallery(load_json("desktop_results.json"), lang))}</div>'
                f'<h2>{sec[1]}</h2><div class="shots">{figs_of(gallery_items(e2e, lang))}</div>')
        intro = {"ru": "Скриншоты сделаны автоматически при сквозном тестировании (tools/e2e.js) на чистой базе.",
                 "ro": "Capturile de ecran au fost făcute automat la testarea completă (tools/e2e.js) pe o bază curată.",
                 "en": "Screenshots were taken automatically during end-to-end testing (tools/e2e.js) on a clean database."}
        body = f'<h1>{DOC_TITLES["gallery"][lang]}</h1><p class="mut">{intro[lang]}</p>{figs}'
        out = os.path.join(OUT, lang, "gallery.html")
        open(out, "w", encoding="utf-8").write(page(DOC_TITLES["gallery"][lang], body, lang, "../", nav(lang, "gallery", "../"),
                                                    {l: f"../{l}/gallery.html" for l in LANGS}))
        written.append(out)
    return written


def build_index(e2e: dict, unit: list[dict]) -> str:
    tiles = []
    for lang in LANGS:
        links = "".join(f'<li><a href="{lang}/{d}.html">{DOC_TITLES[d][lang]}</a></li>' for d in DOCS + ["gallery"])
        tiles.append(f'<section><h3>{LANG_NAMES[lang]}</h3><ul>{links}</ul></section>')
    passed_u = sum(r["status"] == "PASS" for r in unit)
    passed_e = sum(r["status"] == "PASS" for r in e2e["results"])
    desk = load_json("desktop_results.json")
    passed_d = sum(r["status"] == "PASS" for r in desk["results"])
    body = f"""<h1>TexFlow — все материалы</h1>
<p>Автономное приложение Python + Flask + SQLite для приёмки одежды из мешков (Турция / Китай), каталога,
цен и этикеток Zebra / TSC / PDF. Интерфейс и документация — RU / RO / EN.</p>
<div class="kpis"><div><b>{passed_u}/{len(unit)}</b>модульных тестов</div><div><b>{passed_e}/{len(e2e["results"])}</b>сквозных проверок в браузере</div>
<div><b>{passed_d}/{len(desk["results"])}</b>сквозных проверок нативного приложения</div><div><b>3</b>языка</div><div><b>{sum(len(r["images"]) for r in e2e["results"])}</b>скриншотов</div></div>
<div class="tiles"><section><h3>Акт и презентация</h3><ul><li><a href="test_act.html">Акт тестирования со скриншотами</a></li>
<li><a href="presentation.html">Презентация</a> (стрелки ← →) · <a href="presentation.pdf">PDF</a></li>
<li><a href="test_act.pdf">Акт тестирования — PDF для печати и подписи</a></li>
<li><a href="ru/ARTICLE.html">Статья «Автоматизация „с коленок“: от мешка до ценника»</a></li></ul>
<p class="mut">Образцы выходных файлов: <a href="sample_label.zpl">ZPL</a> · <a href="sample_label.tspl">TSPL</a> ·
<a href="sample_catalog.csv">CSV каталога</a> · <a href="img/e2e_label_a4.png">лист A4</a> · <a href="img/e2e_label_roll.png">этикетка 58×40</a></p></section>
{''.join(tiles)}</div>
<p class="mut">Материалы собраны командой <code>tools/run_all.sh</code>; HTML открывается без интернета.</p>"""
    out = os.path.join(OUT, "index.html")
    open(out, "w", encoding="utf-8").write(page("Все материалы", body, "ru", ""))
    return out


# ------------------------------------------------------------------ акт тестирования

def git(*args) -> str:
    try:
        return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def versions() -> list[tuple[str, str]]:
    import importlib.metadata as md
    vers = [("ОС", f"{platform.system()} {platform.release()}"),
            ("Python (веб-версия, браузерный прогон, сборка отчёта)", platform.python_version())]
    for pkg in ("flask", "reportlab", "pytest", "markdown"):
        try:
            vers.append((pkg, md.version(pkg)))
        except md.PackageNotFoundError:
            pass
    return vers


DEFECTS = [
    ("Д-1", "Журнал печати хранил сообщение на языке, на котором печатали: на экранах RO/EN в истории оставался русский текст.",
     "T24/T25 (e2e, RO/EN без кириллицы)", "В журнал пишется нейтральная запись «N B → адрес»; регрессионный тест test_print_log_is_language_neutral.",
     "bcdb1af"),
    ("Д-2", "Страница поставки показывала себестоимость 0.00 / 0.00, пока не нажать «Сохранить и пересчитать».",
     "скриншот T09 (сверка)", "Себестоимость пересчитывается при открытии страницы; тест test_shipment_page_shows_landed_cost_without_recalc.",
     "FIX2"),
    ("Д-3", "Схема процесса на странице «Инструкция» рисовалась на чёрном фоне и обрезалась по высоте 340 px.",
     "скриншот T23 (инструкция)", "Отдельный стиль pre.mermaid: белый фон, без ограничения высоты.", "FIX2"),
    ("Д-4", "Русская инструкция не упоминала румынские заголовки упаковочного листа (после перевода на 3 языка).",
     "скриншот T23", "Текст инструкции дополнен.", "FIX2"),
    ("Д-5", "Редактор этикеток: рамка вокруг всей этикетки перехватывала щелчок — текст и штрихкод внутри нельзя "
            "было выделить и перетащить мышью.",
     "D09 (desktop e2e, перетаскивание мышью)", "Рамка выбирается только щелчком по контуру; повторный прогон D09.",
     "GREP:рамка выбирается по контуру"),
    ("Д-6", "Нативное приложение на RO/EN: меню «Файл», вкладка «Редактор этикеток» и ещё 39 строк оставались на русском.",
     "скриншот сборки PyInstaller на RO", "Все строки desktop/ в каталоге переводов; тест test_every_ui_string_translated "
     "теперь проверяет и desktop/, D16/D17 — ни одной кириллической подписи.", "GREP:перевод всех строк desktop"),
    ("Д-7", "Собранная программа (PyInstaller) в --check писала «reportlab: нет», хотя библиотека внутри.",
     "запуск бинарника --check", "Версия берётся из модуля, если в сборке нет метаданных пакета; I06.",
     "GREP:перевод всех строк desktop"),
    ("Д-8", "Установщик на Linux: скрипт запуска назывался как папка ядра «texflow» (ошибка IsADirectoryError); "
            "в .bat для Windows переводы строк удваивались (\\r\\r\\n).",
     "первый прогон установщика в чистой домашней папке", "Скрипт texflow-desktop; .bat пишется с одним CRLF; "
     "тест test_installer_windows_and_mac_scripts проверяет отсутствие \\r\\r\\n.", "GREP:самоустановщик Windows/macOS/Linux"),
]


def build_act(e2e: dict, unit: list[dict]) -> str:
    now = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    head = git("rev-parse", "--short", "HEAD")
    fix2 = git("log", "--format=%h", "-1", "--grep=себестоимость на странице поставки") or "—"
    desk, inst = load_json("desktop_results.json"), load_json("install_results.json")
    dp, dt_ = sum(r["status"] == "PASS" for r in desk["results"]), len(desk["results"])
    ip, it = sum(r["status"] == "PASS" for r in inst["results"]), len(inst["results"])

    def commit(h):
        if h == "FIX2":
            return fix2
        if h.startswith("GREP:"):
            return git("log", "--format=%h", "-1", "--fixed-strings", f"--grep={h[5:]}") or "—"
        return h
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    from importlib import import_module
    sys.path.insert(0, ROOT)
    version = import_module("texflow").__version__
    meta = e2e.get("meta", {})
    env = versions() + [("Chromium", meta.get("chromium", "")), ("Playwright", meta.get("playwright", "")),
                        ("Node.js", meta.get("node", "")),
                        ("Нативное приложение и pytest", f"Python {desk['meta'].get('python', '—')} · Tk {desk['meta'].get('tk', '—')}"
                                                         f" · {desk['meta'].get('os', '')} · Xvfb 1360×860")]
    e2e_rows = e2e["results"]
    up, ut = sum(r["status"] == "PASS" for r in unit), len(unit)
    ep, et = sum(r["status"] == "PASS" for r in e2e_rows), len(e2e_rows)
    unit_fail = sum(r["status"] == "FAIL" for r in unit)
    verdict_ok = unit_fail == 0 and ep == et and dp == dt_ and ip == it and ut > 0 and et > 0

    def thumbs(imgs):
        return "".join(f'<a href="img/{i}"><img loading="lazy" src="img/{i}" alt="{i}"></a>' for i in imgs)

    def ci_html():
        ci = load_json("ci_results.json")
        from texflow import integrity as INT
        key = INT.known_key()
        head_ = (f'<p>Подписант <b>{INT.SIGNER}</b> · Ed25519 · отпечаток открытого ключа <code>{INT.fingerprint(key)}</code> '
                 f'(<code>install/signing/unisim-soft.pub</code>). Сборка: <code>.github/workflows/texflow-desktop.yml</code> — на '
                 f'каждый push с изменениями TexFlow и на теги <code>texflow-v*</code>.</p>')
        if not ci.get("jobs"):
            return head_ + '<p class="mut">Результаты запуска GitHub Actions не приложены.</p>'
        rows = "".join(
            f'<tr><td>{html.escape(j["name"])}</td><td>{html.escape(j.get("runner", ""))}</td>'
            f'<td class="{"pass" if j["conclusion"] == "success" else "fail"}">{j["conclusion"]}</td>'
            f'<td>{j.get("seconds", 0) // 60} мин {j.get("seconds", 0) % 60} с</td></tr>' for j in ci["jobs"])
        sums = f'<h3>SHA256SUMS запуска</h3><pre>{html.escape(ci["sums"])}</pre>' if ci.get("sums") else ""
        notes = "".join(f"<li>{html.escape(n)}</li>" for n in ci.get("notes", []))
        return (head_ + f'<p>Запуск <a href="{ci["url"]}">#{ci["run_number"]}</a> · коммит <code>{ci["sha"][:12]}</code> · '
                f'итог: <b class="{"pass" if ci["conclusion"] == "success" else "fail"}">{ci["conclusion"]}</b></p>'
                f'<table><tr><th>Задание</th><th>ОС</th><th>Итог</th><th>Время</th></tr>{rows}</table>'
                + (f"<ul>{notes}</ul>" if notes else "") + sums)

    def rows_of(rows):
        return "".join(
            f'<tr><td>{r["id"]}</td><td>{r["lang"].upper()}</td><td><b>{html.escape(r["title"])}</b><br>'
            f'<span class="mut">Ожидается: {html.escape(r["expected"])}</span></td>'
            f'<td>{html.escape(r["actual"])}</td><td class="{"pass" if r["status"] == "PASS" else "fail"}">{r["status"]}</td>'
            f'<td>{r["ms"] / 1000:.1f} с</td><td class="thumbs">{thumbs(r["images"])}</td></tr>' for r in rows)

    e2e_html = "".join(
        f'<tr><td>{r["id"]}</td><td>{r["lang"].upper()}</td><td><b>{html.escape(r["title"])}</b><br>'
        f'<span class="mut">Ожидается: {html.escape(r["expected"])}</span></td>'
        f'<td>{html.escape(r["actual"])}</td><td class="{"pass" if r["status"] == "PASS" else "fail"}">{r["status"]}</td>'
        f'<td>{r["ms"] / 1000:.1f} с</td><td class="thumbs">{thumbs(r["images"])}</td></tr>' for r in e2e_rows)
    by_file: dict[str, list] = {}
    for r in unit:
        by_file.setdefault(r["file"], []).append(r)
    unit_summary = "".join(
        f'<tr><td><code>{f}</code></td><td>{len(rs)}</td><td class="pass">{sum(x["status"] == "PASS" for x in rs)}</td>'
        f'<td class="{"fail" if any(x["status"] == "FAIL" for x in rs) else ""}">{sum(x["status"] == "FAIL" for x in rs)}</td>'
        f'<td>{sum(x["time"] for x in rs):.2f} с</td></tr>' for f, rs in sorted(by_file.items()))
    unit_detail = "".join(
        f'<tr><td><code>{r["file"]}</code></td><td><code>{html.escape(r["name"])}</code></td>'
        f'<td class="{"pass" if r["status"] == "PASS" else "fail"}">{r["status"]}</td><td>{r["time"]:.3f}</td></tr>'
        for r in unit)
    defects = "".join(f'<tr><td>{d}</td><td>{html.escape(a)}</td><td>{html.escape(b)}</td><td>{html.escape(c)}</td>'
                      f'<td><code>{commit(h)}</code></td><td class="pass">исправлено</td></tr>'
                      for d, a, b, c, h in DEFECTS)
    zpl = open(os.path.join(OUT, "sample_label.zpl"), encoding="utf-8").read() if os.path.exists(os.path.join(OUT, "sample_label.zpl")) else ""
    tspl = open(os.path.join(OUT, "sample_label.tspl"), encoding="utf-8").read() if os.path.exists(os.path.join(OUT, "sample_label.tspl")) else ""
    zpl_first = zpl.split("^XZ")[0] + "^XZ" if zpl else ""
    tspl_first = tspl.split("PRINT")[0] + "PRINT 1,1" if tspl else ""
    body = f"""
<h1>АКТ ТЕСТИРОВАНИЯ № TF-{dt.date.today():%Y%m%d}</h1>
<table><tr><th style="width:240px">Объект</th><td>TexFlow {version} — автономная приёмка одежды из мешков, каталог, цены, этикетки</td></tr>
<tr><th>Расположение</th><td><code>standalone/texflow/</code>, репозиторий PavelTuhari/Artgranit, ветка <code>{branch}</code>, коммит <code>{head}</code></td></tr>
<tr><th>Дата и время</th><td>{now}</td></tr>
<tr><th>Исполнитель</th><td>Claude Code (автоматизированное тестирование), по заданию владельца</td></tr>
<tr><th>Вид испытаний</th><td>модульные и интеграционные (pytest); сквозные в браузере (Playwright + Chromium) и в нативном приложении (Tkinter, Xvfb) на RU / RO / EN; установка, запуск, удаление и сборка PyInstaller; визуальная проверка скриншотов и этикеток</td></tr>
<tr><th>Итог</th><td class="{"pass" if verdict_ok else "fail"}">{"СООТВЕТСТВУЕТ — все проверки пройдены" if verdict_ok else "НЕ СООТВЕТСТВУЕТ — есть непройденные проверки"}</td></tr></table>

<div class="kpis"><div><b>{up}/{ut}</b>модульных и интеграционных тестов</div><div><b>{ep}/{et}</b>сквозных проверок в браузере</div>
<div><b>{dp}/{dt_}</b>сквозных проверок нативного приложения</div><div><b>{ip}/{it}</b>проверок установки и сборки</div>
<div><b>{sum(len(r["images"]) for r in e2e_rows) + sum(len(r["images"]) for r in desk["results"])}</b>скриншотов</div><div><b>{len(DEFECTS)}</b>дефектов найдено и исправлено</div></div>

<h2 id="env">1. Среда испытаний</h2>
<table>{''.join(f"<tr><th style='width:240px'>{k}</th><td>{html.escape(str(v))}</td></tr>" for k, v in env)}
<tr><th>База данных</th><td>SQLite, новая пустая база для каждого прогона (временный файл)</td></tr>
<tr><th>Принтер</th><td>поддельный сетевой принтер TCP (сокет, принимающий задание как порт 9100); физические Zebra / TSC не подключались</td></tr></table>

<h2 id="method">2. Методика</h2>
<ol><li><b>pytest</b> ({ut} тестов): чистые правила (EAN-13, SKU, распределение затрат, цены, сверка), генерация ZPL/TSPL/PDF,
отправка на TCP-принтер, слой данных SQLite, HTTP-сценарии всех страниц, полнота переводов RU/RO/EN, миграция старой базы,
изоляция от общего кода портала Artgranit.</li>
<li><b>Сквозной прогон</b> (<code>tools/e2e.js</code>, {et} шагов): приложение запускается на чистой базе, браузер проходит
весь процесс как оператор — поставка → упаковочный лист → разбор мешков → сканер → сверка → цены → карточки → каталог → этикетки
всех форматов → печать на сетевой принтер → настройки и справочники; затем все экраны на румынском и английском и мобильная ширина.
Каждый шаг проверяется утверждением и сохраняется скриншотом.</li>
<li><b>Нативное приложение</b> (<code>tools/desktop_e2e.py</code>, {dt_} шагов, Xvfb): программа сама нажимает кнопки, заполняет
поля, протаскивает мышью элементы в редакторе этикеток, выгружает и загружает Excel/CSV, печатает на сетевой «принтер»; затем
обходит все 8 вкладок на румынском и английском и проверяет, что ни одна подпись интерфейса не осталась на русском.</li>
<li><b>Установка</b> (<code>tools/install_check.py</code>, {it} шагов): установщик в чистую домашнюю папку, ярлыки, запуск
установленной программы ярлыком, удаление; сборка PyInstaller и запуск бинарника без системного Python.</li>
<li><b>Визуальная проверка</b>: скриншоты и изображения этикеток просмотрены; найденные по ним недочёты внесены в раздел 5.</li></ol>

<h2 id="e2e">3. Сквозные проверки в браузере ({ep}/{et})</h2>
<p class="mut">Нажмите на миниатюру, чтобы открыть скриншот целиком.</p>
<table><tr><th>№</th><th>Язык</th><th>Проверка</th><th>Фактический результат</th><th>Итог</th><th>Время</th><th>Скриншоты</th></tr>{e2e_html}</table>

<h2 id="desktop">3a. Нативное приложение ({dp}/{dt_})</h2>
<table><tr><th>№</th><th>Язык</th><th>Проверка</th><th>Фактический результат</th><th>Итог</th><th>Время</th><th>Скриншоты</th></tr>{rows_of(desk["results"])}</table>

<h2 id="install">3b. Установка, удаление, сборка ({ip}/{it})</h2>
<p class="mut">{inst["meta"].get("os", "")} · Python {inst["meta"].get("python", "")}</p>
<table><tr><th>№</th><th>Проверка</th><th>Фактический результат</th><th>Итог</th><th>Время</th></tr>
{"".join(f'<tr><td>{r["id"]}</td><td><b>{html.escape(r["title"])}</b><br><span class="mut">Ожидается: {html.escape(r["expected"])}</span></td><td>{html.escape(r["actual"])}</td><td class="{"pass" if r["status"] == "PASS" else "fail"}">{r["status"]}</td><td>{r["ms"] / 1000:.1f} с</td></tr>' for r in inst["results"])}</table>

<h2 id="ci">3c. Сборка на каждый push и подпись unisim-soft</h2>
{ci_html()}

<h2 id="unit">4. Модульные и интеграционные тесты ({up}/{ut})</h2>
<table><tr><th>Файл</th><th>Тестов</th><th>Пройдено</th><th>Не пройдено</th><th>Время</th></tr>{unit_summary}</table>
<details><summary>Полный список тестов</summary><table><tr><th>Файл</th><th>Тест</th><th>Итог</th><th>с</th></tr>{unit_detail}</table></details>

<h2 id="defects">5. Найденные дефекты</h2>
<p>Все дефекты найдены в ходе этого испытания, исправлены в коде и закрыты регрессионными тестами или повторным прогоном.</p>
<table><tr><th>№</th><th>Описание</th><th>Как найден</th><th>Исправление</th><th>Коммит</th><th>Статус</th></tr>{defects}</table>

<h2 id="samples">6. Образцы выходных данных</h2>
<div class="shots">
<figure><a href="img/e2e_label_roll.png"><img src="img/e2e_label_roll.png" alt=""></a><figcaption>Этикетка 58×40 мм (PDF-рулон), язык RU</figcaption></figure>
<figure><a href="img/e2e_label_roll_ro.png"><img src="img/e2e_label_roll_ro.png" alt=""></a><figcaption>Та же этикетка, язык этикетки RO</figcaption></figure>
<figure><a href="img/e2e_label_a4.png"><img src="img/e2e_label_a4.png" alt=""></a><figcaption>Лист A4 3×8 (первая страница из 180 этикеток)</figcaption></figure></div>
<h3>ZPL (Zebra), первая этикетка — <a href="sample_label.zpl">файл</a></h3><pre>{html.escape(zpl_first)}</pre>
<h3>TSPL (TSC), первая этикетка — <a href="sample_label.tspl">файл</a></h3><pre>{html.escape(tspl_first)}</pre>
<p>Экспорт каталога: <a href="sample_catalog.csv">sample_catalog.csv</a> · полный отчёт Excel из нативного приложения:
<a href="sample_full_report.xlsx">sample_full_report.xlsx</a></p>
<div class="shots"><figure><a href="img/desk_label_custom.png"><img src="img/desk_label_custom.png" alt=""></a>
<figcaption>Этикетка по шаблону, нарисованному в редакторе мышью (D09–D11): 50×30 мм, CODE128, рамка</figcaption></figure></div>

<h2 id="limits">7. Что не проверялось</h2>
<ul><li>Печать на физических Zebra и TSC: принтеров в среде испытаний нет. Проверены структура ZPL/TSPL (тесты), доставка задания по TCP
(поддельный принтер) и вид этикетки в PDF. Перед вводом в работу — пробная печать одной этикетки и её сканирование.</li>
<li>Отрисовка ZPL в онлайн-просмотрщике labelary.com: отправка данных во внешний сервис в среде испытаний запрещена.</li>
<li>Запуск на Windows и macOS: испытания проводились на Linux (Ubuntu 24.04, Xvfb). Для Windows и macOS проверено,
что установщик формирует правильные файлы (<code>.bat</code> с CRLF, <code>TexFlow.app</code> с Info.plist и иконкой) — тесты
<code>test_installer_windows_and_mac_scripts</code>; ярлыки Windows (.lnk через PowerShell) и запуск на этих ОС не проверялись.
Сборка PyInstaller выполнена только для Linux; для Windows (.exe) и macOS (.app) — шаблон GitHub Actions
<code>.github/workflows/texflow-desktop.yml</code>, собирает и запускает их на своих ОС на каждый push.</li>
<li>Системная печать PDF (кнопка «Печать на системный принтер») — вызывает <code>lp</code> / печать Windows; в среде испытаний
системного принтера нет.</li>
<li>Схема процесса на странице «Инструкция» в самом приложении рисуется библиотекой mermaid с CDN; без интернета показывается её текст.
В HTML-документации схемы встроены готовыми SVG и работают без интернета.</li>
<li>Нагрузочное тестирование не проводилось: приложение рассчитано на 1–5 рабочих мест одного склада.</li></ul>

<h2 id="verdict">8. Заключение</h2>
<p>TexFlow {version} на коммите <code>{head}</code> {"прошёл все" if verdict_ok else "прошёл не все"} модульные ({up}/{ut}),
сквозные в браузере ({ep}/{et}) и в нативном приложении ({dp}/{dt_}) проверки на трёх языках, а также проверки установки и
сборки ({ip}/{it}). Найденные в ходе испытания дефекты ({len(DEFECTS)}) исправлены и закрыты тестами.
Приложение {"рекомендуется к опытной эксплуатации" if verdict_ok else "требует доработки"} при условии пробной печати на конкретном
модели термопринтера (раздел 7).</p>
<table style="margin-top:40px"><tr><th style="width:50%">Испытания провёл</th><th>Принял</th></tr>
<tr><td style="height:70px">Claude Code (автоматизировано)<br><span class="mut">{now}</span></td><td>________________ / ________________<br><span class="mut">дата, подпись</span></td></tr></table>
<p class="mut">Повторить испытание: <code>cd standalone/texflow && tools/run_all.sh</code> — акт и скриншоты пересоберутся.</p>"""
    out = os.path.join(OUT, "test_act.html")
    open(out, "w", encoding="utf-8").write(page("Акт тестирования", body, "ru", ""))
    return out


# ------------------------------------------------------------------ презентация

def build_presentation(e2e: dict, unit: list[dict]) -> str:
    up, ut = sum(r["status"] == "PASS" for r in unit), len(unit)
    ep, et = sum(r["status"] == "PASS" for r in e2e["results"]), len(e2e["results"])
    desk, inst = load_json("desktop_results.json"), load_json("install_results.json")
    dp, dt_ = sum(r["status"] == "PASS" for r in desk["results"]), len(desk["results"])
    ip, it = sum(r["status"] == "PASS" for r in inst["results"]), len(inst["results"])
    img = {re.sub(r"^e2e_\d+_", "", os.path.splitext(i)[0]): i for r in e2e["results"] for i in r["images"]}
    dimg = {re.sub(r"^desk_\d+_", "", os.path.splitext(i)[0]): i for r in desk["results"] for i in r["images"]}

    def dpic(key, cap=""):
        f = dimg.get(key)
        return f'<figure><img src="img/{f}" alt=""><figcaption>{cap}</figcaption></figure>' if f else ""
    def pic(key, cap=""):
        f = img.get(key)
        return f'<figure><img src="img/{f}" alt=""><figcaption>{cap}</figcaption></figure>' if f else ""

    slides = [
        f"""<div class="title"><div class="logo">TEXFLOW</div><h1>Приёмка одежды из мешков<br>за минуты, а не за часы</h1>
<p>Каталог в стиле Zara · цены от себестоимости · этикетки Zebra / TSC / PDF · RU / RO / EN</p>
<p class="mut">Автономное приложение Python + Flask + SQLite · {dt.date.today():%d.%m.%Y}</p></div>""",
        """<h2>Задача</h2><div class="two"><ul>
<li>Одежда из Турции и Китая приходит <b>мешками</b>, всё вперемешку</li>
<li>Упаковочный лист — <b>примерный</b>: «футболки — 120 шт.», без цветов и размеров</li>
<li>Нужно быстро завести каждую вещь как <b>модель · цвет · размер</b> со штрихкодом</li>
<li>Посчитать <b>себестоимость</b> с фрахтом, таможней и брокером и поставить цены</li>
<li>Напечатать <b>этикетки</b> на термопринтере или на обычном принтере</li></ul>
<div class="big">5 шагов<br><span>от мешка до вешалки</span></div></div>""",
        """<h2>Решение: один процесс</h2><div class="flow">
<div><b>1</b>Мешки из Турции / Китая</div><div><b>2</b>Поставка: курс, фрахт, таможня, брокер</div>
<div><b>3</b>Примерный лист CSV → мешки</div><div><b>4</b>Разбор: матрица цвет × размер или сканер</div>
<div><b>5</b>Сверка с листом</div><div><b>6</b>Себестоимость → цена</div>
<div><b>7</b>Карточки и каталог</div><div><b>8</b>Этикетки ZPL / TSPL / PDF</div></div>
<p>Сервер и интернет не нужны: один файл базы SQLite, запуск на ноутбуке склада, несколько рабочих мест по локальной сети.
Полные блок-схемы — в <a href="ru/ARCHITECTURE.html">документации</a>.</p>""",
        f"""<h2>1. Поставка и примерный лист</h2><div class="two">{pic("shipment_form", "Поставка: валюта, курс, фрахт, таможня, брокер")}
{pic("packing_loaded", "Лист CSV загружен — мешки созданы сами")}</div>
<p>Заголовки листа понимаются на RU / RO / EN / TR / ZH; кодировки UTF-8, cp1251, cp1254, GB18030.</p>""",
        f"""<h2>2. Разбор мешка: матрица цвет × размер</h2><div class="two">{pic("matrix_filled", "Клик по цветам → строки, количества по размерам → Ctrl+Enter")}
<div><ul><li>Цвета сгруппированы как у Zara: Белый, Бежевый, Синий…</li><li>Шкала размеров — по категории: XS–3XL, EU 32–48, джинсы W, детская, обувь</li>
<li>SKU <code>TSH0001-800-M</code> и EAN-13 — автоматически</li><li>Закупочная цена подставляется из листа</li><li>Enter — следующая ячейка, стрелки — навигация</li></ul></div></div>""",
        f"""<h2>Сканер и журнал приёмки</h2><div class="two">{pic("scanner", "Повторная модель: скан EAN → +1 шт.; чужой код → ошибка")}
{pic("intake_logged", "Журнал: каждая партия из мешка, ошибку можно удалить")}</div>""",
        f"""<h2>3. Сверка с упаковочным листом</h2>{pic("reconciliation", "По категориям и по мешкам: совпало / недостача / излишек / нет в листе")}""",
        f"""<h2>4. Себестоимость и цены</h2><div class="two">{pic("pricing", "Предложение по каждой модели, своя цена, фиксация")}
<div><pre>себестоимость = закупка × курс
             + пошлина категории
             + доля затрат поставки
цена = себестоимость × (1 + наценка)
     × (1 + НДС) → 189.90</pre><p>Затраты распределяются по стоимости, по штукам или по весу мешков.</p></div></div>""",
        f"""<h2>5. Карточки и каталог</h2><div class="two">{pic("product_card", "Карточка: цвета, сетка размеров с остатками, SKU / EAN, переводы")}
{pic("catalog", "Каталог, поиск по названию на любом языке, SKU, EAN; экспорт CSV")}</div>""",
        f"""<h2>Этикетки: четыре формата</h2><div class="three">
<figure><img src="img/e2e_label_roll.png" alt=""><figcaption>Термоэтикетка 58×40</figcaption></figure>
<figure><img src="img/e2e_label_roll_ro.png" alt=""><figcaption>Та же — на румынском</figcaption></figure>
<figure><img src="img/e2e_label_a4.png" alt=""><figcaption>Лист A4 3×8</figcaption></figure></div>
<p><b>ZPL</b> → Zebra · <b>TSPL</b> → TSC · <b>PDF A4</b> → обычный принтер · <b>PDF-рулон</b> → виртуальный принтер / драйвер.
Печать по сети (порт 9100), через CUPS или в папку; копии — одной командой.</p>""",
        f"""<h2>Три языка: русский · румынский · английский</h2><div class="three">{pic("ro_sort", "Разбор — RO")}{pic("en_pricing", "Цены — EN")}{pic("ro_product", "Карточка — RO")}</div>
<p>Переключатель RU / RO / EN, переведены справочники, названия моделей и этикетки. Тест не даёт добавить строку без перевода.</p>""",
        f"""<h2>Нативное приложение: Windows · macOS · Linux</h2><div class="two">{dpic("matrix", "Разбор мешка — матрица цвет × размер в окне программы")}
<div><ul><li>Обычная программа с окном (Python + Tkinter), без браузера и сервера</li>
<li>То же ядро и та же база SQLite, что у веб-версии</li><li>8 вкладок: поставки, разбор, цены, каталог, этикетки,
<b>редактор этикеток</b>, <b>Excel / CSV</b>, настройки</li><li>RU / RO / EN — переключение кнопкой, без перезапуска</li></ul></div></div>""",
        f"""<h2>Встроенный редактор этикеток</h2><div class="two">{dpic("editor_open", "Шаблон 58×40 с данными вещи")}
<div>{dpic("editor_new", "Свой шаблон 50×30: текст, CODE128, рамка — мышью")}
<ul><li>Любой размер; текст с полями <code>{{name}} {{size}} {{price}}</code>…</li><li>EAN-13 и CODE128, рамки, линии</li>
<li>Перетаскивание мышью, стрелки, свойства справа</li><li>Печать ZPL · TSPL · PDF; экспорт JSON</li></ul></div></div>""",
        f"""<h2>Excel и CSV: выгрузка и загрузка</h2><div class="two">{dpic("exchange", "Полный отчёт Excel — 7 листов")}
<div><ul><li>Выгрузка: каталог, цены, поставки, приёмка, лист, сверка, предложение цен</li>
<li>Загрузка: упаковочный лист, <b>цены после правки в Excel</b>, каталог (сразу в приёмку), результаты приёмки с другого места</li>
<li>Заголовки — на RU / RO / EN, EAN хранится текстом</li></ul>{dpic("exchange_import", "Загрузка цен и каталога")}</div></div>""",
        f"""<h2>Самоустановка</h2><table style="width:100%;border-collapse:collapse;font-size:18px">
<tr><th style="text-align:left;border-bottom:2px solid #111">Windows</th><th style="text-align:left;border-bottom:2px solid #111">macOS</th><th style="text-align:left;border-bottom:2px solid #111">Linux</th></tr>
<tr><td>Install-TexFlow-Windows.bat</td><td>Install-TexFlow-macOS.command</td><td>install-texflow-linux.sh</td></tr>
<tr><td>Python через winget</td><td>python.org / brew</td><td>apt / dnf / pacman</td></tr>
<tr><td>Ярлык «Пуск» и рабочий стол</td><td>TexFlow.app</td><td>меню и рабочий стол</td></tr></table>
<ul style="margin-top:24px"><li>Двойной щелчок → Python, библиотеки в отдельном venv, ярлыки — без прав администратора</li>
<li>Без установки: <code>python texflow_app.py</code> сам доставит библиотеки</li>
<li>Готовая программа без Python: PyInstaller → TexFlow.exe / .app / бинарник</li>
<li>Удаление одной командой; база данных сохраняется</li></ul>""",
        """<h2>Сборка на каждый push · подпись unisim-soft</h2><div class="flow">
<div><b>1</b>Тесты: pytest + окно в Xvfb</div><div><b>2</b>Скрипты: запуск на Windows · macOS · Linux</div>
<div><b>3</b>Сборка .exe · .app · Linux — и запуск без Python</div><div><b>4</b>SHA256SUMS + подпись Ed25519 unisim-soft + аттестация GitHub</div></div>
<ul><li>Скриптовая версия при каждом запуске сама сверяет свои файлы с подписанным манифестом</li>
<li><code>python texflow_app.py --verify-sums SHA256SUMS</code> — проверка скачанных архивов</li>
<li>push в main → выпуск <b>texflow-nightly</b>; тег <code>texflow-v1.2.0</code> → выпуск версии</li></ul>""",
        f"""<h2>Тестирование</h2><div class="kpis"><div><b>{up}/{ut}</b>модульных тестов</div><div><b>{ep}/{et}</b>браузер</div>
<div><b>{dp}/{dt_}</b>нативное приложение</div><div><b>{ip}/{it}</b>установка и сборка</div></div>
<ul><li>Браузер и окно программы проходят весь путь оператора на чистой базе и печатают на сетевой «принтер»</li>
<li>Все экраны на RO и EN — без единой русской строки интерфейса (веб и desktop)</li>
<li>Установщик: установка в чистую папку, запуск ярлыком, удаление; бинарник PyInstaller без Python</li>
<li>{len(DEFECTS)} дефектов найдено и исправлено</li>
<li>Подробности, скриншоты каждого шага и найденные дефекты — в <a href="test_act.html">акте тестирования</a></li></ul>""",
        f"""<h2>Мобильный экран</h2><div class="two">{pic("mobile_sort", "Разбор мешка на телефоне / планшете кладовщика")}
<div><p>Интерфейс адаптивный: на складе можно работать с планшета, подключившись к ноутбуку по локальной сети
(<code>python run.py --host 0.0.0.0</code>).</p></div></div>""",
        """<h2>Как запустить</h2><pre># Windows / macOS: двойной щелчок
Install-TexFlow-Windows.bat   ·   Install-TexFlow-macOS.command
# Linux
sh install-texflow-linux.sh
# без установки
python texflow_app.py --demo  # окно программы
python texflow_app.py --web   # веб-версия
tools/run_all.sh              # все тесты + скриншоты + акт</pre>
<p>Документация: <a href="index.html">все материалы</a> · <a href="ru/OPERATOR_GUIDE.html">инструкция оператора</a> ·
<a href="ru/LABELS.html">принтеры</a> · <a href="ru/DESKTOP.html">нативное приложение</a> · <a href="ru/ARCHITECTURE.html">схемы</a></p>""",
        """<h2>Дальше</h2><ul><li>Пробная печать на вашем Zebra / TSC и сканирование этикетки</li>
<li>Установка на Windows и macOS двойным щелчком; сборка TexFlow.exe / TexFlow.app через GitHub Actions</li>
<li>Загрузка шрифта с кириллицей в принтер — для этикеток на русском</li>
<li>Фото моделей в карточках и выгрузка каталога в интернет-магазин</li>
<li>Опытная эксплуатация на одной реальной поставке</li></ul>
<p class="mut">Код: standalone/texflow/ · PR #60 слит в main</p>""",
    ]
    secs = "".join(f'<section class="slide" id="s{i + 1}">{s}<div class="num">{i + 1} / {len(slides)}</div></section>'
                   for i, s in enumerate(slides))
    doc = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TexFlow — презентация</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#1b1b1b;font:20px/1.45 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#111}}
.slide{{width:1280px;height:720px;margin:24px auto;background:#fff;padding:48px 60px;position:relative;overflow:hidden;box-shadow:0 4px 30px #0008}}
h2{{margin:0 0 20px;font-size:34px;letter-spacing:.02em;text-transform:uppercase}}h1{{font-size:48px;line-height:1.15}}
.title{{display:flex;flex-direction:column;justify-content:center;height:100%}}.logo{{font-weight:800;letter-spacing:.3em;font-size:22px}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start}}.three{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;align-items:start}}
figure{{margin:0}}figure img{{width:100%;max-height:400px;object-fit:contain;object-position:top left;border:1px solid #ddd}}
.three figure img{{max-height:340px}}.slide>figure img{{max-height:500px}}.two>div figure img{{max-height:200px}}figcaption{{font-size:15px;color:#555;margin-top:6px}}
.diagram,.diagram *{{line-height:normal}}.diagram{{font-size:16px}}.diagram svg{{max-width:100%;height:auto;max-height:420px}}pre{{background:#111;color:#eee;padding:16px;font-size:17px}}
.big{{font-size:64px;font-weight:800;text-align:center;align-self:center}}.big span{{display:block;font-size:22px;font-weight:400;color:#666}}
.flow{{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin:10px 0 30px}}
.flow div{{border:2px solid #111;padding:18px;font-size:21px;min-height:120px;position:relative}}.flow b{{display:block;font-size:34px;margin-bottom:6px}}
.flow div:not(:nth-child(4n)):after{{content:"→";position:absolute;right:-17px;top:40%;font-size:22px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:10px 0 24px}}.kpis div{{border:1px solid #ddd;padding:16px;font-size:16px}}
.kpis b{{display:block;font-size:40px}}.mut{{color:#777}}.num{{position:absolute;right:28px;bottom:18px;font-size:14px;color:#999}}
a{{color:#1f4fa0}}.hint{{position:fixed;left:12px;bottom:10px;color:#aaa;font-size:13px}}
@media print{{body{{background:#fff}}.slide{{margin:0;box-shadow:none;page-break-after:always}}.hint{{display:none}}@page{{size:1280px 720px;margin:0}}}}
</style></head><body>{secs}<div class="hint">← → — слайды · Ctrl+P — сохранить в PDF</div>
<script>
const s=[...document.querySelectorAll('.slide')];let i=0;
function go(n){{i=Math.max(0,Math.min(s.length-1,n));s[i].scrollIntoView({{behavior:'smooth',block:'center'}});}}
document.addEventListener('keydown',e=>{{if(['ArrowRight','PageDown',' '].includes(e.key)){{e.preventDefault();go(i+1)}}
if(['ArrowLeft','PageUp'].includes(e.key)){{e.preventDefault();go(i-1)}}}});
</script></body></html>"""
    out = os.path.join(OUT, "presentation.html")
    open(out, "w", encoding="utf-8").write(doc)
    return out


def build_article() -> str:
    """Статья «Автоматизация с коленок» (только RU): docs/ARTICLE.md → docs/html/ru/ARTICLE.html."""
    out = os.path.join(OUT, "ru", "ARTICLE.html")
    title, body, toc = convert_md(os.path.join(ROOT, "docs", "ARTICLE.md"), out)
    side = (f'<nav class="side"><b>Статья</b><div class="toc">{toc.replace("<!--cdn-->", "")}</div>'
            f'<b>Материалы</b><a href="../index.html">Все материалы</a><a href="OPERATOR_GUIDE.html">Инструкция оператора</a>'
            f'<a href="DESKTOP.html">Нативное приложение</a><a href="../test_act.html">Акт тестирования</a></nav>')
    open(out, "w", encoding="utf-8").write(page(title, body, "ru", "../", side))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    e2e, unit = load_e2e(), load_pytest()
    written = build_docs(e2e)
    written.append(build_article())
    written.append(build_index(e2e, unit))
    written.append(build_act(e2e, unit))
    written.append(build_presentation(e2e, unit))
    for w in written:
        print("  ", os.path.relpath(w, ROOT))
    print(f"HTML: {len(written)} страниц; pytest {sum(r['status'] == 'PASS' for r in unit)}/{len(unit)}, "
          f"e2e {sum(r['status'] == 'PASS' for r in e2e['results'])}/{len(e2e['results'])}")


if __name__ == "__main__":
    main()
