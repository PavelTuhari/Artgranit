"""UaMenu Cassa — источник мониторинга касс через Oracle DB Links.

Порт логики боевого дашборда `unisim-dashboard.una.md`
(`/var/www/unisim-dashboard/api.php` на 192.168.0.148) в движок Artgranit:

    1. в схеме источника читается `ybmb_dif_cassa` (реестр касс) с именем
       родителя-магазина из `tms_univers.denumirea`;
    2. для каждой кассы её доступность проверяется по DB Link —
       `SELECT pvalue FROM tms_init_params@<PREFIX>.WORLD WHERE pname='ServerID'`;
    3. статус кассы: OFF_LINE=1 → SHUTDOWN; ServerID получен → ONLINE;
       иначе OFFLINE с текстом ошибки DB Link;
    4. агрегат магазина считается представлением `V_TBC_CASSA_STORES`
       (правило FUNCTIONAL при доле online ≥ 60% — как в оригинале).

Источники живут в Oracle 11g `cloudbd` (та же БД, что OfficePlus/Biro26),
поэтому доступ идёт через уже существующий thick-режимный subprocess-воркер
`models/biro26_worker.py` с override учётных данных (`auth`). Основной
thin-контур приложения (production nufarul.eminescu.md) не затрагивается.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKER = os.path.join(_PROJECT_ROOT, "models", "biro26_worker.py")

# Таймауты: источник целиком и одиночный DB Link (мёртвая касса не должна
# блокировать весь опрос — в оригинале те же 15/8 секунд).
SOURCE_TIMEOUT = int(os.environ.get("UNISIM_SOURCE_TIMEOUT", "60"))
DBLINK_TIMEOUT = int(os.environ.get("UNISIM_DBLINK_TIMEOUT", "8"))

MAIN_SQL = (
    "SELECT c.COD_UNIV, c.DB_LINK, c.SHEMA, c.IN_PROCESS, c.OFF_LINE, "
    "NVL((SELECT u.DENUMIREA FROM tms_univers u WHERE u.COD = c.COD_UNIV), 'Unknown') AS PARENT_NAME "
    "FROM ybmb_dif_cassa c "
    "ORDER BY regexp_substr(c.db_link, '^[[:alpha:]]+'), "
    "to_number(regexp_substr(c.db_link, '[[:digit:]]+')), c.db_link"
)


def _call_worker(auth: Dict[str, str], sql: str, timeout: int) -> Dict[str, Any]:
    """Один запрос в изолированном thick-воркере под кредами источника."""
    req = {"op": "query", "sql": sql, "params": {}, "auth": auth}
    try:
        proc = subprocess.run(
            [sys.executable, _WORKER], input=json.dumps(req),
            capture_output=True, text=True, cwd=_PROJECT_ROOT, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"success": False, "message": f"timeout after {timeout}s"}
    except Exception as e:
        return {"success": False, "message": f"worker spawn failed: {e}"}
    if proc.returncode != 0:
        return {"success": False,
                "message": f"worker exit {proc.returncode}: {(proc.stderr or '')[:300]}"}
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"success": False, "message": f"bad worker output: {(proc.stdout or '')[:200]}"}


def _rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    cols = [c.lower() for c in (result.get("columns") or [])]
    return [dict(zip(cols, row)) for row in (result.get("data") or [])]


def _clean_error(message: str) -> str:
    """Короткий текст Oracle-ошибки без стека (ORA-xxxxx: описание)."""
    msg = (message or "").strip().replace("\n", " ")
    return msg[:300] if msg else "неизвестная ошибка DB Link"


def link_prefix(raw_link: str) -> str:
    """`pos1.world` → `pos1` (домен отбрасывается, как в оригинале)."""
    return (raw_link or "").split(".")[0].strip()


def probe_registers(auth: Dict[str, str], links: List[str]) -> Dict[str, Dict[str, Any]]:
    """Резолвит ServerID по каждому DB Link одним запросом-объединением.

    UNION ALL по всем ссылкам в одном обращении вместо N подключений:
    так опрос источника укладывается в один вызов воркера. Если весь
    объединённый запрос падает (обычно из-за одной мёртвой ссылки),
    ссылки перепроверяются поодиночке.
    """
    out: Dict[str, Dict[str, Any]] = {}
    if not links:
        return out

    parts = [
        f"SELECT '{p}' AS LNK, (SELECT pvalue FROM tms_init_params@{p}.WORLD "
        f"WHERE pname = 'ServerID') AS SRV FROM dual"
        for p in links
    ]
    res = _call_worker(auth, " UNION ALL ".join(parts), SOURCE_TIMEOUT)
    if res.get("success"):
        for row in _rows(res):
            out[row.get("lnk")] = {"server_id": row.get("srv"), "link_error": None}
        for p in links:
            out.setdefault(p, {"server_id": None, "link_error": "DB Link не вернул ServerID"})
        return out

    # Пакет не прошёл — проверяем ссылки по одной, чтобы найти живые.
    for p in links:
        single = _call_worker(
            auth,
            f"SELECT (SELECT pvalue FROM tms_init_params@{p}.WORLD "
            f"WHERE pname = 'ServerID') AS SRV FROM dual",
            DBLINK_TIMEOUT)
        if single.get("success"):
            rows = _rows(single)
            srv = rows[0].get("srv") if rows else None
            out[p] = {"server_id": srv,
                      "link_error": None if srv else "DB Link не вернул ServerID"}
        else:
            out[p] = {"server_id": None, "link_error": _clean_error(single.get("message"))}
    return out


def query_source(source: Dict[str, Any]) -> Dict[str, Any]:
    """Опрашивает один источник. Возвращает список касс с их статусами.

    source: {code, name, db_user, db_password, db_dsn}
    """
    auth = {"user": source.get("db_user"), "password": source.get("db_password"),
            "dsn": source.get("db_dsn")}
    if not all(auth.values()):
        return {"success": False, "error": "Не заданы логин/пароль/DSN источника"}

    main = _call_worker(auth, MAIN_SQL, SOURCE_TIMEOUT)
    if not main.get("success"):
        return {"success": False, "error": _clean_error(main.get("message"))}

    rows = _rows(main)
    prefixes = []
    for r in rows:
        p = link_prefix(r.get("db_link") or "")
        # OFF_LINE=1 — касса штатно выключена, DB Link не дёргаем.
        if p and str(r.get("off_line") or "0").strip() not in ("1",):
            prefixes.append(p)
    probes = probe_registers(auth, sorted(set(prefixes)))

    registers = []
    for r in rows:
        raw_link = (r.get("db_link") or "").strip()
        prefix = link_prefix(raw_link)
        off_line = 1 if str(r.get("off_line") or "0").strip() == "1" else 0
        probe = probes.get(prefix, {})
        server_id = probe.get("server_id")
        link_error = probe.get("link_error")

        if off_line == 1:
            status = "SHUTDOWN"
            reason = "OFF_LINE = 1: касса помечена как остановленная"
        elif server_id is not None and str(server_id).strip() != "":
            status = "ONLINE"
            reason = "DB Link отвечает, ServerID получен"
        else:
            status = "OFFLINE"
            reason = link_error or "ServerID отсутствует"

        registers.append({
            "source_code": source.get("code"), "source_name": source.get("name"),
            "cod_univ": str(r.get("cod_univ") or ""),
            "store_name": r.get("parent_name") or "Unknown",
            "db_link": raw_link, "db_link_prefix": prefix,
            "shema": r.get("shema"), "in_process": r.get("in_process"),
            "off_line": off_line, "server_id": str(server_id) if server_id is not None else None,
            "status": status, "status_reason": reason, "link_error": link_error,
        })

    return {"success": True, "data": {
        "source": {"code": source.get("code"), "name": source.get("name")},
        "registers": registers,
        "total": len(registers),
        "online": sum(1 for x in registers if x["status"] == "ONLINE"),
        "offline": sum(1 for x in registers if x["status"] == "OFFLINE"),
        "shutdown": sum(1 for x in registers if x["status"] == "SHUTDOWN"),
    }}


def test_source(source: Dict[str, Any]) -> Dict[str, Any]:
    """Быстрая проверка соединения с источником (без опроса DB Links)."""
    auth = {"user": source.get("db_user"), "password": source.get("db_password"),
            "dsn": source.get("db_dsn")}
    if not all(auth.values()):
        return {"success": False, "error": "Не заданы логин/пароль/DSN источника"}
    res = _call_worker(
        auth, "SELECT COUNT(*) AS CNT FROM ybmb_dif_cassa", DBLINK_TIMEOUT + 12)
    if not res.get("success"):
        return {"success": False, "error": _clean_error(res.get("message"))}
    rows = _rows(res)
    return {"success": True, "registers": rows[0].get("cnt") if rows else 0}
