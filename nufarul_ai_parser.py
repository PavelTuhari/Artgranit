"""
Nufarul AI Parser — умный разбор текстовых заказов в позиции корзины.
Использует rapidfuzz для нечёткого поиска по каталогу услуг.
Поддержка двух языков: русский и румынский (+ смешанный ввод).

Вход: произвольный текст (напр. «2 рубашки, palton, 3 perne»)
Выход: [{service_id, qty, original, confidence, service_name}]
"""
import re
from typing import List, Dict, Any, Optional
from rapidfuzz import fuzz, process

# ---- Нормализация текста ----

# Русские синонимы / короткие формы → полные формы (как в каталоге RU)
SYNONYMS_RU = {
    "рубашка": "блуза с коротким рукавом",
    "рубашки": "блуза с коротким рукавом",
    "рубаха": "блуза с коротким рукавом",
    "сорочка": "блуза с коротким рукавом",
    "куртка": "куртка без капюшона",
    "пуховик": "куртка пуховая",
    "штаны": "брюки, джинсы",
    "джинсы": "брюки, джинсы",
    "брюки": "брюки, джинсы",
    "костюм": "спортивный костюм",
    "пиджак": "пиджак",
    "жакет": "пиджак",
    "кардиган": "пиджак (свыше 85 см), кардиган",
    "платье": "платье простое",
    "юбка": "юбка <70 см",
    "свитер": "свитер, жакет, джемпер с длинным рукавом",
    "пуловер": "свитер, жакет, джемпер с длинным рукавом",
    "толстовка": "свитер, жакет, джемпер с длинным рукавом",
    "джемпер": "свитер, жакет, джемпер с длинным рукавом",
    "плащ": "плащ",
    "шуба": "шуба (волк, норка)",
    "полушубок": "полушубок (волк, норка)",
    "пальто": "демисезонное пальто без капюшона",
    "подушка": "подушка на синтепоне 50x70",
    "подушки": "подушка на синтепоне 50x70",
    "одеяло": "одеяло 2-х спальное синтепоновое",
    "покрывало": "покрывало до 3 кв.м",
    "ковёр": "тонкие ковры стирка",
    "ковер": "тонкие ковры стирка",
    "шторы": "гардино, тюлевые изделия, шторы",
    "штора": "гардино, тюлевые изделия, шторы",
    "тюль": "гардино, тюлевые изделия, шторы",
    "галстук": "галстук",
    "шарф": "шарф, платок <1м²",
    "платок": "шарф, платок <1м²",
    "шапка": "тонкая шапка, кепка, берет",
    "берет": "тонкая шапка, кепка, берет",
    "кепка": "тонкая шапка, кепка, берет",
    "перчатки": "перчатки",
    "сумка": "сумка, ранец",
    "сумки": "сумка, ранец",
    "ранец": "сумка, ранец",
    "ботинки": "ботики кожа",
    "обувь": "ботики кожа",
    "туфли": "туфли, мокасины, кроссовки кожаные",
    "кроссовки": "туфли, мокасины, кроссовки кожаные",
    "мокасины": "туфли, мокасины, кроссовки кожаные",
    "сапоги": "сапожки кожа",
    "полусапожки": "полусапожки кожа",
    "халат": "халат длинный без капюшона",
    "пижама": "пижама тонкая",
    "комбинезон": "комбинезон",
    "майка": "майка трикотажная",
    "футболка": "поло, футболка, раглан с рукавами",
    "поло": "поло, футболка, раглан с рукавами",
    "носки": "носки",
    "дублёнка": "дублёнка 60-90 см",
    "дубленка": "дублёнка 60-90 см",
    "плед": "плед",
    "фартук": "фартук",
    "ремень": "ремень крашение",
    "воротник": "воротник (волк, норка)",
    "наперник": "наперник 50x70",
    "игрушка": "мягкие игрушки до 1 кг",
    "игрушки": "мягкие игрушки до 1 кг",
}

