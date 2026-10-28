from collections import Counter
from pathlib import Path
import time
import tracemalloc

# Імпортуємо наші функції
from findex.core import iter_documents
from findex.tokenize import tokenize


def collect_corpus_statistics(data_dir: str | Path):
  """Збирає статистику корпусу за один прохід у потоковому режимі:

  - Загальна кількість документів
  - Загальна кількість токенів
  - Розмір словника (унікальних термів)
  - Топ-50 найчастіших термів
  - Час виконання та пікова пам'ять (tracemalloc)
  """
  data_path = Path(data_dir)

  # Запускаємо відстеження пам'яті та часу
  tracemalloc.start()
  start_time = time.time()

  total_documents = 0
  total_tokens = 0
  term_counter = Counter()

  # Потокова обробка корпусу (документ за документом)
  for doc_id, text in iter_documents(data_path):
    total_documents += 1

    # Токенізація потоку слів у поточному документі
    for token in tokenize(text):
      total_tokens += 1
      term_counter[token] += 1

  # Зупиняємо заміри
  end_time = time.time()
  current_memory, peak_memory = tracemalloc.get_traced_memory()
  tracemalloc.stop()

  # Формуємо результати
  execution_time = end_time - start_time
  peak_memory_mb = peak_memory / (1024 * 1024)

  print("=" * 50)
  print(" СТАТИСТИКА КОРПУСУ (Потоковий / Лінивий підхід)")
  print("=" * 50)
  print(f"Загальна кількість документів: {total_documents:,}")
  print(f"Загальна кількість токенів:   {total_tokens:,}")
  print(f"Розмір словника (унікальних): {len(term_counter):,}")
  print(f"Час виконання:                {execution_time:.2f} секунд")
  print(f"Пікова пам'ять (Peak RAM):    {peak_memory_mb:.2f} МБ")
  print("=" * 50)

  print("\nТоп-50 найчастіших слів:")
  for word, freq in term_counter.most_common(50):
    print(f"  {word}: {freq:,}")


if __name__ == "__main__":
  # Шлях до папки data відносно розташування цього файлу
  data_path = Path(__file__).resolve().parent.parent.parent / "data"
  collect_corpus_statistics(data_path)