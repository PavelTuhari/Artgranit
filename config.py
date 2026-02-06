"""
Конфигурация приложения
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

EASYCREDIT_SETTINGS_PATH = Path(__file__).resolve().parent / "data" / "easycredit_settings.json"
IUTE_SETTINGS_PATH = Path(__file__).resolve().parent / "data" / "iute_settings.json"


def _load_easycredit_overrides():
    """Читает data/easycredit_settings.json (переопределения к .env). Без секретов в репо."""
    if not EASYCREDIT_SETTINGS_PATH.exists():
        return {}
    try:
        with open(EASYCREDIT_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_iute_overrides():
    """Читает data/iute_settings.json (переопределения к .env). Без секретов в репо."""
    if not IUTE_SETTINGS_PATH.exists():
        return {}
    try:
        with open(IUTE_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_easycredit_settings(env: str, base_url: str, api_user: str, api_password: str) -> None:
    """Сохраняет настройки EasyCredit в data/easycredit_settings.json.
    Если api_password пустой, сохраняем существующий (не перезаписываем)."""
    EASYCREDIT_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    prev = _load_easycredit_overrides()
    pwd = (api_password or "").strip()
    if not pwd and prev:
        pwd = prev.get("api_password") or ""
    payload = {
        "env": (env or "sandbox").lower(),
        "base_url": (base_url or "").strip(),
        "api_user": (api_user or "").strip(),
        "api_password": pwd,
    }
    with open(EASYCREDIT_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def save_iute_settings(env: str, base_url: str, api_key: str, pos_identifier: str, salesman_identifier: str) -> None:
    """Сохраняет настройки Iute в data/iute_settings.json.
    Если api_key пустой, сохраняем существующий (не перезаписываем)."""
    IUTE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    prev = _load_iute_overrides()
    key = (api_key or "").strip()
    if not key and prev:
        key = prev.get("api_key") or ""
    payload = {
        "env": (env or "sandbox").lower(),
        "base_url": (base_url or "").strip(),
        "api_key": key,
        "pos_identifier": (pos_identifier or "").strip(),
        "salesman_identifier": (salesman_identifier or "").strip(),
    }
    with open(IUTE_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


class Config:
    """Базовый класс конфигурации"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Определяем окружение (LOCAL для Mac, REMOTE для сервера)
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'LOCAL').upper()  # LOCAL или REMOTE
    IS_LOCAL = ENVIRONMENT == 'LOCAL'
    
    # Конфигурация сервера
    # Локальный Mac: 0.0.0.0 для доступа по локальному IP, Удаленный сервер: 0.0.0.0:8000
    SERVER_HOST = os.environ.get('SERVER_HOST', '0.0.0.0')
    SERVER_PORT = int(os.environ.get('PORT', 3003 if IS_LOCAL else 8000))
    
    # Удаленный сервер (значения по умолчанию)
    REMOTE_SERVER_HOST = "92.5.3.187"
    REMOTE_SERVER_PORT = 8000
    REMOTE_SERVER_URL = f"http://{REMOTE_SERVER_HOST}:{REMOTE_SERVER_PORT}"
    
    # Oracle Database конфигурация (только из .env файла - безопасно!)
    # Все значения должны быть в .env файле, иначе будут пустые строки
    DB_USER = os.environ.get('DB_USER', '')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    WALLET_PASSWORD = os.environ.get('WALLET_PASSWORD', '')
    WALLET_ZIP = os.environ.get('WALLET_ZIP', '')
    WALLET_DIR = os.environ.get('WALLET_DIR', '')
    TNS_ALIAS = os.environ.get('TNS_ALIAS', '')
    CONNECT_STRING = os.environ.get('CONNECT_STRING', '')
    
    # WebSocket конфигурация
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"
    
    # Dashboard обновления (в секундах)
    DASHBOARD_UPDATE_INTERVAL = 60  # 1 минута для каждого элемента
    
    # Аутентификация (только из .env файла)
    DEFAULT_USERNAME = os.environ.get('DEFAULT_USERNAME') or os.environ.get('DB_USER', '')
    DEFAULT_PASSWORD = os.environ.get('DEFAULT_PASSWORD') or os.environ.get('DB_PASSWORD', '')
    
    # Языковая конфигурация (i18n)
    BABEL_DEFAULT_LOCALE = 'ru'  # Русский по умолчанию
    BABEL_DEFAULT_TIMEZONE = 'Europe/Moscow'
    LANGUAGES = {
        'ru': 'Русский',
        'ro': 'Română',
        'en': 'English'
    }
    SUPPORTED_LANGUAGES = ['ru', 'ro', 'en']

    # EasyCredit API (sandbox/production). См. creditare produselor in magazine Bomba — user/passwd, test/prod URLs.
    EASYCREDIT_ENV = os.environ.get('EASYCREDIT_ENV', 'sandbox').lower()  # sandbox | production
    EASYCREDIT_BASE_URL = os.environ.get('EASYCREDIT_BASE_URL', '').strip()  # пусто = дефолт по ENV
    EASYCREDIT_API_USER = os.environ.get('EASYCREDIT_API_USER', 'demo').strip()
    EASYCREDIT_API_PASSWORD = os.environ.get('EASYCREDIT_API_PASSWORD', 'demo').strip()

    @classmethod
    def easycredit_base_url(cls) -> str:
        o = _load_easycredit_overrides()
        base = o.get('base_url') or cls.EASYCREDIT_BASE_URL
        if base:
            return base.rstrip('/')
        if (o.get('env') or cls.EASYCREDIT_ENV) == 'production':
            return 'https://w81.ecredit.md:8082'
        return 'https://tst.ecmoldova.cloud:8082'

    @classmethod
    def easycredit_env(cls) -> str:
        o = _load_easycredit_overrides()
        return o.get('env') or cls.EASYCREDIT_ENV

    @classmethod
    def easycredit_api_user(cls) -> str:
        o = _load_easycredit_overrides()
        return o.get('api_user') or cls.EASYCREDIT_API_USER

    @classmethod
    def easycredit_api_password(cls) -> str:
        o = _load_easycredit_overrides()
        return o.get('api_password') or cls.EASYCREDIT_API_PASSWORD

    # Iute API (sandbox/production). См. https://iute-core-partner-gateway.iute.eu/docs/public/guide.html
    IUTE_ENV = os.environ.get('IUTE_ENV', 'sandbox').lower()  # sandbox | production
    IUTE_BASE_URL = os.environ.get('IUTE_BASE_URL', '').strip()  # пусто = дефолт по ENV
    IUTE_API_KEY = os.environ.get('IUTE_API_KEY', '').strip()
    IUTE_POS_IDENTIFIER = os.environ.get('IUTE_POS_IDENTIFIER', '').strip()
    IUTE_SALESMAN_IDENTIFIER = os.environ.get('IUTE_SALESMAN_IDENTIFIER', '').strip()

    @classmethod
    def iute_base_url(cls) -> str:
        o = _load_iute_overrides()
        base = o.get('base_url') or cls.IUTE_BASE_URL
        if base:
            return base.rstrip('/')
        # По умолчанию production URL
        return 'https://iute-core-partner-gateway.iute.eu'

    @classmethod
    def iute_env(cls) -> str:
        o = _load_iute_overrides()
        return o.get('env') or cls.IUTE_ENV

    @classmethod
    def iute_api_key(cls) -> str:
        o = _load_iute_overrides()
        return o.get('api_key') or cls.IUTE_API_KEY

    @classmethod
    def iute_pos_identifier(cls) -> str:
        o = _load_iute_overrides()
        return o.get('pos_identifier') or cls.IUTE_POS_IDENTIFIER

    @classmethod
    def iute_salesman_identifier(cls) -> str:
        o = _load_iute_overrides()
        return o.get('salesman_identifier') or cls.IUTE_SALESMAN_IDENTIFIER

    # Rate limiting
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '200 per hour')
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'true').lower() == 'true'

    @staticmethod
    def init_app(app):
        pass

