"""SQL модуля vpnguide: ссылки для получателя доступа OpenVPN (VPNG_*).

Все сравнения времени — внутри Oracle, с SYSTIMESTAMP и столбцами
TIMESTAMP WITH TIME ZONE: ссылку создаёт машина администратора, а проверяет
публичный сервер в другом часовом поясе. Наружу время отдаётся в UTC.

Прямой курсор, а не DatabaseModel.execute_query: тот глотает ошибки и
неудобен с CLOB, а здесь молча потерянная запись означает ссылку, которая
не открывается.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from models.database import DatabaseModel
from modules.vpnguide import rules

LOCAL_TZ = ZoneInfo("Europe/Chisinau")
_ISO = "YYYY-MM-DD\"T\"HH24:MI:SS"

_STATE = ("CASE WHEN s.REVOKED_AT IS NOT NULL THEN 'revoked' "
          "WHEN s.EXPIRES_AT <= SYSTIMESTAMP THEN 'expired' ELSE 'active' END")


def _purge(cur) -> int:
    """Стирает шифротекст у истёкших и отозванных ссылок. Строки остаются."""
    cur.execute("UPDATE VPNG_SHARES SET PAYLOAD = NULL "
                "WHERE PAYLOAD IS NOT NULL "
                "AND (EXPIRES_AT <= SYSTIMESTAMP OR REVOKED_AT IS NOT NULL)")
    return cur.rowcount


def local_time(iso_utc: str) -> str:
    """'2026-10-04T19:45:00' (UTC) → '22:45 04.10.2026' по Кишинёву."""
    dt = datetime.strptime(iso_utc, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ).strftime("%H:%M %d.%m.%Y")


def create_share(client_name: str, profile: str, ttl_min, created_by: str,
                 lang: str = "ru") -> dict:
    """Новая ссылка. Токен возвращается ОДИН раз — в базе его нет."""
    minutes = rules.ttl(ttl_min)
    token = rules.new_token()
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        _purge(cur)
        new_id = cur.var(int)
        cur.execute(
            "INSERT INTO VPNG_SHARES (CLIENT_NAME, TOKEN_HASH, PAYLOAD, TTL_MIN, LANG, "
            "EXPIRES_AT, CREATED_BY) VALUES (:cn, :th, :pl, :ttl, :lg, "
            "SYSTIMESTAMP + NUMTODSINTERVAL(:ttl, 'MINUTE'), :usr) RETURNING ID INTO :nid",
            cn=client_name, th=rules.token_hash(token), pl=rules.encrypt(token, profile),
            ttl=minutes, lg=rules.lang(lang), usr=(created_by or "system")[:100], nid=new_id)
        share_id = new_id.getvalue()[0]
        cur.execute(f"SELECT TO_CHAR(SYS_EXTRACT_UTC(EXPIRES_AT), '{_ISO}') "
                    "FROM VPNG_SHARES WHERE ID = :i", i=share_id)
        expires = cur.fetchone()[0]
        db.connection.commit()
    return {"id": share_id, "token": token, "ttl_min": minutes,
            "expires_utc": expires, "expires_local": local_time(expires)}


def open_share(token: str, kind: str, ip: str = "", user_agent: str = "") -> dict:
    """Открыть ссылку: {'state': 'active'|'expired'|'revoked'|'unknown', ...}.

    Каждое открытие пишется в журнал, в том числе открытие уже мёртвой
    ссылки: попытка воспользоваться отозванной ссылкой — повод разобраться.
    """
    if not rules.token_valid(token):
        return {"state": "unknown"}
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        cur.execute(
            f"SELECT s.ID, s.CLIENT_NAME, s.PAYLOAD, s.LANG, "
            f"TO_CHAR(SYS_EXTRACT_UTC(s.EXPIRES_AT), '{_ISO}'), {_STATE}, "
            "ROUND((CAST(SYS_EXTRACT_UTC(s.EXPIRES_AT) AS DATE) "
            "      - CAST(SYS_EXTRACT_UTC(SYSTIMESTAMP) AS DATE)) * 1440) "
            "FROM VPNG_SHARES s WHERE s.TOKEN_HASH = :th", th=rules.token_hash(token))
        row = cur.fetchone()
        if not row:
            return {"state": "unknown"}
        share_id, client, payload, lang, expires, state, left = row
        payload = payload.read() if payload is not None and hasattr(payload, "read") else payload
        cur.execute("INSERT INTO VPNG_SHARE_HITS (SHARE_ID, KIND, CLIENT_IP, USER_AGENT) "
                    "VALUES (:s, :k, :ip, :ua)",
                    s=share_id, k=kind, ip=(ip or "")[:45], ua=(user_agent or "")[:300])
        profile = None
        if state == "active":
            profile = rules.decrypt(token, payload) if payload else None
            if profile is None:
                state = "expired"     # шифротекст стёрт или не сходится — ссылка мертва
        else:
            _purge(cur)
        db.connection.commit()
    res = {"state": state, "id": share_id, "client_name": client, "lang": lang,
           "expires_utc": expires, "expires_local": local_time(expires),
           "minutes_left": max(int(left or 0), 0)}
    if profile is not None:
        res["profile"] = profile
    return res


def revoke(share_id: int, reason: str = "") -> bool:
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        cur.execute("UPDATE VPNG_SHARES SET REVOKED_AT = SYSTIMESTAMP, PAYLOAD = NULL, "
                    "REVOKE_REASON = :r WHERE ID = :i AND REVOKED_AT IS NULL",
                    r=(reason or "")[:200], i=share_id)
        n = cur.rowcount
        db.connection.commit()
    return n > 0


def revoke_for_client(client_name: str, reason: str) -> int:
    """Все живые ссылки клиента — при отзыве его сертификата."""
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        cur.execute("UPDATE VPNG_SHARES SET REVOKED_AT = SYSTIMESTAMP, PAYLOAD = NULL, "
                    "REVOKE_REASON = :r WHERE CLIENT_NAME = :cn AND REVOKED_AT IS NULL "
                    "AND EXPIRES_AT > SYSTIMESTAMP",
                    r=(reason or "")[:200], cn=client_name)
        n = cur.rowcount
        db.connection.commit()
    return n


def list_shares(limit: int = 50) -> list[dict]:
    with DatabaseModel() as db:
        cur = db.connection.cursor()
        _purge(cur)
        db.connection.commit()
        cur.execute(
            "SELECT * FROM ("
            f" SELECT s.ID, s.CLIENT_NAME, TO_CHAR(SYS_EXTRACT_UTC(s.CREATED_AT), '{_ISO}'),"
            f"  TO_CHAR(SYS_EXTRACT_UTC(s.EXPIRES_AT), '{_ISO}'), s.TTL_MIN, s.CREATED_BY,"
            f"  {_STATE}, s.REVOKE_REASON,"
            "  (SELECT COUNT(*) FROM VPNG_SHARE_HITS h WHERE h.SHARE_ID = s.ID AND h.KIND = 'page'),"
            "  (SELECT COUNT(*) FROM VPNG_SHARE_HITS h WHERE h.SHARE_ID = s.ID AND h.KIND = 'profile'),"
            f"  (SELECT TO_CHAR(SYS_EXTRACT_UTC(MAX(h.HIT_AT)), '{_ISO}') FROM VPNG_SHARE_HITS h"
            "    WHERE h.SHARE_ID = s.ID)"
            " FROM VPNG_SHARES s ORDER BY s.ID DESC"
            ") WHERE ROWNUM <= :lim", lim=int(limit))
        rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({"id": r[0], "client_name": r[1],
                    "created_local": local_time(r[2]), "expires_local": local_time(r[3]),
                    "ttl_min": r[4], "created_by": r[5], "state": r[6],
                    "revoke_reason": r[7], "page_hits": r[8], "downloads": r[9],
                    "last_hit_local": local_time(r[10]) if r[10] else None})
    return out
