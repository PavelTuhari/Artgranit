import re

import pytest

from texflow import labels as L
from texflow.rules import make_ean13


def lb(**kw):
    d = dict(ean13=make_ean13("200", 7), sku="TSH0001-800-M", name="Футболка ^базовая~", color="Чёрный",
             size="M", price=179.9, currency="MDL", brand="Shop_1", composition="100% хлопок", copies=2)
    d.update(kw)
    return L.LabelData(**d)


def test_zpl_structure_and_copies():
    z = L.to_zpl([lb(), lb(size="L", copies=1)])
    assert z.count("^XA") == 2 and z.count("^XZ") == 2
    assert "^CI28" in z and "^PW463" in z and "^LL319" in z            # 58×40 мм при 203 dpi
    assert re.search(r"\^BEN,\d+,Y,N\^FD2000000000070\^FS".replace("0070", "007"), z)
    assert "^PQ2,0,1,N" in z and "^PQ1,0,1,N" in z
    assert "179.90 MDL" in z


def test_zpl_escaping_and_translit():
    z = L.to_zpl([lb()])
    assert "Futbolka _5Ebazovaya_7E" in z          # ^ и ~ не ломают команду
    assert "Shop_5F1".upper() in z                  # _ экранирован (бренд в верхнем регистре)
    assert "Футболка" not in z                      # без шрифта — латиница
    z2 = L.to_zpl([lb()], font="E:ARIAL.TTF")
    assert "Футболка" in z2 and "^A@N" in z2


def test_zpl_300dpi_scales():
    z = L.to_zpl([lb()], L.LabelLayout(58, 40, 2, 300))
    assert "^PW685" in z and "^BY3" in z


def test_tspl_structure():
    t = L.to_tspl([lb(name='Платье "Миди"')])
    assert t.startswith("SIZE 58 mm,40 mm\r\n")
    assert "GAP 2 mm,0 mm" in t and "CLS" in t and "CODEPAGE UTF-8" in t
    assert '"EAN13"' in t and ',"200000000007"' in t
    assert "PRINT 1,2" in t
    assert '\\["]' in t                             # кавычка экранирована
    assert "\r\n" in t and "\n" not in t.replace("\r\n", "")
    assert "Plat" in t and "Платье" not in t
    t2 = L.to_tspl([lb()], font="ARIAL.TTF")
    assert '"ARIAL.TTF"' in t2 and "Футболка" in t2


def test_invalid_ean_rejected():
    with pytest.raises(ValueError):
        L.to_zpl([lb(ean13="1234567890123")])
    with pytest.raises(ValueError):
        L.to_tspl([lb(ean13="123")])


def _pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


def test_pdf_a4_sheet_paging():
    one = L.to_pdf_sheet([lb(copies=24)])
    assert one.startswith(b"%PDF") and _pages(one) == 1
    two = L.to_pdf_sheet([lb(copies=25)])
    assert _pages(two) == 2
    # пропуск уже использованных ячеек
    assert _pages(L.to_pdf_sheet([lb(copies=4)], L.SheetLayout(start_cell=22))) == 2
    assert _pages(L.to_pdf_sheet([])) == 1


def test_pdf_roll_one_page_per_label():
    pdf = L.to_pdf_roll([lb(copies=3), lb(price=None, copies=1)])
    assert pdf.startswith(b"%PDF") and _pages(pdf) == 4
    assert b"/MediaBox [ 0 0 164.4094 113.3858 ]" in pdf     # 58×40 мм


def test_pdf_font_has_cyrillic_or_falls_back():
    reg, bold, uni = L.pdf_fonts()
    assert reg and bold
    assert isinstance(uni, bool)
