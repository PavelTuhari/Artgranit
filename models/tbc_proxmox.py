"""TBControl — Proxmox VE 4.4 (PROXMOX3) через mTLS-шлюз (TBC_PVE_OBJECTS).

Источник `KIND = 'proxmox'` (код `pve-proxmox3`), `API_URL` указывает на
префикс шлюза `https://192.168.0.148:8443/proxmox` — nginx отдаёт его как
`https://192.168.0.149:8006/api2/json/` (проверено 02.09.2026: `/proxmox/access/ticket`
→ 200, `/proxmox/api2/json/...` → 401 «No ticket»). Поэтому пути строятся от
API_URL напрямую; если в API_URL уже есть `/api2/json` — не дублируется.
Логин — PVE-тикет (`/access/ticket`, `root@pam` + пароль из API_SECRET или
ссылка `keychain:<svc>/<acct>`), дальше cookie `PVEAuthCookie`.

Один проход `sync()` собирает ноды, VM (qemu), контейнеры (lxc) и
хранилища, считает HEALTH (OK/WARN/CRIT) по чистому правилу `pve_health`,
делает upsert в TBC_PVE_OBJECTS по (SOURCE_CODE, OBJ_TYPE, OBJ_ID) и
синхронизирует события `source='proxmox'` (corr `pve-<type>-<id>`):
нода offline → P1, объект CRIT → P2. Остановленная VM событием не является —
на гипервизоре половина машин выключена намеренно.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from models import tbc_mtls

KIND = "proxmox"
SOURCE = "proxmox"
CORR_PREFIX = "pve-"
SERVICE_CODE = {"node": "api", "qemu": "api", "lxc": "api", "storage": "database"}


# ---------- чистые правила ----------

def pct(used: Any, total: Any) -> Optional[float]:
    try:
        used, total = float(used or 0), float(total or 0)
    except (TypeError, ValueError):
        return None
    return round(used * 100.0 / total, 2) if total > 0 else None


def pve_health(obj_type: str, status: str, cpu_pct: Optional[float], mem_pct: Optional[float],
               disk_pct: Optional[float]) -> Tuple[str, str]:
    """(HEALTH, HEALTH_REASON). Пороги: диск 85/95 %, CPU 75/90 %, RAM 90/97 %."""
    level, reasons = "OK", []

    def bump(lvl: str, why: str):
        nonlocal level
        reasons.append(why)
        if lvl == "CRIT":
            level = "CRIT"
        elif level == "OK":
            level = "WARN"

    if obj_type == "node" and status != "online":
        bump("CRIT", f"нода {status}")
    if obj_type == "storage" and status == "inactive":
        bump("WARN", "хранилище неактивно")
    active = status in ("online", "running", "active", "available", "unknown")
    if disk_pct is not None and (obj_type == "storage" or active):
        if disk_pct >= 95:
            bump("CRIT", f"диск заполнен на {disk_pct:.0f}%")
        elif disk_pct >= 85:
            bump("WARN", f"диск заполнен на {disk_pct:.0f}%")
    if active and obj_type != "storage":
        if cpu_pct is not None:
            if cpu_pct >= 90:
                bump("CRIT", f"CPU {cpu_pct:.0f}%")
            elif cpu_pct >= 75:
                bump("WARN", f"CPU {cpu_pct:.0f}%")
        if mem_pct is not None:
            if mem_pct >= 97:
                bump("CRIT", f"RAM {mem_pct:.0f}%")
            elif mem_pct >= 90:
                bump("WARN", f"RAM {mem_pct:.0f}%")
    return level, ("; ".join(reasons) or "показатели в норме")[:500]


def build_row(source_code: str, obj_type: str, node: str, item: Dict[str, Any],
              pve_version: Optional[str] = None) -> Dict[str, Any]:
    """Строка TBC_PVE_OBJECTS из элемента ответа API."""
    if obj_type == "node":
        obj_id, name = item.get("node") or node, item.get("node") or node
        # PVE 4.4 в /nodes не отдаёт status — живая нода узнаётся по uptime
        status = item.get("status") or ("online" if item.get("uptime") else "unknown")
    elif obj_type == "storage":
        obj_id = name = item.get("storage") or "?"
        status = "disabled" if str(item.get("enabled", "1")) == "0" else \
            ("active" if str(item.get("active", "")) == "1" else ("inactive" if "active" in item else "unknown"))
    else:
        obj_id = str(item.get("vmid") or "?")
        name = item.get("name") or obj_id
        status = item.get("status") or "unknown"
    mem_used, mem_max = item.get("mem"), item.get("maxmem")
    disk_used, disk_max = (item.get("used"), item.get("total")) if obj_type == "storage" \
        else (item.get("disk"), item.get("maxdisk"))
    cpu = item.get("cpu")
    cpu_pct = round(float(cpu) * 100.0, 2) if cpu is not None and str(cpu) != "" else None
    if obj_type == "storage":
        cpu_pct = None
    mem_pct, disk_pct = pct(mem_used, mem_max), pct(disk_used, disk_max)
    health, reason = pve_health(obj_type, status, cpu_pct, mem_pct, disk_pct)
    uptime = item.get("uptime")
    extra = []
    if str(item.get("template", "0")) == "1":
        extra.append("шаблон")
    if obj_type == "storage":
        extra.append(f"{item.get('type') or ''} {item.get('content') or ''}".strip())
    if obj_type == "node" and item.get("loadavg"):
        extra.append("load " + "/".join(str(x) for x in item["loadavg"]))
    return {
        "source_code": source_code, "obj_type": obj_type, "obj_id": str(obj_id)[:60], "name": str(name)[:200],
        "node_name": node, "status": str(status)[:20], "health": health, "health_reason": reason,
        "cpu_pct": cpu_pct, "mem_pct": mem_pct,
        "mem_used_mb": round(float(mem_used) / 1048576, 0) if mem_used else None,
        "mem_max_mb": round(float(mem_max) / 1048576, 0) if mem_max else None,
        "disk_pct": disk_pct,
        "disk_used_gb": round(float(disk_used) / 1073741824, 2) if disk_used else None,
        "disk_max_gb": round(float(disk_max) / 1073741824, 2) if disk_max else None,
        "uptime_days": round(float(uptime) / 86400, 1) if uptime else None,
        "pve_version": (pve_version or None) if obj_type == "node" else None,
        "extra": ("; ".join(x for x in extra if x))[:1000] or None,
    }


def wanted_events(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for r in rows:
        if r["health"] != "CRIT":
            continue
        corr = f"{CORR_PREFIX}{r['obj_type']}-{r['obj_id']}"[:30]
        sev = "P1" if r["obj_type"] == "node" and r["status"] != "online" else "P2"
        out[corr] = {"severity": sev, "service_code": SERVICE_CODE.get(r["obj_type"], "api"),
                     "problem": f"Proxmox [{r['obj_type']} {r['name']}] на {r['node_name']}: {r['health_reason']}"}
    return out


# ---------- PVE API через шлюз ----------

class ProxmoxMtls:
    def __init__(self, src: Dict[str, Any]):
        self.client = tbc_mtls.MtlsClient(src)
        self.api = self.client.base  # шлюз уже указывает на /api2/json
        self.user = (src.get("api_user") or "root@pam").strip()
        self.password = tbc_mtls.resolve_secret(src.get("api_secret"))
        self.csrf: Optional[str] = None

    def _check(self, r) -> Any:
        if r.status_code == 401:
            raise RuntimeError("Proxmox: неверный логин/пароль (401)")
        if r.status_code != 200:
            raise RuntimeError(f"Proxmox HTTP {r.status_code}: {(r.text or '')[:120]}")
        return r.json().get("data")

    def login(self) -> None:
        r = self.client.request("POST", self.api + "/access/ticket",
                                data={"username": self.user, "password": self.password})
        data = self._check(r) or {}
        ticket = data.get("ticket")
        if not ticket:
            raise RuntimeError("Proxmox: тикет не выдан")
        self.client.session.cookies.set("PVEAuthCookie", ticket)
        self.csrf = data.get("CSRFPreventionToken")

    def get(self, path: str) -> Any:
        return self._check(self.client.request("GET", self.api + path))

    def version(self) -> str:
        v = self.get("/version") or {}
        return f"{v.get('version', '?')}-{v.get('release', '?')}"

    def collect(self, source_code: str) -> List[Dict[str, Any]]:
        ver = self.version()
        rows: List[Dict[str, Any]] = []
        for n in self.get("/nodes") or []:
            node = n.get("node")
            item = dict(n)
            online = n.get("status") == "online" or (n.get("status") is None and bool(n.get("uptime")))
            if online:
                try:
                    st = self.get(f"/nodes/{node}/status") or {}
                    item.update({"cpu": st.get("cpu", n.get("cpu")), "loadavg": st.get("loadavg"),
                                 "mem": (st.get("memory") or {}).get("used", n.get("mem")),
                                 "maxmem": (st.get("memory") or {}).get("total", n.get("maxmem")),
                                 "disk": (st.get("rootfs") or {}).get("used", n.get("disk")),
                                 "maxdisk": (st.get("rootfs") or {}).get("total", n.get("maxdisk")),
                                 "uptime": st.get("uptime", n.get("uptime"))})
                    ver = st.get("pveversion") or ver
                except Exception:
                    pass
            rows.append(build_row(source_code, "node", node, item, ver))
            if not online:
                continue
            for kind in ("qemu", "lxc"):
                try:
                    for vm in self.get(f"/nodes/{node}/{kind}") or []:
                        rows.append(build_row(source_code, kind, node, vm))
                except Exception as e:
                    rows.append(build_row(source_code, kind, node, {"vmid": f"{kind}-error", "name": str(e)[:100],
                                                                    "status": "unknown"}))
            for stg in self.get(f"/nodes/{node}/storage") or []:
                rows.append(build_row(source_code, "storage", node, stg))
        return rows


# ---------- публичный API модуля ----------

def test_source(src: Dict[str, Any]) -> Dict[str, Any]:
    try:
        p = ProxmoxMtls(src)
        health = p.client.health()
        if not health["ok"]:
            return {"success": False, "error": f"Шлюз /health: HTTP {health['status_code']}"}
        p.login()
        nodes = p.get("/nodes") or []
        return {"success": True, "version": p.version(), "gateway": "OK", "nodes": len(nodes),
                "insecure_tls": p.client.insecure}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


_COLS = ["source_code", "obj_type", "obj_id", "name", "node_name", "status", "health", "health_reason",
         "cpu_pct", "mem_pct", "mem_used_mb", "mem_max_mb", "disk_pct", "disk_used_gb", "disk_max_gb",
         "uptime_days", "pve_version", "extra"]


def sync_source(src: Dict[str, Any]) -> Dict[str, Any]:
    from models.database import DatabaseModel
    code = src["code"]
    try:
        p = ProxmoxMtls(src)
        p.login()
        rows = p.collect(code)
    except Exception as e:
        tbc_mtls.mark_source(code, False, str(e))
        return {"success": False, "source_code": code, "error": str(e)[:300]}
    try:
        with DatabaseModel() as db:
            keys = []
            for r in rows:
                keys.append((r["obj_type"], r["obj_id"]))
                upd = db.execute_query(
                    "UPDATE TBC_PVE_OBJECTS SET " + ", ".join(f"{c.upper()}=:{c}" for c in _COLS[3:])
                    + ", CHECKED_AT=SYSTIMESTAMP WHERE SOURCE_CODE=:source_code AND OBJ_TYPE=:obj_type "
                    "AND OBJ_ID=:obj_id", r)
                if not upd.get("rowcount"):
                    db.execute_query(
                        "INSERT INTO TBC_PVE_OBJECTS (" + ", ".join(c.upper() for c in _COLS) + ") VALUES ("
                        + ", ".join(f":{c}" for c in _COLS) + ")", r)
            existing = tbc_mtls.rows_to_dicts(db.execute_query(
                "SELECT ID, OBJ_TYPE, OBJ_ID FROM TBC_PVE_OBJECTS WHERE SOURCE_CODE = :s", {"s": code}))
            for e in existing:
                if (e["obj_type"], e["obj_id"]) not in keys:
                    db.execute_query("DELETE FROM TBC_PVE_OBJECTS WHERE ID = :id", {"id": e["id"]})
            created, resolved = tbc_mtls.sync_events(db, SOURCE, CORR_PREFIX, wanted_events(rows))
            tbc_mtls.audit(db, "sync", "pve", f"Proxmox {code}: объектов {len(rows)}, событий +{created}/-{resolved}")
            db.connection.commit()
        tbc_mtls.mark_source(code, True, "TLS без проверки сервера" if p.client.insecure else None)
        return {"success": True, "source_code": code, "objects": len(rows),
                "crit": sum(1 for r in rows if r["health"] == "CRIT"),
                "warn": sum(1 for r in rows if r["health"] == "WARN"),
                "events_created": created, "events_resolved": resolved}
    except Exception as e:
        tbc_mtls.mark_source(code, False, str(e))
        return {"success": False, "source_code": code, "error": str(e)[:300]}


def sync_all(source_code: Optional[str] = None) -> Dict[str, Any]:
    try:
        sources = tbc_mtls.sources_of_kind(KIND, source_code)
    except Exception as e:
        return {"success": False, "error": str(e)}
    if not sources:
        return {"success": False, "error": "Нет включённых источников proxmox"}
    results = [sync_source(s) for s in sources]
    ok = any(r["success"] for r in results)
    return {"success": ok, "data": results,
            "error": None if ok else "; ".join(r.get("error", "") for r in results)}


def get_objects(source_code: Optional[str] = None, obj_type: Optional[str] = None,
                health: Optional[str] = None) -> Dict[str, Any]:
    from models.database import DatabaseModel
    try:
        with DatabaseModel() as db:
            sql = "SELECT * FROM TBC_PVE_OBJECTS WHERE 1=1"
            params: Dict[str, Any] = {}
            if source_code:
                sql += " AND SOURCE_CODE = :src"; params["src"] = source_code
            if obj_type:
                sql += " AND OBJ_TYPE = :t"; params["t"] = obj_type
            if health:
                sql += " AND HEALTH = :h"; params["h"] = health
            sql += (" ORDER BY NODE_NAME, CASE OBJ_TYPE WHEN 'node' THEN 0 WHEN 'storage' THEN 1 "
                    "WHEN 'lxc' THEN 2 ELSE 3 END, CASE HEALTH WHEN 'CRIT' THEN 0 WHEN 'WARN' THEN 1 ELSE 2 END, "
                    "CASE STATUS WHEN 'running' THEN 0 ELSE 1 END, NAME")
            data = tbc_mtls.rows_to_dicts(db.execute_query(sql, params or None))
            stats = tbc_mtls.rows_to_dicts(db.execute_query("SELECT * FROM V_TBC_PVE_STATS"))
            sources = tbc_mtls.rows_to_dicts(db.execute_query(
                "SELECT CODE, NAME, ENABLED, LAST_SYNC_AT, LAST_STATUS, LAST_ERROR FROM TBC_SOURCES "
                "WHERE KIND = :k ORDER BY SORT_ORDER", {"k": KIND}))
        return {"success": True, "data": data, "total": len(data), "stats": stats[0] if stats else {},
                "sources": sources}
    except Exception as e:
        return {"success": False, "error": str(e)}


def dossier_section(db, obj_id: int) -> Tuple[str, Optional[str], str]:
    """(title, severity, markdown) для AI-досье типа 'pve'."""
    rows = tbc_mtls.rows_to_dicts(db.execute_query("SELECT * FROM TBC_PVE_OBJECTS WHERE ID = :id", {"id": obj_id}))
    if not rows:
        raise ValueError("Объект Proxmox не найден")
    o = rows[0]
    md = [f"\n## Proxmox {o['obj_type']} {o['name']} (нода {o.get('node_name')})\n",
          f"- **Источник:** {o['source_code']} · id {o['obj_id']} · PVE {o.get('pve_version') or '—'}\n"
          f"- **Состояние:** {o['status']} · HEALTH **{o['health']}** — {o.get('health_reason')}\n"
          f"- **CPU:** {o.get('cpu_pct')}% · RAM {o.get('mem_pct')}% ({o.get('mem_used_mb')}/{o.get('mem_max_mb')} MB) · "
          f"диск {o.get('disk_pct')}% ({o.get('disk_used_gb')}/{o.get('disk_max_gb')} GB)\n"
          f"- **Uptime:** {o.get('uptime_days')} дн · {o.get('extra') or ''} · проверено {o.get('checked_at')}\n"]
    sev = "P1" if o["obj_type"] == "node" and o["status"] != "online" else ("P2" if o["health"] == "CRIT" else "P3")
    return f"Proxmox {o['obj_type']} {o['name']}: {o['health']}", sev, "".join(md)
