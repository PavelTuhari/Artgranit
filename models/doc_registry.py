"""
Реестр документации модуля: что лежит в папке docs/<Модуль>/.

Та же болезнь, что и с меню модулей, только в документации. Список
документов был вписан в `app.py` руками, и новый файл в папке не
появлялся в хабе, пока кто-нибудь не вспомнит про этот список. Пример
свежий: методичку по топливу пришлось добавлять в реестр отдельным
действием — а могли и не добавить.

Теперь источник правды — **сама папка**. Все `*.md` из неё попадают
в хаб. Файл `docs.json` рядом добавляет иконку, аудиторию, порядок
и флаг публичности; документ без записи в манифесте всё равно виден,
просто с названием из первого заголовка `#` и описанием из первого
абзаца.

Про публичность отдельно. Незнакомый документ по умолчанию **закрыт
входом**, а не открыт: в docs-папках лежат в том числе пути на сервере,
размещение wallet и перечень ключей окружения, и открывать такое
автоматически нельзя. «Видно» и «доступно анониму» — разные вещи:
в хабе документ виден всегда, читать его без входа можно только
если это указано в манифесте явно.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

CLASSES = ('', 'g', 'w', 'v', 'c')


def _title_and_lead(path: str) -> tuple[str, str]:
    """Заголовок и первый абзац файла — на случай, когда манифест молчит."""
    title, lead = '', ''
    try:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                if not title:
                    if line.startswith('# '):
                        title = line[2:].strip()
                    continue
                if line.startswith('#') or line.startswith('>'):
                    continue
                lead = re.sub(r'[*`\[\]]|\(/[^)]*\)', '', line)[:220]
                break
    except Exception:                                            # noqa: BLE001
        pass
    return title, lead


def _slug(filename: str) -> str:
    return os.path.splitext(filename)[0].lower().replace('_', '-')


def scan(docs_dir: str) -> List[Dict[str, Any]]:
    """
    Список документов папки: манифест + всё остальное, что там лежит.

    Порядок: сначала описанные в манифесте (в его порядке), затем
    найденные автоматически — по алфавиту.
    """
    manifest: Dict[str, Any] = {}
    mpath = os.path.join(docs_dir, 'docs.json')
    if os.path.isfile(mpath):
        try:
            with open(mpath, encoding='utf-8') as fh:
                manifest = json.load(fh)
        except Exception:                                        # noqa: BLE001
            manifest = {}

    files = sorted(f for f in os.listdir(docs_dir)
                   if f.lower().endswith('.md')) if os.path.isdir(docs_dir) else []

    out: List[Dict[str, Any]] = []
    described = [f for f in manifest if f in files]
    described.sort(key=lambda f: manifest[f].get('order', 500))
    rest = [f for f in files if f not in manifest]

    for order, filename in enumerate(described + rest):
        man = manifest.get(filename, {})
        auto_title, auto_lead = _title_and_lead(os.path.join(docs_dir, filename))
        out.append({
            'slug': man.get('slug') or _slug(filename),
            'file': filename,
            'public': bool(man.get('public', False)),
            'icon': man.get('icon') or '📄',
            'cls': man.get('cls') if man.get('cls') in CLASSES else '',
            'title': man.get('title') or auto_title or filename,
            'audience': man.get('audience') or ('без описания в docs.json'),
            'descr': man.get('descr') or auto_lead,
            'known': filename in manifest,
            'order': man.get('order', 1000 + order),
        })
    return out
