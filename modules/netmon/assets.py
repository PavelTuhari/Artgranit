"""Домены, серверы в стойке и перерасход электроэнергии.

Три вещи, которых не видно в обычном мониторинге, но которые стоят денег:
домен может молча истечь, сервер в стойке — остаться без описания и
инструкции, а рабочие станции — жечь электричество круглосуточно.

Данные о доменах берутся из реестров (whois/RDAP), о простое машин —
из истории ICMP в Zabbix. SQL — в store.py, здесь только сбор и расчёт.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from datetime import date, datetime

# ------------------------------------------------------------------ домены

DOMAINS = [
    {"name": "una.md", "role": "основной домен компании, DNS ns1.una.md",
     "owner": "UNISIM-SOFT S.R.L.", "whois": "whois.nic.md"},
    {"name": "unisim-soft.com", "role": "корпоративный сайт и почта support@",
     "owner": "UNISIM-SOFT S.R.L.", "whois": "rdap"},
    {"name": "erp1.eu", "role": "почта support_unamd@erp1.eu, рассылка отчётов OTRS",
     "owner": "UNISIM-SOFT S.R.L.", "whois": "whois.eu"},
    {"name": "eminescu.md", "role": "портал nufarul.eminescu.md (боевой контур)",
     "owner": "UNISIM-SOFT S.R.L.", "whois": "whois.nic.md"},
    {"name": "autogara.md", "role": "сайт автовокзала, продажа билетов",
     "owner": "—", "whois": "whois.nic.md"},
]


def _run(cmd: list[str], timeout: int = 25) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:  # noqa: BLE001
        return ""


def _rdap(domain: str) -> dict:
    """Для .com реестр Verisign отдаёт даты в RDAP — точнее и стабильнее whois."""
    url = f"https://rdap.verisign.com/com/v1/domain/{domain}"
    try:
        d = json.load(urllib.request.urlopen(url, timeout=20))
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for e in d.get("events", []):
        if e.get("eventAction") == "registration":
            out["registered"] = (e.get("eventDate") or "")[:10]
        if e.get("eventAction") == "expiration":
            out["expires"] = (e.get("eventDate") or "")[:10]
    for x in d.get("entities", []):
        if "registrar" in (x.get("roles") or []):
            v = x.get("vcardArray", [None, []])[1]
            names = [i[3] for i in v if i and i[0] == "fn"]
            if names:
                out["registrar"] = names[0]
    out["status"] = ", ".join(d.get("status", []))[:200]
    return out


def _whois(domain: str, server: str) -> dict:
    txt = _run(["whois", "-h", server, domain])
    out = {}
    for line in txt.splitlines():
        m = re.match(r"\s*Registered on:\s*(\S+)", line, re.I)
        if m:
            out["registered"] = m.group(1)
        m = re.match(r"\s*Expires on:\s*(\S+)", line, re.I)
        if m:
            out["expires"] = m.group(1)
        m = re.match(r"\s*Registrant:\s*(.+)", line, re.I)
        if m:
            out["registrant"] = m.group(1).strip()
        m = re.match(r"\s*Name:\s*(.+)", line, re.I)
        if m and "registrar" not in out:
            out["registrar"] = m.group(1).strip()
        m = re.match(r"\s*NameServer:\s*(\S+)", line, re.I)
        if m:
            out.setdefault("ns", []).append(m.group(1))
    if isinstance(out.get("ns"), list):
        out["ns"] = ", ".join(out["ns"][:4])
    return out


def days_left(expires: str) -> int | None:
    """Сколько дней осталось до истечения регистрации."""
    if not expires:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%b-%Y"):
        try:
            return (datetime.strptime(expires[:10], fmt).date() - date.today()).days
        except ValueError:
            continue
    return None


def domain_level(days: int | None) -> str:
    """Насколько срочно платить за домен."""
    if days is None:
        return "unknown"
    if days <= 30:
        return "critical"
    if days <= 90:
        return "warning"
    if days <= 180:
        return "notice"
    return "ok"


def check_domains() -> list[dict]:
    out = []
    for d in DOMAINS:
        info = _rdap(d["name"]) if d["whois"] == "rdap" else _whois(d["name"], d["whois"])
        left = days_left(info.get("expires", ""))
        out.append({
            "domain": d["name"], "role": d["role"],
            "owner": info.get("registrant") or d["owner"],
            "registrar": info.get("registrar", ""),
            "registered": info.get("registered", ""),
            "expires": info.get("expires", ""),
            "days_left": left,
            "level": domain_level(left),
            "ns": info.get("ns", ""),
            "status": info.get("status", ""),
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
    return out


# ------------------------------------------------------------------ перерасход энергии

# Оценка потребления офисного рабочего места: системный блок в простое
# 60–90 Вт плюс периферия. Значение осознанно консервативное.
IDLE_WATT = 75
# Рабочее время: 10 часов × 5 дней. Остальное — впустую.
WORK_HOURS_PER_WEEK = 50
HOURS_PER_WEEK = 168
# Тариф для юридических лиц, лей за кВт·ч. Параметр: уточняется по счёту.
TARIFF_MDL = 2.9


def energy_waste(machines: int, watt: int = IDLE_WATT, tariff: float = TARIFF_MDL) -> dict:
    """Во что обходится привычка не выключать компьютеры на ночь.

    Считаем только заведомо лишние часы: всё, что вне рабочего времени.
    Экономия при выключении — это те же часы, умноженные на мощность и тариф.
    """
    idle_h_week = HOURS_PER_WEEK - WORK_HOURS_PER_WEEK
    kwh_week = machines * idle_h_week * watt / 1000
    kwh_month = kwh_week * 4.345
    return {
        "machines": machines,
        "watt_per_machine": watt,
        "tariff_mdl": tariff,
        "idle_hours_week": idle_h_week,
        "kwh_week": round(kwh_week, 1),
        "kwh_month": round(kwh_month, 1),
        "kwh_year": round(kwh_week * 52, 1),
        "mdl_month": round(kwh_month * tariff),
        "mdl_year": round(kwh_week * 52 * tariff),
    }


def night_activity(zbx, group: str = "Office Auto-Discovered", hours: int = 36) -> list[dict]:
    """Кто из наблюдаемых машин не выключается на ночь.

    Смотрим историю ICMP за ночные часы: если узел отвечал всегда, значит
    его не выключали. Для рабочих станций это прямой перерасход.
    """
    import time
    g = zbx.call("hostgroup.get", {"filter": {"name": group}, "output": ["groupid"],
                                   "selectHosts": ["hostid", "host"]})
    if not g:
        return []
    hosts = {h["hostid"]: h["host"] for h in g[0].get("hosts", [])}
    items = [i for i in zbx.call("item.get", {"groupids": g[0]["groupid"],
                                              "search": {"key_": "icmpping"},
                                              "output": ["itemid", "hostid", "key_"]})
             if i["key_"] == "icmpping"]
    now = int(time.time())
    out = []
    for it in items:
        hist = []
        for ht in (3, 0, 1):
            hist = zbx.call("history.get", {"itemids": it["itemid"], "history": ht,
                                            "time_from": now - hours * 3600,
                                            "sortfield": "clock", "limit": 5000})
            if hist:
                break
        night = [x for x in hist
                 if datetime.fromtimestamp(int(x["clock"])).hour in (0, 1, 2, 3, 4, 5, 6, 22, 23)]
        if not night:
            continue
        up = sum(1 for x in night if float(x["value"]) > 0)
        host = hosts.get(it["hostid"], "?")
        pct = round(up * 100 / len(night))
        out.append({
            "host": host,
            "samples": len(night),
            "night_uptime_pct": pct,
            "is_workstation": host.startswith(("win-ws", "win-")),
            "always_on": pct >= 95,
        })
    out.sort(key=lambda x: (not x["is_workstation"], -x["night_uptime_pct"]))
    return out


# ------------------------------------------------------------------ серверы в стойке

RACK_SERVERS = [
    {
        "name": "cloudbd", "ip": "192.168.0.24", "role": "боевая база Oracle cloudbd",
        "cpu": "2× Intel Xeon E5-2623 v3 @ 3.00GHz",
        "criticality": "критично — на нём вся учётная система",
        "runbook": [
            "Перед любыми работами проверить: SELECT STATUS FROM V$INSTANCE (должно быть OPEN).",
            "Диск /mnt/md3 свободен менее 10 % — следить, при <3 % база встанет.",
            "Перезапуск Oracle только по согласованию: на нём работают все конторы.",
            "t° CPU: норма до 73 °C, троттлинг около 85 °C. Текущие значения 40–50 °C.",
        ],
    },
    {
        "name": "PROXMOX3", "ip": "192.168.0.149", "role": "гипервизор, 51 виртуальная машина",
        "cpu": "2× Intel Xeon E5-2620 v3 @ 2.40GHz",
        "criticality": "критично — падение остановит 20 работающих гостей и сам мониторинг",
        "runbook": [
            "Хранилище storage заполнено на 99 %, ctx на 99 % — разгружать в первую очередь.",
            "Новые машины размещать только на local-zfs (свободно 5,3 ТБ).",
            "Кэш ZFS ARC ограничен 64 ГБ; при нехватке памяти гостям он ужимается сам.",
            "На этом же узле работает Zabbix (CT 101) — мониторинг наблюдает сам себя.",
            "t° CPU: норма до 73 °C. Максимум за два года — 58 °C (данные Kvazar).",
        ],
    },
]


# ------------------------------------------------------------------ отправка в Zabbix

def domain_values(domains: list[dict]) -> dict:
    """Готовит значения для Zabbix, пропуская домены с неизвестной датой.

    Реестр .eu публично дат не отдаёт. Отправить для такого домена 0 значило
    бы поднять ложную тревогу «регистрация истекла», поэтому его просто
    пропускаем, а в панели он показан как «требует ручной проверки».
    """
    return {f"domain.days[{d['domain']}]": d["days_left"]
            for d in domains if d.get("days_left") is not None}


def push_to_zabbix(values: dict, host: str = "business-metrics",
                   server: str = "192.168.0.110") -> dict:
    """Отправляет бизнес-показатели в Zabbix через zabbix_sender на контейнере.

    Локально zabbix_sender может быть не установлен, поэтому отправка идёт
    с самого сервера мониторинга по SSH — он гарантированно умеет.
    """
    import os
    from modules.netmon import proxmox  # keychain-помощник лежит там

    pw = proxmox.keychain("root", "zabbix34-ct")
    if not pw:
        return {"sent": 0, "error": "нет пароля контейнера Zabbix в Keychain"}
    lines = "\n".join(f'- {k} {v}' for k, v in values.items())
    remote = (f"cat <<'EOF' > /tmp/netmon_values.txt\n{lines}\nEOF\n"
              f"zabbix_sender -z 127.0.0.1 -s {host} -i /tmp/netmon_values.txt 2>&1 | tail -2; "
              f"rm -f /tmp/netmon_values.txt")
    env = dict(os.environ)
    env["SSHPASS"] = pw
    r = subprocess.run(
        ["sshpass", "-e", "ssh", "-o", "HostKeyAlgorithms=+ssh-rsa",
         "-o", "PubkeyAcceptedKeyTypes=+ssh-rsa", "-o", "StrictHostKeyChecking=no",
         "-o", "ConnectTimeout=15", "root@192.168.0.110", remote],
        capture_output=True, text=True, env=env, timeout=60)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"processed:\s*(\d+);\s*failed:\s*(\d+)", out)
    return {"sent": int(m.group(1)) if m else 0,
            "failed": int(m.group(2)) if m else 0,
            "raw": out.strip()[:200]}
