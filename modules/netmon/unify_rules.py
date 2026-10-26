"""Унификация клиентов — чистые правила сопоставления, без базы.

Один клиент записан по-разному: «FASTSERVICE SRL» в заявках OTRS, логин
«fastservice» с кодом контрагента 4103, «FASTSERVICE S.R.L.» в нашей
бухгалтерии (UNI.TMS_UNIVERS), схема FASTSERVICE в базе. Здесь — как эти
записи узнают друг друга, что считать точкой магазина и рабочим местом по
истории входов, какие продукты видны по заявкам.
"""
from __future__ import annotations

import re
import unicodedata

from modules.netmon.clients_rules import client_key

# Организационно-правовые формы — шум для сопоставления
_LEGAL = re.compile(
    r"\b(S\s*\.?\s*R\s*\.?\s*L|S\s*\.?\s*A|I\s*\.?\s*I|I\s*\.?\s*C\s*\.?\s*S|I\s*\.?\s*M|GT|SC|LLC|LTD|"
    r"COOP|CONCERN|ООО|ОАО|ЗАО|АО|ИП|SOCIETATEA|CU\s+RASPUNDERE\s+LIMITATA|INTREPRINDEREA|"
    r"INDIVIDUALA|COMPANIA|GRUP)\b\.?", re.I)

# Хвосты схем: роль схемы при основном клиенте
_ROLE_SUFFIX = [("_BK", "bk"), ("_TEST", "test"), ("_HR", "hr"), ("_SALES", "sales"), ("_WEB", "web"),
                ("_SCALES", "scales"), ("_CONT", "cont"), ("_REP", "rep"), ("_UN4EXT", "other"),
                ("_READONLY", "other"), ("_POS", "pos")]


def _ascii(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(name: str | None) -> str:
    """Название → ключ: без формы собственности, диакритики, пробелов и знаков.
    «FASTSERVICE S.R.L.» и «FASTSERVICE SRL» → FASTSERVICE, «Bio Holda SRL» → BIOHOLDA."""
    s = _ascii((name or "").upper())
    s = re.sub(r"\(.*?\)", " ", s)
    s = _LEGAL.sub(" ", s)
    return re.sub(r"[^0-9A-ZА-ЯЁ]", "", s)


def base_of(schema: str | None) -> str:
    """Схема → основной клиент: без служебного хвоста, префикса POS_ и года.
    MOLLTEX18 → MOLLTEX, DATACONTROL2025 → DATACONTROL, POS_BOMBA2025 → BOMBA,
    SANIX_BK → SANIX. Короткие имена (SP245) год не теряют."""
    s = client_key(schema)
    for suf, _role in _ROLE_SUFFIX:
        if s.endswith(suf) and len(s) > len(suf) + 2:
            s = s[: -len(suf)]
    s = re.sub(r"^POS_", "", s)
    s = re.sub(r"_\d+$", "", s)
    m = re.match(r"^(.*?[A-Z])((?:19|20)?\d{2})$", s)
    if m and len(m.group(1)) >= 4:
        s = m.group(1)
    return s


def role_of(schema: str | None) -> str:
    s = (schema or "").upper()
    if s.startswith("POS_"):
        return "pos"
    for suf, role in _ROLE_SUFFIX:
        if s.endswith(suf):
            return role
    return "back"


def match_score(a: str, b: str) -> tuple[int, str]:
    """Насколько два ключа — один клиент: 100 — совпали, 70 — один начало
    другого и не короче 6 букв (FASTSERVICE ≠ FASTFORWARD: общее только FAST)."""
    if not a or not b:
        return 0, ""
    if a == b:
        return 100, "name"
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 6 and long_.startswith(short):
        return 70, "prefix"
    return 0, ""


# ------------------------------------------------- точки по истории входов

_WEB_USERS = {"apache", "www-data", "wwwrun", "nginx", "unisimso", "zhdvpdxv", "php", "web"}
_WEB_HOST = re.compile(r"(^web\d*$|apache|hosting|\.(com|net|ro|md|org|ru)$|^php|^instance|warehouse-storage|"
                       r"server\.|docker)", re.I)


def host_kind(userhost: str | None, os_user: str | None) -> str:
    """Тип точки по записи аудита (программы в аудите нет — только компьютер и
    пользователь): локальная база магазина ходит под OracleService*, касса —
    под pos/casa, сайт — под apache, unisimso и т. п."""
    h, u = (userhost or "").strip(), (os_user or "").strip()
    ul, hl = u.lower(), h.lower()
    if ul.startswith("oracleservice") or ul == "oracle" and not hl.startswith("cloudbd"):
        return "shop"
    if ul in ("pos", "casa", "kassa", "cassa") or re.search(r"\b(casa|kassa|pos)\d*\b", hl.replace("\\", " ")):
        return "pos"
    if "scale" in hl or "cantar" in hl:
        return "scales"
    if ul in _WEB_USERS or _WEB_HOST.search(hl):
        return "web"
    return "office"


def host_name(userhost: str | None) -> str:
    h = (userhost or "").strip()
    return h.split("\\")[-1] if "\\" in h else h


# ------------------------------------------------------------- продукты

PRODUCTS = [
    ("UaMenu", re.compile(r"ua\s?menu", re.I)),
    ("Весы", re.compile(r"cantar|весы|весов|scale|balanta", re.I)),
    ("Кассы / POS", re.compile(r"\bcas[aă]\b|касс|\bpos\b|\btcd\b|fiscal", re.I)),
    ("WooCommerce / сайт", re.compile(r"woocommerce|site|сайт|magazin online|web", re.I)),
    ("Обмен с 1C", re.compile(r"\b1\s?[cс]\b", re.I)),
    ("e-Factura", re.compile(r"e-?factur", re.I)),
    ("Кадры и зарплата", re.compile(r"\bhr\b|salariz|кадр|зарплат|resurse umane", re.I)),
    ("Склад", re.compile(r"depozit|склад|stoc|inventar", re.I)),
    ("Отчёты", re.compile(r"raport|отч[её]т|report", re.I)),
    ("Бонусы и лояльность", re.compile(r"bonus|бонус|loial|card", re.I)),
    ("Резервное копирование", re.compile(r"backup|бэкап|rezerv", re.I)),
]

HOST_PRODUCT = {"shop": "Магазин со своей базой", "pos": "Кассы / POS", "scales": "Весы",
                "web": "WooCommerce / сайт", "office": "UniAcc: рабочие места"}


def products_of_titles(titles: list[tuple[str, str]]) -> dict[str, str]:
    """[(номер заявки, название)] → {продукт: «#номер название» — первое упоминание}."""
    out: dict[str, str] = {}
    for tn, title in titles:
        for prod, rx in PRODUCTS:
            if prod not in out and rx.search(title or ""):
                out[prod] = f"#{tn} {(title or '').strip()}"[:300]
    return out


def kind_of(points: list[dict]) -> str:
    kinds = {p["kind"] for p in points}
    if kinds & {"shop", "pos", "scales"}:
        return "shop"
    if "office" in kinds:
        return "back"
    if "web" in kinds:
        return "web"
    return "none"
