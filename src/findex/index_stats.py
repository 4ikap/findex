import heapq
from dataclasses import dataclass

from findex.index import Index


@dataclass(frozen=True)
class IndexStats:
    terms: int
    docs: int
    avg_doc_length: float
    total_postings: int
    has_positions: bool
    max_df: int
    top_terms: list[tuple[str, int]]


def compute_stats(index: Index, top: int = 10) -> IndexStats:
    """Підсумкова статистика індексу + топ термінів за document frequency."""
    top_terms = heapq.nlargest(
        top,
        ((term, len(postings)) for term, postings in index.items()),
        key=lambda item: (item[1], item[0]),
    )
    return IndexStats(
        terms=len(index),
        docs=index.num_docs,
        avg_doc_length=index.avg_doc_length,
        total_postings=sum(len(postings) for postings in index.values()),
        has_positions=index.has_positions,
        max_df=top_terms[0][1] if top_terms else 0,
        top_terms=top_terms,
    )
