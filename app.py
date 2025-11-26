#!/usr/bin/env python3
"""
Главное приложение Oracle SQL Developer - UNA.md/orasldev
MVC архитектура с WebSockets для реального времени
"""
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
from config import Config
from controllers.auth_controller import AuthController
from controllers.dashboard_controller import DashboardController
from controllers.sql_controller import SQLController
from controllers.objects_controller import ObjectsController
import threading
import time
import os
import sys

# Создание приложения Flask
app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Инициализация SocketIO для WebSockets
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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
            return jsonify({"success": False, "error": "Неверные учетные данные"}), 401
    
    # GET запрос - показываем форму с предзаполненными данными
    return render_template('login.html', 
                         default_username=Config.DEFAULT_USERNAME,
                         default_password=Config.DEFAULT_PASSWORD)


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
        return redirect(url_for('login'))
    return render_template('sqldeveloper_mdi.html', username=AuthController.get_current_user())


@app.route('/UNA.md/orasldev/dashboard')
def dashboard():
    """Dashboard с метриками БД"""
    if not AuthController.is_authenticated():
        return redirect(url_for('login'))
    return render_template('dashboard_mdi.html')


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
    """API endpoint для входа"""
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    
    if AuthController.login(username, password):
        AuthController.set_authenticated(True)
        return jsonify({"success": True})
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
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    data = request.get_json()
    sql_query = data.get('sql', '').strip()
    
    result = SQLController.execute(sql_query)
    return jsonify(result)


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


@app.route('/api/objects/schemas', methods=['GET'])
def api_objects_schemas():
    """API endpoint для получения списка схем"""
    if not AuthController.is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    result = ObjectsController.get_schemas()
    return jsonify(result)


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
    port = int(os.environ.get('PORT', 8000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
