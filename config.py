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

    # ── Biro26 module — OfficePlus ERP (Oracle 11g) ──
    # 11g needs python-oracledb THICK mode (Instant Client). Because thick is a
    # whole-process switch that would break the main app's thin cloud-wallet
    # connection, Biro26 runs its Oracle access in an isolated subprocess worker
    # (models/biro26_worker.py). These settings configure that worker.
    BIRO26_DB_USER = os.environ.get('BIRO26_DB_USER', 'officeplus')
    BIRO26_DB_PASSWORD = os.environ.get('BIRO26_DB_PASSWORD', '')  # secret: set in .env, never hardcoded
    BIRO26_DB_DSN = os.environ.get('BIRO26_DB_DSN', 'orange.una.md:4024/cloudbd.world')
    BIRO26_NLS_LANGUAGE = os.environ.get('BIRO26_NLS_LANGUAGE', 'ENGLISH')
    BIRO26_NLS_TERRITORY = os.environ.get('BIRO26_NLS_TERRITORY', 'AMERICA')
    # RO/EN: display name of the module in all Biro26 UIs (title, header,
    # launcher). Change it in ONE place (here or via env) to rebrand.
    BIRO26_APP_NAME = os.environ.get('BIRO26_APP_NAME', 'OfficePlus')

    # RO/EN: API token for machine clients (una.md/desktop etc.) — grants
    # access to the document PDFs/JSON without a browser session. Empty =
    # the token path is disabled. Secret: .env only.
    BIRO26_API_TOKEN = os.environ.get('BIRO26_API_TOKEN', '')

    # RO/EN: shop top-bar theming + nav links (per deployment; e.g. the
    # officeplus.md embed uses the site's footer green and WP page links).
    # NAV format: "Label|/url;Label2|/url2". URL kinds:
    #   "info:<slug>" — WP page rendered INSIDE the shop (menu stays visible);
    #   "?"           — the catalog itself (clears the info view);
    #   anything else — normal link, opens in _top (escapes the iframe).
    BIRO26_SHOP_TOPBAR_BG = os.environ.get('BIRO26_SHOP_TOPBAR_BG', '#0d0d1a')
    BIRO26_SHOP_TOPBAR_FG = os.environ.get('BIRO26_SHOP_TOPBAR_FG', '#e2e8f0')
    BIRO26_SHOP_NAV = os.environ.get('BIRO26_SHOP_NAV', '')
    # RO: baza WP REST API pentru paginile "info:<slug>" din nav,
    #     ex. https://officeplus.md/wp-json; gol = functie oprita.
    # EN: WP REST API base for the nav "info:<slug>" pages; empty = off.
    BIRO26_SHOP_WP_API = os.environ.get('BIRO26_SHOP_WP_API', '')

    # ── jsReport service (reports/ — node sidecar, localhost only) ──
    # RO: PDF-urile "cont de plata" / "comanda" din cos se genereaza aici.
    # EN: the cart's invoice/order PDFs are rendered by this service.
    JSREPORT_URL = os.environ.get('JSREPORT_URL', 'http://127.0.0.1:5488')
    # RO/EN: seller requisites printed on the forms (override via env)
    BIRO26_FIRM_NAME = os.environ.get('BIRO26_FIRM_NAME', 'S.R.L. „GRECU OFFICE GROUP”')
    BIRO26_FIRM_ADDRESS = os.environ.get('BIRO26_FIRM_ADDRESS',
                                         'Bălţi, str. Libertăţii, 96, ap.(of.) 1')
    BIRO26_FIRM_FISCAL = os.environ.get('BIRO26_FIRM_FISCAL', '1026602001837')
    BIRO26_FIRM_IBAN = os.environ.get('BIRO26_FIRM_IBAN', '22517448478')
    BIRO26_FIRM_BANK = os.environ.get('BIRO26_FIRM_BANK',
                                      "BC'MOLDOVA-AGROINDBANK'S.A. fil.Balti")
    BIRO26_FIRM_BRANCH = os.environ.get('BIRO26_FIRM_BRANCH', 'AGRNMD2X750')
    BIRO26_FIRM_PHONE = os.environ.get('BIRO26_FIRM_PHONE', '')
    BIRO26_FIRM_DIRECTOR = os.environ.get('BIRO26_FIRM_DIRECTOR', '')
    BIRO26_TVA_RATE = float(os.environ.get('BIRO26_TVA_RATE', '20'))  # % inclusa in pret

    # ── notifications about new orders/invoices (module Biro26) ──
    # RO/EN: SMTP secrets live ONLY here (.env, project rule); recipients,
    # toggles and messenger tokens are edited in the admin page and stored
    # in YBIRO_SETTINGS.
    BIRO26_SMTP_HOST = os.environ.get('BIRO26_SMTP_HOST', '')
    BIRO26_SMTP_PORT = int(os.environ.get('BIRO26_SMTP_PORT', '587'))
    BIRO26_SMTP_USER = os.environ.get('BIRO26_SMTP_USER', '')
    BIRO26_SMTP_PASSWORD = os.environ.get('BIRO26_SMTP_PASSWORD', '')
    BIRO26_SMTP_FROM = os.environ.get('BIRO26_SMTP_FROM',
                                      os.environ.get('BIRO26_SMTP_USER', ''))
    BIRO26_SMTP_SSL = os.environ.get('BIRO26_SMTP_SSL', '0').strip() in ('1', 'true', 'yes')
    # Instant Client dir for thick mode (the 23_26 build connects to this 11g DB;
    # the 23_3 build raises ORA-28041). Override via env if installed elsewhere.
    # Permanent local home is ~/lib (never ~/Downloads — macOS TCC blocks shell
    # access there; see /Users/pt/lib/instantclient_23_26/SETUP.md).
    BIRO26_INSTANT_CLIENT = os.environ.get(
        'BIRO26_INSTANT_CLIENT', '/Users/pt/lib/instantclient_23_26')

    # Version widget (fixed bottom-right popup)
    VERSION_WIDGET_ENABLED = os.environ.get('VERSION_WIDGET_ENABLED', '0').strip() in ('1', 'true', 'yes')

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

