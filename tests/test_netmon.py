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


# ------------------------------------------------------------------ активы и энергия

def test_cpu_thresholds_follow_intel_spec_not_blynk_emoji():
    # Пороги 52 °C были взяты из эмодзи Blynk-бота и оказались занижены:
    # для Xeon E5-26xx v3 Tcase = 72,6 °C, троттлинг около 85 °C.
    doc = _read("modules/netmon/assets.py")
    assert "73" in doc and "85" in doc


def test_domain_expiry_levels():
    from modules.netmon import assets
    assert assets.domain_level(10) == "critical"
    assert assets.domain_level(30) == "critical"      # ровно месяц — уже срочно
    assert assets.domain_level(60) == "warning"
    assert assets.domain_level(365) == "ok"
    assert assets.domain_level(None) == "unknown"     # реестр .eu не отдаёт дату


def test_domains_without_known_date_are_not_pushed_to_zabbix():
    # Отправить 0 значило бы поднять ложную тревогу «регистрация истекла»
    from modules.netmon import assets
    vals = assets.domain_values([
        {"domain": "a.md", "days_left": 100},
        {"domain": "b.eu", "days_left": None},
    ])
    assert "domain.days[a.md]" in vals and "domain.days[b.eu]" not in vals


def test_energy_counts_only_hours_outside_working_time():
    from modules.netmon import assets
    e = assets.energy_waste(1, watt=100, tariff=3.0)
    assert e["idle_hours_week"] == 118          # 168 − 50
    assert e["kwh_week"] == 11.8
    assert e["mdl_year"] > 0


def test_energy_scales_with_machine_count():
    from modules.netmon import assets
    one = assets.energy_waste(1)["mdl_year"]
    ten = assets.energy_waste(10)["mdl_year"]
    # округление идёт на каждом расчёте, поэтому сравниваем с допуском
    assert abs(ten - one * 10) <= 10


def test_vault_never_returns_password_values():
    # Панель показывает, какой доступ есть и как достать его из Keychain,
    # но не сами значения.
    src = _read("modules/netmon/controller.py")
    vault = src[src.index("def vault("):src.index("def _vault_group")]
    # проверяем наличие пароля только там, где он был бы значением,
    # а не в названии команды security find-*-password
    cleaned = vault.replace("find-generic-password", "").replace("find-internet-password", "")
    assert "kc_get" in vault, "статус доступа должен проверяться"
    assert '"password"' not in cleaned and "'password'" not in cleaned, \
        "панель не должна отдавать значения паролей"


def test_vault_file_must_live_outside_the_repository():
    src = _read("modules/netmon/scripts/netmon_vault.py")
    assert "внутри репозитория" in src and "0o600" in src


# ------------------------------------------------------------------ оборудование офиса

def test_no_reserved_word_as_bind_variable_name():
    # ORA-01745: BY зарезервировано в Oracle (GROUP BY / ORDER BY).
    # Ловушка уже стоила отладки в TBControl, см. CLAUDE.md.
    src = _read("modules/netmon/store.py")
    reserved = (":by", ":level", ":order", ":group", ":size", ":comment", ":date")
    for word in reserved:
        assert f"{word})" not in src and f"{word}," not in src, \
            f"{word} — зарезервированное слово Oracle в имени bind-переменной"


def test_service_state_marks_overdue():
    from datetime import date, timedelta
    from modules.netmon import facility as fac
    today = date(2026, 9, 12)
    assert fac.service_state(today - timedelta(days=120), 90, today)["level"] == "overdue"
    assert fac.service_state(today - timedelta(days=10), 90, today)["level"] == "ok"
    assert fac.service_state(None, 90, today)["level"] == "unknown"


def test_service_state_counts_days_overdue():
    from datetime import date, timedelta
    from modules.netmon import facility as fac
    today = date(2026, 9, 12)
    st = fac.service_state(today - timedelta(days=100), 90, today)
    assert st["days_over"] == 10


