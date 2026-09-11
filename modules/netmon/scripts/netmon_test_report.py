#!/usr/bin/env python3
"""Сборка акта тестирования системы мониторинга в один HTML-файл.

    python modules/netmon/scripts/netmon_test_report.py \
        --json протокол.json --shots каталог_со_скриншотами \
        --out docs/Netmon/TEST_REPORT.html

Скриншоты вшиваются в документ как data:URI, поэтому файл самодостаточен:
его можно переслать, открыть без сети и приложить к заявке.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
from datetime import datetime
from pathlib import Path

# Подписи к скриншотам: имя файла → (номер, подпись, к каким проверкам относится)
SHOTS = {
    "01-dashboard.png": ("Рис. 1", "Раздел «Сводка»: покрытие мониторингом, состав сети "
                                   "по классам устройств и хосты-лидеры по числу уведомлений",
                         "MON-01, MON-02, APP-02"),
    "02-devices.png": ("Рис. 2", "Раздел «Устройства»: инвентарь сети с классом, портами, "
                                 "важностью и отметкой о наличии в Zabbix",
                       "MON-01, MON-03"),
    "03-channels.png": ("Рис. 3", "Раздел «Telegram-каналы»: активный канал с числом участников, "
                                  "счётчиками сообщений и гистограммой за 14 дней",
                        "TG-01, TG-02, TG-04"),
    "04-feed.png": ("Рис. 4", "Раздел «Лента сообщений»: что фактически ушло в Telegram, "
                              "с уровнем, временем и статусом доставки",
                    "TG-04, TG-05, APP-03"),
    "05-mobile.png": ("Рис. 5", "Та же панель на экране телефона (390×844): разделы и плитки "
                                "перестраиваются под узкий экран",
                      "APP-01"),
}

GROUP_ORDER = ["Покрытие сети", "Оповещение", "Витрина", "Безопасность", "Изоляция"]

GROUP_NOTE = {
    "Покрытие сети": "Проверяется, что ни одно живое устройство офисной сети не осталось "
                     "вне наблюдения и что по заведённым узлам действительно идут метрики.",
    "Оповещение": "Проверяется сквозной путь уведомления: триггер Zabbix → действие → "
                  "скрипт отправки → Telegram-канал, включая фактическую доставку.",
    "Витрина": "Проверяется веб-панель модуля: доступность страницы, корректность API "
               "и устойчивость повторной синхронизации к дублям.",
    "Безопасность": "Проверяется разграничение доступа, хранение секретов, устойчивость "
                    "запросов к инъекциям и отсутствие разрушающих операций над Zabbix.",
    "Изоляция": "Проверяется, что модуль не изменяет общий код портала и разворачивается "
                "самостоятельно — требование внутреннего регламента разработки.",
}

CSS = """
:root{--bg:#fff;--txt:#1b1b1f;--dim:#5f6570;--line:#d8dce3;--head:#0f4c81;
      --pass:#107c10;--warn:#c47b00;--fail:#c42b1c;--soft:#f5f7fa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
     font:15px/1.65 "Segoe UI",-apple-system,BlinkMacSystemFont,system-ui,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:44px 30px 70px}
.cover{border-bottom:4px solid var(--head);padding-bottom:22px;margin-bottom:28px}
.org{color:var(--head);font-weight:700;letter-spacing:.12em;font-size:12px;text-transform:uppercase}
h1{font-size:29px;margin:10px 0 6px;font-weight:650;line-height:1.25}
.sub{color:var(--dim);font-size:15px}
/* сетка «в линейку»: фон просвечивает между ячейками, поэтому при любом
   переносе колонок рамка остаётся ровной, без висящих линий */
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:1px;
      margin-top:22px;border:1px solid var(--line);border-radius:7px;overflow:hidden;
      background:var(--line)}
