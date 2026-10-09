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

    # ---------------------------------------------------------------- бизнес-активы

    @staticmethod
    def assets():
        """Домены, серверы в стойке и перерасход энергии — одним ответом."""
        try:
            from modules.netmon import assets as a
            doms = a.check_domains()
            night = []
            try:
                night = a.night_activity(sources.Zabbix())
            except Exception:  # noqa: BLE001 — Zabbix может быть недоступен без VPN
                pass
            ws = [n for n in night if n["is_workstation"] and n["always_on"]]
            energy = a.energy_waste(len(ws) or 0)
            return _ok({
                "domains": doms,
                "domains_alert": [d for d in doms if d["level"] in ("critical", "warning")],
                "rack": a.RACK_SERVERS,
                "night": night,
                "always_on_workstations": ws,
                "energy": energy,
            })
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def sync_assets():
        """Проверяет домены и отправляет показатели в Zabbix."""
        try:
            from modules.netmon import assets as a
            doms = a.check_domains()
            vals = a.domain_values(doms)
            night = a.night_activity(sources.Zabbix())
            ws = [n for n in night if n["is_workstation"] and n["always_on"]]
            e = a.energy_waste(len(ws))
            vals.update({"energy.idle.machines": len(ws),
                         "energy.idle.mdl_month": e["mdl_month"],
                         "energy.idle.kwh_month": int(e["kwh_month"])})
            res = a.push_to_zabbix(vals)
            return _ok({"domains_checked": len(doms), "workstations_always_on": len(ws),
                        "energy": e, "zabbix": res})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    # ---------------------------------------------------------------- пароли

    @staticmethod
    def vault():
        """Реестр доступов: ЧТО есть и ГДЕ лежит. Сами пароли не отдаются."""
        try:
            from modules.netmon.scripts import netmon_vault as v
            groups: dict[str, list] = {}
            for account, service, what, where in v.KNOWN:
                ok = bool(v.kc_get(account, service))
                groups.setdefault(_vault_group(what), []).append({
                    "what": what, "where": where, "login": account,
                    "keychain": service, "kind": "generic", "present": ok,
                    "howto": f"security find-generic-password -a {account} -s {service} -w"})
            for account, service, what, where in v.KNOWN_INTERNET:
                ok = bool(v.kc_get(account, service, internet=True))
                groups.setdefault(_vault_group(what), []).append({
                    "what": what, "where": where, "login": account,
                    "keychain": service, "kind": "internet", "present": ok,
                    "howto": f"security find-internet-password -a {account} -s {service} -w"})
            total = sum(len(v_) for v_ in groups.values())
            here = v.keychain_available()
            note = ("Значения паролей через веб не отдаются намеренно. Панель "
                    "показывает, какой доступ существует и как достать его из "
                    "Keychain на рабочей машине.")
            if not here:
                note += (" Столбец «статус» пуст: Keychain есть только на macOS, "
                         "а эта страница открыта с сервера — проверить наличие "
                         "записи можно только на рабочей машине владельца.")
            return _ok({"groups": [{"group": g, "items": sorted(items, key=lambda x: x["what"])}
                                   for g, items in sorted(groups.items())],
                        "total": total, "keychain_here": here, "note": note})
        except Exception as e:  # noqa: BLE001
            return _fail(e)
    # ---------------------------------------------------------------- оборудование

    @staticmethod
    def facilities(kind=None, room=None):
        """Реестр инженерного оборудования со сроками обслуживания."""
        try:
            from datetime import date
            from modules.netmon import facility as fac
            rows = store.facilities(kind=kind, room=room)
            for r in rows:
                r["kind_title"] = fac.KIND_TITLE.get(r["kind"], r["kind"])
                r["service"] = _service_summary(r, fac)
            overdue = [r for r in rows if r["service"]["level"] == "overdue"]
            return _ok({"facilities": rows, "stats": store.facility_stats(),
                        "overdue": len(overdue),
                        "work_kinds": fac.WORK_TITLE, "kinds": fac.KIND_TITLE})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def facility(code):
        """Паспорт объекта: журнал работ и фотографии."""
        try:
            from modules.netmon import facility as fac
            f = store.facility(code)
            if not f:
                return _fail(f"объект {code} не найден", 404)
            f["kind_title"] = fac.KIND_TITLE.get(f["kind"], f["kind"])
            f["service"] = _service_summary(f, fac)
            for w in f["log"]:
                w["work_title"] = fac.WORK_TITLE.get(w["work_kind"], w["work_kind"])
            return _ok(f)
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def add_work(code, data, user="system"):
        """Запись в журнал: что сделали с оборудованием и когда повторить."""
        try:
            from datetime import date
            from modules.netmon import facility as fac
            f = store.facility(code)
            if not f:
                return _fail(f"объект {code} не найден", 404)
            kind = (data.get("work_kind") or "").strip()
            if kind not in fac.WORK_TITLE:
                return _fail(f"вид работ должен быть одним из: "
                             f"{', '.join(fac.WORK_TITLE)}", 400)
            due = data.get("next_due")
            if not due:
                d = fac.next_due(kind, f["kind"])
                due = d.isoformat() if d else None
            log_id = store.add_log(f["id"], {
                "work_kind": kind, "done_at": data.get("done_at"),
                "performer": (data.get("performer") or user)[:120],
                "description": (data.get("description") or "")[:2000],
                "next_due": due, "cost_mdl": data.get("cost_mdl"),
                "created_by": user})
            return _ok({"log_id": log_id, "facility": code, "next_due": due})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def add_photo(code, file_storage, caption="", user="system", log_id=None):
        """Снимок состояния оборудования от сотрудника."""
        try:
            from modules.netmon import facility as fac
            f = store.facility(code)
            if not f:
                return _fail(f"объект {code} не найден", 404)
            if not file_storage or not file_storage.filename:
                return _fail("файл не передан", 400)
            try:
                name = fac.safe_filename(file_storage.filename, code)
            except ValueError as e:
                return _fail(str(e), 400)
            path = fac.photo_path(name)
            file_storage.save(str(path))
            size_kb = path.stat().st_size // 1024
            if size_kb > fac.MAX_PHOTO_MB * 1024:
                path.unlink(missing_ok=True)
                return _fail(f"снимок больше {fac.MAX_PHOTO_MB} МБ", 400)
            pid = store.add_photo(f["id"], {
                "file_path": str(path), "file_name": name,
                "caption": (caption or "")[:500], "taken_by": user,
                "size_kb": size_kb, "log_id": log_id})
            return _ok({"photo_id": pid, "file": name, "size_kb": size_kb})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    # ---------------------------------------------------------------- розетки

    @staticmethod
    def plugs():
        try:
            from modules.netmon import smartplug
            rows = smartplug.all_status()
            return _ok({"plugs": rows,
                        "online": sum(1 for r in rows if r.get("online")),
                        "controllable": sum(1 for r in rows if r.get("controllable")),
                        "hint": ("Управление включается, когда для розетки заведён "
                                 "ключ в Keychain: запись tuya-<ip>, логин = device_id, "
                                 "пароль = local_key. Как их получить — "
                                 "docs/Netmon/SMART_PLUGS.md")})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def switch_plug(ip, on: bool, user="system"):
        """Включение и выключение розетки. Действие записывается в журнал."""
        try:
            from modules.netmon import smartplug
            if ip not in smartplug.KNOWN_PLUGS:
                return _fail(f"розетка {ip} не в списке известных", 404)
            res = smartplug.switch(ip, on)
            code = "PLUG-" + ip.rsplit(".", 1)[-1]
            f = store.facility(code)
            if f:
                store.add_log(f["id"], {
                    "work_kind": "other",
                    "description": f"Дистанционное {'включение' if on else 'выключение'} "
                                   f"розетки через панель мониторинга",
                    "performer": user, "created_by": user})
            return _ok(res)
        except Exception as e:  # noqa: BLE001
            return _fail(e, 400)

    # ---------------------------------------------------------------- OpenVPN

    @staticmethod
    def vpn():
        """Состояние сервера OpenVPN: кто в сети и какие сертификаты выданы."""
        try:
            from modules.netmon import openvpn as ov
            d = ov.status()
            return _ok({**d, "summary": ov.summary(d)})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def vpn_create(name, user="system", share_minutes=None, share_lang="ru"):
        """Выдаёт новый доступ: сертификат и готовый профиль .ovpn.

        share_minutes — по желанию сразу сделать ссылку для получателя.
        Если сертификат выпущен, а ссылка не создалась, выдача НЕ считается
        неудачной: профиль уже в ответе, ссылку можно сделать отдельно.
        """
        try:
            from modules.netmon import openvpn as ov
            res = ov.create_client((name or "").strip())
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)
        if share_minutes not in (None, "", False, 0, "0"):
            try:
                res["share"] = _make_share(res["name"], res["profile"], share_minutes,
                                           share_lang, user)
            except Exception as e:  # noqa: BLE001
                res["share_error"] = str(e)[:200]
        return _ok(res)

    @staticmethod
    def vpn_share(name, minutes=None, lang="ru", user="system"):
        """Ссылка для получателя на уже выданный сертификат."""
        try:
            from modules.netmon import openvpn as ov
            prof = ov.get_profile((name or "").strip())
            return _ok(_make_share(prof["name"], prof["profile"], minutes, lang, user))
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def vpn_shares():
        try:
            from modules.vpnguide import store
            return _ok(store.list_shares())
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def vpn_share_revoke(share_id, user="system"):
        try:
            from modules.vpnguide import store
            if not store.revoke(int(share_id), f"отозвана вручную ({user})"):
                return _fail("ссылка уже не действует", 404)
            return _ok({"id": int(share_id), "revoked": True})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def vpn_profile(name):
        """Профиль уже выданного сертификата — повторное скачивание без выпуска."""
        try:
            from modules.netmon import openvpn as ov
            return _ok(ov.get_profile((name or "").strip()))
        except ValueError as e:
            return _fail(e, 404)
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def vpn_revoke(name, user="system"):
        """Отзывает доступ — и вместе с ним все живые ссылки на этот профиль."""
        try:
            from modules.netmon import openvpn as ov
            name = (name or "").strip()
            res = ov.revoke_client(name)
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)
        try:
            from modules.vpnguide import store
            res["shares_revoked"] = store.revoke_for_client(name, f"сертификат отозван ({user})",
                                                            kind="openvpn")
        except Exception as e:  # noqa: BLE001
            res["shares_error"] = str(e)[:200]
        return _ok(res)

    # ------------------------------------------------ MikroTik (L2TP/PPTP)

    @staticmethod
    def mikrotik():
        """Главный маршрутизатор: учётки PPP, кто в сети, выводы."""
        try:
            from modules.netmon import mikrotik as mt
            d = mt.status()
            return _ok({**d, "summary": mt.summary(d), "findings": mt.findings(d)})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def mikrotik_create(name, user="system", share_minutes=None, share_lang="ru"):
        """Новая учётка L2TP/IPsec и, по желанию, сразу ссылка для получателя."""
        try:
            from modules.netmon import mikrotik as mt
            res = mt.create_user((name or "").strip(), by=user)
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)
        _attach_l2tp_share(res, share_minutes, share_lang, user)
        return _ok(res)

    @staticmethod
    def mikrotik_reset(name, user="system", share_minutes=None, share_lang="ru"):
        """Новый пароль существующей учётке и ссылка — «редактирование» доступа."""
        try:
            from modules.netmon import mikrotik as mt
            res = mt.reset_password((name or "").strip(), by=user)
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)
        try:
            from modules.vpnguide import store
            store.revoke_for_client(res["name"], f"пароль сменён ({user})", kind="l2tp")
        except Exception:  # noqa: BLE001
            pass        # старые ссылки и так несут старый пароль — он уже не действует
        _attach_l2tp_share(res, share_minutes, share_lang, user)
        return _ok(res)

    @staticmethod
    def mikrotik_disable(name, disabled=True, user="system"):
        """Выключить (с разрывом сессии) или включить учётку. Не удаляем."""
        try:
            from modules.netmon import mikrotik as mt
            res = mt.set_disabled((name or "").strip(), disabled)
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)
        if disabled:
            try:
                from modules.vpnguide import store
                res["shares_revoked"] = store.revoke_for_client(
                    res["name"], f"учётка выключена ({user})", kind="l2tp")
            except Exception as e:  # noqa: BLE001
                res["shares_error"] = str(e)[:200]
        return _ok(res)

    # ------------------------------------- файловые ресурсы 192.168.0.21

    @staticmethod
    def fs_status():
        """Состояние ресурсов, выводы, учёт сотрудников и сверка с сервером."""
        try:
            from modules.netmon import fileshare as fs, fs_store
            d = fs.status()
            people = fs_store.list_people()
            policy = fs_store.load_policy()
            on_server = {u["login"]: u for u in d["local_users"]}
            for p in people:
                srv = on_server.get(p["login"])
                p["on_server"] = srv is not None
                p["server_disabled"] = bool(srv and srv["disabled"])
                p["machines"] = srv["machines"] if srv else []
                p["drives"] = [s["drive"] for s in policy["shares"] if p["role"] in s["roles"]]
            known = {p["login"] for p in people}
            d["unmanaged"] = [u for u in d["local_users"] if u["login"] not in known]
            return _ok({**d, "findings": fs.findings(d), "people": people, "policy": policy,
                        "log": fs_store.recent_log(), "email_domain": fs.EMAIL_DOMAIN,
                        "legacy": list(fs.LEGACY_ACCOUNTS)})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def fs_plan(mode):
        try:
            from modules.netmon import fileshare as fs
            return _ok(fs.plan(mode))
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def fs_apply(mode, md5, user="system"):
        """Изменение доступа всей компании — только после пробного расчёта (md5)."""
        try:
            from modules.netmon import fileshare as fs, fs_store
            res = fs.apply(mode, md5)
            fs_store.log(user, "policy_apply", mode,
                         f"резервная копия {res['backup']}, md5 {res['md5_before']} → {res['md5_after']}")
            return _ok(res)
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def fs_backups():
        try:
            from modules.netmon import fileshare as fs
            return _ok(fs.backups())
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def fs_rollback(backup, user="system"):
        try:
            from modules.netmon import fileshare as fs, fs_store
            res = fs.rollback(backup)
            fs_store.log(user, "policy_rollback", "smb.conf",
                         f"возвращён {res['restored']}, текущий сохранён как {res['saved_current_as']}")
            return _ok(res)
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def fs_add_person(email, full_name, role, user="system", share_minutes=None, share_lang="ru"):
        """Новый сотрудник: учёт по почте, учётка на сервере, ссылка с дисками роли.

        Порядок выбран так, чтобы сбой не оставил «половинчатого» сотрудника:
        запись в учёте → учётка на сервере (при сбое запись удаляется).
        """
        from modules.netmon import fileshare as fs, fs_store
        try:
            email = (email or "").strip().lower()
            login = fs.login_from_email(email)
            policy = fs_store.load_policy()
            if role not in policy["roles"]:
                raise ValueError("неизвестная роль")
            if any(p["email"] == email or p["login"] == login for p in fs_store.list_people()):
                raise ValueError(f"{email} уже в учёте")
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)
        password = fs.new_password()
        try:
            fs_store.add_person(email, login, full_name, role, user)
        except Exception as e:  # noqa: BLE001
            return _fail(f"не записалось в учёт: {e}")
        try:
            fs.ensure_role_groups()
            fs.create_account(login, role, password)
        except Exception as e:  # noqa: BLE001
            fs_store.delete_person(login)
            return _fail(e, 400 if isinstance(e, ValueError) else 500)
        fs_store.log(user, "person_add", login, f"{email}, роль {role}")
        res = {"email": email, "login": login, "role": role, "password": password,
               "server": fs.HOST, "drives": _role_drives(policy, role)}
        _attach_smb_share(res, share_minutes, share_lang, user)
        return _ok(res)

    @staticmethod
    def fs_set_role(login, role, user="system"):
        try:
            from modules.netmon import fileshare as fs, fs_store
            policy = fs_store.load_policy()
            if role not in policy["roles"]:
                raise ValueError("неизвестная роль")
            fs.set_role(login, role)
            fs_store.update_person(login, role=role)
            fs_store.log(user, "person_role", login, f"роль {role}")
            return _ok({"login": login, "role": role, "drives": [d["drive"] for d in _role_drives(policy, role)]})
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def fs_set_disabled(login, disabled, user="system"):
        try:
            from modules.netmon import fileshare as fs, fs_store
            res = fs.set_disabled(login, disabled)
            fs_store.update_person(login, status="disabled" if disabled else "active")
            fs_store.log(user, "person_disable" if disabled else "person_enable", login,
                         f"закрыто подключений {res['sessions_closed']}")
            if disabled:
                from modules.vpnguide import store
                res["shares_revoked"] = store.revoke_for_client(login, f"учётка выключена ({user})", kind="smb")
            return _ok(res)
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def fs_reset(login, user="system", share_minutes=15, share_lang="ru"):
        """Новый пароль и ссылка — «редактирование» доступа сотрудника."""
        try:
            from modules.netmon import fileshare as fs, fs_store
            person = fs_store.get_person(login)
            if not person:
                raise ValueError(f"{login} нет в учёте")
            password = fs.new_password()
            fs.reset_password(login, password)
            fs_store.log(user, "person_reset", login, "новый пароль")
            from modules.vpnguide import store
            store.revoke_for_client(login, f"пароль сменён ({user})", kind="smb")
            policy = fs_store.load_policy()
            res = {"email": person["email"], "login": login, "role": person["role"],
                   "password": password, "server": fs.HOST,
                   "drives": _role_drives(policy, person["role"])}
            _attach_smb_share(res, share_minutes, share_lang, user)
            return _ok(res)
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    # ------------------------------------- нагрузка сервера баз данных

    @staticmethod
    def dbload():
        """Нагрузка Linux cloudbd и сессии Oracle: кто грузит процессор и диск."""
        try:
            from modules.netmon import dbload as dl
            d = dl.collect()
            return _ok({**d, "summary": dl.summary(d)})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    # ------------------------------------------- серьёзное наблюдение

    @staticmethod
    def observe_status():
        try:
            from modules.netmon import observe_store as st
            return _ok(_observe_state())
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def observe_start():
        """Запустить фоновую запись, если она ещё не идёт."""
        try:
            import subprocess
            import sys
            from pathlib import Path
            from modules.netmon import observe_store as st
            state = _observe_state()
            if state["alive"]:
                return _ok({**state, "note": "наблюдение уже идёт"})
            st.set_control(desired="running", last_error=None)
            root = Path(__file__).resolve().parents[2]
            log = st.DB_PATH.parent / "observe.log"
            with open(log, "a") as fh:
                proc = subprocess.Popen(
                    [sys.executable, str(root / "modules/netmon/scripts/netmon_observe.py")],
                    cwd=str(root), stdout=fh, stderr=subprocess.STDOUT,
                    start_new_session=True)          # не умрёт при перезапуске веб-сервера
            # Номер — сразу: иначе повторное нажатие в первые секунды, пока процесс
            # поднимается, запускало второй (поймано проверкой 08.10.2026).
            import time as _t
            st.set_control(pid=proc.pid, started_at=_t.time(), heartbeat=_t.time())
            return _ok({**_observe_state(), "pid": proc.pid, "log": str(log)})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def observe_stop():
        try:
            import os
            import signal
            from modules.netmon import observe_store as st
            ctl = st.control()
            st.set_control(desired="stopped")     # процесс увидит на ближайшем замере
            if ctl["pid"]:
                try:
                    os.kill(ctl["pid"], signal.SIGTERM)
                except ProcessLookupError:
                    st.set_control(pid=None)
            return _ok(_observe_state())
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def observe_settings(values=None):
        try:
            from modules.netmon import observe_store as st
            return _ok(st.save_settings(values) if values else st.get_settings())
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def observe_series(minutes):
        try:
            from modules.netmon import observe_store as st
            m = min(max(float(minutes or 30), 1), 60 * 24 * 7)
            return _ok({**st.series(m), "state": _observe_state()})
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    @staticmethod
    def observe_sessions(ts):
        try:
            from modules.netmon import observe_store as st
            return _ok(st.sessions_at(float(ts)))
        except Exception as e:  # noqa: BLE001
            return _fail(e)

    # ------------------------------------------- диски сервера баз данных

    @staticmethod
    def storage():
        """Состояние аппаратного RAID и разделов сервера cloudbd.

        Здесь есть подвох, ради которого раздел и сделан: система видит
        только логические тома контроллера, и штатный SMART отвечает «OK»
        даже при сдохшем диске в зеркале. Спрашиваем сам контроллер.
        """
        try:
            from modules.netmon import storage as st
            d = st.collect()
            return _ok({**d, "summary": st.summary(d)})
        except Exception as e:  # noqa: BLE001
            return _fail(e)