def test_next_due_follows_regulation():
    from datetime import date
    from modules.netmon import facility as fac
    done = date(2026, 9, 12)
    assert (fac.next_due("filter", "aircon", done) - done).days == 90
    assert (fac.next_due("freon", "aircon", done) - done).days == 730
    assert (fac.next_due("inspect", "elevator", done) - done).days == 30


def test_photo_filename_rejects_foreign_formats_and_paths():
    from modules.netmon import facility as fac
    import pytest
    with pytest.raises(ValueError):
        fac.safe_filename("evil.exe", "AC-01")
    name = fac.safe_filename("../../../etc/passwd.jpg", "AC-01")
    assert "/" not in name and name.endswith(".jpg")


def test_every_office_room_has_its_own_aircon():
    from modules.netmon import facility as fac
    rooms = [f["room"] for f in fac.SEED if f["kind"] == "aircon"]
    assert len(rooms) == 4 and len(set(rooms)) == 4


def test_all_discovered_plugs_are_registered():
    from modules.netmon import facility as fac, smartplug
    codes = {f["ip"] for f in fac.SEED if f["kind"] == "smartplug"}
    assert codes == set(smartplug.KNOWN_PLUGS)


def test_plug_keys_are_read_from_keychain_only():
    # local_key не должен появляться в коде или конфигах
    src = _read("modules/netmon/smartplug.py")
    assert "keychain_pair" in src
    assert "local_key=" not in src.replace("local_key=local_key", "")


def test_zabbix_items_for_days_must_allow_negative_values():
    # value_type 3 (unsigned) превращает отрицательные значения в 0,
    # и просрочка обслуживания никогда бы не показалась.
    src = _read("modules/netmon/scripts/netmon_zabbix_facility.py")
    block = src[src.index('key_": key'):src.index("created += 1")]
    assert '"value_type": 0' in block, "дни до срока должны быть numeric float"


def test_missing_work_does_not_swallow_real_deadlines():
    # Невыполненная работа даёт -интервал, а не «минус бесконечность»,
    # иначе по числу не понять, насколько всё запущено.
    src = _read("modules/netmon/scripts/netmon_zabbix_facility.py")
    assert "-999" not in src
    assert "-days if not last" in src


def test_classifier_detects_smart_plugs_before_ttl_rule():
    from modules.netmon import rules
    # у розеток TTL 255 — без проверки порта они уедут в «сетевое оборудование»
    assert rules.classify(254, [6668]) == rules.KIND_SMARTPLUG
    assert rules.classify(254, [9999]) == rules.KIND_SMARTPLUG
    assert rules.classify(254, []) == rules.KIND_NETGEAR


# ------------------------------------------------------------------ фронт-офисы

def test_service_schemas_are_not_counted_as_front_offices():
    # SYS, XWIKI и учётки мониторинга — не торговые точки
    from modules.netmon import frontoffice as fo
    assert "SYS" in fo.NOT_FRONTOFFICE and "XWIKI" in fo.NOT_FRONTOFFICE
    assert "RETAILMARKETS" not in fo.NOT_FRONTOFFICE


def test_both_databases_are_monitored():
    from modules.netmon import frontoffice as fo
    assert set(fo.DATABASES) == {"cloudbd", "clouddev"}


def test_front_office_trigger_tolerates_restart():
    # Порог nodata должен быть заметно больше времени перезагрузки кассы,
    # иначе каждый перезапуск даёт ложную тревогу.
    src = _read("modules/netmon/scripts/netmon_zabbix_frontoffice.py")
    assert "NODATA_MIN = 30" in src


def test_front_office_items_allow_float():
    src = _read("modules/netmon/scripts/netmon_zabbix_frontoffice.py")
    assert '"value_type": 3' not in src, "unsigned обнуляет отрицательные значения"


def test_handover_covers_every_role():
    doc = _read("docs/Netmon/HANDOVER.md")
    for topic in ("Oracle DBA", "clouddev", "Резервное копирование",
                  "Доступы", "Чего в этом хозяйстве нет"):
        assert topic in doc, f"в передаче дел не хватает раздела: {topic}"


