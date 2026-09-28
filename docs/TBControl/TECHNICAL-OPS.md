# TECHNICAL-OPS.md
# Единая платформа эксплуатации Front Office, POS, Self-Service и Store Applications

**Версия:** 1.0  
**Дата:** 2026-08-08  
**Статус:** Target Architecture / Technical Specification

---

## 1. Назначение

Документ определяет целевую техническую архитектуру платформы мониторинга, диагностики, эксплуатации и сопровождения магазинов торговой сети.

Платформа объединяет:

- IT отдел компании-заказчика;
- компанию-разработчика;
- Service Desk / техническую поддержку;
- магазины;
- POS-кассы;
- Self-Service / Self-Checkout кассы;
- Windows-компьютеры;
- Android-устройства;
- Store Applications;
- Front Office applications;
- периферийное оборудование;
- локальную инфраструктуру магазинов;
- центральные серверы;
- API и интеграции.

Центральным компонентом мониторинга является **Zabbix**.

Основной принцип:

> Мониторить необходимо не компьютер как таковой, а способность магазина выполнять бизнес-операции.

---

# 2. Цели платформы

## 2.1. Основные цели

Платформа должна обеспечивать:

1. Централизованный мониторинг всех магазинов.
2. Автоматическую регистрацию новых устройств.
3. Мониторинг Windows POS.
4. Мониторинг Self-Service касс.
5. Мониторинг Android-устройств.
6. Мониторинг приложений.
7. Мониторинг API и интеграций.
8. Мониторинг синхронизации.
9. Мониторинг периферии.
10. Централизованное управление событиями.
11. Автоматическую корреляцию событий.
12. Автоматическое создание инцидентов.
13. Разделение ответственности между заказчиком и разработчиком.
14. Контроль версий программного обеспечения.
15. Контроль SLA.
16. Автоматическую диагностику.
17. Аудит административных действий.
18. Предиктивный мониторинг.
19. Интеграцию с CI/CD.
20. Единую observability-модель Metrics + Logs + Traces.

---

# 3. Архитектурные принципы

## 3.1. Everything is a service

Магазин рассматривается как набор взаимосвязанных сервисов:

```text
Store
 ├── Network
 ├── POS
 ├── Self-Service
 ├── Android
 ├── Store Application
 ├── Payment
 ├── Fiscalization
 ├── Inventory
 └── Synchronization
```

## 3.2. Business-first monitoring

Низкоуровневый мониторинг:

```text
CPU
RAM
Disk
Network
Process
Service
```

является только фундаментом.

Основной объект контроля:

```text
Can the store sell?
```

---

# 4. Общая архитектура

```text
                         ┌───────────────────────┐
                         │      MANAGEMENT       │
                         └───────────┬───────────┘
                                     │
                         ┌───────────▼───────────┐
                         │       DASHBOARDS      │
                         └───────────┬───────────┘
                                     │
       ┌─────────────────────────────┼─────────────────────────────┐
       │                             │                             │
       ▼                             ▼                             ▼
┌──────────────┐             ┌──────────────┐             ┌──────────────┐
│ CUSTOMER IT  │             │  DEVELOPER   │             │   SUPPORT    │
└──────┬───────┘             └──────┬───────┘             └──────┬───────┘
       │                            │                            │
       └────────────────────────────┼────────────────────────────┘
                                    │
                           ┌────────▼────────┐
                           │     ZABBIX       │
                           │                 │
                           │ Metrics         │
                           │ Events          │
                           │ Triggers        │
                           │ Discovery       │
                           │ Alerting        │
                           └────────┬────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
           Zabbix Proxy       Zabbix Agent 2      Android Agent
                 │                  │                  │
                 └──────────────────┼──────────────────┘
                                    │
                              ┌─────▼─────┐
                              │   STORE   │
                              └─────┬─────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
      POS / FO                  SELF-SERVICE              ANDROID
          │                         │                         │
          └─────────────────────────┼─────────────────────────┘
                                    │
                           ┌────────▼────────┐
                           │ Store Services  │
                           └────────┬────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 ▼                  ▼                  ▼
               API              DATABASE          INTEGRATIONS
```

---

# 5. Компоненты

## 5.1. Zabbix Server

