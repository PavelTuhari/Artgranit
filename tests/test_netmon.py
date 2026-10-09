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
    start = src.index("def vault(")
    vault = src[start:src.index("    @staticmethod", start)]   # только сам метод vault()
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


# ---------------------------------------- модуль только во внутренней сети

def test_module_is_off_unless_explicitly_enabled():
    """На публичном сервере модуля быть не должно — даже если код туда приехал.

    Выключено по умолчанию: без NETMON_ENABLED=1 маршруты не импортируются
    вовсе. Если кто-то «упростит» это до проверки внутри маршрута, модуль
    снова окажется на nufarul за одним лишь логином.
    """
    src = _read("modules/netmon/__init__.py")
    assert 'os.environ.get("NETMON_ENABLED", "").strip() == "1"' in src
    assert "if ENABLED:\n    from modules.netmon import routes" in src, \
        "маршруты должны импортироваться только при включённом флаге"


def test_source_network_check_covers_every_route():
    """Проверка сети — на весь blueprint, а не на отдельные маршруты."""
    src = _read("modules/netmon/routes.py")
    assert "@blueprint.before_request" in src
    assert "abort(404)" in src, "снаружи не должно быть видно, что модуль есть"


def test_source_allowed_networks():
    import importlib, os
    os.environ["NETMON_ENABLED"] = "1"
    import modules.netmon as pkg
    importlib.reload(pkg)
    from modules.netmon import routes
    for ok in ("127.0.0.1", "::1", "192.168.0.57", "10.8.0.6"):
        assert routes.source_allowed(ok), f"отклонён свой адрес {ok}"
    for bad in ("93.115.136.18", "92.5.3.187", "8.8.8.8", "192.168.1.5",
                "10.9.0.1", "", "мусор", "2001:db8::1"):
        assert not routes.source_allowed(bad), f"пропущен чужой адрес {bad!r}"


# ------------------------------------------- отзыв доступа OpenVPN

def test_crl_unreadable_means_revocation_does_not_work():
    from modules.netmon import openvpn as ov
    crl = ov._parse_crl({"CRLREAD": ["path=/x/pki/crl.pem", "user=nobody",
                                     "readable=no", "serials=23"]})
    assert crl["works"] is False and crl["serials"] == 23


def test_crl_readable_means_revocation_works():
    from modules.netmon import openvpn as ov
    crl = ov._parse_crl({"CRLREAD": ["path=/etc/openvpn/server/crl.pem",
                                     "user=nobody", "readable=yes", "serials=23"]})
    assert crl["works"] is True


def test_crl_missing_from_config_is_not_working():
    from modules.netmon import openvpn as ov
    assert ov._parse_crl({})["works"] is False


def test_revoke_fixes_crl_permissions_and_reports_effect():
    """gen-crl создаёт файл 0600 — служба под nobody перестаёт его читать.

    И отзыв обязан честно сказать, подействовал ли он: снаружи отзыв
    выглядит выполненным, даже когда доступ у человека остался.
    """
    src = _read("modules/netmon/openvpn.py")
    assert "chmod 644 {EASYRSA}/pki/crl.pem" in src
    assert '"effective"' in src and "доступ НЕ закрыт" in src


def test_ssh_reuses_one_connection():
    """Серия входов подряд выглядит как подбор пароля и ловит блокировку."""
    for f in ("modules/netmon/openvpn.py", "modules/netmon/frontoffice.py"):
        assert "ControlMaster=auto" in _read(f), f


# ---------------------------------------- выдача доступа из панели

def test_panel_post_sends_request_body():
    """Регрессия 04.10.2026: post() молча выбрасывала тело запроса.

    Выдача OpenVPN и запись работ по оборудованию уходили на сервер пустыми
    и падали на валидации имени. Из интерфейса это выглядело как «ошибка»
    без причины.
    """
    import re
    html = _read("modules/netmon/templates/netmon.html")
    m = re.search(r"async function post\(([^)]*)\)\{(.*?)\n\}", html, re.S)
    assert m, "функция post() не найдена"
    args, body = m.group(1), m.group(2)
    assert "body" in args, "post() должна принимать тело запроса"
    assert "JSON.stringify(body)" in body and "application/json" in body


