"""Тесты модуля netmon.

Первые два — обязательные тесты изоляции (CLAUDE.md, правило №1): модуль не
должен оставлять следов в общем коде. Остальные проверяют чистые правила
классификации и разбора алертов — без Oracle, без VPN, без wallet.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ изоляция

def test_shared_app_py_does_not_mention_the_module():
    # Модуль подключает ядро; в app.py ему делать нечего.
    assert not re.search(r"\bnetmon\b", _read("app.py")), \
        "app.py упоминает модуль — нарушена изоляция"


def test_shared_deploy_script_is_untouched_by_the_module():
    src = _read("deploy_oracle_objects.py")
    assert "NMON_" not in src and "netmon" not in src.lower(), \
        "общий установщик знает о модуле — у модуля есть свой netmon_deploy.py"


def test_module_exports_blueprint_named_after_key():
    from modules.netmon import blueprint
    assert blueprint.name == "netmon"


def test_template_takes_base_url_from_url_for():
    # Адрес портала строкой в шаблоне запрещён (CLAUDE.md, правило №1 п.2)
    html = _read("modules/netmon/templates/netmon.html")
    assert "url_for('netmon.api_overview')" in html
    assert "http://" not in html.split("<script>")[1] or "127.0.0.1" not in html


# ------------------------------------------------------------------ классификация

def test_proxmox_is_detected_by_its_web_port():
    from modules.netmon import rules
    assert rules.classify(63, [22, 8006], "", "") == rules.KIND_HYPERVISOR


def test_camera_needs_both_rtsp_and_http_api_ports():
    from modules.netmon import rules
    assert rules.classify(63, [554, 8000], "", "") == rules.KIND_CAMERA
    # один только RTSP — ещё не камера
    assert rules.classify(63, [554], "", "") != rules.KIND_CAMERA


def test_windows_workstation_is_detected_by_rdp():
    from modules.netmon import rules
    assert rules.classify(127, [3389, 445], "", "") == rules.KIND_WIN_WS


def test_network_gear_is_detected_by_high_ttl_without_ports():
    from modules.netmon import rules
    # TTL 255 (в пути 254) — признак коммутатора, принтера или IP-телефона
    assert rules.classify(254, [], "", "") == rules.KIND_NETGEAR


def test_page_title_overrides_port_guess():
    from modules.netmon import rules
    # по портам это был бы обычный Linux-веб, но заголовок говорит прямо
    assert rules.classify(63, [22, 80], "RouterOS router configuration page", "") \
        == rules.KIND_ROUTER


def test_oracle_server_is_more_important_than_a_workstation():
    from modules.netmon import rules
    assert rules.criticality(rules.KIND_ORACLE) == rules.CRIT_HIGH
    assert rules.criticality(rules.KIND_WIN_WS) == rules.CRIT_LOW


def test_ip_sorting_is_numeric_not_lexicographic():
    from modules.netmon import rules
    ips = ["192.168.0.100", "192.168.0.9", "192.168.0.21"]
    assert sorted(ips, key=rules.ip_key) == \
        ["192.168.0.9", "192.168.0.21", "192.168.0.100"]


def test_host_name_prefers_dns_then_falls_back_to_class_and_octet():
    from modules.netmon import rules
    assert rules.host_name("192.168.0.24", rules.KIND_ORACLE,
                           dns="cloudbd.internal.uniacc.md") == "cloudbd"
    assert rules.host_name("192.168.0.150", rules.KIND_CAMERA) == "cam-150"


# ------------------------------------------------------------------ алерты и каналы

def test_resolved_message_is_not_counted_as_a_problem():
    from modules.netmon import rules
    # «RESOLVED: …» несёт то же слово Warning в теле, но это закрытие проблемы
    assert rules.alert_severity("RESOLVED: cloudbd | 192.168.0.24") == "resolved"
    assert rules.alert_severity("Warning: cloudbd | 192.168.0.24") == "warning"
    assert rules.alert_severity("Disaster: cloudbd | 192.168.0.24") == "disaster"


def test_host_is_extracted_from_the_alert_subject():
    from modules.netmon import rules
    assert rules.alert_host("Warning: cloudbd | 192.168.0.24") == "cloudbd"
    assert rules.alert_host("RESOLVED: apache | 192.168.0.148") == "apache"


def test_channel_kind_tells_channel_from_group_by_id_prefix():
    from modules.netmon import rules
    assert rules.channel_kind("-1001544437696") == "channel"
    assert rules.channel_kind("-621328357") == "group"


def test_every_severity_has_an_emoji():
    from modules.netmon import rules
    for sev in ("disaster", "high", "average", "warning", "information", "resolved", "other"):
        assert rules.SEVERITY_EMOJI.get(sev)


# ------------------------------------------------------------------ схема и секреты

def test_ddl_declares_every_table_and_wraps_plsql_with_slashes():
    ddl = _read("modules/netmon/sql/200_nmon_tables.sql")
    for t in ("NMON_SCANS", "NMON_DEVICES", "NMON_TG_CHANNELS", "NMON_TG_ALERTS"):
        assert f"CREATE TABLE {t}" in ddl, t
        assert f"{t}_SEQ" in ddl, t
    # '/' обязателен и ПЕРЕД, и ПОСЛЕ каждого PL/SQL-блока (CLAUDE.md §2 п.5)
    triggers = ddl.count("CREATE OR REPLACE TRIGGER")
    assert triggers == 4
    assert ddl.count("\n/\n") >= triggers


def test_alert_table_deduplicates_by_zabbix_alert_id():
    ddl = _read("modules/netmon/sql/200_nmon_tables.sql")
    assert "UK_NMON_TG_ALERT UNIQUE (ZBX_ALERTID)" in ddl


def test_no_bot_token_is_hardcoded_in_the_module():
    # Токен бота живёт только в скрипте на сервере Zabbix, в репозиторий не копируется
    for rel in ("modules/netmon/sources.py", "modules/netmon/store.py",
                "modules/netmon/controller.py", "modules/netmon/rules.py",
                "modules/netmon/scripts/netmon_zabbix_sync.py",
                "modules/netmon/templates/netmon.html"):
        assert not re.search(r"[0-9]{8,}:[A-Za-z0-9_-]{30,}", _read(rel)), f"токен в {rel}"


def test_secrets_come_from_keychain_not_from_code():
    src = _read("modules/netmon/sources.py")
    assert "find-generic-password" in src
    assert "zabbix-web" in src  # имя записи Keychain, не сам пароль


# ------------------------------------------------------------------ миграция

def test_migration_plan_names_the_blocking_versions():
    # План обязан называть конкретные версии-блокеры, а не «всё устарело»
    doc = _read("docs/Netmon/ZABBIX_MIGRATION_PLAN.md")
    for fact in ("3.4.15", "7.9.2009", "5.5.68", "5.6.40", "Proxmox VE **4.4-1**"):
        assert fact.replace("**", "") in doc.replace("**", ""), fact


def test_migration_plan_covers_rollback_and_acceptance():
    doc = _read("docs/Netmon/ZABBIX_MIGRATION_PLAN.md")
    for section in ("План отката", "Тесты приёмки", "Технические требования",
                    "Стратегия переноса данных"):
        assert section in doc, section


def test_export_tool_is_read_only():
    # Инструмент выгрузки не должен уметь менять Zabbix
    src = _read("modules/netmon/scripts/netmon_zabbix_export.py")
    for danger in (".create", ".update", ".delete", "configuration.import"):
        assert danger not in src, f"экспорт умеет {danger} — должен только читать"
    assert "configuration.export" in src


# ------------------------------------------------------------------ Proxmox

def test_credentials_from_vm_descriptions_are_never_exposed():
    # В описаниях ВМ на PROXMOX3 записаны пары «логин/пароль» — ни одна
    # не должна попасть ни в базу, ни на панель.
    from modules.netmon import proxmox
    raw = "IP: 192.168.0.1\nAuth: root/s3cretpass\nRole: сервер\nadmin/qwerty123"
    clean = proxmox._strip_secrets(raw)
    assert "s3cretpass" not in clean and "qwerty123" not in clean
    assert "192.168.0.1" in clean and "сервер" in clean


def test_masked_field_keeps_useful_values():
    from modules.netmon import proxmox
    assert proxmox._mask_secret("role", "сервер печати") == "сервер печати"
    assert "скрыт" in proxmox._mask_secret("auth", "root/pass")


def test_cyrillic_description_decodes_correctly():
    from modules.netmon import proxmox
    # Proxmox хранит описание percent-encoded; кириллица — многобайтовая
    assert proxmox._unescape_description("%D0%A1%D0%B5%D1%80%D0%B2%D0%B5%D1%80") == "Сервер"
    assert proxmox._unescape_description("a%0Ab") == "a\nb"


def test_legacy_os_guest_is_not_proposed_for_plain_migration():
    from modules.netmon import proxmox
    g = {"vmid": 1, "ostype": "winxp", "status": "running", "last_backup": "2026-09-01",
         "description": "", "disk_gb": 20, "memory_mb": 2048, "onboot": True}
    p = proxmox.passport(g)
    assert p["legacy_os"] and p["decision"] == proxmox.DECISION_REPLACE
    assert p["risk_level"] == "high"


def test_unused_stopped_guest_is_proposed_for_retirement():
    from modules.netmon import proxmox
    g = {"vmid": 2, "ostype": "l26", "status": "stopped", "last_backup": "2020-01-01",
         "description": "not used", "disk_gb": 10, "memory_mb": 512, "onboot": False}
    assert proxmox.passport(g)["decision"] == proxmox.DECISION_RETIRE


def test_guest_without_backup_is_high_risk():
    from modules.netmon import proxmox
    g = {"vmid": 3, "ostype": "l26", "status": "running", "last_backup": "",
         "description": "", "disk_gb": 10, "memory_mb": 1024, "onboot": True}
    p = proxmox.passport(g)
    assert p["risk_level"] == "high"
    assert any("резервной копии нет" in r for r in p["risks"])


def test_pve_ddl_uses_character_semantics_for_cyrillic_columns():
    # Oracle считает VARCHAR2 в байтах: «пересоздать на новой ОС» = 43 байта
    ddl = _read("modules/netmon/sql/201_nmon_pve.sql")
    for col in ("DECISION", "RISKS", "NOTES", "DESCR", "ROLE_HINT"):
        assert re.search(rf"{col}\s+VARCHAR2\(\d+ CHAR\)", ddl), col
