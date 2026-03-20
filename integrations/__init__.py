# Integrations (EasyCredit, Iute, ...)
# Авто-регистрация провайдеров в глобальном реестре.

from integrations.base_provider import registry

from integrations.easycredit_provider import EasyCreditProvider
from integrations.iute_provider import IuteProvider

registry.register(EasyCreditProvider())
registry.register(IuteProvider())