Центральный компонент.

Отвечает за:

- hosts;
- templates;
- items;
- triggers;
- discovery;
- events;
- correlation;
- alerting;
- dashboards;
- SLA;
- API;
- inventory.

Рекомендуется размещать Zabbix Server в центральной инфраструктуре заказчика.

---

# 6. Zabbix Proxy

Для распределённой сети магазинов рекомендуется использовать Zabbix Proxy.

Схема:

```text
                    ZABBIX SERVER
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
           Proxy-1    Proxy-2    Proxy-3
              │          │          │
           Stores       Stores      Stores
```

Proxy применяется для:

- уменьшения WAN-трафика;
- локального сбора данных;
- работы при нестабильном канале;
- изоляции магазинов;
- масштабирования.

---

# 7. Zabbix Agent 2

На Windows POS и Windows SCO используется Zabbix Agent 2.

Контролируется:

```text
OS
CPU
RAM
Disk
Network
Services
Processes
Event Log
Applications
Custom scripts
Application API
```

Agent должен запускаться как системная служба.

---

# 8. Android Monitoring Agent

Android не должен контролироваться только через ping.

На Android устанавливается специальное monitoring application.

Она предоставляет локальный или защищённый API:

```text
GET /health
GET /metrics
GET /version
GET /diagnostics
```

Пример:

```json
{
  "device_id": "MD-CHS-001-AND-01",
  "status": "OK",
  "application": "StoreApp",
  "version": "5.12.3",
  "battery": 87,
  "storage_free_mb": 32100,
  "network": true,
  "last_sync": "2026-08-08T00:01:12Z"
}
```

Zabbix получает показатели через поддерживаемый агент/gateway/API механизм.

---

# 9. Store Inventory

Каждое устройство должно иметь технический паспорт.

Минимальные поля:

```text
device_id
hostname
serial_number
asset_id
store_id
device_type
manufacturer
model
os
os_version
application
application_version
ip
mac
installation_date
status
owner
support_group
criticality
```

---

# 10. Идентификация

Формат:

```text
<COUNTRY>-<CITY>-<STORE>-<TYPE>-<NUMBER>
```

Примеры:

```text
MD-CHS-001-POS-01
MD-CHS-001-POS-02
MD-CHS-001-SCO-01
MD-CHS-001-AND-01
MD-CHS-001-SRV-01
```

---

# 11. Zabbix Host Groups

Рекомендуемая структура:

```text
Stores
├── Moldova
│   ├── Chisinau
│   │   ├── Store-001
│   │   ├── Store-002
│   │   └── Store-003
│   └── Balti
│       └── Store-101
│
Central
├── Servers
├── Databases
├── APIs
└── Network
```

Дополнительно применяются Tags.

---

# 12. Zabbix Tags

Минимальный набор:

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

- event routing;
- alerting;
- dashboards;
- correlation;
- SLA;
- Service Desk.

---

# 13. Templates

## 13.1. Базовые Templates

```text
Template OS Windows
Template OS Linux
Template Network Device
```

## 13.2. POS

```text
Template Store POS
Template POS Application
Template POS Peripheral
```

## 13.3. Self-Service

```text
Template Store SCO
Template SCO Application
Template SCO Peripheral
```

## 13.4. Android

```text
Template Android Device
Template Android Store Application
```

## 13.5. Store

```text
Template Store Health
Template Store Synchronization
Template Store Business KPI
```

---

# 14. Low-Level Discovery

LLD используется для автоматического обнаружения:

- дисков;
- сетевых интерфейсов;
- Windows Services;
- процессов;
- периферийных устройств;
- приложений;
- Android endpoints;
- Store Services.

Новые объекты должны появляться в мониторинге автоматически.

---

# 15. Windows POS Monitoring

## System

```text
CPU utilization
Memory utilization
Disk utilization
Disk latency
Free disk space
Network traffic
Network errors
System uptime
```

## Services

```text
Zabbix Agent
POS Service
Fiscal Service
Payment Service
Store Service
```

## Processes

```text
POS.exe
StoreApp.exe
Fiscal.exe
Payment.exe
```

## Event Log

Контролируются:

- application crashes;
- service failures;
- disk errors;
- system errors;
- security events;
- unexpected shutdowns.

