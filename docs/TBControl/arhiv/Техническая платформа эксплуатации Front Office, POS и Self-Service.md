# Техническая платформа эксплуатации Front Office, POS и Self-Service

## 1. Назначение

Данный документ описывает единую техническую обвязку для эксплуатации, мониторинга, диагностики и сопровождения Front Office инфраструктуры торговой сети.

Платформа предназначена для совместной работы:

- IT отдела компании-заказчика;
- компании-разработчика программного обеспечения;
- службы эксплуатации магазинов;
- службы технической поддержки;
- системных администраторов;
- специалистов по POS и Self-Service;
- DevOps/SRE специалистов.

Основная задача платформы — обеспечить централизованный контроль состояния всех технических компонентов магазина и предоставить единый механизм обнаружения, диагностики и эскалации проблем.

В состав контролируемой инфраструктуры входят:

- POS-кассы;
- компьютеры касс;
- Self-Service / Self-Checkout кассы;
- Windows-терминалы;
- Android-терминалы;
- планшеты и handheld-устройства;
- периферийное оборудование;
- локальная сеть магазина;
- серверы магазина;
- приложения Front Office;
- приложения Back Office;
- программное обеспечение учёта магазина;
- интеграционные сервисы;
- базы данных;
- API;
- сетевые сервисы;
- интернет-каналы;
- VPN;
- системные службы;
- критические процессы.

Центральной системой мониторинга является **Zabbix**.

---

# 2. Основная концепция

Архитектура строится по принципу:

```text
                    ┌─────────────────────────┐
                    │       ZABBIX            │
                    │ Monitoring / Events     │
                    │ Dashboards / Alerting   │
                    └────────────┬────────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
                ▼                ▼                ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │ IT заказчика │ │ Разработчик  │ │   Support    │
        │              │ │              │ │              │
        └──────────────┘ └──────────────┘ └──────────────┘
                                 │
                                 │
                       ┌─────────▼─────────┐
                       │   Магазины        │
                       └─────────┬─────────┘
                                 │
              ┌──────────────────┼───────────────────┐
              │                  │                   │
              ▼                  ▼                   ▼
       ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
       │ POS / Front │    │ Self-Service│    │ Android     │
       │ Office      │    │ Checkout    │    │ Devices     │
       └─────────────┘    └─────────────┘    └─────────────┘
              │                  │                   │
              └──────────────────┼───────────────────┘
                                 │
                       ┌─────────▼─────────┐
                       │ Store Application │
                       │ / ERP / Inventory │
                       └───────────────────┘
```

Каждое устройство должно рассматриваться не как отдельный компьютер, а как часть **технического сервиса магазина**.

---

# 3. Иерархия объектов

Zabbix должен отражать физическую и логическую структуру компании.

Рекомендуемая иерархия:

```text
Company
│
├── Region
│   │
│   ├── City
│   │   │
│   │   ├── Store
│   │   │   │
│   │   │   ├── Front Office
│   │   │   │   ├── POS-01
│   │   │   │   ├── POS-02
│   │   │   │   └── POS-03
│   │   │   │
│   │   │   ├── Self-Service
│   │   │   │   ├── SCO-01
│   │   │   │   ├── SCO-02
│   │   │   │   └── SCO-03
│   │   │   │
│   │   │   ├── Android
│   │   │   │   ├── AND-01
│   │   │   │   └── AND-02
│   │   │   │
│   │   │   ├── Store Server
│   │   │   ├── Network
│   │   │   └── Peripheral
│   │   │
│   │   └── ...
│   │
│   └── ...
│
└── Central Infrastructure
    ├── Application Servers
    ├── Database
    ├── API
    ├── Integration
    └── Zabbix
```

---

# 4. Уникальная идентификация оборудования

Каждое устройство должно иметь уникальный технический идентификатор.

Например:

```text
MD-CHS-001-POS-01
MD-CHS-001-POS-02

MD-CHS-001-SCO-01
MD-CHS-001-SCO-02

MD-CHS-001-AND-01
MD-CHS-001-AND-02
```

Где:

```text
MD       = страна
CHS      = город
001      = магазин
POS      = тип устройства
01       = номер устройства
```

Для каждого объекта должны храниться:

```text
Device ID
Hostname
Serial Number
MAC Address
IP Address
Store
Department
Device Type
Operating System
Application Version
Hardware Model
Installation Date
Responsible Team
Support Level
Environment
Status
```

---

