"""Autopark — конструктор деловых книг Excel с элементами BI.

Слой без бизнес-логики: он не знает ни про рейсы, ни про аудит. Умеет
одно — собирать лист, который не стыдно открыть на совете директоров:
шапка, плитки показателей, таблица с фильтром, светофор, диаграмма,
выпадающий список-срез.

Почему «элементы BI», а не просто выгрузка. Обычный экспорт — снимок:
открыл, посмотрел, закрыл. Здесь книга остаётся живой:

  * лист «Куб» — плоская таблица фактов с измерениями (месяц, регион,
    продукт) и мерами; на неё ссылаются все показатели;
  * срезы — выпадающие списки (`DataValidation`) на листе панели;
  * показатели — формулы `SUMIFS`, которые читают срез из ячейки, а не
    посчитанное число из Python;
  * диаграммы построены на диапазонах формул.

Следствие: пользователь меняет месяц в выпадающем списке — и вся панель
пересчитывается в самом Excel, без нас. Если бы Python записал готовые
числа, книга умирала бы в момент сохранения.

Ограничение, выбранное сознательно: только функции уровня Excel 2007
(`SUMIFS`, `INDEX`, `MATCH`, `IFERROR`, `COUNTIFS`). Современные
`XLOOKUP`/`FILTER`/`UNIQUE` — формулы с «разливом» массива, а книга,
записанная openpyxl, не несёт метаданных разлива: в файле окажется одно
значение вместо столбца, причём без единой ошибки при проверке. Ошибка,
которую не видно при проверке, хуже отсутствующей возможности.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from openpyxl.chart import BarChart, DoughnutChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

# ── Палитра ─────────────────────────────────────────────────────────────
# Палитра проекта (та же, что в пакете отчётности и в презентации).
# Фирменные цвета аудиторских компаний здесь сознательно не используются:
# формат отчёта заимствован, принадлежность — нет.

NAVY = "132038"
ACCENT = "1D4ED8"
INK = "1F2937"
MUTED = "6B7280"
LINE = "D7DDE5"
BAND = "F5F7FA"
WHITE = "FFFFFF"

OK_TEXT, OK_FILL = "0F7B4F", "D8F0E5"
WARN_TEXT, WARN_FILL = "9A5B00", "FCEBD2"
BAD_TEXT, BAD_FILL = "A8261E", "F8D8D5"
NA_TEXT, NA_FILL = "5A6472", "E9ECF1"

FONT = "Arial"

NUM0 = "# ##0"
NUM1 = "# ##0.0"
NUM2 = "# ##0.00"
PCT = "0.0%"
PCT2 = "0.00%"
LEI = '# ##0.00" лей"'

THIN = Side(style="thin", color=LINE)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def f(size: int = 10, *, bold: bool = False, color: str = INK,
      italic: bool = False) -> Font:
    return Font(name=FONT, size=size, bold=bold, color=color, italic=italic)


def fill(color: str) -> PatternFill:
    return PatternFill("solid", fgColor=color)


def center(wrap: bool = False) -> Alignment:
    return Alignment(horizontal="center", vertical="center", wrap_text=wrap)


def left(wrap: bool = True, indent: int = 0) -> Alignment:
    return Alignment(horizontal="left", vertical="top", wrap_text=wrap,
                     indent=indent)


RATING_STYLE = {
    "Эффективен": (OK_TEXT, OK_FILL),
    "Требует улучшения": (WARN_TEXT, WARN_FILL),
    "Неэффективен": (BAD_TEXT, BAD_FILL),
    "Не тестировался": (NA_TEXT, NA_FILL),
    "Без отклонений": (OK_TEXT, OK_FILL),
    "Отклонения": (BAD_TEXT, BAD_FILL),
    "Высокий": (BAD_TEXT, BAD_FILL),
    "Средний": (WARN_TEXT, WARN_FILL),
    "Низкий": (OK_TEXT, OK_FILL),
}


# ── Каркас листа ────────────────────────────────────────────────────────

def prepare(ws: Worksheet, widths: Sequence[float], *,
            grid: bool = False, zoom: int = 100) -> None:
    """Ширины колонок, сетка и масштаб — один раз на лист."""
    ws.sheet_view.showGridLines = grid
    ws.sheet_view.zoomScale = zoom
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def banner(ws: Worksheet, row: int, last_col: int, title: str,
           subtitle: str = "", *, height: int = 34) -> int:
    """Тёмная полоса-заголовок раздела. Возвращает следующую строку."""
    ws.merge_cells(start_row=row, start_column=1,
                   end_row=row, end_column=last_col)
    cell = ws.cell(row=row, column=1, value=title)
    cell.font = f(13, bold=True, color=WHITE)
    cell.fill = fill(NAVY)
    cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = height
    row += 1
    if subtitle:
        ws.merge_cells(start_row=row, start_column=1,
                       end_row=row, end_column=last_col)
        sub = ws.cell(row=row, column=1, value=subtitle)
        sub.font = f(9, color=MUTED, italic=True)
        sub.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[row].height = 20
        row += 1
    return row + 1


def kpi_tiles(ws: Worksheet, row: int, tiles: Sequence[Dict[str, Any]], *,
              width: int = 3, gap: int = 1, start_col: int = 1) -> int:
    """Плитки показателей: подпись, крупное число, сноска.

    `value` может быть формулой (строка с «=») — тогда плитка живая и
    пересчитывается вместе со срезом.
    """
    col = start_col
    for tile in tiles:
        end = col + width - 1
        ws.merge_cells(start_row=row, start_column=col,
                       end_row=row, end_column=end)
        cap = ws.cell(row=row, column=col, value=tile["label"])
        cap.font = f(9, bold=True, color=MUTED)
        cap.fill = fill(BAND)
        cap.alignment = Alignment(horizontal="left", vertical="center", indent=1)

        ws.merge_cells(start_row=row + 1, start_column=col,
                       end_row=row + 1, end_column=end)
        val = ws.cell(row=row + 1, column=col, value=tile["value"])
        val.font = f(int(tile.get("size", 20)), bold=True,
                     color=tile.get("color", NAVY))
        val.fill = fill(BAND)
        val.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        if tile.get("format"):
            val.number_format = tile["format"]

        ws.merge_cells(start_row=row + 2, start_column=col,
                       end_row=row + 2, end_column=end)
        note = ws.cell(row=row + 2, column=col, value=tile.get("note", ""))
        note.font = f(8, color=MUTED)
        note.fill = fill(BAND)
        note.alignment = Alignment(horizontal="left", vertical="center", indent=1)

        for r in (row, row + 1, row + 2):
            for c in range(col, end + 1):
                ws.cell(row=r, column=c).border = BOX
        col = end + 1 + gap
    ws.row_dimensions[row].height = 18
    ws.row_dimensions[row + 1].height = 30
    ws.row_dimensions[row + 2].height = 16
    return row + 4


def table(ws: Worksheet, row: int, columns: Sequence[str],
          rows: Iterable[Sequence[Any]], *, start_col: int = 1,
          formats: Optional[Dict[int, str]] = None,
          rating_cols: Sequence[int] = (),
          wrap_cols: Sequence[int] = (),
          name: Optional[str] = None,
          zebra: bool = True,
          height: Optional[int] = None) -> Tuple[int, int]:
    """Таблица с шапкой. Возвращает (первая строка данных, последняя).

    `rating_cols` — номера колонок (1-based внутри таблицы), значения
    которых красятся по словарю RATING_STYLE: одна и та же оценка всегда
    одного цвета во всей книге, иначе светофор перестаёт читаться.
    """
    formats = formats or {}
    head = row
    for i, title in enumerate(columns):
        c = ws.cell(row=head, column=start_col + i, value=title)
        c.font = f(9, bold=True, color=WHITE)
        c.fill = fill(NAVY)
        c.alignment = Alignment(horizontal="center", vertical="center",
                                wrap_text=True)
        c.border = BOX
    ws.row_dimensions[head].height = 30

    r = head
    for n, data in enumerate(rows):
        r += 1
        for i, value in enumerate(data):
            c = ws.cell(row=r, column=start_col + i, value=value)
            c.font = f(9)
            c.border = BOX
            c.alignment = (left() if (i + 1) in wrap_cols
                           else Alignment(horizontal="left", vertical="center")
                           if isinstance(value, str)
                           else Alignment(horizontal="right", vertical="center"))
            if (i + 1) in formats:
                c.number_format = formats[i + 1]
            if (i + 1) in rating_cols and value in RATING_STYLE:
                text, back = RATING_STYLE[value]
                c.font = f(9, bold=True, color=text)
                c.fill = fill(back)
                c.alignment = center()
            elif zebra and n % 2 == 1:
                c.fill = fill(BAND)
        if height:
            ws.row_dimensions[r].height = height

    if name and r > head:
        ref = (f"{get_column_letter(start_col)}{head}:"
               f"{get_column_letter(start_col + len(columns) - 1)}{r}")
        tab = Table(displayName=name, ref=ref)
        tab.tableStyleInfo = TableStyleInfo(
            name="TableStyleLight9", showRowStripes=True, showColumnStripes=False)
        ws.add_table(tab)
    return head + 1, r


def note_block(ws: Worksheet, row: int, last_col: int, title: str,
               lines: Sequence[str], *, numbered: bool = False) -> int:
    """Абзац пояснений — там, где читатель на него наткнётся."""
    ws.merge_cells(start_row=row, start_column=1, end_row=row,
                   end_column=last_col)
    head = ws.cell(row=row, column=1, value=title)
    head.font = f(10, bold=True, color=NAVY)
    head.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    row += 1
    for i, line in enumerate(lines, 1):
        ws.merge_cells(start_row=row, start_column=1, end_row=row,
                       end_column=last_col)
        c = ws.cell(row=row, column=1,
                    value=(f"{i}. {line}" if numbered else f"•  {line}"))
        c.font = f(9, color=INK)
        c.alignment = Alignment(horizontal="left", vertical="top",
                                wrap_text=True, indent=1)
        ws.row_dimensions[row].height = max(14, 12 * (1 + len(line) // 110))
        row += 1
    return row + 1


# ── Срезы и условное форматирование ─────────────────────────────────────

def slicer(ws: Worksheet, cell: str, label_cell: str, label: str,
           options: Sequence[str], default: str) -> None:
    """Выпадающий список-срез: то, чем пользователь управляет панелью."""
    lab = ws[label_cell]
    lab.value = label
    lab.font = f(9, bold=True, color=MUTED)
    lab.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    target = ws[cell]
    target.value = default
    target.font = f(11, bold=True, color=ACCENT)
    target.fill = fill("FFF8DC")
    target.border = BOX
    target.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    joined = ",".join(options)
    if len(joined) > 250:                       # ограничение формата xlsx
        joined = ",".join(options[:20])
    dv = DataValidation(type="list", formula1=f'"{joined}"', allow_blank=False,
                        showDropDown=False)
    dv.prompt = "Выберите значение — панель пересчитается"
    dv.promptTitle = label
    ws.add_data_validation(dv)
    dv.add(target)


def _empty_range(ref: str) -> bool:
    """Диапазон вида «K6:K5» — таблица без строк.

    Возникает в самом правильном случае: проверка не нашла отклонений,
    реестр находок пуст, и вызывающий код честно передаёт
    (первая строка данных, последняя) = (6, 5). openpyxl падает на таком
    диапазоне с невнятным TypeError. Условное форматирование пустой
    таблицы — не ошибка, а отсутствие работы, поэтому просто выходим.
    """
    try:
        start, end = ref.split(":")
        row_of = lambda part: int("".join(c for c in part if c.isdigit()))
        return row_of(end) < row_of(start)
    except (ValueError, TypeError):
        return False


def data_bars(ws: Worksheet, ref: str, color: str = ACCENT) -> None:
    if _empty_range(ref):
        return
    ws.conditional_formatting.add(ref, DataBarRule(
        start_type="num", start_value=0, end_type="max", color=color,
        showValue=True))


def color_scale(ws: Worksheet, ref: str, *, reverse: bool = False) -> None:
    if _empty_range(ref):
        return
    lo, hi = (BAD_FILL, OK_FILL) if reverse else (OK_FILL, BAD_FILL)
    ws.conditional_formatting.add(ref, ColorScaleRule(
        start_type="min", start_color=lo, end_type="max", end_color=hi))


def flag_above(ws: Worksheet, ref: str, threshold: float) -> None:
    if _empty_range(ref):
        return
    ws.conditional_formatting.add(ref, CellIsRule(
        operator="greaterThan", formula=[str(threshold)],
        font=Font(name=FONT, size=9, bold=True, color=BAD_TEXT),
        fill=fill(BAD_FILL)))


# ── Диаграммы ───────────────────────────────────────────────────────────

def _style(chart, title: str, height: float, width: float) -> None:
    chart.title = title
    chart.height = height
    chart.width = width
    chart.style = 2


def _labels(chart, *, value: bool = True, percent: bool = False) -> None:
    """Подписи данных — только то, что попросили.

    Одного `showVal = True` мало: остальные флаги остаются
    неопределёнными, и Excel с LibreOffice подставляют свои умолчания.
    LibreOffice печатает тогда «A92; Принято, л; 16517684» в каждой
    точке — диаграмма превращается в кашу. Поэтому все пять флагов
    задаются явно, включая те, что нужно выключить.
    """
    labels = DataLabelList()
    labels.showVal = value
    labels.showPercent = percent
    labels.showCatName = False
    labels.showSerName = False
    labels.showLegendKey = False
    labels.showBubbleSize = False
    chart.dataLabels = labels


def bar_chart(ws: Worksheet, anchor: str, title: str, *,
              cats: Reference, data: Reference, height: float = 7.5,
              width: float = 14.0, horizontal: bool = False,
              labels: bool = True) -> None:
    ch = BarChart()
    ch.type = "bar" if horizontal else "col"
    _style(ch, title, height, width)
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(cats)
    ch.gapWidth = 60
    if labels:
        _labels(ch)
    if len(ch.series) == 1:
        ch.legend = None
    else:
        ch.legend.position = "b"
    ws.add_chart(ch, anchor)


def line_chart(ws: Worksheet, anchor: str, title: str, *,
               cats: Reference, data: Reference, height: float = 7.5,
               width: float = 14.0) -> None:
    ch = LineChart()
    _style(ch, title, height, width)
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(cats)
    for s in ch.series:
        s.smooth = False
    ch.legend.position = "b"
    ws.add_chart(ch, anchor)


def doughnut_chart(ws: Worksheet, anchor: str, title: str, *,
                   cats: Reference, data: Reference, height: float = 7.5,
                   width: float = 9.0) -> None:
    ch = DoughnutChart(holeSize=55)
    _style(ch, title, height, width)
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(cats)
    _labels(ch)
    ch.legend.position = "b"
    ws.add_chart(ch, anchor)