def test_profile_download_does_not_issue_new_certificate():
    """Повторное скачивание профиля не должно выпускать сертификат заново."""
    import re
    src = _read("modules/netmon/routes.py")
    m = re.search(r"def api_vpn_profile\(name\):(.*?)(?:\n\n\n|\Z)", src, re.S)
    assert m and "vpn_profile(name)" in m.group(1)
    assert "vpn_create" not in m.group(1)


def test_profile_template_inserts_name_in_cert_and_key():
    from modules.netmon import openvpn as ov
    cmd = ov._PROFILE_CMD.format(name="ivan.petrov")
    assert "issued/ivan.petrov.crt" in cmd and "private/ivan.petrov.key" in cmd
    assert cmd.startswith("{ ") and cmd.rstrip().endswith("} 2>/dev/null")


def test_incomplete_profile_is_rejected():
    import pytest
    from modules.netmon import openvpn as ov
    with pytest.raises(RuntimeError):
        ov._profile_result("x", "client\n<ca></ca><cert></cert><key></key>")


# ------------------------------------------------------------- MikroTik

def test_mikrotik_name_rejects_injection():
    """Имя подставляется в команду RouterOS."""
    from modules.netmon import mikrotik as mt
    for bad in ('a"; /system reboot', "a b", "a]", "a[", "a$x", "", "a;b", "имя", "a" * 40):
        assert not mt.NAME_RE.match(bad), bad
    assert mt.NAME_RE.match("ivan.petrov") and mt.NAME_RE.match("Tudor_2")


def test_mikrotik_password_is_alnum_and_long():
    from modules.netmon import mikrotik as mt
    pw = {mt.new_password() for _ in range(30)}
    assert len(pw) == 30 and all(len(p) == 16 and p.isalnum() for p in pw)


def test_mikrotik_record_parsing_traps():
    """Три ловушки разбора вывода RouterOS, пойманные 06.10.2026."""
    from modules.netmon import mikrotik as mt
    f = ["name", "service", "comment"]
    # многострочный комментарий склеивается, а не ломает запись
    r = mt._record("ivan\x1fl2tp\x1fстрока1\r\nстрока2\x1f~\r\n", f)
    assert r == {"name": "ivan", "service": "l2tp", "comment": "строка1 строка2"}
    # пустое последнее поле не теряется благодаря явному «~»
    assert mt._record("ivan\x1fl2tp\x1f\x1f~", f)["comment"] == ""
    # обрыв записи распознаётся, а не превращается в мусор
    assert mt._record("ivan\x1fl2tp", f) is None


def test_mikrotik_uses_uppercase_hex_separator_and_safe_strip():
    src = _read("modules/netmon/mikrotik.py")
    assert '"\\\\1F"' in src and '"\\\\1f"' not in src, "RouterOS понимает только \\1F"
    assert 'out.strip(" \\r\\n\\t")' in src, ".strip() срезает 0x1E/0x1F — терялась первая запись"


def test_mikrotik_never_counts_with_print_count_only():
    """`:put [… print count-only]` печатает число дважды — сравнение с 0 ломается."""
    import re
    src = _read("modules/netmon/mikrotik.py")
    assert not re.search(r"run\([^)]*print count-only", src)


def test_mikrotik_never_prints_secrets():
    """print в RouterOS v6 выводит пароли PPP и ключ IPsec открытым текстом."""
    import re
    src = _read("modules/netmon/mikrotik.py")
    cmds = re.findall(r'run\(f?["\']([^"\']+)', src)
    for c in cmds:
        assert not re.search(r"/(ppp secret|interface l2tp-server server|ip ipsec \w+) print(?! count)", c), c
    # ключ IPsec читается ровно в одном месте — для ссылки получателя
    assert src.count("ipsec-secret") == 1, "ключ IPsec читается только в l2tp_psk()"


def test_mikrotik_new_users_are_l2tp_only():
    src = _read("modules/netmon/mikrotik.py")
    assert "service=l2tp" in src and "service=pptp" not in src


def test_mikrotik_reset_refuses_pptp_only_accounts():
    src = _read("modules/netmon/mikrotik.py")
    assert 'not in ("l2tp", "any")' in src


