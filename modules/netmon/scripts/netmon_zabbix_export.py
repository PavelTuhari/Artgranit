#!/usr/bin/env python3
"""Выгрузка конфигурации действующего Zabbix — для миграции и как резервная копия.

    python modules/netmon/scripts/netmon_zabbix_export.py --out ./zbx-export
    python modules/netmon/scripts/netmon_zabbix_export.py --out ./zbx-export --inventory-only

Забирает через API всё, что придётся воссоздавать на новом сервере:
шаблоны и хосты в XML (родной формат экспорта 3.4), а также действия,
пользователей,媒 media types, группы, скрипты и настройки — в JSON.
Ничего не меняет: только чтение.

План миграции: docs/Netmon/ZABBIX_MIGRATION_PLAN.md
Пароль Zabbix: security find-generic-password -a Admin -s zabbix-web -w
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from modules.netmon import sources  # noqa: E402

# Что выгружаем в JSON: метод API → (имя файла, параметры)
JSON_DUMPS = {
    "hostgroup": ("groups.json", {"output": "extend"}),
    "action": ("actions.json", {"output": "extend", "selectFilter": "extend",
                                "selectOperations": "extend",
                                "selectRecoveryOperations": "extend"}),
    "mediatype": ("mediatypes.json", {"output": "extend"}),
    "usergroup": ("usergroups.json", {"output": "extend", "selectRights": "extend"}),
    "user": ("users.json", {"output": ["userid", "alias", "name", "surname",
                                       "type", "lang", "theme"],
                            "selectMedias": "extend", "selectUsrgrps": ["name"]}),
    "script": ("scripts.json", {"output": "extend"}),
    "drule": ("discovery_rules.json", {"output": "extend", "selectDChecks": "extend"}),
    "maintenance": ("maintenance.json", {"output": "extend"}),
    "proxy": ("proxies.json", {"output": "extend"}),
}


def dump(path: Path, data) -> int:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path.stat().st_size


def export_xml(z, out: Path, kind: str, ids: list[str], chunk: int = 25) -> list[str]:
    """Экспорт хостов или шаблонов в XML пачками: целиком 3.4 отдаёт долго."""
    files = []
    for i in range(0, len(ids), chunk):
        part = ids[i:i + chunk]
        xml = z.call("configuration.export", {
            "format": "xml",
            "options": {kind: part},
        })
        f = out / f"{kind}_{i // chunk + 1:02d}.xml"
        f.write_text(xml, encoding="utf-8")
        files.append(f.name)
        print(f"   {f.name}: {len(part)} шт., {f.stat().st_size // 1024} КБ")
    return files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="каталог для выгрузки")
    ap.add_argument("--inventory-only", action="store_true",
                    help="только сводка по объектам, без экспорта XML")
    ap.add_argument("--chunk", type=int, default=25, help="сколько объектов в одном XML")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    z = sources.Zabbix()
    print(f"Выгрузка конфигурации Zabbix → {out}\n")

    # --- сводка по объектам ---
    hosts = z.call("host.get", {"output": ["hostid", "host", "name", "status"],
                                "selectInterfaces": ["ip", "type", "port"],
                                "selectGroups": ["name"],
                                "selectParentTemplates": ["host"]})
    templates = z.call("template.get", {"output": ["templateid", "host", "name"]})
    items = z.call("item.get", {"output": ["itemid", "type", "status", "state"],
                                "templated": False})

    by_type: dict[str, int] = {}
    broken = 0
    for it in items:
        by_type[it["type"]] = by_type.get(it["type"], 0) + 1
        if it.get("state") == "1" and it.get("status") == "0":
            broken += 1

    inventory = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "zabbix_api": z.call("apiinfo.version", {}) if False else None,
        "hosts": len(hosts),
        "templates": len(templates),
        "items_own": len(items),
        "items_broken": broken,
        "items_by_type": by_type,
        "host_list": [{"host": h["host"], "name": h["name"], "status": h["status"],
                       "ip": (h.get("interfaces") or [{}])[0].get("ip", ""),
                       "groups": [g["name"] for g in h.get("groups", [])],
                       "templates": [t["host"] for t in h.get("parentTemplates", [])]}
                      for h in sorted(hosts, key=lambda x: x["host"])],
    }
    dump(out / "inventory.json", inventory)
    print(f"  inventory.json: хостов {len(hosts)}, шаблонов {len(templates)}, "
          f"своих элементов {len(items)} (сломано {broken})")

    # --- справочники в JSON ---
    for method, (fname, params) in JSON_DUMPS.items():
        try:
            data = z.call(f"{method}.get", params)
            size = dump(out / fname, data)
            print(f"  {fname}: {len(data)} записей, {size // 1024 or 1} КБ")
        except Exception as e:  # noqa: BLE001 — часть методов может быть недоступна
            print(f"  {fname}: пропущено ({str(e)[:70]})")

    if a.inventory_only:
        print("\nрежим --inventory-only: XML не выгружался")
        return

    # --- XML-экспорт шаблонов и хостов ---
    print("\nЭкспорт шаблонов:")
    tpl_files = export_xml(z, out, "templates", [t["templateid"] for t in templates], a.chunk)
    print("Экспорт хостов:")
    host_files = export_xml(z, out, "hosts", [h["hostid"] for h in hosts], a.chunk)

    # --- памятка по восстановлению ---
    (out / "README.txt").write_text(
        "Выгрузка конфигурации Zabbix 3.4 для миграции\n"
        f"Снята: {datetime.now():%d.%m.%Y %H:%M}\n\n"
        f"inventory.json   — сводка и полный список хостов ({len(hosts)} шт.)\n"
        "groups.json      — группы хостов, создать первыми\n"
        f"templates_*.xml  — шаблоны ({len(templates)} шт.), импортировать до хостов\n"
        f"hosts_*.xml      — хосты, импортировать после шаблонов\n"
        "actions.json     — действия; создаются вручную, API-формат 3.4 и 8.0 отличается\n"
        "mediatypes.json  — типы оповещений; пароли и токены в выгрузку НЕ попадают\n"
        "users.json       — учётные записи и их media; пароли не выгружаются\n"
        "scripts.json     — скрипты действий\n\n"
        "Порядок восстановления: группы → шаблоны → хосты → действия → пользователи.\n"
        "Внешние скрипты (/usr/lib/zabbix/externalscripts) и alert-скрипты\n"
        "переносятся отдельно, файлами: в API их содержимого нет.\n"
        "Полный план: docs/Netmon/ZABBIX_MIGRATION_PLAN.md\n", encoding="utf-8")

    total = sum(f.stat().st_size for f in out.iterdir() if f.is_file())
    print(f"\nготово: {len(list(out.iterdir()))} файлов, {total // 1024} КБ в {out}")


if __name__ == "__main__":
    main()
