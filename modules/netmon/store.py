"""Хранилище модуля netmon: весь SQL к таблицам NMON_* — только здесь.

Наружу отдаёт готовые словари; ни один другой файл модуля в Oracle не ходит.
"""
from __future__ import annotations

from models.database import DatabaseModel

from modules.netmon import rules


def _rows(r):
    """execute_query отдаёт то dict, то список — приводим к списку кортежей."""
    if isinstance(r, dict):
        return r.get("data") or []
    return r or []


def _dicts(r, cols):
    return [dict(zip(cols, row)) for row in _rows(r)]


def _checked(r, what: str = "запрос"):
    """execute_query НЕ бросает исключений: при ошибке возвращает success=False.

    Из-за этого неудачная вставка выглядела как успешная, и 5 из 51 паспорта
    молча не сохранялись. Все изменяющие запросы проходят через эту проверку.
    """
    if isinstance(r, dict) and r.get("success") is False:
        raise RuntimeError(f"{what}: {r.get('message', 'неизвестная ошибка')}")
    return r


def _commit(db) -> None:
    try:
        db.connection.commit()
    except Exception:  # noqa: BLE001 — часть обёрток коммитит сама
        pass


# ------------------------------------------------------------------ прогоны скана

def start_scan(subnet: str, run_by: str) -> int:
    with DatabaseModel() as db:
        db.execute_query(
            "INSERT INTO NMON_SCANS (SUBNET, RUN_BY) VALUES (:subnet, :run_by)",
            {"subnet": subnet, "run_by": run_by})
        r = db.execute_query("SELECT NMON_SCANS_SEQ.CURRVAL FROM DUAL")
        _commit(db)
        return int(_rows(r)[0][0])


def finish_scan(scan_id: int, found: int, new: int, gone: int) -> None:
    with DatabaseModel() as db:
        db.execute_query(
            "UPDATE NMON_SCANS SET FINISHED_AT = SYSTIMESTAMP, HOSTS_FOUND = :f, "
            "HOSTS_NEW = :n, HOSTS_GONE = :g WHERE ID = :id",
            {"f": found, "n": new, "g": gone, "id": scan_id})
        _commit(db)


# ------------------------------------------------------------------ устройства

def upsert_device(dev: dict, scan_id: int) -> bool:
    """Пишет устройство; возвращает True, если оно увидено впервые."""
    params = {
        "ip": dev["ip"],
        "dns": (dev.get("dns") or "")[:150] or None,
        "ttl": dev.get("ttl"),
        "ports": ",".join(str(p) for p in dev.get("ports") or [])[:300] or None,
        "kind": (dev.get("kind") or "")[:80] or None,
        "crit": dev.get("criticality") or rules.criticality(dev.get("kind") or ""),
        "title": (dev.get("title") or "")[:200] or None,
        "srv": (dev.get("server") or "")[:120] or None,
        "ssh": (dev.get("ssh") or "")[:120] or None,
        "inz": "Y" if dev.get("in_zabbix") else "N",
        "zhost": (dev.get("zabbix_host") or "")[:128] or None,
        "scan": scan_id,
    }
    with DatabaseModel() as db:
        exists = _rows(db.execute_query("SELECT ID FROM NMON_DEVICES WHERE IP = :ip",
                                        {"ip": dev["ip"]}))
        if exists:
            db.execute_query(
                "UPDATE NMON_DEVICES SET DNS_NAME = :dns, TTL = :ttl, PORTS = :ports, "
                "KIND = :kind, CRITICALITY = :crit, TITLE = :title, SERVER_BANNER = :srv, "
                "SSH_BANNER = :ssh, IN_ZABBIX = :inz, ZABBIX_HOST = :zhost, STATUS = 'up', "
                "LAST_SEEN = SYSTIMESTAMP, LAST_SCAN_ID = :scan WHERE IP = :ip", params)
            _commit(db)
            return False
        db.execute_query(
            "INSERT INTO NMON_DEVICES (IP, DNS_NAME, TTL, PORTS, KIND, CRITICALITY, TITLE, "
            "SERVER_BANNER, SSH_BANNER, IN_ZABBIX, ZABBIX_HOST, LAST_SCAN_ID) "
            "VALUES (:ip, :dns, :ttl, :ports, :kind, :crit, :title, :srv, :ssh, :inz, "
            ":zhost, :scan)", params)
        _commit(db)
        return True


