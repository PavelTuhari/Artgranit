#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote


TR_RE = re.compile(r"<tr\b.*?</tr>", re.I | re.S)
IMG_RE = re.compile(r'<img[^>]+src="([^"]+\.(?:png|jpg|jpeg|gif|webp))"', re.I)
TAG_RE = re.compile(r"<[^>]+>")
CODE_RE = re.compile(r"\b(?:[A-Z]{1,6}[.-]?[A-Z0-9]+(?:-[A-Z0-9]+)*|O\.\d{3,5}|\d{6,})\b")


def esc(s: str) -> str:
    return html.escape(str(s))


def strip_html(text: str) -> str:
    s = TAG_RE.sub(" ", text)
    s = html.unescape(s)
    return " ".join(s.split())


def code_candidates(plain: str) -> list[str]:
    out: list[str] = []
    for m in CODE_RE.finditer(plain):
        c = m.group(0).strip()
        if c in {"TR", "PC", "KG", "AD", "MTR", "TOTAL", "KOD", "REF", "DIV"}:
            continue
        if c.startswith("#"):
            continue
        if not (re.search(r"\d", c) or "." in c or "-" in c):
            continue
        if c.replace(".", "", 1).isdigit() and len(c) < 6:
            continue
        out.append(c)
    return list(dict.fromkeys(out))


def slugify(name: str) -> str:
    s = name.lower()
    translit = {
        "ü": "u", "ı": "i", "İ": "i", "ş": "s", "ğ": "g", "ç": "c", "ö": "o",
        "Ü": "u", "Ş": "s", "Ğ": "g", "Ç": "c", "Ö": "o",
    }
    for a, b in translit.items():
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "file"


def parse_rows_from_word_html(html_file: Path) -> list[dict]:
    text = html_file.read_text(encoding="utf-8", errors="ignore")
    rows: list[dict] = []
    for idx, tr in enumerate(TR_RE.findall(text), start=1):
        img_match = IMG_RE.search(tr)
        if not img_match:
            continue
        img_rel_raw = img_match.group(1)
        img_rel = unquote(img_rel_raw)
        img_path = (html_file.parent / img_rel).resolve()
        if not img_path.exists():
            continue
        plain = strip_html(tr)
        codes = code_candidates(plain)
        if not codes:
            continue
        rows.append(
            {
                "row_index": idx,
                "codes": codes,
                "file_name": img_path.name,
                "file_path": img_path,
                "img_rel": img_rel,
                "text": plain,
            }
        )
    return rows


