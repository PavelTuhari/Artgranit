"""
Единый контроллер тестирования кредитных провайдеров (OOP, MVP).

Все провайдеры работают через единый интерфейс CreditProvider.
Фронтенд вызывает /api/credit-testing/... с параметром provider=easycredit|iute|...
"""
from __future__ import annotations

from typing import Any

from integrations.base_provider import registry


class CreditTestingController:
    """Единый контроллер для тестирования любого кредитного провайдера."""

    @staticmethod
    def get_providers() -> dict[str, Any]:
        """Список всех зарегистрированных провайдеров с метаданными."""
        return {
            "success": True,
            "providers": registry.list_dicts(),
        }

    @staticmethod
    def get_provider_info(provider_id: str) -> dict[str, Any]:
        """Информация о конкретном провайдере."""
        p = registry.get(provider_id)
        if not p:
            return {"success": False, "error": f"Провайдер '{provider_id}' не найден"}
        return {"success": True, "data": p.to_dict()}

    # --- Универсальные операции ---

    @staticmethod
    def search_client(provider_id: str, **kwargs) -> dict[str, Any]:
        """Поиск клиента через указанный провайдер."""
        p = registry.get(provider_id)
        if not p:
            return {"success": False, "error": f"Провайдер '{provider_id}' не найден"}
        if "search_client" not in p.capabilities:
            return {"success": False, "error": f"'{p.name}' не поддерживает поиск клиента"}
        return p.search_client(**kwargs)

    @staticmethod
    def preapproved(provider_id: str, **kwargs) -> dict[str, Any]:
        """Проверка предодобренной суммы."""
        p = registry.get(provider_id)
        if not p:
            return {"success": False, "error": f"Провайдер '{provider_id}' не найден"}
        if "preapproved" not in p.capabilities:
            return {"success": False, "error": f"'{p.name}' не поддерживает preapproved"}
        return p.preapproved(**kwargs)

    @staticmethod
    def submit(provider_id: str, **kwargs) -> dict[str, Any]:
        """Отправка заявки / создание заказа (единый метод)."""
        p = registry.get(provider_id)
        if not p:
            return {"success": False, "error": f"Провайдер '{provider_id}' не найден"}
        # submit поддерживается если есть capability submit ИЛИ create_order
        if "submit" not in p.capabilities and "create_order" not in p.capabilities:
            return {"success": False, "error": f"'{p.name}' не поддерживает отправку заявок"}
        return p.submit(**kwargs)

    @staticmethod
    def check_status(provider_id: str, **kwargs) -> dict[str, Any]:
        """Проверка статуса заявки / заказа (единый метод)."""
        p = registry.get(provider_id)
        if not p:
            return {"success": False, "error": f"Провайдер '{provider_id}' не найден"}
        if "status" not in p.capabilities and "order_status" not in p.capabilities:
            return {"success": False, "error": f"'{p.name}' не поддерживает проверку статуса"}
        return p.check_status(**kwargs)

    @staticmethod
    def check_auth(provider_id: str) -> dict[str, Any]:
        """Проверка авторизации / подключения."""
        p = registry.get(provider_id)
        if not p:
            return {"success": False, "error": f"Провайдер '{provider_id}' не найден"}
        if "check_auth" not in p.capabilities:
            return {"success": False, "error": f"'{p.name}' не поддерживает check_auth"}
        return p.check_auth()

    @staticmethod
    def create_order(provider_id: str, **kwargs) -> dict[str, Any]:
        """Создание заказа (Iute-стиль)."""
        p = registry.get(provider_id)
        if not p:
            return {"success": False, "error": f"Провайдер '{provider_id}' не найден"}
        if "create_order" not in p.capabilities:
            return {"success": False, "error": f"'{p.name}' не поддерживает create_order"}
        return p.create_order(**kwargs)

    @staticmethod
    def order_status(provider_id: str, **kwargs) -> dict[str, Any]:
        """Статус заказа (Iute-стиль)."""
        p = registry.get(provider_id)
        if not p:
            return {"success": False, "error": f"Провайдер '{provider_id}' не найден"}
        if "order_status" not in p.capabilities:
            return {"success": False, "error": f"'{p.name}' не поддерживает order_status"}
        return p.order_status(**kwargs)
