"""Biro26 notifications: new orders / invoices -> email, Telegram, WhatsApp.

RO: Setarile (destinatari, comutatoare, token-uri messenger) se editeaza in
    pagina de admin si stau in YBIRO_SETTINGS (y_ai_BIRO26.set_setting);
    secretele SMTP raman DOAR in .env (regula proiectului). Trimiterea la
    crearea documentului e fire-and-forget (thread daemon) — cosul nu
    asteapta si nu esueaza din cauza notificarilor.
EN: Settings (recipients, toggles, messenger tokens) are edited in the
    admin page and live in YBIRO_SETTINGS; SMTP secrets stay ONLY in .env
    (project rule). Sending on document creation is fire-and-forget
    (daemon thread) — the cart never waits on or fails because of
    notifications. WhatsApp uses CallMeBot (free, per-phone apikey);
    Telegram uses the Bot API sendMessage.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

import requests

from config import Config
from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows

# RO: cheile YBIRO_SETTINGS / EN: the YBIRO_SETTINGS keys
KEYS = [
    "NOTIFY_EMAIL_ENABLED", "NOTIFY_EMAIL_TO",
    "NOTIFY_TG_ENABLED", "NOTIFY_TG_TOKEN", "NOTIFY_TG_CHAT",
    "NOTIFY_WA_ENABLED", "NOTIFY_WA_PHONE", "NOTIFY_WA_APIKEY",
]


class Biro26Notify:

    # ── settings over YBIRO_SETTINGS ──

    @staticmethod
    def get_settings() -> Dict[str, Any]:
        try:
            marks = ",".join(f":k{i}" for i in range(len(KEYS)))
            rows = _rows(Biro26DB().execute_query(
                f"SELECT skey, sval FROM YBIRO_SETTINGS WHERE skey IN ({marks})",
                {f"k{i}": k for i, k in enumerate(KEYS)}))
            vals = {r["skey"].lower(): (r["sval"] or "") for r in rows}
            data = {k.lower(): vals.get(k.lower(), "") for k in KEYS}
            data["smtp_configured"] = bool(Config.BIRO26_SMTP_HOST)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_settings(d: Dict[str, Any]) -> Dict[str, Any]:
        try:
            steps = []
            for k in KEYS:
                if k.lower() in d:
                    steps.append({
                        "sql": "BEGIN y_ai_BIRO26.set_setting(:k, :v); END;",
                        "params": {"k": k, "v": str(d[k.lower()] or "")[:400]},
                        "kind": "dml"})
            if not steps:
                return {"success": False, "error": "nothing to save"}
            r = Biro26DB().execute_script(steps)
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return Biro26Notify.get_settings()
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── channels (each returns {'success', 'error'?}) ──

    @staticmethod
    def _send_email(s: Dict[str, str], subject: str, body: str) -> Dict[str, Any]:
        import smtplib
        from email.mime.text import MIMEText
        if not Config.BIRO26_SMTP_HOST:
            return {"success": False,
                    "error": "SMTP is not configured (.env BIRO26_SMTP_HOST/USER/PASSWORD)"}
        to = [a.strip() for a in (s.get("notify_email_to") or "").split(",") if a.strip()]
        if not to:
            return {"success": False, "error": "no recipients (NOTIFY_EMAIL_TO)"}
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = Config.BIRO26_SMTP_FROM or Config.BIRO26_SMTP_USER
        msg["To"] = ", ".join(to)
        try:
            cls = smtplib.SMTP_SSL if Config.BIRO26_SMTP_SSL else smtplib.SMTP
            with cls(Config.BIRO26_SMTP_HOST, Config.BIRO26_SMTP_PORT, timeout=20) as sm:
                if not Config.BIRO26_SMTP_SSL:
                    sm.starttls()
                if Config.BIRO26_SMTP_USER:
                    sm.login(Config.BIRO26_SMTP_USER, Config.BIRO26_SMTP_PASSWORD)
                sm.sendmail(msg["From"], to, msg.as_string())
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"smtp: {e}"}

    @staticmethod
    def _send_telegram(s: Dict[str, str], text: str) -> Dict[str, Any]:
        token = (s.get("notify_tg_token") or "").strip()
        chat = (s.get("notify_tg_chat") or "").strip()
        if not token or not chat:
            return {"success": False, "error": "Telegram token/chat_id missing"}
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text}, timeout=15)
            b = r.json()
            if not b.get("ok"):
                return {"success": False, "error": f"telegram: {b.get('description')}"}
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"telegram: {e}"}

    @staticmethod
    def _send_whatsapp(s: Dict[str, str], text: str) -> Dict[str, Any]:
        phone = (s.get("notify_wa_phone") or "").strip()
        apikey = (s.get("notify_wa_apikey") or "").strip()
        if not phone or not apikey:
            return {"success": False, "error": "WhatsApp phone/apikey missing (CallMeBot)"}
        try:
            r = requests.get("https://api.callmebot.com/whatsapp.php",
                             params={"phone": phone, "text": text, "apikey": apikey},
                             timeout=25)
            if r.status_code != 200 or "ERROR" in r.text.upper()[:400]:
                return {"success": False, "error": f"whatsapp: HTTP {r.status_code} {r.text[:150]}"}
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"whatsapp: {e}"}

    # ── public API ──

    @staticmethod
    def send_all(subject: str, text: str,
                 settings: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Send through every ENABLED channel; per-channel results."""
        s = settings or (Biro26Notify.get_settings().get("data") or {})
        res = {}
        if s.get("notify_email_enabled") == "1":
            res["email"] = Biro26Notify._send_email(s, subject, text)
        if s.get("notify_tg_enabled") == "1":
            res["telegram"] = Biro26Notify._send_telegram(s, text)
        if s.get("notify_wa_enabled") == "1":
            res["whatsapp"] = Biro26Notify._send_whatsapp(s, text)
        return {"success": True, "data": res}

    @staticmethod
    def test_channel(channel: str) -> Dict[str, Any]:
        """Synchronous test send from the admin page (ignores the toggles)."""
        s = Biro26Notify.get_settings().get("data") or {}
        text = "Test Biro26/OfficePlus: canalul de notificari functioneaza ✔"
        if channel == "email":
            return Biro26Notify._send_email(s, "Biro26 — test notificare", text)
        if channel == "telegram":
            return Biro26Notify._send_telegram(s, text)
        if channel == "whatsapp":
            return Biro26Notify._send_whatsapp(s, text)
        return {"success": False, "error": f"unknown channel: {channel}"}

    @staticmethod
    def notify_new_doc(cod: int, nrset, client_name: str, total: float,
                       source: str = "magazin") -> None:
        """Fire-and-forget notification about a freshly created invoice."""
        subject = f"Cont de plată nou № {nrset} — {client_name}"
        text = (f"🧾 Cont de plată nou (Biro26/{source})\n"
                f"Nr.: {nrset} (document COD {cod})\n"
                f"Client: {client_name}\n"
                f"Suma: {total:.2f} LEI")

        def _run():
            try:
                Biro26Notify.send_all(subject, text)
            except Exception:
                pass  # never disturb the request path

        threading.Thread(target=_run, daemon=True).start()
