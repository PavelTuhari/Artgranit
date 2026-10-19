"""
Контроллер модуля TBControl — платформа контроля софта и оборудования
магазинов: Front Office, POS, Self-Service (SCO), Android-устройства.

Спецификация: docs/TBControl/TECHNICAL-OPS.md
Oracle-объекты: префикс TBC_ (sql/70_tbc_tables.sql, 71_tbc_views.sql).
"""
import sys
import os
import random
import secrets
from typing import Dict, List, Optional

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseModel
from models import tbc_services, tbc_proxmox, tbc_certs  # инфраструктура: сервисы Zabbix, Proxmox, SSL (правило №2)
from flask import session


class TBControlController:
    """Контроллер платформы эксплуатации Front Office / POS / SCO / Android"""

    # Диагностический workflow POS (раздел 39 ТЗ)
    DIAG_COMPONENTS = {
        'POS': ['network', 'dns', 'gateway', 'agent', 'process', 'database', 'api', 'payment', 'fiscal', 'printer'],
        'SCO': ['network', 'dns', 'gateway', 'agent', 'process', 'scanner', 'scale', 'payment', 'printer', 'cash'],
        'AND': ['network', 'api', 'process', 'battery', 'storage', 'sync'],
        'SRV': ['network', 'dns', 'agent', 'process', 'database', 'api'],
        'NET': ['network', 'gateway'],
        'PRN': ['network', 'process'],
    }

    # Deployment verification (раздел 32 ТЗ)
    DEPLOY_CHECKS = ['process', 'version', 'health', 'database', 'api', 'sync', 'peripheral', 'business']

    @staticmethod
    def _rows_to_dicts(result: Dict) -> List[Dict]:
        if not result.get("success") or not result.get("data"):
            return []
        cols = [c.lower() for c in (result.get("columns") or [])]
        return [dict(zip(cols, row)) for row in result.get("data", [])]

    @staticmethod
    def _first_row(result: Dict) -> Optional[Dict]:
        rows = TBControlController._rows_to_dicts(result)
        return rows[0] if rows else None

    @staticmethod
    def _username():
        return session.get('username', 'system')

    @staticmethod
    def _add_audit(action, entity_type, entity_id, details=""):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO TBC_EVENT_LOG (ACTION, ENTITY_TYPE, ENTITY_ID, DETAILS, USERNAME) "
                    "VALUES (:action, :etype, :eid, :details, :uname)",
                    {"action": action, "etype": entity_type, "eid": entity_id,
                     "details": details[:2000] if details else None,
                     "uname": TBControlController._username()}
                )
                db.connection.commit()
        except Exception:
            pass

    # ========== Дашборд ==========

    @staticmethod
    def _empty_stats():
        return {
            "stores": {"total": 0, "ok": 0, "degraded": 0, "critical": 0},
            "devices": {"total": 0, "online": 0, "offline": 0, "degraded": 0},
            "pos": {"total": 0, "online": 0}, "sco": {"total": 0, "online": 0},
            "android": {"total": 0, "online": 0},
            "events": {"p1": 0, "p2": 0, "p3": 0, "p4": 0},
            "incidents_open": 0, "outdated_apps": 0, "pending_changes": 0,
        }

    @staticmethod
    def get_dashboard_stats():
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_TBC_DASHBOARD_STATS")
                row = TBControlController._first_row(r)
                if not row:
                    return {"success": True, "data": TBControlController._empty_stats()}
                return {"success": True, "data": {
                    "stores": {"total": row.get("total_stores", 0), "ok": row.get("ok_stores", 0),
                               "degraded": row.get("degraded_stores", 0), "critical": row.get("critical_stores", 0)},
                    "devices": {"total": row.get("total_devices", 0), "online": row.get("online_devices", 0),
                                "offline": row.get("offline_devices", 0), "degraded": row.get("degraded_devices", 0)},
                    "pos": {"total": row.get("pos_total", 0), "online": row.get("pos_online", 0)},
                    "sco": {"total": row.get("sco_total", 0), "online": row.get("sco_online", 0)},
                    "android": {"total": row.get("and_total", 0), "online": row.get("and_online", 0)},
                    "events": {"p1": row.get("p1_open", 0), "p2": row.get("p2_open", 0),
                               "p3": row.get("p3_open", 0), "p4": row.get("p4_open", 0)},
                    "incidents_open": row.get("open_incidents", 0),
                    "outdated_apps": row.get("outdated_apps", 0),
                    "pending_changes": row.get("pending_changes", 0),
                }}
        except Exception as e:
            return {"success": True, "data": TBControlController._empty_stats(), "warning": str(e)}

    @staticmethod
    def get_store_health():
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_TBC_STORE_HEALTH ORDER BY CODE")
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Магазины ==========

    @staticmethod
    def get_stores():
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT s.*, (SELECT COUNT(*) FROM TBC_DEVICES d WHERE d.STORE_ID = s.ID) AS DEVICE_COUNT "
                    "FROM TBC_STORES s ORDER BY s.CODE")
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_store(data):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO TBC_STORES (CODE, NAME, COUNTRY, CITY, ADDRESS, STATUS, "
                    "MAINT_DOW, MAINT_TIME_FROM, MAINT_TIME_TO) "
                    "VALUES (:code, :name, :country, :city, :address, :status, :mdow, :mfrom, :mto)",
                    {"code": data.get("code", ""), "name": data.get("name", ""),
                     "country": data.get("country", "MD"), "city": data.get("city", ""),
                     "address": data.get("address", ""), "status": data.get("status", "active"),
                     "mdow": int(data["maint_dow"]) if data.get("maint_dow") else None,
                     "mfrom": data.get("maint_time_from"), "mto": data.get("maint_time_to")}
                )
                db.connection.commit()
                r = db.execute_query("SELECT ID FROM TBC_STORES WHERE CODE = :code", {"code": data.get("code", "")})
                row = TBControlController._first_row(r)
                store_id = row["id"] if row else None
                TBControlController._add_audit("create", "store", store_id, f"Создан магазин {data.get('code')}")
                return {"success": True, "data": {"id": store_id, **data}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_store(store_id, data):
        try:
            with DatabaseModel() as db:
                field_map = {"code": "CODE", "name": "NAME", "country": "COUNTRY", "city": "CITY",
                             "address": "ADDRESS", "status": "STATUS", "maint_dow": "MAINT_DOW",
                             "maint_time_from": "MAINT_TIME_FROM", "maint_time_to": "MAINT_TIME_TO"}
                sets, params = [], {"id": int(store_id)}
                for key, col in field_map.items():
                    if key in data:
                        sets.append(f"{col} = :{key}")
                        params[key] = data[key] if data[key] != "" else None
                if not sets:
                    return {"success": False, "error": "Нет данных для обновления"}
                db.execute_query(f"UPDATE TBC_STORES SET {', '.join(sets)} WHERE ID = :id", params)
                db.connection.commit()
                TBControlController._add_audit("update", "store", int(store_id), "Обновлён магазин")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_store(store_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT COUNT(*) AS CNT FROM TBC_DEVICES WHERE STORE_ID = :id",
                                     {"id": int(store_id)})
                row = TBControlController._first_row(r)
                if row and row.get("cnt", 0) > 0:
                    return {"success": False, "error": f"Нельзя удалить: {row['cnt']} устройств привязано"}
                db.execute_query("DELETE FROM TBC_STORES WHERE ID = :id", {"id": int(store_id)})
                db.connection.commit()
                TBControlController._add_audit("delete", "store", int(store_id), "Удалён магазин")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Устройства ==========

    @staticmethod
    def get_devices(store_id=None, device_type=None, status=None):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_TBC_DEVICES WHERE 1=1"
                params = {}
                if store_id:
                    sql += " AND STORE_ID = :store_id"
                    params["store_id"] = int(store_id)
                if device_type:
                    sql += " AND DEVICE_TYPE = :dtype"
                    params["dtype"] = device_type
                if status:
                    sql += " AND STATUS = :status"
                    params["status"] = status
                sql += " ORDER BY CODE"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_device(device_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_TBC_DEVICES WHERE ID = :id", {"id": int(device_id)})
                device = TBControlController._first_row(r)
                if not device:
                    return {"success": False, "error": "Устройство не найдено"}
                r2 = db.execute_query("SELECT * FROM V_TBC_VERSIONS WHERE DEVICE_ID = :id", {"id": int(device_id)})
                device["apps"] = TBControlController._rows_to_dicts(r2)
                r3 = db.execute_query(
                    "SELECT COMPONENT, STATUS, LATENCY_MS, DETAILS, CHECKED_AT FROM TBC_HEALTH_CHECKS "
                    "WHERE DEVICE_ID = :id ORDER BY CHECKED_AT DESC FETCH FIRST 20 ROWS ONLY",
                    {"id": int(device_id)})
                device["health_checks"] = TBControlController._rows_to_dicts(r3)
                return {"success": True, "data": device}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def register_device(data):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO TBC_DEVICES (CODE, STORE_ID, DEVICE_TYPE, HOSTNAME, SERIAL_NUMBER, ASSET_ID, "
                    "MANUFACTURER, MODEL, OS, OS_VERSION, IP_ADDRESS, MAC_ADDRESS, STATUS, OWNER_SIDE, "
                    "SUPPORT_GROUP, CRITICALITY) "
                    "VALUES (:code, :store_id, :dtype, :hostname, :sn, :asset, :manuf, :model, :os, :osv, "
                    ":ip, :mac, :status, :owner, :grp, :crit)",
                    {"code": data.get("code", ""), "store_id": int(data.get("store_id", 0)),
                     "dtype": data.get("device_type", "POS"), "hostname": data.get("hostname", ""),
                     "sn": data.get("serial_number", ""), "asset": data.get("asset_id", ""),
                     "manuf": data.get("manufacturer", ""), "model": data.get("model", ""),
                     "os": data.get("os", ""), "osv": data.get("os_version", ""),
                     "ip": data.get("ip_address", ""), "mac": data.get("mac_address", ""),
                     "status": data.get("status", "offline"), "owner": data.get("owner_side", "customer"),
                     "grp": data.get("support_group") or "customer_it",
                     "crit": data.get("criticality", "medium")}
                )
                db.connection.commit()
                r = db.execute_query("SELECT ID FROM TBC_DEVICES WHERE CODE = :code", {"code": data.get("code", "")})
                row = TBControlController._first_row(r)
                dev_id = row["id"] if row else None
                TBControlController._add_audit("create", "device", dev_id,
                                               f"Зарегистрировано устройство {data.get('code')}")
                return {"success": True, "data": {"id": dev_id, **data}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_device(device_id, data):
        try:
            with DatabaseModel() as db:
                field_map = {"code": "CODE", "store_id": "STORE_ID", "device_type": "DEVICE_TYPE",
                             "hostname": "HOSTNAME", "serial_number": "SERIAL_NUMBER", "asset_id": "ASSET_ID",
                             "manufacturer": "MANUFACTURER", "model": "MODEL", "os": "OS",
                             "os_version": "OS_VERSION", "ip_address": "IP_ADDRESS", "mac_address": "MAC_ADDRESS",
                             "status": "STATUS", "owner_side": "OWNER_SIDE", "support_group": "SUPPORT_GROUP",
                             "criticality": "CRITICALITY"}
                sets, params = [], {"id": int(device_id)}
                for key, col in field_map.items():
                    if key in data:
                        sets.append(f"{col} = :{key}")
                        params[key] = int(data[key]) if key == "store_id" and data[key] else (data[key] or None)
                if not sets:
                    return {"success": False, "error": "Нет данных для обновления"}
                db.execute_query(f"UPDATE TBC_DEVICES SET {', '.join(sets)} WHERE ID = :id", params)
                db.connection.commit()
                TBControlController._add_audit("update", "device", int(device_id), "Обновлено устройство")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_device(device_id):
        try:
            with DatabaseModel() as db:
                db.execute_query("DELETE FROM TBC_DEVICES WHERE ID = :id", {"id": int(device_id)})
                db.connection.commit()
                TBControlController._add_audit("delete", "device", int(device_id), "Удалено устройство")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Agent Heartbeat (авторегистрация, разделы 8, 44 ТЗ) ==========

    @staticmethod
    def agent_heartbeat(data):
        """Приём heartbeat от агента (Windows POS / SCO / Android Monitoring Agent).
        Устройство идентифицируется по CODE (device_id из ТЗ, напр. MD-CHS-001-AND-01).
        Неизвестное устройство автоматически регистрируется (Auto Registration)."""
        code = (data.get("device_id") or data.get("code") or "").strip()
        if not code:
            return {"success": False, "error": "device_id обязателен"}
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT ID, STORE_ID FROM TBC_DEVICES WHERE CODE = :code", {"code": code})
                row = TBControlController._first_row(r)
                registered = False
                if not row:
                    # Auto Registration: определяем магазин и тип из кода MD-CHS-001-AND-01
                    parts = code.split("-")
                    store_code = "-".join(parts[:3]) if len(parts) >= 5 else None
                    dtype = parts[3] if len(parts) >= 5 else "POS"
                    rs = db.execute_query("SELECT ID FROM TBC_STORES WHERE CODE = :c", {"c": store_code})
                    srow = TBControlController._first_row(rs)
                    if not srow:
                        return {"success": False, "error": f"Магазин {store_code} не зарегистрирован"}
                    db.execute_query(
                        "INSERT INTO TBC_DEVICES (CODE, STORE_ID, DEVICE_TYPE, HOSTNAME, OS, OS_VERSION, "
                        "IP_ADDRESS, STATUS, SUPPORT_GROUP) "
                        "VALUES (:code, :sid, :dtype, :host, :os, :osv, :ip, 'online', 'customer_it')",
                        {"code": code, "sid": srow["id"], "dtype": dtype,
                         "host": data.get("hostname", ""), "os": data.get("os", ""),
                         "osv": data.get("os_version", ""), "ip": data.get("ip", "")})
                    db.connection.commit()
                    r = db.execute_query("SELECT ID, STORE_ID FROM TBC_DEVICES WHERE CODE = :code", {"code": code})
                    row = TBControlController._first_row(r)
                    registered = True
                    TBControlController._add_audit("auto_register", "device", row["id"],
                                                   f"Auto Registration: {code}")
                dev_id = row["id"]

                # Метрики
                status = 'online' if (data.get("status", "OK") or "OK").upper() in ("OK", "ONLINE") else 'degraded'
                db.execute_query(
                    "UPDATE TBC_DEVICES SET STATUS = :status, LAST_SEEN = SYSTIMESTAMP, "
                    "CPU_PCT = NVL(:cpu, CPU_PCT), RAM_PCT = NVL(:ram, RAM_PCT), DISK_PCT = NVL(:disk, DISK_PCT), "
                    "BATTERY_PCT = NVL(:battery, BATTERY_PCT), STORAGE_FREE_MB = NVL(:storage, STORAGE_FREE_MB), "
                    "PENDING_OPS = NVL(:pending, PENDING_OPS), "
                    "LAST_SYNC = NVL(TO_TIMESTAMP(:last_sync, 'YYYY-MM-DD\"T\"HH24:MI:SS'), LAST_SYNC) "
                    "WHERE ID = :id",
                    {"status": status, "cpu": data.get("cpu"), "ram": data.get("ram"),
                     "disk": data.get("disk"), "battery": data.get("battery"),
                     "storage": data.get("storage_free_mb"), "pending": data.get("pending_operations"),
                     "last_sync": (data.get("last_sync") or "")[:19] or None, "id": dev_id})

                # Материализация телеметрии в time series (раздел 72 ТЗ)
                samples = [('hw', 'cpu', data.get("cpu")), ('hw', 'ram', data.get("ram")),
                           ('hw', 'disk', data.get("disk")), ('hw', 'battery', data.get("battery")),
                           ('app', 'app_latency', data.get("app_latency")),
                           ('app', 'tx_count', data.get("tx_count")),
                           ('app', 'app_errors', data.get("app_errors")),
                           ('app', 'queue_len', data.get("queue_len"))]
                for scope, metric, value in samples:
                    if value is not None:
                        db.execute_query(
                            "INSERT INTO TBC_METRIC_SAMPLES (DEVICE_ID, SCOPE, METRIC, NUM_VALUE) "
                            "VALUES (:did, :scope, :metric, :val)",
                            {"did": dev_id, "scope": scope, "metric": metric, "val": value})

                # Версия приложения: сверка с ожидаемой (раздел 30 ТЗ)
                app_code = data.get("application")
                version = data.get("version")
                version_status = None
                if app_code and version:
                    ra = db.execute_query(
                        "SELECT ID, EXPECTED_VERSION FROM TBC_APPLICATIONS WHERE LOWER(CODE) = LOWER(:c) OR LOWER(NAME) = LOWER(:c2)",
                        {"c": app_code, "c2": app_code})
                    arow = TBControlController._first_row(ra)
                    if arow:
                        version_status = 'OK' if arow.get("expected_version") == version else 'OUTDATED'
                        db.execute_query(
                            "MERGE INTO TBC_DEVICE_APPS da USING (SELECT :did AS DID, :aid AS AID FROM DUAL) src "
                            "ON (da.DEVICE_ID = src.DID AND da.APP_ID = src.AID) "
                            "WHEN MATCHED THEN UPDATE SET da.CURRENT_VERSION = :ver, da.BUILD = :build, "
                            "  da.STATUS = :vstatus, da.LAST_CHECK = SYSTIMESTAMP "
                            "WHEN NOT MATCHED THEN INSERT (DEVICE_ID, APP_ID, CURRENT_VERSION, BUILD, STATUS, "
                            "  DEPLOYED_AT, LAST_CHECK) "
                            "VALUES (:did2, :aid2, :ver2, :build2, :vstatus2, SYSTIMESTAMP, SYSTIMESTAMP)",
                            {"did": dev_id, "aid": arow["id"], "ver": version, "build": data.get("build"),
                             "vstatus": version_status, "did2": dev_id, "aid2": arow["id"],
                             "ver2": version, "build2": data.get("build"), "vstatus2": version_status})
                db.connection.commit()
                return {"success": True, "data": {"device_id": dev_id, "code": code,
                                                  "registered": registered, "status": status,
                                                  "version_status": version_status}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Диагностика (разделы 39-40 ТЗ) ==========

    @staticmethod
    def run_diagnostics(device_id):
        """Запускает стандартный diagnostic workflow для устройства
        и записывает результаты в TBC_HEALTH_CHECKS (симуляция агента)."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT ID, CODE, DEVICE_TYPE, STATUS FROM TBC_DEVICES WHERE ID = :id",
                                     {"id": int(device_id)})
                dev = TBControlController._first_row(r)
                if not dev:
                    return {"success": False, "error": "Устройство не найдено"}
                components = TBControlController.DIAG_COMPONENTS.get(dev["device_type"],
                                                                     TBControlController.DIAG_COMPONENTS['POS'])
                report = {"device": dev["code"]}
                for comp in components:
                    if dev["status"] == 'offline' and comp in ('network', 'gateway'):
                        status, latency, details = 'FAIL', None, 'Нет ответа'
                    elif dev["status"] == 'degraded' and comp in ('payment', 'battery', 'storage', 'sync'):
                        status, latency, details = 'WARN', None, 'Деградация компонента'
                    else:
                        status = 'OK'
                        latency = random.randint(2, 60) if comp in ('network', 'dns', 'gateway', 'database', 'api') else None
                        details = None
                    db.execute_query(
                        "INSERT INTO TBC_HEALTH_CHECKS (DEVICE_ID, COMPONENT, STATUS, LATENCY_MS, DETAILS) "
                        "VALUES (:did, :comp, :status, :lat, :det)",
                        {"did": int(device_id), "comp": comp, "status": status, "lat": latency, "det": details})
                    report[comp] = status
                db.connection.commit()
                TBControlController._add_audit("diagnostics", "device", int(device_id),
                                               f"Диагностика {dev['code']}")
                return {"success": True, "data": report}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Приложения и версии ==========

    @staticmethod
    def get_applications():
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT a.*, "
                    "(SELECT COUNT(*) FROM TBC_DEVICE_APPS da WHERE da.APP_ID = a.ID) AS INSTALL_COUNT, "
                    "(SELECT COUNT(*) FROM TBC_DEVICE_APPS da WHERE da.APP_ID = a.ID AND da.STATUS = 'OUTDATED') AS OUTDATED_COUNT "
                    "FROM TBC_APPLICATIONS a ORDER BY a.CODE")
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_application(data):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO TBC_APPLICATIONS (CODE, NAME, APP_TYPE, EXPECTED_VERSION, EXPECTED_BUILD, "
                    "RELEASE_CHANNEL, HEALTH_URL) VALUES (:code, :name, :atype, :ver, :build, :channel, :url)",
                    {"code": data.get("code", ""), "name": data.get("name", ""),
                     "atype": data.get("app_type", "frontoffice"), "ver": data.get("expected_version"),
                     "build": data.get("expected_build"), "channel": data.get("release_channel", "PRODUCTION"),
                     "url": data.get("health_url")})
                db.connection.commit()
                r = db.execute_query("SELECT ID FROM TBC_APPLICATIONS WHERE CODE = :c", {"c": data.get("code", "")})
                row = TBControlController._first_row(r)
                app_id = row["id"] if row else None
                TBControlController._add_audit("create", "application", app_id, f"Приложение {data.get('code')}")
                return {"success": True, "data": {"id": app_id, **data}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_application(app_id, data):
        try:
            with DatabaseModel() as db:
                field_map = {"code": "CODE", "name": "NAME", "app_type": "APP_TYPE",
                             "expected_version": "EXPECTED_VERSION", "expected_build": "EXPECTED_BUILD",
                             "release_channel": "RELEASE_CHANNEL", "health_url": "HEALTH_URL", "status": "STATUS"}
                sets, params = [], {"id": int(app_id)}
                for key, col in field_map.items():
                    if key in data:
                        sets.append(f"{col} = :{key}")
                        params[key] = data[key] or None
                if not sets:
                    return {"success": False, "error": "Нет данных для обновления"}
                db.execute_query(f"UPDATE TBC_APPLICATIONS SET {', '.join(sets)} WHERE ID = :id", params)
                # Пересчёт статусов версий при смене ожидаемой версии
                if "expected_version" in data:
                    db.execute_query(
                        "UPDATE TBC_DEVICE_APPS SET STATUS = CASE WHEN CURRENT_VERSION = :ver THEN 'OK' "
                        "ELSE 'OUTDATED' END WHERE APP_ID = :id AND STATUS IN ('OK','OUTDATED')",
                        {"ver": data["expected_version"], "id": int(app_id)})
                db.connection.commit()
                TBControlController._add_audit("update", "application", int(app_id), "Обновлено приложение")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_application(app_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT COUNT(*) AS CNT FROM TBC_CHANGES WHERE APP_ID = :id",
                                     {"id": int(app_id)})
                row = TBControlController._first_row(r)
                if row and row.get("cnt", 0) > 0:
                    return {"success": False, "error": f"Есть {row['cnt']} изменений (changes) по приложению"}
                db.execute_query("DELETE FROM TBC_APPLICATIONS WHERE ID = :id", {"id": int(app_id)})
                db.connection.commit()
                TBControlController._add_audit("delete", "application", int(app_id), "Удалено приложение")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_versions(app_id=None, status=None):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_TBC_VERSIONS WHERE 1=1"
                params = {}
                if app_id:
                    sql += " AND APP_ID = :app_id"
                    params["app_id"] = int(app_id)
                if status:
                    sql += " AND STATUS = :status"
                    params["status"] = status
                sql += " ORDER BY STORE_CODE, DEVICE_CODE"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== События ==========

    @staticmethod
    def get_events(status=None, severity=None, store_id=None, limit=200):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_TBC_EVENTS WHERE 1=1"
                params = {}
                if status:
                    if status == 'active':
                        sql += " AND STATUS IN ('open','ack')"
                    else:
                        sql += " AND STATUS = :status"
                        params["status"] = status
                if severity:
                    sql += " AND SEVERITY = :severity"
                    params["severity"] = severity
                if store_id:
                    sql += " AND STORE_ID = :store_id"
                    params["store_id"] = int(store_id)
                sql += f" ORDER BY CREATED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_event(data):
        try:
            status = data.get("status") if data.get("status") in ('open', 'ack', 'suppressed') else 'open'
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO TBC_EVENTS (SEVERITY, STORE_ID, DEVICE_ID, SERVICE_CODE, PROBLEM, "
                    f"STATUS, SOURCE, CORRELATION_ID, PARENT_EVENT_ID) "
                    f"VALUES (:sev, :sid, :did, :svc, :problem, '{status}', :source, :corr, :parent)",
                    {"sev": data.get("severity", "P4"),
                     "sid": int(data["store_id"]) if data.get("store_id") else None,
                     "did": int(data["device_id"]) if data.get("device_id") else None,
                     "svc": data.get("service_code") or None,
                     "problem": data.get("problem", ""), "source": data.get("source", "manual"),
                     "corr": data.get("correlation_id") or None,
                     "parent": int(data["parent_event_id"]) if data.get("parent_event_id") else None})
                db.connection.commit()
                r = db.execute_query("SELECT MAX(ID) AS ID FROM TBC_EVENTS")
                row = TBControlController._first_row(r)
                ev_id = row["id"] if row else None
                TBControlController._add_audit("create", "event", ev_id,
                                               f"{data.get('severity')}: {data.get('problem')}")
                return {"success": True, "data": {"id": ev_id, **data}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def set_event_status(event_id, status):
        if status not in ('open', 'ack', 'resolved', 'suppressed'):
            return {"success": False, "error": "Недопустимый статус"}
        try:
            with DatabaseModel() as db:
                extra = ""
                if status == 'ack':
                    extra = ", ACKED_AT = SYSTIMESTAMP"
                elif status == 'resolved':
                    extra = ", RESOLVED_AT = SYSTIMESTAMP"
                db.execute_query(f"UPDATE TBC_EVENTS SET STATUS = :status{extra} WHERE ID = :id",
                                 {"status": status, "id": int(event_id)})
                # Разрешение root cause закрывает подавленные downstream-события
                if status == 'resolved':
                    db.execute_query(
                        "UPDATE TBC_EVENTS SET STATUS = 'resolved', RESOLVED_AT = SYSTIMESTAMP "
                        "WHERE PARENT_EVENT_ID = :id AND STATUS = 'suppressed'", {"id": int(event_id)})
                db.connection.commit()
                TBControlController._add_audit(status, "event", int(event_id), f"Событие → {status}")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_incident_from_event(event_id, data=None):
        """Событие → инцидент (раздел 35 ТЗ). Назначение группы по границе
        ответственности: application → developer, infrastructure → customer_it."""
        data = data or {}
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_TBC_EVENTS WHERE ID = :id", {"id": int(event_id)})
                ev = TBControlController._first_row(r)
                if not ev:
                    return {"success": False, "error": "Событие не найдено"}
                app_services = ('store_app', 'api', 'sync', 'database', 'pos', 'sco', 'android')
                infra_services = ('network', 'payment', 'fiscal', 'inventory')
                group = data.get("assigned_group")
                if not group:
                    svc = ev.get("service_code") or ""
                    group = 'developer' if svc in app_services and svc not in infra_services else 'customer_it'
                    if ev.get("severity") == 'P1':
                        group = data.get("assigned_group", 'service_desk')
                sla_hours = {'P1': 2, 'P2': 4, 'P3': 8, 'P4': 24}.get(ev.get("severity"), 24)
                db.execute_query(
                    "INSERT INTO TBC_INCIDENTS (CODE, EVENT_ID, STORE_ID, DEVICE_ID, SEVERITY, TITLE, "
                    "DESCRIPTION, ASSIGNED_GROUP, STATUS, SLA_DEADLINE) "
                    "VALUES ('INC-' || TO_CHAR(SYSDATE, 'YYYY') || '-' || TBC_INCIDENT_NUM_SEQ.NEXTVAL, "
                    ":eid, :sid, :did, :sev, :title, :descr, :grp, 'new', "
                    "SYSTIMESTAMP + NUMTODSINTERVAL(:sla, 'HOUR'))",
                    {"eid": int(event_id), "sid": ev.get("store_id"), "did": ev.get("device_id"),
                     "sev": ev.get("severity"), "title": data.get("title") or ev.get("problem"),
                     "descr": data.get("description") or ev.get("problem"),
                     "grp": group, "sla": sla_hours})
                db.execute_query("UPDATE TBC_EVENTS SET STATUS = 'ack', ACKED_AT = SYSTIMESTAMP "
                                 "WHERE ID = :id AND STATUS = 'open'", {"id": int(event_id)})
                db.connection.commit()
                r2 = db.execute_query("SELECT MAX(ID) AS ID FROM TBC_INCIDENTS")
                row = TBControlController._first_row(r2)
                inc_id = row["id"] if row else None
                TBControlController._add_audit("create", "incident", inc_id,
                                               f"Инцидент из события #{event_id} → {group}")
                # P1/P2 → автоматическое AI-досье (раздел 74.3 ТЗ)
                dossier = None
                if inc_id and ev.get("severity") in ('P1', 'P2'):
                    dr = TBControlController.generate_dossier('incident', inc_id)
                    if dr.get("success"):
                        dossier = dr["data"]["code"]
                return {"success": True, "data": {"id": inc_id, "dossier": dossier}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Инциденты ==========

    @staticmethod
    def get_incidents(status=None, severity=None, limit=200):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_TBC_INCIDENTS WHERE 1=1"
                params = {}
                if status:
                    if status == 'active':
                        sql += " AND STATUS <> 'closed'"
                    else:
                        sql += " AND STATUS = :status"
                        params["status"] = status
                if severity:
                    sql += " AND SEVERITY = :severity"
                    params["severity"] = severity
                sql += f" ORDER BY OPENED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_incident(incident_id, data):
        try:
            with DatabaseModel() as db:
                field_map = {"title": "TITLE", "description": "DESCRIPTION",
                             "assigned_group": "ASSIGNED_GROUP", "assignee": "ASSIGNEE", "status": "STATUS",
                             "root_cause": "ROOT_CAUSE", "tech_cause": "TECH_CAUSE",
                             "business_impact": "BUSINESS_IMPACT", "resolution": "RESOLUTION",
                             "corrective_action": "CORRECTIVE_ACTION", "preventive_action": "PREVENTIVE_ACTION"}
                sets, params = [], {"id": int(incident_id)}
                for key, col in field_map.items():
                    if key in data:
                        sets.append(f"{col} = :{key}")
                        params[key] = data[key] or None
                if data.get("status") == 'closed':
                    sets.append("CLOSED_AT = SYSTIMESTAMP")
                if not sets:
                    return {"success": False, "error": "Нет данных для обновления"}
                db.execute_query(f"UPDATE TBC_INCIDENTS SET {', '.join(sets)} WHERE ID = :id", params)
                db.connection.commit()
                TBControlController._add_audit("update", "incident", int(incident_id),
                                               f"Инцидент: {data.get('status', 'обновлён')}")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Изменения / Deployment ==========

    @staticmethod
    def get_changes(status=None):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_TBC_CHANGES WHERE 1=1"
                params = {}
                if status:
                    sql += " AND STATUS = :status"
                    params["status"] = status
                sql += " ORDER BY CREATED_AT DESC"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_change(change_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_TBC_CHANGES WHERE ID = :id", {"id": int(change_id)})
                chg = TBControlController._first_row(r)
                if not chg:
                    return {"success": False, "error": "Изменение не найдено"}
                r2 = db.execute_query(
                    "SELECT s.ID, s.CODE, s.NAME FROM TBC_CHANGE_STORES cs "
                    "JOIN TBC_STORES s ON s.ID = cs.STORE_ID WHERE cs.CHANGE_ID = :id ORDER BY s.CODE",
                    {"id": int(change_id)})
                chg["stores"] = TBControlController._rows_to_dicts(r2)
                r3 = db.execute_query(
                    "SELECT dc.CHECK_TYPE, dc.STATUS, dc.DETAILS, dc.CHECKED_AT, d.CODE AS DEVICE_CODE "
                    "FROM TBC_DEPLOY_CHECKS dc JOIN TBC_DEVICES d ON d.ID = dc.DEVICE_ID "
                    "WHERE dc.CHANGE_ID = :id ORDER BY dc.CHECKED_AT DESC FETCH FIRST 100 ROWS ONLY",
                    {"id": int(change_id)})
                chg["checks"] = TBControlController._rows_to_dicts(r3)
                return {"success": True, "data": chg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_change(data):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO TBC_CHANGES (CODE, APP_ID, VERSION, ROLLBACK_VERSION, DESCRIPTION, REASON, "
                    "OWNER, RELEASE_CHANNEL, WINDOW_START, WINDOW_END, STATUS, CREATED_BY) "
                    "VALUES ('CHG-' || TO_CHAR(SYSDATE, 'YYYY') || '-' || LPAD(TBC_CHANGE_NUM_SEQ.NEXTVAL, 4, '0'), "
                    ":app_id, :version, :rb_ver, :descr, :reason, :owner, :channel, "
                    "TO_TIMESTAMP(:wstart, 'YYYY-MM-DD\"T\"HH24:MI'), TO_TIMESTAMP(:wend, 'YYYY-MM-DD\"T\"HH24:MI'), "
                    "'planned', :usr)",
                    {"app_id": int(data.get("app_id", 0)), "version": data.get("version", ""),
                     "rb_ver": data.get("rollback_version"), "descr": data.get("description"),
                     "reason": data.get("reason"), "owner": data.get("owner"),
                     "channel": data.get("release_channel", "PILOT"),
                     "wstart": (data.get("window_start") or "")[:16] or None,
                     "wend": (data.get("window_end") or "")[:16] or None,
                     "usr": TBControlController._username()})
                db.connection.commit()
                r = db.execute_query("SELECT MAX(ID) AS ID FROM TBC_CHANGES")
                row = TBControlController._first_row(r)
                chg_id = row["id"] if row else None
                for sid in data.get("store_ids", []):
                    db.execute_query("INSERT INTO TBC_CHANGE_STORES (CHANGE_ID, STORE_ID) VALUES (:cid, :sid)",
                                     {"cid": chg_id, "sid": int(sid)})
                db.connection.commit()
                TBControlController._add_audit("create", "change", chg_id,
                                               f"Изменение {data.get('version')} для app {data.get('app_id')}")
                return {"success": True, "data": {"id": chg_id}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def deploy_change(change_id):
        """Запускает deployment: обновляет версии на целевых устройствах
        и выполняет verification checks (раздел 32 ТЗ, симуляция)."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM TBC_CHANGES WHERE ID = :id", {"id": int(change_id)})
                chg = TBControlController._first_row(r)
                if not chg:
                    return {"success": False, "error": "Изменение не найдено"}
                if chg.get("status") not in ('planned', 'failed'):
                    return {"success": False, "error": f"Недопустимый статус: {chg.get('status')}"}
                db.execute_query("UPDATE TBC_CHANGES SET STATUS = 'in_progress' WHERE ID = :id",
                                 {"id": int(change_id)})
                # Целевые устройства: приложение установлено + магазин в scope изменения
                r2 = db.execute_query(
                    "SELECT da.DEVICE_ID, d.STATUS AS DEV_STATUS FROM TBC_DEVICE_APPS da "
                    "JOIN TBC_DEVICES d ON d.ID = da.DEVICE_ID "
                    "WHERE da.APP_ID = :app_id AND d.STORE_ID IN "
                    "(SELECT STORE_ID FROM TBC_CHANGE_STORES WHERE CHANGE_ID = :cid)",
                    {"app_id": chg["app_id"], "cid": int(change_id)})
                targets = TBControlController._rows_to_dicts(r2)
                failed = 0
                for t in targets:
                    dev_ok = t["dev_status"] in ('online', 'degraded')
                    if dev_ok:
                        db.execute_query(
                            "UPDATE TBC_DEVICE_APPS SET CURRENT_VERSION = :ver, STATUS = 'OK', "
                            "DEPLOYED_AT = SYSTIMESTAMP, LAST_CHECK = SYSTIMESTAMP "
                            "WHERE DEVICE_ID = :did AND APP_ID = :aid",
                            {"ver": chg["version"], "did": t["device_id"], "aid": chg["app_id"]})
                    else:
                        db.execute_query(
                            "UPDATE TBC_DEVICE_APPS SET STATUS = 'FAILED', LAST_CHECK = SYSTIMESTAMP "
                            "WHERE DEVICE_ID = :did AND APP_ID = :aid",
                            {"did": t["device_id"], "aid": chg["app_id"]})
                        failed += 1
                    for check in TBControlController.DEPLOY_CHECKS:
                        db.execute_query(
                            "INSERT INTO TBC_DEPLOY_CHECKS (CHANGE_ID, DEVICE_ID, CHECK_TYPE, STATUS, DETAILS) "
                            "VALUES (:cid, :did, :ct, :status, :det)",
                            {"cid": int(change_id), "did": t["device_id"], "ct": check,
                             "status": 'OK' if dev_ok else 'FAIL',
                             "det": None if dev_ok else 'Устройство offline'})
                result = 'SUCCESS' if failed == 0 else 'FAILED'
                db.execute_query(
                    "UPDATE TBC_CHANGES SET STATUS = :st, VALIDATION_RESULT = :vr WHERE ID = :id",
                    {"st": 'success' if failed == 0 else 'failed', "vr": result, "id": int(change_id)})
                # Актуализация ожидаемой версии при успешном PRODUCTION deployment
                if failed == 0 and chg.get("release_channel") == 'PRODUCTION':
                    db.execute_query("UPDATE TBC_APPLICATIONS SET EXPECTED_VERSION = :ver WHERE ID = :id",
                                     {"ver": chg["version"], "id": chg["app_id"]})
                db.connection.commit()
                TBControlController._add_audit("deploy", "change", int(change_id),
                                               f"DEPLOYMENT = {result} ({len(targets)} устройств, {failed} сбоев)")
                return {"success": True, "data": {"result": result, "devices": len(targets), "failed": failed}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def rollback_change(change_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM TBC_CHANGES WHERE ID = :id", {"id": int(change_id)})
                chg = TBControlController._first_row(r)
                if not chg:
                    return {"success": False, "error": "Изменение не найдено"}
                if not chg.get("rollback_version"):
                    return {"success": False, "error": "Rollback-версия не задана"}
                db.execute_query(
                    "UPDATE TBC_DEVICE_APPS SET CURRENT_VERSION = :ver, LAST_CHECK = SYSTIMESTAMP "
                    "WHERE APP_ID = :aid AND DEVICE_ID IN ("
                    "  SELECT d.ID FROM TBC_DEVICES d WHERE d.STORE_ID IN "
                    "  (SELECT STORE_ID FROM TBC_CHANGE_STORES WHERE CHANGE_ID = :cid))",
                    {"ver": chg["rollback_version"], "aid": chg["app_id"], "cid": int(change_id)})
                db.execute_query("UPDATE TBC_CHANGES SET STATUS = 'rolled_back' WHERE ID = :id",
                                 {"id": int(change_id)})
                db.connection.commit()
                TBControlController._add_audit("rollback", "change", int(change_id),
                                               f"Rollback → {chg['rollback_version']}")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== SLA ==========

    @staticmethod
    def get_sla():
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT t.ID, t.SERVICE_CODE, s.NAME AS SERVICE_NAME, t.TARGET_PCT, t.CURRENT_PCT, "
                    "t.PERIOD, t.UPDATED_AT FROM TBC_SLA_TARGETS t "
                    "JOIN TBC_REF_SERVICES s ON s.CODE = t.SERVICE_CODE ORDER BY s.SORT_ORDER")
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_sla(sla_id, data):
        try:
            with DatabaseModel() as db:
                sets, params = [], {"id": int(sla_id)}
                if "target_pct" in data:
                    sets.append("TARGET_PCT = :target")
                    params["target"] = float(data["target_pct"])
                if "current_pct" in data:
                    sets.append("CURRENT_PCT = :current")
                    params["current"] = float(data["current_pct"])
                if not sets:
                    return {"success": False, "error": "Нет данных для обновления"}
                sets.append("UPDATED_AT = SYSTIMESTAMP")
                db.execute_query(f"UPDATE TBC_SLA_TARGETS SET {', '.join(sets)} WHERE ID = :id", params)
                db.connection.commit()
                TBControlController._add_audit("update", "sla", int(sla_id), "Обновлён SLA")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Monitoring Center (раздел 72 ТЗ) ==========

    @staticmethod
    def monitor_overview(store_id=None, device_type=None):
        """Сводка по кассам: NOW + агрегаты за сегодня и за 7 дней,
        раздельно по HW-контуру и APP-контуру (Front Office)."""
        try:
            with DatabaseModel() as db:
                sql = ("SELECT d.ID, d.CODE, d.DEVICE_TYPE, d.STATUS, d.STORE_ID, s.CODE AS STORE_CODE, "
                       "d.CPU_PCT, d.RAM_PCT, d.DISK_PCT, d.LAST_SEEN, d.LAST_SYNC, "
                       "t.CPU_AVG_TODAY, t.CPU_MAX_TODAY, t.LAT_AVG_TODAY, t.TX_TODAY, t.ERR_TODAY, "
                       "w.CPU_AVG_WEEK, w.CPU_MAX_WEEK, w.LAT_AVG_WEEK, w.TX_WEEK, w.ERR_WEEK "
                       "FROM TBC_DEVICES d "
                       "JOIN TBC_STORES s ON s.ID = d.STORE_ID "
                       "LEFT JOIN (SELECT DEVICE_ID, "
                       "  ROUND(AVG(CASE WHEN SCOPE='hw' AND METRIC='cpu' THEN NUM_VALUE END), 1) AS CPU_AVG_TODAY, "
                       "  MAX(CASE WHEN SCOPE='hw' AND METRIC='cpu' THEN NUM_VALUE END) AS CPU_MAX_TODAY, "
                       "  ROUND(AVG(CASE WHEN SCOPE='app' AND METRIC='app_latency' THEN NUM_VALUE END), 1) AS LAT_AVG_TODAY, "
                       "  SUM(CASE WHEN SCOPE='app' AND METRIC='tx_count' THEN NUM_VALUE END) AS TX_TODAY, "
                       "  SUM(CASE WHEN SCOPE='app' AND METRIC='app_errors' THEN NUM_VALUE END) AS ERR_TODAY "
                       "  FROM TBC_METRIC_SAMPLES WHERE SAMPLED_AT >= TRUNC(SYSDATE) GROUP BY DEVICE_ID) t "
                       "ON t.DEVICE_ID = d.ID "
                       "LEFT JOIN (SELECT DEVICE_ID, "
                       "  ROUND(AVG(CASE WHEN SCOPE='hw' AND METRIC='cpu' THEN NUM_VALUE END), 1) AS CPU_AVG_WEEK, "
                       "  MAX(CASE WHEN SCOPE='hw' AND METRIC='cpu' THEN NUM_VALUE END) AS CPU_MAX_WEEK, "
                       "  ROUND(AVG(CASE WHEN SCOPE='app' AND METRIC='app_latency' THEN NUM_VALUE END), 1) AS LAT_AVG_WEEK, "
                       "  SUM(CASE WHEN SCOPE='app' AND METRIC='tx_count' THEN NUM_VALUE END) AS TX_WEEK, "
                       "  SUM(CASE WHEN SCOPE='app' AND METRIC='app_errors' THEN NUM_VALUE END) AS ERR_WEEK "
                       "  FROM TBC_METRIC_SAMPLES WHERE SAMPLED_AT >= SYSTIMESTAMP - 7 GROUP BY DEVICE_ID) w "
                       "ON w.DEVICE_ID = d.ID "
                       "WHERE d.DEVICE_TYPE IN ('POS','SCO')")
                params = {}
                if store_id:
                    sql += " AND d.STORE_ID = :store_id"
                    params["store_id"] = int(store_id)
                if device_type:
                    sql += " AND d.DEVICE_TYPE = :dtype"
                    params["dtype"] = device_type
                sql += " ORDER BY d.CODE"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def monitor_series(device_id, scope='hw', date_from=None, date_to=None, bucket='hour'):
        """Временные ряды метрик кассы за произвольный период.
        bucket: hour|day. Возвращает {metric: [{t, v}...]}."""
        try:
            with DatabaseModel() as db:
                # Двоеточие в литерале нельзя: oracledb примет ':00' за bind-переменную
                fmt = 'YYYY-MM-DD HH24' if bucket == 'hour' else 'YYYY-MM-DD'
                sql = (f"SELECT METRIC, TO_CHAR(SAMPLED_AT, '{fmt}') AS BUCKET_TS, "
                       "ROUND(AVG(NUM_VALUE), 1) AS AVG_V, MAX(NUM_VALUE) AS MAX_V, "
                       "SUM(NUM_VALUE) AS SUM_V "
                       "FROM TBC_METRIC_SAMPLES WHERE DEVICE_ID = :did AND SCOPE = :scope")
                params = {"did": int(device_id), "scope": scope}
                if date_from:
                    sql += " AND SAMPLED_AT >= TO_TIMESTAMP(:dfrom, 'YYYY-MM-DD')"
                    params["dfrom"] = date_from[:10]
                else:
                    sql += " AND SAMPLED_AT >= SYSTIMESTAMP - 7"
                if date_to:
                    sql += " AND SAMPLED_AT < TO_TIMESTAMP(:dto, 'YYYY-MM-DD') + 1"
                    params["dto"] = date_to[:10]
                sql += f" GROUP BY METRIC, TO_CHAR(SAMPLED_AT, '{fmt}') ORDER BY 2"
                r = db.execute_query(sql, params)
                rows = TBControlController._rows_to_dicts(r)
                series = {}
                for row in rows:
                    m = row["metric"]
                    # tx_count/app_errors — суммируем, остальные усредняем
                    v = row["sum_v"] if m in ('tx_count', 'app_errors') else row["avg_v"]
                    series.setdefault(m, []).append({"t": row["bucket_ts"], "v": v, "max": row["max_v"]})
                return {"success": True, "data": series}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Processing Center (раздел 73 ТЗ) ==========

    @staticmethod
    def get_proc_stats():
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_TBC_PROC_STATS")
                row = TBControlController._first_row(r) or {}
                return {"success": True, "data": row}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_nodes(node_type=None):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_TBC_NODES WHERE 1=1"
                params = {}
                if node_type:
                    sql += " AND NODE_TYPE = :ntype"
                    params["ntype"] = node_type
                sql += " ORDER BY CASE NODE_TYPE WHEN 'backoffice' THEN 3 WHEN 'central' THEN 2 ELSE 1 END, CODE"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_node(data):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO TBC_NODES (CODE, NAME, NODE_TYPE, STORE_ID, HOSTNAME, IP_ADDRESS, OS, "
                    "STATUS, APP_NAME, APP_VERSION, DB_ENGINE, DB_VERSION) "
                    "VALUES (:code, :name, :ntype, :sid, :host, :ip, :os, :status, :app, :appv, :eng, :dbv)",
                    {"code": data.get("code", ""), "name": data.get("name", ""),
                     "ntype": data.get("node_type", "store_srv"),
                     "sid": int(data["store_id"]) if data.get("store_id") else None,
                     "host": data.get("hostname"), "ip": data.get("ip_address"), "os": data.get("os"),
                     "status": data.get("status", "offline"), "app": data.get("app_name"),
                     "appv": data.get("app_version"), "eng": data.get("db_engine", "sqlite"),
                     "dbv": data.get("db_version")})
                db.connection.commit()
                r = db.execute_query("SELECT ID FROM TBC_NODES WHERE CODE = :c", {"c": data.get("code", "")})
                row = TBControlController._first_row(r)
                node_id = row["id"] if row else None
                TBControlController._add_audit("create", "node", node_id, f"Узел {data.get('code')}")
                return {"success": True, "data": {"id": node_id}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def node_heartbeat(data):
        """Heartbeat узла обработки: HW + приложение + БД (раздел 73.3)."""
        code = (data.get("node_id") or data.get("code") or "").strip()
        if not code:
            return {"success": False, "error": "node_id обязателен"}
        try:
            with DatabaseModel() as db:
                status = 'online' if (data.get("status", "OK") or "OK").upper() in ("OK", "ONLINE") else 'degraded'
                r = db.execute_query(
                    "UPDATE TBC_NODES SET STATUS = :status, LAST_SEEN = SYSTIMESTAMP, "
                    "CPU_PCT = NVL(:cpu, CPU_PCT), RAM_PCT = NVL(:ram, RAM_PCT), DISK_PCT = NVL(:disk, DISK_PCT), "
                    "APP_STATUS = NVL(:appst, APP_STATUS), APP_VERSION = NVL(:appv, APP_VERSION), "
                    "DB_STATUS = NVL(:dbst, DB_STATUS), DB_SIZE_MB = NVL(:dbsz, DB_SIZE_MB), "
                    "DB_CONNECTIONS = NVL(:dbcon, DB_CONNECTIONS) WHERE CODE = :code",
                    {"status": status, "cpu": data.get("cpu"), "ram": data.get("ram"),
                     "disk": data.get("disk"), "appst": data.get("app_status"),
                     "appv": data.get("app_version"), "dbst": data.get("db_status"),
                     "dbsz": data.get("db_size_mb"), "dbcon": data.get("db_connections"),
                     "code": code})
                db.connection.commit()
                if r.get("rowcount", 0) == 0:
                    return {"success": False, "error": f"Узел {code} не зарегистрирован"}
                return {"success": True, "data": {"code": code, "status": status}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_flows(status=None, store_id=None):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_TBC_FLOWS WHERE 1=1"
                params = {}
                if status:
                    if status == 'problems':
                        sql += " AND STATUS IN ('LAGGING','STALLED','FAIL')"
                    else:
                        sql += " AND STATUS = :status"
                        params["status"] = status
                if store_id:
                    sql += " AND STORE_CODE = (SELECT CODE FROM TBC_STORES WHERE ID = :sid)"
                    params["sid"] = int(store_id)
                sql += (" ORDER BY CASE STATUS WHEN 'FAIL' THEN 1 WHEN 'STALLED' THEN 2 "
                        "WHEN 'LAGGING' THEN 3 ELSE 4 END, CODE")
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_flow_log(flow_id, limit=50):
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID, BATCH_CODE, ROWS_SENT, ROWS_ACCEPTED, STATUS, ERROR_MSG, STARTED_AT, FINISHED_AT "
                    f"FROM TBC_FLOW_LOG WHERE FLOW_ID = :fid ORDER BY STARTED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY",
                    {"fid": int(flow_id)})
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def flow_report(flow_id, data):
        """Отчёт агента о передаче батча: обновляет статус/lag/pending потока
        и пишет журнал. Правила статусов — раздел 73.2 ТЗ."""
        try:
            with DatabaseModel() as db:
                status = (data.get("status") or "OK").upper()
                if status not in ('OK', 'FAIL', 'PARTIAL'):
                    return {"success": False, "error": "status: OK/FAIL/PARTIAL"}
                db.execute_query(
                    "INSERT INTO TBC_FLOW_LOG (FLOW_ID, BATCH_CODE, ROWS_SENT, ROWS_ACCEPTED, STATUS, "
                    "ERROR_MSG, FINISHED_AT) VALUES (:fid, :batch, :sent, :acc, :status, :err, SYSTIMESTAMP)",
                    {"fid": int(flow_id), "batch": data.get("batch_code"),
                     "sent": data.get("rows_sent", 0), "acc": data.get("rows_accepted", 0),
                     "status": status, "err": (data.get("error") or "")[:500] or None})
                if status == 'OK':
                    db.execute_query(
                        "UPDATE TBC_FLOWS SET STATUS = 'OK', LAG_MIN = 0, "
                        "PENDING_ROWS = GREATEST(0, NVL(:pending, 0)), LAST_OK_AT = SYSTIMESTAMP, "
                        "LAST_ERROR = NULL WHERE ID = :fid",
                        {"pending": data.get("pending_rows"), "fid": int(flow_id)})
                else:
                    db.execute_query(
                        "UPDATE TBC_FLOWS SET "
                        "LAG_MIN = ROUND(NVL((CAST(SYSTIMESTAMP AS DATE) - CAST(LAST_OK_AT AS DATE)) * 1440, 9999)), "
                        "PENDING_ROWS = NVL(:pending, PENDING_ROWS), LAST_ERROR = :err, "
                        "STATUS = CASE "
                        "  WHEN :st = 'FAIL' THEN 'FAIL' "
                        "  WHEN NVL((CAST(SYSTIMESTAMP AS DATE) - CAST(LAST_OK_AT AS DATE)) * 1440, 9999) > SCHEDULE_MIN * 6 THEN 'STALLED' "
                        "  WHEN NVL((CAST(SYSTIMESTAMP AS DATE) - CAST(LAST_OK_AT AS DATE)) * 1440, 9999) > SCHEDULE_MIN * 2 THEN 'LAGGING' "
                        "  ELSE STATUS END "
                        "WHERE ID = :fid",
                        {"pending": data.get("pending_rows"), "err": (data.get("error") or "")[:500] or None,
                         "st": status, "fid": int(flow_id)})
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def retry_flow(flow_id):
        """Ручной повтор передачи: имитирует успешный батч на весь pending."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT PENDING_ROWS FROM TBC_FLOWS WHERE ID = :id", {"id": int(flow_id)})
                row = TBControlController._first_row(r)
                if not row:
                    return {"success": False, "error": "Поток не найден"}
                pending = row.get("pending_rows") or 0
                db.execute_query(
                    "INSERT INTO TBC_FLOW_LOG (FLOW_ID, BATCH_CODE, ROWS_SENT, ROWS_ACCEPTED, STATUS, FINISHED_AT) "
                    "VALUES (:fid, 'RETRY-' || TO_CHAR(SYSDATE, 'HH24MISS'), :rows_cnt, :rows_cnt2, 'OK', SYSTIMESTAMP)",
                    {"fid": int(flow_id), "rows_cnt": pending, "rows_cnt2": pending})
                db.execute_query(
                    "UPDATE TBC_FLOWS SET STATUS = 'OK', LAG_MIN = 0, PENDING_ROWS = 0, "
                    "LAST_OK_AT = SYSTIMESTAMP, LAST_ERROR = NULL WHERE ID = :id", {"id": int(flow_id)})
                db.connection.commit()
                TBControlController._add_audit("retry", "flow", int(flow_id), f"Повтор передачи, {pending} строк")
                return {"success": True, "data": {"rows": pending}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Действия персонала / тикеты / климат / отчёт ==========

    @staticmethod
    def get_actions(store_id=None, unjustified=None, limit=200):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_TBC_ACTIONS WHERE 1=1"
                params = {}
                if store_id:
                    sql += " AND STORE_ID = :sid"
                    params["sid"] = int(store_id)
                if unjustified:
                    sql += " AND IS_JUSTIFIED = 'N'"
                sql += f" ORDER BY STARTED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_action(data):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO TBC_ACTIONS (STORE_ID, DEVICE_ID, EVENT_ID, ACTION_TYPE, PERFORMED_BY, "
                    "NOTE, IS_JUSTIFIED, RESULT, FINISHED_AT) "
                    "VALUES (:sid, :did, :eid, :atype, :who, :note, :just, :res, SYSTIMESTAMP)",
                    {"sid": int(data.get("store_id", 0)),
                     "did": int(data["device_id"]) if data.get("device_id") else None,
                     "eid": int(data["event_id"]) if data.get("event_id") else None,
                     "atype": data.get("action_type", "other"), "who": data.get("performed_by"),
                     "note": data.get("note"), "just": data.get("is_justified", "Y"),
                     "res": data.get("result", "fixed")})
                db.connection.commit()
                TBControlController._add_audit("create", "action", None,
                                               f"Действие {data.get('action_type')} магазин {data.get('store_id')}")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_tickets(target=None, status=None, limit=200):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_TBC_TICKETS WHERE 1=1"
                params = {}
                if target:
                    sql += " AND TARGET = :tgt"
                    params["tgt"] = target
                if status:
                    sql += " AND STATUS = :status"
                    params["status"] = status
                sql += f" ORDER BY OPENED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_ticket(data):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO TBC_SUPPORT_TICKETS (TICKET_NO, STORE_ID, TARGET, PROVIDER_NAME, "
                    "RELATED_EVENT_ID, SUBJECT, DESCRIPTION, OPENED_BY) "
                    "VALUES ('TSK-' || TO_CHAR(SYSDATE, 'YYYY') || '-' || TBC_TICKET_NUM_SEQ.NEXTVAL, "
                    ":sid, :tgt, :prov, :eid, :subj, :descr, :who)",
                    {"sid": int(data.get("store_id", 0)), "tgt": data.get("target", "network_support"),
                     "prov": data.get("provider_name"),
                     "eid": int(data["related_event_id"]) if data.get("related_event_id") else None,
                     "subj": data.get("subject", ""), "descr": data.get("description"),
                     "who": data.get("opened_by") or TBControlController._username()})
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_ticket(ticket_id, data):
        try:
            with DatabaseModel() as db:
                sets, params = [], {"id": int(ticket_id)}
                if data.get("status") == 'answered':
                    sets.append("STATUS = 'answered'")
                    sets.append("FIRST_RESPONSE_AT = NVL(FIRST_RESPONSE_AT, SYSTIMESTAMP)")
                elif data.get("status") == 'resolved':
                    sets.append("STATUS = 'resolved'")
                    sets.append("FIRST_RESPONSE_AT = NVL(FIRST_RESPONSE_AT, SYSTIMESTAMP)")
                    sets.append("RESOLVED_AT = SYSTIMESTAMP")
                if "resolution" in data:
                    sets.append("RESOLUTION = :res")
                    params["res"] = data["resolution"]
                if not sets:
                    return {"success": False, "error": "Нет данных"}
                db.execute_query(f"UPDATE TBC_SUPPORT_TICKETS SET {', '.join(sets)} WHERE ID = :id", params)
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def env_series(store_id=None, node_id=None, metric=None, hours=48):
        """Ряды климат/питание/UPS по магазину или узлу."""
        try:
            with DatabaseModel() as db:
                sql = ("SELECT METRIC, TO_CHAR(SAMPLED_AT, 'YYYY-MM-DD HH24') || 'h' AS BUCKET_TS, "
                       "ROUND(AVG(NUM_VALUE), 1) AS AVG_V, MIN(NUM_VALUE) AS MIN_V, MAX(NUM_VALUE) AS MAX_V "
                       "FROM TBC_ENV_SAMPLES WHERE SAMPLED_AT >= CAST(SYSTIMESTAMP AS TIMESTAMP) - NUMTODSINTERVAL(:hrs, 'HOUR')")
                params = {"hrs": int(hours)}
                if store_id:
                    sql += " AND STORE_ID = :sid"
                    params["sid"] = int(store_id)
                if node_id:
                    sql += " AND NODE_ID = :nid"
                    params["nid"] = int(node_id)
                if metric:
                    sql += " AND METRIC = :metric"
                    params["metric"] = metric
                sql += " GROUP BY METRIC, TO_CHAR(SAMPLED_AT, 'YYYY-MM-DD HH24') ORDER BY 2"
                r = db.execute_query(sql, params)
                rows = TBControlController._rows_to_dicts(r)
                series = {}
                for row in rows:
                    series.setdefault(row["metric"], []).append(
                        {"t": row["bucket_ts"], "v": row["avg_v"], "min": row["min_v"], "max": row["max_v"]})
                return {"success": True, "data": series}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def env_report(data):
        """Приём климат/UPS-телеметрии от агентов (или эмулятора).
        {samples: [{store_code|node_code, metric, value}, ...]}"""
        samples = data.get("samples") or []
        if not samples:
            return {"success": False, "error": "samples пуст"}
        try:
            with DatabaseModel() as db:
                ok = 0
                for smp in samples[:500]:
                    store_id = node_id = None
                    if smp.get("store_code"):
                        r = db.execute_query("SELECT ID FROM TBC_STORES WHERE CODE = :c",
                                             {"c": smp["store_code"]})
                        row = TBControlController._first_row(r)
                        store_id = row["id"] if row else None
                    if smp.get("node_code"):
                        r = db.execute_query("SELECT ID FROM TBC_NODES WHERE CODE = :c",
                                             {"c": smp["node_code"]})
                        row = TBControlController._first_row(r)
                        node_id = row["id"] if row else None
                    if not store_id and not node_id:
                        continue
                    db.execute_query(
                        "INSERT INTO TBC_ENV_SAMPLES (STORE_ID, NODE_ID, METRIC, NUM_VALUE) "
                        "VALUES (:sid, :nid, :metric, :val)",
                        {"sid": store_id, "nid": node_id,
                         "metric": smp.get("metric", ""), "val": smp.get("value", 0)})
                    ok += 1
                db.connection.commit()
                return {"success": True, "data": {"accepted": ok}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Настройки модуля ==========

    @staticmethod
    def get_settings():
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT PARAM_CODE, PARAM_VALUE FROM TBC_SETTINGS")
                rows = TBControlController._rows_to_dicts(r)
                out = {row["param_code"]: row["param_value"] for row in rows}
                # Секреты наружу не отдаём целиком
                if out.get("zabbix_token"):
                    out["zabbix_token"] = out["zabbix_token"][:4] + "***"
                if out.get("zabbix_password"):
                    out["zabbix_password"] = "***"
                return {"success": True, "data": out}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_settings(data):
        allowed = ('emulator_interval', 'zabbix_url', 'zabbix_token', 'zabbix_user', 'zabbix_password')
        try:
            with DatabaseModel() as db:
                for key in allowed:
                    if key in data and data[key] is not None:
                        if key in ('zabbix_token', 'zabbix_password') and str(data[key]).endswith('***'):
                            continue  # маскированное значение не перезаписываем
                        db.execute_query(
                            "MERGE INTO TBC_SETTINGS s USING (SELECT :c AS C FROM DUAL) src "
                            "ON (s.PARAM_CODE = src.C) "
                            "WHEN MATCHED THEN UPDATE SET s.PARAM_VALUE = :v, s.UPDATED_AT = SYSTIMESTAMP "
                            "WHEN NOT MATCHED THEN INSERT (PARAM_CODE, PARAM_VALUE) VALUES (:c2, :v2)",
                            {"c": key, "v": str(data[key]), "c2": key, "v2": str(data[key])})
                db.connection.commit()
                TBControlController._add_audit("update", "settings", None, "Настройки модуля обновлены")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_setting_raw(key):
        """Внутреннее чтение настройки без маскирования (для рантайма)."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT PARAM_VALUE FROM TBC_SETTINGS WHERE PARAM_CODE = :c", {"c": key})
                row = TBControlController._first_row(r)
                return row["param_value"] if row else None
        except Exception:
            return None

    @staticmethod
    def report_ops(days=14):
        """Отчёт «Динамика операций»: события по дням, очереди на кассах,
        действия персонала (вкл. ненужные перезагрузки), обращения в
        поддержку/банк/MEV с временем реакции, климат/UPS-сводка."""
        try:
            with DatabaseModel() as db:
                out = {}
                days = int(days)
                # 1. Динамика событий по дням и приоритетам
                r = db.execute_query(
                    "SELECT TO_CHAR(CREATED_AT, 'YYYY-MM-DD') AS D, SEVERITY, COUNT(*) AS CNT "
                    "FROM TBC_EVENTS WHERE CREATED_AT >= TRUNC(SYSDATE) - :d "
                    "GROUP BY TO_CHAR(CREATED_AT, 'YYYY-MM-DD'), SEVERITY ORDER BY 1", {"d": days})
                out["events_by_day"] = TBControlController._rows_to_dicts(r)
                # 2. Очереди на кассах: по магазинам за сегодня и максимум за неделю
                r = db.execute_query(
                    "SELECT s.ID AS STORE_ID, s.CODE, s.BRAND, s.STORE_FORMAT, "
                    "ROUND(AVG(CASE WHEN m.SAMPLED_AT >= TRUNC(SYSDATE) THEN m.NUM_VALUE END), 1) AS Q_AVG_TODAY, "
                    "MAX(CASE WHEN m.SAMPLED_AT >= TRUNC(SYSDATE) THEN m.NUM_VALUE END) AS Q_MAX_TODAY, "
                    "ROUND(AVG(m.NUM_VALUE), 1) AS Q_AVG_WEEK, MAX(m.NUM_VALUE) AS Q_MAX_WEEK "
                    "FROM TBC_METRIC_SAMPLES m "
                    "JOIN TBC_DEVICES d ON d.ID = m.DEVICE_ID "
                    "JOIN TBC_STORES s ON s.ID = d.STORE_ID "
                    "WHERE m.METRIC = 'queue_len' AND m.SAMPLED_AT >= SYSTIMESTAMP - 7 "
                    "GROUP BY s.ID, s.CODE, s.BRAND, s.STORE_FORMAT ORDER BY Q_MAX_WEEK DESC NULLS LAST")
                out["queues"] = TBControlController._rows_to_dicts(r)
                # 3. Действия персонала: сводка + ненужные перезагрузки
                r = db.execute_query(
                    "SELECT ACTION_TYPE, COUNT(*) AS CNT, "
                    "SUM(CASE WHEN IS_JUSTIFIED = 'N' THEN 1 ELSE 0 END) AS UNJUSTIFIED, "
                    "SUM(CASE WHEN RESULT = 'no_effect' THEN 1 ELSE 0 END) AS NO_EFFECT "
                    "FROM TBC_ACTIONS WHERE STARTED_AT >= TRUNC(SYSDATE) - :d "
                    "GROUP BY ACTION_TYPE ORDER BY CNT DESC", {"d": days})
                out["actions_summary"] = TBControlController._rows_to_dicts(r)
                r = db.execute_query(
                    "SELECT * FROM V_TBC_ACTIONS WHERE STARTED_AT >= TRUNC(SYSDATE) - :d "
                    "ORDER BY STARTED_AT DESC FETCH FIRST 50 ROWS ONLY", {"d": days})
                out["actions"] = TBControlController._rows_to_dicts(r)
                # 4. Обращения: время реакции по адресатам
                r = db.execute_query(
                    "SELECT TARGET, COUNT(*) AS CNT, ROUND(AVG(RESPONSE_MIN)) AS AVG_RESPONSE_MIN, "
                    "MAX(RESPONSE_MIN) AS MAX_RESPONSE_MIN, "
                    "SUM(CASE WHEN RESPONSE_MIN > 60 THEN 1 ELSE 0 END) AS DELAYED, "
                    "SUM(CASE WHEN STATUS = 'open' THEN 1 ELSE 0 END) AS STILL_OPEN "
                    "FROM V_TBC_TICKETS WHERE OPENED_AT >= TRUNC(SYSDATE) - :d "
                    "GROUP BY TARGET ORDER BY CNT DESC", {"d": days})
                out["tickets_summary"] = TBControlController._rows_to_dicts(r)
                r = db.execute_query(
                    "SELECT * FROM V_TBC_TICKETS WHERE OPENED_AT >= TRUNC(SYSDATE) - :d "
                    "ORDER BY OPENED_AT DESC FETCH FIRST 50 ROWS ONLY", {"d": days})
                out["tickets"] = TBControlController._rows_to_dicts(r)
                # 5. Климат/питание: текущие экстремумы
                r = db.execute_query(
                    "SELECT NVL(s.CODE, n.CODE) AS OBJ_CODE, s.BRAND, e.METRIC, "
                    "ROUND(MAX(e.NUM_VALUE), 1) AS MAX_V, ROUND(MIN(e.NUM_VALUE), 1) AS MIN_V, "
                    "ROUND(AVG(CASE WHEN e.SAMPLED_AT >= CAST(SYSTIMESTAMP AS TIMESTAMP) - INTERVAL '2' HOUR THEN e.NUM_VALUE END), 1) AS NOW_V "
                    "FROM TBC_ENV_SAMPLES e "
                    "LEFT JOIN TBC_STORES s ON s.ID = e.STORE_ID "
                    "LEFT JOIN TBC_NODES n ON n.ID = e.NODE_ID "
                    "WHERE e.SAMPLED_AT >= SYSTIMESTAMP - 2 "
                    "GROUP BY NVL(s.CODE, n.CODE), s.BRAND, e.METRIC ORDER BY 1, 3")
                out["env_summary"] = TBControlController._rows_to_dicts(r)
                # 6. Магазины на UPS прямо сейчас
                r = db.execute_query(
                    "SELECT DISTINCT s.CODE, s.BRAND FROM TBC_ENV_SAMPLES e "
                    "JOIN TBC_STORES s ON s.ID = e.STORE_ID "
                    "WHERE e.METRIC = 'on_ups' AND e.NUM_VALUE = 1 "
                    "AND e.SAMPLED_AT >= CAST(SYSTIMESTAMP AS TIMESTAMP) - INTERVAL '30' MINUTE")
                out["stores_on_ups"] = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": out}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== AI Diagnostic Dossiers (раздел 74 ТЗ) ==========

    @staticmethod
    def _md_table(rows, cols):
        """rows: список dict, cols: [(key, title), ...] → markdown-таблица"""
        if not rows:
            return "_нет данных_\n"
        head = "| " + " | ".join(t for _, t in cols) + " |\n"
        head += "|" + "---|" * len(cols) + "\n"
        body = ""
        for r in rows:
            body += "| " + " | ".join(str(r.get(k, '') if r.get(k) is not None else '—') for k, _ in cols) + " |\n"
        return head + body

    @staticmethod
    def generate_dossier(source_type, ref_id):
        """Генерирует исчерпывающее MD-досье сбоя для внешних AI-провайдеров
        (раздел 74 ТЗ): контекст сбоя, паспорт объекта, метрики, health,
        версии, потоки обмена, журналы, рекомендуемый workflow."""
        try:
            with DatabaseModel() as db:
                md = []
                title = ""
                severity = None
                device_id = node_id = store_id = None

                if source_type == 'event':
                    r = db.execute_query("SELECT * FROM V_TBC_EVENTS WHERE ID = :id", {"id": int(ref_id)})
                    obj = TBControlController._first_row(r)
                    if not obj:
                        return {"success": False, "error": "Событие не найдено"}
                    title = f"{obj['severity']}: {obj['problem']}"
                    severity, device_id, store_id = obj.get("severity"), obj.get("device_id"), obj.get("store_id")
                    md.append(f"## Событие #{obj['id']}\n")
                    md.append(f"- **Приоритет:** {obj['severity']} ({obj.get('severity_name')})\n"
                              f"- **Проблема:** {obj['problem']}\n"
                              f"- **Сервис:** {obj.get('service_name') or '—'}\n"
                              f"- **Статус:** {obj['status']} · Источник: {obj.get('source')}\n"
                              f"- **Correlation ID:** {obj.get('correlation_id') or '—'}\n"
                              f"- **Создано:** {obj.get('created_at')}\n")
                    if obj.get("parent_event_id"):
                        md.append(f"- **Зависимое от root cause:** событие #{obj['parent_event_id']}\n")
                    if obj.get("child_count"):
                        md.append(f"- **Root cause для:** {obj['child_count']} подавленных событий\n")
                elif source_type == 'incident':
                    r = db.execute_query("SELECT * FROM V_TBC_INCIDENTS WHERE ID = :id", {"id": int(ref_id)})
                    obj = TBControlController._first_row(r)
                    if not obj:
                        return {"success": False, "error": "Инцидент не найден"}
                    title = f"{obj['code']}: {obj['title']}"
                    severity, device_id, store_id = obj.get("severity"), obj.get("device_id"), obj.get("store_id")
                    md.append(f"## Инцидент {obj['code']}\n")
                    md.append(f"- **Приоритет:** {obj['severity']}\n- **Заголовок:** {obj['title']}\n"
                              f"- **Описание:** {obj.get('description') or '—'}\n"
                              f"- **Группа:** {obj.get('assigned_group_name') or '—'} · Исполнитель: {obj.get('assignee') or '—'}\n"
                              f"- **Статус:** {obj['status']} · SLA до: {obj.get('sla_deadline')}\n"
                              f"- **Открыт:** {obj.get('opened_at')}\n")
                elif source_type == 'flow':
                    r = db.execute_query("SELECT * FROM V_TBC_FLOWS WHERE ID = :id", {"id": int(ref_id)})
                    obj = TBControlController._first_row(r)
                    if not obj:
                        return {"success": False, "error": "Поток не найден"}
                    title = f"Поток {obj['code']}: {obj['status']}"
                    severity = 'P2' if obj['status'] in ('FAIL', 'STALLED') else 'P3'
                    device_id = obj.get("src_device_id")
                    node_id = obj.get("src_node_id")
                    md.append(f"## Поток обмена {obj['code']}\n")
                    md.append(f"- **Маршрут:** {obj.get('src_code')} → {obj.get('dst_node_code')} ({obj.get('flow_type')})\n"
                              f"- **Статус:** {obj['status']} · Отставание: {obj.get('lag_min')} мин · "
                              f"Накоплено: {obj.get('pending_rows')} строк\n"
                              f"- **Последняя успешная передача:** {obj.get('last_ok_at') or 'никогда'}\n"
                              f"- **Последняя ошибка:** `{obj.get('last_error') or '—'}`\n"
                              f"- **Периодичность:** каждые {obj.get('schedule_min')} мин · Сбоев за 24ч: {obj.get('fails_24h')}\n")
                elif source_type == 'node':
                    node_id = int(ref_id)
                elif source_type == 'service':
                    title, severity, section = tbc_services.dossier_section(db, int(ref_id)); md.append(section)
                elif source_type == 'pve':
                    title, severity, section = tbc_proxmox.dossier_section(db, int(ref_id)); md.append(section)
                else:
                    device_id = int(ref_id)

                # --- Паспорт устройства + метрики ---
                if device_id:
                    r = db.execute_query("SELECT * FROM V_TBC_DEVICES WHERE ID = :id", {"id": device_id})
                    d = TBControlController._first_row(r)
                    if d:
                        store_id = store_id or d.get("store_id")
                        if not title:
                            title = f"Устройство {d['code']}"
                        md.append(f"\n## Устройство {d['code']}\n")
                        md.append(f"- **Тип:** {d.get('device_type_name')} · Статус: **{d['status']}** · "
                                  f"Критичность: {d.get('criticality')}\n"
                                  f"- **Магазин:** {d.get('store_code')} {d.get('store_name')}\n"
                                  f"- **HW:** {d.get('manufacturer') or ''} {d.get('model') or ''} · "
                                  f"SN {d.get('serial_number') or '—'} · Asset {d.get('asset_id') or '—'}\n"
                                  f"- **ОС:** {d.get('os') or ''} {d.get('os_version') or ''} · "
                                  f"IP {d.get('ip_address') or '—'} · MAC {d.get('mac_address') or '—'}\n"
                                  f"- **Метрики NOW:** CPU {d.get('cpu_pct')}% · RAM {d.get('ram_pct')}% · "
                                  f"Disk {d.get('disk_pct')}%"
                                  + (f" · Battery {d.get('battery_pct')}% · Free {d.get('storage_free_mb')}MB · "
                                     f"Pending ops {d.get('pending_ops')}" if d.get('device_type') == 'AND' else "") + "\n"
                                  f"- **Last seen:** {d.get('last_seen')} · Last sync: {d.get('last_sync')}\n"
                                  f"- **Ответственность:** {d.get('owner_side')} / {d.get('support_group_name')}\n")
                        r2 = db.execute_query("SELECT * FROM V_TBC_VERSIONS WHERE DEVICE_ID = :id", {"id": device_id})
                        md.append("\n### Софт на устройстве\n")
                        md.append(TBControlController._md_table(
                            TBControlController._rows_to_dicts(r2),
                            [("app_name", "Приложение"), ("current_version", "Текущая"),
                             ("expected_version", "Ожидаемая"), ("status", "Статус"), ("last_check", "Проверено")]))
                        r3 = db.execute_query(
                            "SELECT COMPONENT, STATUS, LATENCY_MS, DETAILS, CHECKED_AT FROM TBC_HEALTH_CHECKS "
                            "WHERE DEVICE_ID = :id ORDER BY CHECKED_AT DESC FETCH FIRST 15 ROWS ONLY", {"id": device_id})
                        md.append("\n### Последние health checks\n")
                        md.append(TBControlController._md_table(
                            TBControlController._rows_to_dicts(r3),
                            [("component", "Компонент"), ("status", "Статус"), ("latency_ms", "мс"),
                             ("details", "Детали"), ("checked_at", "Когда")]))
                        r4 = db.execute_query(
                            "SELECT SCOPE, METRIC, ROUND(AVG(NUM_VALUE),1) AS AVG_V, MAX(NUM_VALUE) AS MAX_V "
                            "FROM TBC_METRIC_SAMPLES WHERE DEVICE_ID = :id AND SAMPLED_AT >= SYSTIMESTAMP - 1 "
                            "GROUP BY SCOPE, METRIC ORDER BY SCOPE, METRIC", {"id": device_id})
                        md.append("\n### Телеметрия за 24 часа (hw = касса-компьютер, app = Front Office)\n")
                        md.append(TBControlController._md_table(
                            TBControlController._rows_to_dicts(r4),
                            [("scope", "Контур"), ("metric", "Метрика"), ("avg_v", "Среднее"), ("max_v", "Максимум")]))
                        r5 = db.execute_query("SELECT * FROM V_TBC_FLOWS WHERE SRC_DEVICE_ID = :id", {"id": device_id})
                        md.append("\n### Потоки обмена устройства\n")
                        md.append(TBControlController._md_table(
                            TBControlController._rows_to_dicts(r5),
                            [("code", "Поток"), ("dst_node_code", "Приёмник"), ("status", "Статус"),
                             ("lag_min", "Lag, мин"), ("pending_rows", "Pending"), ("last_error", "Ошибка")]))

                # --- Узел обработки ---
                if node_id:
                    r = db.execute_query("SELECT * FROM V_TBC_NODES WHERE ID = :id", {"id": node_id})
                    n = TBControlController._first_row(r)
                    if n:
                        if not title:
                            title = f"Узел {n['code']}"
                        md.append(f"\n## Узел обработки {n['code']}\n")
                        md.append(f"- **Тип:** {n['node_type']} · Магазин: {n.get('store_code') or 'центр.офис'} · "
                                  f"Статус: **{n['status']}**\n"
                                  f"- **HW:** CPU {n.get('cpu_pct')}% · RAM {n.get('ram_pct')}% · Disk {n.get('disk_pct')}%\n"
                                  f"- **Приложение:** {n.get('app_name')} {n.get('app_version')} — {n.get('app_status')}\n"
                                  f"- **БД:** {n.get('db_engine')} {n.get('db_version')} — **{n.get('db_status')}** · "
                                  f"{n.get('db_size_mb')} MB · {n.get('db_connections')} соединений\n"
                                  f"- **Last seen:** {n.get('last_seen')}\n")
                        r2 = db.execute_query(
                            "SELECT * FROM V_TBC_FLOWS WHERE SRC_NODE_ID = :id OR DST_NODE_ID = :id2",
                            {"id": node_id, "id2": node_id})
                        md.append("\n### Потоки узла\n")
                        md.append(TBControlController._md_table(
                            TBControlController._rows_to_dicts(r2),
                            [("code", "Поток"), ("src_code", "Источник"), ("dst_node_code", "Приёмник"),
                             ("status", "Статус"), ("lag_min", "Lag, мин"), ("pending_rows", "Pending"),
                             ("last_error", "Ошибка")]))

                # --- Контекст магазина ---
                if store_id:
                    r = db.execute_query("SELECT * FROM V_TBC_STORE_HEALTH WHERE ID = :id", {"id": store_id})
                    sh = TBControlController._first_row(r)
                    if sh:
                        md.append(f"\n## Магазин {sh['code']} — {sh['name']}\n")
                        md.append(f"- **STORE_HEALTH:** {sh['health']}\n"
                                  f"- POS online: {sh['pos_online']}/{sh['pos_total']} · "
                                  f"SCO: {sh['sco_online']}/{sh['sco_total']} · "
                                  f"Android: {sh['and_online']}/{sh['and_total']}\n"
                                  f"- Открытые события: P1={sh['p1_open']} P2={sh['p2_open']} "
                                  f"P3={sh['p3_open']} P4={sh['p4_open']}\n"
                                  f"- Maintenance window: день {sh.get('maint_dow')}, "
                                  f"{sh.get('maint_time_from')}–{sh.get('maint_time_to')}\n")
                        r2 = db.execute_query(
                            "SELECT * FROM V_TBC_EVENTS WHERE STORE_ID = :id AND STATUS IN ('open','ack') "
                            "ORDER BY CREATED_AT DESC FETCH FIRST 10 ROWS ONLY", {"id": store_id})
                        md.append("\n### Открытые события магазина\n")
                        md.append(TBControlController._md_table(
                            TBControlController._rows_to_dicts(r2),
                            [("severity", "Prio"), ("device_code", "Устройство"), ("problem", "Проблема"),
                             ("status", "Статус"), ("created_at", "Создано")]))

                # --- Журнал последних передач при сбоях потоков ---
                if source_type == 'flow':
                    r = db.execute_query(
                        "SELECT BATCH_CODE, ROWS_SENT, ROWS_ACCEPTED, STATUS, ERROR_MSG, STARTED_AT "
                        "FROM TBC_FLOW_LOG WHERE FLOW_ID = :id ORDER BY STARTED_AT DESC FETCH FIRST 15 ROWS ONLY",
                        {"id": int(ref_id)})
                    md.append("\n### Журнал последних батчей\n")
                    md.append(TBControlController._md_table(
                        TBControlController._rows_to_dicts(r),
                        [("batch_code", "Батч"), ("rows_sent", "Отправлено"), ("rows_accepted", "Принято"),
                         ("status", "Статус"), ("error_msg", "Ошибка"), ("started_at", "Когда")]))

                # --- Рекомендации для AI-агента ---
                md.append("\n## Инструкция для AI-диагностики\n")
                md.append("Рекомендуемый порядок (раздел 39 ТЗ): network → dns → gateway → agent → "
                          "process → database → api → payment → fiscal → peripheral.\n\n"
                          "Доступные действия через API модуля (требуется сервисный токен, "
                          "выдаётся отдельно через Secret Store — в досье не включён):\n\n"
                          "- `POST /api/tbc/devices/<id>/diagnostics` — запустить диагностику;\n"
                          "- `POST /api/tbc/flows/<id>/retry` — повторить передачу потока;\n"
                          "- `POST /api/tbc/events/<id>/resolve` — закрыть событие после устранения;\n"
                          "- `PUT /api/tbc/incidents/<id>` — обновить инцидент (RCA-поля).\n\n"
                          "Разрешены только whitelist-действия (раздел 61-62 ТЗ): без изменения "
                          "финансовых данных, production-конфигурации и security controls.\n")

                md_text = f"# AI Diagnostic Dossier — {title}\n\n" \
                          f"_Сгенерировано TBControl. Секреты и credentials в документ не включаются._\n\n" \
                          + "".join(md)
                token = secrets.token_urlsafe(32)
                db.execute_query(
                    "INSERT INTO TBC_AI_DOSSIERS (CODE, SOURCE_TYPE, REF_ID, TITLE, SEVERITY, MD_CONTENT, ACCESS_TOKEN) "
                    "VALUES ('DSR-' || TO_CHAR(SYSDATE, 'YYYY') || '-' || LPAD(TBC_DOSSIERS_SEQ.NEXTVAL, 6, '0'), "
                    ":stype, :rid, :title, :sev, :md, :token)",
                    {"stype": source_type, "rid": int(ref_id), "title": title[:300],
                     "sev": severity, "md": md_text, "token": token})
                db.connection.commit()
                r = db.execute_query("SELECT ID, CODE FROM TBC_AI_DOSSIERS ORDER BY ID DESC FETCH FIRST 1 ROW ONLY")
                row = TBControlController._first_row(r)
                TBControlController._add_audit("generate", "dossier", row["id"] if row else None,
                                               f"AI-досье {row['code'] if row else ''}: {title[:120]}")
                return {"success": True, "data": {"id": row["id"], "code": row["code"],
                                                  "token": token, "md": md_text}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_dossiers(limit=100):
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID, CODE, SOURCE_TYPE, REF_ID, TITLE, SEVERITY, STATUS, READS_COUNT, "
                    f"CREATED_AT, UPDATED_AT FROM TBC_AI_DOSSIERS ORDER BY CREATED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY")
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_dossier_md(code, token, authenticated=False):
        """Выдача MD-досье. Для внешних AI — только по ACCESS_TOKEN."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID, MD_CONTENT, ACCESS_TOKEN FROM TBC_AI_DOSSIERS WHERE CODE = :code", {"code": code})
                row = TBControlController._first_row(r)
                if not row:
                    return {"success": False, "error": "Досье не найдено", "status": 404}
                if not authenticated and (not token or token != row.get("access_token")):
                    return {"success": False, "error": "Недействительный токен", "status": 403}
                md = row.get("md_content")
                if hasattr(md, 'read'):
                    md = md.read()
                db.execute_query(
                    "UPDATE TBC_AI_DOSSIERS SET READS_COUNT = NVL(READS_COUNT, 0) + 1, "
                    "STATUS = CASE WHEN STATUS = 'new' THEN 'sent' ELSE STATUS END WHERE ID = :id",
                    {"id": row["id"]})
                db.connection.commit()
                return {"success": True, "md": md}
        except Exception as e:
            return {"success": False, "error": str(e), "status": 500}

    @staticmethod
    def update_dossier(dossier_id, data):
        try:
            with DatabaseModel() as db:
                if data.get("status") not in ('new', 'sent', 'analyzed', 'resolved'):
                    return {"success": False, "error": "Недопустимый статус"}
                db.execute_query("UPDATE TBC_AI_DOSSIERS SET STATUS = :st WHERE ID = :id",
                                 {"st": data["status"], "id": int(dossier_id)})
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Источники мониторинга (TBC_SOURCES) ==========

    _SRC_SECRET_FIELDS = ("db_password", "api_secret")

    _SRC_MTLS_FIELDS = ("cert_path", "ca_path", "key_keychain_svc", "key_keychain_acc")

    @staticmethod
    def get_sources(kind=None, with_secrets=False):
        """Реестр источников. Секреты наружу отдаются маскированными."""
        try:
            with DatabaseModel() as db:
                sql = ("SELECT ID, CODE, NAME, KIND, DB_USER, DB_PASSWORD, DB_DSN, "
                       "API_URL, API_USER, API_SECRET, ENABLED, SORT_ORDER, NOTE, "
                       "LAST_SYNC_AT, LAST_STATUS, LAST_ERROR, "
                       "CERT_PATH, CA_PATH, CERT_FINGERPRINT, KEY_KEYCHAIN_SVC, KEY_KEYCHAIN_ACC "
                       "FROM TBC_SOURCES WHERE 1=1")
                params = {}
                if kind:
                    sql += " AND KIND = :kind"
                    params["kind"] = kind
                sql += " ORDER BY SORT_ORDER, CODE"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                if not with_secrets:
                    for row in data:
                        for f in TBControlController._SRC_SECRET_FIELDS:
                            if row.get(f):
                                row[f] = "***"
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _source_by_code(code, with_secrets=True):
        r = TBControlController.get_sources(with_secrets=with_secrets)
        if not r.get("success"):
            return None
        for row in r["data"]:
            if row.get("code") == code:
                return row
        return None

    @staticmethod
    def save_source(data):
        """Создаёт или обновляет источник. Маскированные секреты (***)
        не перезаписывают сохранённые значения."""
        code = (data.get("code") or "").strip()
        if not code:
            return {"success": False, "error": "Код источника обязателен"}
        kind = data.get("kind") or "unisim_cassa"
        if kind not in ("unisim_cassa", "zabbix", "emulator", "zabbix_svc", "proxmox"):
            return {"success": False, "error": "kind: unisim_cassa/zabbix/emulator/zabbix_svc/proxmox"}
        try:
            with DatabaseModel() as db:
                exists = TBControlController._first_row(
                    db.execute_query("SELECT ID FROM TBC_SOURCES WHERE CODE = :c", {"c": code}))
                field_map = {"name": "NAME", "kind": "KIND", "db_user": "DB_USER",
                             "db_password": "DB_PASSWORD", "db_dsn": "DB_DSN",
                             "api_url": "API_URL", "api_user": "API_USER",
                             "api_secret": "API_SECRET", "note": "NOTE",
                             "sort_order": "SORT_ORDER", "cert_path": "CERT_PATH", "ca_path": "CA_PATH",
                             "key_keychain_svc": "KEY_KEYCHAIN_SVC", "key_keychain_acc": "KEY_KEYCHAIN_ACC"}
                if exists:
                    sets, params = [], {"id": exists["id"]}
                    for key, col in field_map.items():
                        if key not in data or data[key] is None:
                            continue
                        if key in TBControlController._SRC_SECRET_FIELDS and str(data[key]).endswith("***"):
                            continue  # маскированное значение — оставляем прежнее
                        if key in TBControlController._SRC_MTLS_FIELDS and str(data[key]).strip() == "":
                            continue  # пустое поле mTLS не стирает сохранённые пути/адрес ключа
                        sets.append(f"{col} = :{key}")
                        params[key] = data[key]
                    if "enabled" in data:
                        sets.append("ENABLED = :enabled")
                        params["enabled"] = 'Y' if data["enabled"] in (True, 'Y', 'y', 1, '1') else 'N'
                    if not sets:
                        return {"success": False, "error": "Нет данных для обновления"}
                    db.execute_query(f"UPDATE TBC_SOURCES SET {', '.join(sets)} WHERE ID = :id", params)
                else:
                    db.execute_query(
                        "INSERT INTO TBC_SOURCES (CODE, NAME, KIND, DB_USER, DB_PASSWORD, DB_DSN, "
                        "API_URL, API_USER, API_SECRET, ENABLED, SORT_ORDER, NOTE) "
                        "VALUES (:code, :name, :kind, :db_user, :db_password, :db_dsn, "
                        ":api_url, :api_user, :api_secret, :enabled, :sort_order, :note)",
                        {"code": code, "name": data.get("name") or code, "kind": kind,
                         "db_user": data.get("db_user"), "db_password": data.get("db_password"),
                         "db_dsn": data.get("db_dsn"), "api_url": data.get("api_url"),
                         "api_user": data.get("api_user"), "api_secret": data.get("api_secret"),
                         "enabled": 'Y' if data.get("enabled") in (True, 'Y', 'y', 1, '1') else 'N',
                         "sort_order": int(data.get("sort_order") or 100),
                         "note": data.get("note")})
                db.connection.commit()
                TBControlController._add_audit("save", "source", None, f"Источник {code} ({kind})")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_source(code):
        try:
            with DatabaseModel() as db:
                db.execute_query("DELETE FROM TBC_CASSA_STATE WHERE SOURCE_CODE = :c", {"c": code})
                db.execute_query("DELETE FROM TBC_SERVICES WHERE SOURCE_CODE = :c", {"c": code})
                db.execute_query("DELETE FROM TBC_PVE_OBJECTS WHERE SOURCE_CODE = :c", {"c": code})
                db.execute_query("DELETE FROM TBC_SOURCES WHERE CODE = :c", {"c": code})
                db.connection.commit()
                TBControlController._add_audit("delete", "source", None, f"Источник {code} удалён")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def test_source(code):
        """Проверка соединения с источником без полного опроса."""
        src = TBControlController._source_by_code(code)
        if not src:
            return {"success": False, "error": "Источник не найден"}
        if src.get("kind") == "unisim_cassa":
            from models import unisim_cassa
            res = unisim_cassa.test_source(src)
            TBControlController._mark_source(code, res.get("success"), res.get("error"))
            return res
        if src.get("kind") in ("zabbix_svc", "proxmox"):
            from models import tbc_mtls
            mod = tbc_services if src.get("kind") == "zabbix_svc" else tbc_proxmox
            res = mod.test_source(tbc_mtls.source_row(code) or {})
            TBControlController._mark_source(code, res.get("success"), res.get("error"))
            return res
        if src.get("kind") == "zabbix":
            try:
                from tbc_emulator import ZabbixConnector
                conn = ZabbixConnector(None, src.get("api_url"), src.get("api_secret"),
                                       src.get("api_user"), src.get("api_secret"))
                ver = conn.connect()
                TBControlController._mark_source(code, True, None)
                return {"success": True, "version": ver}
            except Exception as e:
                TBControlController._mark_source(code, False, str(e))
                return {"success": False, "error": str(e)[:300]}
        return {"success": True, "message": "Встроенный источник, проверка не требуется"}

    @staticmethod
    def _mark_source(code, ok, error=None):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "UPDATE TBC_SOURCES SET LAST_SYNC_AT = SYSTIMESTAMP, LAST_STATUS = :st, "
                    "LAST_ERROR = :err WHERE CODE = :c",
                    {"st": 'OK' if ok else 'ERROR', "err": (error or "")[:500] or None, "c": code})
                db.connection.commit()
        except Exception:
            pass

    # ========== Инфраструктура: сервисы Zabbix (mTLS), Proxmox, SSL ==========
    # Логика — в models/tbc_services.py, tbc_proxmox.py, tbc_certs.py (правило №2 CLAUDE.md).

    @staticmethod
    def get_services(source_code=None, status=None, kind=None):
        return tbc_services.get_services(source_code, status, kind)

    @staticmethod
    def sync_services(source_code=None):
        return tbc_services.sync_all(source_code)

    @staticmethod
    def get_proxmox(source_code=None, obj_type=None, health=None):
        return tbc_proxmox.get_objects(source_code, obj_type, health)

    @staticmethod
    def sync_proxmox(source_code=None):
        return tbc_proxmox.sync_all(source_code)

    @staticmethod
    def get_certs():
        return tbc_certs.get_certs()

    @staticmethod
    def save_cert(data):
        return tbc_certs.save_cert(data or {})

    @staticmethod
    def delete_cert(cert_id):
        return tbc_certs.delete_cert(cert_id)

    @staticmethod
    def check_certs(cert_id=None):
        return tbc_certs.check_all(cert_id)

    # ========== Кассы UaMenu (TBC_CASSA_STATE) ==========

    @staticmethod
    def sync_cassa(code=None):
        """Опрашивает источники unisim_cassa и обновляет снимок касс.
        Кассы, ушедшие в OFFLINE, порождают события P2/P3."""
        from models import unisim_cassa
        srcs = [s for s in (TBControlController.get_sources('unisim_cassa', with_secrets=True).get("data") or [])
                if s.get("enabled") == 'Y' and (not code or s.get("code") == code)]
        if not srcs:
            return {"success": False, "error": "Нет включённых источников unisim_cassa"}
        summary = []
        for src in srcs:
            res = unisim_cassa.query_source(src)
            if not res.get("success"):
                TBControlController._mark_source(src["code"], False, res.get("error"))
                summary.append({"source": src["code"], "success": False, "error": res.get("error")})
                continue
            data = res["data"]
            try:
                with DatabaseModel() as db:
                    prev = {}
                    r = db.execute_query(
                        "SELECT DB_LINK, STATUS FROM TBC_CASSA_STATE WHERE SOURCE_CODE = :c",
                        {"c": src["code"]})
                    for row in TBControlController._rows_to_dicts(r):
                        prev[row["db_link"]] = row["status"]

                    for reg in data["registers"]:
                        db.execute_query(
                            "MERGE INTO TBC_CASSA_STATE t USING (SELECT :src AS SRC, :link AS LNK FROM DUAL) s "
                            "ON (t.SOURCE_CODE = s.SRC AND t.DB_LINK = s.LNK) "
                            "WHEN MATCHED THEN UPDATE SET t.SOURCE_NAME = :sname, t.COD_UNIV = :cod, "
                            "  t.STORE_NAME = :store, t.DB_LINK_PREFIX = :prefix, t.SHEMA = :shema, "
                            "  t.IN_PROCESS = :inproc, t.OFF_LINE = :offline, t.SERVER_ID = :srv, "
                            "  t.STATUS = :status, t.STATUS_REASON = :reason, t.LINK_ERROR = :lerr, "
                            "  t.CHECKED_AT = SYSTIMESTAMP "
                            "WHEN NOT MATCHED THEN INSERT (SOURCE_CODE, SOURCE_NAME, COD_UNIV, STORE_NAME, "
                            "  DB_LINK, DB_LINK_PREFIX, SHEMA, IN_PROCESS, OFF_LINE, SERVER_ID, STATUS, "
                            "  STATUS_REASON, LINK_ERROR) "
                            "VALUES (:src2, :sname2, :cod2, :store2, :link2, :prefix2, :shema2, :inproc2, "
                            "  :offline2, :srv2, :status2, :reason2, :lerr2)",
                            {"src": src["code"], "link": reg["db_link"], "sname": src.get("name"),
                             "cod": reg["cod_univ"], "store": reg["store_name"],
                             "prefix": reg["db_link_prefix"], "shema": reg["shema"],
                             "inproc": reg["in_process"], "offline": reg["off_line"],
                             "srv": reg["server_id"], "status": reg["status"],
                             "reason": (reg["status_reason"] or "")[:500],
                             "lerr": (reg["link_error"] or "")[:500] or None,
                             "src2": src["code"], "sname2": src.get("name"), "cod2": reg["cod_univ"],
                             "store2": reg["store_name"], "link2": reg["db_link"],
                             "prefix2": reg["db_link_prefix"], "shema2": reg["shema"],
                             "inproc2": reg["in_process"], "offline2": reg["off_line"],
                             "srv2": reg["server_id"], "status2": reg["status"],
                             "reason2": (reg["status_reason"] or "")[:500],
                             "lerr2": (reg["link_error"] or "")[:500] or None})
                        # Переход ONLINE → OFFLINE открывает событие
                        if reg["status"] == "OFFLINE" and prev.get(reg["db_link"]) != "OFFLINE":
                            db.execute_query(
                                "INSERT INTO TBC_EVENTS (SEVERITY, SERVICE_CODE, PROBLEM, STATUS, "
                                "SOURCE, CORRELATION_ID) VALUES ('P3', 'pos', :problem, 'open', "
                                "'unisim_cassa', :corr)",
                                {"problem": (f"UaMenu [{src.get('name')}] {reg['store_name']}: "
                                             f"касса {reg['db_link']} недоступна — "
                                             f"{reg['status_reason']}")[:500],
                                 "corr": f"cassa-{src['code']}-{reg['db_link_prefix']}"[:30]})
                        # Возврат в ONLINE закрывает событие
                        if reg["status"] == "ONLINE" and prev.get(reg["db_link"]) == "OFFLINE":
                            db.execute_query(
                                "UPDATE TBC_EVENTS SET STATUS = 'resolved', RESOLVED_AT = SYSTIMESTAMP "
                                "WHERE CORRELATION_ID = :corr AND STATUS IN ('open','ack')",
                                {"corr": f"cassa-{src['code']}-{reg['db_link_prefix']}"[:30]})
                    db.connection.commit()
            except Exception as e:
                TBControlController._mark_source(src["code"], False, str(e))
                summary.append({"source": src["code"], "success": False, "error": str(e)[:300]})
                continue
            TBControlController._mark_source(src["code"], True, None)
            summary.append({"source": src["code"], "success": True, "total": data["total"],
                            "online": data["online"], "offline": data["offline"],
                            "shutdown": data["shutdown"]})
        TBControlController._add_audit("sync", "cassa", None,
                                       f"Опрос касс: {len([s for s in summary if s.get('success')])}"
                                       f"/{len(summary)} источников")
        return {"success": True, "data": summary}

    @staticmethod
    def get_cassa(source_code=None, status=None):
        """Кассы, сгруппированные по магазинам (как в UaMenu Dashboard)."""
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_TBC_CASSA_STORES WHERE 1=1"
                params = {}
                if source_code:
                    sql += " AND SOURCE_CODE = :src"
                    params["src"] = source_code
                if status:
                    sql += " AND STATUS = :status"
                    params["status"] = status
                sql += " ORDER BY SOURCE_NAME, STORE_NAME"
                stores = TBControlController._rows_to_dicts(
                    db.execute_query(sql, params if params else None))

                sql2 = ("SELECT SOURCE_CODE, SOURCE_NAME, COD_UNIV, STORE_NAME, DB_LINK, "
                        "DB_LINK_PREFIX, SHEMA, SERVER_ID, OFF_LINE, STATUS, STATUS_REASON, "
                        "LINK_ERROR, CHECKED_AT FROM TBC_CASSA_STATE WHERE 1=1")
                if source_code:
                    sql2 += " AND SOURCE_CODE = :src"
                sql2 += " ORDER BY SOURCE_CODE, STORE_NAME, DB_LINK"
                regs = TBControlController._rows_to_dicts(
                    db.execute_query(sql2, {"src": source_code} if source_code else None))
                by_store = {}
                for reg in regs:
                    by_store.setdefault((reg["source_code"], reg["cod_univ"]), []).append(reg)
                for st in stores:
                    st["registers"] = by_store.get((st["source_code"], st["cod_univ"]), [])

                stats = TBControlController._first_row(
                    db.execute_query("SELECT * FROM V_TBC_CASSA_STATS")) or {}
                return {"success": True, "data": {"stores": stores, "stats": stats},
                        "total": len(stores)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Хэш-инвайты автологина (таблица INV_LINKS) ==========

    @staticmethod
    def get_invites():
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID, HASH, MODULE_CODE, TARGET_PATH, LOGIN, STATUS, EXPIRES_AT, "
                    "MAX_USES, USES_COUNT, NOTE, CREATED_BY, CREATED_AT, LAST_USED_AT "
                    "FROM INV_LINKS ORDER BY CREATED_AT DESC")
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_invite(data):
        try:
            login = (data.get("login") or "").strip()
            passwd = data.get("password") or ""
            target = (data.get("target_path") or "").strip()
            module = (data.get("module_code") or "").strip()
            if not login or not passwd:
                return {"success": False, "error": "Логин и пароль обязательны"}
            if not target.startswith("/"):
                return {"success": False, "error": "target_path должен начинаться с /"}
            if not module:
                module = target.rstrip("/").rsplit("/", 1)[-1] or "portal"
            inv_hash = secrets.token_urlsafe(24)
            with DatabaseModel() as db:
                r = db.execute_query(
                    "INSERT INTO INV_LINKS (HASH, MODULE_CODE, TARGET_PATH, LOGIN, PASSWD, "
                    "EXPIRES_AT, MAX_USES, NOTE, CREATED_BY) "
                    "VALUES (:h, :module, :target, :login, :passwd, "
                    "TO_TIMESTAMP(:expires, 'YYYY-MM-DD\"T\"HH24:MI'), :max_uses, :note, :who)",
                    {"h": inv_hash, "module": module, "target": target,
                     "login": login, "passwd": passwd,
                     "expires": (data.get("expires_at") or "")[:16] or None,
                     "max_uses": int(data["max_uses"]) if data.get("max_uses") else None,
                     "note": data.get("note"), "who": TBControlController._username()})
                if not r.get("success"):
                    return {"success": False, "error": r.get("message", "insert failed")[:200]}
                db.connection.commit()
                TBControlController._add_audit("create", "invite", None,
                                               f"Инвайт для {module} ({target}), login {login}")
                return {"success": True, "data": {"hash": inv_hash, "target_path": target,
                                                  "url": f"{target}?h={inv_hash}"}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_invite(invite_id, data):
        try:
            with DatabaseModel() as db:
                if data.get("status") in ("active", "disabled"):
                    db.execute_query("UPDATE INV_LINKS SET STATUS = :st WHERE ID = :id",
                                     {"st": data["status"], "id": int(invite_id)})
                    db.connection.commit()
                    TBControlController._add_audit(data["status"], "invite", int(invite_id),
                                                   f"Инвайт → {data['status']}")
                    return {"success": True}
                return {"success": False, "error": "status: active/disabled"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_invite(invite_id):
        try:
            with DatabaseModel() as db:
                db.execute_query("DELETE FROM INV_LINKS WHERE ID = :id", {"id": int(invite_id)})
                db.connection.commit()
                TBControlController._add_audit("delete", "invite", int(invite_id), "Инвайт удалён")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def resolve_invite(inv_hash):
        """Проверка хэша из ?h=... Возвращает {login, password} если инвайт
        активен, не истёк и не исчерпан. Использование учитывается."""
        if not inv_hash or len(inv_hash) > 64:
            return None
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID, LOGIN, PASSWD, STATUS, EXPIRES_AT, MAX_USES, USES_COUNT "
                    "FROM INV_LINKS WHERE HASH = :h", {"h": inv_hash})
                row = TBControlController._first_row(r)
                if not row or row.get("status") != "active":
                    return None
                r2 = db.execute_query(
                    "SELECT CASE WHEN EXPIRES_AT IS NOT NULL AND EXPIRES_AT < SYSTIMESTAMP THEN 1 ELSE 0 END "
                    "FROM INV_LINKS WHERE ID = :id", {"id": row["id"]})
                if r2.get("data") and r2["data"][0][0] == 1:
                    return None
                if row.get("max_uses") and (row.get("uses_count") or 0) >= row["max_uses"]:
                    return None
                db.execute_query(
                    "UPDATE INV_LINKS SET USES_COUNT = NVL(USES_COUNT, 0) + 1, "
                    "LAST_USED_AT = SYSTIMESTAMP WHERE ID = :id", {"id": row["id"]})
                db.connection.commit()
                return {"login": row["login"], "password": row["passwd"]}
        except Exception:
            return None

    # ========== Справочники и журнал ==========

    @staticmethod
    def get_refs():
        try:
            with DatabaseModel() as db:
                out = {}
                for key, sql in [
                    ("device_types", "SELECT CODE, NAME, ICON FROM TBC_REF_DEVICE_TYPES ORDER BY SORT_ORDER"),
                    ("severities", "SELECT CODE, NAME, COLOR FROM TBC_REF_SEVERITIES ORDER BY SORT_ORDER"),
                    ("channels", "SELECT CODE, NAME FROM TBC_REF_CHANNELS ORDER BY SORT_ORDER"),
                    ("support_groups", "SELECT CODE, NAME FROM TBC_REF_SUPPORT_GROUPS ORDER BY SORT_ORDER"),
                    ("services", "SELECT CODE, NAME FROM TBC_REF_SERVICES ORDER BY SORT_ORDER"),
                ]:
                    out[key] = TBControlController._rows_to_dicts(db.execute_query(sql))
                return {"success": True, "data": out}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_audit_log(limit=100, entity_type=None):
        try:
            with DatabaseModel() as db:
                sql = ("SELECT ID, ACTION, ENTITY_TYPE, ENTITY_ID, DETAILS, USERNAME, CREATED_AT "
                       "FROM TBC_EVENT_LOG WHERE 1=1")
                params = {}
                if entity_type:
                    sql += " AND ENTITY_TYPE = :etype"
                    params["etype"] = entity_type
                sql += f" ORDER BY CREATED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY"
                r = db.execute_query(sql, params if params else None)
                data = TBControlController._rows_to_dicts(r)
                return {"success": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Инициализация демо-данных ==========

    @staticmethod
    def _parse_sql_blocks(content):
        """Парсит SQL-файл на исполняемые блоки (';' и '/' для PL/SQL)."""
        raw_blocks = []
        current = []
        for line in content.split('\n'):
            if line.strip() == '/':
                if current:
                    raw_blocks.append('\n'.join(current))
                    current = []
            else:
                current.append(line)
        if current:
            raw_blocks.append('\n'.join(current))

        statements = []
        for block in raw_blocks:
            block = block.strip()
            if not block:
                continue
            upper = block.upper()
            is_plsql = any(kw in upper for kw in [
                'CREATE OR REPLACE TRIGGER', 'CREATE OR REPLACE PACKAGE',
                'CREATE OR REPLACE FUNCTION', 'CREATE OR REPLACE PROCEDURE'])
            if is_plsql:
                statements.append(block)
            else:
                for part in block.split(';'):
                    stmt = part.strip()
                    if not stmt:
                        continue
                    non_comment = [l for l in stmt.split('\n')
                                   if l.strip() and not l.strip().startswith('--')]
                    if not non_comment:
                        continue
                    if stmt.upper().strip() == 'COMMIT':
                        continue
                    statements.append(stmt)
        return statements

    @staticmethod
    def init_demo_data():
        """Создаёт TBC_* объекты и загружает демо-данные из sql/7x_tbc_*.sql"""
        log = []
        try:
            with DatabaseModel() as db:
                try:
                    r = db.execute_query("SELECT COUNT(*) AS CNT FROM TBC_STORES")
                    row = TBControlController._first_row(r)
                    if row and row.get("cnt", 0) > 0:
                        return {"success": True, "message": f"Данные уже загружены: {row['cnt']} магазинов"}
                except Exception:
                    pass  # Таблицы ещё не существуют — создадим ниже

                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sql_dir = os.path.join(base_dir, 'sql')
                files = [
                    ('70_tbc_tables.sql', 'DDL'),
                    ('71_tbc_views.sql', 'Views'),
                    ('72_tbc_demo_data.sql', 'Demo data'),
                    ('73_tbc_processing.sql', 'Processing DDL'),
                    ('74_tbc_processing_demo.sql', 'Processing demo'),
                    ('75_tbc_ops.sql', 'Ops DDL'),
                    ('76_tbc_ops_demo.sql', 'Ops demo'),
                    ('77_tbc_settings.sql', 'Settings'),
                    ('78_invite_links.sql', 'Invite links'),
                ]
                for filename, desc in files:
                    filepath = os.path.join(sql_dir, filename)
                    if not os.path.exists(filepath):
                        log.append(f"{desc}: файл не найден")
                        continue
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    stmts = TBControlController._parse_sql_blocks(content)
                    ok_count = skip_count = err_count = 0
                    last_err = ""
                    for stmt in stmts:
                        try:
                            with db.connection.cursor() as cursor:
                                cursor.execute(stmt)
                            db.connection.commit()
                            ok_count += 1
                        except Exception as e:
                            err_str = str(e)
                            ignorable = ['ORA-00955', 'ORA-02261', 'ORA-01408', 'ORA-04081',
                                         'ORA-00001', 'ORA-02264', 'ORA-02275', 'ORA-00972',
                                         'ORA-01430']  # column being added already exists
                            if any(code in err_str for code in ignorable):
                                skip_count += 1
                            else:
                                err_count += 1
                                last_err = err_str[:200]
                    status = f"{desc}: {ok_count} OK"
                    if skip_count:
                        status += f", {skip_count} уже существует"
                    if err_count:
                        status += f", {err_count} ошибок ({last_err})"
                    log.append(status)

                try:
                    r = db.execute_query("SELECT COUNT(*) AS CNT FROM TBC_STORES")
                    row = TBControlController._first_row(r)
                    cnt = row.get("cnt", 0) if row else 0
                    if cnt > 0:
                        return {"success": True,
                                "message": f"Инициализация завершена: {cnt} магазинов. " + "; ".join(log)}
                except Exception:
                    pass
                return {"success": True, "message": "Инициализация завершена. " + "; ".join(log)}
        except Exception as e:
            return {"success": False,
                    "error": f"Ошибка инициализации: {str(e)}" + (f". {'; '.join(log)}" if log else "")}
