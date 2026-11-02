import os
import socket
import threading

import pytest

from texflow import printing


def fake_printer():
    """Мини-«принтер» на TCP: принимает задание и складывает байты."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    got = {}

    def run():
        conn, _ = srv.accept()
        buf = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
        got["data"] = buf
        conn.close()
        srv.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return srv.getsockname()[1], got, t


def test_raw_tcp_9100_like():
    port, got, t = fake_printer()
    msg = printing.dispatch(f"tcp://127.0.0.1:{port}", b"^XA^FDhi^FS^XZ", "zpl")
    t.join(3)
    assert got["data"] == b"^XA^FDhi^FS^XZ"
    assert "14 байт" in msg


def test_spool_dir(tmp_path):
    msg = printing.dispatch(f"dir://{tmp_path}", b"SIZE 58 mm,40 mm", "tspl")
    files = os.listdir(tmp_path)
    assert len(files) == 1 and files[0].endswith(".tspl") and str(tmp_path) in msg


def test_bad_target_and_unreachable():
    with pytest.raises(ValueError):
        printing.dispatch("lpt1", b"x", "zpl")
    with pytest.raises(OSError):
        printing.send_raw_tcp("127.0.0.1", b"x", port=1, timeout=1)


def test_cups_without_lp(monkeypatch):
    monkeypatch.setattr(printing.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError):
        printing.dispatch("cups://Zebra", b"x", "zpl")
