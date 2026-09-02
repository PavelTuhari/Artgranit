"""TBControl — инфраструктурные источники (сервисы Zabbix через mTLS, Proxmox,
SSL-сертификаты). Тесты без Oracle и без сети: чистые правила моделей,
разбор DDL 79b–79e, приёмочные проверки правила №2 CLAUDE.md (логика в
отдельных файлах, контроллер — вызовы в одну строку) и маршруты через
Flask test client с замоканными моделями.

Восстановление 02.09.2026: docs/TBControl/INFRA_RESTORE_20260902.md
"""
import datetime as dt
import os
import re
import sys
from unittest import mock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from models import tbc_services, tbc_proxmox, tbc_certs, tbc_mtls  # noqa: E402


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


# ── правило №2: логика в отдельных файлах, контроллер — одна строка ──────

def test_logic_lives_in_separate_model_files():
    for f in ("models/tbc_mtls.py", "models/tbc_services.py", "models/tbc_proxmox.py", "models/tbc_certs.py",
              "controllers/tbc_infra_routes.py", "static/tbcontrol/tbc_infra.js"):
        assert os.path.isfile(os.path.join(ROOT, f)), f


def test_controller_methods_are_one_line_delegations():
    src = _read("controllers/tbcontrol_controller.py")
    for name, target in (("get_services", "tbc_services.get_services"), ("sync_services", "tbc_services.sync_all"),
                         ("get_proxmox", "tbc_proxmox.get_objects"), ("sync_proxmox", "tbc_proxmox.sync_all"),
                         ("get_certs", "tbc_certs.get_certs"), ("check_certs", "tbc_certs.check_all")):
        m = re.search(rf"def {name}\([^)]*\):\n(.*?)\n\n", src, re.S)
        assert m, name
        body = [ln for ln in m.group(1).splitlines() if ln.strip()]
        assert len(body) == 1 and target in body[0], f"{name}: {body}"


def test_controller_has_no_zabbix_or_proxmox_sql():
    src = _read("controllers/tbcontrol_controller.py")
    for word in ("TBC_SERVICES SET", "TBC_PVE_OBJECTS SET", "INSERT INTO TBC_CERTS", "api2/json", "trigger.get"):
        assert word not in src, word


def test_app_registers_infra_blueprint_in_one_line():
    src = _read("app.py")
    assert src.count("register_blueprint(tbc_infra_bp)") == 1
    assert "/api/tbc/proxmox" not in src  # маршруты — в controllers/tbc_infra_routes.py


def test_template_loads_separate_script_and_panels():
    html = _read("templates/tbcontrol.html")
    assert "tbcontrol/tbc_infra.js" in html
    for pid in ("panel-services", "panel-proxmox", "panel-certs"):
        assert f'id="{pid}"' in html, pid
    assert "/UNA.md/orasldev" not in _read("static/tbcontrol/tbc_infra.js")


# ── DDL 79b–79e ──────────────────────────────────────────────────────

def test_ddl_files_declare_objects_and_are_registered():
    ddl = {n: _read(f"sql/{n}").upper() for n in
           ("79b_tbc_services_mtls.sql", "79c_tbc_dossier_types.sql", "79d_tbc_proxmox.sql", "79e_tbc_certs.sql")}
    assert "CREATE TABLE TBC_SERVICES" in ddl["79b_tbc_services_mtls.sql"]
    assert "KEY_KEYCHAIN_SVC" in ddl["79b_tbc_services_mtls.sql"]
    assert "'ZABBIX_SVC','PROXMOX'" in ddl["79b_tbc_services_mtls.sql"]
    assert "'SERVICE','CASSA','STORE','PVE'" in ddl["79c_tbc_dossier_types.sql"]
    assert "CREATE TABLE TBC_PVE_OBJECTS" in ddl["79d_tbc_proxmox.sql"]
    assert "V_TBC_PVE_STATS" in ddl["79d_tbc_proxmox.sql"]
    assert "CREATE TABLE TBC_CERTS" in ddl["79e_tbc_certs.sql"]
    assert "V_TBC_CERTS_STATS" in ddl["79e_tbc_certs.sql"]
    deploy = _read("deploy_oracle_objects.py")
    for n in ddl:
        assert f'"{n}"' in deploy, n
    # приватный ключ не должен попасть в DDL/seed
    for body in ddl.values():
        assert "BEGIN PRIVATE KEY" not in body and "BEGIN RSA" not in body


# ── чистые правила: сервисы Zabbix ──────────────────────────────────────

def test_classify_kind():
    assert tbc_services.classify_kind("cloudbd", "cloudbd", "Linux servers, Oracle", "Template OS Linux") == "db"
    assert tbc_services.classify_kind("apache | una.md", "", "Linux servers", "") == "web"
    assert tbc_services.classify_kind("mikrotik-core", "", "", "") == "network"
    assert tbc_services.classify_kind("mx1", "Mail relay", "", "") == "mail"
    assert tbc_services.classify_kind("PROXMOX3", "PROXMOX3", "Linux servers", "Template OS Linux") == "server"


