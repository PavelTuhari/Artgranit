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
            username: str) -> Dict[str, Any]:
        with DatabaseModel() as db:
            r = db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES (:tip, :entitate, :entitate_id, "
                ":utilizator, :detalii)",
                {"tip": tip, "entitate": entitate, "entitate_id": entitate_id,
                 "utilizator": username, "detalii": (detalii or "")[:1000]})
            if not r.get("success"):
                return _fail(r.get("message") or "Eroare la scrierea in jurnal")
            db.connection.commit()
        return _done()

    # ── участники ───────────────────────────────────────────────────

    @staticmethod
    def list_partic() -> Dict[str, Any]:
        """Участники SDA. Без них единицу сети создать нельзя: PARTIC_ID
        в SDA_UNIT — NOT NULL с внешним ключом сюда."""
        with DatabaseModel() as db:
            r = db.execute_query(
                "SELECT PARTIC_ID, IDNO, DENUMIRE, DATA_INREG, NR_CONTRACT, "
                "DATA_CONTRACT, CONTACT_NUME, CONTACT_TEL, CONTACT_EMAIL, "
                "STARE, VANDUT_AN_ANT, ESTIMARE_AN FROM SDA_PARTIC "
                "ORDER BY DENUMIRE")
        if not r.get("success"):
            return _fail(r.get("message") or "Eroare la citirea participantilor")
        return _done(_rows(r))

    @staticmethod
    def save_partic(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        def _num(key):
            raw = payload.get(key)
            return int(raw) if raw not in (None, "") else None

        params = {
            "partic_id": payload.get("partic_id"),
            "idno": payload.get("idno"),
            "denumire": payload.get("denumire"),
            "nr_contract": payload.get("nr_contract") or None,
            "contact_nume": payload.get("contact_nume") or None,
            "contact_tel": payload.get("contact_tel") or None,
            "contact_email": payload.get("contact_email") or None,
            "stare": (payload.get("stare") or "ACTIV").upper(),
            "vandut_an_ant": _num("vandut_an_ant"),
            "estimare_an": _num("estimare_an"),
        }

        partic_id = payload.get("partic_id")
        has_id = partic_id not in (None, "")

        if has_id:
            sql = ("UPDATE SDA_PARTIC SET IDNO = :idno, DENUMIRE = :denumire, "
                   "NR_CONTRACT = :nr_contract, CONTACT_NUME = :contact_nume, "
                   "CONTACT_TEL = :contact_tel, CONTACT_EMAIL = :contact_email, "
                   "STARE = :stare, VANDUT_AN_ANT = :vandut_an_ant, "
                   "ESTIMARE_AN = :estimare_an WHERE PARTIC_ID = :partic_id")
        else:
            params.pop("partic_id")
            sql = ("INSERT INTO SDA_PARTIC (IDNO, DENUMIRE, NR_CONTRACT, "
                   "CONTACT_NUME, CONTACT_TEL, CONTACT_EMAIL, STARE, "
                   "VANDUT_AN_ANT, ESTIMARE_AN) VALUES (:idno, :denumire, "
                   ":nr_contract, :contact_nume, :contact_tel, :contact_email, "
                   ":stare, :vandut_an_ant, :estimare_an)")

        with DatabaseModel() as db:
            r = db.execute_query(sql, params)
            if not r.get("success"):
                return _fail(r.get("message")
                             or "Eroare la salvarea participantului")
            if has_id and not r.get("rowcount"):
                return _fail(
                    f"Participantul {partic_id} nu mai exista")
            jr = db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES ('PARTIC_SAVE', 'SDA_PARTIC', "
                ":entitate_id, :utilizator, :detalii)",
                {"entitate_id": partic_id,
                 "utilizator": username,
                 "detalii": (f"{params['idno']} {params['denumire']}")[:1000]})
            if not jr.get("success"):
                return _fail(jr.get("message")
                             or "Eroare la scrierea in jurnal")
            db.connection.commit()
        return _done({"idno": params["idno"], "denumire": params["denumire"]})

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
        unit_id = payload.get("unit_id")
        if unit_id == "":
            unit_id = None

        # Признака HoReCa нет отдельной колонкой: он живёт только в REGIM.
        # Если форма его не прислала, при правке существующей точки его
        # надо унести вперёд, иначе редактирование адреса молча разжалует
        # заведение из C_HORECA в обычный магазин.
        is_horeca = payload.get("is_horeca")
        if is_horeca is None and unit_id is not None:
            with DatabaseModel() as db:
                cur = db.execute_query(
                    "SELECT REGIM FROM SDA_UNIT WHERE UNIT_ID = :unit_id",
                    {"unit_id": unit_id})
            if not cur.get("success"):
                return _fail(cur.get("message")
                             or "Eroare la citirea regimului curent")
            rows = _rows(cur)
            is_horeca = bool(rows) and rows[0].get("regim") == "C_HORECA"

        regim, motiv = sda_rules.classify_regime(suprafata, tip, bool(is_horeca))

        params = {
            "unit_id": unit_id,
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

        if unit_id is not None:
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
                message = r.get("message") or "Eroare la salvarea unitatii"
                # FK-ul e adevăratul garant, dar restul modulului traduce
                # fiecare constrângere într-o frază — nu lăsăm un ORA brut
                # în banner-ul operatorului.
                if "ORA-02291" in message:
                    message = "Participantul indicat nu exista"
                return _fail(message)
            if unit_id is not None and not r.get("rowcount"):
                return _fail(f"Unitatea {unit_id} nu mai exista")
            jr = db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES ('UNIT_SAVE', 'SDA_UNIT', "
                ":entitate_id, :utilizator, :detalii)",
                {"entitate_id": unit_id,
                 "utilizator": username,
                 "detalii": (f"{payload.get('denumire')} -> "
                             f"{regim or 'FARA REGIM'}")[:1000]})
            if not jr.get("success"):
                return _fail(jr.get("message") or "Eroare la scrierea in jurnal")
            db.connection.commit()
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
                # Сравнивать только режим мало: исправленная площадь внутри
                # той же полосы или уточнённая формулировка оставили бы
                # REGIM_MOTIV и DATA_EVALUARE от прошлой оценки, а модуль
                # предъявляет их как основание досье.
                if (regim, motiv) == (unit.get("regim"),
                                      unit.get("regim_motiv")):
                    continue
                ur = db.execute_query(
                    "UPDATE SDA_UNIT SET REGIM = :regim, "
                    "REGIM_MOTIV = :regim_motiv, DATA_EVALUARE = :data_evaluare "
                    "WHERE UNIT_ID = :unit_id",
                    {"regim": regim, "regim_motiv": motiv,
                     "data_evaluare": date.today(), "unit_id": unit["unit_id"]})
                if not ur.get("success"):
                    # Un rând eșuat nu trebuie contorizat drept succes, iar
                    # lotul întreg nu se comite peste un update ratat.
                    return _fail(ur.get("message")
                                 or "Eroare la reclasificarea unitatilor")
                changed += 1
            # Intrarea de jurnal se scrie pe ACEEASI conexiune/tranzactie ca
            # UPDATE-urile de mai sus, inainte de commit: altfel un jurnal
            # scris separat (SDAStore.log, conexiune proprie) ar putea reusi
            # sau esua independent de lot, iar cele doua nu ar mai fi atomice.
            jr = db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES ('RECLASSIFY', 'SDA_UNIT', "
                ":entitate_id, :utilizator, :detalii)",
                {"entitate_id": None, "utilizator": username,
                 "detalii": (f"reclasificate {changed} unitati")[:1000]})
            if not jr.get("success"):
                return _fail(jr.get("message") or "Eroare la scrierea in jurnal")
            db.connection.commit()
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
        pack_id = payload.get("pack_id")
        if pack_id == "":
            pack_id = None
        params = {
            "pack_id": pack_id,
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

        if pack_id is not None:
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
            if pack_id is not None and not r.get("rowcount"):
                return _fail(f"Ambalajul {pack_id} nu mai exista")
            jr = db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES ('PACK_SAVE', 'SDA_PACK', "
                ":entitate_id, :utilizator, :detalii)",
                {"entitate_id": pack_id, "utilizator": username,
                 "detalii": (f"{params['ean']} "
                             f"{params['cat_admin']}/{params['cat_gest']}")[:1000]})
            if not jr.get("success"):
                return _fail(jr.get("message") or "Eroare la scrierea in jurnal")
            db.connection.commit()
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
                "SELECT T.TARIFF_ID, L.CATEGORIE, L.METODA, L.REUTILIZABIL, "
                "L.VALOARE_LEI "
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
        # Сначала период, потом категория внутри него. Иначе точное совпадение
        # категории из старого периода перебило бы «*» из нового: pick_value
        # перебирает категории снаружи, и порядок строк ему тут не помог бы.
        winner = lines[0].get("tariff_id")
        lines = [l for l in lines if l.get("tariff_id") == winner]
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

    # ── досье регистрации (пункт 78) ────────────────────────────────

    @staticmethod
    def registration_dossier(partic_id: int,
                             on_date: Optional[date] = None) -> Dict[str, Any]:
        """Восемь блоков уведомления о регистрации у Администратора.

        Блок «unitati» несёт площадь каждой точки: именно он решает,
        нужен ли сети собственный пункт возврата. Точки без площади
        считаются отдельно — досье с ними подавать нельзя.
        """
        on_date = on_date or date.today()
        with DatabaseModel() as db:
            p = db.execute_query(
                "SELECT PARTIC_ID, IDNO, DENUMIRE, CONTACT_NUME, CONTACT_TEL, "
                "CONTACT_EMAIL, VANDUT_AN_ANT, ESTIMARE_AN FROM SDA_PARTIC "
                "WHERE PARTIC_ID = :partic_id",
                {"partic_id": partic_id})
            if not p.get("success"):
                return _fail(p.get("message")
                             or "Eroare la citirea participantului")
            partics = _rows(p)
            if not partics:
                return _fail(f"Participantul {partic_id} nu exista")

            u = db.execute_query(
                "SELECT UNIT_ID, DENUMIRE, ADRESA, SUPRAFATA_MP, "
                "TIP_AMPLASAMENT, REGIM FROM SDA_UNIT "
                "WHERE PARTIC_ID = :partic_id ORDER BY DENUMIRE",
                {"partic_id": partic_id})
            if not u.get("success"):
                return _fail(u.get("message") or "Eroare la citirea unitatilor")
            units = _rows(u)

            r = db.execute_query(
                "SELECT PT.POINT_ID, PT.UNIT_ID, PT.ADRESA, PT.ORAR, PT.TIP "
                "FROM SDA_RETURN_POINT PT JOIN SDA_UNIT UN "
                "ON UN.UNIT_ID = PT.UNIT_ID WHERE UN.PARTIC_ID = :partic_id "
                "AND (PT.ACTIV_PANA IS NULL OR PT.ACTIV_PANA >= :d) "
                "AND (PT.ACTIV_DIN IS NULL OR PT.ACTIV_DIN <= :d)",
                {"partic_id": partic_id, "d": on_date})
            if not r.get("success"):
                return _fail(r.get("message")
                             or "Eroare la citirea punctelor de preluare")
            points = _rows(r)

        partic = partics[0]
        incomplet = sum(1 for x in units if not x.get("regim"))
        # Без пунктов возврата способ приёма не «MANUAL по умолчанию»,
        # а неизвестен: это юридическое заявление, а не значение по вкусу.
        metode = sorted({x["tip"] for x in points})

        # Единица в режиме A_PUNCT_PROPRIU обязана содержать собственный
        # пункт возврата (регламент). Если ни один пункт сети за ней не
        # заявлен, досье формально «полное» (у всех точек есть режим), но
        # подавать его нельзя — статутарное поле способа приёма пустое
        # именно для той точки, которая обязана его иметь.
        units_with_points = {p.get("unit_id") for p in points}
        missing_own_point = any(
            x.get("regim") == "A_PUNCT_PROPRIU"
            and x.get("unit_id") not in units_with_points
            for x in units)

        return _done({
            "identificare": {"idno": partic["idno"], "denumire": partic["denumire"]},
            "contact": {"nume": partic.get("contact_nume"),
                        "telefon": partic.get("contact_tel"),
                        "email": partic.get("contact_email")},
            "unitati": units,
            "punct_preluare": points,
            "modalitate_preluare": metode,
            "vandut_an_anterior": partic.get("vandut_an_ant"),
            "estimare_an_curent": partic.get("estimare_an"),
            "exceptii": [x for x in units if x.get("regim") == "B_EXCEPTIE_APL"],
            "incomplet": incomplet,
            # Досье с точками без площади подавать нельзя (см. docstring):
            # это правило должно быть в данных, а не только в тексте.
            "poate_fi_depus": incomplet == 0 and not missing_own_point,
        })
