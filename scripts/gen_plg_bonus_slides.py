#!/usr/bin/env python3
"""
Добавляет в презентацию модуля «Планограммы» блок слайдов для сети Bonus.

Опора — только проверяемые факты: 11 магазинов сети уже заведены в модуле
TBControl этого же приложения (см. docs/TBControl/SCENARIOS.md и таблицу
TBC_STORES), Oracle и сервер общие, интерфейс трёхъязычный.

Про чужие продукты утверждений НЕ делаем: вместо «у них плохо, у нас хорошо»
дан чек-лист вопросов, которые сеть задаёт любому поставщику ПО, — выводы
менеджеры делают сами по фактам, а не по нашим словам.

Запуск: python3 scripts/gen_plg_bonus_slides.py
"""
from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECK = os.path.join(ROOT, 'docs', 'Planograms', 'presentation.html')
MODULE = '/UNA.md/orasldev/planograms'
TBC = '/UNA.md/orasldev/tbcontrol'

# Магазины сети — как они заведены в TBControl
STORES = [
    ('MD-CHS-001', 'Магазин №1 Центр', 'Кишинёв'),
    ('MD-CHS-002', 'Магазин №2 Ботаника', 'Кишинёв'),
    ('MD-CHS-003', 'Магазин №3 Рышкановка', 'Кишинёв'),
    ('MD-CHS-010', 'Bonus Дачия', 'Кишинёв'),
    ('MD-CHS-011', 'Super Bonus Мунчешть', 'Кишинёв'),
    ('MD-CHS-012', 'Local Крянгэ', 'Кишинёв'),
    ('MD-CHS-013', 'Local Expres Москова', 'Кишинёв'),
    ('MD-CHS-014', 'Foxi Петрикань', 'Кишинёв'),
    ('MD-BLT-101', 'Магазин №101 Бельцы', 'Бельцы'),
    ('MD-BLT-102', 'Foxi Бельцы Центр', 'Бельцы'),
    ('MD-ORH-201', 'Local Орхей', 'Орхей'),
]


def livebar(links, hint=''):
    items = ''.join(
        f'<a class="live {cls}" href="{href}" target="_blank" rel="noopener">{text}</a>'
        for text, href, cls in links)
    tail = f'<span class="hint">{hint}</span>' if hint else ''
    return f'<div class="foot"><div class="livebar">{items}{tail}</div></div>'


def store_rows():
    return ''.join(
        f'<tr><td class="mono" style="font-family:ui-monospace,monospace;font-size:12px">{c}</td>'
        f'<td><b>{n}</b></td><td class="muted">{city}</td>'
        f'<td><span class="pill ok">под контуром</span></td></tr>'
        for c, n, city in STORES)