def mark_gone(seen_ips: list[str], scan_id: int) -> int:
    """Устройства, которых не было в этом прогоне, помечаются как down."""
    if not seen_ips:
        return 0
    seen = set(seen_ips)
    with DatabaseModel() as db:
        rows = _rows(db.execute_query("SELECT IP FROM NMON_DEVICES WHERE STATUS = 'up'"))
        gone = [r[0] for r in rows if r[0] not in seen]
        for ip in gone:
            db.execute_query(
                "UPDATE NMON_DEVICES SET STATUS = 'down', LAST_SCAN_ID = :scan WHERE IP = :ip",
                {"scan": scan_id, "ip": ip})
        _commit(db)
        return len(gone)


DEVICE_COLS = ("id", "ip", "dns_name", "ttl", "ports", "kind", "criticality", "title",
               "server_banner", "ssh_banner", "in_zabbix", "zabbix_host", "status",
               "first_seen", "last_seen")


def devices(kind: str | None = None, only_missing: bool = False) -> list[dict]:
    sql = ("SELECT ID, IP, DNS_NAME, TTL, PORTS, KIND, CRITICALITY, TITLE, SERVER_BANNER, "
           "SSH_BANNER, IN_ZABBIX, ZABBIX_HOST, STATUS, "
           "TO_CHAR(FIRST_SEEN, 'DD.MM.YYYY'), TO_CHAR(LAST_SEEN, 'DD.MM HH24:MI') "
           "FROM NMON_DEVICES WHERE 1 = 1")
    p: dict = {}
    if kind:
        sql += " AND KIND = :kind"
        p["kind"] = kind
    if only_missing:
        sql += " AND IN_ZABBIX = 'N'"
    sql += (" ORDER BY TO_NUMBER(REGEXP_SUBSTR(IP, '\\d+', 1, 3)), "
            "TO_NUMBER(REGEXP_SUBSTR(IP, '\\d+', 1, 4))")
    with DatabaseModel() as db:
        return _dicts(db.execute_query(sql, p or None), DEVICE_COLS)


def device_stats() -> dict:
    with DatabaseModel() as db:
        total = _rows(db.execute_query(
            "SELECT COUNT(*), SUM(CASE WHEN IN_ZABBIX = 'Y' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN STATUS = 'up' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN CRITICALITY = 'high' THEN 1 ELSE 0 END) FROM NMON_DEVICES"))
        by_kind = _rows(db.execute_query(
            "SELECT KIND, COUNT(*) FROM NMON_DEVICES GROUP BY KIND ORDER BY COUNT(*) DESC"))
        last = _rows(db.execute_query(
            "SELECT TO_CHAR(MAX(FINISHED_AT), 'DD.MM.YYYY HH24:MI') FROM NMON_SCANS"))
    t = total[0] if total else (0, 0, 0, 0)
    return {
        "total": int(t[0] or 0),
        "in_zabbix": int(t[1] or 0),
        "up": int(t[2] or 0),
        "critical": int(t[3] or 0),
        "by_kind": [{"kind": k, "count": int(c)} for k, c in by_kind],
        "last_scan": last[0][0] if last and last[0][0] else None,
    }


# ------------------------------------------------------------------ Telegram-каналы