---

# 16. POS Application Monitoring

Каждый POS должен предоставлять:

```text
Process status
Application version
Configuration version
Database status
API status
Payment status
Fiscal status
Printer status
Scanner status
Cash drawer status
Last transaction
Last synchronization
```

---

# 17. Self-Service Monitoring

SCO контролируется как комплекс.

```text
SCO
├── OS
├── Application
├── Scanner
├── Scale
├── Payment
├── Printer
├── Cash Acceptor
├── Cash Dispenser
├── Display
├── Camera
└── Network
```

---

# 18. Android Monitoring

Минимальный набор:

```text
Online status
Battery
Storage
Memory
Network
Application process
Application version
API
Last synchronization
Pending operations
Last successful operation
```

---

# 19. Health API

Все критические приложения должны реализовывать стандартный Health API.

## /health

Быстрая проверка.

Ответ:

```json
{
  "status": "OK"
}
```

## /health/details

Расширенная проверка.

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
    "pending": 0
  }
}
```

---

# 20. Business Health

Для магазина создаётся агрегированный показатель:

```text
STORE_HEALTH
```

Он определяется из:

```text
Network
+
POS
+
SCO
+
Payment
+
Fiscalization
+
Store Application
+
Inventory
+
Synchronization
```

Пример:

```text
STORE_HEALTH = OK
STORE_HEALTH = DEGRADED
STORE_HEALTH = CRITICAL
```

---

# 21. Store Health Model

```text
                    STORE
                      │
        ┌─────────────┼─────────────┐
        │             │             │
      POS            SCO          Android
        │             │             │
        └─────────────┼─────────────┘
                      │
                 APPLICATION
                      │
          ┌───────────┼───────────┐
          │           │           │
        API        DATABASE       SYNC
          │           │           │
          └───────────┼───────────┘
                      │
                STORE HEALTH
```

---

# 22. Business KPI

Рекомендуемые показатели:

```text
POS Availability
SCO Availability
Store Application Availability
Payment Availability
Fiscalization Availability
Synchronization Delay
Last Successful Transaction
Offline POS Count
Offline SCO Count
Failed Transactions
Pending Operations
```

---

# 23. Event Severity

| Level | Назначение | Пример |
|---|---|---|
| P1 | Critical | магазин не может продавать |
| P2 | High | существенная деградация |
| P3 | Medium | проблема одного устройства |
| P4 | Low | информационное событие |

---

# 24. P1

Примеры:

```text
All POS unavailable
All SCO unavailable
Store network unavailable
Payment unavailable
Fiscalization unavailable
Central database unavailable
Critical API unavailable
```

P1 автоматически направляется:

```text
Customer IT
Developer
Service Desk
Management
```

---

# 25. P2

```text
50% POS unavailable
Multiple SCO unavailable
Synchronization stopped
Payment degradation
Store server unavailable
```

---

# 26. P3

```text
Single POS offline
Single SCO offline
Printer failure
Scanner failure
Android device offline
Application restart required
```

---

# 27. P4

```text
Low disk space
New software version
Configuration change
Reboot
Informational message
```

---

# 28. Event Correlation

Пример:

```text
NETWORK FAILURE
      │
      ├── POS-01 unavailable
      ├── POS-02 unavailable
      ├── POS-03 unavailable
      ├── SCO-01 unavailable
      ├── SCO-02 unavailable
      └── Android unavailable
```

Итоговый инцидент:

```text
ROOT CAUSE:
Store network unavailable
```

Все downstream events должны быть suppressed/dependent, чтобы не создавать event storm.

---

# 29. Dependency Model

Zabbix должен использовать зависимости:

```text
Store Network
      │
      ├── POS-01
      ├── POS-02
      ├── POS-03
      ├── SCO-01
      └── Android
```

Если сеть недоступна, события конечных устройств не должны создавать отдельные P1.

---

# 30. Application Version Monitoring

Для каждого приложения:

```text
Current Version
Expected Version
Release Channel
Build
Deployment Date
Status
```

Пример:

```text
POS-01    7.4.12    OK
POS-02    7.4.12    OK
POS-03    7.3.9     OUTDATED
SCO-01    3.8.4     OK
AND-01    5.12.3    OK
```

---

# 31. Release Channels

Рекомендуются:

```text
DEV
TEST
PILOT
PRODUCTION
```

Deployment:

```text
DEV
 ↓
