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

        if payload.get("unit_id") is not None:
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
        with DatabaseModel() as db:
            for unit in listed["data"]:
                is_horeca = unit.get("regim") == "C_HORECA"
                regim, motiv = sda_rules.classify_regime(
                    unit.get("suprafata_mp"), unit.get("tip_amplasament") or "MAGAZIN",
                    is_horeca)
                if regim == unit.get("regim"):
                    continue
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

    # ── реестр упаковки ─────────────────────────────────────────────

    @staticmethod
    def list_packs(search: Optional[str] = None) -> Dict[str, Any]:
        sql = ("SELECT PACK_ID, EAN, DENUMIRE, PRODUCATOR, MATERIAL, CULOARE, "
               "BARIERA_O2, REUTILIZABIL, VOLUM_L, GREUTATE_G, CAT_ADMIN, "
               "CAT_GEST, SURSA FROM SDA_PACK WHERE 1=1")
        params: Dict[str, Any] = {}
        if search:
            sql += " AND (UPPER(DENUMIRE) LIKE :q OR EAN LIKE :q)"
            params["q"] = f"%{search.upper()}%"
        sql += " ORDER BY DENUMIRE"

        with DatabaseModel() as db:
            r = db.execute_query(sql, params or None)
        if not r.get("success"):
            return _fail(r.get("message") or "Eroare la citirea registrului")
        return _done(_rows(r))

    @staticmethod
    def save_pack(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        material = (payload.get("material") or "").upper()
        volum = float(payload.get("volum_l") or 0)
        params = {
            "pack_id": payload.get("pack_id"),
            "ean": payload.get("ean"),
            "denumire": payload.get("denumire"),
            "producator": payload.get("producator"),
            "material": material,
            "culoare": (payload.get("culoare") or None),
            "bariera_o2": (payload.get("bariera_o2") or "N").upper(),
            "reutilizabil": (payload.get("reutilizabil") or "N").upper(),
            "volum_l": volum,
            "greutate_g": float(payload.get("greutate_g") or 0),
            "cat_admin": sda_rules.admin_category(
                material, payload.get("culoare"),
                (payload.get("bariera_o2") or "N"), volum),
            "cat_gest": sda_rules.gest_category(material, volum),
            "sursa": (payload.get("sursa") or "MANUAL").upper(),
        }

        if payload.get("pack_id") is not None:
            sql = ("UPDATE SDA_PACK SET EAN = :ean, DENUMIRE = :denumire, "
                   "PRODUCATOR = :producator, MATERIAL = :material, "
                   "CULOARE = :culoare, BARIERA_O2 = :bariera_o2, "
                   "REUTILIZABIL = :reutilizabil, VOLUM_L = :volum_l, "
                   "GREUTATE_G = :greutate_g, CAT_ADMIN = :cat_admin, "
                   "CAT_GEST = :cat_gest, SURSA = :sursa "
                   "WHERE PACK_ID = :pack_id")
        else:
            params.pop("pack_id")
            sql = ("INSERT INTO SDA_PACK (EAN, DENUMIRE, PRODUCATOR, MATERIAL, "
                   "CULOARE, BARIERA_O2, REUTILIZABIL, VOLUM_L, GREUTATE_G, "
                   "CAT_ADMIN, CAT_GEST, SURSA) VALUES (:ean, :denumire, "
                   ":producator, :material, :culoare, :bariera_o2, "
                   ":reutilizabil, :volum_l, :greutate_g, :cat_admin, "
                   ":cat_gest, :sursa)")

        with DatabaseModel() as db:
            r = db.execute_query(sql, params)
            if not r.get("success"):
                return _fail(r.get("message") or "Eroare la salvarea ambalajului")
            db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES ('PACK_SAVE', 'SDA_PACK', "
                ":entitate_id, :utilizator, :detalii)",
                {"entitate_id": payload.get("pack_id"), "utilizator": username,
                 "detalii": f"{params['ean']} {params['cat_admin']}/{params['cat_gest']}"})
        return _done({"cat_admin": params["cat_admin"],
                      "cat_gest": params["cat_gest"]})

    @staticmethod
    def deposit_for_ean(ean: str, on_date: Optional[date] = None) -> Dict[str, Any]:
        """Величина депозита для штрихкода на дату.

        Неизвестный EAN — это ошибка, а не ноль. Молчаливый ноль означал бы,
        что сеть недобирает депозит и обнаруживает это при сверке.
        """
        on_date = on_date or date.today()
        with DatabaseModel() as db:
            r = db.execute_query(
                "SELECT PACK_ID, EAN, CAT_ADMIN, REUTILIZABIL FROM SDA_PACK "
                "WHERE EAN = :ean", {"ean": ean})
            packs = _rows(r)
            if not r.get("success"):
                return _fail(r.get("message") or "Eroare la citirea registrului")
            if not packs:
                return _fail(f"EAN {ean} nu exista in registrul ambalajelor SD")

            # Периоды тарифа не должны пересекаться (см. sda_rules.validate_periods),
            # но если это всё же произошло, результат обязан быть детерминирован:
            # без ORDER BY Oracle не гарантирует порядок строк. Правило разрешения
            # конфликта: побеждает период с более поздней датой начала.
            t = db.execute_query(
                "SELECT L.CATEGORIE, L.METODA, L.REUTILIZABIL, L.VALOARE_LEI "
                "FROM SDA_TARIFF T JOIN SDA_TARIFF_LINE L "
                "ON L.TARIFF_ID = T.TARIFF_ID "
                "WHERE T.TIP = 'DEPOZIT' AND T.DATA_START <= :d "
                "AND (T.DATA_END IS NULL OR T.DATA_END >= :d) "
                "ORDER BY T.DATA_START DESC, T.TARIFF_ID DESC",
                {"d": on_date})
            lines = _rows(t)

        if not lines:
            return _fail("Nu exista tarif de depozit valabil la data ceruta")

        pack = packs[0]
        # lines сохраняет порядок ORDER BY из запроса (позднее начавшийся
        # период первым) — pick_value берёт первое совпадение, поэтому
        # порядок должен пройти через list comprehension без изменений.
        value = sda_rules.pick_value(
            [{"categorie": l["categorie"], "metoda": l["metoda"],
              "reutilizabil": l["reutilizabil"], "valoare_lei": l["valoare_lei"]}
             for l in lines],
            pack.get("cat_admin") or "*",
            reutilizabil=pack.get("reutilizabil"))
        if value is None:
            return _fail("Nu exista tarif de depozit pentru aceasta categorie")
        return _done({"ean": pack["ean"], "pack_id": pack["pack_id"],
                      "valoare_lei": float(value)})
