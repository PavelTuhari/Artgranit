"""
Разбор голосовой команды заказа для мобильного приложения «Планограммы».

Распознавание речи выполняет само устройство (системный ASR iOS/Android) —
сюда приходит уже ТЕКСТ. Задача модуля: превратить фразу продавца в позиции
заказа, ничего не выдумав.

  «закажи два ящика помидоров и десять килограмм картошки»
   → add | помидоры × 2 ящика | картофель × 10 кг

Три решения, определяющие всю логику ниже.

1. **Никакой генеративной модели.** Разбор детерминированный: числительные,
   единицы измерения, словарь товаров. Менеджер в зале должен получать
   один и тот же результат на одну и ту же фразу, а спорную позицию —
   с честной пометкой «не распознано», а не с правдоподобной выдумкой.

2. **Сопоставление товара — с оценкой уверенности.** Позиция ниже порога
   уходит в заказ со статусом ambiguous/unmatched и требует выбора руками.
   Заказ на 20 ящиков не то́й позиции дороже лишнего касания экрана.

3. **Три языка равноправны.** Русский, румынский и английский разбираются
   одним кодом: отличаются только словари числительных, единиц и команд.

Oracle-объекты: sql/94_plg_mobile.sql
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ==================== Словари ====================

NUMBER_WORDS: Dict[str, Dict[str, float]] = {
    'ru': {
        'ноль': 0, 'один': 1, 'одна': 1, 'одну': 1, 'два': 2, 'две': 2, 'двe': 2,
        'три': 3, 'четыре': 4, 'пять': 5, 'шесть': 6, 'семь': 7, 'восемь': 8,
        'девять': 9, 'десять': 10, 'одиннадцать': 11, 'двенадцать': 12,
        'тринадцать': 13, 'четырнадцать': 14, 'пятнадцать': 15, 'шестнадцать': 16,
        'семнадцать': 17, 'восемнадцать': 18, 'девятнадцать': 19, 'двадцать': 20,
        'тридцать': 30, 'сорок': 40, 'пятьдесят': 50, 'шестьдесят': 60,
        'семьдесят': 70, 'восемьдесят': 80, 'девяносто': 90, 'сто': 100,
        'полтора': 1.5, 'полторы': 1.5, 'пол': 0.5, 'половину': 0.5,
        'пару': 2, 'парочку': 2, 'дюжину': 12, 'дюжина': 12,
    },
    'ro': {
        'zero': 0, 'un': 1, 'una': 1, 'unu': 1, 'doi': 2, 'doua': 2, 'două': 2,
        'trei': 3, 'patru': 4, 'cinci': 5, 'sase': 6, 'șase': 6, 'sapte': 7,
        'șapte': 7, 'opt': 8, 'noua': 9, 'nouă': 9, 'zece': 10, 'unsprezece': 11,
        'doisprezece': 12, 'douasprezece': 12, 'douăsprezece': 12,
        'treisprezece': 13, 'paisprezece': 14, 'cincisprezece': 15,
        'saisprezece': 16, 'șaisprezece': 16, 'saptesprezece': 17,
        'optsprezece': 18, 'nouasprezece': 19, 'douazeci': 20, 'douăzeci': 20,
        'treizeci': 30, 'patruzeci': 40, 'cincizeci': 50, 'suta': 100, 'sută': 100,
        'jumatate': 0.5, 'jumătate': 0.5, 'duzina': 12,
    },
    'en': {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
        'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
        'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
        'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
        'thirty': 30, 'forty': 40, 'fifty': 50, 'hundred': 100,
        'half': 0.5, 'dozen': 12, 'couple': 2, 'a': 1, 'an': 1,
    },
}

# Единица → (код, множитель к базовой единице товара)
# Ящик/короб не имеют фиксированного размера: множитель берётся из
# ORDER_MULTIPLE товара, здесь помечается признаком pack=True.
UNITS: Dict[str, Dict[str, Tuple[str, bool]]] = {
    'ru': {
        'штука': ('pcs', False), 'штуки': ('pcs', False), 'штук': ('pcs', False),
        'шт': ('pcs', False), 'единиц': ('pcs', False),
        'килограмм': ('kg', False), 'килограмма': ('kg', False),
        'килограммов': ('kg', False), 'кило': ('kg', False), 'кг': ('kg', False),
        'грамм': ('g', False), 'граммов': ('g', False), 'г': ('g', False),
        'литр': ('l', False), 'литра': ('l', False), 'литров': ('l', False), 'л': ('l', False),
        'ящик': ('case', True), 'ящика': ('case', True), 'ящиков': ('case', True),
        'коробка': ('case', True), 'коробки': ('case', True), 'коробок': ('case', True),
        'короб': ('case', True), 'короба': ('case', True), 'коробов': ('case', True),
        'упаковка': ('case', True), 'упаковки': ('case', True), 'упаковок': ('case', True),
        'палета': ('pallet', True), 'палеты': ('pallet', True), 'паллет': ('pallet', True),
        'лоток': ('case', True), 'лотка': ('case', True), 'лотков': ('case', True),
    },
    'ro': {
        'bucata': ('pcs', False), 'bucată': ('pcs', False), 'bucati': ('pcs', False),
        'bucăți': ('pcs', False), 'buc': ('pcs', False),
        'kilogram': ('kg', False), 'kilograme': ('kg', False), 'kg': ('kg', False),
        'gram': ('g', False), 'grame': ('g', False),
        'litru': ('l', False), 'litri': ('l', False), 'l': ('l', False),
        'cutie': ('case', True), 'cutii': ('case', True),
        'lada': ('case', True), 'ladă': ('case', True), 'lazi': ('case', True),
        'bax': ('case', True), 'baxuri': ('case', True),
        'palet': ('pallet', True), 'paleti': ('pallet', True), 'paleți': ('pallet', True),
    },
    'en': {
        'piece': ('pcs', False), 'pieces': ('pcs', False), 'pcs': ('pcs', False),
        'unit': ('pcs', False), 'units': ('pcs', False),
        'kilogram': ('kg', False), 'kilograms': ('kg', False), 'kilo': ('kg', False),
        'kg': ('kg', False), 'gram': ('g', False), 'grams': ('g', False),
        'litre': ('l', False), 'liter': ('l', False), 'liters': ('l', False), 'l': ('l', False),
        'box': ('case', True), 'boxes': ('case', True), 'case': ('case', True),
        'cases': ('case', True), 'crate': ('case', True), 'crates': ('case', True),
        'pack': ('case', True), 'packs': ('case', True),
        'pallet': ('pallet', True), 'pallets': ('pallet', True),
    },
}

# Намерение → список слов-триггеров. Порядок важен: submit/cancel проверяются
# раньше add, иначе «отправь заказ» разберётся как «закажи отправь».
INTENT_WORDS: List[Tuple[str, Dict[str, Sequence[str]]]] = [
    ('submit', {'ru': ('отправь', 'отправить', 'подтверди', 'подтвердить', 'готово',
                       'отправляй', 'проведи'),
                'ro': ('trimite', 'confirma', 'confirmă', 'gata'),
                'en': ('submit', 'send', 'confirm', 'done')}),
    ('cancel', {'ru': ('отмени заказ', 'очисти заказ', 'удали заказ', 'сбрось'),
                'ro': ('anuleaza comanda', 'anulează comanda', 'sterge comanda'),
                'en': ('cancel order', 'clear order', 'discard order')}),
    ('remove', {'ru': ('убери', 'удали', 'исключи', 'не надо', 'отмени'),
                'ro': ('scoate', 'sterge', 'șterge', 'elimina', 'elimină'),
                'en': ('remove', 'delete', 'drop', 'take out')}),
    ('set',    {'ru': ('поставь', 'сделай', 'измени', 'исправь', 'замени на'),
                'ro': ('pune', 'schimba', 'schimbă', 'modifica'),
                'en': ('set', 'change', 'make it', 'update')}),
    ('query',  {'ru': ('сколько', 'покажи', 'что в заказе', 'остаток'),
                'ro': ('cat', 'cât', 'arata', 'arată', 'stoc'),
                'en': ('how many', 'show', 'what is in', 'stock')}),
    ('add',    {'ru': ('закажи', 'заказать', 'добавь', 'добавить', 'нужно', 'надо',
                       'привези', 'привезти', 'закажем', 'дозакажи'),
                'ro': ('comanda', 'comandă', 'adauga', 'adaugă', 'trebuie', 'aduc'),
                'en': ('order', 'add', 'need', 'bring', 'reorder')}),
]

# Разделители перечисления
SPLIT_WORDS = {
    'ru': (' и ', ' плюс ', ' также ', ' ещё ', ' еще ', ' затем '),
    'ro': (' si ', ' și ', ' plus ', ' apoi ', ' inca ', ' încă '),
    'en': (' and ', ' plus ', ' also ', ' then '),
}

# Слова, не несущие смысла при сопоставлении товара
STOP_WORDS = {
    'ru': {'мне', 'нам', 'пожалуйста', 'на', 'в', 'для', 'по', 'из', 'с', 'со',
           'этого', 'этот', 'склад', 'магазин', 'завтра', 'сегодня', 'срочно'},
    'ro': {'te', 'rog', 'pentru', 'la', 'de', 'din', 'cu', 'maine', 'mâine', 'azi', 'urgent'},
    'en': {'please', 'for', 'to', 'from', 'with', 'the', 'of', 'tomorrow', 'today', 'urgent'},
}

MATCH_OK = 72.0          # выше — позиция принимается автоматически
MATCH_AMBIGUOUS = 45.0   # между порогами — просим подтвердить выбор


# ==================== Нормализация ====================

def normalize(text: str) -> str:
    """
    К нижнему регистру, без диакритики и знаков препинания.

    Диакритика снимается намеренно: ASR на румынском отдаёт то «lapte proaspăt»,
    то «lapte proaspat» — в зависимости от версии системы и настроек клавиатуры.
    Сопоставление не должно от этого зависеть.
    """
    if not text:
        return ''
    text = text.replace('ё', 'е').replace('Ё', 'Е')
    text = unicodedata.normalize('NFD', text)
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    text = unicodedata.normalize('NFC', text).lower()
    text = re.sub(r'[^\w\s.,]', ' ', text, flags=re.UNICODE)
    text = text.replace(',', ' , ')
    return re.sub(r'\s+', ' ', text).strip()


def _tokens(text: str) -> List[str]:
    return [t for t in normalize(text).split() if t and t != ',']


def _trigrams(word: str) -> set:
    w = f'  {word} '
    return {w[i:i + 3] for i in range(len(w) - 2)}


def similarity(a: str, b: str) -> float:
    """Схожесть строк по триграммам, 0..1. Устойчива к окончаниям и опечаткам ASR."""
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return 2.0 * len(ta & tb) / (len(ta) + len(tb))


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def words_match(spoken: str, name_word: str) -> bool:
    """
    Совпадает ли слово из фразы со словом из названия товара.

    Одних триграмм мало для русского и румынского: «картошки» и «картофель»
    расходятся уже на пятой букве, а «белого» и «белый» — на четвёртой,
    хотя для человека это очевидно одно и то же. Поэтому к триграммам
    добавлено сравнение по общей основе: четыре и более совпавших символа
    в начале при коротком расхождении считаются совпадением.
    """
    if spoken == name_word:
        return True
    if similarity(spoken, name_word) >= 0.45:
        return True
    pref = _common_prefix(spoken, name_word)
    shortest = min(len(spoken), len(name_word))
    return pref >= 4 and shortest and pref >= 0.55 * shortest


# ==================== Разбор фразы ====================

def detect_intent(text: str, lang: str) -> str:
    norm = normalize(text)
    for intent, words in INTENT_WORDS:
        for w in words.get(lang, ()):  # многословные триггеры проверяются как подстрока
            wn = normalize(w)
            if ' ' in wn:
                if wn in norm:
                    return intent
            elif wn in norm.split():
                return intent
    return 'add' if norm else 'unknown'


def parse_quantity(tokens: Sequence[str], lang: str) -> Tuple[Optional[float], Optional[str], bool, List[str]]:
    """
    Достаёт количество и единицу измерения из сегмента — где бы они ни стояли.

    Возвращает (количество, код единицы, признак «упаковка», оставшиеся слова).

    Позиция числа не фиксирована сознательно: в зале говорят и «два ящика
    помидоров», и «молоко домашнее двенадцать штук», и «огурцы, пять кило».
    Требовать один порядок слов — значит требовать от продавца говорить
    как программист.

    Числительные складываются: «двадцать пять» → 25; сотни умножаются:
    «сто двадцать» → 120.
    """
    words = NUMBER_WORDS.get(lang, {})
    units = UNITS.get(lang, {})
    qty: Optional[float] = None
    unit_code: Optional[str] = None
    is_pack = False
    rest: List[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        cleaned = tok.replace(',', '.')
        is_number = bool(re.fullmatch(r'\d+(\.\d+)?', cleaned)) or tok in words
        if is_number and qty is None or (is_number and unit_code is None and qty is not None
                                         and i > 0 and _was_number(tokens[i - 1], words)):
            val = float(cleaned) if re.fullmatch(r'\d+(\.\d+)?', cleaned) else float(words[tok])
            if qty is not None and val >= 100:
                qty *= val
            else:
                qty = (qty or 0) + val
            i += 1
            # Единица измерения — сразу за числом
            if i < len(tokens) and tokens[i] in units and unit_code is None:
                unit_code, is_pack = units[tokens[i]]
                i += 1
            continue
        # Единица без числа («закажи ящик томатов») — количество 1
        if tok in units and unit_code is None and qty is None:
            unit_code, is_pack = units[tok]
            qty = 1.0
            i += 1
            continue
        rest.append(tok)
        i += 1
    return qty, unit_code, is_pack, rest


def _was_number(token: str, words: Dict[str, float]) -> bool:
    return bool(re.fullmatch(r'\d+(\.\d+)?', token.replace(',', '.'))) or token in words


def split_segments(text: str, lang: str) -> List[str]:
    norm = normalize(text)
    parts = [norm]
    for sep in SPLIT_WORDS.get(lang, ()):
        nxt: List[str] = []
        for p in parts:
            nxt.extend(p.split(sep))
        parts = nxt
    out: List[str] = []
    for p in parts:
        out.extend(x.strip() for x in p.split(','))
    return [p for p in out if p.strip()]


def strip_intent_words(segment: str, lang: str) -> str:
    """Убирает команду из сегмента, чтобы она не мешала сопоставлению товара."""
    tokens = segment.split()
    triggers = set()
    for _, words in INTENT_WORDS:
        for w in words.get(lang, ()):
            triggers.update(normalize(w).split())
    while tokens and tokens[0] in triggers:
        tokens.pop(0)
    return ' '.join(tokens)


# ==================== Сопоставление товара ====================

class ProductMatcher:
    """
    Ищет товар по фразе из зала.

    Кандидаты — названия SKU на трёх языках плюс речевые синонимы
    (PLG_VOICE_SYNONYMS). Оценка складывается из доли совпавших слов
    и триграммной схожести: первое ловит «молоко домашнее» → «Молоко
    домашнее 3.2%», второе — оговорки и падежи.
    """

    def __init__(self, products: Sequence[Dict[str, Any]],
                 synonyms: Optional[Sequence[Dict[str, Any]]] = None,
                 lang: str = 'ru'):
        self.lang = lang
        self.products = list(products)
        self.index: List[Tuple[Dict[str, Any], str, List[str], float]] = []
        for p in self.products:
            for key in ('name_ru', 'name_ro', 'name_en', 'name'):
                name = p.get(key)
                if not name:
                    continue
                norm = normalize(str(name))
                self.index.append((p, norm, norm.split(), 1.0))
            if p.get('barcode'):
                self.index.append((p, str(p['barcode']), [str(p['barcode'])], 1.0))
        # Синоним категории повышает шанс её товаров, но сам по себе слабее названия
        self.category_hints: Dict[int, List[str]] = {}
        for s in (synonyms or []):
            phrase = normalize(str(s.get('phrase') or ''))
            if not phrase:
                continue
            if s.get('product_id'):
                for p in self.products:
                    if p.get('id') == s['product_id']:
                        self.index.append((p, phrase, phrase.split(), float(s.get('weight') or 1)))
            elif s.get('category_id'):
                self.category_hints.setdefault(int(s['category_id']), []).append(phrase)

    def match(self, phrase: str) -> Tuple[Optional[Dict[str, Any]], float, List[Dict[str, Any]]]:
        words = [w for w in normalize(phrase).split()
                 if w not in STOP_WORDS.get(self.lang, set())]
        if not words:
            return None, 0.0, []
        scored: Dict[int, Tuple[float, Dict[str, Any]]] = {}
        for product, norm_name, name_words, weight in self.index:
            overlap = sum(1 for w in words if any(words_match(w, nw) for nw in name_words))
            cover = overlap / len(words)
            sim = similarity(' '.join(words), norm_name)
            score = (0.65 * cover + 0.35 * sim) * 100 * weight
            pid = product.get('id')
            if pid is None:
                continue
            if pid not in scored or score > scored[pid][0]:
                scored[pid] = (score, product)

        # Подсказка категории: если во фразе прозвучало «молочка», товары
        # молочной категории получают надбавку — но не выигрывают сами по себе
        for cat_id, phrases in self.category_hints.items():
            if not any(any(similarity(w, ph) > 0.75 for w in words) for ph in phrases):
                continue
            for pid, (score, product) in list(scored.items()):
                if product.get('category_id') == cat_id:
                    scored[pid] = (min(100.0, score * 1.15), product)

        ranked = sorted(scored.values(), key=lambda x: -x[0])[:5]
        if not ranked:
            return None, 0.0, []
        best_score, best = ranked[0]
        options = [{'id': p.get('id'), 'name': p.get('name') or p.get('name_ru'),
                    'score': round(s, 1)} for s, p in ranked]
        # Две почти равные позиции — не угадываем, а показываем выбор
        if len(ranked) > 1 and ranked[1][0] > best_score * 0.92:
            return best, min(best_score, MATCH_AMBIGUOUS + 0.1), options
        return best, best_score, options


# ==================== Основной вход ====================

def parse_order(text: str, lang: str, matcher: ProductMatcher) -> Dict[str, Any]:
    """
    Фраза → намерение и позиции заказа.

    Позиции без количества получают 1 — так говорят в зале («добавь молоко»),
    и уточнить одну цифру дешевле, чем не понять команду целиком.
    """
    lang = lang if lang in NUMBER_WORDS else 'ru'
    intent = detect_intent(text, lang)
    items: List[Dict[str, Any]] = []

    if intent in ('submit', 'cancel', 'query'):
        return {'intent': intent, 'items': [], 'text': text, 'lang': lang,
                'confidence': 100.0, 'matched': 0, 'unmatched': 0}

    for segment in split_segments(text, lang):
        seg = strip_intent_words(segment, lang)
        tokens = seg.split()
        if not tokens:
            continue
        qty, unit, is_pack, rest_tokens = parse_quantity(tokens, lang)
        rest = ' '.join(rest_tokens).strip()
        if not rest:
            # «два ящика» без товара — количество без предмета, пропускаем:
            # додумывать, к чему оно относилось, нельзя
            continue
        product, score, options = matcher.match(rest)
        status = 'ok' if score >= MATCH_OK else ('ambiguous' if score >= MATCH_AMBIGUOUS else 'unmatched')
        item: Dict[str, Any] = {
            'qty': float(qty) if qty is not None else 1.0,
            'unit': unit or 'pcs',
            'is_pack': bool(is_pack),
            'source_text': segment.strip(),
            'confidence': round(min(100.0, score), 1),
            'status': status,
            'options': options if status != 'ok' else [],
        }
        if product and status != 'unmatched':
            item['product_id'] = product.get('id')
            item['match_name'] = product.get('name') or product.get('name_ru')
            pack_size = float(product.get('order_multiple') or 1)
            if is_pack and pack_size > 1:
                item['pack_qty'] = pack_size
                item['qty'] = item['qty'] * pack_size
            item['uom'] = unit or product.get('uom') or 'pcs'
        else:
            item['match_name'] = None
            item['uom'] = unit or 'pcs'
        items.append(item)

    matched = sum(1 for i in items if i['status'] == 'ok')
    unmatched = sum(1 for i in items if i['status'] != 'ok')
    conf = round(sum(i['confidence'] for i in items) / len(items), 1) if items else 0.0
    return {'intent': intent if items else ('unknown' if intent == 'add' else intent),
            'items': items, 'text': text, 'lang': lang,
            'confidence': conf, 'matched': matched, 'unmatched': unmatched}
