import time
import tracemalloc
from collections import Counter
from pathlib import Path

from findex.core import iter_documents
from findex.tokenize import tokenize


def collect_corpus_statistics(data_dir: str | Path) -> None:
    """Збирає статистику корпусу за один прохід у потоковому режимі (Лаб 1):

    кількість документів і токенів, розмір словника, топ-50 термів, час і
    пікова пам'ять (tracemalloc). Результат — звіт у stdout.
    """
    tracemalloc.start()
    start_time = time.time()

    total_documents = 0
    total_tokens = 0
    term_counter: Counter[str] = Counter()

    for _doc_id, text in iter_documents(Path(data_dir)):
        total_documents += 1
        for token in tokenize(text):
            total_tokens += 1
            term_counter[token] += 1

    execution_time = time.time() - start_time
    _current, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("=" * 50)
    print(" СТАТИСТИКА КОРПУСУ (Потоковий / Лінивий підхід)")
    print("=" * 50)
    print(f"Загальна кількість документів: {total_documents:,}")
    print(f"Загальна кількість токенів:   {total_tokens:,}")
    print(f"Розмір словника (унікальних): {len(term_counter):,}")
    print(f"Час виконання:                {execution_time:.2f} секунд")
    print(f"Пікова пам'ять (Peak RAM):    {peak_memory / (1024 * 1024):.2f} МБ")
    print("=" * 50)

    print("\nТоп-50 найчастіших слів:")
    for word, freq in term_counter.most_common(50):
        print(f"  {word}: {freq:,}")


if __name__ == "__main__":
    collect_corpus_statistics(Path(__file__).resolve().parent.parent.parent / "data")
