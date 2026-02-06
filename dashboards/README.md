# Dashboard Configurations

Эта директория содержит JSON конфигурации для динамических dashboard'ов.

## Формат файлов

Каждый файл должен называться `dashboard_XX.json`, где `XX` - уникальный двухсимвольный код dashboard'а (например, `00`, `01`, `02`, ...).

## Структура JSON

### Основная структура

```json
{
  "dashboard_id": "00",
  "dashboard_name": "Main Dashboard",
  "dashboard_description": "Описание dashboard",
  "widgets": [...],
  "metadata": {...}
}
```

### Поля верхнего уровня

- **dashboard_id** (string): Уникальный двухсимвольный идентификатор dashboard'а
- **dashboard_name** (string): Название dashboard'а
- **dashboard_description** (string): Описание назначения dashboard'а
- **widgets** (array): Массив виджетов (окон)
- **metadata** (object): Метаданные dashboard'а

### Структура виджета

Каждый виджет описывает одно окно в MDI интерфейсе:

```json
{
  "widget_id": "instance",
  "window_id": "instance-window",
  "title": "Instance Info",
  "metric_name": "instance",
  "class_name": "DatabaseModel",
  "method_name": "get_instance_info",
  "method_parameters": {},
  "position": {
    "top": 20,
    "left": 20
  },
  "size": {
    "width": 350,
    "height": 250
  },
  "z_index": 100,
  "enabled": true,
  "draggable": true,
  "resizable": false,
  "closable": true,
  "maximizable": true,
  "description": "Описание виджета"
}
```

#### Поля виджета

- **widget_id** (string): Уникальный идентификатор виджета (используется в коде)
- **window_id** (string): ID HTML элемента окна (должен быть уникальным)
- **title** (string): Заголовок окна
- **metric_name** (string): Имя метрики для подписки через WebSocket (должно совпадать с `metric_name` в backend)
- **class_name** (string): Имя класса Python (например, `DatabaseModel` или `DashboardController`)
- **method_name** (string): Имя метода класса для получения данных
- **method_parameters** (object): Параметры метода (например, `{"limit": 5}` для `get_top_sql`)
- **position** (object): Позиция окна
  - **top** (number): Расстояние от верха в пикселях
  - **left** (number): Расстояние слева в пикселях
- **size** (object): Размер окна
  - **width** (number): Ширина в пикселях
  - **height** (number): Высота в пикселях
- **z_index** (number): Порядок наложения окон (больше = выше)
- **enabled** (boolean): Включен ли виджет
- **draggable** (boolean): Можно ли перемещать окно
- **resizable** (boolean): Можно ли изменять размер окна (пока не реализовано)
- **closable** (boolean): Можно ли закрывать окно
- **maximizable** (boolean): Можно ли разворачивать окно на весь экран
- **description** (string): Описание назначения виджета

### Структура metadata

```json
{
  "created_at": "2025-01-01",
  "version": "1.0",
  "update_interval": 60,
  "websocket_enabled": true,
  "default_layout": "grid"
}
```

#### Поля metadata

- **created_at** (string): Дата создания (YYYY-MM-DD)
- **version** (string): Версия конфигурации
- **update_interval** (number): Интервал обновления метрик в секундах
- **websocket_enabled** (boolean): Использовать ли WebSocket для обновлений в реальном времени
- **default_layout** (string): Макет по умолчанию (например, "grid", "list")

## Доступные классы и методы

### DatabaseModel

Класс для работы с базой данных Oracle.

- `get_instance_info()` - Информация об экземпляре БД
- `get_memory_metrics()` - Метрики памяти (SGA)
- `get_cpu_metrics()` - Метрики CPU
- `get_sessions_metrics()` - Метрики сессий
- `get_tablespaces()` - Табличные пространства
- `get_top_sql(limit)` - Топ SQL запросов
- `get_uptime()` - Время работы БД

### DashboardController

Класс контроллера dashboard'а.

- `get_system_metrics()` - Системные метрики сервера (память, диск)
- `execute_custom_sql(database_type, sql_query, connection_params)` - Выполнение произвольного SQL запроса к разным БД

### Типы виджетов

#### Стандартные виджеты метрик

Используют `metric_name`, `class_name` и `method_name` для подключения к методам Python классов.

#### Custom SQL виджет (`widget_type: "custom_sql"`)

Новый тип виджета для выполнения произвольных SQL запросов к разным базам данных.

**Дополнительные поля:**
- **widget_type** (string, обязательное): `"custom_sql"`
- **database_type** (string, обязательное): Тип базы данных - `"oracle"`, `"mysql"` или `"sqlite"`
- **sql_query** (string, обязательное): SQL запрос для выполнения
- **connection_params** (object, опциональное): Параметры подключения к БД
  - Для Oracle: используется существующее подключение (можно оставить пустым `{}`)
  - Для MySQL: `{"host": "localhost", "port": 3306, "user": "root", "password": "", "database": ""}`
  - Для SQLite: `{"database": "/path/to/database.db"}` или `{"database": ":memory:"}` для in-memory БД

**Пример custom_sql виджета:**

```json
{
  "widget_id": "custom_sql",
  "window_id": "custom-sql-window",
  "title": "Custom SQL Query",
  "widget_type": "custom_sql",
  "database_type": "oracle",
  "sql_query": "SELECT USER, SYSDATE FROM DUAL",
  "connection_params": {},
  "metric_name": "custom_sql",
  "position": {"top": 720, "left": 20},
  "size": {"width": 800, "height": 400},
  "z_index": 93,
  "enabled": true,
  "draggable": true,
  "resizable": false,
  "closable": true,
  "maximizable": true,
  "description": "Произвольный SQL запрос к базе данных с отображением результатов в гриде"
}
```

**Результаты SQL запроса отображаются в виде таблицы (грида) с автоматическим определением колонок и строк.**

## Пример создания нового dashboard

Создайте файл `dashboard_01.json` с нужной конфигурацией:

```json
{
  "dashboard_id": "01",
  "dashboard_name": "Custom Dashboard",
  "dashboard_description": "Мой кастомный dashboard",
  "widgets": [
    {
      "widget_id": "instance",
      "window_id": "instance-window",
      "title": "Instance Info",
      "metric_name": "instance",
      "class_name": "DatabaseModel",
      "method_name": "get_instance_info",
      "method_parameters": {},
      "position": {"top": 50, "left": 50},
      "size": {"width": 400, "height": 300},
      "z_index": 100,
      "enabled": true,
      "draggable": true,
      "resizable": false,
      "closable": true,
      "maximizable": true,
      "description": "Информация об экземпляре"
    }
  ],
  "metadata": {
    "created_at": "2025-01-01",
    "version": "1.0",
    "update_interval": 60,
    "websocket_enabled": true,
    "default_layout": "grid"
  }
}
```

## Эталонный файл

`dashboard_00.json` содержит текущую конфигурацию основного dashboard'а со всеми 7 виджетами:
1. Instance Info
2. Memory Usage
3. CPU Usage
4. Sessions
5. Tablespaces
6. Top SQL Queries
7. Server System Metrics

