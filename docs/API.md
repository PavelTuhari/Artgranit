# API Документация

## Обзор

Система предоставляет REST API для взаимодействия с дашбордами, кредитными программами и операциями с базой данных. Все API endpoints требуют аутентификации (кроме `/login`).

## Базовый URL

- **Локально**: `http://localhost:3003`
- **Production**: `http://92.5.3.187:8000`

## Аутентификация

Большинство endpoints требуют аутентификации. Используйте cookie-based сессии после входа через `/login`.

## Dashboard API

### Получение списка дашбордов

**Endpoint**: `GET /api/dashboard/list`

**Ответ**:
```json
{
  "success": true,
  "dashboards": [
    {
      "dashboard_id": "00",
      "dashboard_name": "Main Dashboard",
      "dashboard_description": "Основной дашборд с базовыми метриками"
    }
  ],
  "count": 6
}
```

### Получение конфигурации дашборда

**Endpoint**: `GET /api/dashboard/config/<dashboard_id>`

**Пример**: `GET /api/dashboard/config/00`

**Ответ**:
```json
{
  "success": true,
  "config": {
    "dashboard_id": "00",
    "dashboard_name": "Main Dashboard",
    "widgets": [...]
  }
}
```

### Получение метрики

**Endpoint**: `GET /api/dashboard/metric/<metric_name>`

**Пример**: `GET /api/dashboard/metric/instance`

**Ответ**:
```json
{
  "success": true,
  "metric": "instance",
  "data": {
    "instance_name": "ORCL",
    "host_name": "server.example.com",
    "version": "19.0.0.0.0"
  }
}
```

## Credit Admin API

### Получение списка программ

**Endpoint**: `GET /api/credit-admin/programs?active=1`

**Параметры запроса**:
- `active` (optional): 1 - только активные, 0 - все

**Ответ**:
```json
{
  "success": true,
  "data": [
    {
      "program_id": 1,
      "program_name": "Maib 0-0-24",
      "bank_name": "Maib",
      "term_months": 24,
      "rate_pct": 0,
      "first_payment_pct": 0,
      "min_amount": 1000,
      "max_amount": 50000,
      "commission_pct": 0,
      "is_active": 1
    }
  ]
}
```

### Получение программы по ID

**Endpoint**: `GET /api/credit-admin/programs/<id>`

**Пример**: `GET /api/credit-admin/programs/1`

**Ответ**:
```json
{
  "success": true,
  "data": {
    "program_id": 1,
    "program_name": "Maib 0-0-24",
    "bank_id": 1,
    "bank_name": "Maib",
    ...
  }
}
```

### Создание/обновление программы

**Endpoint**: `POST /api/credit-admin/programs`

**Тело запроса**:
```json
{
  "program_id": null,  // null для создания, число для обновления
  "program_name": "Новая программа",
  "bank_id": 1,
  "term_months": 12,
  "rate_pct": 0,
  "first_payment_pct": 0,
  "min_amount": 5000,
  "max_amount": 100000,
  "commission_pct": 0,
  "is_active": 1,
  "notes": "Примечания"
}
```

**Ответ**:
```json
{
  "success": true,
  "program_id": 5,
  "message": "Программа успешно сохранена"
}
```

### Удаление программы

**Endpoint**: `DELETE /api/credit-admin/programs/<id>`

**Пример**: `DELETE /api/credit-admin/programs/1`

**Ответ**:
```json
{
  "success": true,
  "message": "Программа удалена"
}
```

### Получение матрицы доступности

**Endpoint**: `GET /api/credit-admin/matrix`

**Ответ**:
```json
{
  "success": true,
  "data": [
    {
      "category_id": 1,
      "category_name": "Холодильники",
      "programs": [
        {
          "program_id": 1,
          "program_name": "Maib 0-0-24",
          "is_available": 1
        }
      ]
    }
  ]
}
```

### Обновление матрицы доступности

**Endpoint**: `POST /api/credit-admin/matrix`

**Тело запроса**:
```json
{
  "category_id": 1,
  "program_id": 1,
  "enabled": 1
}
```

**Ответ**:
```json
{
  "success": true,
  "message": "Матрица обновлена"
}
```

### Получение справочников

**Endpoint**: `GET /api/credit-admin/banks`
**Endpoint**: `GET /api/credit-admin/categories`
**Endpoint**: `GET /api/credit-admin/brands`

**Ответ** (пример для banks):
```json
{
  "success": true,
  "data": [
    {
      "bank_id": 1,
      "bank_name": "Maib",
      "is_active": 1
    }
  ]
}
```

## Credit Operator API

### Получение популярных товаров

**Endpoint**: `GET /api/credit-operator/products?limit=6`

**Параметры запроса**:
- `limit` (optional): Количество товаров (по умолчанию 10)

**Ответ**:
```json
{
  "success": true,
  "data": [
    {
      "product_id": 1,
      "product_name": "Холодильник Samsung",
      "category_name": "Холодильники",
      "brand_name": "Samsung",
      "price": 25000,
      "barcode": "1234567890",
      "img_url": "/static/images/product1.jpg"
    }
  ]
}
```

### Поиск товара по ID

**Endpoint**: `GET /api/credit-operator/products/<id>`

**Пример**: `GET /api/credit-operator/products/1`

### Поиск товара по штрихкоду

**Endpoint**: `GET /api/credit-operator/products?barcode=<barcode>`

**Пример**: `GET /api/credit-operator/products?barcode=1234567890`

