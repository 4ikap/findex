import inspect
import unicodedata

import pytest

from findex.tokenize import tokenize


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Привіт, Світ! Це тест.", ["привіт", "світ", "це", "тест"]),
        (
            "Пам'ять, об'єкт та будь-що працюють добре.",
            ["пам'ять", "об'єкт", "та", "будь-що", "працюють", "добре"],
        ),
        ("п’ятниця й П’ЯТНИЦЯ", ["п’ятниця", "й", "п’ятниця"]),
        ("Блок №1 містить 100 елементів.", ["блок", "1", "містить", "100", "елементів"]),
        ("ЇЖАК Ґанок Європа", ["їжак", "ґанок", "європа"]),
        ("Hello, WORLD! python3", ["hello", "world", "python3"]),
        ("дощ 🌧 ніч", ["дощ", "ніч"]),
        ("snake_case і kebab-case", ["snake_case", "і", "kebab-case"]),
        ("будь- що", ["будь", "що"]),
        ("   \t\n ", []),
        ("!!! ... ???", []),
        ("", []),
    ],
)
def test_tokenize_cases(text: str, expected: list[str]) -> None:
    assert list(tokenize(text)) == expected


def test_tokenize_nfd_equals_nfc() -> None:
    """«й» у розкладеному вигляді (NFD) дає той самий токен, що й у NFC."""
    composed = "Йшов дощ"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    assert list(tokenize(decomposed)) == list(tokenize(composed)) == ["йшов", "дощ"]


def test_tokenize_is_lazy_generator() -> None:
    assert inspect.isgenerator(tokenize("a b c"))
    iterator = tokenize("один два три")
    assert next(iterator) == "один"
    assert next(iterator) == "два"


def test_tokenize_none_gives_nothing() -> None:
    assert list(tokenize(None)) == []  # type: ignore[arg-type]  # перевіряємо стійкість до None
