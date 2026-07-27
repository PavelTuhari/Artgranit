# Руководство по развертыванию

## Обзор

Это руководство описывает процесс развертывания системы Oracle SQL Developer Web & Dashboard на сервере. Система включает в себя веб-приложение на Flask, Oracle Database объекты, и различные дашборды для мониторинга и управления.

## Предварительные требования

### Системные требования

- **ОС**: Ubuntu Server 20.04+ или macOS 12+
- **Python**: 3.12 или выше
- **Oracle Database**: 12c+ (рекомендуется Oracle Autonomous Database)
- **Память**: Минимум 2GB RAM
- **Диск**: Минимум 5GB свободного места

### Необходимые компоненты

1. **Oracle Wallet**: ZIP архив с сертификатами для подключения к Oracle Cloud
2. **Python зависимости**: Устанавливаются через `requirements.txt`
3. **Переменные окружения**: Файл `.env` с параметрами подключения

## Установка

### 1. Подготовка окружения

```bash
# Клонируйте или скопируйте проект
cd /path/to/project

# Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установите зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```bash
# База данных Oracle
DB_USER=ADMIN
DB_PASSWORD=your_password_here
WALLET_PASSWORD=your_wallet_password
WALLET_ZIP=Wallet_HXPAVUNKCLU9HE7Q.zip
WALLET_DIR=wallet_HXPAVUNKCLU9HE7Q
TNS_ALIAS=hxpavunkclu9he7q_high
CONNECT_STRING=(description= (retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=adb.eu-frankfurt-1.oraclecloud.com))(connect_data=(service_name=g47056ff8b1b3d4_hxpavunkclu9he7q_high.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))

# Приложение
SECRET_KEY=your_secret_key_here
ENVIRONMENT=REMOTE
PORT=8000
SERVER_HOST=0.0.0.0

# Аутентификация
DEFAULT_USERNAME=admin
DEFAULT_PASSWORD=admin123
```

**ВАЖНО**: Никогда не коммитьте `.env` файл в git! Он должен быть в `.gitignore`.

### 3. Подготовка Oracle Wallet

```bash
# Распакуйте Oracle Wallet ZIP
unzip Wallet_HXPAVUNKCLU9HE7Q.zip -d wallet_HXPAVUNKCLU9HE7Q

# Проверьте содержимое
ls wallet_HXPAVUNKCLU9HE7Q/
# Должны быть файлы: cwallet.sso, ewallet.p12, sqlnet.ora, tnsnames.ora и др.
```

### 4. Развертывание объектов базы данных

```bash
# Развертывание всех объектов (таблицы, представления, триггеры, пакеты)
python deploy_oracle_objects.py

# Или с очисткой существующих объектов
python deploy_oracle_objects.py --drop

# Только демо-данные
python deploy_oracle_objects.py --demo
```

**Порядок выполнения скриптов:**
1. `00_drop.sql` - Удаление существующих объектов (если используется `--drop`)
2. `01_bus_tables.sql` - Таблицы для табло отправлений
3. `02_bus_views.sql` - Представления для табло
4. `03_bus_triggers.sql` - Триггеры для табло
5. `04_bus_package.sql` - Пакет для табло
6. `05_cred_tables.sql` - Таблицы для кредитов
7. `06_cred_views.sql` - Представления для кредитов
8. `07_cred_triggers.sql` - Триггеры для кредитов
9. `08_cred_admin_package.sql` - Пакет администрирования кредитов
10. `09_cred_operator_package.sql` - Пакет оператора кредитов
11. `10_demo_data.sql` - Демонстрационные данные

## Запуск приложения

### Локальный запуск (Mac)

```bash
./run_local.sh
```

Или вручную:
```bash
source venv/bin/activate
export ENVIRONMENT=LOCAL
export PORT=3003
python app.py
```

### Удаленный сервер (Production)

#### Вариант 1: Использование скрипта

```bash
./full_restart.sh
```

#### Вариант 2: Ручной запуск

```bash
source venv/bin/activate
export ENVIRONMENT=REMOTE
export PORT=8000
nohup python app.py > app.log 2>&1 &
```

#### Вариант 3: Systemd service (рекомендуется для production)

Создайте файл `/etc/systemd/system/oracle-dashboard.service`:

```ini
[Unit]
Description=Oracle SQL Developer Web & Dashboard
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/oracle_test_app
Environment="PATH=/home/ubuntu/oracle_test_app/venv/bin"
ExecStart=/home/ubuntu/oracle_test_app/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable oracle-dashboard
sudo systemctl start oracle-dashboard
sudo systemctl status oracle-dashboard
```

## Проверка работоспособности

### 1. Проверка подключения к БД

```bash
# Через Python
python -c "from models.database import DatabaseModel; db = DatabaseModel(); print('Connected!' if db.connection else 'Failed')"
```

### 2. Проверка веб-сервера

```bash
# Проверка доступности
curl http://localhost:8000/

