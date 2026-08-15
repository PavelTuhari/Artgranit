#!/usr/bin/env python3
"""
Генератор SQL-файла с описанием бизнес-процессов модуля «Планограммы».

Схемы хранятся в формате draw.io (mxGraph XML) — тот же файл открывается
в diagrams.net без конвертации и рендерится собственным просмотрщиком
в бэк-офисе. Гиперссылки узлов пишутся штатным для draw.io способом —
через <UserObject link="...">, поэтому клик работает и там, и там.

Запуск:  python3 scripts/gen_plg_processes.py
Результат: sql/91_plg_processes.sql
"""
from __future__ import annotations

import os
import textwrap
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'sql', '91_plg_processes.sql')

MODULE = '/UNA.md/orasldev/planograms'

# Палитра BPMN: задача, шлюз, событие начала/конца, подпроцесс
STYLE = {
    'task':    'rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#1e3a5f;strokeColor=#3b82f6;fontColor=#e8eef7;fontSize=12;',
    'task2':   'rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#14532d;strokeColor=#22c55e;fontColor=#e8eef7;fontSize=12;',
    'task3':   'rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#4a2c0a;strokeColor=#f59e0b;fontColor=#e8eef7;fontSize=12;',
    'gateway': 'rhombus;whiteSpace=wrap;html=1;fillColor=#3f2d0b;strokeColor=#f59e0b;fontColor=#fde68a;fontSize=11;',
    'start':   'ellipse;whiteSpace=wrap;html=1;fillColor=#14532d;strokeColor=#22c55e;fontColor=#dcfce7;fontSize=11;',
    'end':     'ellipse;whiteSpace=wrap;html=1;fillColor=#4c1414;strokeColor=#ef4444;fontColor=#fee2e2;fontSize=11;strokeWidth=3;',
    'edge':    'edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=#64748b;fontColor=#94a3b8;fontSize=10;endArrow=block;endFill=1;',
}
SIZE = {'task': (170, 56), 'task2': (170, 56), 'task3': (170, 56),
        'gateway': (110, 70), 'start': (52, 52), 'end': (52, 52)}


def cell(node_id, label, kind, x, y, link=None):
    w, h = SIZE[kind]
    geom = f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />'
    style = STYLE[kind]
    if link:
        return (f'<UserObject label="{escape(label)}" link="{escape(link)}" id="{node_id}">'
                f'<mxCell style="{style}" vertex="1" parent="1">{geom}</mxCell>'
                f'</UserObject>')
    return (f'<mxCell id="{node_id}" value="{escape(label)}" style="{style}" '
            f'vertex="1" parent="1">{geom}</mxCell>')


def edge(edge_id, src, dst, label=''):
    return (f'<mxCell id="{edge_id}" value="{escape(label)}" style="{STYLE["edge"]}" '
            f'edge="1" parent="1" source="{src}" target="{dst}">'
            f'<mxGeometry relative="1" as="geometry" /></mxCell>')


def diagram(nodes, edges):
    body = ''.join(cell(*n) for n in nodes) + ''.join(edge(*e) for e in edges)
    return ('<mxGraphModel dx="1100" dy="700" grid="0" gridSize="10" guides="1" '
            'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            'pageWidth="1200" pageHeight="700" math="0" shadow="0">'
            '<root><mxCell id="0" /><mxCell id="1" parent="0" />'
            f'{body}</root></mxGraphModel>')


# ==================== Описание процессов ====================
# (node_id, подпись, тип, x, y, ссылка в модуль)

