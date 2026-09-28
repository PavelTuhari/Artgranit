#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List
import xml.etree.ElementTree as ET


PKG_NS = {"pkg": "http://schemas.microsoft.com/office/2006/xmlPackage"}
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
W = f"{{{W_NS}}}"
A = f"{{{A_NS}}}"
R = f"{{{R_NS}}}"


def slugify(name: str) -> str:
    s = (name or "").strip().lower()
    repl = {
        "ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
        "ü": "u", "ı": "i", "ğ": "g", "ö": "o", "ç": "c",
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9._-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("._")
    return s or "decor_order"


def text_of(elem: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(t.text or "" for t in elem.findall(f".//{W}t"))).strip()


def parse_money(text: str) -> float:
    s = str(text or "").strip().replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_qty(text: str) -> float:
    s = str(text or "").strip().replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_xml_package(xml_path: Path) -> Dict[str, Any]:
    root = ET.parse(xml_path).getroot()
    parts: Dict[str, Dict[str, Any]] = {}
    for part in root.findall("pkg:part", PKG_NS):
        name = part.attrib.get("{http://schemas.microsoft.com/office/2006/xmlPackage}name") or part.attrib.get("pkg:name") or ""
        ctype = part.attrib.get("{http://schemas.microsoft.com/office/2006/xmlPackage}contentType") or ""
        parts[name] = {"content_type": ctype, "part": part}

    doc_part = parts.get("/word/document.xml")
    rels_part = parts.get("/word/_rels/document.xml.rels")
    if not doc_part or not rels_part:
        raise RuntimeError("Missing /word/document.xml or /word/_rels/document.xml.rels in XML package")

    doc_xml = list(doc_part["part"].find("{http://schemas.microsoft.com/office/2006/xmlPackage}xmlData"))[0]
    rels_xml = list(rels_part["part"].find("{http://schemas.microsoft.com/office/2006/xmlPackage}xmlData"))[0]

    rels: Dict[str, Dict[str, str]] = {}
    for rel in rels_xml.findall(f"{{{PR_NS}}}Relationship"):
        rels[rel.attrib.get("Id", "")] = {
            "type": rel.attrib.get("Type", ""),
            "target": rel.attrib.get("Target", ""),
        }

    media_blobs: Dict[str, bytes] = {}
    for name, info in parts.items():
        if not name.startswith("/word/media/"):
            continue
        binary = info["part"].find("{http://schemas.microsoft.com/office/2006/xmlPackage}binaryData")
        if binary is None or binary.text is None:
            continue
        raw = re.sub(r"\s+", "", binary.text)
        media_blobs[name.replace("/word/media/", "media/")] = base64.b64decode(raw)

    return {"doc_xml": doc_xml, "rels": rels, "media_blobs": media_blobs, "parts": parts}


def extract_order_rows(xml_path: Path) -> Dict[str, Any]:
    pkg = parse_xml_package(xml_path)
    doc_xml = pkg["doc_xml"]
    rels = pkg["rels"]
    media_blobs = pkg["media_blobs"]

    rows: List[Dict[str, Any]] = []
    seen = set()

    for tbl in doc_xml.findall(f".//{W}tbl"):
        for tr in tbl.findall(f"{W}tr"):
            tcs = tr.findall(f"{W}tc")
            if len(tcs) < 8:
                continue
            values = [text_of(tc) for tc in tcs[:8]]
            if not values or values[0].strip().lower() in {"nr.", "nr"}:
                continue
            if not re.fullmatch(r"\d+", values[0].strip()):
                continue

            embeds: List[str] = []
            for blip in tcs[2].findall(f".//{A}blip"):
                rid = blip.attrib.get(f"{R}embed")
                if rid:
                    embeds.append(rid)
            image_rel = embeds[0] if embeds else None
            target = None
            source_media_name = None
            if image_rel and image_rel in rels and rels[image_rel]["type"].endswith("/image"):
                target = rels[image_rel]["target"]  # e.g. media/image1.jpeg
                source_media_name = Path(target).name

            rec = {
                "row_no": values[0],
                "date": values[1],
                "description": values[2],
                "code": values[3],
                "qty_text": values[4],
                "qty": parse_qty(values[4]),
                "unit": values[5],
                "unit_price_text": values[6],
                "unit_price": parse_money(values[6]),
                "amount_text": values[7],
                "amount": parse_money(values[7]),
                "image_rel_id": image_rel,
                "image_target": target,
                "image_source_name": source_media_name,
            }
            dedup_key = (
                rec["row_no"], rec["date"], rec["description"], rec["code"],
                rec["qty_text"], rec["unit"], rec["unit_price_text"], rec["amount_text"],
            )
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            rows.append(rec)

    rows.sort(key=lambda x: int(x["row_no"]) if str(x["row_no"]).isdigit() else 999999)
    return {"rows": rows, "media_blobs": media_blobs}


def build_html_table(title: str, rows: List[Dict[str, Any]], img_rel_dir: str) -> str:
    body_rows = []
    for r in rows:
        img_name = r.get("image_copied_name") or ""
        img_src = f"{img_rel_dir}/{img_name}" if img_name else ""
        img_html = f'<img src="{html.escape(img_src)}" alt="{html.escape(r.get("code") or "")}">' if img_src else '<span class="na">no image</span>'
        body_rows.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('row_no','')))}</td>"
            f"<td>{html.escape(str(r.get('code','')))}</td>"
            f"<td>{html.escape(str(r.get('description','')))}</td>"
            f"<td>{html.escape(str(r.get('qty_text','')))}</td>"
            f"<td>{html.escape(str(r.get('unit','')))}</td>"
            f"<td>{html.escape(str(r.get('unit_price_text','')))}</td>"
            f"<td>{html.escape(str(r.get('amount_text','')))}</td>"
            f"<td class='mono'>{html.escape(img_name)}</td>"
            f"<td>{img_html}</td>"
            "</tr>"
        )
    tbody_html = "".join(body_rows) if body_rows else '<tr><td colspan="9">No rows</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="ro">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: ui-sans-serif, -apple-system, Segoe UI, sans-serif; margin: 16px; background: #f6f8fb; color: #111827; }}
    h1 {{ font-size: 18px; margin: 0 0 8px; }}
    .muted {{ color: #6b7280; font-size: 12px; margin-bottom: 12px; }}
    .wrap {{ overflow: auto; border: 1px solid #dbe2ea; border-radius: 10px; background:#fff; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
    th, td {{ border-bottom: 1px solid #edf1f5; padding: 8px; vertical-align: top; font-size: 12px; }}
    th {{ background: #f8fafc; position: sticky; top: 0; text-align: left; }}
    td img {{ width: 120px; height: 80px; object-fit: contain; border: 1px solid #dbe2ea; border-radius: 6px; background: #fff; display:block; }}
    .mono {{ font-family: Menlo, Consolas, monospace; font-size: 11px; }}
    .na {{ color: #9ca3af; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Строки заказа: код изделия, наименование, количество, цена, файл изображения и превью. Картинки лежат отдельно в sibling-папке <span class="mono">{html.escape(img_rel_dir)}/</span>.</div>
  <div class="wrap">
    <table>
      <thead>
        <tr>
          <th>Nr</th>
          <th>Cod / Код</th>
          <th>Denumire / Наименование</th>
          <th>Cant.</th>
          <th>UM</th>
          <th>Preț</th>
          <th>Suma</th>
          <th>Fișier imagine</th>
          <th>Imagine</th>
        </tr>
      </thead>
      <tbody>
        {tbody_html}
      </tbody>
    </table>
  </div>
</body>
</html>
"""


def convert_xml_to_html(xml_path: Path, out_dir: Path) -> Dict[str, Any]:
    parsed = extract_order_rows(xml_path)
    rows = parsed["rows"]
    media_blobs = parsed["media_blobs"]

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = slugify(xml_path.stem)
    out_html = out_dir / f"{stem}__order_table.html"
    out_fld = out_dir / f"{stem}__order_table.fld"
    if out_fld.exists():
        shutil.rmtree(out_fld)
    out_fld.mkdir(parents=True, exist_ok=True)

    for r in rows:
        target = r.get("image_target")
        if not target:
            r["image_copied_name"] = ""
            continue
        src_name = Path(target).name
        blob = media_blobs.get(target)
        if not blob:
            r["image_copied_name"] = ""
            continue
        (out_fld / src_name).write_bytes(blob)
        r["image_copied_name"] = src_name

    html_text = build_html_table(
        title=f"{xml_path.name} — order image table",
        rows=rows,
        img_rel_dir=out_fld.name,
    )
    out_html.write_text(html_text, encoding="utf-8")

    index = out_dir / "index.html"
    existing_links = []
    if index.exists():
        existing_links = re.findall(r'href="([^"]+)"', index.read_text(encoding="utf-8", errors="ignore"))
    link_name = out_html.name
    links = sorted(set(existing_links + [link_name]))
    index.write_text(
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>DECOR XML order tables</title></head><body>"
        "<h1>DECOR XML order tables</h1><ul>"
        + "".join(f"<li><a href=\"{html.escape(x)}\">{html.escape(x)}</a></li>" for x in links)
        + "</ul></body></html>",
        encoding="utf-8",
    )

    return {
        "success": True,
        "xml": str(xml_path),
        "rows_count": len(rows),
        "out_html": str(out_html),
        "out_fld": str(out_fld),
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert DECOR Word XML order file to HTML table + external images")
    ap.add_argument("xml_files", nargs="+", help="Path(s) to Word XML package files")
    ap.add_argument("--out-dir", default="docs/DECOR/xml_order_tables", help="Output directory for HTML tables")
    ap.add_argument("--json-report", default="", help="Optional path to JSON report file")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    reports = []
    for raw in args.xml_files:
        xml_path = Path(raw)
        if not xml_path.exists():
            raise SystemExit(f"File not found: {xml_path}")
        reports.append(convert_xml_to_html(xml_path, out_dir))
        print(f"[ok] {xml_path.name}: rows={reports[-1]['rows_count']} -> {reports[-1]['out_html']}")

    if args.json_report:
        Path(args.json_report).write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ok] json report -> {args.json_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