def test_service_status_rules():
    assert tbc_services.service_status("1", "available", 5) == ("DISABLED", None)
    assert tbc_services.service_status("0", "available", 5) == ("PROBLEM", "P1")
    assert tbc_services.service_status("0", "available", 4) == ("PROBLEM", "P2")
    assert tbc_services.service_status("0", "available", 3) == ("WARN", "P3")
    assert tbc_services.service_status("0", "unavailable", None) == ("WARN", "P3")
    assert tbc_services.service_status("0", "available", None) == ("OK", None)


def test_build_rows_and_events_from_zabbix_payload():
    hosts = [{"hostid": "10108", "host": "cloudbd", "name": "cloudbd", "status": "0", "available": "1",
              "groups": [{"name": "Linux servers"}, {"name": "Oracle"}],
              "interfaces": [{"ip": "192.168.0.24", "main": "1"}], "parentTemplates": [{"name": "Template OS Linux"}]},
             {"hostid": "10125", "host": "localhost", "name": "Standby", "status": "0", "available": "0",
              "groups": [], "interfaces": [], "parentTemplates": []}]
    triggers = [{"triggerid": "1", "description": "Free disk space is less than 3% on volume /mnt/md3", "priority": "5",
                 "hosts": [{"hostid": "10108"}]},
                {"triggerid": "2", "description": "Free disk space is less than 20% on volume /mnt/md3", "priority": "2",
                 "hosts": [{"hostid": "10108"}]},
                {"triggerid": "3", "description": "Zabbix agent on Standby is unreachable", "priority": "3",
                 "hosts": [{"hostid": "10125"}]}]
    rows = tbc_services.build_rows("zbx-svc-unisim", hosts, triggers)
    by = {r["zbx_hostid"]: r for r in rows}
    assert by["10108"]["status"] == "PROBLEM" and by["10108"]["worst_severity"] == "P1"
    assert by["10108"]["problems_cnt"] == 2 and by["10108"]["problem_text"].startswith("Free disk space is less than 3%")
    assert by["10108"]["ip_address"] == "192.168.0.24" and by["10108"]["service_kind"] == "db"
    assert by["10125"]["status"] == "WARN" and by["10125"]["available"] == "unknown"
    events = tbc_services.wanted_events(rows)
    assert list(events) == ["svc-zbx-svc-unisim-10108"]
    ev = events["svc-zbx-svc-unisim-10108"]
    assert ev["severity"] == "P1" and ev["service_code"] == "database" and "cloudbd" in ev["problem"]
    assert all(len(k) <= 30 for k in events)


# ── чистые правила: Proxmox ────────────────────────────────────────────

def test_pve_health_thresholds():
    assert tbc_proxmox.pve_health("node", "online", 21.0, 89.5, 7.0) == ("OK", "показатели в норме")
    assert tbc_proxmox.pve_health("node", "online", 21.0, 91.0, 7.0)[0] == "WARN"
    assert tbc_proxmox.pve_health("storage", "active", None, None, 98.0) == ("CRIT", "диск заполнен на 98%")
    assert tbc_proxmox.pve_health("node", "offline", None, None, None)[0] == "CRIT"
    assert tbc_proxmox.pve_health("qemu", "stopped", 0.0, 99.0, 99.0)[0] == "OK"  # выключенная VM не тревожит
    lvl, why = tbc_proxmox.pve_health("lxc", "running", 95.0, 50.0, 90.0)
    assert lvl == "CRIT" and "CPU 95%" in why and "диск заполнен на 90%" in why


def test_build_row_pve44_node_without_status_field():
    item = {"node": "proxmox3", "uptime": 5271036, "cpu": 0.3152, "mem": 150169186304, "maxmem": 168908546048,
            "disk": 453025726464, "maxdisk": 6333137289216, "loadavg": ["1.1", "1.0", "0.9"]}
    row = tbc_proxmox.build_row("pve-proxmox3", "node", "proxmox3", item, "4.4-1")
    assert row["status"] == "online" and row["health"] == "OK"
    assert row["cpu_pct"] == 31.52 and row["mem_pct"] == pytest.approx(88.9, abs=0.1)
    assert row["uptime_days"] == 61.0 and row["pve_version"] == "4.4-1" and "load 1.1/1.0/0.9" in row["extra"]


def test_build_row_storage_and_events():
    stg = {"storage": "storage", "type": "dir", "active": 1, "enabled": 1, "used": 98, "total": 100, "content": "images"}
    row = tbc_proxmox.build_row("pve-proxmox3", "storage", "proxmox3", stg)
    assert row["status"] == "active" and row["health"] == "CRIT" and row["cpu_pct"] is None
    node_down = tbc_proxmox.build_row("pve-proxmox3", "node", "proxmox3", {"node": "proxmox3", "status": "offline"})
    events = tbc_proxmox.wanted_events([row, node_down])
    assert events["pve-storage-storage"]["severity"] == "P2" and events["pve-storage-storage"]["service_code"] == "database"
    assert events["pve-node-proxmox3"]["severity"] == "P1"
    assert all(len(k) <= 30 for k in events)