def _vault_group(what: str) -> str:
    """Группировка доступов по типу объекта."""
    w = what.lower()
    if "oracle" in w or "схема" in w:
        return "Базы данных Oracle"
    if "zabbix" in w:
        return "Мониторинг"
    if "гипервизор" in w or "proxmox" in w:
        return "Виртуализация"
    if "ssh" in w or "сервер" in w:
        return "Серверы (SSH)"
    return "Прочее"

def _service_summary(f: dict, fac) -> dict:
    """Ближайшая просрочка по объекту среди всех видов регламентных работ."""
    from datetime import date
    rules = fac.SERVICE_RULES.get(f["kind"], {})
    worst = {"level": "ok", "text": "по регламенту", "work": None}
    order = {"overdue": 3, "unknown": 2, "soon": 1, "ok": 0}
    for work, days in rules.items():
        if not days:
            continue
        last = (f.get("last_works") or {}).get(work)
        last_date = date.fromisoformat(last) if last else None
        st = fac.service_state(last_date, days)
        st["work"] = fac.WORK_TITLE.get(work, work)
        st["last"] = last
        if order[st["level"]] > order[worst["level"]]:
            worst = st
    return worst


def _make_share(client_name: str, profile: str, minutes, lang: str, user: str,
                kind: str = "openvpn") -> dict:
    """Ссылка для получателя: модуль vpnguide хранит её и отдаёт публично.

    Абсолютный адрес — всегда публичного сервера: открывать ссылку будут
    снаружи, а не с машины администратора.
    """
    from flask import url_for

    from modules.vpnguide import store
    from modules.vpnguide.routes import PUBLIC_BASE
    s = store.create_share(client_name, profile, minutes, user, lang, kind=kind)
    path = url_for("vpnguide.share_page", token=s["token"])
    return {"id": s["id"], "url": PUBLIC_BASE + path,
            "markdown_url": PUBLIC_BASE + url_for("vpnguide.share_markdown", token=s["token"]),
            "ttl_min": s["ttl_min"], "expires_local": s["expires_local"]}