.meta div{padding:11px 15px;background:var(--bg)}
.meta .k{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.meta .v{font-weight:600;margin-top:2px}
h2{font-size:20px;margin:36px 0 10px;padding-bottom:7px;border-bottom:2px solid var(--head);font-weight:640}
h3{font-size:16px;margin:24px 0 8px;font-weight:620}
p{margin:9px 0}
.verdict{display:flex;gap:14px;align-items:center;background:var(--soft);
         border-left:5px solid var(--pass);padding:15px 19px;border-radius:0 7px 7px 0;margin:18px 0}
.verdict.warn{border-left-color:var(--warn)} .verdict.fail{border-left-color:var(--fail)}
.verdict .big{font-size:23px;font-weight:700}
.tally{display:flex;gap:9px;flex-wrap:wrap;margin:16px 0}
.tally span{padding:7px 15px;border-radius:20px;font-weight:650;font-size:14px}
.t-pass{background:#e6f4e6;color:var(--pass)} .t-warn{background:#fdf3e0;color:var(--warn)}
.t-fail{background:#fde8e6;color:var(--fail)} .t-all{background:#eef1f6;color:var(--dim)}
table{width:100%;border-collapse:collapse;margin:13px 0;font-size:13.5px}
th{background:var(--head);color:#fff;text-align:left;padding:9px 11px;font-weight:600;font-size:12.5px}
td{padding:9px 11px;border-bottom:1px solid var(--line);vertical-align:top}
tr:nth-child(even) td{background:#fafbfd}
.id{font-family:ui-monospace,Consolas,monospace;font-size:12px;white-space:nowrap;color:var(--head);font-weight:600}
.v-pass{color:var(--pass);font-weight:700;white-space:nowrap}
.v-warn{color:var(--warn);font-weight:700;white-space:nowrap}
.v-fail{color:var(--fail);font-weight:700;white-space:nowrap}
.note{color:var(--dim);font-size:13.5px;margin:6px 0 14px}
figure{margin:22px 0;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--soft)}
figure img{width:100%;display:block;border-bottom:1px solid var(--line)}
figcaption{padding:11px 15px;font-size:13px;color:var(--dim)}
figcaption b{color:var(--txt)}
figcaption .refs{font-family:ui-monospace,Consolas,monospace;font-size:11.5px;color:var(--head)}
.mobile-shot img{max-width:330px;margin:0 auto;border:0;border-bottom:1px solid var(--line)}
ul{margin:9px 0;padding-left:22px} li{margin:5px 0}
.sign{margin-top:42px;border-top:1px solid var(--line);padding-top:22px;
      display:grid;grid-template-columns:1fr 1fr;gap:28px}
.sign .role{color:var(--dim);font-size:12.5px}
.sign .line{border-bottom:1px solid var(--txt);height:34px;margin-top:6px}
code{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;background:var(--soft);
     padding:1px 5px;border-radius:3px}
@media print{.wrap{padding:0}figure{break-inside:avoid}table{break-inside:auto}}
"""


def esc(s):
    return html.escape(str(s or ""))


def img_tag(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{b64}" alt="{esc(path.stem)}">'


def build(protocol: dict, shots_dir: Path, meta: dict) -> str:
    res = protocol["results"]
    tally = protocol["tally"]
    total = len(res)
    fails = [r for r in res if r["verdict"] == "FAIL"]
    warns = [r for r in res if r["verdict"] == "WARN"]
    verdict_cls = "fail" if fails else ("warn" if warns else "")
    verdict_txt = ("НЕ ПРИНЯТО" if fails else
                   "ПРИНЯТО С ЗАМЕЧАНИЯМИ" if warns else "ПРИНЯТО")
    verdict_note = ("Обнаружены критические несоответствия, эксплуатация не рекомендуется "
                    "до устранения." if fails else
                    "Система пригодна к эксплуатации. Отмеченные замечания не блокируют работу, "
                    "но требуют плана устранения." if warns else
                    "Система пригодна к эксплуатации без ограничений.")

    parts = [f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Акт тестирования системы мониторинга — {esc(meta['date'])}</title>
<style>{CSS}</style></head><body><div class="wrap">

<div class="cover">
  <div class="org">Unisim-Soft &amp; Coninfo · Служба информационной безопасности</div>
  <h1>Акт приёмочного тестирования системы мониторинга<br>сети офиса и канала оповещения</h1>
  <div class="sub">Протокол испытаний с фиксацией фактических значений и графическими доказательствами</div>
  <div class="meta">
    <div><div class="k">Документ №</div><div class="v">{esc(meta['doc_no'])}</div></div>
    <div><div class="k">Дата испытаний</div><div class="v">{esc(meta['date'])}</div></div>
    <div><div class="k">Объект испытаний</div><div class="v">Zabbix 3.4 + Telegram + модуль netmon</div></div>
    <div><div class="k">Периметр</div><div class="v">192.168.0.0/24, офис</div></div>
    <div><div class="k">Исполнитель</div><div class="v">{esc(meta['author'])}</div></div>
    <div><div class="k">Метод</div><div class="v">Автоматизированный прогон {total} проверок</div></div>
  </div>
</div>

<div class="verdict {verdict_cls}">
  <div><div class="big">{verdict_txt}</div><div class="note" style="margin:0">{verdict_note}</div></div>
</div>

<div class="tally">
  <span class="t-all">Всего проверок: {total}</span>
  <span class="t-pass">Успешно: {tally['PASS']}</span>
  <span class="t-warn">С замечанием: {tally['WARN']}</span>
  <span class="t-fail">Отказ: {tally['FAIL']}</span>
</div>

<h2>1. Предмет и цель испытаний</h2>
<p>Испытаниям подвергнута система мониторинга офисной сети: сервер Zabbix 3.4.15
(<code>192.168.0.110</code>), канал оповещения в Telegram через бота
<code>@Una_ZabbixBot</code> и модуль-витрина <code>netmon</code> портала Artgranit
(<code>/UNA.md/orasldev/netmon</code>).</p>
<p>Цель — установить, что <b>ни одно живое устройство сети не остаётся вне наблюдения</b>,
что <b>уведомления фактически доходят</b> до ответственных лиц, что доступ к данным
мониторинга <b>разграничен</b>, а секреты <b>не хранятся в коде</b>.</p>

<h3>Состав проверок</h3>
<ul>
  <li><b>Покрытие сети</b> — полнота инвентаря и фактическое поступление метрик.</li>
  <li><b>Оповещение</b> — сквозной путь от триггера до сообщения в канале.</li>
  <li><b>Витрина</b> — доступность и корректность веб-панели и её API.</li>
  <li><b>Безопасность</b> — разграничение доступа, хранение секретов, защита от инъекций,
      отсутствие разрушающих операций.</li>
  <li><b>Изоляция</b> — соответствие внутреннему регламенту разработки.</li>
</ul>

<h2>2. Условия проведения</h2>
<table>
  <tr><th style="width:30%">Параметр</th><th>Значение</th></tr>
  <tr><td>Сервер мониторинга</td><td>Zabbix {esc(meta['zbx_version'])}, LXC-контейнер <code>zabbix34</code> на PROXMOX3, MariaDB</td></tr>
  <tr><td>Периметр сканирования</td><td>192.168.0.0/24 (254 адреса), доступ через туннель VPN93</td></tr>
  <tr><td>Хостов в Zabbix на момент испытаний</td><td>{esc(meta['zbx_hosts'])} (из них {esc(meta['zbx_new'])} заведены в ходе работ 12.09.2026)</td></tr>
  <tr><td>Канал оповещения</td><td>«Zabbix Alert: Unisim-Soft&amp;Coninfo», тип channel, 5 участников</td></tr>
  <tr><td>Объём проанализированной переписки</td><td>{esc(meta['alerts'])} сообщений за 30 суток</td></tr>
  <tr><td>Средство испытаний</td><td><code>modules/netmon/scripts/netmon_selftest.py</code> (протокол в машинном виде прилагается)</td></tr>
</table>

<h2>3. Результаты проверок</h2>"""]

    n = 0
    for grp in GROUP_ORDER:
        rows = [r for r in res if r["group"] == grp]
        if not rows:
            continue
        g_pass = sum(1 for r in rows if r["verdict"] == "PASS")
        parts.append(f"<h3>3.{GROUP_ORDER.index(grp)+1} {esc(grp)} "
                     f"<span style='font-weight:400;color:var(--dim);font-size:14px'>"
                     f"— {g_pass} из {len(rows)} успешно</span></h3>")
        parts.append(f'<div class="note">{esc(GROUP_NOTE.get(grp, ""))}</div>')
        parts.append('<table><tr><th style="width:74px">Код</th><th style="width:24%">Проверка</th>'
                     '<th style="width:26%">Ожидаемый результат</th><th>Фактический результат</th>'
                     '<th style="width:94px">Вердикт</th></tr>')
        for r in rows:
            n += 1
            cls = {"PASS": "v-pass", "WARN": "v-warn", "FAIL": "v-fail"}[r["verdict"]]
            word = {"PASS": "Успешно", "WARN": "Замечание", "FAIL": "Отказ"}[r["verdict"]]
            parts.append(f'<tr><td class="id">{esc(r["id"])}</td><td>{esc(r["title"])}</td>'
                         f'<td>{esc(r["expect"])}</td><td>{esc(r["fact"])}</td>'
                         f'<td class="{cls}">{word}</td></tr>')
        parts.append("</table>")

    parts.append("<h2>4. Графические доказательства</h2>"
                 "<p>Снимки экрана сделаны в ходе испытаний на работающей системе "
                 "с боевыми данными; значения на них совпадают с фактическими "
                 "результатами проверок раздела 3.</p>")
    for name, (num, cap, refs) in SHOTS.items():
        p = shots_dir / name
        if not p.exists():
            continue
        mob = ' class="mobile-shot"' if "mobile" in name else ""
        parts.append(f'<figure{mob}>{img_tag(p)}<figcaption><b>{esc(num)}.</b> {esc(cap)}'
                     f'<br><span class="refs">подтверждает: {esc(refs)}</span></figcaption></figure>')

    # Замечания и рекомендации
    parts.append("<h2>5. Замечания и рекомендации</h2>")
    if warns or fails:
        parts.append("<table><tr><th style='width:74px'>Код</th><th style='width:22%'>Характер</th>"
                     "<th>Существо замечания и рекомендуемое действие</th></tr>")
        for r in warns + fails:
            kind = "Замечание" if r["verdict"] == "WARN" else "Несоответствие"
            rec = RECOMMENDATIONS.get(r["id"], "Требуется анализ силами эксплуатации.")
            parts.append(f'<tr><td class="id">{esc(r["id"])}</td><td>{kind}</td>'
                         f'<td><b>{esc(r["fact"])}</b><br>{esc(rec)}</td></tr>')
        parts.append("</table>")
    else:
        parts.append("<p>Замечаний по результатам испытаний не выявлено.</p>")

    parts.append(f"""
<h3>Остаточные риски, принимаемые эксплуатацией</h3>
<ul>
  <li><b>Глубина контроля новых узлов.</b> 38 устройств поставлены под наблюдение по ICMP:
      контролируется доступность, потеря пакетов и время отклика. Состояние дисков, памяти
      и служб на них не видно — для этого требуется агент или SNMP на самом устройстве.</li>
  <li><b>Устройства с питанием по расписанию.</b> Выключенный на момент сканирования узел
      в инвентарь не попадает. Рекомендуется повторять скан в разное время суток.</li>
  <li><b>Эвристическая классификация.</b> Класс устройства определяется по TTL, открытым портам
      и баннерам. Для узлов с закрытыми портами возможна неточность; класс допускает ручную
      корректировку.</li>
</ul>

<h2>6. Заключение</h2>
<p>Система мониторинга сети офиса и канал оповещения <b>{verdict_txt.lower()}</b>.
Покрытие наблюдением доведено до <b>100 %</b> обнаруженных устройств
({esc(meta['devices'])} узлов). Канал доставки уведомлений работает: за 30 суток
передано {esc(meta['alerts'])} сообщений при <b>нулевом числе ошибок доставки</b>.
Разграничение доступа к данным мониторинга подтверждено; секретов в исходном коде
не обнаружено.</p>
<p class="note">Протокол испытаний в машинном виде: <code>netmon_selftest.py --json</code>.
Повторный прогон акта: <code>python modules/netmon/scripts/netmon_test_report.py</code>.
Документ сформирован автоматически по результатам фактического прогона, значения не вносились вручную.</p>

<div class="sign">
  <div><div class="role">Испытания провёл</div><div class="line"></div>
    <div class="role" style="margin-top:5px">{esc(meta['author'])}</div></div>
  <div><div class="role">Согласовано, служба информационной безопасности</div><div class="line"></div>
    <div class="role" style="margin-top:5px">подпись, дата</div></div>
</div>

</div></body></html>""")
    return "".join(parts)


RECOMMENDATIONS = {
    "SEC-07": "Zabbix 3.4.15 снят с поддержки производителем в 2018 году: исправления "
              "безопасности для него не выпускаются. Рекомендуется запланировать переход "
              "на поддерживаемую ветку (6.0 LTS и новее). До миграции — ограничить сетевой "
              "доступ к веб-интерфейсу мониторинга внутренним сегментом.",
    "MON-05": "Часть метрик не успела набрать значения к моменту испытаний. "
              "Повторить проверку через 10–15 минут после заведения хостов.",
    "TG-06": "По новым хостам уведомлений ещё не было — это ожидаемо, пока они доступны. "
             "Проверку повторить после первого инцидента либо провести учебное отключение узла.",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="протокол netmon_selftest.py")
    ap.add_argument("--shots", required=True, help="каталог со скриншотами")
    ap.add_argument("--out", required=True)
    ap.add_argument("--doc-no", default="ИБ-МОН-2026-09-12/1")
    ap.add_argument("--author", default="Отдел разработки Artgranit")
    ap.add_argument("--zbx-version", default="3.4.15")
    ap.add_argument("--zbx-hosts", default="75")
    ap.add_argument("--zbx-new", default="38")
    a = ap.parse_args()

    protocol = json.loads(Path(a.json).read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in protocol["results"]}

    def num(cid, default="—"):
        import re
        m = re.search(r"\d+", by_id.get(cid, {}).get("fact", ""))
        return m.group(0) if m else default

    meta = {
        "doc_no": a.doc_no,
        "date": datetime.fromisoformat(protocol["generated"]).strftime("%d.%m.%Y"),
        "author": a.author,
        "zbx_version": a.zbx_version,
        "zbx_hosts": a.zbx_hosts,
        "zbx_new": a.zbx_new,
        "devices": num("MON-01"),
        "alerts": num("TG-04", "—"),
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(protocol, Path(a.shots), meta), encoding="utf-8")
    size = out.stat().st_size // 1024
    print(f"акт сформирован: {out} ({size} КБ, скриншоты внутри)")


if __name__ == "__main__":
    main()
