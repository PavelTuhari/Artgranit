"""TBControl — сервисы Zabbix unisim-soft.com через mTLS-шлюз (TBC_SERVICES).

Источник `KIND = 'zabbix_svc'` (код `zbx-svc-unisim`). В отличие от источника
`zabbix` (события по триггерам), здесь единица учёта — **хост Zabbix как
сервис**: сервер, БД, веб, почта, сеть. Один проход `sync()`:

    1. apiinfo.version + user.login (Zabbix 3.4: параметр `user`);
    2. host.get — хосты, группы, интерфейсы, шаблоны, доступность агента;
    3. trigger.get value=1 — активные проблемы, группируются по хосту;
    4. upsert в TBC_SERVICES по (SOURCE_CODE, ZBX_HOSTID), пропавшие хосты
       удаляются;
    5. хосты со статусом PROBLEM порождают события `source='zabbix_svc'`
       (corr `svc-<source>-<hostid>`), ушедшие из PROBLEM — закрываются.

Чистые правила (`classify_kind`, `service_status`) не трогают БД и
тестируются без wallet (tests/test_tbcontrol_infra.py).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from models import tbc_mtls

KIND = "zabbix_svc"
SOURCE = "zabbix_svc"
CORR_PREFIX = "svc-"

# priority Zabbix → приоритет TBC (как в ZabbixConnector)
SEV_MAP = {5: "P1", 4: "P2", 3: "P3", 2: "P3", 1: "P4", 0: "P4"}
AVAIL_MAP = {"0": "unknown", "1": "available", "2": "unavailable"}
# service_kind → код сервиса TBC_REF_SERVICES для событий
SERVICE_CODE = {"db": "database", "network": "network", "web": "api", "mail": "api", "server": "api"}

_KIND_RULES = (
    ("db", ("oracle", "mysql", "postgres", "mssql", "database", "db ", " db", "standby")),
    ("mail", ("mail", "smtp", "imap", "zimbra", "postfix", "exim")),
    ("network", ("mikrotik", "router", "switch", "network", "firewall", "vpn", "ubiquiti", "cisco")),
    ("web", ("apache", "nginx", "web", "http", "www", "site", ".md", ".com")),
)


# ---------- чистые правила ----------

def classify_kind(host: str, name: str = "", groups: str = "", templates: str = "") -> str:
    """Тип сервиса по имени хоста, группам и шаблонам Zabbix."""
    text = " ".join(x or "" for x in (host, name, groups, templates)).lower()
    for kind, words in _KIND_RULES:
        if any(w in text for w in words):
            return kind
    return "server"


def service_status(host_status: Any, available: str, worst_priority: Optional[int]) -> Tuple[str, Optional[str]]:
    """(STATUS, WORST_SEVERITY): DISABLED для выключенного хоста,
    PROBLEM при High/Disaster, WARN при любой проблеме или недоступном агенте."""
    if str(host_status) == "1":
        return "DISABLED", None
    sev = SEV_MAP.get(worst_priority) if worst_priority is not None else None
    if worst_priority is not None and worst_priority >= 4:
        return "PROBLEM", sev
    if worst_priority is not None or available == "unavailable":
        return "WARN", sev or "P3"
    return "OK", None


def build_rows(source_code: str, hosts: List[Dict[str, Any]], triggers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Список строк TBC_SERVICES из ответов host.get и trigger.get."""
    by_host: Dict[str, List[Dict[str, Any]]] = {}
    for t in triggers:
        for h in t.get("hosts") or []:
            by_host.setdefault(str(h.get("hostid")), []).append(t)
    rows = []
    for h in hosts:
        hid = str(h.get("hostid"))
        groups = ", ".join(g.get("name", "") for g in (h.get("groups") or []))
        templates = ", ".join(t.get("name", "") for t in (h.get("parentTemplates") or []))
        ifaces = h.get("interfaces") or []
        main = next((i for i in ifaces if str(i.get("main")) == "1"), ifaces[0] if ifaces else {})
        probs = sorted(by_host.get(hid, []), key=lambda t: -int(t.get("priority") or 0))
        worst = int(probs[0].get("priority") or 0) if probs else None
        available = AVAIL_MAP.get(str(h.get("available")), "unknown")
        status, sev = service_status(h.get("status"), available, worst)
        rows.append({
            "source_code": source_code, "zbx_hostid": hid, "host": h.get("host") or hid,
            "name": h.get("name") or h.get("host"), "group_name": groups[:200] or None,
            "service_kind": classify_kind(h.get("host", ""), h.get("name", ""), groups, templates),
            "ip_address": (main.get("ip") or main.get("dns") or None), "available": available,
            "status": status, "worst_severity": sev, "problems_cnt": len(probs),
            "problem_text": (" | ".join(t.get("description", "") for t in probs))[:1000] or None,
            "templates": templates[:500] or None,
        })
    return rows


