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

    def __init__(self, settings_source: Any = None) -> None:
        """settings_source — объект с методом get(code) -> dict | None
        (обычно models.credite_settings.CrediteSettings). None = читать Config."""
        self._settings_source = settings_source

    def _cfg(self) -> dict[str, Any]:
        """Настройки этого провайдера из settings_source. {} если источника нет."""
        if self._settings_source is None:
            return {}
        try:
            d = self._settings_source.get(self.id)
        except Exception:
            return {}
        return d or {}

    def _cfg_param(self, name: str) -> str:
        """Значение параметра из settings_source ('' если нет)."""
        return (self._cfg().get("params") or {}).get(name) or ""

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
    """Реестр доступных кредитных провайдеров.

    Глобальный экземпляр `registry` обслуживает основной проект (настройки ADB
    через Config). Для отдельного контура (например, Biro26 с настройками в
    Oracle 11g) создаётся свой экземпляр — см. integrations.build_registry.
    """

    def __init__(self) -> None:
        self._providers: dict[str, CreditProvider] = {}

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
