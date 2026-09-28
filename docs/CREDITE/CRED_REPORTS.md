# Настраиваемые отчёты

## Обзор

Модуль настраиваемых отчётов позволяет создавать отчёты, параметры, шаблоны и алгоритмы которых полностью задаются через таблицы Oracle и пакеты PL/SQL.

## Таблицы

### CRED_REPORTS

Справочник отчётов.

| Колонка | Тип | Описание |
|---------|-----|----------|
| ID | NUMBER | PK |
| CODE | VARCHAR2(50) | Уникальный код |
| NAME | VARCHAR2(200) | Название |
| DESCRIPTION | VARCHAR2(500) | Описание |
| PACKAGE_NAME | VARCHAR2(100) | Имя пакета PL/SQL |
| PROCEDURE_NAME | VARCHAR2(100) | Имя процедуры |
| TEMPLATE_TYPE | VARCHAR2(20) | table / json / custom |
| TEMPLATE_HTML | CLOB | HTML-шаблон (опционально) |
| ENABLED | CHAR(1) | Y/N |
| DISPLAY_ORDER | NUMBER | Порядок вывода |

### CRED_REPORT_PARAMS

Параметры отчётов.

| Колонка | Тип | Описание |
|---------|-----|----------|
| ID | NUMBER | PK |
| REPORT_ID | NUMBER | FK → CRED_REPORTS |
| PARAM_CODE | VARCHAR2(50) | Код параметра (для JSON) |
| PARAM_NAME | VARCHAR2(200) | Отображаемое название |
| PARAM_TYPE | VARCHAR2(20) | string / number / date / select |
| DEFAULT_VALUE | VARCHAR2(500) | Значение по умолчанию |
| REQUIRED | CHAR(1) | Y/N |
| OPTIONS_JSON | VARCHAR2(2000) | Для select: массив или `{"source":"banks"}` |
| DISPLAY_ORDER | NUMBER | Порядок в форме |

## Пакеты PL/SQL

### CRED_REPORT_LOGIC_PKG

Содержит алгоритмы отчётов (процедуры с динамическими параметрами):

- **REPORT_APPLICATIONS_BY_STATUS** — заявки по статусу и периоду  
  Параметры: `P_STATUS`, `P_DATE_FROM`, `P_DATE_TO`

- **REPORT_PROGRAMS_BY_BANK** — программы по банку с количеством заявок  
  Параметры: `P_BANK_ID`

### CRED_REPORTS_PKG

Управление и выполнение:

- **GET_REPORTS** — список активных отчётов
- **GET_REPORT_PARAMS(P_REPORT_ID)** — параметры отчёта
- **EXECUTE_REPORT(P_REPORT_ID, P_PARAMS_JSON, P_CUR)** — выполнение с JSON-параметрами

## Добавление нового отчёта

1. Создать процедуру в `CRED_REPORT_LOGIC_PKG`:
```sql
PROCEDURE REPORT_MY_NEW (
  P_PARAM1 IN VARCHAR2 DEFAULT NULL,
  P_PARAM2 IN NUMBER DEFAULT NULL,
  P_CUR    OUT SYS_REFCURSOR
);
```

2. Добавить ветку в `EXECUTE_REPORT`:
```sql
ELSIF v_proc = 'REPORT_MY_NEW' THEN
  v_p1 := JSON_VALUE(P_PARAMS_JSON, '$.param1');
  v_p2 := TO_NUMBER(JSON_VALUE(P_PARAMS_JSON, '$.param2'));
  CRED_REPORT_LOGIC_PKG.REPORT_MY_NEW(v_p1, v_p2, P_CUR);
```

3. Вставить запись в CRED_REPORTS и CRED_REPORT_PARAMS.

## API

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/credit-admin/reports` | Список отчётов |
| GET | `/api/credit-admin/reports/:id` | Отчёт по ID (для редактирования шаблона) |
| GET | `/api/credit-admin/reports/:id/params` | Параметры отчёта |
| POST | `/api/credit-admin/reports/:id/execute` | Выполнить отчёт |
| POST | `/api/credit-admin/reports/:id/export` | Экспорт в CSV, Excel, PDF |
| PUT | `/api/credit-admin/reports/:id/template` | Обновить шаблон (name, description, template_html) |

Тело execute: `{"params": {"status": "pending", "date_from": "2026-01-01"}}`  
Тело export: `{"params": {...}, "format": "csv|excel|pdf", "report_name": "..."}`

## BI-функции просмотра

При просмотре отчёта доступны:

- **Поиск** — по всем колонкам
- **Сортировка** — клик по заголовку колонки, выбор из выпадающего списка
- **Фильтр по колонке** — поле ввода под каждым заголовком
- **Экспорт** — CSV, Excel, PDF
- **Редактирование шаблона** — кнопка «Шаблон» для изменения названия, описания и конфига колонок (JSON)

## Интерфейс

Админка кредитов → **Отчёты**: выбор отчёта, ввод параметров, формирование.

## Дополнительные ресурсы

- [DDL скрипты](/UNA.md/orasldev/docs/sql)
- [API документация](/UNA.md/orasldev/docs/api)
- [Dashboard 04: Админка](/UNA.md/orasldev/docs/dashboard/04)
