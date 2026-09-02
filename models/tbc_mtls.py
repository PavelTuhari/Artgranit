"""TBControl — mTLS-транспорт к шлюзу nginx на 192.168.0.148.

Шлюз (`/etc/nginx/conf.d/tbc-zabbix-mtls.conf`, порт 8443) пускает только
клиентов с сертификатом, подписанным нашим CA, и проксирует:

    /api_jsonrpc.php  → Zabbix unisim-soft.com (JSON-RPC)
    /proxmox/         → Proxmox VE 4.4 (PROXMOX3, 192.168.0.149:8006)
    /health           → «жив ли шлюз» (200 при валидном клиентском сертификате)

Источник в `TBC_SOURCES` хранит только пути к публичным файлам
(`CERT_PATH`, `CA_PATH`) и адрес приватного ключа в Keychain
(`KEY_KEYCHAIN_SVC` / `KEY_KEYCHAIN_ACC`). Сам ключ на диске проекта не
лежит: он читается из macOS Keychain командой `security` на время процесса
и кладётся во временный файл с правами 0600, который удаляется при выходе.

На Linux-сервере (nufarul) Keychain нет — там ключ можно передать через
переменную окружения `TBC_MTLS_KEY_PATH`. Если ни того, ни другого нет,
источник честно отвечает ошибкой, а не падает с 500.

Восстановлено 02.09.2026 по правилу №2 CLAUDE.md: логика — в отдельном
файле, контроллер вызывает в одну строку. См. docs/TBControl/MTLS_SOURCE.md.
"""
from __future__ import annotations

import atexit
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, Optional, Tuple

import requests

TIMEOUT = int(os.environ.get("TBC_MTLS_TIMEOUT", "25"))

# Кэш временных файлов ключа на время процесса: {(svc, acc): path}
_KEY_FILES: Dict[Tuple[str, str], str] = {}
_TMP_DIR: Optional[str] = None


def _tmp_dir() -> str:
    global _TMP_DIR
    if _TMP_DIR is None or not os.path.isdir(_TMP_DIR):
        _TMP_DIR = tempfile.mkdtemp(prefix="tbc-mtls-")
        os.chmod(_TMP_DIR, 0o700)
        atexit.register(_cleanup)
    return _TMP_DIR


def _cleanup() -> None:
    global _TMP_DIR
    if _TMP_DIR and os.path.isdir(_TMP_DIR):
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
    _TMP_DIR = None
    _KEY_FILES.clear()


def _keychain_secret(service: str, account: str) -> str:
    """Читает секрет из macOS Keychain. Возвращает PEM-текст ключа."""
    if sys.platform != "darwin":
        raise RuntimeError("Keychain доступен только на macOS; на сервере задайте TBC_MTLS_KEY_PATH")
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, timeout=15, check=False)
    except FileNotFoundError:
        raise RuntimeError("Команда security не найдена")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Keychain не ответил за 15 с (ждёт подтверждения доступа в диалоге macOS)")
    if out.returncode != 0:
        raise RuntimeError(f"Keychain: ключ {service}/{account} не найден ({out.stderr.strip()[:120]})")
    secret = out.stdout.strip()
    if not secret.startswith("-----BEGIN"):
        # security печатает hex, если значение содержит непечатаемые байты
        try:
            secret = bytes.fromhex(secret).decode("utf-8").strip()
        except ValueError:
            pass
    if "-----BEGIN" not in secret:
        raise RuntimeError("Keychain: значение не похоже на PEM-ключ")
    return secret + "\n"


def resolve_secret(value: Optional[str]) -> str:
    """Секрет источника: обычная строка или ссылка `keychain:<service>/<account>` —
    тогда пароль читается из macOS Keychain и в Oracle не хранится."""
    value = (value or "").strip()
    if value.lower().startswith("keychain:"):
        ref = value.split(":", 1)[1]
        svc, _, acc = ref.partition("/")
        if not svc or not acc:
            raise RuntimeError("Формат секрета: keychain:<service>/<account>")
        if sys.platform != "darwin":
            raise RuntimeError("Секрет в Keychain доступен только на macOS")
        out = subprocess.run(["security", "find-generic-password", "-s", svc, "-a", acc, "-w"],
                             capture_output=True, text=True, timeout=15, check=False)
        if out.returncode != 0:
            raise RuntimeError(f"Keychain: секрет {svc}/{acc} не найден")
        return out.stdout.rstrip("\n")
    return value


