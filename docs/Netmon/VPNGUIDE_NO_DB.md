# Ссылка для получателя без базы (08.11.2026)

## Что случилось

08.11.2026 база ADB перестала отвечать. Ошибка `DPY-6001: Service … is not
registered with the listener`, с nufarul соединение висит больше минуты.
Сертификат OpenVPN выпускался, а ссылка для получателя — нет: она хранилась
только в `VPNG_SHARES`.

## Что сделано

Если база не ответила за 12 секунд или вернула ошибку, ссылка выдаётся **без
базы**. Имя, тип, язык, срок и профиль сжимаются (zlib) и шифруются (Fernet)
прямо в адрес `…/vpnguide/s/z.<шифротекст>`. Ключ выводится через HKDF из
`SECRET_KEY` (или `VPNGUIDE_SEAL_KEY`, если задан). Этот секрет одинаков на
машине администратора и на nufarul, поэтому ссылку может открыть только сервер.

| | Обычная ссылка | Ссылка без базы |
|---|---|---|
| Длина адреса | ~100 символов | ~4,7 КБ для профиля 5 КБ (лимит строки nginx 8 КБ, тест) |
| Срок | 1…1440 мин | 1…1440 мин, плюс верхняя граница Fernet — сутки |
| Досрочный отзыв | да, в таблице | нет: доступ закрывается отзывом сертификата или учётки |
| Журнал открытий | `VPNG_SHARE_HITS` | журнал службы (`journalctl -u artgranit`, `vpnguide:`) |
| Подделка или чужой ключ | — | не открывается (подпись Fernet) |

Панель показывает у такой ссылки пометку «база сейчас недоступна».

## Файлы

- `modules/vpnguide/rules.py`: `seal()`, `unseal()`, `sealed_valid()`, чистые функции
- `modules/vpnguide/store.py`: `create_share()` ждёт базу 12 с, затем вызывает `create_sealed()`;
  `open_share()` обрабатывает токены `z.` без базы
- `modules/netmon/controller.py`: в ответ добавлены `sealed` и `db_error`
- `modules/netmon/templates/netmon.html`: пометка в карточке ссылки
- `tests/test_netmon.py`: проверки шифрования, срока, подделки, длины адреса
  и запасного пути при ошибке базы

## Выкатка на nufarul

Ссылки открывает nufarul, поэтому туда нужны только два файла модуля:
`app.py` и общие файлы не меняются.

```bash
cd /Users/pt/Projects.AI/Artgranit-netmon
COPYFILE_DISABLE=1 tar -czf /tmp/vpng.tgz modules/vpnguide/rules.py modules/vpnguide/store.py
scp -i ~/.ssh/artgranit-oci.key /tmp/vpng.tgz ubuntu@92.5.3.187:/tmp/vpng.tgz
ssh -i ~/.ssh/artgranit-oci.key ubuntu@92.5.3.187 'cd /home/ubuntu/artgranit && D=$(date +%Y%m%d) \
  && cp -p modules/vpnguide/rules.py modules/vpnguide/rules.py.bak-$D \
  && cp -p modules/vpnguide/store.py modules/vpnguide/store.py.bak-$D \
  && tar -xzf /tmp/vpng.tgz && rm -f /tmp/vpng.tgz \
  && venv/bin/python -m py_compile modules/vpnguide/rules.py modules/vpnguide/store.py \
  && sudo systemctl restart artgranit && sleep 8 \
  && curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/login'
curl -I https://nufarul.eminescu.md/login
```

До выкатки 08.11.2026 на nufarul стояла версия из `main` (md5 rules
`6a60eddc…`, store `351a63d1…`). Откат — из `.bak-ДАТА`.

## Панель при недоступной базе (`modules/netmon/dbguard.py`)

Тот же день: дашборд панели не грузил **ничего**. `loadAll()` ждал сводку,
сводка минуту висела на базе и падала, и следом не загружались Proxmox, Zabbix,
VPN и MikroTik, хотя им база не нужна.

1. `dbguard.status()` проверяет базу с ожиданием 6 с и помнит ответ минуту.
   Пока база лежит, разделы на её данных (`/devices`, `/alerts`,
   `/vpn/shares`, отзыв ссылки) отвечают сразу понятной ошибкой, а не через минуту.
2. Сводка `/api/overview` без базы строится из Zabbix: хосты на мониторинге
   и текущие проблемы по важности. В ответе `degraded: true` и `db_error`.
3. В `netmon.html` каждый раздел грузится в своём `try`. Сверху висит плашка
   «База ADB недоступна» с подсказкой, как её включить, а в таблице ссылок
   пояснение, что новые ссылки всё равно выдаются.

Проверено 08.11.2026 при лежащей ADB: сводка 200 за 6,4 с (дальше из памяти
мгновенно), 73 хоста и 36 проблем из Zabbix. `/devices`, `/alerts` и
`/vpn/shares` отвечают за 0,0 с текстом «база ADB недоступна…».
