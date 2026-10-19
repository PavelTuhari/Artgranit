#!/usr/bin/env python3
"""Autopark — телеграм-бот логиста: команды и мониторинг (long polling).

    venv/bin/python modules/autopark/scripts/autopark_bot.py            # polling
    venv/bin/python modules/autopark/scripts/autopark_bot.py --monitor  # + пуши
    venv/bin/python modules/autopark/scripts/autopark_bot.py \
        --dry-run /stock "/pay 2026-07" "/control 7"                    # без API

Сознательно без сторонних SDK: Telegram Bot API — это три HTTPS-вызова
(getUpdates/sendMessage/getMe), urllib из стандартной библиотеки
покрывает их целиком, а бот живёт на сервере рядом с приложением и не
должен тянуть в venv лишние зависимости.

Конфигурация — из окружения/.env в корне проекта:

    AUTOPARK_TG_TOKEN=123456:ABC...     токен из @BotFather
    AUTOPARK_TG_CHAT_IDS=11111,22222    белый список chat_id (через запятую)

Безопасность: БЕЗ белого списка бот не отвечает НИКОМУ — бизнес-данные
(зарплаты, остатки АЗС) не должны раздаваться любому, кто нашёл бота по
имени. Сообщение из чужого чата молча игнорируется (никакого ответа —
чтобы не подтверждать чужому чату, что бот жив).

Данные бот читает напрямую через AutoparkStore/AutoparkController (он
работает на том же сервере, что и приложение) — Telegram-слой отделён от
бизнес-логики: каждая команда — чистая функция, возвращающая Markdown,
и тестируется без сети (tests/test_autopark.py).

Мониторинг (--monitor, каждые 10 минут в том же процессе):
  * запас АЗС упал ниже страхового — не чаще 1 раза в СУТКИ на пару
    АЗС/продукт (антидубль);
  * появился рейс с превышением лимита (км или ДТ) — один раз на рейс.
Состояние антидубля — локальный JSON рядом со скриптом
(autopark_bot_state.json): это курсор уведомлений, а не бизнес-данные,
поэтому Oracle-first правило проекта на него не распространяется
(потеря файла означает максимум один повторный пуш, не потерю данных).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "autopark_bot_state.json")
API_BASE = "https://api.telegram.org/bot{token}/{method}"
POLL_TIMEOUT_S = 50
MONITOR_INTERVAL_S = 600

NO_TOKEN_HELP = """\
AUTOPARK_TG_TOKEN не задан — боту не с чем идти в Telegram API.

Как настроить:
  1. В Telegram открыть @BotFather -> /newbot, задать имя и username,
     скопировать выданный токен вида 123456789:AA...
  2. В .env в корне проекта (тот же файл, где WALLET_DIR) добавить:
         AUTOPARK_TG_TOKEN=123456789:AA...
         AUTOPARK_TG_CHAT_IDS=11111111,22222222
     Свой chat_id проще всего узнать у @userinfobot.
  3. Перезапустить бота. БЕЗ AUTOPARK_TG_CHAT_IDS (белый список) бот не
     будет отвечать никому — это защита, а не поломка.

Проверить команды без Telegram можно прямо сейчас:
    venv/bin/python modules/autopark/scripts/autopark_bot.py \\
        --dry-run /stock "/pay 2026-07" "/control 7"
"""

HELP_TEXT = """\
*Autopark — бот логиста (Bemol)*

