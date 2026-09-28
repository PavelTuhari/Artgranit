# Dashboard 03: Табло отправлений автовокзала

## Описание

Дашборд для отображения информации о рейсах автовокзала в реальном времени. Показывает расписание отправлений, статусы рейсов, платформы и ворота.

## Назначение

Этот дашборд предназначен для:
- **Пассажиров**: Просмотр актуального расписания отправлений
- **Персонала автовокзала**: Управление рейсами и статусами
- **Администраторов**: Мониторинг работы системы

## Доступные виджеты

### 1. Табло отправлений
**Тип**: Метрика  
**Класс**: `DashboardController.get_departure_board`  
**Описание**: Отображает список рейсов на сегодня:
- Номер маршрута
- Направление (пункт назначения)
- Время отправления
- Платформа
- Ворота
- Статус (Ожидание, Посадка, Отправлен, Задержан)

## База данных

### Таблицы

#### BUS_ROUTES
Хранит информацию о маршрутах:
- `ROUTE_ID` (PK) - ID маршрута
- `ROUTE_NUMBER` - Номер маршрута
- `DESTINATION` - Пункт назначения
- `DISTANCE_KM` - Расстояние в км
- `DURATION_MINUTES` - Продолжительность в минутах

#### BUS_DEPARTURES
Хранит информацию о рейсах:
- `DEPARTURE_ID` (PK) - ID рейса
- `ROUTE_ID` (FK) - Ссылка на маршрут
- `DEPARTURE_TIME` - Время отправления
- `PLATFORM` - Платформа
- `GATE` - Ворота
- `STATUS` - Статус рейса
- `CREATED_AT` - Дата создания
- `UPDATED_AT` - Дата обновления

### Представления (Views)

#### V_BUS_DEPARTURES_TODAY
Представление для получения рейсов на сегодня:
```sql
SELECT 
    r.ROUTE_NUMBER as ROUTE,
    r.DESTINATION,
    d.DEPARTURE_TIME,
    d.PLATFORM,
    d.GATE,
    d.STATUS
FROM BUS_DEPARTURES d
JOIN BUS_ROUTES r ON d.ROUTE_ID = r.ROUTE_ID
WHERE TRUNC(d.DEPARTURE_TIME) = TRUNC(SYSDATE)
ORDER BY d.DEPARTURE_TIME
```

### Пакеты (Packages)

#### BUS_PKG
Содержит процедуры для работы с рейсами:
- `GET_DEPARTURES(P_DATE DATE, P_CUR OUT SYS_REFCURSOR)` - Получение рейсов на дату
- `UPDATE_STATUS(P_DEPARTURE_ID NUMBER, P_STATUS VARCHAR2)` - Обновление статуса

## Развертывание

### 1. Развертывание объектов БД

Используйте скрипт развертывания:
```bash
python deploy_oracle_objects.py
```

Или вручную выполните SQL скрипты в порядке:
1. `sql/01_bus_tables.sql` - Создание таблиц
2. `sql/02_bus_views.sql` - Создание представлений
3. `sql/03_bus_triggers.sql` - Создание триггеров
4. `sql/04_bus_package.sql` - Создание пакета
5. `sql/10_demo_data.sql` - Заполнение демо-данными

### 2. Настройка приложения

Виджет автоматически подключается к БД через `DashboardController.get_departure_board()`.

### 3. Заполнение данными

Для заполнения тестовыми данными выполните:
```bash
python deploy_oracle_objects.py --demo
```

Или используйте SQL скрипт `sql/10_demo_data.sql`.

## Доработка

### Добавление нового статуса

1. **Обновите CHECK constraint в таблице:**
```sql
ALTER TABLE BUS_DEPARTURES 
DROP CONSTRAINT CHK_DEPARTURE_STATUS;

ALTER TABLE BUS_DEPARTURES 
ADD CONSTRAINT CHK_DEPARTURE_STATUS 
CHECK (STATUS IN ('Ожидание', 'Посадка', 'Отправлен', 'Задержан', 'Новый статус'));
```

2. **Обновите виджет в `dashboard_mdi.html`:**
Добавьте обработку нового статуса в рендеринг.

### Добавление новых полей

1. **Добавьте колонку в таблицу:**
```sql
ALTER TABLE BUS_DEPARTURES ADD NEW_FIELD VARCHAR2(100);
```

2. **Обновите представление:**
Добавьте новое поле в `V_BUS_DEPARTURES_TODAY`.

3. **Обновите контроллер:**
Добавьте обработку нового поля в `get_departure_board()`.

4. **Обновите виджет:**
Добавьте отображение нового поля в HTML.

## API

### Получение данных табло

**Endpoint**: `GET /api/dashboard/metric/departure_board`

**Ответ**:
```json
{
  "success": true,
  "metric": "departure_board",
  "data": {
    "title": "Табло отправлений",
    "current_time": "14:30:00",
    "departures": [
      {
        "route": "101",
        "destination": "Кишинэу",
        "departure": "14:45",
        "platform": "3",
        "gate": "A",
        "status": "Посадка"
      }
    ]
  }
}
```

## Troubleshooting

### Данные не отображаются
- Проверьте, что таблицы созданы: `SELECT * FROM BUS_ROUTES;`
- Проверьте, что представление работает: `SELECT * FROM V_BUS_DEPARTURES_TODAY;`
- Проверьте логи сервера на ошибки SQL

### Статусы не обновляются
- Убедитесь, что триггер `TR_BUS_DEPARTURES_BIU` создан
- Проверьте права доступа к таблице `BUS_DEPARTURES`

### Ошибки при развертывании
- Убедитесь, что последовательности созданы перед таблицами
- Проверьте, что нет конфликтов имен объектов
- Используйте `--drop` для очистки перед развертыванием

## Дополнительные ресурсы

- [DDL скрипты](../../sql/README.md)
- [Общая документация проекта](../README.md)
- [Руководство по развертыванию](../DEPLOYMENT.md)