# 5. Мониторинг Windows POS

На каждый Windows POS устанавливается Zabbix Agent 2.

Контролируются как сама операционная система, так и прикладные процессы.

## 5.1 Windows

Минимальный набор:

- CPU;
- RAM;
- свободное место на дисках;
- состояние дисков;
- загрузка дисковой подсистемы;
- сетевые интерфейсы;
- доступность DNS;
- доступность Gateway;
- доступность центральных сервисов;
- время системы;
- Windows Services;
- Windows Event Log;
- количество активных процессов;
- критические системные события;
- температура оборудования, если доступна;
- состояние Windows Update.

---

# 6. Мониторинг POS-приложения

POS должен контролироваться не только на уровне Windows.

Необходимо контролировать:

```text
POS Application
│
├── Process
├── Windows Service
├── Application Version
├── Configuration Version
├── Database Connection
├── API Connection
├── Payment Service
├── Fiscal Service
├── Printer
├── Scanner
├── Cash Drawer
├── Customer Display
└── Synchronization
```

Например:

```text
POS process running
POS service running
POS application version
POS database connection
POS API latency
POS synchronization age
Last successful transaction
Last successful synchronization
```

---

# 7. Мониторинг Self-Service / SCO

Self-Service касса является отдельным типом технического объекта.

Она должна контролироваться независимо от обычного POS.

```text
SCO
│
├── Windows / Android OS
├── SCO Application
├── Scanner
├── Scale
├── Payment Terminal
├── Receipt Printer
├── Cash Acceptor
├── Cash Dispenser
├── Customer Display
├── Camera
├── Security Sensors
└── Network
```

Критические события:

```text
SCO application stopped
Scanner unavailable
Scale unavailable
Payment terminal unavailable
Printer unavailable
Cash module unavailable
Network unavailable
Device locked
Application crashed
Critical hardware error
```

---

# 8. Android-инфраструктура

Android устройства также являются полноценными объектами мониторинга.

На Android устанавливается специализированный monitoring agent / application.

Приложение должно предоставлять локальный API для мониторинга.

Например:

```text
http://127.0.0.1:PORT/health
```

Ответ:

```json
{
  "device_id": "MD-CHS-001-AND-01",
  "status": "OK",
  "application": "StoreApp",
  "version": "5.12.3",
  "battery": 87,
  "storage_free": 31.4,
  "network": true,
  "last_sync": "2026-08-07T23:51:14",
  "api": true
}
```

Zabbix получает данные через API или промежуточный gateway.

---

# 9. Контроль приложения учёта магазина

Критически важно мониторить не только оборудование.

Необходимо контролировать состояние программы, используемой сотрудниками магазина для внутреннего учёта.

Например:

```text
Store Application
│
├── Application running
├── Version
├── Database connection
├── API availability
├── Last synchronization
├── Number of pending operations
├── Queue size
├── Last successful transaction
├── Error count
└── License status
```

---

# 10. Application Health API

Каждое критическое приложение рекомендуется оснащать стандартным Health API.

Минимальный endpoint:

```text
GET /health
```

Расширенный:

```text
GET /health/details
```

Пример:

```json
{
  "status": "OK",

  "application": {
    "name": "StoreFront",
    "version": "7.4.12",
    "build": "2026.08.07.3"
  },

  "database": {
    "status": "OK",
    "latency_ms": 8
  },

  "api": {
    "status": "OK",
    "latency_ms": 32
  },

  "sync": {
    "status": "OK",
    "last_success": "2026-08-07T23:56:12Z",
    "pending": 0
  },

  "services": {
    "fiscal": "OK",
    "payment": "OK",
    "printer": "OK"
  }
}
```

Это позволяет перейти от мониторинга:

```text
"компьютер включен"
```

к мониторингу:

```text
"бизнес-сервис магазина работает"
```

---

# 11. Zabbix Templates

Все устройства должны подключаться к Zabbix через Templates.

Пример:

```text
Template Store POS
Template Store SCO
Template Android Store Device
Template Store Application
Template Windows POS
Template Linux Store Server
Template Network Device
Template Payment Terminal
Template Fiscal Device
```

Общие элементы должны наследоваться.

Например:

```text
Template Store Device
        │
        ├── Template Windows POS
        │
        ├── Template SCO
        │
        └── Template Android Device
```

---

# 12. Low-Level Discovery

Для автоматического обнаружения оборудования необходимо использовать Zabbix Low-Level Discovery.

