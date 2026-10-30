import argparse
import pickle
import json
import tracemalloc
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple
from pathlib import Path

# Імпортуємо готові інструменти з нашого проєкту
from findex.core import iter_documents
from findex.tokenize import tokenize


@dataclass(frozen=True, slots=True)
class Posting:
    doc_id: str  # Ідентифікатор документа
    freq: int


@dataclass(frozen=True, slots=True)
class DocMeta:
    doc_id: str
    length: int


def build_inverted_index(data_dir: str | Path) -> Tuple[Dict[str, List[Posting]], Dict[str, DocMeta]]:
    """
    Будує інвертований індекс та метадані документів одним проходом
    по лінивому пайплайну (core + tokenize).
    """
    raw_index = defaultdict(lambda: defaultdict(int))
    doc_meta: Dict[str, DocMeta] = {}

    # Один прохід по всіх документах корпусу
    for doc_id, text in iter_documents(data_dir):
        token_count = 0
        term_freqs = defaultdict(int)

        # Рахуємо частоти термінів усередині поточного документа
        for token in tokenize(text):
            term_freqs[token] += 1
            token_count += 1

        # Зберігаємо довжину документа в метаданих
        doc_meta[doc_id] = DocMeta(doc_id=doc_id, length=token_count)

        # Додаємо дані в загальний сирий індекс
        for term, freq in term_freqs.items():
            raw_index[term][doc_id] = freq

    # Фіналізація індексу: конвертуємо у відсортовані за doc_id списки Posting
    index: Dict[str, List[Posting]] = {}
    for term, doc_freqs in raw_index.items():
        sorted_postings = [
            Posting(doc_id=d_id, freq=f)
            for d_id, f in sorted(doc_freqs.items())
        ]
        index[term] = sorted_postings

    return index, doc_meta


# --- Альтернативна серіалізація через JSON ---

def save_index_json(index: Dict[str, List[Posting]], meta: Dict[str, DocMeta], path: Path):
    """Зберігає індекс та метадані у форматі JSON (альтернатива pickle)."""
    serializable_index = {
        term: [{"doc_id": p.doc_id, "freq": p.freq} for p in postings]
        for term, postings in index.items()
    }
    serializable_meta = {
        doc_id: {"doc_id": m.doc_id, "length": m.length}
        for doc_id, m in meta.items()
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"index": serializable_index, "meta": serializable_meta}, f, ensure_ascii=False, indent=2)


def load_index_json(path: Path) -> Tuple[Dict[str, List[Posting]], Dict[str, DocMeta]]:
    """Завантажує індекс та метадані з JSON-файлу."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    index = {
        term: [Posting(doc_id=item["doc_id"], freq=item["freq"]) for item in postings]
        for term, postings in data["index"].items()
    }
    meta = {
        doc_id: DocMeta(doc_id=m["doc_id"], length=m["length"])
        for doc_id, m in data["meta"].items()
    }
    return index, meta


# --- УВАГА БЕЗПЕКИ PICKLE ---
# Завантаження файлів pickle (`pickle.load`) з ненадійних джерел є критично небезпечним,
# оскільки під час десеріалізації бібліотека може виконати довільний код (RCE),
# закладений злочинцем у байт-коді. Використовувати pickle виключно для власних локальних файлів.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Findex Builder CLI")
    parser.add_argument("data_dir", type=Path, help="Шлях до папки з корпусом даних (наприклад, data/)")
    parser.add_argument("--out", type=Path, default=Path("index.bin"), help="Шлях до вихідного файлу індексу")
    parser.add_argument("--format", choices=["pickle", "json"], default="pickle", help="Формат збереження індексу")

    args = parser.parse_args()

    # Заміри пам'яті через tracemalloc
    tracemalloc.start()

    print(f"Будуємо індекс із корпусу в: {args.data_dir}")
    index, meta = build_inverted_index(args.data_dir)
    print(f"Успішно побудовано! Унікальних термінів: {len(index)}, документів: {len(meta)}")

    print(f"Зберігаємо індекс у {args.out} у форматі [{args.format}]...")

    if args.format == "json":
        save_index_json(index, meta, args.out)
    else:
        with open(args.out, "wb") as f:
            pickle.dump({"index": index, "meta": meta}, f)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Індекс успішно збережено!")
    print(f"Пік споживання пам'яті: {peak / 1024 / 1024:.2f} MB")



#python -m findex.index data --out index.bin    команду, яка запустить побудову індексу з вашої папки data і збереже його у файл index.bin (з виведенням піку пам'яті через tracemalloc)

#python -m findex.index data --out index.json --format json     зберегти індекс у форматі JSON