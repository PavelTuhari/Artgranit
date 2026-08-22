"""
Реестр модулей портала: что вообще есть в системе.

Задача одна и практическая: **ничто не должно теряться в меню**. Раньше
список модулей был вписан руками в шаблон `sqldeveloper_mdi.html` — пять
пунктов при 111 реально работающих страницах. Любой, кто добавлял модуль,
должен был вспомнить про этот шаблон, и почти никто не вспоминал: Biro26,
Планограммы, ServOuts26, Colass, Nufarul, Decor существовали, работали
и были невидимы из портала.

Поэтому источник правды здесь — не список, а **сама карта маршрутов Flask**.
Если страница зарегистрирована, она попадёт в меню, кто бы её ни написал
и в какой бы сессии это ни произошло.

Два слоя:

1. **Автообнаружение.** Все GET-страницы под `/UNA.md/orasldev/` без
   параметров и без `/api/` группируются по первому сегменту пути.
   Это работает без единой строчки настройки.

2. **Манифест** — `modules/<ключ>/module.json`. Даёт человеческое название
   на трёх языках, иконку, порядок и подписи страниц. Манифест ТОЛЬКО
   украшает: модуль без манифеста всё равно виден, просто с названием,
   собранным из адреса, и с пометкой «без манифеста». Спрятать модуль
   из меню манифестом нельзя — можно лишь понизить его в порядке;
   иначе вернулась бы та же болезнь, от которой этот файл написан.

Добавление модуля сводится к одному действию: создать папку
`modules/<ключ>/` с `module.json`. Сканирование — при первом обращении
к меню после старта приложения.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(ROOT, 'modules')
BASE = '/UNA.md/orasldev'
LANGS = ('ru', 'ro', 'en')

# Служебные ветки, которые не являются модулями сети: у них своя точка
# входа в интерфейсе. В меню они всё равно показываются, но отдельной
# группой — «Инструменты», а не «Модули».
TOOL_KEYS = {'dashboard', 'docs', 'modules'}

_cache: Optional[Dict[str, Any]] = None


# ==================== Манифесты ====================


def _read_manifests() -> Dict[str, Dict[str, Any]]:
    """Читает `modules/*/module.json`. Битый файл не роняет портал."""
    out: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(MODULES_DIR):
        return out
    for name in sorted(os.listdir(MODULES_DIR)):
        path = os.path.join(MODULES_DIR, name, 'module.json')
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception as e:                                   # noqa: BLE001
            # Ошибка в одном манифесте не должна прятать остальные модули
            out[name] = {'key': name, 'error': f'{type(e).__name__}: {e}'}
            continue
        data['key'] = data.get('key') or name
        out[data['key']] = data
    return out


# ==================== Автообнаружение маршрутов ====================


def _is_page(rule) -> bool:
    path = str(rule.rule)
    if not path.startswith(BASE):
        return False
    if 'GET' not in (rule.methods or ()):
        return False
    if '<' in path:                      # маршруты с параметрами — не пункты меню
        return False
    if '/api/' in path:
        return False
    tail = path[len(BASE):].strip('/')
    if not tail:
        return False
    # Выгрузки файлов (…/что-то.zip) — не страницы
    if re.search(r'\.[a-z0-9]{2,5}$', tail.split('/')[-1]):
        return False
    return True


def _module_key(tail: str) -> str:
    """
    Ключ модуля из адреса.

    `biro26-site/account` → `biro26`, `credit-admin` → `credit`,
    `planograms/docs` → `planograms`. Дефис и слэш здесь означают одно
    и то же — «подраздел того же модуля».
    """
    first = tail.split('/')[0]
    return first.split('-')[0].lower()


def _pretty(tail: str) -> str:
    """Читаемая подпись из адреса, когда манифест молчит."""
    label = tail.replace('/', ' · ').replace('-', ' ')
    return label[:1].upper() + label[1:]


def discover(app) -> Dict[str, Any]:
    """
    Собирает карту модулей по маршрутам приложения и манифестам.

    Возвращает готовую к отрисовке структуру: группы → модули → страницы.
    """
    manifests = _read_manifests()

    pages: Dict[str, List[Dict[str, Any]]] = {}
    for rule in app.url_map.iter_rules():
        if not _is_page(rule):
            continue
        tail = str(rule.rule)[len(BASE):].strip('/')
        key = _module_key(tail)
        url = f'{BASE}/{tail}'
        bucket = pages.setdefault(key, [])
        if any(p['url'] == url for p in bucket):
            continue
        bucket.append({'url': url, 'tail': tail, 'endpoint': rule.endpoint})

    modules: List[Dict[str, Any]] = []
    for key, items in pages.items():
        man = manifests.get(key, {})
        titles = man.get('title') or {}
        # Заглавная страница модуля — самый короткий адрес в группе
        items.sort(key=lambda p: (p['tail'].count('/'), len(p['tail']), p['tail']))
        page_titles = man.get('pages') or {}
        for p in items:
            p['title'] = page_titles.get(p['tail']) or _pretty(p['tail'])
        modules.append({
            'key': key,
            'title': {lang: titles.get(lang) or titles.get('ru') or _pretty(key)
                      for lang in LANGS},
            'icon': man.get('icon') or '▪',
            'descr': man.get('descr') or '',
            'order': man.get('order', 500),
            'group': man.get('group') or ('tools' if key in TOOL_KEYS else 'modules'),
            'url': man.get('url') or items[0]['url'],
            'docs': man.get('docs'),
            'sql_prefix': man.get('sql_prefix'),
            'pages': items,
            'page_count': len(items),
            'has_manifest': bool(man) and 'error' not in man,
            'manifest_error': man.get('error'),
        })

    # Модули, у которых есть манифест, но не осталось ни одного маршрута —
    # тоже показываем: это сигнал, что маршруты отвалились, а не повод
    # молча убрать пункт из меню.
    for key, man in manifests.items():
        if key in pages:
            continue
        titles = man.get('title') or {}
        modules.append({
            'key': key,
            'title': {lang: titles.get(lang) or titles.get('ru') or _pretty(key)
                      for lang in LANGS},
            'icon': man.get('icon') or '▪',
            'descr': man.get('descr') or '',
            'order': man.get('order', 500),
            'group': man.get('group') or 'modules',
            'url': man.get('url') or f'{BASE}/{key}',
            'docs': man.get('docs'), 'sql_prefix': man.get('sql_prefix'),
            'pages': [], 'page_count': 0,
            'has_manifest': 'error' not in man,
            'manifest_error': man.get('error'),
            'orphan': True,
        })

    modules.sort(key=lambda m: (m['order'], m['title']['ru']))
    return {
        'modules': modules,
        'by_group': {
            'modules': [m for m in modules if m['group'] == 'modules'],
            'tools': [m for m in modules if m['group'] == 'tools'],
        },
        'total_modules': len(modules),
        'total_pages': sum(m['page_count'] for m in modules),
        'without_manifest': [m['key'] for m in modules if not m['has_manifest']],
    }


def get(app, lang: str = 'ru', refresh: bool = False) -> Dict[str, Any]:
    """Карта модулей с кэшем на время работы процесса."""
    global _cache
    if _cache is None or refresh:
        _cache = discover(app)
    data = json.loads(json.dumps(_cache))          # копия: язык подставляем поверх
    for m in data['modules']:
        m['name'] = m['title'].get(lang) or m['title']['ru']
    for grp in data['by_group'].values():
        for m in grp:
            m['name'] = m['title'].get(lang) or m['title']['ru']
    return data


def reset() -> None:
    global _cache
    _cache = None
