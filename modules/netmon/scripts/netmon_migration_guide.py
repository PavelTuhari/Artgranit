#!/usr/bin/env python3
"""Сборка пошаговой инструкции по миграции Zabbix в один HTML-файл.

    python modules/netmon/scripts/netmon_migration_guide.py \
        --out docs/Netmon/MIGRATION_GUIDE.html

Инструкция рассчитана на исполнителя: команды копируются кнопкой, каждый шаг
имеет проверку результата и признак необратимости. Данные о текущей системе
подставляются из обследования, чтобы не держать их в двух местах.

Полный план и обоснование решений: docs/Netmon/ZABBIX_MIGRATION_PLAN.md
"""
from __future__ import annotations

import argparse
import html
from datetime import datetime
from pathlib import Path

# Факты обследования 12.09.2026 — подставляются в текст инструкции
FACTS = {
    "old_ip": "192.168.0.110", "old_ct": "101", "old_ver": "3.4.15",
    "old_os": "CentOS 7.9.2009", "old_db": "MariaDB 5.5.68", "old_php": "PHP 5.6.40",
    "db_size": "1 532,7 МБ", "db_charset": "utf8 / utf8_bin", "dbversion": "3040000",
    "hosts": "77", "items": "2 734", "triggers": "1 699",
    "new_ip": "192.168.0.111", "new_vmid": "141", "new_name": "zabbix8",
    "pve": "192.168.0.149", "pve_ver": "4.4-1",
    "iso": "ubuntu-22.04.3-live-server-amd64.iso",
    "zbx_new": "8.0 LTS", "os_new": "Ubuntu 22.04.3 LTS",
}