SLIDES = f"""
<!-- Bonus: сеть сегодня -->
<section class="slide">
  <div class="kicker">Сеть Bonus</div>
  <h2>Мы уже внутри вашего контура</h2>
  <div class="cols">
    <div>
      <p>Одиннадцать магазинов сети — Bonus, Super Bonus, Local, Local Expres,
         Foxi — уже заведены в этой же системе: модуль эксплуатации следит
         за кассами, серверами, самообслуживанием и климатом серверных.</p>
      <div class="cols" style="grid-template-columns:1fr 1fr; gap:12px; margin:18px 0">
        <div class="stat"><div class="v">11</div><div class="l">магазинов сети</div></div>
        <div class="stat g"><div class="v">39</div><div class="l">устройств под контролем</div></div>
        <div class="stat w"><div class="v">5</div><div class="l">брендов сети</div></div>
        <div class="stat v"><div class="v">3</div><div class="l">города</div></div>
      </div>
      <div class="card accent">
        <h3>Что это меняет</h3>
        <p>Планограммы — не новая система, а следующий раздел в том,
           чем сеть уже пользуется. Тот же адрес, тот же вход, та же база
           Oracle, тот же сервер. Отдельного внедрения не требуется.</p>
      </div>
    </div>
    <div>
      <div class="card" style="padding:0; overflow:hidden">
        <table>
          <thead><tr><th>Код</th><th>Магазин</th><th>Город</th><th>Статус</th></tr></thead>
          <tbody>{store_rows()}</tbody>
        </table>
      </div>
    </div>
  </div>
  {livebar([('Открыть модуль планограмм', f'{MODULE}#overview', ''),
            ('Ассортимент и категории', f'{MODULE}#products', 'blue')],
           'список магазинов — из таблицы TBC_STORES; контур эксплуатации открывается по входу')}
  <div class="num">X</div>
</section>

<!-- Bonus: что получает каждый -->
<section class="slide">
  <div class="kicker">Сеть Bonus · роли</div>
  <h2>Что получает каждый менеджер в первый же день</h2>
  <div class="cols3" style="margin-bottom:16px">
    <div class="card accent">
      <h3>◈ Категорийный менеджер</h3>
      <p>Актуальная выкладка по всем 11 магазинам в одном месте, версии
         и согласование вместо переписки. Видно, какие зоны недорабатывают
         по проходимости и где мы дороже конкурента.</p>
    </div>
    <div class="card ok">
      <h3>◆ Закупщик</h3>
      <p>Заказ считается моделью с измеренной точностью, а не «по опыту».
         Учитываются запланированные акции, срок поставки и кратность короба —
         на выходе готовый заказ поставщику.</p>
    </div>
    <div class="card warn">
      <h3>▤ Руководитель логистики</h3>
      <p>График завоза по трём плечам на одной диаграмме: кто, куда, в какое
         окно, кто опоздал. Загрузка парка видна полосами — сразу понятно,
         где перекос.</p>
    </div>
  </div>
  <div class="cols3">
    <div class="card" style="border-left:3px solid var(--violet)">
      <h3>◇ Коммерческий директор</h3>
      <p>Ценовой индекс по товарным группам против Linella, Kaufland, Nr.1,
         Fidesco. Плюс бенчмарк с сетями Румынии, Польши, Украины —
         где сеть стоит по выручке с метра и среднему чеку.</p>
    </div>
    <div class="card crit">
      <h3>◉ Поставщик-менеджер</h3>
      <p>Карточка поставщика: контакты по ролям, договоры с отсрочкой
         и ретро-бонусом, товарные группы. Список контрактов, истекающих
         в ближайшие 60 дней, — одним флажком.</p>
    </div>
    <div class="card">
      <h3>⚙ ИТ-служба</h3>
      <p>Ни одной новой системы в ландшафте: та же Oracle, тот же сервер,
         тот же процесс обновления. Исходный код у сети. Все действия
         записи — в журнале.</p>
    </div>
  </div>
  {livebar([('Выкладка', f'{MODULE}#storemap', ''),
            ('Заказ', f'{MODULE}#forecast', 'blue'),
            ('Завоз', f'{MODULE}#logistics', 'blue'),
            ('Конкуренты', f'{MODULE}#competitors', 'blue'),
            ('Поставщики', f'{MODULE}#suppliers', 'blue')])}
  <div class="num">X</div>
</section>

<!-- Bonus: чек-лист выбора -->
<section class="slide">
  <div class="kicker">Сеть Bonus · выбор поставщика</div>
  <h2>Семь вопросов, которые стоит задать любому вендору</h2>
  <p>Включая нас. Ответы ниже — про эту систему; их можно проверить прямо
     на слайде по ссылкам, не дожидаясь демо-стенда.</p>
  <div class="card" style="padding:0; overflow:hidden; margin-top:6px">
    <table>
      <thead><tr><th style="width:52%">Вопрос</th><th>Ответ по этой системе</th></tr></thead>
      <tbody>
        <tr><td>Где физически лежат данные сети?</td>
            <td>В вашей Oracle, рядом с остальными модулями. Выгрузка не нужна —
                данные и так ваши</td></tr>
        <tr><td>Что будет, если мы захотим уйти?</td>
            <td>Таблицы <code>PLG_*</code> остаются в вашей базе, схема
                документирована, исходный код у сети</td></tr>
        <tr><td>Сколько стоит подключить 12-й магазин?</td>
            <td>Строка в справочнике. Лицензии на магазин в этой системе нет</td></tr>
        <tr><td>Работает ли на румынском?</td>
            <td>RU / RO / EN с первого релиза, включая названия зон,
                категорий и поставщиков</td></tr>
        <tr><td>Можно ли проверить точность заказа <b>до</b> внедрения?</td>
            <td>Да: backtest на вашей истории продаж, метрики MAPE / MAE /
                смещение по каждой модели</td></tr>
        <tr><td>Как описаны бизнес-процессы?</td>
            <td>BPMN-схемы в формате draw.io, редактируются в системе,
                фигуры ведут в рабочие разделы</td></tr>
        <tr><td>Что с интеграцией в то, что уже работает?</td>
            <td>Тот же сервер, тот же вход, тот же контур эксплуатации сети —
                интеграция уже сделана</td></tr>
      </tbody>
    </table>
  </div>
  {livebar([('Проверить: прогноз и backtest', f'{MODULE}#forecast', ''),
            ('Проверить: бизнес-процессы', f'{MODULE}#processes', 'blue'),
            ('Проверить: документация', f'{MODULE}/docs', 'blue')],
           'каждый ответ проверяется по ссылке')}
  <div class="num">X</div>
</section>

<!-- Bonus: механика перехода -->
<section class="slide">
  <div class="kicker">Сеть Bonus · переход</div>
  <h2>Переход без остановки работы</h2>
  <p>Ничего не выключается одномоментно. Новая система набирает данные
     параллельно, пока сеть работает как обычно, — и её видно в деле
     раньше, чем принято решение.</p>
  <div class="cols3" style="margin-top:14px">
    <div class="card ok">
      <h3>Что переносим</h3>
      <p>Справочник магазинов — уже перенесён (11 точек в системе).
         Дальше: товары и категории, поставщики с договорами, история продаж
         выгрузкой в тестовый набор. Всё через файл, без доступа к чужому API.</p>
    </div>
    <div class="card accent">
      <h3>Что работает параллельно</h3>
      <p>Первые недели сеть заказывает как раньше, а система считает свой
         вариант заказа рядом. Сравниваются две цифры на одних и тех же данных —
         спор о точности закрывается фактом.</p>
    </div>
    <div class="card warn">
      <h3>Чего не будет</h3>
      <p>Ни остановки касс, ни нового сервера, ни отдельного входа для
         сотрудников, ни платы за подключение следующего магазина.
         Контур эксплуатации сети продолжает работать как работал.</p>
    </div>
  </div>
  <div class="card" style="margin-top:14px">
    <h3>Стартовые точки, которые предлагаем</h3>
    <p style="font-size:14.5px">
      <b>Super Bonus Мунчешть</b> — крупный формат, максимум ассортимента и
      сложная выкладка. <b>Bonus Дачия</b> — типовой городской магазин.
      <b>Local Expres Москова</b> — малый формат с частым завозом.
      Три разных профиля спроса дают честную картину по всей сети,
      а не по одному удачному магазину.</p>
  </div>
  {livebar([('Открыть систему', f'{MODULE}#overview', ''),
            ('Загрузить свой набор данных', f'{MODULE}#testdata', 'blue'),
            ('Сравнение моделей заказа', f'{MODULE}#forecast', 'blue'),
            ('Как это устроено', f'{MODULE}/docs', 'blue')])}
  <div class="num">X</div>
</section>
"""


def main():
    with open(DECK, encoding='utf-8') as f:
        deck = f.read()

    if 'Сеть Bonus' in deck:
        print('слайды для Bonus уже есть — выходим, чтобы не задвоить')
        return

    slides = re.findall(r'<section class="slide.*?</section>', deck, re.S)
    last = slides[-1]                       # «Пилот на три недели» — оставляем финалом
    deck = deck.replace(last, SLIDES + '\n' + last, 1)

    n = [0]

    def renum(m):
        n[0] += 1
        return f'<div class="num">{n[0]}</div>'

    deck = re.sub(r'<div class="num">[^<]*</div>', renum, deck)

    with open(DECK, 'w', encoding='utf-8') as f:
        f.write(deck)

    total = len(re.findall(r'<section class="slide', deck))
    live = len(re.findall(r'class="live', deck))
    print(f'слайдов: {total} (добавлено 4), живых ссылок: {live}')


if __name__ == '__main__':
    main()
