"""Файловые ресурсы офиса на 192.168.0.21: кто куда входит и выдача прав.

Сервер — CentOS 6.9, Samba 3.6.23 (`21.centos6`, виртуальная машина на
PROXMOX3). Сам ничего не хранит: раздаёт по SMB каталоги, примонтированные
по NFS с гипервизора (`/storage`, `/st8`) и с cloudbd (`/sda`).

Шесть ресурсов, которые у сотрудников стоят дисками:

    U: \\\\192.168.0.21\\unisim    I: \\\\192.168.0.21\\docs     X: \\\\192.168.0.21\\shares
    M: \\\\192.168.0.21\\db        K: \\\\192.168.0.21\\uni_bank T: \\\\192.168.0.21\\st8

Почему права — локальными учётками, а не через домен
----------------------------------------------------
Сервер введён в домен INTERNAL.UNIACC.MD (security = ADS), но связи с
доменом у него нет: `net ads testjoin` → «No logon servers». У контроллера
192.168.0.104 закрыт 445, у 192.168.0.103 — Kerberos и LDAP, 192.168.17.6
недоступен. Samba держится на кэше winbind, и права, выданные через группы
AD, до ресурсов не дойдут. Реально входят только локальные учётки
(`pdbedit -L`: netadmin, netuser, ptuhari, ivantesting). Поэтому сотрудники
получают ЛОКАЛЬНЫЕ учётки на этом сервере, а роли — локальные группы Unix.
Когда домен починят, роли можно перенести в AD без смены политики ресурсов.

Учёт людей — по почте @unisim-soft.com (Oracle, NMON_FS_*). Имя входа
выводится из почты: точки в именах пользователей CentOS 6 недопустимы.

Учётки сотрудников создаются БЕЗ входа в систему (/sbin/nologin): только
SMB. Общие netuser/netadmin заведены с /bin/bash — так делать не надо.

Подключение — root по SSH, пароль в Keychain (pve-21.centos6).
"""
from __future__ import annotations

import re
import secrets
import string
import subprocess
from datetime import datetime

HOST = "192.168.0.21"
KEYCHAIN_SERVICE = "pve-21.centos6"
EMAIL_DOMAIN = "unisim-soft.com"

# Роли: код → (название, группа Unix). Группы с префиксом fs_, чтобы не
# пересечься с группами домена, которые winbind тоже показывает.
ROLES = {
    "admin": ("Администрация", "fs_administratia"),
    "consult": ("Консультанты и программисты", "fs_consult_prog"),
    "support": ("Инженеры техподдержки", "fs_support"),
}

# Политика владельца (06.10.2026): U, K, T — только администрация,
# I, X, M — все три группы.
SHARES = [
    # (ресурс, диск, роли с доступом)
    ("unisim", "U", ("admin",)),
    ("uni_bank", "K", ("admin",)),
    ("st8", "T", ("admin",)),
    ("docs", "I", ("admin", "consult", "support")),
    ("shares", "X", ("admin", "consult", "support")),
    ("db", "M", ("admin", "consult", "support")),
]

# Общие учётки, под которыми сейчас работает вся компания. В переходном
# режиме политики их доступ сохраняется, иначе все отключатся разом.
LEGACY_ACCOUNTS = ("netuser", "netadmin", "ptuhari")

EMAIL_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,40}@" + re.escape(EMAIL_DOMAIN) + "$")
LOGIN_RE = re.compile(r"^[a-z_][a-z0-9_-]{1,31}$")
_PW_ALPHABET = string.ascii_letters + string.digits


