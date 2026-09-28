"""Настройки кредитных провайдеров в Oracle (TMS_CREDITE_PROVIDER + _PARAM).

Один и тот же DDL развёрнут в двух БД, и каждый контур читает свою:
  AdbBackend    — Oracle ADB основного проекта (thin mode + wallet)
  Biro26Backend — Oracle 11g OfficePlus (thick mode, subprocess worker)

CrediteSettings — CRUD поверх любого бэкенда, с кэшем в памяти (TTL 60 c).
При недоступности БД чтение возвращает None: вызывающий код (config.py,
провайдеры) откатывается на значения из .env.
"""
from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

CACHE_TTL_SEC = 60


class CrediteBackendError(RuntimeError):
    """Ошибка доступа к БД настроек."""


# Описание провайдеров: единственный источник правды о наборе параметров.
# params: список (имя, секретный?) — секретные маскируются в API-ответах,
# и пустое значение при сохранении означает «не менять».
PROVIDER_DEFS: Dict[str, Dict[str, Any]] = {
    "easycredit": {
        "name": "EasyCredit",
        "icon": "💳",
        "color": "#667eea",
        "ord": 1,
        # RO: gateway-ul cere DOUA nivele: HTTP Basic pe cerere (basic_*) SI
        #     Login/Password in corpul SOAP (api_*). Basic e optional —
        #     endpoint-urile vechi (tst.ecmoldova.cloud) merg fara el.
        # RO: `product_id` e OBLIGATORIU pentru contul de PARTENER (serviciul
        #     Request_v3): creditorul atribuie produsul magazinului, iar el
        #     decide si termenele acceptate. Magazinul NU se indica — se alege
        #     automat dupa Login (de aceea v3, nu v4, care ar cere ShopID).
        #     `first_installment_days` — peste cite zile e prima rata (implicit 31).
        # EN: partner accounts (Request_v3) need the lender-assigned Product;
        #     the shop itself is resolved from the Login, so no ShopID here.
        "params": [("api_user", False), ("api_password", True),
                   ("basic_user", False), ("basic_password", True),
                   ("product_id", False), ("first_installment_days", False)],
        "default_base_url": {"sandbox": "https://api.ecredit.md/TEST/",
                             "production": "https://w81.ecredit.md:8082"},
    },
    "iute": {
        "name": "Iute Credit",
        "icon": "🟣",
        "color": "#7c3aed",
        "ord": 2,
        "params": [("api_key", True), ("pos_identifier", False),
                   ("salesman_identifier", False)],
        "default_base_url": {"sandbox": "https://iute-core-partner-gateway.iute.eu",
                             "production": "https://iute-core-partner-gateway.iute.eu"},
    },
}


class CrediteBackend(ABC):
    """Доступ к БД, в которой лежат TMS_CREDITE_*."""

    id: str = "abstract"

    @abstractmethod
    def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """SELECT. Ключи словарей — имена колонок в нижнем регистре."""

    @abstractmethod
    def dml(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        """INSERT/UPDATE/DELETE/DDL. Бросает CrediteBackendError при ошибке."""


class AdbBackend(CrediteBackend):
    """Oracle ADB основного проекта."""

    id = "adb"

    def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        from models.database import DatabaseModel
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql, params or {})
        except Exception as e:
            raise CrediteBackendError(str(e)) from e
        if not r.get("success"):
            raise CrediteBackendError(r.get("message") or "query failed")
        cols = [c.lower() for c in r.get("columns", [])]
        return [dict(zip(cols, row)) for row in r.get("data", [])]

    def dml(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        from models.database import DatabaseModel
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql, params or {})
                if r.get("success"):
                    db.connection.commit()
        except Exception as e:
            raise CrediteBackendError(str(e)) from e
        if not r.get("success"):
            raise CrediteBackendError(r.get("message") or "dml failed")