def upsert_channel(ch: dict) -> int:
    params = {
        "chat": str(ch["chat_id"]),
        "title": (ch.get("title") or "")[:200] or None,
        "ctype": ch.get("chat_type") or rules.channel_kind(ch["chat_id"]),
        "cnt": ch.get("members_count"),
        "bot": (ch.get("bot_username") or "")[:100] or None,
        "mt": (ch.get("mediatype") or "")[:100] or None,
        "usr": (ch.get("zbx_user") or "")[:100] or None,
        "en": "Y" if ch.get("enabled", True) else "N",
        "note": (ch.get("note") or "")[:400] or None,
    }
    with DatabaseModel() as db:
        found = _rows(db.execute_query(
            "SELECT ID FROM NMON_TG_CHANNELS WHERE CHAT_ID = :chat", {"chat": params["chat"]}))
        if found:
            db.execute_query(
                "UPDATE NMON_TG_CHANNELS SET TITLE = :title, CHAT_TYPE = :ctype, "
                "MEMBERS_CNT = :cnt, BOT_USERNAME = :bot, MEDIATYPE = :mt, ZBX_USER = :usr, "
                "IS_ENABLED = :en, NOTE = :note, LAST_SYNC_AT = SYSTIMESTAMP "
                "WHERE CHAT_ID = :chat", params)
            _commit(db)
            return int(found[0][0])
        db.execute_query(
            "INSERT INTO NMON_TG_CHANNELS (CHAT_ID, TITLE, CHAT_TYPE, MEMBERS_CNT, "
            "BOT_USERNAME, MEDIATYPE, ZBX_USER, IS_ENABLED, NOTE, LAST_SYNC_AT) "
            "VALUES (:chat, :title, :ctype, :cnt, :bot, :mt, :usr, :en, :note, SYSTIMESTAMP)",
            params)
        r = db.execute_query("SELECT NMON_TG_CHANNELS_SEQ.CURRVAL FROM DUAL")
        _commit(db)
        return int(_rows(r)[0][0])


CHANNEL_COLS = ("id", "chat_id", "title", "chat_type", "members_cnt", "bot_username",
                "mediatype", "zbx_user", "is_enabled", "last_sync_at", "last_alert_at", "note")


def channels() -> list[dict]:
    with DatabaseModel() as db:
        rows = _dicts(db.execute_query(
            "SELECT ID, CHAT_ID, TITLE, CHAT_TYPE, MEMBERS_CNT, BOT_USERNAME, MEDIATYPE, "
            "ZBX_USER, IS_ENABLED, TO_CHAR(LAST_SYNC_AT, 'DD.MM HH24:MI'), "
            "TO_CHAR(LAST_ALERT_AT, 'DD.MM HH24:MI'), NOTE "
            "FROM NMON_TG_CHANNELS ORDER BY IS_ENABLED DESC, ID"), CHANNEL_COLS)
        for c in rows:
            st = _rows(db.execute_query(
                "SELECT COUNT(*), SUM(CASE WHEN SEND_STATUS = 'sent' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN SEND_STATUS = 'failed' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN SENT_AT > SYSTIMESTAMP - 1 THEN 1 ELSE 0 END) "
                "FROM NMON_TG_ALERTS WHERE CHANNEL_ID = :id", {"id": c["id"]}))
            s = st[0] if st else (0, 0, 0, 0)
            c["alerts_total"] = int(s[0] or 0)
            c["alerts_sent"] = int(s[1] or 0)
            c["alerts_failed"] = int(s[2] or 0)
            c["alerts_24h"] = int(s[3] or 0)
        return rows


def channel_id_by_chat(chat_id: str):
    with DatabaseModel() as db:
        r = _rows(db.execute_query("SELECT ID FROM NMON_TG_CHANNELS WHERE CHAT_ID = :c",
                                   {"c": str(chat_id)}))
    return int(r[0][0]) if r else None


# ------------------------------------------------------------------ лента алертов

