import re
import unicodedata
from typing import Generator


def tokenize(text: str) -> Generator[str, None, None]:
    """Потоковий генератор токенів із тексту:

    1. Нормалізує Unicode (NFC).
    2. Переводить у нижній регістр.
    3. Знаходить слова за допомогою регулярного виразу
       (з підтримкою українських та латинських літер, апострофів і дефісів).
    """
    if not text:
        return

    # 1. Unicode-нормалізація (NFC) та нижній регістр
    normalized_text = unicodedata.normalize("NFC", text).lower()

    # 2. Регулярний вираз для пошуку слів
    # Дозволяє букви (включно з українськими ї, і, є, ґ), цифри,
    # а також апострофи та дефіси всередині слів
    token_pattern = re.compile(
        r"[a-zа-яіїєґ0-9]+(?:['’_-][a-zа-яіїєґ0-9]+)*", re.UNICODE
    )

    # 3. Потокове повернення токенів через генератор
    for match in token_pattern.finditer(normalized_text):
        yield match.group()


if __name__ == "__main__":
  # Швидка перевірка токенізатора
  sample_text = (
      "Привіт, світ! Це тестовий речення №1 із м'яким знаком та дефіс-словом"
      " будь-що."
  )
  print(f"Оригінал: {sample_text}\n")
  print("Згенеровані токени:")
  for token in tokenize(sample_text):
    print(f"  -> {token}")