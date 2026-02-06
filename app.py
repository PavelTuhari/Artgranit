#!/usr/bin/env python3
"""
Главное приложение Oracle SQL Developer - UNA.md/orasldev
MVC архитектура с WebSockets для реального времени
"""
from flask import Flask, Response, render_template, jsonify, request, session, redirect, url_for, g, send_from_directory
from flask_socketio import SocketIO, emit
from flask_babel import Babel, _, lazy_gettext as _l
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from controllers.auth_controller import AuthController
from controllers.dashboard_controller import DashboardController
from controllers.sql_controller import SQLController
from controllers.objects_controller import ObjectsController
from controllers.combo_scenario_controller import ComboScenarioController
from controllers.credit_controller import CreditController
from controllers.nufarul_controller import NufarulController
from controllers.documentation_controller import DocumentationController
from controllers.shell_controller import ShellController
from controllers.digi_marketing_controller import DigiMarketingController
import threading
import time
import os
import sys
from pathlib import Path

# Создание приложения Flask
app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Инициализация Babel для интернационализации
babel = Babel()

def get_locale():
    """Определяет язык из сессии или заголовков браузера"""
    # Проверяем язык в сессии
    if 'language' in session:
        if session['language'] in Config.SUPPORTED_LANGUAGES:
            return session['language']
    
    # Проверяем язык из query параметра
    language = request.args.get('lang', None)
    if language and language in Config.SUPPORTED_LANGUAGES:
        session['language'] = language
        return language
    
    # Используем язык браузера
    return request.accept_languages.best_match(Config.SUPPORTED_LANGUAGES) or Config.BABEL_DEFAULT_LOCALE

# Инициализируем Babel с приложением
babel.init_app(app, locale_selector=get_locale)

# Rate limiting (только для /api/*)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[Config.RATELIMIT_DEFAULT] if Config.RATELIMIT_ENABLED else [],
    storage_uri=Config.RATELIMIT_STORAGE_URI,
    default_limits_per_method=True,
)


@limiter.request_filter
def _skip_limit_for_non_api():
    """Применять rate limit только к /api/*"""
    return not request.path.startswith('/api/')


@app.errorhandler(429)
def ratelimit_handler(e):
    """Ответ при превышении лимита запросов"""
    return jsonify({
        "success": False,
        "error": "Rate limit exceeded",
        "message": "Слишком много запросов. Попробуйте позже.",
    }), 429


# Инициализация SocketIO для WebSockets
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Контекстный процессор для шаблонов - делает функцию _() доступной везде
@app.context_processor
def inject_gettext():
    return dict(_=_, get_locale=get_locale, languages=Config.LANGUAGES, supported_languages=Config.SUPPORTED_LANGUAGES)


def _login_redirect():
    """Редирект на логин с сохранением текущего URL в next= для возврата после входа."""
    next_path = (request.full_path or request.path or "").strip()
    if next_path and next_path != "login" and not next_path.startswith("/login"):
        return redirect(url_for("login", next=next_path))
    return redirect(url_for("login"))


def _is_safe_redirect_url(url):
    """Проверка, что URL для редиректа внутренний (нет открытых редиректов)."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith("/") or "//" in url:
        return False
    return True

# Хранилище активных подписок на метрики
active_subscriptions = {}


@app.route('/')
def index():
    """Главная страница - редирект на login или SQL Developer"""
    if AuthController.is_authenticated():
        return redirect(url_for('sqldeveloper'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        if AuthController.login(username, password):
            AuthController.set_authenticated(True)
            return jsonify({"success": True, "redirect": url_for('sqldeveloper')})
        else:
            return jsonify({"success": False, "error": _("Invalid credentials")}), 401
    
    # GET запрос - показываем форму с предзаполненными данными (next — куда вернуться после входа)
    next_url = request.args.get('next', '')
    return render_template('login.html', 
                         default_username=Config.DEFAULT_USERNAME,
                         default_password=Config.DEFAULT_PASSWORD,
                         next_url=next_url)


@app.route('/logout')
def logout():
    """Выход из системы"""
    AuthController.logout()
    return redirect(url_for('login'))


@app.route('/UNA.md/orasldev')
@app.route('/UNA.md/orasldev/')
def sqldeveloper():
    """Oracle SQL Developer интерфейс"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return render_template('sqldeveloper_mdi.html', username=AuthController.get_current_user())


@app.route('/UNA.md/orasldev/dashboard')
@app.route('/UNA.md/orasldev/dashboard/<dashboard_id>')
def dashboard(dashboard_id=None):
    """Dashboard с метриками БД"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    
    # Проверяем query параметр ?p=XX
    query_param = request.args.get('p', None)
    if query_param:
        dashboard_id = query_param
    
    # Определяем режим: fullscreen если указан dashboard_id
    is_fullscreen = dashboard_id is not None
    
    return render_template('dashboard_mdi.html', dashboard_id=dashboard_id, is_fullscreen=is_fullscreen)


@app.route('/UNA.md/orasldev/credit-admin')
def credit_admin():
    """Админ-панель настройки кредитных предложений (embed в дашборде 04)"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return render_template('credit_admin.html')


@app.route('/UNA.md/orasldev/credit-portfolio-bomba')
def credit_portfolio_bomba():
    """Кредитный портфель Бомба: пивот категории/товары × банки/программы + настройки."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return render_template('credit_portfolio_bomba.html')


@app.route('/UNA.md/orasldev/credit-operator')
def credit_operator():
    """Интерфейс оператора оформления кредитов (embed в дашборде 05)"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return render_template('credit_operator.html')


@app.route('/UNA.md/orasldev/nufarul-admin')
def nufarul_admin():
    """Админка Nufarul: услуги, заказы, отчёты"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return render_template('nufarul_admin.html')


@app.route('/UNA.md/orasldev/nufarul-operator')
def nufarul_operator():
    """Интерфейс оператора приёма заказов в зале (Nufarul)"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return render_template('nufarul_operator.html')


@app.route('/UNA.md/orasldev/credit-easycredit')
def credit_easycredit():
    """Оформление кредита по EasyCredit API (sandbox). Preapproved → Request → Status."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return render_template('credit_easycredit.html')


@app.route('/UNA.md/orasldev/credit-iute')
def credit_iute():
    """Оформление кредита по Iute API. Check Auth → Create Order → Check Status."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return render_template('credit_iute.html')


@app.route('/UNA.md/orasldev/docs')
@app.route('/UNA.md/orasldev/docs/')
def docs_index():
    """Главная страница документации"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return render_template('docs_index.html')


def _docs_md_to_html(markdown_content):
    """Конвертация Markdown в HTML для docs viewer."""
    try:
        import markdown
        from markdown.extensions import codehilite, fenced_code, tables
        md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables', 'nl2br'])
        return md.convert(markdown_content)
    except ImportError:
        import re
        html = markdown_content
        html = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'(?<!`)(?<!<code>)`([^`\n]+)`(?!`)(?!</code>)', r'<code>\1</code>', html)
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


def _render_doc_page(md_path, title):
    """Загружает .md, конвертирует в HTML, рендерит docs_viewer."""
    from pathlib import Path
    path = Path(md_path)
    if not path.exists():
        return None, ("<h1>Документация не найдена</h1>", 404)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            html_content = _docs_md_to_html(f.read())
        return render_template('docs_viewer.html', content=html_content, title=title), None
    except Exception as e:
        return None, (f"<h1>Ошибка</h1><p>{e}</p>", 500)


@app.route('/UNA.md/orasldev/docs/dashboard/<dashboard_id>')
def docs_dashboard(dashboard_id):
    """Документация по конкретному дашборду"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from pathlib import Path
    docs_path = Path(__file__).parent / "docs" / "dashboards" / f"dashboard_{dashboard_id}.md"
    if not docs_path.exists():
        return f"<h1>Документация не найдена</h1><p>Документация для дашборда {dashboard_id} не существует.</p>", 404
    resp, err = _render_doc_page(docs_path, f"Документация: Dashboard {dashboard_id}")
    if err:
        return err
    return resp


@app.route('/UNA.md/orasldev/docs/configuration')
def docs_configuration():
    """Страница «Конфигурация»"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from pathlib import Path
    p = Path(__file__).parent / "docs" / "CONFIGURATION.md"
    resp, err = _render_doc_page(p, "Конфигурация")
    if err:
        return err
    return resp


@app.route('/UNA.md/orasldev/docs/deployment')
def docs_deployment():
    """Страница «Развертывание»"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from pathlib import Path
    p = Path(__file__).parent / "docs" / "DEPLOYMENT.md"
    resp, err = _render_doc_page(p, "Развертывание")
    if err:
        return err
    return resp


@app.route('/UNA.md/orasldev/docs/widgets')
def docs_widgets():
    """Страница «Разработка виджетов»"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from pathlib import Path
    p = Path(__file__).parent / "docs" / "WIDGET_DEVELOPMENT.md"
    resp, err = _render_doc_page(p, "Разработка виджетов")
    if err:
        return err
    return resp


@app.route('/UNA.md/orasldev/docs/api')
def docs_api():
    """Страница «API документация»"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from pathlib import Path
    p = Path(__file__).parent / "docs" / "API.md"
    resp, err = _render_doc_page(p, "API документация")
    if err:
        return err
    return resp


@app.route('/UNA.md/orasldev/docs/easycredit')
def docs_easycredit():
    """Документация интеграции EasyCredit"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from pathlib import Path
    p = Path(__file__).parent / "docs" / "project_easycredit.html"
    if not p.exists():
        return "<h1>Документация не найдена</h1>", 404
    return p.read_text(encoding='utf-8')


@app.route('/UNA.md/orasldev/docs/iute')
def docs_iute():
    """Документация интеграции Iute"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from pathlib import Path
    p = Path(__file__).parent / "docs" / "project_iute.html"
    if not p.exists():
        return "<h1>Документация Iute не найдена</h1><p><a href='/UNA.md/orasldev/docs'>Назад</a></p>", 404
    return p.read_text(encoding='utf-8')


@app.route('/UNA.md/orasldev/docs/cred-reports')
def docs_cred_reports():
    """Документация настраиваемых отчётов"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from pathlib import Path
    p = Path(__file__).parent / "docs" / "CRED_REPORTS.md"
    resp, err = _render_doc_page(p, "Настраиваемые отчёты")
    if err:
        return err
    return resp


@app.route('/UNA.md/orasldev/docs/project-documentation')
def docs_project_documentation():
    """Полная документация проекта в HTML для передачи в Claude Code"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    p = Path(__file__).resolve().parent / "docs" / "PROJECT_DOCUMENTATION.html"
    if not p.is_file():
        return "<h1>Документация не найдена</h1><p>Файл docs/PROJECT_DOCUMENTATION.html отсутствует.</p>", 404
    return Response(p.read_text(encoding="utf-8"), mimetype="text/html; charset=utf-8")


@app.route('/UNA.md/orasldev/docs/sql')
def docs_sql():
    """Документация DDL скриптов"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from pathlib import Path
    p = Path(__file__).parent / "sql" / "README.md"
    if not p.exists():
        return "<h1>Документация SQL не найдена</h1><p><a href='/UNA.md/orasldev/docs'>Назад</a></p>", 404
    resp, err = _render_doc_page(p, "DDL скрипты")
    if err:
        return err
    return resp


# База для HTML-документов Nufarul (абсолютный путь)
_DOCS_NUFARUL_DIR = Path(__file__).resolve().parent / "docs" / "Nufarul"


@app.route('/UNA.md/orasldev/docs/nufarul')
@app.route('/UNA.md/orasldev/docs/nufarul/')
def docs_nufarul_index():
    """ТЗ Nufarul — список материалов (индекс)"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    p = _DOCS_NUFARUL_DIR / "index.html"
    if not p.is_file():
        return "<h1>Не найдено</h1><p><a href='/UNA.md/orasldev/docs'>Назад</a></p>", 404
    html = p.read_text(encoding='utf-8')
    return Response(html, mimetype='text/html; charset=utf-8')


# Разрешить скачивание/просмотр исходных файлов из docs/Nufarul (.doc, .xlsx, .pdf, .rtf, изображения)
_DOCS_NUFARUL_ALLOWED_EXT = {'.doc', '.docx', '.xlsx', '.xls', '.pdf', '.rtf', '.jpeg', '.jpg', '.png', '.gif'}


