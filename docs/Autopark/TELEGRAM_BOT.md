# Autopark — телеграм-бот логиста (оперативный мониторинг)

Long-polling бот для оперативного взаимодействия логиста с модулем:
команды со сводками и пуш-уведомления о критичных событиях. Код:
`modules/autopark/scripts/autopark_bot.py`. Без сторонних SDK — Telegram
Bot API это три HTTPS-вызова (`getUpdates`/`sendMessage`), их покрывает
`urllib` из стандартной библиотеки; в venv ничего доставлять не нужно.

Бот работает на сервере рядом с приложением и читает данные напрямую
через `AutoparkStore`/`AutoparkController` — тем же кодом, что и портал.
Telegram-слой отделён: каждая команда — чистая функция «данные →
Markdown», тестируется без сети (`tests/test_autopark.py`, блок bot).

## Команды

| Команда | Ответ |
|---|---|
| `/start`, `/help` | список команд |
| `/stock` | АЗС с запасом ниже страхового, топ-10 по критичности (из `stock_days_report`) |
| `/plan` | краткий план поставок: сколько АЗС требуют, предложенные рейсы одной строкой каждый (`supply_plan`) |
| `/trips` | сегодняшние рейсы со статусами, нормой и фактом |
| `/pay [YYYY-MM]` | свод зарплаты за месяц по водителям (по умолчанию текущий) |
| `/control [N]` | рейсы с превышением лимита (км/ДТ) за N дней (по умолчанию 7) |
| `/prices` | текущие предельные цены ANRE + изменение за неделю |

## Настройка

1. В Telegram открыть **@BotFather** → `/newbot`, задать имя и username,
   скопировать токен вида `123456789:AA...`.
2. Узнать свой `chat_id` (проще всего у **@userinfobot**).
3. В `.env` в корне проекта (тот же файл, где `WALLET_DIR`) добавить:

```bash
AUTOPARK_TG_TOKEN=123456789:AA...
AUTOPARK_TG_CHAT_IDS=11111111,22222222   # белый список через запятую
```

4. Запуск:

```bash
venv/bin/python modules/autopark/scripts/autopark_bot.py            # только команды
venv/bin/python modules/autopark/scripts/autopark_bot.py --monitor  # + пуши раз в 10 мин
```

Без токена бот не гадает: печатает эту же инструкцию и выходит с кодом 2.

## Безопасность

* **Без белого списка бот не отвечает никому.** Пустой
  `AUTOPARK_TG_CHAT_IDS` — это «молчать всем», а не «отвечать всем»:
  зарплаты и остатки АЗС не должны раздаваться любому, кто нашёл бота
  по имени.
* Сообщение из чата вне списка игнорируется **молча** — без ответа,
  чтобы не подтверждать постороннему, что бот жив.
* Токен живёт только в `.env` (файл вне git и вне deploy-архива) — в
  репозиторий он не попадает.

## Мониторинг (`--monitor`)

Раз в 10 минут в том же процессе:

* **запас АЗС упал ниже страхового** — пуш во все чаты белого списка,
  не чаще 1 раза в сутки на пару АЗС/продукт;
* **рейс с превышением лимита** (км или ДТ, окно — последние 3 дня) —
  один пуш на рейс.

Антидубль хранится в локальном `autopark_bot_state.json` рядом со
скриптом. Это курсор уведомлений, а не бизнес-данные — Oracle-first
правило проекта на него не распространяется: потеря файла означает
максимум один повторный пуш, не потерю данных.

## Проверка без Telegram (`--dry-run`)

Команды исполняются локально на живых данных, ответ — в stdout:

```bash
venv/bin/python modules/autopark/scripts/autopark_bot.py \
    --dry-run /stock "/pay 2026-07" "/control 7" /prices
```

## systemd-unit (пример, по образцу artgranit.service — НЕ установлен)

```ini
[Unit]
Description=Autopark Telegram bot (logist)
After=network-online.target artgranit.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/artgranit
ExecStart=/home/ubuntu/artgranit/venv/bin/python3 modules/autopark/scripts/autopark_bot.py --monitor
EnvironmentFile=/home/ubuntu/artgranit/.env
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Установка (когда владелец решит запускать на сервере):
`sudo cp ... /etc/systemd/system/autopark-bot.service && sudo systemctl
enable --now autopark-bot`. После любых работ на сервере — стандартная
проверка `curl -I https://nufarul.eminescu.md/login` → 200.

## Тесты

`tests/test_autopark.py`, блок «Task 5 (bot)»: разбор команд (включая
`/cmd@BotName`), молчаливый отказ чату вне белого списка и при пустом
списке, форматирование `/pay` с проверкой границ месяца, антидубль
мониторинга (в сутках и на рейс, с перечитыванием состояния с диска).
Всё на моках store — без сети, wallet и Oracle.