# ── чистые правила: сертификаты ────────────────────────────────────────

def test_cert_status_and_auto_renew():
    assert tbc_certs.cert_status(82) == "OK"
    assert tbc_certs.cert_status(14) == "EXPIRING"
    assert tbc_certs.cert_status(-1) == "EXPIRED"
    assert tbc_certs.cert_status(None, "timeout") == "ERROR"
    assert tbc_certs.auto_renew_of("Let's Encrypt") == "letsencrypt"
    assert tbc_certs.auto_renew_of("DigiCert Inc") == "manual"
    assert tbc_certs.auto_renew_of("Let's Encrypt", "manual") == "manual"


def test_parse_der_self_signed():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Let's Encrypt")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(0x1234).not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=10)).sign(key, hashes.SHA256()))
    info = tbc_certs.parse_der(cert.public_bytes(serialization.Encoding.DER), now)
    assert info["subject_cn"] == "test.example" and info["issuer"] == "Let's Encrypt"
    assert info["serial_no"] == "1234" and info["days_left"] == 9
    assert tbc_certs.cert_status(info["days_left"]) == "EXPIRING"


def test_cert_wanted_events():
    rows = [{"domain_name": "a.md", "port": 443, "status": "OK", "enabled": "Y"},
            {"domain_name": "b.md", "port": 443, "status": "EXPIRED", "enabled": "Y", "valid_to": "2026-01-01"},
            {"domain_name": "c.md", "port": 443, "status": "ERROR", "enabled": "N", "last_error": "x"}]
    ev = tbc_certs.wanted_events(rows)
    assert list(ev) == ["cert-b.md"] and ev["cert-b.md"]["severity"] == "P1"


# ── mTLS-транспорт: секреты и ключ ─────────────────────────────────────

def test_resolve_secret_plain_and_keychain(monkeypatch):
    assert tbc_mtls.resolve_secret("  plain  ") == "plain"
    monkeypatch.setattr(tbc_mtls.sys, "platform", "darwin")
    calls = {}

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        return mock.Mock(returncode=0, stdout="s3cret\n", stderr="")
    monkeypatch.setattr(tbc_mtls.subprocess, "run", fake_run)
    assert tbc_mtls.resolve_secret("keychain:proxmox3-ssh/root") == "s3cret"
    assert calls["cmd"][:3] == ["security", "find-generic-password", "-s"] and "-w" in calls["cmd"]
    with pytest.raises(RuntimeError):
        tbc_mtls.resolve_secret("keychain:broken")


def test_client_key_path_prefers_env_and_fails_loudly(monkeypatch, tmp_path):
    key = tmp_path / "k.pem"; key.write_text("-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----\n")
    monkeypatch.setenv("TBC_MTLS_KEY_PATH", str(key))
    assert tbc_mtls.client_key_path({}) == str(key)
    monkeypatch.delenv("TBC_MTLS_KEY_PATH")
    with pytest.raises(RuntimeError, match="Keychain"):
        tbc_mtls.client_key_path({"key_keychain_svc": "", "key_keychain_acc": ""})


def test_mtls_client_requires_cert_file(monkeypatch):
    with pytest.raises(RuntimeError, match="сертификат"):
        tbc_mtls.MtlsClient({"api_url": "https://gw:8443/x", "cert_path": "/nonexistent.crt"})


# ── маршруты через Flask test client (модели замоканы) ─────────────────

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(tbc_services, "get_services", lambda *a: {"success": True, "data": [], "total": 0, "args": a})
    monkeypatch.setattr(tbc_services, "sync_all", lambda code=None: {"success": True, "data": [], "code": code})
    monkeypatch.setattr(tbc_proxmox, "get_objects", lambda *a: {"success": True, "data": [], "args": a})
    monkeypatch.setattr(tbc_certs, "get_certs", lambda: {"success": True, "data": []})
    monkeypatch.setattr(tbc_certs, "check_all", lambda cid=None: {"success": True, "checked": 0, "id": cid})
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def test_services_route_returns_success(client):
    r = client.get("/api/tbc/services?status=PROBLEM&kind=db")
    assert r.status_code == 200
    j = r.get_json()
    assert j["success"] is True and j["args"] == [None, "PROBLEM", "db"]


def test_infra_routes(client):
    assert client.get("/api/tbc/proxmox?health=CRIT").get_json()["args"] == [None, None, "CRIT"]
    assert client.get("/api/tbc/certs").get_json()["success"] is True
    # запись — только авторизованным
    assert client.post("/api/tbc/services/sync", json={}).status_code == 401
    assert client.post("/api/tbc/proxmox/sync", json={}).status_code == 401
    assert client.post("/api/tbc/certs/check", json={}).status_code == 401
