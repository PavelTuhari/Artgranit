"""Источники данных модуля netmon: Zabbix JSON-RPC и Telegram Bot API.

Здесь только чтение из внешних систем и приведение к простым словарям.
SQL — в store.py, правила разбора — в rules.py. Секреты не хранятся в коде:
пароль Zabbix берётся из macOS Keychain, токен бота читается на самом
сервере Zabbix по SSH и наружу не выносится.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request

from modules.netmon import rules

ZBX_URL = "http://192.168.0.110/zabbix/api_jsonrpc.php"
ZBX_HOST = "192.168.0.110"
ALERTSCRIPT = "/usr/lib/zabbix/alertscripts/telegram_bot.sh"


def keychain(account: str, service: str) -> str:
    r = subprocess.run(["security", "find-generic-password", "-a", account, "-s", service, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


# ------------------------------------------------------------------ Zabbix

class Zabbix:
    """Минимальный клиент Zabbix 3.4 JSON-RPC (только чтение и host.create)."""

    def __init__(self, url: str = ZBX_URL, user: str = "Admin", password: str | None = None):
        self.url = url
        self.token = None
        pw = password if password is not None else keychain("Admin", "zabbix-web")
        self.token = self._rpc("user.login", {"user": user, "password": pw})

    def _rpc(self, method: str, params):
        body = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        if self.token:
            body["auth"] = self.token
        req = urllib.request.Request(self.url, json.dumps(body).encode(),
                                     {"Content-Type": "application/json-rpc"})
        r = json.load(urllib.request.urlopen(req, timeout=30))
        if "error" in r:
            raise RuntimeError(r["error"].get("data") or r["error"]["message"])
        return r["result"]

    def call(self, method: str, params):
        return self._rpc(method, params)

    def hosts_by_ip(self) -> dict[str, dict]:
        hosts = self.call("host.get", {"output": ["hostid", "host", "status", "available"],
                                       "selectInterfaces": ["ip"]})
        out = {}
        for h in hosts:
            for i in h.get("interfaces", []):
                out[i["ip"]] = {"host": h["host"], "hostid": h["hostid"],
                                "available": h.get("available")}
        return out

    def telegram_targets(self) -> list[dict]:
        """Куда Zabbix шлёт Telegram: media пользователей + тип media."""
        mt = {m["mediatypeid"]: m for m in
              self.call("mediatype.get", {"output": ["mediatypeid", "description", "type",
                                                     "status", "exec_path"]})}
        out = []
        for u in self.call("user.get", {"output": ["userid", "alias"], "selectMedias": "extend"}):
            for m in u.get("medias") or []:
                mid = str(m.get("mediatypeid") or m.get("mediatype") or "")
                info = mt.get(mid, {})
                if "telegram" not in (info.get("description", "") or "").lower():
                    continue
                out.append({
                    "chat_id": m["sendto"],
                    "mediatype": info.get("description"),
                    "mediatype_enabled": info.get("status") == "0",
                    "exec_path": info.get("exec_path"),
                    "zbx_user": u["alias"],
                    # в media Zabbix active: 0 — включено, 1 — выключено
                    "enabled": m.get("active") == "0" and info.get("status") == "0",
                })
        return out

    def alerts(self, days: int = 30, limit: int = 3000) -> list[dict]:
        import time
        rows = self.call("alert.get", {
            "output": ["alertid", "clock", "sendto", "subject", "status", "retries", "error"],
            "time_from": int(time.time()) - days * 86400,
            "sortfield": "clock", "sortorder": "DESC", "limit": limit})
        status_map = {"0": "queued", "1": "sent", "2": "failed", "3": "new"}
        return [{
            "alertid": int(a["alertid"]),
            "chat_id": a["sendto"],
            "clock": int(a["clock"]),
            "subject": a.get("subject") or "",
            "severity": rules.alert_severity(a.get("subject") or ""),
            "host": rules.alert_host(a.get("subject") or ""),
            "status": status_map.get(a.get("status"), "unknown"),
            "retries": int(a.get("retries") or 0),
            "error": a.get("error") or "",
        } for a in rows]


# ------------------------------------------------------------------ Telegram

def telegram_chats(chat_ids: list[str]) -> dict[str, dict]:
    """Названия каналов через Bot API. Токен читается и остаётся на сервере Zabbix.

    Запрос выполняется по SSH на самом контейнере Zabbix: так токен бота не
    попадает ни в репозиторий, ни в логи этой машины.
    """
    if not chat_ids:
        return {}
    pw = keychain("root", "zabbix34-ct")
    if not pw:
        return {}
    ids = " ".join(chat_ids)
    # Команда уходит одной строкой в sh на контейнере: кавычки внутри $() не
    # экранируем — ssh и так передаёт аргумент целиком, лишние \" ломали curl.
    remote = (
        "T=$(grep -oE '[0-9]{8,}:[A-Za-z0-9_-]{30,}' " + ALERTSCRIPT + " | head -1); "
        "[ -z \"$T\" ] && exit 0; "
        "echo BOT $(curl -s --max-time 10 https://api.telegram.org/bot$T/getMe); "
        "for C in " + ids + "; do "
        "echo CHAT $C $(curl -s --max-time 10 https://api.telegram.org/bot$T/getChat?chat_id=$C); "
        "echo CNT $C $(curl -s --max-time 10 https://api.telegram.org/bot$T/getChatMembersCount?chat_id=$C); "
        "done")
    env = dict(os.environ)
    env["SSHPASS"] = pw
    r = subprocess.run(
        ["sshpass", "-e", "ssh", "-o", "HostKeyAlgorithms=+ssh-rsa",
         "-o", "PubkeyAcceptedKeyTypes=+ssh-rsa", "-o", "StrictHostKeyChecking=no",
         "-o", "ConnectTimeout=15", f"root@{ZBX_HOST}", remote],
        capture_output=True, text=True, env=env)
    out: dict[str, dict] = {}
    bot = ""
    for line in r.stdout.splitlines():
        if line.startswith("BOT "):
            try:
                bot = json.loads(line[4:]).get("result", {}).get("username", "")
            except Exception:  # noqa: BLE001
                pass
        elif line.startswith("CHAT "):
            _, cid, payload = line.split(" ", 2)
            try:
                d = json.loads(payload)
            except Exception:  # noqa: BLE001
                continue
            if d.get("ok"):
                res = d["result"]
                out.setdefault(cid, {}).update({
                    "title": res.get("title"), "chat_type": res.get("type"),
                    "note": res.get("description") or ""})
            else:
                out.setdefault(cid, {}).update({"note": f"Telegram: {d.get('description')}"})
        elif line.startswith("CNT "):
            _, cid, payload = line.split(" ", 2)
            try:
                d = json.loads(payload)
            except Exception:  # noqa: BLE001
                continue
            if d.get("ok"):
                out.setdefault(cid, {})["members_count"] = d["result"]
    for cid in out:
        out[cid]["bot_username"] = bot
    return out


def zabbix_overview() -> dict:
    """Всё, что видно в Zabbix: хосты, их доступность, элементы, проблемы.

    Читается напрямую из Zabbix (не из Oracle): это «зеркало» состояния
    мониторинга на текущую секунду, а не снимок из базы модуля.
    """
    z = Zabbix()
    hosts = z.call("host.get", {
        "output": ["hostid", "host", "name", "status", "available", "error"],
        "selectInterfaces": ["ip", "type"], "selectGroups": ["name"],
        "selectParentTemplates": ["host"]})
    items = z.call("item.get", {"output": ["itemid", "hostid", "type", "status", "state"]})
    triggers = z.call("trigger.get", {"output": ["triggerid", "priority", "value", "status"],
                                      "monitored": 1, "filter": {"value": 1},
                                      "only_true": 1, "skipDependent": 1,
                                      "selectHosts": ["hostid"], "expandDescription": 1})

    per_host: dict[str, dict] = {}
    for it in items:
        h = per_host.setdefault(it["hostid"], {"items": 0, "broken": 0, "disabled": 0})
        h["items"] += 1
        if it.get("status") == "1":
            h["disabled"] += 1
        elif it.get("state") == "1":
            h["broken"] += 1
    for t in triggers:
        for h in t.get("hosts", []):
            per_host.setdefault(h["hostid"], {"items": 0, "broken": 0, "disabled": 0}) \
                .setdefault("problems", 0)
            per_host[h["hostid"]]["problems"] = per_host[h["hostid"]].get("problems", 0) + 1

    avail = {"0": "неизвестно", "1": "доступен", "2": "недоступен"}
    rows = []
    for h in hosts:
        st = per_host.get(h["hostid"], {})
        rows.append({
            "hostid": h["hostid"],
            "host": h["host"],
            "name": h.get("name") or h["host"],
            "enabled": h.get("status") == "0",
            "available": avail.get(h.get("available"), "?"),
            "error": (h.get("error") or "")[:160],
            "ip": (h.get("interfaces") or [{}])[0].get("ip", ""),
            "groups": [g["name"] for g in h.get("groups", [])],
            "templates": [t["host"] for t in h.get("parentTemplates", [])],
            "items": st.get("items", 0),
            "items_broken": st.get("broken", 0),
            "items_disabled": st.get("disabled", 0),
            "problems": st.get("problems", 0),
        })
    rows.sort(key=lambda r: (-r["problems"], not r["enabled"], r["host"].lower()))

    sev = {}
    for t in triggers:
        p = int(t.get("priority", 0))
        sev[p] = sev.get(p, 0) + 1
    return {
        "hosts": rows,
        "totals": {
            "hosts": len(rows),
            "enabled": sum(1 for r in rows if r["enabled"]),
            "disabled": sum(1 for r in rows if not r["enabled"]),
            "unavailable": sum(1 for r in rows if r["available"] == "недоступен"),
            "items": sum(r["items"] for r in rows),
            "items_broken": sum(r["items_broken"] for r in rows),
            "problems": len(triggers),
        },
        "problems_by_severity": [
            {"severity": ["Not classified", "Information", "Warning", "Average",
                          "High", "Disaster"][min(max(p, 0), 5)], "count": c}
            for p, c in sorted(sev.items(), reverse=True)],
    }
