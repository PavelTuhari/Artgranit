"""Контроллер модуля Работа с поставщиками: валидация и сборка ответов.

Возвращает (payload, http_status). SQL — только в store.py, чистые правила —
в rules.py (тестируются без wallet).
"""
from modules.furnizori import rules, store


class FurnizoriController:
    @staticmethod
    def status():
        try:
            data = store.counters()
        except Exception as e:  # noqa: BLE001 — наружу только текст
            return {"success": False, "message": str(e)}, 500
        return {"success": True, "data": data, "rules_version": rules.VERSION}, 200
