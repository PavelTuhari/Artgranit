"""Источник данных Proxmox: паспорта всех виртуальных машин и контейнеров.

Собирает сведения обо ВСЕХ гостях — включая выключенные, про которые
обычно и забывают. Работает через SSH и штатный `pvesh`, а не через
HTTPS-API: на PVE 4.4 сертификат самоподписанный, а тикет-авторизация
добавляет лишний слой без выгоды. Пароль берётся из macOS Keychain.

Один SSH-вызов собирает всё разом — 51 гость, иначе было бы 51 подключение.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

from modules.netmon import rules

PVE_HOST = "192.168.0.149"
PVE_NODE = "proxmox3"
KEYCHAIN_SERVICE = "proxmox3-ssh"

# Скрипт выполняется НА гипервизоре и печатает один JSON.
# Разделители ===VM=== позволяют разобрать вывод без вложенных экранирований.
_COLLECT = r"""
echo '===RESOURCES==='
pvesh get /cluster/resources --type vm 2>/dev/null
echo '===NODE==='
pvesh get /nodes/NODE/status 2>/dev/null
echo '===STORAGE==='
pvesm status 2>/dev/null
echo '===BACKUPS==='
ls -l --time-style=+%Y-%m-%d /var/lib/vz/dump/ 2>/dev/null | grep -E '\.(vma|tar)' || true
for i in $(qm list 2>/dev/null | tail -n +2 | awk '{print $1}'); do
  echo "===CONFIG qemu $i==="
  qm config $i 2>/dev/null
  echo "===SNAP qemu $i==="
  qm listsnapshot $i 2>/dev/null | grep -v no-parent || true
done
for i in $(pct list 2>/dev/null | tail -n +2 | awk '{print $1}'); do
  echo "===CONFIG lxc $i==="
  pct config $i 2>/dev/null
  echo "===SNAP lxc $i==="
  pct listsnapshot $i 2>/dev/null || true
