# Integrations (EasyCredit, Iute, ...)
# Авто-регистрация провайдеров в глобальном реестре (настройки основного
# проекта — через Config, который читает Oracle ADB).
# Для отдельного контура (Biro26, Oracle 11g) — build_registry(settings_source).

from typing import Any

from integrations.base_provider import CreditProvider, ProviderRegistry, registry

from integrations.easycredit_provider import EasyCreditProvider
from integrations.iute_provider import IuteProvider

registry.register(EasyCreditProvider())
registry.register(IuteProvider())

PROVIDER_CLASSES = [EasyCreditProvider, IuteProvider]


def build_registry(settings_source: Any) -> ProviderRegistry:
    """Новый реестр провайдеров, читающих настройки из settings_source.

    settings_source — объект с методом get(code) -> dict | None,
    обычно models.credite_settings.CrediteSettings.
    """
    reg = ProviderRegistry()
    for cls in PROVIDER_CLASSES:
        reg.register(cls(settings_source))
    return reg
