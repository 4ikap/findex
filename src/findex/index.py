import argparse
import json
import logging
import pickle
import tracemalloc
from collections import defaultdict
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Callable, Dict, Iterator, List

# Імпортуємо готові інструменти з нашого проєкту
from findex.core import iter_documents
from findex.tokenize import tokenize
from findex.utils import timed


@dataclass(frozen=True, slots=True)
class Posting:
    doc_id: str  # Ідентифікатор документа
    freq: int
    # ЛАБ 3: позиції терміна в документі (номери токенів).
    # Заповнюються лише якщо індекс збудовано з прапорцем --positions.
    positions: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class DocMeta:
    doc_id: str
    length: int


class Index(Mapping):
    """Інвертований індекс як Python-об'єкт.

    Наслідує collections.abc.Mapping: len(index), term in index, index[term],
    for term in index, index.get(term), index.items() працюють «з коробки».
    """

    def __init__(
        self,
        postings: Dict[str, List[Posting]],
        meta: Dict[str, DocMeta],
        has_positions: bool = False,
    ):
        self._postings = postings
        self._meta = meta
        self.has_positions = has_positions
        self._closed = False
        self._on_close: List[Callable[[], None]] = []

    # --- Протокол Mapping ---

    def __getitem__(self, term: str) -> List[Posting]:
        return self._postings[term]

    def __iter__(self) -> Iterator[str]:
        return iter(self._postings)

    def __len__(self) -> int:
        return len(self._postings)

    def __contains__(self, term: object) -> bool:
        return term in self._postings

    def __repr__(self) -> str:
        return (
            f"Index(terms={len(self)}, docs={self.num_docs}, "
            f"avg_doc_length={self.avg_doc_length:.1f}, "
            f"positions={self.has_positions}, closed={self._closed})"
        )

    # --- Властивості ---

    @property
    def meta(self) -> Dict[str, DocMeta]:
        return self._meta

    @property
    def num_docs(self) -> int:
        return len(self._meta)

    @cached_property
    def avg_doc_length(self) -> float:
        """Середня довжина документа (рахується один раз і кешується)."""
        if not self._meta:
            return 0.0
        return sum(m.length for m in self._meta.values()) / len(self._meta)

    def df(self, term: str) -> int:
        """Document frequency: у скількох документах трапляється термін."""
        return len(self._postings.get(term, ()))

    def doc_length(self, doc_id: str) -> int:
        return self._meta[doc_id].length

    # --- Керування ресурсами ---

    @property
    def closed(self) -> bool:
        return self._closed

    def on_close(self, callback: Callable[[], None]) -> None:
        """Реєструє функцію, яку буде викликано при close() (наприклад, очищення кешу)."""
        self._on_close.append(callback)

    def close(self) -> None:
        """Звільняє ресурси: викликає колбеки, очищає словники та кеш."""
        if self._closed:
            return
        self._closed = True
        try:
            for callback in self._on_close:
                callback()
        finally:
            self._on_close.clear()
            self._postings = {}
            self._meta = {}
            self.__dict__.pop("avg_doc_length", None)

    # --- Серіалізація ---

    def save(self, path: str | Path, fmt: str = "pickle") -> None:
        path = Path(path)
        if fmt == "json":
            data = {
                "has_positions": self.has_positions,
                "index": {
                    term: [
                        {"doc_id": p.doc_id, "freq": p.freq, "positions": list(p.positions)}
                        for p in postings
                    ]
                    for term, postings in self._postings.items()
                },
                "meta": {
                    doc_id: {"doc_id": m.doc_id, "length": m.length}
                    for doc_id, m in self._meta.items()
                },
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        elif fmt == "pickle":
            # Зберігаємо ПРОСТІ дані (кортежі, словники), а не об'єкти Posting/DocMeta:
            # інакше pickle запам'ятає клас як __main__.Posting (якщо індекс будували
            # через python -m findex.index) і файл не завантажиться з іншого модуля.
            data = {
                "has_positions": self.has_positions,
                "index": {
                    term: [(p.doc_id, p.freq, p.positions) for p in postings]
                    for term, postings in self._postings.items()
                },
                "meta": {doc_id: m.length for doc_id, m in self._meta.items()},
            }
            with open(path, "wb") as f:
                pickle.dump(data, f)
        else:
            raise ValueError(f"Невідомий формат: {fmt!r}")

    @classmethod
    @timed
    def load(cls, path: str | Path, fmt: str | None = None) -> "Index":
        path = Path(path)
        if fmt is None:
            fmt = "json" if path.suffix == ".json" else "pickle"

        if fmt == "json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            postings = {
                term: [
                    Posting(
                        doc_id=item["doc_id"],
                        freq=item["freq"],
                        positions=tuple(item.get("positions", ())),
                    )
                    for item in items
                ]
                for term, items in data["index"].items()
            }
            meta = {
                doc_id: DocMeta(doc_id=m["doc_id"], length=m["length"])
                for doc_id, m in data["meta"].items()
            }
        elif fmt == "pickle":
            with open(path, "rb") as f:
                data = pickle.load(f)
            postings = {
                term: [Posting(doc_id, freq, positions) for doc_id, freq, positions in items]
                for term, items in data["index"].items()
            }
            meta = {doc_id: DocMeta(doc_id, length) for doc_id, length in data["meta"].items()}
        else:
            raise ValueError(f"Невідомий формат: {fmt!r}")

        return cls(postings, meta, has_positions=data.get("has_positions", False))