# Проверка API
curl http://localhost:8000/api/dashboard/list
```

### 3. Проверка дашбордов

Откройте в браузере:
- `http://your-server:8000/UNA.md/orasldev/login`
- Войдите с учётными данными
- Перейдите на `/UNA.md/orasldev/dashboard`
- Проверьте работу виджетов

## Обслуживание

### Просмотр логов

```bash
# Логи приложения
tail -f app.log

# Логи systemd
sudo journalctl -u oracle-dashboard -f
```

### Перезапуск сервиса

```bash
# Если используется systemd
sudo systemctl restart oracle-dashboard

# Если запущено через nohup
pkill -f "python app.py"
# Затем запустите снова
```

### Обновление кода

```bash
# Остановите сервис
sudo systemctl stop oracle-dashboard

# Обновите код (git pull или копирование файлов)

# Обновите зависимости (если нужно)
source venv/bin/activate
pip install -r requirements.txt

# Запустите снова
sudo systemctl start oracle-dashboard
```

### Резервное копирование

```bash
# Создайте бэкап проекта
./backup.sh

# Бэкап будет в папке ./backups/
```

## Troubleshooting

### Проблемы с подключением к БД

**Ошибка**: "Не удалось извлечь wallet"
- Проверьте, что файл Wallet ZIP существует
- Проверьте, что wallet распакован в правильную папку
- Проверьте права доступа к файлам wallet

**Ошибка**: "ORA-12154: TNS:could not resolve the connect identifier"
- Проверьте `CONNECT_STRING` в `.env`
- Проверьте `tnsnames.ora` в wallet директории
- Убедитесь, что `WALLET_DIR` указан правильно

**Ошибка**: "ORA-01017: invalid username/password"
- Проверьте `DB_USER` и `DB_PASSWORD` в `.env`
- Убедитесь, что пользователь существует в БД

### Проблемы с портом

**Ошибка**: "Address already in use"
```bash
# Найдите процесс, использующий порт
lsof -i:8000

# Остановите процесс
kill -9 <PID>
```

### Проблемы с зависимостями

**Ошибка**: "ModuleNotFoundError"
```bash
# Переустановите зависимости
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

## Безопасность

### Рекомендации

1. **Никогда не коммитьте `.env` файл** в git
2. **Используйте сильные пароли** для БД и wallet
3. **Ограничьте доступ** к серверу через firewall
4. **Используйте HTTPS** в production (настройте reverse proxy с SSL)
5. **Регулярно обновляйте** зависимости
6. **Мониторьте логи** на подозрительную активность

### Настройка firewall

```bash
# Разрешить только необходимые порты
sudo ufw allow 8000/tcp
sudo ufw enable
```

### Reverse Proxy (Nginx)

Пример конфигурации `/etc/nginx/sites-available/oracle-dashboard`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Масштабирование

### Горизонтальное масштабирование

Для увеличения нагрузки можно:
1. Запустить несколько экземпляров приложения на разных портах
2. Использовать load balancer (Nginx, HAProxy)
3. Настроить connection pooling в `models/database.py`

### Вертикальное масштабирование

- Увеличьте размер connection pool
- Настройте кэширование метрик
- Оптимизируйте SQL-запросы

## Мониторинг

### Рекомендуемые метрики

- Время отклика API
- Количество активных соединений к БД
- Использование памяти и CPU
- Количество ошибок в логах
- Доступность сервиса (uptime)

### Инструменты мониторинга

- **Логи**: `tail -f app.log`
- **Процессы**: `ps aux | grep python`
- **Сеть**: `netstat -tulpn | grep 8000`
- **База данных**: Используйте дашборды для мониторинга БД

## Дополнительные ресурсы

- [Общая документация](./README.md)
- [Конфигурация](./CONFIGURATION.md)
- [API документация](./API.md)
- [Troubleshooting](./TROUBLESHOOTING.md)
