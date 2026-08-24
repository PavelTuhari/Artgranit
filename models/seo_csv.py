"""SEOForge — разбор и валидация CSV расходов рекламы и метрик сайтов.

Модуль намеренно чистый: ни Oracle, ни Flask, ни файловой системы. Всё,
что он делает, — превращает текст выгрузки в строки, готовые к записи,
и в список ошибок с номерами строк. Благодаря этому разбор тестируется
без базы, а импорт может быть двухшаговым: предпросмотр показывает ровно
то, что запишет commit.

Коннекторов к рекламным кабинетам и GSC в первой версии нет (кусок E
проекта), поэтому CSV — основной путь поступления факта. Когда коннекторы
появятся, они будут писать те же словари в те же таблицы.
"""
from __future__ import annotations

import datetime
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

# Колонки фиксированы и описаны в docs/SEOForge/CSV_FORMAT.md.
SPEND_COLUMNS = (
    "site", "channel", "article", "campaign", "spend_date", "suma",
    "valuta", "clicks", "impressions", "conversions", "revenue", "ext_id",
)

METRICS_COLUMNS = (
    "site", "metric", "channel", "fact_date", "value", "source", "ext_id",
)

_SPEND_REQUIRED = ("site", "channel", "article", "spend_date", "suma")
_METRICS_REQUIRED = ("site", "metric", "fact_date", "value")

_SEPARATORS = (";", "\t", ",")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class ParseResult:
    """Итог разбора: что запишем, что не смогли прочесть, какие колонки нашли."""

    rows: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)


# ── чистые помощники ─────────────────────────────────────────────────

def period_of(day) -> str:
    """Дата -> период YYYY-MM. Принимает date, datetime и строку YYYY-MM-DD."""
    if isinstance(day, (datetime.date, datetime.datetime)):
        return day.strftime("%Y-%m")
    text = (day or "").strip()
    if not _DATE_RE.match(text):
        raise ValueError(f"expected YYYY-MM-DD, got {day!r}")
    try:
        parsed = datetime.date.fromisoformat(text)
    except ValueError as exc:                                    # noqa: PERF203
        raise ValueError(f"expected YYYY-MM-DD, got {day!r}") from exc
    return parsed.strftime("%Y-%m")


def make_ext_id(source: str, day: str, campaign: str, channel: str,
                extra: str = "") -> str:
    """Детерминированный ключ дедупликации.

    Выгрузки кабинетов редко несут собственный идентификатор строки, но
    комбинация «источник + дата + кампания + канал» задаёт ту же строку
    при любой повторной выгрузке. Хеш берётся, чтобы уложиться в колонку
    и не тащить в ключ произвольный текст названий.
    """
    raw = "|".join(str(part or "").strip().lower()
                   for part in (source, day, campaign, channel, extra))
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _detect_separator(header: str) -> str:
    counts = {sep: header.count(sep) for sep in _SEPARATORS}
    best = max(counts, key=lambda sep: counts[sep])
    return best if counts[best] else ";"


def _number(raw: str, column: str, *, allow_negative: bool,
            default: float = 0.0) -> float:
    text = (raw or "").strip().replace(" ", "").replace(" ", "")
    if not text:
        return default
    # Выгрузки приходят и с точкой, и с запятой как десятичным разделителем.
    text = text.replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"{column}: не число ({raw!r})") from None
    if not allow_negative and value < 0:
        raise ValueError(f"{column}: отрицательное значение ({raw!r})")
    return value


def _date(raw: str, column: str) -> str:
    text = (raw or "").strip()
    if not _DATE_RE.match(text):
        raise ValueError(f"{column}: ожидается дата YYYY-MM-DD ({raw!r})")
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{column}: несуществующая дата ({raw!r})") from None
    return text


def _text(raw: str, column: str, *, required: bool) -> str:
    value = (raw or "").strip()
    if required and not value:
        raise ValueError(f"{column}: обязательное поле пустое")
    return value


