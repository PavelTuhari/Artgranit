"""
Базовый класс кредитного провайдера (OOP, MVP).

Каждая кредитная организация (EasyCredit, Iute, ...) реализует
единый интерфейс CreditProvider. Реестр ProviderRegistry позволяет
динамически получать список доступных провайдеров и их capabilities.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CreditProvider(ABC):
    """Абстрактный базовый класс для всех кредитных провайдеров."""

    # --- Метаданные (переопределяются в подклассах) ---

    @property
    @abstractmethod
    def id(self) -> str:
        """Уникальный slug провайдера, напр. 'easycredit', 'iute'."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Человекочитаемое название, напр. 'EasyCredit'."""

    @property
    def icon(self) -> str:
        """Эмодзи / иконка для UI."""
        return "🏦"

    @property
    def color(self) -> str:
        """HEX-цвет для визуального различения."""
        return "#0066CC"

    @property
    def description(self) -> str:
        """Краткое описание."""
        return ""

    # --- Capabilities ---

    @property
    def capabilities(self) -> list[str]:
        """Список поддерживаемых операций.

        Возможные значения:
        - 'search_client'   — поиск клиента (по IDNP / телефону)
        - 'preapproved'     — проверка предодобренной суммы
        - 'submit'          — отправка заявки
        - 'status'          — проверка статуса заявки
        - 'check_auth'      — проверка авторизации / соединения
        - 'create_order'    — создание заказа (Iute-стиль)
        - 'order_status'    — статус заказа (Iute-стиль)
        """
        return []

    # --- Настройки ---

    @abstractmethod
    def get_settings(self) -> dict[str, Any]:
        """Текущие настройки (env, base_url, маскированные credentials)."""

    @abstractmethod
    def is_configured(self) -> bool:
        """True если есть минимально необходимые credentials."""

    # --- Тестовые данные ---

    @abstractmethod
    def get_test_clients(self) -> list[dict[str, Any]]:
        """Список предзаполненных тестовых клиентов для UI.

        Каждый элемент — dict с ключами, зависящими от провайдера.
        Общие: fio, phone, id_number, amount.
        """

    # --- Операции (реализуются по наличию capability) ---

    def search_client(self, **kwargs) -> dict[str, Any]:
        """Поиск клиента. kwargs: uin, phone, ..."""
        return {"success": False, "error": "Not supported"}

    def preapproved(self, **kwargs) -> dict[str, Any]:
        """Проверка предодобренной суммы. kwargs: uin, amount, ..."""
        return {"success": False, "error": "Not supported"}

    def submit(self, **kwargs) -> dict[str, Any]:
        """Отправка заявки. kwargs: fio, phone, uin, amount, ..."""
        return {"success": False, "error": "Not supported"}

    def check_status(self, **kwargs) -> dict[str, Any]:
        """Проверка статуса. kwargs: urn, order_id, ..."""
        return {"success": False, "error": "Not supported"}

    def check_auth(self) -> dict[str, Any]:
        """Проверка авторизации / подключения."""
        return {"success": False, "error": "Not supported"}

    def create_order(self, **kwargs) -> dict[str, Any]:
        """Создание заказа. kwargs зависят от провайдера."""
        return {"success": False, "error": "Not supported"}

    def order_status(self, **kwargs) -> dict[str, Any]:
        """Статус заказа. kwargs: order_id."""
        return {"success": False, "error": "Not supported"}

    # --- Сериализация для API ---

    def to_dict(self) -> dict[str, Any]:
        """Краткая информация о провайдере для фронтенда."""
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "color": self.color,
            "description": self.description,
            "capabilities": self.capabilities,
            "configured": self.is_configured(),
            "settings": self.get_settings(),
            "test_clients": self.get_test_clients(),
        }


class ProviderRegistry:
    """Реестр доступных кредитных провайдеров (Singleton-паттерн)."""

    _instance: ProviderRegistry | None = None
    _providers: dict[str, CreditProvider]

    def __new__(cls) -> ProviderRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
        return cls._instance

    def register(self, provider: CreditProvider) -> None:
        """Зарегистрировать провайдера."""
        self._providers[provider.id] = provider

    def get(self, provider_id: str) -> CreditProvider | None:
        """Получить провайдера по id."""
        return self._providers.get(provider_id)

    def list_all(self) -> list[CreditProvider]:
        """Все зарегистрированные провайдеры."""
        return list(self._providers.values())

    def list_dicts(self) -> list[dict[str, Any]]:
        """Все провайдеры как dicts (для JSON API)."""
        return [p.to_dict() for p in self._providers.values()]

    def ids(self) -> list[str]:
        """Список id всех провайдеров."""
        return list(self._providers.keys())


# Глобальный реестр
registry = ProviderRegistry()