done
echo '===END==='
"""


def keychain(account: str, service: str) -> str:
    r = subprocess.run(["security", "find-generic-password", "-a", account, "-s", service, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _ssh(command: str, timeout: int = 180) -> str:
    pw = keychain("root", KEYCHAIN_SERVICE)
    if not pw:
        raise RuntimeError(f"нет пароля Proxmox в Keychain (запись {KEYCHAIN_SERVICE})")
    env = dict(os.environ)
    env["SSHPASS"] = pw
    r = subprocess.run(
        ["sshpass", "-e", "ssh", "-o", "HostKeyAlgorithms=+ssh-rsa",
         "-o", "PubkeyAcceptedKeyTypes=+ssh-rsa", "-o", "StrictHostKeyChecking=no",
         "-o", "ConnectTimeout=15", f"root@{PVE_HOST}", command],
        capture_output=True, text=True, env=env, timeout=timeout)
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError(f"Proxmox недоступен: {r.stderr.strip()[:160]}")
    return r.stdout


# ---------------------------------------------------------------- разбор вывода

def _split_sections(out: str) -> dict:
    """Режет вывод по маркерам ===NAME=== в словарь секций."""
    sections: dict[str, list[str]] = {}
    key = None
    for line in out.splitlines():
        m = re.match(r"^===(.+)===$", line.strip())
        if m:
            key = m.group(1).strip()
            sections[key] = []
            continue
        if key:
            sections[key].append(line)
    return {k: "\n".join(v) for k, v in sections.items()}


def _parse_config(text: str) -> dict:
    """Конфиг qm/pct: строки вида «ключ: значение»."""
    cfg: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line or line.startswith("#"):
            continue
        k, v = line.split(":", 1)
        cfg[k.strip()] = v.strip()
    return cfg


def _unescape_description(raw: str) -> str:
    """Описание в конфиге Proxmox хранится percent-encoded: %0A, %D0%B5 и т.п.

    Декодировать посимвольно нельзя: кириллица там — многобайтовый UTF-8,
    и chr() на каждый байт даёт мусор вида «Ð µÑ‰Ñ‘». Собираем байты и
    декодируем целиком.
    """
    if not raw:
        return ""
    out = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] == "%" and i + 2 < len(raw) + 1:
            try:
                out.append(int(raw[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        out.extend(raw[i].encode("utf-8"))
        i += 1
    return out.decode("utf-8", "replace")


# Поля описания, которые нельзя показывать: там админы держат пароли
_SECRET_FIELDS = ("auth", "pass", "password", "пароль", "логин", "login", "pwd")


def _mask_secret(name: str, value: str) -> str:
    """Учётные данные из описания ВМ наружу не отдаём.

    В описаниях гостей на PROXMOX3 обнаружены строки вида
    «Auth: root/<пароль>». Показывать их на панели и класть в базу нельзя:
    панель доступна всем, у кого есть вход в портал.
    """
    if any(s in name.lower() for s in _SECRET_FIELDS):
        return "указаны в описании ВМ на гипервизоре (скрыты)"
    return value


def _disks(cfg: dict) -> list[dict]:
    """Диски гостя: размер и хранилище. Ключи scsi0/virtio0/ide0/rootfs/mp0."""
    out = []
    for key, val in cfg.items():
        if not re.match(r"^(scsi|virtio|ide|sata|rootfs|mp)\d*$", key):
            continue
        if "media=cdrom" in val:
            continue
        store = val.split(":", 1)[0] if ":" in val else ""
        size = ""
        m = re.search(r"size=(\d+[KMGT]?)", val)
        if m:
            size = m.group(1)
        out.append({"slot": key, "storage": store, "size": size})
    return out


def _nets(cfg: dict) -> list[dict]:
    out = []
    for key, val in cfg.items():
        if not re.match(r"^net\d+$", key):
            continue
        mac = ""
        m = re.search(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})", val)
        if m:
            mac = m.group(1)
        bridge = ""
        m = re.search(r"bridge=(\w+)", val)
        if m:
            bridge = m.group(1)
        ip = ""
        m = re.search(r"ip=([0-9./]+)", val)
        if m:
            ip = m.group(1)
        model = val.split("=", 1)[0].split(",")[0]
        out.append({"slot": key, "mac": mac, "bridge": bridge, "ip": ip, "model": model})
    return out


def _size_to_gb(size: str) -> float:
    if not size:
        return 0.0
    m = re.match(r"^(\d+)([KMGT]?)$", size)
    if not m:
        return 0.0
    n, unit = int(m.group(1)), m.group(2)
    return round(n * {"": 1 / 1073741824, "K": 1 / 1048576, "M": 1 / 1024,
                      "G": 1, "T": 1024}.get(unit, 1), 1)


# ---------------------------------------------------------------- сбор

def collect() -> dict:
    """Собирает паспорта всех гостей гипервизора одним заходом."""
    out = _ssh(_COLLECT.replace("NODE", PVE_NODE))
    sec = _split_sections(out)
    if "END" not in sec:
        raise RuntimeError("сбор данных Proxmox не завершился — проверьте доступ")

    try:
        resources = json.loads(sec.get("RESOURCES", "[]") or "[]")
    except json.JSONDecodeError:
        resources = []
    live = {str(r.get("id", "")).split("/")[-1]: r for r in resources}

    # свежесть резервных копий по vmid
    backups: dict[str, str] = {}
    for line in sec.get("BACKUPS", "").splitlines():
        m = re.search(r"(\d{4}-\d{2}-\d{2}).*vzdump-(?:qemu|lxc)-(\d+)-", line)
        if m:
            vmid, date = m.group(2), m.group(1)
            if vmid not in backups or date > backups[vmid]:
                backups[vmid] = date

    guests = []
    for key, text in sec.items():
        m = re.match(r"^CONFIG (qemu|lxc) (\d+)$", key)
        if not m:
            continue
        kind, vmid = m.group(1), m.group(2)
        cfg = _parse_config(text)
        snaps = [s for s in sec.get(f"SNAP {kind} {vmid}", "").splitlines()
                 if s.strip() and "current" not in s]
        r = live.get(vmid, {})
        descr = _unescape_description(cfg.get("description", ""))
        disks = _disks(cfg)
        guest = {
            "vmid": int(vmid),
            "kind": kind,
            "name": cfg.get("name") or cfg.get("hostname") or f"{kind}-{vmid}",
            "status": r.get("status", "stopped"),
            "cores": int(cfg.get("cores", 0) or 0),
            "sockets": int(cfg.get("sockets", 1) or 1),
            "memory_mb": int(cfg.get("memory", 0) or 0),
            "ostype": cfg.get("ostype", ""),
            "onboot": cfg.get("onboot", "0") == "1",
            "disks": disks,
            "disk_gb": round(sum(_size_to_gb(d["size"]) for d in disks), 1),
            "nets": _nets(cfg),
            # сырое описание наружу не отдаём: в нём встречаются пароли.
            # Пользователю показываем только разобранные и очищенные поля.
            "description": _strip_secrets(descr).strip(),
            "snapshots": len(snaps),
            "last_backup": backups.get(vmid, ""),
            "uptime_s": int(r.get("uptime", 0) or 0),
            "cpu_pct": round(float(r.get("cpu", 0) or 0) * 100, 1),
            "mem_used_mb": int(int(r.get("mem", 0) or 0) / 1048576),
        }
        guest.update(passport(guest))
        guests.append(guest)

    guests.sort(key=lambda g: g["vmid"])
    return {"node": PVE_NODE, "host": PVE_HOST,
            "storages": _storages(sec.get("STORAGE", "")), "guests": guests}


def _storages(text: str) -> list[dict]:
    out = []
    for line in text.splitlines()[1:]:
        p = line.split()
        if len(p) >= 6:
            try:
                out.append({"name": p[0], "type": p[1],
                            "total_gb": round(int(p[3]) / 1048576, 1),
                            "used_gb": round(int(p[4]) / 1048576, 1),
                            "used_pct": float(p[6].rstrip("%")) if len(p) > 6 else 0.0})
            except (ValueError, IndexError):
                continue
    return out


# ---------------------------------------------------------------- паспорт и решение

# ОС, снятые с поддержки: гость на такой ОС нельзя переносить «как есть»
LEGACY_OS = {
    "win7": "Windows 7 (поддержка закончилась 14.01.2020)",
    "winxp": "Windows XP (поддержка закончилась 08.04.2014)",
    "w2k3": "Windows Server 2003 (поддержка закончилась 14.07.2015)",
    "w2k8": "Windows Server 2008 (поддержка закончилась 14.01.2020)",
    "wxp": "Windows XP (поддержка закончилась 08.04.2014)",
    "w2k": "Windows 2000 (поддержка закончилась 13.07.2010)",
}

DECISION_RETIRE = "списать"
DECISION_MIGRATE = "переносить"
DECISION_REPLACE = "пересоздать на новой ОС"
DECISION_KEEP = "оставить как есть"
DECISION_REVIEW = "нужно решение"


def passport(g: dict) -> dict:
    """Заключение по гостю: на что смотреть и что с ним делать дальше.

    Возвращает признаки риска и предлагаемое решение. Это подсказка
    человеку, а не приговор: окончательное решение принимает владелец.
    """
    notes: list[str] = []
    risks: list[str] = []
    descr = (g.get("description") or "").lower()

    legacy = LEGACY_OS.get(g.get("ostype", ""))
    if legacy:
        risks.append(f"ОС снята с поддержки: {legacy}")

    if not g.get("last_backup"):
        risks.append("резервной копии нет ни одной")
    elif g["last_backup"] < "2025-01-01":
        risks.append(f"последняя резервная копия — {g['last_backup']}")

    unused = any(w in descr for w in ("not used", "не использ", "unused", "старый", "old"))
    if unused:
        notes.append("в описании помечена как неиспользуемая")

    if g["status"] == "stopped":
        notes.append("выключена")
    if g.get("disk_gb", 0) >= 100:
        notes.append(f"крупный диск {g['disk_gb']} ГБ — перенос будет долгим")
    if g.get("memory_mb", 0) >= 16384:
        notes.append(f"много памяти {g['memory_mb']} МБ — учесть на приёмнике")
    if not g.get("onboot") and g["status"] == "running":
        risks.append("автозапуск выключен — после перезагрузки хоста не поднимется")

    # предлагаемое решение
    if unused and g["status"] == "stopped":
        decision = DECISION_RETIRE
    elif legacy and g["status"] == "running":
        decision = DECISION_REPLACE
    elif legacy:
        decision = DECISION_REVIEW
    elif g["status"] == "running":
        decision = DECISION_MIGRATE
    elif g["status"] == "stopped" and not g.get("last_backup"):
        decision = DECISION_REVIEW
    else:
        decision = DECISION_KEEP

    # извлекаем из описания то, что админы писали руками; секреты маскируем
    fields = {}
    has_secret = False
    for line in (g.get("description") or "").splitlines():
        m = re.match(r"^\s*(IP|Auth|Role|OS|Роль|Логин|Пароль|Password)\s*[:=]\s*(.+)$",
                     line, re.I)
        if m:
            name, value = m.group(1).strip().lower(), m.group(2).strip()
            if any(s in name for s in _SECRET_FIELDS):
                has_secret = True
            fields[name] = _mask_secret(name, value)
    if has_secret:
        risks.append("в описании ВМ хранятся учётные данные открытым текстом")

    return {
        "legacy_os": bool(legacy),
        "risks": risks,
        "notes": notes,
        "decision": decision,
        "descr_fields": fields,
        "risk_level": "high" if legacy or not g.get("last_backup") else
                      ("medium" if risks else "low"),
    }


# Пара «логин/пароль», записанная без подписи — встречается в описаниях
# отдельной строкой вида «admin/s3cret». Ловим её отдельно от «Auth: …».
_CREDENTIAL_PAIR = re.compile(r"\b[\w.@-]{3,24}\s*/\s*\S{5,}", re.UNICODE)


def _strip_secrets(text: str) -> str:
    """Вычищает из описания учётные данные — и подписанные, и голые пары.

    Две формы записи в реальных описаниях на PROXMOX3:
      «Auth: root/пароль»  — ловится по имени поля;
      «admin/пароль»       — отдельной строкой без подписи, ловится образцом.
    """
    keep = []
    for line in (text or "").splitlines():
        name = line.split(":", 1)[0].strip().lower() if ":" in line else ""
        if name and any(s in name for s in _SECRET_FIELDS):
            keep.append(f"{line.split(':', 1)[0]}: (скрыто)")
            continue
        cleaned = _CREDENTIAL_PAIR.sub("(учётные данные скрыты)", line)
        keep.append(cleaned)
    return "\n".join(keep)


def summary(data: dict) -> dict:
    """Сводка по гипервизору для плитки на панели."""
    gs = data.get("guests", [])
    by_decision: dict[str, int] = {}
    for g in gs:
        by_decision[g["decision"]] = by_decision.get(g["decision"], 0) + 1
    return {
        "node": data.get("node"),
        "total": len(gs),
        "running": sum(1 for g in gs if g["status"] == "running"),
        "stopped": sum(1 for g in gs if g["status"] != "running"),
        "vm": sum(1 for g in gs if g["kind"] == "qemu"),
        "ct": sum(1 for g in gs if g["kind"] == "lxc"),
        "legacy_os": sum(1 for g in gs if g["legacy_os"]),
        "no_backup": sum(1 for g in gs if not g["last_backup"]),
        "disk_gb": round(sum(g["disk_gb"] for g in gs), 1),
        "memory_mb": sum(g["memory_mb"] for g in gs),
        "by_decision": by_decision,
        "storages": data.get("storages", []),
    }
