"""Ядро портала: общая часть, на которую опираются все модули.

Ядро отвечает за то, чтобы модуль можно было добавить, не трогая общий код,
и чтобы модули не мешали друг другу. Всё, что специфично для конкретного
модуля, живёт в `modules/<ключ>/` и в ядро не попадает.
"""
from core.module_loader import BASE_URL, LoadReport, ModuleLoadError, load_modules

__all__ = ["BASE_URL", "LoadReport", "ModuleLoadError", "load_modules"]