# Румынские синонимы / короткие формы → полные формы (как в каталоге RO)
SYNONYMS_RO = {
    # Одежда верхняя
    "geacă": "geacă pe puf fără glugă",
    "geaca": "geacă pe puf fără glugă",
    "jachetă": "geacă pe puf fără glugă",
    "jacheta": "geacă pe puf fără glugă",
    "palton": "palton de demi-sezon fără glugă",
    "haină": "haină de blană (lup, nurcă)",
    "haina": "haină de blană (lup, nurcă)",
    "cojoc": "cojoc 60-90 cm",
    "scurteică": "scurteică (lup, nurcă)",
    "scurteica": "scurteică (lup, nurcă)",
    "impermeabil": "impermeabil",
    "pelerină": "impermeabil, pelerină cu glugă",
    "pelerina": "impermeabil, pelerină cu glugă",
    "vestă": "vestă fără glugă",
    "vesta": "vestă fără glugă",
    # Одежда
    "cămașă": "cămașă",
    "camasa": "cămașă",
    "bluză": "bluză cu mânecă scurtă",
    "bluza": "bluză cu mânecă scurtă",
    "rochie": "rochie simplă",
    "fustă": "fustă <70 cm",
    "fusta": "fustă <70 cm",
    "pantaloni": "pantaloni, jeanși",
    "jeanși": "pantaloni, jeanși",
    "jeansi": "pantaloni, jeanși",
    "sacou": "sacou",
    "cardigan": "sacou (peste 85 cm), cardigan",
    "costum": "costum sportiv",
    "combinezon": "combinezon",
    "halat": "halat lung fără glugă",
    "pijama": "pijama subțire",
    "pulover": "pulover, jacheta, bluză cu mânecă lungă",
    "tricou": "polo, tricou, raglan cu mâneci",
    "maiou": "maiou tricotat",
    "polo": "polo, tricou, raglan cu mâneci",
    # Аксессуары
    "cravată": "cravată",
    "cravata": "cravată",
    "eșarfă": "eșarfă, batic <1m²",
    "esarfa": "eșarfă, batic <1m²",
    "batic": "eșarfă, batic <1m²",
    "mănuși": "mănuși",
    "manusi": "mănuși",
    "căciulă": "căciulă de iarnă",
    "caciula": "căciulă de iarnă",
    "șapcă": "șapcă subțire, chipiu, beretă",
    "sapca": "șapcă subțire, chipiu, beretă",
    "beretă": "șapcă subțire, chipiu, beretă",
    "bereta": "șapcă subțire, chipiu, beretă",
    "chipiu": "șapcă subțire, chipiu, beretă",
    "geantă": "geantă, rucsac",
    "geanta": "geantă, rucsac",
    "rucsac": "geantă, rucsac",
    "șorț": "șorț",
    "sort": "șorț",
    # Обувь
    "pantofi": "pantofi, mocasini, adidași din piele",
    "adidași": "pantofi, mocasini, adidași din piele",
    "adidasi": "pantofi, mocasini, adidași din piele",
    "mocasini": "pantofi, mocasini, adidași din piele",
    "teniși": "pantofi, teniși, mocasini, adidași vopsire",
    "tenisi": "pantofi, teniși, mocasini, adidași vopsire",
    "botine": "botine din piele",
    "ghete": "ghete din piele",
    "cizme": "cizme din piele",
    # Домашний текстиль
    "pernă": "pernă pe sintepon 50x70",
    "perna": "pernă pe sintepon 50x70",
    "perne": "pernă pe sintepon 50x70",
    "plapumă": "plapumă 2 persoane din sintepon",
    "plapuma": "plapumă 2 persoane din sintepon",
    "cuvertură": "cuvertură până la 3 m²",
    "cuvertura": "cuvertură până la 3 m²",
    "pled": "pled",
    "perdele": "perdele, tul, draperii",
    "perdea": "perdele, tul, draperii",
    "tul": "perdele, tul, draperii",
    "draperii": "perdele, tul, draperii",
    "covor": "covoare, carpete grosime <10 mm",
    "covoare": "covoare, carpete grosime <10 mm",
    "carpetă": "covoare, carpete grosime <10 mm",
    "carpeta": "covoare, carpete grosime <10 mm",
    "jucărie": "jucării moi până la 1 kg",
    "jucarii": "jucării moi până la 1 kg",
    "jucării": "jucării moi până la 1 kg",
    "husă": "husă de saltea din stofă subțire",
    "husa": "husă de saltea din stofă subțire",
    "față de pernă": "față de pernă 50x70",
    "fata de perna": "față de pernă 50x70",
    "napernik": "față de pernă 50x70",
    # Стирка
    "spălare": "spălare combinată cu curățare chimică",
    "spalare": "spălare combinată cu curățare chimică",
    "călcare": "călcare rufe după spălare",
    "calcare": "călcare rufe după spălare",
    "lenjerie": "lenjerie de pat și lenjerie de modă",
    # Доставка
    "livrare": "livrare în toate sectoarele orașului (botanica, buiucani, centru, râșcani, ciocana)",
    # Кожа
    "ciorapi": "ciorapi",
    "curea": "curea vopsire",
}


def _normalize(text: str) -> str:
    """Приведение к нижнему регистру + нормализация пробелов + диакритика."""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def _remove_diacritics(text: str) -> str:
    """Убираем румынские диакритики для fuzzy-сравнения: ăâîșț → aaisit."""
    table = str.maketrans('ăâîșțĂÂÎȘȚ', 'aaistAAIST')
    return text.translate(table)


