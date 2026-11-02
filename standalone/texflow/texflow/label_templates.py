"""Шаблоны этикеток: хранение в SQLite и отрисовка в ZPL, TSPL, PDF (лист A4 и рулон).

Шаблон = размер этикетки + список элементов. Координаты — в миллиметрах от левого
верхнего угла. Виды элементов:

* ``text``    — текст с подстановками полей: ``{name}``, ``{color} · {sku}``, ``{price}``;
* ``barcode`` — штрихкод EAN-13 (поле ean13) или CODE128 (текст с подстановками, обычно ``{sku}``);
* ``box``     — рамка; ``line`` — линия (горизонтальная, вертикальная или наклонная).

Тот же шаблон рисует редактор этикеток в нативном приложении (геометрия — ``layout()``),
поэтому предпросмотр совпадает с печатью.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field, asdict

from .labels import LabelData, SheetLayout, _expand, pdf_fonts
from .rules import translit, is_valid_ean13
from .i18n import _

MM_PER_INCH = 25.4
FIELDS = ("brand", "name", "color", "size", "price", "sku", "ean13", "style", "composition", "origin",
          "currency", "price_value")
KINDS = ("text", "barcode", "box", "line")


@dataclass
class Element:
    kind: str = "text"
    text: str = ""
    symbology: str = "EAN13"
    x_mm: float = 2
    y_mm: float = 2
    w_mm: float = 20
    h_mm: float = 5
    font_mm: float = 3
    bold: bool = False
    align: str = "L"
    thickness: float = 0.3
    id: int | None = None


@dataclass
class Template:
    name: str
    width_mm: float = 58
    height_mm: float = 40
    elements: list[Element] = field(default_factory=list)
    is_default: bool = False
    id: int | None = None


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def values(lb: LabelData) -> dict:
    return {"brand": lb.brand, "name": lb.name, "color": lb.color, "size": lb.size,
            "price": lb.price_text(), "price_value": "" if lb.price is None else f"{lb.price:.2f}",
            "currency": lb.currency, "sku": lb.sku, "ean13": lb.ean13, "style": lb.style,
            "composition": lb.composition, "origin": lb.origin}


def fill(text: str, lb: LabelData) -> str:
    try:
        return text.format_map(_Safe(values(lb)))
    except (ValueError, IndexError):
        return text


def sample_label() -> LabelData:
    """Образец данных для предпросмотра в редакторе."""
    return LabelData(ean13="2000000000015", sku="TSH0001-800-M", name="Футболка базовая оверсайз",
                     color="Чёрный", size="M", price=189.9, currency="MDL", brand="MY STORE",
                     style="TSH0001", composition="100% хлопок", origin="TR")


# ======================================================================= стандартные шаблоны

def default_templates() -> list[Template]:
    E = Element
    std = Template("Standard 58×40", 58, 40, is_default=True, elements=[
        E("text", "{brand}", x_mm=2, y_mm=2, w_mm=54, h_mm=3.5, font_mm=2.9, bold=True),
        E("text", "{name}", x_mm=2, y_mm=5.8, w_mm=54, h_mm=4.2, font_mm=3.8, bold=True),
        E("text", "{color}   {sku}", x_mm=2, y_mm=10.4, w_mm=54, h_mm=3.4, font_mm=2.9),
        E("box", x_mm=2, y_mm=14.3, w_mm=11, h_mm=7.4, thickness=0.3),
        E("text", "{size}", x_mm=2, y_mm=15, w_mm=11, h_mm=6, font_mm=5.6, bold=True, align="C"),
        E("text", "{price}", x_mm=14, y_mm=15, w_mm=42, h_mm=6, font_mm=5.6, bold=True, align="R"),
        E("barcode", "{ean13}", "EAN13", x_mm=12, y_mm=23.3, w_mm=34, h_mm=11),
        E("text", "{composition}", x_mm=2, y_mm=35.6, w_mm=54, h_mm=3, font_mm=2.6),
    ])
    mini = Template("Mini 40×30", 40, 30, elements=[
        E("text", "{name}", x_mm=1.5, y_mm=1.5, w_mm=37, h_mm=3.4, font_mm=3, bold=True),
        E("text", "{color} · {size}", x_mm=1.5, y_mm=5.3, w_mm=22, h_mm=3.4, font_mm=3),
        E("text", "{price}", x_mm=18, y_mm=5, w_mm=20.5, h_mm=4.2, font_mm=4, bold=True, align="R"),
        E("line", x_mm=1.5, y_mm=10, w_mm=37, h_mm=0, thickness=0.3),
        E("barcode", "{ean13}", "EAN13", x_mm=4, y_mm=11.5, w_mm=32, h_mm=14),
        E("text", "{sku}", x_mm=1.5, y_mm=26.5, w_mm=37, h_mm=2.6, font_mm=2.4, align="C"),
    ])
    price_tag = Template("SKU tag 58×30 (CODE128)", 58, 30, elements=[
        E("text", "{brand}", x_mm=2, y_mm=1.5, w_mm=54, h_mm=3, font_mm=2.6, bold=True, align="C"),
        E("text", "{name}", x_mm=2, y_mm=5, w_mm=54, h_mm=3.6, font_mm=3.4, align="C"),
        E("text", "{size}", x_mm=2, y_mm=9.5, w_mm=14, h_mm=6, font_mm=5.4, bold=True),
        E("text", "{price}", x_mm=16, y_mm=9.5, w_mm=40, h_mm=6, font_mm=5.4, bold=True, align="R"),
        E("barcode", "{sku}", "CODE128", x_mm=4, y_mm=17, w_mm=50, h_mm=11),
    ])
    return [std, mini, price_tag]


# ======================================================================= хранение

def seed(con) -> None:
    if con.execute("SELECT COUNT(*) FROM label_templates").fetchone()[0]:
        return
    for t in default_templates():
        save(con, t)


def list_templates(con) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT t.*, (SELECT COUNT(*) FROM label_template_elements e WHERE e.template_id = t.id) AS elements "
        "FROM label_templates t ORDER BY t.is_default DESC, t.name")]


def load(con, template_id: int | None = None) -> Template | None:
    if template_id:
        r = con.execute("SELECT * FROM label_templates WHERE id = ?", (template_id,)).fetchone()
    else:
        r = con.execute("SELECT * FROM label_templates ORDER BY is_default DESC, id LIMIT 1").fetchone()
    if not r:
        return None
    els = [Element(kind=e["kind"], text=e["text"], symbology=e["symbology"], x_mm=e["x_mm"], y_mm=e["y_mm"],
                   w_mm=e["w_mm"], h_mm=e["h_mm"], font_mm=e["font_mm"], bold=bool(e["bold"]), align=e["align"],
                   thickness=e["thickness"], id=e["id"])
           for e in con.execute("SELECT * FROM label_template_elements WHERE template_id = ? ORDER BY sort, id",
                                (r["id"],))]
    return Template(r["name"], r["width_mm"], r["height_mm"], els, bool(r["is_default"]), r["id"])


def validate(t: Template) -> None:
    if not t.name.strip():
        raise ValueError(_("У шаблона должно быть название"))
    if not (10 <= t.width_mm <= 220 and 10 <= t.height_mm <= 300):
        raise ValueError(_("Размер этикетки — от 10 до 220 × 300 мм"))
    for e in t.elements:
        if e.kind not in KINDS:
            raise ValueError(f"kind: {e.kind}")
        if e.align not in ("L", "C", "R"):
            raise ValueError(f"align: {e.align}")
        if e.symbology not in ("EAN13", "CODE128"):
            raise ValueError(f"symbology: {e.symbology}")


def save(con, t: Template) -> int:
    """Создать или полностью обновить шаблон (элементы перезаписываются)."""
    validate(t)
    if t.id:
        con.execute("UPDATE label_templates SET name = ?, width_mm = ?, height_mm = ? WHERE id = ?",
                    (t.name.strip(), t.width_mm, t.height_mm, t.id))
        con.execute("DELETE FROM label_template_elements WHERE template_id = ?", (t.id,))
        tid = t.id
    else:
        tid = con.execute("INSERT INTO label_templates(name, width_mm, height_mm) VALUES (?, ?, ?)",
                          (t.name.strip(), t.width_mm, t.height_mm)).lastrowid
    for i, e in enumerate(t.elements):
        con.execute("""INSERT INTO label_template_elements(template_id, sort, kind, text, symbology, x_mm, y_mm,
                       w_mm, h_mm, font_mm, bold, align, thickness) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (tid, i, e.kind, e.text, e.symbology, e.x_mm, e.y_mm, e.w_mm, e.h_mm, e.font_mm,
                     1 if e.bold else 0, e.align, e.thickness))
    if t.is_default:
        set_default(con, tid)
    con.commit()
    t.id = tid
    return tid