/stock — АЗС с запасом ниже страхового (топ-10 по критичности)
/plan — краткий план поставок (сколько АЗС требуют, предлагаемые рейсы)
/trips — сегодняшние рейсы со статусами
/pay `[YYYY-MM]` — свод зарплаты за месяц по водителям
/control `[N]` — отклонения (км/ДТ) за N дней (по умолчанию 7)
/prices — текущие цены ANRE и изменение за неделю
/help — эта справка"""


# ── конфигурация ────────────────────────────────────────────────────────

def _read_env_file(path: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def load_config() -> Tuple[Optional[str], List[str]]:
    """Токен и белый список: окружение важнее .env (как у Flask-конфига)."""
    env_file = _read_env_file(os.path.join(ROOT, ".env"))
    token = os.environ.get("AUTOPARK_TG_TOKEN") or env_file.get(
        "AUTOPARK_TG_TOKEN") or None
    raw_ids = os.environ.get("AUTOPARK_TG_CHAT_IDS") or env_file.get(
        "AUTOPARK_TG_CHAT_IDS") or ""
    chat_ids = [c.strip() for c in raw_ids.split(",") if c.strip()]
    return token, chat_ids


# ── разбор команд ───────────────────────────────────────────────────────

def parse_command(text: str) -> Tuple[Optional[str], str]:
    """'/pay 2026-07' -> ('pay', '2026-07'); '/stock@MyBot' -> ('stock', '').

    Не-команды (обычный текст) дают (None, '') — бот на них не отвечает.
    """
    text = (text or "").strip()
    if not text.startswith("/"):
        return None, ""
    head, _, rest = text.partition(" ")
    cmd = head[1:].split("@", 1)[0].lower()
    return (cmd or None), rest.strip()


def _fmt_l(value: Any) -> str:
    return f"{float(value):,.0f}".replace(",", " ")


def _fmt2(value: Any) -> str:
    return f"{float(value):,.2f}".replace(",", " ")


# ── команды (чистые функции: данные -> Markdown) ────────────────────────

def cmd_stock() -> str:
    from modules.autopark.store import AutoparkStore
    res = AutoparkStore.stock_days_report()
    if not res.get("success"):
        return f"Ошибка: {res.get('message')}"
    low = [r for r in res["data"] if r.get("need_supply")]
    if not low:
        return "Все АЗС выше страхового запаса. Поставки не требуются."
    low.sort(key=lambda r: (float(r["stock_days"])
                            if r.get("stock_days") is not None else -1))
    lines = ["*АЗС ниже страхового запаса* (топ-10 по критичности):"]
    for r in low[:10]:
        days = (f"{float(r['stock_days']):.1f} дн."
                if r.get("stock_days") is not None else "нет реализации")
        lines.append(
            f"• `{r['station_code']}` {r['station_name']} — "
            f"{r['product_code']}: {_fmt_l(r.get('current_l') or 0)} л "
            f"(мин {_fmt_l(r.get('min_stock_l') or 0)} л, запас {days})")
    if len(low) > 10:
        lines.append(f"…и ещё {len(low) - 10} позиций (см. портал).")
    return "\n".join(lines)


def cmd_plan() -> str:
    from modules.autopark.controller import AutoparkController
    res = AutoparkController.supply_plan()
    if not res.get("success"):
        return f"Ошибка: {res.get('message')}"
    trips = res["data"].get("trips") or []
    if not trips:
        return "План поставок пуст: потребности выше страхового нет."
    stations = {s["station_id"] for t in trips for s in t["stops"]}
    lines = [f"*План поставок*: {len(stations)} АЗС требуют топлива, "
             f"предложено рейсов: {len(trips)}"]
    for i, t in enumerate(trips, start=1):
        stops_txt = "; ".join(
            f"АЗС {s['station_id']}: "
            + ", ".join(f"{it['product']} {_fmt_l(it['volume'])} л"
                        for it in s["items"])
            for s in t["stops"])
        lines.append(f"{i}. Бензовоз {t['truck']} (~{t['est_km']:.0f} км): "
                     f"{stops_txt}")
    return "\n".join(lines)


def cmd_trips() -> str:
    from modules.autopark.store import AutoparkStore
    today = date.today()
    res = AutoparkStore.list_trips(today, today)
    if not res.get("success"):
        return f"Ошибка: {res.get('message')}"
    trips = res["data"]
    if not trips:
        return f"Сегодня ({today.isoformat()}) рейсов нет."
    status_ru = {"DRAFT": "черновик", "APPROVED": "утверждён",
                 "DONE": "завершён"}
    type_ru = {"DOMESTIC": "внутренний", "IMPORT": "импортный"}
    lines = [f"*Рейсы на {today.isoformat()}*: {len(trips)}"]
    for t in trips:
        fact = (f", факт {float(t['fact_km']):.0f} км"
                if t.get("fact_km") is not None else "")
        lines.append(
            f"• №{t['id']} {type_ru.get(t['type_code'], t['type_code'])}, "
            f"{len(t.get('stops') or [])} АЗС, "
            f"норма {float(t.get('norm_km') or 0):.0f} км{fact} — "
            f"_{status_ru.get(t['status_code'], t['status_code'])}_")
    return "\n".join(lines)


def cmd_pay(arg: str) -> str:
    from modules.autopark.store import AutoparkStore
    try:
        ym = datetime.strptime(arg, "%Y-%m") if arg else datetime.now()
    except ValueError:
        return "Формат: /pay YYYY-MM (например /pay 2026-07)."
    first = date(ym.year, ym.month, 1)
    last = (date(ym.year + 1, 1, 1) if ym.month == 12
            else date(ym.year, ym.month + 1, 1)) - timedelta(days=1)
    res = AutoparkStore.driver_summary(first, last)
    if not res.get("success"):
        return f"Ошибка: {res.get('message')}"
    rows = res["data"]
    if not rows:
        return f"За {first.strftime('%Y-%m')} утверждённых рейсов нет."
    lines = [f"*Зарплата за {first.strftime('%Y-%m')}* "
             "(утверждённые рейсы):"]
    total = 0.0
    for r in rows:
        pay = float(r.get("total_pay") or 0)
        total += pay
        lines.append(
            f"• {r['full_name']}: {_fmt2(pay)} леев "
            f"({int(r.get('domestic_cnt') or 0)} внутр. + "
            f"{int(r.get('import_cnt') or 0)} имп., "
            f"{_fmt_l(r.get('total_norm_km') or 0)} км)")
    lines.append(f"*Итого: {_fmt2(total)} леев*")
    return "\n".join(lines)


def cmd_control(arg: str) -> str:
    from modules.autopark.store import AutoparkStore
    try:
        days = int(arg) if arg else 7
    except ValueError:
        return "Формат: /control N (число дней, например /control 7)."
    date_to = date.today()
    date_from = date_to - timedelta(days=days)
    res = AutoparkStore.trip_control_report(date_from, date_to)
    if not res.get("success"):
        return f"Ошибка: {res.get('message')}"
    bad = [r for r in res["data"]
           if r.get("over_km_limit") or r.get("over_fuel_limit")]
    if not bad:
        return f"За {days} дн. отклонений сверх лимита нет."
    lines = [f"*Отклонения за {days} дн.* ({len(bad)} рейсов):"]
    for r in bad[:15]:
        parts = []
        if r.get("over_km_limit"):
            parts.append(f"пробег {float(r.get('km_deviation') or 0):+.0f} км")
        if r.get("over_fuel_limit"):
            parts.append(f"ДТ {float(r.get('fuel_deviation') or 0):+.1f} л")
        trip_date = r.get("trip_date")
        day_txt = (trip_date.date().isoformat()
                   if isinstance(trip_date, datetime)
                   else str(trip_date or ""))
        lines.append(f"• №{r['trip_id']} {day_txt} {r.get('plate', '')}: "
                     + ", ".join(parts))
    if len(bad) > 15:
        lines.append(f"…и ещё {len(bad) - 15} (см. портал).")
    return "\n".join(lines)


def cmd_prices() -> str:
    from modules.autopark.store import AutoparkStore
    date_to = date.today()
    res = AutoparkStore.list_fuel_prices(date_to - timedelta(days=14), date_to)
    if not res.get("success"):
        return f"Ошибка: {res.get('message')}"
    series: Dict[str, List[Dict[str, Any]]] = {}
    for p in res["data"]:
        series.setdefault(p["product_code"], []).append(p)
    if not series:
        return "Цен за последние 2 недели нет в FLT_FUEL_PRICES."
    lines = ["*Цены ANRE (предельные, лей/л)*:"]
    week_ago = date_to - timedelta(days=7)
    for product in sorted(series):
        pts = sorted(series[product], key=lambda p: p["price_date"])
        last = float(pts[-1]["price_lei"])
        base = None
        for p in pts:
            d = p["price_date"]
            d = d.date() if isinstance(d, datetime) else d
            if d <= week_ago:
                base = float(p["price_lei"])
        delta = (f" ({last - base:+.2f} за неделю)"
                 if base is not None else "")
        lines.append(f"• {product}: *{last:.2f}*{delta}")
    return "\n".join(lines)


COMMANDS: Dict[str, Callable[[str], str]] = {
    "start": lambda arg: HELP_TEXT,
    "help": lambda arg: HELP_TEXT,
    "stock": lambda arg: cmd_stock(),
    "plan": lambda arg: cmd_plan(),
    "trips": lambda arg: cmd_trips(),
    "pay": cmd_pay,
    "control": cmd_control,
    "prices": lambda arg: cmd_prices(),
}


def execute_command(text: str) -> Optional[str]:
    """Текст сообщения -> ответ бота (или None, если отвечать нечего)."""
    cmd, arg = parse_command(text)
    if cmd is None:
        return None
    handler = COMMANDS.get(cmd)
    if handler is None:
        return ("Не знаю команду /" + cmd + ". Список — /help.")
    try:
        return handler(arg)
    except Exception as exc:  # noqa: BLE001 — бот не должен умирать на команде
        return f"Внутренняя ошибка команды /{cmd}: {exc}"


def process_update(update: Dict[str, Any],
                   allowed_chat_ids: List[str]) -> Optional[Tuple[str, str]]:
    """Update Telegram -> (chat_id, ответ) или None (игнор).

    Чат вне белого списка (или пустой белый список) игнорируется МОЛЧА —
    см. модульный docstring про безопасность.
    """
    message = update.get("message") or update.get("edited_message") or {}
    chat_id = str((message.get("chat") or {}).get("id") or "")
    text = message.get("text") or ""
    if not chat_id or chat_id not in allowed_chat_ids:
        return None
    reply = execute_command(text)
    if reply is None:
        return None
    return chat_id, reply


# ── состояние мониторинга (антидубль) ───────────────────────────────────

class NotifyState:
    """Курсор уведомлений: что и когда уже отправляли (локальный JSON)."""

    def __init__(self, path: str = STATE_PATH):
        self.path = path
        self._data: Dict[str, Any] = {"stock_alerts": {}, "trip_alerts": []}
        try:
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self._data["stock_alerts"] = dict(
                    loaded.get("stock_alerts") or {})
                self._data["trip_alerts"] = list(
                    loaded.get("trip_alerts") or [])
        except (OSError, ValueError):
            pass  # нет файла/битый файл -> чистое состояние, максимум 1 повтор

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=1)
        except OSError:
            pass  # курсор не важнее самого пуша

    def should_notify_stock(self, station_id, product_code: str,
                            today: date) -> bool:
        """Не чаще 1 раза в сутки на пару АЗС/продукт."""
        key = f"{station_id}:{product_code}"
        return self._data["stock_alerts"].get(key) != today.isoformat()

    def mark_stock(self, station_id, product_code: str, today: date) -> None:
        self._data["stock_alerts"][f"{station_id}:{product_code}"] = (
            today.isoformat())

    def should_notify_trip(self, trip_id) -> bool:
        return int(trip_id) not in self._data["trip_alerts"]

    def mark_trip(self, trip_id) -> None:
        self._data["trip_alerts"].append(int(trip_id))
        self._data["trip_alerts"] = self._data["trip_alerts"][-500:]


def monitor_tick(state: NotifyState,
                 send: Callable[[str], None],
                 today: Optional[date] = None) -> int:
    """Один проход мониторинга; возвращает число отправленных пушей."""
    from modules.autopark.store import AutoparkStore
    today = today or date.today()
    sent = 0

    stock = AutoparkStore.stock_days_report()
    if stock.get("success"):
        for r in stock["data"]:
            if not r.get("need_supply"):
                continue
            if not state.should_notify_stock(r["station_id"],
                                             r["product_code"], today):
                continue
            days = (f"{float(r['stock_days']):.1f} дн."
                    if r.get("stock_days") is not None else "н/д")
            send(f"⚠️ *Запас ниже страхового*: `{r['station_code']}` "
                 f"{r['station_name']} — {r['product_code']}: "
                 f"{_fmt_l(r.get('current_l') or 0)} л "
                 f"(мин {_fmt_l(r.get('min_stock_l') or 0)} л, {days})")
            state.mark_stock(r["station_id"], r["product_code"], today)
            sent += 1

    control = AutoparkStore.trip_control_report(today - timedelta(days=3),
                                                today)
    if control.get("success"):
        for r in control["data"]:
            if not (r.get("over_km_limit") or r.get("over_fuel_limit")):
                continue
            if not state.should_notify_trip(r["trip_id"]):
                continue
            parts = []
            if r.get("over_km_limit"):
                parts.append(
                    f"пробег {float(r.get('km_deviation') or 0):+.0f} км")
            if r.get("over_fuel_limit"):
                parts.append(
                    f"ДТ {float(r.get('fuel_deviation') or 0):+.1f} л")
            send(f"🚨 *Превышение лимита*: рейс №{r['trip_id']} "
                 f"{r.get('plate', '')}: " + ", ".join(parts))
            state.mark_trip(r["trip_id"])
            sent += 1

    state.save()
    return sent


# ── Telegram API (urllib, без SDK) ──────────────────────────────────────

def tg_api(token: str, method: str,
           params: Optional[Dict[str, Any]] = None,
           timeout: int = POLL_TIMEOUT_S + 10) -> Dict[str, Any]:
    url = API_BASE.format(token=token, method=method)
    data = urllib.parse.urlencode(params or {}).encode()
    with urllib.request.urlopen(url, data=data, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tg_send(token: str, chat_id: str, text: str) -> None:
    try:
        tg_api(token, "sendMessage",
               {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
               timeout=30)
    except Exception as exc:  # noqa: BLE001
        print(f"[bot] sendMessage {chat_id}: {exc}", file=sys.stderr)


def run_polling(token: str, chat_ids: List[str], monitor: bool) -> None:
    if not chat_ids:
        print("[bot] AUTOPARK_TG_CHAT_IDS пуст — бот запущен, но по правилу "
              "безопасности не ответит никому. Заполните белый список.",
              file=sys.stderr)
    state = NotifyState()
    offset = 0
    last_monitor = 0.0
    print("[bot] long polling запущен")
    while True:
        try:
            res = tg_api(token, "getUpdates",
                         {"offset": offset, "timeout": POLL_TIMEOUT_S})
            for update in res.get("result") or []:
                offset = max(offset, int(update["update_id"]) + 1)
                handled = process_update(update, chat_ids)
                if handled:
                    tg_send(token, handled[0], handled[1])
        except Exception as exc:  # noqa: BLE001 — сеть моргает, бот живёт
            print(f"[bot] getUpdates: {exc}", file=sys.stderr)
            time.sleep(5)
        if monitor and time.time() - last_monitor >= MONITOR_INTERVAL_S:
            last_monitor = time.time()
            try:
                sent = monitor_tick(
                    state,
                    lambda text: [tg_send(token, cid, text)
                                  for cid in chat_ids])
                if sent:
                    print(f"[bot] мониторинг: отправлено {sent} пушей")
            except Exception as exc:  # noqa: BLE001
                print(f"[bot] monitor: {exc}", file=sys.stderr)


# ── CLI ─────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Телеграм-бот логиста Autopark (long polling)")
    parser.add_argument("--monitor", action="store_true",
                        help="включить пуш-мониторинг (раз в 10 минут)")
    parser.add_argument("--dry-run", nargs="+", metavar="CMD",
                        help="исполнить команды локально (stdout вместо "
                             "Telegram), напр.: --dry-run /stock '/pay 2026-07'")
    args = parser.parse_args(argv)

    if args.dry_run:
        for text in args.dry_run:
            print(f"\n>>> {text}")
            print(execute_command(text) or "(нет ответа)")
        return 0

    token, chat_ids = load_config()
    if not token:
        print(NO_TOKEN_HELP, file=sys.stderr)
        return 2
    run_polling(token, chat_ids, args.monitor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