TEST
 ↓
PILOT
 ↓
PRODUCTION
```

---

# 32. Deployment Verification

После deployment автоматически выполняются:

```text
Process check
Version check
Health check
Database check
API check
Synchronization check
Peripheral check
Business transaction check
```

Результат:

```text
DEPLOYMENT = SUCCESS
```

или:

```text
DEPLOYMENT = FAILED
```

---

# 33. Maintenance Windows

Каждый магазин должен иметь собственное maintenance window.

Пример:

```text
Store: 001
Sunday
02:00 - 04:00
```

В этот период:

- плановые перезапуски;
- обновления;
- deployment;
- конфигурационные изменения

не создают обычные аварийные уведомления.

---

# 34. Dashboard Levels

## Executive

```text
Total Stores
Online Stores
Degraded Stores
Critical Stores
POS Availability
SCO Availability
Application Availability
P1
P2
SLA
```

## IT

```text
Network
Servers
POS
SCO
Android
CPU
RAM
Disk
VPN
Infrastructure events
```

## Developer

```text
Application availability
API latency
Application errors
Version distribution
Database
Synchronization
Queues
Failed operations
```

## Store

```text
POS-01 OK
POS-02 OK
POS-03 WARNING

SCO-01 OK
SCO-02 OFFLINE

Android-01 OK

Store Application OK
Synchronization OK
```

---

# 35. Service Desk Integration

Архитектура:

```text
ZABBIX
   │
   │ Webhook/API
   ▼
SERVICE DESK
   │
   ├── Incident
   ├── Assignment
   ├── SLA
   ├── Escalation
   └── Closure
```

Incident должен содержать:

```text
event_id
store
device
service
severity
problem
timestamp
owner
status
zabbix_url
```

---

# 36. Responsibility Model

## Customer IT

Отвечает за:

- LAN;
- WAN;
- Internet;
- VPN;
- Windows;
- Android infrastructure;
- hardware;
- printers;
- scanners;
- local servers;
- network equipment.

## Developer

Отвечает за:

- Front Office;
- POS application;
- SCO application;
- Store Application;
- API;
- integrations;
- application database logic;
- application errors;
- releases.

## Shared

Совместная ответственность:

```text
Monitoring
Incident Management
Deployment
Performance
Security
Integration
SLA
Root Cause Analysis
```

---

# 37. RBAC

Рекомендуемые роли:

```text
Zabbix Viewer
Store Operator
IT Operator
Developer
Support Engineer
Zabbix Administrator
Security Auditor
```

Developer должен видеть application monitoring, но не получать полный administrative access к инфраструктуре заказчика.

---

# 38. Least Privilege

Все privileged actions должны:

- выполняться персональными учётными записями;
- иметь MFA;
- логироваться;
- иметь ограниченный scope;
- иметь срок действия при необходимости.

Запрещены общие privileged accounts без аудита.

---

# 39. Remote Diagnostics

Для каждого типа устройства создаётся стандартный diagnostic workflow.

## POS

```text
Network
 ↓
DNS
 ↓
Gateway
 ↓
Zabbix Agent
 ↓
POS Process
 ↓
Database
 ↓
API
 ↓
Payment
 ↓
Fiscalization
 ↓
Peripheral
```

---

# 40. Diagnostic Report

Пример:

```json
{
  "device": "MD-CHS-001-POS-03",
  "network": "OK",
  "dns": "OK",
  "gateway": "OK",
  "zabbix": "OK",
  "pos": "OK",
  "database": "OK",
  "api": "OK",
  "payment": "FAIL",
  "fiscal": "OK",
  "printer": "OK"
}
```

---

# 41. Logs

Приложения должны использовать structured logging.

Пример:

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

---

# 42. Observability Stack

Рекомендуемая модель:

```text
Metrics
   │
   └── Zabbix

Logs
   │
   └── OpenSearch / Loki / Elasticsearch

Traces
   │
   └── OpenTelemetry
