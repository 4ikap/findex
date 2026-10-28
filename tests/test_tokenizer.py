import unittest
# Імпортуємо нашу функцію tokenize з пакету findex

from findex.tokenize import tokenize


class TestTokenizer(unittest.TestCase):

  def test_basic_tokenization(self):
    """Перевірка переведення в нижній регістр та видалення розділових знаків."""
    text = "Привіт, Світ! Це тест."
    expected = ["привіт", "світ", "це", "тест"]
    self.assertEqual(list(tokenize(text)), expected)

  def test_apostrophe_and_hyphen(self):
    """Перевірка збереження українських апострофів та дефісів."""
    text = "Пам'ять, об'єкт та будь-що працюють добре."
    expected = ["пам'ять", "об'єкт", "та", "будь-що", "працюють", "добре"]
    self.assertEqual(list(tokenize(text)), expected)

  def test_numbers(self):
    """Перевірка обробки цифр."""
    text = "Блок №1 містить 100 елементів."
    expected = ["блок", "1", "містить", "100", "елементів"]
    self.assertEqual(list(tokenize(text)), expected)

  def test_empty_input(self):
    """Перевірка поведінки на пустому рядку."""
    self.assertEqual(list(tokenize("")), [])
    self.assertEqual(list(tokenize(None)), [])  # type: ignore


if __name__ == "__main__":
  unittest.main()