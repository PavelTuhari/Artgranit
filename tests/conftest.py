"""Общая подготовка тестов.

Кэш каталога у магазина ОБЩИЙ для всех процессов: значения пишутся ещё и
в файл во временной папке, чтобы второй воркер gunicorn не платил заново
за тяжёлые запросы. В бою это правильно, в тестах — источник ложных
падений: один тест кладёт в кэш свой ответ, следующий получает его вместо
обращения к подставной базе и проверяет запрос, которого не было
(`last_sql` оказывается None).

Ловилось так: шесть тестов каталога падали вместе, поодиночке проходили,
а после запуска приложения на живой базе падали и подавно — в кэше лежали
настоящие данные.

Поэтому перед каждым тестом кэш очищается: и в памяти, и на диске.
"""
import os
import shutil

import pytest


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    def wipe():
        try:
            from models import biro26_oracle_store as store
        except Exception:                                    # noqa: BLE001
            return
        getattr(store, "_CACHE", {}).clear()
        cache_dir = getattr(store, "_CACHE_DIR", "")
        if cache_dir and os.path.isdir(cache_dir):
            shutil.rmtree(cache_dir, ignore_errors=True)

    wipe()
    yield
    wipe()
