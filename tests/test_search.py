import logging
from pathlib import Path

import pytest

from findex.evaluate import precision_at_k
from findex.index import Index
from findex.scoring import BM25, TfIdf
from findex.search import SearchEngine, SearchResult, run_query
from findex.snippets import best_snippet


def test_search_result_ordering() -> None:
    low, high = SearchResult(1.0, "a"), SearchResult(2.0, "b")
    assert low < high
    assert max(low, high).doc_id == "b"
    assert SearchResult(1.0, "a") == SearchResult(1.0, "zzz")  # doc_id не порівнюється


@pytest.mark.parametrize("scorer", [TfIdf(), BM25()], ids=["tfidf", "bm25"])
def test_ranking_and_topk(toy_index: Index, scorer: TfIdf | BM25) -> None:
    results = SearchEngine(toy_index, scorer).search("python", k=2)
    assert len(results) == 2
    assert results[0].score >= results[1].score
    assert results[0].doc_id == "d1"  # 2 входження в короткому документі


def test_boolean_filter_applies(toy_index: Index) -> None:
    ids = {r.doc_id for r in SearchEngine(toy_index).search("python NOT java")}
    assert ids == {"d1", "d3"}


def test_scores_accumulate_over_terms(toy_index: Index) -> None:
    engine = SearchEngine(toy_index)
    both = {r.doc_id: r.score for r in engine.search("python AND code")}
    only_python = {r.doc_id: r.score for r in engine.search("python")}
    assert both["d1"] > only_python["d1"]


def test_cache_hit_is_logged(toy_index: Index, caplog: pytest.LogCaptureFixture) -> None:
    engine = SearchEngine(toy_index)
    with caplog.at_level(logging.INFO, logger="findex"):
        engine.search("python")
        engine.search("python")
    assert "[cache] MISS" in caplog.text
    assert "[cache] HIT" in caplog.text
    assert "[timed] SearchEngine.search" in caplog.text


def test_cache_cleared_on_close(toy_index: Index) -> None:
    engine = SearchEngine(toy_index)
    engine.search("python")
    assert engine.matching("python")[0] == {"d1", "d2", "d3"}
    toy_index.close()
    assert engine._cached_match.cache_info().currsize == 0


def test_ties_are_deterministic(toy_index: Index) -> None:
    engine = SearchEngine(toy_index)
    first = [r.doc_id for r in engine.search("python OR java OR loop OR event", k=4)]
    second = [r.doc_id for r in engine.search("python OR java OR loop OR event", k=4)]
    assert first == second


def test_pure_not_query_still_returns_documents(toy_index: Index) -> None:
    results = SearchEngine(toy_index).search("NOT python")
    assert [r.doc_id for r in results] == ["d4"]
    assert results[0].score == 0.0


def test_unknown_term_gives_empty_result(toy_index: Index) -> None:
    assert SearchEngine(toy_index).search("ruby") == []


def test_run_query_adds_snippets(corpus_index: Index, corpus_dir: Path) -> None:
    engine = SearchEngine(corpus_index)
    hits = run_query(engine, "ніч", 5, corpus_dir, mark=("<", ">"))
    assert {h.doc_id for h in hits} == {"a.bz2_line_1", "a.bz2_line_4", "b.bz2_line_2"}
    assert all(h.snippet is not None and "<ніч>" in h.snippet.lower() for h in hits)
    assert [h.rank for h in hits] == [1, 2, 3]


def test_run_query_without_data_has_no_snippets(corpus_index: Index) -> None:
    hits = run_query(SearchEngine(corpus_index), "ніч", 5)
    assert all(h.snippet is None for h in hits)


def test_snippet_window_and_highlight() -> None:
    text = "x" * 200 + " python async " + "y" * 200
    snippet = best_snippet(text, ["python", "async"], window=20)
    assert "**python**" in snippet
    assert "**async**" in snippet
    assert snippet.startswith("…")
    assert snippet.endswith("…")
    assert len(snippet) < 80


def test_snippet_prefers_window_with_more_terms() -> None:
    text = "python " + "z" * 300 + " python async"
    assert "**async**" in best_snippet(text, ["python", "async"], window=30)


def test_snippet_is_case_insensitive() -> None:
    assert best_snippet("Дощ і ніч", ["дощ"]) == "**Дощ** і ніч"


def test_snippet_without_match_returns_start() -> None:
    assert best_snippet("зовсім інший текст", ["python"]) == "зовсім інший текст"


def test_snippet_without_terms_returns_start() -> None:
    assert best_snippet("a" * 500, []) == "a" * 160


def test_precision_at_k() -> None:
    results = [SearchResult(5 - i, f"d{i}") for i in range(5)]
    assert precision_at_k(results, {"d0", "d1", "d9"}, 5) == pytest.approx(0.4)
    assert precision_at_k(results, set(), 5) == 0.0
