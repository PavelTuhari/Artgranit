"""Модуль «Инструкция OpenVPN»: изоляция и безопасность содержимого."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------- изоляция

def test_app_py_does_not_mention_the_module():
    # Модуль подключает ядро; общий app.py о нём ничего не знает.
    assert "vpnguide" not in _read("app.py").lower()


def test_shared_deploy_script_is_untouched_by_the_module():
    assert "vpnguide" not in _read("deploy_oracle_objects.py").lower()


def test_blueprint_name_equals_module_key():
    src = _read("modules/vpnguide/__init__.py")
    assert 'Blueprint("vpnguide"' in src


# ------------------------------------------------- содержимое страницы

def test_guide_contains_no_network_addresses_or_keys():
    """Страница работает на публичном сервере — в ней не должно быть ничего,
    что помогает войти в сеть без файла профиля."""
    html = _read("modules/vpnguide/templates/vpnguide.html")
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", html), "в инструкции IP-адрес"
    assert not re.search(r":(1194|4024|8006|22)\b", html), "в инструкции порт сервера"
    for marker in ("BEGIN PRIVATE KEY", "BEGIN CERTIFICATE", "tls-crypt", "<key>",
                   "una.md", "uniacc", "192.168"):
        assert marker not in html, f"в инструкции лишнее: {marker}"


def test_guide_links_only_to_official_sources():
    html = _read("modules/vpnguide/templates/vpnguide.html")
    hosts = set(re.findall(r'href="https?://([^/"]+)', html))
    assert hosts <= {"openvpn.net", "apps.apple.com", "play.google.com"}, hosts


def test_every_platform_has_a_tab_and_a_pane():
    from modules.vpnguide.routes import PLATFORMS
    html = _read("modules/vpnguide/templates/vpnguide.html")
    for key, _ in PLATFORMS:
        assert f'id="p-{key}"' in html, f"нет раздела для {key}"


def test_page_requires_login():
    assert "is_authenticated()" in _read("modules/vpnguide/routes.py")


def test_netmon_panel_links_to_the_guide():
    assert 'url_for("vpnguide.index")' in _read("modules/netmon/routes.py")
    assert "vpn_guide_url" in _read("modules/netmon/templates/netmon.html")


def test_netmon_panel_survives_without_the_guide_module():
    """Регрессия 04.10.2026: url_for на чужой модуль прямо в шаблоне уронил
    панель мониторинга с BuildError, когда сервер работал без vpnguide.
    Ссылка на соседний модуль — только через безопасную обёртку."""
    from flask import Flask
    html = _read("modules/netmon/templates/netmon.html")
    assert "url_for('vpnguide" not in html and 'url_for("vpnguide' not in html
    import importlib, os
    os.environ["NETMON_ENABLED"] = "1"
    import modules.netmon as pkg
    importlib.reload(pkg)
    from modules.netmon import routes
    app = Flask(__name__)
    with app.test_request_context():
        assert routes._vpn_guide_url() is None, "без модуля ссылка должна просто пропасть"


# ------------------------------------------------ ссылки для получателя

def test_ttl_default_and_bounds():
    from modules.vpnguide import rules
    assert rules.ttl(None) == 15 and rules.ttl("") == 15
    assert rules.ttl(1) == 1, "1 == True в Python: одноминутная ссылка не должна стать 15-минутной"
    assert rules.ttl("30") == 30 and rules.ttl(1440) == 1440
    import pytest
    for bad in (0, -5, 1441, "abc", False):
        with pytest.raises(ValueError):
            rules.ttl(bad)


def test_token_is_long_random_and_validated():
    from modules.vpnguide import rules
    toks = {rules.new_token() for _ in range(50)}
    assert len(toks) == 50 and all(rules.token_valid(t) for t in toks)
    for bad in ("", "abc", "A" * 42, "A" * 44, "../../etc/passwd" + "A" * 27, "A" * 42 + "!"):
        assert not rules.token_valid(bad)


def test_profile_is_encrypted_with_key_from_token():
    from modules.vpnguide import rules
    t1, t2 = rules.new_token(), rules.new_token()
    prof = "client\n<key>\n-----BEGIN PRIVATE KEY-----\nSECRET\n-----END PRIVATE KEY-----\n</key>\n"
    ct = rules.encrypt(t1, prof)
    assert "SECRET" not in ct and "PRIVATE" not in ct
    assert rules.decrypt(t1, ct) == prof
    assert rules.decrypt(t2, ct) is None, "чужой токен не должен расшифровывать"
    assert rules.decrypt(t1, ct[:-4] + "AAAA") is None, "подмена шифротекста должна ловиться"


def test_lookup_hash_is_not_the_token_and_not_the_key():
    from modules.vpnguide import rules
    t = rules.new_token()
    h = rules.token_hash(t)
    assert t not in h and len(h) == 64
    import hashlib
    assert h != hashlib.sha256(t.encode()).hexdigest(), "хэш поиска — с собственным префиксом"


def test_markdown_carries_profile_between_markers_and_all_languages():
    import re
    from modules.vpnguide import rules
    prof = "client\nremote x 1194\n<key>\nK\n</key>\n"
    md = rules.markdown("ivan", prof, "10:00 04.10.2026", 15, "https://example/s/T/profile")
    m = re.search(r"-----BEGIN OVPN PROFILE-----\n(.*)\n-----END OVPN PROFILE-----", md, re.S)
    assert m and m.group(1) + "\n" == prof
    for lg in rules.LANGS:
        assert rules.text("title", lg) in md
    for url in (rules.DOWNLOADS["windows"], rules.DOWNLOADS["macos"], rules.DOWNLOADS["site"]):
        assert url in md
    assert rules.profile_sha256(prof) in md


def test_every_text_exists_in_three_languages():
    from modules.vpnguide import rules
    for key, v in rules.T.items():
        assert set(v) == set(rules.LANGS), f"{key}: не хватает языка"


def test_share_pages_do_not_leak_token_in_referer():
    """Со страницы ссылки ведут на openvpn.net, Apple и Google — токен не должен
    уходить им в заголовке Referer."""
    src = _read("modules/vpnguide/routes.py")
    assert '"Referrer-Policy"] = "no-referrer"' in src
    assert "no-store" in src and "noindex" in src
    html = _read("modules/vpnguide/templates/vpnguide_share.html")
    assert '<meta name="referrer" content="no-referrer">' in html


def test_share_pages_do_not_require_login():
    """У получателя учётной записи портала нет."""
    import re
    src = _read("modules/vpnguide/routes.py")
    for fn in ("share_page", "share_profile", "share_markdown"):
        body = re.search(rf"def {fn}\(token\):(.*?)(?:\n\n\n|\Z)", src, re.S).group(1)
        assert "is_authenticated" not in body, fn


def test_db_times_are_timezone_aware():
    """Ссылку создаёт машина в Кишинёве, открывает сервер в UTC."""
    ddl = _read("modules/vpnguide/sql/300_vpng_shares.sql")
    for col in ("CREATED_AT", "EXPIRES_AT", "REVOKED_AT", "HIT_AT"):
        assert re.search(rf"{col}\s+TIMESTAMP WITH TIME ZONE", ddl), col


def test_ddl_comments_have_no_semicolons():
    """Общий разборщик режет по ';' и не понимает комментариев (04.10.2026)."""
    for line in _read("modules/vpnguide/sql/300_vpng_shares.sql").splitlines():
        if line.strip().startswith("--"):
            assert ";" not in line, line


def test_shared_deploy_script_does_not_know_vpng_tables():
    assert "vpng" not in _read("deploy_oracle_objects.py").lower()


def test_revoking_certificate_revokes_its_links():
    src = _read("modules/netmon/controller.py")
    assert "revoke_for_client" in src


def test_page_contains_downloads_and_profile_slots():
    html = _read("modules/vpnguide/templates/vpnguide_share.html")
    for slot in ("dl.windows", "dl.macos", "dl.site", "profile_url", 'id="ovpn-profile"',
                 'id="ovpn-data"', "md_url"):
        assert slot in html, slot


def test_store_disables_parallel_dml():
    """ADB выполняет DML параллельно, и с внешним ключом это ORA-12860 (04.10.2026)."""
    src = _read("modules/vpnguide/store.py")
    assert "ALTER SESSION DISABLE PARALLEL DML" in src
    assert src.count("db.connection.cursor()") == 1, "все курсоры — через _cursor(db)"


# ------------------------------------------------------- ссылки L2TP

def test_l2tp_payload_requires_all_fields():
    import pytest
    from modules.vpnguide import rules
    with pytest.raises(ValueError):
        rules.l2tp_payload("srv", "user", "", "psk")
    cfg = rules.l2tp_settings(rules.l2tp_payload("srv", "user", "pw", "psk"))
    assert cfg == {"server": "srv", "username": "user", "password": "pw", "psk": "psk"}


def test_powershell_quotes_secrets_literally():
    """В двойных кавычках $ и ` в ключе превратились бы в код PowerShell."""
    from modules.vpnguide import rules
    ps = rules.powershell({"server": "s", "username": "u", "password": "p$1`x", "psk": "it's$`"})
    assert "-L2tpPsk 'it''s$`'" in ps and "'p$1`x'" in ps
    assert '"it' not in ps