def test_mikrotik_ssh_avoids_broken_rsa_host_key():
    src = _read("modules/netmon/mikrotik.py")
    assert '"ssh-rsa"' in src and "disabled_algorithms" in src
    assert ">= 4" in src, "paramiko 4 не умеет DSA — должна быть явная проверка версии"


def test_mikrotik_ros_date():
    from modules.netmon import mikrotik as mt
    assert mt._ros_date("oct/06/2026 14:11:50") == "2026-10-06"
    assert mt._ros_date("jan/01/1970 00:00:00") == ""


def test_mikrotik_findings_flag_pptp():
    from modules.netmon import mikrotik as mt
    d = {"users": [], "active": [{"name": "a", "service": "pptp"}, {"name": "b", "service": "l2tp"}],
         "servers": {"pptp": True}, "version": "6.45.5 (stable)"}
    titles = " ".join(f["title"] for f in mt.findings(d))
    assert "PPTP" in titles and "6.45.5" in titles


def test_mikrotik_disable_revokes_only_l2tp_links():
    src = _read("modules/netmon/controller.py")
    assert 'kind="l2tp"' in src and 'kind="openvpn"' in src


# --------------------------------------------- файловые ресурсы 192.168.0.21

def test_fs_login_from_email():
    import pytest
    from modules.netmon import fileshare as fs
    assert fs.login_from_email("Ivan.Petrov@unisim-soft.com") == "ivan-petrov"
    assert fs.login_from_email("o_tuhari@unisim-soft.com") == "o_tuhari"
    for bad in ("ivan@gmail.com", "ivan@unisim-soft.com.evil.md", "; rm -rf /@unisim-soft.com",
                "", "@unisim-soft.com", "a b@unisim-soft.com"):
        with pytest.raises(ValueError):
            fs.login_from_email(bad)


def test_fs_policy_matches_owner_decision():
    """06.10.2026: U, K, T — только администрация, I, X, M — все три группы."""
    ddl = _read("modules/netmon/sql/203_nmon_fs.sql")
    import re
    pol = set(re.findall(r"VALUES \('(\w+)', '(admin|consult|support)'\)", ddl))
    for share in ("unisim", "uni_bank", "st8"):
        assert {r for s, r in pol if s == share} == {"admin"}, share
    for share in ("docs", "shares", "db"):
        assert {r for s, r in pol if s == share} == {"admin", "consult", "support"}, share
    drives = dict(re.findall(r"VALUES \('(\w+)', '([A-Z])'", ddl))
    assert drives == {"unisim": "U", "uni_bank": "K", "st8": "T", "docs": "I", "shares": "X", "db": "M"}


def test_fs_effective_open_share_lets_everyone_in():
    """Без valid users в ресурс входит любой — так сейчас устроены U, I, M, T."""
    from modules.netmon import fileshare as fs
    e = fs.effective({"read only": "No", "admin users": "netuser"}, ["a", "netuser"], {})
    assert e["open_to_all"] and e["enter"] == ["a", "netuser"] and e["root"] == ["netuser"]


def test_fs_effective_groups_and_junk():
    from modules.netmon import fileshare as fs
    sh = {"valid users": '"@shares read", ivan', "read list": '"@shares read"  ; all from folder clients',
          "read only": "No"}
    e = fs.effective(sh, ["ivan", "petr", "maria"], {"shares read": ["petr"]}, known={"ivan", "petr", "maria"})
    assert e["enter"] == ["ivan", "petr"] and e["write"] == ["ivan"]
    assert {"all", "from", "folder", "clients"} <= set(e["junk"]), "встроенный «комментарий» — мусор"


_FS_POLICY = {"roles": {"admin": {"title": "А", "group": "fs_administratia"},
                        "consult": {"title": "К", "group": "fs_consult_prog"}},
              "shares": [{"name": "unisim", "drive": "U", "roles": ["admin"]},
                         {"name": "docs", "drive": "I", "roles": ["admin", "consult"]}]}
_FS_CONF = ("[global]\n\tworkgroup = INTERNAL\n\tsecurity = ADS\n"
            "[docs]\n   path = /storage/docs\n   admin users = netuser\n   ;valid users = x\n   read only = No\n"
            "[unisim]\n   path = /storage/unisim\n   admin users = \"@domain admins\", netuser\n"
            "\tread list = \"@unisim read\"\n[other]\n   valid users = keep-me\n")


