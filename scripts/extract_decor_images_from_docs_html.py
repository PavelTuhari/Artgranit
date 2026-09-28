from __future__ import annotations

import html as html_lib
import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
DOCS_DECOR = ROOT / "docs" / "DECOR"
OUT_DIR = ROOT / "static" / "decor" / "materials_dochtml"
OUT_JSON = ROOT / "data" / "decor_material_images_docs_html.json"

HTML_FILES = [
    DOCS_DECOR / "Configurator2 Proiect Test UNA 1.html",
    DOCS_DECOR / "YENİ VERANDA ÜRETİM MALİYET HESAPLAMA.html",
]

TR_RE = re.compile(r"<tr\b.*?</tr>", re.I | re.S)
IMG_RE = re.compile(r'<img[^>]+src="([^"]+\.(?:png|jpg|jpeg|gif|webp))"', re.I)
TAG_RE = re.compile(r"<[^>]+>")
CODE_RE = re.compile(r"\b(?:[A-Z]{1,6}[.-]?[A-Z0-9]+(?:-[A-Z0-9]+)*|O\.\d{3,5}|\d{6,})\b")


def strip_html(text: str) -> str:
    s = TAG_RE.sub(" ", text)
    s = html_lib.unescape(s)
    return " ".join(s.split())


def code_candidates(plain: str) -> list[str]:
    out: list[str] = []
    for m in CODE_RE.finditer(plain):
        c = m.group(0).strip()
        if c in {"TR", "PC", "KG", "AD", "MTR", "TOTAL", "KOD", "REF"}:
            continue
        if c.startswith("#"):
            continue
        if not (re.search(r"\d", c) or "." in c or "-" in c):
            continue
        if c.replace(".", "", 1).isdigit():
            # keep long numeric article/model ids only
            if len(c) < 6:
                continue
        out.append(c)
    return list(dict.fromkeys(out))


def first_likely_name(plain: str, codes: list[str]) -> str:
    s = plain
    for c in codes:
        s = s.replace(c, " ")
    # prune obvious noise/numbers
    s = re.sub(r"\b\d+[.,]?\d*\b", " ", s)
    s = re.sub(r"#DIV/0!|#N/A|#REF!", " ", s, flags=re.I)
    s = re.sub(r"\b(?:CM|MTR|KG|AD|PC)\b", " ", s)
    s = " ".join(s.split())
    return s[:220].strip()


def slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower() or "doc"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    by_code: dict[str, dict] = {}
    rows: list[dict] = []
    copied: set[str] = set()

    for html_file in HTML_FILES:
        if not html_file.exists():
            continue
        text = html_file.read_text(encoding="utf-8", errors="ignore")
        for tr_idx, tr in enumerate(TR_RE.findall(text), start=1):
            img_match = IMG_RE.search(tr)
            if not img_match:
                continue
            img_rel_raw = img_match.group(1)
            img_rel = unquote(img_rel_raw)
            src_path = (html_file.parent / img_rel).resolve()
            if not src_path.exists():
                continue

            plain = strip_html(tr)
            codes = code_candidates(plain)
            if not codes:
                continue

            out_name = f"{slug(html_file.stem)}__{src_path.name.lower()}"
            out_path = OUT_DIR / out_name
            if out_name not in copied:
                shutil.copy2(src_path, out_path)
                copied.add(out_name)
            rel_url = f"/static/decor/materials_dochtml/{out_name}"

            row_meta = {
                "doc_file": html_file.name,
                "row_index": tr_idx,
                "codes": codes,
                "image_src": str(src_path),
                "url": rel_url,
                "text": plain,
                "name_hint": first_likely_name(plain, codes),
            }
            rows.append(row_meta)
            for code in codes:
                by_code.setdefault(code, row_meta)

    payload = {"by_code": by_code, "rows": rows}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {OUT_JSON} rows={len(rows)} codes={len(by_code)} files={len(copied)}")


if __name__ == "__main__":
    main()