def upsert_alerts(rows: list[dict]) -> int:
    """Пишет пачку отправленных сообщений в ОДНОМ соединении.

    По одному соединению на запись 1200 алертов грузились минутами — поэтому
    здесь единственный connect, один SELECT существующих id и executemany.
    Возвращает число реально добавленных.
    """
    if not rows:
        return 0
    with DatabaseModel() as db:
        have = {int(r[0]) for r in _rows(db.execute_query(
            "SELECT ZBX_ALERTID FROM NMON_TG_ALERTS"))}
        # дедупликация и по базе, и внутри самой пачки: Zabbix отдаёт один
        # alertid дважды, когда сообщение ушло в несколько адресатов
        fresh, seen = [], set()
        for a in rows:
            aid = int(a["alertid"])
            if aid in have or aid in seen:
                continue
            seen.add(aid)
            fresh.append(a)
        if not fresh:
            return 0
        data = [{
            "aid": int(a["alertid"]), "ch": a["channel_id"], "clock": a["clock"],
            "subj": (a.get("subject") or "")[:500], "sev": a.get("severity"),
            "host": (a.get("host") or "")[:128] or None, "status": a.get("status"),
            "retries": a.get("retries") or 0,
            "err": (a.get("error") or "")[:500] or None,
        } for a in fresh]
        sql = ("INSERT INTO NMON_TG_ALERTS (ZBX_ALERTID, CHANNEL_ID, SENT_AT, SUBJECT, "
               "SEVERITY, HOST_NAME, SEND_STATUS, RETRIES, ERROR_TEXT) VALUES (:aid, :ch, "
               "TO_TIMESTAMP('1970-01-01', 'YYYY-MM-DD') + NUMTODSINTERVAL(:clock, 'SECOND'), "
               ":subj, :sev, :host, :status, :retries, :err)")
        with db.connection.cursor() as cur:
            cur.executemany(sql, data)
        db.execute_query(
            "UPDATE NMON_TG_CHANNELS c SET LAST_ALERT_AT = "
            "(SELECT MAX(SENT_AT) FROM NMON_TG_ALERTS a WHERE a.CHANNEL_ID = c.ID)")
        _commit(db)
        return len(fresh)


ALERT_COLS = ("id", "zbx_alertid", "channel_id", "sent_at", "subject", "severity",
              "host_name", "send_status", "retries", "error_text", "channel_title")


def alerts(limit: int = 100, channel_id: int | None = None,
           severity: str | None = None) -> list[dict]:
    sql = ("SELECT a.ID, a.ZBX_ALERTID, a.CHANNEL_ID, TO_CHAR(a.SENT_AT, 'DD.MM HH24:MI'), "
           "a.SUBJECT, a.SEVERITY, a.HOST_NAME, a.SEND_STATUS, a.RETRIES, a.ERROR_TEXT, "
           "c.TITLE FROM NMON_TG_ALERTS a JOIN NMON_TG_CHANNELS c ON c.ID = a.CHANNEL_ID "
           "WHERE 1 = 1")
    p: dict = {}
    if channel_id:
        sql += " AND a.CHANNEL_ID = :ch"
        p["ch"] = channel_id
    if severity:
        sql += " AND a.SEVERITY = :sev"
        p["sev"] = severity
    sql += " ORDER BY a.SENT_AT DESC"
    with DatabaseModel() as db:
        rows = _dicts(db.execute_query(sql, p or None), ALERT_COLS)
    return rows[:limit]


def alert_stats() -> dict:
    with DatabaseModel() as db:
        by_sev = _rows(db.execute_query(
            "SELECT SEVERITY, COUNT(*) FROM NMON_TG_ALERTS GROUP BY SEVERITY "
            "ORDER BY COUNT(*) DESC"))
        by_host = _rows(db.execute_query(
            "SELECT HOST_NAME, COUNT(*) FROM NMON_TG_ALERTS WHERE HOST_NAME IS NOT NULL "
            "GROUP BY HOST_NAME ORDER BY COUNT(*) DESC"))
        by_day = _rows(db.execute_query(
            "SELECT TO_CHAR(SENT_AT, 'DD.MM'), COUNT(*) FROM NMON_TG_ALERTS "
            "WHERE SENT_AT > SYSTIMESTAMP - 14 GROUP BY TO_CHAR(SENT_AT, 'DD.MM') "
            "ORDER BY MIN(SENT_AT)"))
        totals = _rows(db.execute_query(
            "SELECT COUNT(*), SUM(CASE WHEN SEND_STATUS = 'failed' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN SENT_AT > SYSTIMESTAMP - 1 THEN 1 ELSE 0 END) FROM NMON_TG_ALERTS"))
    t = totals[0] if totals else (0, 0, 0)
    return {
        "total": int(t[0] or 0),
        "failed": int(t[1] or 0),
        "last_24h": int(t[2] or 0),
        "by_severity": [{"severity": s, "count": int(c)} for s, c in by_sev],
        "top_hosts": [{"host": h, "count": int(c)} for h, c in by_host][:12],
        "by_day": [{"day": d, "count": int(c)} for d, c in by_day],
    }


