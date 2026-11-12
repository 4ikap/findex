import time
import tracemalloc
from collections import Counter
from pathlib import Path

from findex.core import iter_documents
from findex.tokenize import tokenize


def collect_corpus_statistics_greedy(data_dir: str | Path) -> None:
    """«Жадібна» (List-based) версія статистики (Лаб 1).

    Завантажує весь корпус і всі токени у великі списки в пам'яті. Результат —
    звіт у stdout.
    """
    tracemalloc.start()
    start_time = time.time()

    all_documents = list(iter_documents(Path(data_dir)))

    all_tokens: list[str] = []
    for _doc_id, text in all_documents:
        all_tokens.extend(tokenize(text))

    term_counter = Counter(all_tokens)

    execution_time = time.time() - start_time
    _current, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("=" * 50)
    print(" СТАТИСТИКА КОРПУСУ (Жадібний / List-based підхід)")
    print("=" * 50)
    print(f"Загальна кількість документів: {len(all_documents):,}")
    print(f"Загальна кількість токенів:   {len(all_tokens):,}")
    print(f"Розмір словника (унікальних): {len(term_counter):,}")
    print(f"Час виконання:                {execution_time:.2f} секунд")
    print(f"Пікова пам'ять (Peak RAM):    {peak_memory / (1024 * 1024):.2f} МБ")
    print("=" * 50)


if __name__ == "__main__":
    collect_corpus_statistics_greedy(Path(__file__).resolve().parent.parent.parent / "data")
