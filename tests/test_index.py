import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

from findex.index import open_index
from tests.helpers import make_index


class TestIndex(unittest.TestCase):

  def setUp(self):
    self.index = make_index()

  def test_mapping_protocol(self):
    self.assertIsInstance(self.index, Mapping)
    self.assertEqual(len(self.index), 7)
    self.assertIn("python", self.index)
    self.assertNotIn("ruby", self.index)
    self.assertEqual(self.index["java"][0].doc_id, "d2")
    self.assertEqual(self.index.get("ruby", []), [])
    self.assertIn("loop", list(self.index))
    with self.assertRaises(KeyError):
      self.index["ruby"]

  def test_properties(self):
    self.assertEqual(self.index.num_docs, 4)
    self.assertAlmostEqual(self.index.avg_doc_length, 4.0)
    self.assertEqual(self.index.df("python"), 3)
    self.assertEqual(self.index.df("ruby"), 0)

  def test_repr(self):
    text = repr(self.index)
    self.assertIn("terms=7", text)
    self.assertIn("docs=4", text)

  def test_save_load_roundtrip(self):
    for fmt, name in (("pickle", "i.bin"), ("json", "i.json")):
      with self.subTest(fmt=fmt), tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        self.index.save(path, fmt)
        with open_index(path) as loaded:
          self.assertEqual(dict(loaded), dict(self.index))
          self.assertTrue(loaded.has_positions)

  def test_open_index_closes_on_exception(self):
    with tempfile.TemporaryDirectory() as tmp:
      path = Path(tmp) / "i.bin"
      self.index.save(path)
      holder = []
      with self.assertRaises(RuntimeError):
        with open_index(path) as idx:
          holder.append(idx)
          raise RuntimeError("boom")
      self.assertTrue(holder[0].closed)
      self.assertEqual(len(holder[0]), 0)


if __name__ == "__main__":
  unittest.main()
