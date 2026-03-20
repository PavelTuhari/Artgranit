"""
Контроллер аутентификации
"""
from flask import session, request, jsonify
from functools import wraps
from config import Config


class AuthController:
    """Класс для управления аутентификацией"""
    
    @staticmethod
    def login(username: str, password: str) -> bool:
        """Проверяет учетные данные"""
        return username == Config.DEFAULT_USERNAME and password == Config.DEFAULT_PASSWORD
    
    @staticmethod
    def is_authenticated() -> bool:
        """Проверяет, аутентифицирован ли пользователь"""
        return session.get('authenticated', False)
    
    @staticmethod
    def set_authenticated(value: bool = True):
        """Устанавливает статус аутентификации"""
        session['authenticated'] = value
        if value:
            session['username'] = Config.DEFAULT_USERNAME
    
    @staticmethod
    def logout():
        """Выход из системы"""
        session.clear()
    
    @staticmethod
    def get_current_user() -> str:
        """Получает текущего пользователя"""
        return session.get('username', '')
    
    @staticmethod
    def require_auth(f):
        """Декоратор для защиты маршрутов"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not AuthController.is_authenticated():
                return jsonify({"error": "Authentication required"}), 401
            return f(*args, **kwargs)
        return decorated_function

