"""Чистые правила ссылок для получателя доступа — без базы, тестируются без wallet.

Ссылка вида …/vpnguide/s/<токен> открывает инструкцию на трёх языках с файлом
профиля внутри. Устройство защиты:

* токен — 32 случайных байта (256 бит), подобрать нельзя;
* в базе хранится только SHA-256 токена — по дампу базы ссылку не восстановить;
* профиль шифруется ключом, выведенным из ТОКЕНА (HKDF → Fernet). Без ссылки
  расшифровать его нельзя даже с полным доступом к базе;
* срок по умолчанию 15 минут, после него шифротекст стирается.

Токен и ключ выводятся из одного секрета, но разными функциями: хэш для
поиска — SHA-256 с префиксом, ключ — HKDF со своей солью и контекстом.
Знание хэша ничего не даёт для ключа.
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

TTL_DEFAULT = 15
TTL_MIN = 1
TTL_MAX = 1440          # сутки — дольше ключу от офиса лежать в чужой почте незачем
LANGS = ("ru", "ro", "en")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")   # secrets.token_urlsafe(32)

DOWNLOADS = {
    "site": "https://openvpn.net/client/",
    "windows": "https://openvpn.net/downloads/openvpn-connect-v3-windows.msi",
    "macos": "https://openvpn.net/downloads/openvpn-connect-v3-macos.dmg",
    "iphone": "https://apps.apple.com/app/openvpn-connect/id590379981",
    "android": "https://play.google.com/store/apps/details?id=net.openvpn.openvpn",
}


# ---------------------------------------------------------------- токен и ключ

def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_valid(token: str) -> bool:
    return bool(TOKEN_RE.match(token or ""))


def token_hash(token: str) -> str:
    return hashlib.sha256(b"vpng-lookup-v1:" + token.encode()).hexdigest()


def _fernet(token: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32,
               salt=b"vpng-share-salt-v1", info=b"vpng-profile-key").derive(token.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(token: str, profile: str) -> str:
    return _fernet(token).encrypt(profile.encode("utf-8")).decode("ascii")


def decrypt(token: str, payload: str) -> str | None:
    try:
        return _fernet(token).decrypt(payload.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def ttl(value) -> int:
    """Срок жизни ссылки в минутах: по умолчанию 15, в пределах 1…1440."""
    # Не `value in (None, "", True)`: в Python 1 == True, и ссылка на одну
    # минуту молча становилась пятнадцатиминутной.
    if value is None or value is True or value == "":
        return TTL_DEFAULT
    if value is False:
        raise ValueError("срок ссылки не задан")
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"срок ссылки — число минут от {TTL_MIN} до {TTL_MAX}")
    if not TTL_MIN <= v <= TTL_MAX:
        raise ValueError(f"срок ссылки — от {TTL_MIN} до {TTL_MAX} минут")
    return v


def lang(value) -> str:
    v = (value or "").strip().lower()[:2]
    return v if v in LANGS else "ru"


def profile_sha256(profile: str) -> str:
    return hashlib.sha256(profile.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------- тексты

# Все три языка собираются на каждой странице: получатель переключает язык
# без нового запроса, а ИИ-агент видит инструкцию целиком.
T = {
    "title": {
        "ru": "Подключение к офису через OpenVPN",
        "ro": "Conectarea la birou prin OpenVPN",
        "en": "Connecting to the office via OpenVPN",
    },
    "for": {"ru": "Доступ для", "ro": "Acces pentru", "en": "Access for"},
    "expires": {
        "ru": "Ссылка действует до {at} (осталось {left} мин). После этого она перестанет открываться.",
        "ro": "Linkul este valabil până la {at} (au rămas {left} min). După aceea nu se va mai deschide.",
        "en": "This link is valid until {at} ({left} min left). After that it will stop working.",
    },
    "s1": {"ru": "1. Установите программу OpenVPN Connect",
           "ro": "1. Instalați programul OpenVPN Connect",
           "en": "1. Install OpenVPN Connect"},
    "s1_text": {
        "ru": "Официальный бесплатный клиент. Скачайте для своего устройства:",
        "ro": "Clientul oficial gratuit. Descărcați-l pentru dispozitivul dvs.:",
        "en": "The official free client. Download it for your device:",
    },
    "dl_windows": {"ru": "Windows (.msi)", "ro": "Windows (.msi)", "en": "Windows (.msi)"},
    "dl_macos": {"ru": "macOS (.dmg)", "ro": "macOS (.dmg)", "en": "macOS (.dmg)"},
    "dl_iphone": {"ru": "iPhone / iPad — App Store", "ro": "iPhone / iPad — App Store",
                  "en": "iPhone / iPad — App Store"},
    "dl_android": {"ru": "Android — Google Play", "ro": "Android — Google Play",
                   "en": "Android — Google Play"},
    "dl_site": {"ru": "Все версии на сайте OpenVPN", "ro": "Toate versiunile pe site-ul OpenVPN",
                "en": "All versions on the OpenVPN website"},
    "s2": {"ru": "2. Скачайте свой файл доступа",
           "ro": "2. Descărcați fișierul dvs. de acces",
           "en": "2. Download your access file"},
    "s2_btn": {"ru": "Скачать {file}", "ro": "Descărcați {file}", "en": "Download {file}"},
    "s3": {"ru": "3. Импортируйте файл и подключитесь",
           "ro": "3. Importați fișierul și conectați-vă",
           "en": "3. Import the file and connect"},
    "s3_steps": {
        "ru": ["Откройте OpenVPN Connect.",
               "Выберите «Upload File» / «Import Profile → File» и укажите скачанный файл.",
               "Нажмите «Add», затем «Connect». Разрешите системе добавить конфигурацию VPN, если она спросит.",
               "Статус «Connected» — подключение готово. Закончили работу — «Disconnect»."],
        "ro": ["Deschideți OpenVPN Connect.",
               "Alegeți „Upload File” / „Import Profile → File” și indicați fișierul descărcat.",
               "Apăsați „Add”, apoi „Connect”. Permiteți sistemului să adauge configurația VPN, dacă vă întreabă.",
               "Starea „Connected” — conexiunea este gata. La final — „Disconnect”."],
        "en": ["Open OpenVPN Connect.",
               "Choose “Upload File” / “Import Profile → File” and select the downloaded file.",
               "Press “Add”, then “Connect”. Allow the system to add the VPN configuration if asked.",
               "Status “Connected” means you are in. When done, press “Disconnect”."],
    },
    "s4": {"ru": "4. Если файл не скачивается — соберите его сами",
           "ro": "4. Dacă fișierul nu se descarcă — creați-l singur",
           "en": "4. If the download fails — build the file yourself"},
    "s4_text": {
        "ru": "Ниже полное содержимое файла. Скопируйте его без изменений в текстовый файл "
              "и сохраните под именем {file} (кодировка UTF-8, расширение именно .ovpn). "
              "Помощник с ИИ может сделать это за вас: дайте ему эту страницу.",
        "ro": "Mai jos este conținutul complet al fișierului. Copiați-l fără modificări într-un fișier "
              "text și salvați-l cu numele {file} (codare UTF-8, extensia exact .ovpn). "
              "Un asistent AI poate face asta în locul dvs.: dați-i această pagină.",
        "en": "Below is the full file content. Copy it unchanged into a text file and save it as "
              "{file} (UTF-8, extension exactly .ovpn). An AI assistant can do this for you: "
              "give it this page.",
    },
    "copy": {"ru": "Скопировать", "ro": "Copiați", "en": "Copy"},
    "copied": {"ru": "Скопировано", "ro": "Copiat", "en": "Copied"},
    "sha": {"ru": "Контрольная сумма SHA-256 файла", "ro": "Suma de control SHA-256 a fișierului",
            "en": "File SHA-256 checksum"},
    "rules": {"ru": "Важно", "ro": "Important", "en": "Important"},
    "rules_list": {
        "ru": ["Файл — ваш личный ключ от офисной сети. Не пересылайте ни его, ни эту ссылку.",
               "Если ссылку мог увидеть кто-то ещё — сразу сообщите администратору: доступ отключат.",
               "Потеряли устройство с установленным профилем — тоже сообщите администратору."],
        "ro": ["Fișierul este cheia dvs. personală la rețeaua biroului. Nu-l trimiteți nimănui, nici acest link.",
               "Dacă linkul ar fi putut fi văzut de altcineva — anunțați imediat administratorul: accesul va fi dezactivat.",
               "Ați pierdut dispozitivul cu profilul instalat — anunțați, de asemenea, administratorul."],
        "en": ["The file is your personal key to the office network. Do not forward it or this link.",
               "If anyone else may have seen this link, tell the administrator at once: access will be disabled.",
               "If you lose a device with the profile installed, tell the administrator as well."],
    },
    "gone_title": {"ru": "Ссылка больше не действует", "ro": "Linkul nu mai este valabil",
                   "en": "This link is no longer valid"},
    "gone_text": {
        "ru": "Срок ссылки истёк или её отозвали. Попросите администратора выдать новую.",
        "ro": "Linkul a expirat sau a fost revocat. Rugați administratorul să emită unul nou.",
        "en": "The link has expired or was revoked. Ask the administrator for a new one.",
    },
    "ai_hint": {
        "ru": "Для ИИ-помощника: та же инструкция простым текстом —",
        "ro": "Pentru asistentul AI: aceeași instrucțiune în text simplu —",
        "en": "For an AI assistant: the same instruction as plain text —",
    },
}


def text(key: str, lang_: str, **kw):
    v = T[key][lang_]
    if isinstance(v, list):
        return [s.format(**kw) for s in v]
    return v.format(**kw) if kw else v


def file_name(client_name: str) -> str:
    return f"{client_name}.ovpn"


def markdown(client_name: str, profile: str, expires_at: str, minutes_left: int,
             profile_url: str) -> str:
    """Та же инструкция простым текстом — для ИИ-агента и для командной строки.

    Английский идёт первым: так её надёжнее разбирает любой агент. Профиль —
    в последнем блоке, между явными маркерами, чтобы его можно было вырезать
    программно без разбора разметки.
    """
    f = file_name(client_name)
    out = []
    for lg in ("en", "ru", "ro"):
        out += [f"# {text('title', lg)} — {client_name}", "",
                text("expires", lg, at=expires_at, left=minutes_left), "",
                f"## {text('s1', lg)}", "",
                text("s1_text", lg), "",
                f"- {text('dl_windows', lg)}: {DOWNLOADS['windows']}",
                f"- {text('dl_macos', lg)}: {DOWNLOADS['macos']}",
                f"- {text('dl_iphone', lg)}: {DOWNLOADS['iphone']}",
                f"- {text('dl_android', lg)}: {DOWNLOADS['android']}",
                f"- {text('dl_site', lg)}: {DOWNLOADS['site']}", "",
                f"## {text('s2', lg)}", "", f"{profile_url}", "",
                f"## {text('s3', lg)}", ""]
        out += [f"{i}. {s}" for i, s in enumerate(text("s3_steps", lg), 1)]
        out += ["", f"## {text('rules', lg)}", ""]
        out += [f"- {s}" for s in text("rules_list", lg)]
        out += ["", "---", ""]
    out += [f"## {text('s4', 'en')}", "",
            text("s4_text", "en", file=f), "",
            f"File name: {f}",
            f"SHA-256: {profile_sha256(profile)}", "",
            "-----BEGIN OVPN PROFILE-----",
            profile.rstrip("\n"),
            "-----END OVPN PROFILE-----", ""]
    return "\n".join(out)


# =================================================================== L2TP/IPsec
# Доступ на маршрутизатор MikroTik. Файла профиля у L2TP нет — есть четыре
# настройки (сервер, логин, пароль, общий ключ). Чтобы получателю не набирать
# их руками, на лету собираются скрипт PowerShell для Windows и профиль
# .mobileconfig для macOS и iPhone.

KINDS = ("openvpn", "l2tp")
VPN_NAME = "Office VPN"


def l2tp_payload(server: str, username: str, password: str, psk: str) -> str:
    import json
    for k, v in (("server", server), ("username", username), ("password", password), ("psk", psk)):
        if not v:
            raise ValueError(f"для ссылки L2TP не хватает: {k}")
    return json.dumps({"server": server, "username": username,
                       "password": password, "psk": psk}, ensure_ascii=False)


def l2tp_settings(payload: str) -> dict:
    import json
    d = json.loads(payload)
    return {k: d[k] for k in ("server", "username", "password", "psk")}


def _ps_quote(v: str) -> str:
    """Строка PowerShell в одинарных кавычках: всё буквально, ' удваивается.
    В двойных кавычках $ и ` в ключе или пароле превратились бы в код."""
    return "'" + v.replace("'", "''") + "'"


def powershell(cfg: dict) -> str:
    """Скрипт, который создаёт подключение и сразу подключается.

    Запуск: правой кнопкой → «Выполнить с помощью PowerShell», или
    powershell -ExecutionPolicy Bypass -File office-vpn.ps1
    """
    n = _ps_quote(VPN_NAME)
    return "\r\n".join([
        f"# {VPN_NAME}: L2TP/IPsec, пользователь {cfg['username']}",
        "# Создаёт подключение Windows и сразу подключается. Запускать от своего имени.",
        "$ErrorActionPreference = 'Stop'",
        f"$name = {n}",
        "if (Get-VpnConnection -Name $name -ErrorAction SilentlyContinue) {",
        "    Remove-VpnConnection -Name $name -Force",
        "}",
        f"Add-VpnConnection -Name $name -ServerAddress {_ps_quote(cfg['server'])} "
        f"-TunnelType L2tp -L2tpPsk {_ps_quote(cfg['psk'])} -AuthenticationMethod MSChapv2 "
        "-EncryptionLevel Required -RememberCredential -Force",
        f"rasdial $name {_ps_quote(cfg['username'])} {_ps_quote(cfg['password'])}",
        "if ($LASTEXITCODE -eq 0) { Write-Host 'Подключено / Conectat / Connected' -ForegroundColor Green }",
        "else { Write-Host \"Ошибка подключения, код $LASTEXITCODE\" -ForegroundColor Red }",
        "",
    ])


def mobileconfig(cfg: dict) -> bytes:
    """Профиль конфигурации Apple (macOS и iPhone/iPad) с настроенным L2TP.

    OverridePrimary = 1: весь трафик идёт через офис. Без этого macOS
    маршрутизирует только сеть выданного адреса (10.x), и офисная сеть
    192.168.0.0/24 не открывается.
    """
    import plistlib
    import uuid
    inner, outer = str(uuid.uuid4()).upper(), str(uuid.uuid4()).upper()
    vpn = {
        "PayloadType": "com.apple.vpn.managed",
        "PayloadIdentifier": f"md.office.vpn.l2tp.{inner}",
        "PayloadUUID": inner, "PayloadVersion": 1,
        "PayloadDisplayName": VPN_NAME, "UserDefinedName": VPN_NAME,
        "VPNType": "L2TP",
        "PPP": {"AuthName": cfg["username"], "AuthPassword": cfg["password"],
                "CommRemoteAddress": cfg["server"]},
        "IPSec": {"AuthenticationMethod": "SharedSecret",
                  "SharedSecret": cfg["psk"].encode("utf-8")},
        "IPv4": {"OverridePrimary": 1},
    }
    profile = {
        "PayloadContent": [vpn],
        "PayloadDisplayName": f"{VPN_NAME} — {cfg['username']}",
        "PayloadIdentifier": f"md.office.vpn.{outer}",
        "PayloadType": "Configuration", "PayloadUUID": outer, "PayloadVersion": 1,
        "PayloadRemovalDisallowed": False,
    }
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML)


T.update({
    "l2tp_title": {
        "ru": "Подключение к офису (L2TP/IPsec)",
        "ro": "Conectarea la birou (L2TP/IPsec)",
        "en": "Connecting to the office (L2TP/IPsec)",
    },
    "l2tp_lead": {
        "ru": "Отдельная программа не нужна: L2TP/IPsec встроен в Windows, macOS и iPhone. "
              "Проще всего — скачать готовую настройку для своего устройства и запустить её.",
        "ro": "Nu este nevoie de un program separat: L2TP/IPsec este integrat în Windows, macOS și iPhone. "
              "Cel mai simplu — descărcați configurația gata pentru dispozitivul dvs. și rulați-o.",
        "en": "No extra app is needed: L2TP/IPsec is built into Windows, macOS and iPhone. "
              "The easiest way is to download the ready-made setup for your device and run it.",
    },
    "l2tp_auto": {"ru": "1. Настройка в один шаг", "ro": "1. Configurare într-un singur pas",
                  "en": "1. One-step setup"},
    "l2tp_win_btn": {"ru": "Windows — скрипт настройки (.ps1)", "ro": "Windows — script de configurare (.ps1)",
                     "en": "Windows — setup script (.ps1)"},
    "l2tp_win_how": {
        "ru": "Скачайте, нажмите на файл правой кнопкой → «Выполнить с помощью PowerShell». "
              "Если Windows не даст запустить, откройте PowerShell в папке с файлом и выполните:",
        "ro": "Descărcați, faceți clic dreapta pe fișier → „Executare cu PowerShell”. "
              "Dacă Windows nu permite rularea, deschideți PowerShell în dosarul fișierului și executați:",
        "en": "Download it, right-click the file → “Run with PowerShell”. "
              "If Windows refuses, open PowerShell in the file's folder and run:",
    },
    "l2tp_apple_btn": {"ru": "macOS и iPhone — профиль (.mobileconfig)",
                       "ro": "macOS și iPhone — profil (.mobileconfig)",
                       "en": "macOS and iPhone — profile (.mobileconfig)"},
    "l2tp_apple_how": {
        "ru": "Mac: откройте файл, затем «Системные настройки → Конфиденциальность и безопасность → "
              "Профили» → «Установить». iPhone: откройте ссылку в Safari, затем «Настройки → Профиль "
              "загружен» → «Установить». Система предупредит, что профиль не подписан, — это нормально.",
        "ro": "Mac: deschideți fișierul, apoi „Setări sistem → Confidențialitate și securitate → Profiluri” → "
              "„Instalare”. iPhone: deschideți linkul în Safari, apoi „Setări → Profil descărcat” → „Instalare”. "
              "Sistemul va avertiza că profilul nu este semnat — este normal.",
        "en": "Mac: open the file, then “System Settings → Privacy & Security → Profiles” → “Install”. "
              "iPhone: open the link in Safari, then “Settings → Profile Downloaded” → “Install”. "
              "The system will warn that the profile is unsigned — that is expected.",
    },
    "l2tp_android": {
        "ru": "Android 12 и новее больше не умеет L2TP/IPsec. Для телефона Android попросите у "
              "администратора доступ OpenVPN.",
        "ro": "Android 12 și versiunile mai noi nu mai suportă L2TP/IPsec. Pentru un telefon Android "
              "cereți administratorului acces OpenVPN.",
        "en": "Android 12 and newer no longer support L2TP/IPsec. For an Android phone, ask the "
              "administrator for OpenVPN access.",
    },
    "l2tp_manual": {"ru": "2. Если хотите настроить вручную", "ro": "2. Dacă doriți configurare manuală",
                    "en": "2. If you prefer to set it up manually"},
    "l2tp_manual_text": {
        "ru": "Тип VPN — «L2TP/IPsec с общим ключом» (L2TP over IPSec, pre-shared key). Значения:",
        "ro": "Tip VPN — „L2TP/IPsec cu cheie partajată” (L2TP over IPSec, pre-shared key). Valori:",
        "en": "VPN type — “L2TP/IPsec with pre-shared key” (L2TP over IPSec). Values:",
    },
    "f_server": {"ru": "Сервер", "ro": "Server", "en": "Server"},
    "f_user": {"ru": "Имя пользователя", "ro": "Nume utilizator", "en": "User name"},
    "f_password": {"ru": "Пароль", "ro": "Parolă", "en": "Password"},
    "f_psk": {"ru": "Общий ключ (IPsec PSK)", "ro": "Cheie partajată (IPsec PSK)",
              "en": "Pre-shared key (IPsec PSK)"},
    "f_auth": {"ru": "Проверка подлинности", "ro": "Autentificare", "en": "Authentication"},
    "l2tp_ai": {
        "ru": "Для ИИ-помощника: все настройки в машиночитаемом виде — в блоке JSON на странице "
              "и в текстовой версии.",
        "ro": "Pentru asistentul AI: toate setările în format citibil de mașină — în blocul JSON "
              "de pe pagină și în versiunea text.",
        "en": "For an AI assistant: all settings in machine-readable form are in the JSON block on "
              "this page and in the plain-text version.",
    },
})


def markdown_l2tp(cfg: dict, expires_at: str, minutes_left: int,
                  ps1_url: str, apple_url: str) -> str:
    """Текстовая версия для ИИ-агента. Настройки — в последнем блоке, JSON."""
    import json
    out = []
    for lg in ("en", "ru", "ro"):
        out += [f"# {text('l2tp_title', lg)} — {cfg['username']}", "",
                text("expires", lg, at=expires_at, left=minutes_left), "",
                text("l2tp_lead", lg), "",
                f"## {text('l2tp_auto', lg)}", "",
                f"- {text('l2tp_win_btn', lg)}: {ps1_url}",
                f"  {text('l2tp_win_how', lg)} `powershell -ExecutionPolicy Bypass -File office-vpn.ps1`",
                f"- {text('l2tp_apple_btn', lg)}: {apple_url}",
                f"  {text('l2tp_apple_how', lg)}",
                f"- {text('l2tp_android', lg)}", "",
                f"## {text('l2tp_manual', lg)}", "",
                text("l2tp_manual_text", lg), "",
                f"- {text('f_server', lg)}: {cfg['server']}",
                f"- {text('f_user', lg)}: {cfg['username']}",
                f"- {text('f_password', lg)}: {cfg['password']}",
                f"- {text('f_psk', lg)}: {cfg['psk']}",
                f"- {text('f_auth', lg)}: MS-CHAP v2", "",
                f"## {text('rules', lg)}", ""]
        out += [f"- {s}" for s in text("rules_list", lg)]
        out += ["", "---", ""]
    out += ["## Machine-readable settings", "", "```json",
            json.dumps({"type": "L2TP/IPsec PSK", "authentication": "MS-CHAPv2", **cfg},
                       ensure_ascii=False, indent=2),
            "```", ""]
    return "\n".join(out)


