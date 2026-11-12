import re
import unicodedata
from collections.abc import Iterator

# Дозволяє букви (включно з українськими ї, і, є, ґ), цифри, а також апострофи,
# підкреслення та дефіси всередині слів.
_TOKEN_PATTERN = re.compile(r"[a-zа-яіїєґ0-9]+(?:['’_-][a-zа-яіїєґ0-9]+)*")


def tokenize(text: str) -> Iterator[str]:
    """Потоковий генератор токенів із тексту:

    1. Нормалізує Unicode (NFC).
    2. Переводить у нижній регістр.
    3. Знаходить слова регулярним виразом.
    """
    if not text:
        return

    normalized_text = unicodedata.normalize("NFC", text).lower()
    for match in _TOKEN_PATTERN.finditer(normalized_text):
        yield match.group()