PROCESSES = [
    {
        'code': 'planogram-change', 'sort': 1,
        'ru': 'Изменение выкладки', 'ro': 'Modificarea expunerii', 'en': 'Layout change',
        'dru': 'От инициативы категорийного менеджера до внедрения новой выкладки '
               'в зале с фотоотчётом. Каждый шаг опирается на данные модуля: '
               'проходимость зоны, версии планограммы, задачи мерчандайзеру.',
        'dro': 'De la inițiativa managerului de categorie până la implementarea expunerii.',
        'den': 'From the category manager initiative to the implemented layout.',
        'nodes': [
            ('s1', 'Инициатива', 'start', 40, 150, None),
            ('n1', 'Анализ проходимости зоны', 'task', 130, 143, f'{MODULE}#analytics'),
            ('n2', 'Оценка текущей выкладки', 'task', 340, 143, f'{MODULE}#storemap'),
            ('g1', 'Зона перегружена?', 'gateway', 560, 136, f'{MODULE}#storemap'),
            ('n3', 'Перераспределить полочное пространство', 'task', 720, 40, f'{MODULE}#storemap'),
            ('n4', 'Точечная замена SKU', 'task', 720, 250, f'{MODULE}#products'),
            ('n5', 'Создать версию планограммы', 'task', 940, 143, f'{MODULE}#plglist'),
            ('g2', 'Согласовано?', 'gateway', 940, 300, f'{MODULE}#plglist'),
            ('n6', 'Задача мерчандайзеру', 'task2', 700, 400, f'{MODULE}#tasks'),
            ('n7', 'Внедрение и фотоотчёт', 'task2', 460, 400, f'{MODULE}#docs'),
            ('e1', 'Готово', 'end', 380, 407, f'{MODULE}#history'),
        ],
        'edges': [('c1', 's1', 'n1'), ('c2', 'n1', 'n2'), ('c3', 'n2', 'g1'),
                  ('c4', 'g1', 'n3', 'да'), ('c5', 'g1', 'n4', 'нет'),
                  ('c6', 'n3', 'n5'), ('c7', 'n4', 'n5'), ('c8', 'n5', 'g2'),
                  ('c9', 'g2', 'n6', 'да'), ('c10', 'g2', 'n1', 'нет: доработка'),
                  ('c11', 'n6', 'n7'), ('c12', 'n7', 'e1')],
    },
    {
        'code': 'order-forecast', 'sort': 2,
        'ru': 'Формирование заказа', 'ro': 'Formarea comenzii', 'en': 'Order calculation',
        'dru': 'От истории продаж до заказа поставщику. Модель прогноза выбирается '
               'не на веру: backtest прячет последнюю неделю и сравнивает прогноз '
               'с фактом, а заказ считается со страховым запасом и кратностью короба.',
        'dro': 'De la istoricul vânzărilor până la comanda către furnizor.',
        'den': 'From sales history to the supplier order.',
        'nodes': [
            ('s1', 'Плановый цикл', 'start', 40, 150, None),
            ('n1', 'История продаж по SKU', 'task', 130, 143, f'{MODULE}#analytics'),
            ('n2', 'Выбор модели прогноза', 'task', 340, 143, f'{MODULE}#forecast'),
            ('n3', 'Backtest на факте', 'task', 550, 143, f'{MODULE}#forecast'),
            ('g1', 'MAPE приемлем?', 'gateway', 780, 136, f'{MODULE}#forecast'),
            ('n4', 'Настройка параметров модели', 'task3', 760, 20, f'{MODULE}#forecast'),
            ('n5', 'Прогноз спроса на горизонт', 'task', 950, 143, f'{MODULE}#forecast'),
            ('n6', 'Учёт плановых акций', 'task', 950, 260, f'{MODULE}#promos'),
            ('n7', 'Расчёт заказа: запас и кратность', 'task2', 720, 380, f'{MODULE}#forecast'),
            ('n8', 'Заказ поставщику', 'task2', 470, 380, f'{MODULE}#suppliers'),
            ('e1', 'Заказ размещён', 'end', 390, 387, f'{MODULE}#logistics'),
        ],
        'edges': [('c1', 's1', 'n1'), ('c2', 'n1', 'n2'), ('c3', 'n2', 'n3'),
                  ('c4', 'n3', 'g1'), ('c5', 'g1', 'n4', 'нет'), ('c6', 'n4', 'n2'),
                  ('c7', 'g1', 'n5', 'да'), ('c8', 'n5', 'n6'), ('c9', 'n6', 'n7'),
                  ('c10', 'n7', 'n8'), ('c11', 'n8', 'e1')],
    },
    {
        'code': 'inbound-delivery', 'sort': 3,
        'ru': 'Завоз товара', 'ro': 'Livrarea mărfii', 'en': 'Inbound delivery',
        'dru': 'Схема сети — распределительный центр плюс прямые поставки. '
               'Скоропортящееся идёт в магазин напрямую, остальное через РЦ. '
               'Окна разгрузки не пересекаются ни по доку, ни по машине.',
        'dro': 'Centru de distribuție plus livrări directe.',
        'den': 'Distribution centre plus direct deliveries.',
        'nodes': [
            ('s1', 'Заказ размещён', 'start', 40, 180, f'{MODULE}#forecast'),
            ('g1', 'Тип товара', 'gateway', 130, 173, f'{MODULE}#products'),
            ('n1', 'Прямой завоз в магазин', 'task3', 300, 40, f'{MODULE}#logistics'),
            ('n2', 'Поставка на РЦ', 'task', 300, 280, f'{MODULE}#logistics'),
            ('n3', 'Приёмка на доке', 'task', 520, 280, f'{MODULE}#logistics'),
            ('g2', 'В окно разгрузки?', 'gateway', 740, 273, f'{MODULE}#logistics'),
            ('n4', 'Фиксация опоздания', 'task3', 720, 400, f'{MODULE}#logistics'),
            ('n5', 'Хранение и комплектация', 'task', 900, 280, f'{MODULE}#logistics'),
            ('n6', 'Развозка по магазинам', 'task', 900, 160, f'{MODULE}#logistics'),
            ('n7', 'Выкладка по планограмме', 'task2', 640, 40, f'{MODULE}#plglist'),
            ('e1', 'Товар на полке', 'end', 570, 47, f'{MODULE}#storemap'),
        ],
        'edges': [('c1', 's1', 'g1'), ('c2', 'g1', 'n1', 'фреш'), ('c3', 'g1', 'n2', 'сухой'),
                  ('c4', 'n2', 'n3'), ('c5', 'n3', 'g2'), ('c6', 'g2', 'n4', 'нет'),
                  ('c7', 'n4', 'n5'), ('c8', 'g2', 'n5', 'да'), ('c9', 'n5', 'n6'),
                  ('c10', 'n6', 'n7'), ('c11', 'n1', 'n7'), ('c12', 'n7', 'e1')],
    },
    {
        'code': 'supplier-management', 'sort': 4,
        'ru': 'Работа с поставщиком', 'ro': 'Lucrul cu furnizorul', 'en': 'Supplier management',
        'dru': 'Жизненный цикл поставщика: от заведения карточки и договора '
               'до контроля надёжности поставок и перезаключения контракта. '
               'OTIF и рейтинг считаются по фактическим рейсам.',
        'dro': 'Ciclul de viață al furnizorului: de la fișă până la reînnoirea contractului.',
        'den': 'Supplier lifecycle: from the card to contract renewal.',
        'nodes': [
            ('s1', 'Новый поставщик', 'start', 40, 60, None),
            ('n1', 'Карточка и реквизиты', 'task', 130, 53, f'{MODULE}#suppliers'),
            ('n2', 'Контакты по ролям', 'task', 340, 53, f'{MODULE}#suppliers'),
            ('n3', 'Договор: отсрочка, ретро-бонус', 'task', 550, 53, f'{MODULE}#suppliers'),
            ('n4', 'Закрепление товарных групп', 'task', 760, 53, f'{MODULE}#suppliers'),
            ('n5', 'Плановые поставки', 'task2', 970, 53, f'{MODULE}#logistics'),
            ('g1', 'OTIF ниже нормы?', 'gateway', 990, 200, f'{MODULE}#suppliers'),
            ('n6', 'Претензия и пересмотр условий', 'task3', 740, 300, f'{MODULE}#suppliers'),
            ('g2', 'Контракт истекает?', 'gateway', 520, 300, f'{MODULE}#suppliers'),
            ('n7', 'Перезаключение', 'task', 300, 293, f'{MODULE}#suppliers'),
            ('e1', 'Работа продолжается', 'end', 200, 400, f'{MODULE}#suppliers'),
        ],
        'edges': [('c1', 's1', 'n1'), ('c2', 'n1', 'n2'), ('c3', 'n2', 'n3'),
                  ('c4', 'n3', 'n4'), ('c5', 'n4', 'n5'), ('c6', 'n5', 'g1'),
                  ('c7', 'g1', 'n6', 'да'), ('c8', 'g1', 'g2', 'нет'),
                  ('c9', 'n6', 'g2'), ('c10', 'g2', 'n7', 'да'),
                  ('c11', 'g2', 'e1', 'нет'), ('c12', 'n7', 'e1')],
    },
    {
        'code': 'price-monitoring', 'sort': 5,
        'ru': 'Ценовой мониторинг', 'ro': 'Monitorizarea prețurilor', 'en': 'Price monitoring',
        'dru': 'Сбор цен конкурентов, расчёт ценового индекса по товарным группам '
               'и реакция там, где мы заметно дороже. Средняя цифра по сети '
               'бесполезна — перекос всегда сидит в конкретных категориях.',
        'dro': 'Colectarea prețurilor concurenților și reacția pe categorii.',
        'den': 'Collecting competitor prices and reacting by category.',
        'nodes': [
            ('s1', 'Цикл мониторинга', 'start', 40, 150, None),
            ('n1', 'Полевой аудит и парсинг', 'task', 130, 143, f'{MODULE}#competitors'),
            ('n2', 'Импорт замеров CSV', 'task', 340, 143, f'{MODULE}#competitors'),
            ('n3', 'Расчёт индекса по группам', 'task', 550, 143, f'{MODULE}#competitors'),
            ('g1', 'Индекс ниже 92?', 'gateway', 780, 136, f'{MODULE}#competitors'),
            ('n4', 'Разбор SKU с наибольшим отрывом', 'task3', 950, 40, f'{MODULE}#competitors'),
            ('g2', 'Причина в закупке?', 'gateway', 960, 200, f'{MODULE}#suppliers'),
            ('n5', 'Переговоры с поставщиком', 'task', 740, 330, f'{MODULE}#suppliers'),
            ('n6', 'Пересмотр розничной цены', 'task', 520, 330, f'{MODULE}#products'),
            ('n7', 'Сверка с рынками стран', 'task2', 300, 330, f'{MODULE}#markets'),
            ('e1', 'Цена актуальна', 'end', 220, 400, f'{MODULE}#competitors'),
        ],
        'edges': [('c1', 's1', 'n1'), ('c2', 'n1', 'n2'), ('c3', 'n2', 'n3'),
                  ('c4', 'n3', 'g1'), ('c5', 'g1', 'n4', 'да'), ('c6', 'g1', 'n7', 'нет'),
                  ('c7', 'n4', 'g2'), ('c8', 'g2', 'n5', 'да'), ('c9', 'g2', 'n6', 'нет'),
                  ('c10', 'n5', 'n6'), ('c11', 'n6', 'n7'), ('c12', 'n7', 'e1')],
    },
]