# ================================================================ сетевые диски
# Файловый сервер 192.168.0.21: личная учётка и диски, положенные роли.

KINDS = ("openvpn", "l2tp", "smb")
_DRIVE_RE = re.compile(r"^[A-Z]$")
_SHARE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
_SAFE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def smb_payload(server: str, netbios: str, login: str, password: str,
                drives: list[dict]) -> str:
    import json
    if not drives:
        raise ValueError("у роли нет ни одного диска")
    for v in (server, netbios, login, password):
        if not _SAFE_RE.match(v or ""):
            raise ValueError("недопустимые символы в настройках подключения")
    for d in drives:
        if not _DRIVE_RE.match(d["drive"]) or not _SHARE_RE.match(d["share"]):
            raise ValueError(f"недопустимый диск: {d}")
    return json.dumps({"server": server, "netbios": netbios, "login": login,
                       "password": password,
                       "drives": [{"drive": d["drive"], "share": d["share"],
                                   "title": d.get("title", "")} for d in drives]},
                      ensure_ascii=False)


def smb_settings(payload: str) -> dict:
    import json
    return json.loads(payload)


def smb_cmd(cfg: dict) -> str:
    """Файл .cmd: снимает старые подключения к серверу и подключает диски роли.

    Windows не даёт подключиться к одному серверу двумя учётками сразу
    (ошибка 1219), а сейчас почти у всех открыты подключения под общей
    netuser. Поэтому сначала снимаются все подключения к ЭТОМУ серверу
    (другие серверы не трогаются), затем пароль кладётся в диспетчер учётных
    данных — после перезагрузки диски поднимутся сами.
    Значения проверены smb_payload: только буквы, цифры, . _ - — кавычки и
    спецсимволы cmd в них попасть не могут.
    """
    srv, user = cfg["server"], f"{cfg['netbios']}\\{cfg['login']}"
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        f"echo Подключение сетевых дисков для {cfg['login']} / Conectarea discurilor de rețea / Mapping network drives",
        # /l /c: — буквальный поиск: по умолчанию findstr видит в точках регулярное выражение
        f"for /f \"tokens=2\" %%d in ('net use ^| findstr /i /l /c:\"\\\\{srv}\\\\\"') do net use %%d /delete /y >nul 2>&1",
        f"net use \\\\{srv}\\IPC$ /delete /y >nul 2>&1",
        f"cmdkey /delete:{srv} >nul 2>&1",
        f"cmdkey /add:{srv} /user:{user} /pass:{cfg['password']} >nul",
    ]
    for d in cfg["drives"]:
        lines += [f"net use {d['drive']}: /delete /y >nul 2>&1",
                  f"net use {d['drive']}: \\\\{srv}\\{d['share']} /persistent:yes",
                  f"if errorlevel 1 (echo [!] {d['drive']}: \\\\{srv}\\{d['share']} — ошибка / eroare / failed) "
                  f"else (echo [ok] {d['drive']}: \\\\{srv}\\{d['share']})"]
    lines += ["echo.", "pause", ""]
    return "\r\n".join(lines)