def render_output_html(source_html: Path, rows: list[dict], local_assets_dir_name: str) -> str:
    body_rows: list[str] = []
    for r in rows:
        codes_html = "<br>".join(esc(c) for c in r["codes"])
        file_name = r["file_name"]
        local_rel = f"{local_assets_dir_name}/{quote(file_name)}"
        body_rows.append(
            "<tr>"
            f"<td class='code'>{codes_html}</td>"
            f"<td class='fname'><div>{esc(file_name)}</div><div class='sub'>{esc(local_assets_dir_name + '/' + file_name)}</div></td>"
            f"<td class='imgcell'><img src='{local_rel}' alt='{esc(file_name)}'><div class='sub'><a href='{local_rel}' target='_blank'>Открыть файл</a></div></td>"
            "</tr>"
        )

    rows_html = "\n".join(body_rows) or "<tr><td colspan='3'>Нет строк с кодом и изображением</td></tr>"
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(source_html.name)} - image table (local copied files)</title>
  <style>
    :root {{ --bg:#f5fafb; --card:#fff; --line:#dbe4ea; --ink:#12323c; --muted:#607483; --brand:#0f766e; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Segoe UI, system-ui, sans-serif; background: var(--bg); color: var(--ink); margin: 0; padding: 22px; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; }}
    .muted {{ color: var(--muted); font-size: 13px; margin-bottom: 12px; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #e8eef2; padding: 8px; vertical-align: top; }}
    th {{ background: #eef9f7; text-align: left; position: sticky; top: 0; }}
    td.code {{ width: 180px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    td.fname {{ width: 260px; word-break: break-word; }}
    td.imgcell {{ width: auto; }}
    td.imgcell img {{ max-width: 100%; height: auto; display: block; border: 1px solid var(--line); border-radius: 6px; background:#fff; }}
    .toolbar a {{ color: var(--brand); text-decoration: none; }}
    .sub {{ color: var(--muted); font-size: 11px; margin-top: 4px; word-break: break-word; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Таблица картинок: {esc(source_html.name)}</h1>
    <p class="muted">3 колонки: код артикула, имя файла, картинка из файла. Изображения скопированы рядом с результатом в подпапку <code>{esc(local_assets_dir_name)}</code> и подключены относительным путём (по принципу исходного Word-HTML + .fld).</p>
    <p class="toolbar"><a href="/UNA.md/orasldev/docs/decor/">← docs/DECOR</a></p>
    <div class="card">
      <table>
        <thead><tr><th>Код артикула</th><th>Имя файла</th><th>Файл (внешний img src)</th></tr></thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>"""


def render_index(output_dir: Path, generated: list[tuple[Path, int]]) -> str:
    items = []
    for out_file, cnt in generated:
        href = f"/UNA.md/orasldev/docs/decor/{quote(output_dir.name)}/{quote(out_file.name)}"
        items.append(f"<li><a href='{href}'>{esc(out_file.name)}</a> <span>rows: {cnt}</span></li>")
    items_html = "\n".join(items) or "<li>Нет файлов</li>"
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DECOR HTML image tables</title>
  <style>
    body {{ font-family: Segoe UI, system-ui, sans-serif; margin: 24px; background:#f5fafb; color:#12323c; }}
    .card {{ background:#fff; border:1px solid #dbe4ea; border-radius:12px; padding:16px; max-width:960px; }}
    li {{ margin-bottom:8px; }}
    a {{ color:#0f766e; }}
    span {{ color:#607483; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>DECOR - HTML image tables</h1>
    <p>Автогенерация таблиц (код / имя файла / картинка) из Word-HTML файлов с копированием изображений в соседние подпапки <code>*.fld</code>.</p>
    <ul>{items_html}</ul>
    <p><a href="/UNA.md/orasldev/docs/decor/">← docs/DECOR</a></p>
  </div>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-dir", default=str(Path("docs") / "DECOR"))
    parser.add_argument("--out-subdir", default="html_image_tables")
    parser.add_argument("inputs", nargs="*", help="HTML files to parse (relative to docs-dir if not absolute)")
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir).resolve()
    out_dir = docs_dir / args.out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs: list[Path]
    if args.inputs:
        inputs = []
        for p in args.inputs:
            path = Path(p)
            if not path.is_absolute():
                path = docs_dir / path
            inputs.append(path.resolve())
    else:
        inputs = sorted(docs_dir.glob("*.html"))

    generated: list[tuple[Path, int]] = []
    for src in inputs:
        if not src.exists():
            print(f"skip missing: {src}")
            continue
        rows = parse_rows_from_word_html(src)
        out_name = f"{slugify(src.stem)}__image_table.html"
        out_path = out_dir / out_name
        assets_dir = out_dir / f"{out_path.stem}.fld"
        assets_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for r in rows:
            dst = assets_dir / r["file_name"]
            src_img = r["file_path"]
            if (not dst.exists()) or dst.stat().st_size != src_img.stat().st_size:
                shutil.copy2(src_img, dst)
                copied += 1
        out_path.write_text(render_output_html(src, rows, assets_dir.name), encoding="utf-8")
        generated.append((out_path, len(rows)))
        print(f"generated {out_path} rows={len(rows)} copied_images={copied} assets={assets_dir.name}")

    (out_dir / "index.html").write_text(render_index(out_dir, generated), encoding="utf-8")
    print(f"generated {(out_dir / 'index.html')}")


if __name__ == "__main__":
    main()
