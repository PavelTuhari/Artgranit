# Troubleshooting Guide

## Общие проблемы

### Проблема: Приложение не запускается

**Симптомы**:
- Ошибка при запуске `python app.py`
- `ModuleNotFoundError`
- Порт занят

**Решения**:

1. **Проверьте зависимости**:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

2. **Проверьте порт**:
```bash
lsof -i:3003  # или 8000 для production
kill -9 <PID>  # если порт занят
```

3. **Проверьте .env файл**:
```bash
# Убедитесь, что файл существует и заполнен
cat .env
```

### Проблема: Ошибки подключения к БД

**Симптомы**:
- "Не удалось извлечь wallet"
- "ORA-12154: TNS:could not resolve the connect identifier"
- "ORA-01017: invalid username/password"

**Решения**:

1. **Проверьте wallet**:
```bash
# Убедитесь, что wallet распакован
ls wallet_HXPAVUNKCLU9HE7Q/
# Должны быть: cwallet.sso, ewallet.p12, sqlnet.ora, tnsnames.ora

# Если нет - распакуйте
unzip Wallet_HXPAVUNKCLU9HE7Q.zip -d wallet_HXPAVUNKCLU9HE7Q
```

2. **Проверьте .env параметры**:
```bash
# Убедитесь, что все параметры заполнены
grep -E "DB_USER|DB_PASSWORD|WALLET|CONNECT_STRING" .env
```

3. **Проверьте подключение вручную**:
```python
python -c "
from models.database import DatabaseModel
db = DatabaseModel()
print('Connected!' if db.connection else 'Failed')
"
```

### Проблема: Виджеты не отображаются

**Симптомы**:
- Виджет не появляется на дашборде
- Пустое содержимое виджета
- Ошибки в консоли браузера

**Решения**:

1. **Проверьте JSON конфигурацию**:
```bash
# Убедитесь, что виджет включен
cat dashboards/dashboard_00.json | grep -A 5 "widget_id.*my_widget"
# Проверьте, что "enabled": true
```

2. **Проверьте консоль браузера**:
- Откройте Developer Tools (F12)
- Перейдите на вкладку Console
- Ищите ошибки JavaScript

3. **Проверьте API**:
```bash
# Проверьте, что API возвращает данные
curl http://localhost:3003/api/dashboard/metric/my_metric
```

### Проблема: Данные не обновляются

**Симптомы**:
- Виджет показывает старые данные
- WebSocket не работает

**Решения**:

1. **Проверьте WebSocket подключение**:
```javascript
// В консоли браузера
socket.connected  // должно быть true
```

2. **Проверьте метаданные дашборда**:
```json
{
  "metadata": {
    "websocket_enabled": true,
    "update_interval": 60
  }
}
```

3. **Проверьте логи сервера**:
```bash
tail -f app.log | grep -i websocket
```

## Проблемы с конкретными дашбордами

### Dashboard 03: Табло отправлений

**Проблема**: Данные не отображаются

**Решения**:
1. Проверьте, что таблицы созданы:
```sql
SELECT * FROM BUS_ROUTES;
SELECT * FROM BUS_DEPARTURES;
```

2. Проверьте представление:
```sql
SELECT * FROM V_BUS_DEPARTURES_TODAY;
```

3. Проверьте демо-данные:
```sql
SELECT COUNT(*) FROM BUS_DEPARTURES;
```

### Dashboard 04: Кредиты — Админка

**Проблема**: Программы не сохраняются

**Решения**:
1. Проверьте права доступа:
```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON CRED_PROGRAMS TO ADMIN;
```

2. Проверьте последовательность:
```sql
SELECT CRED_PROGRAMS_SEQ.NEXTVAL FROM DUAL;
```

3. Проверьте пакет:
```sql
SELECT * FROM USER_SOURCE WHERE NAME = 'CRED_ADMIN_PKG';
```

**Проблема**: Матрица не обновляется

**Решения**:
1. Проверьте процедуру:
```sql
EXEC CRED_ADMIN_PKG.SET_MATRIX_ROW(1, 1, 1);
```

2. Проверьте таблицу связей:
```sql
SELECT * FROM CRED_PROGRAM_CATEGORIES;
```

### Dashboard 05: Кредиты — Оператор

**Проблема**: Товары не находятся

**Решения**:
1. Проверьте таблицу товаров:
```sql
SELECT * FROM CRED_PRODUCTS WHERE IS_ACTIVE = 1;
```

2. Проверьте поиск:
```sql
-- Поиск по названию
SELECT * FROM V_CRED_PRODUCTS WHERE PRODUCT_NAME LIKE '%холодильник%';
```

