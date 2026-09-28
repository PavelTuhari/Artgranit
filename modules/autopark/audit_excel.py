"""Autopark — сборка аудиторской книги Excel из результата `audit.run_audit`.

Двенадцать листов в порядке чтения: от заключения к доказательствам.
Так устроен любой отчёт по проверке — сначала вывод, потом основания,
а не наоборот: у читателя, который принимает решение, редко есть час.

  1. Титул            — предмет, период, объём данных, ограничения
  2. Резюме           — заключение, счёт находок и контролей, диаграмма
  3. Панель BI        — срезы и показатели, живые формулы
  4. Контроли         — матрица: дизайн, эффективность, покрытие
  5. Находки          — реестр с местом под ответ руководства
  6. Карта рисков     — вероятность × влияние, 5 × 5
  7. Тесты            — что именно проверено и какой процедурой
  8. Отклонения       — расшифровка: каждый выявленный случай
  9. Выборка          — состав и воспроизводимость выборки
 10. Куб              — факты по поставкам (источник панели)
 11. КубРейсы         — факты по рейсам (источник панели)
 12. Методика         — шкалы, определения, ограничения

Про формулы. Ни один показатель не записан посчитанным числом: всё, что
можно выразить формулой, выражено формулой — `SUMPRODUCT` по кубу,
`COUNTIF` по реестру находок. Причина простая: книгу открывают и меняют
срез. Записанное Python число при этом останется прежним и будет врать
уверенно и молча.

Про лист «Самопроверка» — он появляется только на сгенерированном
наборе, где известно, сколько дефектов каждого вида подложено. Это
проверка не системы, а самого аудита.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from openpyxl import Workbook
from openpyxl.chart import Reference
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from modules.autopark import excel_bi as bi

MONTH_RU = ["", "январь", "февраль", "март", "апрель", "май", "июнь",
            "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]

PREPARER = "Группа сопровождения контура «Автопарк»"
STANDARD = ("Методика внутреннего аудита информационных систем: "
            "тестирование дизайна и операционной эффективности контролей, "
            "тесты по существу на полной популяции (формат отчёта Big-4)")


def _d(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _month_key(day: Any) -> str:
    d = _d(day)
    return f"{d.year}-{d.month:02d}" if d else "—"


def _month_label(key: str) -> str:
    if key == "—" or "-" not in key:
        return key
    y, m = key.split("-")
    return f"{MONTH_RU[int(m)]} {y}"


# ══ Кубы: плоские таблицы фактов, на которые ссылается панель ═══════════

def build_cube(pop: Dict[str, Any]) -> Tuple[List[List[Any]], List[str],
                                             List[str], List[str]]:
    """Поставки: месяц × регион × продукт → объём, позиции, потери."""
    price = pop.get("prices") or {}
    station_region = {s["code"]: s.get("region") or "—"
                      for s in pop.get("stations") or []}
    trip_month = {t["id"]: _month_key(t.get("trip_date")) for t in pop["trips"]}
    agg: Dict[Tuple[str, str, str], List[float]] = {}
    for item in pop["trip_items"]:
        month = trip_month.get(item.get("trip_id"), "—")
        region = item.get("region") or station_region.get(
            item.get("station_code"), "—")
        product = item.get("product_code") or "—"
        key = (month, region, product)
        cell = agg.setdefault(key, [0.0, 0.0, 0.0, 0.0])
        accepted = item.get("accepted_l")
        planned = item.get("planned_l") or 0
        loaded = item.get("loaded_l")
        cell[0] += float(accepted if accepted is not None else planned)
        cell[1] += 1
        if loaded is not None and accepted is not None:
            loss = float(loaded) - float(accepted)
            if loss > 0:
                cell[2] += loss
                cell[3] += loss * float(price.get(product, 0) or 0)

    rows = []
    for (month, region, product), v in sorted(agg.items()):
        rows.append([month, region, product, round(v[0], 0), int(v[1]),
                     round(v[2], 0), round(v[3], 2)])
    months = sorted({r[0] for r in rows})
    regions = sorted({r[1] for r in rows})
    products = sorted({r[2] for r in rows})
    return rows, months, regions, products


def build_trip_cube(pop: Dict[str, Any]) -> Tuple[List[List[Any]], List[str]]:
    """Рейсы: месяц × тип → количество, пробег, оплата, топливо."""
    trucks = {t["id"]: t for t in pop["trucks"]}
    agg: Dict[Tuple[str, str], List[float]] = {}
    for trip in pop["trips"]:
        if trip.get("status_code") == "DRAFT":
            continue
        key = (_month_key(trip.get("trip_date")), trip.get("type_code") or "—")
        cell = agg.setdefault(key, [0.0] * 7)
        norm_km = float(trip.get("norm_km") or 0)
        fact_km = float(trip.get("fact_km") or 0)
        truck = trucks.get(trip.get("truck_id")) or {}
        norm_l = norm_km * float(truck.get("norm_l_per_100km") or 0) / 100
        cell[0] += 1
        cell[1] += norm_km
        cell[2] += fact_km
        cell[3] += max(0.0, fact_km - norm_km)
        cell[4] += float(trip.get("pay_stored") or 0)
        cell[5] += norm_l
        cell[6] += float(trip.get("fact_fuel_l") or 0)
    rows = []
    for (month, type_code), v in sorted(agg.items()):
        rows.append([month, type_code, int(v[0]), round(v[1], 0),
                     round(v[2], 0), round(v[3], 0), round(v[4], 2),
                     round(v[5], 0), round(v[6], 0)])
    types = sorted({r[1] for r in rows})
    return rows, types


# ══ Листы ═══════════════════════════════════════════════════════════════

def _sheet_cover(wb: Workbook, rep: Dict[str, Any], pop: Dict[str, Any]) -> None:
    ws = wb.create_sheet("Титул")
    bi.prepare(ws, [3, 26, 60, 26, 3])
    period = rep["period"]
    facts = rep["facts"]
    op = rep["opinion"]

    ws.merge_cells("B2:D3")
    t = ws["B2"]
    t.value = "ОТЧЁТ ПО НЕЗАВИСИМОЙ ПРОВЕРКЕ"
    t.font = bi.f(22, bold=True, color=bi.NAVY)
    t.alignment = Alignment(horizontal="left", vertical="center")

    ws.merge_cells("B4:D4")
    s = ws["B4"]
    s.value = "Контур автоматизации автопарка бензовозов и распределения топлива"
    s.font = bi.f(12, color=bi.ACCENT)

    ws.merge_cells("B5:D5")
    ws["B5"].value = rep["entity"]
    ws["B5"].font = bi.f(11, color=bi.MUTED)

    row = 8
    label = rep.get("data_label") or ""
    if label:
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        c = ws.cell(row=row, column=2, value=label)
        c.font = bi.f(11, bold=True, color=bi.BAD_TEXT)
        c.fill = bi.fill(bi.BAD_FILL)
        c.alignment = bi.center()
        ws.row_dimensions[row].height = 26
        row += 2

    facts_rows = [
        ("Предмет проверки", "Расчёт заработной платы водителей, "
         "планирование и исполнение поставок топлива"),
        ("Проверяемый период", f"{period.get('from')} — {period.get('to')}"),
        ("Основание", "ТЗ заказчика от 18.09.2026 (два документа): "
         "распределение топлива и расходы автопарка"),
        ("Методика", STANDARD),
        ("Исполнитель", PREPARER),
        ("Дата отчёта", date.today().isoformat()),
        ("Объём популяции", f"{facts['trips']} рейсов, {facts['items']} позиций "
         f"груза, {facts['tanks']} резервуаров, {facts['trucks']} бензовозов, "
         f"{facts['drivers']} водителей"),
        ("Выполнено проверок", f"{facts['total_tested']} объектов по "
         f"{len(rep['tests'])} процедурам"),
    ]
    for name, value in facts_rows:
        c1 = ws.cell(row=row, column=2, value=name)
        c1.font = bi.f(10, bold=True, color=bi.MUTED)
        c1.alignment = bi.left()
        c1.border = bi.BOX
        c2 = ws.cell(row=row, column=3, value=value)
        c2.font = bi.f(10)
        c2.alignment = bi.left()
        c2.border = bi.BOX
        c3 = ws.cell(row=row, column=4, value="")
        c3.border = bi.BOX
        ws.row_dimensions[row].height = max(18, 13 * (1 + len(value) // 70))
        row += 1

    row += 1
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
    c = ws.cell(row=row, column=2, value="ЗАКЛЮЧЕНИЕ")
    c.font = bi.f(12, bold=True, color=bi.WHITE)
    c.fill = bi.fill(bi.NAVY)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 28
    row += 1

    text, back = {0: (bi.OK_TEXT, bi.OK_FILL), 1: (bi.OK_TEXT, bi.OK_FILL),
                  2: (bi.WARN_TEXT, bi.WARN_FILL),
                  3: (bi.BAD_TEXT, bi.BAD_FILL)}[op["level"]]
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
    c = ws.cell(row=row, column=2, value=op["title"])
    c.font = bi.f(16, bold=True, color=text)
    c.fill = bi.fill(back)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 34
    row += 1
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
    c = ws.cell(row=row, column=2, value=op["text"])
    c.font = bi.f(10)
    c.alignment = bi.left()
    ws.row_dimensions[row].height = 42
    row += 3

    bi.note_block(ws, row, 4, "Ограничения проверки", rep["limitations"],
                  numbered=True)


def _sheet_summary(wb: Workbook, rep: Dict[str, Any]) -> None:
    ws = wb.create_sheet("Резюме")
    bi.prepare(ws, [2] + [13] * 12)
    op = rep["opinion"]
    facts = rep["facts"]

    row = bi.banner(ws, 2, 13, "Резюме для руководства",
                    "Счётчики ниже — формулы по листам «Находки» и "
                    "«Контроли»: правка реестра меняет резюме сама.")

    row = bi.kpi_tiles(ws, row, [
        {"label": "НАХОДОК: ВЫСОКОЙ",
         "value": '=COUNTIF(Находки!$B:$B,"Высокий")',
         "color": bi.BAD_TEXT, "note": "требуют устранения до эксплуатации"},
        {"label": "НАХОДОК: СРЕДНЕЙ",
         "value": '=COUNTIF(Находки!$B:$B,"Средний")',
         "color": bi.WARN_TEXT, "note": "устранить в согласованный срок"},
        {"label": "НАХОДОК: НИЗКОЙ",
         "value": '=COUNTIF(Находки!$B:$B,"Низкий")',
         "color": bi.OK_TEXT, "note": "принять к сведению"},
        {"label": "КОНТРОЛЕЙ ЭФФЕКТИВНЫ",
         # Не «12 из 13» одной строкой: текстовая склейка нечитаема в
         # ячейке с числовым форматом и ломает сортировку. Число —
         # формулой, знаменатель — в подписи под плиткой.
         "value": '=COUNTIF(Контроли!$H:$H,"Эффективен")',
         "format": bi.NUM0, "color": bi.NAVY,
         "note": f"из {len(rep['controls'])} контролей контура"},
    ], width=3, gap=0)

    row = bi.kpi_tiles(ws, row, [
        {"label": "ПРОВЕРЕНО ОБЪЕКТОВ", "value": facts["total_tested"],
         "format": bi.NUM0, "color": bi.NAVY,
         "note": "полная популяция, не выборка"},
        {"label": "ВЫЯВЛЕНО ОТКЛОНЕНИЙ", "value": facts["total_exceptions"],
         "format": bi.NUM0, "color": bi.BAD_TEXT,
         "note": "каждое расшифровано на листе «Отклонения»"},
        {"label": "ДОЛЯ ОТКЛОНЕНИЙ",
         "value": facts["exception_rate_pct"] / 100,
         "format": bi.PCT2, "color": bi.WARN_TEXT,
         "note": "отклонений к проверенным объектам"},
        {"label": "ДЕНЕЖНАЯ ОЦЕНКА", "value": facts["impact_lei"],
         "format": bi.NUM2, "color": bi.BAD_TEXT,
         "note": "лей: лишний пробег, перерасход, потери"},
    ], width=3, gap=0)

    # Данные для диаграмм — сами формулы, а не числа.
    base = row + 1
    ws.cell(row=base, column=2, value="Значимость").font = bi.f(9, bold=True)
    ws.cell(row=base, column=3, value="Находок").font = bi.f(9, bold=True)
    for i, sev in enumerate(("Высокий", "Средний", "Низкий"), 1):
        ws.cell(row=base + i, column=2, value=sev).font = bi.f(9)
        c = ws.cell(row=base + i, column=3,
                    value=f'=COUNTIF(Находки!$B:$B,"{sev}")')
        c.font = bi.f(9)

    ws.cell(row=base, column=5, value="Оценка").font = bi.f(9, bold=True)
    ws.cell(row=base, column=6, value="Контролей").font = bi.f(9, bold=True)
    for i, rating in enumerate(("Эффективен", "Требует улучшения",
                                "Неэффективен", "Не тестировался"), 1):
        ws.cell(row=base + i, column=5, value=rating).font = bi.f(9)
        c = ws.cell(row=base + i, column=6,
                    value=f'=COUNTIF(Контроли!$H:$H,"{rating}")')
        c.font = bi.f(9)

    bi.doughnut_chart(
        ws, f"B{base + 7}", "Находки по значимости",
        cats=Reference(ws, min_col=2, min_row=base + 1, max_row=base + 3),
        data=Reference(ws, min_col=3, min_row=base, max_row=base + 3))
    bi.bar_chart(
        ws, f"F{base + 7}", "Оценка контролей контура",
        cats=Reference(ws, min_col=5, min_row=base + 1, max_row=base + 4),
        data=Reference(ws, min_col=6, min_row=base, max_row=base + 4),
        horizontal=True, width=16.0)

    row = base + 23
    row = bi.note_block(ws, row, 13, "Как читать заключение", [
        f"«{op['title']}» — {op['text']}",
        "Значимость находки не назначается экспертно: она выводится из "
        "доли отклонений и денежной оценки по шкале на листе «Методика».",
        "Контроль с дефектом дизайна не получает оценку выше «требует "
        "улучшения», даже если отклонений в периоде не найдено: контроль, "
        "который легко обойти, не доказан отсутствием попыток обхода.",
        "Оценка «не тестировался» означает, что в данных нет реквизита для "
        "проверки. Это не «всё хорошо» — это отсутствие доказательства.",
    ])
    bi.note_block(ws, row, 13, "Предмет проверки", rep["scope"], numbered=True)


def _sheet_panel(wb: Workbook, rep: Dict[str, Any], cube: List[List[Any]],
                 months: List[str], regions: List[str], products: List[str],
                 trip_cube: List[List[Any]], types: List[str]) -> None:
    """Панель BI: срезы управляют формулами, формулы — диаграммами."""
    ws = wb.create_sheet("Панель BI")
    bi.prepare(ws, [2, 16, 15, 13, 15, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13])
    n = len(cube) + 1
    m = len(trip_cube) + 1

    row = bi.banner(ws, 2, 15, "BI-панель контура",
                    "Измените значение в жёлтой ячейке — показатели и "
                    "диаграммы пересчитаются в Excel без выгрузки заново.")

    bi.slicer(ws, "C6", "B6", "Месяц", ["Все"] + [_month_label(x) for x in months], "Все")
    bi.slicer(ws, "F6", "E6", "Регион", ["Все"] + regions, "Все")
    bi.slicer(ws, "I6", "H6", "Продукт", ["Все"] + products, "Все")
    bi.slicer(ws, "L6", "K6", "Тип рейса", ["Все"] + types, "Все")

    row = 9
    ws.cell(row=row, column=2,
            value="Поставки — срез по месяцу, региону и продукту").font = \
        bi.f(11, bold=True, color=bi.NAVY)
    row += 1
    row = bi.kpi_tiles(ws, row, [
        {"label": "ПРИНЯТО НА АЗС, Л",
         "value": f"=SUMPRODUCT(Куб!$H$2:$H${n},Куб!$D$2:$D${n})",
         "format": bi.NUM0, "note": "по выбранному срезу"},
        {"label": "ПОЗИЦИЙ ГРУЗА",
         "value": f"=SUMPRODUCT(Куб!$H$2:$H${n},Куб!$E$2:$E${n})",
         "format": bi.NUM0, "note": "отсеков слито"},
        {"label": "ПОТЕРИ ПРИ ПРИЁМКЕ, Л",
         "value": f"=SUMPRODUCT(Куб!$H$2:$H${n},Куб!$F$2:$F${n})",
         "format": bi.NUM0, "color": bi.BAD_TEXT,
         "note": "загружено минус принято"},
        {"label": "ОЦЕНКА ПОТЕРЬ, ЛЕЙ",
         "value": f"=SUMPRODUCT(Куб!$H$2:$H${n},Куб!$G$2:$G${n})",
         "format": bi.NUM2, "color": bi.BAD_TEXT,
         "note": "по цене продукта"},
    ], width=3, gap=0, start_col=2)

    ws.cell(row=row, column=2,
            value="Рейсы и оплата — срез по месяцу и типу рейса").font = \
        bi.f(11, bold=True, color=bi.NAVY)
    row += 1
    row = bi.kpi_tiles(ws, row, [
        {"label": "РЕЙСОВ",
         "value": f"=SUMPRODUCT(КубРейсы!$J$2:$J${m},КубРейсы!$C$2:$C${m})",
         "format": bi.NUM0, "note": "без черновиков"},
        {"label": "НОРМАТИВНЫЙ ПРОБЕГ, КМ",
         "value": f"=SUMPRODUCT(КубРейсы!$J$2:$J${m},КубРейсы!$D$2:$D${m})",
         "format": bi.NUM0, "note": "основание для оплаты"},
        {"label": "ЛИШНИЙ ПРОБЕГ, КМ",
         "value": f"=SUMPRODUCT(КубРейсы!$J$2:$J${m},КубРейсы!$F$2:$F${m})",
         "format": bi.NUM0, "color": bi.BAD_TEXT,
         "note": "факт сверх норматива"},
        {"label": "НАЧИСЛЕНО, ЛЕЙ",
         "value": f"=SUMPRODUCT(КубРейсы!$J$2:$J${m},КубРейсы!$G$2:$G${m})",
         "format": bi.NUM2, "note": "зарплата водителей по срезу"},
    ], width=3, gap=0, start_col=2)

    # ── Блоки данных для диаграмм ───────────────────────────────────────
    pb = row + 1
    cap = ws.cell(row=pb - 1, column=2, value="Данные диаграмм — пересчитываются вместе со срезом")
    cap.font = bi.f(9, bold=True, color=bi.MUTED)
    ws.cell(row=pb, column=2, value="Продукт").font = bi.f(9, bold=True)
    ws.cell(row=pb, column=3, value="Принято, л").font = bi.f(9, bold=True)
    for i, product in enumerate(products, 1):
        ws.cell(row=pb + i, column=2, value=product).font = bi.f(9)
        c = ws.cell(row=pb + i, column=3, value=(
            f"=SUMPRODUCT((Куб!$C$2:$C${n}=$B{pb + i})*Куб!$H$2:$H${n}*"
            f"Куб!$D$2:$D${n})"))
        c.font = bi.f(9)
        c.number_format = bi.NUM0

    mb = pb + len(products) + 2
    ws.cell(row=mb, column=2, value="Месяц").font = bi.f(9, bold=True)
    ws.cell(row=mb, column=3, value="Принято, л").font = bi.f(9, bold=True)
    ws.cell(row=mb, column=4, value="Начислено, лей").font = bi.f(9, bold=True)
    for i, month in enumerate(months, 1):
        ws.cell(row=mb + i, column=2, value=_month_label(month)).font = bi.f(9)
        # Тренд игнорирует срез по месяцу (иначе останется одна точка),
        # но подчиняется срезам по региону и продукту — колонка I куба.
        c = ws.cell(row=mb + i, column=3, value=(
            f'=SUMPRODUCT((Куб!$A$2:$A${n}="{month}")*Куб!$I$2:$I${n}*'
            f"Куб!$D$2:$D${n})"))
        c.font = bi.f(9)
        c.number_format = bi.NUM0
        c2 = ws.cell(row=mb + i, column=4, value=(
            f'=SUMPRODUCT((КубРейсы!$A$2:$A${m}="{month}")*'
            f"КубРейсы!$K$2:$K${m}*КубРейсы!$G$2:$G${m})"))
        c2.font = bi.f(9)
        c2.number_format = bi.NUM0

    tb = mb + len(months) + 2
    ws.cell(row=tb, column=2, value="Процедура").font = bi.f(9, bold=True)
    ws.cell(row=tb, column=3, value="Отклонений").font = bi.f(9, bold=True)
    ws.cell(row=tb, column=4, value="Название").font = bi.f(9, bold=True)
    for i, test in enumerate(rep["tests"], 1):
        ws.cell(row=tb + i, column=2, value=test["id"]).font = bi.f(9)
        ws.cell(row=tb + i, column=4, value=test["title"]).font = \
            bi.f(8, color=bi.MUTED)
        c = ws.cell(row=tb + i, column=3, value=test["exceptions"])
        c.font = bi.f(9)
        c.number_format = bi.NUM0

    chart_row = pb
    bi.bar_chart(
        ws, f"F{chart_row}", "Принято на АЗС по продуктам, л",
        cats=Reference(ws, min_col=2, min_row=pb + 1, max_row=pb + len(products)),
        data=Reference(ws, min_col=3, min_row=pb, max_row=pb + len(products)),
        width=15.0, height=8.0)
    bi.line_chart(
        ws, f"F{chart_row + 17}", "Динамика приёмки по месяцам, л",
        cats=Reference(ws, min_col=2, min_row=mb + 1, max_row=mb + len(months)),
        data=Reference(ws, min_col=3, min_row=mb, max_row=mb + len(months)),
        width=15.0, height=8.0)
    bi.line_chart(
        ws, f"N{chart_row + 17}", "Начислено водителям по месяцам, лей",
        cats=Reference(ws, min_col=2, min_row=mb + 1, max_row=mb + len(months)),
        data=Reference(ws, min_col=4, min_row=mb, max_row=mb + len(months)),
        width=15.0, height=8.0)
    bi.bar_chart(
        ws, f"N{chart_row}", "Отклонения по процедурам проверки",
        cats=Reference(ws, min_col=2, min_row=tb + 1,
                       max_row=tb + len(rep["tests"])),
        data=Reference(ws, min_col=3, min_row=tb,
                       max_row=tb + len(rep["tests"])),
        horizontal=True, width=15.0, height=9.0)

    last = tb + len(rep["tests"]) + 3
    bi.note_block(ws, last, 15, "Что считает панель", [
        "Показатели блока «Поставки» подчиняются трём срезам: месяц, "
        "регион, продукт. Блок «Рейсы и оплата» — двум: месяц и тип рейса; "
        "регион к рейсу не относится, один рейс обслуживает несколько АЗС.",
        "Диаграммы динамики намеренно не подчиняются срезу по месяцу: "
        "иначе на графике осталась бы одна точка. Срезы по региону и "
        "продукту они соблюдают.",
        "Источник всех чисел — листы «Куб» и «КубРейсы»; колонки «В срезе» "
        "на них — формулы, читающие жёлтые ячейки этой панели.",
    ])


def _sheet_controls(wb: Workbook, rep: Dict[str, Any]) -> None:
    ws = wb.create_sheet("Контроли")
    bi.prepare(ws, [11, 20, 26, 42, 13, 11, 11, 15, 15, 12, 12, 16])
    row = bi.banner(ws, 2, 12, "Матрица контролей",
                    "Дизайн — предотвращает ли правило ошибку в принципе. "
                    "Эффективность — сработало ли оно на данных периода.")
    rows = []
    for c in rep["controls"]:
        rows.append([c["id"], c["domain"], c["title"], c["objective"],
                     c["type"], c["design"], c["operating"], c["rating"],
                     c["coverage"], c["tested"], c["exceptions"],
                     c["impact_lei"]])
    first, last = bi.table(
        ws, row,
        ["Код", "Область", "Контроль", "Цель контроля", "Тип", "Дизайн",
         "Эффективность", "Итоговая оценка", "Покрытие", "Проверено",
         "Отклонений", "Оценка, лей"],
        rows, formats={10: bi.NUM0, 11: bi.NUM0, 12: bi.NUM2},
        rating_cols=(6, 7, 8), wrap_cols=(3, 4), height=46)
    ws.freeze_panes = ws.cell(row=first, column=1)
    bi.data_bars(ws, f"K{first}:K{last}")

    row = last + 2
    rows2 = [[c["id"], c["design_note"], ", ".join(c["test_ids"])]
             for c in rep["controls"]]
    row = bi.banner(ws, row, 12, "Обоснование оценки дизайна",
                    "Почему контроль признан эффективным или требующим "
                    "улучшения — и какой процедурой это проверено.")
    bi.table(ws, row, ["Код", "Как контроль реализован в системе",
                       "Процедуры проверки"], rows2, wrap_cols=(2,), height=42)


def _sheet_findings(wb: Workbook, rep: Dict[str, Any]) -> None:
    ws = wb.create_sheet("Находки")
    bi.prepare(ws, [9, 14, 11, 9, 46, 40, 40, 12, 12, 11, 14, 12, 11,
                    20, 14, 16])
    row = bi.banner(ws, 2, 16, "Реестр находок",
                    "Три последние колонки — для ответа руководства; "
                    "их заполняет заказчик, остальное считает проверка.")
    rows = []
    for fnd in rep["findings"]:
        heat = next((h for h in rep["heat_map"] if h["id"] == fnd["id"]), {})
        rows.append([fnd["id"], fnd["severity"], fnd["control_id"],
                     fnd["test_id"], fnd["observation"], fnd["risk"],
                     fnd["recommendation"], fnd["exceptions"], fnd["tested"],
                     fnd["rate_pct"] / 100, fnd["impact_lei"],
                     heat.get("likelihood"), heat.get("impact"),
                     "", "", ""])
    first, last = bi.table(
        ws, row,
        ["№", "Значимость", "Контроль", "Тест", "Наблюдение", "Риск",
         "Рекомендация", "Отклонений", "Проверено", "Доля", "Оценка, лей",
         "Вероятн. 1–5", "Влияние 1–5", "Ответственный", "Срок",
         "Статус устранения"],
        rows, formats={8: bi.NUM0, 9: bi.NUM0, 10: bi.PCT2, 11: bi.NUM2},
        rating_cols=(2,), wrap_cols=(5, 6, 7), height=70)
    ws.freeze_panes = ws.cell(row=first, column=1)
    bi.data_bars(ws, f"K{first}:K{last}", color=bi.BAD_TEXT)
    for r in range(first, last + 1):
        for col in ("N", "O", "P"):
            cell = ws[f"{col}{r}"]
            cell.fill = bi.fill("FFF8DC")
            cell.border = bi.BOX

    bi.note_block(ws, last + 2, 16, "Заполняет заказчик", [
        "Жёлтые ячейки колонок «Ответственный», «Срок» и «Статус "
        "устранения» — единственные, которые вносит заказчик. "
        "Например: «Морару И., руководитель транспортного отдела» / "
        "«31.10.2026» / «Принято, в работе».",
        "Остальные колонки рассчитаны проверкой; их правка разрывает связь "
        "с листами «Тесты» и «Отклонения» и делает отчёт непроверяемым.",
        "Значимость: «Высокий» — доля отклонений ≥ 5 % либо денежная "
        "оценка ≥ 50 000 лей; «Средний» — ≥ 1 % либо ≥ 5 000 лей; "
        "«Низкий» — всё остальное.",
    ])


def _sheet_heatmap(wb: Workbook, rep: Dict[str, Any]) -> None:
    ws = wb.create_sheet("Карта рисков")
    bi.prepare(ws, [10, 26, 14, 17, 17, 17, 17, 17])
    row = bi.banner(ws, 2, 8, "Карта рисков: вероятность × влияние",
                    "Обе координаты выведены из результата тестирования — "
                    "из доли отклонений и денежной оценки, а не назначены.")

    top = row + 1
    ws.merge_cells(start_row=top, start_column=2, end_row=top + 4,
                   end_column=2)
    c = ws.cell(row=top, column=2, value="ВЛИЯНИЕ")
    c.font = bi.f(10, bold=True, color=bi.MUTED)
    c.alignment = bi.center()

    zone = {
        (5, 5): bi.BAD_FILL, (5, 4): bi.BAD_FILL, (4, 5): bi.BAD_FILL,
        (4, 4): bi.BAD_FILL, (3, 5): bi.BAD_FILL, (5, 3): bi.BAD_FILL,
        (5, 2): bi.WARN_FILL, (4, 3): bi.WARN_FILL, (3, 4): bi.WARN_FILL,
        (2, 5): bi.WARN_FILL, (3, 3): bi.WARN_FILL, (4, 2): bi.WARN_FILL,
        (2, 4): bi.WARN_FILL, (5, 1): bi.WARN_FILL, (1, 5): bi.WARN_FILL,
    }
    by_cell: Dict[Tuple[int, int], List[str]] = {}
    for h in rep["heat_map"]:
        by_cell.setdefault((h["likelihood"], h["impact"]), []).append(h["id"])

    for i, impact in enumerate((5, 4, 3, 2, 1)):
        r = top + i
        lab = ws.cell(row=r, column=3, value=impact)
        lab.font = bi.f(10, bold=True, color=bi.MUTED)
        lab.alignment = bi.center()
        lab.border = bi.BOX
        for j, likely in enumerate((1, 2, 3, 4, 5)):
            col = 4 + j
            ids = by_cell.get((likely, impact), [])
            cell = ws.cell(row=r, column=col,
                           value=(", ".join(ids) if ids else ""))
            cell.fill = bi.fill(zone.get((likely, impact), bi.OK_FILL))
            cell.font = bi.f(10, bold=True, color=bi.INK)
            cell.alignment = bi.center(wrap=True)
            cell.border = bi.BOX
        ws.row_dimensions[r].height = 42

    axis = top + 5
    ws.cell(row=axis, column=3, value="").border = bi.BOX
    for j, likely in enumerate((1, 2, 3, 4, 5)):
        c = ws.cell(row=axis, column=4 + j, value=likely)
        c.font = bi.f(10, bold=True, color=bi.MUTED)
        c.alignment = bi.center()
        c.border = bi.BOX
    ws.merge_cells(start_row=axis + 1, start_column=4, end_row=axis + 1,
                   end_column=8)
    c = ws.cell(row=axis + 1, column=4, value="ВЕРОЯТНОСТЬ")
    c.font = bi.f(10, bold=True, color=bi.MUTED)
    c.alignment = bi.center()

    row = axis + 3
    rows = [[h["id"], h["title"], h["severity"], h["likelihood"], h["impact"],
             h["likelihood"] * h["impact"]] for h in rep["heat_map"]]
    rows.sort(key=lambda r: -r[5])
    row = bi.banner(ws, row, 8, "Находки на карте", "")
    first, last = bi.table(
        ws, row, ["№", "Находка", "Значимость", "Вероятность", "Влияние",
                  "Ранг"], rows, rating_cols=(3,), wrap_cols=(2,), height=30)
    if last >= first:
        bi.color_scale(ws, f"F{first}:F{last}")

    bi.note_block(ws, last + 2, 8, "Шкала", [
        "Вероятность 5 — отклонения более чем в 10 % проверенных объектов; "
        "4 — свыше 5 %; 3 — свыше 1 %; 2 — свыше 0,1 %; 1 — единичные.",
        "Влияние 5 — денежная оценка от 50 000 лей; 4 — от 5 000; "
        "3 — от 500; 2 — оценка ниже 500 лей либо более пяти случаев; "
        "1 — единичный случай без денежной оценки.",
        "Ранг = вероятность × влияние. Красная зона — устранять до "
        "перевода контура в промышленную эксплуатацию.",
    ])


def _sheet_tests(wb: Workbook, rep: Dict[str, Any]) -> None:
    ws = wb.create_sheet("Тесты")
    bi.prepare(ws, [9, 30, 44, 46, 30, 13, 13, 12, 14, 16])
    row = bi.banner(ws, 2, 10, "Выполненные процедуры",
                    "Пересчёт выполнен отдельной реализацией формул, не "
                    "использующей проверяемый код: совпадение результата не "
                    "может быть следствием общей ошибки.")
    rows = [[t["id"], t["title"], t["objective"], t["procedure"], t["scope"],
             t["tested"], t["exceptions"], t["rate_pct"] / 100,
             t["impact_lei"], t["result"]] for t in rep["tests"]]
    first, last = bi.table(
        ws, row,
        ["Код", "Процедура", "Что должно выполняться", "Как проверено",
         "Охват", "Проверено", "Отклонений", "Доля", "Оценка, лей",
         "Результат"],
        rows, formats={6: bi.NUM0, 7: bi.NUM0, 8: bi.PCT2, 9: bi.NUM2},
        rating_cols=(10,), wrap_cols=(2, 3, 4, 5), height=64)
    ws.freeze_panes = ws.cell(row=first, column=1)
    bi.data_bars(ws, f"G{first}:G{last}", color=bi.BAD_TEXT)
    bi.note_block(ws, last + 2, 10, "Методика", rep["methodology"],
                  numbered=True)


def _sheet_exceptions(wb: Workbook, rep: Dict[str, Any],
                      cap: int = 250) -> None:
    ws = wb.create_sheet("Отклонения")
    bi.prepare(ws, [14, 14, 20, 26, 16, 16, 16, 16, 16, 16])
    row = bi.banner(ws, 2, 10, "Расшифровка отклонений",
                    "Каждый выявленный случай с реквизитами документа — "
                    "чтобы находку можно было проверить, а не принять "
                    "на веру.")
    for test in rep["tests"]:
        if not test["rows"]:
            continue
        head = ws.cell(row=row, column=1,
                       value=f"{test['id']} · {test['title']} · "
                             f"отклонений: {test['exceptions']} из "
                             f"{test['tested']} проверенных")
        head.font = bi.f(10, bold=True, color=bi.NAVY)
        ws.merge_cells(start_row=row, start_column=1, end_row=row,
                       end_column=10)
        ws.row_dimensions[row].height = 22
        row += 1
        shown = test["rows"][:cap]
        _, last = bi.table(ws, row, test["columns"], shown)
        row = last + 1
        if len(test["rows"]) > cap:
            c = ws.cell(row=row, column=1, value=(
                f"Показаны первые {cap} случаев из {len(test['rows'])}. "
                "Полный перечень воспроизводится командой выгрузки — "
                "ограничение только на объём книги."))
            c.font = bi.f(9, italic=True, color=bi.MUTED)
            ws.merge_cells(start_row=row, start_column=1, end_row=row,
                           end_column=10)
            row += 1
        row += 2


def _sheet_sample(wb: Workbook, rep: Dict[str, Any]) -> None:
    ws = wb.create_sheet("Выборка")
    bi.prepare(ws, [14, 8, 12, 14, 18, 18, 18, 20])
    row = bi.banner(ws, 2, 8, "Аудиторская выборка",
                    "Для контролей, которые не видны в данных целиком, "
                    "проверяется выборка документов.")
    sample = rep["sample"]
    row = bi.note_block(ws, row, 8, "Как сформирована выборка", [
        f"Ключ воспроизводимости: «{sample['seed']}». Состав выборки "
        "определяется хешем SHA-256 от ключа и номера документа, а не "
        "генератором случайных чисел: та же команда на другой машине и в "
        "другом году даст тот же список.",
        "Объём выборки задан шкалой attribute sampling при ожидаемом "
        "нулевом уровне отклонений и доверии 90 %: контроль, "
        "срабатывающий ежедневно — 25 документов, еженедельно — 5, "
        "ежемесячно — 2.",
        "Одно отклонение в выборке уже означает, что контроль не может "
        "быть признан эффективным: нулевой ожидаемый уровень отклонений "
        "не допускает исключений.",
    ])
    if sample["rows"]:
        first, last = bi.table(ws, row, sample["columns"], sample["rows"],
                               rating_cols=(8,))
        ws.freeze_panes = ws.cell(row=first, column=1)
    else:
        c = ws.cell(row=row, column=1, value=(
            "Выборка не формировалась: в данных периода нет реквизитов, "
            "по которым проверяются ручные контроли (автор документа, "
            "журнал статусов). Это отражено оценкой «не тестировался» в "
            "матрице контролей."))
        c.font = bi.f(10, color=bi.BAD_TEXT)
        ws.merge_cells(start_row=row, start_column=1, end_row=row + 1,
                       end_column=8)
        c.alignment = bi.left()


def _sheet_cube(wb: Workbook, cube: List[List[Any]], months: List[str],
                regions: List[str], products: List[str]) -> None:
    ws = wb.create_sheet("Куб")
    bi.prepare(ws, [12, 16, 12, 15, 12, 14, 16, 12, 12], grid=True)
    ws.cell(row=1, column=1, value="Месяц")
    headers = ["Месяц", "Регион", "Продукт", "Принято, л", "Позиций",
               "Потери, л", "Оценка потерь, лей", "В срезе", "В срезе без месяца"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = bi.f(9, bold=True, color=bi.WHITE)
        c.fill = bi.fill(bi.NAVY)
        c.alignment = bi.center(wrap=True)
    for r, data in enumerate(cube, 2):
        ws.cell(row=r, column=1, value=data[0]).font = bi.f(9)
        ws.cell(row=r, column=2, value=data[1]).font = bi.f(9)
        ws.cell(row=r, column=3, value=data[2]).font = bi.f(9)
        for i, value in enumerate(data[3:], 4):
            c = ws.cell(row=r, column=i, value=value)
            c.font = bi.f(9)
            c.number_format = bi.NUM2 if i == 7 else bi.NUM0
        # Колонки-признаки: единственное место, где срез превращается в
        # число. Всё остальное на панели — SUMPRODUCT по ним.
        month_label = _month_label(data[0])
        flag = ws.cell(row=r, column=8, value=(
            f'=IF(AND(OR(\'Панель BI\'!$C$6="Все","{month_label}"='
            f"'Панель BI'!$C$6),OR('Панель BI'!$F$6=\"Все\",$B{r}="
            f"'Панель BI'!$F$6),OR('Панель BI'!$I$6=\"Все\",$C{r}="
            f"'Панель BI'!$I$6)),1,0)"))
        flag.font = bi.f(9, color=bi.MUTED)
        flag2 = ws.cell(row=r, column=9, value=(
            f'=IF(AND(OR(\'Панель BI\'!$F$6="Все",$B{r}='
            f"'Панель BI'!$F$6),OR('Панель BI'!$I$6=\"Все\",$C{r}="
            f"'Панель BI'!$I$6)),1,0)"))
        flag2.font = bi.f(9, color=bi.MUTED)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:I{len(cube) + 1}"


def _sheet_trip_cube(wb: Workbook, cube: List[List[Any]]) -> None:
    ws = wb.create_sheet("КубРейсы")
    bi.prepare(ws, [12, 14, 10, 15, 15, 15, 16, 14, 14, 12, 12], grid=True)
    headers = ["Месяц", "Тип рейса", "Рейсов", "Норматив, км", "Факт, км",
               "Лишний пробег, км", "Начислено, лей", "Норма ДТ, л",
               "Факт ДТ, л", "В срезе", "В срезе без месяца"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = bi.f(9, bold=True, color=bi.WHITE)
        c.fill = bi.fill(bi.NAVY)
        c.alignment = bi.center(wrap=True)
    for r, data in enumerate(cube, 2):
        ws.cell(row=r, column=1, value=data[0]).font = bi.f(9)
        ws.cell(row=r, column=2, value=data[1]).font = bi.f(9)
        for i, value in enumerate(data[2:], 3):
            c = ws.cell(row=r, column=i, value=value)
            c.font = bi.f(9)
            c.number_format = bi.NUM2 if i == 7 else bi.NUM0
        month_label = _month_label(data[0])
        c = ws.cell(row=r, column=10, value=(
            f'=IF(AND(OR(\'Панель BI\'!$C$6="Все","{month_label}"='
            f"'Панель BI'!$C$6),OR('Панель BI'!$L$6=\"Все\",$B{r}="
            f"'Панель BI'!$L$6)),1,0)"))
        c.font = bi.f(9, color=bi.MUTED)
        c2 = ws.cell(row=r, column=11, value=(
            f'=IF(OR(\'Панель BI\'!$L$6="Все",$B{r}=\'Панель BI\'!$L$6),1,0)'))
        c2.font = bi.f(9, color=bi.MUTED)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:K{len(cube) + 1}"


def _sheet_selfcheck(wb: Workbook, rep: Dict[str, Any],
                     injected: Dict[str, int]) -> None:
    ws = wb.create_sheet("Самопроверка")
    bi.prepare(ws, [10, 44, 16, 16, 16, 24])
    row = bi.banner(ws, 2, 6, "Самопроверка методики",
                    "Лист существует только для сгенерированного набора: "
                    "в него намеренно заложено известное число дефектов "
                    "каждого вида.")
    row = bi.note_block(ws, row, 6, "Зачем это нужно", [
        "Проверка, которой нечего находить, ничего не доказывает: она "
        "одинаково молчит и когда всё чисто, и когда сама сломана.",
        "Поэтому набор данных генерируется с известным числом нарушений "
        "каждого вида, а проверка прогоняется вслепую. Совпадение "
        "«подложено» и «найдено» по всем процедурам — доказательство, что "
        "методика ловит то, что должна, и не выдумывает лишнего.",
        "Расхождение в любую сторону — отказ: «найдено меньше» означает "
        "пропуск, «найдено больше» — ложные срабатывания, и то и другое "
        "делает вывод непригодным.",
    ])
    found = {t["id"]: t["exceptions"] for t in rep["tests"]}
    titles = {t["id"]: t["title"] for t in rep["tests"]}
    rows = []
    ok = True
    for tid in sorted(set(injected) | set(found)):
        exp = injected.get(tid, 0)
        got = found.get(tid, 0)
        verdict = "Совпало" if exp == got else "РАСХОЖДЕНИЕ"
        if exp != got:
            ok = False
        rows.append([tid, titles.get(tid, "—"), exp, got, got - exp, verdict])
    first, last = bi.table(
        ws, row, ["Код", "Процедура", "Подложено дефектов", "Найдено",
                  "Разница", "Итог"], rows,
        formats={3: bi.NUM0, 4: bi.NUM0, 5: bi.NUM0})
    for r in range(first, last + 1):
        cell = ws.cell(row=r, column=6)
        text, back = ((bi.OK_TEXT, bi.OK_FILL) if cell.value == "Совпало"
                      else (bi.BAD_TEXT, bi.BAD_FILL))
        cell.font = bi.f(9, bold=True, color=text)
        cell.fill = bi.fill(back)
        cell.alignment = bi.center()

    row = last + 2
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    c = ws.cell(row=row, column=1, value=(
        "ИТОГ: методика воспроизвела все заложенные дефекты и не дала "
        "ложных срабатываний." if ok else
        "ИТОГ: есть расхождения — вывод отчёта использовать нельзя до "
        "разбора причин."))
    c.font = bi.f(12, bold=True,
                  color=bi.OK_TEXT if ok else bi.BAD_TEXT)
    c.fill = bi.fill(bi.OK_FILL if ok else bi.BAD_FILL)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 30


def _sheet_method(wb: Workbook, rep: Dict[str, Any]) -> None:
    ws = wb.create_sheet("Методика")
    bi.prepare(ws, [3, 26, 90])
    row = bi.banner(ws, 2, 3, "Методика, шкалы и определения", "")
    row = bi.note_block(ws, row, 3, "Подход", rep["methodology"], numbered=True)
    row = bi.note_block(ws, row, 3, "Предмет проверки", rep["scope"],
                        numbered=True)
    row = bi.note_block(ws, row, 3, "Ограничения", rep["limitations"],
                        numbered=True)
    row = bi.note_block(ws, row, 3, "Определения", [
        "Контроль — правило, которое должно не допустить ошибку. "
        "Оценивается по двум измерениям: дизайн и операционная "
        "эффективность.",
        "Тест по существу — независимый пересчёт величины аудитором и "
        "сравнение с тем, что в системе.",
        "Полная популяция — проверены все документы периода, а не выборка. "
        "Возможно там, где данные машинные.",
        "Отклонение — единичное несовпадение. Находка — вывод, к которому "
        "приводит совокупность отклонений.",
        "Значимость находки выводится из доли отклонений и денежной "
        "оценки, а не назначается экспертно.",
    ])
    row = bi.note_block(ws, row, 3, "Шкала оценки контроля", [
        "Эффективен — отклонений не выявлено и дизайн контроля не имеет "
        "дефектов.",
        "Требует улучшения — отклонения выявлены в пределах 5 % "
        "популяции, либо дизайн контроля позволяет его обойти.",
        "Неэффективен — отклонения более чем в 5 % проверенных объектов.",
        "Не тестировался — в данных нет реквизита для проверки. Это "
        "отсутствие доказательства, а не подтверждение исправности.",
    ])
    bi.note_block(ws, row, 3, "Источники данных", [
        "Oracle-объекты контура с префиксом FLT_ (рейсы, позиции груза, "
        "резервуары, бензовозы, водители, периоды ставок, цены ANRE).",
        "Фактический пробег и расход топлива — из GPS-прослойки контура в "
        "том виде, в каком их передал провайдер.",
        "Цены продуктов — последнее решение ANRE на дату окончания "
        "периода.",
    ])


# ══ Сборка ══════════════════════════════════════════════════════════════

def build_workbook(rep: Dict[str, Any], pop: Dict[str, Any], path: str) -> str:
    """Собрать книгу и сохранить. Возвращает путь."""
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.title = "Аудиторский отчёт — контур «Автопарк»"
    wb.properties.creator = PREPARER
    wb.properties.subject = rep["entity"]

    cube, months, regions, products = build_cube(pop)
    trip_cube, types = build_trip_cube(pop)

    _sheet_cover(wb, rep, pop)
    _sheet_summary(wb, rep)
    _sheet_panel(wb, rep, cube, months, regions, products, trip_cube, types)
    _sheet_controls(wb, rep)
    _sheet_findings(wb, rep)
    _sheet_heatmap(wb, rep)
    _sheet_tests(wb, rep)
    _sheet_exceptions(wb, rep)
    _sheet_sample(wb, rep)
    _sheet_cube(wb, cube, months, regions, products)
    _sheet_trip_cube(wb, trip_cube)
    if pop.get("injected"):
        _sheet_selfcheck(wb, rep, pop["injected"])
    _sheet_method(wb, rep)

    # Печать: книгу распечатают и приложат к акту приёмки. Без этого
    # альбомная таблица на 16 колонок рвётся на четыре листа по ширине,
    # и читать её невозможно ни на бумаге, ни в PDF-версии отчёта.
    for ws in wb.worksheets:
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_options.horizontalCentered = True
        ws.page_margins.left = ws.page_margins.right = 0.3
        ws.page_margins.top = ws.page_margins.bottom = 0.4
        ws.oddFooter.left.text = "Аудиторский отчёт — контур «Автопарк»"
        ws.oddFooter.left.size = 8
        ws.oddFooter.right.text = "Стр. &P из &N"
        ws.oddFooter.right.size = 8

    wb.save(path)
    return path
