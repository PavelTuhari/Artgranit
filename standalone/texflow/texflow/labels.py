"""Этикетки: ZPL (Zebra), TSPL (TSC) и PDF (A4-лист или рулон для виртуального принтера).

Одни данные этикетки (LabelData) → три выхода. Модуль не знает о БД.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass

from .rules import translit, is_valid_ean13

MM_PER_INCH = 25.4


@dataclass
class LabelData:
    ean13: str
    sku: str
    name: str
    color: str
    size: str
    price: float | None
    currency: str = "MDL"
    brand: str = ""
    style: str = ""
    composition: str = ""
    origin: str = ""
    copies: int = 1
    ref: int = 0                   # id варианта в базе (для UI)

    def price_text(self) -> str:
        if self.price is None:
            return ""
        return f"{self.price:,.2f}".replace(",", " ") + f" {self.currency}"


@dataclass
class LabelLayout:
    width_mm: float = 58.0
    height_mm: float = 40.0
    gap_mm: float = 2.0
    dpi: int = 203                 # 203 / 300 / 600


def _clip(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


# ======================================================================= ZPL

def _zpl_escape(text: str) -> str:
    # ^FH: «_» — префикс шестнадцатеричного кода, поэтому экранируем _ ^ ~
    return (text.replace("_", "_5F").replace("^", "_5E").replace("~", "_7E"))


def to_zpl(labels: list[LabelData], layout: LabelLayout | None = None,
           font: str = "", transliterate: bool | None = None) -> str:
    """ZPL II для Zebra (GK420, ZD220/ZD420/ZT230 и совместимых).

    font — имя TTF-шрифта на принтере для кириллицы (например
    ``E:ARIAL.TTF``); без него текст переводится в латиницу.
    """
    lay = layout or LabelLayout()
    k = lay.dpi / MM_PER_INCH
    W, H = int(lay.width_mm * k), int(lay.height_mm * k)
    tr = (not font) if transliterate is None else transliterate

    def txt(s: str) -> str:
        s = translit(s) if tr else s
        return _zpl_escape(s)

    def fnt(h: int) -> str:
        return f"^A@N,{h},{h},{font}" if font else f"^A0N,{h},{h}"

    m = int(2 * k)                                  # поле 2 мм
    small, mid, big = int(H * .075), int(H * .10), int(H * .17)
    mod = 2 if lay.dpi < 300 else 3                 # ширина модуля штрихкода
    bar_h = int(H * .20)
    out = []
    for lb in labels:
        if not is_valid_ean13(lb.ean13):
            raise ValueError(f"неверный EAN-13: {lb.ean13}")
        y = m
        z = ["^XA", "^CI28", f"^PW{W}", f"^LL{H}", "^LH0,0"]
        if lb.brand:
            z.append(f"^FO{m},{y}{fnt(small)}^FH^FD{txt(lb.brand.upper())}^FS")
            y += small + int(k)
        z.append(f"^FO{m},{y}{fnt(mid)}^FB{W - 2 * m},1,0,L^FH^FD{txt(_clip(lb.name, 32))}^FS")
        y += mid + int(k)
        z.append(f"^FO{m},{y}{fnt(small)}^FH^FD{txt(_clip(lb.color, 22))}  {txt(lb.sku)}^FS")
        y += small + int(1.5 * k)
        # размер — крупно слева, цена — крупно справа
        z.append(f"^FO{m},{y}^GB{int(big * 1.6)},{big + 6},2^FS")
        z.append(f"^FO{m + 4},{y + 4}{fnt(big)}^FB{int(big * 1.6) - 8},1,0,C^FH^FD{txt(lb.size)}^FS")
        if lb.price is not None:
            z.append(f"^FO{m + int(big * 1.8)},{y + 4}{fnt(big)}^FB{W - 2 * m - int(big * 1.8)},1,0,R"
                     f"^FH^FD{txt(lb.price_text())}^FS")
        y += big + int(2.5 * k)
        bx = max(m, (W - (95 + 22) * mod) // 2)
        z.append(f"^BY{mod},3,{bar_h}^FO{bx},{y}^BEN,{bar_h},Y,N^FD{lb.ean13[:12]}^FS")
        if lb.composition:
            z.append(f"^FO{m},{H - small - m}{fnt(small)}^FB{W - 2 * m},1,0,L"
                     f"^FH^FD{txt(_clip(lb.composition, 40))}^FS")
        z.append(f"^PQ{max(1, int(lb.copies))},0,1,N")
        z.append("^XZ")
        out.append("\n".join(z))
    return "\n".join(out) + "\n"


# ====================================================================== TSPL

def _tspl_escape(text: str) -> str:
    return text.replace('"', '\\["]')


def to_tspl(labels: list[LabelData], layout: LabelLayout | None = None,
            font: str = "", transliterate: bool | None = None) -> str:
    """TSPL/TSPL2 для TSC (TE200/TE210/TE300, TTP-244, DA200 и совместимых).

    font — имя TTF, загруженного в принтер (например ``ARIAL.TTF``) для
    кириллицы с ``CODEPAGE UTF-8``; без него — встроенный шрифт и латиница.
    """
    lay = layout or LabelLayout()
    k = lay.dpi / MM_PER_INCH
    W, H = int(lay.width_mm * k), int(lay.height_mm * k)
    tr = (not font) if transliterate is None else transliterate
    m = int(2 * k)
    mod = 2 if lay.dpi < 300 else 3
    bar_h = int(H * .24)

    def text(x, y, s, size):
        s = _tspl_escape(translit(s) if tr else s)
        if font:  # TTF: размер в пунктах
            return f'TEXT {x},{y},"{font}",0,{size},{size},"{s}"'
        builtin = {8: "2", 10: "3", 14: "4", 20: "5"}.get(size, "3")
        return f'TEXT {x},{y},"{builtin}",0,1,1,"{s}"'

    out = []
    for lb in labels:
        if not is_valid_ean13(lb.ean13):
            raise ValueError(f"неверный EAN-13: {lb.ean13}")
        y = m
        t = [f"SIZE {lay.width_mm:g} mm,{lay.height_mm:g} mm",
             f"GAP {lay.gap_mm:g} mm,0 mm", "DIRECTION 1", "REFERENCE 0,0",
             "CODEPAGE UTF-8", "SET TEAR ON", "CLS"]
        if lb.brand:
            t.append(text(m, y, lb.brand.upper(), 8)); y += int(3.5 * k)
        t.append(text(m, y, _clip(lb.name, 30), 10)); y += int(4.5 * k)
        t.append(text(m, y, f"{_clip(lb.color, 20)}  {lb.sku}", 8)); y += int(4 * k)
        box = int(11 * k)
        t.append(f"BOX {m},{y},{m + box},{y + int(7 * k)},2")
        t.append(text(m + int(1.5 * k), y + int(1 * k), lb.size, 20))
        if lb.price is not None:
            t.append(text(m + box + int(3 * k), y + int(1 * k), lb.price_text(), 20))
        y += int(9 * k)
        t.append(f'BARCODE {m + int(4 * k)},{y},"EAN13",{bar_h},1,0,{mod},{mod},"{lb.ean13[:12]}"')
        if lb.composition:
            t.append(text(m, H - int(4 * k), _clip(lb.composition, 40), 8))
        t.append(f"PRINT 1,{max(1, int(lb.copies))}")
        out.append("\n".join(t))
    return "\r\n".join("\n".join(out).split("\n")) + "\r\n"


# ======================================================================= PDF

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
_fonts: tuple[str, str, bool] | None = None


def pdf_fonts() -> tuple[str, str, bool]:
    """(обычный, жирный, есть_юникод). Ищет системный TTF с кириллицей."""
    global _fonts
    if _fonts:
        return _fonts
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    env = os.environ.get("TEXFLOW_PDF_FONT")
    reg = next((p for p in ([env] if env else []) + _FONT_CANDIDATES if p and os.path.exists(p)), None)
    bold = next((p for p in _BOLD_CANDIDATES if os.path.exists(p)), None) or reg
    if reg:
        pdfmetrics.registerFont(TTFont("TF-Regular", reg))
        pdfmetrics.registerFont(TTFont("TF-Bold", bold))
        _fonts = ("TF-Regular", "TF-Bold", True)
    else:
        _fonts = ("Helvetica", "Helvetica-Bold", False)
    return _fonts


@dataclass
class SheetLayout:
    """Лист A4 с сеткой самоклеящихся этикеток (по умолчанию 3×8, 70×37 мм)."""
    cols: int = 3
    rows: int = 8
    label_w_mm: float = 70.0
    label_h_mm: float = 37.0
    margin_left_mm: float = 0.0
    margin_top_mm: float = 0.5
    gap_x_mm: float = 0.0
    gap_y_mm: float = 0.0
    border: bool = True
    start_cell: int = 0            # пропустить уже использованные ячейки листа


def _draw_label(c, x, y, w, h, lb: LabelData, fonts, border: bool):
    from reportlab.lib.units import mm
    from reportlab.graphics.barcode import eanbc
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF

    reg, bold, uni = fonts
    T = (lambda s: s) if uni else translit
    if border:
        c.setLineWidth(0.3); c.setStrokeGray(0.7)
        c.rect(x, y, w, h)
    pad = 2 * mm
    fs_small = max(5.5, h / mm * 0.19)
    fs_mid = max(7, h / mm * 0.24)
    fs_big = max(10, h / mm * 0.38)
    cy = y + h - pad - fs_small
    c.setFillGray(0)
    if lb.brand:
        c.setFont(bold, fs_small); c.drawString(x + pad, cy, T(lb.brand.upper()))
        cy -= fs_mid + 1
    c.setFont(bold, fs_mid)
    c.drawString(x + pad, cy, T(_clip(lb.name, int(w / mm * 0.85))))
    cy -= fs_small + 2
    c.setFont(reg, fs_small)
    c.drawString(x + pad, cy, T(f"{_clip(lb.color, 22)}   {lb.sku}"))
    # размер в рамке + цена
    cy -= fs_big + 4
    box_w = max(c.stringWidth(lb.size, bold, fs_big) + 3 * mm, 10 * mm)
    c.rect(x + pad, cy - 1.2 * mm, box_w, fs_big + 1.6 * mm)
    c.setFont(bold, fs_big)
    c.drawCentredString(x + pad + box_w / 2, cy, T(lb.size))
    if lb.price is not None:
        c.drawRightString(x + w - pad, cy, lb.price_text())
    # штрихкод
    bar_h = max(6 * mm, h * 0.28)
    bc = eanbc.Ean13BarcodeWidget(lb.ean13[:12])
    bc.barHeight = bar_h
    bc.fontName = "Helvetica"
    bc.fontSize = max(6, fs_small)
    bx0, by0, bx1, by1 = bc.getBounds()
    bw = bx1 - bx0
    scale = min(1.0, (w - 2 * pad) / bw)
    d = Drawing(bw * scale, (by1 - by0) * scale)
    d.add(bc)
    d.scale(scale, scale)
    bot = y + pad + (fs_small + 1 if lb.composition else 0)
    renderPDF.draw(d, c, x + (w - bw * scale) / 2, bot)
    if lb.composition:
        c.setFont(reg, fs_small * 0.9)
        c.drawString(x + pad, y + pad * 0.6, T(_clip(lb.composition, int(w / mm))))


def _expand(labels: list[LabelData]) -> list[LabelData]:
    return [lb for lb in labels for _ in range(max(1, int(lb.copies)))]


def to_pdf_sheet(labels: list[LabelData], sheet: SheetLayout | None = None) -> bytes:
    """A4-лист для обычного лазерного/струйного принтера."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    s = sheet or SheetLayout()
    fonts = pdf_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("TexFlow labels A4")
    pw, ph = A4
    per_page = s.cols * s.rows
    cell = max(0, min(s.start_cell, per_page - 1))
    items = _expand(labels)
    for i, lb in enumerate(items):
        if cell == per_page:
            c.showPage(); cell = 0
        col, row = cell % s.cols, cell // s.cols
        x = (s.margin_left_mm + col * (s.label_w_mm + s.gap_x_mm)) * mm
        y = ph - (s.margin_top_mm + (row + 1) * s.label_h_mm + row * s.gap_y_mm) * mm
        _draw_label(c, x, y, s.label_w_mm * mm, s.label_h_mm * mm, lb, fonts, s.border)
        cell += 1
    if not items:
        c.setFont(fonts[0], 12); c.drawString(20 * mm, ph - 20 * mm, "Нет этикеток" if fonts[2] else "No labels")
    c.showPage(); c.save()
    return buf.getvalue()


def to_pdf_roll(labels: list[LabelData], layout: LabelLayout | None = None) -> bytes:
    """PDF «страница = этикетка» для виртуального принтера или печати на
    термопринтере через обычный драйвер Windows/macOS/CUPS."""
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    lay = layout or LabelLayout()
    fonts = pdf_fonts()
    w, h = lay.width_mm * mm, lay.height_mm * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setTitle("TexFlow labels roll")
    for lb in _expand(labels):
        _draw_label(c, 0, 0, w, h, lb, fonts, border=False)
        c.showPage()
    c.save()
    return buf.getvalue()