STEPS = [
    # (этап, № , заголовок, что делаем, команды, проверка, необратимо?)
    ("Подготовка", "0.1", "Снять полный дамп базы",
     "Дамп — единственная страховка на весь проект. Снимается на работающей системе, "
     "простоя не требует.",
     "ssh root@{old_ip}\n"
     "mysqldump -uroot --single-transaction --quick --default-character-set=utf8 \\\n"
     "          --routines --triggers zabbix | gzip > /root/zabbix34-$(date +%F).sql.gz\n"
     "ls -lh /root/zabbix34-*.sql.gz\n"
     "gunzip -t /root/zabbix34-*.sql.gz && echo 'архив цел'",
     "Файл 300–400 МБ, проверка целостности без ошибок.", False),

    ("Подготовка", "0.2", "Сохранить скрипты и конфигурацию",
     "Внешние скрипты и alert-скрипт Telegram в базе не лежат — только файлами. "
     "Токен бота находится внутри telegram_bot.sh.",
     "ssh root@{old_ip}\n"
     "tar czf /root/zabbix34-files-$(date +%F).tar.gz \\\n"
     "    /etc/zabbix /usr/lib/zabbix/externalscripts /usr/lib/zabbix/alertscripts\n"
     "ls -lh /root/zabbix34-files-*.tar.gz",
     "Архив создан, внутри 8 внешних скриптов и telegram_bot.sh.", False),

    ("Подготовка", "0.3", "Выгрузить конфигурацию через API",
     "Вторая, независимая от дампа копия конфигурации — на случай, если апгрейд схемы "
     "не удастся и придётся собирать систему заново.",
     "cd /Users/pt/Projects.AI/Artgranit-netmon\n"
     "python modules/netmon/scripts/netmon_zabbix_export.py --out ~/zbx-export",
     "53 шаблона и 75 хостов в XML, файл inventory.json со списком.", False),

    ("Подготовка", "0.4", "Освободить память на гипервизоре",
     "Кэш ZFS занимает 78,7 ГБ из 157 ГБ. Он отдаёт память сам, но при старте новой ВМ "
     "возможна просадка ввода-вывода — лучше ограничить заранее.",
     "ssh root@{pve}\n"
     "echo 68719476736 > /sys/module/zfs/parameters/zfs_arc_max\n"
     "echo 'options zfs zfs_arc_max=68719476736' >> /etc/modprobe.d/zfs.conf\n"
     "update-initramfs -u",
     "cat /sys/module/zfs/parameters/zfs_arc_max → 68719476736", False),

    ("Развёртывание", "1.1", "Создать виртуальную машину",
     "KVM, а не контейнер: на Proxmox {pve_ver} ядро 4.4, и контейнер с Ubuntu 22.04 "
     "не запустится. У виртуальной машины собственное ядро.",
     "ssh root@{pve}\n"
     "qm create {new_vmid} --name {new_name} --memory 8192 --cores 4 --sockets 1 \\\n"
     "  --net0 virtio,bridge=vmbr0 --ostype l26 --machine pc-i440fx-2.7 \\\n"
     "  --scsihw virtio-scsi-pci --scsi0 local-zfs:100,discard=on \\\n"
     "  --ide2 local:iso/{iso},media=cdrom \\\n"
     "  --boot order='ide2;scsi0' --onboot 1 --agent 1\n"
     "qm start {new_vmid}",
     "qm status {new_vmid} → running; консоль открывается в веб-интерфейсе Proxmox.", False),

    ("Развёртывание", "1.2", "Установить Ubuntu и задать сеть",
     "Адрес {new_ip} свободен: он закреплён за контейнером 130 «zabbixt», который "
     "остановлен и помечен как неиспользуемый.",
     "# в установщике Ubuntu:\n"
     "#   IP       {new_ip}/24\n"
     "#   шлюз     192.168.0.101\n"
     "#   DNS      192.168.0.103, 192.168.0.102\n"
     "#   имя      {new_name}\n"
     "# после установки:\n"
     "apt update && apt -y upgrade && apt -y install qemu-guest-agent\n"
     "systemctl enable --now qemu-guest-agent",
     "ping {new_ip} проходит; в Proxmox у ВМ отображается IP.", False),

    ("Развёртывание", "1.3", "Поставить СУБД и создать базу",
     "Кодировка сразу utf8mb4: Zabbix {zbx_new} корректно работает только с ней, "
     "а старая база в utf8. Пароль — случайный, не «zabbix», как сейчас.",
     "apt -y install mariadb-server\n"
     "PW=$(openssl rand -base64 24)\n"
     "echo \"пароль БД: $PW\"   # записать в Keychain, в файлы не класть\n"
     "mysql -uroot <<SQL\n"
     "CREATE DATABASE zabbix CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;\n"
     "CREATE USER zabbix@localhost IDENTIFIED BY '$PW';\n"
     "GRANT ALL ON zabbix.* TO zabbix@localhost;\n"
     "SET GLOBAL log_bin_trust_function_creators = 1;\n"
     "SQL",
     "SHOW CREATE DATABASE zabbix содержит utf8mb4.", False),

    ("Развёртывание", "1.4", "Поднять лимиты СУБД под импорт",
     "На старом сервере max_allowed_packet = 1 МБ. С таким значением импорт истории "
     "оборвётся на первой же крупной строке.",
     "cat >> /etc/mysql/mariadb.conf.d/99-zabbix.cnf <<CNF\n"
     "[mysqld]\n"
     "max_allowed_packet = 64M\n"
     "innodb_buffer_pool_size = 4G\n"
     "innodb_file_per_table = ON\n"
     "CNF\n"
     "systemctl restart mariadb\n"
     "mysql -uroot -e \"SHOW VARIABLES LIKE 'max_allowed_packet'\"",
     "max_allowed_packet = 67108864.", False),

    ("Развёртывание", "1.5", "Установить Zabbix {zbx_new}",
     "Ubuntu 22.04 входит в матрицу поддержки Zabbix 8.0 — проверено в репозитории.",
     "wget https://repo.zabbix.com/zabbix/8.0/release/ubuntu/pool/main/z/zabbix-release/\\\n"
     "zabbix-release_8.0-0.2+ubuntu22.04_all.deb\n"
     "dpkg -i zabbix-release_8.0-*.deb && apt update\n"
     "apt -y install zabbix-server-mysql zabbix-frontend-php zabbix-nginx-conf \\\n"
     "               zabbix-sql-scripts zabbix-agent2 fping snmp unixodbc\n"
     "zabbix_server -V",
     "zabbix_server -V показывает 8.0.x.", False),

    ("Перенос базы", "2.1", "Перенести дамп на новую машину",
     "Передаётся 300–400 МБ по локальной сети.",
     "scp root@{old_ip}:/root/zabbix34-*.sql.gz /root/\n"
     "scp root@{old_ip}:/root/zabbix34-files-*.tar.gz /root/\n"
     "ls -lh /root/zabbix34-*",
     "Оба архива на месте, размеры совпадают с исходными.", False),

    ("Перенос базы", "2.2", "Импортировать базу с конвертацией кодировки",
     "Дамп снят в utf8, а база создана в utf8mb4 — объявления кодировки заменяются "
     "на лету, иначе таблицы вернутся к старой кодировке.",
     "zcat /root/zabbix34-*.sql.gz \\\n"
     "  | sed -e 's/CHARSET=utf8 /CHARSET=utf8mb4 /g' \\\n"
     "        -e 's/CHARSET=utf8;/CHARSET=utf8mb4;/g' \\\n"
     "        -e 's/COLLATE=utf8_bin/COLLATE=utf8mb4_bin/g' \\\n"
     "  | mysql -uroot zabbix\n"
     "mysql -uroot zabbix -e \"SELECT COUNT(*) FROM history; SELECT COUNT(*) FROM hosts;\"",
     "140 таблиц; число строк history совпадает со старым сервером; "
     "SHOW TABLE STATUS показывает utf8mb4_bin.", False),

    ("Перенос базы", "2.3", "Прописать базу в конфигурации сервера",
     "Переносим параметры, отличающиеся от стандартных: они подобраны под текущую "
     "нагрузку и на новом сервере нужны те же.",
     "cat >> /etc/zabbix/zabbix_server.conf <<CFG\n"
     "DBPassword=<пароль из шага 1.3>\n"
     "StartPollers=20\n"
     "StartPollersUnreachable=10\n"
     "StartPingers=5\n"
     "StartDiscoverers=5\n"
     "StartHTTPPollers=5\n"
     "CacheSize=256M\n"
     "Timeout=30\n"
     "CFG",
     "Файл без опечаток; пароль совпадает с созданным.", False),

    ("Перенос базы", "2.4", "Запустить сервер — пойдёт апгрейд схемы 3.4 → 8.0",
     "Ключевой шаг. Zabbix 8.0 поддерживает прямой апгрейд начиная с версии 2.0, "
     "поэтому промежуточные версии не нужны. На 11 млн строк истории займёт "
     "от 30 до 90 минут. Старый сервер в это время продолжает работать.",
     "ssh root@{pve} 'qm snapshot {new_vmid} before-db-upgrade'   # снимок ДО запуска\n"
     "systemctl start zabbix-server\n"
     "tail -f /var/log/zabbix/zabbix_server.log | grep -i 'database upgrade'",
     "В логе «database upgrade fully completed»; "
     "SELECT mandatory FROM dbversion показывает версию 8.0, а не {dbversion}.", True),

    ("Перенос базы", "2.5", "Вернуть внешние скрипты",
     "Скрипты в базе не хранятся. Пять из восьми обращаются к Oracle через sqlplus "
     "или cx_Oracle, им нужен клиент либо переписывание.",
     "tar xzf /root/zabbix34-files-*.tar.gz -C /\n"
     "chown -R zabbix:zabbix /usr/lib/zabbix/externalscripts\n"
     "chmod 750 /usr/lib/zabbix/externalscripts/*\n"
     "ls -l /usr/lib/zabbix/externalscripts/",
     "8 скриптов на месте, владелец zabbix, права на запуск.", False),

    ("Перенос базы", "2.6", "Портировать pyora.py на Python 3",
     "Единственная работа, требующая написания кода: скрипт написан на Python 2.7 "
     "с cx_Oracle, а в Ubuntu 22.04 интерпретатора python2 нет. Библиотека oracledb "
     "в тонком режиме не требует Oracle Instant Client.",
     "apt -y install python3-pip\n"
     "pip3 install oracledb\n"
     "# в скрипте: import cx_Oracle  →  import oracledb as cx_Oracle\n"
     "#            print \"x\"        →  print(\"x\")\n"
     "#            cx_Oracle.connect(...) работает без клиента в тонком режиме\n"
     "sudo -u zabbix /usr/lib/zabbix/externalscripts/pyora.py --help",
     "Скрипт запускается и возвращает значение, а не трассировку.", False),

    ("Перенос базы", "2.7", "Вернуть отправку в Telegram",
     "Alert-скрипт содержит токен бота. Канал и действие уже перенеслись вместе "
     "с базой — их создавать заново не нужно.",
     "chmod 750 /usr/lib/zabbix/alertscripts/telegram_bot.sh\n"
     "chown zabbix:zabbix /usr/lib/zabbix/alertscripts/telegram_bot.sh\n"
     "sudo -u zabbix /usr/lib/zabbix/alertscripts/telegram_bot.sh \\\n"
     "     -1001544437696 'Проверка' 'Тест с нового сервера Zabbix 8.0'",
     "Сообщение появилось в канале «Zabbix Alert: Unisim-Soft&Coninfo».", False),

    ("Перенос базы", "2.8", "Включить веб-интерфейс",
     "Фронтенд на nginx + PHP-FPM 8.1 из репозитория Ubuntu.",
     "sed -i 's/# listen 8080;/listen 80;/; s/# server_name example.com;/server_name {new_ip};/' \\\n"
     "    /etc/zabbix/nginx.conf\n"
     "systemctl restart nginx php8.1-fpm\n"
     "systemctl enable zabbix-server zabbix-agent2 nginx php8.1-fpm\n"
     "curl -I http://{new_ip}/",
     "Открывается веб-интерфейс; вход существующими учётными записями работает — "
     "пароли перенеслись вместе с базой.", False),

    ("Параллельная работа", "3.1", "Направить агенты на оба сервера",
     "Пассивные проверки заработают сразу, активным (282 элемента) нужен "
     "ServerActive. Пока указаны оба сервера, данные собирают обе системы.",
     "# на каждом наблюдаемом хосте, в /etc/zabbix/zabbix_agentd.conf:\n"
     "#   Server={old_ip},{new_ip}\n"
     "#   ServerActive={old_ip},{new_ip}\n"
     "systemctl restart zabbix-agent",
     "На новом сервере элементы получают значения; в «Последних данных» идут числа.",
     False),

    ("Параллельная работа", "3.2", "Сверить полноту сбора",
     "Расхождение больше 5 % означает, что часть проверок на новом сервере не "
     "работает — искать причину до переключения.",
     "# на обоих серверах:\n"
     "mysql -uroot zabbix -e \"SELECT COUNT(*) FROM items WHERE status=0 AND state=0\"\n"
     "# и сравнить значения",
     "Число работающих элементов отличается не более чем на 5 %.", False),

    ("Параллельная работа", "3.3", "Проверить приёмочными тестами",
     "Готовый прогон проверяет покрытие, доставку уведомлений и безопасность.",
     "cd /Users/pt/Projects.AI/Artgranit-netmon\n"
     "# в modules/netmon/sources.py заменить ZBX_URL на новый сервер\n"
     "python modules/netmon/scripts/netmon_selftest.py --json /tmp/after.json",
     "0 отказов. Замечание SEC-07 про устаревшую версию должно исчезнуть.", False),

    ("Переключение", "4.1", "Остановить отправку уведомлений со старого сервера",
     "Иначе два сервера будут слать в один канал дубли.",
     "# на СТАРОМ сервере, в веб-интерфейсе:\n"
     "#   Administration → Actions → Telegram → Disabled\n"
     "# либо через API",
     "В канал приходит по одному сообщению на событие, а не по два.", False),

    ("Переключение", "4.2", "Убрать старый сервер из агентов",
     "После этого мониторинг полностью работает на новом сервере.",
     "# в /etc/zabbix/zabbix_agentd.conf оставить только новый:\n"
     "#   Server={new_ip}\n"
     "#   ServerActive={new_ip}\n"
     "systemctl restart zabbix-agent",
     "На новом сервере данные продолжают поступать, на старом — прекратились.", False),

    ("Переключение", "4.3", "Остановить старый сервер, контейнер не удалять",
     "Контейнер остаётся выключенным как страховка. Удалять — не раньше чем через "
     "90 дней и только после архивации.",
     "ssh root@{old_ip} 'systemctl stop zabbix-server && systemctl disable zabbix-server'\n"
     "ssh root@{pve} 'pct stop {old_ct}'",
     "Новый сервер собирает данные, уведомления приходят, старый выключен.", True),
]

