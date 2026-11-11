import unittest

from findex.query import And, Not, Or, Phrase, QuerySyntaxError, Term, parse_query
from tests.helpers import make_index


class TestParser(unittest.TestCase):
  """Тести порівнюють ДЕРЕВА, а не рядки."""

  def test_example_from_assignment(self):
    tree = parse_query('python AND (async OR await) NOT java "event loop"')
    expected = And(
        And(
            And(Term("python"), Or(Term("async"), Term("await"))),
            Not(Term("java")),
        ),
        Phrase(("event", "loop")),
    )
    self.assertEqual(tree, expected)

  def test_operators_build_same_tree(self):
    built = (
        Term("python") & (Term("async") | Term("await")) & ~Term("java")
        & Phrase(("event", "loop"))
    )
    parsed = parse_query('python AND (async OR await) NOT java "event loop"')
    self.assertEqual(built, parsed)

  def test_precedence_and_over_or(self):
    self.assertEqual(
        parse_query("a OR b AND c"), Or(Term("a"), And(Term("b"), Term("c")))
    )

  def test_leading_not_and_implicit_and(self):
    self.assertEqual(parse_query("NOT a"), Not(Term("a")))
    self.assertEqual(parse_query("a b"), And(Term("a"), Term("b")))

  def test_lowercase_operators_are_terms(self):
    self.assertEqual(parse_query("the and"), And(Term("the"), Term("and")))

  def test_syntax_errors(self):
    for bad in ["", "(a OR b", "a OR", 'a "b', "a )", "AND a"]:
      with self.subTest(query=bad):
        with self.assertRaises(QuerySyntaxError):
          parse_query(bad)


class TestEvaluate(unittest.TestCase):

  def setUp(self):
    self.index = make_index()

  def ev(self, query):
    return parse_query(query).evaluate(self.index)

  def test_and_or_not(self):
    self.assertEqual(self.ev("python AND code"), {"d1"})
    self.assertEqual(self.ev("java OR async"), {"d1", "d2"})
    self.assertEqual(self.ev("python NOT java"), {"d1", "d3"})
    self.assertEqual(self.ev("NOT python"), {"d4"})

  def test_full_example(self):
    self.assertEqual(self.ev("python AND (async OR await) NOT java"), {"d1"})

  def test_phrase(self):
    self.assertEqual(self.ev('"event loop"'), {"d3", "d4"})
    self.assertEqual(self.ev('"loop event"'), set())

  def test_phrase_requires_positions(self):
    self.index.has_positions = False
    with self.assertRaises(ValueError):
      self.ev('"event loop"')

  def test_terms_skip_negated(self):
    tree = parse_query('python NOT java "event loop"')
    self.assertEqual(tree.terms(), ["python", "event", "loop"])


if __name__ == "__main__":
  unittest.main()
