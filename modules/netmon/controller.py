"""Контроллер модуля netmon: валидация, синхронизация, сборка ответов.

Возвращает (payload, http_status). SQL — только в store.py, внешние системы —
в sources.py, чистые правила — в rules.py (тестируются без wallet).
"""
from __future__ import annotations

from modules.netmon import rules, sources, store


def _ok(data, **extra):
    return {"success": True, "data": data, **extra}, 200


def _fail(msg, code=500):
    return {"success": False, "message": str(msg)[:400]}, code


class NetmonController:

    # ---------------------------------------------------------------- сводка

    @staticmethod
    def status():
        try:
            return _ok(store.counters(), rules_version=rules.VERSION)
        except Exception as e:  # noqa: BLE001 — наружу только текст
            return _fail(e)

    @staticmethod
    def overview():
        """Единая сводка для дашборда: устройства + каналы + лента."""
        try:
            dev = store.device_stats()
            al = store.alert_stats()
            ch = store.channels()
            pct = round(dev["in_zabbix"] * 100.0 / dev["total"], 1) if dev["total"] else 0.0
            return _ok({"devices": dev, "alerts": al, "channels": ch, "coverage_pct": pct})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    # ---------------------------------------------------------------- устройства

    @staticmethod
    def devices(kind=None, only_missing=False):
        try:
            return _ok(store.devices(kind=kind, only_missing=only_missing))
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def sync_devices(run_by: str = "system", subnet: str = "192.168.0."):
        """Скан сети → Oracle. Сам Zabbix не меняет, только сверяет покрытие."""
        try:
            from modules.netmon.scripts import netmon_zabbix_sync as scanner
        except Exception as e:  # noqa: BLE001
            return _fail(f"сканер недоступен: {e}")
        try:
            devices = scanner.scan()
            known = sources.Zabbix().hosts_by_ip()
            scan_id = store.start_scan(subnet, run_by)
            new = 0
            for d in devices:
                info = known.get(d["ip"])
                d["in_zabbix"] = bool(info)
                d["zabbix_host"] = info["host"] if info else ""
                if store.upsert_device(d, scan_id):
                    new += 1
            gone = store.mark_gone([d["ip"] for d in devices], scan_id)
            store.finish_scan(scan_id, len(devices), new, gone)
            return _ok({"scan_id": scan_id, "found": len(devices), "new": new, "gone": gone})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    # ---------------------------------------------------------------- Telegram

    @staticmethod
    def channels():
        try:
            return _ok(store.channels())
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def sync_channels():
        """Каналы из Zabbix + названия из Telegram API → Oracle."""
        try:
            targets = sources.Zabbix().telegram_targets()
            meta = sources.telegram_chats([t["chat_id"] for t in targets])
            for t in targets:
                m = meta.get(t["chat_id"], {})
                store.upsert_channel({
                    "chat_id": t["chat_id"],
                    "title": m.get("title") or f"chat {t['chat_id']}",
                    "chat_type": m.get("chat_type") or rules.channel_kind(t["chat_id"]),
                    "members_count": m.get("members_count"),
                    "bot_username": m.get("bot_username"),
                    "mediatype": t.get("mediatype"),
                    "zbx_user": t.get("zbx_user"),
                    "enabled": t.get("enabled"),
                    "note": m.get("note") or "",
                })
            return _ok({"channels": len(targets)})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def alerts(limit=100, channel_id=None, severity=None):
        try:
            return _ok(store.alerts(limit=limit, channel_id=channel_id, severity=severity))
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def sync_alerts(days: int = 30):
        """Лента отправленных сообщений из Zabbix → Oracle (идемпотентно)."""
        try:
            rows = sources.Zabbix().alerts(days=days)
            skipped = 0
            cache: dict[str, int] = {}
            ready = []
            for a in rows:
                cid = cache.get(a["chat_id"])
                if cid is None:
                    cid = store.channel_id_by_chat(a["chat_id"])
                    if cid is None:
                        skipped += 1
                        continue
                    cache[a["chat_id"]] = cid
                a["channel_id"] = cid
                ready.append(a)
            added = store.upsert_alerts(ready)
            return _ok({"fetched": len(rows), "added": added, "skipped_no_channel": skipped})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def sync_all(run_by: str = "system"):
        """Полная синхронизация: каналы → лента → устройства."""
        result = {}
        for name, fn in (("channels", NetmonController.sync_channels),
                         ("alerts", NetmonController.sync_alerts),
                         ("devices", lambda: NetmonController.sync_devices(run_by))):
            payload, code = fn()
            result[name] = payload.get("data") if code == 200 else {"error": payload.get("message")}
        return _ok(result)

    # ---------------------------------------------------------------- Zabbix-обзор

    @staticmethod
    def zabbix_overview():
        """Зеркало состояния Zabbix на текущий момент — читается напрямую."""
        try:
            return _ok(sources.zabbix_overview())
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    # ---------------------------------------------------------------- Proxmox

    @staticmethod
    def pve_guests(status=None, decision=None, risk=None):
        try:
            return _ok({"guests": store.guests(status=status, decision=decision, risk=risk),
                        "stats": store.guest_stats()})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def pve_guest(vmid: int):
        """Паспорт одной машины — то, что открывается в один клик."""
        try:
            rows = [g for g in store.guests() if g["vmid"] == int(vmid)]
            if not rows:
                return _fail(f"гость {vmid} не найден; выполните синхронизацию", 404)
            return _ok(rows[0])
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def sync_pve():
        """Опрос гипервизора и обновление паспортов всех гостей."""
        try:
            from modules.netmon import proxmox
            data = proxmox.collect()
            new = 0
            for g in data["guests"]:
                if store.upsert_guest(data["node"], g):
                    new += 1
            return _ok({"node": data["node"], "guests": len(data["guests"]), "new": new,
                        "storages": data.get("storages", []),
                        "summary": proxmox.summary(data)})
        except Exception as e:  # noqa: BLE001
            return _fail(e)
