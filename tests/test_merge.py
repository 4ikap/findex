from typing import Literal

import pytest

from findex.index import Index, Posting
from findex.search import (
    execute_query,
    merge_intersect,
    merge_not,
    merge_union,
    set_intersect,
    set_not,
    set_union,
)


def _postings(*doc_ids: str) -> list[Posting]:
    return [Posting(doc_id, 1) for doc_id in doc_ids]


@pytest.mark.parametrize(
    ("left", "right", "inter", "union", "diff"),
    [
        (["a", "b", "c"], ["b", "c", "d"], ["b", "c"], ["a", "b", "c", "d"], ["a"]),
        (["a"], ["b"], [], ["a", "b"], ["a"]),
        ([], ["a"], [], ["a"], []),
        (["a", "b"], [], [], ["a", "b"], ["a", "b"]),
        (["a", "b"], ["a", "b"], ["a", "b"], ["a", "b"], []),
    ],
)
def test_merge_and_set_engines_agree(
    left: list[str], right: list[str], inter: list[str], union: list[str], diff: list[str]
) -> None:
    p1, p2 = _postings(*left), _postings(*right)
    assert [p.doc_id for p in merge_intersect(p1, p2)] == inter
    assert [p.doc_id for p in merge_union(p1, p2)] == union
    assert [p.doc_id for p in merge_not(p1, p2)] == diff
    assert set_intersect(p1, p2) == set(inter)
    assert set_union(p1, p2) == set(union)
    assert set_not(p1, p2) == set(diff)


@pytest.mark.parametrize("engine", ["merge", "set"])
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("python AND code", {"d1"}),
        ("java OR async", {"d1", "d2"}),
        ("python NOT java", {"d1", "d3"}),
        ("Python", {"d1", "d2", "d3"}),
        ("", set()),
    ],
)
def test_execute_query(
    toy_index: Index, engine: Literal["merge", "set"], query: str, expected: set[str]
) -> None:
    assert execute_query(query, toy_index, engine=engine) == expected


@pytest.mark.parametrize("engine", ["merge", "set"])
def test_execute_query_unknown_operator_returns_first_term(
    toy_index: Index, engine: Literal["merge", "set"]
) -> None:
    assert execute_query("java XOR python", toy_index, engine=engine) == {"d2"}
