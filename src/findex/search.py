import argparse
import heapq
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Set, Tuple

from findex.core import read_document
from findex.index import Index, Posting, open_index
from findex.query import parse_query
from findex.scoring import BM25, Scorer, TfIdf
from findex.snippets import best_snippet
from findex.utils import timed

log = logging.getLogger("findex")


# ============================================================
# ЛАБ 2 (залишено): булеві движки merge / set для запитів "термін ОПЕРАТОР термін"
# Працюють і з новим Index, бо він підтримує index.get(term, []).
# ============================================================

# --- Движок 1: Two-Pointer Merge ---

def merge_intersect(p1: List[Posting], p2: List[Posting]) -> List[Posting]:
    result = []
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


def merge_union(p1: List[Posting], p2: List[Posting]) -> List[Posting]:
    result = []
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


def merge_not(p1: List[Posting], p2: List[Posting]) -> List[Posting]:
    exclude = {p.doc_id for p in p2}
    return [p for p in p1 if p.doc_id not in exclude]


# --- Движок 2: Python Set ---

def set_intersect(p1: List[Posting], p2: List[Posting]) -> Set[str]:
    return {p.doc_id for p in p1}.intersection(p.doc_id for p in p2)


def set_union(p1: List[Posting], p2: List[Posting]) -> Set[str]:
    return {p.doc_id for p in p1}.union(p.doc_id for p in p2)


def set_not(p1: List[Posting], p2: List[Posting]) -> Set[str]:
    return {p.doc_id for p in p1}.difference(p.doc_id for p in p2)


def execute_query(query: str, index, engine: str = "merge") -> Set[str]:
    """
    Простий парсер та виконавець булевих запитів (підтримує терміни через AND, OR, NOT).
    Приклад запиту: "python AND code", "data NOT test"
    (Лаб 2. Для складних запитів із дужками та фразами — SearchEngine нижче.)
    """
    parts = query.strip().split()
    if not parts:
        return set()

    # Простий розбір по черзі (термін оператор термін)
    term1 = parts[0]
    postings1 = index.get(term1.lower(), [])

    if len(parts) == 1:
        return {p.doc_id for p in postings1} if engine == "set" else postings1

    op = parts[1].upper()
    term2 = parts[2] if len(parts) > 2 else ""
    postings2 = index.get(term2.lower(), []) if term2 else []

    if engine == "merge":
        if op == "AND":
            res = merge_intersect(postings1, postings2)
        elif op == "OR":
            res = merge_union(postings1, postings2)
        elif op == "NOT":
            res = merge_not(postings1, postings2)
        else:
            res = postings1
        return {p.doc_id for p in res}
    else:  # set engine
        if op == "AND":
            return set_intersect(postings1, postings2)
        elif op == "OR":
            return set_union(postings1, postings2)
        elif op == "NOT":
            return set_not(postings1, postings2)
        else:
            return {p.doc_id for p in postings1}


# ============================================================
# ЛАБ 3: ранжований пошук
# ============================================================

@dataclass(frozen=True, order=True)
class SearchResult:
    """Результат пошуку. order=True: порівнюються за score (doc_id у порівнянні не бере участі)."""

    score: float
    doc_id: str = field(compare=False)


class SearchEngine:
    """Ранжований пошук: парсить запит, знаходить документи, рахує бали Scorer-ом."""

    def __init__(self, index: Index, scorer: Scorer | None = None, cache_size: int = 128):
        self.index = index
        self.scorer: Scorer = scorer or BM25()
        # lru_cache: рядок запиту -> (множина doc_id, терміни для рейтингу)
        self._cached_match = lru_cache(maxsize=cache_size)(self._match)
        # коли індекс закривається, кеш очищається
        index.on_close(self._cached_match.cache_clear)

    def _match(self, query: str) -> Tuple[frozenset, Tuple[str, ...]]:
        tree = parse_query(query)
        ids = frozenset(tree.evaluate(self.index))
        terms = tuple(dict.fromkeys(tree.terms()))  # унікальні, зі збереженням порядку
        return ids, terms

    def matching(self, query: str) -> Tuple[frozenset, Tuple[str, ...]]:
        """Обгортка над кешем, яка пише в лог cache HIT / MISS."""
        hits_before = self._cached_match.cache_info().hits
        result = self._cached_match(query)
        if self._cached_match.cache_info().hits > hits_before:
            log.info("[cache] HIT  %r", query)
        else:
            log.info("[cache] MISS %r", query)
        return result

    @timed
    def search(self, query: str, k: int = 10) -> List[SearchResult]:
        ids, terms = self.matching(query)

        # накопичуємо бали по всіх термінах запиту
        scores: Dict[str, float] = defaultdict(float)
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


# --- CLI ---

SCORERS = {"bm25": BM25, "tfidf": TfIdf}
BOLD, RESET = "\033[1;33m", "\033[0m"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Findex Search CLI (ранжований пошук)")
    parser.add_argument("index_file", type=Path, help="Шлях до файлу індексу (.bin або .json)")
    parser.add_argument("query", type=str, help='Запит, напр.: python AND (async OR await) NOT java "event loop"')
    parser.add_argument("--scorer", choices=list(SCORERS), default="bm25", help="Функція рейтингу")
    parser.add_argument("-k", type=int, default=10, help="Скільки результатів показати")
    parser.add_argument("--data", type=Path, default=None, help="Папка з корпусом (для сніпетів)")
    parser.add_argument("--repeat", type=int, default=1, help="Повторити запит N разів (щоб побачити cache HIT)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    with open_index(args.index_file) as index:
        print(index)
        engine = SearchEngine(index, SCORERS[args.scorer]())

        for _ in range(args.repeat):
            results = engine.search(args.query, args.k)

        terms = parse_query(args.query).terms()
        print(f"\nТоп-{len(results)} за запитом {args.query!r} ({args.scorer}):")
        for rank, result in enumerate(results, 1):
            print(f"{rank:>2}. {result.score:8.4f}  {result.doc_id}")
            if args.data:
                text = read_document(args.data, result.doc_id)
                print("    " + best_snippet(text, terms, mark=(BOLD, RESET)))


if __name__ == "__main__":
    main()


#python -m findex.search index.bin "the" --scorer bm25 -k 5                       простий запит
#python -m findex.search index.bin 'python AND (async OR await) NOT java "event loop"' --data data --repeat 2
