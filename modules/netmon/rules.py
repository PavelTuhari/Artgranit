"""Чистые правила модуля netmon: без импорта БД, тестируются без wallet.

Здесь живёт вся классификация устройств офисной сети и разбор алертов Zabbix.
Правила отделены от SQL и от сетевых вызовов намеренно: их можно прогнать
тестами на голом Python, без Oracle и без VPN.
"""

VERSION = "1.0"

# Порты, по которым опознаём устройство при скане
PROBE_PORTS = [22, 80, 443, 3389, 8006, 8080, 161, 9100, 631, 554,
               1521, 3306, 5432, 445, 10050, 8000, 8001]

# Классы устройств
KIND_HYPERVISOR = "Гипервизор Proxmox"
KIND_ORACLE = "Сервер Oracle"
KIND_ZABBIX = "Сервер Zabbix"
KIND_ROUTER = "Маршрутизатор MikroTik"
KIND_CAMERA = "IP-камера / видеорегистратор"
KIND_PRINTER = "Принтер / МФУ"
KIND_NETGEAR = "Сетевое оборудование (коммутатор/принтер/IP-телефон)"
KIND_WIN_WS = "Рабочая станция Windows"
KIND_WIN_HOST = "Хост Windows"
KIND_LINUX_WEB = "Сервер Linux (веб)"
KIND_LINUX = "Сервер Linux"
KIND_WEB = "Веб-устройство"
KIND_UNKNOWN = "Неопознанное устройство"

CRIT_HIGH = "high"
CRIT_MEDIUM = "medium"
CRIT_LOW = "low"

_CRITICALITY = {
    KIND_HYPERVISOR: CRIT_HIGH,
    KIND_ORACLE: CRIT_HIGH,
    KIND_ZABBIX: CRIT_HIGH,
    KIND_ROUTER: CRIT_HIGH,
    KIND_LINUX_WEB: CRIT_MEDIUM,
    KIND_LINUX: CRIT_MEDIUM,
    KIND_CAMERA: CRIT_MEDIUM,
    KIND_WIN_WS: CRIT_LOW,
    KIND_WIN_HOST: CRIT_LOW,
    KIND_PRINTER: CRIT_LOW,
    KIND_NETGEAR: CRIT_LOW,
    KIND_WEB: CRIT_LOW,
    KIND_UNKNOWN: CRIT_LOW,
}


def ip_key(ip: str):
    """Ключ сортировки IP по октетам, а не по строке (иначе .100 < .9)."""
    parts = (ip or "").split(".")
    if len(parts) != 4 or not all(p.isdigit() for p in parts):
        return (999, 999, 999, 999)
    return tuple(int(p) for p in parts)


def classify(ttl, ports, title: str = "", server: str = "") -> str:
    """Класс устройства по TTL, открытым портам и баннерам.

    TTL — грубый, но надёжный признак семейства ОС: 64 (в пути −1 → 63)
    Linux/BSD, 128 (→127) Windows, 255 (→254) сетевое железо.
    Порты уточняют роль; заголовки страниц перебивают догадку по портам.
    """
    p = set(ports or [])
    t = f"{title} {server}".lower()
    ttl = ttl or 0

    if 8006 in p or "proxmox" in t:
        return KIND_HYPERVISOR
    if 554 in p and 8000 in p:
        return KIND_CAMERA
    if 1521 in p:
        return KIND_ORACLE
    if 9100 in p or 631 in p:
        return KIND_PRINTER
    if "mikrotik" in t or "routeros" in t:
        return KIND_ROUTER
    if "zabbix" in t:
        return KIND_ZABBIX
    if ttl >= 200:
        return KIND_NETGEAR
    if 3389 in p:
        return KIND_WIN_WS
    if 22 in p and (80 in p or 443 in p):
        return KIND_LINUX_WEB
    if 22 in p:
        return KIND_LINUX
    if 80 in p or 443 in p:
        return KIND_WEB
    if ttl in (127, 128):
        return KIND_WIN_HOST
    return KIND_UNKNOWN


def criticality(kind: str, ports=None) -> str:
    """Насколько больно, если устройство пропадёт."""
    return _CRITICALITY.get(kind, CRIT_LOW)


def host_name(ip: str, kind: str, dns: str = "", title: str = "") -> str:
    """Техническое имя хоста в Zabbix: уникальное и читаемое.

    Если обратная зона DNS отдала имя — берём его; иначе собираем из класса
    и последнего октета, чтобы в списке хостов было видно, что за железка.
    """
    if dns:
        return dns.split(".")[0][:60]
    short = {
        KIND_HYPERVISOR: "pve", KIND_ORACLE: "oracle", KIND_ZABBIX: "zabbix",
        KIND_ROUTER: "mikrotik", KIND_CAMERA: "cam", KIND_PRINTER: "printer",
        KIND_NETGEAR: "net", KIND_WIN_WS: "win-ws", KIND_WIN_HOST: "win",
        KIND_LINUX_WEB: "linux-web", KIND_LINUX: "linux", KIND_WEB: "web",
        KIND_UNKNOWN: "host",
    }.get(kind, "host")
    return f"{short}-{ip.split('.')[-1]}"


def host_description(dev: dict) -> str:
    """Описание хоста в Zabbix: откуда он взялся и что про него известно."""
    bits = [f"Заведён автоматически модулем netmon (скан {dev.get('ip')})",
            f"Класс: {dev.get('kind')}",
            f"Открытые порты: {', '.join(str(p) for p in dev.get('ports') or []) or '—'}"]
    if dev.get("title"):
        bits.append(f"Заголовок: {dev['title']}")
    if dev.get("ssh"):
        bits.append(f"SSH: {dev['ssh']}")
    return "\n".join(bits)


# ------------------------------------------------------------- Telegram и алерты

def alert_severity(subject: str) -> str:
    """Уровень сообщения по его теме — так же, как это делает telegram_bot.sh.

    Скрипт на стороне Zabbix подбирает эмодзи по словам в теме; повторяем ту
    же логику, чтобы лента на панели совпадала с тем, что видно в канале.
    """
    s = (subject or "").lower()
    if s.startswith("resolved") or "resolved:" in s:
        return "resolved"
    if "disaster" in s:
        return "disaster"
    if "high" in s:
        return "high"
    if "average" in s:
        return "average"
    if "warning" in s:
        return "warning"
    if "information" in s:
        return "information"
    return "other"


SEVERITY_EMOJI = {
    "disaster": "🔴🔴", "high": "🔴", "average": "🟠",
    "warning": "🟡", "information": "🔵", "resolved": "🟢", "other": "⚪",
}


def alert_host(subject: str) -> str:
    """Имя хоста из темы вида «Warning: cloudbd | 192.168.0.24»."""
    s = subject or ""
    if ":" in s:
        s = s.split(":", 1)[1]
    return s.split("|")[0].strip()


def channel_kind(chat_id: str) -> str:
    """Тип чата Telegram по его id: -100… — канал/супергруппа, -… — группа."""
    cid = str(chat_id or "")
    if cid.startswith("-100"):
        return "channel"
    if cid.startswith("-"):
        return "group"
    return "private"


def normalize_code(value: str) -> str:
    """Код сущности: без пробелов, верхний регистр."""
    return (value or "").strip().upper()
