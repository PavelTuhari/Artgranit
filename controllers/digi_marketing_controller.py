"""
Контроллер модуля DIGI Marketing - централизованное управление
мультимедийным контентом для весов DIGI SM5300/SM6000 и касс WEB3110
"""
import datetime
import uuid
import os
import json
from flask import session


class DigiMarketingController:
    """Контроллер для управления медиаконтентом на весах DIGI"""

    # In-memory хранилище (в продакшене - Oracle DB)
    _stores = {}
    _departments = {}
    _devices = {}
    _media = {}
    _playlists = {}
    _campaigns = {}
    _sync_log = []
    _event_log = []

    # Типы отделов
    DEPARTMENT_TYPES = [
        {"id": "confectionery", "name": "Кондитерские изделия"},
        {"id": "culinary", "name": "Кулинария"},
        {"id": "cheese", "name": "Сыры"},
        {"id": "sausage", "name": "Колбасы"},
        {"id": "meat", "name": "Мясо"},
        {"id": "fish", "name": "Рыба"},
    ]

    # Типы устройств
    DEVICE_TYPES = [
        {"id": "SM5300", "name": "DIGI SM5300", "resolutions": ["800x480", "1024x600"]},
        {"id": "SM6000", "name": "DIGI SM6000", "resolutions": ["1024x600", "1280x800"]},
        {"id": "WEB3110", "name": "Касса WEB3110", "resolutions": ["1920x1080", "1280x1024"]},
    ]

    # Допустимые форматы
    ALLOWED_IMAGE_FORMATS = ["jpg", "jpeg", "png", "bmp", "gif"]
    ALLOWED_VIDEO_FORMATS = ["mp4", "avi", "mkv", "webm"]
    ALLOWED_RESOLUTIONS = ["800x480", "1024x600", "1280x800", "1920x1080", "1280x1024"]

    # Роли доступа
    ROLES = [
        {"id": "admin", "name": "Администратор", "permissions": ["all"]},
        {"id": "content_manager", "name": "Контент-менеджер", "permissions": ["media", "playlists", "campaigns"]},
        {"id": "marketer", "name": "Маркетолог", "permissions": ["campaigns", "reports", "playlists"]},
        {"id": "store_admin", "name": "Администратор магазина", "permissions": ["devices", "reports"]},
    ]

    @classmethod
    def _generate_id(cls):
        return str(uuid.uuid4())[:8]

    @classmethod
    def _timestamp(cls):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _add_event(cls, action, entity_type, entity_id, details=""):
        cls._event_log.insert(0, {
            "id": cls._generate_id(),
            "timestamp": cls._timestamp(),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details,
            "user": session.get('username', 'system')
        })
        if len(cls._event_log) > 500:
            cls._event_log = cls._event_log[:500]

    # ========== Магазины ==========

    @classmethod
    def get_stores(cls):
        stores = sorted(cls._stores.values(), key=lambda x: x.get('name', ''))
        return {"success": True, "data": stores, "total": len(stores), "timestamp": cls._timestamp()}

    @classmethod
    def get_store(cls, store_id):
        store = cls._stores.get(store_id)
        if not store:
            return {"success": False, "error": "Магазин не найден"}
        # Подсчитываем связанные устройства
        device_count = sum(1 for d in cls._devices.values() if d.get('store_id') == store_id)
        dept_count = sum(1 for d in cls._departments.values() if d.get('store_id') == store_id)
        store['device_count'] = device_count
        store['department_count'] = dept_count
        return {"success": True, "data": store, "timestamp": cls._timestamp()}

    @classmethod
    def create_store(cls, data):
        store_id = cls._generate_id()
        store = {
            "id": store_id,
            "name": data.get('name', ''),
            "address": data.get('address', ''),
            "region": data.get('region', ''),
            "timezone": data.get('timezone', 'Europe/Chisinau'),
            "status": data.get('status', 'active'),
            "created_at": cls._timestamp(),
            "updated_at": cls._timestamp(),
        }
        cls._stores[store_id] = store
        cls._add_event("create", "store", store_id, f"Создан магазин: {store['name']}")
        return {"success": True, "data": store, "timestamp": cls._timestamp()}

    @classmethod
    def update_store(cls, store_id, data):
        store = cls._stores.get(store_id)
        if not store:
            return {"success": False, "error": "Магазин не найден"}
        for key in ['name', 'address', 'region', 'timezone', 'status']:
            if key in data:
                store[key] = data[key]
        store['updated_at'] = cls._timestamp()
        cls._add_event("update", "store", store_id, f"Обновлен магазин: {store['name']}")
        return {"success": True, "data": store, "timestamp": cls._timestamp()}

    @classmethod
    def delete_store(cls, store_id):
        store = cls._stores.get(store_id)
        if not store:
            return {"success": False, "error": "Магазин не найден"}
        # Проверяем привязанные устройства
        linked = [d for d in cls._devices.values() if d.get('store_id') == store_id]
        if linked:
            return {"success": False, "error": f"Нельзя удалить: {len(linked)} устройств привязано к магазину"}
        del cls._stores[store_id]
        # Удаляем отделы магазина
        dept_ids = [d_id for d_id, d in cls._departments.items() if d.get('store_id') == store_id]
        for d_id in dept_ids:
            del cls._departments[d_id]
        cls._add_event("delete", "store", store_id, f"Удален магазин: {store['name']}")
        return {"success": True, "timestamp": cls._timestamp()}

    # ========== Отделы ==========

    @classmethod
    def get_departments(cls, store_id=None):
        depts = list(cls._departments.values())
        if store_id:
            depts = [d for d in depts if d.get('store_id') == store_id]
        # Обогащаем названием магазина
        for d in depts:
            store = cls._stores.get(d.get('store_id'))
            d['store_name'] = store['name'] if store else '-'
        return {"success": True, "data": depts, "total": len(depts), "timestamp": cls._timestamp()}

    @classmethod
    def create_department(cls, data):
        dept_id = cls._generate_id()
        dept = {
            "id": dept_id,
            "store_id": data.get('store_id', ''),
            "type": data.get('type', ''),
            "name": data.get('name', ''),
            "status": "active",
            "created_at": cls._timestamp(),
        }
        cls._departments[dept_id] = dept
        cls._add_event("create", "department", dept_id, f"Создан отдел: {dept['name']}")
        return {"success": True, "data": dept, "timestamp": cls._timestamp()}

    @classmethod
    def delete_department(cls, dept_id):
        dept = cls._departments.get(dept_id)
        if not dept:
            return {"success": False, "error": "Отдел не найден"}
        del cls._departments[dept_id]
        cls._add_event("delete", "department", dept_id, f"Удален отдел: {dept['name']}")
        return {"success": True, "timestamp": cls._timestamp()}

    # ========== Устройства (весы/кассы) ==========

    @classmethod
    def get_devices(cls, store_id=None, department_id=None):
        devices = list(cls._devices.values())
        if store_id:
            devices = [d for d in devices if d.get('store_id') == store_id]
        if department_id:
            devices = [d for d in devices if d.get('department_id') == department_id]
        # Обогащаем
        for d in devices:
            store = cls._stores.get(d.get('store_id'))
            dept = cls._departments.get(d.get('department_id'))
            d['store_name'] = store['name'] if store else '-'
            d['department_name'] = dept['name'] if dept else '-'
        return {"success": True, "data": devices, "total": len(devices), "timestamp": cls._timestamp()}

    @classmethod
    def get_device(cls, device_id):
        device = cls._devices.get(device_id)
        if not device:
            return {"success": False, "error": "Устройство не найдено"}
        store = cls._stores.get(device.get('store_id'))
        dept = cls._departments.get(device.get('department_id'))
        device['store_name'] = store['name'] if store else '-'
        device['department_name'] = dept['name'] if dept else '-'
        return {"success": True, "data": device, "timestamp": cls._timestamp()}

    @classmethod
    def register_device(cls, data):
        device_id = cls._generate_id()
        device = {
            "id": device_id,
            "serial_number": data.get('serial_number', ''),
            "name": data.get('name', ''),
            "device_type": data.get('device_type', 'SM5300'),
            "resolution": data.get('resolution', '800x480'),
            "store_id": data.get('store_id', ''),
            "department_id": data.get('department_id', ''),
            "ip_address": data.get('ip_address', ''),
            "status": "online",
            "last_sync": None,
            "firmware_version": data.get('firmware_version', ''),
            "memory_total_mb": data.get('memory_total_mb', 512),
            "memory_used_mb": 0,
            "created_at": cls._timestamp(),
            "updated_at": cls._timestamp(),
        }
        cls._devices[device_id] = device
        cls._add_event("create", "device", device_id, f"Зарегистрировано устройство: {device['name']} ({device['serial_number']})")
        return {"success": True, "data": device, "timestamp": cls._timestamp()}

    @classmethod
    def update_device(cls, device_id, data):
        device = cls._devices.get(device_id)
        if not device:
            return {"success": False, "error": "Устройство не найдено"}
        for key in ['name', 'store_id', 'department_id', 'ip_address', 'status', 'resolution', 'firmware_version']:
            if key in data:
                device[key] = data[key]
        device['updated_at'] = cls._timestamp()
        cls._add_event("update", "device", device_id, f"Обновлено устройство: {device['name']}")
        return {"success": True, "data": device, "timestamp": cls._timestamp()}

    @classmethod
    def delete_device(cls, device_id):
        device = cls._devices.get(device_id)
        if not device:
            return {"success": False, "error": "Устройство не найдено"}
        del cls._devices[device_id]
        cls._add_event("delete", "device", device_id, f"Удалено устройство: {device['name']}")
        return {"success": True, "timestamp": cls._timestamp()}

    # ========== Медиаконтент ==========

    @classmethod
    def get_media_list(cls, media_type=None, resolution=None):
        media = list(cls._media.values())
        if media_type:
            media = [m for m in media if m.get('type') == media_type]
        if resolution:
            media = [m for m in media if resolution in m.get('resolutions', [])]
        media.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return {"success": True, "data": media, "total": len(media), "timestamp": cls._timestamp()}

    @classmethod
    def get_media(cls, media_id):
        m = cls._media.get(media_id)
        if not m:
            return {"success": False, "error": "Медиафайл не найден"}
        return {"success": True, "data": m, "timestamp": cls._timestamp()}

    @classmethod
    def upload_media(cls, data):
        media_id = cls._generate_id()
        filename = data.get('filename', 'unknown')
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        if ext in cls.ALLOWED_IMAGE_FORMATS:
            media_type = 'image'
        elif ext in cls.ALLOWED_VIDEO_FORMATS:
            media_type = 'video'
        else:
            return {"success": False, "error": f"Неподдерживаемый формат: {ext}"}

        media = {
            "id": media_id,
            "filename": filename,
            "original_name": data.get('original_name', filename),
            "type": media_type,
            "format": ext,
            "size_bytes": data.get('size_bytes', 0),
            "resolutions": data.get('resolutions', []),
            "description": data.get('description', ''),
            "tags": data.get('tags', []),
            "duration_seconds": data.get('duration_seconds', 0) if media_type == 'video' else 0,
            "width": data.get('width', 0),
            "height": data.get('height', 0),
            "status": "ready",
            "created_at": cls._timestamp(),
            "created_by": session.get('username', 'system'),
        }
        cls._media[media_id] = media
        cls._add_event("upload", "media", media_id, f"Загружен: {filename} ({media_type})")
        return {"success": True, "data": media, "timestamp": cls._timestamp()}

    @classmethod
    def update_media(cls, media_id, data):
        m = cls._media.get(media_id)
        if not m:
            return {"success": False, "error": "Медиафайл не найден"}
        for key in ['description', 'tags', 'resolutions']:
            if key in data:
                m[key] = data[key]
        cls._add_event("update", "media", media_id, f"Обновлен: {m['filename']}")
        return {"success": True, "data": m, "timestamp": cls._timestamp()}

    @classmethod
    def delete_media(cls, media_id):
        m = cls._media.get(media_id)
        if not m:
            return {"success": False, "error": "Медиафайл не найден"}
        # Проверяем использование в плейлистах
        used_in = []
        for pl in cls._playlists.values():
            if media_id in [item.get('media_id') for item in pl.get('items', [])]:
                used_in.append(pl.get('name', pl['id']))
        if used_in:
            return {"success": False, "error": f"Используется в плейлистах: {', '.join(used_in)}"}
        del cls._media[media_id]
        cls._add_event("delete", "media", media_id, f"Удален: {m['filename']}")
        return {"success": True, "timestamp": cls._timestamp()}

    # ========== Плейлисты ==========

    @classmethod
    def get_playlists(cls):
        playlists = list(cls._playlists.values())
        for pl in playlists:
            pl['item_count'] = len(pl.get('items', []))
        playlists.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return {"success": True, "data": playlists, "total": len(playlists), "timestamp": cls._timestamp()}

    @classmethod
    def get_playlist(cls, playlist_id):
        pl = cls._playlists.get(playlist_id)
        if not pl:
            return {"success": False, "error": "Плейлист не найден"}
        # Обогащаем данными медиа
        enriched_items = []
        for item in pl.get('items', []):
            media = cls._media.get(item.get('media_id'))
            enriched_items.append({
                **item,
                "media": media
            })
        pl['items'] = enriched_items
        return {"success": True, "data": pl, "timestamp": cls._timestamp()}

    @classmethod
    def create_playlist(cls, data):
        pl_id = cls._generate_id()
        playlist = {
            "id": pl_id,
            "name": data.get('name', ''),
            "description": data.get('description', ''),
            "items": data.get('items', []),
            "total_duration": 0,
            "status": "draft",
            "created_at": cls._timestamp(),
            "updated_at": cls._timestamp(),
            "created_by": session.get('username', 'system'),
        }
        # Считаем длительность
        for item in playlist['items']:
            media = cls._media.get(item.get('media_id'))
            if media:
                playlist['total_duration'] += item.get('duration', media.get('duration_seconds', 5))
        cls._playlists[pl_id] = playlist
        cls._add_event("create", "playlist", pl_id, f"Создан плейлист: {playlist['name']}")
        return {"success": True, "data": playlist, "timestamp": cls._timestamp()}

    @classmethod
    def update_playlist(cls, playlist_id, data):
        pl = cls._playlists.get(playlist_id)
        if not pl:
            return {"success": False, "error": "Плейлист не найден"}
        for key in ['name', 'description', 'items', 'status']:
            if key in data:
                pl[key] = data[key]
        # Пересчитываем длительность
        pl['total_duration'] = 0
        for item in pl.get('items', []):
            media = cls._media.get(item.get('media_id'))
            if media:
                pl['total_duration'] += item.get('duration', media.get('duration_seconds', 5))
        pl['updated_at'] = cls._timestamp()
        cls._add_event("update", "playlist", playlist_id, f"Обновлен плейлист: {pl['name']}")
        return {"success": True, "data": pl, "timestamp": cls._timestamp()}

    @classmethod
    def delete_playlist(cls, playlist_id):
        pl = cls._playlists.get(playlist_id)
        if not pl:
            return {"success": False, "error": "Плейлист не найден"}
        # Проверяем использование в кампаниях
        used_in = [c.get('name', c['id']) for c in cls._campaigns.values() if c.get('playlist_id') == playlist_id]
        if used_in:
            return {"success": False, "error": f"Используется в кампаниях: {', '.join(used_in)}"}
        del cls._playlists[playlist_id]
        cls._add_event("delete", "playlist", playlist_id, f"Удален плейлист: {pl['name']}")
        return {"success": True, "timestamp": cls._timestamp()}

    # ========== Кампании ==========

    @classmethod
    def get_campaigns(cls, status=None):
        campaigns = list(cls._campaigns.values())
        if status:
            campaigns = [c for c in campaigns if c.get('status') == status]
        # Обогащаем
        for c in campaigns:
            pl = cls._playlists.get(c.get('playlist_id'))
            c['playlist_name'] = pl['name'] if pl else '-'
            c['target_summary'] = cls._build_target_summary(c.get('targeting', {}))
        campaigns.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return {"success": True, "data": campaigns, "total": len(campaigns), "timestamp": cls._timestamp()}

    @classmethod
    def get_campaign(cls, campaign_id):
        c = cls._campaigns.get(campaign_id)
        if not c:
            return {"success": False, "error": "Кампания не найдена"}
        pl = cls._playlists.get(c.get('playlist_id'))
        c['playlist'] = pl
        c['target_summary'] = cls._build_target_summary(c.get('targeting', {}))
        return {"success": True, "data": c, "timestamp": cls._timestamp()}

    @classmethod
    def create_campaign(cls, data):
        campaign_id = cls._generate_id()
        campaign = {
            "id": campaign_id,
            "name": data.get('name', ''),
            "description": data.get('description', ''),
            "playlist_id": data.get('playlist_id', ''),
            "targeting": data.get('targeting', {}),
            "schedule": data.get('schedule', {}),
            "priority": data.get('priority', 5),
            "status": "draft",
            "delivery_status": "pending",
            "devices_total": 0,
            "devices_synced": 0,
            "created_at": cls._timestamp(),
            "updated_at": cls._timestamp(),
            "created_by": session.get('username', 'system'),
        }
        # Подсчитываем целевые устройства
        campaign['devices_total'] = cls._count_target_devices(campaign['targeting'])
        cls._campaigns[campaign_id] = campaign
        cls._add_event("create", "campaign", campaign_id, f"Создана кампания: {campaign['name']}")
        return {"success": True, "data": campaign, "timestamp": cls._timestamp()}

    @classmethod
    def update_campaign(cls, campaign_id, data):
        c = cls._campaigns.get(campaign_id)
        if not c:
            return {"success": False, "error": "Кампания не найдена"}
        for key in ['name', 'description', 'playlist_id', 'targeting', 'schedule', 'priority', 'status']:
            if key in data:
                c[key] = data[key]
        if 'targeting' in data:
            c['devices_total'] = cls._count_target_devices(c['targeting'])
        c['updated_at'] = cls._timestamp()
        cls._add_event("update", "campaign", campaign_id, f"Обновлена кампания: {c['name']}")
        return {"success": True, "data": c, "timestamp": cls._timestamp()}

    @classmethod
    def publish_campaign(cls, campaign_id):
        c = cls._campaigns.get(campaign_id)
        if not c:
            return {"success": False, "error": "Кампания не найдена"}
        if not c.get('playlist_id'):
            return {"success": False, "error": "Не выбран плейлист"}
        c['status'] = 'active'
        c['delivery_status'] = 'delivering'
        c['published_at'] = cls._timestamp()
        c['updated_at'] = cls._timestamp()
        # Имитация начала доставки
        cls._add_event("publish", "campaign", campaign_id, f"Опубликована кампания: {c['name']}")
        cls._simulate_delivery(campaign_id)
        return {"success": True, "data": c, "timestamp": cls._timestamp()}

    @classmethod
    def pause_campaign(cls, campaign_id):
        c = cls._campaigns.get(campaign_id)
        if not c:
            return {"success": False, "error": "Кампания не найдена"}
        c['status'] = 'paused'
        c['updated_at'] = cls._timestamp()
        cls._add_event("pause", "campaign", campaign_id, f"Приостановлена кампания: {c['name']}")
        return {"success": True, "data": c, "timestamp": cls._timestamp()}

    @classmethod
    def stop_campaign(cls, campaign_id):
        c = cls._campaigns.get(campaign_id)
        if not c:
            return {"success": False, "error": "Кампания не найдена"}
        c['status'] = 'stopped'
        c['delivery_status'] = 'stopped'
        c['updated_at'] = cls._timestamp()
        cls._add_event("stop", "campaign", campaign_id, f"Остановлена кампания: {c['name']}")
        return {"success": True, "data": c, "timestamp": cls._timestamp()}

    @classmethod
    def delete_campaign(cls, campaign_id):
        c = cls._campaigns.get(campaign_id)
        if not c:
            return {"success": False, "error": "Кампания не найдена"}
        if c.get('status') == 'active':
            return {"success": False, "error": "Нельзя удалить активную кампанию. Сначала остановите."}
        del cls._campaigns[campaign_id]
        cls._add_event("delete", "campaign", campaign_id, f"Удалена кампания: {c['name']}")
        return {"success": True, "timestamp": cls._timestamp()}

    # ========== Синхронизация и доставка ==========

    @classmethod
    def _simulate_delivery(cls, campaign_id):
        """Имитация доставки контента на устройства"""
        c = cls._campaigns.get(campaign_id)
        if not c:
            return
        target_devices = cls._get_target_devices(c.get('targeting', {}))
        synced = 0
        for device in target_devices:
            synced += 1
            cls._sync_log.insert(0, {
                "id": cls._generate_id(),
                "campaign_id": campaign_id,
                "device_id": device['id'],
                "device_name": device.get('name', ''),
                "status": "delivered",
                "timestamp": cls._timestamp(),
            })
            device['last_sync'] = cls._timestamp()
        c['devices_synced'] = synced
        if synced == c['devices_total']:
            c['delivery_status'] = 'completed'
        if len(cls._sync_log) > 1000:
            cls._sync_log = cls._sync_log[:1000]

    @classmethod
    def get_sync_log(cls, campaign_id=None, device_id=None, limit=50):
        log = cls._sync_log
        if campaign_id:
            log = [l for l in log if l.get('campaign_id') == campaign_id]
        if device_id:
            log = [l for l in log if l.get('device_id') == device_id]
        return {"success": True, "data": log[:limit], "total": len(log), "timestamp": cls._timestamp()}

    @classmethod
    def retry_delivery(cls, campaign_id, device_id=None):
        c = cls._campaigns.get(campaign_id)
        if not c:
            return {"success": False, "error": "Кампания не найдена"}
        if device_id:
            device = cls._devices.get(device_id)
            if device:
                cls._sync_log.insert(0, {
                    "id": cls._generate_id(),
                    "campaign_id": campaign_id,
                    "device_id": device_id,
                    "device_name": device.get('name', ''),
                    "status": "retry_delivered",
                    "timestamp": cls._timestamp(),
                })
                device['last_sync'] = cls._timestamp()
        else:
            cls._simulate_delivery(campaign_id)
        cls._add_event("retry", "campaign", campaign_id, "Повторная доставка")
        return {"success": True, "timestamp": cls._timestamp()}

    # ========== Мониторинг и отчеты ==========

    @classmethod
    def get_dashboard_stats(cls):
        now = cls._timestamp()
        total_devices = len(cls._devices)
        online_devices = sum(1 for d in cls._devices.values() if d.get('status') == 'online')
        offline_devices = sum(1 for d in cls._devices.values() if d.get('status') == 'offline')
        error_devices = sum(1 for d in cls._devices.values() if d.get('status') == 'error')
        active_campaigns = sum(1 for c in cls._campaigns.values() if c.get('status') == 'active')
        total_media = len(cls._media)
        total_playlists = len(cls._playlists)
        total_stores = len(cls._stores)

        return {
            "success": True,
            "data": {
                "stores": total_stores,
                "devices": {
                    "total": total_devices,
                    "online": online_devices,
                    "offline": offline_devices,
                    "error": error_devices,
                },
                "campaigns": {
                    "total": len(cls._campaigns),
                    "active": active_campaigns,
                    "draft": sum(1 for c in cls._campaigns.values() if c.get('status') == 'draft'),
                    "paused": sum(1 for c in cls._campaigns.values() if c.get('status') == 'paused'),
                    "stopped": sum(1 for c in cls._campaigns.values() if c.get('status') == 'stopped'),
                },
                "media": {
                    "total": total_media,
                    "images": sum(1 for m in cls._media.values() if m.get('type') == 'image'),
                    "videos": sum(1 for m in cls._media.values() if m.get('type') == 'video'),
                },
                "playlists": total_playlists,
            },
            "timestamp": now,
        }

    @classmethod
    def get_event_log(cls, limit=100, entity_type=None):
        log = cls._event_log
        if entity_type:
            log = [l for l in log if l.get('entity_type') == entity_type]
        return {"success": True, "data": log[:limit], "total": len(log), "timestamp": cls._timestamp()}

    @classmethod
    def get_delivery_report(cls, campaign_id=None):
        if campaign_id:
            c = cls._campaigns.get(campaign_id)
            if not c:
                return {"success": False, "error": "Кампания не найдена"}
            logs = [l for l in cls._sync_log if l.get('campaign_id') == campaign_id]
            return {
                "success": True,
                "data": {
                    "campaign": c,
                    "deliveries": logs,
                    "total_devices": c.get('devices_total', 0),
                    "synced_devices": c.get('devices_synced', 0),
                },
                "timestamp": cls._timestamp(),
            }
        # Общий отчет по всем кампаниям
        report = []
        for c in cls._campaigns.values():
            report.append({
                "campaign_id": c['id'],
                "campaign_name": c.get('name', ''),
                "status": c.get('status', ''),
                "delivery_status": c.get('delivery_status', ''),
                "devices_total": c.get('devices_total', 0),
                "devices_synced": c.get('devices_synced', 0),
            })
        return {"success": True, "data": report, "timestamp": cls._timestamp()}

    # ========== Справочники ==========

    @classmethod
    def get_department_types(cls):
        return {"success": True, "data": cls.DEPARTMENT_TYPES}

    @classmethod
    def get_device_types(cls):
        return {"success": True, "data": cls.DEVICE_TYPES}

    @classmethod
    def get_resolutions(cls):
        return {"success": True, "data": cls.ALLOWED_RESOLUTIONS}

    @classmethod
    def get_roles(cls):
        return {"success": True, "data": cls.ROLES}

    # ========== Вспомогательные методы ==========

    @classmethod
    def _build_target_summary(cls, targeting):
        if not targeting:
            return "Не задано"
        target_type = targeting.get('type', '')
        if target_type == 'all':
            return "Все магазины"
        elif target_type == 'stores':
            store_ids = targeting.get('store_ids', [])
            names = [cls._stores.get(s, {}).get('name', s) for s in store_ids]
            return f"Магазины: {', '.join(names)}"
        elif target_type == 'departments':
            dept_ids = targeting.get('department_ids', [])
            names = [cls._departments.get(d, {}).get('name', d) for d in dept_ids]
            return f"Отделы: {', '.join(names)}"
        elif target_type == 'devices':
            device_ids = targeting.get('device_ids', [])
            return f"Устройства: {len(device_ids)} шт."
        return "Не задано"

    @classmethod
    def _count_target_devices(cls, targeting):
        return len(cls._get_target_devices(targeting))

    @classmethod
    def _get_target_devices(cls, targeting):
        if not targeting:
            return []
        target_type = targeting.get('type', '')
        if target_type == 'all':
            return list(cls._devices.values())
        elif target_type == 'stores':
            store_ids = targeting.get('store_ids', [])
            return [d for d in cls._devices.values() if d.get('store_id') in store_ids]
        elif target_type == 'departments':
            dept_ids = targeting.get('department_ids', [])
            return [d for d in cls._devices.values() if d.get('department_id') in dept_ids]
        elif target_type == 'devices':
            device_ids = targeting.get('device_ids', [])
            return [d for d in cls._devices.values() if d['id'] in device_ids]
        return []

    # ========== Инициализация демо-данных ==========

    @classmethod
    def init_demo_data(cls):
        """Загрузка демонстрационных данных"""
        if cls._stores:
            return {"success": True, "message": "Данные уже загружены"}

        # Магазины
        stores_data = [
            {"name": "ТЦ Малина", "address": "ул. Каля Ешилор 8, Кишинёв", "region": "Кишинёв", "timezone": "Europe/Chisinau"},
            {"name": "Маркет №1", "address": "ул. Штефана чел Маре 120, Бельцы", "region": "Бельцы", "timezone": "Europe/Chisinau"},
            {"name": "Супермаркет Центральный", "address": "ул. Независимости 5, Кишинёв", "region": "Кишинёв", "timezone": "Europe/Chisinau"},
        ]
        created_stores = []
        for s in stores_data:
            result = cls.create_store(s)
            created_stores.append(result['data'])

        # Отделы
        dept_types = ["confectionery", "culinary", "cheese", "sausage", "meat", "fish"]
        dept_names = ["Кондитерские изделия", "Кулинария", "Сыры", "Колбасы", "Мясо", "Рыба"]
        created_depts = []
        for store in created_stores:
            for dt, dn in zip(dept_types[:4], dept_names[:4]):
                result = cls.create_department({"store_id": store['id'], "type": dt, "name": dn})
                created_depts.append(result['data'])

        # Устройства
        device_configs = [
            {"device_type": "SM5300", "resolution": "800x480"},
            {"device_type": "SM5300", "resolution": "1024x600"},
            {"device_type": "SM6000", "resolution": "1024x600"},
            {"device_type": "WEB3110", "resolution": "1920x1080"},
        ]
        for i, store in enumerate(created_stores):
            depts = [d for d in created_depts if d['store_id'] == store['id']]
            for j, dept in enumerate(depts[:3]):
                cfg = device_configs[(i * 3 + j) % len(device_configs)]
                cls.register_device({
                    "serial_number": f"DIGI-{1000 + i * 10 + j}",
                    "name": f"Весы {dept['name']} #{j + 1}",
                    "device_type": cfg['device_type'],
                    "resolution": cfg['resolution'],
                    "store_id": store['id'],
                    "department_id": dept['id'],
                    "ip_address": f"192.168.{10 + i}.{100 + j}",
                    "firmware_version": "2.1.4",
                    "memory_total_mb": 512,
                })

        # Медиаконтент
        media_items = [
            {"filename": "promo_summer_sale.jpg", "original_name": "Летняя распродажа", "size_bytes": 524288, "resolutions": ["800x480", "1024x600"], "description": "Баннер летней распродажи", "tags": ["акция", "лето"], "width": 1024, "height": 600},
            {"filename": "cheese_collection.jpg", "original_name": "Коллекция сыров", "size_bytes": 412000, "resolutions": ["800x480", "1024x600"], "description": "Ассортимент европейских сыров", "tags": ["сыры", "ассортимент"], "width": 800, "height": 480},
            {"filename": "meat_promo.mp4", "original_name": "Акция на мясо", "size_bytes": 8500000, "resolutions": ["1024x600"], "description": "Видео-промо мясного отдела", "tags": ["мясо", "видео", "акция"], "duration_seconds": 15, "width": 1024, "height": 600},
            {"filename": "new_year_sale.jpg", "original_name": "Новогодняя акция", "size_bytes": 620000, "resolutions": ["800x480", "1024x600", "1920x1080"], "description": "Новогодние скидки", "tags": ["новый год", "акция"], "width": 1920, "height": 1080},
            {"filename": "sausage_week.jpg", "original_name": "Неделя колбас", "size_bytes": 380000, "resolutions": ["800x480"], "description": "Промо неделя колбас", "tags": ["колбасы", "промо"], "width": 800, "height": 480},
            {"filename": "fish_friday.mp4", "original_name": "Рыбная пятница", "size_bytes": 12000000, "resolutions": ["1024x600", "1920x1080"], "description": "Еженедельная акция на рыбу", "tags": ["рыба", "видео"], "duration_seconds": 20, "width": 1920, "height": 1080},
        ]
        created_media = []
        for m in media_items:
            result = cls.upload_media(m)
            created_media.append(result['data'])

        # Плейлисты
        playlist1 = cls.create_playlist({
            "name": "Летний промо-микс",
            "description": "Промо-материалы для летнего сезона",
            "items": [
                {"media_id": created_media[0]['id'], "duration": 8, "order": 1},
                {"media_id": created_media[1]['id'], "duration": 6, "order": 2},
                {"media_id": created_media[2]['id'], "duration": 15, "order": 3},
            ],
        })
        playlist2 = cls.create_playlist({
            "name": "Общий рекламный",
            "description": "Стандартный плейлист для всех магазинов",
            "items": [
                {"media_id": created_media[3]['id'], "duration": 10, "order": 1},
                {"media_id": created_media[4]['id'], "duration": 7, "order": 2},
                {"media_id": created_media[5]['id'], "duration": 20, "order": 3},
            ],
        })

        # Кампании
        cls.create_campaign({
            "name": "Летняя кампания 2025",
            "description": "Промо-материалы для летнего сезона по всем магазинам",
            "playlist_id": playlist1['data']['id'],
            "targeting": {"type": "all"},
            "schedule": {
                "start_date": "2025-06-01",
                "end_date": "2025-08-31",
                "time_from": "08:00",
                "time_to": "22:00",
                "days_of_week": [1, 2, 3, 4, 5, 6, 7],
            },
            "priority": 8,
        })
        cls.create_campaign({
            "name": "Новогодняя акция",
            "description": "Новогодние промо для ТЦ Малина",
            "playlist_id": playlist2['data']['id'],
            "targeting": {"type": "stores", "store_ids": [created_stores[0]['id']]},
            "schedule": {
                "start_date": "2025-12-15",
                "end_date": "2026-01-15",
                "time_from": "09:00",
                "time_to": "21:00",
                "days_of_week": [1, 2, 3, 4, 5, 6, 7],
            },
            "priority": 10,
        })

        return {
            "success": True,
            "message": f"Демо-данные загружены: {len(created_stores)} магазинов, {len(created_depts)} отделов, {len(cls._devices)} устройств, {len(created_media)} медиа, 2 плейлиста, 2 кампании",
            "timestamp": cls._timestamp(),
        }