Автоматически обнаруживаются:

- диски;
- сетевые интерфейсы;
- Windows Services;
- процессы;
- Android devices;
- приложения;
- периферийные устройства;
- Store Services.

Это позволяет не создавать вручную сотни и тысячи Items.

---

# 13. Мониторинг на уровне бизнеса

Необходимо разделять:

### Infrastructure monitoring

```text
CPU
RAM
Disk
Network
OS
Process
Service
```

### Application monitoring

```text
Application
API
Database
Queue
Synchronization
Errors
Version
```

### Business monitoring

```text
Last transaction
Transactions/hour
Synchronization delay
Number of offline POS
Number of unavailable SCO
Number of stores with degraded service
```

Именно третий уровень должен использоваться руководством и Service Desk.

---

# 14. Централизованная модель инцидентов

Все проблемы должны классифицироваться.

## P1 — Critical

Полная остановка критического сервиса.

Примеры:

```text
Store completely offline
All POS unavailable
All SCO unavailable
Payment system unavailable
Central database unavailable
Critical integration unavailable
```

## P2 — High

Серьёзная деградация.

```text
50% POS unavailable
Multiple SCO unavailable
Synchronization stopped
Payment degradation
Store server failure
```

## P3 — Medium

Проблема отдельного устройства.

```text
POS-03 offline
Printer unavailable
Android device offline
Application restart required
```

## P4 — Low

Информационные события.

```text
Low disk space
New application version
Device reboot
Configuration change
```

---

# 15. Correlation

Zabbix не должен создавать десятки одинаковых тревог при одной причине.

Например:

```text
Store network failure
        │
        ├── POS-01 unavailable
        ├── POS-02 unavailable
        ├── POS-03 unavailable
        ├── SCO-01 unavailable
        ├── SCO-02 unavailable
        └── Android devices unavailable
```

Вместо 10 независимых аварий система должна определить:

```text
ROOT CAUSE:
Store network unavailable
```

А остальные события должны быть зависимыми.

Это существенно уменьшает количество ложных инцидентов и облегчает работу IT.

---

# 16. Maintenance

Каждый магазин должен иметь собственные Maintenance Windows.

Например:

```text
Store: MD-CHS-001

Maintenance:
Sunday
02:00 - 04:00
```

Во время Maintenance:

- обновления;
- перезагрузки;
- deployment;
- изменение конфигурации;
- обслуживание оборудования

не должны создавать обычные аварийные уведомления.

---

# 17. Управление версиями

Для каждого приложения необходимо хранить версию.

Например:

```text
POS Application
7.4.12

SCO Application
3.8.4

Store Android
5.12.3
```

Zabbix должен позволять увидеть:

```text
Store
Device
Current Version
Expected Version
Version Status
```

Пример:

```text
Store 001

POS-01   7.4.12   OK
POS-02   7.4.12   OK
POS-03   7.3.9    OUTDATED
SCO-01   3.8.4    OK
AND-01   5.12.3   OK
```

---

# 18. Deployment

Мониторинг должен быть связан с процессом обновления.

Рекомендуемый цикл:

```text
Development
      │
      ▼
Build
      │
      ▼
Test
      │
      ▼
Pilot Store
      │
      ▼
Production
      │
      ▼
Zabbix verification
      │
      ▼
Health Check
      │
      ▼
Release completed
```

После deployment автоматически проверяется:

```text
Process
Version
API
Database
Synchronization
Peripheral Devices
Business Health
```

---

# 19. Взаимодействие разработчика и IT заказчика

Система должна иметь чёткое разделение ответственности.

## IT заказчика

Отвечает за:

- сеть;
- интернет;
- VPN;
- Windows;
- Android infrastructure;
- оборудование;
- локальную инфраструктуру;
- доступность магазинов;
- физические устройства.

## Компания-разработчик

Отвечает за:

- Front Office application;
- SCO application;
- Store application;
- API;
- интеграции;
- database logic;
- application errors;
- releases;
- application configuration.

## Совместная зона

```text
Monitoring
Incident Management
Deployment
Performance
Integration
Security
Capacity Planning
```

---

# 20. Доступ разработчика

Разработчик не должен получать полный административный доступ к инфраструктуре заказчика.

Доступ предоставляется по принципу:

```text
Least Privilege
```

Рекомендуемые уровни:

```text
VIEWER
OPERATOR
APPLICATION SUPPORT
SYSTEM ADMIN
ZABBIX ADMIN
```