@app.route('/UNA.md/orasldev/docs/nufarul/file/<path:encoded_name>')
def docs_nufarul_download(encoded_name):
    """Скачать/открыть исходный файл из docs/Nufarul (имя в URL-кодировке)."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from urllib.parse import unquote
    try:
        decoded = unquote(encoded_name, errors='strict')
    except Exception:
        return "<h1>Неверное имя файла</h1>", 400
    safe = Path(decoded).name
    if not safe or '..' in decoded or '/' in decoded or '\\' in decoded:
        return "<h1>Неверный путь</h1>", 400
    if Path(safe).suffix.lower() not in _DOCS_NUFARUL_ALLOWED_EXT:
        return "<h1>Тип файла не разрешён</h1>", 400
    p = (_DOCS_NUFARUL_DIR / safe).resolve()
    try:
        p.relative_to(_DOCS_NUFARUL_DIR.resolve())
    except ValueError:
        return "<h1>Неверный путь</h1>", 400
    if not p.is_file():
        return "<h1>Файл не найден</h1><p><a href='/UNA.md/orasldev/docs/nufarul/'>Назад</a></p>", 404
    from flask import send_file
    return send_file(
        p, as_attachment=False, download_name=safe,
        mimetype=None
    )


@app.route('/UNA.md/orasldev/docs/nufarul/view-xlsx/<path:encoded_name>')
def docs_nufarul_view_xlsx(encoded_name):
    """Просмотр .xlsx из docs/Nufarul в виде HTML-таблиц."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from urllib.parse import unquote
    try:
        decoded = unquote(encoded_name, errors='strict')
    except Exception:
        return "<h1>Неверное имя файла</h1>", 400
    safe = Path(decoded).name
    if not safe or Path(safe).suffix.lower() != '.xlsx':
        return "<h1>Только .xlsx</h1>", 400
    p = (_DOCS_NUFARUL_DIR / safe).resolve()
    try:
        p.relative_to(_DOCS_NUFARUL_DIR.resolve())
    except ValueError:
        return "<h1>Неверный путь</h1>", 400
    if not p.is_file():
        return "<h1>Файл не найден</h1><p><a href='/UNA.md/orasldev/docs/nufarul/'>Назад</a></p>", 404
    try:
        import openpyxl
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    except Exception as e:
        return f"<h1>Ошибка чтения Excel</h1><p>{e}</p><p><a href='/UNA.md/orasldev/docs/nufarul/'>Назад</a></p>", 500
    from html import escape
    def _cell(v):
        if v is None:
            return ""
        return escape(str(v).strip())
    parts = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            parts.append(f"<h2>{escape(sheet_name)}</h2><p>Пустой лист</p>")
            continue
        parts.append(f"<h2>{escape(sheet_name)}</h2>")
        parts.append("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse; width:100%;'>")
        for i, row in enumerate(rows):
            tag = "th" if i == 0 else "td"
            cells = "".join(f"<{tag}>{_cell(v)}</{tag}>" for v in (row or []))
            parts.append(f"<tr>{cells}</tr>")
        parts.append("</table>")
    wb.close()
    html = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>{escape(safe)}</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:24px;color:#134e4a;}} table{{margin-bottom:24px;}} th{{background:#0d9488;color:#fff;}}</style></head><body>
<h1>{escape(safe)}</h1>
{"".join(parts)}
<p><a href="/UNA.md/orasldev/docs/nufarul/">← К списку материалов</a></p>
</body></html>"""
    return Response(html, mimetype='text/html; charset=utf-8')


def _docs_nufarul_convert_doc_to_html(p: Path, safe: str) -> tuple[str | None, str | None]:
    """Конвертирует .doc/.docx в HTML. Возвращает (html_body, error_message)."""
    from html import escape
    suffix = p.suffix.lower()
    # 1) .docx через mammoth
    if suffix == '.docx':
        try:
            import mammoth
            with open(p, 'rb') as f:
                result = mammoth.convert_to_html(f)
            body = result.value or ''
            if not body.strip():
                body = '<p>Документ пуст или не удалось извлечь текст.</p>'
            return (f'<h1>{escape(safe)}</h1>{body}', None)
        except Exception as e:
            return (None, str(e))
    # 2) .doc — пробуем mammoth (иногда срабатывает), иначе LibreOffice
    if suffix == '.doc':
        try:
            import mammoth
            with open(p, 'rb') as f:
                result = mammoth.convert_to_html(f)
            body = (result.value or '').strip()
            if body:
                return (f'<h1>{escape(safe)}</h1>{body}', None)
        except Exception:
            pass
        # LibreOffice headless: soffice --headless --convert-to html --outdir <dir> <file>
        import subprocess
        import tempfile
        soffice = None
        for candidate in ('soffice', '/Applications/LibreOffice.app/Contents/MacOS/soffice', '/usr/bin/soffice'):
            try:
                r = subprocess.run([candidate, '--version'], capture_output=True, timeout=2)
                if r.returncode == 0:
                    soffice = candidate
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        if soffice:
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    out_dir = Path(tmp)
                    r = subprocess.run(
                        [soffice, '--headless', '--convert-to', 'html', '--outdir', str(out_dir), str(p)],
                        capture_output=True, text=True, timeout=30, cwd=str(p.parent)
                    )
                    if r.returncode == 0:
                        # Ищем .html в tmp (имя без .doc + .html)
                        html_name = p.stem + '.html'
                        html_path = out_dir / html_name
                        if not html_path.exists():
                            for f in out_dir.glob('*.html'):
                                html_path = f
                                break
                        if html_path and html_path.is_file():
                            raw = html_path.read_text(encoding='utf-8', errors='replace')
                            # Внутреннее содержимое body (без тегов <body>...</body>)
                            if '<body' in raw and '</body>' in raw:
                                start = raw.find('<body')
                                start = raw.find('>', start) + 1
                                end = raw.find('</body>', start)
                                body = raw[start:end] if end > start else raw
                            else:
                                body = raw
                            return (f'<h1>{escape(safe)}</h1><div class="doc-body">{body}</div>', None)
            except Exception as e:
                return (None, str(e))
        return (None, 'Для просмотра .doc в браузере установите LibreOffice или скачайте файл и откройте в Word.')
    return (None, 'Поддерживаются только .doc и .docx')


@app.route('/UNA.md/orasldev/docs/nufarul/view-doc/<path:encoded_name>')
def docs_nufarul_view_doc(encoded_name):
    """Просмотр .doc/.docx из docs/Nufarul в виде HTML."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from urllib.parse import unquote, quote
    try:
        decoded = unquote(encoded_name, errors='strict')
    except Exception:
        return "<h1>Неверное имя файла</h1>", 400
    safe = Path(decoded).name
    if not safe or Path(safe).suffix.lower() not in ('.doc', '.docx'):
        return "<h1>Только .doc и .docx</h1>", 400
    p = (_DOCS_NUFARUL_DIR / safe).resolve()
    try:
        p.relative_to(_DOCS_NUFARUL_DIR.resolve())
    except ValueError:
        return "<h1>Неверный путь</h1>", 400
    if not p.is_file():
        return "<h1>Файл не найден</h1><p><a href='/UNA.md/orasldev/docs/nufarul/'>Назад</a></p>", 404
    from html import escape
    body_html, err = _docs_nufarul_convert_doc_to_html(p, safe)
    if err:
        back = '/UNA.md/orasldev/docs/nufarul/'
        file_url = f'/UNA.md/orasldev/docs/nufarul/file/{quote(safe, safe="")}'
        return Response(
            f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>{escape(safe)}</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:24px;color:#134e4a;}} .err{{background:#fef2f2;padding:16px;border-radius:8px;}}</style></head><body>
<h1>{escape(safe)}</h1>
<p class="err">{escape(err)}</p>
<p><a href="{escape(file_url)}">Скачать исходный файл</a></p>
<p><a href="{back}">← К списку материалов</a></p>
</body></html>""",
            mimetype='text/html; charset=utf-8'
        )
    full_html = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>{escape(safe)}</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:24px;max-width:800px;color:#134e4a;}} .doc-body table{{border-collapse:collapse;}} .doc-body th,.doc-body td{{border:1px solid #99f6e4;padding:8px;}}</style></head><body>
{body_html}
<p><a href="/UNA.md/orasldev/docs/nufarul/">← К списку материалов</a></p>
</body></html>"""
    return Response(full_html, mimetype='text/html; charset=utf-8')


def _docs_nufarul_convert_pdf_to_html(p: Path, safe: str) -> tuple[str | None, str | None]:
    """Конвертирует PDF в HTML (текст/разметка через pdfminer.six). Возвращает (html_body, error_message)."""
    from html import escape
    try:
        from io import BytesIO
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams
        out = BytesIO()
        with open(p, 'rb') as fin:
            extract_text_to_fp(fin, out, laparams=LAParams(), output_type='html', codec='utf-8')
        body = out.getvalue().decode('utf-8', errors='replace')
        if not (body and body.strip()):
            return (None, 'Не удалось извлечь текст из PDF.')
        # pdfminer HTML может содержать полную страницу или фрагмент — берём содержимое body
        if '<body' in body and '</body>' in body:
            start = body.find('<body')
            start = body.find('>', start) + 1
            end = body.find('</body>', start)
            body = body[start:end] if end > start else body
        return (f'<h1>{escape(safe)}</h1><div class="pdf-body">{body}</div>', None)
    except ImportError:
        return (None, 'Установите pdfminer.six: pip install pdfminer.six')
    except Exception as e:
        return (None, str(e))


@app.route('/UNA.md/orasldev/docs/nufarul/view-pdf/<path:encoded_name>')
def docs_nufarul_view_pdf(encoded_name):
    """Просмотр PDF из docs/Nufarul в виде HTML."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    from urllib.parse import unquote, quote
    try:
        decoded = unquote(encoded_name, errors='strict')
    except Exception:
        return "<h1>Неверное имя файла</h1>", 400
    safe = Path(decoded).name
    if not safe or Path(safe).suffix.lower() != '.pdf':
        return "<h1>Только .pdf</h1>", 400
    p = (_DOCS_NUFARUL_DIR / safe).resolve()
    try:
        p.relative_to(_DOCS_NUFARUL_DIR.resolve())
    except ValueError:
        return "<h1>Неверный путь</h1>", 400
    if not p.is_file():
        return "<h1>Файл не найден</h1><p><a href='/UNA.md/orasldev/docs/nufarul/'>Назад</a></p>", 404
    from html import escape
    body_html, err = _docs_nufarul_convert_pdf_to_html(p, safe)
    if err:
        back = '/UNA.md/orasldev/docs/nufarul/'
        file_url = f'/UNA.md/orasldev/docs/nufarul/file/{quote(safe, safe="")}'
        return Response(
            f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>{escape(safe)}</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:24px;color:#134e4a;}} .err{{background:#fef2f2;padding:16px;border-radius:8px;}}</style></head><body>
<h1>{escape(safe)}</h1>
<p class="err">{escape(err)}</p>
<p><a href="{escape(file_url)}">Скачать исходный PDF</a></p>
<p><a href="{back}">← К списку материалов</a></p>
</body></html>""",
            mimetype='text/html; charset=utf-8'
        )
    full_html = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>{escape(safe)}</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:24px;max-width:900px;color:#134e4a;}} .pdf-body table{{border-collapse:collapse;}} .pdf-body th,.pdf-body td{{border:1px solid #99f6e4;padding:6px;}}</style></head><body>
{body_html}
<p><a href="/UNA.md/orasldev/docs/nufarul/">← К списку материалов</a></p>
</body></html>"""
    return Response(full_html, mimetype='text/html; charset=utf-8')


_DOCS_NUFARUL_JPG_DIR = _DOCS_NUFARUL_DIR / "docs_jpg"


@app.route('/UNA.md/orasldev/docs/nufarul/docs_jpg')
@app.route('/UNA.md/orasldev/docs/nufarul/docs_jpg/')
def docs_nufarul_docs_jpg_index():
    """Уточнение постановки задач — галерея JPG (docs_jpg)."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    p = _DOCS_NUFARUL_JPG_DIR / "index.html"
    if not p.is_file():
        return "<h1>Не найдено</h1><p><a href='/UNA.md/orasldev/docs/nufarul/'>Назад</a></p>", 404
    return Response(p.read_text(encoding='utf-8'), mimetype='text/html; charset=utf-8')