def counters() -> dict:
    """Сводка для /api/status (совместимость с каркасом модуля)."""
    d = device_stats()
    a = alert_stats()
    return {"devices": d["total"], "in_zabbix": d["in_zabbix"], "alerts": a["total"]}


# ------------------------------------------------------------------ гости Proxmox

def _j(value, limit: int) -> str | None:
    """Списки и словари кладём строкой: их показывают как есть, не ищут по ним."""
    import json as _json
    if not value:
        return None
    s = value if isinstance(value, str) else _json.dumps(value, ensure_ascii=False)
    return s[:limit] or None


def upsert_guest(node: str, g: dict) -> bool:
    """Паспорт гостя гипервизора. True, если запись новая."""
    f = g.get("descr_fields") or {}
    params = {
        "node": node, "vmid": g["vmid"], "kind": g["kind"],
        "name": (g.get("name") or "")[:128] or None,
        "status": (g.get("status") or "")[:16] or None,
        "cores": g.get("cores") or 0,
        "mem": g.get("memory_mb") or 0,
        "disk": g.get("disk_gb") or 0,
        "os": (g.get("ostype") or "")[:32] or None,
        "onboot": "Y" if g.get("onboot") else "N",
        "legacy": "Y" if g.get("legacy_os") else "N",
        "risk": g.get("risk_level") or "low",
        "dec": (g.get("decision") or "")[:40] or None,
        "backup": (g.get("last_backup") or "")[:10] or None,
        "snaps": g.get("snapshots") or 0,
        "up": g.get("uptime_s") or 0,
        "ip": (f.get("ip") or "")[:64] or None,
        "role": (f.get("role") or f.get("роль") or "")[:300] or None,
        "oshint": (f.get("os") or "")[:120] or None,
        "risks": _j("; ".join(g.get("risks") or []), 1000),
        "notes": _j("; ".join(g.get("notes") or []), 1000),
        "descr": _j(g.get("description"), 2000),
        "nets": _j(g.get("nets"), 600),
        "disks": _j(g.get("disks"), 600),
    }
    with DatabaseModel() as db:
        found = _rows(db.execute_query(
            "SELECT ID FROM NMON_PVE_GUESTS WHERE NODE_NAME = :node AND VMID = :vmid",
            {"node": node, "vmid": g["vmid"]}))
        if found:
            _checked(db.execute_query(
                "UPDATE NMON_PVE_GUESTS SET KIND=:kind, NAME=:name, STATUS=:status, "
                "CORES=:cores, MEMORY_MB=:mem, DISK_GB=:disk, OSTYPE=:os, ONBOOT=:onboot, "
                "LEGACY_OS=:legacy, RISK_LEVEL=:risk, DECISION=:dec, LAST_BACKUP=:backup, "
                "SNAPSHOTS=:snaps, UPTIME_S=:up, IP_HINT=:ip, ROLE_HINT=:role, "
                "OS_HINT=:oshint, RISKS=:risks, NOTES=:notes, DESCR=:descr, NETS=:nets, "
                "DISKS=:disks, SYNCED_AT=SYSTIMESTAMP "
                "WHERE NODE_NAME=:node AND VMID=:vmid", params), f"обновление гостя {g['vmid']}")
            _commit(db)
            return False
        _checked(db.execute_query(
            "INSERT INTO NMON_PVE_GUESTS (NODE_NAME, VMID, KIND, NAME, STATUS, CORES, "
            "MEMORY_MB, DISK_GB, OSTYPE, ONBOOT, LEGACY_OS, RISK_LEVEL, DECISION, "
            "LAST_BACKUP, SNAPSHOTS, UPTIME_S, IP_HINT, ROLE_HINT, OS_HINT, RISKS, NOTES, "
            "DESCR, NETS, DISKS) VALUES (:node, :vmid, :kind, :name, :status, :cores, :mem, "
            ":disk, :os, :onboot, :legacy, :risk, :dec, :backup, :snaps, :up, :ip, :role, "
            ":oshint, :risks, :notes, :descr, :nets, :disks)", params), f"вставка гостя {g['vmid']}")
        _commit(db)
        return True


