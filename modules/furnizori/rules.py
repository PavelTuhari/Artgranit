"""Чистые правила модуля furnizori: без импорта БД, тестируются без wallet."""

VERSION = "1.1"

# Жизненный цикл письма. Порядок = порядок кнопок в интерфейсе.
STATUSES = ("NOU", "TRIMIS", "RASPUNS", "INCHIS")
STATUS_LABEL = {
    "NOU": "Черновик", "TRIMIS": "Отправлено",
    "RASPUNS": "Есть ответ", "INCHIS": "Закрыто",
}
TIPURI = ("DENUMIRI", "PRETURI", "STOC", "GENERAL")
TIP_LABEL = {
    "DENUMIRI": "Наименования", "PRETURI": "Цены",
    "STOC": "Остатки", "GENERAL": "Общее",
}

# Что разрешено класть во вложения. Исполняемое не принимаем принципиально:
# файл потом отдаётся обратно в браузер, и .html/.svg с этого же домена
# выполнили бы свой скрипт в сессии оператора.
ALLOWED_EXT = ("eml", "xlsx", "xls", "csv", "pdf", "docx", "png", "jpg", "jpeg", "zip")
MAX_FILE_BYTES = 25 * 1024 * 1024


def normalize_code(value: str) -> str:
    """Код сущности: без пробелов, верхний регистр."""
    return (value or "").strip().upper()


def valid_status(value: str) -> bool:
    return normalize_code(value) in STATUSES


def valid_tip(value: str) -> bool:
    return normalize_code(value) in TIPURI


def ext_of(name: str) -> str:
    return (name.rsplit(".", 1)[-1] if "." in (name or "") else "").lower()


def check_upload(name: str, size: int) -> str | None:
    """None = можно грузить, иначе — причина отказа для оператора."""
    if not (name or "").strip():
        return "Имя файла пустое"
    if ext_of(name) not in ALLOWED_EXT:
        return f"Тип файла .{ext_of(name) or '?'} не принимается"
    if size <= 0:
        return "Файл пустой"
    if size > MAX_FILE_BYTES:
        return f"Файл больше {MAX_FILE_BYTES // 1024 // 1024} МБ"
    return None


def safe_filename(name: str) -> str:
    """Имя для заголовка скачивания: без путей и переводов строк, иначе
    можно подделать HTTP-заголовок."""
    base = (name or "file").replace("\\", "/").rsplit("/", 1)[-1]
    return "".join(ch for ch in base if ch.isprintable() and ch not in '"\r\n')[:200] or "file"
