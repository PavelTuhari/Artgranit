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
    if value in (None, "", True):
        return TTL_DEFAULT
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
