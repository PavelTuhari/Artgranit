# Копия officeplus.md на площадке 192.168.0.250

Развёрнута 2026-08-18. Полная копия боевого сайта: витрина, бэк-офис,
WordPress и общая с продакшеном база Oracle.

**Адрес: `http://192.168.0.250:8001/`** (только из внутренней сети / через VPN93).

## Что где

| Часть | Где |
|---|---|
| Flask (витрина + бэк-офис) | `/home/ubuntu/artgranit`, systemd `artgranit`, gunicorn на `127.0.0.1:8000` |
| WordPress | `/var/www/officeplus`, php8.1-fpm |
| MySQL (WordPress) | системный MariaDB 10.6, база `officeplus_wp`, `127.0.0.1:3306` |
| Веб-сервер | системный Apache, vhost `officeplus.conf` на порту **8001** |
| Oracle ERP | `orange.una.md:4024/cloudbd.world` — **общий с продакшеном** |
| Instant Client | `/opt/oracle/instantclient_19_28` |
| Кошелёк ADB | `/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q` |

## ⚠️ Копия работает с БОЕВОЙ базой Oracle

Скопированы только файлы и MySQL WordPress. Oracle — тот же, что у
`officeplus.md`. Значит заказ, оформленный на этой копии, создаст **настоящий
документ в ERP**, а правки в бэк-офисе изменят боевые данные.

Если нужна изолированная песочница — заводить отдельную схему Oracle и менять
`BIRO26_DB_DSN` в `/home/ubuntu/artgranit/.env`.

## Чем эта площадка отличается от боевой

| | Боевой (92.5.130.1) | Копия (.250) |
|---|---|---|
| Веб-сервер | nginx, порты 80/443 | Apache, порт 8001 |
| TLS | Let's Encrypt | нет |
| Публикация | из интернета | только внутренняя сеть / VPN93 |
| `FORCE_SSL_ADMIN` | `true` | `false` (TLS нет) |
| `WP_HOME` / `WP_SITEURL` | `https://officeplus.md` | `http://192.168.0.250:8001` |

## Что пришлось поставить

На машине уже были Python 3.10, Apache, Redis, PostgreSQL и клиент MariaDB.
Добавлено: `mariadb-server`, `php8.1-fpm` с модулями, `python3.10-venv`,
Oracle Instant Client.

**MariaDB и Nextcloud.** Единственный работавший MySQL — внутри snap
Nextcloud, и установщик системного MariaDB из-за него отказывался ставиться
(`There is a MariaDB/MySQL server running`). Nextcloud останавливали примерно
на минуту, ставили MariaDB, запускали обратно. Теперь они сосуществуют:
snap — на своём unix-сокете и своём каталоге данных, системный MariaDB — на
`127.0.0.1:3306`. Порт 80 не трогали.

## Ловушка Apache: ProxyPassMatch дописывает путь

Витрина отвечала 404, потому что `ProxyPassMatch "^/catalog$"` подставлял цель
и **дописывал исходный путь** — во Flask уходило
`/UNA.md/orasldev/biro26-site/catalog/catalog`.

Точные адреса переведены на `RewriteRule ... [P,L]`, который подставляет адрес
ровно как написано. Префиксы (`/UNA.md/`, `/api/`, `/static/`) остались на
обычном `ProxyPass` — там дописывание как раз и нужно.

## Обслуживание

```bash
# подключение (пароль в macOS Keychain, см. паспорт хоста)
export SSHPASS=$(security find-internet-password -s 192.168.0.250 -a ubuntu -w)
sshpass -e ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no ubuntu@192.168.0.250

sudo systemctl restart artgranit      # перезапуск приложения
sudo journalctl -u artgranit -f       # логи приложения
sudo tail -f /var/log/apache2/officeplus_error.log
```

Обновление кода: распаковать архив поверх `/home/ubuntu/artgranit`,
затем `sudo systemctl restart artgranit`. Каталог `venv`, `.env` и кошелёк
распаковка не затрагивает.

## Проверка после любых работ

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/                     # Nextcloud → 200
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/icingaweb2/     # Icinga → 302
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.0.250:8001/catalog     # витрина → 200
```

## Откат

Перед работами сделан снапшот ВМ на Proxmox: узел `192.168.0.149`, VMID 138,
имя **`beforeOfficeplusDeploy`**.

```bash
qm listsnapshot 138
qm rollback 138 beforeOfficeplusDeploy
```

## Не сделано

- **TLS отсутствует** — для приёма платежей площадка непригодна.
- **Наружу не опубликовано.** По паспорту хоста снаружи на `.250` проброшен
  только порт 8003; чтобы открыть копию из интернета, нужен либо новый NAT на
  MikroTik (доступа нет), либо проксирование через `.148`. Решение за
  владельцем — см. §5 паспорта хоста.
- Проверка в Icinga для этой копии не заведена.