T.update({
    "smb_title": {"ru": "Сетевые диски офиса", "ro": "Discurile de rețea ale biroului",
                  "en": "Office network drives"},
    "smb_lead": {
        "ru": "Ваша личная учётка на файловом сервере. Диски работают в офисе или через VPN.",
        "ro": "Contul dvs. personal pe serverul de fișiere. Discurile funcționează în birou sau prin VPN.",
        "en": "Your personal account on the file server. Drives work in the office or over VPN.",
    },
    "smb_drives": {"ru": "Ваши диски", "ro": "Discurile dvs.", "en": "Your drives"},
    "smb_win": {"ru": "1. Windows — подключение в один шаг", "ro": "1. Windows — conectare într-un singur pas",
                "en": "1. Windows — one-step setup"},
    "smb_win_btn": {"ru": "Скачать и запустить office-drives.cmd", "ro": "Descărcați și rulați office-drives.cmd",
                    "en": "Download and run office-drives.cmd"},
    "smb_win_how": {
        "ru": "Дважды щёлкните по скачанному файлу. Он отключит старые подключения к этому серверу "
              "(в том числе под общей учёткой), запомнит ваш пароль и подключит диски. После "
              "перезагрузки диски поднимутся сами.",
        "ro": "Faceți dublu clic pe fișierul descărcat. Acesta va deconecta conexiunile vechi la acest "
              "server (inclusiv cu contul comun), va memora parola și va conecta discurile. După "
              "repornire discurile se vor reconecta singure.",
        "en": "Double-click the downloaded file. It removes old connections to this server (including "
              "the shared account), remembers your password and maps the drives. They reconnect "
              "automatically after a restart.",
    },
    "smb_mac": {"ru": "2. macOS", "ro": "2. macOS", "en": "2. macOS"},
    "smb_mac_how": {
        "ru": "Finder → «Переход» → «Подключение к серверу» (⌘K), введите адрес из таблицы, затем "
              "имя и пароль ниже.",
        "ro": "Finder → „Mergi” → „Conectare la server” (⌘K), introduceți adresa din tabel, apoi "
              "numele și parola de mai jos.",
        "en": "Finder → Go → Connect to Server (⌘K), enter the address from the table, then the "
              "user name and password below.",
    },
    "smb_manual": {"ru": "3. Данные для входа", "ro": "3. Date de autentificare", "en": "3. Sign-in details"},
    "smb_user": {"ru": "Имя пользователя (вводить вместе с именем сервера)",
                 "ro": "Nume utilizator (împreună cu numele serverului)",
                 "en": "User name (including the server name)"},
    "smb_vpn": {
        "ru": "Вне офиса сначала подключите VPN — ссылку на него даёт администратор.",
        "ro": "În afara biroului conectați mai întâi VPN — linkul îl oferă administratorul.",
        "en": "Outside the office, connect the VPN first — the administrator provides its link.",
    },
})


