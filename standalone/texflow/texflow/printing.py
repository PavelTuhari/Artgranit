"""Отправка этикеток на принтер: RAW по сети (порт 9100), CUPS/lp, папка-спул.

Zebra и TSC с сетевой картой принимают ZPL/TSPL «как есть» на TCP 9100.
USB-принтер на Linux/macOS — через очередь CUPS в режиме raw.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time


def send_raw_tcp(host: str, data: bytes, port: int = 9100, timeout: float = 5.0) -> int:
    """Отправить байты на принтер. Возвращает количество отправленных байт."""
    with socket.create_connection((host, int(port)), timeout=timeout) as s:
        s.sendall(data)
        try:
            s.shutdown(socket.SHUT_WR)
        except OSError:
            pass
    return len(data)


def send_cups(queue: str, data: bytes) -> str:
    """Печать через CUPS в режиме raw (USB-принтер, Linux/macOS)."""
    lp = shutil.which("lp")
    if not lp:
        raise RuntimeError("команда lp не найдена — CUPS не установлен")
    r = subprocess.run([lp, "-d", queue, "-o", "raw"], input=data,
                       capture_output=True, timeout=20)
    if r.returncode:
        raise RuntimeError(r.stderr.decode(errors="replace").strip() or "lp: ошибка")
    return r.stdout.decode(errors="replace").strip()


def save_spool(folder: str, data: bytes, ext: str) -> str:
    """Сохранить задание в папку (её может забирать драйвер/скрипт печати)."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"labels_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}.{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return path


def dispatch(target: str, data: bytes, ext: str) -> str:
    """target: ``tcp://10.0.0.50:9100`` | ``cups://Zebra_ZD220`` | ``dir:///path``."""
    if target.startswith("tcp://"):
        hostport = target[6:]
        host, _, port = hostport.partition(":")
        n = send_raw_tcp(host, data, int(port or 9100))
        return f"отправлено {n} байт на {host}:{port or 9100}"
    if target.startswith("cups://"):
        return send_cups(target[7:], data) or "отправлено в CUPS"
    if target.startswith("dir://"):
        return "сохранено: " + save_spool(target[6:], data, ext)
    raise ValueError("адрес принтера: tcp://IP:9100, cups://ОЧЕРЕДЬ или dir:///папка")
