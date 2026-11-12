import random
from pathlib import Path

import pytest

from findex.index import build_inverted_index
from findex.scoring import BM25
from findex.search import SearchEngine
from tests.conftest import write_bz2


@pytest.mark.slow
def test_large_corpus_build_and_search(tmp_path: Path) -> None:
    """Довший за секунду тест: індекс із 60 000 документів і пошук по ньому."""
    rng = random.Random(1)
    vocab = [f"слово{n}" for n in range(400)]  # «рідкісне» навмисно не входить у словник
    lines = [" ".join(rng.choices(vocab, k=rng.randint(5, 25))) for _ in range(60_000)]
    lines[31_337] += " рідкісне"
    write_bz2(tmp_path / "big.bz2", lines)

    index = build_inverted_index(tmp_path, positions=True)
    assert index.num_docs == 60_000
    engine = SearchEngine(index, BM25())
    top = engine.search("рідкісне", k=3)
    assert [r.doc_id for r in top] == ["big.bz2_line_31338"]  # єдиний документ зі словом
    assert len(engine.search('слово1 AND "слово2 слово3"', k=5)) <= 5
