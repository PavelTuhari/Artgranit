# Руководство по конфигурации

## Обзор

Это руководство описывает все параметры конфигурации системы Oracle SQL Developer Web & Dashboard.

## Файлы конфигурации

### 1. `.env` файл

Основной файл конфигурации. Содержит все секретные данные и параметры подключения.

**Расположение**: Корень проекта (`/path/to/project/.env`)

**ВАЖНО**: Этот файл НЕ должен коммититься в git! Убедитесь, что он в `.gitignore`.

#### Структура `.env` файла

```bash
# ============================================
# Oracle Database Configuration
# ============================================

# Пользователь базы данных
DB_USER=ADMIN

# Пароль пользователя БД (НЕ коммитьте в git!)
DB_PASSWORD=your_secure_password_here

# Пароль для Oracle Wallet
WALLET_PASSWORD=your_wallet_password_here

# Имя ZIP архива wallet
WALLET_ZIP=Wallet_HXPAVUNKCLU9HE7Q.zip

# Директория с распакованным wallet
WALLET_DIR=wallet_HXPAVUNKCLU9HE7Q

# TNS Alias (опционально, если используется tnsnames.ora)
TNS_ALIAS=hxpavunkclu9he7q_high

# Connect String для прямого подключения
CONNECT_STRING=(description= (retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=adb.eu-frankfurt-1.oraclecloud.com))(connect_data=(service_name=g47056ff8b1b3d4_hxpavunkclu9he7q_high.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))

# ============================================
# Application Configuration
# ============================================

# Секретный ключ для Flask сессий (сгенерируйте случайную строку)
SECRET_KEY=your-secret-key-here-change-in-production

# Окружение: LOCAL или REMOTE
ENVIRONMENT=REMOTE

# Порт сервера
PORT=8000

# Хост сервера (0.0.0.0 для доступа извне)
SERVER_HOST=0.0.0.0

# ============================================
# Authentication
# ============================================

# Учётные данные по умолчанию (измените в production!)
DEFAULT_USERNAME=admin
DEFAULT_PASSWORD=admin123
```

### 2. `config.py`

Python модуль конфигурации, который читает `.env` файл.

**Расположение**: Корень проекта

**Использование**:
```python
from config import Config

# Доступ к параметрам
db_user = Config.DB_USER
db_password = Config.DB_PASSWORD
```

### 3. JSON конфигурации дашбордов

**Расположение**: `dashboards/dashboard_XX.json`

**Структура**:
```json
{
  "dashboard_id": "00",
  "dashboard_name": "Main Dashboard",
  "dashboard_description": "Описание",
  "widgets": [...],
  "metadata": {
    "update_interval": 60,
    "websocket_enabled": true
  }
}
```

## Настройка подключения к Oracle

### Вариант 1: Connect String (рекомендуется)

Используйте полный connect string в `.env`:

```bash
CONNECT_STRING=(description= (retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=adb.eu-frankfurt-1.oraclecloud.com))(connect_data=(service_name=your_service_name.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))
```

### Вариант 2: TNS Alias

Если используете `tnsnames.ora`:

```bash
TNS_ALIAS=your_alias_name
```

И в `tnsnames.ora`:
```
your_alias_name = (description= ...)
```

### Вариант 3: Easy Connect

Для простых подключений:
```bash
CONNECT_STRING=user/password@host:port/service_name
```

## Настройка окружения

### LOCAL (разработка)

```bash
ENVIRONMENT=LOCAL
PORT=3003
SERVER_HOST=0.0.0.0  # Для доступа по локальному IP
```

### REMOTE (production)

```bash
ENVIRONMENT=REMOTE
PORT=8000
SERVER_HOST=0.0.0.0
```

## Безопасность

### Рекомендации

1. **Используйте сильные пароли**:
   - Минимум 16 символов
   - Смесь букв, цифр, символов
   - Не используйте словарные слова

2. **Ограничьте доступ к `.env`**:
```bash
chmod 600 .env
```

3. **Не коммитьте секреты**:
```bash
# В .gitignore
.env
*.env
.env.local
```

4. **Используйте разные пароли** для:
   - DB_PASSWORD
   - WALLET_PASSWORD
   - SECRET_KEY

### Генерация SECRET_KEY

```python
import secrets
print(secrets.token_hex(32))
```

Или через командную строку:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Настройка дашбордов

### Изменение интервала обновления

В JSON конфигурации дашборда:
```json
{
  "metadata": {
    "update_interval": 120  // секунды
  }
}
```

### Включение/выключение WebSocket

```json
{
  "metadata": {
    "websocket_enabled": true
  }
}
```

### Настройка виджетов

```json
{
  "widgets": [
    {
      "enabled": true,  // Включить/выключить виджет
      "draggable": true,  // Разрешить перетаскивание
      "resizable": true,  // Разрешить изменение размера
      "position": {"top": 20, "left": 20},
      "size": {"width": 400, "height": 300}
    }
  ]
}
```

## Настройка для разных окружений

### Development

```bash
# .env.development
ENVIRONMENT=LOCAL
PORT=3003
DEBUG=True
```

### Staging

```bash
# .env.staging
ENVIRONMENT=REMOTE
PORT=8000
DEBUG=False
```

### Production

```bash
# .env.production
ENVIRONMENT=REMOTE
PORT=8000
DEBUG=False
# Используйте сильные пароли!
```

## Переменные окружения

Все параметры можно переопределить через переменные окружения:

```bash
export DB_USER=custom_user
export DB_PASSWORD=custom_password
python app.py
```

Приоритет: переменные окружения > `.env` файл > значения по умолчанию

## Проверка конфигурации

### Скрипт проверки

Создайте `check_config.py`:

```python
from config import Config
import os

print("=== Проверка конфигурации ===")
print(f"DB_USER: {'✓' if Config.DB_USER else '✗'}")
print(f"DB_PASSWORD: {'✓' if Config.DB_PASSWORD else '✗'}")
print(f"WALLET_DIR: {'✓' if os.path.exists(Config.WALLET_DIR) else '✗'}")
print(f"ENVIRONMENT: {Config.ENVIRONMENT}")
print(f"PORT: {Config.SERVER_PORT}")
```

Запуск:
```bash
python check_config.py
```

## Миграция конфигурации

При переносе на новый сервер:

1. Скопируйте `.env.example` в `.env`
2. Заполните все параметры
3. Проверьте подключение: `python check_config.py`
4. Запустите приложение

## Rate Limiting

Ограничение количества запросов к API (только для `/api/*`):

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `RATELIMIT_DEFAULT` | `200 per hour` | Лимит запросов (например `100 per minute`) |
| `RATELIMIT_STORAGE_URI` | `memory://` | Хранилище (`memory://` или `redis://localhost:6379`) |
| `RATELIMIT_ENABLED` | `true` | Включить/выключить |

## Дополнительные ресурсы

- [Развертывание](/UNA.md/orasldev/docs/deployment)
- [Troubleshooting](/UNA.md/orasldev/docs)
- [API документация](/UNA.md/orasldev/docs/api)
