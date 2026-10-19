"""Инженерное оборудование офиса: паспорта, журнал обслуживания, фото.

Кондиционеры, котёл, система контроля доступа, кнопка лифта и умные
розетки. Большую часть этого нельзя опросить по сети — состояние знает
только человек, который к нему подошёл. Поэтому здесь: паспорт объекта,
журнал работ (замена фреона, чистка фильтров, осмотр) и фотофиксация.

Файлы фотографий лежат на диске, в базе — только путь: снимки занимают
мегабайты, а Oracle нужен для связей и поиска, не для хранения картинок.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

# Куда складываются снимки. Внутри модуля, но вне репозитория по .gitignore:
# фотографии оборудования — операционные данные, а не исходный код.
PHOTO_DIR = Path(__file__).resolve().parent / "photos"
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
MAX_PHOTO_MB = 12

KIND_TITLE = {
    "aircon": "Кондиционер",
    "boiler": "Котёл",
    "access": "Система контроля доступа",
    "elevator": "Лифт",
    "smartplug": "Умная розетка",
    "other": "Прочее оборудование",
}

WORK_TITLE = {
    "freon": "Заправка фреоном",
    "filter": "Чистка фильтров",
    "inspect": "Осмотр",
    "repair": "Ремонт",
    "install": "Установка",
    "other": "Прочие работы",
}

# Регламент обслуживания по типам. Для кондиционеров интервалы взяты
# из обычной практики: фильтры — раз в квартал, фреон — раз в два года.
SERVICE_RULES = {
    "aircon": {"filter": 90, "freon": 730, "inspect": 180},
    "boiler": {"inspect": 365, "repair": None},
    "access": {"inspect": 180},
    "elevator": {"inspect": 30},       # лифт — ежемесячный осмотр по нормативу
    "smartplug": {"inspect": 365},
}

# Стартовый состав оборудования офиса. Заводится один раз командой
# netmon_facility_seed.py; дальше правится через панель.
SEED = [
    # --- кондиционеры: четыре комнаты ---
    {"code": "AC-01", "kind": "aircon", "name": "Кондиционер, серверная",
     "room": "Серверная", "service_days": 90,
     "note": "Критичный: держит температуру стойки с cloudbd и PROXMOX3. "
             "При отказе оборудование греется — следить в первую очередь."},
    {"code": "AC-02", "kind": "aircon", "name": "Кондиционер, кабинет разработки",
     "room": "Кабинет разработки", "service_days": 90},
    {"code": "AC-03", "kind": "aircon", "name": "Кондиционер, бухгалтерия",
     "room": "Бухгалтерия", "service_days": 90},
    {"code": "AC-04", "kind": "aircon", "name": "Кондиционер, переговорная",
     "room": "Переговорная", "service_days": 90},
    # --- прочее инженерное ---
    {"code": "BOILER-01", "kind": "boiler", "name": "Котёл отопления",
     "room": "Техническое помещение", "service_days": 365,
     "note": "Проверка перед отопительным сезоном. В сеть не подключён — "
             "состояние заносится вручную."},
    {"code": "ACS-01", "kind": "access", "name": "Система контроля доступа ZKAccess",
     "room": "Вход", "service_days": 180, "vendor": "ZKTeco",
     "protocol": "ZKTeco (порт 4370)",
     "note": "Серверная часть — виртуальная машина 133 «ZKAcces» на PROXMOX3, "
             "сейчас ОСТАНОВЛЕНА. Контроллер в сети не отвечает: либо работает "
             "автономно, либо отключён. Требует проверки."},
    {"code": "LIFT-01", "kind": "elevator", "name": "Кнопка управления лифтом",
     "room": "Холл", "service_days": 30,
     "note": "Осмотр ежемесячно. Обслуживание — специализированная организация."},
    # --- умные розетки, найдены сканированием сети ---
    {"code": "PLUG-203", "kind": "smartplug", "name": "Умная розетка 192.168.0.203",
     "room": "уточнить", "ip": "192.168.0.203", "protocol": "Tuya 3.4 (порт 6668)",
     "is_monitored": "Y", "service_days": 365},
    {"code": "PLUG-206", "kind": "smartplug", "name": "Умная розетка 192.168.0.206",
     "room": "уточнить", "ip": "192.168.0.206", "protocol": "Tuya 3.4 (порт 6668)",
     "is_monitored": "Y", "service_days": 365},
    {"code": "PLUG-207", "kind": "smartplug", "name": "Умная розетка 192.168.0.207",
     "room": "уточнить", "ip": "192.168.0.207", "protocol": "Tuya 3.4 (порт 6668)",
     "is_monitored": "Y", "service_days": 365},
    {"code": "PLUG-240", "kind": "smartplug", "name": "Умная розетка 192.168.0.240",
     "room": "уточнить", "ip": "192.168.0.240", "protocol": "Tuya 3.4 (порт 6668)",
     "is_monitored": "Y", "service_days": 365},
]


def next_due(work_kind: str, kind: str, done: date | None = None) -> date | None:
    """Когда работу нужно повторить."""
    days = SERVICE_RULES.get(kind, {}).get(work_kind)
    if not days:
        return None
    return (done or date.today()) + timedelta(days=days)


def service_state(last_done: date | None, interval_days: int,
                  today: date | None = None) -> dict:
    """Просрочено ли обслуживание и насколько.

    Возвращает уровень для подсветки: срок вышел — красный, подходит —
    жёлтый, работ вообще не было — тоже требует внимания.
    """
    today = today or date.today()
    if last_done is None:
        return {"level": "unknown", "days_over": None,
                "text": "работ не зафиксировано"}
    due = last_done + timedelta(days=interval_days)
    left = (due - today).days
    if left < 0:
        return {"level": "overdue", "days_over": -left,
                "text": f"просрочено на {-left} дн"}
    if left <= max(7, interval_days // 10):
        return {"level": "soon", "days_over": 0, "text": f"через {left} дн"}
    return {"level": "ok", "days_over": 0, "text": f"через {left} дн"}


def safe_filename(name: str, facility_code: str) -> str:
    """Имя файла снимка: без путей и неожиданных символов."""
    ext = Path(name or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"формат {ext or '—'} не поддерживается; "
                         f"допустимы {', '.join(sorted(ALLOWED_EXT))}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    code = re.sub(r"[^\w.-]", "_", facility_code)[:30]
    return f"{code}_{stamp}{ext}"


def photo_path(filename: str) -> Path:
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    return PHOTO_DIR / filename
