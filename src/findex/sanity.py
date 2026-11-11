"""Три sanity-check рейтингу на вашому корпусі.

    python -m findex.sanity index.bin

Виводить markdown, який можна вставити в README.
"""
import argparse
import logging
from pathlib import Path

from findex.index import Index, open_index
from findex.scoring import BM25, Scorer, TfIdf


def run_checks(index: Index) -> str:
    words = [t for t in index if t.isalpha() and len(t) >= 4]
    rare = min(words, key=index.df)
    frequent = max(words, key=index.df)
    avg_len = max(1, round(index.avg_doc_length))
    lengths = [m.length for m in index.meta.values() if m.length > 0]
    short_len, long_len = min(lengths), max(lengths)

    lines = [
        f"Корпус: {index.num_docs} документів, середня довжина {index.avg_doc_length:.1f} токенів.",
        f"Рідкий термін: `{rare}` (df={index.df(rare)}), частий: `{frequent}` (df={index.df(frequent)}).",
        "",
        "| Перевірка | TF-IDF | BM25 |",
        "| :--- | :--- | :--- |",
    ]

    def row(title, fn):
        cells = [fn(s) for s in (TfIdf(), BM25())]
        lines.append(f"| {title} | {cells[0]} | {cells[1]} |")

    def check1(s: Scorer) -> str:
        a = s.score(1, index.df(rare), avg_len, index)
        b = s.score(1, index.df(frequent), avg_len, index)
        return f"{'✅' if a > b else '❌'} рідкий {a:.4f} > частий {b:.4f}"

    def check2(s: Scorer) -> str:
        first = s.score(1, index.df(rare), avg_len, index)
        gain = s.score(20, index.df(rare), avg_len, index) - s.score(19, index.df(rare), avg_len, index)
        return f"{'✅' if gain < 0.1 * first else '❌'} 1-е входження +{first:.4f}, 20-те +{gain:.4f}"

    def check3(s: Scorer) -> str:
        short = s.score(1, index.df(rare), short_len, index)
        long_ = s.score(1, index.df(rare), long_len, index)
        return f"{'✅' if short > long_ else '❌'} короткий ({short_len}) {short:.4f} > довгий ({long_len}) {long_:.4f}"

    row("1. Рідкий термін вище частого (tf=1)", check1)
    row("2. 20-те повторення майже нічого не додає", check2)
    row("3. Короткий документ вище довгого (tf=1)", check3)
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sanity-check рейтингу")
    parser.add_argument("index_file", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with open_index(args.index_file) as idx:
        print(run_checks(idx))
