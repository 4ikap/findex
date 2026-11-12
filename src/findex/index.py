import json
import logging
import pickle
from collections import defaultdict
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

from findex.core import iter_documents
from findex.errors import FindexError, IndexLoadError
from findex.tokenize import tokenize
from findex.utils import timed

log = logging.getLogger("findex.index")

IndexFormat = Literal["pickle", "json"]


@dataclass(frozen=True, slots=True)
class Posting:
    doc_id: str  # Ідентифікатор документа
    freq: int
    # Позиції терміна в документі (номери токенів). Заповнюються лише якщо
    # індекс збудовано з прапорцем positions=True.
    positions: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class DocMeta:
    doc_id: str
    length: int


class Index(Mapping[str, list[Posting]]):
    """Інвертований індекс як Python-об'єкт.

    Наслідує collections.abc.Mapping: len(index), term in index, index[term],
    for term in index, index.get(term), index.items() працюють «з коробки».
    """

    def __init__(
        self,
        postings: dict[str, list[Posting]],
        meta: dict[str, DocMeta],
        has_positions: bool = False,
    ) -> None:
        self._postings = postings
        self._meta = meta
        self.has_positions = has_positions
        self._closed = False
        self._on_close: list[Callable[[], None]] = []

    # --- Протокол Mapping ---

    def __getitem__(self, term: str) -> list[Posting]:
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
    def meta(self) -> dict[str, DocMeta]:
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

    def save(self, path: str | Path, fmt: IndexFormat = "pickle") -> None:
        file_path = Path(path)
        if fmt == "json":
            payload: dict[str, Any] = {
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
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        elif fmt == "pickle":
            # Зберігаємо ПРОСТІ дані (кортежі, словники), а не об'єкти Posting/DocMeta:
            # інакше pickle запам'ятає клас як __main__.Posting і файл не завантажиться
            # з іншого модуля.
            data: dict[str, Any] = {
                "has_positions": self.has_positions,
                "index": {
                    term: [(p.doc_id, p.freq, p.positions) for p in postings]
                    for term, postings in self._postings.items()
                },
                "meta": {doc_id: m.length for doc_id, m in self._meta.items()},
            }
            with file_path.open("wb") as f:
                pickle.dump(data, f)
        else:
            raise FindexError(f"Невідомий формат індексу: {fmt!r}")


@timed
def load_index(path: str | Path, fmt: IndexFormat | None = None) -> Index:
    """Завантажує індекс із файлу. Формат за замовчуванням — за розширенням."""
    file_path = Path(path)
    if fmt is None:
        fmt = "json" if file_path.suffix == ".json" else "pickle"

    try:
        data: dict[str, Any]
        if fmt == "json":
            with file_path.open("r", encoding="utf-8") as f:
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
            with file_path.open("rb") as f:
                data = pickle.load(f)
            postings = {
                term: [Posting(doc_id, freq, tuple(pos)) for doc_id, freq, pos in items]
                for term, items in data["index"].items()
            }
            meta = {doc_id: DocMeta(doc_id, length) for doc_id, length in data["meta"].items()}
        else:
            raise FindexError(f"Невідомий формат індексу: {fmt!r}")
    except (
        pickle.UnpicklingError,
        EOFError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ImportError,
        IndexError,
    ) as exc:
        raise IndexLoadError(f"Файл індексу {file_path} пошкоджений: {exc}") from exc

    return Index(postings, meta, has_positions=bool(data.get("has_positions", False)))


@contextmanager
def open_index(
    path: str | Path, fmt: IndexFormat | None = None
) -> Generator[Index, None, None]:
    """Context manager: завантажує індекс і гарантовано закриває його,
    навіть якщо всередині with виникло виняток.

        with open_index("index.bin") as index:
            ...
    """
    index = load_index(path, fmt)
    try:
        yield index
    finally:
        index.close()


def build_index(documents: Iterable[tuple[str, str]], positions: bool = False) -> Index:
    """Будує інвертований індекс і метадані за один прохід по потоку документів.

    positions=True — додатково зберігає позиції термінів (потрібно для фраз "...").
    Документ із вже відомим doc_id пропускається (з попередженням у лог).
    """
    freq_index: defaultdict[str, dict[str, int]] = defaultdict(dict)
    pos_index: defaultdict[str, dict[str, tuple[int, ...]]] = defaultdict(dict)
    doc_meta: dict[str, DocMeta] = {}

    for doc_id, text in documents:
        if doc_id in doc_meta:
            log.warning("Дублікат doc_id %s пропущено", doc_id)
            continue

        token_count = 0
        term_positions: defaultdict[str, list[int]] = defaultdict(list)
        for token in tokenize(text):
            term_positions[token].append(token_count)
            token_count += 1

        doc_meta[doc_id] = DocMeta(doc_id=doc_id, length=token_count)

        for term, pos_list in term_positions.items():
            if positions:
                pos_index[term][doc_id] = tuple(pos_list)
            else:
                freq_index[term][doc_id] = len(pos_list)

    # Фіналізація: відсортовані за doc_id списки Posting
    postings: dict[str, list[Posting]] = {}
    if positions:
        for term, pos_docs in pos_index.items():
            postings[term] = [
                Posting(doc_id=d_id, freq=len(pl), positions=pl)
                for d_id, pl in sorted(pos_docs.items())
            ]
    else:
        for term, freq_docs in freq_index.items():
            postings[term] = [Posting(doc_id=d_id, freq=f) for d_id, f in sorted(freq_docs.items())]

    return Index(postings, doc_meta, has_positions=positions)


@timed
def build_inverted_index(
    data_dir: str | Path,
    positions: bool = False,
    on_bytes: Callable[[int], None] | None = None,
) -> Index:
    """Будує індекс із корпусу .bz2 (лінивий пайплайн core + tokenize).

    on_bytes — колбек прогресу (скільки стиснутих байтів прочитано).
    """
    index = build_index(iter_documents(data_dir, on_bytes), positions=positions)
    log.info("Індекс збудовано: %r", index)
    return index
