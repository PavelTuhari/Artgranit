#!/usr/bin/env python3
"""Autopark — аудиторский отчёт: книга Excel, PDF и скриншоты.

    venv/bin/python modules/autopark/scripts/autopark_audit.py \
        --demo --xlsx --pdf --png --md --out docs/Autopark/examples

Режимы источника данных:

  --demo   сгенерированный представительный набор (год работы сети,
           ~3 500 рейсов, ~10 500 позиций) с известным числом заложенных
           дефектов. Книга получает лист «Самопроверка»: подложено против
           найдено по каждой процедуре.
  --live   боевой контур Oracle за указанный период. Требует wallet.

PDF и PNG делает установленный LibreOffice (`soffice`) плюс `pdftoppm`
из poppler. Второй рендерер не заводим: две разные картинки одного
отчёта — гарантированный спор о том, какая настоящая.

Скриншот конкретного листа находится не по номеру страницы, а по тексту:
книга печатается в PDF целиком, `pdftotext` даёт текст каждой страницы, и
страница берётся по заголовку листа. Нумерация страниц зависит от объёма
данных и поехала бы при первом же изменении набора.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.autopark import audit, audit_data, audit_excel  # noqa: E402

SOFFICE_CANDIDATES = (
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice", "/opt/homebrew/bin/soffice",
)

#: Листы, попадающие в скриншоты, и маркер для поиска страницы в PDF.
SHOTS = [
    ("01-cover", "ОТЧЁТ ПО НЕЗАВИСИМОЙ ПРОВЕРКЕ"),
    ("02-summary", "Резюме для руководства"),
    ("03-bi", "BI-панель контура"),
    ("04-controls", "Матрица контролей"),
    ("05-findings", "Реестр находок"),
    ("06-heatmap", "Карта рисков: вероятность"),
    ("07-tests", "Выполненные процедуры"),
    ("08-selfcheck", "Самопроверка методики"),
]


def _soffice() -> str:
    found = shutil.which("soffice")
    if found:
        return found
    for path in SOFFICE_CANDIDATES:
        if os.path.exists(path):
            return path
    raise SystemExit("LibreOffice (soffice) не найден — PDF и скриншоты "
                     "собрать нечем. Установите LibreOffice или уберите "
                     "--pdf/--png.")


def to_pdf(xlsx: str, out_dir: str) -> str:
    """XLSX → PDF средствами LibreOffice."""
    subprocess.run(
        [_soffice(), "--headless", "--norestore", "--convert-to", "pdf",
         "--outdir", out_dir, xlsx],
        check=True, capture_output=True, timeout=300)
    pdf = os.path.join(out_dir,
                       os.path.splitext(os.path.basename(xlsx))[0] + ".pdf")
    if not os.path.exists(pdf):
        raise SystemExit(f"LibreOffice не создал {pdf}")
    return pdf


def _page_texts(pdf: str) -> list:
    """Текст каждой страницы PDF (для поиска нужного листа)."""
    if not shutil.which("pdftotext"):
        return []
    out = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                         capture_output=True, text=True, timeout=120).stdout
    return out.split("\f")


def to_png(pdf: str, out_dir: str, prefix: str = "audit",
           dpi: int = 130) -> list:
    """Скриншоты нужных листов: страница ищется по заголовку, не по номеру."""
    if not shutil.which("pdftoppm"):
        raise SystemExit("pdftoppm (poppler) не найден — скриншоты собрать "
                         "нечем.")
    pages = _page_texts(pdf)
    made = []
    for name, marker in SHOTS:
        page_no = next((i + 1 for i, text in enumerate(pages)
                        if marker in text), None)
        if page_no is None:
            print(f"  · лист «{marker}» в PDF не найден — пропущен")
            continue
        stem = os.path.join(out_dir, f"{prefix}-{name}")
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), "-f", str(page_no),
             "-l", str(page_no), "-cropbox", pdf, stem],
            check=True, capture_output=True, timeout=180)
        produced = [p for p in os.listdir(out_dir)
                    if p.startswith(f"{prefix}-{name}-") and p.endswith(".png")]
        for p in produced:
            final = os.path.join(out_dir, f"{prefix}-{name}.png")
            os.replace(os.path.join(out_dir, p), final)
            made.append(final)
            break
    return made


def to_markdown(rep: dict, pop: dict, xlsx_name: str) -> str:
    """Краткий акт в Markdown — для хаба документации и акта приёмки."""
    op = rep["opinion"]
    facts = rep["facts"]
    period = rep["period"]
    lines = [
        "# Акт независимой проверки контура «Автопарк»",
        "",
        f"**Предмет:** {rep['entity']}  ",
        f"**Период:** {period.get('from')} — {period.get('to')}  ",
        f"**Данные:** {rep.get('data_label') or '—'}  ",
        f"**Дата отчёта:** {date.today().isoformat()}  ",
        f"**Исполнитель:** {audit_excel.PREPARER}",
        "",
        "## Заключение",
        "",
        f"### {op['title']}",
        "",
        op["text"],
        "",
        "| Показатель | Значение |",
        "|---|---:|",
        f"| Проверено объектов | {facts['total_tested']} |",
        f"| Выявлено отклонений | {facts['total_exceptions']} |",
        f"| Доля отклонений | {facts['exception_rate_pct']:.2f} % |",
        f"| Денежная оценка | {facts['impact_lei']:,.2f} лей |".replace(",", " "),
        f"| Находок: высокой / средней / низкой значимости | "
        f"{op['high']} / {op['medium']} / {op['low']} |",
        f"| Контролей эффективны / требуют улучшения / неэффективны / "
        f"не тестировались | {op['controls_ok']} / {op['controls_warn']} / "
        f"{op['controls_bad']} / {op['controls_na']} |",
        "",
        "## Что проверено",
        "",
        "| Код | Процедура | Охват | Проверено | Отклонений | Результат |",
        "|---|---|---|---:|---:|---|",
    ]
    for t in rep["tests"]:
        lines.append(f"| {t['id']} | {t['title']} | {t['scope']} | "
                     f"{t['tested']} | {t['exceptions']} | {t['result']} |")

    lines += ["", "## Матрица контролей", "",
              "| Код | Контроль | Дизайн | Эффективность | Итог |",
              "|---|---|---|---|---|"]
    for c in rep["controls"]:
        lines.append(f"| {c['id']} | {c['title']} | {c['design']} | "
                     f"{c['operating']} | **{c['rating']}** |")

    if rep["findings"]:
        lines += ["", "## Находки", ""]
        for fnd in rep["findings"]:
            lines += [
                f"### {fnd['id']} · {fnd['severity']} · {fnd['title']}",
                "",
                f"**Наблюдение.** {fnd['observation']}",
                "",
                f"**Риск.** {fnd['risk']}",
                "",
                f"**Рекомендация.** {fnd['recommendation']}",
                "",
                f"*Контроль {fnd['control_id']}, процедура {fnd['test_id']}.*",
                "",
            ]

    if pop.get("injected"):
        found = {t["id"]: t["exceptions"] for t in rep["tests"]}
        ok = all(pop["injected"].get(k, 0) == found.get(k, 0)
                 for k in set(pop["injected"]) | set(found))
        lines += ["", "## Самопроверка методики", "",
                  "В набор намеренно заложено известное число дефектов "
                  "каждого вида. Проверка прогнана вслепую.", "",
                  "| Процедура | Подложено | Найдено | Итог |",
                  "|---|---:|---:|---|"]
        for tid in sorted(set(pop["injected"]) | set(found)):
            exp, got = pop["injected"].get(tid, 0), found.get(tid, 0)
            lines.append(f"| {tid} | {exp} | {got} | "
                         f"{'совпало' if exp == got else '**расхождение**'} |")
        lines += ["", ("**Итог: методика воспроизвела все заложенные дефекты "
                       "и не дала ложных срабатываний.**" if ok else
                       "**Итог: есть расхождения — вывод отчёта использовать "
                       "нельзя.**"), ""]

    lines += ["", "## Ограничения проверки", ""]
    for i, lim in enumerate(rep["limitations"], 1):
        lines.append(f"{i}. {lim}")
    lines += ["", "## Файлы", "",
              f"- Книга Excel с BI-панелью: `{xlsx_name}`",
              f"- PDF-версия: `{os.path.splitext(xlsx_name)[0]}.pdf`", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--demo", action="store_true",
                     help="сгенерированный представительный набор")
    src.add_argument("--live", action="store_true",
                     help="боевые данные контура из Oracle")
    ap.add_argument("--date-from", help="ГГГГ-ММ-ДД (для --live)")
    ap.add_argument("--date-to", help="ГГГГ-ММ-ДД (для --live)")
    ap.add_argument("--seed", type=int, default=20260919)
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--stations", type=int, default=24)
    ap.add_argument("--trucks", type=int, default=14)
    ap.add_argument("--drivers", type=int, default=22)
    ap.add_argument("--out", default="docs/Autopark/examples")
    ap.add_argument("--name", default=None, help="имя файла без расширения")
    ap.add_argument("--xlsx", action="store_true", default=True)
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--md", nargs="?", const="", default=None,
                    metavar="FILE",
                    help="сохранить акт в markdown; без значения — рядом с книгой")
    ap.add_argument("--png-dir", default=None,
                    help="куда класть скриншоты (по умолчанию --out)")
    args = ap.parse_args()

    out_dir = os.path.join(ROOT, args.out) if not os.path.isabs(args.out) \
        else args.out
    os.makedirs(out_dir, exist_ok=True)

    t0 = datetime.now()
    if args.demo:
        pop = audit_data.demo_population(
            args.seed, months=args.months, stations=args.stations,
            trucks=args.trucks, drivers=args.drivers)
        stem = args.name or "autopark_audit_demo"
    else:
        if not (args.date_from and args.date_to):
            ap.error("--live требует --date-from и --date-to")
        pop = audit_data.live_population(
            date.fromisoformat(args.date_from),
            date.fromisoformat(args.date_to))
        stem = args.name or f"autopark_audit_{args.date_from}_{args.date_to}"
    t_gen = (datetime.now() - t0).total_seconds()

    t0 = datetime.now()
    rep = audit.run_audit(pop)
    t_audit = (datetime.now() - t0).total_seconds()

    t0 = datetime.now()
    xlsx = audit_excel.build_workbook(rep, pop, os.path.join(out_dir, stem + ".xlsx"))
    t_xlsx = (datetime.now() - t0).total_seconds()

    facts = rep["facts"]
    print(f"Популяция: {facts['trips']} рейсов, {facts['items']} позиций, "
          f"{facts['tanks']} резервуаров — собрана за {t_gen:.2f} с")
    print(f"Проверено {facts['total_tested']} объектов по "
          f"{len(rep['tests'])} процедурам за {t_audit:.2f} с")
    print(f"Заключение: {rep['opinion']['title']} "
          f"(находок В{rep['opinion']['high']}/С{rep['opinion']['medium']}/"
          f"Н{rep['opinion']['low']})")
    print(f"Книга: {xlsx} — {os.path.getsize(xlsx) / 1024:.0f} КБ "
          f"за {t_xlsx:.2f} с")

    if pop.get("injected"):
        found = {t["id"]: t["exceptions"] for t in rep["tests"]}
        bad = [k for k in set(pop["injected"]) | set(found)
               if pop["injected"].get(k, 0) != found.get(k, 0)]
        print("Самопроверка: " + ("все заложенные дефекты воспроизведены"
                                  if not bad else
                                  f"РАСХОЖДЕНИЯ по {', '.join(sorted(bad))}"))

    if args.pdf or args.png:
        pdf = to_pdf(xlsx, out_dir)
        print(f"PDF: {pdf} — {os.path.getsize(pdf) / 1024:.0f} КБ")
        if args.png:
            png_dir = args.png_dir or out_dir
            if not os.path.isabs(png_dir):
                png_dir = os.path.join(ROOT, png_dir)
            os.makedirs(png_dir, exist_ok=True)
            shots = to_png(pdf, png_dir, prefix=stem.replace("_", "-"))
            print(f"Скриншотов: {len(shots)}")
            for s in shots:
                print(f"  · {s}")

    if args.md is not None:
        md_path = (args.md if args.md else os.path.join(out_dir, stem + ".md"))
        if not os.path.isabs(md_path):
            md_path = os.path.join(ROOT, md_path)
        os.makedirs(os.path.dirname(md_path), exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(rep, pop, os.path.basename(xlsx)))
        print(f"Акт: {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