def test_fs_render_is_reversible_and_idempotent():
    """revert(render(x)) == x байт в байт: панель не трогает ничего лишнего."""
    from modules.netmon import fs_policy as fp
    for mode in fp.MODES:
        new = fp.render(_FS_CONF, _FS_POLICY, mode, ("netuser",), "2026-10-06")
        assert fp.revert(new) == _FS_CONF, mode
        again = fp.render(new, _FS_POLICY, mode, ("netuser",), "2026-10-07")
        assert again.count(fp.BEGIN) == 2 and fp.revert(again) == _FS_CONF
        assert "valid users = keep-me" in new, "чужие ресурсы не трогаются"


def test_fs_transition_keeps_legacy_and_root():
    from modules.netmon import fs_policy as fp
    new = fp.render(_FS_CONF, _FS_POLICY, "transition", ("netuser", "netadmin"), "2026-10-06")
    assert "valid users = @fs_administratia, netuser, netadmin" in new
    assert "valid users = @fs_administratia, @fs_consult_prog, netuser, netadmin" in new
    assert '\n   admin users = "@domain admins", netuser' in new, "root-права в переходном режиме не меняются"


def test_fs_final_drops_legacy_and_root():
    from modules.netmon import fs_policy as fp
    new = fp.render(_FS_CONF, _FS_POLICY, "final", ("netuser",), "2026-10-06")
    assert "valid users = @fs_administratia\n" in new
    active = [l for l in new.split("\n") if not l.startswith(";") and "admin users" in l]
    assert not active, "в финальном режиме root-права убраны"


def test_fs_impact_transition_cuts_nobody_working():
    from modules.netmon import fs_policy as fp
    status = {"shares": [{"name": "unisim", "open_to_all": True, "local_enter": ["netuser", "tester"]},
                         {"name": "docs", "open_to_all": True, "local_enter": ["netuser", "tester"]}],
              "local_users": [{"login": "netuser"}, {"login": "tester"}],
              "role_groups": {"admin": ["ivan"], "consult": ["maria"]},
              "sessions": {"netuser": ["pc1", "pc2"]}, "domain_users": 424}
    imp = {i["name"]: i for i in fp.impact(status, _FS_POLICY, "transition", ("netuser",))}
    assert imp["unisim"]["machines_cut"] == [] and imp["unisim"]["lose"] == ["tester"]
    assert "ivan" in imp["unisim"]["gain"] and "maria" not in imp["unisim"]["gain"]
    assert "maria" in imp["docs"]["gain"]
    fin = {i["name"]: i for i in fp.impact(status, _FS_POLICY, "final", ("netuser",))}
    assert fin["unisim"]["machines_cut"] == ["pc1", "pc2"], "финальный режим честно показывает, кого отрежет"


def test_fs_apply_guards():
    src = _read("modules/netmon/fileshare.py")
    assert "md5 != expected_md5" in src, "применение только по свежему пробному расчёту"
    assert "testparm -s {tmp}" in src and "cp -a {CONF} {backup}" in src
    assert "reload-config" in src and "restart" not in src.split("def apply")[1].split("def backups")[0]
    routes = _read("modules/netmon/routes.py")
    assert 'body.get("confirm") != "ПРИМЕНИТЬ"' in routes


def test_fs_accounts_have_no_shell_and_password_via_stdin():
    src = _read("modules/netmon/fileshare.py")
    assert "-s /sbin/nologin" in src, "учётки сотрудников — без входа в систему"
    assert 'smbpasswd -s -a {login}", stdin=' in src, "пароль не должен попадать в командную строку"


def test_fs_ddl_has_no_semicolons_in_comments_and_tz_times():
    import re
    ddl = _read("modules/netmon/sql/203_nmon_fs.sql")
    for line in ddl.splitlines():
        if line.strip().startswith("--"):
            assert ";" not in line, line
    assert re.search(r"CREATED_AT\s+TIMESTAMP WITH TIME ZONE", ddl)


