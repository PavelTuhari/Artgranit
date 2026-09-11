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
        fresh = [a for a in rows if int(a["alertid"]) not in have]
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