# ------------------------------------------- диски сервера БД (аудит 2021, п. 4.1)

def test_storage_reads_controller_not_only_smart():
    """Главная ловушка раздела: smartctl на логическом томе всегда «OK».

    Если сборщик когда-нибудь «упростят» до smartctl/mdstat, отказ диска в
    аппаратном зеркале снова станет невидимым. Тест держит источник данных.
    """
    src = _read("modules/netmon/storage.py")
    assert "MegaCli64" in src, "состояние надо брать с контроллера, а не с тома"
    for cmd in ("-LDInfo", "-PDList", "GetBbuStatus"):
        assert cmd in src, f"не опрашивается {cmd}"


def test_storage_volume_without_mirror_is_a_finding():
    from modules.netmon import storage as st
    vol = {"id": 0, "name": "", "level": "RAID 0", "size": "2 TB",
           "state": "Optimal", "drives": 1, "cache": "", "bad_blocks": "",
           "ok": True, "mirrored": False}
    f = st.findings({}, [vol], [], [])
    assert any(x["level"] == "crit" for x in f), \
        "том без избыточности обязан быть опасной находкой, даже если Optimal"


def test_storage_offline_disk_is_critical():
    from modules.netmon import storage as st
    disk = {"slot": 3, "state": "Unconfigured(bad)", "model": "ST4000", "size": "3.6 TB",
            "temp": 35, "media_errors": 0, "other_errors": 0, "predictive": 0, "ok": False}
    f = st.findings({}, [], [disk], [])
    assert f and f[0]["level"] == "crit" and "слоте 3" in f[0]["title"]


def test_storage_predictive_failure_is_critical():
    from modules.netmon import storage as st
    disk = {"slot": 1, "state": "Online, Spun Up", "model": "x", "size": "1 TB",
            "temp": 33, "media_errors": 0, "other_errors": 0, "predictive": 2, "ok": True}
    f = st.findings({}, [], [disk], [])
    assert any(x["level"] == "crit" and "предсказано" in x["title"] for x in f), \
        "предсказание отказа важнее исправного состояния: менять до отказа"


def test_storage_healthy_server_has_no_findings():
    from modules.netmon import storage as st
    vol = {"id": 0, "name": "", "level": "RAID 1", "size": "2 TB", "state": "Optimal",
           "drives": 2, "cache": "", "bad_blocks": "No", "ok": True, "mirrored": True}
    disk = {"slot": 0, "state": "Online, Spun Up", "model": "x", "size": "2 TB",
            "temp": 35, "media_errors": 0, "other_errors": 0, "predictive": 0, "ok": True}
    mount = {"mount": "/db", "what": "данные", "percent": 50, "free_gb": 900,
             "level": "ok"}
    adp = {"bbu_present": True, "bbu_ok": True, "roc_temp": 58}
    assert st.findings(adp, [vol], [disk], [mount]) == []


def test_storage_bad_cache_battery_is_reported():
    """Отказ батареи не виден в Oracle: база просто замедляется."""
    from modules.netmon import storage as st
    f = st.findings({"bbu_present": True, "bbu_ok": False, "bbu_state": "Failed"},
                    [], [], [])
    assert any("батарея" in x["title"].lower() or "Батарея" in x["title"] for x in f)


def test_storage_parses_megacli_output():
    from modules.netmon import storage as st
    out = st._sections("""===VD===
Virtual Drive: 1 (Target Id: 1)
Name                :
RAID Level          : Primary-1, Secondary-0, RAID Level Qualifier-0
Size                : 3.637 TB
State               : Optimal
Number Of Drives    : 2
===PD===
Slot Number: 5
Raw Size: 1.819 TB [0xe8e088b0 Sectors]
Firmware state: Online, Spun Up
Inquiry Data:            2426KKYRFTOSHIBA MG03ACA200                      FL1A
Media Error Count: 0
Other Error Count: 0
Predictive Failure Count: 0
Drive Temperature :32C (89.60 F)
===END===""")
    v = st._volumes(out["VD"])[0]
    assert (v["level"], v["state"], v["drives"], v["mirrored"]) == ("RAID 1", "Optimal", 2, True)
    d = st._physical(out["PD"])[0]
    assert (d["slot"], d["ok"], d["temp"]) == (5, True, 32)
    assert "MG03ACA200" in d["model"], "модель диска должна быть читаемой"