def set_default(con, tid: int) -> None:
    con.execute("UPDATE label_templates SET is_default = CASE WHEN id = ? THEN 1 ELSE 0 END", (tid,))
    con.commit()


def delete(con, tid: int) -> None:
    if con.execute("SELECT COUNT(*) FROM label_templates").fetchone()[0] <= 1:
        raise ValueError(_("Нельзя удалить последний шаблон"))
    was_default = con.execute("SELECT is_default FROM label_templates WHERE id = ?", (tid,)).fetchone()
    con.execute("DELETE FROM label_templates WHERE id = ?", (tid,))
    if was_default and was_default[0]:
        first = con.execute("SELECT id FROM label_templates ORDER BY id LIMIT 1").fetchone()[0]
        set_default(con, first)
    con.commit()


def duplicate(con, tid: int, new_name: str) -> int:
    t = load(con, tid)
    t.id, t.name, t.is_default = None, new_name, False
    for e in t.elements:
        e.id = None
    return save(con, t)


def to_dict(t: Template) -> dict:
    return asdict(t)


def from_dict(d: dict) -> Template:
    els = [Element(**{k: v for k, v in e.items() if k in Element.__dataclass_fields__}) for e in d.get("elements", [])]
    return Template(d["name"], float(d.get("width_mm", 58)), float(d.get("height_mm", 40)), els,
                    bool(d.get("is_default")), d.get("id"))


