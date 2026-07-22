"""Biro26/OfficePlus — achitare prin CREDITARE (rate).

RO: Lista DINAMICA a organizatiilor de creditare (YBIRO_CREDIT_ORG) si
    pachetele lor (YBIRO_CREDIT_PLAN), administrate in pagina
    /UNA.md/orasldev/biro26-credit-admin. ORG_MODE='manual' (conditiile
    se seteaza in admin) sau 'api' (integrare cu organizatia — API_URL;
    adaptorul per organizatie se adauga cind partenerul ofera API).

    METODA DE CALCUL la achitarea prin credit (sursa: tabelul EasyCredit,
    TaskDezvoltare/1 credite):
      pret_credit  = pret * (1 + MARKUP_PCT/100)      -- comisionul
                     (pachetele «0%»: costul e comisionul magazinului,
                      inclus in pretul marfii afisat la credit)
      finantat     = pret_credit - avans
      rata lunara  = finantat/luni
                     + finantat * ANNUAL_PCT/12/100    -- dobinda anuala
                     + finantat * MONTHLY_FEE_PCT/100  -- comision lunar
      total credit = avans + rata*luni + ISSUE_FEE
    Calcul ESTIMATIV — oferta ferma apartine organizatiei de creditare.
EN: dynamic credit-organizations list + plans; credit-mode price
    recalculation via the store-commission markup; estimative rate.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows


class Biro26Credit:

    # ── admin: organizatii ──

    @staticmethod
    def orgs_list(include_disabled: bool = True) -> Dict[str, Any]:
        try:
            w = "" if include_disabled else "WHERE o.ENABLED = '1'"
            rows = _rows(Biro26DB().execute_query(
                f"SELECT o.ID, o.NAME, o.ENABLED, o.ORG_MODE, o.API_URL, "
                f"o.LOGO_URL, o.INFO, o.ORD, "
                f"(SELECT COUNT(*) FROM YBIRO_CREDIT_PLAN p "
                f" WHERE p.ORG_ID = o.ID) PLANS "
                f"FROM YBIRO_CREDIT_ORG o {w} ORDER BY o.ORD, o.ID"))
            return {"success": True, "data": rows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def org_save(d: Dict[str, Any]) -> Dict[str, Any]:
        try:
            db = Biro26DB()
            params = {"n": (d.get("name") or "").strip()[:100],
                      "en": "1" if d.get("enabled") in (True, "1", 1) else "0",
                      "m": (d.get("org_mode") or "manual")[:10],
                      "au": (d.get("api_url") or "")[:400] or None,
                      "lu": (d.get("logo_url") or "")[:400] or None,
                      "inf": (d.get("info") or "")[:2000] or None,
                      "o": int(d.get("ord") or 0)}
            if not params["n"]:
                return {"success": False, "error": "numele este obligatoriu"}
            if d.get("id"):
                params["id"] = int(d["id"])
                r = db.execute_dml(
                    "UPDATE YBIRO_CREDIT_ORG SET NAME=:n, ENABLED=:en, "
                    "ORG_MODE=:m, API_URL=:au, LOGO_URL=:lu, INFO=:inf, ORD=:o "
                    "WHERE ID=:id", params)
            else:
                r = db.execute_dml(
                    "INSERT INTO YBIRO_CREDIT_ORG "
                    "(ID, NAME, ENABLED, ORG_MODE, API_URL, LOGO_URL, INFO, ORD) "
                    "VALUES (YBIRO_CREDIT_ORG_SEQ.NEXTVAL, :n, :en, :m, :au, :lu, :inf, :o)",
                    params)
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── admin: pachete ──

    @staticmethod
    def plans_list(org_id: Optional[int] = None) -> Dict[str, Any]:
        try:
            w, params = "", {}
            if org_id:
                w, params = "WHERE p.ORG_ID = :o", {"o": int(org_id)}
            rows = _rows(Biro26DB().execute_query(
                f"SELECT p.*, o.NAME ORG_NAME FROM YBIRO_CREDIT_PLAN p "
                f"JOIN YBIRO_CREDIT_ORG o ON o.ID = p.ORG_ID {w} "
                f"ORDER BY p.ORG_ID, p.MONTHS_MIN, p.ID", params))
            return {"success": True, "data": rows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def plan_save(d: Dict[str, Any]) -> Dict[str, Any]:
        try:
            def num(k, dflt=0):
                v = d.get(k)
                return float(v) if v not in (None, "") else dflt
            params = {"org": int(d.get("org_id") or 0),
                      "n": (d.get("name") or "").strip()[:120],
                      "m1": int(num("months_min", 1)),
                      "m2": int(num("months_max", 1)),
                      "a1": num("amount_min", 1000), "a2": num("amount_max", 100000),
                      "mk": num("markup_pct"), "an": num("annual_pct"),
                      "mf": num("monthly_fee_pct"), "isf": num("issue_fee"),
                      "av": num("avans_min_pct"),
                      "en": "1" if d.get("enabled") in (True, "1", 1) else "0",
                      "inf": (d.get("info") or "")[:2000] or None}
            if not params["n"] or not params["org"]:
                return {"success": False, "error": "org_id si numele sunt obligatorii"}
            if params["m2"] < params["m1"]:
                params["m2"] = params["m1"]
            db = Biro26DB()
            if d.get("id"):
                params["id"] = int(d["id"])
                r = db.execute_dml(
                    "UPDATE YBIRO_CREDIT_PLAN SET ORG_ID=:org, NAME=:n, "
                    "MONTHS_MIN=:m1, MONTHS_MAX=:m2, AMOUNT_MIN=:a1, AMOUNT_MAX=:a2, "
                    "MARKUP_PCT=:mk, ANNUAL_PCT=:an, MONTHLY_FEE_PCT=:mf, "
                    "ISSUE_FEE=:isf, AVANS_MIN_PCT=:av, ENABLED=:en, INFO=:inf "
                    "WHERE ID=:id", params)
            else:
                r = db.execute_dml(
                    "INSERT INTO YBIRO_CREDIT_PLAN (ID, ORG_ID, NAME, MONTHS_MIN, "
                    "MONTHS_MAX, AMOUNT_MIN, AMOUNT_MAX, MARKUP_PCT, ANNUAL_PCT, "
                    "MONTHLY_FEE_PCT, ISSUE_FEE, AVANS_MIN_PCT, ENABLED, INFO) "
                    "VALUES (YBIRO_CREDIT_PLAN_SEQ.NEXTVAL, :org, :n, :m1, :m2, "
                    ":a1, :a2, :mk, :an, :mf, :isf, :av, :en, :inf)", params)
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def plan_delete(plan_id: int) -> Dict[str, Any]:
        try:
            r = Biro26DB().execute_dml(
                "DELETE FROM YBIRO_CREDIT_PLAN WHERE ID = :i", {"i": int(plan_id)})
            return ({"success": True} if r.get("success")
                    else {"success": False, "error": r.get("message")})
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── public: oferte + calcul ──

    @staticmethod
    def public_offers() -> Dict[str, Any]:
        """RO: organizatiile active cu pachetele active (pentru magazin).
        EN: enabled orgs with enabled plans, for the public shop."""
        try:
            orgs = _rows(Biro26DB().execute_query(
                "SELECT ID, NAME, ORG_MODE, LOGO_URL, INFO FROM YBIRO_CREDIT_ORG "
                "WHERE ENABLED = '1' ORDER BY ORD, ID"))
            plans = _rows(Biro26DB().execute_query(
                "SELECT p.ID, p.ORG_ID, p.NAME, p.MONTHS_MIN, p.MONTHS_MAX, "
                "p.AMOUNT_MIN, p.AMOUNT_MAX, p.MARKUP_PCT, p.ANNUAL_PCT, "
                "p.MONTHLY_FEE_PCT, p.ISSUE_FEE, p.AVANS_MIN_PCT "
                "FROM YBIRO_CREDIT_PLAN p JOIN YBIRO_CREDIT_ORG o ON o.ID = p.ORG_ID "
                "WHERE p.ENABLED = '1' AND o.ENABLED = '1' "
                "ORDER BY p.ORG_ID, p.MONTHS_MIN"))
            for o in orgs:
                o["plans"] = [p for p in plans if p["org_id"] == o["id"]]
            return {"success": True, "data": [o for o in orgs if o["plans"]]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def plan_get(plan_id: int) -> Optional[Dict[str, Any]]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT p.*, o.NAME ORG_NAME FROM YBIRO_CREDIT_PLAN p "
            "JOIN YBIRO_CREDIT_ORG o ON o.ID = p.ORG_ID "
            "WHERE p.ID = :i AND p.ENABLED = '1' AND o.ENABLED = '1'",
            {"i": int(plan_id)}))
        return rows[0] if rows else None

    # ── cereri de credit (flux bomba.md) — doua niveluri de integrare ──

    @staticmethod
    def request_create(d: Dict[str, Any]) -> Dict[str, Any]:
        """RO: cererea din formularul «Solicitati un imprumut»:
        1) se jurnalizeaza in YBIRO_CREDIT_REQ;
        2) nivelul de integrare per organizatie (ORG_MODE):
           'manual' (minim) — notificare magazinului (managerul suna);
           'api' (maxim)    — cererea se trimite si la API_URL-ul
                              organizatiei (JSON, best-effort).
        EN: journal + notify (manual) or forward to the org API (api)."""
        name = (d.get("client_name") or "").strip()
        phone = (d.get("phone") or "").strip()
        if not name or not phone:
            return {"success": False,
                    "error": "Numele și telefonul sunt obligatorii"}
        try:
            plan_id = int(d.get("plan_id") or 0)
            qty = max(1, int(d.get("qty") or 1))
            amount = round(float(d.get("amount") or 0), 2)
        except (TypeError, ValueError):
            return {"success": False, "error": "date invalide"}
        sim = Biro26Credit.calc(amount, plan_id, d.get("months"), 0)
        if not sim.get("success"):
            return sim
        s = sim["data"]
        p = Biro26Credit.plan_get(plan_id)
        org_rows = _rows(Biro26DB().execute_query(
            "SELECT ID, NAME, ORG_MODE, API_URL FROM YBIRO_CREDIT_ORG "
            "WHERE ID = :i", {"i": int(p["org_id"])}))
        org = org_rows[0] if org_rows else {}
        # 1) jurnal
        r = Biro26DB().execute_dml(
            "INSERT INTO YBIRO_CREDIT_REQ (ID, ORG_ID, PLAN_ID, MONTHS, "
            "PRODUCT_COD, PRODUCT_NAME, QTY, AMOUNT, CREDIT_PRICE, MONTHLY, "
            "CLIENT_NAME, PHONE) VALUES (YBIRO_CREDIT_REQ_SEQ.NEXTVAL, "
            ":o, :p, :m, :pc, :pn, :q, :a, :cp, :mo, :cn, :ph)",
            {"o": org.get("id"), "p": plan_id, "m": s["months"],
             "pc": int(d.get("product_cod") or 0) or None,
             "pn": (d.get("product_name") or "")[:300],
             "q": qty, "a": amount, "cp": s["credit_price"],
             "mo": s["monthly"], "cn": name[:200], "ph": phone[:40]})
        if not r.get("success"):
            return {"success": False, "error": r.get("message")}
        # 2a) nivel MAXIM: trimitere la API-ul organizatiei (daca e setat)
        api_note = ""
        if org.get("org_mode") == "api" and org.get("api_url"):
            try:
                import requests as _rq
                resp = _rq.post(org["api_url"], timeout=20, json={
                    "source": "officeplus.md", "client_name": name,
                    "phone": phone, "product": d.get("product_name"),
                    "qty": qty, "amount": amount,
                    "credit_price": s["credit_price"], "plan": s["plan"],
                    "months": s["months"], "monthly": s["monthly"]})
                api_note = f"HTTP {resp.status_code}"
                Biro26DB().execute_dml(
                    "UPDATE YBIRO_CREDIT_REQ SET API_SENT = '1', "
                    "API_RESULT = :r WHERE ID = "
                    "(SELECT MAX(ID) FROM YBIRO_CREDIT_REQ)",
                    {"r": api_note[:400]})
            except Exception as e:
                api_note = f"api error: {e}"
        # 2b) nivel MINIM (mereu): notificare magazinului
        try:
            import threading
            from models.biro26_notify import Biro26Notify

            def _notify():
                try:
                    Biro26Notify.send_all(
                        f"Cerere credit/rate — {name}",
                        f"💳 Cerere NOUĂ de credit/rate ({org.get('name')})\n"
                        f"Client: {name} · tel. {phone}\n"
                        f"Produs: {d.get('product_name')} × {qty}\n"
                        f"Preț standard: {amount:.2f} lei\n"
                        f"Preț în rate: {s['credit_price']:.2f} lei\n"
                        f"Pachet: {s['plan']} · {s['months']} luni · "
                        f"rata {s['monthly']:.2f} lei/lună"
                        + (f"\nAPI: {api_note}" if api_note else ""))
                except Exception:
                    pass

            threading.Thread(target=_notify, daemon=True).start()
        except Exception:
            pass
        return {"success": True, "data": {"monthly": s["monthly"],
                                          "months": s["months"],
                                          "org": org.get("name")}}

    @staticmethod
    def requests_list(limit: int = 50) -> Dict[str, Any]:
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT * FROM (SELECT r.ID, o.NAME ORG_NAME, r.PRODUCT_NAME, "
                "r.QTY, r.AMOUNT, r.CREDIT_PRICE, r.MONTHS, r.MONTHLY, "
                "r.CLIENT_NAME, r.PHONE, r.STATUS, r.API_SENT, r.API_RESULT, "
                "TO_CHAR(r.CREATED,'DD.MM.YYYY HH24:MI') CREATED "
                "FROM YBIRO_CREDIT_REQ r "
                "LEFT JOIN YBIRO_CREDIT_ORG o ON o.ID = r.ORG_ID "
                "ORDER BY r.ID DESC) WHERE ROWNUM <= :n",
                {"n": max(1, min(int(limit), 500))}))
            return {"success": True, "data": rows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def request_status(req_id: int, status: str) -> Dict[str, Any]:
        if status not in ("NEW", "PROCESSED"):
            status = "PROCESSED"
        r = Biro26DB().execute_dml(
            "UPDATE YBIRO_CREDIT_REQ SET STATUS = :s WHERE ID = :i",
            {"s": status, "i": int(req_id)})
        return ({"success": True} if r.get("success")
                else {"success": False, "error": r.get("message")})

    @staticmethod
    def calc(amount: float, plan_id: int, months: Optional[int] = None,
             avans: float = 0) -> Dict[str, Any]:
        """RO: simulare ESTIMATIVA (vezi formula in docstring-ul modulului).
        EN: estimative credit simulation for one plan."""
        p = Biro26Credit.plan_get(plan_id)
        if not p:
            return {"success": False, "error": "pachet de credit inexistent"}
        try:
            amount = round(float(amount), 2)
            avans = max(0.0, round(float(avans or 0), 2))
        except (TypeError, ValueError):
            return {"success": False, "error": "sume invalide"}
        m = int(months or p["months_max"])
        m = max(int(p["months_min"]), min(m, int(p["months_max"])))
        credit_price = round(amount * (1 + float(p["markup_pct"] or 0) / 100), 2)
        avans_min = round(credit_price * float(p["avans_min_pct"] or 0) / 100, 2)
        if avans < avans_min:
            avans = avans_min
        financed = round(credit_price - avans, 2)
        if financed < float(p["amount_min"] or 0):
            return {"success": False,
                    "error": f"suma finanțată sub minim ({p['amount_min']:.0f} lei)"}
        if financed > float(p["amount_max"] or 1e12):
            return {"success": False,
                    "error": f"suma finanțată peste maxim ({p['amount_max']:.0f} lei)"}
        monthly = round(financed / m
                        + financed * float(p["annual_pct"] or 0) / 12 / 100
                        + financed * float(p["monthly_fee_pct"] or 0) / 100, 2)
        total = round(avans + monthly * m + float(p["issue_fee"] or 0), 2)
        return {"success": True, "data": {
            "plan_id": p["id"], "plan": p["name"], "org": p["org_name"],
            "months": m, "price": amount, "credit_price": credit_price,
            "markup_pct": float(p["markup_pct"] or 0),
            "avans": avans, "financed": financed,
            "monthly": monthly, "issue_fee": float(p["issue_fee"] or 0),
            "total": total,
            "overcost": round(total - amount, 2)}}
