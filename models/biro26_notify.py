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

import os
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
    # RO: mod WhatsApp: 'callmebot' (text + link PDF) sau 'cloud' (WhatsApp
    #     Cloud API — trimite si FISIERUL PDF ca document).
    # EN: WhatsApp mode: 'callmebot' (text + PDF link) or 'cloud' (WhatsApp
    #     Cloud API — delivers the actual PDF as a document).
    "NOTIFY_WA_MODE", "NOTIFY_WA_CLOUD_TOKEN", "NOTIFY_WA_CLOUD_PHONE_ID",
    "NOTIFY_WA_CLOUD_TO",
    # RO: URL-ul public al site-ului pentru linkurile PDF semnate
    # EN: public site base URL for the signed PDF links
    "NOTIFY_PUBLIC_BASE",
]

# RO: campurile SMTP se editeaza tot in admin, dar se SCRIU in .env (regula
# proiectului: secretele nu stau in DB) si se aplica imediat in proces.
# EN: the SMTP fields are edited in the same admin page but are WRITTEN to
# .env (project rule: secrets never live in the DB) and applied to the
# running process immediately (no restart needed).
SMTP_ENV = {
    "smtp_host": "BIRO26_SMTP_HOST",
    "smtp_port": "BIRO26_SMTP_PORT",
    "smtp_user": "BIRO26_SMTP_USER",
    "smtp_password": "BIRO26_SMTP_PASSWORD",
    "smtp_from": "BIRO26_SMTP_FROM",
    "smtp_ssl": "BIRO26_SMTP_SSL",
}
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def _update_env_file(pairs: Dict[str, str]) -> None:
    """Update KEY=VALUE lines in .env preserving everything else (order,
    comments); missing keys are appended at the end."""
    lines = []
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()
    seen = set()
    out = []
    for ln in lines:
        key = ln.split("=", 1)[0].strip() if "=" in ln and not ln.lstrip().startswith("#") else None
        if key in pairs:
            out.append(f"{key}={pairs[key]}")
            seen.add(key)
        else:
            out.append(ln)
    missing = [k for k in pairs if k not in seen]
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.append("# Biro26 notifications SMTP (managed by the admin page)")
        out.extend(f"{k}={pairs[k]}" for k in missing)
    with open(_ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


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
            # RO: campurile SMTP vin din config/.env; parola NU se intoarce
            # EN: SMTP fields come from config/.env; the password is never echoed
            data["smtp_host"] = Config.BIRO26_SMTP_HOST
            data["smtp_port"] = str(Config.BIRO26_SMTP_PORT)
            data["smtp_user"] = Config.BIRO26_SMTP_USER
            data["smtp_from"] = Config.BIRO26_SMTP_FROM
            data["smtp_ssl"] = "1" if Config.BIRO26_SMTP_SSL else "0"
            data["smtp_has_password"] = bool(Config.BIRO26_SMTP_PASSWORD)
            data["smtp_configured"] = bool(Config.BIRO26_SMTP_HOST)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_settings(d: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # 1) SMTP -> .env (+ live update of the running process)
            env_pairs: Dict[str, str] = {}
            for fld, env_key in SMTP_ENV.items():
                if fld not in d:
                    continue
                v = str(d[fld] or "").strip()
                if fld == "smtp_password" and not v:
                    continue          # empty password field = keep the current one
                if fld == "smtp_port":
                    v = v or "587"
                if fld == "smtp_ssl":
                    v = "1" if v in ("1", "true", "on") else "0"
                env_pairs[env_key] = v
            if env_pairs:
                _update_env_file(env_pairs)
                for env_key, v in env_pairs.items():
                    os.environ[env_key] = v
                Config.BIRO26_SMTP_HOST = os.environ.get("BIRO26_SMTP_HOST", Config.BIRO26_SMTP_HOST)
                Config.BIRO26_SMTP_PORT = int(os.environ.get("BIRO26_SMTP_PORT", Config.BIRO26_SMTP_PORT) or 587)
                Config.BIRO26_SMTP_USER = os.environ.get("BIRO26_SMTP_USER", Config.BIRO26_SMTP_USER)
                if "BIRO26_SMTP_PASSWORD" in env_pairs:
                    Config.BIRO26_SMTP_PASSWORD = env_pairs["BIRO26_SMTP_PASSWORD"]
                Config.BIRO26_SMTP_FROM = os.environ.get("BIRO26_SMTP_FROM", "") or Config.BIRO26_SMTP_USER
                Config.BIRO26_SMTP_SSL = os.environ.get("BIRO26_SMTP_SSL", "0") in ("1", "true", "yes")

            # 2) everything else -> YBIRO_SETTINGS
            steps = []
            for k in KEYS:
                if k.lower() in d:
                    steps.append({
                        "sql": "BEGIN y_ai_BIRO26.set_setting(:k, :v); END;",
                        "params": {"k": k, "v": str(d[k.lower()] or "")[:400]},
                        "kind": "dml"})
            if steps:
                r = Biro26DB().execute_script(steps)
                if not r.get("success"):
                    return {"success": False, "error": r.get("message")}
            elif not env_pairs:
                return {"success": False, "error": "nothing to save"}
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
    def _send_whatsapp(s: Dict[str, str], text: str,
                       pdf_url: Optional[str] = None,
                       pdf_name: Optional[str] = None) -> Dict[str, Any]:
        """RO: mod 'cloud' (WhatsApp Cloud API) trimite si PDF-ul ca document;
        mod 'callmebot' trimite doar text (linkul PDF e deja in text).
        EN: 'cloud' mode (WhatsApp Cloud API) also delivers the PDF as a
        document; 'callmebot' is text-only (the PDF link is in the text)."""
        mode = (s.get("notify_wa_mode") or "callmebot").strip().lower()
        if mode == "cloud":
            token = (s.get("notify_wa_cloud_token") or "").strip()
            phone_id = (s.get("notify_wa_cloud_phone_id") or "").strip()
            to = ((s.get("notify_wa_cloud_to") or s.get("notify_wa_phone") or "")
                  .strip().lstrip("+"))
            if not token or not phone_id or not to:
                return {"success": False,
                        "error": "WhatsApp Cloud: token/phone_number_id/destinatar lipsesc"}
            try:
                if pdf_url:
                    payload = {"messaging_product": "whatsapp", "to": to,
                               "type": "document",
                               "document": {"link": pdf_url,
                                            "filename": pdf_name or "document.pdf",
                                            "caption": text[:1000]}}
                else:
                    payload = {"messaging_product": "whatsapp", "to": to,
                               "type": "text", "text": {"body": text}}
                r = requests.post(
                    f"https://graph.facebook.com/v20.0/{phone_id}/messages",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"}, timeout=25)
                b = r.json() if r.content else {}
                if r.status_code != 200 or not b.get("messages"):
                    err = (b.get("error") or {}).get("message") or r.text[:150]
                    return {"success": False, "error": f"whatsapp cloud: {err}"}
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": f"whatsapp cloud: {e}"}
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

    # ── signed public PDF links (WhatsApp/Telegram/email need no login) ──

    @staticmethod
    def pdf_sig(kind: str, cod: int) -> str:
        """RO: semnatura HMAC pentru accesul public la UN singur document.
        EN: HMAC signature granting public access to one document only."""
        import hashlib
        import hmac as _hmac
        key = (Config.BIRO26_API_TOKEN or Config.SECRET_KEY).encode("utf-8")
        return _hmac.new(key, f"{kind}:{int(cod)}".encode("utf-8"),
                         hashlib.sha256).hexdigest()

    @staticmethod
    def pdf_link(s: Dict[str, str], kind: str, cod: int) -> Optional[str]:
        base = (s.get("notify_public_base") or "").strip().rstrip("/")
        if not base:
            return None
        return (f"{base}/api/biro26/shop/report/{kind}/{int(cod)}"
                f"?sig={Biro26Notify.pdf_sig(kind, cod)}")

    # ── public API ──

    @staticmethod
    def send_all(subject: str, text: str,
                 settings: Optional[Dict[str, str]] = None,
                 pdf_url: Optional[str] = None,
                 pdf_name: Optional[str] = None) -> Dict[str, Any]:
        """Send through every ENABLED channel; per-channel results."""
        s = settings or (Biro26Notify.get_settings().get("data") or {})
        res = {}
        if s.get("notify_email_enabled") == "1":
            res["email"] = Biro26Notify._send_email(s, subject, text)
        if s.get("notify_tg_enabled") == "1":
            res["telegram"] = Biro26Notify._send_telegram(s, text)
        if s.get("notify_wa_enabled") == "1":
            res["whatsapp"] = Biro26Notify._send_whatsapp(s, text, pdf_url, pdf_name)
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
                s = Biro26Notify.get_settings().get("data") or {}
                # RO: link PDF semnat (public, doar acest document); pe
                #     WhatsApp Cloud pleaca si fisierul PDF ca document.
                # EN: signed public PDF link (this document only); WhatsApp
                #     Cloud mode also delivers the PDF file itself.
                link = Biro26Notify.pdf_link(s, "invoice", cod)
                body = text + (f"\nPDF: {link}" if link else "")
                Biro26Notify.send_all(subject, body, settings=s,
                                      pdf_url=link,
                                      pdf_name=f"Cont_{nrset}.pdf")
            except Exception:
                pass  # never disturb the request path

        threading.Thread(target=_run, daemon=True).start()
