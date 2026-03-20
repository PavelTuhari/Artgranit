#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from decor_local_store import DecorLocalStore
from convert_decor_order_xml_to_html import extract_order_rows, slugify


def _parse_doc_date(s: str) -> str:
    s = str(s or "").strip()
    for fmt in ("%d.%m.%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def import_sample_order(xml_path: Path, static_root: Path) -> Dict[str, Any]:
    parsed = extract_order_rows(xml_path)
    rows: List[Dict[str, Any]] = parsed["rows"]
    media_blobs: Dict[str, bytes] = parsed["media_blobs"]
    if not rows:
        return {"success": False, "error": "No item rows parsed from XML"}

    slug = slugify(xml_path.stem)
    rel_static_dir = Path("static") / "decor" / "sample_orders" / slug
    abs_static_dir = static_root / "decor" / "sample_orders" / slug
    if abs_static_dir.exists():
        shutil.rmtree(abs_static_dir)
    abs_static_dir.mkdir(parents=True, exist_ok=True)

    lines = []
    total = 0.0
    for idx, r in enumerate(rows, start=1):
        image_url = ""
        target = r.get("image_target")
        if target:
            blob = media_blobs.get(target)
            fname = Path(target).name
            if blob:
                (abs_static_dir / fname).write_bytes(blob)
                image_url = "/" + (rel_static_dir / fname).as_posix()
        amount = float(r.get("amount") or 0.0)
        unit_price = float(r.get("unit_price") or 0.0)
        qty = float(r.get("qty") or 0.0)
        total += amount
        lines.append({
            "code": str(r.get("code") or f"XML-{idx:03d}"),
            "name": str(r.get("description") or r.get("code") or f"XML item {idx}"),
            "qty": qty,
            "unit": str(r.get("unit") or "pc"),
            "unit_price": unit_price,
            "amount": amount,
            "image_url": image_url,
            "source": "xml_import",
            "category": "xml_import",
        })

    with DecorLocalStore._lock:
        state = DecorLocalStore._load()
        source_tag = f"[XML_IMPORT] {xml_path.name}"
        for o in state.get("orders", []):
            if source_tag in str(o.get("notes") or ""):
                return {
                    "success": True,
                    "skipped": True,
                    "message": "Order already imported",
                    "existing_order_number": o.get("order_number"),
                    "items_count": len(o.get("items") or []),
                }

        order_id = int(state.get("next_order_id") or 1)
        state["next_order_id"] = order_id + 1
        order_number = DecorLocalStore._order_number(state)
        status = DecorLocalStore._status_by_id(state, 1) or {"id": 1, "code": "lead", "name": "Лид / Новый"}
        created_at = _parse_doc_date(rows[0].get("date"))

        quote = {
            "inputs": {"source": "xml_import", "xml_file": xml_path.name, "extra_items_count": len(lines)},
            "metrics": {},
            "lines": lines,
            "summary": {
                "currency": "MDL",
                "direct_cost": round(total, 2),
                "waste_amount": 0.0,
                "subtotal": round(total, 2),
                "margin_amount": 0.0,
                "total": round(total, 2),
                "exchange_rate_usd_to_mdl": None,
                "total_mdl": round(total, 2),
                "extra_items_amount": round(total, 2),
            },
        }

        order = {
            "id": order_id,
            "order_number": order_number,
            "barcode": order_number,
            "client_name": "XML Sample / 3 canale 1HUUN",
            "client_phone": "+37300000000",
            "client_email": "",
            "project_type": "Стеклянная крыша",
            "project_name": xml_path.stem,
            "location": "Imported XML sample",
            "color": "",
            "notes": f"{source_tag} · imported with line images",
            "status_id": status.get("id"),
            "status_code": status.get("code"),
            "status_name": status.get("name"),
            "quote": quote,
            "items": lines,
            "total_amount": round(total, 2),
            "currency": "MDL",
            "created_at": created_at,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        state.setdefault("orders", []).insert(0, order)
        DecorLocalStore._save(state)

    return {
        "success": True,
        "order_id": order_id,
        "order_number": order_number,
        "items_count": len(lines),
        "total_mdl": round(total, 2),
        "static_dir": str(abs_static_dir),
        "sample_image_url": next((x.get("image_url") for x in lines if x.get("image_url")), ""),
    }


def import_xml_orders_from_dir(xml_dir: Path, static_root: Path) -> Dict[str, Any]:
    if not xml_dir.exists() or not xml_dir.is_dir():
        return {"success": False, "error": f"Directory not found: {xml_dir}"}

    results: List[Dict[str, Any]] = []
    xml_files = sorted(
        p for p in xml_dir.glob("*.xml")
        if p.is_file() and ".fld" not in p.as_posix()
        and p.name.lower() not in {"filelist.xml", "colorschememapping.xml"}
    )
    for xml_file in xml_files:
        try:
            res = import_sample_order(xml_file, static_root)
        except Exception as e:
            res = {"success": False, "error": str(e), "xml_file": str(xml_file)}
        res.setdefault("xml_file", str(xml_file))
        results.append(res)

    imported = [r for r in results if r.get("success") and not r.get("skipped")]
    skipped = [r for r in results if r.get("success") and r.get("skipped")]
    failed = [r for r in results if not r.get("success")]
    return {
        "success": True,
        "dir": str(xml_dir),
        "total_files": len(xml_files),
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "results": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Import DECOR sample order from Word XML into local JSON DB")
    ap.add_argument("xml_file", nargs="?", default="", help="Path to XML file, e.g. docs/DECOR/3 canale 1HUUN.xml")
    ap.add_argument("--static-root", default="static", help="Static root dir (default: static)")
    ap.add_argument("--dir", default="", help="Bulk mode: import all *.xml in directory")
    args = ap.parse_args()

    if args.dir:
        result = import_xml_orders_from_dir(Path(args.dir), Path(args.static_root))
    else:
        if not args.xml_file:
            print({"success": False, "error": "xml_file or --dir is required"})
            return 1
        result = import_sample_order(Path(args.xml_file), Path(args.static_root))
    if result.get("success"):
        print(result)
        return 0
    print(result)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
