#!/usr/bin/env python3
"""
Базовый реестр версий приложения/shell/модулей.
Хранит версии в JSON-файле и умеет определять текущий модуль по URL.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class VersionRegistry:
    _manifest_path = Path(__file__).parent / "data" / "version_manifest.json"

    @classmethod
    def _now_iso(cls) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    @classmethod
    def _default_manifest(cls) -> Dict[str, Any]:
        ts = cls._now_iso()
        return {
            "app": {
                "name": "UNA orasldev",
                "version": "0.1.0",
                "updated_at": ts,
                "notes": "Base app runtime",
            },
            "shell": {
                "name": "UNA Shell",
                "version": "0.1.0",
                "updated_at": ts,
                "notes": "Shell project launcher + dashboards",
            },
            "modules": {
                "decor": {"name": "DECOR", "version": "0.3.0", "updated_at": ts, "notes": "Operator/Admin + docs + AI batch"},
                "nufarul": {"name": "Nufarul", "version": "0.1.0", "updated_at": ts, "notes": "Operator/Admin"},
                "credit": {"name": "Credits", "version": "0.1.0", "updated_at": ts, "notes": "Credit workflows"},
                "colass": {"name": "Colass", "version": "0.1.0", "updated_at": ts, "notes": "Contracts/catalog/CRM"},
                "dashboard": {"name": "Dashboard", "version": "0.1.0", "updated_at": ts, "notes": "MDI dashboards"},
                "docs": {"name": "Docs", "version": "0.1.0", "updated_at": ts, "notes": "Module documentation viewers"},
                "digi_sm": {"name": "DIGI SM", "version": "0.1.0", "updated_at": ts, "notes": "Scales integration"},
                "auth": {"name": "Auth/Login", "version": "0.1.0", "updated_at": ts, "notes": "Login and session"},
            },
            "meta": {
                "schema_version": 1,
                "updated_at": ts,
                "managed_by": "version_registry.py",
            },
        }

    @classmethod
    def _merge_defaults(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        base = cls._default_manifest()
        if not isinstance(data, dict):
            return base
        for root_key in ("app", "shell", "meta"):
            if isinstance(data.get(root_key), dict):
                base[root_key].update(data[root_key])
        if isinstance(data.get("modules"), dict):
            for k, v in data["modules"].items():
                if isinstance(v, dict):
                    base.setdefault("modules", {}).setdefault(k, {}).update(v)
        return base

    @classmethod
    def load(cls) -> Dict[str, Any]:
        p = cls._manifest_path
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            data = cls._default_manifest()
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return data
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        data = cls._merge_defaults(raw)
        # Persist merged defaults if keys were missing
        try:
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return data

    @classmethod
    def detect_module_key(cls, path: str) -> str:
        p = (path or "").lower()
        if "/una.md/shell/" in p:
            return "shell"
        if "/decor" in p:
            return "decor"
        if "/nufarul" in p:
            return "nufarul"
        if "/credit" in p:
            return "credit"
        if "/colass" in p:
            return "colass"
        if "/digi-sm" in p:
            return "digi_sm"
        if "/docs/" in p:
            return "docs"
        if "/dashboard" in p:
            return "dashboard"
        if p.endswith("/login") or p == "/login" or p == "/":
            return "auth"
        return "dashboard"

    @classmethod
    def for_path(cls, path: str) -> Dict[str, Any]:
        manifest = cls.load()
        module_key = cls.detect_module_key(path)
        modules = manifest.get("modules") or {}
        shell_info = (manifest.get("shell") or {}).copy()
        app_info = (manifest.get("app") or {}).copy()
        if module_key == "shell":
            module_info = shell_info.copy()
        else:
            module_info = (modules.get(module_key) or {}).copy()
        return {
            "success": True,
            "path": path or "",
            "module_key": module_key,
            "module": module_info,
            "shell": shell_info,
            "app": app_info,
            "meta": manifest.get("meta") or {},
            "all_modules": modules,
        }