GUEST_COLS = ("id", "node_name", "vmid", "kind", "name", "status", "cores", "memory_mb",
              "disk_gb", "ostype", "onboot", "legacy_os", "risk_level", "decision",
              "last_backup", "snapshots", "uptime_s", "ip_hint", "role_hint", "os_hint",
              "risks", "notes", "descr", "nets", "disks", "synced_at")


def guests(status: str | None = None, decision: str | None = None,
           risk: str | None = None) -> list[dict]:
    sql = ("SELECT ID, NODE_NAME, VMID, KIND, NAME, STATUS, CORES, MEMORY_MB, DISK_GB, "
           "OSTYPE, ONBOOT, LEGACY_OS, RISK_LEVEL, DECISION, LAST_BACKUP, SNAPSHOTS, "
           "UPTIME_S, IP_HINT, ROLE_HINT, OS_HINT, RISKS, NOTES, DESCR, NETS, DISKS, "
           "TO_CHAR(SYNCED_AT, 'DD.MM HH24:MI') FROM NMON_PVE_GUESTS WHERE 1 = 1")
    p: dict = {}
    if status:
        sql += " AND STATUS = :st"
        p["st"] = status
    if decision:
        sql += " AND DECISION = :dec"
        p["dec"] = decision
    if risk:
        sql += " AND RISK_LEVEL = :risk"
        p["risk"] = risk
    sql += " ORDER BY VMID"
    with DatabaseModel() as db:
        return _dicts(db.execute_query(sql, p or None), GUEST_COLS)


def guest_stats() -> dict:
    with DatabaseModel() as db:
        t = _rows(db.execute_query(
            "SELECT COUNT(*), SUM(CASE WHEN STATUS='running' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN LEGACY_OS='Y' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN LAST_BACKUP IS NULL THEN 1 ELSE 0 END), "
            "SUM(DISK_GB), SUM(MEMORY_MB), SUM(CASE WHEN KIND='qemu' THEN 1 ELSE 0 END) "
            "FROM NMON_PVE_GUESTS"))
        by_dec = _rows(db.execute_query(
            "SELECT DECISION, COUNT(*) FROM NMON_PVE_GUESTS GROUP BY DECISION "
            "ORDER BY COUNT(*) DESC"))
        by_risk = _rows(db.execute_query(
            "SELECT RISK_LEVEL, COUNT(*) FROM NMON_PVE_GUESTS GROUP BY RISK_LEVEL"))
    r = t[0] if t else (0, 0, 0, 0, 0, 0, 0)
    return {
        "total": int(r[0] or 0), "running": int(r[1] or 0),
        "stopped": int(r[0] or 0) - int(r[1] or 0),
        "legacy_os": int(r[2] or 0), "no_backup": int(r[3] or 0),
        "disk_gb": round(float(r[4] or 0), 1), "memory_mb": int(r[5] or 0),
        "vm": int(r[6] or 0), "ct": int(r[0] or 0) - int(r[6] or 0),
        "by_decision": [{"decision": d, "count": int(c)} for d, c in by_dec],
        "by_risk": {k: int(v) for k, v in by_risk},
    }


# ------------------------------------------------------------------ оборудование

FAC_COLS = ("id", "code", "kind", "name", "room", "model", "serial_no", "vendor",
            "ip", "protocol", "installed_on", "responsible", "service_days",
            "status", "is_monitored", "note", "updated_at")

FAC_SELECT = ("SELECT ID, CODE, KIND, NAME, ROOM, MODEL, SERIAL_NO, VENDOR, IP, "
              "PROTOCOL, TO_CHAR(INSTALLED_ON,'YYYY-MM-DD'), RESPONSIBLE, "
              "SERVICE_DAYS, STATUS, IS_MONITORED, NOTE, "
              "TO_CHAR(UPDATED_AT,'DD.MM.YYYY HH24:MI') FROM NMON_FACILITIES")