CSS = """
:root{--bg:#fff;--txt:#1b1b1f;--dim:#5f6570;--line:#dfe3ea;--head:#0f4c81;
      --ok:#107c10;--warn:#c47b00;--danger:#c42b1c;--soft:#f6f8fb;--code:#1e2430}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
     font:15px/1.6 "Segoe UI",-apple-system,BlinkMacSystemFont,system-ui,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:40px 26px 80px}
header.cover{border-bottom:4px solid var(--head);padding-bottom:20px;margin-bottom:24px}
.org{color:var(--head);font-weight:700;letter-spacing:.11em;font-size:12px;text-transform:uppercase}
h1{font-size:28px;margin:9px 0 6px;font-weight:650;line-height:1.25}
.lead{color:var(--dim);font-size:15px;max-width:80ch}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1px;
       background:var(--line);border:1px solid var(--line);border-radius:8px;
       overflow:hidden;margin:20px 0}
.facts div{background:#fff;padding:10px 14px}
.facts .k{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.facts .v{font-weight:600;margin-top:2px;font-size:14px}
.toc{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:14px 20px;margin:22px 0}
.toc b{display:block;margin-bottom:6px}
.toc a{color:var(--head);text-decoration:none;font-size:14px}
.toc a:hover{text-decoration:underline}
h2{font-size:20px;margin:34px 0 4px;padding-bottom:7px;border-bottom:2px solid var(--head)}
.stage-note{color:var(--dim);font-size:13.5px;margin-bottom:14px}
.step{border:1px solid var(--line);border-radius:10px;margin:14px 0;overflow:hidden}
.step.irreversible{border-color:#f0b0a8}
.step-head{display:flex;gap:12px;align-items:baseline;padding:13px 17px;background:var(--soft)}
.step.irreversible .step-head{background:#fdf0ee}
.num{font-family:ui-monospace,Consolas,monospace;font-weight:700;color:var(--head);
     font-size:13px;white-space:nowrap}
.step-head h3{margin:0;font-size:16px;font-weight:620;flex:1}
.tag{font-size:11px;font-weight:700;padding:2px 9px;border-radius:20px;white-space:nowrap}
.tag-irr{background:#fde8e6;color:var(--danger)}
.step-body{padding:14px 17px}
.why{color:var(--dim);font-size:14px;margin:0 0 12px}
pre{background:var(--code);color:#e6edf3;border-radius:8px;padding:13px 15px;margin:0;
    overflow-x:auto;font:13px/1.55 ui-monospace,Consolas,"SF Mono",monospace}
pre .c{color:#8b98a9}
.cmd{position:relative}
.copy{position:absolute;top:8px;right:8px;background:#30363d;color:#e6edf3;border:0;
      border-radius:6px;padding:4px 10px;font-size:11.5px;cursor:pointer;opacity:.85}
.copy:hover{opacity:1;background:#3c444d}
.check{margin-top:12px;padding:10px 14px;background:#eef7ee;border-left:4px solid var(--ok);
       border-radius:0 7px 7px 0;font-size:14px}
.check b{color:var(--ok)}
.warnbox{margin:18px 0;padding:13px 17px;background:#fdf3e0;border-left:4px solid var(--warn);
         border-radius:0 8px 8px 0}
.dangerbox{margin:18px 0;padding:13px 17px;background:#fde8e6;border-left:4px solid var(--danger);
           border-radius:0 8px 8px 0}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}
th{background:var(--head);color:#fff;text-align:left;padding:8px 11px;font-size:12.5px}
td{padding:8px 11px;border-bottom:1px solid var(--line);vertical-align:top}
tr:nth-child(even) td{background:#fafbfd}
code{font-family:ui-monospace,Consolas,monospace;font-size:13px;background:var(--soft);
     padding:1px 5px;border-radius:3px}
ul{padding-left:22px}li{margin:5px 0}
@media print{.copy{display:none}.step{break-inside:avoid}.wrap{padding:0}}
"""


