"""Precision@5 для TF-IDF та BM25 на ваших власних запитах.

    python -m findex.evaluate index.bin eval/queries.json

Формат eval/queries.json (10 запитів із ручною розміткою «має бути в топ-5»):

    [
      {"query": "python AND async", "relevant": ["file.bz2_line_12", "file.bz2_line_40"]},
      ...
    ]
"""
import argparse
import json
import logging
from pathlib import Path
from typing import Iterable

from findex.index import open_index
from findex.scoring import BM25, TfIdf
from findex.search import SearchEngine, SearchResult


def precision_at_k(results: Iterable[SearchResult], relevant: set, k: int = 5) -> float:
    top = [r.doc_id for r in list(results)[:k]]
    return sum(1 for doc_id in top if doc_id in relevant) / k


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Оцінка P@5")
    parser.add_argument("index_file", type=Path)
    parser.add_argument("queries_file", type=Path)
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    queries = json.loads(args.queries_file.read_text(encoding="utf-8"))

    with open_index(args.index_file) as index:
        engines = {"TF-IDF": SearchEngine(index, TfIdf()), "BM25": SearchEngine(index, BM25())}
        totals = {name: 0.0 for name in engines}

        print(f"| # | Запит | TF-IDF P@{args.k} | BM25 P@{args.k} |")
        print("| :-- | :-- | :-- | :-- |")
        for i, item in enumerate(queries, 1):
            relevant = set(item["relevant"])
            cells = []
            for name, engine in engines.items():
                p = precision_at_k(engine.search(item["query"], args.k), relevant, args.k)
                totals[name] += p
                cells.append(f"{p:.2f}")
            print(f"| {i} | `{item['query']}` | {cells[0]} | {cells[1]} |")
        n = len(queries)
        print(f"| | **Середнє** | **{totals['TF-IDF'] / n:.2f}** | **{totals['BM25'] / n:.2f}** |")
