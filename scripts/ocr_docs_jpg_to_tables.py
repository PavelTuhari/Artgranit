#!/usr/bin/env python3
"""
OCR изображений из docs/Nufarul/docs_jpg и генерация HTML-таблиц.
Требуется: pip install pytesseract Pillow, установленный Tesseract (brew install tesseract).
Запуск из корня проекта: python scripts/ocr_docs_jpg_to_tables.py
"""
from __future__ import annotations

import os
import re
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_JPG = ROOT / "docs" / "Nufarul" / "docs_jpg"

# Описание по смыслу для каждой страницы (без OCR)
PAGE_SEMANTIC_DESCRIPTIONS = {
    1: "Схема или титульный элемент документа (содержимое распознано частично).",
    2: "Бланк заказа (BON DE COMANDĂ), приложение 2 к приказу №12 от 26.03.2024: прейскурант услуг химчистки (очистка пера и пуха, продажа пакетов 0,40×0,40 м — 0,80×0,80 м, изменение размеров пакета, пошив из ткани заказчика), колонки — наименование/описание, количество, цена, итого; условия оказания услуг.",
    3: "Заполненный бланк заказа (BON DE COMANDĂ): номер заказа, дата/время, числовые значения (23, 210, 225233).",
    4: "Фрагмент страницы или схема (распознано частично: обозначения Mea, mA, Pa).",
    5: "Страница без распознанного текста (возможно, изображение, график или фото).",
    6: "Страница без распознанного текста (возможно, изображение или схема).",
    7: "Форма приёма заказа (код F-FIP-01-01): пункт приёма, менеджер, дата приёма, номер заказа (Comanda / заказ, Car. 499759); ссылка на стандарты и условия (химикаты, химчистка); блок подписей (менеджер, клиент).",
    8: "Страница без распознанного текста (возможно, изображение или схема).",
}

# Порядок изображений (как в галерее)
IMAGE_FILES = [
    "0-02-05-07af6583836e1f1aa32c260781ab197d19872016a9db1e441eac63c975a7d96e_22131a71b7b.jpg",
    "0-02-05-3306ee75f3235c26822a33a8b96ad1ca748c2221f4932bfc94403241e36ae567_22131a74553.jpg",
    "0-02-05-74bc305a4e0b3ce699f9ff5dc73e87592f6bc42205cdf3e0e3d9e80049ae2828_22131a6fc7f.jpg",
    "0-02-05-a2ebd704fa1dc0438beb5c86e58d8f94fedf49db9a64743b67bae177124642ed_22131a752ed.jpg",
    "0-02-05-a8ee3d774af4ed70775d52f85319e68e3ea2bb0016397e282260cf27b5ff6023_22131a771f6.jpg",
    "0-02-05-d2dc54ae3828a0ec838b9605bf2355bdab4c04afec79fea628c7d4873e3d5f04_22131a7724b.jpg",
    "0-02-05-e5bb4937139f1573aff097f7e52217afe4cbd3548ac897e53dc9861d3bf5bd7e_22131a6f6c6.jpg",
    "0-02-05-f66daccf98c1184603f5116aad9f125fcb416da3bf38b1ae33ca0614bcf35e34_22131a7d72c.jpg",
]

ROW_TOLERANCE = 18   # пикселей — объединять строки с близким top
COL_GAP = 35         # пикселей — если разрыв по x больше, новая ячейка
MIN_SIZE_FOR_SCALE = 600   # если меньшая сторона меньше — масштабируем для OCR