def esc(s):
    return html.escape(str(s or ""))


def fmt(text: str) -> str:
    return text.format(**FACTS)


def code_block(cmds: str) -> str:
    lines = []
    for line in fmt(cmds).split("\n"):
        e = esc(line)
        if line.strip().startswith("#"):
            e = f'<span class="c">{e}</span>'
        lines.append(e)
    body = "\n".join(lines)
    raw = esc(fmt(cmds)).replace("&#x27;", "'")
    return (f'<div class="cmd"><button class="copy" onclick="cp(this)" '
            f'data-cmd="{raw}">копировать</button><pre>{body}</pre></div>')


def build() -> str:
    stages: dict[str, list] = {}
    for s in STEPS:
        stages.setdefault(s[0], []).append(s)

    stage_notes = {
        "Подготовка": "Ничего не меняется, простоя нет. Задача — получить страховку: "
                      "дамп, файлы и независимую выгрузку конфигурации.",
        "Развёртывание": "Создаётся новая машина рядом с работающей системой. "
                         "Старый сервер не затрагивается.",
        "Перенос базы": "Переносится вся база целиком, с историей за 90 дней и трендами "
                        "за год. Шаг 2.4 необратим — перед ним снимок ВМ.",
        "Параллельная работа": "Две недели оба сервера работают одновременно. "
                               "Это и проверка, и путь отката.",
        "Переключение": "Старый сервер выводится из работы, но не удаляется.",
    }

    parts = [f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Инструкция по миграции Zabbix {FACTS['old_ver']} → {FACTS['zbx_new']}</title>
<style>{CSS}</style></head><body><div class="wrap">

<header class="cover">
  <div class="org">Unisim-Soft &amp; Coninfo · эксплуатация</div>
  <h1>Инструкция по миграции Zabbix {FACTS['old_ver']} → {FACTS['zbx_new']}</h1>
  <p class="lead">Пошаговый порядок работ для исполнителя. Каждый шаг содержит команды
  и проверку результата. <b>Простоя мониторинга нет:</b> старый сервер работает до
  последнего шага, откат возможен на любом этапе.</p>
  <div class="facts">
    <div><div class="k">Откуда</div><div class="v">Zabbix {FACTS['old_ver']}, {FACTS['old_ip']}</div></div>
    <div><div class="k">Куда</div><div class="v">Zabbix {FACTS['zbx_new']}, {FACTS['new_ip']}</div></div>
    <div><div class="k">Основание</div><div class="v">{FACTS['old_os']}, {FACTS['old_db']}, {FACTS['old_php']} — сняты с поддержки</div></div>
    <div><div class="k">Данные</div><div class="v">{FACTS['db_size']}, история сохраняется</div></div>
    <div><div class="k">Объём</div><div class="v">{FACTS['hosts']} хостов, {FACTS['items']} элементов</div></div>
    <div><div class="k">Трудоёмкость</div><div class="v">≈ 22 часа + 2 недели наблюдения</div></div>
  </div>
</header>

<div class="warnbox"><b>Перед началом прочитать план.</b> Здесь только порядок действий;
обоснование решений, требования к машине и расчёты — в документе
<code>ZABBIX_MIGRATION_PLAN.md</code>. Решение о сохранении истории принято владельцем
12.09.2026: база переносится целиком.</div>

<div class="toc"><b>Этапы</b>
""" + " · ".join(f'<a href="#s{i}">{esc(st)}</a>' for i, st in enumerate(stages)) + "</div>"]

    for i, (stage, steps) in enumerate(stages.items()):
        parts.append(f'<h2 id="s{i}">{esc(stage)}</h2>')
        parts.append(f'<div class="stage-note">{esc(stage_notes.get(stage, ""))}</div>')
        for _, num, title, why, cmds, check, irr in steps:
            parts.append(f'''<div class="step{' irreversible' if irr else ''}">
  <div class="step-head"><span class="num">{esc(num)}</span>
    <h3>{esc(fmt(title))}</h3>
    {'<span class="tag tag-irr">необратимо</span>' if irr else ''}</div>
  <div class="step-body">
    <p class="why">{esc(fmt(why))}</p>
    {code_block(cmds)}
    <div class="check"><b>Проверка:</b> {esc(fmt(check))}</div>
  </div></div>''')

    parts.append(f"""
<h2>Если что-то пошло не так</h2>
<p>Старый сервер работает до шага 4.3, поэтому откат почти всегда бесплатный.</p>
<table>
  <tr><th style="width:36%">Ситуация</th><th>Что делать</th><th style="width:90px">Время</th></tr>
  <tr><td>Новый сервер не собирает данные</td><td>Продолжаем на старом, разбираемся без спешки</td><td>0 мин</td></tr>
  <tr><td>Импорт базы упал</td><td>Удалить базу, создать заново, повторить шаг 2.2 — дамп не пострадал</td><td>40 мин</td></tr>
  <tr><td><b>Апгрейд схемы (2.4) прервался</b></td><td>Восстановить снимок <code>before-db-upgrade</code> и повторить; при повторной неудаче — собирать систему из выгрузки шага 0.3</td><td>20 мин</td></tr>
  <tr><td>Уведомления не уходят</td><td>Включить обратно действие на старом сервере</td><td>5 мин</td></tr>
  <tr><td>Нужно вернуть всё</td><td>Запустить <code>zabbix-server</code> на CT {FACTS['old_ct']}, вернуть агентам старый адрес</td><td>30 мин</td></tr>
</table>

<div class="dangerbox"><b>Чего не делать.</b> Не удалять контейнер {FACTS['old_ct']} и его
дамп раньше чем через 90 дней. Не запускать оба сервера с включённым действием
«Telegram» дольше необходимого — пойдут дубли. Не копировать файлы базы напрямую:
на старом сервере <code>innodb_file_per_table = OFF</code>, все данные в общем
<code>ibdata1</code>, перенос возможен только логическим дампом.</div>

<h2>После миграции</h2>
<p>Работы, которые логично сделать сразу, пока система в фокусе:</p>
<ul>
  <li><b>Вычистить мусор.</b> Вместе с базой перенеслись 72 неработающих элемента,
      87 неопрашиваемых JMX и 13 выключенных хостов. По каждому — решение: чиним или удаляем.</li>
  <li><b>Настроить резервное копирование.</b> Регулярного бэкапа базы Zabbix сейчас нет;
      достаточно ежедневного дампа конфигурации (21 МБ) с хранением 30 копий.</li>
  <li><b>Java gateway.</b> Поставить и вернуть JMX-мониторинг либо осознанно отказаться.</li>
  <li><b>Шифрование агентов.</b> Zabbix 8.0 поддерживает PSK; сейчас трафик открыт.</li>
  <li><b>Вынести мониторинг с PROXMOX3.</b> Сейчас падение гипервизора лишает и сервисов,
      и наблюдения за ними.</li>
</ul>

<p style="color:var(--dim);font-size:13px;margin-top:28px">
Документ сформирован {datetime.now():%d.%m.%Y} из данных обследования боевых систем.
Пересобрать: <code>python modules/netmon/scripts/netmon_migration_guide.py</code></p>

</div>
<script>
function cp(b){{
  navigator.clipboard.writeText(b.dataset.cmd).then(() => {{
    const t = b.textContent; b.textContent = "скопировано";
    setTimeout(() => b.textContent = t, 1400);
  }});
}}
</script>
</body></html>""")
    return "".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(), encoding="utf-8")
    steps = len(STEPS)
    print(f"инструкция готова: {out} ({out.stat().st_size // 1024} КБ, {steps} шагов)")


if __name__ == "__main__":
    main()
