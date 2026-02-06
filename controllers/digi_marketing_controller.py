"""
Контроллер модуля DIGI Marketing - централизованное управление
мультимедийным контентом для весов DIGI SM5300/SM6000 и касс WEB3110.

Работает с Oracle DB через пакет DIGI_MARKETING_PKG.
"""
import sys
import os
import traceback
from typing import Dict, Any, List, Optional

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseModel
from flask import session


class DigiMarketingController:
    """Контроллер для управления медиаконтентом на весах DIGI"""

    ALLOWED_IMAGE_FORMATS = ["jpg", "jpeg", "png", "bmp", "gif"]
    ALLOWED_VIDEO_FORMATS = ["mp4", "avi", "mkv", "webm"]

    @staticmethod
    def _rows_to_dicts(result: Dict) -> List[Dict]:
        """Преобразует результат execute_query в список словарей"""
        if not result.get("success") or not result.get("data"):
            return []
        cols = [c.lower() for c in (result.get("columns") or [])]
        out = []
        for row in result.get("data", []):
            d = dict(zip(cols, row))
            out.append(d)
        return out

    @staticmethod
    def _first_row(result: Dict) -> Optional[Dict]:
        rows = DigiMarketingController._rows_to_dicts(result)
        return rows[0] if rows else None

    @staticmethod
    def _username():
        return session.get('username', 'system')

    @staticmethod
    def _add_event(action, entity_type, entity_id, details=""):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO DIGI_EVENT_LOG (ACTION, ENTITY_TYPE, ENTITY_ID, DETAILS, USERNAME) "
                    "VALUES (:action, :etype, :eid, :details, :uname)",
                    {"action": action, "etype": entity_type, "eid": entity_id,
                     "details": details[:2000] if details else None,
                     "uname": DigiMarketingController._username()}
                )
                db.connection.commit()
        except Exception:
            pass

    # ========== Магазины ==========

    @staticmethod
    def get_stores():
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID, NAME, ADDRESS, REGION, TIMEZONE, STATUS, CREATED_AT, UPDATED_AT, "
                    "(SELECT COUNT(*) FROM DIGI_DEVICES dv WHERE dv.STORE_ID = s.ID) AS DEVICE_COUNT, "
                    "(SELECT COUNT(*) FROM DIGI_DEPARTMENTS dp WHERE dp.STORE_ID = s.ID) AS DEPARTMENT_COUNT "
                    "FROM DIGI_STORES s ORDER BY NAME"
                )
                stores = DigiMarketingController._rows_to_dicts(r)
                return {"success": True, "data": stores, "total": len(stores)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_store(store_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID, NAME, ADDRESS, REGION, TIMEZONE, STATUS, CREATED_AT, UPDATED_AT, "
                    "(SELECT COUNT(*) FROM DIGI_DEVICES dv WHERE dv.STORE_ID = s.ID) AS DEVICE_COUNT, "
                    "(SELECT COUNT(*) FROM DIGI_DEPARTMENTS dp WHERE dp.STORE_ID = s.ID) AS DEPARTMENT_COUNT "
                    "FROM DIGI_STORES s WHERE ID = :id", {"id": int(store_id)}
                )
                store = DigiMarketingController._first_row(r)
                if not store:
                    return {"success": False, "error": "Магазин не найден"}
                return {"success": True, "data": store}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_store(data):
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "INSERT INTO DIGI_STORES (NAME, ADDRESS, REGION, TIMEZONE, STATUS) "
                    "VALUES (:name, :address, :region, :tz, :status) "
                    "RETURNING ID INTO :out_id",
                    {"name": data.get("name", ""), "address": data.get("address", ""),
                     "region": data.get("region", ""), "tz": data.get("timezone", "Europe/Chisinau"),
                     "status": data.get("status", "active")}
                )
                # Для INSERT RETURNING используем альтернативный подход
                db.connection.commit()
                # Получаем последнюю вставленную запись
                r2 = db.execute_query(
                    "SELECT ID FROM DIGI_STORES WHERE NAME = :name ORDER BY ID DESC FETCH FIRST 1 ROW ONLY",
                    {"name": data.get("name", "")}
                )
                row = DigiMarketingController._first_row(r2)
                store_id = row["id"] if row else None
                DigiMarketingController._add_event("create", "store", store_id, f"Создан магазин: {data.get('name')}")
                return {"success": True, "data": {"id": store_id, **data}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_store(store_id, data):
        try:
            with DatabaseModel() as db:
                sets = []
                params = {"id": int(store_id)}
                for key in ["name", "address", "region", "timezone", "status"]:
                    if key in data:
                        col = key.upper() if key != "timezone" else "TIMEZONE"
                        sets.append(f"{col} = :{key}")
                        params[key] = data[key]
                if not sets:
                    return {"success": False, "error": "Нет данных для обновления"}
                db.execute_query(f"UPDATE DIGI_STORES SET {', '.join(sets)} WHERE ID = :id", params)
                db.connection.commit()
                DigiMarketingController._add_event("update", "store", int(store_id), f"Обновлен магазин")
                return DigiMarketingController.get_store(store_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_store(store_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT COUNT(*) AS CNT FROM DIGI_DEVICES WHERE STORE_ID = :id", {"id": int(store_id)})
                row = DigiMarketingController._first_row(r)
                if row and row.get("cnt", 0) > 0:
                    return {"success": False, "error": f"Нельзя удалить: {row['cnt']} устройств привязано к магазину"}
                db.execute_query("DELETE FROM DIGI_STORES WHERE ID = :id", {"id": int(store_id)})
                db.connection.commit()
                DigiMarketingController._add_event("delete", "store", int(store_id), "Удален магазин")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Отделы ==========

    @staticmethod
    def get_departments(store_id=None):
        try:
            with DatabaseModel() as db:
                sql = ("SELECT dp.ID, dp.STORE_ID, s.NAME AS STORE_NAME, dp.DEPT_TYPE, "
                       "rt.NAME AS DEPT_TYPE_NAME, dp.NAME, dp.STATUS, dp.CREATED_AT "
                       "FROM DIGI_DEPARTMENTS dp "
                       "JOIN DIGI_STORES s ON s.ID = dp.STORE_ID "
                       "JOIN DIGI_REF_DEPT_TYPES rt ON rt.CODE = dp.DEPT_TYPE "
                       "WHERE 1=1")
                params = {}
                if store_id:
                    sql += " AND dp.STORE_ID = :store_id"
                    params["store_id"] = int(store_id)
                sql += " ORDER BY s.NAME, dp.NAME"
                r = db.execute_query(sql, params if params else None)
                depts = DigiMarketingController._rows_to_dicts(r)
                return {"success": True, "data": depts, "total": len(depts)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_department(data):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO DIGI_DEPARTMENTS (STORE_ID, DEPT_TYPE, NAME) VALUES (:store_id, :dtype, :name)",
                    {"store_id": int(data.get("store_id", 0)), "dtype": data.get("type", ""),
                     "name": data.get("name", "")}
                )
                db.connection.commit()
                r = db.execute_query("SELECT MAX(ID) AS ID FROM DIGI_DEPARTMENTS")
                row = DigiMarketingController._first_row(r)
                dept_id = row["id"] if row else None
                DigiMarketingController._add_event("create", "department", dept_id, f"Создан отдел: {data.get('name')}")
                return {"success": True, "data": {"id": dept_id, **data}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_department(dept_id):
        try:
            with DatabaseModel() as db:
                db.execute_query("DELETE FROM DIGI_DEPARTMENTS WHERE ID = :id", {"id": int(dept_id)})
                db.connection.commit()
                DigiMarketingController._add_event("delete", "department", int(dept_id), "Удален отдел")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Устройства ==========

    @staticmethod
    def get_devices(store_id=None, department_id=None):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_DIGI_DEVICES WHERE 1=1"
                params = {}
                if store_id:
                    sql += " AND STORE_ID = :store_id"
                    params["store_id"] = int(store_id)
                if department_id:
                    sql += " AND DEPARTMENT_ID = :dept_id"
                    params["dept_id"] = int(department_id)
                sql += " ORDER BY STORE_NAME, NAME"
                r = db.execute_query(sql, params if params else None)
                devices = DigiMarketingController._rows_to_dicts(r)
                return {"success": True, "data": devices, "total": len(devices)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_device(device_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_DIGI_DEVICES WHERE ID = :id", {"id": int(device_id)})
                device = DigiMarketingController._first_row(r)
                if not device:
                    return {"success": False, "error": "Устройство не найдено"}
                return {"success": True, "data": device}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def register_device(data):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO DIGI_DEVICES (SERIAL_NUMBER, NAME, DEVICE_TYPE, RESOLUTION, STORE_ID, "
                    "DEPARTMENT_ID, IP_ADDRESS, STATUS, FIRMWARE_VERSION, MEMORY_TOTAL_MB) "
                    "VALUES (:sn, :name, :dtype, :res, :store_id, :dept_id, :ip, :status, :fw, :mem)",
                    {"sn": data.get("serial_number", ""), "name": data.get("name", ""),
                     "dtype": data.get("device_type", "SM5300"), "res": data.get("resolution", "800x480"),
                     "store_id": int(data.get("store_id", 0)),
                     "dept_id": int(data["department_id"]) if data.get("department_id") else None,
                     "ip": data.get("ip_address", ""), "status": "online",
                     "fw": data.get("firmware_version", ""), "mem": data.get("memory_total_mb", 512)}
                )
                db.connection.commit()
                r = db.execute_query("SELECT MAX(ID) AS ID FROM DIGI_DEVICES")
                row = DigiMarketingController._first_row(r)
                dev_id = row["id"] if row else None
                DigiMarketingController._add_event("create", "device", dev_id,
                    f"Зарегистрировано устройство: {data.get('name')} ({data.get('serial_number')})")
                return {"success": True, "data": {"id": dev_id, **data}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_device(device_id, data):
        try:
            with DatabaseModel() as db:
                sets = []
                params = {"id": int(device_id)}
                field_map = {"name": "NAME", "store_id": "STORE_ID", "department_id": "DEPARTMENT_ID",
                             "ip_address": "IP_ADDRESS", "status": "STATUS", "resolution": "RESOLUTION",
                             "firmware_version": "FIRMWARE_VERSION"}
                for key, col in field_map.items():
                    if key in data:
                        sets.append(f"{col} = :{key}")
                        params[key] = int(data[key]) if key in ("store_id", "department_id") and data[key] else data[key]
                if not sets:
                    return {"success": False, "error": "Нет данных для обновления"}
                db.execute_query(f"UPDATE DIGI_DEVICES SET {', '.join(sets)} WHERE ID = :id", params)
                db.connection.commit()
                DigiMarketingController._add_event("update", "device", int(device_id), "Обновлено устройство")
                return DigiMarketingController.get_device(device_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_device(device_id):
        try:
            with DatabaseModel() as db:
                db.execute_query("DELETE FROM DIGI_DEVICES WHERE ID = :id", {"id": int(device_id)})
                db.connection.commit()
                DigiMarketingController._add_event("delete", "device", int(device_id), "Удалено устройство")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Медиаконтент ==========

    @staticmethod
    def get_media_list(media_type=None, resolution=None):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_DIGI_MEDIA WHERE 1=1"
                params = {}
                if media_type:
                    sql += " AND MEDIA_TYPE = :mtype"
                    params["mtype"] = media_type
                if resolution:
                    sql += " AND INSTR(RESOLUTIONS, :res) > 0"
                    params["res"] = resolution
                sql += " ORDER BY CREATED_AT DESC"
                r = db.execute_query(sql, params if params else None)
                media = DigiMarketingController._rows_to_dicts(r)
                # Парсим теги и разрешения из CSV в массивы
                for m in media:
                    m["tags"] = [t.strip() for t in (m.get("tags") or "").split(",") if t.strip()]
                    m["resolutions"] = [r.strip() for r in (m.get("resolutions") or "").split(",") if r.strip()]
                return {"success": True, "data": media, "total": len(media)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_media(media_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_DIGI_MEDIA WHERE ID = :id", {"id": int(media_id)})
                m = DigiMarketingController._first_row(r)
                if not m:
                    return {"success": False, "error": "Медиафайл не найден"}
                m["tags"] = [t.strip() for t in (m.get("tags") or "").split(",") if t.strip()]
                m["resolutions"] = [r.strip() for r in (m.get("resolutions") or "").split(",") if r.strip()]
                return {"success": True, "data": m}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upload_media(data):
        filename = data.get("filename", "unknown")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in DigiMarketingController.ALLOWED_IMAGE_FORMATS:
            media_type = "image"
        elif ext in DigiMarketingController.ALLOWED_VIDEO_FORMATS:
            media_type = "video"
        else:
            return {"success": False, "error": f"Неподдерживаемый формат: {ext}"}

        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO DIGI_MEDIA (FILENAME, ORIGINAL_NAME, MEDIA_TYPE, FORMAT, SIZE_BYTES, "
                    "DESCRIPTION, DURATION_SECONDS, WIDTH, HEIGHT, CREATED_BY) "
                    "VALUES (:fn, :orig, :mtype, :fmt, :sz, :desc, :dur, :w, :h, :by)",
                    {"fn": filename, "orig": data.get("original_name", filename),
                     "mtype": media_type, "fmt": ext,
                     "sz": data.get("size_bytes", 0), "desc": data.get("description", ""),
                     "dur": data.get("duration_seconds", 0) if media_type == "video" else 0,
                     "w": data.get("width", 0), "h": data.get("height", 0),
                     "by": DigiMarketingController._username()}
                )
                db.connection.commit()
                r = db.execute_query("SELECT MAX(ID) AS ID FROM DIGI_MEDIA")
                row = DigiMarketingController._first_row(r)
                media_id = row["id"] if row else None

                # Теги
                for tag in data.get("tags", []):
                    if tag:
                        db.execute_query("INSERT INTO DIGI_MEDIA_TAGS (MEDIA_ID, TAG) VALUES (:mid, :tag)",
                                         {"mid": media_id, "tag": tag.strip()})
                # Разрешения
                for res in data.get("resolutions", []):
                    if res:
                        db.execute_query("INSERT INTO DIGI_MEDIA_RESOLUTIONS (MEDIA_ID, RESOLUTION_CODE) VALUES (:mid, :res)",
                                         {"mid": media_id, "res": res.strip()})
                db.connection.commit()
                DigiMarketingController._add_event("upload", "media", media_id, f"Загружен: {filename} ({media_type})")
                return {"success": True, "data": {"id": media_id, "filename": filename, "type": media_type}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_media(media_id, data):
        try:
            with DatabaseModel() as db:
                if "description" in data:
                    db.execute_query("UPDATE DIGI_MEDIA SET DESCRIPTION = :desc WHERE ID = :id",
                                     {"desc": data["description"], "id": int(media_id)})
                if "tags" in data:
                    db.execute_query("DELETE FROM DIGI_MEDIA_TAGS WHERE MEDIA_ID = :id", {"id": int(media_id)})
                    for tag in data["tags"]:
                        if tag:
                            db.execute_query("INSERT INTO DIGI_MEDIA_TAGS (MEDIA_ID, TAG) VALUES (:mid, :tag)",
                                             {"mid": int(media_id), "tag": tag.strip()})
                if "resolutions" in data:
                    db.execute_query("DELETE FROM DIGI_MEDIA_RESOLUTIONS WHERE MEDIA_ID = :id", {"id": int(media_id)})
                    for res in data["resolutions"]:
                        if res:
                            db.execute_query("INSERT INTO DIGI_MEDIA_RESOLUTIONS (MEDIA_ID, RESOLUTION_CODE) VALUES (:mid, :res)",
                                             {"mid": int(media_id), "res": res.strip()})
                db.connection.commit()
                DigiMarketingController._add_event("update", "media", int(media_id), "Обновлен медиафайл")
                return DigiMarketingController.get_media(media_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_media(media_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT COUNT(*) AS CNT FROM DIGI_PLAYLIST_ITEMS WHERE MEDIA_ID = :id",
                                     {"id": int(media_id)})
                row = DigiMarketingController._first_row(r)
                if row and row.get("cnt", 0) > 0:
                    return {"success": False, "error": f"Используется в {row['cnt']} плейлистах"}
                db.execute_query("DELETE FROM DIGI_MEDIA WHERE ID = :id", {"id": int(media_id)})
                db.connection.commit()
                DigiMarketingController._add_event("delete", "media", int(media_id), "Удален медиафайл")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Плейлисты ==========

    @staticmethod
    def get_playlists():
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_DIGI_PLAYLISTS ORDER BY CREATED_AT DESC")
                playlists = DigiMarketingController._rows_to_dicts(r)
                return {"success": True, "data": playlists, "total": len(playlists)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_playlist(playlist_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_DIGI_PLAYLISTS WHERE ID = :id", {"id": int(playlist_id)})
                pl = DigiMarketingController._first_row(r)
                if not pl:
                    return {"success": False, "error": "Плейлист не найден"}
                # Получаем элементы
                r2 = db.execute_query("SELECT * FROM V_DIGI_PLAYLIST_ITEMS WHERE PLAYLIST_ID = :id ORDER BY SORT_ORDER",
                                      {"id": int(playlist_id)})
                pl["items"] = DigiMarketingController._rows_to_dicts(r2)
                return {"success": True, "data": pl}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_playlist(data):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO DIGI_PLAYLISTS (NAME, DESCRIPTION, STATUS, CREATED_BY) "
                    "VALUES (:name, :desc, :status, :by)",
                    {"name": data.get("name", ""), "desc": data.get("description", ""),
                     "status": data.get("status", "draft"),
                     "by": DigiMarketingController._username()}
                )
                db.connection.commit()
                r = db.execute_query("SELECT MAX(ID) AS ID FROM DIGI_PLAYLISTS")
                row = DigiMarketingController._first_row(r)
                pl_id = row["id"] if row else None

                # Добавляем элементы
                total_dur = 0
                for item in data.get("items", []):
                    dur = item.get("duration", 5)
                    db.execute_query(
                        "INSERT INTO DIGI_PLAYLIST_ITEMS (PLAYLIST_ID, MEDIA_ID, DURATION, SORT_ORDER) "
                        "VALUES (:pl_id, :mid, :dur, :ord)",
                        {"pl_id": pl_id, "mid": int(item["media_id"]), "dur": dur,
                         "ord": item.get("order", item.get("sort_order", 0))}
                    )
                    total_dur += dur
                db.execute_query("UPDATE DIGI_PLAYLISTS SET TOTAL_DURATION = :dur WHERE ID = :id",
                                 {"dur": total_dur, "id": pl_id})
                db.connection.commit()
                DigiMarketingController._add_event("create", "playlist", pl_id, f"Создан плейлист: {data.get('name')}")
                return {"success": True, "data": {"id": pl_id, "name": data.get("name"), "total_duration": total_dur}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_playlist(playlist_id, data):
        try:
            with DatabaseModel() as db:
                if "name" in data or "description" in data or "status" in data:
                    sets = []
                    params = {"id": int(playlist_id)}
                    for key, col in [("name", "NAME"), ("description", "DESCRIPTION"), ("status", "STATUS")]:
                        if key in data:
                            sets.append(f"{col} = :{key}")
                            params[key] = data[key]
                    if sets:
                        db.execute_query(f"UPDATE DIGI_PLAYLISTS SET {', '.join(sets)} WHERE ID = :id", params)

                if "items" in data:
                    db.execute_query("DELETE FROM DIGI_PLAYLIST_ITEMS WHERE PLAYLIST_ID = :id",
                                     {"id": int(playlist_id)})
                    total_dur = 0
                    for item in data["items"]:
                        dur = item.get("duration", 5)
                        db.execute_query(
                            "INSERT INTO DIGI_PLAYLIST_ITEMS (PLAYLIST_ID, MEDIA_ID, DURATION, SORT_ORDER) "
                            "VALUES (:pl_id, :mid, :dur, :ord)",
                            {"pl_id": int(playlist_id), "mid": int(item["media_id"]), "dur": dur,
                             "ord": item.get("order", item.get("sort_order", 0))}
                        )
                        total_dur += dur
                    db.execute_query("UPDATE DIGI_PLAYLISTS SET TOTAL_DURATION = :dur WHERE ID = :id",
                                     {"dur": total_dur, "id": int(playlist_id)})

                db.connection.commit()
                DigiMarketingController._add_event("update", "playlist", int(playlist_id), "Обновлен плейлист")
                return DigiMarketingController.get_playlist(playlist_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_playlist(playlist_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT COUNT(*) AS CNT FROM DIGI_CAMPAIGNS WHERE PLAYLIST_ID = :id",
                                     {"id": int(playlist_id)})
                row = DigiMarketingController._first_row(r)
                if row and row.get("cnt", 0) > 0:
                    return {"success": False, "error": f"Используется в {row['cnt']} кампаниях"}
                db.execute_query("DELETE FROM DIGI_PLAYLISTS WHERE ID = :id", {"id": int(playlist_id)})
                db.connection.commit()
                DigiMarketingController._add_event("delete", "playlist", int(playlist_id), "Удален плейлист")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Кампании ==========

    @staticmethod
    def get_campaigns(status=None):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_DIGI_CAMPAIGNS WHERE 1=1"
                params = {}
                if status:
                    sql += " AND STATUS = :status"
                    params["status"] = status
                sql += " ORDER BY CREATED_AT DESC"
                r = db.execute_query(sql, params if params else None)
                campaigns = DigiMarketingController._rows_to_dicts(r)
                return {"success": True, "data": campaigns, "total": len(campaigns)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_campaign(campaign_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_DIGI_CAMPAIGNS WHERE ID = :id", {"id": int(campaign_id)})
                c = DigiMarketingController._first_row(r)
                if not c:
                    return {"success": False, "error": "Кампания не найдена"}
                # Получаем таргеты
                r2 = db.execute_query(
                    "SELECT TARGET_TYPE, TARGET_ID FROM DIGI_CAMPAIGN_TARGETS WHERE CAMPAIGN_ID = :id",
                    {"id": int(campaign_id)}
                )
                targets = DigiMarketingController._rows_to_dicts(r2)
                if targets:
                    c["targeting"] = {
                        "type": targets[0]["target_type"] + "s",
                        (targets[0]["target_type"] + "_ids"): [t["target_id"] for t in targets]
                    }
                else:
                    c["targeting"] = {"type": "all"}
                # Schedule
                c["schedule"] = {
                    "start_date": str(c.get("schedule_start", "")) if c.get("schedule_start") else None,
                    "end_date": str(c.get("schedule_end", "")) if c.get("schedule_end") else None,
                    "time_from": c.get("schedule_time_from"),
                    "time_to": c.get("schedule_time_to"),
                    "days_of_week": [int(d) for d in (c.get("schedule_days") or "").split(",") if d.strip()]
                }
                return {"success": True, "data": c}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_campaign(data):
        try:
            with DatabaseModel() as db:
                schedule = data.get("schedule", {})
                db.execute_query(
                    "INSERT INTO DIGI_CAMPAIGNS (NAME, DESCRIPTION, PLAYLIST_ID, PRIORITY, STATUS, "
                    "SCHEDULE_START, SCHEDULE_END, SCHEDULE_TIME_FROM, SCHEDULE_TIME_TO, SCHEDULE_DAYS, CREATED_BY) "
                    "VALUES (:name, :desc, :pl_id, :pri, 'draft', "
                    "TO_DATE(:sstart, 'YYYY-MM-DD'), TO_DATE(:send, 'YYYY-MM-DD'), :tfrom, :tto, :days, :by)",
                    {"name": data.get("name", ""), "desc": data.get("description", ""),
                     "pl_id": int(data["playlist_id"]) if data.get("playlist_id") else None,
                     "pri": data.get("priority", 5),
                     "sstart": schedule.get("start_date"), "send": schedule.get("end_date"),
                     "tfrom": schedule.get("time_from"), "tto": schedule.get("time_to"),
                     "days": ",".join(str(d) for d in schedule.get("days_of_week", [])) if schedule.get("days_of_week") else None,
                     "by": DigiMarketingController._username()}
                )
                db.connection.commit()
                r = db.execute_query("SELECT MAX(ID) AS ID FROM DIGI_CAMPAIGNS")
                row = DigiMarketingController._first_row(r)
                camp_id = row["id"] if row else None

                # Таргетинг
                targeting = data.get("targeting", {})
                target_type = targeting.get("type", "all")
                if target_type != "all":
                    singular = target_type.rstrip("s")
                    ids = targeting.get(f"{singular}_ids", targeting.get(f"store_ids", []))
                    for tid in ids:
                        db.execute_query(
                            "INSERT INTO DIGI_CAMPAIGN_TARGETS (CAMPAIGN_ID, TARGET_TYPE, TARGET_ID) "
                            "VALUES (:cid, :ttype, :tid)",
                            {"cid": camp_id, "ttype": singular, "tid": int(tid)}
                        )

                # Пересчитываем devices_total
                devices_total = DigiMarketingController._count_target_devices_db(db, camp_id, targeting)
                db.execute_query("UPDATE DIGI_CAMPAIGNS SET DEVICES_TOTAL = :cnt WHERE ID = :id",
                                 {"cnt": devices_total, "id": camp_id})
                db.connection.commit()

                DigiMarketingController._add_event("create", "campaign", camp_id, f"Создана кампания: {data.get('name')}")
                return {"success": True, "data": {"id": camp_id, "name": data.get("name"), "devices_total": devices_total}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_campaign(campaign_id, data):
        try:
            with DatabaseModel() as db:
                sets = []
                params = {"id": int(campaign_id)}
                for key, col in [("name", "NAME"), ("description", "DESCRIPTION"),
                                 ("playlist_id", "PLAYLIST_ID"), ("priority", "PRIORITY"), ("status", "STATUS")]:
                    if key in data:
                        sets.append(f"{col} = :{key}")
                        params[key] = int(data[key]) if key in ("playlist_id", "priority") and data[key] else data[key]
                schedule = data.get("schedule", {})
                if schedule:
                    for sk, col in [("start_date", "SCHEDULE_START"), ("end_date", "SCHEDULE_END")]:
                        if sk in schedule:
                            sets.append(f"{col} = TO_DATE(:{sk}, 'YYYY-MM-DD')")
                            params[sk] = schedule[sk]
                    for sk, col in [("time_from", "SCHEDULE_TIME_FROM"), ("time_to", "SCHEDULE_TIME_TO")]:
                        if sk in schedule:
                            sets.append(f"{col} = :{sk}")
                            params[sk] = schedule[sk]
                    if "days_of_week" in schedule:
                        sets.append("SCHEDULE_DAYS = :days")
                        params["days"] = ",".join(str(d) for d in schedule["days_of_week"])
                if sets:
                    db.execute_query(f"UPDATE DIGI_CAMPAIGNS SET {', '.join(sets)} WHERE ID = :id", params)

                if "targeting" in data:
                    targeting = data["targeting"]
                    db.execute_query("DELETE FROM DIGI_CAMPAIGN_TARGETS WHERE CAMPAIGN_ID = :id",
                                     {"id": int(campaign_id)})
                    target_type = targeting.get("type", "all")
                    if target_type != "all":
                        singular = target_type.rstrip("s")
                        ids = targeting.get(f"{singular}_ids", targeting.get("store_ids", []))
                        for tid in ids:
                            db.execute_query(
                                "INSERT INTO DIGI_CAMPAIGN_TARGETS (CAMPAIGN_ID, TARGET_TYPE, TARGET_ID) "
                                "VALUES (:cid, :ttype, :tid)",
                                {"cid": int(campaign_id), "ttype": singular, "tid": int(tid)}
                            )
                    devices_total = DigiMarketingController._count_target_devices_db(db, int(campaign_id), targeting)
                    db.execute_query("UPDATE DIGI_CAMPAIGNS SET DEVICES_TOTAL = :cnt WHERE ID = :id",
                                     {"cnt": devices_total, "id": int(campaign_id)})

                db.connection.commit()
                DigiMarketingController._add_event("update", "campaign", int(campaign_id), "Обновлена кампания")
                return DigiMarketingController.get_campaign(campaign_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def publish_campaign(campaign_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT PLAYLIST_ID, STATUS FROM DIGI_CAMPAIGNS WHERE ID = :id",
                                     {"id": int(campaign_id)})
                row = DigiMarketingController._first_row(r)
                if not row:
                    return {"success": False, "error": "Кампания не найдена"}
                if not row.get("playlist_id"):
                    return {"success": False, "error": "Не выбран плейлист"}
                db.execute_query(
                    "UPDATE DIGI_CAMPAIGNS SET STATUS = 'active', DELIVERY_STATUS = 'delivering', "
                    "PUBLISHED_AT = SYSTIMESTAMP WHERE ID = :id", {"id": int(campaign_id)}
                )
                db.connection.commit()

                # Симуляция доставки
                DigiMarketingController._simulate_delivery_db(db, int(campaign_id))

                DigiMarketingController._add_event("publish", "campaign", int(campaign_id), "Опубликована кампания")
                return DigiMarketingController.get_campaign(campaign_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def pause_campaign(campaign_id):
        try:
            with DatabaseModel() as db:
                db.execute_query("UPDATE DIGI_CAMPAIGNS SET STATUS = 'paused' WHERE ID = :id",
                                 {"id": int(campaign_id)})
                db.connection.commit()
                DigiMarketingController._add_event("pause", "campaign", int(campaign_id), "Приостановлена кампания")
                return DigiMarketingController.get_campaign(campaign_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def stop_campaign(campaign_id):
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "UPDATE DIGI_CAMPAIGNS SET STATUS = 'stopped', DELIVERY_STATUS = 'stopped' WHERE ID = :id",
                    {"id": int(campaign_id)}
                )
                db.connection.commit()
                DigiMarketingController._add_event("stop", "campaign", int(campaign_id), "Остановлена кампания")
                return DigiMarketingController.get_campaign(campaign_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_campaign(campaign_id):
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT STATUS FROM DIGI_CAMPAIGNS WHERE ID = :id", {"id": int(campaign_id)})
                row = DigiMarketingController._first_row(r)
                if not row:
                    return {"success": False, "error": "Кампания не найдена"}
                if row.get("status") == "active":
                    return {"success": False, "error": "Нельзя удалить активную кампанию. Сначала остановите."}
                db.execute_query("DELETE FROM DIGI_CAMPAIGNS WHERE ID = :id", {"id": int(campaign_id)})
                db.connection.commit()
                DigiMarketingController._add_event("delete", "campaign", int(campaign_id), "Удалена кампания")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Синхронизация ==========

    @staticmethod
    def get_sync_log(campaign_id=None, device_id=None, limit=50):
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_DIGI_SYNC_LOG WHERE 1=1"
                params = {}
                if campaign_id:
                    sql += " AND CAMPAIGN_ID = :cid"
                    params["cid"] = int(campaign_id)
                if device_id:
                    sql += " AND DEVICE_ID = :did"
                    params["did"] = int(device_id)
                sql += f" FETCH FIRST {int(limit)} ROWS ONLY"
                r = db.execute_query(sql, params if params else None)
                log = DigiMarketingController._rows_to_dicts(r)
                return {"success": True, "data": log, "total": len(log)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def retry_delivery(campaign_id, device_id=None):
        try:
            with DatabaseModel() as db:
                if device_id:
                    db.execute_query(
                        "INSERT INTO DIGI_SYNC_LOG (CAMPAIGN_ID, DEVICE_ID, STATUS) VALUES (:cid, :did, 'retry_delivered')",
                        {"cid": int(campaign_id), "did": int(device_id)}
                    )
                    db.execute_query("UPDATE DIGI_DEVICES SET LAST_SYNC = SYSTIMESTAMP WHERE ID = :id",
                                     {"id": int(device_id)})
                    db.connection.commit()
                else:
                    DigiMarketingController._simulate_delivery_db(db, int(campaign_id))
                DigiMarketingController._add_event("retry", "campaign", int(campaign_id), "Повторная доставка")
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_delivery_report(campaign_id=None):
        try:
            with DatabaseModel() as db:
                if campaign_id:
                    r = db.execute_query(
                        "SELECT ID AS CAMPAIGN_ID, NAME AS CAMPAIGN_NAME, STATUS, DELIVERY_STATUS, "
                        "DEVICES_TOTAL, DEVICES_SYNCED FROM DIGI_CAMPAIGNS WHERE ID = :id",
                        {"id": int(campaign_id)}
                    )
                else:
                    r = db.execute_query(
                        "SELECT ID AS CAMPAIGN_ID, NAME AS CAMPAIGN_NAME, STATUS, DELIVERY_STATUS, "
                        "DEVICES_TOTAL, DEVICES_SYNCED FROM DIGI_CAMPAIGNS ORDER BY CREATED_AT DESC"
                    )
                data = DigiMarketingController._rows_to_dicts(r)
                return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Статистика ==========

    @staticmethod
    def _empty_stats():
        """Возвращает пустую структуру статистики для безопасного отображения"""
        return {
            "stores": 0,
            "devices": {"total": 0, "online": 0, "offline": 0, "error": 0},
            "campaigns": {"total": 0, "active": 0, "draft": 0, "paused": 0, "stopped": 0},
            "media": {"total": 0, "images": 0, "videos": 0},
            "playlists": 0,
        }

    @staticmethod
    def get_dashboard_stats():
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_DIGI_DASHBOARD_STATS")
                row = DigiMarketingController._first_row(r)
                if not row:
                    return {"success": True, "data": DigiMarketingController._empty_stats()}
                return {
                    "success": True,
                    "data": {
                        "stores": row.get("total_stores", 0),
                        "devices": {
                            "total": row.get("total_devices", 0),
                            "online": row.get("online_devices", 0),
                            "offline": row.get("offline_devices", 0),
                            "error": row.get("error_devices", 0),
                        },
                        "campaigns": {
                            "total": row.get("total_campaigns", 0),
                            "active": row.get("active_campaigns", 0),
                            "draft": row.get("draft_campaigns", 0),
                            "paused": row.get("paused_campaigns", 0),
                            "stopped": row.get("stopped_campaigns", 0),
                        },
                        "media": {
                            "total": row.get("total_media", 0),
                            "images": row.get("image_media", 0),
                            "videos": row.get("video_media", 0),
                        },
                        "playlists": row.get("total_playlists", 0),
                    },
                }
        except Exception as e:
            return {"success": True, "data": DigiMarketingController._empty_stats(), "warning": str(e)}

    @staticmethod
    def get_event_log(limit=100, entity_type=None):
        try:
            with DatabaseModel() as db:
                sql = ("SELECT ID, ACTION, ENTITY_TYPE, ENTITY_ID, DETAILS, USERNAME, CREATED_AT "
                       "FROM DIGI_EVENT_LOG WHERE 1=1")
                params = {}
                if entity_type:
                    sql += " AND ENTITY_TYPE = :etype"
                    params["etype"] = entity_type
                sql += f" ORDER BY CREATED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY"
                r = db.execute_query(sql, params if params else None)
                log = DigiMarketingController._rows_to_dicts(r)
                return {"success": True, "data": log, "total": len(log)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Справочники ==========

    @staticmethod
    def get_department_types():
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT CODE AS ID, NAME FROM DIGI_REF_DEPT_TYPES ORDER BY SORT_ORDER, CODE")
                return {"success": True, "data": DigiMarketingController._rows_to_dicts(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_device_types():
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT dt.CODE AS ID, dt.NAME, "
                    "(SELECT LISTAGG(dr.RESOLUTION_CODE, ',') WITHIN GROUP (ORDER BY dr.RESOLUTION_CODE) "
                    " FROM DIGI_REF_DEVICE_RESOLUTIONS dr WHERE dr.DEVICE_TYPE_CODE = dt.CODE) AS RESOLUTIONS "
                    "FROM DIGI_REF_DEVICE_TYPES dt ORDER BY dt.SORT_ORDER, dt.CODE"
                )
                data = DigiMarketingController._rows_to_dicts(r)
                for d in data:
                    d["resolutions"] = [r.strip() for r in (d.get("resolutions") or "").split(",") if r.strip()]
                return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_resolutions():
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT CODE FROM DIGI_REF_RESOLUTIONS ORDER BY SORT_ORDER, CODE")
                data = DigiMarketingController._rows_to_dicts(r)
                return {"success": True, "data": [d["code"] for d in data]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_roles():
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT CODE AS ID, NAME, PERMISSIONS FROM DIGI_REF_ROLES ORDER BY CODE")
                data = DigiMarketingController._rows_to_dicts(r)
                for d in data:
                    d["permissions"] = [p.strip() for p in (d.get("permissions") or "").split(",") if p.strip()]
                return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Инициализация демо-данных ==========

    @staticmethod
    def _parse_sql_blocks(content):
        """Парсит SQL-файл, разделяя на исполняемые блоки.
        Обрабатывает как ';' разделители, так и '/' для PL/SQL блоков."""
        # Разделяем по '/' на отдельной строке (PL/SQL block terminator)
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
            # PL/SQL блоки (триггеры, пакеты) — исполняем целиком
            is_plsql = any(kw in upper for kw in [
                'CREATE OR REPLACE TRIGGER',
                'CREATE OR REPLACE PACKAGE',
                'CREATE OR REPLACE FUNCTION',
                'CREATE OR REPLACE PROCEDURE',
            ])
            if is_plsql:
                statements.append(block)
            else:
                # Обычный SQL — разделяем по ';'
                for part in block.split(';'):
                    stmt = part.strip()
                    if not stmt:
                        continue
                    # Пропускаем строки, состоящие только из комментариев
                    non_comment = [l for l in stmt.split('\n')
                                   if l.strip() and not l.strip().startswith('--')]
                    if not non_comment:
                        continue
                    # Пропускаем голые COMMIT (будем коммитить сами)
                    if stmt.upper().strip() == 'COMMIT':
                        continue
                    statements.append(stmt)
        return statements

    @staticmethod
    def init_demo_data():
        """Автоматически создает DDL/Views/Package и вставляет демо-данные"""
        log = []
        try:
            with DatabaseModel() as db:
                # Проверяем, есть ли уже данные
                try:
                    r = db.execute_query("SELECT COUNT(*) AS CNT FROM DIGI_STORES")
                    row = DigiMarketingController._first_row(r)
                    if row and row.get("cnt", 0) > 0:
                        return {"success": True, "message": f"Данные уже загружены: {row['cnt']} магазинов"}
                except Exception:
                    pass  # Таблицы ещё не существуют — создадим ниже

                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sql_dir = os.path.join(base_dir, 'sql')

                files = [
                    ('20_digi_tables.sql', 'DDL'),
                    ('21_digi_views.sql', 'Views'),
                    ('22_digi_package.sql', 'Package'),
                    ('23_digi_demo_data.sql', 'Demo data'),
                ]

                for filename, desc in files:
                    filepath = os.path.join(sql_dir, filename)
                    if not os.path.exists(filepath):
                        log.append(f"{desc}: файл не найден")
                        continue

                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()

                    stmts = DigiMarketingController._parse_sql_blocks(content)
                    ok_count = 0
                    skip_count = 0
                    err_count = 0
                    last_err = ""

                    for stmt in stmts:
                        try:
                            with db.connection.cursor() as cursor:
                                cursor.execute(stmt)
                            db.connection.commit()
                            ok_count += 1
                        except Exception as e:
                            err_str = str(e)
                            # Игнорируем ошибки "уже существует"
                            ignorable = ['ORA-00955', 'ORA-02261', 'ORA-01408',
                                         'ORA-04081', 'ORA-00001', 'ORA-02264',
                                         'ORA-02275', 'ORA-00972']
                            if any(code in err_str for code in ignorable):
                                skip_count += 1
                            else:
                                err_count += 1
                                last_err = err_str[:200]

                    status = f"{desc}: {ok_count} OK"
                    if skip_count:
                        status += f", {skip_count} уже существует"
                    if err_count:
                        status += f", {err_count} ошибок"
                        if last_err:
                            status += f" ({last_err})"
                    log.append(status)

                # Проверяем итог
                try:
                    r = db.execute_query("SELECT COUNT(*) AS CNT FROM DIGI_STORES")
                    row = DigiMarketingController._first_row(r)
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

    # ========== Вспомогательные методы ==========

    @staticmethod
    def _count_target_devices_db(db, campaign_id, targeting):
        target_type = targeting.get("type", "all") if targeting else "all"
        if target_type == "all":
            r = db.execute_query("SELECT COUNT(*) AS CNT FROM DIGI_DEVICES")
        else:
            r = db.execute_query(
                "SELECT COUNT(DISTINCT d.ID) AS CNT FROM DIGI_DEVICES d "
                "JOIN DIGI_CAMPAIGN_TARGETS t ON ("
                "  (t.TARGET_TYPE = 'store' AND d.STORE_ID = t.TARGET_ID) OR "
                "  (t.TARGET_TYPE = 'department' AND d.DEPARTMENT_ID = t.TARGET_ID) OR "
                "  (t.TARGET_TYPE = 'device' AND d.ID = t.TARGET_ID)"
                ") WHERE t.CAMPAIGN_ID = :cid", {"cid": campaign_id}
            )
        row = DigiMarketingController._first_row(r)
        return row.get("cnt", 0) if row else 0

    @staticmethod
    def _simulate_delivery_db(db, campaign_id):
        """Симулирует доставку контента на все целевые устройства"""
        # Получаем целевые устройства
        r = db.execute_query(
            "SELECT DISTINCT d.ID FROM DIGI_DEVICES d "
            "WHERE d.ID IN ("
            "  SELECT d2.ID FROM DIGI_DEVICES d2 "
            "  WHERE NOT EXISTS (SELECT 1 FROM DIGI_CAMPAIGN_TARGETS t WHERE t.CAMPAIGN_ID = :cid)"
            "  UNION "
            "  SELECT d3.ID FROM DIGI_DEVICES d3 "
            "  JOIN DIGI_CAMPAIGN_TARGETS t ON ("
            "    (t.TARGET_TYPE = 'store' AND d3.STORE_ID = t.TARGET_ID) OR "
            "    (t.TARGET_TYPE = 'department' AND d3.DEPARTMENT_ID = t.TARGET_ID) OR "
            "    (t.TARGET_TYPE = 'device' AND d3.ID = t.TARGET_ID)"
            "  ) WHERE t.CAMPAIGN_ID = :cid2"
            ")", {"cid": campaign_id, "cid2": campaign_id}
        )
        devices = DigiMarketingController._rows_to_dicts(r)
        synced = 0
        for dev in devices:
            db.execute_query(
                "INSERT INTO DIGI_SYNC_LOG (CAMPAIGN_ID, DEVICE_ID, STATUS) VALUES (:cid, :did, 'delivered')",
                {"cid": campaign_id, "did": dev["id"]}
            )
            db.execute_query("UPDATE DIGI_DEVICES SET LAST_SYNC = SYSTIMESTAMP WHERE ID = :id", {"id": dev["id"]})
            synced += 1

        r2 = db.execute_query("SELECT DEVICES_TOTAL FROM DIGI_CAMPAIGNS WHERE ID = :id", {"id": campaign_id})
        row = DigiMarketingController._first_row(r2)
        total = row.get("devices_total", 0) if row else 0

        db.execute_query(
            "UPDATE DIGI_CAMPAIGNS SET DEVICES_SYNCED = :synced, "
            "DELIVERY_STATUS = CASE WHEN :synced >= :total THEN 'completed' ELSE 'delivering' END "
            "WHERE ID = :id",
            {"synced": synced, "total": total, "id": campaign_id}
        )
        db.connection.commit()
