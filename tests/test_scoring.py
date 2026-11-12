import pytest

from findex.index import Index
from findex.scoring import BM25, Scorer, ScorerName, TfIdf, make_scorer

SCORERS: list[Scorer] = [TfIdf(), BM25()]


@pytest.mark.parametrize("scorer", SCORERS, ids=["tfidf", "bm25"])
class TestSanityChecks:
    """Три перевірки рейтингу з лаби 3 для обох реалізацій."""

    def test_rare_term_beats_frequent(self, toy_index: Index, scorer: Scorer) -> None:
        assert scorer.score(1, 1, 4, toy_index) > scorer.score(1, 3, 4, toy_index)

    def test_20th_repetition_adds_almost_nothing(self, toy_index: Index, scorer: Scorer) -> None:
        first = scorer.score(1, 1, 4, toy_index)
        gain = scorer.score(20, 1, 4, toy_index) - scorer.score(19, 1, 4, toy_index)
        assert gain < 0.1 * first

    def test_short_document_beats_long(self, toy_index: Index, scorer: Scorer) -> None:
        assert scorer.score(1, 1, 3, toy_index) > scorer.score(1, 1, 3000, toy_index)

    def test_zero_tf_or_df_scores_zero(self, toy_index: Index, scorer: Scorer) -> None:
        assert scorer.score(0, 1, 4, toy_index) == 0.0
        assert scorer.score(1, 0, 4, toy_index) == 0.0


@pytest.mark.parametrize("scorer", SCORERS, ids=["tfidf", "bm25"])
def test_scorers_satisfy_protocol_without_inheritance(scorer: Scorer) -> None:
    assert isinstance(scorer, Scorer)
    assert Scorer not in type(scorer).__mro__


def test_bm25_defaults() -> None:
    assert (BM25().k1, BM25().b) == (1.5, 0.75)


def test_bm25_parameters_change_score(toy_index: Index) -> None:
    default = BM25().score(3, 1, 8, toy_index)
    no_length_norm = BM25(b=0.0).score(3, 1, 8, toy_index)
    assert default != no_length_norm


@pytest.mark.parametrize(("name", "cls"), [("bm25", BM25), ("tfidf", TfIdf)])
def test_make_scorer(name: ScorerName, cls: type) -> None:
    assert isinstance(make_scorer(name), cls)


def test_make_scorer_unknown_name() -> None:
    with pytest.raises(ValueError, match="Невідомий scorer"):
        make_scorer("pagerank")  # type: ignore[arg-type]  # навмисно неіснуюча назва