# ======================================================================= штрихкоды

_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
_G = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"]
_R = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"]
_PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def ean13_modules(code: str) -> str:
    """95 модулей EAN-13 ('1' — чёрный). Нужна для предпросмотра без внешних библиотек."""
    if not is_valid_ean13(code):
        raise ValueError(_("неверный EAN-13: {code}", code=code))
    d = [int(c) for c in code]
    par = _PARITY[d[0]]
    left = "".join((_L if par[i] == "L" else _G)[d[i + 1]] for i in range(6))
    right = "".join(_R[d[i]] for i in range(7, 13))
    return "101" + left + "01010" + right + "101"


# Code 128 B: шаблоны ширин полос/пробелов (код 0..106)
_C128 = ("212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 "
         "122231 113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 "
         "322112 322211 212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 "
         "112133 112331 132131 113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 "
         "331121 312113 312311 332111 314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 "
         "112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 111242 121142 121241 114212 "
         "124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 114311 411113 "
         "411311 113141 114131 311141 411131 211412 211214 211232 2331112").split()


def code128_modules(text: str) -> str:
    """Модули Code 128 (набор B, печатные ASCII) — для предпросмотра."""
    text = "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in translit(text)) or " "
    codes = [104] + [ord(c) - 32 for c in text]
    check = (104 + sum(i * c for i, c in enumerate(codes[1:], 1))) % 103
    out = []
    for c in codes + [check, 106]:
        for i, w in enumerate(_C128[c]):
            out.append(("1" if i % 2 == 0 else "0") * int(w))
    return "".join(out)


# ======================================================================= геометрия (редактор, PDF)

def layout(t: Template, lb: LabelData) -> list[dict]:
    """Готовые к рисованию примитивы в мм: text / rect / line / bars."""
    out = []
    for e in t.elements:
        if e.kind == "text":
            out.append({"type": "text", "x": e.x_mm, "y": e.y_mm, "w": e.w_mm, "h": e.h_mm,
                        "text": fill(e.text, lb), "font": e.font_mm, "bold": e.bold, "align": e.align})
        elif e.kind == "box":
            out.append({"type": "rect", "x": e.x_mm, "y": e.y_mm, "w": e.w_mm, "h": e.h_mm, "t": e.thickness})
        elif e.kind == "line":
            out.append({"type": "line", "x1": e.x_mm, "y1": e.y_mm, "x2": e.x_mm + e.w_mm, "y2": e.y_mm + e.h_mm,
                        "t": e.thickness})
        elif e.kind == "barcode":
            value = fill(e.text or "{ean13}", lb)
            try:
                mods = ean13_modules(value) if e.symbology == "EAN13" else code128_modules(value)
            except ValueError:
                mods = ""
            text_h = min(2.6, e.h_mm * 0.25)
            out.append({"type": "bars", "x": e.x_mm, "y": e.y_mm, "w": e.w_mm, "h": e.h_mm - text_h,
                        "modules": mods, "caption": value, "caption_h": text_h, "symbology": e.symbology})
    return out


