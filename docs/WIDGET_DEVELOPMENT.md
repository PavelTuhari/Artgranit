# Руководство по разработке виджетов

## Обзор

Виджеты - это независимые компоненты дашборда, которые отображают данные или предоставляют функциональность. Каждый виджет имеет свой тип, конфигурацию и логику отображения.

## Архитектура виджетов

Виджеты следуют принципам MVC (Model-View-Controller):

- **Model**: Данные из базы данных или внешних источников
- **View**: HTML/CSS/JavaScript для отображения
- **Controller**: Логика обработки запросов в Python (Flask)

## Типы виджетов

### 1. Metric Widget (Метрика)

Отображает данные из контроллера через метод класса.

**Конфигурация в JSON**:
```json
{
  "widget_id": "instance",
  "title": "Instance Info",
  "metric_name": "instance",
  "class_name": "DatabaseModel",
  "method_name": "get_instance_info",
  "method_parameters": {}
}
```

**Контроллер**:
```python
# В controllers/dashboard_controller.py или models/database.py
@staticmethod
def get_instance_info() -> Dict[str, Any]:
    # Ваша логика получения данных
    return {
        "instance_name": "ORCL",
        "host_name": "server.example.com",
        "version": "19.0.0.0.0"
    }
```

**Рендеринг**:
```javascript
// В templates/dashboard_mdi.html, функция renderMetricHTML
case 'instance':
    html = `
        <div class="metric-card">
            <div class="metric-title">Instance Name</div>
            <div class="metric-value">${escapeHtml(data.instance_name)}</div>
        </div>
    `;
    break;
```

### 2. Embed Widget (Встроенная страница)

Загружает внешний HTML-шаблон через iframe.

**Конфигурация в JSON**:
```json
{
  "widget_id": "credit_admin_embed",
  "title": "Кредиты — Админка",
  "widget_type": "embed",
  "embed_url": "/UNA.md/orasldev/credit-admin"
}
```

**Создание страницы**:
1. Создайте HTML файл в `templates/credit_admin.html`
2. Добавьте маршрут в `app.py`:
```python
@app.route('/UNA.md/orasldev/credit-admin')
def credit_admin():
    if not AuthController.is_authenticated():
        return redirect(url_for('login'))
    return render_template('credit_admin.html')
```

### 3. Custom SQL Widget

Выполняет произвольный SQL-запрос.

**Конфигурация в JSON**:
```json
{
  "widget_id": "custom_sql_oracle",
  "title": "Custom SQL Query",
  "widget_type": "custom_sql",
  "database_type": "oracle",
  "sql_query": "SELECT * FROM DUAL",
  "connection_params": {
    "type": "oracle"
  }
}
```

### 4. Documentation Widget

Отображает документацию дашборда с кнопками для генерации скриптов.

**Конфигурация в JSON**:
```json
{
  "widget_id": "documentation_00",
  "title": "📚 Документация Dashboard",
  "widget_type": "documentation",
  "dashboard_id": "00"
}
```

## Создание нового виджета

### Шаг 1: Определите тип виджета

Выберите подходящий тип:
- **Metric** - если данные из контроллера
- **Embed** - если нужна отдельная HTML-страница
- **Custom SQL** - если нужен произвольный SQL
- **Documentation** - если это документация

### Шаг 2: Создайте метод контроллера (для Metric)

```python
# В controllers/dashboard_controller.py
@staticmethod
def get_my_metric() -> Dict[str, Any]:
    """Получение данных для нового виджета"""
    try:
        from models.database import DatabaseModel
        with DatabaseModel() as db:
            # Ваш SQL-запрос или логика
            result = db.execute_query("SELECT ...")
        
        if result.get("success"):
            # Обработка данных
            return {
                "data": processed_data,
                "status": "ok"
            }
        else:
            return {"error": result.get("message")}
    except Exception as e:
        return {"error": str(e)}
```

### Шаг 3: Добавьте рендеринг (для Metric)

```javascript
// В templates/dashboard_mdi.html, функция renderMetricHTML
case 'my_metric':
    html = `
        <div class="metric-card">
            <div class="metric-title">My Metric</div>
            <div class="metric-value">${escapeHtml(data.value || 'N/A')}</div>
            <div class="metric-label">${escapeHtml(data.label || '')}</div>
        </div>
    `;
    break;
```

### Шаг 4: Добавьте виджет в JSON конфигурацию

```json
{
  "widget_id": "my_widget",
  "window_id": "my-widget-window",
  "title": "My Widget",
  "metric_name": "my_metric",
  "class_name": "DashboardController",
  "method_name": "get_my_metric",
  "method_parameters": {},
  "position": { "top": 20, "left": 20 },
  "size": { "width": 400, "height": 300 },
  "z_index": 100,
  "enabled": true,
  "draggable": true,
  "resizable": true,
  "closable": true,
  "maximizable": true,
  "description": "Описание виджета"
}
```