Разработчик получает доступ только к необходимым:

- Zabbix hosts;
- dashboards;
- application metrics;
- logs;
- events;
- application API.

---

# 21. RBAC

Доступ должен управляться ролями.

Пример:

```text
Zabbix Viewer
    │
    └── Только просмотр

Store Operator
    │
    └── Только свои магазины

IT Operator
    │
    └── Все инфраструктурные события

Developer
    │
    └── Application monitoring

Support
    │
    └── Events + diagnostics

Zabbix Administrator
    │
    └── Full monitoring administration
```

---

# 22. Dashboards

Необходимо создать несколько уровней Dashboard.

## Executive Dashboard

Показывает:

```text
Total Stores
Online Stores
Stores with Problems
POS Availability
SCO Availability
Android Availability
Critical Incidents
P1/P2 incidents
Application Availability
```

## IT Dashboard

```text
CPU
RAM
Disk
Network
VPN
Servers
POS
SCO
Android
Infrastructure alerts
```

## Developer Dashboard

```text
Application availability
API latency
Application errors
Version distribution
Database performance
Synchronization
Queues
Failed transactions
```

## Store Dashboard

```text
POS-01   ONLINE
POS-02   ONLINE
POS-03   WARNING

SCO-01   ONLINE
SCO-02   OFFLINE

Android-01 ONLINE
Android-02 ONLINE
```

---

# 23. Карта магазина

Для каждого магазина рекомендуется иметь отдельный Dashboard.

Пример:

```text
STORE 001
────────────────────────────────────

NETWORK             OK
INTERNET            OK
STORE SERVER        OK

POS
01                  OK
02                  OK
03                  WARNING

SELF SERVICE
01                  OK
02                  OK
03                  OFFLINE

ANDROID
01                  OK
02                  OK

APPLICATION         OK
DATABASE             OK
SYNCHRONIZATION      OK
```

---

# 24. Notifications

Уведомления должны отправляться в зависимости от ответственности.

```text
Zabbix
 │
 ├── P1
 │    ├── IT
 │    ├── Developer
 │    └── Management
 │
 ├── P2
 │    ├── IT
 │    └── Developer
 │
 ├── P3
 │    └── Support
 │
 └── P4
      └── Dashboard
```

Каналы:

- Email;
- Microsoft Teams;
- Telegram;
- Slack;
- SMS;
- Service Desk;
- Webhook;
- REST API.

---

# 25. Webhook / API

Zabbix должен интегрироваться с внешней системой Service Desk.

Пример:

```text
Zabbix
   │
   │ Webhook
   ▼
Service Desk
   │
   ├── Incident
   ├── Assignment
   ├── SLA
   ├── Escalation
   └── Resolution
```

Каждое событие должно иметь:

```text
event_id
host
store
device
severity
problem
timestamp
owner
status
```

---

# 26. Logs

Приложения должны предоставлять структурированные логи.

Предпочтительный формат:

```json
{
  "timestamp": "2026-08-08T00:01:22Z",
  "level": "ERROR",
  "service": "POS",
  "store": "001",
  "device": "POS-03",
  "version": "7.4.12",
  "event": "PAYMENT_TIMEOUT",
  "message": "Payment terminal timeout",
  "correlation_id": "a82d91"
}
```

Рекомендуется использовать единый `correlation_id`.

Это позволяет проследить одну операцию через:

```text
POS
 ↓
Store Application
 ↓
API
 ↓
Payment Service
 ↓
Fiscal Service
 ↓
Database
```

---

# 27. Observability

Современная система должна использовать три основных направления наблюдаемости:

```text
Metrics
Logs
Traces
```

### Metrics

Zabbix.

### Logs

Централизованный Log Management.

Например:

```text
OpenSearch
Loki
Elasticsearch
```

### Traces

Для распределённых приложений:

```text
OpenTelemetry
```

---

# 28. Рекомендуемая современная архитектура

```text
                     ┌──────────────────────────┐
                     │          USERS           │
                     └────────────┬─────────────┘
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
             ▼                    ▼                    ▼
        Management               IT               Developer
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  │
                         ┌────────▼────────┐
                         │    ZABBIX       │
                         │ Metrics/Events  │
                         └────────┬────────┘
                                  │
                    ┌─────────────┼──────────────┐
                    │             │              │
                    ▼             ▼              ▼
                 Windows       Android        Network
                    │             │              │
                    ▼             ▼              ▼
                  POS/SCO     Store App      Routers
                    │             │
                    └─────────────┼──────────────┘
                                  │
                          ┌───────▼────────┐
                          │ Store Services │
                          └───────┬────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
           Database              API              Integrations
```