def client_key_path(src: Dict[str, Any]) -> str:
    """Путь к приватному ключу клиента: env → Keychain → ошибка."""
    env_path = os.environ.get("TBC_MTLS_KEY_PATH", "").strip()
    if env_path:
        if not os.path.isfile(env_path):
            raise RuntimeError(f"TBC_MTLS_KEY_PATH={env_path}: файла нет")
        return env_path
    svc = (src.get("key_keychain_svc") or "").strip()
    acc = (src.get("key_keychain_acc") or "").strip()
    if not svc or not acc:
        raise RuntimeError("У источника не задан адрес ключа в Keychain (KEY_KEYCHAIN_SVC/ACC)")
    cached = _KEY_FILES.get((svc, acc))
    if cached and os.path.isfile(cached):
        return cached
    pem = _keychain_secret(svc, acc)
    path = os.path.join(_tmp_dir(), f"{hashlib.sha1((svc + acc).encode()).hexdigest()[:12]}.key")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(pem)
    os.chmod(path, 0o600)
    _KEY_FILES[(svc, acc)] = path
    return path


def cert_fingerprint(cert_path: str) -> str:
    """SHA-256 отпечаток сертификата в формате AA:BB:… (как в TBC_SOURCES)."""
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding
    with open(cert_path, "rb") as fh:
        cert = x509.load_pem_x509_certificate(fh.read())
    digest = hashlib.sha256(cert.public_bytes(Encoding.DER)).hexdigest()
    return ":".join(digest[i:i + 2] for i in range(0, len(digest), 2)).upper()


class MtlsClient:
    """HTTP-клиент к шлюзу с клиентским сертификатом.

    `verify`: CA шлюза (`CA_PATH`), если файл есть. Сертификат сервера
    выписан на IP, и если проверка имени не проходит, второй запрос идёт с
    `verify=False` — факт отмечается в `insecure`, чтобы попасть в LAST_ERROR.
    """

    def __init__(self, src: Dict[str, Any]):
        self.src = src
        self.base = (src.get("api_url") or "").strip().rstrip("/")
        if not self.base:
            raise RuntimeError("У источника не задан API_URL")
        cert = (src.get("cert_path") or "").strip()
        if not cert or not os.path.isfile(cert):
            raise RuntimeError(f"Клиентский сертификат не найден: {cert or 'CERT_PATH пуст'}")
        self.cert = (cert, client_key_path(src))
        ca = (src.get("ca_path") or "").strip()
        self.verify: Any = ca if ca and os.path.isfile(ca) else False
        self.insecure = self.verify is False
        self.session = requests.Session()
        self.session.cert = self.cert

    @property
    def gateway_root(self) -> str:
        """https://host:port — корень шлюза для /health."""
        from urllib.parse import urlsplit
        p = urlsplit(self.base)
        return f"{p.scheme}://{p.netloc}"

    def request(self, method: str, url: str, **kw) -> requests.Response:
        kw.setdefault("timeout", TIMEOUT)
        try:
            return self.session.request(method, url, verify=self.verify, **kw)
        except requests.exceptions.SSLError as e:
            msg = str(e)
            if self.verify and ("match" in msg or "hostname" in msg.lower() or "IP address" in msg):
                self.verify = False
                self.insecure = True
                return self.session.request(method, url, verify=False, **kw)
            raise RuntimeError(f"TLS: {msg[:200]}")

    def health(self) -> Dict[str, Any]:
        r = self.request("GET", self.gateway_root + "/health")
        return {"status_code": r.status_code, "ok": r.status_code == 200,
                "body": (r.text or "")[:200], "insecure": self.insecure}


