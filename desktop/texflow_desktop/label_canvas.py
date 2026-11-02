"""Рисование этикетки по шаблону на tk.Canvas (редактор и предпросмотр печати)."""
from __future__ import annotations

import tkinter.font as tkfont

from texflow import label_templates as LT

_fonts: dict = {}


def _font(px: int, bold: bool, root=None):
    """Шрифты кэшируются на окно: после закрытия окна (новое окно в том же процессе) — создаются заново."""
    key = (id(root), px, bold)
    f = _fonts.get(key)
    if f is not None:
        try:
            f.measure("x")
            return f
        except Exception:   # noqa: BLE001 — окно, которому принадлежал шрифт, уже закрыто
            pass
    _fonts[key] = tkfont.Font(root=root, family="Helvetica", size=-max(4, px), weight="bold" if bold else "normal")
    return _fonts[key]


def _clip(text: str, font, width: int) -> str:
    if font.measure(text) <= width:
        return text
    while text and font.measure(text + "…") > width:
        text = text[:-1]
    return text + "…"


def draw(canvas, tpl: LT.Template, lb, scale: float, ox: float = 10, oy: float = 10, tag: str = "label",
         element_tags: bool = False) -> None:
    """Нарисовать этикетку: scale — пикселей на мм, (ox, oy) — левый верхний угол."""
    W, H = tpl.width_mm * scale, tpl.height_mm * scale
    canvas.create_rectangle(ox + 3, oy + 3, ox + W + 3, oy + H + 3, fill="#d8d8d4", outline="", tags=(tag,))
    canvas.create_rectangle(ox, oy, ox + W, oy + H, fill="white", outline="#999999", tags=(tag,))
    X = lambda mm: ox + mm * scale  # noqa: E731
    Y = lambda mm: oy + mm * scale  # noqa: E731
    for idx, p in enumerate(LT.layout(tpl, lb)):
        tags = (tag, f"el{idx}") if element_tags else (tag,)
        if p["type"] == "text":
            f = _font(int(round(p["font"] * scale)), p["bold"], canvas.winfo_toplevel())
            w = int(p["w"] * scale)
            txt = _clip(p["text"], f, w)
            anchor, x = {"L": ("nw", X(p["x"])), "C": ("n", X(p["x"] + p["w"] / 2)),
                         "R": ("ne", X(p["x"] + p["w"]))}[p["align"]]
            canvas.create_text(x, Y(p["y"]), text=txt, anchor=anchor, font=f, fill="#111111", tags=tags)
        elif p["type"] == "rect":
            canvas.create_rectangle(X(p["x"]), Y(p["y"]), X(p["x"] + p["w"]), Y(p["y"] + p["h"]),
                                    width=max(1, p["t"] * scale), outline="#111111", tags=tags)
        elif p["type"] == "line":
            canvas.create_line(X(p["x1"]), Y(p["y1"]), X(p["x2"]), Y(p["y2"]), width=max(1, p["t"] * scale),
                               fill="#111111", tags=tags)
        elif p["type"] == "bars":
            mods = p["modules"]
            if not mods:
                canvas.create_rectangle(X(p["x"]), Y(p["y"]), X(p["x"] + p["w"]), Y(p["y"] + p["h"]),
                                        fill="#f3d6d6", outline="#b3202a", tags=tags)
                canvas.create_text(X(p["x"] + p["w"] / 2), Y(p["y"] + p["h"] / 2), text="?", fill="#b3202a",
                                   tags=tags)
                continue
            mw = p["w"] * scale / len(mods)
            run = 0
            for i, bit in enumerate(mods + "0"):
                if bit == "1":
                    run += 1
                elif run:
                    x0 = X(p["x"]) + (i - run) * mw
                    canvas.create_rectangle(x0, Y(p["y"]), x0 + run * mw, Y(p["y"] + p["h"]), fill="#111111",
                                            outline="", tags=tags)
                    run = 0
            cf = _font(max(6, int(p["caption_h"] * scale * 0.95)), False, canvas.winfo_toplevel())
            canvas.create_text(X(p["x"] + p["w"] / 2), Y(p["y"] + p["h"]), text=p["caption"], anchor="n",
                               font=cf, fill="#111111", tags=tags)
