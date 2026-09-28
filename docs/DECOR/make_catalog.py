#!/usr/bin/env python3
"""
Process Word-exported HTML files with images.
Generates a new HTML with 3 columns:
  1. Article code (MALZEME KODU / артикул)
  2. Image filename
  3. Embedded image (base64 data URI)

Usage:
  python3 make_catalog.py
"""

import re
import base64
from pathlib import Path
from urllib.parse import unquote


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_tags(html: str) -> str:
    """Remove all HTML/XML tags and clean whitespace."""
    text = re.sub(r'<[^>]+>', '', html, flags=re.DOTALL)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&#45;', '-')
    return re.sub(r'\s+', ' ', text).strip()


def get_cells(row_html: str) -> list:
    """Return list of raw HTML contents for each <td> in a row."""
    return re.findall(r'<td\b[^>]*>(.*?)</td>', row_html,
                      re.DOTALL | re.IGNORECASE)


def get_img_src(cell_html: str):
    """
    Extract the non-VML img src from a cell.
    Word HTML wraps images in <!--[if !vml]><img ...><![endif]-->.
    The [^>]+ pattern already crosses newlines (negated class).
    """
    # Preferred: the non-vml fallback img (actual raster image)
    m = re.search(
        r'\[if\s+!vml\]><img\b[^>]+src="([^"]+)"',
        cell_html, re.IGNORECASE
    )
    if m:
        return m.group(1)
    # Fallback: any <img src="..."> in the cell
    m = re.search(r'<img\b[^>]+src="([^"]+)"', cell_html, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


MIME = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
}


def embed_image(img_src: str, base_dir: Path):
    """Read image file and return (data-URI, bare filename) or (None, None)."""
    rel_path = unquote(img_src)          # decode %20 → space etc.
    full_path = base_dir / rel_path
    if not full_path.exists():
        print(f"    [WARN] image not found: {full_path}")
        return None, None
    mime = MIME.get(full_path.suffix.lower(), 'image/png')
    b64 = base64.b64encode(full_path.read_bytes()).decode('ascii')
    return f"data:{mime};base64,{b64}", full_path.name


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

def process_html(html_path: Path) -> list[dict]:
    """
    Parse one Word-exported HTML file.
    Returns list of dicts: {code, filename, data_uri}.

    Table column layout (0-indexed):
      0 – SIRANO      (row number)
      1 – MALZEME KODU  (article code / артикул)
      2 – MALZEME İSİM  (name)
      3 – RESİM          (image cell)
      4 – AÇIKLAMA/NOT
      5 – KESİM ÖLÇÜ
    """
    content = html_path.read_text(encoding='utf-8', errors='replace')
    base_dir = html_path.parent

    # Find data rows: skip header (irow:0)
    # Note: Word HTML uses single-quoted style attr, so [^>]* stops safely at >
    rows = re.findall(
        r'<tr\b[^>]*mso-yfti-irow:(\d+)[^>]*>(.*?)</tr>',
        content, re.DOTALL | re.IGNORECASE
    )

    items = []
    for irow_str, row_html in rows:
        if int(irow_str) == 0:      # header row
            continue

        cells = get_cells(row_html)
        if len(cells) < 4:
            continue

        article_code = strip_tags(cells[1])   # MALZEME KODU
        img_src      = get_img_src(cells[3])  # RESİM cell

        if not img_src:
            continue

        data_uri, filename = embed_image(img_src, base_dir)
        if not data_uri:
            continue

        items.append({
            'code':     article_code or '—',
            'filename': filename,
            'data_uri': data_uri,
        })

    return items


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def generate_html(items: list[dict], source_name: str) -> str:
    rows_html = ''
    for item in items:
        rows_html += f"""
    <tr>
      <td class="col-code">{item['code']}</td>
      <td class="col-filename">{item['filename']}</td>
      <td class="col-image">
        <img src="{item['data_uri']}" alt="{item['filename']}">
      </td>
    </tr>"""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{source_name} — каталог</title>
  <style>
    body  {{ font-family: Arial, sans-serif; font-size: 13px; margin: 24px; background: #fafafa; }}
    h1    {{ font-size: 15px; color: #444; margin-bottom: 12px; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; }}
    th, td{{ border: 1px solid #ccc; padding: 7px 12px; vertical-align: middle; }}
    th    {{ background: #c0504d; color: #fff; font-size: 12px; text-align: center; }}
    .col-code     {{ width: 130px; font-weight: bold; font-family: monospace; font-size: 13px; }}
    .col-filename {{ width: 200px; color: #777; font-size: 11px; word-break: break-all; }}
    .col-image    {{ text-align: center; }}
    .col-image img{{ max-height: 90px; max-width: 220px; object-fit: contain; }}
    tr:nth-child(even) {{ background: #f5f5f5; }}
    tr:hover           {{ background: #eef4fb; }}
  </style>
</head>
<body>
  <h1>Артикулы и изображения: {source_name}</h1>
  <p style="color:#888;font-size:11px;">Строк: {len(items)}</p>
  <table>
    <thead>
      <tr>
        <th>Артикул (код)</th>
        <th>Имя файла</th>
        <th>Изображение</th>
      </tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    base = Path("/Users/pt/Projects.AI/Artgranit/docs/DECOR")

    files = [
        "Configurator2 Proiect Test UNA 1.html",
        "YENİ VERANDA ÜRETİM MALİYET HESAPLAMA.html",
    ]

    out_dir = base / "image_catalog"
    out_dir.mkdir(exist_ok=True)
    print(f"Output directory: {out_dir}\n")

    for fname in files:
        html_path = base / fname
        if not html_path.exists():
            print(f"[SKIP] not found: {html_path}")
            continue

        print(f"Processing: {fname}")
        items = process_html(html_path)
        print(f"  → {len(items)} images found")

        # Safe output filename (strip special chars)
        safe_stem = re.sub(r'[^\w\- ]', '_', html_path.stem).strip()
        out_path = out_dir / f"{safe_stem}_catalog.html"

        out_path.write_text(generate_html(items, fname), encoding='utf-8')
        print(f"  → written: {out_path.name}\n")

    print("Done.")


if __name__ == "__main__":
    main()
