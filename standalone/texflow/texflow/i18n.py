"""Три языка интерфейса: русский (ru), румынский (ro), английский (en).

Ключ перевода — исходная русская строка. ``_("Поставки")`` → «Livrări» / «Shipments».
Нет перевода — показывается русская строка (тест ``test_i18n`` следит, чтобы таких не было).
"""
from __future__ import annotations

from contextvars import ContextVar

from .i18n_catalog import CATALOG

LANGS = ("ru", "ro", "en")
LANG_NAMES = {"ru": "Русский", "ro": "Română", "en": "English"}
_lang: ContextVar[str] = ContextVar("texflow_lang", default="ru")


def set_lang(lang: str) -> str:
    lang = lang if lang in LANGS else "ru"
    _lang.set(lang)
    return lang


def current_lang() -> str:
    return _lang.get()


def gettext(text: str, lang: str | None = None, **kw) -> str:
    lang = lang or _lang.get()
    out = text
    if lang != "ru":
        out = CATALOG.get(text, {}).get(lang) or text
    return out.format(**kw) if kw else out


_ = gettext


def name_sql(alias: str = "", lang: str | None = None, col: str = "name") -> str:
    """SQL-выражение локализованного названия справочника с откатом на русское."""
    lang = lang or _lang.get()
    p = f"{alias}." if alias else ""
    if lang == "ru":
        return f"{p}{col}"
    return f"COALESCE(NULLIF({p}{col}_{lang}, ''), {p}{col})"


_STATUS = {
    "shipment": {"open": "открыта", "sorted": "разобрана", "priced": "оценена", "closed": "закрыта"},
    "bag": {"closed": "закрыт", "sorting": "в разборе", "done": "разобран"},
}
_GENDER = {"": "", "women": "Женское", "men": "Мужское", "kids": "Детское", "unisex": "Унисекс"}
JS_KEYS = ("ошибка сети",)


def status_name(code: str, kind: str = "shipment") -> str:
    ru = _STATUS.get(kind, {}).get(code)
    return gettext(ru) if ru else code


def gender_name(code: str) -> str:
    ru = _GENDER.get(code)
    return gettext(ru) if ru is not None else code   # старые значения показываются как есть


def js_strings() -> dict:
    return {k: gettext(k) for k in JS_KEYS}