def wanted_events(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for r in rows:
        if r["status"] != "PROBLEM":
            continue
        corr = f"{CORR_PREFIX}{r['source_code']}-{r['zbx_hostid']}"[:30]
        out[corr] = {"severity": r["worst_severity"] or "P2",
                     "service_code": SERVICE_CODE.get(r["service_kind"], "api"),
                     "problem": f"Сервис [{r['host']}] ({r['service_kind']}): {r['problem_text'] or 'проблема'}"}
    return out


# ---------- Zabbix JSON-RPC через шлюз ----------

class ZabbixMtls:
    def __init__(self, src: Dict[str, Any]):
        self.client = tbc_mtls.MtlsClient(src)
        self.url = self.client.base
        self.user = (src.get("api_user") or "").strip()
        self.password = tbc_mtls.resolve_secret(src.get("api_secret"))
        self.auth: Optional[str] = None
        self.version = ""

    def rpc(self, method: str, params: Any, with_auth: bool = True) -> Any:
        body: Dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        if with_auth and self.auth:
            body["auth"] = self.auth
        r = self.client.request("POST", self.url, json=body,
                                headers={"Content-Type": "application/json-rpc"})
        if r.status_code != 200:
            raise RuntimeError(f"Шлюз ответил HTTP {r.status_code}: {(r.text or '')[:120]}")
        data = r.json()
        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"Zabbix API: {err.get('data') or err.get('message')}")
        return data["result"]

    def connect(self) -> str:
        self.version = self.rpc("apiinfo.version", {}, with_auth=False)
        if not self.user:
            raise RuntimeError("Не задан логин Zabbix (API_USER)")
        try:
            self.auth = self.rpc("user.login", {"user": self.user, "password": self.password}, with_auth=False)
        except RuntimeError:
            self.auth = self.rpc("user.login", {"username": self.user, "password": self.password}, with_auth=False)
        return self.version

    def hosts(self) -> List[Dict[str, Any]]:
        return self.rpc("host.get", {
            "output": ["hostid", "host", "name", "status", "available", "error"],
            "selectGroups": ["name"], "selectInterfaces": ["ip", "dns", "main", "type"],
            "selectParentTemplates": ["name"], "sortfield": "host"})

    def problems(self) -> List[Dict[str, Any]]:
        return self.rpc("trigger.get", {
            "output": ["triggerid", "description", "priority"], "filter": {"value": 1},
            "monitored": True, "active": True, "expandDescription": True,
            "selectHosts": ["hostid", "host"], "limit": 1000})


# ---------- публичный API модуля ----------

def test_source(src: Dict[str, Any]) -> Dict[str, Any]:
    """Проверка: шлюз /health + apiinfo.version + login."""
    try:
        z = ZabbixMtls(src)
        health = z.client.health()
        if not health["ok"]:
            return {"success": False, "error": f"Шлюз /health: HTTP {health['status_code']}"}
        ver = z.connect()
        return {"success": True, "version": ver, "gateway": "OK",
                "insecure_tls": z.client.insecure, "hosts": len(z.hosts())}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


def sync_source(src: Dict[str, Any]) -> Dict[str, Any]:
    from models.database import DatabaseModel
    code = src["code"]
    try:
        z = ZabbixMtls(src)
        z.connect()
        rows = build_rows(code, z.hosts(), z.problems())
    except Exception as e:
        tbc_mtls.mark_source(code, False, str(e))
        return {"success": False, "source_code": code, "error": str(e)[:300]}
    try:
        with DatabaseModel() as db:
            seen = []
            for r in rows:
                seen.append(r["zbx_hostid"])
                upd = db.execute_query(
                    "UPDATE TBC_SERVICES SET HOST=:host, NAME=:name, GROUP_NAME=:group_name, "
                    "SERVICE_KIND=:service_kind, IP_ADDRESS=:ip_address, AVAILABLE=:available, "
                    "STATUS=:status, WORST_SEVERITY=:worst_severity, PROBLEMS_CNT=:problems_cnt, "
                    "PROBLEM_TEXT=:problem_text, TEMPLATES=:templates, CHECKED_AT=SYSTIMESTAMP "
                    "WHERE SOURCE_CODE=:source_code AND ZBX_HOSTID=:zbx_hostid", r)
                if not upd.get("rowcount"):
                    db.execute_query(
                        "INSERT INTO TBC_SERVICES (SOURCE_CODE, ZBX_HOSTID, HOST, NAME, GROUP_NAME, "
                        "SERVICE_KIND, IP_ADDRESS, AVAILABLE, STATUS, WORST_SEVERITY, PROBLEMS_CNT, "
                        "PROBLEM_TEXT, TEMPLATES) VALUES (:source_code, :zbx_hostid, :host, :name, "
                        ":group_name, :service_kind, :ip_address, :available, :status, :worst_severity, "
                        ":problems_cnt, :problem_text, :templates)", r)
            if seen:
                binds = {f"h{i}": h for i, h in enumerate(seen)}
                db.execute_query(
                    "DELETE FROM TBC_SERVICES WHERE SOURCE_CODE = :src AND ZBX_HOSTID NOT IN ("
                    + ", ".join(f":{k}" for k in binds) + ")", {"src": code, **binds})
            created, resolved = tbc_mtls.sync_events(db, SOURCE, f"{CORR_PREFIX}{code}-", wanted_events(rows))
            tbc_mtls.audit(db, "sync", "service",
                           f"Zabbix-сервисы {code}: хостов {len(rows)}, событий +{created}/-{resolved}")
            db.connection.commit()
        tbc_mtls.mark_source(code, True, "TLS без проверки сервера" if z.client.insecure else None)
        problems = sum(1 for r in rows if r["status"] == "PROBLEM")
        return {"success": True, "source_code": code, "hosts": len(rows), "problems": problems,
                "events_created": created, "events_resolved": resolved, "version": z.version}
    except Exception as e:
        tbc_mtls.mark_source(code, False, str(e))
        return {"success": False, "source_code": code, "error": str(e)[:300]}


