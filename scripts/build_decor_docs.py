#!/usr/bin/env python3
"""
Генерация docs/DECOR/*.html:
- TZ.html (техническое задание DECOR)
- index.html (индекс материалов)
- HTML-конверсии файлов из внешней директории veranda (xlsx/pdf -> html)

Без внешних зависимостей (openpyxl/pdfminer не требуются).
"""
from __future__ import annotations

import html
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = Path("/Users/pt/Projects.AI/decor/docs/veranda")
OUT_DIR = ROOT / "docs" / "DECOR"

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


def slugify_filename(name: str) -> str:
    base = Path(name).stem.lower()
    translit = (
        ("ü", "u"), ("ı", "i"), ("İ", "i"), ("ş", "s"), ("ğ", "g"), ("ç", "c"), ("ö", "o"),
        ("Ü", "u"), ("Ş", "s"), ("Ğ", "g"), ("Ç", "c"), ("Ö", "o"),
    )
    for a, b in translit:
        base = base.replace(a, b)
    base = re.sub(r"[^a-z0-9]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    return (base or "file") + ".html"


def xlsx_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: List[str] = []
    for si in root.findall("a:si", NS):
        texts = [t.text or "" for t in si.findall(".//a:t", NS)]
        strings.append("".join(texts))
    return strings


def xlsx_sheet_targets(zf: zipfile.ZipFile) -> List[Tuple[str, str]]:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
    out = []
    for sh in wb.findall("a:sheets/a:sheet", NS):
        name = sh.attrib.get("name", "Sheet")
        rid = sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rid_to_target.get(rid)
        if not target:
            continue
        path = "xl/" + target.lstrip("/")
        out.append((name, path))
    return out


def xlsx_parse_rows(sheet_xml: bytes, shared: List[str], max_rows: int = 250) -> List[List[str]]:
    root = ET.fromstring(sheet_xml)
    rows_out: List[List[str]] = []
    for row in root.findall("a:sheetData/a:row", NS):
        row_vals: List[str] = []
        for c in row.findall("a:c", NS):
            ctype = c.attrib.get("t")
            v = c.find("a:v", NS)
            if v is None:
                is_node = c.find("a:is", NS)
                if is_node is not None:
                    txt = "".join((t.text or "") for t in is_node.findall(".//a:t", NS))
                    row_vals.append(txt)
                else:
                    row_vals.append("")
                continue
            raw = v.text or ""
            if ctype == "s":
                try:
                    row_vals.append(shared[int(raw)])
                except Exception:
                    row_vals.append(raw)
            else:
                row_vals.append(raw)
        if any(str(v).strip() for v in row_vals):
            rows_out.append(row_vals)
        if len(rows_out) >= max_rows:
            break
    return rows_out


def render_xlsx_html(src: Path) -> str:
    with zipfile.ZipFile(src) as zf:
        shared = xlsx_shared_strings(zf)
        sheets = xlsx_sheet_targets(zf)
        body_parts: List[str] = []
        for sheet_name, path in sheets:
            if path not in zf.namelist():
                continue
            rows = xlsx_parse_rows(zf.read(path), shared)
            body_parts.append(f"<section class='sheet'><h2>{esc(sheet_name)}</h2>")
            if not rows:
                body_parts.append("<p class='muted'>Пустой лист.</p></section>")
                continue
            body_parts.append("<div class='tbl-wrap'><table>")
            for i, row in enumerate(rows):
                tag = "th" if i == 0 else "td"
                cells = "".join(f"<{tag}>{esc(v)}</{tag}>" for v in row)
                body_parts.append(f"<tr>{cells}</tr>")
            body_parts.append("</table></div>")
            if len(rows) >= 250:
                body_parts.append("<p class='muted'>Показаны первые 250 непустых строк листа.</p>")
            body_parts.append("</section>")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(src.name)}</title>
  <style>
    body {{ font-family: Segoe UI, system-ui, sans-serif; margin: 24px; background:#f5fbfb; color:#12323c; }}
    h1 {{ margin:0 0 8px; }} .meta {{ color:#5f7480; margin-bottom:16px; font-size:13px; }}
    .sheet {{ background:#fff; border:1px solid #d6e2e8; border-radius:12px; padding:14px; margin-bottom:16px; }}
    h2 {{ margin:0 0 10px; color:#0f766e; font-size:18px; }}
    .tbl-wrap {{ overflow:auto; border:1px solid #e5edf1; border-radius:10px; }}
    table {{ border-collapse:collapse; width:100%; font-size:12px; }}
    th, td {{ border-bottom:1px solid #edf2f7; padding:6px 8px; text-align:left; vertical-align:top; white-space:nowrap; }}
    th {{ background:#ecfeff; position:sticky; top:0; }}
    .muted {{ color:#6b7280; font-size:12px; }}
    a {{ color:#0f766e; }}
  </style>
</head>
<body>
  <h1>{esc(src.name)}</h1>
  <p class="meta">Конвертация XLSX в HTML без внешних библиотек. Источник: <code>{esc(str(src))}</code></p>
  {''.join(body_parts)}
  <p><a href="/UNA.md/orasldev/docs/decor/">← К списку материалов DECOR</a></p>
</body>
</html>"""


def printable_chunks_from_binary(data: bytes, min_len: int = 6, max_items: int = 300) -> List[str]:
    text = data.decode("latin1", errors="ignore")
    chunks = re.findall(r"[ -~]{%d,}" % min_len, text)
    out = []
    for c in chunks:
        c = c.strip()
        if not c:
            continue
        if c.startswith("%PDF") or c.startswith("/Filter") or c.startswith("endobj"):
            continue
        out.append(c)
        if len(out) >= max_items:
            break
    return out


def render_pdf_html(src: Path) -> str:
    st = src.stat()
    chunks = printable_chunks_from_binary(src.read_bytes())
    useful = []
    for c in chunks:
        if any(x in c.lower() for x in ["veranda", "glass", "roof", "pergola", "system", "profile", "huun", "page", "pdf"]):
            useful.append(c)
    if not useful:
        useful = chunks[:80]
    list_html = "".join(f"<li>{esc(x)}</li>" for x in useful[:150]) or "<li>Текст не извлечён (PDF вероятно преимущественно графический).</li>"
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(src.name)}</title>
  <style>
    body {{ font-family: Segoe UI, system-ui, sans-serif; margin:24px; background:#f8fafc; color:#1f2937; }}
    .card {{ background:#fff; border:1px solid #dbe4ea; border-radius:12px; padding:16px; margin-bottom:14px; }}
    h1 {{ margin-bottom:8px; }} h2 {{ color:#0f766e; margin:0 0 8px; font-size:18px; }}
    .meta {{ color:#6b7280; font-size:13px; line-height:1.6; }}
    ul {{ margin-left:20px; }} li {{ margin-bottom:4px; font-family: ui-monospace, monospace; font-size:12px; }}
    a {{ color:#0f766e; }}
  </style>
</head>
<body>
  <h1>{esc(src.name)}</h1>
  <div class="card">
    <h2>Описание конверсии</h2>
    <p class="meta">PDF-конверсия выполнена в HTML-обёртку (метаданные + извлечённые строковые фрагменты из бинарного файла) без внешних библиотек. Для визуальной проверки оригинальный PDF находится во внешней директории проекта DECOR.</p>
    <p class="meta">Размер файла: {st.st_size:,} bytes · Изменён: {datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p class="meta">Источник: <code>{esc(str(src))}</code></p>
  </div>
  <div class="card">
    <h2>Извлечённые текстовые фрагменты (best effort)</h2>
    <ul>{list_html}</ul>
  </div>
  <p><a href="/UNA.md/orasldev/docs/decor/">← К списку материалов DECOR</a></p>
</body>
</html>"""


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def decor_html_inventory_list_html() -> str:
    items: List[str] = []
    if OUT_DIR.exists():
        for p in sorted(OUT_DIR.rglob("*.html")):
            if p.name == "TZ.html":
                continue
            rel = p.relative_to(OUT_DIR).as_posix()
            href = f"/UNA.md/orasldev/docs/decor/{esc(rel)}"
            items.append(f'<li><a href="{href}">{esc(rel)}</a></li>')
    return "".join(items) or "<li>HTML-файлы не найдены.</li>"


def build_tz_html(converted_files: List[Tuple[str, str, str]]) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    files_list = "".join(
        f'<li><a href="/UNA.md/orasldev/docs/decor/{esc(out_name)}">{esc(out_name)}</a> <span style="color:#64748b;">— {esc(src_name)} ({esc(kind)})</span></li>'
        for src_name, out_name, kind in converted_files
    )
    html_inventory_list = decor_html_inventory_list_html()
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ТЗ DECOR — стеклянные крыши / веранда</title>
  <style>
    :root {{ --primary:#0f766e; --bg:#eef7f8; --card:#fff; --text:#12323c; --muted:#5f7480; --line:#d6e2e8; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family: Segoe UI, system-ui, sans-serif; background:var(--bg); color:var(--text); line-height:1.6; padding:24px; max-width:980px; margin:0 auto; }}
    .lead {{ margin: 16px 0 22px; background: linear-gradient(135deg,#dff4f2,#eaf8fb); border:1px solid var(--line); border-left:4px solid var(--primary); border-radius:14px; padding:16px; }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:20px; }}
    @media (max-width: 760px) {{ .grid {{ grid-template-columns:1fr; }} }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px; margin-bottom:14px; }}
    h1 {{ font-size:28px; margin-bottom:6px; }}
    h2 {{ font-size:20px; color:var(--primary); margin-bottom:8px; }}
    h3 {{ font-size:16px; margin:8px 0; }}
    p, ul, ol {{ margin-bottom:10px; }}
    ul, ol {{ margin-left:22px; }}
    .btn {{ display:inline-block; text-decoration:none; font-weight:600; padding:10px 12px; border-radius:10px; margin:4px 6px 0 0; }}
    .btn.primary {{ background:var(--primary); color:#fff; }}
    .btn.ghost {{ background:#f7fbfb; color:var(--primary); border:1px solid var(--line); }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th, td {{ border:1px solid #e7eef2; padding:8px 10px; text-align:left; vertical-align:top; }}
    th {{ background:#f3fafb; color:var(--muted); }}
    .muted {{ color:var(--muted); font-size:13px; }}
    code {{ background:#f3fafb; padding:1px 4px; border-radius:4px; }}
    a {{ color:var(--primary); }}
  </style>
</head>
<body>
  <h1>DECOR — Техническое задание</h1>
  <p class="muted">Проект: админка и интерфейс оператора приёма заказов для стеклянных крыш / веранд / пергол. Сгенерировано: {esc(generated)}.</p>
  <div class="lead">
    ТЗ сформировано на основе: 1) страницы GARDECOR для категории стеклянных крыш/веранд (каталог/лид-форма/консультация/showroom/contact, best-effort из открытых snippets), 2) материалов <code>decor/docs/veranda</code> (PDF + 2 XLSX: прайс материалов и производственная калькуляция), 3) shell-концепции и паттерна модулей <em>credit / nufarul</em> в текущем проекте Artgranit.
  </div>

  <div class="grid">
    <div class="card">
      <h2>Рабочие интерфейсы</h2>
      <p>Реализованы внутри платформы UNA shell как отдельный модуль DECOR.</p>
      <p>
        <a class="btn primary" href="/UNA.md/orasldev/decor-operator">DECOR Оператор</a>
        <a class="btn primary" href="/UNA.md/orasldev/decor-admin">DECOR Админка</a>
      </p>
      <p><a class="btn ghost" href="/UNA.md/orasldev/docs/decor/">Материалы / HTML-конверсии</a></p>
    </div>
    <div class="card">
      <h2>Ключевая идея</h2>
      <p>Оператор в зале быстро вводит параметры изделия (габариты, стекло, LED, опции), получает расчёт сметы и сохраняет заявку/заказ. Администратор управляет справочником материалов, коэффициентами расчёта, статусами заказов и отчётностью.</p>
    </div>
  </div>

  <div class="card">
    <h2>1. Предметная область (по материалам veranda)</h2>
    <ul>
      <li>Прайс профилей и аксессуаров HUUN Veranda: листы <code>PROFILE (NEW SYSTEM)</code>, <code>ACCESSORY (2)</code>.</li>
      <li>Производственная калькуляция veranda (турецкий шаблон): типы стекла <code>TEKCAM / ISICAM</code>, размеры (ширина/вылет/высоты), LED / RGB / dimmer, листы себестоимости и спецификации.</li>
      <li>Категории материалов: профили, аксессуары, стекло, водоотвод, монтаж, опции LED.</li>
      <li>Тип заказа: индивидуальный проект с параметрами, а не стандартная товарная корзина.</li>
    </ul>
  </div>

  <div class="card">
    <h2>2. Роли пользователей</h2>
    <table>
      <tr><th>Роль</th><th>Назначение</th><th>Функции</th></tr>
      <tr><td>Оператор приёма</td><td>Работа в шоуруме / в зале</td><td>Ввод параметров изделия, расчёт сметы, оформление заявки/заказа, поиск по номеру, просмотр последних заказов</td></tr>
      <tr><td>Администратор</td><td>Поддержка справочников и расчётной модели</td><td>Материалы, коэффициенты (маржа/отходы/ставки), список заказов, смена статусов, отчёт по дням</td></tr>
    </table>
  </div>

  <div class="card">
    <h2>3. Функциональные требования</h2>
    <h3>3.1 Оператор (зал)</h3>
    <ul>
      <li>Форма параметров: тип проекта, тип системы (TEKCAM/ISICAM), цвет, ширина/вылет, передняя/задняя высоты, LED-опция.</li>
      <li>Опции включения в смету: водоотвод, транспорт, монтаж.</li>
      <li>Кнопка расчёта сметы с отображением: площадь, периметр, уклон, строки сметы, итог в USD и MDL.</li>
      <li>Карточка клиента: имя, телефон, email, адрес/локация, примечание.</li>
      <li>Сохранение заказа/лида с автогенерацией номера формата <code>DEC-YYYYMM-NNNNN</code>.</li>
      <li>Поиск заказа по номеру/штрихкоду, список последних заказов.</li>
    </ul>
    <h3>3.2 Админка</h3>
    <ul>
      <li>Справочник материалов: CRUD (код, название, категория, единица, цена, валюта, источник: файл/лист, активность).</li>
      <li>Настройки расчёта: курсы валют, маржа, отходы, ставки на стекло, монтаж, транспорт, LED-опции, списки типов/цветов.</li>
      <li>Список заказов с фильтрами по статусу/периоду/поиску.</li>
      <li>Смена статуса заказа (лид, смета отправлена, согласовано, производство, монтаж, завершено, отменено).</li>
      <li>Отчёт по дням: количество заказов и сумма.</li>
    </ul>
  </div>

  <div class="card">
    <h2>4. Расчётная модель (MVP)</h2>
    <p>Расчёт реализован как конфигурируемая оценочная модель (не заменяет инженерный production-калькулятор из XLSX, но даёт быстрый коммерческий расчёт для оператора).</p>
    <ul>
      <li><strong>Площадь:</strong> ширина × вылет (в м²).</li>
      <li><strong>Периметр:</strong> используется для LED white per meter.</li>
      <li><strong>Уклон:</strong> вычисляется из разницы высот (rear - front) и вылета.</li>
      <li><strong>Себестоимость:</strong> стекло + профиль (оценка) + аксессуары + водоотвод + LED + монтаж + транспорт.</li>
      <li><strong>Коммерция:</strong> тех. отходы (%) + маржа (%).</li>
      <li><strong>Валюты:</strong> итог в USD и пересчёт в MDL по настраиваемому курсу.</li>
    </ul>
  </div>

  <div class="card">
    <h2>5. Техническая реализация (в рамках shell-концепции)</h2>
    <ul>
      <li>Платформа: Flask-приложение текущего проекта <code>Artgranit</code>.</li>
      <li>Маршруты UI: <code>/UNA.md/orasldev/decor-operator</code>, <code>/UNA.md/orasldev/decor-admin</code>.</li>
      <li>Маршруты docs: <code>/UNA.md/orasldev/docs/decor/</code> + HTML-файлы из <code>docs/DECOR</code>.</li>
      <li>API:
        <ul>
          <li><code>/api/decor-operator/catalog</code>, <code>/api/decor-operator/calculate</code>, <code>/api/decor-operator/order</code>, <code>/api/decor-operator/recent-orders</code>, <code>/api/decor-operator/order-by-number</code></li>
          <li><code>/api/decor-admin/materials</code>, <code>/api/decor-admin/settings</code>, <code>/api/decor-admin/statuses</code>, <code>/api/decor-admin/orders</code>, <code>/api/decor-admin/orders/&lt;id&gt;/status</code>, <code>/api/decor-admin/report-by-day</code></li>
        </ul>
      </li>
      <li>Хранилище MVP: локальный JSON <code>data/decor_store.json</code> (fallback без Oracle-таблиц/контроллеров).</li>
    </ul>
  </div>

  <div class="card">
    <h2>6. Конвертированные материалы veranda (HTML)</h2>
    <ul>
      {files_list}
    </ul>
  </div>

  <div class="card">
    <h2>6.1 Все HTML-файлы в docs/DECOR (включая поддиректории)</h2>
    <ul>
      {html_inventory_list}
    </ul>
  </div>

  <div class="card">
    <h2>7. Ограничения и дальнейшие шаги</h2>
    <ul>
      <li>Текущий расчёт — коммерческий MVP; для инженерной точности нужна более глубокая интеграция с логикой XLSX (формулы/все коэффициенты).</li>
      <li>PDF <code>Veranda.pdf</code> конвертирован в HTML-обёртку best-effort без OCR/профильных библиотек.</li>
      <li>Для shell-списка проектов (<code>/una.md/shell/projects</code>) может потребоваться запись в таблицу <code>UNA_SHELL_PROJECTS</code>.</li>
    </ul>
  </div>

  <p><a href="/UNA.md/orasldev/docs/decor/">← К списку материалов DECOR</a></p>
</body>
</html>"""


def build_index_html(converted_files: List[Tuple[str, str, str]]) -> str:
    items = "".join(
        f'<li><a href="/UNA.md/orasldev/docs/decor/{esc(out_name)}">{esc(out_name)}</a><span>{esc(src_name)} · {esc(kind)}</span></li>'
        for src_name, out_name, kind in converted_files
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DECOR — материалы ТЗ</title>
  <style>
    :root {{ --primary:#0f766e; --bg:#eef7f8; --card:#fff; --text:#12323c; --muted:#5f7480; --line:#d6e2e8; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family: Segoe UI, system-ui, sans-serif; background:var(--bg); color:var(--text); padding:24px; max-width:860px; margin:0 auto; }}
    h1 {{ margin-bottom:16px; }}
    .lead {{ margin-bottom:18px; border:1px solid var(--line); background:#e7f6f4; border-radius:12px; padding:14px; }}
    ul {{ list-style:none; }}
    li {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 14px; margin-bottom:10px; }}
    li a {{ color:var(--primary); font-weight:600; text-decoration:none; }}
    li span {{ display:block; margin-top:4px; color:var(--muted); font-size:13px; }}
    a {{ color:var(--primary); }}
  </style>
</head>
<body>
  <h1>Проект DECOR — материалы ТЗ</h1>
  <p class="lead"><a href="/UNA.md/orasldev/docs/decor/TZ.html">TZ.html</a> — техническое задание на модуль DECOR (админка + оператор) и описание реализации.</p>
  <ul>
    <li><a href="/UNA.md/orasldev/docs/decor/TZ.html">TZ.html</a><span>Техническое задание DECOR (стеклянные крыши / веранды / перголы)</span></li>
    {items}
  </ul>
</body>
</html>"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    converted: List[Tuple[str, str, str]] = []

    if not SRC_DIR.is_dir():
        raise SystemExit(f"Source directory not found: {SRC_DIR}")

    for src in sorted(SRC_DIR.iterdir()):
        if not src.is_file():
            continue
        if src.name.startswith("~$"):
            continue
        suffix = src.suffix.lower()
        out_name = slugify_filename(src.name)
        out_path = OUT_DIR / out_name
        if suffix == ".xlsx":
            html_text = render_xlsx_html(src)
            write_file(out_path, html_text)
            converted.append((src.name, out_name, "xlsx"))
        elif suffix == ".pdf":
            html_text = render_pdf_html(src)
            write_file(out_path, html_text)
            converted.append((src.name, out_name, "pdf"))

    write_file(OUT_DIR / "TZ.html", build_tz_html(converted))
    write_file(OUT_DIR / "index.html", build_index_html(converted))
    print(f"Generated docs in {OUT_DIR}")
    for item in converted:
        print(" -", item[1], "<-", item[0])
    print(" - TZ.html")
    print(" - index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