# ── общий каркас разбора ─────────────────────────────────────────────

def _parse(text: str, columns: Sequence[str], required: Sequence[str],
           build) -> ParseResult:
    result = ParseResult()

    lines = [ln for ln in (text or "").replace("\r\n", "\n").split("\n")]
    # BOM ломает имя первой колонки, а пустые строки в конце файла — норма.
    if lines and lines[0].startswith("﻿"):
        lines[0] = lines[0][1:]
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines or not lines[0].strip():
        result.errors.append({"line": 0, "message": "Файл пуст"})
        return result

    separator = _detect_separator(lines[0])
    header = [cell.strip().strip('"').lower() for cell in lines[0].split(separator)]
    result.columns = header

    missing = [name for name in required if name not in header]
    if missing:
        result.errors.append({
            "line": 1,
            "message": "Отсутствуют обязательные колонки: "
                       + ", ".join(name.upper() for name in missing),
        })
        return result

    index = {name: pos for pos, name in enumerate(header)}

    # Номер строки — как в файле, вместе с заголовком: пользователь
    # открывает CSV и видит ровно эту строку.
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        cells = line.split(separator)

        def cell(name: str) -> str:
            pos = index.get(name)
            if pos is None or pos >= len(cells):
                return ""
            return cells[pos].strip().strip('"')

        try:
            result.rows.append(build(cell))
        except ValueError as exc:
            result.errors.append({"line": number, "message": str(exc)})

    return result


def parse_spend_csv(text: str) -> ParseResult:
    """Разбирает выгрузку расходов рекламы."""

    def build(cell) -> Dict[str, Any]:
        spend_date = _date(cell("spend_date"), "spend_date")
        row = {
            "site": _text(cell("site"), "site", required=True),
            "channel": _text(cell("channel"), "channel", required=True),
            "article": _text(cell("article"), "article", required=True),
            "campaign": _text(cell("campaign"), "campaign", required=False),
            "platform": _text(cell("platform"), "platform", required=False),
            "spend_date": spend_date,
            "period": period_of(spend_date),
            "suma": _number(cell("suma"), "suma", allow_negative=False),
            "valuta": (_text(cell("valuta"), "valuta", required=False) or "MDL").upper(),
            "clicks": int(_number(cell("clicks"), "clicks", allow_negative=False)),
            "impressions": int(_number(cell("impressions"), "impressions",
                                       allow_negative=False)),
            "conversions": int(_number(cell("conversions"), "conversions",
                                       allow_negative=False)),
            "revenue": _number(cell("revenue"), "revenue", allow_negative=False),
        }
        supplied = _text(cell("ext_id"), "ext_id", required=False)
        row["ext_id"] = supplied or make_ext_id(
            "spend", row["spend_date"], row["campaign"], row["channel"],
            row["site"])
        return row

    return _parse(text, SPEND_COLUMNS, _SPEND_REQUIRED, build)


def parse_metrics_csv(text: str) -> ParseResult:
    """Разбирает выгрузку метрик сайта."""

    def build(cell) -> Dict[str, Any]:
        fact_date = _date(cell("fact_date"), "fact_date")
        row = {
            "site": _text(cell("site"), "site", required=True),
            "metric": _text(cell("metric"), "metric", required=True),
            "channel": _text(cell("channel"), "channel", required=False),
            "fact_date": fact_date,
            "period": period_of(fact_date),
            # Дельта позиции и изменение трафика бывают отрицательными.
            "value": _number(cell("value"), "value", allow_negative=True),
            "source": _text(cell("source"), "source", required=False),
        }
        supplied = _text(cell("ext_id"), "ext_id", required=False)
        row["ext_id"] = supplied or make_ext_id(
            "metrics", row["fact_date"], row["metric"], row["channel"],
            row["site"])
        return row

    return _parse(text, METRICS_COLUMNS, _METRICS_REQUIRED, build)