def sync_all(source_code: Optional[str] = None) -> Dict[str, Any]:
    """Опрос всех включённых источников zabbix_svc (или одного по коду)."""
    try:
        sources = tbc_mtls.sources_of_kind(KIND, source_code)
    except Exception as e:
        return {"success": False, "error": str(e)}
    if not sources:
        return {"success": False, "error": "Нет включённых источников zabbix_svc"}
    results = [sync_source(s) for s in sources]
    return {"success": any(r["success"] for r in results), "data": results,
            "error": None if any(r["success"] for r in results) else "; ".join(r.get("error", "") for r in results)}


def get_services(source_code: Optional[str] = None, status: Optional[str] = None,
                 kind: Optional[str] = None) -> Dict[str, Any]:
    from models.database import DatabaseModel
    try:
        with DatabaseModel() as db:
            sql = "SELECT * FROM TBC_SERVICES WHERE 1=1"
            params: Dict[str, Any] = {}
            if source_code:
                sql += " AND SOURCE_CODE = :src"; params["src"] = source_code
            if status:
                sql += " AND STATUS = :st"; params["st"] = status
            if kind:
                sql += " AND SERVICE_KIND = :k"; params["k"] = kind
            sql += " ORDER BY CASE STATUS WHEN 'PROBLEM' THEN 0 WHEN 'WARN' THEN 1 WHEN 'OK' THEN 2 ELSE 3 END, HOST"
            data = tbc_mtls.rows_to_dicts(db.execute_query(sql, params or None))
            stats = tbc_mtls.rows_to_dicts(db.execute_query("SELECT * FROM V_TBC_SERVICES_STATS"))
            by_kind = tbc_mtls.rows_to_dicts(db.execute_query("SELECT * FROM V_TBC_SERVICES_BY_KIND ORDER BY SERVICE_KIND"))
            sources = tbc_mtls.rows_to_dicts(db.execute_query(
                "SELECT CODE, NAME, ENABLED, LAST_SYNC_AT, LAST_STATUS, LAST_ERROR FROM TBC_SOURCES "
                "WHERE KIND = :k ORDER BY SORT_ORDER", {"k": KIND}))
        return {"success": True, "data": data, "total": len(data), "stats": stats[0] if stats else {},
                "by_kind": by_kind, "sources": sources}
    except Exception as e:
        return {"success": False, "error": str(e)}


def dossier_section(db, service_id: int) -> Tuple[str, Optional[str], str]:
    """(title, severity, markdown) для AI-досье типа 'service'."""
    rows = tbc_mtls.rows_to_dicts(db.execute_query("SELECT * FROM TBC_SERVICES WHERE ID = :id", {"id": service_id}))
    if not rows:
        raise ValueError("Сервис не найден")
    s = rows[0]
    md = [f"\n## Сервис Zabbix {s['host']} ({s.get('service_kind')})\n",
          f"- **Источник:** {s['source_code']} · hostid {s['zbx_hostid']} · IP {s.get('ip_address') or '—'}\n"
          f"- **Статус:** {s['status']} · агент: {s.get('available')} · худший приоритет: {s.get('worst_severity') or '—'}\n"
          f"- **Группы:** {s.get('group_name') or '—'} · шаблоны: {s.get('templates') or '—'}\n"
          f"- **Проверено:** {s.get('checked_at')}\n"]
    if s.get("problem_text"):
        md.append("\n### Активные проблемы\n")
        md.extend(f"- {p.strip()}\n" for p in str(s["problem_text"]).split("|"))
    return f"Сервис {s['host']}: {s['status']}", s.get("worst_severity"), "".join(md)
