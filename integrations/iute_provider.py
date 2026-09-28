"""
Iute Credit провайдер — обёртка над iute_client.py с единым интерфейсом CreditProvider.
"""
from __future__ import annotations

from typing import Any

from integrations.base_provider import CreditProvider
from config import Config


class IuteProvider(CreditProvider):
    """Iute Credit — REST API (physical-api-partners)."""

    @property
    def id(self) -> str:
        return "iute"

    @property
    def name(self) -> str:
        return "Iute Credit"

    @property
    def icon(self) -> str:
        return "🟢"

    @property
    def color(self) -> str:
        return "#00CC66"

    @property
    def description(self) -> str:
        return "Iute Credit — REST API (CheckAuth, CreateOrder, OrderStatus)"

    @property
    def capabilities(self) -> list[str]:
        return ["check_auth", "create_order", "order_status"]

    # --- Настройки ---

    def _base_url(self) -> str:
        return self._setting("base_url", Config.iute_base_url)

    def _env(self) -> str:
        return self._setting("env", Config.iute_env) or "sandbox"

    def _api_key(self) -> str:
        return self._setting("api_key", Config.iute_api_key)

    def _pos_identifier(self) -> str:
        return self._setting("pos_identifier", Config.iute_pos_identifier)

    def _salesman_identifier(self) -> str:
        return self._setting("salesman_identifier", Config.iute_salesman_identifier)

    def get_settings(self) -> dict[str, Any]:
        key = self._api_key()
        return {
            "env": self._env(),
            "base_url": self._base_url(),
            "api_key": (key[:8] + "***") if key else "",
            "pos_identifier": self._pos_identifier(),
            "salesman_identifier": self._salesman_identifier(),
        }

    def is_configured(self) -> bool:
        return bool(self._base_url() and self._api_key())

    # --- Тестовые клиенты ---

    def get_test_clients(self) -> list[dict[str, Any]]:
        return [
            {
                "fio": "Test Client 1",
                "phone": "+37377374279",
                "amount": 1000,
                "currency": "MDL",
                "id_number": "",
                "order_id": "test-order-001",
            },
            {
                "fio": "Test Client 2",
                "phone": "+37378963107",
                "amount": 2000,
                "currency": "MDL",
                "id_number": "",
                "order_id": "test-order-002",
            },
            {
                "fio": "Test Client 3",
                "phone": "+37371531475",
                "amount": 3000,
                "currency": "MDL",
                "id_number": "",
                "order_id": "test-order-003",
            },
        ]

    # --- Операции ---

    def check_auth(self) -> dict[str, Any]:
        """Проверка авторизации партнёра."""
        if not self.is_configured():
            return {"success": False, "error": "Iute не настроен (нет API key)"}

        try:
            from integrations.iute_client import check_auth as iute_check_auth
            return iute_check_auth(self._base_url(), self._api_key())
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_order(self, **kwargs) -> dict[str, Any]:
        """Создание заказа. kwargs: order_id, phone, amount, currency, user_pin, birthday, gender, items."""
        if not self.is_configured():
            return {"success": False, "error": "Iute не настроен"}

        try:
            from integrations.iute_client import create_order as iute_create_order
            return iute_create_order(
                self._base_url(),
                self._api_key(),
                order_id=kwargs.get("order_id", "test-order-001"),
                myiute_phone=kwargs.get("phone", "+37369123456"),
                total_amount=int(kwargs.get("amount", 1000)),
                currency=kwargs.get("currency", "MDL"),
                pos_identifier=self._pos_identifier(),
                salesman_identifier=self._salesman_identifier(),
                user_pin=kwargs.get("user_pin"),
                birthday=kwargs.get("birthday"),
                gender=kwargs.get("gender"),
                items=kwargs.get("items"),
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    def order_status(self, **kwargs) -> dict[str, Any]:
        """Статус заказа. kwargs: order_id."""
        order_id = kwargs.get("order_id", "")
        if not order_id:
            return {"success": False, "error": "Order ID не указан"}

        if not self.is_configured():
            return {"success": False, "error": "Iute не настроен"}

        try:
            from integrations.iute_client import get_order_status as iute_order_status
            return iute_order_status(self._base_url(), self._api_key(), order_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Маппинг на единые методы submit / check_status ---

    def submit(self, **kwargs) -> dict[str, Any]:
        """Маппинг submit → create_order для единого интерфейса."""
        return self.create_order(**kwargs)

    def check_status(self, **kwargs) -> dict[str, Any]:
        """Маппинг check_status → order_status для единого интерфейса."""
        return self.order_status(**kwargs)
