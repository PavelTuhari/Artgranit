"""Главный маршрутизатор офиса MikroTik: VPN-доступы L2TP/PPTP, сессии, выдача доступа.

Маршрутизатор — RB1100AHx2, RouterOS 6.45.5, 192.168.0.101, шлюз всей сети.
Снаружи — 93.115.136.18. Кроме OpenVPN (см. openvpn.py), часть сотрудников и
партнёров ходит в офис через PPP прямо на маршрутизатор: L2TP/IPsec и PPTP.

Как подключаемся и почему так
-----------------------------
Только SSH: программный API (8728) на этом маршрутизаторе закрыт. И не
системным `ssh`, а paramiko 3.x (`pip install "paramiko>=3.4,<4"`):

* RSA-ключ хоста на маршрутизаторе сломан — на RSA он обрывает соединение
  сразу после обмена ключами (disconnect 3, до проверки пароля);
* второй ключ хоста — DSA, а его поддержку убрали из OpenSSH 10 и из
  paramiko 4. Поэтому клиент — paramiko 3.x с явным отказом от RSA.
  Лечится на маршрутизаторе: `/ip ssh regenerate-host-key`.

Учётка — `ptuhari`, пароль в Keychain (internet-password, сервер 192.168.0.101).

Что с маршрутизатора НЕ уходит
------------------------------
`print` в RouterOS v6 выводит пароли PPP и общий ключ IPsec открытым текстом.
Поэтому все чтения — через `:foreach … get` с явно перечисленными полями.
Ключ IPsec читается одной командой только при создании ссылки для получателя
и сразу шифруется (modules/vpnguide). В журналы и ответы API он не попадает.
"""
from __future__ import annotations

import re
import secrets
import string
import subprocess
from datetime import datetime

HOST = "192.168.0.101"
USER = "ptuhari"
PUBLIC_ENDPOINT = "93.115.136.18"
DEFAULT_PROFILE = "l2tp-unisim"      # профиль, в котором уже живут L2TP-учётки офиса
COMMENT_TAG = "netmon"

# Имя попадает в команду RouterOS — набор символов узкий, как у OpenVPN.
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{1,30}$")
# Пароль генерируем сами и только из букв и цифр: его будут набирать руками
# в настройках VPN телефона, а спецсимволы в RouterOS-скрипте ещё и экранировать.
_PW_ALPHABET = string.ascii_letters + string.digits
SEP = "\x1f"   # разделитель полей в выводе: в именах и комментариях его не бывает