@app.route('/UNA.md/orasldev/docs/nufarul/docs_jpg/<path:subpath>')
def docs_nufarul_docs_jpg_file(subpath):
    """Файлы из docs/Nufarul/docs_jpg (JPG, HTML и т.д.)."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    safe = Path(subpath).name
    if not safe or ".." in subpath or subpath != subpath.strip():
        return "<h1>Неверный путь</h1>", 400
    p = (_DOCS_NUFARUL_JPG_DIR / subpath).resolve()
    try:
        p.relative_to(_DOCS_NUFARUL_JPG_DIR.resolve())
    except ValueError:
        return "<h1>Неверный путь</h1>", 400
    if not p.is_file():
        return "<h1>Не найдено</h1><p><a href='/UNA.md/orasldev/docs/nufarul/docs_jpg/'>Назад</a></p>", 404
    suffix = p.suffix.lower()
    if suffix == '.html':
        return Response(p.read_text(encoding='utf-8'), mimetype='text/html; charset=utf-8')
    if suffix in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        from flask import send_file
        return send_file(p, mimetype=None, download_name=p.name)
    return "<h1>Тип файла не разрешён</h1>", 400


@app.route('/UNA.md/orasldev/docs/nufarul/<path:filename>')
def docs_nufarul_file(filename):
    """ТЗ Nufarul — HTML файлы (TZ.html, caiet_de_sacrini_2.html и т.д.)"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    safe = Path(filename).name
    if not safe or safe != filename.strip():
        return "<h1>Неверный путь</h1>", 400
    if Path(safe).suffix.lower() != '.html':
        return "<h1>Неверный тип файла</h1>", 400
    p = (_DOCS_NUFARUL_DIR / safe).resolve()
    try:
        p.relative_to(_DOCS_NUFARUL_DIR.resolve())
    except ValueError:
        return "<h1>Неверный путь</h1>", 400
    if not p.is_file():
        return "<h1>Не найдено</h1><p><a href='/UNA.md/orasldev/docs/nufarul/'>Назад</a></p>", 404
    html = p.read_text(encoding='utf-8')
    return Response(html, mimetype='text/html; charset=utf-8')


# ========== Shell: основное приложение без дочерних проектов, список проектов из таблицы ==========
SHELL_PREFIX = '/una.md/shell'
# Каталог статики приложения «Агенты» (Nuxt generate → копировать в static/agents/)
SHELL_AGENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'agents')


@app.route(SHELL_PREFIX)
@app.route(SHELL_PREFIX + '/')
def shell_home():
    """Shell — главная: редирект на список проектов"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return redirect(url_for('shell_projects'))


@app.route(SHELL_PREFIX + '/projects')
def shell_projects():
    """Страница со списком ссылок на проекты: /una.md/shell/projects"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    links = ShellController.project_links(base_url=request.host_url.rstrip('/'))
    return render_template('shell_projects.html', project_links=links)


@app.route(SHELL_PREFIX + '/agents')
def shell_agents():
    """Приложение «Агенты» (Nuxt SPA) — редирект на слэш для корректных путей"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    return redirect(SHELL_PREFIX + '/agents/')


@app.route(SHELL_PREFIX + '/agents/')
def shell_agents_index():
    """Приложение «Агенты» — index.html (статическая сборка в static/agents/)"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    if not os.path.isdir(SHELL_AGENTS_DIR):
        return "<h1>Агенты</h1><p>Сборка не найдена. Выполните в каталоге AI_v7: <code>npm run generate</code>, затем скопируйте <code>.output/public/</code> в <code>Artgranit/static/agents/</code>.</p>", 404
    return send_from_directory(SHELL_AGENTS_DIR, 'index.html')


@app.route(SHELL_PREFIX + '/agents/<path:path>')
def shell_agents_static(path):
    """Приложение «Агенты» — статика и SPA fallback (client-side routing)"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    if not os.path.isdir(SHELL_AGENTS_DIR):
        return "<h1>Агенты</h1><p>Сборка не найдена.</p>", 404
    file_path = os.path.join(SHELL_AGENTS_DIR, path)
    if os.path.isfile(file_path):
        return send_from_directory(SHELL_AGENTS_DIR, path)
    return send_from_directory(SHELL_AGENTS_DIR, 'index.html')


@app.route(SHELL_PREFIX + '/<project_slug>')
@app.route(SHELL_PREFIX + '/<project_slug>/')
def shell_project_home(project_slug):
    """Проект по slug: редирект на дашборд проекта"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    project = ShellController.get_project_by_slug(project_slug)
    if not project:
        return f"<h1>Проект не найден</h1><p>Slug: {project_slug}</p><a href='{url_for('shell_projects')}'>← Список проектов</a>", 404
    return redirect(url_for('shell_project_dashboard', project_slug=project_slug))


@app.route(SHELL_PREFIX + '/<project_slug>/dashboard')
@app.route(SHELL_PREFIX + '/<project_slug>/dashboard/')
@app.route(SHELL_PREFIX + '/<project_slug>/dashboard/<dashboard_id>')
def shell_project_dashboard(project_slug, dashboard_id=None):
    """Дашборд проекта: свой набор дашбордов под префиксом /una.md/shell/<slug>"""
    if not AuthController.is_authenticated():
        return _login_redirect()
    project = ShellController.get_project_by_slug(project_slug)
    if not project:
        return f"<h1>Проект не найден</h1><p>Slug: {project_slug}</p><a href='{url_for('shell_projects')}'>← Список проектов</a>", 404
    query_param = request.args.get('p')
    if query_param:
        dashboard_id = query_param
    is_fullscreen = dashboard_id is not None
    return render_template(
        'shell_dashboard_mdi.html',
        project_slug=project_slug,
        project_name=project.get('name', project_slug),
        dashboard_id=dashboard_id,
        is_fullscreen=is_fullscreen,
    )


@app.route('/api/shell/projects', methods=['GET'])
def api_shell_projects():
    """API: список проектов shell (для страницы /una.md/shell/projects)"""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    projects = ShellController.get_all_projects()
    return jsonify({"success": True, "projects": projects, "count": len(projects)})


@app.route('/api/shell/projects/<project_slug>', methods=['GET'])
def api_shell_project(project_slug):
    """API: один проект по slug"""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    project = ShellController.get_project_by_slug(project_slug)
    if not project:
        return jsonify({"success": False, "error": "Project not found"}), 404
    return jsonify({"success": True, "project": project})


@app.route('/api/test_connection')
def test_connection():
    """Тест подключения к БД (для test.html)"""
    try:
        from models.database import DatabaseModel
        import datetime
        start_time = time.time()
        
        with DatabaseModel() as db:
            with db.connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")
                result = cursor.fetchone()
                
        duration = time.time() - start_time
        return jsonify({
            "success": True, 
            "message": f"Connected successfully! Result: {result[0]}",
            "duration": f"{duration:.3f}s",
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        return jsonify({
            "success": False, 
            "error": str(e)
        })


@app.route('/test.html')
def test_html():
    """Тестовая HTML страница"""
    return render_template('test.html')


# API Routes
@app.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint для входа. Поддерживает next= для редиректа после входа."""
    data = request.get_json() or {}
    username = data.get('username', '')
    password = data.get('password', '')
    next_path = data.get('next', '').strip()
    
    if AuthController.login(username, password):
        AuthController.set_authenticated(True)
        redirect_url = url_for('sqldeveloper')
        if next_path and _is_safe_redirect_url(next_path):
            redirect_url = next_path
        return jsonify({"success": True, "redirect": redirect_url})
    else:
        return jsonify({"success": False, "error": "Неверные учетные данные"}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """API endpoint для выхода"""
    AuthController.logout()
    return jsonify({"success": True})


@app.route('/api/status', methods=['GET'])
def api_status():
    """API endpoint для проверки статуса сервера"""
    return jsonify({
        "status": "running",
        "authenticated": AuthController.is_authenticated(),
        "username": AuthController.get_current_user() if AuthController.is_authenticated() else None,
        "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route('/api/execute-sql', methods=['POST'])
def api_execute_sql():
    """API endpoint для выполнения SQL запросов"""
    try:
        if not AuthController.is_authenticated():
            return jsonify({"success": False, "error": "Authentication required"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Invalid JSON in request body"}), 400
        
        sql_query = data.get('sql', '').strip()
        if not sql_query:
            return jsonify({"success": False, "error": "SQL query is empty"}), 400
        
        result = SQLController.execute(sql_query)
        # Убеждаемся, что результат всегда валидный JSON
        if not isinstance(result, dict):
            result = {"success": False, "error": "Invalid response format"}
        return jsonify(result)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": error_trace
        }), 500


@app.route('/api/dashboard/metrics', methods=['GET'])
def api_dashboard_metrics():
    """API endpoint для получения всех метрик БД"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    result = DashboardController.get_all_metrics()
    return jsonify(result)


@app.route('/api/dashboard/metric/<metric_name>', methods=['GET'])
def api_dashboard_metric(metric_name):
    """API endpoint для получения конкретной метрики"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    result = DashboardController.get_metric(metric_name)
    return jsonify(result)


@app.route('/api/dashboard/list', methods=['GET'])
def api_dashboard_list():
    """API endpoint для получения списка доступных dashboard'ов. Для shell: ?project_slug=<slug>."""
    try:
        if not AuthController.is_authenticated():
            return jsonify({"success": False, "error": "Authentication required"}), 401
        
        project_slug = request.args.get('project_slug') or None
        result = DashboardController.get_dashboards_list(project_slug=project_slug)
        if not isinstance(result, dict):
            result = {"success": False, "error": "Invalid response format", "dashboards": [], "count": 0}
        return jsonify(result)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "dashboards": [],
            "count": 0,
            "traceback": error_trace
        }), 500


@app.route('/api/dashboard/config/<dashboard_id>', methods=['GET'])
def api_dashboard_config(dashboard_id):
    """API endpoint для получения конфигурации dashboard'а по ID"""
    try:
        if not AuthController.is_authenticated():
            return jsonify({"success": False, "error": "Authentication required"}), 401
        
        result = DashboardController.get_dashboard_config(dashboard_id)
        if not isinstance(result, dict):
            result = {"success": False, "error": "Invalid response format"}
        return jsonify(result)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": error_trace
        }), 500


@app.route('/api/dashboard/widget/custom-sql', methods=['POST'])
def api_dashboard_widget_custom_sql():
    """API endpoint для выполнения SQL запроса из custom_sql виджета"""
    try:
        if not AuthController.is_authenticated():
            return jsonify({"success": False, "error": "Authentication required"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Invalid JSON in request body"}), 400
        
        database_type = data.get('database_type', 'oracle')
        sql_query = data.get('sql_query', '').strip()
        connection_params = data.get('connection_params', {})
        
        if not sql_query:
            return jsonify({"success": False, "error": "SQL query is empty"}), 400
        
        result = DashboardController.execute_custom_sql(database_type, sql_query, connection_params)
        if not isinstance(result, dict):
            result = {"success": False, "error": "Invalid response format"}
        return jsonify(result)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": error_trace
        }), 500


@app.route('/api/objects/schemas', methods=['GET'])
def api_objects_schemas():
    """API endpoint для получения списка схем"""
    try:
        if not AuthController.is_authenticated():
            return jsonify({"success": False, "error": "Authentication required"}), 401
        
        result = ObjectsController.get_schemas()
        # Убеждаемся, что результат всегда валидный JSON
        if not isinstance(result, dict):
            result = {"success": False, "error": "Invalid response format", "schemas": [], "count": 0}
        return jsonify(result)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "schemas": [],
            "count": 0,
            "traceback": error_trace
        }), 500


@app.route('/api/objects/tables', methods=['GET'])
def api_objects_tables():
    """API endpoint для получения списка таблиц"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_tables(schema)
    return jsonify(result)


@app.route('/api/objects/views', methods=['GET'])
def api_objects_views():
    """API endpoint для получения списка представлений"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_views(schema)
    return jsonify(result)


@app.route('/api/objects/procedures', methods=['GET'])
def api_objects_procedures():
    """API endpoint для получения списка процедур"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_procedures(schema)
    return jsonify(result)


@app.route('/api/objects/functions', methods=['GET'])
def api_objects_functions():
    """API endpoint для получения списка функций"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_functions(schema)
    return jsonify(result)


@app.route('/api/objects/packages', methods=['GET'])
def api_objects_packages():
    """API endpoint для получения списка пакетов"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_packages(schema)
    return jsonify(result)


@app.route('/api/objects/sequences', methods=['GET'])
def api_objects_sequences():
    """API endpoint для получения списка последовательностей"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_sequences(schema)
    return jsonify(result)


@app.route('/api/objects/synonyms', methods=['GET'])
def api_objects_synonyms():
    """API endpoint для получения списка синонимов"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_synonyms(schema)
    return jsonify(result)


@app.route('/api/objects/indexes', methods=['GET'])
def api_objects_indexes():
    """API endpoint для получения списка индексов"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_indexes(schema)
    return jsonify(result)


@app.route('/api/objects/triggers', methods=['GET'])
def api_objects_triggers():
    """API endpoint для получения списка триггеров"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_triggers(schema)
    return jsonify(result)


@app.route('/api/objects/types', methods=['GET'])
def api_objects_types():
    """API endpoint для получения списка типов"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_types(schema)
    return jsonify(result)