---

# 29. Автоматическая регистрация устройств

Новые устройства не должны регистрироваться вручную.

Рекомендуется использовать:

```text
Device Provisioning
        │
        ▼
Device Identity
        │
        ▼
Zabbix Auto Registration
        │
        ▼
Host Group
        │
        ▼
Templates
        │
        ▼
Monitoring
```

При установке устройства автоматически определяются:

```text
Store
Device Type
Operating System
Serial Number
Hostname
Application
Version
```

После чего Zabbix автоматически назначает необходимые Templates.

---

# 30. Теги Zabbix

Каждый Host должен иметь стандартный набор Tags.

Например:

```text
country=MD
city=Chisinau
store=001
device_type=POS
environment=production
application=frontoffice
owner=customer
support=developer
criticality=high
```

Tags используются для:

- фильтрации;
- корреляции;
- маршрутизации уведомлений;
- Service Desk;
- SLA;
- Dashboard;
- автоматизации.

---

# 31. SLA

Для критических сервисов необходимо определить SLA.

Пример:

```text
POS Availability       >= 99.95%
SCO Availability       >= 99.90%
Store Application      >= 99.95%
API                    >= 99.99%
Central Monitoring     >= 99.99%
```

SLA должен рассчитываться автоматически на основании данных мониторинга.

---

# 32. Capacity Monitoring

Система должна прогнозировать проблемы до их возникновения.

Например:

```text
Disk usage
Memory
CPU
Database size
Transaction volume
Queue size
Network traffic
```

Пример:

```text
Disk:

Today       72%
+30 days    81%
+60 days    91%

Forecast:
Critical in approximately 52 days
```

---

# 33. Security Monitoring

Мониторятся:

- неожиданные изменения конфигурации;
- установка неизвестного ПО;
- изменение системных служб;
- отключение Zabbix Agent;
- отключение защитных механизмов;
- изменение пользователей;
- изменение сетевых параметров;
- подозрительные процессы;
- устаревшие версии ПО.

При этом Zabbix является **элементом monitoring/security observability**, но не заменяет полноценный EDR/SIEM.

---

# 34. Backup

Критические конфигурации должны резервироваться.

Резервируются:

```text
Zabbix configuration
Templates
Dashboards
Scripts
Application configuration
Store configuration
Device inventory
```

Для приложений дополнительно:

```text
Database
Configuration
Secrets
Certificates
Integration settings
```

---

# 35. Disaster Recovery

Необходимо иметь сценарий восстановления.

Минимально:

```text
Zabbix Server failure
        ↓
Restore
        ↓
Database restore
        ↓
Configuration restore
        ↓
Agents reconnect
        ↓
Monitoring restored
```

Для центральных компонентов рекомендуется HA.

---

# 36. Change Management

Любое существенное изменение должно иметь:

```text
Change ID
Description
Reason
Owner
Affected Stores
Affected Devices
Rollback Plan
Deployment Time
Validation
Result
```

Пример:

```text
CHG-2026-0812

Application:
FrontOffice

Version:
7.4.13

Stores:
001-020

Deployment:
02:00-04:00

Rollback:
7.4.12

Validation:
Zabbix Health Check
```

---

# 37. Incident Management

Каждая проблема проходит цикл:

```text
Detection
   ↓
Classification
   ↓
Correlation
   ↓
Assignment
   ↓
Diagnosis
   ↓
Resolution
   ↓
Verification
   ↓
Closure
```

---

# 38. Root Cause Analysis

Для серьёзных аварий необходимо формировать RCA.

Структура:

```text
Incident
Date
Duration
Affected Stores
Affected Services

Root Cause

Technical Cause

Business Impact

Resolution

Preventive Action
```

---

# 39. Принцип "Everything as Code"

Конфигурация инфраструктуры должна по возможности храниться в Git.

Например:

```text
monitoring/
│
├── zabbix/
│   ├── templates/
│   ├── dashboards/
│   ├── triggers/
│   ├── discovery/
│   └── scripts/
│
├── deployment/
├── configuration/
└── documentation/
```

Изменения проходят через:

```text
Git
 ↓
Pull Request
 ↓
Review
 ↓
Test
 ↓
Deploy
```

---

# 40. GitOps для мониторинга