def keychain() -> str:
    r = subprocess.run(["security", "find-internet-password", "-s", HOST, "-a", USER, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _connect():
    try:
        import paramiko
    except ImportError as e:  # pragma: no cover
        raise RuntimeError('нужен paramiko 3.x: pip install "paramiko>=3.4,<4"') from e
    if int(paramiko.__version__.split(".")[0]) >= 4:
        raise RuntimeError("paramiko 4 не умеет DSA, а RSA-ключ маршрутизатора сломан: "
                           'нужен pip install "paramiko>=3.4,<4"')
    pw = keychain()
    if not pw:
        raise RuntimeError(f"нет пароля маршрутизатора в Keychain (сервер {HOST}, учётка {USER})")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=pw, timeout=15, banner_timeout=15,
              look_for_keys=False, allow_agent=False,
              disabled_algorithms={"keys": ["rsa-sha2-256", "rsa-sha2-512", "ssh-rsa"]})
    return c


class Session:
    """Одно SSH-соединение на серию команд: маршрутизатор — шлюз всей сети,
    лишние входы ему ни к чему, а серия отказов похожа на подбор пароля."""

    def __enter__(self):
        self.c = _connect()
        return self

    def __exit__(self, *exc):
        self.c.close()

    def run(self, cmd: str, timeout: int = 40) -> str:
        _, o, e = self.c.exec_command(cmd, timeout=timeout)
        out = (o.read() + e.read()).decode("utf-8", "replace")
        return out.strip()

    def rows(self, menu: str, fields: list[str], where: str = "") -> list[dict]:
        """Записи меню RouterOS — только перечисленные поля."""
        getters = ' . "\\1f" . '.join(f'[{menu} get $i {f}]' for f in fields)
        out = self.run(f':foreach i in=[{menu} find {where}] do={{:put ({getters})}}')
        res = []
        for line in out.splitlines():
            parts = line.split(SEP)
            if len(parts) == len(fields):
                res.append(dict(zip(fields, parts)))
        return res


# --------------------------------------------------------------- состояние

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _ros_date(s: str) -> str:
    """'oct/06/2026 14:11:50' → '2026-10-06'. Дата 1970 значит «ни разу»."""
    m = re.match(r"^([a-z]{3})/(\d{2})/(\d{4})", s or "")
    if not m or m.group(3) == "1970":
        return ""
    return f"{m.group(3)}-{_MONTHS.get(m.group(1), 1):02d}-{m.group(2)}"


def status() -> dict:
    with Session() as s:
        res = dict(s.rows("/system resource",
                          ["version", "uptime", "cpu-load", "free-memory", "total-memory",
                           "board-name", "architecture-name"])[0:1] and
                   s.rows("/system resource",
                          ["version", "uptime", "cpu-load", "free-memory", "total-memory",
                           "board-name", "architecture-name"])[0])
        servers = {}
        for proto in ("l2tp", "pptp", "sstp"):
            r = s.run(f':put [/interface {proto}-server server get enabled]')
            servers[proto] = r.strip() == "true"
        auth_l2tp = s.run(':put [/interface l2tp-server server get authentication]')
        secrets_ = s.rows("/ppp secret",
                          ["name", "service", "profile", "disabled", "last-logged-out", "comment"])
        active = s.rows("/ppp active", ["name", "service", "caller-id", "address", "uptime"])
    online = {a["name"] for a in active}
    users = []
    for u in secrets_:
        users.append({
            "name": u["name"], "service": u["service"], "profile": u["profile"],
            "disabled": u["disabled"] == "true",
            "last_login": _ros_date(u["last-logged-out"]),
            "comment": u["comment"],
            "online": u["name"] in online,
            "ours": u["comment"].startswith(COMMENT_TAG),
        })
    users.sort(key=lambda x: (x["disabled"], not x["online"], x["name"].lower()))
    return {
        "host": HOST, "endpoint": PUBLIC_ENDPOINT,
        "board": res.get("board-name", ""), "version": res.get("version", ""),
        "uptime": res.get("uptime", ""), "cpu_load": int(res.get("cpu-load") or 0),
        "memory_free_pct": _pct(res.get("free-memory"), res.get("total-memory")),
        "servers": servers, "l2tp_auth": auth_l2tp.strip(),
        "users": users,
        "active": [{"name": a["name"], "service": a["service"], "from": a["caller-id"],
                    "address": a["address"], "uptime": a["uptime"]} for a in active],
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _pct(free, total) -> int | None:
    """'1456.6MiB' / '1536.0MiB' → 95."""
    def num(v):
        m = re.match(r"([\d.]+)\s*([KMG]i?B)?", v or "")
        if not m:
            return None
        k = {"KiB": 1, "MiB": 1024, "GiB": 1024 ** 2}.get(m.group(2) or "KiB", 1)
        return float(m.group(1)) * k
    f, t = num(free), num(total)
    return round(f * 100 / t) if f is not None and t else None


def summary(d: dict) -> dict:
    users = d.get("users", [])
    act = d.get("active", [])
    return {
        "users": len(users),
        "enabled": sum(1 for u in users if not u["disabled"]),
        "online": len(act),
        "online_pptp": sum(1 for a in act if a["service"] == "pptp"),
        "online_l2tp": sum(1 for a in act if a["service"] == "l2tp"),
        "never_logged": sum(1 for u in users if not u["disabled"] and not u["last_login"]),
        "version": d.get("version", ""),
        "cpu_load": d.get("cpu_load"),
    }


def findings(d: dict) -> list[dict]:
    """Выводы словами — как у дисков и OpenVPN."""
    out = []
    s = summary(d)
    if s["online_pptp"]:
        out.append({"level": "crit", "title": f"По PPTP сейчас подключено {s['online_pptp']} из {s['online']}",
                    "text": "PPTP защищён MS-CHAPv2, который взламывается перебором за часы. "
                            "Новые доступы выдаются только L2TP/IPsec или OpenVPN; "
                            "существующих PPTP-пользователей переводить по одному."})
    if d.get("servers", {}).get("pptp"):
        out.append({"level": "warn", "title": "PPTP-сервер включён",
                    "text": "Выключить, когда последние PPTP-подключения будут переведены."})
    v = d.get("version", "")
    m = re.match(r"(\d+)\.(\d+)", v)
    if m and (int(m.group(1)), int(m.group(2))) < (6, 49):
        out.append({"level": "warn", "title": f"RouterOS {v} — версия 2019 года",
                    "text": "Последняя ветка 6.x — 6.49 (long-term), дальше 7.x. Обновлять в окно "
                            "обслуживания: это шлюз всей сети."})
    if s["never_logged"]:
        out.append({"level": "warn", "title": f"{s['never_logged']} включённых учёток ни разу не входили",
                    "text": "Включённая учётка — открытая дверь. Не нужна — выключить."})
    stale = [u for u in d.get("users", []) if not u["disabled"] and u["last_login"]
             and u["last_login"] < f"{datetime.now().year - 1}-01-01"]
    if stale:
        out.append({"level": "warn", "title": f"{len(stale)} включённых учёток не входили больше года",
                    "text": ", ".join(u["name"] for u in stale[:12]) + ("…" if len(stale) > 12 else "")})
    out.append({"level": "info", "title": "RSA-ключ SSH на маршрутизаторе сломан",
                "text": "Подключение работает только по DSA, который убран из новых SSH-клиентов. "
                        "Лечение: /ip ssh regenerate-host-key в окно обслуживания."})
    return out


# ----------------------------------------------------------- выдача доступа

def new_password(length: int = 16) -> str:
    return "".join(secrets.choice(_PW_ALPHABET) for _ in range(length))


def create_user(name: str, by: str = "system") -> dict:
    """Новая учётка L2TP/IPsec. PPTP не выдаём — см. findings()."""
    if not NAME_RE.match(name or ""):
        raise ValueError("имя: латиница, цифры, точка, дефис и подчёркивание; "
                         "начинается с буквы, до 31 символа")
    pw = new_password()
    comment = f"{COMMENT_TAG} {datetime.now():%Y-%m-%d} {re.sub(r'[^A-Za-z0-9_.@-]', '', by)[:30]}"
    with Session() as s:
        if s.run(f':put [/ppp secret print count-only where name="{name}"]').strip() != "0":
            raise ValueError(f"учётка «{name}» на маршрутизаторе уже есть")
        out = s.run(f'/ppp secret add name="{name}" password="{pw}" service=l2tp '
                    f'profile={DEFAULT_PROFILE} comment="{comment}"')
        if out:
            raise RuntimeError(f"маршрутизатор не принял учётку: {out[:160]}")
        if s.run(f':put [/ppp secret print count-only where name="{name}"]').strip() != "1":
            raise RuntimeError("учётка не появилась после добавления")
    return {"name": name, "password": pw, "service": "l2tp", "server": PUBLIC_ENDPOINT,
            "profile": DEFAULT_PROFILE,
            "hint": "Пароль показан один раз и на маршрутизаторе не читается панелью. "
                    "Передайте его получателю лично или ссылкой."}


def set_disabled(name: str, disabled: bool) -> dict:
    """Выключить (и выбить текущую сессию) или включить учётку. Не удаляем:
    выключение обратимо, а удалённую учётку партнёра не восстановить."""
    if not NAME_RE.match(name or "") and not re.match(r"^[\w.@<>-]{1,64}$", name or ""):
        raise ValueError("недопустимое имя")
    with Session() as s:
        if s.run(f':put [/ppp secret print count-only where name="{name}"]').strip() != "1":
            raise ValueError(f"учётки «{name}» нет")
        s.run(f'/ppp secret set [find name="{name}"] disabled={"yes" if disabled else "no"}')
        kicked = 0
        if disabled:
            kicked = int(s.run(f':put [/ppp active print count-only where name="{name}"]') or 0)
            s.run(f'/ppp active remove [find name="{name}"]')
        state = s.run(f':put [/ppp secret get [find name="{name}"] disabled]').strip()
    return {"name": name, "disabled": state == "true", "sessions_closed": kicked}


def l2tp_psk() -> str:
    """Общий ключ IPsec L2TP-сервера — только для ссылки получателя, сразу в шифр."""
    with Session() as s:
        return s.run(":put [/interface l2tp-server server get ipsec-secret]").strip()