def _stem_ru(word: str) -> str:
    """Примитивная стемминг-функция для русского: убираем окончания."""
    for suffix in ('ами', 'ями', 'ого', 'ему', 'ую', 'ой', 'ей', 'ые',
                   'ом', 'ем', 'ов', 'ев', 'ах', 'ях', 'ки', 'ка', 'ку',
                   'ок', 'ек', 'ий', 'ые', 'ой', 'ей', 'ую', 'ая', 'яя',
                   'ы', 'и', 'а', 'о', 'у', 'е', 'я'):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[:-len(suffix)]
    return word


def _stem_ro(word: str) -> str:
    """Примитивная стемминг-функция для румынского: убираем окончания."""
    for suffix in ('elor', 'ilor', 'ului', 'elor',
                   'ată', 'ită', 'ută', 'ări', 'iri', 'uri',
                   'ele', 'ile', 'ule', 'ări',
                   'ți', 'te', 'tă', 'că',
                   'ul', 'ea', 'ua', 'ia', 'le', 'ri',
                   'ă', 'e', 'i', 'a'):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[:-len(suffix)]
    return word


def _is_cyrillic(text: str) -> bool:
    """Проверяет, содержит ли текст кириллицу."""
    return bool(re.search(r'[а-яёА-ЯЁ]', text))


def _is_latin(text: str) -> bool:
    """Проверяет, содержит ли текст латиницу."""
    return bool(re.search(r'[a-zA-ZăâîșțĂÂÎȘȚ]', text))


def _expand_synonyms(query: str) -> List[str]:
    """
    Раскрытие синонимов в обоих языках.
    Возвращает список кандидатов (1-3 строки) для поиска.
    """
    q = _normalize(query)
    q_no_dia = _remove_diacritics(q)
    candidates = [q]

    # 1. Точное совпадение в RU-синонимах
    if q in SYNONYMS_RU:
        candidates.insert(0, SYNONYMS_RU[q])

    # 2. Точное совпадение в RO-синонимах (с диакритиками и без)
    if q in SYNONYMS_RO:
        candidates.insert(0, SYNONYMS_RO[q])
    else:
        # Пробуем без диакритик
        for syn_key, syn_val in SYNONYMS_RO.items():
            if _remove_diacritics(syn_key) == q_no_dia:
                candidates.insert(0, syn_val)
                break

    # 3. Стем-совпадение RU
    q_stem_ru = _stem_ru(q)
    for short, full in SYNONYMS_RU.items():
        if _stem_ru(short) == q_stem_ru and full not in candidates:
            candidates.insert(0, full)
            break

    # 4. Стем-совпадение RO
    q_stem_ro = _stem_ro(q_no_dia)
    for short, full in SYNONYMS_RO.items():
        if _stem_ro(_remove_diacritics(short)) == q_stem_ro and full not in candidates:
            candidates.insert(0, full)
            break

    return candidates


def _split_order_text(text: str) -> List[Dict[str, Any]]:
    """
    Разбивает текст «2 рубашки, palton, 3 perne» на [{query, qty}].
    Поддерживает: запятую, точку с запятой, перенос строки,
    русское «и», румынское «și» как разделители.
    """
    # Разделяем по ,  ;  \n  и слово "и"/"și" между элементами
    text = re.sub(r'\s+и\s+', ', ', text)
    text = re.sub(r'\s+[sș]i\s+', ', ', text, flags=re.I)
    parts = re.split(r'[,;\n]+', text)
    items = []

    # Паттерн для единиц: шт/штук/штуки (RU) + buc/bucăți/bucată/bucati (RO)
    unit_pattern = r'(?:шт\.?|штук[иа]?|buc\.?|bucăț[ia]?|bucata|bucati)'

    for part in parts:
        part = part.strip()
        if not part:
            continue
        qty = 1
        query = part
        # ПОРЯДОК ВАЖЕН: сначала проверяем паттерны с единицами (шт/buc),
        # потом простые числовые паттерны

        # 1. Число + единица в начале: «2шт рубашка» / «2 buc rochie»
        m_unit_start = re.match(r'^(\d+)\s*' + unit_pattern + r'\s+(.+)', part, re.I)
        if m_unit_start:
            qty = int(m_unit_start.group(1))
            query = m_unit_start.group(2)
        else:
            # 2. Единица в конце: «рубашка 2 шт» / «rochie 2 buc»
            m_unit_end = re.match(r'^(.+?)\s+(\d+)\s*' + unit_pattern + r'$', part, re.I)
            if m_unit_end:
                query = m_unit_end.group(1)
                qty = int(m_unit_end.group(2))
            else:
                # 3. Число в начале: «2 рубашки» / «2 rochii»
                m = re.match(r'^(\d+)\s+(.+)', part)
                if m:
                    qty = int(m.group(1))
                    query = m.group(2)
                else:
                    # 4. Число в конце: «рубашка 2» / «rochie 2»
                    m2 = re.match(r'^(.+?)\s+(\d+)$', part)
                    if m2:
                        query = m2.group(1)
                        qty = int(m2.group(2))
        items.append({"query": query.strip(), "qty": max(qty, 1)})
    return items