def _attach_l2tp_share(res: dict, minutes, lang: str, user: str) -> None:
    """Ссылка для получателя L2TP. Ключ IPsec читается с маршрутизатора только
    здесь и сразу уходит в шифр — в ответ API и в журналы он не попадает."""
    if minutes in (None, "", False, 0, "0"):
        return
    try:
        from modules.netmon import mikrotik as mt
        from modules.vpnguide import rules
        payload = rules.l2tp_payload(res["server"], res["name"], res["password"], mt.l2tp_psk())
        res["share"] = _make_share(res["name"], payload, minutes, lang, user, kind="l2tp")
    except Exception as e:  # noqa: BLE001
        res["share_error"] = str(e)[:200]


def _role_drives(policy: dict, role: str) -> list[dict]:
    return [{"drive": s["drive"], "share": s["name"], "title": s.get("title") or ""}
            for s in policy["shares"] if role in s["roles"]]


def _attach_smb_share(res: dict, minutes, lang: str, user: str) -> None:
    """Ссылка для сотрудника: диски его роли, файл .cmd, вход СЕРВЕР\\логин."""
    if minutes in (None, "", False, 0, "0"):
        return
    try:
        from modules.netmon import fileshare as fs
        from modules.vpnguide import rules
        payload = rules.smb_payload(fs.HOST, fs.netbios_name(), res["login"], res["password"],
                                    res["drives"])
        res["share"] = _make_share(res["login"], payload, minutes, lang, user, kind="smb")
    except Exception as e:  # noqa: BLE001
        res["share_error"] = str(e)[:200]


def _observe_state() -> dict:
    """Идёт ли наблюдение на самом деле: процесс жив И пульс свежий."""
    import os
    import time
    from modules.netmon import observe_store as st
    ctl, cfg = st.control(), st.get_settings()
    alive = False
    if ctl["pid"]:
        try:
            os.kill(ctl["pid"], 0)
            # пульс должен быть не старше трёх интервалов (и минуты на подключение)
            alive = (time.time() - (ctl["heartbeat"] or 0)) < cfg["interval_sec"] * 3 + 60
        except (ProcessLookupError, PermissionError):
            alive = False
    return {**ctl, "alive": alive, "settings": cfg, "store": st.stats(),
            "heartbeat_age": round(time.time() - ctl["heartbeat"], 1) if ctl["heartbeat"] else None}
