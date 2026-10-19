"""TBControl — контроль SSL-сертификатов публичных доменов (TBC_CERTS).

Список доменов ведётся в TBC_CERTS (домен + порт, заметка, включён).
`check_all()` подключается к каждому домену по TLS, читает сертификат
(cryptography, DER) и обновляет issuer / CN / серийник / срок / дни до
истечения. Истёкший или недоверенный сертификат тоже читается — второй
попыткой без проверки цепочки, чтобы в таблице была причина, а не «ERROR».

Статусы: OK (> 14 дней), EXPIRING (≤ 14), EXPIRED, ERROR (не подключился).
События `source='certs'` (corr `cert-<домен>`): EXPIRING → P3, EXPIRED → P1,
ERROR → P3; при возврате в OK — закрываются.
"""
from __future__ import annotations

import datetime as dt
import socket
import ssl
from typing import Any, Dict, List, Optional, Tuple

from models import tbc_mtls

SOURCE = "certs"
CORR_PREFIX = "cert-"
EXPIRING_DAYS = 14
TIMEOUT = 8


# ---------- чистые правила ----------

def cert_status(days_left: Optional[int], error: Optional[str] = None) -> str:
    if error:
        return "ERROR"
    if days_left is None:
        return "ERROR"
    if days_left < 0:
        return "EXPIRED"
    if days_left <= EXPIRING_DAYS:
        return "EXPIRING"
    return "OK"


def auto_renew_of(issuer: Optional[str], current: Optional[str] = None) -> str:
    if current:
        return current
    return "letsencrypt" if issuer and "let's encrypt" in issuer.lower() else "manual"


