"""Три sanity-check рейтингу на корпусі (результат — markdown-таблиця для звіту)."""

from collections.abc import Callable

from findex.index import Index
from findex.scoring import BM25, Scorer, TfIdf


def run_checks(index: Index) -> str:
    """Перевіряє: рідкий термін вищий за частий, 20-те повторення майже нічого
    не додає, короткий документ вищий за довгий. Повертає markdown."""
    words = [t for t in index if t.isalpha() and len(t) >= 4]
    rare = min(words, key=index.df)
    frequent = max(words, key=index.df)
    avg_len = max(1, round(index.avg_doc_length))
    lengths = [m.length for m in index.meta.values() if m.length > 0]
    short_len, long_len = min(lengths), max(lengths)

    lines = [
        f"Корпус: {index.num_docs} документів, середня довжина {index.avg_doc_length:.1f} токенів.",
        f"Рідкий термін: `{rare}` (df={index.df(rare)}), "
        f"частий: `{frequent}` (df={index.df(frequent)}).",
        "",
        "| Перевірка | TF-IDF | BM25 |",
        "| :--- | :--- | :--- |",
    ]

    def check_rare_vs_frequent(s: Scorer) -> str:
        a = s.score(1, index.df(rare), avg_len, index)
        b = s.score(1, index.df(frequent), avg_len, index)
        return f"{'✅' if a > b else '❌'} рідкий {a:.4f} > частий {b:.4f}"

    def check_saturation(s: Scorer) -> str:
        first = s.score(1, index.df(rare), avg_len, index)
        tf20 = s.score(20, index.df(rare), avg_len, index)
        tf19 = s.score(19, index.df(rare), avg_len, index)
        gain = tf20 - tf19
        mark = "✅" if gain < 0.1 * first else "❌"
        return f"{mark} 1-е входження +{first:.4f}, 20-те +{gain:.4f}"

    def check_length(s: Scorer) -> str:
        short = s.score(1, index.df(rare), short_len, index)
        long_ = s.score(1, index.df(rare), long_len, index)
        mark = "✅" if short > long_ else "❌"
        return f"{mark} короткий ({short_len}) {short:.4f} > довгий ({long_len}) {long_:.4f}"

    checks: list[tuple[str, Callable[[Scorer], str]]] = [
        ("1. Рідкий термін вище частого (tf=1)", check_rare_vs_frequent),
        ("2. 20-те повторення майже нічого не додає", check_saturation),
        ("3. Короткий документ вище довгого (tf=1)", check_length),
    ]
    for title, check in checks:
        lines.append(f"| {title} | {check(TfIdf())} | {check(BM25())} |")
    return "\n".join(lines)
