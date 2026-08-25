"""SDA — контроллер модуля: HTTP наверху, хранилище внизу.

Проверки формы живут здесь, а не в хранилище: в базу не должна уезжать
запись, про которую заранее известно, что она не пройдёт CHECK. Границы
объёма 0,1–3 л взяты из пункта 14.1 регламента и продублированы в DDL —
пользователю нужна внятная фраза, базе нужен запрет.
"""
from __future__ import annotations

from typing import Any, Dict

from models.sda_oracle_store import SDAStore

VOLUM_MIN_L = 0.1
VOLUM_MAX_L = 3.0


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


class SDAController:
    """Тонкий слой между Flask и SDAStore."""

    # ── сеть ────────────────────────────────────────────────────────

    @staticmethod
    def get_units(args) -> Dict[str, Any]:
        partic_id = args.get("partic_id")
        return SDAStore.list_units(
            int(partic_id) if partic_id else None, args.get("regim") or None)

    @staticmethod
    def save_unit(data: Dict[str, Any], username: str) -> Dict[str, Any]:
        if not (data.get("denumire") or "").strip():
            return _fail("Denumirea unitatii este obligatorie")
        suprafata = data.get("suprafata_mp")
        if suprafata not in (None, ""):
            try:
                if float(suprafata) <= 0:
                    return _fail("Suprafata trebuie sa fie mai mare ca zero")
            except (TypeError, ValueError):
                return _fail("Suprafata trebuie sa fie un numar")
        return SDAStore.save_unit(data, username)

    @staticmethod
    def reclassify(username: str) -> Dict[str, Any]:
        return SDAStore.reclassify_all(username)

    @staticmethod
    def get_compliance(args) -> Dict[str, Any]:
        partic_id = args.get("partic_id")
        return SDAStore.compliance_map(int(partic_id) if partic_id else None)

    # ── реестр ──────────────────────────────────────────────────────

    @staticmethod
    def get_packs(args) -> Dict[str, Any]:
        return SDAStore.list_packs(args.get("q") or None)

    @staticmethod
    def save_pack(data: Dict[str, Any], username: str) -> Dict[str, Any]:
        if not (data.get("ean") or "").strip():
            return _fail("Codul EAN este obligatoriu")
        if (data.get("material") or "").upper() not in ("PLASTIC", "STICLA", "METAL"):
            return _fail("Materialul trebuie sa fie PLASTIC, STICLA sau METAL")
        try:
            volum = float(data.get("volum_l"))
        except (TypeError, ValueError):
            return _fail("Volumul trebuie sa fie un numar")
        if not (VOLUM_MIN_L <= volum <= VOLUM_MAX_L):
            return _fail(
                f"Volumul trebuie sa fie intre {VOLUM_MIN_L} si {VOLUM_MAX_L} litri")
        try:
            if float(data.get("greutate_g")) <= 0:
                return _fail("Greutatea trebuie sa fie mai mare ca zero")
        except (TypeError, ValueError):
            return _fail("Greutatea trebuie sa fie un numar")
        return SDAStore.save_pack(data, username)

    @staticmethod
    def get_deposit(args) -> Dict[str, Any]:
        ean = args.get("ean")
        if not ean:
            return _fail("Parametrul ean este obligatoriu")
        return SDAStore.deposit_for_ean(ean)
