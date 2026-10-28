from collections import Counter
from pathlib import Path
import time
import tracemalloc
from findex.core import iter_documents
from findex.tokenize import tokenize


def collect_corpus_statistics_greedy(data_dir: str | Path):
  """«Жадібна» (List-based) версія:

  Збирає всю статистику, завантажуючи весь корпус і токени у великі списки в
  пам'яті.
  """
  data_path = Path(data_dir)

  tracemalloc.start()
  start_time = time.time()

  # ЖАДІБНИЙ ПІДХІД: збираємо всі документи у звичайний список у пам'яті
  all_documents = list(iter_documents(data_path))

  all_tokens = []
  for doc_id, text in all_documents:
    # Завантажуємо всі токени кожного документа у великий список
    doc_tokens = list(tokenize(text))
    all_tokens.extend(doc_tokens)

  term_counter = Counter(all_tokens)

  end_time = time.time()
  current_memory, peak_memory = tracemalloc.get_traced_memory()
  tracemalloc.stop()

  execution_time = end_time - start_time
  peak_memory_mb = peak_memory / (1024 * 1024)

  print("=" * 50)
  print(" СТАТИСТИКА КОРПУСУ (Жадібний / List-based підхід)")
  print("=" * 50)
  print(f"Загальна кількість документів: {len(all_documents):,}")
  print(f"Загальна кількість токенів:   {len(all_tokens):,}")
  print(f"Розмір словника (унікальних): {len(term_counter):,}")
  print(f"Час виконання:                {execution_time:.2f} секунд")
  print(f"Пікова пам'ять (Peak RAM):    {peak_memory_mb:.2f} МБ")
  print("=" * 50)


if __name__ == "__main__":
  data_path = Path(__file__).resolve().parent.parent.parent / "data"
  collect_corpus_statistics_greedy(data_path)