def test_mobileconfig_routes_all_traffic_and_holds_key():
    import plistlib
    from modules.vpnguide import rules
    p = plistlib.loads(rules.mobileconfig({"server": "s", "username": "u", "password": "p", "psk": "k"}))
    v = p["PayloadContent"][0]
    assert v["VPNType"] == "L2TP" and v["IPSec"]["SharedSecret"] == b"k"
    assert v["IPv4"]["OverridePrimary"] == 1, "без этого офисная сеть 192.168.0.0/24 не откроется"


def test_l2tp_markdown_ends_with_machine_readable_json():
    import json, re
    from modules.vpnguide import rules
    cfg = {"server": "s", "username": "u", "password": "p", "psk": "k"}
    md = rules.markdown_l2tp(cfg, "10:00", 15, "https://x/w.ps1", "https://x/a.mobileconfig")
    block = re.search(r"```json\n(.*)\n```\s*$", md, re.S).group(1)
    assert json.loads(block)["psk"] == "k"
    for lg in rules.LANGS:
        assert rules.text("l2tp_title", lg) in md


def test_android_warning_present():
    """Android 12+ не умеет L2TP/IPsec — получатель должен знать об этом сразу."""
    from modules.vpnguide import rules
    assert "Android 12" in rules.text("l2tp_android", "ru")


def test_ovpn_route_refuses_l2tp_links():
    src = _read("modules/vpnguide/routes.py")
    assert 'if s.get("kind") != "openvpn":' in src


def test_kind_installer_is_rerunnable():
    src = _read("modules/vpnguide/scripts/vpnguide_deploy.py")
    assert "ORA-00955" in src and "301_vpng_kind.sql" in src
    for line in _read("modules/vpnguide/sql/301_vpng_kind.sql").splitlines():
        if line.strip().startswith("--"):
            assert ";" not in line
