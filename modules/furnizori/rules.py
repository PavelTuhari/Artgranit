"""Чистые правила модуля furnizori: без импорта БД, тестируются без wallet."""

VERSION = "1.0"


def normalize_code(value: str) -> str:
    """Код сущности: без пробелов, верхний регистр."""
    return (value or "").strip().upper()
