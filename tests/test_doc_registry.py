"""Реестр документации: что попадает в хаб модуля, а что нет.

Хаб собирается из самой папки `docs/<Модуль>/`, поэтому в него попадает
всё, что там лежит. На боевом сервере это дало карточки-призраки
«._SPEC_SDA.md — без описания в docs.json»: macOS кладёт рядом с каждым
файлом AppleDouble-двойник `._имя`, и он приезжает вместе с архивом
деплоя. Тесты закрывают ровно этот класс: служебные файлы — не документы.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import doc_registry  # noqa: E402


def _docs_dir(tmp, files, manifest=None):
    for name, body in files.items():
        with open(os.path.join(tmp, name), 'w', encoding='utf-8') as fh:
            fh.write(body)
    if manifest is not None:
        with open(os.path.join(tmp, 'docs.json'), 'w', encoding='utf-8') as fh:
            json.dump(manifest, fh)
    return tmp


def test_appledouble_twins_are_not_documents():
    with tempfile.TemporaryDirectory() as tmp:
        _docs_dir(tmp, {
            'GUIDE.md': '# Ghid\n\nPrimul paragraf.\n',
            '._GUIDE.md': 'Mac OS X\x00\x02\x00binary junk',
        })
        names = [d['file'] for d in doc_registry.scan(tmp)]
        assert names == ['GUIDE.md'], names


def test_hidden_files_are_not_documents():
    with tempfile.TemporaryDirectory() as tmp:
        _docs_dir(tmp, {
            'GUIDE.md': '# Ghid\n\nPrimul paragraf.\n',
            '.draft.md': '# Ciornă\n',
        })
        names = [d['file'] for d in doc_registry.scan(tmp)]
        assert names == ['GUIDE.md'], names


def test_a_real_document_without_a_manifest_entry_is_still_listed():
    """Отсечение по точке не должно задеть обычные файлы."""
    with tempfile.TemporaryDirectory() as tmp:
        _docs_dir(tmp, {
            'GUIDE.md': '# Ghid\n\nPrimul paragraf.\n',
            'EXTRA.md': '# Extra\n\nAl doilea.\n',
        }, manifest={'GUIDE.md': {'slug': 'guide', 'public': True}})
        names = sorted(d['file'] for d in doc_registry.scan(tmp))
        assert names == ['EXTRA.md', 'GUIDE.md'], names