### Шаг 5: Обновите документацию

Создайте или обновите файл `docs/dashboards/dashboard_XX.md` с описанием нового виджета.

## Расширенные возможности

### WebSocket обновления

Для виджетов, которые должны обновляться в реальном времени:

1. **Подписка на метрику**:
```javascript
// В dashboard_mdi.html
function subscribeToMetric(metricName) {
    socket.emit('subscribe', { metric: metricName });
}

socket.on('metric_update', (data) => {
    if (data.metric === 'my_metric') {
        updateMetricDisplay('my_metric', data.data);
    }
});
```

2. **Отправка обновлений с сервера**:
```python
# В app.py или контроллере
socketio.emit('metric_update', {
    'metric': 'my_metric',
    'data': get_my_metric()
})
```

### Кастомизация стилей

Виджеты используют общие стили из `dashboard_mdi.html`. Для кастомизации:

```css
/* В dashboard_mdi.html, секция <style> */
.my-widget-custom {
    background: #2d2d30;
    border-left: 3px solid #4ec9b0;
}
```

### Интерактивность

Для интерактивных виджетов используйте JavaScript:

```javascript
// В renderMetricHTML или в отдельном скрипте
case 'my_metric':
    html = `
        <div class="metric-card">
            <button onclick="doSomething()">Действие</button>
        </div>
    `;
    break;

function doSomething() {
    // Ваша логика
    fetch('/api/my-endpoint')
        .then(response => response.json())
        .then(data => {
            // Обновление виджета
        });
}
```

## Примеры

### Пример 1: Простой Metric виджет

**Контроллер** (`controllers/dashboard_controller.py`):
```python
@staticmethod
def get_simple_counter() -> Dict[str, Any]:
    return {
        "count": 42,
        "label": "Счётчик"
    }
```

**Рендеринг** (`templates/dashboard_mdi.html`):
```javascript
case 'simple_counter':
    html = `
        <div class="metric-card">
            <div class="metric-title">${escapeHtml(data.label)}</div>
            <div class="metric-value">${data.count || 0}</div>
        </div>
    `;
    break;
```

**JSON конфигурация**:
```json
{
  "widget_id": "simple_counter",
  "title": "Simple Counter",
  "metric_name": "simple_counter",
  "class_name": "DashboardController",
  "method_name": "get_simple_counter"
}
```

### Пример 2: Embed виджет с API

**HTML** (`templates/my_embed.html`):
```html
<!DOCTYPE html>
<html>
<head>
    <title>My Embed Widget</title>
    <style>
        /* Ваши стили */
    </style>
</head>
<body>
    <div id="content"></div>
    <script>
        async function loadData() {
            const response = await fetch('/api/my-endpoint');
            const data = await response.json();
            document.getElementById('content').innerHTML = data.html;
        }
        loadData();
    </script>
</body>
</html>
```

**Маршрут** (`app.py`):
```python
@app.route('/UNA.md/orasldev/my-embed')
def my_embed():
    if not AuthController.is_authenticated():
        return redirect(url_for('login'))
    return render_template('my_embed.html')
```

## Best Practices

### 1. Обработка ошибок

Всегда обрабатывайте ошибки:

```python
@staticmethod
def get_my_metric() -> Dict[str, Any]:
    try:
        # Логика
        return {"data": result}
    except Exception as e:
        return {
            "error": str(e),
            "data": None
        }
```

### 2. Кэширование

Для тяжёлых запросов используйте кэширование:

```python
from functools import lru_cache
import time

@lru_cache(maxsize=1)
def get_cached_metric(cache_key):
    # Логика получения данных
    return data

@staticmethod
def get_my_metric() -> Dict[str, Any]:
    cache_key = int(time.time() / 60)  # Кэш на 1 минуту
    return get_cached_metric(cache_key)
```

### 3. Валидация данных

Проверяйте данные перед использованием:

```javascript
case 'my_metric':
    if (!data || !data.value) {
        html = '<div style="color: #f48771;">Данные недоступны</div>';
        break;
    }
    html = `...`;
    break;
```

### 4. Оптимизация производительности

- Используйте индексы в SQL-запросах
- Ограничивайте количество возвращаемых строк
- Используйте пагинацию для больших наборов данных

## Тестирование

### Тестирование виджета

1. **Проверка контроллера**:
```python
# test_widget.py
from controllers.dashboard_controller import DashboardController

result = DashboardController.get_my_metric()
assert result.get("data") is not None
```

2. **Проверка API**:
```bash
curl http://localhost:3003/api/dashboard/metric/my_metric
```

3. **Проверка в браузере**:
- Откройте дашборд
- Найдите виджет
- Проверьте отображение данных
- Проверьте обновления (если есть WebSocket)

## Дополнительные ресурсы

- [Общая документация](./README.md)
- [Dashboard 00: Main Dashboard](./dashboards/dashboard_00.md)
- [API документация](./API.md)