def source_row(code: str) -> Optional[Dict[str, Any]]:
    """Полная строка TBC_SOURCES (со всеми mTLS-колонками) по коду."""
    from models.database import DatabaseModel
    with DatabaseModel() as db:
        r = db.execute_query("SELECT * FROM TBC_SOURCES WHERE CODE = :c", {"c": code})
        rows = rows_to_dicts(r)
        return rows[0] if rows else None


def sources_of_kind(kind: str, code: Optional[str] = None, enabled_only: bool = True):
    from models.database import DatabaseModel
    sql = "SELECT * FROM TBC_SOURCES WHERE KIND = :k"
    params: Dict[str, Any] = {"k": kind}
    if code:
        sql += " AND CODE = :c"
        params["c"] = code
    elif enabled_only:
        sql += " AND ENABLED = 'Y'"
    sql += " ORDER BY SORT_ORDER, CODE"
    with DatabaseModel() as db:
        return rows_to_dicts(db.execute_query(sql, params))


def mark_source(code: str, ok: bool, error: Optional[str] = None) -> None:
    from models.database import DatabaseModel
    try:
        with DatabaseModel() as db:
            db.execute_query(
                "UPDATE TBC_SOURCES SET LAST_SYNC_AT = SYSTIMESTAMP, LAST_STATUS = :st, "
                "LAST_ERROR = :err WHERE CODE = :c",
                {"st": "OK" if ok else "ERROR", "err": (error or "")[:500] or None, "c": code})
            db.connection.commit()
    except Exception:
        pass


def rows_to_dicts(result: Dict[str, Any]):
    if not result.get("success") or not result.get("data"):
        return []
    cols = [c.lower() for c in (result.get("columns") or [])]
    return [dict(zip(cols, row)) for row in result.get("data", [])]


# ---------- события TBC_EVENTS для инфраструктурных источников ----------

def open_events(db, source: str, corr_prefix: str) -> Dict[str, Dict[str, Any]]:
    """Открытые события источника: {correlation_id: row}."""
    r = db.execute_query(
        "SELECT ID, CORRELATION_ID, SEVERITY, PROBLEM FROM TBC_EVENTS "
        "WHERE SOURCE = :s AND STATUS IN ('open','ack') AND CORRELATION_ID LIKE :p",
        {"s": source, "p": corr_prefix + "%"})
    return {row["correlation_id"]: row for row in rows_to_dicts(r)}


def sync_events(db, source: str, corr_prefix: str, wanted: Dict[str, Dict[str, Any]]) -> Tuple[int, int]:
    """Приводит открытые события источника к списку `wanted`
    ({corr: {severity, service_code, problem}}): новые создаёт, исчезнувшие закрывает.
    Возвращает (created, resolved). Коммит — на стороне вызывающего."""
    active = open_events(db, source, corr_prefix)
    created = resolved = 0
    for corr, ev in wanted.items():
        if corr in active:
            continue
        db.execute_query(
            "INSERT INTO TBC_EVENTS (SEVERITY, SERVICE_CODE, PROBLEM, STATUS, SOURCE, CORRELATION_ID) "
            "VALUES (:sev, :svc, :problem, 'open', :source, :corr)",
            {"sev": ev.get("severity") or "P3", "svc": ev.get("service_code"),
             "problem": (ev.get("problem") or "")[:500], "source": source, "corr": corr[:30]})
        created += 1
    for corr, row in active.items():
        if corr not in wanted:
            db.execute_query(
                "UPDATE TBC_EVENTS SET STATUS = 'resolved', RESOLVED_AT = SYSTIMESTAMP WHERE ID = :id",
                {"id": row["id"]})
            resolved += 1
    return created, resolved


def audit(db, action: str, entity_type: str, details: str) -> None:
    try:
        db.execute_query(
            "INSERT INTO TBC_EVENT_LOG (ACTION, ENTITY_TYPE, ENTITY_ID, DETAILS, USERNAME) "
            "VALUES (:a, :t, NULL, :d, 'system')", {"a": action, "t": entity_type, "d": details[:2000]})
    except Exception:
        pass