def _preprocess_for_ocr(img):  # PIL Image -> PIL Image
    """Увеличивает мелкие изображения и переводит в оттенки серого для лучшего OCR."""
    from PIL import Image as PILImage, ImageFilter, ImageOps
    w, h = img.size
    if min(w, h) < MIN_SIZE_FOR_SCALE and max(w, h) > 0:
        scale = MIN_SIZE_FOR_SCALE / min(w, h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        resample = getattr(getattr(PILImage, "Resampling", None), "LANCZOS", None) or getattr(PILImage, "LANCZOS", PILImage.BICUBIC)
        img = img.resize((new_w, new_h), resample)
    try:
        img = ImageOps.grayscale(img)
    except Exception:
        pass
    try:
        img = img.filter(ImageFilter.SHARPEN)
    except Exception:
        pass
    return img


def ocr_image_to_table(img_path: Path) -> tuple[str, str]:
    """
    Распознаёт изображение, возвращает (описание_текста, html_таблицы).
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return (
            "OCR недоступен: установите pytesseract и Pillow (pip install pytesseract Pillow), а также Tesseract (brew install tesseract).",
            "<p>Таблица не сгенерирована.</p>"
        )
    if not img_path.is_file():
        return "Файл не найден", "<p>—</p>"
    try:
        img = Image.open(img_path)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
    except Exception as e:
        return f"Ошибка открытия: {e}", "<p>—</p>"
    img_ocr = _preprocess_for_ocr(img.copy())
    # Полный текст для описания (по тому же изображению, что и таблица)
    try:
        full_text = pytesseract.image_to_string(img_ocr, lang="ron+rus+eng")
        full_text = (full_text or "").strip()
    except Exception:
        full_text = pytesseract.image_to_string(img_ocr)
        full_text = (full_text or "").strip()
    # Данные по словам для таблицы
    try:
        data = pytesseract.image_to_data(img_ocr, lang="ron+rus+eng", output_type=pytesseract.Output.DICT)
    except Exception:
        data = pytesseract.image_to_data(img_ocr, output_type=pytesseract.Output.DICT)
    n = len(data.get("text", []))
    if n == 0:
        desc = full_text[:2000] if full_text else "Текст не распознан."
        return desc, "<p>Не удалось выделить ячейки таблицы.</p>"
    words = []
    for i in range(n):
        text = (data.get("text", []) or [""])[i]
        text = (text or "").strip()
        if not text:
            continue
        left = int((data.get("left", []) or [0])[i])
        top = int((data.get("top", []) or [0])[i])
        width = int((data.get("width", []) or [0])[i])
        height = int((data.get("height", []) or [0])[i])
        words.append({"text": text, "left": left, "top": top, "width": width, "height": height})
    if not words:
        return full_text[:2000] or "Текст не распознан.", "<p>Нет слов для таблицы.</p>"
    # Группировка по строкам (по top)
    words.sort(key=lambda w: (w["top"], w["left"]))
    rows_dict = {}
    for w in words:
        t = w["top"]
        key = t
        for k in list(rows_dict.keys()):
            if abs(k - t) <= ROW_TOLERANCE:
                key = k
                break
        rows_dict.setdefault(key, []).append(w)
    rows_sorted = sorted(rows_dict.items(), key=lambda x: x[0])
    table_rows = []
    for _, row_words in rows_sorted:
        row_words.sort(key=lambda w: w["left"])
        cells = []
        prev_right = -999
        for w in row_words:
            gap = w["left"] - prev_right
            if gap > COL_GAP and cells:
                cells.append([])  # новая ячейка
            if not cells or not isinstance(cells[-1], list):
                cells.append([])
            cells[-1].append(w["text"])
            prev_right = w["left"] + w.get("width", 0)
        out_cells = [(" ".join(c) if isinstance(c, list) else str(c)).strip() for c in cells]
        table_rows.append(out_cells)
    # Нормализация: одинаковое число ячеек в строке (по максимуму)
    max_cols = max(len(r) for r in table_rows) if table_rows else 0
    for r in table_rows:
        while len(r) < max_cols:
            r.append("")
    # HTML таблица
    if not table_rows:
        return full_text[:2000] or "Текст не распознан.", "<p>Нет данных для таблицы.</p>"
    html_rows = []
    for i, row in enumerate(table_rows):
        tag = "th" if i == 0 else "td"
        cells_html = "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in row)
        html_rows.append(f"<tr>{cells_html}</tr>")
    table_html = f'<table class="ocr-table"><tbody>{"".join(html_rows)}</tbody></table>'
    description = full_text[:2000] if full_text else "Текст не распознан."
    return description, table_html


def main():
    for idx, img_name in enumerate(IMAGE_FILES, start=1):
        img_path = DOCS_JPG / img_name
        page_path = DOCS_JPG / f"page_{idx}.html"
        if not page_path.is_file():
            print(f"Пропуск страницы {idx}: {page_path} не найден")
            continue
        print(f"OCR: {img_name[:50]}...")
        desc, table_html = ocr_image_to_table(img_path)
        # Вставить в page_N.html: заменить секцию .content-tables
        content = page_path.read_text(encoding="utf-8")
        semantic = PAGE_SEMANTIC_DESCRIPTIONS.get(idx, "")
        desc_esc = html.escape(desc).replace("\n", "<br>\n")
        new_section = (
            f'<section class="content-tables" aria-label="Таблицы и данные со страницы">\n'
            f'<p class="ocr-desc"><strong>Описание по смыслу:</strong></p>\n<p class="ocr-semantic">{html.escape(semantic)}</p>\n'
            f'<p class="ocr-desc"><strong>Данные в виде таблицы (OCR):</strong></p>\n{table_html}\n'
            f'<p class="ocr-desc"><strong>Распознанный текст (OCR), для справки:</strong></p>\n<p class="ocr-text">{desc_esc}</p>\n'
            f"</section>"
        )
        pattern = r'<section class="content-tables"[^>]*>.*?</section>'
        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, new_section, content, count=1, flags=re.DOTALL)
        else:
            content = content.replace(
                '<section class="content-tables" aria-label="Таблицы и данные со страницы">\n        <!-- Место для таблиц',
                new_section.replace("</section>", "") + "<!-- "
            ).replace("    </section>", "--> </section>")
        # Добавить стили для .ocr-desc и .ocr-text если нет
        if ".content-tables .ocr-semantic" not in content:
            content = content.replace(
                ".content-tables tr:nth-child(even) { background: #f0fdfa; }",
                ".content-tables .ocr-desc { margin-top: 16px; margin-bottom: 6px; }\n        .content-tables .ocr-semantic { background: #ecfdf5; padding: 12px; border-radius: 8px; font-size: 14px; line-height: 1.5; margin-bottom: 16px; border-left: 4px solid var(--primary); }\n        .content-tables .ocr-text { background: #f8fafc; padding: 12px; border-radius: 8px; font-size: 13px; line-height: 1.5; white-space: pre-wrap; margin-bottom: 16px; }\n        .content-tables tr:nth-child(even) { background: #f0fdfa; }"
            )
        page_path.write_text(content, encoding="utf-8")
        print(f"  Обновлён {page_path.name}")
    print("Готово.")


if __name__ == "__main__":
    main()
