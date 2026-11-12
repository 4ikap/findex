import heapq
import logging
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from findex.core import read_document
from findex.index import Index, Posting
from findex.query import parse_query
from findex.scoring import BM25, Scorer
from findex.snippets import best_snippet
from findex.utils import timed

log = logging.getLogger("findex")

# ============================================================
# Лаб 2 (залишено): булеві движки merge / set для запитів "термін ОПЕРАТОР термін".
# Працюють і з Index, бо він підтримує index.get(term, []).
# ============================================================

# --- Движок 1: Two-Pointer Merge ---


def merge_intersect(p1: list[Posting], p2: list[Posting]) -> list[Posting]:
    result: list[Posting] = []
    i, j = 0, 0
    while i < len(p1) and j < len(p2):
        if p1[i].doc_id == p2[j].doc_id:
            result.append(p1[i])
            i += 1
            j += 1
        elif p1[i].doc_id < p2[j].doc_id:
            i += 1
        else:
            j += 1
    return result


def merge_union(p1: list[Posting], p2: list[Posting]) -> list[Posting]:
    result: list[Posting] = []
    i, j = 0, 0
    while i < len(p1) and j < len(p2):
        if p1[i].doc_id == p2[j].doc_id:
            result.append(p1[i])
            i += 1
            j += 1
        elif p1[i].doc_id < p2[j].doc_id:
            result.append(p1[i])
            i += 1
        else:
            result.append(p2[j])
            j += 1
    result.extend(p1[i:])
    result.extend(p2[j:])
    return result


def merge_not(p1: list[Posting], p2: list[Posting]) -> list[Posting]:
    exclude = {p.doc_id for p in p2}
    return [p for p in p1 if p.doc_id not in exclude]


# --- Движок 2: Python Set ---


def set_intersect(p1: list[Posting], p2: list[Posting]) -> set[str]:
    return {p.doc_id for p in p1}.intersection(p.doc_id for p in p2)


def set_union(p1: list[Posting], p2: list[Posting]) -> set[str]:
    return {p.doc_id for p in p1}.union(p.doc_id for p in p2)


def set_not(p1: list[Posting], p2: list[Posting]) -> set[str]:
    return {p.doc_id for p in p1}.difference(p.doc_id for p in p2)


def execute_query(
    query: str,
    index: Mapping[str, list[Posting]],
    engine: Literal["merge", "set"] = "merge",
) -> set[str]:
    """Простий булевий запит «термін [AND|OR|NOT термін]» (Лаб 2).

    Завжди повертає множину doc_id. Для складних запитів із дужками та фразами
    використовуйте SearchEngine.
    """
    parts = query.strip().split()
    if not parts:
        return set()

    postings1 = index.get(parts[0].lower(), [])
    if len(parts) == 1:
        return {p.doc_id for p in postings1}

    op = parts[1].upper()
    postings2 = index.get(parts[2].lower(), []) if len(parts) > 2 else []

    if engine == "merge":
        if op == "AND":
            return {p.doc_id for p in merge_intersect(postings1, postings2)}
        if op == "OR":
            return {p.doc_id for p in merge_union(postings1, postings2)}
        if op == "NOT":
            return {p.doc_id for p in merge_not(postings1, postings2)}
        return {p.doc_id for p in postings1}

    if op == "AND":
        return set_intersect(postings1, postings2)
    if op == "OR":
        return set_union(postings1, postings2)
    if op == "NOT":
        return set_not(postings1, postings2)
    return {p.doc_id for p in postings1}


# ============================================================
# Лаб 3: ранжований пошук
# ============================================================


@dataclass(frozen=True, order=True)
class SearchResult:
    """Результат пошуку. order=True: порівнюється за score (doc_id не бере участі)."""

    score: float
    doc_id: str = field(compare=False)


class SearchEngine:
    """Ранжований пошук: парсить запит, знаходить документи, рахує бали Scorer-ом."""

    def __init__(self, index: Index, scorer: Scorer | None = None, cache_size: int = 128) -> None:
        self.index = index
        self.scorer: Scorer = scorer or BM25()
        # lru_cache: рядок запиту -> (множина doc_id, терміни для рейтингу)
        self._cached_match = lru_cache(maxsize=cache_size)(self._match)
        # коли індекс закривається, кеш очищається
        index.on_close(self._cached_match.cache_clear)

    def _match(self, query: str) -> tuple[frozenset[str], tuple[str, ...]]:
        tree = parse_query(query)
        log.debug("Розібраний запит: %r", tree)
        ids = frozenset(tree.evaluate(self.index))
        terms = tuple(dict.fromkeys(tree.terms()))  # унікальні, зі збереженням порядку
        return ids, terms

    def matching(self, query: str) -> tuple[frozenset[str], tuple[str, ...]]:
        """Обгортка над кешем, яка пише в лог cache HIT / MISS."""
        hits_before = self._cached_match.cache_info().hits
        result = self._cached_match(query)
        if self._cached_match.cache_info().hits > hits_before:
            log.info("[cache] HIT  %r", query)
        else:
            log.info("[cache] MISS %r", query)
        return result

    @timed
    def search(self, query: str, k: int = 10) -> list[SearchResult]:
        ids, terms = self.matching(query)

        # накопичуємо бали по всіх термінах запиту
        scores: defaultdict[str, float] = defaultdict(float)
        for term in terms:
            df = self.index.df(term)
            for posting in self.index.get(term, ()):
                if posting.doc_id in ids:
                    scores[posting.doc_id] += self.scorer.score(
                        posting.freq, df, self.index.doc_length(posting.doc_id), self.index
                    )

        # sorted() — щоб при однакових балах порядок був детермінованим
        candidates = sorted(scores) if scores else sorted(ids)
        results = (SearchResult(scores.get(doc_id, 0.0), doc_id) for doc_id in candidates)
        return heapq.nlargest(k, results)


@dataclass(frozen=True)
class Hit:
    """Рядок видачі: позиція, бал, документ і (необов'язково) сніпет."""

    rank: int
    score: float
    doc_id: str
    snippet: str | None = None


def run_query(
    engine: SearchEngine,
    query: str,
    k: int,
    data_dir: Path | None = None,
    mark: tuple[str, str] = ("**", "**"),
) -> list[Hit]:
    """Виконує запит і (якщо задано data_dir) додає до результатів сніпети."""
    results = engine.search(query, k)
    terms = parse_query(query).terms()
    hits: list[Hit] = []
    for rank, result in enumerate(results, 1):
        snippet: str | None = None
        if data_dir is not None:
            snippet = best_snippet(read_document(data_dir, result.doc_id), terms, mark=mark)
        hits.append(Hit(rank, result.score, result.doc_id, snippet))
    return hits
