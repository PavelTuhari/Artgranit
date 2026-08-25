"""SDA — контроллер модуля: HTTP наверху, хранилище внизу.

Проверки формы живут здесь, а не в хранилище: в базу не должна уезжать
запись, про которую заранее известно, что она не пройдёт CHECK. Границы
объёма 0,1–3 л взяты из пункта 14.1 регламента и продублированы в DDL —
пользователю нужна внятная фраза, базе нужен запрет.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from models.sda_oracle_store import SDAStore

VOLUM_MIN_L = 0.1
VOLUM_MAX_L = 3.0


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _parse_partic_id(raw: Any) -> Optional[int]:
    """Разбирает query-параметр ``partic_id``.

    Пустое значение (None/"") означает "без фильтра" и возвращает None.
    Нечисловое значение — ошибка формы, поднимается как ValueError с
    понятным сообщением, которое вызывающая сторона оборачивает в _fail().
    """
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError("Parametrul partic_id trebuie sa fie un numar intreg")


class SDAController:
    """Тонкий слой между Flask и SDAStore."""

    # ── участники ───────────────────────────────────────────────────

    @staticmethod
    def get_partic(args) -> Dict[str, Any]:
        return SDAStore.list_partic()

    @staticmethod
    def save_partic(data: Dict[str, Any], username: str) -> Dict[str, Any]:
        if not (data.get("denumire") or "").strip():
            return _fail("Denumirea participantului este obligatorie")
        if not (data.get("idno") or "").strip():
            return _fail("IDNO al participantului este obligatoriu")
        stare = (data.get("stare") or "ACTIV").upper()
        if stare not in ("ACTIV", "SUSPENDAT", "INCHIS"):
            return _fail("Starea trebuie sa fie ACTIV, SUSPENDAT sau INCHIS")
        # Volumele comerciale sunt informative, dar dacă sunt completate
        # trebuie să fie numere întregi — altfel int() explodează mai jos,
        # în store, cu un ValueError necaptat (500 in loc de raspuns JSON).
        for key, label in (("vandut_an_ant", "Vandut anul anterior"),
                           ("estimare_an", "Estimare anul curent")):
            raw = data.get(key)
            if raw in (None, ""):
                continue
            try:
                as_float = float(raw)
            except (TypeError, ValueError):
                return _fail(f"{label} trebuie sa fie un numar intreg")
            if as_float != int(as_float):
                return _fail(f"{label} trebuie sa fie un numar intreg")
        return SDAStore.save_partic(data, username)

    # ── сеть ────────────────────────────────────────────────────────

    @staticmethod
    def get_units(args) -> Dict[str, Any]:
        try:
            partic_id = _parse_partic_id(args.get("partic_id"))
        except ValueError as exc:
            return _fail(str(exc))
        return SDAStore.list_units(partic_id, args.get("regim") or None)

    @staticmethod
    def save_unit(data: Dict[str, Any], username: str) -> Dict[str, Any]:
        if not (data.get("denumire") or "").strip():
            return _fail("Denumirea unitatii este obligatorie")
        # PARTIC_ID в SDA_UNIT — NOT NULL с внешним ключом: без него Oracle
        # ответит ORA-01400, и оператор увидит её в баннере как есть.
        if data.get("partic_id") in (None, ""):
            return _fail("Participantul este obligatoriu pentru o unitate")
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
        try:
            partic_id = _parse_partic_id(args.get("partic_id"))
        except ValueError as exc:
            return _fail(str(exc))
        return SDAStore.compliance_map(partic_id)

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

    # ── досье ───────────────────────────────────────────────────────

    @staticmethod
    def get_dossier(args) -> Dict[str, Any]:
        try:
            partic_id = _parse_partic_id(args.get("partic_id"))
        except ValueError as exc:
            return _fail(str(exc))
        if not partic_id:
            return _fail("Parametrul partic_id este obligatoriu")
        return SDAStore.registration_dossier(partic_id)