def test_smb_cmd_handles_error_1219_and_literal_findstr():
    from modules.vpnguide import rules
    cfg = {"server": "192.168.0.21", "netbios": "CENTOS666", "login": "ivan", "password": "Abc1",
           "drives": [{"drive": "I", "share": "docs"}]}
    c = rules.smb_cmd(cfg)
    assert "findstr /i /l /c:" in c, "буквальный поиск: точки в адресе"
    assert "cmdkey /add:192.168.0.21 /user:CENTOS666\\ivan" in c
    assert c.index("/delete") < c.index("cmdkey /add"), "сначала снять старые подключения (ошибка 1219)"
    assert c.startswith("@echo off") and "\r\n" in c


def test_smb_payload_rejects_cmd_metacharacters():
    import pytest
    from modules.vpnguide import rules
    for bad in ("a&b", 'a"b', "a b", "a%b", "a^b", "a|b", "a>b"):
        with pytest.raises(ValueError):
            rules.smb_payload("192.168.0.21", "CENTOS666", "ivan", bad, [{"drive": "I", "share": "docs"}])


# ------------------------------------------- нагрузка сервера баз данных

def _dl_act(**kw):
    from modules.netmon import dbload as dl
    base = dict(sid="10", serial="5", username="APP", osuser="u", machine="pc", program="p", module="m",
                sql_id="abc", event="", wait_class="", state="WAITED SHORT TIME", seconds_in_wait="0",
                call_seconds="1", blocking_session="", spid="100", cpu_cs="500", phys_reads="7")
    base.update({k: str(v) for k, v in kw.items()})
    return "ACT" + dl.SEP + dl.SEP.join(base[f] for f in dl._ACT)


def test_dbload_idle_active_sessions_are_not_counted():
    """Исполнители заданий висят ACTIVE в ожидании класса Idle — это не работа."""
    from modules.netmon import dbload as dl
    lines = [_dl_act(sid=1, state="WAITING", wait_class="Idle", event="jobq slave wait"),
             _dl_act(sid=2, state="WAITED KNOWN TIME", wait_class="User I/O"),
             _dl_act(sid=3, state="WAITING", wait_class="User I/O", event="db file sequential read")]
    d = dl.parse_db("cloudbd", lines)
    assert [a["sid"] for a in d["active"]] == [2, 3]
    assert d["active"][0]["on_cpu"] and not d["active"][1]["on_cpu"]
    assert d["active"][0]["cpu_seconds"] == 5, "CPU used by this session — в сотых долях секунды"


def test_dbload_blocking_and_long_calls_become_findings():
    from modules.netmon import dbload as dl
    db = dl.parse_db("cloudbd", [
        _dl_act(sid=7, state="WAITING", wait_class="Application", event="enq: TX - row lock contention",
                seconds_in_wait=120, blocking_session=42),
        _dl_act(sid=8, call_seconds=2400, sql_id="zzz")])
    host = {"load1": 2, "cores": 16, "cpu": {"idle": 80, "iowait": 1}, "mem": {"available_pct": 60}, "disks": []}
    f = dl.findings(host, [db])
    titles = " ".join(x["title"] for x in f)
    assert "ждёт блокировку от сессии 42" in titles
    assert any(x["level"] == "crit" and "40 мин" in x["title"] for x in f), "дольше 30 минут — опасно"
    assert db["active"][0]["kill"].startswith("ALTER SYSTEM KILL SESSION '7,5'")


def test_dbload_host_parsing_vmstat_iostat_top():
    from modules.netmon import dbload as dl
    sec = {"LOADAVG": ["3.15 3.43 3.47 2/665 1343", "16"],
           "VMSTAT": [" 3  0 311252 13686484 168952 30109704  0  0  363  230 7829 6797 18  1 81  0  0"],
           "MEM": ["64155 39020", "31999 303"],
           "IOSTAT": ["sdb 0.00 0.00 120.0 30.0 5.5 0.4 30.0 0.8 6.1 6.0 6.5 2.0 52.3",
                      "dm-0 0 0 0 0 0 0 0 0 0 0 0 0 0"],
           "TOP": [" 3708 oracle    20   0 8521m 1.2g 1.1g R  94.1  1.9   0:12.34 oracleCLOUDBD (LOCAL=NO)"]}
    h = dl.parse_host(sec)
    assert h["cores"] == 16 and h["cpu"]["idle"] == 81 and h["mem"]["available_pct"] == 61
    assert [d["device"] for d in h["disks"]] == ["sdb"], "dm-* — дубли логических томов"
    assert h["disks"][0]["role"].startswith("/db") and h["disks"][0]["util_pct"] == 52.3
    assert h["top"][0]["pid"] == "3708" and h["top"][0]["cpu_pct"] == 94.1


