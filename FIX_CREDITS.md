# Исправление проблемы с отображением данных кредитов

## Проблема
Данные есть в БД Oracle, но не отображаются в интерфейсах кредиты-оператор и кредиты-админка.

## Выполненные исправления

### 1. Обновлены SQL пакеты
- ✅ Добавлен `RATE_PCT` в `CRED_ADMIN_PKG.GET_PROGRAMS`
- ✅ Добавлен `RATE_PCT` в `CRED_OPERATOR_PKG.GET_PROGRAMS_FOR_PRODUCT`
- ✅ Пакеты обновлены в БД через `update_credit_packages_simple.py`

### 2. Улучшена нормализация данных
- ✅ Все методы контроллера нормализуют поля перед возвратом
- ✅ Поддержка альтернативных названий полей (id/product_id, name/product_name и т.д.)
- ✅ Правильное преобразование типов (int, float, str)

### 3. Улучшена обработка ошибок
- ✅ Добавлено логирование в JavaScript (консоль браузера)
- ✅ Улучшена обработка пустых результатов
- ✅ Добавлены сообщения об ошибках для пользователя

## Что нужно проверить

### 1. Проверьте данные в БД
Выполните в SQL Developer или через SQL*Plus:
```sql
SELECT COUNT(*) FROM CRED_PRODUCTS;  -- должно быть > 0
SELECT COUNT(*) FROM CRED_PROGRAMS; -- должно быть > 0
SELECT COUNT(*) FROM V_CRED_PRODUCTS; -- должно быть > 0
SELECT COUNT(*) FROM V_CRED_PROGRAMS; -- должно быть > 0
```

### 2. Проверьте работу пакетов
```sql
-- Тест GET_PRODUCTS
DECLARE
  cur SYS_REFCURSOR;
  v_id NUMBER;
  v_name VARCHAR2(300);
BEGIN
  CRED_OPERATOR_PKG.GET_PRODUCTS(NULL, 3, cur);
  LOOP
    FETCH cur INTO v_id, v_name, v_article, v_barcode, v_price, v_cat_id, v_cat_name, v_brand_id, v_brand_name, v_img;
    EXIT WHEN cur%NOTFOUND;
    DBMS_OUTPUT.PUT_LINE('ID: ' || v_id || ', Name: ' || v_name);
  END LOOP;
  CLOSE cur;
END;
/
```

### 3. Проверьте консоль браузера
1. Откройте кредиты-оператор или кредиты-админка
2. Нажмите F12 (открыть консоль разработчика)
3. Перезагрузите страницу (Ctrl+F5 или Cmd+Shift+R)
4. Проверьте логи в консоли:
   - Должны быть сообщения "API response: /products ..."
   - Если есть ошибки - они будут показаны

### 4. Проверьте логи сервера
Если сервер запущен, проверьте логи:
```bash
tail -f app.log
# или
ps aux | grep python
```

## Если данные все еще не отображаются

### Вариант 1: Пересоздать все объекты
```bash
python3 deploy_oracle_objects.py
```

### Вариант 2: Только обновить пакеты
```bash
python3 update_credit_packages_simple.py
```

### Вариант 3: Загрузить демо-данные заново
```bash
# Выполните только 10_demo_data.sql через SQL Developer
```

## Отладка

### Проверка через Python
```python
from controllers.credit_controller import CreditController

# Тест товаров
result = CreditController.get_products(limit=3)
print(f"Success: {result.get('success')}")
print(f"Data: {result.get('data')}")

# Тест программ
result = CreditController.get_programs()
print(f"Success: {result.get('success')}")
print(f"Data: {result.get('data')}")
```

### Проверка через API (если сервер запущен)
```bash
# Нужна авторизация, но можно проверить структуру ответа
curl -X GET "http://localhost:3003/api/credit-operator/products?limit=3" \
  -H "Cookie: session=..." \
  | python3 -m json.tool
```

## Возможные причины проблемы

1. **Пакеты не обновлены в БД** - выполните `update_credit_packages_simple.py`
2. **Данные не загружены** - выполните `deploy_oracle_objects.py` или загрузите `10_demo_data.sql`
3. **Проблема с подключением к БД** - проверьте `.env` файл
4. **Ошибка в JavaScript** - проверьте консоль браузера (F12)
5. **Кэш браузера** - очистите кэш (Ctrl+Shift+Delete) или используйте режим инкогнито

## Контакты для отладки

Если проблема не решена, предоставьте:
1. Скриншот консоли браузера (F12)
2. Логи сервера Python
3. Результат SQL запросов из пункта "Проверьте данные в БД"
