"""Сервер OpenVPN офиса: кто подключён, чьи сертификаты, выдача новых доступов.

Через этот сервер идёт вся удалённая работа с офисной сетью — им же
подключён и сам владелец. Обычный мониторинг показывает только «машина
жива»; здесь видно главное: кто сейчас в сети, сколько сертификатов
выдано и какие из них давно не используются.

Сервер — виртуальная машина 139 на PROXMOX3, Ubuntu 20.04, OpenVPN 2.4.12.
Внутри сети `192.168.0.200`, снаружи `93.115.136.18:1194` (UDP).
Работаем по SSH: у OpenVPN нет сетевого API, состояние лежит в файлах.
"""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone

HOST = "192.168.0.200"
PUBLIC_ENDPOINT = "93.115.136.18:1194"
VM_ID = 139
KEYCHAIN_SERVICE = "pve-openvpn"
SRV_DIR = "/etc/openvpn/server"
EASYRSA = f"{SRV_DIR}/easy-rsa"
STATUS_FILE = f"{SRV_DIR}/openvpn-status.log"
INDEX_FILE = f"{EASYRSA}/pki/index.txt"

# Имя клиента попадает в имя файла и в команды easy-rsa, поэтому
# допускаем только безопасный набор символов.
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{1,30}$")


def keychain() -> str:
    r = subprocess.run(["security", "find-generic-password", "-a", "root",
                        "-s", KEYCHAIN_SERVICE, "-w"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _ssh(command: str, timeout: int = 120) -> str:
    pw = keychain()
    if not pw:
        raise RuntimeError(f"нет пароля сервера OpenVPN в Keychain (запись {KEYCHAIN_SERVICE})")
    env = dict(os.environ)
    env["SSHPASS"] = pw
    r = subprocess.run(
        ["sshpass", "-e", "ssh", "-o", "HostKeyAlgorithms=+ssh-rsa",
         "-o", "PubkeyAcceptedKeyTypes=+ssh-rsa", "-o", "StrictHostKeyChecking=no",
         "-o", "ConnectTimeout=15", f"root@{HOST}", command],
        capture_output=True, text=True, env=env, timeout=timeout)
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError(f"сервер OpenVPN недоступен: {r.stderr.strip()[:140]}")
    return r.stdout


def _parse_index_date(raw: str) -> str:
    """Дата в index.txt — формат UTCTime: YYMMDDHHMMSSZ.

    Двузначный год: по соглашению X.509 значения 50-99 относятся к 19xx,
    00-49 — к 20xx. Сертификаты здесь выписаны на 10 лет, поэтому попадают
    в 30xx-е по этому правилу — приводим к нормальному виду.
    """
    m = re.match(r"^(\d{2})(\d{2})(\d{2})", raw or "")
    if not m:
        return ""
    yy = int(m.group(1))
    year = 2000 + yy if yy < 50 else 1900 + yy
    return f"{year}-{m.group(2)}-{m.group(3)}"


def status() -> dict:
    """Состояние службы, подключённые клиенты и реестр сертификатов."""
    out = _ssh(
        "echo '===SERVICE==='; systemctl is-active openvpn-server@server 2>/dev/null; "
        "echo '===UPTIME==='; uptime -p 2>/dev/null; "
        "echo '===VERSION==='; openvpn --version 2>/dev/null | head -1; "
        f"echo '===STATUS==='; cat {STATUS_FILE} 2>/dev/null; "
        f"echo '===INDEX==='; cat {INDEX_FILE} 2>/dev/null; "
        "echo '===END==='")
    parts: dict[str, list[str]] = {}
    key = None
    for line in out.splitlines():
        m = re.match(r"^===(\w+)===$", line.strip())
        if m:
            key = m.group(1)
            parts[key] = []
        elif key:
            parts[key].append(line)

    clients = []
    for line in parts.get("STATUS", []):
        if not line.startswith("CLIENT_LIST,"):
            continue
        f = line.split(",")
        if len(f) < 9:
            continue
        clients.append({
            "name": f[1], "real_address": f[2], "vpn_address": f[3],
            "bytes_received": int(f[5] or 0), "bytes_sent": int(f[6] or 0),
            "connected_since": f[7],
            "mb_received": round(int(f[5] or 0) / 1048576, 1),
            "mb_sent": round(int(f[6] or 0) / 1048576, 1),
        })

    certs = []
    for line in parts.get("INDEX", []):
        f = line.split("\t")
        if len(f) < 6 or f[0] not in ("V", "R"):
            continue
        cn = ""
        m = re.search(r"/CN=([^/]+)", f[-1])
        if m:
            cn = m.group(1)
        if not cn or cn == "server":
            continue
        certs.append({
            "name": cn,
            "revoked": f[0] == "R",
            "expires": _parse_index_date(f[1]),
            "revoked_at": _parse_index_date(f[2]) if f[0] == "R" else "",
        })

    online = {c["name"] for c in clients}
    for c in certs:
        c["online"] = c["name"] in online

    svc = (parts.get("SERVICE") or [""])[0].strip()
    return {
        "host": HOST, "vm_id": VM_ID, "endpoint": PUBLIC_ENDPOINT,
        "service": svc, "running": svc == "active",
        "uptime": (parts.get("UPTIME") or [""])[0].strip(),
        "version": (parts.get("VERSION") or [""])[0].strip()[:60],
        "clients": sorted(clients, key=lambda x: -x["bytes_sent"]),
        "certificates": sorted(certs, key=lambda x: (x["revoked"], x["name"].lower())),
        "checked_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
    }


def summary(data: dict) -> dict:
    certs = data.get("certificates", [])
    return {
        "running": data.get("running"),
        "online": len(data.get("clients", [])),
        "certs_valid": sum(1 for c in certs if not c["revoked"]),
        "certs_revoked": sum(1 for c in certs if c["revoked"]),
        "mb_in": round(sum(c["mb_received"] for c in data.get("clients", [])), 1),
        "mb_out": round(sum(c["mb_sent"] for c in data.get("clients", [])), 1),
    }


# ------------------------------------------------------------------ выдача доступа

def create_client(name: str) -> dict:
    """Выпускает сертификат и собирает готовый профиль .ovpn.

    Профиль возвращается текстом: он содержит закрытый ключ клиента, и
    класть его в общую папку или в репозиторий нельзя. Пользователь
    скачивает файл и сразу передаёт владельцу доступа.
    """
    if not NAME_RE.match(name or ""):
        raise ValueError("имя: латиница, цифры, точка, дефис и подчёркивание; "
                         "начинается с буквы, до 31 символа")
    existing = {c["name"] for c in status()["certificates"] if not c["revoked"]}
    if name in existing:
        raise ValueError(f"сертификат «{name}» уже выдан и действует; "
                         "отзовите его или выберите другое имя")

    out = _ssh(
        f"cd {EASYRSA} && "
        f"EASYRSA_CERT_EXPIRE=3650 ./easyrsa --batch build-client-full {name} nopass "
        "2>&1 | tail -3; echo '===BUILD_DONE==='; "
        # собираем профиль из шаблона и выданных ключей
        f"{{ cat {SRV_DIR}/client-common.txt; "
        f"  echo '<ca>'; cat {EASYRSA}/pki/ca.crt; echo '</ca>'; "
        f"  echo '<cert>'; sed -ne '/BEGIN CERTIFICATE/,$ p' {EASYRSA}/pki/issued/{name}.crt; echo '</cert>'; "
        f"  echo '<key>'; cat {EASYRSA}/pki/private/{name}.key; echo '</key>'; "
        f"  echo '<tls-crypt>'; sed -ne '/BEGIN OpenVPN Static key/,$ p' {SRV_DIR}/tc.key; echo '</tls-crypt>'; "
        f"}} 2>/dev/null", timeout=180)

    if "===BUILD_DONE===" not in out:
        raise RuntimeError(f"выпуск сертификата не завершился: {out[:200]}")
    build_log, _, profile = out.partition("===BUILD_DONE===")
    profile = profile.strip()
    if "<key>" not in profile or "BEGIN PRIVATE KEY" not in profile:
        raise RuntimeError(f"профиль собран неполностью: {build_log.strip()[:200]}")
    return {"name": name, "profile": profile, "size_kb": len(profile) // 1024 + 1,
            "endpoint": PUBLIC_ENDPOINT,
            "hint": "Файл содержит закрытый ключ: передать владельцу лично, "
                    "в репозиторий и общие папки не класть."}


def revoke_client(name: str) -> dict:
    """Отзывает сертификат и обновляет список отзыва."""
    if not NAME_RE.match(name or ""):
        raise ValueError("недопустимое имя клиента")
    out = _ssh(
        f"cd {EASYRSA} && ./easyrsa --batch revoke {name} 2>&1 | tail -2; "
        f"EASYRSA_CRL_DAYS=3650 ./easyrsa gen-crl 2>&1 | tail -1; "
        f"cp -f {EASYRSA}/pki/crl.pem {SRV_DIR}/crl.pem && chmod 644 {SRV_DIR}/crl.pem && "
        f"echo '===REVOKED==='", timeout=180)
    if "===REVOKED===" not in out:
        raise RuntimeError(f"отзыв не выполнен: {out[-200:]}")
    return {"name": name, "revoked": True,
            "note": "Список отзыва обновлён. Действующие сессии этого клиента "
                    "разорвутся при следующем переподключении."}
