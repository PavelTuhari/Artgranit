"""SDA — рендер Markdown в HTML для собственного хаба документации.

`app.py` не подходит: `_docs_md_to_html` там — приватный helper общего
кода, а модуль не имеет права опираться на приватные детали app.py (и
после переноса на ядро модулей общий код о SDA вообще не знает). Поэтому
здесь — самодостаточная копия того же алгоритма: markdown-библиотека,
если она установлена, иначе упрощённый регэксп-фолбэк один в один с
оригиналом из app.py.
"""
from __future__ import annotations

import re
import unicodedata


def _slugify(value, separator='-'):
    """Транслитерация заголовка в якорь ссылки — как в app.py."""
    text = unicodedata.normalize('NFKC', str(value)).strip().lower()
    text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE)
    return re.sub(r'[\s_]+', separator, text).strip(separator)


def docs_md_to_html(markdown_content: str) -> str:
    """Конвертация Markdown в HTML для docs viewer модуля SDA."""
    try:
        import markdown
        # toc даёт заголовкам якоря по тексту: без него внутренние ссылки
        # вида [Раздел](#раздел) в документе никуда не ведут — просмотрщик
        # нумерует заголовки как h0, h1, … и о слагах не знает.
        md = markdown.Markdown(
            extensions=['codehilite', 'fenced_code', 'tables', 'nl2br', 'toc'],
            extension_configs={'toc': {'slugify': _slugify}})
        return md.convert(markdown_content)
    except ImportError:
        html = markdown_content
        html = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code>\2</code></pre>',
                      html, flags=re.DOTALL)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'(?<!`)(?<!<code>)`([^`\n]+)`(?!`)(?!</code>)',
                      r'<code>\1</code>', html)
        html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)
        lines = html.split('\n')
        result, in_list = [], False
        for line in lines:
            m = re.match(r'^[-*]\s+(.+)', line)
            if m:
                if not in_list:
                    result.append('<ul>')
                    in_list = True
                result.append(f'<li>{m.group(1)}</li>')
            else:
                if in_list:
                    result.append('</ul>')
                    in_list = False
                if line.strip() and not line.strip().startswith('<'):
                    result.append(f'<p>{line.strip()}</p>')
                elif line.strip():
                    result.append(line)
        if in_list:
            result.append('</ul>')
        return '\n'.join(result)