@app.route('/api/objects/materialized_views', methods=['GET'])
def api_objects_materialized_views():
    """API endpoint для получения списка материализованных представлений"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    schema = request.args.get('schema', None)
    result = ObjectsController.get_materialized_views(schema)
    return jsonify(result)


# ========== DIGI Marketing Module Routes ==========

@app.route('/UNA.md/digi-marketing')
@app.route('/UNA.md/digi-marketing/')
def digi_marketing():
    """Модуль управления мультимедийным контентом DIGI"""
    if not AuthController.is_authenticated():
        return redirect(url_for('login'))
    return render_template('digi_marketing.html')


# --- Dashboard & Stats ---
@app.route('/api/digi/stats', methods=['GET'])
def api_digi_stats():
    result = DigiMarketingController.get_dashboard_stats()
    return jsonify(result)


@app.route('/api/digi/events', methods=['GET'])
def api_digi_events():
    limit = request.args.get('limit', 100, type=int)
    entity_type = request.args.get('entity_type', None)
    result = DigiMarketingController.get_event_log(limit, entity_type)
    return jsonify(result)


@app.route('/api/digi/init-demo', methods=['POST'])
def api_digi_init_demo():
    result = DigiMarketingController.init_demo_data()
    return jsonify(result)


# --- Stores ---
@app.route('/api/digi/stores', methods=['GET'])
def api_digi_stores():
    result = DigiMarketingController.get_stores()
    return jsonify(result)


@app.route('/api/digi/stores/<store_id>', methods=['GET'])
def api_digi_store(store_id):
    result = DigiMarketingController.get_store(store_id)
    return jsonify(result)


@app.route('/api/digi/stores', methods=['POST'])
def api_digi_create_store():
    data = request.get_json()
    result = DigiMarketingController.create_store(data)
    return jsonify(result)


@app.route('/api/digi/stores/<store_id>', methods=['PUT'])
def api_digi_update_store(store_id):
    data = request.get_json()
    result = DigiMarketingController.update_store(store_id, data)
    return jsonify(result)


@app.route('/api/digi/stores/<store_id>', methods=['DELETE'])
def api_digi_delete_store(store_id):
    result = DigiMarketingController.delete_store(store_id)
    return jsonify(result)


# --- Departments ---
@app.route('/api/digi/departments', methods=['GET'])
def api_digi_departments():
    store_id = request.args.get('store_id', None)
    result = DigiMarketingController.get_departments(store_id)
    return jsonify(result)


@app.route('/api/digi/departments', methods=['POST'])
def api_digi_create_department():
    data = request.get_json()
    result = DigiMarketingController.create_department(data)
    return jsonify(result)


@app.route('/api/digi/departments/<dept_id>', methods=['DELETE'])
def api_digi_delete_department(dept_id):
    result = DigiMarketingController.delete_department(dept_id)
    return jsonify(result)


# --- Devices ---
@app.route('/api/digi/devices', methods=['GET'])
def api_digi_devices():
    store_id = request.args.get('store_id', None)
    department_id = request.args.get('department_id', None)
    result = DigiMarketingController.get_devices(store_id, department_id)
    return jsonify(result)


@app.route('/api/digi/devices/<device_id>', methods=['GET'])
def api_digi_device(device_id):
    result = DigiMarketingController.get_device(device_id)
    return jsonify(result)


@app.route('/api/digi/devices', methods=['POST'])
def api_digi_register_device():
    data = request.get_json()
    result = DigiMarketingController.register_device(data)
    return jsonify(result)


@app.route('/api/digi/devices/<device_id>', methods=['PUT'])
def api_digi_update_device(device_id):
    data = request.get_json()
    result = DigiMarketingController.update_device(device_id, data)
    return jsonify(result)


@app.route('/api/digi/devices/<device_id>', methods=['DELETE'])
def api_digi_delete_device(device_id):
    result = DigiMarketingController.delete_device(device_id)
    return jsonify(result)


# --- Media ---
@app.route('/api/digi/media', methods=['GET'])
def api_digi_media():
    media_type = request.args.get('type', None)
    resolution = request.args.get('resolution', None)
    result = DigiMarketingController.get_media_list(media_type, resolution)
    return jsonify(result)


@app.route('/api/digi/media/<media_id>', methods=['GET'])
def api_digi_media_item(media_id):
    result = DigiMarketingController.get_media(media_id)
    return jsonify(result)


@app.route('/api/digi/media', methods=['POST'])
def api_digi_upload_media():
    data = request.get_json()
    result = DigiMarketingController.upload_media(data)
    return jsonify(result)


@app.route('/api/digi/media/<media_id>', methods=['PUT'])
def api_digi_update_media(media_id):
    data = request.get_json()
    result = DigiMarketingController.update_media(media_id, data)
    return jsonify(result)


@app.route('/api/digi/media/<media_id>', methods=['DELETE'])
def api_digi_delete_media(media_id):
    result = DigiMarketingController.delete_media(media_id)
    return jsonify(result)


# --- Playlists ---
@app.route('/api/digi/playlists', methods=['GET'])
def api_digi_playlists():
    result = DigiMarketingController.get_playlists()
    return jsonify(result)


@app.route('/api/digi/playlists/<playlist_id>', methods=['GET'])
def api_digi_playlist(playlist_id):
    result = DigiMarketingController.get_playlist(playlist_id)
    return jsonify(result)


@app.route('/api/digi/playlists', methods=['POST'])
def api_digi_create_playlist():
    data = request.get_json()
    result = DigiMarketingController.create_playlist(data)
    return jsonify(result)


@app.route('/api/digi/playlists/<playlist_id>', methods=['PUT'])
def api_digi_update_playlist(playlist_id):
    data = request.get_json()
    result = DigiMarketingController.update_playlist(playlist_id, data)
    return jsonify(result)


@app.route('/api/digi/playlists/<playlist_id>', methods=['DELETE'])
def api_digi_delete_playlist(playlist_id):
    result = DigiMarketingController.delete_playlist(playlist_id)
    return jsonify(result)


# --- Campaigns ---
@app.route('/api/digi/campaigns', methods=['GET'])
def api_digi_campaigns():
    status = request.args.get('status', None)
    result = DigiMarketingController.get_campaigns(status)
    return jsonify(result)


@app.route('/api/digi/campaigns/<campaign_id>', methods=['GET'])
def api_digi_campaign(campaign_id):
    result = DigiMarketingController.get_campaign(campaign_id)
    return jsonify(result)


@app.route('/api/digi/campaigns', methods=['POST'])
def api_digi_create_campaign():
    data = request.get_json()
    result = DigiMarketingController.create_campaign(data)
    return jsonify(result)


@app.route('/api/digi/campaigns/<campaign_id>', methods=['PUT'])
def api_digi_update_campaign(campaign_id):
    data = request.get_json()
    result = DigiMarketingController.update_campaign(campaign_id, data)
    return jsonify(result)


@app.route('/api/digi/campaigns/<campaign_id>/publish', methods=['POST'])
def api_digi_publish_campaign(campaign_id):
    result = DigiMarketingController.publish_campaign(campaign_id)
    return jsonify(result)


@app.route('/api/digi/campaigns/<campaign_id>/pause', methods=['POST'])
def api_digi_pause_campaign(campaign_id):
    result = DigiMarketingController.pause_campaign(campaign_id)
    return jsonify(result)


@app.route('/api/digi/campaigns/<campaign_id>/stop', methods=['POST'])
def api_digi_stop_campaign(campaign_id):
    result = DigiMarketingController.stop_campaign(campaign_id)
    return jsonify(result)


@app.route('/api/digi/campaigns/<campaign_id>', methods=['DELETE'])
def api_digi_delete_campaign(campaign_id):
    result = DigiMarketingController.delete_campaign(campaign_id)
    return jsonify(result)


@app.route('/api/digi/campaigns/<campaign_id>/retry', methods=['POST'])
def api_digi_retry_campaign(campaign_id):
    device_id = request.args.get('device_id', None)
    result = DigiMarketingController.retry_delivery(campaign_id, device_id)
    return jsonify(result)


# --- Sync & Reports ---
@app.route('/api/digi/sync-log', methods=['GET'])
def api_digi_sync_log():
    campaign_id = request.args.get('campaign_id', None)
    device_id = request.args.get('device_id', None)
    limit = request.args.get('limit', 50, type=int)
    result = DigiMarketingController.get_sync_log(campaign_id, device_id, limit)
    return jsonify(result)


@app.route('/api/digi/delivery-report', methods=['GET'])
def api_digi_delivery_report():
    campaign_id = request.args.get('campaign_id', None)
    result = DigiMarketingController.get_delivery_report(campaign_id)
    return jsonify(result)


# --- Reference data ---
@app.route('/api/digi/ref/department-types', methods=['GET'])
def api_digi_department_types():
    return jsonify(DigiMarketingController.get_department_types())


@app.route('/api/digi/ref/device-types', methods=['GET'])
def api_digi_device_types():
    return jsonify(DigiMarketingController.get_device_types())


@app.route('/api/digi/ref/resolutions', methods=['GET'])
def api_digi_resolutions():
    return jsonify(DigiMarketingController.get_resolutions())


@app.route('/api/digi/ref/roles', methods=['GET'])
def api_digi_roles():
    return jsonify(DigiMarketingController.get_roles())


# WebSocket Events
@socketio.on('connect')
def handle_connect():
    """Обработка подключения WebSocket"""
    if not AuthController.is_authenticated():
        emit('error', {'message': 'Authentication required'})
        return False
    emit('connected', {'message': 'Connected to server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Обработка отключения WebSocket"""
    # Удаляем все подписки пользователя
    sid = request.sid
    for metric in list(active_subscriptions.keys()):
        if sid in active_subscriptions[metric]:
            active_subscriptions[metric].remove(sid)
            if not active_subscriptions[metric]:
                del active_subscriptions[metric]


@socketio.on('subscribe_metric')
def handle_subscribe_metric(data):
    """Подписка на обновление конкретной метрики"""
    if not AuthController.is_authenticated():
        emit('error', {'message': 'Authentication required'})
        return
    
    metric_name = data.get('metric')
    if not metric_name:
        emit('error', {'message': 'Metric name required'})
        return
    
    sid = request.sid
    
    # Добавляем подписку
    if metric_name not in active_subscriptions:
        active_subscriptions[metric_name] = []
    
    if sid not in active_subscriptions[metric_name]:
        active_subscriptions[metric_name].append(sid)
    
    # Отправляем начальные данные
    result = DashboardController.get_metric(metric_name)
    emit('metric_update', result)


@socketio.on('unsubscribe_metric')
def handle_unsubscribe_metric(data):
    """Отписка от обновления метрики"""
    metric_name = data.get('metric')
    sid = request.sid
    
    if metric_name in active_subscriptions and sid in active_subscriptions[metric_name]:
        active_subscriptions[metric_name].remove(sid)
        if not active_subscriptions[metric_name]:
            del active_subscriptions[metric_name]


def background_metric_updater():
    """Фоновая задача для обновления метрик через WebSocket"""
    while True:
        try:
            time.sleep(Config.DASHBOARD_UPDATE_INTERVAL)
            
            # Обновляем каждую подписанную метрику
            for metric_name in list(active_subscriptions.keys()):
                if active_subscriptions[metric_name]:
                    try:
                        result = DashboardController.get_metric(metric_name)
                        # Отправляем обновление всем подписчикам
                        for sid in active_subscriptions[metric_name]:
                            socketio.emit('metric_update', result, room=sid)
                    except Exception as e:
                        print(f"Error updating metric {metric_name}: {e}")
        except Exception as e:
            print(f"Error in background updater: {e}")
            time.sleep(5)


