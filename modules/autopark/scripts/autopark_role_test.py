#!/usr/bin/env python3
"""Autopark — приёмочный прогон по ролям.

Проверяется не «отвечает ли эндпоинт», а проходит ли РОЛЬ свой рабочий
день целиком: логист планирует завоз, закупщик правит условия, диспетчер
ведёт рейс по статусам, бухгалтер считает зарплату, руководитель смотрит
сводку, администратор настраивает параметры на период.

Каждый шаг — с проверяемым утверждением, а не просто «200 OK». Шаг,
который что-то ломает в данных (создаёт план, двигает статусы), помечен
и выполняется только с --write.

    venv/bin/python modules/autopark/scripts/autopark_role_test.py --base http://127.0.0.1:3003
    venv/bin/python modules/autopark/scripts/autopark_role_test.py --write --md акт.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

MODULE = "/UNA.md/orasldev/autopark"


def _parse_date(raw) -> date:
    """Дата из ответа API: ISO либо RFC («Wed, 01 Jan 2024 00:00:00 GMT»)."""
    text = str(raw)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(text).date()


class Runner:
    def __init__(self, base: str, cookie: str, write: bool):
        self.base = base.rstrip("/")
        self.cookie = cookie
        self.write = write
        self.results = []
        self.context = {}

    def call(self, path, body=None, method=None):
        url = self.base + MODULE + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, method=method or ("POST" if body is not None else "GET"),
            headers={"Cookie": "session=" + self.cookie,
                     "Content-Type": "application/json"})
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode())
                status = resp.status
        except urllib.error.HTTPError as exc:
            payload, status = {"success": False, "message": exc.reason}, exc.code
        return payload, status, round(time.time() - started, 2)

    def step(self, role, title, fn, writes=False):
        if writes and not self.write:
            self.results.append({"role": role, "title": title, "state": "skip",
                                 "note": "требует --write", "seconds": 0})
            return None
        started = time.time()
        try:
            ok, note, value = fn()
        except Exception as exc:                                 # noqa: BLE001
            ok, note, value = False, f"{type(exc).__name__}: {exc}", None
        self.results.append({"role": role, "title": title,
                             "state": "ok" if ok else "fail", "note": note,
                             "seconds": round(time.time() - started, 2)})
        return value

    # ── роли ────────────────────────────────────────────────────────

    def role_logist(self):
        role = "Логист"

        def tanks():
            d, st, sec = self.call("/api/supply/tanks")
            rows = d.get("data") or []
            risky = [r for r in rows if (r.get("days_to_min") or 99) < 1]
            assert d["success"] and rows, "пустое состояние резервуаров"
            for r in rows:
                assert r["allowed_l"] >= 0, "отрицательный допустимый объём"
            return True, (f"{len(rows)} резервуаров, из них ниже суток запаса: "
                          f"{len(risky)}; ответ {sec} с"), rows
        tanks_rows = self.step(role, "Видит состояние всех резервуаров сети", tanks)

        def plan():
            d, st, sec = self.call("/api/supply/plan", {"horizon_days": 3})
            assert d["success"], d.get("message")
            data = d.get("data") or {}
            needs, trips = data.get("needs") or [], data.get("trips") or []
            for t in trips:
                nums = [l["section_no"] for l in t["loads"]]
                assert nums == sorted(nums, reverse=True), \
                    "порядок слива не от хвоста к кабине"
                groups = {l["product_code"] for l in t["loads"]}
                assert not ({"DIESEL"} & groups and groups - {"DIESEL"}), \
                    "бензин и дизель в одной цистерне"
            for n in needs:
                assert n["planned_l"] <= n["allowed_l"] + 1e-6, "перелив резервуара"
            self.context["plan_id"] = data.get("plan_id")
            return True, (f"план {data.get('plan_id')}: потребностей {len(needs)}, "
                          f"рейсов {len(trips)}; ответ {sec} с"), data
        self.step(role, "Рассчитывает план завоза", plan, writes=True)

        def validate():
            pid = self.context.get("plan_id")
            if not pid:
                return False, "план не рассчитан", None
            d, st, sec = self.call(f"/api/supply/plans/{pid}/validate")
            assert d["success"], d.get("message")
            return True, (f"ошибок {d['data']['errors']}, предупреждений "
                          f"{d['data']['warnings']}, утверждать можно: "
                          f"{d['data']['can_confirm']}"), d["data"]
        self.step(role, "Проверяет план на перелив и вместимость отсеков",
                  validate, writes=True)

        def edit_reject():
            pid = self.context.get("plan_id")
            plan_d, _, _ = self.call(f"/api/supply/plans/{pid}")
            trips = plan_d["data"]["trips"]
            if not trips or not trips[0]["loads"]:
                return True, "в плане нет строк для правки (сеть обеспечена)", None
            load = trips[0]["loads"][0]
            over = float(load["section_volume_l"]) + 5000
            d, _, _ = self.call(f"/api/supply/loads/{load['id']}",
                                {"volume_l": over, "plan_id": pid})
            problems = (d.get("data") or {}).get("validation", {}).get("problems", [])
            has_error = any(p["level"] == "error" for p in problems)
            self.call(f"/api/supply/loads/{load['id']}",
                      {"volume_l": load["section_volume_l"], "plan_id": pid})
            assert has_error, "перелив отсека не отклонён"
            return True, "правка сверх объёма отсека отклонена, значение возвращено", None
        self.step(role, "Правит объём вручную — система ловит перелив",
                  edit_reject, writes=True)

    def role_buyer(self):
        role = "Закупщик"

        def periods():
            d, _, _ = self.call("/api/periods/rates")
            rows = d.get("data") or []
            assert d["success"] and rows, "нет ни одного периода ставки"
            open_ended = [r for r in rows if not r.get("valid_to")]
            assert len(open_ended) <= 1, "несколько бессрочных периодов ставки"
            return True, (f"{len(rows)} периодов ставки, бессрочных "
                          f"{len(open_ended)}"), rows
        self.step(role, "Видит историю ставок и параметров", periods)

        def effective():
            past = (date.today() - timedelta(days=45)).isoformat()
            now = date.today().isoformat()
            a, _, _ = self.call(f"/api/periods-effective?date={past}")
            b, _, _ = self.call(f"/api/periods-effective?date={now}")
            ra = (a["data"].get("rate") or {}).get("rate_per_km")
            rb = (b["data"].get("rate") or {}).get("rate_per_km")
            assert a["success"] and b["success"], "период не разрешается"
            return True, f"на {past} ставка {ra}, на {now} — {rb}", (ra, rb)
        self.step(role, "Сверяет, какая ставка действовала в прошлом месяце",
                  effective)

        def overlap():
            # Период ВНУТРИ уже закрытого — его закрыть автоматически
            # нельзя, значит он обязан быть отклонён. Период «с сегодня»
            # проверять бессмысленно: он законно закрывает предыдущий.
            existing, _, _ = self.call("/api/periods/rates")
            closed = [r for r in (existing.get("data") or []) if r.get("valid_to")]
            if not closed:
                return True, "закрытых периодов нет — проверять нечего", None
            row = closed[0]
            # Даты приходят в RFC-формате («Wed, 01 Jan 2024 00:00:00 GMT»),
            # и срез [:10] давал «Wed, 01 Ja» -- период отклонялся из-за
            # формата даты, а тест считал это доказательством проверки
            # пересечений. Зелёный тест, который ничего не доказывает,
            # опаснее красного, поэтому дата разбирается по-настоящему.
            inside = _parse_date(row["valid_from"]) + timedelta(days=1)
            d, _, _ = self.call("/api/periods/rates",
                                {"valid_from": inside.isoformat(),
                                 "valid_to": (inside + timedelta(days=5)).isoformat(),
                                 "rate_per_km": "9.99"})
            assert not d["success"], "пересекающийся период принят"
            assert "ересек" in d["message"], \
                f"отклонено не из-за пересечения, а так: {d['message']}"
            return True, f"отклонено: {d['message'][:80]}", None
        self.step(role, "Пересекающийся период не принимается", overlap, writes=True)

        def refs():
            d, _, _ = self.call("/api/refs")
            data = d.get("data") or {}
            points = data.get("load_points") or []
            foreign = [p for p in points if p.get("is_foreign")]
            assert d["success"] and points, "нет пунктов загрузки"
            return True, (f"пунктов загрузки {len(points)}, из них зарубежных "
                          f"{len(foreign)} (импортный рейс)"), points
        self.step(role, "Открывает справочник пунктов загрузки", refs)

    def role_dispatcher(self):
        role = "Диспетчер"

        def execution():
            today = date.today().isoformat()
            week = (date.today() - timedelta(days=7)).isoformat()
            d, _, sec = self.call(f"/api/supply/execution?date_from={week}"
                                  f"&date_to={today}")
            rows = d.get("data") or []
            assert d["success"], d.get("message")
            self.context["items"] = rows
            statuses = sorted({r["status_code"] for r in rows})
            return True, (f"{len(rows)} позиций к исполнению, статусы: "
                          f"{', '.join(statuses) or '—'}; ответ {sec} с"), rows
        self.step(role, "Видит позиции к исполнению за неделю", execution)

        def chain():
            rows = self.context.get("items") or []
            movable = [r for r in rows if r["status_code"] in
                       ("PLANNED", "LOAD_REQ", "LOADED", "IN_TRANSIT")]
            if not movable:
                return True, "активных рейсов нет — цепочка не проверялась", None
            trip = movable[0]["trip_id"]
            order = ["LOAD_REQ", "LOADED", "IN_TRANSIT", "DELIVERED"]
            moved = []
            for status in order:
                d, _, _ = self.call(f"/api/supply/trips/{trip}/status",
                                    {"status_code": status})
                if d["success"]:
                    moved.append(status)
            bad, _, _ = self.call(f"/api/supply/trips/{trip}/status",
                                  {"status_code": "НЕТ_ТАКОГО"})
            assert not bad["success"], "принят несуществующий статус"
            return True, (f"рейс {trip} проведён: {' → '.join(moved)}; "
                          "несуществующий статус отклонён"), moved
        self.step(role, "Ведёт рейс по цепочке статусов", chain, writes=True)

        def facts():
            rows = self.context.get("items") or []
            if not rows:
                return True, "нет позиций для ввода факта", None
            item = rows[0]
            plan_l = float(item["plan_l"])
            d, _, _ = self.call(f"/api/supply/items/{item['item_id']}/fact",
                                {"loaded_l": plan_l, "doc_l": plan_l,
                                 "accepted_l": plan_l - 700})
            assert d["success"], d.get("message")
            today = date.today().isoformat()
            week = (date.today() - timedelta(days=7)).isoformat()
            diff, _, _ = self.call(f"/api/supply/execution?date_from={week}"
                                   f"&date_to={today}&only_discrepancies=1")
            found = [r for r in (diff.get("data") or [])
                     if r["item_id"] == item["item_id"]]
            assert found, "расхождение приёмки не попало в отчёт"
            return True, (f"недостача 700 л по позиции {item['item_id']} "
                          "выделена в отчёте"), None
        self.step(role, "Вводит факт и видит расхождение план/приёмка",
                  facts, writes=True)

    def role_accountant(self):
        role = "Бухгалтер"

        def payroll():
            today = date.today().isoformat()
            month = (date.today() - timedelta(days=30)).isoformat()
            d, _, sec = self.call(f"/api/report/payroll?date_from={month}"
                                  f"&date_to={today}")
            rows = d.get("data") or []
            assert d["success"], d.get("message")
            total = sum(float(r.get("total_pay") or 0) for r in rows)
            return True, (f"{len(rows)} рейсов в расчёте, к начислению "
                          f"{total:,.0f} лей; ответ {sec} с".replace(",", " ")), rows
        self.step(role, "Считает зарплату за период", payroll)

        def historic_rate():
            old_from = "2026-08-01"
            old_to = "2026-08-31"
            d, _, _ = self.call(f"/api/report/payroll?date_from={old_from}"
                                f"&date_to={old_to}")
            rows = d.get("data") or []
            if not rows:
                return True, "в августе рейсов нет", None
            rates = {round(float(r["km_pay"]) / float(r["norm_km"]), 2)
                     for r in rows if r.get("norm_km")}
            assert rates, "не удалось вычислить ставку"
            return True, (f"август посчитан по ставке {sorted(rates)} лей/км — "
                          "прошлое не переписано"), sorted(rates)
        self.step(role, "Закрытый месяц считается по своей ставке", historic_rate)

        def control():
            today = date.today().isoformat()
            month = (date.today() - timedelta(days=30)).isoformat()
            d, _, _ = self.call(f"/api/report/control?date_from={month}"
                                f"&date_to={today}")
            rows = d.get("data") or []
            over = [r for r in rows if r.get("over_km_limit")]
            return d["success"], (f"{len(rows)} рейсов, с превышением лимита "
                                  f"пробега: {len(over)}"), rows
        self.step(role, "Открывает контроль пробега и расхода", control)

    def role_director(self):
        role = "Руководитель"

        def board():
            today = date.today().isoformat()
            month = (date.today() - timedelta(days=30)).isoformat()
            d, _, sec = self.call(f"/api/board?date_from={month}&date_to={today}")
            assert d["success"], d.get("message")
            data = d["data"]
            for key in ("network", "money", "automation", "actions"):
                assert key in data, f"в сводке нет блока {key}"
            assert data["actions"], "нет ни одной рекомендации"
            assert sec < 3, f"сводка собирается {sec} с — это долго для экрана"
            return True, (f"сеть: {data['network']['headline']}; деньги: "
                          f"{data['money']['headline']}; ответ {sec} с"), data
        self.step(role, "Открывает сводку и видит три ответа", board)

        def management():
            today = date.today().isoformat()
            month = (date.today() - timedelta(days=30)).isoformat()
            d, _, _ = self.call(f"/api/supply/management?date_from={month}"
                                f"&date_to={today}")
            assert d["success"], d.get("message")
            e = d["data"]["economics"]
            assert e["cost_per_liter"] is not None, "не посчитана стоимость литра"
            return True, (f"стоимость доставки литра {e['cost_per_liter']} лей, "
                          f"загрузка {e['avg_load_pct']}%, эффект оптимизации "
                          f"{e['optimization_effect']} лей"), e
        self.step(role, "Смотрит экономику перевозки и рейтинг водителей",
                  management)

    def role_admin(self):
        role = "Администратор"

        def sections():
            d, _, _ = self.call("/api/sections-periods")
            rows = d.get("data") or []
            assert d["success"] and rows, "нет ни одного отсека"
            trucks = {r["plate"] for r in rows}
            return True, (f"{len(rows)} записей об отсеках по {len(trucks)} "
                          "цистернам"), rows
        self.step(role, "Видит конфигурации отсеков с историей", sections)

        def oversize():
            d, _, _ = self.call("/api/refs")
            trucks = d["data"]["trucks"]
            truck = trucks[0]
            big = float(truck["capacity_l"]) + 5000
            r, _, _ = self.call("/api/sections-periods",
                                {"truck_id": truck["id"],
                                 "sections": [{"volume_l": big}]})
            assert not r["success"], "принята сумма отсеков больше цистерны"
            return True, f"отклонено: {r['message'][:70]}", None
        self.step(role, "Сумма отсеков больше цистерны не принимается",
                  oversize, writes=True)

        def groups():
            d, _, _ = self.call("/api/group-periods")
            rows = d.get("data") or []
            assert d["success"], d.get("message")
            total = sum(len(g.get("items") or []) for g in rows)
            return True, f"{len(rows)} групп, записей состава {total}", rows
        self.step(role, "Видит группы АЗС и их состав по периодам", groups)

        def guard():
            url = self.base + MODULE + "/api/board"
            req = urllib.request.Request(url)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    code = resp.status
            except urllib.error.HTTPError as exc:
                code = exc.code
            assert code in (401, 302), f"без сессии отдано {code}"
            return True, f"без входа система отвечает {code}", code
        self.step(role, "Данные закрыты от анонимного доступа", guard)

    def role_auditor(self):
        """Седьмая роль: проверяющий, который не верит системе на слово."""
        role = "Аудитор"

        def verdict():
            d, _, secs = self.call("/api/audit")
            assert d["success"], d.get("message")
            data = d["data"]
            op = data["opinion"]
            assert op.get("title"), "нет заключения"
            assert data["facts"]["total_tested"] >= 0
            return True, (f"«{op['title']}», проверено "
                          f"{data['facts']['total_tested']} объектов "
                          f"по {len(data['tests'])} процедурам за "
                          f"{secs:.2f} с"), data
        audit_data = self.step(role, "Получает заключение по контуру", verdict)

        def consistency():
            d, _, _ = self.call("/api/audit")
            data = d["data"]
            by_test = {t["id"]: t for t in data["tests"]}
            bad = []
            for c in data["controls"]:
                # Контроль не может быть «эффективен», если ни одна
                # процедура его не проверяла: это ровно тот случай, когда
                # контрольная среда выглядит здоровой на пустом месте.
                if not c["test_ids"]:
                    bad.append(f"{c['id']}: нет процедуры")
                if c["rating"] == "Эффективен" and c["tested"] == 0:
                    bad.append(f"{c['id']}: «эффективен» при нулевом покрытии")
                if c["exceptions"] and c["rating"] == "Эффективен":
                    bad.append(f"{c['id']}: «эффективен» при отклонениях")
                for tid in c["test_ids"]:
                    if tid not in by_test:
                        bad.append(f"{c['id']}: процедура {tid} не выполнялась")
            assert not bad, "; ".join(bad[:3])
            return True, (f"{len(data['controls'])} контролей связаны с "
                          "процедурами, оценки согласованы"), None
        self.step(role, "Оценка контроля не выдаётся без процедуры",
                  consistency)

        def selfcheck():
            d, _, _ = self.call("/api/audit/demo")
            assert d["success"], d.get("message")
            sc = d["data"]["selfcheck"]
            miss = [r for r in sc["rows"] if r["injected"] != r["found"]]
            assert sc["passed"] and not miss, (
                "методика не воспроизвела заложенные дефекты: " +
                ", ".join(f"{r['test']} {r['injected']}≠{r['found']}"
                          for r in miss[:3]))
            total = sum(r["injected"] for r in sc["rows"])
            return True, (f"{total} заложенных дефектов по "
                          f"{len(sc['rows'])} процедурам воспроизведены "
                          "полностью, ложных срабатываний нет"), sc
        self.step(role, "Методика ловит намеренно заложенные дефекты",
                  selfcheck)

        def workbook():
            url = self.base + MODULE + "/audit/demo.xlsx"
            req = urllib.request.Request(
                url, headers={"Cookie": "session=" + self.cookie})
            with urllib.request.urlopen(req, timeout=120) as resp:
                blob = resp.read()
            assert blob[:2] == b"PK", "получен не xlsx"
            import io
            import zipfile
            names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
            sheets = [n for n in names if n.startswith("xl/worksheets/sheet")]
            charts = [n for n in names if n.startswith("xl/charts/chart")]
            assert len(sheets) >= 12, f"в книге {len(sheets)} листов"
            assert charts, "в книге нет ни одной диаграммы"
            return True, (f"{len(blob) // 1024} КБ, {len(sheets)} листов, "
                          f"{len(charts)} диаграмм"), None
        self.step(role, "Выгружает книгу Excel с BI-панелью", workbook)

        def guard():
            url = self.base + MODULE + "/api/audit"
            req = urllib.request.Request(url)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    code = resp.status
            except urllib.error.HTTPError as exc:
                code = exc.code
            assert code in (401, 302), f"без сессии отдано {code}"
            return True, f"без входа система отвечает {code}", code
        self.step(role, "Аудит закрыт от анонимного доступа", guard)

    def run(self):
        self.role_logist()
        self.role_buyer()
        self.role_dispatcher()
        self.role_accountant()
        self.role_director()
        self.role_admin()
        self.role_auditor()
        return self.results


def to_markdown(results, base, write_mode) -> str:
    ok = sum(1 for r in results if r["state"] == "ok")
    fail = sum(1 for r in results if r["state"] == "fail")
    skip = sum(1 for r in results if r["state"] == "skip")
    lines = [
        "# Акт приёмочного тестирования по ролям",
        "",
        f"Контур: `{base}`  ",
        f"Дата: {date.today():%d.%m.%Y}  ",
        f"Режим: {'полный (с записью данных)' if write_mode else 'только чтение'}  ",
        f"Итог: **{ok} пройдено**, {fail} провалено, {skip} пропущено",
        "",
        "Проверяется не доступность эндпоинтов, а рабочий день каждой роли "
        "целиком — с утверждениями, которые должны выполняться.",
        "",
    ]
    current = None
    for r in results:
        if r["role"] != current:
            current = r["role"]
            lines += ["", f"## {current}", "",
                      "| Шаг | Результат | Что проверено |", "|---|---|---|"]
        mark = {"ok": "пройдено", "fail": "ПРОВАЛ", "skip": "пропущено"}[r["state"]]
        note = r["note"].replace("|", "\\|") if r["note"] else ""
        lines.append(f"| {r['title']} | {mark} | {note} |")
    lines += ["", "---", "",
              "Прогон выполняется скриптом "
              "`modules/autopark/scripts/autopark_role_test.py`, "
              "повторяется одной командой и не требует ручных действий."]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Приёмочный прогон по ролям")
    ap.add_argument("--base", default="http://127.0.0.1:3003")
    ap.add_argument("--cookie-file", default=None,
                    help="файл с session-cookie (иначе переменная AUTOPARK_COOKIE)")
    ap.add_argument("--write", action="store_true",
                    help="выполнять шаги, изменяющие данные")
    ap.add_argument("--md", metavar="FILE", help="сохранить акт в markdown")
    args = ap.parse_args()

    cookie = os.environ.get("AUTOPARK_COOKIE", "")
    if args.cookie_file:
        with open(args.cookie_file, encoding="utf-8") as fh:
            cookie = fh.read().strip()
    if not cookie:
        raise SystemExit("Нужна сессия: --cookie-file или AUTOPARK_COOKIE")

    runner = Runner(args.base, cookie, args.write)
    results = runner.run()

    width = max(len(r["title"]) for r in results) + 2
    current = None
    for r in results:
        if r["role"] != current:
            current = r["role"]
            print(f"\n=== {current}")
        mark = {"ok": "  ok  ", "fail": " ПРОВАЛ", "skip": " пропуск"}[r["state"]]
        print(f" {mark} {r['title']:<{width}} {r['note']}")

    ok = sum(1 for r in results if r["state"] == "ok")
    fail = sum(1 for r in results if r["state"] == "fail")
    skip = sum(1 for r in results if r["state"] == "skip")
    print(f"\nИтого: {ok} пройдено, {fail} провалено, {skip} пропущено")

    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(results, args.base, args.write))
        print(f"Акт: {args.md}")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
