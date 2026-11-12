"""Метрика якості пошуку: precision@k."""

from collections.abc import Iterable

from findex.search import SearchResult


def precision_at_k(results: Iterable[SearchResult], relevant: set[str], k: int = 5) -> float:
    """Частка релевантних документів серед перших k результатів (ділимо на k)."""
    top = [r.doc_id for r in list(results)[:k]]
    return sum(1 for doc_id in top if doc_id in relevant) / k
