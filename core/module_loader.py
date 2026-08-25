"""Подключение модулей портала без правки общего кода.

## Зачем

Раньше модуль добавлялся строчками в `app.py`: тринадцать модулей — девять
тысяч строк в одном файле. Каждый новый модуль означал правку общего файла,
а значит конфликт слияния с любым другим модулем и риск задеть чужие
маршруты. Отсюда правило: **общее не трогаем**, модуль подключается сам.

## Контракт модуля

Каталог `modules/<ключ>/`:

| Файл | Обязателен | Роль |
|---|---|---|
| `module.json` | нет | манифест меню (название, иконка, порядок) |
| `__init__.py` | да, для кода | пакет модуля, экспортирует `blueprint` |

В `__init__.py` модуль объявляет **один** объект:

```python
from flask import Blueprint

blueprint = Blueprint("seoforge", __name__, template_folder="templates")
```

и регистрирует на нём свои маршруты. Больше от модуля ничего не требуется:
ядро само найдёт пакет, проверит его и подключит.

Модуль без `__init__.py` — не ошибка: так выглядит модуль, у которого пока
есть только манифест меню, а страницы живут в общем `app.py` по старому
образцу. Такие модули ядро пропускает молча.

## Что ядро гарантирует

1. **Имя blueprint равно ключу модуля.** Endpoint'ы получают вид
   `<ключ>.<функция>`, поэтому два модуля не могут занять одно имя, даже
   если функции внутри названы одинаково.
2. **Маршруты модуля лежат под `/UNA.md/orasldev/<ключ>`.** Префикс задаёт
   ядро при регистрации, поэтому модуль физически не может объявить адрес
   вне своей области — не по договорённости, а по устройству.
3. **Обойти префикс нечем.** На время импорта модуля ядро закрывает ему
   `app.add_url_rule` и `app.register_blueprint`: повесить маршрут прямо на
   приложение в обход префикса физически невозможно, попытка сразу даёт
   отказ. Это надёжнее проверки постфактум — Werkzeug не умеет удалять уже
   добавленные маршруты, и «заметить и откатить» было бы не откатить.
4. **Сбой модуля не роняет портал.** Битый импорт, отсутствующий
   `blueprint`, неверное имя — модуль пропускается с записью в отчёт,
   остальные продолжают работать.
5. **Повтор ключа отвергается.** Два модуля с одним ключом — второй не
   подключается.

Меню при этом не меняется: `models/module_registry.py` собирает его из карты
маршрутов Flask, а маршруты blueprint'а попадают туда наравне с обычными.
"""
from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(ROOT, "modules")

# Все страницы портала живут под этим адресом.
BASE_URL = "/UNA.md/orasldev"


class ModuleLoadError(Exception):
    """Модуль не удалось подключить. Портал при этом продолжает работу."""


@dataclass
class LoadReport:
    """Что подключилось, что пропущено и почему.

    Отчёт нужен не для красоты: без него сбой модуля выглядел бы как
    «страница просто не открывается», и искать причину пришлось бы вручную.
    """

    loaded: List[str] = field(default_factory=list)
    skipped: Dict[str, str] = field(default_factory=dict)
    failed: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"loaded": sorted(self.loaded),
                "skipped": dict(sorted(self.skipped.items())),
                "failed": dict(sorted(self.failed.items()))}


def module_keys() -> List[str]:
    """Ключи модулей — имена каталогов в `modules/`."""
    if not os.path.isdir(MODULES_DIR):
        return []
    keys = []
    for name in sorted(os.listdir(MODULES_DIR)):
        path = os.path.join(MODULES_DIR, name)
        if not os.path.isdir(path) or name.startswith((".", "_")):
            continue
        keys.append(name)
    return keys


def module_url(key: str) -> str:
    return f"{BASE_URL}/{key}"


def _rule_set(app) -> set:
    return {rule.rule for rule in app.url_map.iter_rules()}


def _load_manifest(key: str) -> Dict[str, Any]:
    path = os.path.join(MODULES_DIR, key, "module.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                                            # noqa: BLE001
        # Битый манифест — забота меню, а не загрузчика: модуль всё равно
        # должен подключиться.
        return {}


def _import_module(key: str):
    """Пакет модуля либо None, если модуль без кода."""
    if not os.path.isfile(os.path.join(MODULES_DIR, key, "__init__.py")):
        return None
    return importlib.import_module(f"modules.{key}")


def _guarded_import(app, key: str):
    """Импортирует пакет модуля, закрыв ему регистрацию на приложении.

    Модуль обязан объявлять маршруты на своём blueprint, а не на общем
    приложении: иначе он занял бы адрес вне отведённого префикса, и это
    уже нельзя было бы отменить — Werkzeug удалять маршруты не умеет.
    Поэтому на время импорта подменяем оба входа.
    """
    def refuse(*_args, **_kwargs):
        raise ModuleLoadError(
            "модуль объявляет маршруты на общем приложении. Маршруты "
            "объявляются на blueprint модуля, ядро само подключит его "
            f"под {module_url(key)}")

    original_rule = app.add_url_rule
    original_bp = app.register_blueprint
    app.add_url_rule = refuse
    app.register_blueprint = refuse
    try:
        return _import_module(key)
    finally:
        app.add_url_rule = original_rule
        app.register_blueprint = original_bp


def _validate(key: str, blueprint) -> None:
    if blueprint is None:
        raise ModuleLoadError("пакет модуля не экспортирует blueprint")

    name = getattr(blueprint, "name", None)
    if name != key:
        raise ModuleLoadError(
            f"имя blueprint '{name}' не совпадает с ключом модуля '{key}' — "
            "иначе endpoint'ы модулей столкнутся")

    declared = getattr(blueprint, "url_prefix", None)
    expected = module_url(key)
    if declared not in (None, expected):
        raise ModuleLoadError(
            f"модуль объявил префикс '{declared}', а ему отведён '{expected}'")


def load_module(app, key: str, report: Optional[LoadReport] = None) -> bool:
    """Подключает один модуль. Возвращает True, если маршруты появились."""
    report = report if report is not None else LoadReport()
    prefix = module_url(key)

    if key in app.blueprints:
        report.failed[key] = "модуль с таким ключом уже подключён"
        return False

    try:
        package = _guarded_import(app, key)
    except Exception as exc:                                     # noqa: BLE001
        report.failed[key] = f"{type(exc).__name__}: {exc}"
        return False

    if package is None:
        report.skipped[key] = "нет пакета модуля, только манифест"
        return False

    blueprint = getattr(package, "blueprint", None)
    try:
        _validate(key, blueprint)
        app.register_blueprint(blueprint, url_prefix=prefix)
    except Exception as exc:                                     # noqa: BLE001
        report.failed[key] = f"{type(exc).__name__}: {exc}"
        return False

    report.loaded.append(key)
    return True


def load_modules(app) -> LoadReport:
    """Подключает все модули из `modules/`.

    Вызывается один раз при старте приложения. Это единственное, что ядру
    нужно от `app.py`.
    """
    report = LoadReport()
    for key in module_keys():
        load_module(app, key, report)

    app.extensions = getattr(app, "extensions", {})
    app.extensions["module_loader"] = report
    return report