def test_dbload_uses_top_not_ps_for_current_cpu():
    """ps -o pcpu — среднее за жизнь процесса: долгая сессия выглядит тихой."""
    src = _read("modules/netmon/dbload.py")
    assert "top -b -n 2 -d 2" in src and "p.spid in (&pids)" in src


def test_dbload_never_kills_sessions():
    import re
    src = _read("modules/netmon/dbload.py")
    sql = src[src.index('_SQL = r"""'):src.index('_SH = r"""')]
    assert not re.search(r"^\s*alter\s+system", sql, re.I | re.M), "только чтение"
    assert "kill" not in _read("modules/netmon/routes.py").split("def api_dbload")[1]


def test_dbload_zabbix_items_are_float_and_thresholds_from_module():
    src = _read("modules/netmon/scripts/netmon_zabbix_storage.py")
    assert '"value_type": 3' not in src
    assert "dl.LONG_CALL_CRIT" in src and "dl.LOAD_PER_CORE_CRIT" in src


# ------------------------------------------------- серьёзное наблюдение

_PROC = """@@STAT
cpu  1000 0 200 8000 100 0 0 0 0 0
procs_running 3
procs_blocked 1
@@LOAD
2.90 3.10 3.20 2/600 999
@@MEM
MemTotal:       65695744 kB
MemAvailable:   39960576 kB
SwapTotal:      32767996 kB
SwapFree:       32457724 kB
@@DISK
   8      16 sdb 1000 0 80000 500 200 0 16000 300 0 900 800 0 0 0 0
   8      17 sdb1 999 0 79999 499 199 0 15999 299 0 899 799 0 0 0 0
 253       0 dm-0 5 0 5 5 5 0 5 5 0 5 5 0 0 0 0
@@NET
  eth0: 1048576 100 0 0 0 0 0 0 2097152 200 0 0 0 0 0 0
    lo: 999999 9 0 0 0 0 0 0 999999 9 0 0 0 0 0 0
@@END"""


def _proc_later():
    return (_PROC.replace("cpu  1000 0 200 8000 100", "cpu  1600 0 300 9100 200")
                 .replace("sdb 1000 0 80000 500 200 0 16000 300 0 900",
                          "sdb 1100 0 100480 700 300 0 18048 500 0 2400")
                 .replace("eth0: 1048576", "eth0: 3145728").replace("0 2097152 200", "0 4194304 200"))


def test_observe_host_delta_from_proc_counters():
    from modules.netmon import observe_sampler as s
    a, b = s.parse_host_raw(_PROC), s.parse_host_raw(_proc_later())
    assert list(a["disks"]) == ["sdb"], "только целые устройства: без разделов и dm-*"
    assert a["net_rx"] == 1048576, "lo не считается"
    d = s.delta(a, b, dt=2.0)
    # из 1900 тиков: польз 600, сист 100, простой 1100, ожидание 100
    assert (d["cpu_user"], d["cpu_system"], d["cpu_iowait"]) == (31.6, 5.3, 5.3)
    disk = d["disks"][0]
    assert disk["util_pct"] == 75.0, "io_ticks 1500 мс за 2 с"
    assert disk["r_s"] == 50.0 and disk["w_s"] == 50.0
    assert disk["read_mb_s"] == 5.0 and disk["await_ms"] == 2.0
    assert d["net_rx_kbs"] == 1024.0 and d["mem_used_pct"] == 39.2