def upsert_facility(f: dict) -> bool:
    p = {"code": f["code"], "kind": f["kind"], "name": f["name"],
         "room": f.get("room"), "model": f.get("model"), "serial": f.get("serial_no"),
         "vendor": f.get("vendor"), "ip": f.get("ip"), "proto": f.get("protocol"),
         "resp": f.get("responsible"), "days": f.get("service_days", 180),
         "status": f.get("status", "ok"), "mon": f.get("is_monitored", "N"),
         "note": f.get("note")}
    with DatabaseModel() as db:
        found = _rows(db.execute_query(
            "SELECT ID FROM NMON_FACILITIES WHERE CODE = :code", {"code": p["code"]}))
        if found:
            db.execute_query(
                "UPDATE NMON_FACILITIES SET KIND=:kind, NAME=:name, ROOM=:room, "
                "MODEL=:model, SERIAL_NO=:serial, VENDOR=:vendor, IP=:ip, "
                "PROTOCOL=:proto, RESPONSIBLE=:resp, SERVICE_DAYS=:days, "
                "STATUS=:status, IS_MONITORED=:mon, NOTE=:note, "
                "UPDATED_AT=SYSTIMESTAMP WHERE CODE=:code", p)
            _commit(db)
            return False
        db.execute_query(
            "INSERT INTO NMON_FACILITIES (CODE, KIND, NAME, ROOM, MODEL, SERIAL_NO, "
            "VENDOR, IP, PROTOCOL, RESPONSIBLE, SERVICE_DAYS, STATUS, IS_MONITORED, "
            "NOTE) VALUES (:code, :kind, :name, :room, :model, :serial, :vendor, :ip, "
            ":proto, :resp, :days, :status, :mon, :note)", p)
        _commit(db)
        return True


def facilities(kind: str | None = None, room: str | None = None) -> list[dict]:
    sql, p = FAC_SELECT + " WHERE 1 = 1", {}
    if kind:
        sql += " AND KIND = :kind"
        p["kind"] = kind
    if room:
        sql += " AND ROOM = :room"
        p["room"] = room
    sql += " ORDER BY KIND, CODE"
    with DatabaseModel() as db:
        rows = _dicts(db.execute_query(sql, p or None), FAC_COLS)
    # к каждому объекту — дата последних работ каждого вида
    last = last_works()
    for r in rows:
        r["last_works"] = last.get(r["id"], {})
    return rows


def facility(code: str) -> dict | None:
    with DatabaseModel() as db:
        rows = _dicts(db.execute_query(FAC_SELECT + " WHERE CODE = :c", {"c": code}),
                      FAC_COLS)
    if not rows:
        return None
    f = rows[0]
    f["log"] = facility_log(f["id"])
    f["photos"] = facility_photos(f["id"])
    f["last_works"] = last_works().get(f["id"], {})
    return f


def last_works() -> dict:
    """Последняя дата каждого вида работ по каждому объекту."""
    with DatabaseModel() as db:
        rows = _rows(db.execute_query(
            "SELECT FACILITY_ID, WORK_KIND, TO_CHAR(MAX(DONE_AT),'YYYY-MM-DD') "
            "FROM NMON_FAC_LOG GROUP BY FACILITY_ID, WORK_KIND"))
    out: dict = {}
    for fid, kind, when in rows:
        out.setdefault(int(fid), {})[kind] = when
    return out


LOG_COLS = ("id", "facility_id", "work_kind", "done_at", "performer",
            "description", "next_due", "cost_mdl", "created_by", "created_at")


