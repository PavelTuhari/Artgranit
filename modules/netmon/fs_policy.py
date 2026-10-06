"""Политика доступа → новый smb.conf и расчёт последствий. Чистые функции.

Правка файла бережная:

* трогаются только шесть ресурсов из политики и только строки прав
  (valid/invalid users, admin users, read/write list);
* старые строки прав не удаляются, а комментируются с пометкой
  `;netmon-<дата>;` — в самом файле видно, что было до панели;
* новые права пишутся помеченным блоком `# netmon:begin … # netmon:end`;
  при повторном применении заменяется только он.

Два режима:

* `transition` (переходный) — входят роли из политики И общие учётки
  netuser/netadmin/ptuhari, под которыми сейчас работает вся компания.
  root-права (admin users) не меняются. Никто из работающих не отключится,
  но личные учётки уже действуют, а остальные 424 пользователя домена
  перестают проходить на открытые сейчас U, I, M, T;
* `final` — только роли; общие учётки и root-права убраны. Включать, когда
  все переведены на личные учётки (панель показывает, кто ещё сидит под
  общими).
"""
from __future__ import annotations

import re

RIGHTS_KEYS = ("valid users", "invalid users", "admin users", "read list", "write list")
BEGIN, END = "# netmon:begin", "# netmon:end"
MODES = ("transition", "final")


def managed(share: dict, roles: dict, mode: str, legacy: tuple[str, ...]) -> dict[str, str]:
    """Строки прав, которые панель ставит в ресурс."""
    if mode not in MODES:
        raise ValueError(f"неизвестный режим: {mode}")
    groups = [f"@{roles[r]['group']}" for r in share["roles"]]
    if not groups:
        raise ValueError(f"у ресурса {share['name']} в политике нет ни одной роли")
    who = groups + (list(legacy) if mode == "transition" else [])
    return {"valid users": ", ".join(who)}


def render(conf: str, policy: dict, mode: str, legacy: tuple[str, ...], stamp: str) -> str:
    """Новый текст smb.conf. Остальной файл — байт в байт как был."""
    targets = {s["name"].lower(): s for s in policy["shares"]}
    keep_keys = ("admin users",) if mode == "transition" else ()
    out, section, in_block = [], None, False
    lines = conf.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if m:
            section = m.group(1).strip().lower()
            out.append(line)
            if section in targets:
                sh = targets[section]
                out.append(f"   {BEGIN} {stamp} режим {mode}: права выдаёт панель, руками не править")
                for k, v in managed(sh, policy["roles"], mode, legacy).items():
                    out.append(f"   {k} = {v}")
                out.append(f"   {END}")
            continue
        if section not in targets:
            out.append(line)
            continue
        s = line.strip()
        if s.startswith(BEGIN):
            in_block = True          # прежний блок панели — заменён новым выше
            continue
        if in_block:
            if s.startswith(END):
                in_block = False
            continue
        key = re.match(r"^\s*([a-z][a-z ]*?)\s*=", line, re.I)
        if key and key.group(1).strip().lower() in RIGHTS_KEYS \
                and key.group(1).strip().lower() not in keep_keys:
            out.append(f";netmon-{stamp}; {s}")
            continue
        out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------- последствия

def _allowed(login: str, share: dict, roles: dict, member_of: dict[str, list[str]],
             mode: str, legacy: tuple[str, ...]) -> bool:
    if mode == "transition" and login in legacy:
        return True
    return any(login in member_of.get(roles[r]["group"], []) for r in share["roles"])


def impact(status: dict, policy: dict, mode: str, legacy: tuple[str, ...]) -> list[dict]:
    """Что изменится для каждого ресурса: кто потеряет вход, кто получит,
    сколько компьютеров с открытыми сейчас подключениями отрежет."""
    roles = policy["roles"]
    member_of = {roles[c]["group"]: m for c, m in status.get("role_groups", {}).items()}
    by_name = {s["name"].lower(): s for s in status.get("shares", [])}
    accounts = sorted({u["login"] for u in status.get("local_users", [])}
                      | {u for m in member_of.values() for u in m})
    sessions = status.get("sessions", {})
    out = []
    for sh in policy["shares"]:
        cur = by_name.get(sh["name"].lower(), {})
        now = set(cur.get("local_enter", []))
        new = {a for a in accounts if _allowed(a, sh, roles, member_of, mode, legacy)}
        lose = sorted(now - new)
        out.append({
            "name": sh["name"], "drive": sh["drive"],
            "roles": [roles[r]["title"] for r in sh["roles"]],
            "open_to_all_now": cur.get("open_to_all", False),
            "domain_users_now": status.get("domain_users", 0) if cur.get("open_to_all") else None,
            "keep": sorted(now & new), "lose": lose, "gain": sorted(new - now),
            "machines_cut": sorted({m for u in lose for m in sessions.get(u, [])}),
            "root_after": cur.get("local_root", []) if mode == "transition" else [],
        })
    return out
