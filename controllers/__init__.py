"""
Контроллеры приложения
"""
from controllers.auth_controller import AuthController
from controllers.dashboard_controller import DashboardController
from controllers.sql_controller import SQLController

__all__ = ['AuthController', 'DashboardController', 'SQLController']