Изменение мониторинга не должно выполняться только вручную через GUI.

Рекомендуемый процесс:

```text
Developer / IT
      │
      ▼
Git
      │
      ▼
Review
      │
      ▼
CI
      │
      ▼
Validation
      │
      ▼
Zabbix API
      │
      ▼
Production
```

---

# 41. Автоматическая диагностика

Для типовых проблем должны существовать диагностические scripts.

Например:

```text
POS Diagnostic

1. Check network
2. Check DNS
3. Check Zabbix Agent
4. Check POS process
5. Check database
6. Check API
7. Check payment
8. Check fiscal device
9. Check printer
10. Generate diagnostic report
```

Результат:

```json
{
  "device": "POS-03",
  "network": "OK",
  "dns": "OK",
  "zabbix": "OK",
  "pos": "OK",
  "database": "OK",
  "api": "OK",
  "payment": "FAIL",
  "printer": "OK"
}
```

Это значительно сокращает время диагностики.

---

# 42. Remote Support

Удалённая техническая поддержка должна выполняться через контролируемый канал.

Должны фиксироваться:

```text
Who
When
Device
Reason
Duration
Actions
Result
```

Администратор не должен использовать общие пароли типа:

```text
admin
123456
password
```

Каждый privileged access должен быть персональным и аудируемым.

---

# 43. Device Lifecycle

Каждое устройство проходит полный жизненный цикл:

```text
Procurement
   ↓
Provisioning
   ↓
Installation
   ↓
Monitoring
   ↓
Maintenance
   ↓
Upgrade
   ↓
Replacement
   ↓
Decommission
```

Zabbix должен отражать текущий эксплуатационный статус.

---

# 44. Главный принцип архитектуры

Система должна отвечать не только на вопрос:

> "Работает ли компьютер?"

Она должна отвечать на вопрос:

> "Может ли магазин сейчас нормально обслуживать покупателя?"

Поэтому конечная модель мониторинга:

```text
Hardware
   +
Operating System
   +
Network
   +
Application
   +
Integration
   +
Business Process
   =
Store Service Health
```

---

# 45. Итоговая модель ответственности

```text
                         COMPANY
                            │
                  ┌─────────┴─────────┐
                  │                   │
             CUSTOMER IT          DEVELOPER
                  │                   │
                  └─────────┬─────────┘
                            │
                         ZABBIX
                            │
             ┌──────────────┼───────────────┐
             │              │               │
           STORE           POS             SCO
             │              │               │
             ├──────────────┼───────────────┤
             │              │               │
          Android        Windows         Self-Service
             │              │               │
             └──────────────┼───────────────┘
                            │
                    Store Applications
                            │
                 ┌──────────┴──────────┐
                 │                     │
               API                  Database
                 │                     │
                 └──────────┬──────────┘
                            │
                       Business Service
```

---

# 46. Целевое состояние

В результате компания получает единую эксплуатационную платформу, в которой:

1. Все POS автоматически зарегистрированы.
2. Все Self-Service кассы контролируются.
3. Все Android устройства контролируются.
4. Приложения контролируются на уровне процессов и API.
5. Версии ПО видны централизованно.
6. Проблемы автоматически классифицируются.
7. Связанные аварии объединяются.
8. Ответственные команды получают только свои события.
9. Разработчик видит application-level проблемы.
10. IT заказчика видит infrastructure-level проблемы.
11. Руководство видит состояние магазинов.
12. Service Desk получает автоматически созданные инциденты.
13. Все изменения и действия аудируются.
14. Мониторинг интегрирован с deployment.
15. Доступ управляется RBAC.
16. Метрики, логи и трассировки объединяются в единую observability-модель.
17. Система позволяет выявлять проблемы до того, как их заметит пользователь магазина.
18. Эксплуатация становится управляемой как единый технический сервис, а не как набор отдельных компьютеров.

---

# 47. Ключевой KPI платформы

Главный KPI системы:

```text
Customer-facing Store Service Availability
```

а не:

```text
Number of online computers
```

Цель мониторинга — обеспечить максимальную доступность:

```text
POS
+
Self-Service
+
Payments
+
Fiscalization
+
Store Application
+
Inventory
+
Synchronization
```

для конечного бизнес-процесса:

```text
Покупатель → Магазин → Продажа → Оплата → Фискализация → Учёт → Синхронизация
```

Именно эта цепочка является конечным объектом мониторинга и эксплуатации.