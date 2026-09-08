#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genereaza modules/crm/lang.json din lang.json-ul prototipului (TZ TEC-02).

RO: RO si EN se iau ca atare din PavelTuhari/Contragenti/crm_delphi/lang.json
(sursa de adevar a traducerilor); RU = valorile canonice ale prototipului
(captiunile Delphi sint in rusa) — lista de mai jos. Enumerarile RU =
listele canonice din entities.py + titlurile/explicatiile etapelor.
    python3 modules/crm/scripts/crm_make_lang.py [cale/la/lang.json al prototipului]
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

from modules.crm import process  # noqa: E402
from modules.crm.entities import ENUMS  # noqa: E402

OUT = os.path.join(ROOT, "modules", "crm", "lang.json")
DEFAULT_SRC = "/Users/pt/Projects.AI/DATE.gov/Contragenti/crm_delphi/lang.json"

RU = {
    "app.title": "Demo CRM", "app.subtitle": "SDK Contragenti · date.gov.md", "app.user": "Оператор", "app.search": "Поиск клиента…",
    "btn.add_line": "+ Строка", "btn.back": "← Назад", "btn.cancel": "Отмена", "btn.create": "Создать", "btn.del_line": "Удалить строку",
    "btn.delete": "Удалить", "btn.done": "Выполнено", "btn.erp_check": "Проверить соединение", "btn.erp_send": "Отправить в ERP",
    "btn.export_pdf": "Экспорт в PDF", "btn.export_xlsx": "Экспорт в Excel", "btn.folder": "Папка экспорта", "btn.forward": "Вперёд →",
    "btn.from_registry": "Создать из реестра", "btn.post": "Провести", "btn.refresh": "Обновить", "btn.save": "Сохранить",
    "btn.to_clients": "В клиенты", "btn.today": "Сегодня",
    "calendar.day_tasks": "Задачи дня", "calendar.hint": "перетащите задачу мышью на другой день  ·  двойной клик — открыть",
    "calendar.months": "январь;февраль;март;апрель;май;июнь;июль;август;сентябрь;октябрь;ноябрь;декабрь",
    "calendar.moved": "Задача «%s» перенесена на %s.", "calendar.no_tasks": "В этот день задач нет.", "calendar.title": "Календарь",
    "calendar.today": "Сегодня", "calendar.week_days": "Пн;Вт;Ср;Чт;Пт;Сб;Вс",
    "card.client": "Карточка клиента", "col.added": "Добавлен", "col.address": "Адрес", "col.contact": "Контактное лицо",
    "col.email": "E-mail", "col.form": "Форма", "col.idno": "IDNO", "col.manager": "Руководитель", "col.name": "Название",
    "col.phone": "Телефон", "col.type": "Тип", "erp.not_checked": "ERP una.md: соединение не проверено",
    "gantt.all": "Все заказы", "gantt.closed": "закрыт", "gantt.hint": "перетащите полосу мышью — перенос, за края — срок",
    "gantt.late": "опоздание", "gantt.legend": "с отступом — работы заказа", "gantt.open": "Только незакрытые", "gantt.plan": "план",
    "gantt.production": "Производство", "gantt.run": "в работе", "gantt.title": "План работ (Гант)",
    "kanban.all_projects": "Все проекты", "kanban.board": "Доска: %s", "kanban.board_deals": "Сделки — продажи",
    "kanban.board_orders": "Заказы — исполнение", "kanban.board_project_tasks": "Задачи проекта — этапы",
    "kanban.board_projects": "Проекты — этапы", "kanban.board_tasks": "Задачи — работы",
    "kanban.cancelled": "Перенос отменён: карточка остаётся на своём этапе.", "kanban.col_late": "запаздывает %d",
    "kanban.days_late": "−%d д", "kanban.days_left": "%d д", "kanban.done_badge": "выполнено", "kanban.due": "срок",
    "kanban.edge": "Дальше двигать нельзя: «%s» — последний этап", "kanban.hint": "перетащите карточку мышью между колонками  ·  двойной клик — открыть",
    "kanban.moved": "«%s» → этап «%s»", "kanban.no_client": "(без клиента)", "kanban.overdue": "просрочено", "kanban.paid_pct": "оплачено %d%%",
    "kanban.project": "Проект: %s", "kanban.refreshed": "Доска обновлена.", "kanban.select_card": "Выберите карточку на доске.",
    "kanban.selected": "Выбрано: %s  ·  колонка «%s»", "kanban.task_cols": "Просрочено;Сегодня;Позже;Выполнено", "kanban.tasks_of": "задачи %s",
    "kanban.title": "Канбан", "kanban.today": "сегодня",
    "login.bad": "Неверный пользователь или пароль.", "login.enter": "Войти", "login.hint": "При первом запуске: admin / admin — смените пароль в настройках.",
    "login.language": "Язык", "login.logout": "Выход", "login.password": "Пароль", "login.subtitle": "Введите пользователя и пароль",
    "login.title": "Вход в Demo CRM", "login.user": "Пользователь", "login.welcome": "Добро пожаловать, %s.",
    "msg.added": "Добавлено: «%s».", "msg.client_added": "Клиент добавлен: %s (IDNO %s)",
    "msg.confirm_delete": "Удалить «%s»? Нажмите «Удалить» ещё раз для подтверждения", "msg.contragenti_busy": "Contragenti уже открыт — завершите выбор",
    "msg.contragenti_missing": "Contragenti не найден: %s", "msg.contragenti_open": "Contragenti открыт — выберите контрагента",
    "msg.contragenti_wait": "Contragenti открыт — выберите контрагента…", "msg.deleted": "Удалено: «%s».", "msg.duplicate": "Уже в базе: %s (IDNO %s)",
    "msg.filter": "Фильтр: показано %d из %d", "msg.number": "Поле «%s» должно быть числом.", "msg.pick_cancelled": "Выбор отменён: %s",
    "msg.refreshed": "Обновлено. Записей: %d", "msg.required": "Обязательное поле «%s» не заполнено.", "msg.saved": "Сохранено: «%s».",
    "msg.select_row": "Выберите запись в списке.",
    "nav.calendar": "Календарь", "nav.clients": "Клиенты", "nav.contacts": "Контакты", "nav.deals": "Сделки", "nav.gantt": "План работ",
    "nav.items": "Номенклатура", "nav.kanban": "Канбан", "nav.leads": "Лиды", "nav.orders": "Заказы", "nav.process": "Бизнес-процесс",
    "nav.projects": "Проекты", "nav.reports": "Отчёты", "nav.settings": "Настройки", "nav.workspace": "Рабочий стол", "preset.all": "Все",
    "process.cards": "Карточки этапа", "process.count": "%d", "process.desc": "Описание этапа", "process.hint": "клик по этапу — карточки и описание",
    "process.missing": "Файл с описанием процессов не найден:", "process.node_info": "Этап «%s»: %d карточек, запаздывает %d",
    "process.opened": "Раздел открыт с фильтром этапа: %d записей", "process.owner": "Ответственный: %s", "process.save": "Сохранить описание",
    "process.saved": "Описание этапа «%s» сохранено в %s.", "process.select_node": "Выберите этап на схеме.", "process.sla": "Норматив: %d дней",
    "process.title": "Бизнес-процесс",
    "report.funnel": "Воронка продаж", "report.funnel.hint": "Сделки по этапам: количество, сумма, средний чек",
    "report.process": "Процесс исполнения заказов", "report.process.hint": "Этапы от аванса до оплаты, суммы и просрочки",
    "report.projects": "Проекты: тендеры, авансы, задачи", "report.projects.hint": "Каждый проект: этап, бюджет, аванс и оплата, задачи",
    "report.receivables": "Дебиторская задолженность", "report.receivables.hint": "Отгружено, но не оплачено — по клиентам и срокам",
    "report.sales": "Продажи по клиентам", "report.sales.hint": "Заказы, выручка, оплаты и долги по каждому клиенту",
    "report.stock": "Остатки номенклатуры", "report.stock.hint": "Товары и изделия: остаток и его стоимость",
    "reports.preview": "Предпросмотр", "reports.title": "Отчёты",
    "settings.erp_key": "Ключ:", "settings.erp_url": "ERP una.md, адрес API:", "settings.lang_saved": "Язык изменён.",
    "settings.language": "Язык интерфейса:", "settings.launcher": "Путь к Contragenti (exe/py):", "settings.pass_changed": "Пароль изменён.",
    "settings.password": "Новый пароль:", "settings.saved": "Настройки сохранены.",
    "workspace.contract": "ДОГОВОР С КЛИЕНТОМ", "workspace.execution": "ИСПОЛНЕНИЕ ЗАКАЗОВ: ПРОИЗВОДСТВО, ОПЛАТА, ОТГРУЗКА",
    "workspace.last_orders": "Последние заказы", "workspace.late": "запаздывает %d  ·  %s MDL", "workspace.next_tasks": "Ближайшие задачи",
    "workspace.on_time": "всё в срок", "workspace.summary": "заказов в работе и закрытых: %d   ·   незакрытых просрочено: %d",
}


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    src = json.load(open(src_path, encoding="utf-8"))
    ru_enums = {k: list(v) for k, v in ENUMS.items()}
    ru_enums["stage_title"] = list(process.STAGE_TITLES)
    ru_enums["stage_hint"] = list(process.STAGE_HINTS)
    out = {"_comment": "RO/EN din prototipul crm_delphi/lang.json (PavelTuhari/Contragenti); RU = valorile canonice ale "
                       "prototipului. Chei noi: in toate trei limbile, in acelasi commit (TZ TEC-02). Generat de "
                       "modules/crm/scripts/crm_make_lang.py",
           "default": "ro", "languages": src["languages"], "ro": src["ro"], "en": src["en"],
           "ru": {"strings": RU, "enums": ru_enums}}
    missing = [k for k in src["ro"]["strings"] if k not in RU]
    bad = 0
    for lang in ("ro", "en", "ru"):
        for e, v in ENUMS.items():
            if len(out[lang]["enums"].get(e, [])) != len(v):
                print("ATENTIE %s.%s: %d != %d" % (lang, e, len(out[lang]["enums"].get(e, [])), len(v)))
                bad += 1
        for e in ("stage_title", "stage_hint"):
            if len(out[lang]["enums"].get(e, [])) != 8:
                print("ATENTIE %s.%s" % (lang, e))
                bad += 1
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("lang.json: ro %d, en %d, ru %d strings; chei ro fara ru: %s"
          % (len(out["ro"]["strings"]), len(out["en"]["strings"]), len(RU), missing or "niciuna"))
    sys.exit(1 if (missing or bad) else 0)


if __name__ == "__main__":
    main()
