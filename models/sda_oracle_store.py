"""SDA — хранилище модуля поверх таблиц SDA_* в облачной базе портала.

Слой знает про SQL и ничего не знает про HTTP. Наружу отдаёт контракт
портала: {"success": bool, "data": ..., "message": str}.

Режим точки здесь не принимают на веру из формы: он всегда считается
заново функцией sda_rules.classify_regime и сохраняется вместе с датой
оценки. Иначе оператор однажды впишет «исключение» магазину в 300 м²,
и это всплывёт при проверке, а не при вводе.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from models.database import DatabaseModel
from models import sda_rules


def _rows(r: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not r.get("success") or not r.get("data"):
        return []
    cols = [c.lower() for c in r["columns"]]
    return [dict(zip(cols, row)) for row in r["data"]]


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _done(data: Any = None, message: str = "") -> Dict[str, Any]:
    return {"success": True, "data": data, "message": message}


class SDAStore:
    """Все обращения к Oracle для модуля SDA."""

    # ── журнал ──────────────────────────────────────────────────────

    @staticmethod
    def log(tip: str, entitate: str, entitate_id, detalii: str,
            username: str) -> None:
        with DatabaseModel() as db:
            db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES (:tip, :entitate, :entitate_id, "
                ":utilizator, :detalii)",
                {"tip": tip, "entitate": entitate, "entitate_id": entitate_id,
                 "utilizator": username, "detalii": (detalii or "")[:1000]})

    # ── сеть ────────────────────────────────────────────────────────

    @staticmethod
    def list_units(partic_id: Optional[int] = None,
                   regim: Optional[str] = None) -> Dict[str, Any]:
        sql = ("SELECT UNIT_ID, PARTIC_ID, COD_ERP, DENUMIRE, ADRESA, "
               "LOCALITATE, RAION, SUPRAFATA_MP, TIP_AMPLASAMENT, REGIM, "
               "REGIM_MOTIV, DATA_EVALUARE FROM SDA_UNIT WHERE 1=1")
        params: Dict[str, Any] = {}
        if partic_id is not None:
            sql += " AND PARTIC_ID = :partic_id"
            params["partic_id"] = partic_id
        if regim:
            sql += " AND REGIM = :regim"
            params["regim"] = regim
        sql += " ORDER BY DENUMIRE"

        with DatabaseModel() as db:
            r = db.execute_query(sql, params or None)
        if not r.get("success"):
            return _fail(r.get("message") or "Eroare la citirea unitatilor")
        return _done(_rows(r))

    @staticmethod
    def save_unit(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        suprafata = payload.get("suprafata_mp")
        suprafata = float(suprafata) if suprafata not in (None, "") else None
        tip = (payload.get("tip_amplasament") or "MAGAZIN").upper()
        regim, motiv = sda_rules.classify_regime(
            suprafata, tip, bool(payload.get("is_horeca")))

        params = {
            "unit_id": payload.get("unit_id"),
            "partic_id": payload.get("partic_id"),
            "cod_erp": payload.get("cod_erp"),
            "denumire": payload.get("denumire"),
            "adresa": payload.get("adresa"),
            "localitate": payload.get("localitate"),
            "raion": payload.get("raion"),
            "suprafata_mp": suprafata,
            "tip_amplasament": tip,
            "regim": regim,
            "regim_motiv": motiv,
            "data_evaluare": date.today(),
        }

        if payload.get("unit_id"):
            sql = ("UPDATE SDA_UNIT SET COD_ERP = :cod_erp, "
                   "DENUMIRE = :denumire, ADRESA = :adresa, "
                   "LOCALITATE = :localitate, RAION = :raion, "
                   "SUPRAFATA_MP = :suprafata_mp, "
                   "TIP_AMPLASAMENT = :tip_amplasament, REGIM = :regim, "
                   "REGIM_MOTIV = :regim_motiv, "
                   "DATA_EVALUARE = :data_evaluare, PARTIC_ID = :partic_id "
                   "WHERE UNIT_ID = :unit_id")
        else:
            params.pop("unit_id")
            sql = ("INSERT INTO SDA_UNIT (PARTIC_ID, COD_ERP, DENUMIRE, "
                   "ADRESA, LOCALITATE, RAION, SUPRAFATA_MP, "
                   "TIP_AMPLASAMENT, REGIM, REGIM_MOTIV, DATA_EVALUARE) "
                   "VALUES (:partic_id, :cod_erp, :denumire, :adresa, "
                   ":localitate, :raion, :suprafata_mp, :tip_amplasament, "
                   ":regim, :regim_motiv, :data_evaluare)")

        with DatabaseModel() as db:
            r = db.execute_query(sql, params)
            if not r.get("success"):
                return _fail(r.get("message") or "Eroare la salvarea unitatii")
            db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES ('UNIT_SAVE', 'SDA_UNIT', "
                ":entitate_id, :utilizator, :detalii)",
                {"entitate_id": payload.get("unit_id"),
                 "utilizator": username,
                 "detalii": f"{payload.get('denumire')} -> {regim or 'FARA REGIM'}"})
        return _done({"regim": regim, "regim_motiv": motiv})

    @staticmethod
    def reclassify_all(username: str) -> Dict[str, Any]:
        listed = SDAStore.list_units()
        if not listed["success"]:
            return listed
        changed = 0
        for unit in listed["data"]:
            regim, motiv = sda_rules.classify_regime(
                unit.get("suprafata_mp"), unit.get("tip_amplasament") or "MAGAZIN")
            if regim == unit.get("regim"):
                continue
            with DatabaseModel() as db:
                db.execute_query(
                    "UPDATE SDA_UNIT SET REGIM = :regim, "
                    "REGIM_MOTIV = :regim_motiv, DATA_EVALUARE = :data_evaluare "
                    "WHERE UNIT_ID = :unit_id",
                    {"regim": regim, "regim_motiv": motiv,
                     "data_evaluare": date.today(), "unit_id": unit["unit_id"]})
            changed += 1
        SDAStore.log("RECLASSIFY", "SDA_UNIT", None,
                     f"reclasificate {changed} unitati", username)
        return _done({"changed": changed})

    @staticmethod
    def compliance_map(partic_id: Optional[int] = None) -> Dict[str, Any]:
        sql = ("SELECT REGIM, COUNT(*) AS N FROM SDA_UNIT WHERE 1=1")
        params: Dict[str, Any] = {}
        if partic_id is not None:
            sql += " AND PARTIC_ID = :partic_id"
            params["partic_id"] = partic_id
        sql += " GROUP BY REGIM"

        with DatabaseModel() as db:
            r = db.execute_query(sql, params or None)
        if not r.get("success"):
            return _fail(r.get("message") or "Eroare la harta de conformitate")

        by_regime: Dict[str, int] = {}
        unknown = 0
        total = 0
        for row in _rows(r):
            n = int(row["n"])
            total += n
            if row["regim"]:
                by_regime[row["regim"]] = n
            else:
                unknown += n
        return _done({"total": total, "by_regime": by_regime, "unknown": unknown})
