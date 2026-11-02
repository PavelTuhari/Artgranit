"""Чистые правила TexFlow: штрихкоды, SKU, распределение затрат, цены.

Модуль не импортирует БД — всё тестируется без файла SQLite.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------- EAN-13

def ean13_check_digit(first12: str) -> int:
    """Контрольная цифра EAN-13 для 12 цифр."""
    if len(first12) != 12 or not first12.isdigit():
        raise ValueError("нужно ровно 12 цифр")
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first12))
    return (10 - total % 10) % 10


def make_ean13(prefix: str, number: int) -> str:
    """Внутренний EAN-13: префикс (обычно 20..29 — «для внутреннего
    использования магазина») + порядковый номер + контрольная цифра."""
    if not prefix.isdigit() or not 2 <= len(prefix) <= 7:
        raise ValueError("префикс EAN — от 2 до 7 цифр")
    body_len = 12 - len(prefix)
    if number < 0 or number >= 10 ** body_len:
        raise ValueError("номер не помещается в EAN-13")
    first12 = f"{prefix}{number:0{body_len}d}"
    return first12 + str(ean13_check_digit(first12))


def is_valid_ean13(code: str) -> bool:
    return (len(code) == 13 and code.isdigit()
            and ean13_check_digit(code[:12]) == int(code[12]))


# ---------------------------------------------------------------- SKU

_SKU_CLEAN = re.compile(r"[^A-Z0-9]+")


def sku_part(text: str) -> str:
    return _SKU_CLEAN.sub("", translit(text).upper())


def make_sku(style_code: str, color_code: str, size_code: str) -> str:
    """SKU в духе Zara: МОДЕЛЬ-ЦВЕТ-РАЗМЕР, например 4387-401-M."""
    parts = [sku_part(style_code), sku_part(color_code), sku_part(size_code)]
    if not all(parts):
        raise ValueError("пустая часть SKU")
    return "-".join(parts)


# ---------------------------------------------------------------- транслит

_TR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    # румынский / турецкий
    "ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ü": "u", "é": "e", "è": "e",
}


def translit(text: str) -> str:
    """Латиница для встроенных шрифтов принтеров (без кириллицы)."""
    out = []
    for ch in text or "":
        low = ch.lower()
        if low in _TR:
            rep = _TR[low]
            out.append(rep.capitalize() if ch != low and rep else rep)
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------- затраты

@dataclass
class CostLine:
    """Одна позиция приёмки для распределения импортных затрат."""
    key: object
    qty: int
    unit_cost_fx: float
    weight_kg: float = 0.0          # вес, приходящийся на всю позицию
    duty_pct: float = 0.0           # пошлина категории, % от стоимости


@dataclass
class ShipmentCosts:
    fx_rate: float = 1.0            # курс валюты поставки к местной
    freight: float = 0.0            # в местной валюте
    customs: float = 0.0            # фиксированный сбор, местная валюта
    broker: float = 0.0
    other: float = 0.0
    method: str = "value"           # value | qty | weight

    @property
    def lump(self) -> float:
        return self.freight + self.customs + self.broker + self.other


@dataclass
class LandedResult:
    key: object
    qty: int
    goods_unit: float               # закупка за 1 шт в местной валюте
    duty_unit: float
    overhead_unit: float
    landed_unit: float
    extras: dict = field(default_factory=dict)


def allocate_landed_cost(lines: list[CostLine], costs: ShipmentCosts) -> list[LandedResult]:
    """Себестоимость «до полки» (landed cost) за единицу.

    закупка×курс + пошлина категории + доля общих затрат (фрахт, таможня,
    брокер, прочее). Доля считается по стоимости, по штукам или по весу.
    """
    if costs.method not in ("value", "qty", "weight"):
        raise ValueError("метод распределения: value | qty | weight")
    lines = [l for l in lines if l.qty > 0]
    if not lines:
        return []

    def basis(l: CostLine) -> float:
        if costs.method == "qty":
            return float(l.qty)
        if costs.method == "weight":
            return float(l.weight_kg)
        return l.qty * l.unit_cost_fx * costs.fx_rate

    total_basis = sum(basis(l) for l in lines)
    if total_basis <= 0:          # нет весов/стоимости — падаем на штуки
        total_basis = float(sum(l.qty for l in lines))
        basis = lambda l: float(l.qty)  # noqa: E731

    out = []
    for l in lines:
        goods_unit = l.unit_cost_fx * costs.fx_rate
        duty_unit = goods_unit * l.duty_pct / 100.0
        overhead_unit = costs.lump * basis(l) / total_basis / l.qty
        out.append(LandedResult(
            key=l.key, qty=l.qty,
            goods_unit=round(goods_unit, 4),
            duty_unit=round(duty_unit, 4),
            overhead_unit=round(overhead_unit, 4),
            landed_unit=round(goods_unit + duty_unit + overhead_unit, 4),
        ))
    return out


# ---------------------------------------------------------------- цена

def psych_round(price: float, step: float = 10.0, ending: float = 0.1) -> float:
    """Красивая цена: вверх до шага и минус «хвост».
    183 при шаге 10 и хвосте 0.1 → 189.90; шаг 1, хвост 0.01 → 183.99."""
    if price <= 0:
        return 0.0
    if step <= 0:
        return round(price, 2)
    rounded = math.ceil((price + ending) / step - 1e-9) * step - ending
    return round(max(rounded, 0.0), 2)


def retail_price(landed_unit: float, markup_pct: float, vat_pct: float = 0.0,
                 step: float = 10.0, ending: float = 0.1,
                 min_margin_pct: float = 0.0) -> dict:
    """Розничная цена от себестоимости и наценки категории.

    Возвращает разбор: цена без НДС, с НДС, округлённая, фактическая
    наценка после округления.
    """
    markup = max(markup_pct, min_margin_pct)
    net = landed_unit * (1 + markup / 100.0)
    gross = net * (1 + vat_pct / 100.0)
    final = psych_round(gross, step, ending)
    net_after = final / (1 + vat_pct / 100.0) if final else 0.0
    real_markup = (net_after / landed_unit - 1) * 100 if landed_unit > 0 else 0.0
    return {
        "landed": round(landed_unit, 2),
        "net": round(net, 2),
        "gross": round(gross, 2),
        "price": final,
        "real_markup_pct": round(real_markup, 1),
    }


# ---------------------------------------------------------------- сверка

def reconcile(declared: dict, counted: dict) -> list[dict]:
    """Сверка «примерного» упаковочного листа с фактом.

    declared/counted: {ключ: количество}. Возвращает строки с разницей
    и статусом ok / short (недостача) / over (излишек) / extra (не было в листе).
    """
    rows = []
    for key in sorted(set(declared) | set(counted), key=lambda k: str(k)):
        d = int(declared.get(key, 0))
        c = int(counted.get(key, 0))
        diff = c - d
        if key not in declared:
            status = "extra"
        elif diff == 0:
            status = "ok"
        elif diff < 0:
            status = "short"
        else:
            status = "over"
        pct = round(diff / d * 100, 1) if d else None
        rows.append({"key": key, "declared": d, "counted": c,
                     "diff": diff, "diff_pct": pct, "status": status})
    return rows
