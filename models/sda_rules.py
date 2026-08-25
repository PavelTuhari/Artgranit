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

from typing import Optional, Tuple

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
        return REGIM_HORECA, "Unitate HoReCa: predare directa catre Administrator"

    if suprafata_mp is None:
        return None, "Suprafata comerciala nu este cunoscuta - inventar necesar"

    prag = prag_pentru(tip_amplasament)
    if suprafata_mp <= prag:
        return REGIM_EXCEPTIE, (
            f"Suprafata {suprafata_mp:g} m2 nu depaseste pragul de {prag:g} m2"
        )
    return REGIM_PROPRIU, (
        f"Suprafata {suprafata_mp:g} m2 depaseste pragul de {prag:g} m2"
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
