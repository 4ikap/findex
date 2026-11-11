import unittest

from findex.evaluate import precision_at_k
from findex.scoring import BM25, TfIdf
from findex.search import SearchEngine, SearchResult
from findex.snippets import best_snippet
from tests.helpers import make_index


class TestSearch(unittest.TestCase):

  def test_search_result_ordering(self):
    low, high = SearchResult(1.0, "a"), SearchResult(2.0, "b")
    self.assertLess(low, high)
    self.assertEqual(max(low, high).doc_id, "b")

  def test_ranking_and_topk(self):
    for scorer in (TfIdf(), BM25()):
      with self.subTest(scorer=type(scorer).__name__):
        engine = SearchEngine(make_index(), scorer)
        results = engine.search("python", k=2)
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(results[0].score, results[1].score)
        # d1 має 2 входження python у короткому документі — найвищий бал
        self.assertEqual(results[0].doc_id, "d1")

  def test_boolean_filter_applies(self):
    engine = SearchEngine(make_index())
    ids = {r.doc_id for r in engine.search("python NOT java")}
    self.assertEqual(ids, {"d1", "d3"})

  def test_cache_hit_logged(self):
    engine = SearchEngine(make_index())
    with self.assertLogs("findex", level="INFO") as logs:
      engine.search("python")
      engine.search("python")
    text = "\n".join(logs.output)
    self.assertIn("MISS", text)
    self.assertIn("HIT", text)

  def test_cache_cleared_on_close(self):
    index = make_index()
    engine = SearchEngine(index)
    engine.search("python")
    index.close()
    self.assertEqual(engine._cached_match.cache_info().currsize, 0)


class TestSnippetsAndMetrics(unittest.TestCase):

  def test_snippet_window_and_highlight(self):
    text = "x" * 200 + " python async " + "y" * 200
    snippet = best_snippet(text, ["python", "async"], window=20)
    self.assertIn("**python**", snippet)
    self.assertIn("**async**", snippet)
    self.assertTrue(snippet.startswith("…") and snippet.endswith("…"))
    self.assertLess(len(snippet), 80)

  def test_snippet_prefers_window_with_more_terms(self):
    text = "python " + "z" * 300 + " python async"
    snippet = best_snippet(text, ["python", "async"], window=30)
    self.assertIn("**async**", snippet)

  def test_precision_at_k(self):
    results = [SearchResult(5 - i, f"d{i}") for i in range(5)]
    self.assertAlmostEqual(precision_at_k(results, {"d0", "d1", "d9"}, 5), 0.4)


if __name__ == "__main__":
  unittest.main()