```

Zabbix является центральной системой инфраструктурного monitoring/event management, но не обязан заменять специализированные системы логирования и tracing.

---

# 43. Correlation ID

Каждая бизнес-операция должна иметь correlation ID.

Пример:

```text
POS
 ↓
Store API
 ↓
Payment API
 ↓
Fiscal API
 ↓
Database
```

Один:

```text
correlation_id = 8f7a31
```

должен позволять найти операцию во всех системах.

---

# 44. Auto Registration

Новый POS:

```text
Install Agent
      ↓
Agent connects
      ↓
Zabbix Auto Registration
      ↓
Detect Tags
      ↓
Assign Host Group
      ↓
Assign Templates
      ↓
Start Monitoring
```

---

# 45. Device Provisioning

Рекомендуемый lifecycle:

```text
Procurement
 ↓
Asset registration
 ↓
Provisioning
 ↓
Application installation
 ↓
Zabbix registration
 ↓
Health Check
 ↓
Production
```

---

# 46. GitOps

Конфигурация мониторинга должна храниться в Git.

Структура:

```text
monitoring/
├── zabbix/
│   ├── templates/
│   ├── triggers/
│   ├── discovery/
│   ├── dashboards/
│   ├── scripts/
│   └── webhooks/
│
├── deployment/
├── configuration/
└── documentation/
```

Изменения:

```text
Git
 ↓
Pull Request
 ↓
Review
 ↓
Validation
 ↓
Deploy
```

---

# 47. Zabbix API

Zabbix API используется для:

- provisioning;
- auto-registration;
- configuration;
- template deployment;
- dashboard deployment;
- inventory;
- integration;
- automation.

Не рекомендуется вручную создавать сотни однотипных объектов.

---

# 48. Infrastructure as Code

Для инфраструктуры рекомендуется:

```text
Terraform
Ansible
Git
CI/CD
```

Zabbix configuration должна быть максимально reproducible.

---

# 49. Secrets

Пароли, tokens, API keys и certificates не должны храниться в Git.

Рекомендуется использовать:

```text
Vault
Cloud Secret Manager
Password Manager
Enterprise Secret Store
```

---

# 50. Security

Мониторинг должен выявлять:

- неизвестные процессы;
- отключение агента;
- изменение служб;
- изменение конфигурации;
- неизвестное ПО;
- изменение пользователей;
- отключение защитных механизмов;
- устаревшие версии.

Zabbix не заменяет:

```text
EDR
SIEM
IAM
MDM
```

Он является частью общей security/observability architecture.

---

# 51. SLA

Рекомендуемые показатели:

```text
POS Availability              >= 99.95%
SCO Availability              >= 99.90%
Store Application             >= 99.95%
Critical API                  >= 99.99%
Monitoring Platform           >= 99.99%
```

Фактические значения должны быть согласованы договором.

---

# 52. Capacity Planning

Мониторятся:

```text
CPU
RAM
Disk
Database size
Transaction volume
Network traffic
Queue size
Synchronization delay
```

Необходимо использовать прогнозирование.

Пример:

```text
Disk:
72% now
81% forecast +30d
91% forecast +60d

Prediction:
Critical in 52 days
```

---

# 53. Backup

Резервируются:

```text
Zabbix Database
Zabbix Configuration
Templates
Dashboards
Scripts
Application Configuration
Store Configuration
Integration Configuration
```

---

# 54. Disaster Recovery

Минимальный сценарий:

```text
Zabbix failure
 ↓
Provision replacement
 ↓
Restore database
 ↓
Restore configuration
 ↓
Start services
 ↓
Agents reconnect
 ↓
Validate monitoring
```

Для критической инфраструктуры рекомендуется HA.

---

# 55. Change Management

Каждое существенное изменение имеет:

```text
Change ID
Description
Reason
Owner
Affected Stores
Affected Devices
Deployment Window
Rollback Plan
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

# 56. Incident Lifecycle

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

# 57. Root Cause Analysis

Для P1/P2:

```text
Incident ID
Date
Duration
Affected Stores
Affected Services

Root Cause

Technical Cause

Business Impact

Resolution

Corrective Action

Preventive Action
```

---

# 58. Store Topology

Каждый магазин должен иметь логическую topology map:

```text
Internet
   │
Router
   │
Switch
   │
   ├── POS-01
   ├── POS-02
   ├── POS-03
   ├── SCO-01
   ├── SCO-02
   ├── Android
   └── Store Server
```

---

# 59. Business Transaction Monitoring

Для критического магазина рекомендуется synthetic transaction.

Пример:

```text
Create test transaction
 ↓
POS
 ↓
Store Application
 ↓
Payment Test Environment
 ↓
Fiscal Test
 ↓
Database
 ↓
Synchronization
```

Результат:

```text
BUSINESS_TRANSACTION = OK
```

Это наиболее высокий уровень контроля.

---

# 60. Monitoring Maturity Model

## Level 1 — Infrastructure

```text
Ping
CPU
RAM
Disk
```

## Level 2 — Application

```text
Process
Service
API
Database
```

## Level 3 — Service

```text
POS
SCO
Store Application
Synchronization
```

## Level 4 — Business

```text
Transaction
Payment
Fiscalization
Inventory
```

## Level 5 — Predictive

```text
Forecast
Anomaly Detection
Capacity Planning
Root Cause Analysis
Automated Remediation
```

Целевое состояние — Level 4–5.

---

# 61. Automated Remediation

Для безопасных типовых проблем допускается автоматическое исправление.

Пример:

```text
POS Service stopped
       ↓
Zabbix detects
       ↓
Diagnostic
       ↓
Restart Service
       ↓
Health Check
       ↓
OK
```

Если исправление не помогло:

```text
Create Incident
Escalate
```

Автоматические действия должны иметь:

- whitelist;
- audit;
- timeout;
- retry limit;
- rollback;
- permission control.

---

# 62. Не допускается автоматический remediation

Без отдельного согласования нельзя автоматически:

- менять финансовые данные;
- удалять транзакции;
- изменять базу данных;
- менять production configuration;
- отключать security controls;
- менять сетевую маршрутизацию;
- устанавливать неизвестное ПО.

---

# 63. Пример полного сценария

Сбой оплаты на POS-03:

```text
Payment timeout
      ↓
POS reports ERROR
      ↓
Zabbix detects
      ↓
Trigger P3
      ↓
Diagnostic
      ↓
Payment terminal unavailable
      ↓
Check network
      ↓
Network OK
      ↓
Create incident
      ↓
Assign to Customer IT / Payment Support
```

Если одновременно проблема на всех POS:

```text
POS-01 FAIL
POS-02 FAIL
POS-03 FAIL
       ↓
Correlation
       ↓
Payment Service unavailable
       ↓
P1/P2
```

---

# 64. Developer / Customer IT Boundary

```text
                    ZABBIX
                       │
          ┌────────────┴────────────┐
          │                         │
    INFRASTRUCTURE             APPLICATION
          │                         │
    Customer IT                  Developer
          │                         │
    Network                     POS
    Windows                     SCO
    Hardware                    Store App
    VPN                         API
    Android OS                  Integrations
    Servers                     Application DB logic
```

---

# 65. Communication Protocol

Все технические взаимодействия должны использовать единые идентификаторы:

```text
Store ID
Device ID
Incident ID
Change ID
Release ID
Correlation ID
```

Например:

```text
Store: MD-CHS-001
Device: MD-CHS-001-POS-03
Incident: INC-2026-10452
Change: CHG-2026-0812
Release: REL-7.4.13
Correlation: 8f7a31
```

---

# 66. Минимальный обязательный набор для Production

Перед вводом магазина в эксплуатацию должно быть выполнено:

```text
[ ] Store registered
[ ] Devices registered
[ ] Zabbix Agent installed
[ ] Android Agent installed
[ ] Templates assigned
[ ] Tags configured
[ ] Dependencies configured
[ ] Health API available
[ ] POS monitored
[ ] SCO monitored
[ ] Android monitored
[ ] Application monitored
[ ] Network monitored
[ ] Synchronization monitored
[ ] Dashboard available
[ ] Alerts tested
[ ] Service Desk integration tested
[ ] Maintenance window configured
[ ] Responsible teams assigned
```

---

# 67. Acceptance Test

Магазин считается готовым только после успешного прохождения:

```text
Infrastructure Test
Application Test
Payment Test
Fiscal Test
Synchronization Test
Monitoring Test
Alert Test
Recovery Test
```