def parse_der(der: bytes, now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    cert = x509.load_der_x509_certificate(der)

    def attr(name, oid):
        try:
            v = name.get_attributes_for_oid(oid)
            return v[0].value if v else None
        except Exception:
            return None
    issuer = attr(cert.issuer, NameOID.ORGANIZATION_NAME) or attr(cert.issuer, NameOID.COMMON_NAME)
    subject = attr(cert.subject, NameOID.COMMON_NAME)
    nb = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before.replace(tzinfo=dt.timezone.utc)
    na = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=dt.timezone.utc)
    now = now or dt.datetime.now(dt.timezone.utc)
    days = int((na - now).total_seconds() // 86400)
    return {"issuer": (issuer or "")[:200] or None, "subject_cn": (subject or "")[:200] or None,
            "serial_no": format(cert.serial_number, "X")[:80],
            "valid_from": nb.replace(tzinfo=None), "valid_to": na.replace(tzinfo=None), "days_left": days}


def wanted_events(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for r in rows:
        st = r.get("status")
        if st == "OK" or r.get("enabled") == "N":
            continue
        corr = f"{CORR_PREFIX}{r['domain_name']}"[:30]
        if st == "EXPIRED":
            sev, text = "P1", f"истёк {r.get('valid_to')}"
        elif st == "EXPIRING":
            sev, text = "P3", f"истекает через {r.get('days_left')} дн ({r.get('valid_to')})"
        else:
            sev, text = "P3", f"не проверяется: {r.get('last_error') or 'ошибка'}"
        out[corr] = {"severity": sev, "service_code": "api",
                     "problem": f"SSL {r['domain_name']}:{r.get('port') or 443} — {text}"}
    return out


# ---------- сеть ----------

def fetch_cert(domain: str, port: int = 443) -> Dict[str, Any]:
    """Читает сертификат домена. Возвращает parse_der(...) + 'trusted' + 'error'."""
    last_err = None
    for verify in (True, False):
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        try:
            with socket.create_connection((domain, port), timeout=TIMEOUT) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as tls:
                    der = tls.getpeercert(binary_form=True)
            info = parse_der(der)
            info["trusted"] = verify
            info["error"] = None if verify else f"цепочка не проверена: {last_err}"
            return info
        except ssl.SSLError as e:
            last_err = str(e)[:200]
            continue
        except (OSError, socket.timeout) as e:
            return {"error": f"{type(e).__name__}: {str(e)[:150]}", "trusted": False}
    return {"error": last_err or "TLS error", "trusted": False}


# ---------- публичный API модуля ----------

def get_certs() -> Dict[str, Any]:
    from models.database import DatabaseModel
    try:
        with DatabaseModel() as db:
            data = tbc_mtls.rows_to_dicts(db.execute_query(
                "SELECT * FROM TBC_CERTS ORDER BY CASE STATUS WHEN 'EXPIRED' THEN 0 WHEN 'ERROR' THEN 1 "
                "WHEN 'EXPIRING' THEN 2 ELSE 3 END, DAYS_LEFT, DOMAIN_NAME"))
            stats = tbc_mtls.rows_to_dicts(db.execute_query("SELECT * FROM V_TBC_CERTS_STATS"))
        return {"success": True, "data": data, "total": len(data), "stats": stats[0] if stats else {}}
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_cert(data: Dict[str, Any]) -> Dict[str, Any]:
    from models.database import DatabaseModel
    domain = (data.get("domain_name") or "").strip().lower()
    if not domain or " " in domain:
        return {"success": False, "error": "Укажите домен"}
    try:
        port = int(data.get("port") or 443)
    except (TypeError, ValueError):
        return {"success": False, "error": "Порт — число"}
    enabled = "Y" if data.get("enabled", "Y") in (True, "Y", "y", 1, "1") else "N"
    try:
        with DatabaseModel() as db:
            upd = db.execute_query(
                "UPDATE TBC_CERTS SET NOTE = :note, ENABLED = :en WHERE DOMAIN_NAME = :d AND PORT = :p",
                {"note": data.get("note"), "en": enabled, "d": domain, "p": port})
            if not upd.get("rowcount"):
                db.execute_query(
                    "INSERT INTO TBC_CERTS (DOMAIN_NAME, PORT, NOTE, ENABLED) VALUES (:d, :p, :note, :en)",
                    {"d": domain, "p": port, "note": data.get("note"), "en": enabled})
            tbc_mtls.audit(db, "save", "cert", f"Сертификат {domain}:{port}")
            db.connection.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_cert(cert_id: int) -> Dict[str, Any]:
    from models.database import DatabaseModel
    try:
        with DatabaseModel() as db:
            db.execute_query("DELETE FROM TBC_CERTS WHERE ID = :id", {"id": int(cert_id)})
            tbc_mtls.audit(db, "delete", "cert", f"Сертификат #{cert_id} удалён")
            db.connection.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_all(cert_id: Optional[int] = None) -> Dict[str, Any]:
    from models.database import DatabaseModel
    try:
        with DatabaseModel() as db:
            sql = "SELECT * FROM TBC_CERTS WHERE ENABLED = 'Y'"
            params = {}
            if cert_id:
                sql += " AND ID = :id"; params["id"] = int(cert_id)
            certs = tbc_mtls.rows_to_dicts(db.execute_query(sql, params or None))
            results = []
            for c in certs:
                info = fetch_cert(c["domain_name"], int(c.get("port") or 443))
                err = info.get("error")
                row = {"id": c["id"], "issuer": info.get("issuer"), "cn": info.get("subject_cn"),
                       "serial": info.get("serial_no"), "vf": info.get("valid_from"), "vt": info.get("valid_to"),
                       "days": info.get("days_left"),
                       "renew": auto_renew_of(info.get("issuer"), c.get("auto_renew")),
                       "st": cert_status(info.get("days_left"), None if info.get("days_left") is not None else err),
                       "err": (err or "")[:500] or None}
                db.execute_query(
                    "UPDATE TBC_CERTS SET ISSUER = NVL(:issuer, ISSUER), SUBJECT_CN = NVL(:cn, SUBJECT_CN), "
                    "SERIAL_NO = NVL(:serial, SERIAL_NO), VALID_FROM = NVL(:vf, VALID_FROM), "
                    "VALID_TO = NVL(:vt, VALID_TO), DAYS_LEFT = :days, AUTO_RENEW = :renew, STATUS = :st, "
                    "LAST_ERROR = :err, CHECKED_AT = SYSTIMESTAMP WHERE ID = :id", row)
                results.append({"domain_name": c["domain_name"], "port": c.get("port"), "status": row["st"],
                                "days_left": row["days"], "error": row["err"]})
            all_rows = tbc_mtls.rows_to_dicts(db.execute_query("SELECT * FROM TBC_CERTS"))
            created, resolved = tbc_mtls.sync_events(db, SOURCE, CORR_PREFIX, wanted_events(all_rows))
            tbc_mtls.audit(db, "check", "cert", f"Проверено сертификатов: {len(results)}, событий +{created}/-{resolved}")
            db.connection.commit()
        bad = [r for r in results if r["status"] != "OK"]
        return {"success": True, "data": results, "checked": len(results), "problems": len(bad),
                "events_created": created, "events_resolved": resolved}
    except Exception as e:
        return {"success": False, "error": str(e)}