**Проблема**: Программы не фильтруются

**Решения**:
1. Проверьте матрицу доступности:
```sql
SELECT * FROM V_CRED_MATRIX WHERE CATEGORY_ID = 1 AND IS_AVAILABLE = 1;
```

2. Проверьте процедуру:
```sql
EXEC CRED_OPERATOR_PKG.GET_PROGRAMS_FOR_PRODUCT(1, :cur);
```

## Проблемы с документацией

### Проблема: Документация не загружается

**Симптомы**:
- 404 ошибка при открытии `/UNA.md/orasldev/docs/dashboard/00`
- Пустая страница

**Решения**:

1. **Проверьте файлы документации**:
```bash
ls docs/dashboards/dashboard_*.md
```

2. **Проверьте маршрут**:
```python
# В app.py должен быть маршрут
@app.route('/UNA.md/orasldev/docs/dashboard/<dashboard_id>')
```

3. **Проверьте библиотеку markdown**:
```bash
pip install markdown
```

### Проблема: Markdown не отображается правильно

**Решения**:
1. Установите markdown библиотеку:
```bash
pip install markdown
```

2. Проверьте синтаксис markdown файлов
3. Проверьте кодировку файлов (должна быть UTF-8)

## Проблемы с развертыванием

### Проблема: Ошибки при выполнении SQL скриптов

**Симптомы**:
- `ORA-03076`
- `ORA-00942`
- `ORA-00900`

**Решения**:

1. **ORA-03076** (DEFAULT в CREATE TABLE):
   - Удалите все `DEFAULT` clauses из `CREATE TABLE`
   - Используйте последовательности и триггеры для ID

2. **ORA-00942** (таблица не существует):
   - Проверьте порядок выполнения скриптов
   - Убедитесь, что таблицы созданы перед views/triggers

3. **ORA-00900** (неверный SQL):
   - Проверьте синтаксис SQL
   - Убедитесь, что блоки разделены правильно (`/` на новой строке)

### Проблема: Скрипт развертывания падает

**Решения**:

1. **Используйте --dry-run**:
```bash
python deploy_oracle_objects.py --dry-run
```

2. **Проверьте логи**:
```bash
python deploy_oracle_objects.py 2>&1 | tee deploy.log
```

3. **Выполняйте скрипты по одному**:
```bash
# Вручную через SQL*Plus или SQL Developer
sqlplus admin/password@connection < sql/01_bus_tables.sql
```

## Проблемы с производительностью

### Проблема: Медленная загрузка дашборда

**Решения**:

1. **Оптимизируйте SQL-запросы**:
   - Добавьте индексы
   - Используйте LIMIT для больших выборок
   - Кэшируйте результаты

2. **Уменьшите интервал обновления**:
```json
{
  "metadata": {
    "update_interval": 120  // Увеличьте интервал
  }
}
```

3. **Проверьте connection pool**:
```python
# В models/database.py
POOL_MIN = 2
POOL_MAX = 10
```

### Проблема: Высокое использование памяти

**Решения**:

1. **Ограничьте размер выборок**:
```python
# В контроллерах
LIMIT = 100  # Ограничьте количество строк
```

2. **Используйте пагинацию**:
```python
# Добавьте параметры offset и limit
def get_data(offset=0, limit=50):
    ...
```

## Полезные команды

### Проверка состояния

```bash
# Проверка процессов
ps aux | grep python

# Проверка портов
lsof -i:3003
lsof -i:8000

# Проверка логов
tail -f app.log
tail -f /var/log/syslog | grep python
```

### Очистка

```bash
# Остановка всех процессов Python
pkill -f "python app.py"

# Очистка кэша Python
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete
```

### Диагностика БД

```sql
-- Проверка подключения
SELECT * FROM DUAL;

-- Проверка таблиц
SELECT table_name FROM user_tables;

-- Проверка представлений
SELECT view_name FROM user_views;

-- Проверка пакетов
SELECT object_name FROM user_objects WHERE object_type = 'PACKAGE';
```

## Получение помощи

Если проблема не решена:

1. Проверьте логи: `tail -f app.log`
2. Проверьте консоль браузера (F12)
3. Проверьте документацию: `/UNA.md/orasldev/docs`
4. Проверьте API: `curl http://localhost:3003/api/...`

## Дополнительные ресурсы

- [Общая документация](./README.md)
- [Развертывание](./DEPLOYMENT.md)
- [API документация](./API.md)
- [Разработка виджетов](./WIDGET_DEVELOPMENT.md)
