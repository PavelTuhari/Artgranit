"""SDA — чистые правила модуля: порог площади и тарифные категории.

Здесь нет ни базы, ни HTTP, ни настроек. Это сделано намеренно: порог
освобождения магазина решает, нужен ли сети пункт возврата, и такую
величину нельзя проверять только через живую базу.

Пороги: 100 м² для обычного магазина, 150 м² для тарабы на рынке,
киоска, заправки и заведения общественного питания (пункты 93 и 97
регламента). Граница включительна: «suprafață care nu depășește 100 m²»
означает, что ровно 100 попадают в исключение.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional, Tuple

# Обоснование режима видит оператор и оно уходит в досье Администратору,
# поэтому текст пишется на нормальном румынском, с диакритикой. Это
# безопасно: SDA_* живут в облачной базе (AL32UTF8). Запрет на не-ASCII
# касается DDL и контура OfficePlus (CL8MSWIN1251), а не этих строк.
PRAG_STANDARD_MP = 100.0
PRAG_SPECIAL_MP = 150.0

TIPURI_PRAG_SPECIAL = frozenset({
    "TARABA", "CHIOSC", "BENZINARIE", "ALIMENTATIE_PUBLICA",
})

REGIM_PROPRIU = "A_PUNCT_PROPRIU"
REGIM_EXCEPTIE = "B_EXCEPTIE_APL"
REGIM_HORECA = "C_HORECA"

CULORI_SIMPLE = frozenset({"ALBASTRU", "VERDE", "MARO"})


def prag_pentru(tip_amplasament: str) -> float:
    """Порог площади для этого типа точки."""
    return (PRAG_SPECIAL_MP
            if (tip_amplasament or "").upper() in TIPURI_PRAG_SPECIAL
            else PRAG_STANDARD_MP)


def classify_regime(suprafata_mp: Optional[float],
                    tip_amplasament: str,
                    is_horeca: bool = False) -> Tuple[Optional[str], str]:
    """Режим точки и человекочитаемое обоснование.

    Возвращает (regim, motiv). Без площади режим не назначается: молча
    подставить один из двух — значит однажды подставить неверный.
    """
    if is_horeca:
        return REGIM_HORECA, "Unitate HoReCa: predare directă către Administrator"

    if suprafata_mp is None:
        return None, "Suprafața comercială nu este cunoscută — inventar necesar"

    prag = prag_pentru(tip_amplasament)
    if suprafata_mp <= prag:
        return REGIM_EXCEPTIE, (
            f"Suprafața {suprafata_mp:g} m² nu depășește pragul de {prag:g} m²"
        )
    return REGIM_PROPRIU, (
        f"Suprafața {suprafata_mp:g} m² depășește pragul de {prag:g} m²"
    )


def admin_category(material: str, culoare: Optional[str],
                   bariera_o2: str, volum_l: float) -> str:
    """Категория тарифа администрирования, a..g (пункт 14.13)."""
    material = (material or "").upper()
    if material == "METAL":
        return "e"
    if material == "STICLA":
        return "f" if volum_l > 0.5 else "g"

    # Пластик. Барьер по кислороду перекрывает цвет.
    if (bariera_o2 or "N").upper() == "D":
        return "d"
    culoare = (culoare or "").upper()
    if culoare == "TRANSPARENT":
        return "a"
    if culoare in CULORI_SIMPLE:
        return "b"
    return "c"


def gest_category(material: str, volum_l: float) -> str:
    """Категория тарифа обработки, a..e (пункт 14.14)."""
    material = (material or "").upper()
    if material == "METAL":
        return "c"
    if material == "STICLA":
        return "d" if volum_l > 0.5 else "e"
    return "a" if volum_l <= 1.0 else "b"

# ── периоды тарифов ──────────────────────────────────────────────────
#
# Тарифы живут периодами, как цены в OfficePlus. Дыра в периодах — это
# день, за который систему нечем посчитать; наложение — день, за который
# посчитать можно двумя способами. Обе ошибки видны только на границе,
# поэтому их ищет отдельная проверка, а не глаз оператора.

def validate_periods(periods):
    """Список проблем в наборе периодов. Пустой список — всё в порядке."""
    problems = []
    by_type = {}
    for p in periods:
        by_type.setdefault(p["tip"], []).append(p)

    for tip, group in by_type.items():
        group = sorted(group, key=lambda p: p["data_start"])
        furthest = group[0]
        for prev, curr in zip(group, group[1:]):
            if furthest["data_end"] is None:
                problems.append(
                    f"{tip}: perioada {furthest['tariff_id']} este deschisa si "
                    f"se suprapune cu perioada {curr['tariff_id']}")
                continue
            if furthest["data_end"] >= curr["data_start"]:
                problems.append(
                    f"{tip}: perioadele {furthest['tariff_id']} si "
                    f"{curr['tariff_id']} se suprapun")
            elif furthest["data_end"] + timedelta(days=1) < curr["data_start"]:
                problems.append(
                    f"{tip}: gol intre perioadele {furthest['tariff_id']} si "
                    f"{curr['tariff_id']}")
            if furthest["data_end"] is not None and (
                    curr["data_end"] is None
                    or curr["data_end"] > furthest["data_end"]):
                furthest = curr
    return problems


def pick_value(lines, categorie, metoda=None, reutilizabil=None):
    """Значение тарифа для категории. None — если строки нет.

    Точное совпадение важнее подстановочной категории `*`: последняя
    нужна для депозита, у которого категорий нет вовсе.
    """
    def matches(line, cat):
        if line.get("categorie") != cat:
            return False
        if line.get("metoda") is not None and metoda is not None \
                and line["metoda"] != metoda:
            return False
        if line.get("reutilizabil") is not None and reutilizabil is not None \
                and line["reutilizabil"] != reutilizabil:
            return False
        if line.get("metoda") is not None and metoda is None:
            return False
        if line.get("reutilizabil") is not None and reutilizabil is None:
            return False
        return True

    for cat in (categorie, "*"):
        for line in lines:
            if matches(line, cat):
                return line["valoare_lei"]
    return None
