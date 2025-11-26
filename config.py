"""
Конфигурация приложения
"""
import os
from pathlib import Path

class Config:
    """Базовый класс конфигурации"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Oracle Database конфигурация
    DB_USER = "ADMIN"
    DB_PASSWORD = "ArtG2025UNAmd##"
    WALLET_PASSWORD = "UniSim2025UNAmd__"
    WALLET_ZIP = "Wallet_HXPAVUNKCLU9HE7Q.zip"
    WALLET_DIR = "wallet_HXPAVUNKCLU9HE7Q"
    TNS_ALIAS = "hxpavunkclu9he7q_high"
    CONNECT_STRING = '(description= (retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=adb.eu-frankfurt-1.oraclecloud.com))(connect_data=(service_name=g47056ff8b1b3d4_hxpavunkclu9he7q_high.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))'
    
    # WebSocket конфигурация
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"
    
    # Dashboard обновления (в секундах)
    DASHBOARD_UPDATE_INTERVAL = 60  # 1 минута для каждого элемента
    
    # Аутентификация
    DEFAULT_USERNAME = "ADMIN"
    DEFAULT_PASSWORD = "ArtG2025UNAmd##"
    
    @staticmethod
    def init_app(app):
        pass