def parse_order(text: str, services: List[Dict[str, Any]],
                threshold: int = 45) -> List[Dict[str, Any]]:
    """
    Главная функция: парсит текст заказа → список совпадений.
    Полностью двуязычный: RU + RO + смешанный ввод.

    Args:
        text: произвольный текст от оператора (RU, RO, или смешанный)
        services: список услуг из БД [{id, name_ru, name_ro, name_en, name, price, ...}]
        threshold: минимальный порог схожести (0-100)

    Returns:
        [{service_id, qty, original, confidence, service_name, service_name_ro}]
    """
    if not text or not text.strip():
        return []

    # Собираем словарь: normalized_name → (service, lang_key)
    # Каждое имя услуги добавляется на всех доступных языках
    name_map = {}      # normalized_name → service
    choices = []       # для rapidfuzz
    choices_no_dia = []  # без диакритик для RO-поиска

    for s in services:
        for key in ('name_ru', 'name_ro', 'name_en', 'name'):
            name = (s.get(key) or '').strip()
            if name:
                norm = _normalize(name)
                if norm not in name_map:
                    name_map[norm] = s
                    choices.append(norm)
                # Также добавляем версию без диакритик для RO
                norm_no_dia = _remove_diacritics(norm)
                if norm_no_dia != norm and norm_no_dia not in name_map:
                    name_map[norm_no_dia] = s
                    choices.append(norm_no_dia)

    items = _split_order_text(text)
    results = []

    for item in items:
        raw_query = item["query"]
        qty = item["qty"]

        # 1. Раскрытие синонимов (возвращает список кандидатов)
        candidates = _expand_synonyms(raw_query)

        best_match_svc = None
        best_match_score = 0
        best_match_via = None  # для отладки

        for candidate in candidates:
            query_norm = _normalize(candidate)
            query_no_dia = _remove_diacritics(query_norm)

            # 2. Точное вхождение (подстрока) — проверяем и с диакритиками и без
            exact_match = None
            best_substr_len = 999999
            for name, svc in name_map.items():
                if query_norm == name or query_no_dia == name:
                    exact_match = svc
                    best_substr_len = len(name)
                    break
                # Подстрока
                if query_norm in name or query_no_dia in name:
                    if exact_match is None or len(name) < best_substr_len:
                        exact_match = svc
                        best_substr_len = len(name)

            if exact_match:
                # Проверяем совпадение по любому языковому полю
                for lang_key in ('name_ru', 'name_ro', 'name_en', 'name'):
                    lang_name = _normalize(exact_match.get(lang_key, '') or '')
                    lang_name_no_dia = _remove_diacritics(lang_name)
                    if query_norm == lang_name or query_no_dia == lang_name_no_dia:
                        score = 97
                        if score > best_match_score:
                            best_match_svc = exact_match
                            best_match_score = score
                            best_match_via = "exact"
                        break
                    if query_norm in lang_name or query_no_dia in lang_name_no_dia:
                        score = 87
                        if score > best_match_score:
                            best_match_svc = exact_match
                            best_match_score = score
                            best_match_via = "substring"
                        break

            if best_match_score >= 95:
                break  # уже отличное совпадение, не нужно продолжать

            # 3. rapidfuzz fuzzy matching — проверяем и с диакритиками и без
            for q_variant in [query_norm, query_no_dia]:
                for scorer, scorer_name in [
                    (fuzz.token_set_ratio, "token_set"),
                    (fuzz.partial_ratio, "partial"),
                    (fuzz.WRatio, "wratio"),
                ]:
                    res = process.extractOne(
                        q_variant, choices,
                        scorer=scorer,
                        score_cutoff=threshold,
                    )
                    if res and res[1] > best_match_score:
                        matched_svc = name_map.get(res[0])
                        if matched_svc:
                            best_match_svc = matched_svc
                            best_match_score = res[1]
                            best_match_via = scorer_name

        if best_match_svc and best_match_score >= threshold:
            results.append({
                "service_id": best_match_svc["id"],
                "qty": qty,
                "original": raw_query,
                "confidence": round(best_match_score),
                "service_name": best_match_svc.get("name_ru") or best_match_svc.get("name", ""),
                "service_name_ro": best_match_svc.get("name_ro") or "",
            })
        else:
            results.append({
                "service_id": None,
                "qty": qty,
                "original": raw_query,
                "confidence": 0,
                "service_name": None,
                "service_name_ro": None,
            })

    return results
