#!/usr/bin/env python3
"""Зона una.md — второй адрес Orange рядом с адресом МТС.

    python modules/netmon/scripts/netmon_dns_failover.py --dry-run   # показать разницу
    python modules/netmon/scripts/netmon_dns_failover.py             # записать и перечитать зону
    python modules/netmon/scripts/netmon_dns_failover.py --rollback  # вернуть копию до правки

Авария 03.11.2026: otrs.una.md, xwiki.una.md, vpn.una.md (и всё остальное
под «*») вели только на 93.115.136.18 (МТС). Канал МТС лёг — снаружи пропало
всё, хотя через Orange 195.22.241.126 те же страницы отвечали 200: на нём
HTTP/HTTPS проброшены на тот же nginx 192.168.0.148.

Правка: для «@», «*» и «www» — вторая запись A на Orange. Браузер получает оба
адреса и, если первый не отвечает, идёт на второй. Имена, которые ведут на
другие адреса МТС (почта .21, bonus .20 и т. п.), не трогаются: на Orange их
порты заняты nginx и почтой другого домена, их разводить по имени отдельно.
В SPF добавляется адрес Orange — через него уже ходит mx4.

Зона: BIND на 192.168.0.148, файл /etc/named/una.md. Перед записью — копия
una.md.bak-ДАТА рядом, после записи — named-checkzone, при ошибке копия
возвращается; затем rndc reload una.md.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date

HOST = "192.168.0.148"
ZONE_FILE = "/etc/named/una.md"
MTC_IP = "93.115.136.18"
ORANGE_IP = "195.22.241.126"
NAMES = ("@", "*", "www")
MARK = "netmon failover"


def patch_zone(text: str, today: date) -> str:
    """Текст зоны с записями Orange и новым серийным номером. Повтор — без изменений."""
    lines = text.splitlines()
    out, changed = [], False
    for ln in lines:
        out.append(ln)
        m = re.match(r"^(\S+)\s+IN\s+A\s+(\S+)", ln)
        if m and m.group(1) in NAMES and m.group(2) == MTC_IP:
            twin = re.compile(rf"^{re.escape(m.group(1))}\s+IN\s+A\s+{re.escape(ORANGE_IP)}\b")
            if not any(twin.match(x) for x in lines):
                out.append(f"{m.group(1)}\t\tIN\tA\t\t{ORANGE_IP}   ; {MARK} {today:%Y%m%d}: vtoroy kanal Orange")
                changed = True
    for i, ln in enumerate(out):
        if "v=spf1" in ln and f"ip4:{ORANGE_IP}" not in ln:
            out[i] = ln.replace(" -all", f" ip4:{ORANGE_IP} -all").replace(" ~all", f" ip4:{ORANGE_IP} ~all")
            changed = changed or out[i] != ln
    if not changed:
        return text
    return bump_serial("\n".join(out) + ("\n" if text.endswith("\n") else ""), today)


def bump_serial(text: str, today: date) -> str:
    """Серийный ГГГГММДДNN: сегодняшний и на единицу больше прежнего."""
    m = re.search(r"(\d{10})(\s*;\s*Serial)", text, re.I)
    if not m:
        raise ValueError("в зоне не найден серийный номер «… ;Serial»")
    old = int(m.group(1))
    new = max(old + 1, int(f"{today:%Y%m%d}00"))
    return text[:m.start(1)] + str(new) + text[m.end(1):]


def _ssh(cmd: str, timeout: int = 40) -> str:
    import paramiko
    pw = subprocess.run(["security", "find-internet-password", "-s", HOST, "-a", "root", "-w"],
                        capture_output=True, text=True).stdout.strip()
    if not pw:
        raise RuntimeError(f"в Keychain нет пароля root@{HOST}")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=pw, timeout=10, look_for_keys=False, allow_agent=False)
    try:
        _, o, e = c.exec_command(cmd, timeout=timeout)
        return (o.read() + e.read()).decode("utf-8", "replace")
    finally:
        c.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    a = ap.parse_args()
    today = date.today()
    bak = f"{ZONE_FILE}.bak-{today:%Y%m%d}-failover"
    if a.rollback:
        print(_ssh(f"test -f {bak} && cp -p {bak} {ZONE_FILE} && rndc reload una.md && echo откат: {bak}"
                   f" || echo копии {bak} нет"))
        return
    old = _ssh(f"cat {ZONE_FILE}")
    new = patch_zone(old, today)
    if new == old:
        print("зона уже содержит записи Orange — ничего не меняется")
        return
    import difflib
    sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True), "una.md", "una.md+"))
    if a.dry_run:
        print("--dry-run: зона не изменена")
        return
    tmp = f"/tmp/una.md.netmon.{today:%Y%m%d}"
    body = new.replace("'", "'\"'\"'")
    print(_ssh(
        f"cp -p {ZONE_FILE} {bak} && printf '%s' '{body}' > {tmp} "
        f"&& named-checkzone una.md {tmp} && cat {tmp} > {ZONE_FILE} && rm -f {tmp} "
        f"&& rndc reload una.md && echo ГОТОВО, копия {bak} "
        f"|| {{ cp -p {bak} {ZONE_FILE}; echo ОШИБКА, зона не изменена; }}", timeout=60))


if __name__ == "__main__":
    main()