def markdown_smb(cfg: dict, expires_at: str, minutes_left: int, cmd_url: str) -> str:
    import json
    user = f"{cfg['netbios']}\\{cfg['login']}"
    out = []
    for lg in ("en", "ru", "ro"):
        out += [f"# {text('smb_title', lg)} — {cfg['login']}", "",
                text("expires", lg, at=expires_at, left=minutes_left), "",
                text("smb_lead", lg), "", f"## {text('smb_drives', lg)}", ""]
        out += [f"- {d['drive']}: \\\\{cfg['server']}\\{d['share']}" for d in cfg["drives"]]
        out += ["", f"## {text('smb_win', lg)}", "", f"{cmd_url}", "", text("smb_win_how", lg), "",
                f"## {text('smb_mac', lg)}", "", text("smb_mac_how", lg), ""]
        out += [f"- smb://{cfg['server']}/{d['share']}" for d in cfg["drives"]]
        out += ["", f"## {text('smb_manual', lg)}", "",
                f"- {text('smb_user', lg)}: {user}",
                f"- {text('f_password', lg)}: {cfg['password']}", "",
                text("smb_vpn", lg), "", f"## {text('rules', lg)}", ""]
        out += [f"- {s}" for s in text("rules_list", lg)]
        out += ["", "---", ""]
    out += ["## Machine-readable settings", "", "```json",
            json.dumps({"type": "SMB", "user": user, **cfg}, ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(out)