class Biro26Backend(CrediteBackend):
    """Oracle 11g OfficePlus через thick-subprocess worker."""

    id = "biro26"

    def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        from models.biro26_db import Biro26DB
        r = Biro26DB().execute_query(sql, params or {})
        if not r.get("success"):
            raise CrediteBackendError(r.get("message") or "query failed")
        cols = [c.lower() for c in r.get("columns", [])]
        return [dict(zip(cols, row)) for row in r.get("data", [])]

    def dml(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        from models.biro26_db import Biro26DB
        r = Biro26DB().execute_dml(sql, params or {})
        if not r.get("success"):
            raise CrediteBackendError(r.get("message") or "dml failed")


class CrediteSettings:
    """CRUD настроек провайдеров поверх одного бэкенда."""

    def __init__(self, backend: CrediteBackend) -> None:
        self.backend = backend
        self._cache: Dict[str, tuple[float, Optional[Dict[str, Any]]]] = {}
        self._lock = threading.Lock()

    # ── чтение ──

    def get(self, code: str) -> Optional[Dict[str, Any]]:
        """Настройки провайдера с расшифрованными параметрами.

        Возвращает None, если провайдера нет или БД недоступна.
        """
        code = (code or "").strip().lower()
        with self._lock:
            hit = self._cache.get(code)
            if hit and time.time() - hit[0] < CACHE_TTL_SEC:
                return hit[1]
        val = self._load(code)
        with self._lock:
            self._cache[code] = (time.time(), val)
        return val

    def _load(self, code: str) -> Optional[Dict[str, Any]]:
        try:
            rows = self.backend.query(
                "SELECT ID, CODE, NAME, ENABLED, ENV, BASE_URL, ICON, COLOR, INFO, ORD "
                "FROM TMS_CREDITE_PROVIDER WHERE CODE = :c", {"c": code})
        except CrediteBackendError:
            return None
        if not rows:
            return None
        return self._hydrate(rows[0])

    def _hydrate(self, row: Dict[str, Any]) -> Dict[str, Any]:
        try:
            prows = self.backend.query(
                "SELECT PARAM_NAME, PARAM_VALUE, IS_SECRET "
                "FROM TMS_CREDITE_PROVIDER_PARAM WHERE PROVIDER_ID = :p",
                {"p": row["id"]})
        except CrediteBackendError:
            prows = []
        spec = PROVIDER_DEFS.get(row["code"], {})
        env = (row.get("env") or "sandbox").lower()
        base = (row.get("base_url") or "").rstrip("/")
        if not base:
            base = (spec.get("default_base_url") or {}).get(env, "")
        return {
            "id": row["id"],
            "code": row["code"],
            "name": row.get("name") or spec.get("name") or row["code"],
            "enabled": (row.get("enabled") or "0") == "1",
            "env": env,
            "base_url": base,
            # RO: iconita e o constanta de cod, NU se citeste din DB — OfficePlus
            #     e CL8MSWIN1251 si transforma emoji-ul stocat in '?'.
            "icon": spec.get("icon", "🏦"),
            "color": row.get("color") or spec.get("color", "#0066CC"),
            "info": row.get("info") or "",
            "ord": int(row.get("ord") or 0),
            "params": {p["param_name"]: (p["param_value"] or "") for p in prows},
            "secrets": {p["param_name"] for p in prows if p.get("is_secret") == "1"},
        }

    def list_all(self) -> List[Dict[str, Any]]:
        """Все известные провайдеры. Отсутствующие в БД — как незаполненные."""
        out = []
        for code, spec in sorted(PROVIDER_DEFS.items(), key=lambda kv: kv[1]["ord"]):
            d = self.get(code)
            if d is None:
                d = {"id": None, "code": code, "name": spec["name"], "enabled": False,
                     "env": "sandbox",
                     "base_url": spec["default_base_url"]["sandbox"],
                     "icon": spec["icon"], "color": spec["color"], "info": "",
                     "ord": spec["ord"], "params": {}, "secrets": set()}
            out.append(d)
        return out

    def masked(self, code: str) -> Optional[Dict[str, Any]]:
        """Копия get() с замаскированными секретами — безопасна для JSON-API."""
        d = self.get(code)
        if d is None:
            return None
        out = dict(d)
        out["params"] = {}
        out["has_secret"] = {}
        for name, value in d["params"].items():
            if name in d["secrets"]:
                out["params"][name] = (value[:3] + "***") if value else ""
                out["has_secret"][name] = bool(value)
            else:
                out["params"][name] = value
        out["secrets"] = sorted(d["secrets"])
        out["configured"] = self.is_configured(code)
        return out

    def is_configured(self, code: str) -> bool:
        """Заданы ли все секретные параметры провайдера."""
        d = self.get(code)
        if d is None:
            return False
        spec = PROVIDER_DEFS.get(code, {})
        required = [n for n, secret in spec.get("params", []) if secret]
        if code == "easycredit":
            required = ["api_user", "api_password"]
        return all((d["params"].get(n) or "").strip() for n in required)

    # ── запись ──

    def save(self, code: str, *, enabled: bool, env: str, base_url: str,
             params: Dict[str, str]) -> Dict[str, Any]:
        """Сохранить настройки. Пустое значение секретного параметра = «не менять»."""
        code = (code or "").strip().lower()
        spec = PROVIDER_DEFS.get(code)
        if not spec:
            return {"success": False, "error": f"неизвестный провайдер: {code}"}
        env = (env or "sandbox").lower()
        if env not in ("sandbox", "production"):
            env = "sandbox"
        base_url = (base_url or "").strip().rstrip("/") or spec["default_base_url"][env]
        try:
            rows = self.backend.query(
                "SELECT ID FROM TMS_CREDITE_PROVIDER WHERE CODE = :c", {"c": code})
            if rows:
                pid = int(rows[0]["id"])
                self.backend.dml(
                    "UPDATE TMS_CREDITE_PROVIDER SET ENABLED=:en, ENV=:e, BASE_URL=:b, "
                    "UPDATED=SYSDATE WHERE CODE=:c",
                    {"en": "1" if enabled else "0", "e": env, "b": base_url, "c": code})
            else:
                self.backend.dml(
                    # RO: ICON nu se mai scrie — e constanta de cod (PROVIDER_DEFS),
                    #     iar OfficePlus (CL8MSWIN1251) ar stoca emoji-ul ca '?'.
                    "INSERT INTO TMS_CREDITE_PROVIDER (CODE, NAME, ENABLED, ENV, "
                    "BASE_URL, COLOR, ORD) "
                    "VALUES (:c, :n, :en, :e, :b, :col, :o)",
                    {"c": code, "n": spec["name"], "en": "1" if enabled else "0",
                     "e": env, "b": base_url,
                     "col": spec["color"], "o": spec["ord"]})
                pid = int(self.backend.query(
                    "SELECT ID FROM TMS_CREDITE_PROVIDER WHERE CODE = :c",
                    {"c": code})[0]["id"])
            existing = {p["param_name"]: p for p in self.backend.query(
                "SELECT PARAM_NAME, PARAM_VALUE, IS_SECRET "
                "FROM TMS_CREDITE_PROVIDER_PARAM WHERE PROVIDER_ID = :p", {"p": pid})}
            for pname, secret in spec["params"]:
                new = (params.get(pname) or "").strip()
                if pname in existing:
                    if secret and not new:
                        continue  # пустой секрет — не затираем
                    self.backend.dml(
                        "UPDATE TMS_CREDITE_PROVIDER_PARAM SET PARAM_VALUE=:v "
                        "WHERE PROVIDER_ID=:p AND PARAM_NAME=:n",
                        {"v": new or None, "p": pid, "n": pname})
                else:
                    self.backend.dml(
                        "INSERT INTO TMS_CREDITE_PROVIDER_PARAM (PROVIDER_ID, "
                        "PARAM_NAME, PARAM_VALUE, IS_SECRET) VALUES (:p, :n, :v, :s)",
                        {"p": pid, "n": pname, "v": new or None,
                         "s": "1" if secret else "0"})
        except CrediteBackendError as e:
            return {"success": False, "error": str(e)}
        self.invalidate(code)
        return {"success": True}

    def invalidate(self, code: Optional[str] = None) -> None:
        with self._lock:
            if code is None:
                self._cache.clear()
            else:
                self._cache.pop(code.lower(), None)


_ADB: Optional[CrediteSettings] = None
_BIRO26: Optional[CrediteSettings] = None


def adb_settings() -> CrediteSettings:
    """Настройки провайдеров основного проекта (Oracle ADB)."""
    global _ADB
    if _ADB is None:
        _ADB = CrediteSettings(AdbBackend())
    return _ADB


def biro26_settings() -> CrediteSettings:
    """Настройки провайдеров Biro26 (Oracle 11g OfficePlus)."""
    global _BIRO26
    if _BIRO26 is None:
        _BIRO26 = CrediteSettings(Biro26Backend())
    return _BIRO26