# ======================================================================= PDF

def _fit(c, text, font, size, width):
    if c.stringWidth(text, font, size) <= width:
        return text
    while text and c.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text + "…"


def _draw(c, t: Template, lb: LabelData, ox: float, oy: float, fonts, border: bool = False):
    """Нарисовать этикетку на canvas reportlab; (ox, oy) — левый нижний угол в pt."""
    from reportlab.lib.units import mm
    reg, bold_f, uni = fonts
    T = (lambda s: s) if uni else translit
    H = t.height_mm * mm
    if border:
        c.setLineWidth(0.3); c.setStrokeGray(0.7)
        c.rect(ox, oy, t.width_mm * mm, H)
    c.setStrokeGray(0); c.setFillGray(0)
    for p in layout(t, lb):
        if p["type"] == "text":
            font = bold_f if p["bold"] else reg
            size = p["font"] * mm
            x, w = ox + p["x"] * mm, p["w"] * mm
            base = oy + H - (p["y"] * mm) - size * 0.82
            txt = _fit(c, T(p["text"]), font, size, w)
            c.setFont(font, size)
            if p["align"] == "C":
                c.drawCentredString(x + w / 2, base, txt)
            elif p["align"] == "R":
                c.drawRightString(x + w, base, txt)
            else:
                c.drawString(x, base, txt)
        elif p["type"] == "rect":
            c.setLineWidth(p["t"] * mm)
            c.rect(ox + p["x"] * mm, oy + H - (p["y"] + p["h"]) * mm, p["w"] * mm, p["h"] * mm)
        elif p["type"] == "line":
            c.setLineWidth(p["t"] * mm)
            c.line(ox + p["x1"] * mm, oy + H - p["y1"] * mm, ox + p["x2"] * mm, oy + H - p["y2"] * mm)
        elif p["type"] == "bars" and p["modules"]:
            n = len(p["modules"])
            mw = p["w"] * mm / n
            top = oy + H - p["y"] * mm
            bh = p["h"] * mm
            run = 0
            for i, bit in enumerate(p["modules"] + "0"):
                if bit == "1":
                    run += 1
                elif run:
                    c.rect(ox + p["x"] * mm + (i - run) * mw, top - bh, run * mw, bh, stroke=0, fill=1)
                    run = 0
            c.setFont("Helvetica", max(4, p["caption_h"] * mm * 0.95))
            c.drawCentredString(ox + (p["x"] + p["w"] / 2) * mm, top - bh - p["caption_h"] * mm * 0.85,
                                T(p["caption"]))


def to_pdf_roll(t: Template, labels: list[LabelData]) -> bytes:
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    fonts = pdf_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(t.width_mm * mm, t.height_mm * mm))
    c.setTitle(f"TexFlow — {t.name}")
    for lb in _expand(labels) or [sample_label()]:
        _draw(c, t, lb, 0, 0, fonts)
        c.showPage()
    c.save()
    return buf.getvalue()