def test_observe_db_rates_from_sysstat_deltas():
    from modules.netmon import observe_sampler as s
    raw1 = "SYS@@physical reads@@1000\nSYS@@execute count@@500\nSYS@@CPU used by this session@@10000\nCNT@@200@@5@@3@@1@@40"
    raw2 = "SYS@@physical reads@@3000\nSYS@@execute count@@2500\nSYS@@CPU used by this session@@14000\nCNT@@201@@6@@4@@0@@12"
    a, b = s.parse_db_raw("cloudbd", raw1), s.parse_db_raw("cloudbd", raw2)
    d = s.db_delta(a, b, dt=10, cpu_count=16)
    assert d["phys_reads_s"] == 200.0 and d["executions_s"] == 200.0
    assert d["db_cpu_pct"] == 25.0, "40 с процессора за 10 с на 16 ядрах = 25 % сервера"
    assert (d["sessions"], d["active"], d["on_cpu"], d["blocked"], d["longest_call"]) == (201, 6, 4, 0, 12)


def test_observe_session_line_parsing():
    from modules.netmon import observe_sampler as s
    d = s.parse_db_raw("cloudbd", "SES@@924@@5@@UNWEBSHOP@@web4@@php@@abc@@@@1@@3@@\n"
                                  "SES@@7@@1@@APP@@pc@@x@@def@@enq: TX - row lock contention@@0@@120@@42")
    assert d["sessions"][0]["on_cpu"] and d["sessions"][0]["blocking_session"] is None
    assert d["sessions"][1]["blocking_session"] == 42 and d["sessions"][1]["call_seconds"] == 120


def test_observe_settings_limits_and_persistence(tmp_path, monkeypatch):
    import pytest
    from modules.netmon import observe_store as st
    monkeypatch.setattr(st, "DB_PATH", tmp_path / "o.sqlite")
    assert st.get_settings()["interval_sec"] == 30, "по умолчанию — 30 секунд"
    assert st.save_settings({"interval_sec": 3})["interval_sec"] == 3
    assert st.get_settings()["interval_sec"] == 3, "настройка сохраняется"
    for bad in (2, 301, "abc"):
        with pytest.raises(ValueError):
            st.save_settings({"interval_sec": bad})


def test_observe_series_keeps_peaks_when_downsampling(tmp_path, monkeypatch):
    """Длинное окно сжимается: сессии и блокировки — по максимуму, иначе пик пропадёт."""
    import time
    from modules.netmon import observe_store as st
    monkeypatch.setattr(st, "DB_PATH", tmp_path / "o.sqlite")
    now = time.time()
    for i in range(60):
        ts = now - 600 + i * 10
        st.save_sample({"ts": ts, "interval": 10, "cpu_user": 10, "cpu_system": 1, "cpu_iowait": 0,
                        "cpu_idle": 89, "cpu_steal": 0, "load1": 2, "load5": 2, "procs_running": 1,
                        "procs_blocked": 0, "mem_used_pct": 40, "mem_available_mb": 1, "swap_used_mb": 0,
                        "net_rx_kbs": 1, "net_tx_kbs": 1, "collect_ms": 900, "disks": [],
                        "dbs": [{"db": "cloudbd", "sessions": 200, "active": 30 if i == 31 else 2,
                                 "on_cpu": 1, "blocked": 5 if i == 31 else 0, "longest_call": 1,
                                 "db_cpu_pct": 10, "phys_reads_s": 1, "logical_reads_s": 1,
                                 "executions_s": 1, "commits_s": 1, "redo_kbs": 1}],
                        "sessions": []})
    s = st.series(minutes=11, points=6)
    assert len(s["host"]["t"]) <= 7
    assert max(s["dbs"]["cloudbd"]["active"]) == 30 and max(s["dbs"]["cloudbd"]["blocked"]) == 5


def test_observe_single_instance_and_start_race():
    worker = _read("modules/netmon/scripts/netmon_observe.py")
    assert "fcntl.LOCK_EX | fcntl.LOCK_NB" in worker, "второй экземпляр должен выходить"
    assert 'max_hours' in worker, "забытое наблюдение должно остановиться само"
    ctl = _read("modules/netmon/controller.py")
    start = ctl[ctl.index("def observe_start"):ctl.index("def observe_stop")]
    assert "set_control(pid=proc.pid" in start, "номер процесса — сразу, иначе гонка"
    assert "start_new_session=True" in start


def test_observe_cache_lives_outside_repository():
    from modules.netmon import observe_store as st
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert not str(st.DB_PATH).startswith(root), "кэш наблюдения — не в репозитории"
    assert "ЭТО КЭШ, А НЕ ХРАНИЛИЩЕ" in _read("modules/netmon/observe_store.py")
