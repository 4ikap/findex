"""Властивості (Hypothesis): інваріанти, що мають триматися для будь-яких даних."""

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from findex.index import IndexFormat, Posting, build_index, load_index
from findex.scoring import BM25, TfIdf
from findex.search import merge_intersect, merge_not, merge_union
from findex.tokenize import tokenize
from tests.helpers import make_index

VOCAB = ["дощ", "ніч", "python", "a", "b", "x1", "будь-що", "пам'ять"]
TEXTS = st.lists(st.sampled_from(VOCAB), max_size=8).map(" ".join)
DOCS = st.lists(
    st.tuples(st.text(alphabet="abc012", min_size=1, max_size=4), TEXTS),
    min_size=1,
    max_size=8,
    unique_by=lambda pair: pair[0],
)
DOC_IDS = st.lists(
    st.text(alphabet="abcd123", min_size=1, max_size=3), unique=True, max_size=12
).map(sorted)

SETTINGS = settings(max_examples=60, deadline=None)


@given(docs=DOCS, positions=st.booleans(), fmt=st.sampled_from(["pickle", "json"]))
@SETTINGS
def test_load_of_save_is_the_same_index(
    docs: list[tuple[str, str]], positions: bool, fmt: IndexFormat
) -> None:
    index = build_index(docs, positions=positions)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "index.dat"
        index.save(path, fmt)
        loaded = load_index(path, fmt)
    assert dict(loaded) == dict(index)
    assert loaded.meta == index.meta
    assert loaded.has_positions == index.has_positions


@given(docs=DOCS, positions=st.booleans())
@SETTINGS
def test_postings_are_always_sorted_and_consistent(
    docs: list[tuple[str, str]], positions: bool
) -> None:
    index = build_index(docs, positions=positions)
    for postings in index.values():
        ids = [p.doc_id for p in postings]
        assert ids == sorted(ids)
        assert len(ids) == len(set(ids))  # без дублікатів
        for posting in postings:
            assert posting.freq >= 1
            if positions:
                assert posting.freq == len(posting.positions)
    total_freq = sum(p.freq for postings in index.values() for p in postings)
    assert total_freq == sum(meta.length for meta in index.meta.values())


@given(a=DOC_IDS, b=DOC_IDS)
@SETTINGS
def test_merge_matches_set_operations(a: list[str], b: list[str]) -> None:
    pa = [Posting(doc_id, 1) for doc_id in a]
    pb = [Posting(doc_id, 1) for doc_id in b]
    assert [p.doc_id for p in merge_intersect(pa, pb)] == sorted(set(a) & set(b))
    assert [p.doc_id for p in merge_union(pa, pb)] == sorted(set(a) | set(b))
    assert [p.doc_id for p in merge_not(pa, pb)] == sorted(set(a) - set(b))


@given(tf=st.integers(1, 500), df=st.integers(1, 4), doc_len=st.integers(1, 200))
@SETTINGS
def test_score_never_decreases_when_tf_grows(tf: int, df: int, doc_len: int) -> None:
    index = make_index()
    for scorer in (TfIdf(), BM25()):
        assert scorer.score(tf + 1, df, doc_len, index) >= scorer.score(tf, df, doc_len, index)


@given(text=st.text(alphabet="aBя Ї'-_1 .,!Ґ", max_size=40))
@SETTINGS
def test_tokenize_output_is_stable(text: str) -> None:
    tokens = list(tokenize(text))
    assert all(token and token == token.lower() for token in tokens)
    assert list(tokenize(" ".join(tokens))) == tokens  # повторна токенізація нічого не змінює