@app.route('/api/ai-generate-table', methods=['POST'])
def api_ai_generate_table():
    """API endpoint для генерации SQL скрипта создания таблицы через ИИ"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        # Пытаемся использовать основной ai_helper, если не получается - используем серверный
        try:
            from ai_helper import generate_table_sql, is_ai_available
        except ImportError:
            # На сервере может не быть ai_helper, используем серверный вариант
            try:
                from ai_helper_server import generate_table_sql, is_ai_available
            except ImportError:
                return jsonify({
                    "success": False,
                    "error": "AI helper module not found"
                }), 500
        
        data = request.get_json()
        description = data.get('description', '').strip()
        use_ai = data.get('use_ai', True)
        
        if not description:
            return jsonify({
                "success": False,
                "error": "Описание таблицы не может быть пустым"
            }), 400
        
        # Генерируем SQL
        result = generate_table_sql(description, use_ai=use_ai and is_ai_available())
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/combo-scenario/execute', methods=['POST'])
def api_combo_scenario_execute():
    """API endpoint для выполнения комбинированного сценария AI -> SQL"""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Invalid JSON in request body"}), 400
        
        main_task = data.get('main_task', '').strip()
        iterations_count = data.get('iterations_count', 1)
        iterative_task = data.get('iterative_task', '').strip()
        
        if not main_task:
            return jsonify({"success": False, "error": "Главное задание не может быть пустым"}), 400
        
        if iterations_count < 1:
            return jsonify({"success": False, "error": "Количество итераций должно быть больше 0"}), 400
        
        # Функция для генерации SQL через AI
        def ai_generate_func(description: str):
            try:
                from ai_helper import generate_table_sql, is_ai_available
            except ImportError:
                from ai_helper_server import generate_table_sql, is_ai_available
            
            return generate_table_sql(description, use_ai=is_ai_available())
        
        # Выполняем сценарий
        result = ComboScenarioController.execute_scenario(
            main_task=main_task,
            iterations_count=iterations_count,
            iterative_task=iterative_task,
            ai_generate_func=ai_generate_func
        )
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": error_trace
        }), 500


@app.route('/api/combo-scenario/execute-iteration', methods=['POST'])
def api_combo_scenario_execute_iteration():
    """API endpoint для выполнения одной итерации комбинированного сценария"""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Invalid JSON in request body"}), 400
        
        main_task = data.get('main_task', '').strip()
        iterations_count = data.get('iterations_count', 1)
        iterative_task = data.get('iterative_task', '').strip()
        current_iteration = data.get('current_iteration', 1)
        previous_iterations = data.get('previous_iterations', [])
        
        if not main_task:
            return jsonify({"success": False, "error": "Главное задание не может быть пустым"}), 400
        
        # Функция для генерации SQL через AI
        def ai_generate_func(description: str):
            try:
                from ai_helper import generate_table_sql, is_ai_available
            except ImportError:
                from ai_helper_server import generate_table_sql, is_ai_available
            
            return generate_table_sql(description, use_ai=is_ai_available())
        
        # Выполняем одну итерацию
        result = ComboScenarioController.execute_single_iteration_step(
            main_task=main_task,
            iterations_count=iterations_count,
            iterative_task=iterative_task,
            current_iteration=current_iteration,
            previous_iterations=previous_iterations,
            ai_generate_func=ai_generate_func
        )
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": error_trace
        }), 500


@app.route('/api/dashboard/documentation/<dashboard_id>', methods=['GET'])
def api_dashboard_documentation(dashboard_id):
    """API endpoint для получения документации по дашборду"""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(DocumentationController.get_dashboard_documentation(dashboard_id))


@app.route('/api/dashboard/ddl/<dashboard_id>', methods=['GET'])
def api_dashboard_ddl(dashboard_id):
    """API endpoint для генерации DDL скрипта для дашборда"""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    result = DocumentationController.get_ddl_script(dashboard_id)
    return jsonify(result)


@app.route('/api/dashboard/dml/<dashboard_id>', methods=['GET'])
def api_dashboard_dml(dashboard_id):
    """API endpoint для генерации DML скрипта (демо-данные) для дашборда"""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    result = DocumentationController.get_dml_script(dashboard_id)
    return jsonify(result)


@app.route('/api/dashboard/documentation/list', methods=['GET'])
def api_dashboard_documentation_list():
    """API endpoint для получения списка всех дашбордов"""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(DocumentationController.get_all_dashboards_list())


@app.route('/api/credit-admin/programs', methods=['GET'])
def api_credit_admin_programs():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    bank = request.args.get('bank') or None
    term = request.args.get('term', type=int) or None
    active = request.args.get('active') or None
    result = CreditController.get_programs(bank=bank, term=term, active=active)
    return jsonify(result)


@app.route('/api/credit-admin/programs/<int:program_id>', methods=['GET'])
def api_credit_admin_program_get(program_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    try:
        result = CreditController.get_program_by_id(program_id)
        return jsonify(result)
    except Exception as e:
        import traceback
        print(f"Error in api_credit_admin_program_get: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e), "data": None}), 500


@app.route('/api/credit-admin/programs', methods=['POST'])
def api_credit_admin_programs_post():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    return jsonify(CreditController.upsert_program(data))


@app.route('/api/credit-admin/programs/<int:program_id>', methods=['DELETE'])
def api_credit_admin_program_delete(program_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.delete_program(program_id))


@app.route('/api/credit-admin/banks', methods=['GET'])
def api_credit_admin_banks():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_banks())


@app.route('/api/credit-admin/categories', methods=['GET'])
def api_credit_admin_categories():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_categories())


@app.route('/api/credit-admin/brands', methods=['GET'])
def api_credit_admin_brands():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_brands())


@app.route('/api/credit-admin/matrix', methods=['GET'])
def api_credit_admin_matrix():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_matrix())


@app.route('/api/credit-admin/matrix', methods=['POST'])
def api_credit_admin_matrix_post():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    pid = data.get('program_id')
    cid = data.get('category_id')
    enabled = bool(data.get('enabled', True))
    if pid is None or cid is None:
        return jsonify({"success": False, "error": "program_id and category_id required"}), 400
    return jsonify(CreditController.set_matrix_row(int(pid), int(cid), enabled))


@app.route('/api/credit-admin/matrix/products', methods=['GET'])
def api_credit_admin_matrix_products():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    pid = request.args.get('program_id', type=int)
    cid = request.args.get('category_id', type=int)
    if pid is None or cid is None:
        return jsonify({"success": False, "error": "program_id and category_id required"}), 400
    search = request.args.get('search') or None
    limit = request.args.get('limit', default=500, type=int)
    return jsonify(CreditController.get_matrix_products(program_id=pid, category_id=cid, search=search, limit=limit))


@app.route('/api/credit-admin/matrix/products', methods=['POST'])
def api_credit_admin_matrix_products_post():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    pid = data.get('program_id')
    cid = data.get('category_id')
    product_ids = data.get('product_ids') or []
    if pid is None or cid is None:
        return jsonify({"success": False, "error": "program_id and category_id required"}), 400
    try:
        ids = [int(x) for x in product_ids if x is not None and str(x).strip() != '']
    except (TypeError, ValueError):
        ids = []
    return jsonify(CreditController.set_matrix_products(program_id=int(pid), category_id=int(cid), product_ids=ids))


@app.route('/api/credit-admin/pivot/meta', methods=['GET'])
def api_credit_admin_pivot_meta():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_pivot_meta())


@app.route('/api/credit-admin/pivot/matrix', methods=['GET'])
def api_credit_admin_pivot_matrix():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_pivot_matrix())


@app.route('/api/credit-admin/pivot/products', methods=['GET'])
def api_credit_admin_pivot_products():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    cids = request.args.get('category_ids')
    category_ids = [int(x) for x in cids.split(',')] if cids else None
    search = request.args.get('search') or None
    limit = request.args.get('limit', default=500, type=int)
    return jsonify(CreditController.get_pivot_products(category_ids=category_ids, search=search, limit=limit))


@app.route('/api/credit-admin/easycredit-settings', methods=['GET'])
def api_credit_admin_easycredit_settings():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    from config import Config
    env = Config.easycredit_env()
    base_url = Config.easycredit_base_url()
    user = Config.easycredit_api_user()
    pwd = Config.easycredit_api_password()
    return jsonify({
        "success": True,
        "data": {
            "env": env,
            "base_url": base_url,
            "api_user": user,
            "api_password_masked": "********" if pwd else "",
        },
    })


@app.route('/api/credit-admin/easycredit-settings', methods=['POST'])
def api_credit_admin_easycredit_settings_post():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    from config import save_easycredit_settings
    data = request.get_json() or {}
    env = (data.get("env") or "sandbox").strip().lower()
    base_url = (data.get("base_url") or "").strip()
    api_user = (data.get("api_user") or "").strip()
    api_password = (data.get("api_password") or "").strip()
    try:
        save_easycredit_settings(env=env, base_url=base_url, api_user=api_user, api_password=api_password)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": True})


@app.route('/api/credit-admin/iute-settings', methods=['GET'])
def api_credit_admin_iute_settings():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    from config import Config
    env = Config.iute_env()
    base_url = Config.iute_base_url()
    api_key = Config.iute_api_key()
    pos_identifier = Config.iute_pos_identifier()
    salesman_identifier = Config.iute_salesman_identifier()
    # Never return real secrets - only masked indicators
    return jsonify({
        "success": True,
        "data": {
            "env": env,
            "base_url": base_url,
            "api_key_masked": bool(api_key),
            "pos_identifier_masked": bool(pos_identifier),
            "salesman_identifier_masked": bool(salesman_identifier),
        },
    })


@app.route('/api/credit-admin/reports', methods=['GET'])
def api_credit_admin_reports():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_reports())


@app.route('/api/credit-admin/reports/<int:report_id>', methods=['GET'])
def api_credit_admin_report_get(report_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_report_by_id(report_id))


@app.route('/api/credit-admin/reports/<int:report_id>/params', methods=['GET'])
def api_credit_admin_report_params(report_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_report_params(report_id))


@app.route('/api/credit-admin/reports/<int:report_id>/template', methods=['PUT', 'POST'])
def api_credit_admin_report_template(report_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    return jsonify(CreditController.update_report_template(
        report_id,
        name=data.get("name"),
        description=data.get("description"),
        template_html=data.get("template_html"),
    ))


@app.route('/api/credit-admin/reports/<int:report_id>/execute', methods=['POST'])
def api_credit_admin_report_execute(report_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    params = data.get("params") or data
    return jsonify(CreditController.execute_report(report_id, params))


@app.route('/api/credit-admin/reports/<int:report_id>/export', methods=['POST'])
def api_credit_admin_report_export(report_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    params = data.get("params") or data
    fmt = (data.get("format") or "csv").lower()
    report_name = data.get("report_name") or "Report"
    result = CreditController.execute_report(report_id, params)
    if not result.get("success"):
        return jsonify(result), 400
    rows = result.get("data") or []
    cols = list(rows[0].keys()) if rows else []
    try:
        from services.report_export import export_csv, export_excel, export_pdf
        if fmt == "csv":
            content = export_csv(rows, cols)
            from flask import Response
            return Response(content, mimetype="text/csv; charset=utf-8",
                           headers={"Content-Disposition": f"attachment; filename={report_name}.csv"})
        if fmt == "excel" or fmt == "xlsx":
            content = export_excel(rows, report_name, cols)
            from flask import Response
            return Response(content, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           headers={"Content-Disposition": f"attachment; filename={report_name}.xlsx"})
        if fmt == "pdf":
            content = export_pdf(rows, report_name, cols)
            from flask import Response
            return Response(content, mimetype="application/pdf",
                           headers={"Content-Disposition": f"attachment; filename={report_name}.pdf"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": False, "error": f"Формат {fmt} не поддерживается"}), 400


@app.route('/api/credit-admin/reports/export-pdf', methods=['POST'])
def api_credit_admin_export_pdf_direct():
    """Экспорт в PDF по переданным данным (без перезапуска отчёта)."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    rows = data.get("data") or data.get("rows") or []
    cols = data.get("columns") or data.get("cols")
    report_name = data.get("report_name") or "Report"
    if not rows:
        return jsonify({"success": False, "error": "Нет данных"}), 400
    if not cols:
        cols = list(rows[0].keys())
    try:
        from services.report_export import export_pdf
        from flask import Response
        content = export_pdf(rows, report_name, cols)
        return Response(content, mimetype="application/pdf",
                       headers={"Content-Disposition": f"attachment; filename={report_name}.pdf"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/credit-admin/iute-settings', methods=['POST'])
def api_credit_admin_iute_settings_post():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    from config import save_iute_settings
    data = request.get_json() or {}
    env = (data.get("env") or "sandbox").strip().lower()
    base_url = (data.get("base_url") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    pos_identifier = (data.get("pos_identifier") or "").strip()
    salesman_identifier = (data.get("salesman_identifier") or "").strip()
    try:
        save_iute_settings(env=env, base_url=base_url, api_key=api_key, pos_identifier=pos_identifier, salesman_identifier=salesman_identifier)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": True})


# ========== Credit Testing — единый API для всех провайдеров ==========

@app.route('/api/credit-testing/providers', methods=['GET'])
def api_credit_testing_providers():
    """Список всех зарегистрированных кредитных провайдеров."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    # Убедимся что провайдеры зарегистрированы
    import integrations  # noqa: F401  — авто-регистрация
    from controllers.credit_testing_controller import CreditTestingController
    return jsonify(CreditTestingController.get_providers())


@app.route('/api/credit-testing/provider/<provider_id>', methods=['GET'])
def api_credit_testing_provider_info(provider_id):
    """Информация о провайдере."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    import integrations  # noqa: F401
    from controllers.credit_testing_controller import CreditTestingController
    return jsonify(CreditTestingController.get_provider_info(provider_id))


@app.route('/api/credit-testing/search-client', methods=['GET'])
def api_credit_testing_search_client():
    """Поиск клиента через провайдер. ?provider=...&uin=...&phone=..."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    import integrations  # noqa: F401
    from controllers.credit_testing_controller import CreditTestingController
    pid = request.args.get('provider', '')
    kwargs = {k: v for k, v in request.args.items() if k != 'provider'}
    _credit_log(f"{pid}.search_client", f"Поиск клиента: {kwargs}", "INFO", kwargs)
    result = CreditTestingController.search_client(pid, **kwargs)
    _credit_log(f"{pid}.search_client", f"Результат: success={result.get('success')}", "INFO" if result.get("success") else "WARN")
    return jsonify(result)


@app.route('/api/credit-testing/preapproved', methods=['POST'])
def api_credit_testing_preapproved():
    """Preapproved через провайдер."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    import integrations  # noqa: F401
    from controllers.credit_testing_controller import CreditTestingController
    data = request.get_json() or {}
    pid = data.pop('provider', '')
    _credit_log(f"{pid}.preapproved", f"Запрос preapproved", "INFO", {k: v for k, v in data.items() if k != 'password'})
    result = CreditTestingController.preapproved(pid, **data)
    _credit_log(f"{pid}.preapproved", f"Результат: success={result.get('success')}", "INFO" if result.get("success") else "WARN")
    return jsonify(result)


@app.route('/api/credit-testing/submit', methods=['POST'])
def api_credit_testing_submit():
    """Отправка заявки через провайдер."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    import integrations  # noqa: F401
    from controllers.credit_testing_controller import CreditTestingController
    data = request.get_json() or {}
    pid = data.pop('provider', '')
    _credit_log(f"{pid}.submit", f"Отправка заявки", "INFO", {k: v for k, v in data.items() if k not in ('password',)})
    result = CreditTestingController.submit(pid, **data)
    level = "INFO" if result.get("success") else "ERROR"
    _credit_log(f"{pid}.submit", f"Результат: {result.get('data', {})}", level)
    return jsonify(result)


@app.route('/api/credit-testing/status', methods=['GET'])
def api_credit_testing_status():
    """Проверка статуса через провайдер. ?provider=...&urn=...&order_id=..."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    import integrations  # noqa: F401
    from controllers.credit_testing_controller import CreditTestingController
    pid = request.args.get('provider', '')
    kwargs = {k: v for k, v in request.args.items() if k != 'provider'}
    _credit_log(f"{pid}.status", f"Проверка статуса: {kwargs}", "INFO")
    result = CreditTestingController.check_status(pid, **kwargs)
    _credit_log(f"{pid}.status", f"Результат: {result.get('data', {})}", "INFO" if result.get("success") else "WARN")
    return jsonify(result)


@app.route('/api/credit-testing/check-auth', methods=['GET'])
def api_credit_testing_check_auth():
    """Проверка авторизации провайдера. ?provider=..."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    import integrations  # noqa: F401
    from controllers.credit_testing_controller import CreditTestingController
    pid = request.args.get('provider', '')
    _credit_log(f"{pid}.check_auth", "Проверка авторизации", "INFO")
    result = CreditTestingController.check_auth(pid)
    _credit_log(f"{pid}.check_auth", f"Результат: success={result.get('success')}", "INFO" if result.get("success") else "WARN")
    return jsonify(result)


@app.route('/api/credit-testing/create-order', methods=['POST'])
def api_credit_testing_create_order():
    """Создание заказа через провайдер."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    import integrations  # noqa: F401
    from controllers.credit_testing_controller import CreditTestingController
    data = request.get_json() or {}
    pid = data.pop('provider', '')
    _credit_log(f"{pid}.create_order", f"Создание заказа", "INFO", data)
    result = CreditTestingController.create_order(pid, **data)
    _credit_log(f"{pid}.create_order", f"Результат: {result.get('data', {})}", "INFO" if result.get("success") else "ERROR")
    return jsonify(result)


@app.route('/api/credit-testing/order-status', methods=['GET'])
def api_credit_testing_order_status():
    """Статус заказа через провайдер. ?provider=...&order_id=..."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    import integrations  # noqa: F401
    from controllers.credit_testing_controller import CreditTestingController
    pid = request.args.get('provider', '')
    kwargs = {k: v for k, v in request.args.items() if k != 'provider'}
    _credit_log(f"{pid}.order_status", f"Проверка заказа: {kwargs}", "INFO")
    result = CreditTestingController.order_status(pid, **kwargs)
    _credit_log(f"{pid}.order_status", f"Результат: {result.get('data', {})}", "INFO" if result.get("success") else "WARN")
    return jsonify(result)


@app.route('/api/credit-logs', methods=['GET'])
def api_credit_logs():
    """Лог EasyCredit и кредитных операций для виджета Output (как SQL Developer)."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    from services.credit_logger import get as log_get
    limit = request.args.get('limit', default=500, type=int)
    since = request.args.get('since') or None
    entries = log_get(limit=min(limit, 2000), since_ts=since)
    return jsonify({"success": True, "data": entries})


@app.route('/api/credit-logs/clear', methods=['POST'])
def api_credit_logs_clear():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    from services.credit_logger import clear as log_clear
    log_clear()
    return jsonify({"success": True})


@app.route('/api/credit-operator/products', methods=['GET'])
def api_credit_operator_products():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    search = request.args.get('search') or None
    barcode = request.args.get('barcode') or None
    limit = request.args.get('limit', default=10, type=int)
    result = CreditController.get_products(search=search, barcode=barcode, limit=limit)
    return jsonify(result)


@app.route('/api/credit-operator/products/<int:product_id>', methods=['GET'])
def api_credit_operator_product_get(product_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_product_by_id(product_id))


@app.route('/api/credit-operator/programs-for-product/<int:product_id>', methods=['GET'])
def api_credit_operator_programs_for_product(product_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(CreditController.get_programs_for_product(product_id))


@app.route('/api/credit-operator/application', methods=['POST'])
def api_credit_operator_application():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    product_id = data.get('product_id')
    program_id = data.get('program_id')
    fio = (data.get('client_fio') or data.get('fio') or "").strip()
    phone = (data.get('client_phone') or data.get('phone') or "").strip()
    idn = (data.get('client_idn') or data.get('idn') or "").strip()
    if not all([product_id, program_id, fio, phone]):
        return jsonify({"success": False, "error": "product_id, program_id, client_fio, client_phone required"}), 400
    _credit_log(
        "credit.operator.application",
        f"Заявка product_id={product_id} program_id={program_id} fio={fio!r}",
        "INFO",
        {"product_id": product_id, "program_id": program_id},
    )
    out = CreditController.create_application(int(product_id), int(program_id), fio, phone, idn)
    if out.get("success"):
        app_id = out.get("application_id") or out.get("id") or "—"
        _credit_log("credit.operator.application", f"OK application_id={app_id}", "INFO", out)
    else:
        _credit_log("credit.operator.application", f"Ошибка: {out.get('error', '')}", "ERROR", out)
    return jsonify(out)


@app.route('/api/credit-operator/recent-applications', methods=['GET'])
def api_credit_operator_recent():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    limit = request.args.get('limit', default=5, type=int)
    return jsonify(CreditController.get_recent_applications(limit=limit))


# ---------- Nufarul: админка ----------
@app.route('/api/nufarul-admin/services', methods=['GET'])
def api_nufarul_admin_services():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(NufarulController.get_services(active_only=False))


@app.route('/api/nufarul-admin/services', methods=['POST'])
def api_nufarul_admin_services_post():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    return jsonify(NufarulController.upsert_service(data))


@app.route('/api/nufarul-admin/services/<int:service_id>', methods=['GET'])
def api_nufarul_admin_service_get(service_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(NufarulController.get_service_by_id(service_id))


@app.route('/api/nufarul-admin/services/<int:service_id>', methods=['DELETE'])
def api_nufarul_admin_service_delete(service_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(NufarulController.delete_service(service_id))


@app.route('/api/nufarul-admin/statuses', methods=['GET'])
def api_nufarul_admin_statuses():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(NufarulController.get_statuses())


@app.route('/api/nufarul-admin/orders', methods=['GET'])
def api_nufarul_admin_orders():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    status_id = request.args.get('status_id', type=int) or None
    date_from = request.args.get('date_from') or None
    date_to = request.args.get('date_to') or None
    search = request.args.get('search') or None
    limit = request.args.get('limit', default=200, type=int)
    return jsonify(NufarulController.get_orders(status_id=status_id, date_from=date_from, date_to=date_to, search=search, limit=limit))


@app.route('/api/nufarul-admin/orders/<int:order_id>/status', methods=['PUT', 'POST'])
def api_nufarul_admin_order_status(order_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    status_id = data.get('status_id') or data.get('statusId')
    if status_id is None:
        return jsonify({"success": False, "error": "status_id required"}), 400
    return jsonify(NufarulController.update_order_status(order_id, int(status_id)))


@app.route('/api/nufarul-admin/report-by-day', methods=['GET'])
def api_nufarul_admin_report_by_day():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    date_from = request.args.get('date_from') or None
    date_to = request.args.get('date_to') or None
    return jsonify(NufarulController.report_orders_by_day(date_from=date_from, date_to=date_to))


# ---------- Nufarul: оператор ----------
@app.route('/api/nufarul-operator/services', methods=['GET'])
def api_nufarul_operator_services():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(NufarulController.get_services(active_only=True))


@app.route('/api/nufarul-operator/order', methods=['POST'])
def api_nufarul_operator_order():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    client_name = (data.get('client_name') or "").strip()
    client_phone = (data.get('client_phone') or "").strip()
    items = data.get('items') or []
    notes = (data.get('notes') or "").strip() or None
    if not client_name or not client_phone:
        return jsonify({"success": False, "error": "client_name and client_phone required"}), 400
    if not items:
        return jsonify({"success": False, "error": "items required"}), 400
    return jsonify(NufarulController.create_order(client_name, client_phone, items, notes))


@app.route('/api/nufarul-operator/recent-orders', methods=['GET'])
def api_nufarul_operator_recent_orders():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    limit = request.args.get('limit', default=20, type=int)
    return jsonify(NufarulController.get_recent_orders(limit=limit))


@app.route('/api/nufarul-operator/order-by-barcode', methods=['GET'])
def api_nufarul_operator_order_by_barcode():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    barcode = request.args.get('barcode') or ""
    return jsonify(NufarulController.get_order_by_barcode(barcode))


@app.route('/UNA.md/orasldev/nufarul-operator/document/jurnal')
def nufarul_operator_document_jurnal():
    """Журнал регистраций заказов (Jurnal Registru): последние заказы таблицей."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    limit = min(int(request.args.get('limit', 50)), 200)
    result = NufarulController.get_recent_orders(limit=limit)
    if not result.get('success'):
        return f"<h1>Ошибка</h1><p>{result.get('error', '')}</p>", 500
    orders = result.get('data') or []
    entries = []
    for i, o in enumerate(orders, start=1):
        created_time = o.get('created_time')
        if not created_time and o.get('created_at'):
            ct = o['created_at']
            created_time = ct.strftime('%Y-%m-%d %H:%M') if hasattr(ct, 'strftime') else str(ct)[:16]
        entries.append({
            "row_num": i,
            "order_number": o.get('order_number') or '—',
            "client_name": o.get('client_name') or '—',
            "client_phone": o.get('client_phone') or '',
            "total_amount": o.get('total_amount') or 0,
            "created_time": created_time or '—',
        })
    from datetime import datetime
    period_label = f"Ultimele {len(entries)} comenzi / Последние {len(entries)} заказов (generat {datetime.now().strftime('%d.%m.%Y %H:%M')})"
    return render_template(
        "nufarul/document_jurnal_registru.html",
        entries=entries,
        period_label=period_label,
    )


@app.route('/UNA.md/orasldev/nufarul-operator/document/<int:order_id>')
def nufarul_operator_document(order_id):
    """Печать первичного документа по заказу: Bon de Comandă или Comandă (type=bon_comanda|comanda)."""
    if not AuthController.is_authenticated():
        return _login_redirect()
    doc_type = request.args.get('type', 'bon_comanda').strip().lower()
    if doc_type not in ('bon_comanda', 'comanda'):
        doc_type = 'bon_comanda'
    result = NufarulController.get_order_by_id(order_id)
    if not result.get('success') or not result.get('data'):
        return f"<h1>Заказ не найден</h1><p>Order ID: {order_id}</p><p><a href='/UNA.md/orasldev/nufarul-operator'>← Оператор</a></p>", 404
    order = result["data"]
    created_at = order.get('created_at')
    if hasattr(created_at, 'strftime'):
        created_at = created_at.strftime('%d.%m.%Y %H:%M')
    else:
        created_at = str(created_at)[:16] if created_at else '—'
    template_name = f"nufarul/document_{doc_type}.html"
    return render_template(
        template_name,
        order_number=order.get('order_number') or '—',
        barcode=order.get('barcode') or order.get('order_number'),
        client_name=order.get('client_name') or '—',
        client_phone=order.get('client_phone') or '',
        created_at=created_at,
        notes=order.get('notes') or '',
        items=order.get('items') or [],
        total_amount=order.get('total_amount') or 0,
    )


def _easycredit_mock_preapproved(amount: int, idn: str):
    return {
        "success": True,
        "data": {
            "preapproved": True,
            "max_amount": max(int(amount or 10000) * 2, 50000),
            "message": "Mock: предодобрение (тест).",
        },
        "fallback": True,
    }


def _easycredit_mock_submit(fio: str, phone: str):
    import uuid
    urn = f"EC-MOCK-{uuid.uuid4().hex[:12].upper()}"
    return {
        "success": True,
        "data": {"urn": urn, "message": "Mock: заявка (тест)."},
        "fallback": True,
    }


def _easycredit_mock_status(urn: str):
    return {
        "success": True,
        "data": {"urn": urn, "status": "Approved", "message": "Mock: статус (тест)."},
        "fallback": True,
    }


def _credit_log(source: str, message: str, level: str = "INFO", payload: dict = None):
    try:
        from services.credit_logger import append as _append
        _append(source, message, level=level, payload=payload or {})
    except Exception:
        pass


@app.route('/api/credit-easycredit/preapproved', methods=['POST'])
def api_credit_easycredit_preapproved():
    """Preapproved (EasyCredit): проверка предодобренной суммы. Реальный EC при user+pass."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    amount = int(data.get("amount") or 10000)
    idn = (data.get("idn") or "12345678901234").strip()
    idn_masked = ("***" + idn[-4:]) if len(idn) >= 4 else "***"
    _credit_log("easycredit.preapproved", f"Запрос Preapproved amount={amount} idn={idn_masked}", "INFO", {"amount": amount, "idn_masked": idn_masked})
    base_url = Config.easycredit_base_url()
    user = Config.easycredit_api_user()
    passwd = Config.easycredit_api_password()
    if user and passwd:
        try:
            from integrations.easycredit_client import preapproved as ec_preapproved
            verify_ssl = Config.easycredit_env() == "production"
            out = ec_preapproved(base_url, user, passwd, idn=idn, amount=amount, verify_ssl=verify_ssl)
            if out.get("success"):
                d = out["data"] or {}
                _credit_log("easycredit.preapproved", f"OK preapproved={d.get('preapproved')} max_amount={d.get('max_amount')} {d.get('message', '')}", "INFO", d)
                return jsonify({"success": True, "data": out["data"]})
            err = out.get("error") or out.get("data", {}).get("message") or "unknown"
            _credit_log("easycredit.preapproved", f"EC error, fallback to mock: {err}", "WARN", out)
            return jsonify(_easycredit_mock_preapproved(amount, idn))
        except Exception as e:
            _credit_log("easycredit.preapproved", f"Exception, fallback to mock: {e}", "ERROR", {"error": str(e)})
            return jsonify(_easycredit_mock_preapproved(amount, idn))
    _credit_log("easycredit.preapproved", "Нет user/pass, mock", "INFO", {})
    return jsonify(_easycredit_mock_preapproved(amount, idn))


@app.route('/api/credit-easycredit/submit', methods=['POST'])
def api_credit_easycredit_submit():
    """Request (EasyCredit): отправка заявки. Реальный EC при user+pass."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    product_id = data.get("product_id")
    program_id = data.get("program_id")
    try:
        pid = int(product_id) if product_id is not None else None
    except (TypeError, ValueError):
        pid = None
    try:
        prid = int(program_id) if program_id is not None else None
    except (TypeError, ValueError):
        prid = None
    amount = int(data.get("amount") or 10000)
    fio = (data.get("fio") or "Тест Тестович Тестов").strip()
    phone = (data.get("phone") or "+37369123456").strip()
    idn = (data.get("idn") or "12345678901234").strip()
    product_name = (data.get("product_name") or "").strip()
    program_name = (data.get("program_name") or "").strip()
    if not product_name and pid:
        pr = CreditController.get_product_by_id(pid)
        if pr.get("success") and pr.get("data"):
            product_name = (pr["data"].get("name") or "Тестовый товар").strip()
    if not product_name:
        product_name = "Тестовый товар"
    if not program_name and prid and pid:
        prog = CreditController.get_programs_for_product(pid)
        if prog.get("success") and prog.get("data"):
            for p in prog["data"]:
                if (p.get("program_id") or p.get("id")) == prid:
                    program_name = (p.get("program_name") or p.get("name") or "0-0-12").strip()
                    break
    if not program_name:
        program_name = "0-0-12"
    _credit_log("easycredit.submit", f"Запрос Submit amount={amount} fio={fio!r} product={product_name!r} program={program_name!r}", "INFO", {"amount": amount, "product_name": product_name, "program_name": program_name})
    base_url = Config.easycredit_base_url()
    user = Config.easycredit_api_user()
    passwd = Config.easycredit_api_password()
    if user and passwd:
        try:
            from integrations.easycredit_client import submit_request as ec_submit
            verify_ssl = Config.easycredit_env() == "production"
            out = ec_submit(
                base_url, user, passwd,
                amount=amount, fio=fio, phone=phone, idn=idn,
                product_name=product_name, program_name=program_name,
                verify_ssl=verify_ssl,
            )
            if out.get("success") and out.get("data", {}).get("urn"):
                urn = out["data"]["urn"]
                _credit_log("easycredit.submit", f"OK urn={urn}", "INFO", {"urn": urn})
                return jsonify({"success": True, "data": out["data"]})
            err = out.get("error") or (out.get("data") or {}).get("message") or "unknown"
            _credit_log("easycredit.submit", f"EC error, fallback to mock: {err}", "WARN", out)
            return jsonify(_easycredit_mock_submit(fio, phone))
        except Exception as e:
            _credit_log("easycredit.submit", f"Exception, fallback to mock: {e}", "ERROR", {"error": str(e)})
            return jsonify(_easycredit_mock_submit(fio, phone))
    _credit_log("easycredit.submit", "Нет user/pass, mock", "INFO", {})
    return jsonify(_easycredit_mock_submit(fio, phone))


@app.route('/api/credit-easycredit/status', methods=['GET'])
def api_credit_easycredit_status():
    """Status (EasyCredit): статус заявки по URN. Реальный EC при user+pass."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    urn = (request.args.get("urn") or "").strip()
    if not urn:
        return jsonify({"success": False, "error": "urn required"}), 400
    _credit_log("easycredit.status", f"Запрос Status urn={urn}", "INFO", {"urn": urn})
    base_url = Config.easycredit_base_url()
    user = Config.easycredit_api_user()
    passwd = Config.easycredit_api_password()
    if user and passwd:
        try:
            from integrations.easycredit_client import status as ec_status
            verify_ssl = Config.easycredit_env() == "production"
            out = ec_status(base_url, user, passwd, urn, verify_ssl=verify_ssl)
            if out.get("success"):
                d = out.get("data") or {}
                st = d.get("status") or ""
                _credit_log("easycredit.status", f"OK status={st}", "INFO", d)
                return jsonify({"success": True, "data": out["data"]})
            err = out.get("error") or (out.get("data") or {}).get("message") or "unknown"
            _credit_log("easycredit.status", f"EC error, fallback to mock: {err}", "WARN", out)
            return jsonify(_easycredit_mock_status(urn))
        except Exception as e:
            _credit_log("easycredit.status", f"Exception, fallback to mock: {e}", "ERROR", {"error": str(e)})
            return jsonify(_easycredit_mock_status(urn))
    _credit_log("easycredit.status", "Нет user/pass, mock", "INFO", {})
    return jsonify(_easycredit_mock_status(urn))


@app.route('/api/credit-easycredit/client-by-phone', methods=['GET'])
def api_credit_easycredit_client_by_phone():
    """Получить информацию о клиенте по телефону (EasyCredit ECM_GetClientInfoByPhone)."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    phone = (request.args.get("phone") or "").strip()
    if not phone:
        return jsonify({"success": False, "error": "phone required"}), 400
    _credit_log("easycredit.client-by-phone", f"Запрос по телефону {phone[:4]}***", "INFO", {"phone_prefix": phone[:4]})
    base_url = Config.easycredit_base_url()
    user = Config.easycredit_api_user()
    passwd = Config.easycredit_api_password()
    if user and passwd:
        try:
            from integrations.easycredit_client import get_client_info_by_phone
            verify_ssl = Config.easycredit_env() == "production"
            out = get_client_info_by_phone(base_url, user, passwd, phone, verify_ssl=verify_ssl)
            if out.get("success"):
                _credit_log("easycredit.client-by-phone", f"OK", "INFO", out.get("data", {}))
                return jsonify(out)
            err = out.get("error") or "unknown"
            _credit_log("easycredit.client-by-phone", f"EC error: {err}", "WARN", out)
            return jsonify(out)
        except Exception as e:
            _credit_log("easycredit.client-by-phone", f"Exception: {e}", "ERROR", {"error": str(e)})
            return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": False, "error": "Нет user/pass"}), 400


@app.route('/api/credit-easycredit/client-by-uin', methods=['GET'])
def api_credit_easycredit_client_by_uin():
    """Получить информацию о клиенте по UIN (IDNP) (EasyCredit eShopClientInfo_v3)."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    uin = (request.args.get("uin") or "").strip()
    if not uin:
        return jsonify({"success": False, "error": "uin required"}), 400
    uin_masked = ("***" + uin[-4:]) if len(uin) >= 4 else "***"
    _credit_log("easycredit.client-by-uin", f"Запрос по UIN {uin_masked}", "INFO", {"uin_masked": uin_masked})
    base_url = Config.easycredit_base_url()
    user = Config.easycredit_api_user()
    passwd = Config.easycredit_api_password()
    if user and passwd:
        try:
            from integrations.easycredit_client import get_client_info
            verify_ssl = Config.easycredit_env() == "production"
            out = get_client_info(base_url, user, passwd, uin, verify_ssl=verify_ssl)
            if out.get("success"):
                _credit_log("easycredit.client-by-uin", f"OK", "INFO", out.get("data", {}))
                return jsonify(out)
            err = out.get("error") or "unknown"
            _credit_log("easycredit.client-by-uin", f"EC error: {err}", "WARN", out)
            return jsonify(out)
        except Exception as e:
            _credit_log("easycredit.client-by-uin", f"Exception: {e}", "ERROR", {"error": str(e)})
            return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": False, "error": "Нет user/pass"}), 400


@app.route('/api/credit-easycredit/urns', methods=['GET'])
def api_credit_easycredit_urns():
    """Получить список заявок (URN) клиента по UIN (EasyCredit ECM_GetUrnPerUin_V2)."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    uin = (request.args.get("uin") or "").strip()
    if not uin:
        return jsonify({"success": False, "error": "uin required"}), 400
    uin_masked = ("***" + uin[-4:]) if len(uin) >= 4 else "***"
    group = request.args.get("group") or ""
    status_filter = request.args.get("status") or ""
    mode = request.args.get("mode") or ""
    _credit_log("easycredit.urns", f"Запрос URNs по UIN {uin_masked}", "INFO", {"uin_masked": uin_masked, "group": group, "status": status_filter, "mode": mode})
    base_url = Config.easycredit_base_url()
    user = Config.easycredit_api_user()
    passwd = Config.easycredit_api_password()
    if user and passwd:
        try:
            from integrations.easycredit_client import get_urns_per_uin
            verify_ssl = Config.easycredit_env() == "production"
            out = get_urns_per_uin(base_url, user, passwd, uin, group=group, status_filter=status_filter, mode=mode, verify_ssl=verify_ssl)
            if out.get("success"):
                _credit_log("easycredit.urns", f"OK", "INFO", out.get("data", {}))
                return jsonify(out)
            err = out.get("error") or "unknown"
            _credit_log("easycredit.urns", f"EC error: {err}", "WARN", out)
            return jsonify(out)
        except Exception as e:
            _credit_log("easycredit.urns", f"Exception: {e}", "ERROR", {"error": str(e)})
            return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": False, "error": "Нет user/pass"}), 400


@app.route('/api/credit-easycredit/test-submit', methods=['POST'])
def api_credit_easycredit_test_submit():
    """Тестовая заявка (EasyCredit): отправка заявки с тестовыми данными."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    # Тестовые данные клиента
    uin = data.get("uin") or "2000000000001"
    fio = data.get("fio") or "Тестов Тест Тестович"
    phone = data.get("phone") or "+37369000001"
    amount = int(data.get("amount") or 15000)
    goods_name = data.get("goods_name") or "Тестовый товар"
    goods_price = int(data.get("goods_price") or amount)
    
    uin_masked = ("***" + uin[-4:]) if len(uin) >= 4 else "***"
    _credit_log("easycredit.test-submit", f"Тестовая заявка UIN={uin_masked} FIO={fio} amount={amount}", "INFO", {
        "uin_masked": uin_masked, "fio": fio, "phone": phone[:6] + "***", "amount": amount, "goods_name": goods_name
    })
    
    base_url = Config.easycredit_base_url()
    user = Config.easycredit_api_user()
    passwd = Config.easycredit_api_password()
    if user and passwd:
        try:
            from integrations.easycredit_client import submit_request
            verify_ssl = Config.easycredit_env() == "production"
            out = submit_request(
                base_url, user, passwd,
                amount=amount, fio=fio, phone=phone, idn=uin,
                product_name=goods_name, program_name="Test", product_id=0, goods_price=goods_price,
                verify_ssl=verify_ssl
            )
            if out.get("success"):
                d = out.get("data") or {}
                urn = d.get("urn") or d.get("URN") or ""
                st = d.get("status") or ""
                _credit_log("easycredit.test-submit", f"OK urn={urn} status={st}", "INFO", d)
                return jsonify(out)
            err = out.get("error") or (out.get("data") or {}).get("message") or "unknown"
            _credit_log("easycredit.test-submit", f"EC error: {err}", "WARN", out)
            return jsonify(out)
        except Exception as e:
            _credit_log("easycredit.test-submit", f"Exception: {e}", "ERROR", {"error": str(e)})
            return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": False, "error": "Нет user/pass"}), 400


def _iute_mock_check_auth():
    return {
        "success": True,
        "data": {
            "partnerId": "mock-partner-id",
            "posId": "mock-pos-id",
            "products": [{"name": "Flexi", "description": "Mock product"}],
        },
        "fallback": True,
    }


def _iute_mock_create_order(order_id: str, phone: str):
    return {
        "success": True,
        "data": {
            "status": "PENDING",
            "message": "Mock: заказ создан (тест).",
            "myiuteCustomer": True,
        },
        "fallback": True,
    }


def _iute_mock_order_status(order_id: str):
    return {
        "success": True,
        "data": {
            "orderId": order_id,
            "status": "PENDING",
            "productName": None,
            "loanDuration": None,
        },
        "fallback": True,
    }


@app.route('/api/credit-iute/check-auth', methods=['GET'])
def api_credit_iute_check_auth():
    """Check Auth (Iute): проверка авторизации и получение информации о партнёре."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    _credit_log("iute.check-auth", "Запрос Check Auth", "INFO", {})
    base_url = Config.iute_base_url()
    api_key = Config.iute_api_key()
    if api_key:
        try:
            from integrations.iute_client import check_auth as iute_check_auth
            out = iute_check_auth(base_url, api_key)
            if out.get("success"):
                d = out["data"] or {}
                _credit_log("iute.check-auth", f"OK partnerId={d.get('partnerId')} posId={d.get('posId')}", "INFO", d)
                return jsonify({"success": True, "data": out["data"]})
            err = out.get("error") or "unknown"
            _credit_log("iute.check-auth", f"Iute error, fallback to mock: {err}", "WARN", out)
            return jsonify(_iute_mock_check_auth())
        except Exception as e:
            _credit_log("iute.check-auth", f"Exception, fallback to mock: {e}", "ERROR", {"error": str(e)})
            return jsonify(_iute_mock_check_auth())
    _credit_log("iute.check-auth", "Нет API key, mock", "INFO", {})
    return jsonify(_iute_mock_check_auth())


@app.route('/api/credit-iute/create-order', methods=['POST'])
def api_credit_iute_create_order():
    """Create Order (Iute): создание или обновление заказа."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json() or {}
    order_id = (data.get("order_id") or f"order-{int(__import__('time').time() * 1000)}").strip()
    myiute_phone = (data.get("myiute_phone") or "+37369123456").strip()
    total_amount = int(data.get("total_amount") or 1000)
    currency = (data.get("currency") or "EUR").strip()
    pos_identifier = Config.iute_pos_identifier()
    salesman_identifier = Config.iute_salesman_identifier()
    user_pin = (data.get("user_pin") or "").strip() or None
    birthday = (data.get("birthday") or "").strip() or None
    gender = (data.get("gender") or "").strip() or None
    items = data.get("items") or []
    if not items and data.get("product_id"):
        # Попытка получить информацию о товаре
        try:
            pid = int(data.get("product_id"))
            pr = CreditController.get_product_by_id(pid)
            if pr.get("success") and pr.get("data"):
                product_name = pr["data"].get("name") or "Товар"
                product_price = pr["data"].get("price") or total_amount
                items = [{
                    "displayName": product_name,
                    "id": str(pid),
                    "sku": None,
                    "unitPrice": product_price,
                    "qty": 1,
                    "itemImageUrl": None,
                    "itemUrl": None,
                }]
        except Exception:
            pass
    _credit_log("iute.create-order", f"Запрос Create Order order_id={order_id} phone={myiute_phone} amount={total_amount} currency={currency}", "INFO", {"order_id": order_id, "myiute_phone": myiute_phone, "total_amount": total_amount, "currency": currency})
    base_url = Config.iute_base_url()
    api_key = Config.iute_api_key()
    if api_key and pos_identifier and salesman_identifier:
        try:
            from integrations.iute_client import create_order as iute_create_order
            out = iute_create_order(
                base_url, api_key,
                order_id=order_id,
                myiute_phone=myiute_phone,
                total_amount=total_amount,
                currency=currency,
                pos_identifier=pos_identifier,
                salesman_identifier=salesman_identifier,
                user_pin=user_pin,
                birthday=birthday,
                gender=gender,
                items=items,
            )
            if out.get("success"):
                d = out["data"] or {}
                status = d.get("status", "PENDING")
                _credit_log("iute.create-order", f"OK order_id={order_id} status={status} customer={d.get('myiuteCustomer')}", "INFO", d)
                return jsonify({"success": True, "data": out["data"]})
            err = out.get("error") or (out.get("data") or {}).get("message") or "unknown"
            _credit_log("iute.create-order", f"Iute error, fallback to mock: {err}", "WARN", out)
            return jsonify(_iute_mock_create_order(order_id, myiute_phone))
        except Exception as e:
            _credit_log("iute.create-order", f"Exception, fallback to mock: {e}", "ERROR", {"error": str(e)})
            return jsonify(_iute_mock_create_order(order_id, myiute_phone))
    _credit_log("iute.create-order", "Нет API key/POS/Salesman, mock", "INFO", {})
    return jsonify(_iute_mock_create_order(order_id, myiute_phone))


@app.route('/api/credit-iute/order-status', methods=['GET'])
def api_credit_iute_order_status():
    """Order Status (Iute): проверка статуса заказа."""
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    order_id = (request.args.get("order_id") or "").strip()
    if not order_id:
        return jsonify({"success": False, "error": "order_id required"}), 400
    _credit_log("iute.order-status", f"Запрос Order Status order_id={order_id}", "INFO", {"order_id": order_id})
    base_url = Config.iute_base_url()
    api_key = Config.iute_api_key()
    if api_key:
        try:
            from integrations.iute_client import get_order_status as iute_get_status
            out = iute_get_status(base_url, api_key, order_id)
            if out.get("success"):
                d = out["data"] or {}
                status = d.get("status", "")
                _credit_log("iute.order-status", f"OK order_id={order_id} status={status}", "INFO", d)
                return jsonify({"success": True, "data": out["data"]})
            err = out.get("error") or "unknown"
            _credit_log("iute.order-status", f"Iute error, fallback to mock: {err}", "WARN", out)
            return jsonify(_iute_mock_order_status(order_id))
        except Exception as e:
            _credit_log("iute.order-status", f"Exception, fallback to mock: {e}", "ERROR", {"error": str(e)})
            return jsonify(_iute_mock_order_status(order_id))
    _credit_log("iute.order-status", "Нет API key, mock", "INFO", {})
    return jsonify(_iute_mock_order_status(order_id))


@app.route('/api/ai-status', methods=['GET'])
def api_ai_status():
    """API endpoint для проверки доступности ИИ"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        # Пытаемся использовать основной ai_helper, если не получается - используем серверный
        is_server = False
        ai_available = False
        
        try:
            from ai_helper import is_ai_available, IS_SERVER
            is_server = IS_SERVER
            ai_available = is_ai_available()
        except ImportError:
            # На сервере может не быть ai_helper, используем серверный вариант
            try:
                from ai_helper_server import is_ai_available
                is_server = True
                ai_available = is_ai_available()  # Всегда False для сервера
            except ImportError:
                return jsonify({
                    "success": False,
                    "error": "AI helper module not found"
                }), 500
        
        return jsonify({
            "success": True,
            "ai_available": ai_available,
            "is_server": is_server
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/set-language', methods=['POST'])
def set_language():
    """Устанавливает язык интерфейса"""
    data = request.get_json()
    language = data.get('lang', 'ru')
    
    if language in Config.SUPPORTED_LANGUAGES:
        session['language'] = language
        return jsonify({"success": True, "language": language})
    else:
        return jsonify({"success": False, "error": "Unsupported language"}), 400


@app.route('/api/get-language', methods=['GET'])
def get_language():
    """Получает текущий язык интерфейса"""
    current_lang = session.get('language', Config.BABEL_DEFAULT_LOCALE)
    return jsonify({
        "success": True,
        "language": current_lang,
        "supported_languages": Config.SUPPORTED_LANGUAGES,
        "languages": Config.LANGUAGES
    })


@app.route('/api/restart', methods=['POST'])
def restart_server():
    """Перезапускает сервер"""
    def restart():
        time.sleep(1)
        print("Перезапуск сервера по запросу пользователя...")
        import sys
        import os
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=restart).start()
    return jsonify({"success": True, "message": "Server is restarting..."})


if __name__ == '__main__':
    # Запускаем фоновый поток для обновления метрик
    updater_thread = threading.Thread(target=background_metric_updater, daemon=True)
    updater_thread.start()
    
    # Запускаем приложение с SocketIO
    # Используем параметры из конфигурации (поддерживает локальный и удаленный режимы)
    print(f"🚀 Запуск сервера в режиме: {Config.ENVIRONMENT}")
    
    # Получаем локальный IP адрес для отображения
    local_ip = None
    if Config.IS_LOCAL:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass
    
    print(f"📍 Адрес:")
    print(f"   • Localhost: http://localhost:{Config.SERVER_PORT}")
    if local_ip:
        print(f"   • Локальная сеть: http://{local_ip}:{Config.SERVER_PORT}")
    print(f"")
    print(f"🌐 Dashboard:")
    print(f"   • http://localhost:{Config.SERVER_PORT}/UNA.md/orasldev/dashboard")
    if local_ip:
        print(f"   • http://{local_ip}:{Config.SERVER_PORT}/UNA.md/orasldev/dashboard")
        print(f"   • Fullscreen: http://{local_ip}:{Config.SERVER_PORT}/UNA.md/orasldev/dashboard/01")
    print(f"")
    print(f"📂 Shell (список проектов из UNA_SHELL_PROJECTS):")
    print(f"   • http://localhost:{Config.SERVER_PORT}/una.md/shell/projects")
    if local_ip:
        print(f"   • http://{local_ip}:{Config.SERVER_PORT}/una.md/shell/projects")
    print(f"")
    print(f"📺 DIGI Marketing (управление контентом весов):")
    print(f"   • http://localhost:{Config.SERVER_PORT}/UNA.md/digi-marketing")
    if local_ip:
        print(f"   • http://{local_ip}:{Config.SERVER_PORT}/UNA.md/digi-marketing")
    
    use_reloader = Config.ENVIRONMENT != "REMOTE"
    socketio.run(app, host=Config.SERVER_HOST, port=Config.SERVER_PORT, debug=True, use_reloader=use_reloader, allow_unsafe_werkzeug=True)