def sql_chunks(text, size=1800):
    """Режем XML на куски: строковый литерал в SQL ограничен 4000 байт."""
    return textwrap.wrap(text, size, break_long_words=True, break_on_hyphens=False,
                         drop_whitespace=False, replace_whitespace=False)


def main():
    parts = ["""-- ============================================================
-- Планограммы: бизнес-процессы модуля
--
-- Схемы хранятся в формате draw.io (mxGraph XML): один и тот же документ
-- открывается в diagrams.net и рисуется собственным просмотрщиком в бэк-офисе.
-- Гиперссылки узлов — штатные для draw.io <UserObject link="...">, поэтому
-- клик по квадрату или ромбу ведёт в соответствующий раздел модуля.
--
-- ФАЙЛ СГЕНЕРИРОВАН: scripts/gen_plg_processes.py — правки вносить там.
-- Префикс объектов: PLG_
-- ============================================================

CREATE SEQUENCE PLG_PROCESSES_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE TABLE PLG_PROCESSES (
  ID          NUMBER        NOT NULL,
  CODE        VARCHAR2(40)  NOT NULL,
  NAME_RU     VARCHAR2(200) NOT NULL,
  NAME_RO     VARCHAR2(200),
  NAME_EN     VARCHAR2(200),
  DESCR_RU    VARCHAR2(2000),
  DESCR_RO    VARCHAR2(2000),
  DESCR_EN    VARCHAR2(2000),
  DIAGRAM_XML CLOB,                       -- mxGraph XML (формат draw.io)
  NODE_COUNT  NUMBER        DEFAULT 0,
  SORT_ORDER  NUMBER        DEFAULT 0,
  STATUS      VARCHAR2(20)  DEFAULT 'active',
  UPDATED_BY  VARCHAR2(150),
  CREATED_AT  TIMESTAMP     DEFAULT SYSTIMESTAMP,
  UPDATED_AT  TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_PLG_PROCESSES PRIMARY KEY (ID),
  CONSTRAINT UQ_PLG_PROC_CODE UNIQUE (CODE),
  CONSTRAINT CHK_PLG_PROC_STATUS CHECK (STATUS IN ('active','draft','archived'))
);
/

CREATE OR REPLACE TRIGGER PLG_PROCESSES_BI
  BEFORE INSERT ON PLG_PROCESSES FOR EACH ROW
  WHEN (NEW.ID IS NULL)
BEGIN
  :NEW.ID := PLG_PROCESSES_SEQ.NEXTVAL;
END;
/

CREATE OR REPLACE TRIGGER PLG_PROCESSES_BU
  BEFORE UPDATE ON PLG_PROCESSES FOR EACH ROW
BEGIN
  :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/
"""]

    for p in PROCESSES:
        xml = diagram(p['nodes'], p['edges'])
        chunks = sql_chunks(xml)
        appends = '\n'.join(
            f"  DBMS_LOB.APPEND(v_xml, TO_CLOB(q'[{c}]'));" for c in chunks)
        node_count = len([n for n in p['nodes'] if n[2] in ('task', 'task2', 'task3', 'gateway')])
        parts.append(f"""
-- ==================== {p['ru']} ====================

DECLARE
  v_xml CLOB;
BEGIN
  DBMS_LOB.CREATETEMPORARY(v_xml, TRUE);
{appends}
  INSERT INTO PLG_PROCESSES (CODE, NAME_RU, NAME_RO, NAME_EN,
                             DESCR_RU, DESCR_RO, DESCR_EN,
                             DIAGRAM_XML, NODE_COUNT, SORT_ORDER, UPDATED_BY)
  VALUES (q'[{p['code']}]', q'[{p['ru']}]', q'[{p['ro']}]', q'[{p['en']}]',
          q'[{p['dru']}]', q'[{p['dro']}]', q'[{p['den']}]',
          v_xml, {node_count}, {p['sort']}, 'system');
  DBMS_LOB.FREETEMPORARY(v_xml);
END;
/
""")

    parts.append("\nCOMMIT;\n")
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))
    print(f"записан {OUT}")
    for p in PROCESSES:
        x = diagram(p['nodes'], p['edges'])
        print(f"  {p['code']:22} узлов {len(p['nodes']):2}  связей {len(p['edges']):2}  XML {len(x)} симв.")


if __name__ == '__main__':
    main()
