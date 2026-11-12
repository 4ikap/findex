import pytest

from findex.errors import MissingPositionsError, QuerySyntaxError
from findex.index import Index
from findex.query import And, Node, Not, Or, Phrase, Term, parse_query

EXAMPLE = 'python AND (async OR await) NOT java "event loop"'


@pytest.mark.parametrize(
    ("query", "tree"),
    [
        ("python", Term("python")),
        ("Python", Term("python")),  # нормалізація тим самим токенізатором
        ("a AND b", And(Term("a"), Term("b"))),
        ("a b", And(Term("a"), Term("b"))),  # неявний AND
        ("a OR b AND c", Or(Term("a"), And(Term("b"), Term("c")))),  # AND сильніший за OR
        ("(a OR b) AND c", And(Or(Term("a"), Term("b")), Term("c"))),
        ("a NOT b", And(Term("a"), Not(Term("b")))),
        ("NOT a", Not(Term("a"))),
        ("NOT NOT a", Not(Not(Term("a")))),
        ('"event loop"', Phrase(("event", "loop"))),
        ("a AND b AND c", And(And(Term("a"), Term("b")), Term("c"))),  # ліва асоціативність
        ("the and", And(Term("the"), Term("and"))),  # and з малої — звичайне слово
        (
            EXAMPLE,
            And(
                And(And(Term("python"), Or(Term("async"), Term("await"))), Not(Term("java"))),
                Phrase(("event", "loop")),
            ),
        ),
    ],
)
def test_parse_builds_expected_tree(query: str, tree: Node) -> None:
    """Порівнюємо ДЕРЕВА, а не рядки."""
    assert parse_query(query) == tree


def test_operators_build_same_tree_as_parser() -> None:
    built = (
        Term("python")
        & (Term("async") | Term("await"))
        & ~Term("java")
        & Phrase(("event", "loop"))
    )
    assert built == parse_query(EXAMPLE)


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "(a OR b", "a OR", 'a "b', "a )", "AND a", "a AND", "!!!", '""'],
)
def test_syntax_errors(bad: str) -> None:
    with pytest.raises(QuerySyntaxError):
        parse_query(bad)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("python AND code", {"d1"}),
        ("java OR async", {"d1", "d2"}),
        ("python NOT java", {"d1", "d3"}),
        ("NOT python", {"d4"}),
        ("python AND (async OR await) NOT java", {"d1"}),
        ('"event loop"', {"d3", "d4"}),
        ('"loop event"', set()),
        ('"event loop" AND python', {"d3"}),
        ("ruby", set()),
    ],
)
def test_evaluate(toy_index: Index, query: str, expected: set[str]) -> None:
    assert parse_query(query).evaluate(toy_index) == expected


def test_phrase_requires_positions(plain_corpus_index: Index) -> None:
    with pytest.raises(MissingPositionsError):
        parse_query('"темна ніч"').evaluate(plain_corpus_index)


def test_phrase_on_real_corpus(corpus_index: Index) -> None:
    assert parse_query('"темна ніч"').evaluate(corpus_index) == {"a.bz2_line_4", "b.bz2_line_2"}
    assert parse_query('"ніч темна"').evaluate(corpus_index) == set()


def test_terms_skip_negated() -> None:
    assert parse_query('python NOT java "event loop"').terms() == ["python", "event", "loop"]