### Поиск товаров

**Endpoint**: `GET /api/credit-operator/products?search=<query>`

**Пример**: `GET /api/credit-operator/products?search=холодильник`

### Получение программ для товара

**Endpoint**: `GET /api/credit-operator/programs-for-product/<product_id>`

**Пример**: `GET /api/credit-operator/programs-for-product/1`

**Ответ**:
```json
{
  "success": true,
  "data": [
    {
      "program_id": 1,
      "program_name": "Maib 0-0-24",
      "term_months": 24,
      "first_payment_pct": 0,
      "rate_pct": 0,
      "monthly_payment": 1042
    }
  ]
}
```

### Создание заявки

**Endpoint**: `POST /api/credit-operator/application`

**Тело запроса**:
```json
{
  "product_id": 1,
  "program_id": 1,
  "client_fio": "Иванов Иван Иванович",
  "client_phone": "+373 123 456 78",
  "client_id_number": "1234567890"
}
```

**Ответ**:
```json
{
  "success": true,
  "application_id": 1,
  "status": "approved",
  "approved_amount": 25000,
  "reject_reason": null
}
```

**Возможные статусы**:
- `approved` - Одобрено
- `rejected` - Отказано
- `on_review` - На рассмотрении

### Получение последних заявок

**Endpoint**: `GET /api/credit-operator/recent-applications?limit=5`

**Параметры запроса**:
- `limit` (optional): Количество заявок (по умолчанию 5)

**Ответ**:
```json
{
  "success": true,
  "data": [
    {
      "application_id": 1,
      "product_name": "Холодильник Samsung",
      "program_name": "Maib 0-0-24",
      "client_fio": "Иванов И.И.",
      "application_status": "approved",
      "created_at": "2026-01-27T12:00:00"
    }
  ]
}
```

## Documentation API

### Получение документации дашборда

**Endpoint**: `GET /api/dashboard/documentation/<dashboard_id>`

**Пример**: `GET /api/dashboard/documentation/00`

**Ответ**:
```json
{
  "success": true,
  "data": {
    "dashboard_id": "00",
    "dashboard_name": "Main Dashboard",
    "widgets": [...]
  }
}
```

### Генерация DDL скрипта

**Endpoint**: `GET /api/dashboard/ddl/<dashboard_id>`

**Пример**: `GET /api/dashboard/ddl/03`

**Ответ**:
```json
{
  "success": true,
  "script": "-- DDL скрипт...",
  "files_included": ["01_bus_tables.sql", "02_bus_views.sql", ...]
}
```

### Генерация DML скрипта

**Endpoint**: `GET /api/dashboard/dml/<dashboard_id>`

**Пример**: `GET /api/dashboard/dml/03`

**Ответ**:
```json
{
  "success": true,
  "script": "-- DML скрипт (демо-данные)...",
  "files_included": ["10_demo_data.sql"]
}
```

## Обработка ошибок

Все API endpoints возвращают JSON с полем `success`:

```json
{
  "success": false,
  "error": "Описание ошибки",
  "traceback": "..." // только в development режиме
}
```

**HTTP коды статуса**:
- `200` - Успех
- `400` - Ошибка валидации
- `401` - Требуется аутентификация
- `404` - Ресурс не найден
- `500` - Внутренняя ошибка сервера

## Примеры использования

### JavaScript (Fetch API)

```javascript
// Получение списка программ
const response = await fetch('/api/credit-admin/programs?active=1');
const result = await response.json();
if (result.success) {
  console.log(result.data);
}

// Создание программы
const response = await fetch('/api/credit-admin/programs', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    program_name: "Новая программа",
    bank_id: 1,
    term_months: 12,
    // ...
  })
});
const result = await response.json();
```

### Python (requests)

```python
import requests

# Получение списка программ
response = requests.get('http://localhost:3003/api/credit-admin/programs?active=1')
result = response.json()
if result['success']:
    programs = result['data']

# Создание программы
response = requests.post(
    'http://localhost:3003/api/credit-admin/programs',
    json={
        'program_name': 'Новая программа',
        'bank_id': 1,
        'term_months': 12,
        # ...
    }
)
result = response.json()
```

## Rate Limiting

Реализовано ограничение количества запросов к API эндпоинтам (`/api/*`).

| Параметр | Значение по умолчанию | Описание |
|----------|----------------------|----------|
| Лимит | `200 per hour` | Количество запросов в час на IP |
| Хранилище | `memory://` | In-memory (для production рекомендуется Redis) |
| Область | Только `/api/*` | Страницы, login, docs не ограничены |

**Переменные окружения (.env):**
- `RATELIMIT_DEFAULT` — лимит, например `100 per minute` или `1000 per day`
- `RATELIMIT_STORAGE_URI` — `memory://` или `redis://localhost:6379`
- `RATELIMIT_ENABLED` — `true` или `false` (отключить)

**Ответ при превышении (429):**
```json
{
  "success": false,
  "error": "Rate limit exceeded",
  "message": "Слишком много запросов. Попробуйте позже."
}
```

Заголовки ответа: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`

## Версионирование

Текущая версия API: `v1` (неявная)

В будущем можно добавить версионирование через префикс URL: `/api/v1/...`

## Дополнительные ресурсы

- [Общая документация](/UNA.md/orasldev/docs)
- [Развертывание](/UNA.md/orasldev/docs/deployment)
- [Конфигурация](/UNA.md/orasldev/docs/configuration)