def to_pdf_sheet(t: Template, labels: list[LabelData], sheet: SheetLayout | None = None) -> bytes:
    """Лист A4: ячейки сетки берутся из настроек листа, этикетка центрируется в ячейке."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    s = sheet or SheetLayout()
    fonts = pdf_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"TexFlow — {t.name} (A4)")
    _pw, ph = A4
    per = s.cols * s.rows
    cell = max(0, min(s.start_cell, per - 1))
    items = _expand(labels)
    for lb in items:
        if cell == per:
            c.showPage(); cell = 0
        col, row = cell % s.cols, cell // s.cols
        cx = (s.margin_left_mm + col * (s.label_w_mm + s.gap_x_mm)) * mm
        cy = ph - (s.margin_top_mm + (row + 1) * s.label_h_mm + row * s.gap_y_mm) * mm
        if s.border:
            c.setLineWidth(0.3); c.setStrokeGray(0.7)
            c.rect(cx, cy, s.label_w_mm * mm, s.label_h_mm * mm)
        scale = min(1.0, s.label_w_mm / t.width_mm, s.label_h_mm / t.height_mm)
        c.saveState()
        c.translate(cx + (s.label_w_mm * mm - t.width_mm * mm * scale) / 2,
                    cy + (s.label_h_mm * mm - t.height_mm * mm * scale) / 2)
        c.scale(scale, scale)
        _draw(c, t, lb, 0, 0, fonts)
        c.restoreState()
        cell += 1
    c.showPage(); c.save()
    return buf.getvalue()


# ======================================================================= ZPL

def _zpl_esc(s: str) -> str:
    return s.replace("_", "_5F").replace("^", "_5E").replace("~", "_7E")


def to_zpl(t: Template, labels: list[LabelData], dpi: int = 203, font: str = "",
           transliterate: bool | None = None) -> str:
    k = dpi / MM_PER_INCH
    d = lambda v: max(0, int(round(v * k)))  # noqa: E731
    tr = (not font) if transliterate is None else transliterate
    out = []
    for lb in labels:
        z = ["^XA", "^CI28", f"^PW{d(t.width_mm)}", f"^LL{d(t.height_mm)}", "^LH0,0"]
        for e in t.elements:
            if e.kind == "text":
                txt = fill(e.text, lb)
                txt = _zpl_esc(translit(txt) if tr else txt)
                h = max(10, d(e.font_mm))
                f = f"^A@N,{h},{h},{font}" if font else f"^A0N,{h},{h}"
                z.append(f"^FO{d(e.x_mm)},{d(e.y_mm)}{f}^FB{max(1, d(e.w_mm))},1,0,{e.align}^FH^FD{txt}^FS")
                if e.bold:   # у шрифта 0 нет жирного начертания — второй проход со сдвигом на точку
                    z.append(f"^FO{d(e.x_mm) + 1},{d(e.y_mm)}{f}^FB{max(1, d(e.w_mm))},1,0,{e.align}^FH^FD{txt}^FS")
            elif e.kind == "box":
                z.append(f"^FO{d(e.x_mm)},{d(e.y_mm)}^GB{max(1, d(e.w_mm))},{max(1, d(e.h_mm))},"
                         f"{max(1, d(e.thickness))}^FS")
            elif e.kind == "line":
                th = max(1, d(e.thickness))
                if abs(e.h_mm) < 0.01 or abs(e.w_mm) < 0.01:
                    z.append(f"^FO{d(e.x_mm)},{d(e.y_mm)}^GB{max(th, d(e.w_mm))},{max(th, d(e.h_mm))},{th}^FS")
                else:
                    z.append(f"^FO{d(e.x_mm)},{d(e.y_mm)}^GD{d(abs(e.w_mm))},{d(abs(e.h_mm))},{th},B,"
                             f"{'R' if e.h_mm > 0 else 'L'}^FS")
            elif e.kind == "barcode":
                value = fill(e.text or "{ean13}", lb)
                text_h = d(min(2.6, e.h_mm * 0.25))
                bh = max(10, d(e.h_mm) - text_h)
                if e.symbology == "EAN13":
                    if not is_valid_ean13(value):
                        raise ValueError(_("неверный EAN-13: {code}", code=value))
                    mod = max(1, d(e.w_mm) // 113)
                    z.append(f"^BY{mod},3,{bh}^FO{d(e.x_mm)},{d(e.y_mm)}^BEN,{bh},Y,N^FD{value[:12]}^FS")
                else:
                    mod = max(1, d(e.w_mm) // max(1, len(code128_modules(value))))
                    z.append(f"^BY{mod},3,{bh}^FO{d(e.x_mm)},{d(e.y_mm)}^BCN,{bh},Y,N,N^FD"
                             f"{_zpl_esc(translit(value))}^FS")
        z.append(f"^PQ{max(1, int(lb.copies))},0,1,N")
        z.append("^XZ")
        out.append("\n".join(z))
    return "\n".join(out) + "\n"


# ======================================================================= TSPL

_TSPL_BUILTIN = [("1", 12, 8), ("2", 20, 12), ("3", 24, 16), ("4", 32, 24), ("5", 48, 32)]  # (шрифт, высота, ширина) @203


def to_tspl(t: Template, labels: list[LabelData], dpi: int = 203, gap_mm: float = 2, font: str = "",
            transliterate: bool | None = None) -> str:
    k = dpi / MM_PER_INCH
    d = lambda v: max(0, int(round(v * k)))  # noqa: E731
    tr = (not font) if transliterate is None else transliterate
    scale = dpi / 203.0
    out = []
    for lb in labels:
        cmd = [f"SIZE {t.width_mm:g} mm,{t.height_mm:g} mm", f"GAP {gap_mm:g} mm,0 mm", "DIRECTION 1",
               "REFERENCE 0,0", "CODEPAGE UTF-8", "SET TEAR ON", "CLS"]
        for e in t.elements:
            if e.kind == "text":
                txt = fill(e.text, lb)
                txt = (translit(txt) if tr else txt).replace('"', '\\["]')
                x, y, w = d(e.x_mm), d(e.y_mm), d(e.w_mm)
                if font:
                    pt = max(4, round(e.font_mm / 0.3528))
                    al = {"L": 1, "C": 2, "R": 3}[e.align]
                    ax = {"L": x, "C": x + w // 2, "R": x + w}[e.align]
                    cmd.append(f'TEXT {ax},{y},"{font}",0,{pt},{pt},{al},"{txt}"')
                else:
                    want = d(e.font_mm)
                    name, fh, fw = min(_TSPL_BUILTIN, key=lambda f: abs(f[1] * scale - want))
                    cw = int(fw * scale)
                    maxc = max(1, w // max(1, cw))
                    txt = txt if len(txt) <= maxc else txt[:max(1, maxc - 1)] + "~"
                    tw = len(txt) * cw
                    ax = {"L": x, "C": x + (w - tw) // 2, "R": x + w - tw}[e.align]
                    cmd.append(f'TEXT {max(0, ax)},{y},"{name}",0,1,1,"{txt}"')
            elif e.kind == "box":
                cmd.append(f"BOX {d(e.x_mm)},{d(e.y_mm)},{d(e.x_mm + e.w_mm)},{d(e.y_mm + e.h_mm)},"
                           f"{max(1, d(e.thickness))}")
            elif e.kind == "line":
                th = max(1, d(e.thickness))
                if abs(e.h_mm) < 0.01:
                    cmd.append(f"BAR {d(e.x_mm)},{d(e.y_mm)},{max(1, d(e.w_mm))},{th}")
                elif abs(e.w_mm) < 0.01:
                    cmd.append(f"BAR {d(e.x_mm)},{d(e.y_mm)},{th},{max(1, d(e.h_mm))}")
                else:   # в TSPL нет наклонной линии в общем виде — рисуем прямой угол по контуру
                    cmd.append(f"BAR {d(e.x_mm)},{d(e.y_mm)},{max(1, d(e.w_mm))},{th}")
            elif e.kind == "barcode":
                value = fill(e.text or "{ean13}", lb)
                text_h = d(min(2.6, e.h_mm * 0.25))
                bh = max(10, d(e.h_mm) - text_h)
                if e.symbology == "EAN13":
                    if not is_valid_ean13(value):
                        raise ValueError(_("неверный EAN-13: {code}", code=value))
                    mod = max(1, d(e.w_mm) // 113)
                    cmd.append(f'BARCODE {d(e.x_mm)},{d(e.y_mm)},"EAN13",{bh},1,0,{mod},{mod},"{value[:12]}"')
                else:
                    mod = max(1, d(e.w_mm) // max(1, len(code128_modules(value))))
                    cmd.append(f'BARCODE {d(e.x_mm)},{d(e.y_mm)},"128",{bh},1,0,{mod},{mod},"{translit(value)}"')
        cmd.append(f"PRINT 1,{max(1, int(lb.copies))}")
        out.append("\r\n".join(cmd))
    return "\r\n".join(out) + "\r\n"


def render(con_settings: dict, t: Template, labels: list[LabelData], fmt: str, sheet: SheetLayout | None = None):
    """(данные, расширение, mime) для формата pdf_a4 | pdf_roll | zpl | tspl."""
    dpi = int(float(con_settings.get("label_dpi", 203) or 203))
    if fmt == "zpl":
        return to_zpl(t, labels, dpi, con_settings.get("zpl_font", "")).encode("utf-8"), "zpl", "text/plain"
    if fmt == "tspl":
        return (to_tspl(t, labels, dpi, float(con_settings.get("label_gap_mm", 2) or 2),
                        con_settings.get("tspl_font", "")).encode("utf-8"), "tspl", "text/plain")
    if fmt == "pdf_roll":
        return to_pdf_roll(t, labels), "pdf", "application/pdf"
    return to_pdf_sheet(t, labels, sheet), "pdf", "application/pdf"