---

# 68. Главный показатель

Главный KPI платформы:

> **Customer-facing Store Service Availability**

а не количество доступных компьютеров.

Целевая цепочка:

```text
Покупатель
   ↓
POS / SCO
   ↓
Продажа
   ↓
Оплата
   ↓
Фискализация
   ↓
Store Application
   ↓
Inventory
   ↓
Synchronization
   ↓
Central Systems
```

---

# 69. Target State

В целевом состоянии:

- новый POS появляется в мониторинге автоматически;
- новый SCO появляется автоматически;
- Android устройства регистрируются автоматически;
- приложение сообщает свою версию;
- приложение предоставляет Health API;
- Zabbix контролирует инфраструктуру;
- события автоматически классифицируются;
- события коррелируются;
- Service Desk получает инцидент;
- ответственная команда определяется автоматически;
- разработчик видит application-level проблемы;
- IT заказчика видит infrastructure-level проблемы;
- руководство видит состояние сети магазинов;
- deployment автоматически проверяется;
- конфигурация хранится в Git;
- privileged actions аудируются;
- критические проблемы имеют RCA;
- SLA рассчитывается автоматически;
- возможно автоматическое исправление типовых проблем.

---

# 70. Конечная модель

```text
                         BUSINESS
                            │
                            ▼
                    STORE AVAILABILITY
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
         POS               SCO             ANDROID
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                     STORE APPLICATION
                            │
             ┌──────────────┼──────────────┐
             │              │              │
            API          DATABASE         SYNC
             │              │              │
             └──────────────┼──────────────┘
                            │
                         ZABBIX
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
    CUSTOMER IT         DEVELOPER            SUPPORT
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                       SERVICE DESK
```

---

# 71. Результат

Данная архитектура превращает Zabbix из простой системы:

```text
"серверы и компьютеры доступны"
```

в центральную эксплуатационную платформу:

```text
"мы знаем, работает ли каждый магазин,
почему он не работает,
кто отвечает за проблему,
что именно сломалось,
как это диагностировать,
как это исправить,
и когда проблема была устранена."
```

Именно такая модель должна использоваться как техническая граница между **IT заказчика**, **компанией-разработчиком** и **эксплуатацией торговой сети**.

---

# 72. Monitoring Center (кассы: оборудование + Front Office)

Современный центр мониторинга касс. Для каждой POS/SCO-кассы ведутся
**два независимых контура телеметрии**:

```text
Касса
 ├── HW-контур (касса как компьютер)
 │     CPU, RAM, Disk, Uptime, Network
 └── APP-контур (Front Office внутри)
       Process status, Latency, Transactions/hour,
       Application errors, Version, Last transaction
```

## 72.1. Временные разрезы

Обязательные разрезы по каждой кассе:

```text
NOW        актуальное состояние (последний heartbeat)
TODAY      текущий день (агрегаты: avg/max/сумма)
WEEK       последние 7 дней (по дням)
PERIOD     произвольный период (from/to, агрегация по часам/дням)
```

## 72.2. Хранение

Телеметрия — append-only time series `TBC_METRIC_SAMPLES`:

```text
DEVICE_ID | SCOPE (hw/app) | METRIC | NUM_VALUE | SAMPLED_AT
```

Метрики HW: `cpu`, `ram`, `disk`, `uptime`.
Метрики APP: `app_latency`, `tx_count`, `app_errors`.

Источник данных — heartbeat агентов (раздел 8): каждый heartbeat
дополнительно материализуется в сэмплы временного ряда.

## 72.3. UI

Панель «Мониторинг касс»: выбор кассы → карточка NOW + графики
(sparkline/линии) по каждому контуру, переключатели Сегодня / 7 дней /
Период, сводная таблица по всем кассам с агрегатами за день и неделю.

---

# 73. Processing Center (обмен данными)

Магазины работают по многоуровневой цепочке репликации:

```text
POS (SQLite на устройстве)
   │  upload: продажи, чеки, Z-отчёты
   ▼
Промежуточные серверы магазина (1..N на магазин)
   │  консолидация, буферизация
   ▼
Центральный сервер офиса
   │
   ▼
Сервер бэк-офиса
```