def keychain() -> str:
    r = subprocess.run(["security", "find-generic-password", "-a", "root",
                        "-s", KEYCHAIN_SERVICE, "-w"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


class Session:
    """Одно SSH-соединение на серию команд."""

    def __enter__(self):
        import paramiko
        pw = keychain()
        if not pw:
            raise RuntimeError(f"нет пароля root файлового сервера в Keychain ({KEYCHAIN_SERVICE})")
        self.c = paramiko.SSHClient()
        self.c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.c.connect(HOST, username="root", password=pw, timeout=15,
                       look_for_keys=False, allow_agent=False)
        return self

    def __exit__(self, *exc):
        self.c.close()

    def run(self, cmd: str, timeout: int = 90, stdin: str | None = None) -> tuple[int, str]:
        i, o, e = self.c.exec_command(cmd, timeout=timeout)
        if stdin is not None:
            i.write(stdin)
            i.channel.shutdown_write()
        out = (o.read() + e.read()).decode("utf-8", "replace")
        return o.channel.recv_exit_status(), out.rstrip()


# ------------------------------------------------------------- почта и вход

def login_from_email(email: str) -> str:
    """ivan.petrov@unisim-soft.com → ivan-petrov."""
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError(f"нужна почта вида имя@{EMAIL_DOMAIN}")
    login = re.sub(r"[^a-z0-9_-]", "-", email.split("@")[0]).strip("-")[:32]
    if not LOGIN_RE.match(login):
        raise ValueError(f"из почты не получается имя входа: {login!r}")
    return login


def new_password(length: int = 14) -> str:
    return "".join(secrets.choice(_PW_ALPHABET) for _ in range(length))


# --------------------------------------------------------- разбор smb.conf

def _list(v: str) -> list[str]:
    """Список Samba: через запятую или пробел, имена в кавычках с пробелами."""
    return [x.strip().strip('"') for x in re.findall(r'"[^"]*"|[^,\s]+', v or "") if x.strip(",")]


def parse_share(text: str) -> dict:
    """Вывод `testparm -s --section-name=X` → словарь параметров."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"^\s*([a-z][a-z ]+?)\s*=\s*(.*)$", line)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def _member(name: str, entries: list[str], groups: dict[str, list[str]]) -> bool:
    for e in entries:
        e0 = e.lower()
        if e0.startswith(("@", "+", "&")):
            if name in groups.get(e0.lstrip("@+&"), []):
                return True
        elif e0 == name:
            return True
    return False


def effective(share: dict, users: list[str], groups: dict[str, list[str]]) -> dict:
    """Кто входит, кто пишет, кто root — по правилам Samba 3.6.

    Если `valid users` не задан, входит ЛЮБОЙ прошедший проверку пользователь.
    """
    valid = _list(share.get("valid users", ""))
    invalid = _list(share.get("invalid users", ""))
    admin = _list(share.get("admin users", ""))
    read_list = _list(share.get("read list", ""))
    write_list = _list(share.get("write list", ""))
    ro = share.get("read only", "Yes").lower() in ("yes", "true", "1")
    res = {"open_to_all": not valid, "enter": [], "write": [], "root": []}
    for u in users:
        if _member(u, invalid, groups):
            continue
        if valid and not _member(u, valid, groups):
            continue
        res["enter"].append(u)
        if _member(u, admin, groups):
            res["root"].append(u)
        writes = (not ro and not _member(u, read_list, groups)) or _member(u, write_list, groups)
        if writes or _member(u, admin, groups):
            res["write"].append(u)
    # мусор в списках: слова, которые не являются ни пользователем, ни группой
    known = set(users) | {"@" + g for g in groups}
    res["junk"] = sorted({e for e in valid + admin + read_list + write_list + invalid
                          if not e.startswith(("@", "+", "&")) and e.lower() not in known})
    res["groups_without_at"] = sorted({e for e in valid + admin + read_list
                                       if not e.startswith(("@", "+", "&")) and e.lower() in groups})
    return res


# ---------------------------------------------------------------- состояние

_STATE = r"""
echo '===USERS==='; pdbedit -L 2>/dev/null | cut -d: -f1
echo '===FLAGS==='; pdbedit -Lv 2>/dev/null | awk -F': *' '/^Unix username/{u=$2} /^Account Flags/{print u "|" $2}'
echo '===GROUPS==='; for g in %(groups)s; do echo "$g|$(getent group $g | cut -d: -f4)"; done
echo '===SESSIONS==='; smbstatus -b 2>/dev/null | awk 'NR>4 && NF>=4 {print $2 "|" $4}' | sort -u
echo '===SHARESESS==='; smbstatus -S 2>/dev/null | awk 'NR>3 && NF>=3 {print $1 "|" $2}'
echo '===DF==='; df -P -m /storage /st8 /sda 2>/dev/null | tail -n +2
echo '===JOIN==='; timeout 20 net ads testjoin 2>&1 | tail -1
echo '===CONF==='; stat -c '%%y' /etc/samba/smb.conf
"""


def _sections(raw: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    key = None
    for line in raw.splitlines():
        m = re.match(r"^===(\w+)===$", line.strip())
        if m:
            key = m.group(1)
            out[key] = []
        elif key:
            out[key].append(line)
    return out


def status() -> dict:
    with Session() as s:
        shares_raw = {}
        for name, *_ in SHARES:
            _, txt = s.run(f"testparm -s --section-name={name} 2>/dev/null")
            shares_raw[name] = parse_share(txt)
        # группы, упомянутые в шести ресурсах, + наши ролевые
        mentioned = set()
        for sh in shares_raw.values():
            for k in ("valid users", "invalid users", "admin users", "read list", "write list"):
                mentioned |= {e.lstrip("@+&") for e in _list(sh.get(k, "")) if e.startswith(("@", "+", "&"))}
        mentioned |= {g for _, g in ROLES.values()}
        qg = " ".join(f"'{g}'" for g in sorted(mentioned))
        _, raw = s.run(_STATE % {"groups": qg}, timeout=120)
    sec = _sections(raw)
    local_users = [u.strip() for u in sec.get("USERS", []) if u.strip()]
    flags = dict(l.split("|", 1) for l in sec.get("FLAGS", []) if "|" in l)
    groups = {}
    for l in sec.get("GROUPS", []):
        g, _, m = l.partition("|")
        groups[g.lower()] = [x for x in m.split(",") if x]
    sessions = {}
    for l in sec.get("SESSIONS", []):
        u, _, mach = l.partition("|")
        sessions.setdefault(u, set()).add(mach)
    share_sess = {}
    for l in sec.get("SHARESESS", []):
        sh, _, pid = l.partition("|")
        share_sess[sh.lower()] = share_sess.get(sh.lower(), 0) + 1
    # все, кого Samba может впустить по настройке: локальные + члены групп
    universe = sorted(set(local_users) | {u for m in groups.values() for u in m})
    shares = []
    for name, letter, roles in SHARES:
        sh = shares_raw.get(name, {})
        eff = effective(sh, universe, groups)
        eff_local = effective(sh, local_users, groups)
        shares.append({
            "name": name, "letter": letter, "path": sh.get("path", ""),
            "target_roles": list(roles),
            "target_title": ", ".join(ROLES[r][0] for r in roles),
            "valid_users": sh.get("valid users", ""), "admin_users": sh.get("admin users", ""),
            "read_only": sh.get("read only", ""),
            "open_to_all": eff["open_to_all"],
            "enter_count": len(eff["enter"]), "root": eff["root"],
            "local_enter": eff_local["enter"], "local_root": eff_local["root"],
            "junk": eff["junk"], "groups_without_at": eff["groups_without_at"],
            "sessions": share_sess.get(name.lower(), 0),
        })
    disks = []
    for l in sec.get("DF", []):
        f = l.split()
        if len(f) >= 6:
            total, used = int(f[1]), int(f[2])
            disks.append({"mount": f[5], "source": f[0], "total_gb": round(total / 1024),
                          "free_gb": round((total - used) / 1024),
                          "percent": round(used * 100 / total) if total else 0})
    return {
        "host": HOST,
        "domain_join": (sec.get("JOIN") or [""])[-1].strip(),
        "domain_ok": "is OK" in " ".join(sec.get("JOIN", [])),
        "smb_conf_changed": (sec.get("CONF") or [""])[0][:16],
        "local_users": [{"login": u, "disabled": "D" in flags.get(u, ""),
                         "machines": sorted(sessions.get(u, []))} for u in local_users],
        "role_groups": {code: groups.get(g, []) for code, (_, g) in ROLES.items()},
        "role_groups_exist": {code: g in groups and groups[g] is not None
                              for code, (_, g) in ROLES.items()},
        "sessions": {u: sorted(m) for u, m in sessions.items()},
        "shares": shares, "disks": disks,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def findings(d: dict) -> list[dict]:
    out = []
    if not d.get("domain_ok"):
        out.append({"level": "crit", "title": "Сервер потерял связь с доменом",
                    "text": f"net ads testjoin: «{d.get('domain_join')}». Samba держится на кэше; "
                            "личные учётки домена не входят. Права выдаются локальными учётками."})
    legacy = {u: m for u, m in d.get("sessions", {}).items() if u in LEGACY_ACCOUNTS}
    if legacy:
        n = sum(len(m) for m in legacy.values())
        out.append({"level": "crit",
                    "title": f"Сотрудники работают под общими учётками: {', '.join(legacy)} ({n} компьютеров)",
                    "text": "Один пароль на всех: нельзя понять, кто что удалил, и нельзя отключить "
                            "одного человека. Переводить на личные учётки по одному."})
    for sh in d.get("shares", []):
        if sh["open_to_all"]:
            out.append({"level": "crit",
                        "title": f"{sh['letter']}: \\\\{HOST}\\{sh['name']} — входит любой пользователь домена, с записью",
                        "text": f"Нет ограничения valid users. Должно быть: {sh['target_title']}."})
        if sh["local_root"]:
            out.append({"level": "warn",
                        "title": f"{sh['letter']}: работают как root — {', '.join(sh['local_root'])}",
                        "text": "admin users отключает все права файловой системы для этих учёток."})
        if sh["junk"]:
            out.append({"level": "info", "title": f"{sh['letter']}: мусор в списках — {', '.join(sh['junk'])}",
                        "text": "Слова, которые не являются ни пользователем, ни группой."})
    for disk in d.get("disks", []):
        if disk["percent"] >= 90:
            out.append({"level": "crit" if disk["percent"] >= 97 else "warn",
                        "title": f"{disk['mount']} заполнен на {disk['percent']} %, свободно {disk['free_gb']} ГБ",
                        "text": f"Источник {disk['source']}. На нём ресурсы "
                                + ", ".join(f"{s['letter']}:" for s in d.get("shares", [])
                                            if s["path"].startswith(disk["mount"])) + "."})
    return out


# ------------------------------------------------------- изменения на сервере

def ensure_role_groups() -> dict:
    """Создаёт локальные группы ролей, если их нет. Безопасно: никого не трогает."""
    created = []
    with Session() as s:
        for _, g in ROLES.values():
            rc, _ = s.run(f"getent group {g} >/dev/null")
            if rc != 0:
                rc, out = s.run(f"groupadd {g}")
                if rc != 0:
                    raise RuntimeError(f"не создалась группа {g}: {out[:120]}")
                created.append(g)
    return {"created": created}


def create_account(login: str, role: str, password: str) -> None:
    """Учётка Unix без входа в систему + учётка Samba + группа роли."""
    if not LOGIN_RE.match(login) or role not in ROLES:
        raise ValueError("недопустимое имя или роль")
    group = ROLES[role][1]
    with Session() as s:
        rc, _ = s.run(f"getent passwd {login} >/dev/null")
        if rc == 0:
            raise ValueError(f"учётка {login} на сервере уже есть")
        rc, out = s.run(f"useradd -M -d /nonexistent -s /sbin/nologin -g {group} "
                        f"-c 'netmon fileshare' {login}")
        if rc != 0:
            raise RuntimeError(f"useradd: {out[:160]}")
        # пароль — через stdin, не в командной строке: его видно в ps
        rc, out = s.run(f"smbpasswd -s -a {login}", stdin=f"{password}\n{password}\n")
        if rc != 0:
            s.run(f"userdel {login}")
            raise RuntimeError(f"smbpasswd: {out[:160]}")


def set_role(login: str, role: str) -> None:
    if not LOGIN_RE.match(login) or role not in ROLES:
        raise ValueError("недопустимое имя или роль")
    with Session() as s:
        rc, out = s.run(f"usermod -g {ROLES[role][1]} {login}")
        if rc != 0:
            raise RuntimeError(f"usermod: {out[:160]}")


def set_disabled(login: str, disabled: bool) -> dict:
    """smbpasswd -d/-e. Текущие подключения рвём: иначе выключенный человек
    продолжал бы работать до перезагрузки своего компьютера."""
    if not LOGIN_RE.match(login) or login in LEGACY_ACCOUNTS:
        raise ValueError("недопустимое имя (общие учётки выключаются отдельно, при переходе)")
    with Session() as s:
        rc, out = s.run(f"smbpasswd -{'d' if disabled else 'e'} {login}")
        if rc != 0:
            raise RuntimeError(f"smbpasswd: {out[:160]}")
        closed = 0
        if disabled:
            _, pids = s.run(f"smbstatus -b 2>/dev/null | awk 'NR>4 && $2==\"{login}\" {{print $1}}' | sort -u")
            for pid in pids.split():
                if pid.isdigit():
                    s.run(f"kill {pid}")
                    closed += 1
    return {"login": login, "disabled": disabled, "sessions_closed": closed}


def reset_password(login: str, password: str) -> None:
    if not LOGIN_RE.match(login) or login in LEGACY_ACCOUNTS:
        raise ValueError("недопустимое имя")
    with Session() as s:
        rc, out = s.run(f"smbpasswd -s {login}", stdin=f"{password}\n{password}\n")
        if rc != 0:
            raise RuntimeError(f"smbpasswd: {out[:160]}")
