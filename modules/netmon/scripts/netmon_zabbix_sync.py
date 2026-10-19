#!/usr/bin/env python3
"""Постановка найденных устройств офиса на мониторинг Zabbix.

    python modules/netmon/scripts/netmon_zabbix_sync.py --scan            # только скан, ничего не менять
    python modules/netmon/scripts/netmon_zabbix_sync.py --apply           # завести недостающие хосты
    python modules/netmon/scripts/netmon_zabbix_sync.py --apply --dry-run # показать план

Сканирует 192.168.0.0/24 (нужен туннель VPN93), классифицирует устройства по
TTL, открытым портам и баннерам, сверяет с Zabbix и заводит недостающие в
группу «Office Auto-Discovered» с шаблоном ICMP Ping (агент есть не везде).
Ничего не удаляет и не меняет у существующих хостов.

Пароль Zabbix: security find-generic-password -a Admin -s zabbix-web -w
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import socket
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from modules.netmon import rules  # noqa: E402

ZBX_URL = "http://192.168.0.110/zabbix/api_jsonrpc.php"
SUBNET = "192.168.0."
GROUP_NAME = "Office Auto-Discovered"
TPL_ICMP = "Template ICMP Ping"
PORTS = rules.PROBE_PORTS


# ----------------------------------------------------------------- Zabbix API

class Zabbix:
    def __init__(self, url: str, user: str, password: str):
        self.url = url
        self.token = self._rpc("user.login", {"user": user, "password": password})

    def _rpc(self, method: str, params, auth: str | None = None):
        body = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        if auth or getattr(self, "token", None):
            body["auth"] = auth or self.token
        req = urllib.request.Request(self.url, json.dumps(body).encode(),
                                     {"Content-Type": "application/json-rpc"})
        r = json.load(urllib.request.urlopen(req, timeout=30))
        if "error" in r:
            raise RuntimeError(r["error"].get("data") or r["error"]["message"])
        return r["result"]

    def call(self, method, params):
        return self._rpc(method, params)


# ----------------------------------------------------------------- скан сети

def ping(ip: str):
    r = subprocess.run(["ping", "-c1", "-W700", ip], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    ttl = next((int(t[4:]) for t in r.stdout.split() if t.startswith("ttl=")), None)
    return {"ip": ip, "ttl": ttl}


def open_ports(ip: str) -> list[int]:
    out = []
    for p in PORTS:
        s = socket.socket()
        s.settimeout(0.4)
        try:
            s.connect((ip, p))
            out.append(p)
        except Exception:
            pass
        finally:
            s.close()
    return out


def http_title(ip: str, port: int, tls: bool) -> tuple[str, str]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = f"{'https' if tls else 'http'}://{ip}:{port}/"
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "netmon/1.0"}),
            timeout=3, context=ctx)
        body = r.read(4000).decode("utf-8", "ignore")
        m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
        return (m.group(1).strip()[:60] if m else ""), r.headers.get("Server", "")[:40]
    except Exception:
        return "", ""


def ssh_banner(ip: str) -> str:
    try:
        s = socket.socket()
        s.settimeout(2.5)
        s.connect((ip, 22))
        d = s.recv(120).decode("utf-8", "ignore").strip()
        s.close()
        return d[:60]
    except Exception:
        return ""


def scan() -> list[dict]:
    with cf.ThreadPoolExecutor(64) as ex:
        alive = [h for h in ex.map(ping, [SUBNET + str(i) for i in range(1, 255)]) if h]

    def enrich(h):
        h["ports"] = open_ports(h["ip"])
        title = server = ""
        for port, tls in ((443, True), (80, False), (8006, True), (8080, False),
                          (8001, False), (8000, False)):
            if port in h["ports"]:
                title, server = http_title(h["ip"], port, tls)
                if title or server:
                    break
        h["title"], h["server"] = title, server
        h["ssh"] = ssh_banner(h["ip"]) if 22 in h["ports"] else ""
        try:
            h["dns"] = socket.gethostbyaddr(h["ip"])[0]
        except Exception:
            h["dns"] = ""
        h["kind"] = rules.classify(h["ttl"], h["ports"], h["title"], h["server"])
        h["criticality"] = rules.criticality(h["kind"], h["ports"])
        return h

    with cf.ThreadPoolExecutor(24) as ex:
        return sorted(ex.map(enrich, alive), key=lambda x: rules.ip_key(x["ip"]))


# ----------------------------------------------------------------- сверка и заведение

def zabbix_ips(z: Zabbix) -> dict[str, str]:
    hosts = z.call("host.get", {"output": ["hostid", "host"], "selectInterfaces": ["ip"]})
    return {i["ip"]: h["host"] for h in hosts for i in h.get("interfaces", [])}


def ensure_group(z: Zabbix) -> str:
    g = z.call("hostgroup.get", {"filter": {"name": GROUP_NAME}, "output": ["groupid"]})
    if g:
        return g[0]["groupid"]
    return z.call("hostgroup.create", {"name": GROUP_NAME})["groupids"][0]


def add_host(z: Zabbix, dev: dict, groupid: str, tplid: str) -> str:
    name = rules.host_name(dev["ip"], dev["kind"], dev.get("dns", ""), dev.get("title", ""))
    return z.call("host.create", {
        "host": name,
        "name": f"{name} ({dev['kind']})",
        "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": dev["ip"], "dns": "", "port": "10050"}],
        "groups": [{"groupid": groupid}],
        "templates": [{"templateid": tplid}],
        "inventory_mode": 0,
        "description": rules.host_description(dev),
    })["hostids"][0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="только скан, Zabbix не трогаем")
    ap.add_argument("--apply", action="store_true", help="завести недостающие хосты")
    ap.add_argument("--dry-run", action="store_true", help="показать план без изменений")
    ap.add_argument("--json", help="сохранить результат скана в файл")
    a = ap.parse_args()

    print(f"Сканирую {SUBNET}0/24 …")
    devices = scan()
    print(f"живых устройств: {len(devices)}")

    if a.json:
        Path(a.json).write_text(json.dumps(devices, ensure_ascii=False, indent=1), encoding="utf-8")

    if a.scan and not a.apply:
        for d in devices:
            print(f"  {d['ip']:<15} {d['kind']:<44} {d.get('title') or d.get('ssh') or ''}")
        return

    pw = subprocess.run(["security", "find-generic-password", "-a", "Admin", "-s", "zabbix-web", "-w"],
                        capture_output=True, text=True, check=True).stdout.strip()
    z = Zabbix(ZBX_URL, "Admin", pw)
    known = zabbix_ips(z)
    missing = [d for d in devices if d["ip"] not in known]
    print(f"в Zabbix уже есть: {len(devices) - len(missing)}; добавить: {len(missing)}")

    if a.dry_run:
        for d in missing:
            print(f"  + {d['ip']:<15} {rules.host_name(d['ip'], d['kind'], d.get('dns',''), d.get('title',''))}")
        return

    groupid = ensure_group(z)
    tplid = z.call("template.get", {"filter": {"host": TPL_ICMP}, "output": ["templateid"]})[0]["templateid"]
    ok = err = 0
    for d in missing:
        try:
            add_host(z, d, groupid, tplid)
            ok += 1
            print(f"  + {d['ip']:<15} {d['kind']}")
        except Exception as e:  # noqa: BLE001
            err += 1
            print(f"  ! {d['ip']:<15} {str(e)[:90]}")
    print(f"заведено: {ok}, ошибок: {err}")


if __name__ == "__main__":
    main()