Данные могут теряться/застревать **на любом звене**: не доходить из
SQLite касс до промежуточных серверов, и из промежуточных/центрального —
до бэк-офиса. Каждое звено обмена — отдельный контролируемый **поток
(flow)**.

## 73.1. Модель потоков

```text
TBC_FLOWS: источник (касса или узел) → узел-приёмник
  FLOW_TYPE:  sales / docs / prices / stock / sync
  STATUS:     OK / LAGGING / STALLED / FAIL
  LAG_MIN:    отставание в минутах
  PENDING:    накопленные неотправленные строки
  LAST_OK_AT: последняя успешная передача
```

Журнал передач — append-only `TBC_FLOW_LOG` (батчи: отправлено/принято
строк, статус, ошибка).

## 73.2. Правила статусов

```text
OK       lag <= 2 x schedule
LAGGING  lag > 2 x schedule, данные идут
STALLED  передач нет > 6 x schedule, pending растёт
FAIL     последний батч завершился ошибкой
```

## 73.3. Узлы обработки (серверы)

Промежуточные серверы магазинов, центральный сервер и сервер бэк-офиса —
реестр `TBC_NODES` с мониторингом трёх уровней:

```text
1. Оборудование:  CPU, RAM, Disk, статус, last seen
2. Приложение:    сервис обмена/консолидации, версия, статус
3. База данных:   движок, версия, статус, размер, соединения
```

Поддерживаемые движки БД:

```text
oracle | sqlite | mssql | mysql | postgres
```

(SQLite — на кассах и малых узлах; промежуточные серверы — любой движок;
центральный/бэк-офис — как правило Oracle/MSSQL/PostgreSQL.)

## 73.4. UI

Панель «Processing центр»: сводка (потоки по статусам, суммарный
pending), карточки узлов (HW + APP + DB), таблица потоков по цепочке
POS → магазин → центр → бэк-офис, журнал батчей по каждому потоку.

---

# 74. AI Diagnostic Dossiers (MD-досье сбоев)

При сбойной ситуации (P1/P2 событие, инцидент, STALLED/FAIL поток,
отказ узла) платформа генерирует **исчерпывающее MD-досье** — единый
markdown-документ, содержащий всю информацию для диагностики:

```text
- описание сбоя (событие/инцидент/поток) и его контекст
- паспорт устройства/узла + текущие метрики
- STORE_HEALTH магазина и соседние открытые события
- последние health checks и диагностика
- версии ПО (Current vs Expected)
- состояние потоков обмена узла/кассы (lag, pending, ошибки)
- журнал последних передач
- журнал аудита по объекту
- рекомендуемый диагностический workflow (раздел 39)
```

## 74.1. Назначение

Досье читается **внешними AI-провайдерами** (LLM-агентами): по
защищённому URL AI-система получает полный контекст сбоя и может на
лету диагностировать проблему и — при наличии доступа — устранять её
(перезапуск сервиса, повторная отправка батча, rollback версии) в
рамках whitelist-правил раздела 61.

## 74.2. Доступ

```text
GET /api/tbc/ai/dossier/<code>.md?token=<ACCESS_TOKEN>
```

- досье хранится в Oracle (CLOB), выдаётся как text/markdown;
- каждый документ имеет собственный секретный ACCESS_TOKEN;
- credentials для активных действий AI-агенту выдаются отдельно
  (Vault/Secret Store, раздел 49) и в досье не включаются;
- аудит каждой генерации и каждого чтения — в журнале модуля.

## 74.3. Генерация

```text
Автоматически: инцидент из события P1/P2
Вручную:       кнопка «AI-досье» у события / инцидента / потока
```

---

# 75. Итоговая модель данных мониторинга

```text
Кассы:      TBC_DEVICES + TBC_METRIC_SAMPLES (hw/app time series)
Узлы:       TBC_NODES (store_srv / central / backoffice; oracle|sqlite|mssql|mysql|postgres)
Потоки:     TBC_FLOWS + TBC_FLOW_LOG (POS → магазин → центр → бэк-офис)
Сбои:       TBC_EVENTS / TBC_INCIDENTS
AI:         TBC_AI_DOSSIERS (MD-досье, CLOB + ACCESS_TOKEN)
```
