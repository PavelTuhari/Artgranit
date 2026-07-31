"""Biro26/OfficePlus — achitare prin CREDITARE (rate).

RO: Lista DINAMICA a organizatiilor de creditare (TMS_CREDITE_ORG) si
    pachetele lor (TMS_CREDITE_PLAN), administrate in pagina
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

import re
from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _result, _rows


class Biro26Credit:

    # ── admin: organizatii ──

    @staticmethod
    def orgs_list(include_disabled: bool = True) -> Dict[str, Any]:
        try:
            w = "" if include_disabled else "WHERE o.ENABLED = '1'"
            return _result(Biro26DB().execute_query(
                f"SELECT o.ID, o.NAME, o.ENABLED, o.ORG_MODE, o.API_URL, "
                f"o.LOGO_URL, o.INFO, o.ORD, o.PROVIDER_ID, "
                f"(SELECT COUNT(*) FROM TMS_CREDITE_PLAN p "
                f" WHERE p.ORG_ID = o.ID) PLANS "
                f"FROM TMS_CREDITE_ORG o {w} ORDER BY o.ORD, o.ID"))
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
                      "o": int(d.get("ord") or 0),
                      "pid": int(d["provider_id"]) if d.get("provider_id") else None}
            if not params["n"]:
                return {"success": False, "error": "numele este obligatoriu"}
            if d.get("id"):
                params["id"] = int(d["id"])
                r = db.execute_dml(
                    "UPDATE TMS_CREDITE_ORG SET NAME=:n, ENABLED=:en, "
                    "ORG_MODE=:m, API_URL=:au, LOGO_URL=:lu, INFO=:inf, "
                    "PROVIDER_ID=:pid, ORD=:o "
                    "WHERE ID=:id", params)
            else:
                r = db.execute_dml(
                    "INSERT INTO TMS_CREDITE_ORG "
                    "(ID, NAME, ENABLED, ORG_MODE, API_URL, LOGO_URL, INFO, "
                    "PROVIDER_ID, ORD) "
                    "VALUES (TMS_CREDITE_ORG_SEQ.NEXTVAL, :n, :en, :m, :au, :lu, "
                    ":inf, :pid, :o)",
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
            return _result(Biro26DB().execute_query(
                f"SELECT p.*, o.NAME ORG_NAME FROM TMS_CREDITE_PLAN p "
                f"JOIN TMS_CREDITE_ORG o ON o.ID = p.ORG_ID {w} "
                f"ORDER BY p.ORG_ID, p.MONTHS_MIN, p.ID", params))
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
                    "UPDATE TMS_CREDITE_PLAN SET ORG_ID=:org, NAME=:n, "
                    "MONTHS_MIN=:m1, MONTHS_MAX=:m2, AMOUNT_MIN=:a1, AMOUNT_MAX=:a2, "
                    "MARKUP_PCT=:mk, ANNUAL_PCT=:an, MONTHLY_FEE_PCT=:mf, "
                    "ISSUE_FEE=:isf, AVANS_MIN_PCT=:av, ENABLED=:en, INFO=:inf "
                    "WHERE ID=:id", params)
            else:
                r = db.execute_dml(
                    "INSERT INTO TMS_CREDITE_PLAN (ID, ORG_ID, NAME, MONTHS_MIN, "
                    "MONTHS_MAX, AMOUNT_MIN, AMOUNT_MAX, MARKUP_PCT, ANNUAL_PCT, "
                    "MONTHLY_FEE_PCT, ISSUE_FEE, AVANS_MIN_PCT, ENABLED, INFO) "
                    "VALUES (TMS_CREDITE_PLAN_SEQ.NEXTVAL, :org, :n, :m1, :m2, "
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
                "DELETE FROM TMS_CREDITE_PLAN WHERE ID = :i", {"i": int(plan_id)})
            return ({"success": True} if r.get("success")
                    else {"success": False, "error": r.get("message")})
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── public: oferte + calcul ──

    @staticmethod
    def public_offers() -> Dict[str, Any]:
        """RO: organizatiile active cu pachetele active + providerul API legat.
        EN: enabled orgs with enabled plans and the linked API provider."""
        try:
            from models.credite_settings import biro26_settings
            orgs_res = _result(Biro26DB().execute_query(
                "SELECT o.ID, o.NAME, o.ORG_MODE, o.LOGO_URL, o.INFO, "
                "p.CODE PROVIDER_CODE, p.NAME PROVIDER_NAME, p.ICON PROVIDER_ICON "
                "FROM TMS_CREDITE_ORG o "
                "LEFT JOIN TMS_CREDITE_PROVIDER p "
                "  ON p.ID = o.PROVIDER_ID AND p.ENABLED = '1' "
                "WHERE o.ENABLED = '1' ORDER BY o.ORD, o.ID"))
            if not orgs_res.get("success"):
                return {"success": False, "error": orgs_res.get("error")}
            plans_res = _result(Biro26DB().execute_query(
                "SELECT p.ID, p.ORG_ID, p.NAME, p.MONTHS_MIN, p.MONTHS_MAX, "
                "p.AMOUNT_MIN, p.AMOUNT_MAX, p.MARKUP_PCT, p.ANNUAL_PCT, "
                "p.MONTHLY_FEE_PCT, p.ISSUE_FEE, p.AVANS_MIN_PCT "
                "FROM TMS_CREDITE_PLAN p JOIN TMS_CREDITE_ORG o ON o.ID = p.ORG_ID "
                "WHERE p.ENABLED = '1' AND o.ENABLED = '1' "
                "ORDER BY p.ORG_ID, p.MONTHS_MIN"))
            if not plans_res.get("success"):
                return {"success": False, "error": plans_res.get("error")}
            orgs, plans = orgs_res["data"], plans_res["data"]
            st = biro26_settings()
            # RO: reteaua de provideri se construieste O SINGURA data per apel —
            #     nu la fiecare organizatie — ca sa nu multiplicam accesul la
            #     setari (Biro26Credit._registry() nu bate in DB per-provider,
            #     dar tot ramine un cost de construit obiectele).
            reg = Biro26Credit._registry()
            for o in orgs:
                o["plans"] = [p for p in plans if p["org_id"] == o["id"]]
                code = o.pop("provider_code", None)
                prov = reg.get(code) if code else None
                o["provider"] = None if not code else {
                    "code": code,
                    "name": o.get("provider_name") or code,
                    "icon": o.get("provider_icon") or "🏦",
                    "configured": st.is_configured(code),
                    "capabilities": list(prov.capabilities) if prov is not None else []}
                o.pop("provider_name", None)
                o.pop("provider_icon", None)
            return {"success": True, "data": [o for o in orgs if o["plans"]]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def plan_get(plan_id: int) -> Optional[Dict[str, Any]]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT p.*, o.NAME ORG_NAME FROM TMS_CREDITE_PLAN p "
            "JOIN TMS_CREDITE_ORG o ON o.ID = p.ORG_ID "
            "WHERE p.ID = :i AND p.ENABLED = '1' AND o.ENABLED = '1'",
            {"i": int(plan_id)}))
        return rows[0] if rows else None

    # ── cereri de credit (flux bomba.md) — doua niveluri de integrare ──

    @staticmethod
    def request_create(d: Dict[str, Any]) -> Dict[str, Any]:
        """RO: cererea din formularul «Solicitati un imprumut»:
        1) se jurnalizeaza in TMS_CREDITE_REQ;
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
            "SELECT ID, NAME, ORG_MODE, API_URL FROM TMS_CREDITE_ORG "
            "WHERE ID = :i", {"i": int(p["org_id"])}))
        org = org_rows[0] if org_rows else {}
        # 1) jurnal
        # RO: rezervam ID-ul din secventa INAINTE de INSERT — subprocess worker-ul
        #     nu suporta bind-uri OUT, iar SELECT MAX(ID) ar fi supus unei curse
        #     la cereri concurente. NEXTVAL e atomic.
        seq = _rows(Biro26DB().execute_query(
            "SELECT TMS_CREDITE_REQ_SEQ.NEXTVAL ID FROM dual"))
        if not seq:
            return {"success": False, "error": "nu s-a putut aloca ID-ul cererii"}
        req_id = int(seq[0]["id"])
        r = Biro26DB().execute_dml(
            "INSERT INTO TMS_CREDITE_REQ (ID, ORG_ID, PLAN_ID, MONTHS, "
            "PRODUCT_COD, PRODUCT_NAME, QTY, AMOUNT, CREDIT_PRICE, MONTHLY, "
            "CLIENT_NAME, PHONE) VALUES (:id, "
            ":o, :p, :m, :pc, :pn, :q, :a, :cp, :mo, :cn, :ph)",
            {"id": req_id, "o": org.get("id"), "p": plan_id, "m": s["months"],
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
            except Exception as e:
                api_note = f"api error: {e}"
            Biro26DB().execute_dml(
                "UPDATE TMS_CREDITE_REQ SET API_STATUS = :s, LAST_CHECK = SYSDATE "
                "WHERE ID = :i", {"s": api_note[:60], "i": req_id})
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
            r = Biro26DB().execute_query(
                "SELECT * FROM (SELECT r.ID, o.NAME ORG_NAME, r.PRODUCT_NAME, "
                "r.QTY, r.AMOUNT, r.CREDIT_PRICE, r.MONTHS, r.MONTHLY, "
                "r.CLIENT_NAME, r.PHONE, r.STATUS, r.PROVIDER_CODE, r.EXT_REF, "
                "r.API_STATUS, r.IDNP_MASKED, "
                "TO_CHAR(r.LAST_CHECK,'DD.MM.YYYY HH24:MI') LAST_CHECK, "
                "TO_CHAR(r.CREATED,'DD.MM.YYYY HH24:MI') CREATED "
                "FROM TMS_CREDITE_REQ r "
                "LEFT JOIN TMS_CREDITE_ORG o ON o.ID = r.ORG_ID "
                "ORDER BY r.ID DESC) WHERE ROWNUM <= :n",
                {"n": max(1, min(int(limit), 500))})
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def request_status(req_id: int, status: str) -> Dict[str, Any]:
        if status not in ("NEW", "PROCESSED"):
            status = "PROCESSED"
        r = Biro26DB().execute_dml(
            "UPDATE TMS_CREDITE_REQ SET STATUS = :s WHERE ID = :i",
            {"s": status, "i": int(req_id)})
        return ({"success": True} if r.get("success")
                else {"success": False, "error": r.get("message")})

    @staticmethod
    def calc(amount: float, plan_id: int, months: Optional[int] = None,
             avans: float = 0) -> Dict[str, Any]:
        """RO: simulare ESTIMATIVA (vezi formula in docstring-ul modulului).
        EN: estimative credit simulation for one plan."""
        try:
            plan_id = int(plan_id)
        except (TypeError, ValueError):
            return {"success": False, "error": "pachet de credit inexistent"}
        p = Biro26Credit.plan_get(plan_id)
        if not p:
            return {"success": False, "error": "pachet de credit inexistent"}
        try:
            amount = round(float(amount), 2)
            avans = max(0.0, round(float(avans or 0), 2))
        except (TypeError, ValueError):
            return {"success": False, "error": "sume invalide"}
        try:
            m = int(months or p["months_max"])
        except (TypeError, ValueError):
            return {"success": False, "error": "luni invalide"}
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

    # ── провайдеры API (TMS_CREDITE_PROVIDER, настройки Biro26/11g) ──

    @staticmethod
    def _registry():
        """Реестр провайдеров с настройками из Oracle 11g (Biro26)."""
        from integrations import build_registry
        from models.credite_settings import biro26_settings
        return build_registry(biro26_settings())

    @staticmethod
    def providers_list() -> Dict[str, Any]:
        """RO: providerii API cu setari mascate (pentru admin).
        EN: API providers with masked secrets (admin page)."""
        try:
            from models.credite_settings import PROVIDER_DEFS, biro26_settings
            st = biro26_settings()
            out = []
            for code in sorted(PROVIDER_DEFS, key=lambda c: PROVIDER_DEFS[c]["ord"]):
                d = st.masked(code)
                if d is None:
                    spec = PROVIDER_DEFS[code]
                    d = {"code": code, "name": spec["name"], "enabled": False,
                         "env": "sandbox",
                         "base_url": spec["default_base_url"]["sandbox"],
                         "icon": spec["icon"], "color": spec["color"],
                         "params": {n: "" for n, _ in spec["params"]},
                         "secrets": [n for n, s in spec["params"] if s],
                         "configured": False,
                         "id": None, "info": "", "ord": spec["ord"],
                         "has_secret": {}}
                d["param_defs"] = [{"name": n, "secret": s}
                                   for n, s in PROVIDER_DEFS[code]["params"]]
                # RO: default_base_url pe mediu — admin-ul il foloseste ca sa
                #     completeze cimpul base_url la schimbarea env (Finding 2).
                d["default_base_url"] = PROVIDER_DEFS[code]["default_base_url"]
                out.append(d)
            return {"success": True, "data": out}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def provider_save(d: Dict[str, Any]) -> Dict[str, Any]:
        """RO: salveaza setarile providerului. Secret gol = «nu schimba»."""
        from models.credite_settings import PROVIDER_DEFS, biro26_settings
        code = (d.get("code") or "").strip().lower()
        if code not in PROVIDER_DEFS:
            return {"success": False, "error": f"provider necunoscut: {code}"}
        params = {n: (d.get("params") or {}).get(n) or ""
                  for n, _ in PROVIDER_DEFS[code]["params"]}
        return biro26_settings().save(
            code,
            enabled=d.get("enabled") in (True, "1", 1, "true"),
            env=(d.get("env") or "sandbox"),
            base_url=(d.get("base_url") or ""),
            params=params)

    # RO: providerul poate raspunde 200 cu un mesaj de autentificare esuata —
    #     nu tratam un astfel de raspuns drept conexiune reusita.
    _AUTH_FAIL_MARKERS = ("invalid user", "invalid password", "unauthor", "not authenticated",
                          "authentication", "401", "403", "50000")

    @staticmethod
    def _is_auth_failure(res: Dict[str, Any]) -> bool:
        """RO: cauta markerii de esec de autentificare DOAR in cimpurile
        textuale de status/mesaj (status, state, message, error) din res
        si din res["data"] — niciodata in cimpuri numerice (ex. max_amount),
        ca sa nu declansam fals-pozitive pe sume care contin «50000»."""
        data = res.get("data") if isinstance(res.get("data"), dict) else {}
        parts = []
        for holder in (res, data):
            for k in ("status", "state", "message", "error"):
                v = holder.get(k)
                if isinstance(v, str) and v:
                    parts.append(v.lower())
        text = " ".join(parts)
        return any(m in text for m in Biro26Credit._AUTH_FAIL_MARKERS)

    @staticmethod
    def _public_error(res: Dict[str, Any]) -> str:
        """RO: mesaj neutru pentru client — detaliile ramin in jurnal."""
        return ("Serviciul de creditare nu este disponibil momentan · "
                "Сервис кредитования временно недоступен")

    @staticmethod
    def _public_status_error() -> str:
        """RO: mesaj neutru pentru cazul cind providerul a acceptat cererea,
        dar UPDATE-ul statusului local a esuat — nu expunem textul brut al
        erorii Oracle. Detaliile raman in TMS_CREDITE_REQ_EVENT.
        EN: neutral message for provider-accepted-but-local-status-save-failed;
        raw Oracle error text stays in the event journal only."""
        return ("Cererea a fost trimisă cu succes, dar statusul nu este "
                "disponibil momentan · "
                "Заявка успешно отправлена, но статус временно недоступен")

    @staticmethod
    def provider_test(code: str) -> Dict[str, Any]:
        """RO: test de conexiune la provider (check_auth / preapproved de proba).
        Succesul e valid DOAR daca raspunsul nu contine markeri de esec de
        autentificare — unii provideri (ex. EasyCredit) raspund 200 cu
        Status = «Invalid User Name / Password - 50000», ceea ce NU e o
        conexiune reusita."""
        import time as _t
        prov = Biro26Credit._registry().get((code or "").strip().lower())
        if prov is None:
            return {"success": False, "error": f"provider necunoscut: {code}"}
        if not prov.is_configured():
            return {"success": False, "error": "providerul nu e configurat"}
        t0 = _t.time()
        if "check_auth" in prov.capabilities:
            res = prov.check_auth()
        else:
            res = prov.preapproved(uin=Biro26Credit._TEST_IDNP, amount=1000)
        ms = int((_t.time() - t0) * 1000)
        auth_fail = Biro26Credit._is_auth_failure(res)
        data = res.get("data") if isinstance(res.get("data"), dict) else {}
        reply_text = (res.get("error") or data.get("message")
                      or data.get("status") or data.get("state") or "")
        ok = bool(res.get("success")) and not auth_fail
        log_res = dict(res)
        if auth_fail:
            log_res["success"] = False
            log_res.setdefault("error", reply_text)
        Biro26Credit._log_event(None, code, "provider_test", log_res, ms, {})
        if not ok:
            return {"success": False,
                    "error": reply_text or res.get("error") or "conexiune eșuată",
                    "data": {"duration_ms": ms, "result": data}}
        return {"success": True,
                "data": {"duration_ms": ms, "result": data},
                "error": res.get("error")}

    # ── jurnal apeluri API ──

    _TEST_IDNP = "2000000000001"  # RO: IDNP de proba pentru testul de conexiune

    # RO: cimpurile permise in jurnal — restul (nume, data nasterii, IDNP) se taie.
    _EVENT_SAFE_KEYS = {"success", "preapproved", "max_amount", "status", "state",
                        "urn", "order_id", "message", "http_code", "error"}

    @staticmethod
    def _mask_idnp(idnp: str) -> str:
        s = (idnp or "").strip()
        if len(s) <= 6:
            return "*" * len(s)
        return f"{s[:2]}{'*' * (len(s) - 4)}{s[-2:]}"

    @staticmethod
    def _scrub(text: str) -> str:
        """RO: ascunde secventele lungi de cifre (IDNP, telefon), inclusiv cu separatori."""
        import re as _re

        def _hide(m):
            s = m.group(0)
            digits = [i for i, c in enumerate(s) if c.isdigit()]
            keep = set(digits[:2])
            return "".join(c if i in keep or not c.isdigit() else "*"
                           for i, c in enumerate(s))

        return _re.sub(r"\d(?:[\s\-./]?\d){6,}", _hide, text or "")

    @staticmethod
    def _scrub_value(v: Any) -> Any:
        """RO: curata recursiv orice structura — string, lista, dictionar."""
        if isinstance(v, str):
            return Biro26Credit._scrub(v)[:400]
        if isinstance(v, dict):
            return {k: Biro26Credit._scrub_value(x) for k, x in v.items()
                    if k in Biro26Credit._EVENT_SAFE_KEYS}
        if isinstance(v, (list, tuple)):
            return [Biro26Credit._scrub_value(x) for x in v][:20]
        if isinstance(v, (int, float, bool)) or v is None:
            return v
        return Biro26Credit._scrub(str(v))[:400]

    @staticmethod
    def _safe_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """RO: doar cimpurile din allowlist, cu cifrele lungi mascate (recursiv)."""
        src = dict(result or {})
        data = src.get("data") or {}
        out: Dict[str, Any] = {}
        for k in Biro26Credit._EVENT_SAFE_KEYS:
            for holder in (src, data if isinstance(data, dict) else {}):
                if k in holder and k not in out:
                    out[k] = Biro26Credit._scrub_value(holder[k])
        return out

    @staticmethod
    def _log_event(req_id: Optional[int], provider_code: str, op: str,
                   result: Dict[str, Any], duration_ms: int,
                   payload: Dict[str, Any]) -> None:
        """RO: scrie un rind in TMS_CREDITE_REQ_EVENT (best-effort, nu arunca)."""
        import json as _j
        try:
            safe = dict(payload or {})
            if "idnp" in safe:
                safe["idnp"] = Biro26Credit._mask_idnp(safe["idnp"])
            if "phone" in safe and safe["phone"]:
                safe["phone"] = str(safe["phone"])[:5] + "***"
            safe = {k: Biro26Credit._scrub_value(v) if k not in ("idnp", "phone") else v
                    for k, v in safe.items()}
            Biro26DB().execute_dml(
                "INSERT INTO TMS_CREDITE_REQ_EVENT (REQ_ID, PROVIDER_CODE, OP, "
                "HTTP_CODE, DURATION_MS, PAYLOAD, RESULT, IS_ERROR) "
                "VALUES (:r, :p, :o, :h, :d, :pl, :res, :e)",
                {"r": req_id, "p": (provider_code or "")[:30], "o": (op or "")[:30],
                 "h": result.get("http_code"), "d": duration_ms,
                 "pl": _j.dumps(safe, ensure_ascii=False)[:3900],
                 "res": _j.dumps(Biro26Credit._safe_result(result),
                                 ensure_ascii=False, default=str)[:3900],
                 "e": "0" if result.get("success") else "1"})
        except Exception:
            pass

    @staticmethod
    def request_events(req_id: int) -> Dict[str, Any]:
        """RO: jurnalul apelurilor API pentru o cerere."""
        try:
            return _result(Biro26DB().execute_query(
                "SELECT ID, PROVIDER_CODE, OP, HTTP_CODE, DURATION_MS, IS_ERROR, "
                "PAYLOAD, RESULT, TO_CHAR(CREATED,'DD.MM.YYYY HH24:MI:SS') CREATED "
                "FROM TMS_CREDITE_REQ_EVENT WHERE REQ_ID = :i ORDER BY ID",
                {"i": int(req_id)}))
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── fluxul API al clientului: preapproved -> submit -> status ──

    @staticmethod
    def _org_provider(org_id: int) -> Optional[Dict[str, Any]]:
        """RO: providerul legat de organizatie, sau None."""
        rows = _rows(Biro26DB().execute_query(
            "SELECT o.ID ORG_ID, o.NAME ORG_NAME, p.CODE PROVIDER_CODE "
            "FROM TMS_CREDITE_ORG o JOIN TMS_CREDITE_PROVIDER p "
            "  ON p.ID = o.PROVIDER_ID "
            "WHERE o.ID = :i AND o.ENABLED = '1' AND p.ENABLED = '1'",
            {"i": int(org_id)}))
        return rows[0] if rows else None

    @staticmethod
    def api_preapproved(d: Dict[str, Any]) -> Dict[str, Any]:
        """RO: verifica suma preaprobata la providerul organizatiei."""
        import time as _t
        try:
            org_id = int(d.get("org_id") or 0)
            amount = round(float(d.get("amount") or 0), 2)
        except (TypeError, ValueError):
            return {"success": False, "error": "date invalide"}
        idnp = (d.get("idnp") or "").strip()
        if len(idnp) < 10:
            return {"success": False, "error": "IDNP invalid"}
        link = Biro26Credit._org_provider(org_id)
        if not link:
            return {"success": False,
                    "error": "organizația nu are provider API configurat"}
        code = link["provider_code"]
        prov = Biro26Credit._registry().get(code)
        if prov is None or not prov.is_configured():
            return {"success": False, "error": f"providerul {code} nu e configurat"}
        t0 = _t.time()
        res = prov.preapproved(uin=idnp, amount=int(amount),
                               phone=(d.get("phone") or "").strip())
        ms = int((_t.time() - t0) * 1000)
        Biro26Credit._log_event(None, code, "preapproved", res, ms,
                                {"idnp": idnp, "amount": amount, "org_id": org_id})
        if not res.get("success"):
            # RO: eroare de la provider/configurare — detaliile raman in jurnal,
            #     clientului i se arata doar un mesaj neutru.
            return {"success": False, "error": Biro26Credit._public_error(res)}
        data = res.get("data") or {}
        # RO: preapproved:false e un raspuns LEGITIM al providerului, dar
        #     data["message"] poate contine detalii interne (ex. un mesaj de
        #     autentificare esuata a magazinului) — curatam si, daca e cazul,
        #     inlocuim cu mesajul neutru, ca sa nu para o decizie pe cererea
        #     clientului.
        msg = Biro26Credit._scrub(data.get("message") or "")
        if Biro26Credit._is_auth_failure(res):
            msg = Biro26Credit._public_error(res)
        return {"success": True, "data": {
            "preapproved": bool(data.get("preapproved")),
            "max_amount": float(data.get("max_amount") or 0),
            "message": msg}}

    @staticmethod
    def api_submit(d: Dict[str, Any]) -> Dict[str, Any]:
        """RO: creeaza cererea in TMS_CREDITE_REQ si o trimite la provider."""
        import time as _t
        name = (d.get("client_name") or "").strip()
        phone = (d.get("phone") or "").strip()
        idnp = (d.get("idnp") or "").strip()
        if not name or not phone:
            return {"success": False, "error": "Numele și telefonul sunt obligatorii"}
        if len(idnp) < 10:
            return {"success": False, "error": "IDNP invalid"}
        try:
            org_id = int(d.get("org_id") or 0)
            plan_id = int(d.get("plan_id") or 0)
            qty = max(1, int(d.get("qty") or 1))
            amount = round(float(d.get("amount") or 0), 2)
        except (TypeError, ValueError):
            return {"success": False, "error": "date invalide"}
        link = Biro26Credit._org_provider(org_id)
        if not link:
            return {"success": False,
                    "error": "organizația nu are provider API configurat"}
        code = link["provider_code"]
        prov = Biro26Credit._registry().get(code)
        if prov is None or not prov.is_configured():
            return {"success": False, "error": f"providerul {code} nu e configurat"}
        plan = Biro26Credit.plan_get(plan_id)
        if not plan or int(plan["org_id"]) != org_id:
            return {"success": False,
                    "error": "pachetul nu aparține organizației alese"}
        sim = Biro26Credit.calc(amount, plan_id, d.get("months"), 0)
        if not sim.get("success"):
            return sim
        s = sim["data"]
        product_name = (d.get("product_name") or "Comandă OfficePlus")[:300]
        # RO: rezervam ID-ul din secventa INAINTE de INSERT — subprocess worker-ul
        #     nu suporta bind-uri OUT, iar SELECT MAX(ID) ar fi supus unei curse
        #     la cereri concurente. NEXTVAL e atomic.
        seq = _rows(Biro26DB().execute_query(
            "SELECT TMS_CREDITE_REQ_SEQ.NEXTVAL ID FROM dual"))
        if not seq:
            return {"success": False, "error": "nu s-a putut aloca ID-ul cererii"}
        req_id = int(seq[0]["id"])
        ins = Biro26DB().execute_dml(
            "INSERT INTO TMS_CREDITE_REQ (ID, ORG_ID, PLAN_ID, MONTHS, PRODUCT_COD, "
            "PRODUCT_NAME, QTY, AMOUNT, CREDIT_PRICE, MONTHLY, CLIENT_NAME, PHONE, "
            "PROVIDER_CODE, IDNP_MASKED, API_STATUS) VALUES (:id, :o, :p, :m, :pc, "
            ":pn, :q, :a, :cp, :mo, :cn, :ph, :prc, :idm, 'SENDING')",
            {"id": req_id, "o": org_id, "p": plan_id, "m": s["months"],
             "pc": int(d.get("product_cod") or 0) or None, "pn": product_name,
             "q": qty, "a": amount, "cp": s["credit_price"], "mo": s["monthly"],
             "cn": name[:200], "ph": phone[:40], "prc": code[:30],
             "idm": Biro26Credit._mask_idnp(idnp)[:20]})
        if not ins.get("success"):
            return {"success": False, "error": ins.get("message")}
        kwargs = {"fio": name, "phone": phone, "uin": idnp,
                  "amount": int(round(s["credit_price"])),
                  "goods_price": int(round(s["credit_price"])),
                  "product_name": product_name,
                  "program_name": f"0-0-{s['months']}",
                  "order_id": f"OP-{req_id}", "user_pin": idnp,
                  "currency": "MDL"}
        t0 = _t.time()
        res = prov.submit(**kwargs)
        ms = int((_t.time() - t0) * 1000)
        Biro26Credit._log_event(req_id, code, "submit", res, ms,
                                {"idnp": idnp, "phone": phone, "amount": amount,
                                 "plan_id": plan_id, "months": s["months"]})
        data = res.get("data") or {}
        if code == "iute":
            ext_ref = data.get("order_id") or kwargs["order_id"]
        else:
            ext_ref = data.get("urn") or ""
        if res.get("success") and not ext_ref:
            res = {"success": False,
                   "error": "providerul nu a returnat referința cererii"}
        api_status = ("SENT" if res.get("success") else "ERROR")
        upd = Biro26DB().execute_dml(
            "UPDATE TMS_CREDITE_REQ SET EXT_REF = :x, API_STATUS = :s, "
            "LAST_CHECK = SYSDATE WHERE ID = :i",
            {"x": (ext_ref or "")[:120] or None, "s": api_status, "i": req_id})
        if not upd.get("success") and res.get("success"):
            # RO: providerul A ACCEPTAT cererea — doar salvarea locala a
            #     statusului a esuat. Textul brut al erorii Oracle (upd.message)
            #     ramine DOAR in jurnal; clientului i se arata mesaj neutru.
            Biro26Credit._log_event(
                req_id, code, "status_save",
                {"success": False, "error": upd.get("message")}, ms,
                {"ext_ref": ext_ref})
            return {"success": False,
                    "error": Biro26Credit._public_status_error(),
                    "data": {"req_id": req_id, "ext_ref": ext_ref}}
        if not res.get("success"):
            data = {"req_id": req_id}
            if not upd.get("success"):
                data["status_saved"] = False
            # RO: eroare de la provider/configurare — mesaj neutru catre client,
            #     detaliile raman in TMS_CREDITE_REQ_EVENT.
            return {"success": False, "error": Biro26Credit._public_error(res),
                    "data": data}
        return {"success": True, "data": {"req_id": req_id, "ext_ref": ext_ref,
                                          "status": api_status,
                                          "monthly": s["monthly"],
                                          "months": s["months"],
                                          "org": link["org_name"]}}

    @staticmethod
    def api_status(req_id: int, ext_ref: Optional[str] = None) -> Dict[str, Any]:
        """RO: reinterogheaza statusul cererii la provider si il salveaza.
        `ext_ref` != None inseamna acces public: se verifica detinerea cererii
        prin referinta primita la depunere (api_submit). None = apel din
        back-office (deja autorizat), fara verificare de detinere."""
        import time as _t
        rows = _rows(Biro26DB().execute_query(
            "SELECT ID, PROVIDER_CODE, EXT_REF, API_STATUS FROM TMS_CREDITE_REQ "
            "WHERE ID = :i", {"i": int(req_id)}))
        if not rows:
            return {"success": False, "error": "cerere inexistentă"}
        r = rows[0]
        # RO: acces public — cererea se identifica prin referinta primita la depunere.
        if ext_ref is not None and (r.get("ext_ref") or "") != ext_ref:
            return {"success": False, "error": "cerere inexistentă"}
        code, ext = r.get("provider_code"), r.get("ext_ref")
        if not code or not ext:
            return {"success": True, "data": {"status": r.get("api_status") or "",
                                              "ext_ref": ext or ""}}
        prov = Biro26Credit._registry().get(code)
        if prov is None or not prov.is_configured():
            return {"success": True, "data": {"status": r.get("api_status") or "",
                                              "ext_ref": ext}}
        t0 = _t.time()
        res = prov.check_status(urn=ext, order_id=ext)
        ms = int((_t.time() - t0) * 1000)
        Biro26Credit._log_event(int(req_id), code, "status", res, ms, {"ext_ref": ext})
        if not res.get("success"):
            return {"success": False, "error": res.get("error") or "eroare provider",
                    "data": {"status": r.get("api_status") or "", "ext_ref": ext}}
        st = ((res.get("data") or {}).get("status")
              or (res.get("data") or {}).get("state") or "")
        upd = Biro26DB().execute_dml(
            "UPDATE TMS_CREDITE_REQ SET API_STATUS = :s, LAST_CHECK = SYSDATE "
            "WHERE ID = :i", {"s": (st or "")[:60] or None, "i": int(req_id)})
        return {"success": True, "data": {"status": st, "ext_ref": ext,
                                          "saved": bool(upd.get("success"))}}
