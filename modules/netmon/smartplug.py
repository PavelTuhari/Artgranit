"""Управление умными розетками Tuya / Smart Life по локальной сети.

В офисе найдено четыре розетки (192.168.0.203, .206, .207, .240). Они
говорят по локальному протоколу Tuya на порту 6668 и **шифруют обмен**:
без `local_key` конкретного устройства управлять им нельзя — это защита
самого протокола, обойти её нечем.

Поэтому модуль делает две вещи:
  1. Видит розетки всегда — доступность и отклик (это работает без ключей);
  2. Управляет теми, для которых ключ положен в Keychain.

Как получить ключи — docs/Netmon/SMART_PLUGS.md. Ключи хранятся только в
Keychain: запись `tuya-<ip>`, логин = device_id, пароль = local_key.
"""
from __future__ import annotations

import binascii
import json
import socket
import struct
import subprocess
import time
from hashlib import md5

TUYA_PORT = 6668
DISCOVERY_PORTS = (6666, 6667)
# Известные розетки офиса: обнаружены сканированием 12.09.2026
KNOWN_PLUGS = ["192.168.0.203", "192.168.0.206", "192.168.0.207", "192.168.0.240"]

PREFIX = 0x000055AA
SUFFIX = 0x0000AA55
# Команды протокола
CMD_STATUS = 0x0A      # запрос состояния (DP_QUERY)
CMD_CONTROL = 0x07     # управление (CONTROL)


class PlugError(RuntimeError):
    pass


def keychain(account: str, service: str) -> str:
    r = subprocess.run(["security", "find-generic-password", "-a", account,
                        "-s", service, "-w"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def keychain_pair(ip: str) -> tuple[str, str]:
    """device_id и local_key розетки из Keychain (запись tuya-<ip>)."""
    service = f"tuya-{ip}"
    r = subprocess.run(["security", "find-generic-password", "-s", service],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return "", ""
    dev_id = ""
    for line in r.stdout.splitlines():
        if '"acct"' in line and "=" in line:
            dev_id = line.split("=", 1)[1].strip().strip('"')
    return dev_id, keychain(dev_id, service) if dev_id else ""


# ---------------------------------------------------------------- доступность

def ping_plug(ip: str, timeout: float = 2.0) -> dict:
    """Отвечает ли розетка на порту управления. Ключ для этого не нужен."""
    t0 = time.time()
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, TUYA_PORT))
        return {"ip": ip, "online": True, "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:  # noqa: BLE001
        return {"ip": ip, "online": False, "error": str(e)[:80]}
    finally:
        s.close()


def discover(seconds: int = 20) -> list[dict]:
    """Ловит широковещательные пакеты Tuya.

    Устройства объявляют себя каждые несколько секунд. В протоколе 3.1/3.3
    полезная нагрузка открытая (там виден device_id), с 3.4 — зашифрована,
    и по broadcast можно узнать только сам факт присутствия и адрес.
    """
    socks = []
    for port in DISCOVERY_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("", port))
            s.settimeout(2)
            socks.append(s)
        except Exception:  # noqa: BLE001 — порт может быть занят
            pass
    seen: dict[str, dict] = {}
    end = time.time() + seconds
    while time.time() < end and socks:
        import select
        ready, _, _ = select.select(socks, [], [], 2)
        for s in ready:
            try:
                data, addr = s.recvfrom(2048)
            except Exception:  # noqa: BLE001
                continue
            info = {"ip": addr[0], "protocol": "3.4+ (шифрованный)", "device_id": ""}
            payload = data[20:-8] if len(data) > 28 else data
            try:
                j = json.loads(payload.decode("utf-8", "ignore").strip("\x00"))
                info["device_id"] = j.get("gwId") or j.get("devId") or ""
                info["protocol"] = j.get("version") or "3.1/3.3 (открытый)"
                info["product"] = j.get("productKey", "")
            except Exception:  # noqa: BLE001 — шифрованный пакет, это норма
                info["raw_head"] = binascii.hexlify(data[:8]).decode()
            seen[addr[0]] = info
    for s in socks:
        s.close()
    return list(seen.values())


# ---------------------------------------------------------------- протокол

def _pack(cmd: int, payload: bytes, seq: int = 1) -> bytes:
    body = payload + struct.pack(">I", 0)          # место под CRC
    head = struct.pack(">IIII", PREFIX, seq, cmd, len(body) + 4)
    crc = binascii.crc32(head + payload) & 0xFFFFFFFF
    return head + payload + struct.pack(">II", crc, SUFFIX)


def _aes_ecb(key: bytes, data: bytes, encrypt: bool = True) -> bytes:
    """AES-128-ECB средствами стандартной библиотеки недоступен, используем openssl."""
    mode = "-e" if encrypt else "-d"
    r = subprocess.run(["openssl", "enc", "-aes-128-ecb", mode, "-nopad",
                        "-K", key.hex()], input=data, capture_output=True)
    if r.returncode != 0:
        raise PlugError(f"шифрование не удалось: {r.stderr.decode()[:80]}")
    return r.stdout


def _request(ip: str, dev_id: str, local_key: str, cmd: int, dps: dict | None = None,
             timeout: float = 5.0) -> dict:
    """Отправляет команду розетке. Требует device_id и local_key."""
    if not dev_id or not local_key:
        raise PlugError("нет device_id/local_key — управление недоступно "
                        "(см. docs/Netmon/SMART_PLUGS.md)")
    key = local_key.encode()[:16]
    body = {"devId": dev_id, "uid": dev_id, "t": str(int(time.time()))}
    if dps is not None:
        body["dps"] = dps
    raw = json.dumps(body, separators=(",", ":")).encode()
    pad = 16 - (len(raw) % 16)
    enc = _aes_ecb(key, raw + bytes([pad]) * pad, True)
    payload = b"3.3" + b"\x00" * 12 + enc
    pkt = _pack(cmd, payload)

    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, TUYA_PORT))
        s.send(pkt)
        data = s.recv(4096)
    finally:
        s.close()
    if not data or len(data) < 24:
        raise PlugError("розетка не ответила — проверьте local_key и версию протокола")
    chunk = data[20:-8]
    if chunk[:3] in (b"3.3", b"3.4"):
        chunk = chunk[15:]
    try:
        dec = _aes_ecb(key, chunk, False)
        text = dec[:-dec[-1]].decode("utf-8", "ignore")
        return json.loads(text)
    except Exception as e:  # noqa: BLE001
        raise PlugError(f"ответ не расшифрован ({str(e)[:60]}); "
                        "чаще всего это неверный local_key") from e


