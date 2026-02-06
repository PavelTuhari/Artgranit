# Dashboard 01: Custom Dashboard 01

## Описание

Кастомный дашборд с базовыми метриками Oracle Database и дополнительными возможностями, включая Custom SQL виджеты для Oracle и SQLite.

## Назначение

Этот дашборд предназначен для:
- **Разработчиков**: Тестирование SQL-запросов к разным БД
- **Администраторов БД**: Мониторинг и анализ данных
- **Аналитиков**: Выполнение произвольных запросов

## Доступные виджеты

### Основные метрики

Все виджеты из Dashboard 00 плюс:

### Custom SQL Query (Oracle)
**Тип**: Custom SQL  
**Описание**: Выполнение произвольных SQL-запросов к Oracle Database:
- Ввод SQL-запроса в конфигурации виджета
- Отображение результатов в табличном виде
- Поддержка всех типов Oracle запросов

**Пример запроса по умолчанию**:
```sql
SELECT USER, SYSDATE FROM DUAL
```

### Custom SQL Query (SQLite Demo)
**Тип**: Custom SQL  
**Описание**: Выполнение SQL-запросов к демо SQLite базе данных:
- Демонстрационная база с таблицами employees и departments
- JOIN запросы
- Агрегация данных

**Пример запроса по умолчанию**:
```sql
SELECT 
    e.first_name || ' ' || e.last_name AS employee_name, 
    e.department, 
    e.position, 
    e.salary, 
    d.name AS dept_name, 
    d.location 
FROM employees e 
LEFT JOIN departments d ON e.department = d.name 
ORDER BY e.salary DESC
```

## Развертывание

### Требования
- Oracle Database 12c+
- Python 3.12+
- SQLite3 (для демо БД)

### Установка

1. **Установите зависимости:**
```bash
pip install -r requirements.txt
```

2. **Создайте демо SQLite базу (если нужно):**
```bash
python create_demo_sqlite_db.py
```

3. **Настройте подключение к Oracle:**
Отредактируйте `.env` файл.

4. **Запустите приложение:**
```bash
./run_local.sh
```

## Доработка

### Добавление нового Custom SQL виджета

1. **Добавьте виджет в JSON:**
```json
{
  "widget_id": "my_custom_sql",
  "title": "My Custom SQL",
  "widget_type": "custom_sql",
  "database_type": "oracle",
  "sql_query": "SELECT * FROM MY_TABLE",
  "connection_params": {
    "type": "oracle"
  }
}
```

2. **Настройте connection_params:**
- Для Oracle: `{"type": "oracle"}` (использует настройки из .env)
- Для SQLite: `{"type": "sqlite", "database": "path/to/db.db"}`

### Изменение SQL запроса

Измените поле `sql_query` в JSON конфигурации виджета. Запрос будет выполнен при загрузке дашборда.

## API

### Выполнение Custom SQL

**Endpoint**: `POST /api/dashboard/widget/custom-sql`

**Тело запроса**:
```json
{
  "database_type": "oracle",
  "sql_query": "SELECT * FROM DUAL",
  "connection_params": {}
}
```

**Ответ**:
```json
{
  "success": true,
  "data": [[1], [2], [3]],
  "columns": ["ID"],
  "rowcount": 3
}
```

## Troubleshooting

### SQL запрос не выполняется
- Проверьте синтаксис SQL
- Убедитесь, что таблицы существуют
- Проверьте права доступа к таблицам

### SQLite база не найдена
- Убедитесь, что файл `data/demo_database.db` существует
- Проверьте путь в `connection_params.database`
- Создайте базу: `python create_demo_sqlite_db.py`

### Ошибки подключения к Oracle
- Проверьте параметры в `.env`
- Убедитесь, что Oracle Wallet настроен
- Проверьте доступность БД

## Дополнительные ресурсы

- [Dashboard 00: Main Dashboard](./dashboard_00.md)
- [Общая документация проекта](../README.md)
- [API документация](../API.md)