def test_storage_mount_names_are_not_mistaken_for_arrays():
    """/mnt/md3 и /mnt/md4 — исторические имена, массивов за ними нет."""
    doc = _read("docs/Netmon/STORAGE.md")
    assert "имена исторические" in doc or "имена историческ" in doc
    assert st_soft_arrays_are_empty_note(doc)


def st_soft_arrays_are_empty_note(doc: str) -> bool:
    return "/proc/mdstat" in doc and "пусто" in doc


# ------------------------------------------------------ OpenVPN

def test_vpn_client_name_rejects_injection():
    """Имя подставляется в команды easy-rsa — набор символов обязан быть узким."""
    from modules.netmon import openvpn as ov
    for bad in ("; rm -rf /", "a b", "../etc", "имя", "-x", "", "a" * 40,
                "a$(id)", "a`id`", "a|b", "a&b"):
        assert not ov.NAME_RE.match(bad), f"пропущено опасное имя: {bad!r}"
    for good in ("ivan", "ivan.petrov", "ap-kassa_2", "A1"):
        assert ov.NAME_RE.match(good), f"отклонено нормальное имя: {good!r}"


def test_vpn_profile_is_never_stored_on_server():
    """Профиль содержит закрытый ключ: он идёт в браузер и нигде не остаётся."""
    src = _read("modules/netmon/openvpn.py")
    assert "закрытый ключ" in src
    routes = _read("modules/netmon/routes.py")
    assert "no-store" in routes, "файл профиля не должен кэшироваться"


def test_vpn_certificate_date_handles_utctime():
    from modules.netmon import openvpn as ov
    assert ov._parse_index_date("300915120000Z") == "2030-09-15"
    assert ov._parse_index_date("991231235959Z") == "1999-12-31"
    assert ov._parse_index_date("") == ""


def test_vpn_status_counts_valid_and_revoked_apart():
    from modules.netmon import openvpn as ov
    data = {"certificates": [{"name": "a", "revoked": False}, {"name": "b", "revoked": True}],
            "clients": [{"name": "a", "mb_received": 1.0, "mb_sent": 2.0}],
            "running": True}
    s = ov.summary(data)
    assert (s["certs_valid"], s["certs_revoked"], s["online"]) == (1, 1, 1)


def test_zabbix_storage_items_allow_negative_values():
    src = _read("modules/netmon/scripts/netmon_zabbix_storage.py")
    assert '"value_type": 3' not in src, "unsigned обнуляет отрицательные значения"


def test_zabbix_storage_alerts_on_lost_redundancy():
    src = _read("modules/netmon/scripts/netmon_zabbix_storage.py")
    for key in ("raid.disks.bad", "raid.redundancy", "raid.bbu.ok", "vpn.service.up"):
        assert key in src, f"нет наблюдения за {key}"


# ------------------------------------------------ разбор аудита 2021

def test_audit_review_covers_every_finding():
    doc = _read("docs/Netmon/AUDIT_2021_REVIEW.md")
    for point in ("2.1.2", "2.1.8", "2.1.10", "3.1.1", "3.1.2", "3.1.3", "3.1.5", "4.1"):
        assert point in doc, f"замечание аудита {point} не разобрано"


def test_audit_review_does_not_claim_raid_is_absent():
    """Ошибка, которую легко повторить: /proc/mdstat пуст → «RAID нет».

    RAID аппаратный. Если в разборе снова появится вывод об отсутствии
    избыточности, значит кто-то опять проверил не тем способом.
    """
    doc = _read("docs/Netmon/AUDIT_2021_REVIEW.md")
    assert "LSI 3108" in doc
    assert "RAID убрали совсем" not in doc