@contextmanager
def open_index(path: str | Path, fmt: str | None = None):
    """Context manager: завантажує індекс і гарантовано закриває його,
    навіть якщо всередині with виникло виняток.

        with open_index("index.bin") as index:
            ...
    """
    index = Index.load(path, fmt)
    try:
        yield index
    finally:
        index.close()


@timed
def build_inverted_index(data_dir: str | Path, positions: bool = False) -> Index:
    """
    Будує інвертований індекс та метадані документів одним проходом
    по лінивому пайплайну (core + tokenize).

    positions=True — додатково зберігає позиції термінів (потрібно для фраз "...").
    """
    raw_index = defaultdict(dict)  # term -> {doc_id: freq або список позицій}
    doc_meta: Dict[str, DocMeta] = {}

    # Один прохід по всіх документах корпусу
    for doc_id, text in iter_documents(data_dir):
        token_count = 0
        term_positions = defaultdict(list)

        # Рахуємо позиції термінів усередині поточного документа
        for token in tokenize(text):
            term_positions[token].append(token_count)
            token_count += 1

        # Зберігаємо довжину документа в метаданих
        doc_meta[doc_id] = DocMeta(doc_id=doc_id, length=token_count)

        # Додаємо дані в загальний сирий індекс
        for term, pos_list in term_positions.items():
            raw_index[term][doc_id] = pos_list if positions else len(pos_list)

    # Фіналізація індексу: конвертуємо у відсортовані за doc_id списки Posting
    postings: Dict[str, List[Posting]] = {}
    for term, docs in raw_index.items():
        if positions:
            postings[term] = [
                Posting(doc_id=d_id, freq=len(pl), positions=tuple(pl))
                for d_id, pl in sorted(docs.items())
            ]
        else:
            postings[term] = [
                Posting(doc_id=d_id, freq=f)
                for d_id, f in sorted(docs.items())
            ]

    return Index(postings, doc_meta, has_positions=positions)


# --- УВАГА БЕЗПЕКИ PICKLE ---
# Завантаження файлів pickle (`pickle.load`) з ненадійних джерел є критично небезпечним,
# оскільки під час десеріалізації бібліотека може виконати довільний код (RCE),
# закладений злочинцем у байт-коді. Використовувати pickle виключно для власних локальних файлів.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Findex Builder CLI")
    parser.add_argument("data_dir", type=Path, help="Шлях до папки з корпусом даних (наприклад, data/)")
    parser.add_argument("--out", type=Path, default=Path("index.bin"), help="Шлях до вихідного файлу індексу")
    parser.add_argument("--format", choices=["pickle", "json"], default="pickle", help="Формат збереження індексу")
    parser.add_argument("--positions", action="store_true", help="Зберігати позиції термінів (потрібно для пошуку фраз)")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Заміри пам'яті через tracemalloc
    tracemalloc.start()

    print(f"Будуємо індекс із корпусу в: {args.data_dir}")
    index = build_inverted_index(args.data_dir, positions=args.positions)
    print(f"Успішно побудовано! {index}")

    print(f"Зберігаємо індекс у {args.out} у форматі [{args.format}]...")
    index.save(args.out, args.format)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Індекс успішно збережено!")
    print(f"Пік споживання пам'яті: {peak / 1024 / 1024:.2f} MB")



#python -m findex.index data --out index.bin --positions     побудова індексу з позиціями (потрібно для фраз) і збереження у index.bin

#python -m findex.index data --out index.json --format json --positions     зберегти індекс у форматі JSON