def status(ip: str) -> dict:
    """Состояние розетки: включена ли, потребление, если умеет измерять."""
    dev_id, key = keychain_pair(ip)
    alive = ping_plug(ip)
    if not alive["online"]:
        return {**alive, "controllable": False, "reason": "розетка недоступна"}
    if not (dev_id and key):
        return {**alive, "controllable": False,
                "reason": "нет ключа в Keychain (запись tuya-" + ip + ")"}
    try:
        r = _request(ip, dev_id, key, CMD_STATUS)
        dps = r.get("dps", {})
        return {**alive, "controllable": True, "device_id": dev_id,
                "switch_on": bool(dps.get("1")), "dps": dps,
                "power_w": (dps.get("19") or 0) / 10 if dps.get("19") else None}
    except PlugError as e:
        return {**alive, "controllable": False, "reason": str(e)}


def switch(ip: str, on: bool) -> dict:
    """Включает или выключает розетку."""
    dev_id, key = keychain_pair(ip)
    if not (dev_id and key):
        raise PlugError(f"нет ключа для {ip}: заведите запись Keychain tuya-{ip} "
                        "(логин = device_id, пароль = local_key)")
    r = _request(ip, dev_id, key, CMD_CONTROL, dps={"1": bool(on)})
    return {"ip": ip, "requested": "on" if on else "off", "response": r}


def all_status() -> list[dict]:
    """Состояние всех известных розеток офиса."""
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(8) as ex:
        return list(ex.map(status, KNOWN_PLUGS))
