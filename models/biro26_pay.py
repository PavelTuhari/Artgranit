"""Biro26 online payments: MAIB e-commerce (card) + MIA instant payments (QR).

RO: Plata online a "contului de plată" din magazinul public. Două metode:
    - MAIB e-commerce (api.maibmerchants.md v1): pay -> payUrl (redirect),
      confirmarea vine pe callback/okUrl și se VERIFICĂ server-side prin
      pay-info (statusul, RRN) — nu ne încredem în parametrii din URL.
    - MIA instant payments (QMoney, api.qiwi.md): create-qr-dynamic ->
      QR (base64) + link; statusul se citește prin get-qr-extension-status
      și prin callbackEchoUrl.
    Setările needitabile-secrete stau în YBIRO_SETTINGS (PAY_*); secretele
    (project secret / api secret) DOAR în .env (regula proiectului), editate
    din admin exact ca SMTP-ul. Plățile se jurnalizează în YBIRO_PAYMENTS.
EN: Online payment of the shop invoice. Two methods: MAIB e-commerce
    (redirect to payUrl, server-side verification via pay-info) and MIA
    instant payments (dynamic QR + status polling). Non-secret settings in
    YBIRO_SETTINGS; secrets ONLY in .env (edited from the admin page like
    SMTP). Payments are journaled in YBIRO_PAYMENTS.

Sursa de referință / reference sources:
github.com/Unisim-Soft-Com/Telegram-Bots/unisim_BileteGaraAutoBTA
(MaibAPI.php, functions.php qiwiAuth/qiwiGenerateQr, maib_collback.php).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from config import Config
from models.biro26_db import Biro26DB
from models.biro26_notify import Biro26Notify, _update_env_file
from models.biro26_oracle_store import Biro26Store, _rows

# RO: maib Checkout v2 (docs.maibmerchants.md/checkout): sesiune hosted
#     -> checkoutUrl; confirmare prin GET /v2/checkouts/{id}; refund prin
#     POST /v2/payments/{payId}/refund. Cheile: ClientId/ClientSecret
#     (+ SignatureKey pentru callback-uri).
# EN: maib Checkout v2 hosted session -> checkoutUrl; verified via
#     GET /v2/checkouts/{id}; refunds via /v2/payments/{payId}/refund.
MAIB_CHECKOUT_PROD = "https://api.maibmerchants.md"
MAIB_CHECKOUT_SANDBOX = "https://sandbox.maibmerchants.md"
MIA_API = "https://api.qiwi.md/"

# RO: cheile YBIRO_SETTINGS (nesecrete) / EN: non-secret settings keys
PAY_KEYS = ["PAY_ENABLED", "PAY_METHOD", "PAY_MERCHANT_NAME",
            "PAY_MIA_IBAN", "PAY_MAIB_PROJECT_ID", "PAY_MIA_API_KEY",
            # RO: '1' => mediul de TEST maib (sandbox.maibmerchants.md)
            # EN: '1' => maib sandbox environment
            "PAY_MAIB_SANDBOX",
            # RO: transfer MIA catre persoana fizica (numar de telefon) —
            #     metoda manuala, functioneaza IN PARALEL cu QR/MAIB
            # EN: MIA transfer to an individual's phone number — manual
            #     method, usable IN PARALLEL with the QR/MAIB methods
            "PAY_MIA_P2P_ENABLED", "PAY_MIA_P2P_PHONE"]

# RO: secretele -> .env (ca SMTP) / EN: secrets -> .env (like SMTP)
PAY_ENV = {
    "maib_project_secret": "BIRO26_MAIB_PROJECT_SECRET",   # ClientSecret
    "maib_signature_key": "BIRO26_MAIB_SIGNATURE_KEY",
    "mia_api_secret": "BIRO26_MIA_API_SECRET",
}


class Biro26Pay:

    # ── settings ──

    @staticmethod
    def get_settings() -> Dict[str, Any]:
        try:
            data = {k.lower(): Biro26Store.get_setting(k, "") for k in PAY_KEYS}
            data["pay_method"] = data["pay_method"] or "mia"
            data["maib_secret_set"] = bool(Config.BIRO26_MAIB_PROJECT_SECRET)
            data["mia_secret_set"] = bool(Config.BIRO26_MIA_API_SECRET)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_settings(d: Dict[str, Any]) -> Dict[str, Any]:
        try:
            env_pairs: Dict[str, str] = {}
            for fld, env_key in PAY_ENV.items():
                v = str(d.get(fld) or "").strip()
                if v:                       # empty = keep the current secret
                    env_pairs[env_key] = v
            if env_pairs:
                _update_env_file(env_pairs)
                for k, v in env_pairs.items():
                    os.environ[k] = v
                Config.BIRO26_MAIB_PROJECT_SECRET = os.environ.get(
                    "BIRO26_MAIB_PROJECT_SECRET", Config.BIRO26_MAIB_PROJECT_SECRET)
                Config.BIRO26_MAIB_SIGNATURE_KEY = os.environ.get(
                    "BIRO26_MAIB_SIGNATURE_KEY", Config.BIRO26_MAIB_SIGNATURE_KEY)
                Config.BIRO26_MIA_API_SECRET = os.environ.get(
                    "BIRO26_MIA_API_SECRET", Config.BIRO26_MIA_API_SECRET)
            for k in PAY_KEYS:
                if k.lower() in d:
                    r = Biro26Store.set_setting(k, str(d[k.lower()] or ""))
                    if not r.get("success"):
                        return r
            return Biro26Pay.get_settings()
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def public_methods() -> Dict[str, Any]:
        """RO: ce vede magazinul (fara secrete) / EN: what the shop sees."""
        s = (Biro26Pay.get_settings().get("data") or {})
        enabled = s.get("pay_enabled") == "1"
        methods = []
        if enabled:
            m = s.get("pay_method") or "mia"
            if m in ("mia", "both") and s.get("pay_mia_api_key") and s.get("mia_secret_set"):
                methods.append("mia")
            if m in ("maib", "both") and s.get("pay_maib_project_id") and s.get("maib_secret_set"):
                methods.append("maib")
            # RO: transferul MIA pe telefon e independent (paralel)
            # EN: the MIA phone transfer is an independent (parallel) method
            if s.get("pay_mia_p2p_enabled") == "1" and s.get("pay_mia_p2p_phone"):
                methods.append("miap2p")
        return {"success": True, "data": {"enabled": bool(methods),
                                          "methods": methods,
                                          "p2p_phone": s.get("pay_mia_p2p_phone") or ""}}

    # ── payment journal (YBIRO_PAYMENTS) ──

    @staticmethod
    def _record(doc_cod: int, method: str, order_id: str, pay_id: str,
                amount: float) -> None:
        Biro26DB().execute_dml(
            "INSERT INTO YBIRO_PAYMENTS (ID, DOC_COD, METHOD, ORDER_ID, PAY_ID, AMOUNT) "
            "VALUES (YBIRO_PAYMENTS_SEQ.NEXTVAL, :d, :m, :o, :p, :a)",
            {"d": int(doc_cod), "m": method, "o": order_id[:60],
             "p": (pay_id or "")[:80], "a": float(amount)})

    @staticmethod
    def _mark(order_id: str, status: str, rrn: str = "",
              details: str = "") -> None:
        Biro26DB().execute_dml(
            "UPDATE YBIRO_PAYMENTS SET STATUS = :s, RRN = :r, "
            "DETAILS = SUBSTR(:dt, 1, 1000), "
            "CONFIRMED = CASE WHEN :s2 = 'PAID' THEN SYSDATE ELSE CONFIRMED END "
            "WHERE ORDER_ID = :o",
            {"s": status, "r": (rrn or "")[:40], "dt": details or "",
             "s2": status, "o": order_id[:60]})

    @staticmethod
    def doc_status(doc_cod: int) -> Dict[str, Any]:
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT * FROM (SELECT METHOD, ORDER_ID, STATUS, AMOUNT, RRN, "
                "TO_CHAR(CREATED,'DD.MM.YYYY HH24:MI') CREATED "
                "FROM YBIRO_PAYMENTS WHERE DOC_COD = :d ORDER BY ID DESC) "
                "WHERE ROWNUM <= 5", {"d": int(doc_cod)}))
            return {"success": True, "data": rows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _doc_amount(doc_cod: int) -> Optional[float]:
        from models.biro26_report import Biro26Report
        d = Biro26Report.doc_data(int(doc_cod))
        if not d.get("success"):
            return None
        return float((d["data"] or {}).get("total") or 0)

    @staticmethod
    def _callback_base() -> str:
        s = Biro26Notify.get_settings().get("data") or {}
        return (s.get("notify_public_base") or "").strip().rstrip("/")

    @staticmethod
    def _notify_paid(order_id: str, method: str, amount: float) -> None:
        """RO: notificare fire-and-forget la plata reusita (canalele active).
        EN: fire-and-forget notification on successful payment."""
        import threading

        def _run():
            try:
                Biro26Notify.send_all(
                    f"Plată online primită — {order_id}",
                    f"💳 Plată online primită ({method.upper()})\n"
                    f"Comanda: {order_id}\nSuma: {amount:.2f} LEI")
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    # ── MAIB e-commerce Checkout v2 (hosted checkout session) ──

    @staticmethod
    def _maib_base(s: Dict[str, str]) -> str:
        return (MAIB_CHECKOUT_SANDBOX if s.get("pay_maib_sandbox") == "1"
                else MAIB_CHECKOUT_PROD)

    @staticmethod
    def _maib_token(s: Dict[str, str]) -> Optional[str]:
        try:
            r = requests.post(Biro26Pay._maib_base(s) + "/v2/auth/token",
                              timeout=20, json={
                "clientId": s.get("pay_maib_project_id") or "",
                "clientSecret": Config.BIRO26_MAIB_PROJECT_SECRET})
            return (r.json().get("result") or {}).get("accessToken")
        except Exception:
            return None

    @staticmethod
    def maib_create(doc_cod: int, client_ip: str,
                    client: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        s = (Biro26Pay.get_settings().get("data") or {})
        base = Biro26Pay._callback_base()
        if not base:
            return {"success": False,
                    "error": "URL public nesetat (Setări → notificări)"}
        amount = Biro26Pay._doc_amount(doc_cod)
        if not amount or amount <= 0:
            return {"success": False, "error": "suma documentului este 0"}
        token = Biro26Pay._maib_token(s)
        if not token:
            return {"success": False,
                    "error": "MAIB: autentificare eșuată (ClientId/ClientSecret)"}
        import time as _time
        order_id = f"BIRO26-{int(doc_cod)}-{int(_time.time())}"
        cb = f"{base}/api/biro26/pay/maib-callback?orderKey={order_id}"
        body = {
            "amount": round(float(amount), 2), "currency": "MDL",
            "language": "ro",
            "orderInfo": {
                "id": order_id,
                "description": f"Cont de plată OfficePlus (doc {doc_cod})"[:124],
            },
            "payerInfo": {"ip": client_ip or "127.0.0.1"},
            "callbackUrl": cb + "&typeurl=callbackurl",
            "successUrl": cb + "&typeurl=okurl",
            "failUrl": cb + "&typeurl=failurl",
        }
        if client:
            body["payerInfo"]["name"] = (client.get("name") or "")[:100]
            body["payerInfo"]["email"] = (client.get("email") or "")[:100]
        try:
            r = requests.post(Biro26Pay._maib_base(s) + "/v2/checkouts",
                              json=body, timeout=25,
                              headers={"Authorization": f"Bearer {token}"})
            res = (r.json() or {}).get("result") or {}
        except Exception as e:
            return {"success": False, "error": f"MAIB: {e}"}
        if not res.get("checkoutUrl") or not res.get("checkoutId"):
            return {"success": False,
                    "error": f"MAIB: inițializare eșuată — {r.text[:200]}"}
        # RO: PAY_ID = checkoutId; PaymentId-ul (pt. refund) vine la confirmare
        Biro26Pay._record(doc_cod, "maib", order_id, res["checkoutId"], amount)
        return {"success": True, "data": {"pay_url": res["checkoutUrl"],
                                          "order_id": order_id}}

    @staticmethod
    def maib_callback(order_key: str, pay_id: str, typeurl: str) -> Dict[str, Any]:
        """RO: confirmarea se VERIFICĂ prin GET /v2/checkouts/{id} — nu ne
        încredem în parametrii din URL/callback. PaymentId-ul (necesar la
        refund) se salvează în coloana RRN.
        EN: verified via GET /v2/checkouts/{id}; the PaymentId (needed for
        refunds) is stored in the RRN column."""
        rows = _rows(Biro26DB().execute_query(
            "SELECT DOC_COD, PAY_ID, AMOUNT, STATUS FROM YBIRO_PAYMENTS "
            "WHERE ORDER_ID = :o", {"o": (order_key or "")[:60]}))
        if not rows:
            return {"success": False, "paid": False, "error": "unknown order"}
        row = rows[0]
        if row["status"] == "PAID":
            return {"success": True, "paid": True}
        s = (Biro26Pay.get_settings().get("data") or {})
        token = Biro26Pay._maib_token(s)
        info: Dict[str, Any] = {}
        if token and row["pay_id"]:
            try:
                r = requests.get(
                    Biro26Pay._maib_base(s) + "/v2/checkouts/" + row["pay_id"],
                    timeout=20, headers={"Authorization": f"Bearer {token}"})
                info = (r.json() or {}).get("result") or {}
            except Exception:
                info = {}
        status = (info.get("status") or "")
        if status == "Completed":
            payment = info.get("payment") or {}
            payment_id = (payment.get("PaymentId") or payment.get("paymentId")
                          or payment.get("id") or "")
            Biro26Pay._mark(order_key, "PAID", str(payment_id)[:40],
                            f"maib checkout {typeurl}")
            Biro26Pay._notify_paid(order_key, "maib", float(row["amount"] or 0))
            return {"success": True, "paid": True}
        if status in ("Failed", "Expired", "Cancelled"):
            Biro26Pay._mark(order_key, "FAILED", "", f"maib {status}")
        return {"success": True, "paid": False}

    @staticmethod
    def maib_create_test(amount: float, description: str = "") -> Dict[str, Any]:
        """RO: link de plata de TEST (pagina admin «Test plăți MAIB»):
        checkout pe suma indicata, fara document ERP (DOC_COD=0 in jurnal).
        EN: ad-hoc TEST checkout link (admin page), no ERP document."""
        s = (Biro26Pay.get_settings().get("data") or {})
        base = Biro26Pay._callback_base()
        if not base:
            return {"success": False,
                    "error": "URL public nesetat (Setări → notificări)"}
        try:
            amount = round(float(amount), 2)
        except (TypeError, ValueError):
            return {"success": False, "error": "sumă invalidă"}
        if not 0 < amount <= 100000:
            return {"success": False, "error": "suma: 0.01 .. 100000"}
        token = Biro26Pay._maib_token(s)
        if not token:
            return {"success": False,
                    "error": "MAIB: autentificare eșuată (ClientId/ClientSecret)"}
        import time as _time
        order_id = f"BIRO26-TEST-{int(_time.time())}"
        cb = f"{base}/api/biro26/pay/maib-callback?orderKey={order_id}"
        body = {
            "amount": amount, "currency": "MDL", "language": "ro",
            "orderInfo": {"id": order_id,
                          "description": (description
                                          or f"Test maib Checkout {amount:.2f} MDL")[:124]},
            "callbackUrl": cb + "&typeurl=callbackurl",
            "successUrl": cb + "&typeurl=okurl",
            "failUrl": cb + "&typeurl=failurl",
        }
        try:
            r = requests.post(Biro26Pay._maib_base(s) + "/v2/checkouts",
                              json=body, timeout=25,
                              headers={"Authorization": f"Bearer {token}"})
            res = (r.json() or {}).get("result") or {}
        except Exception as e:
            return {"success": False, "error": f"MAIB: {e}"}
        if not res.get("checkoutUrl") or not res.get("checkoutId"):
            return {"success": False,
                    "error": f"MAIB: inițializare eșuată — {r.text[:200]}"}
        Biro26Pay._record(0, "maib", order_id, res["checkoutId"], amount)
        return {"success": True, "data": {
            "order_id": order_id, "pay_url": res["checkoutUrl"],
            "checkout_id": res["checkoutId"], "amount": amount,
            "sandbox": s.get("pay_maib_sandbox") == "1"}}

    @staticmethod
    def payments_list(limit: int = 30) -> Dict[str, Any]:
        """Recent payment attempts (journal) for the admin test page."""
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT * FROM (SELECT ID, DOC_COD, METHOD, ORDER_ID, PAY_ID, "
                "AMOUNT, STATUS, RRN, DETAILS, "
                "TO_CHAR(CREATED,'DD.MM.YYYY HH24:MI') CREATED "
                "FROM YBIRO_PAYMENTS ORDER BY ID DESC) "
                "WHERE ROWNUM <= :n", {"n": max(1, min(int(limit), 200))}))
            return {"success": True, "data": rows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def maib_refund(order_key: str, amount: Optional[float] = None,
                    reason: str = "Refund solicitat de comerciant") -> Dict[str, Any]:
        """RO: refund prin POST /v2/payments/{payId}/refund (payId = RRN
        salvat la confirmare). EN: refund via the Checkout v2 API."""
        rows = _rows(Biro26DB().execute_query(
            "SELECT DOC_COD, RRN, AMOUNT, STATUS FROM YBIRO_PAYMENTS "
            "WHERE ORDER_ID = :o", {"o": (order_key or "")[:60]}))
        if not rows:
            return {"success": False, "error": "plată necunoscută"}
        row = rows[0]
        if row["status"] != "PAID" or not row["rrn"]:
            return {"success": False,
                    "error": f"plata nu e confirmată (status {row['status']})"}
        s = (Biro26Pay.get_settings().get("data") or {})
        token = Biro26Pay._maib_token(s)
        if not token:
            return {"success": False, "error": "MAIB: autentificare eșuată"}
        try:
            r = requests.post(
                Biro26Pay._maib_base(s) + f"/v2/payments/{row['rrn']}/refund",
                json={"amount": round(float(amount or row["amount"] or 0), 2),
                      "reason": reason[:500]},
                timeout=25, headers={"Authorization": f"Bearer {token}"})
            b = r.json() or {}
        except Exception as e:
            return {"success": False, "error": f"MAIB refund: {e}"}
        if not b.get("ok"):
            return {"success": False,
                    "error": f"MAIB refund: {str(b.get('errors'))[:200]}"}
        res = b.get("result") or {}
        Biro26Pay._mark(order_key, "REFUNDED", row["rrn"],
                        f"refund {res.get('refundId')} {res.get('status')}")
        return {"success": True, "data": res}

    # ── MIA transfer la telefon (persoana fizica) — metoda manuala ──

    @staticmethod
    def miap2p_create(doc_cod: int) -> Dict[str, Any]:
        """RO: fara API — cumparatorul face transfer MIA din aplicatia
        bancii pe numarul de telefon setat; plata se inregistreaza PENDING
        si se confirma manual de operator (jurnal YBIRO_PAYMENTS).
        EN: no API — the buyer sends a MIA transfer from their banking app
        to the configured phone number; recorded PENDING, confirmed
        manually by the operator."""
        s = (Biro26Pay.get_settings().get("data") or {})
        phone = (s.get("pay_mia_p2p_phone") or "").strip()
        if not phone:
            return {"success": False,
                    "error": "MIA transfer: numărul de telefon nu e setat"}
        amount = Biro26Pay._doc_amount(doc_cod)
        if not amount or amount <= 0:
            return {"success": False, "error": "suma documentului este 0"}
        import time as _time
        order_id = f"BIRO26-{int(doc_cod)}-{int(_time.time())}"
        Biro26Pay._record(doc_cod, "miap2p", order_id, "", amount)
        return {"success": True, "data": {
            "order_id": order_id, "phone": phone,
            "amount": round(float(amount), 2),
            "merchant": s.get("pay_merchant_name") or "OfficePlus"}}

    # ── MIA instant payments (QMoney / api.qiwi.md) ──

    @staticmethod
    def _mia_token(s: Dict[str, str]) -> Optional[str]:
        try:
            r = requests.post(MIA_API + "v1/auth", timeout=20, json={
                "apiKey": s.get("pay_mia_api_key") or "",
                "apiSecret": Config.BIRO26_MIA_API_SECRET,
                "lifetimeMinutes": 30})
            return (r.json() or {}).get("token")
        except Exception:
            return None

    @staticmethod
    def mia_create(doc_cod: int) -> Dict[str, Any]:
        s = (Biro26Pay.get_settings().get("data") or {})
        base = Biro26Pay._callback_base()
        iban = (s.get("pay_mia_iban") or "").strip()
        if not iban:
            return {"success": False, "error": "MIA: IBAN nesetat (Setări)"}
        amount = Biro26Pay._doc_amount(doc_cod)
        if not amount or amount <= 0:
            return {"success": False, "error": "suma documentului este 0"}
        token = Biro26Pay._mia_token(s)
        if not token:
            return {"success": False,
                    "error": "MIA: autentificare eșuată (apiKey/apiSecret)"}
        import time as _time
        order_id = f"BIRO26-{int(doc_cod)}-{int(_time.time())}"
        payload = {
            "accountIBAN": iban,
            "name": (s.get("pay_merchant_name") or "OfficePlus")[:100],
            "amount": round(float(amount), 2),
            "comment": f"Cont de plata OfficePlus (doc {doc_cod})"[:120],
            "validSeconds": 900,
            "redirectURL": base or "https://officeplus.md/",
            "callbackEchoUrl": f"{base}/api/biro26/pay/mia-callback"
                               f"?orderKey={order_id}" if base else "",
            "merchantID": order_id, "end2EndID": order_id,
            "reference": order_id,
        }
        try:
            r = requests.post(MIA_API + "qr/create-qr-dynamic", json=payload,
                              timeout=25,
                              headers={"Authorization": f"Bearer {token}",
                                       "Content-Type": "application/json"})
            qr = r.json() or {}
        except Exception as e:
            return {"success": False, "error": f"MIA: {e}"}
        if not qr.get("image") or not qr.get("text"):
            return {"success": False,
                    "error": f"MIA: generare QR eșuată — {str(qr)[:200]}"}
        # RO: cheia reala din raspunsul QMoney este extensionUUID (verificat
        #     pe Test API); pastram fallback-urile istoric documentate.
        # EN: the real QMoney response key is extensionUUID (verified).
        pay_id = (qr.get("extensionUUID") or qr.get("qrExtensionUUID")
                  or qr.get("extensionGuid") or "")
        Biro26Pay._record(doc_cod, "mia", order_id, pay_id, amount)
        return {"success": True, "data": {
            "order_id": order_id, "qr_image": qr["image"],
            "qr_link": qr["text"], "valid_seconds": 900}}

    @staticmethod
    def mia_check(order_id: str) -> Dict[str, Any]:
        """RO: polling din UI — verifica statusul QR la MIA si actualizeaza
        jurnalul. EN: UI polling — live status check + journal update."""
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT DOC_COD, PAY_ID, AMOUNT, STATUS FROM YBIRO_PAYMENTS "
                "WHERE ORDER_ID = :o", {"o": (order_id or "")[:60]}))
            if not rows:
                return {"success": False, "error": "plată necunoscută"}
            row = rows[0]
            if row["status"] == "PAID":
                return {"success": True, "paid": True}
            s = (Biro26Pay.get_settings().get("data") or {})
            token = Biro26Pay._mia_token(s)
            if token and row["pay_id"]:
                r = requests.get(
                    MIA_API + "qr/get-qr-extension-status?extensionGuid="
                    + row["pay_id"], timeout=20,
                    headers={"Authorization": f"Bearer {token}"})
                st = (r.json() or {})
                status = str(st.get("extensionStatus") or st.get("status")
                             or st.get("state") or "").upper()
                if status in ("PAID", "EXECUTED", "SUCCESS", "COMPLETED"):
                    Biro26Pay._mark(order_id, "PAID", "", f"mia {status}")
                    Biro26Pay._notify_paid(order_id, "mia",
                                           float(row["amount"] or 0))
                    return {"success": True, "paid": True}
                if status in ("EXPIRED", "CANCELED", "CANCELLED"):
                    Biro26Pay._mark(order_id, "FAILED", "", f"mia {status}")
                    return {"success": True, "paid": False, "final": True}
            return {"success": True, "paid": False}
        except Exception as e:
            return {"success": False, "error": str(e)}
