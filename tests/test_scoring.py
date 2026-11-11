import unittest

from findex.scoring import BM25, Scorer, TfIdf
from tests.helpers import make_index


class TestScorers(unittest.TestCase):

  def setUp(self):
    self.index = make_index()
    self.scorers = [TfIdf(), BM25()]

  def test_protocol(self):
    for scorer in self.scorers:
      self.assertIsInstance(scorer, Scorer)

  def test_bm25_defaults(self):
    self.assertEqual((BM25().k1, BM25().b), (1.5, 0.75))

  def test_rare_term_beats_frequent(self):
    for s in self.scorers:
      with self.subTest(scorer=type(s).__name__):
        rare = s.score(1, 1, 4, self.index)
        frequent = s.score(1, 3, 4, self.index)
        self.assertGreater(rare, frequent)

  def test_20th_repetition_adds_almost_nothing(self):
    for s in self.scorers:
      with self.subTest(scorer=type(s).__name__):
        first = s.score(1, 1, 4, self.index)
        gain = s.score(20, 1, 4, self.index) - s.score(19, 1, 4, self.index)
        self.assertLess(gain, 0.1 * first)

  def test_short_doc_beats_long_doc(self):
    for s in self.scorers:
      with self.subTest(scorer=type(s).__name__):
        self.assertGreater(
            s.score(1, 1, 3, self.index), s.score(1, 1, 3000, self.index)
        )


if __name__ == "__main__":
  unittest.main()