def add_log(facility_id: int, work: dict) -> int:
    p = {"fid": facility_id, "kind": work["work_kind"],
         "done": work.get("done_at"), "perf": work.get("performer"),
         "descr": work.get("description"), "due": work.get("next_due"),
         "cost": work.get("cost_mdl"), "usr": work.get("created_by", "system")}
    with DatabaseModel() as db:
        db.execute_query(
            "INSERT INTO NMON_FAC_LOG (FACILITY_ID, WORK_KIND, DONE_AT, PERFORMER, "
            "DESCRIPTION, NEXT_DUE, COST_MDL, CREATED_BY) VALUES (:fid, :kind, "
            "NVL(TO_DATE(:done,'YYYY-MM-DD'), SYSDATE), :perf, :descr, "
            "TO_DATE(:due,'YYYY-MM-DD'), :cost, :usr)", p)
        r = db.execute_query("SELECT NMON_FAC_LOG_SEQ.CURRVAL FROM DUAL")
        _commit(db)
        return int(_rows(r)[0][0])


def facility_log(facility_id: int, limit: int = 100) -> list[dict]:
    with DatabaseModel() as db:
        return _dicts(db.execute_query(
            "SELECT ID, FACILITY_ID, WORK_KIND, TO_CHAR(DONE_AT,'YYYY-MM-DD'), "
            "PERFORMER, DESCRIPTION, TO_CHAR(NEXT_DUE,'YYYY-MM-DD'), COST_MDL, "
            "CREATED_BY, TO_CHAR(CREATED_AT,'DD.MM.YYYY HH24:MI') FROM NMON_FAC_LOG "
            "WHERE FACILITY_ID = :fid ORDER BY DONE_AT DESC, ID DESC",
            {"fid": facility_id}), LOG_COLS)


PHOTO_COLS = ("id", "facility_id", "log_id", "file_path", "file_name", "caption",
              "taken_by", "taken_at", "size_kb")


def add_photo(facility_id: int, ph: dict) -> int:
    p = {"fid": facility_id, "log": ph.get("log_id"), "path": ph["file_path"],
         "name": ph.get("file_name"), "cap": ph.get("caption"),
         "usr": ph.get("taken_by", "system"), "kb": ph.get("size_kb")}
    with DatabaseModel() as db:
        db.execute_query(
            "INSERT INTO NMON_FAC_PHOTO (FACILITY_ID, LOG_ID, FILE_PATH, FILE_NAME, "
            "CAPTION, TAKEN_BY, SIZE_KB) VALUES (:fid, :log, :path, :name, :cap, "
            ":usr, :kb)", p)
        r = db.execute_query("SELECT NMON_FAC_PHOTO_SEQ.CURRVAL FROM DUAL")
        _commit(db)
        return int(_rows(r)[0][0])


def facility_photos(facility_id: int, limit: int = 60) -> list[dict]:
    with DatabaseModel() as db:
        return _dicts(db.execute_query(
            "SELECT ID, FACILITY_ID, LOG_ID, FILE_PATH, FILE_NAME, CAPTION, TAKEN_BY, "
            "TO_CHAR(TAKEN_AT,'DD.MM.YYYY HH24:MI'), SIZE_KB FROM NMON_FAC_PHOTO "
            "WHERE FACILITY_ID = :fid ORDER BY TAKEN_AT DESC", {"fid": facility_id}),
            PHOTO_COLS)


def facility_stats() -> dict:
    with DatabaseModel() as db:
        by_kind = _rows(db.execute_query(
            "SELECT KIND, COUNT(*) FROM NMON_FACILITIES GROUP BY KIND"))
        tot = _rows(db.execute_query(
            "SELECT COUNT(*), SUM(CASE WHEN STATUS='ok' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN IS_MONITORED='Y' THEN 1 ELSE 0 END) FROM NMON_FACILITIES"))
        works = _rows(db.execute_query("SELECT COUNT(*) FROM NMON_FAC_LOG"))
        photos = _rows(db.execute_query("SELECT COUNT(*) FROM NMON_FAC_PHOTO"))
    t = tot[0] if tot else (0, 0, 0)
    return {"total": int(t[0] or 0), "ok": int(t[1] or 0), "monitored": int(t[2] or 0),
            "by_kind": {k: int(c) for k, c in by_kind},
            "works": int(works[0][0]) if works else 0,
            "photos": int(photos[0][0]) if photos else 0}
