import json
import pickle
from collections.abc import Mapping
from pathlib import Path

import pytest

from findex.errors import FindexError, IndexLoadError
from findex.index import (
    DocMeta,
    Index,
    IndexFormat,
    Posting,
    build_index,
    build_inverted_index,
    load_index,
    open_index,
)


def test_mapping_protocol(toy_index: Index) -> None:
    assert isinstance(toy_index, Mapping)
    assert len(toy_index) == 7
    assert "python" in toy_index
    assert "ruby" not in toy_index
    assert toy_index["java"][0].doc_id == "d2"
    assert toy_index.get("ruby", []) == []
    assert "loop" in list(toy_index)
    with pytest.raises(KeyError):
        _ = toy_index["ruby"]


def test_properties(toy_index: Index) -> None:
    assert toy_index.num_docs == 4
    assert toy_index.avg_doc_length == pytest.approx(4.0)
    assert toy_index.df("python") == 3
    assert toy_index.df("ruby") == 0
    assert toy_index.doc_length("d4") == 6


def test_avg_doc_length_is_cached(toy_index: Index) -> None:
    first = toy_index.avg_doc_length
    assert "avg_doc_length" in vars(toy_index)  # cached_property зберіг значення
    assert toy_index.avg_doc_length == first


def test_repr(toy_index: Index) -> None:
    text = repr(toy_index)
    assert "terms=7" in text
    assert "docs=4" in text
    assert "positions=True" in text


def test_empty_index_is_safe() -> None:
    empty = Index({}, {})
    assert len(empty) == 0
    assert empty.avg_doc_length == 0.0
    assert empty.df("x") == 0


@pytest.mark.parametrize(("fmt", "name"), [("pickle", "i.bin"), ("json", "i.json")])
def test_save_load_roundtrip(
    corpus_index: Index, tmp_path: Path, fmt: IndexFormat, name: str
) -> None:
    path = tmp_path / name
    corpus_index.save(path, fmt)
    loaded = load_index(path)  # формат визначається за розширенням
    assert dict(loaded) == dict(corpus_index)
    assert loaded.meta == corpus_index.meta
    assert loaded.has_positions is True


def test_load_without_positions_keeps_flag(plain_corpus_index: Index, tmp_path: Path) -> None:
    path = tmp_path / "plain.bin"
    plain_corpus_index.save(path)
    loaded = load_index(path)
    assert loaded.has_positions is False
    assert all(p.positions == () for postings in loaded.values() for p in postings)


def test_pickle_stores_plain_data(corpus_index: Index, tmp_path: Path) -> None:
    """Pickle не залежить від класів: у файлі лише словники, кортежі та числа."""
    path = tmp_path / "i.bin"
    corpus_index.save(path)
    with path.open("rb") as f:
        data = pickle.load(f)
    assert set(data) == {"has_positions", "index", "meta"}
    assert isinstance(data["index"]["ніч"][0], tuple)


def test_json_is_valid_and_utf8(corpus_index: Index, tmp_path: Path) -> None:
    path = tmp_path / "i.json"
    corpus_index.save(path, "json")
    assert "ніч" in path.read_text(encoding="utf-8")  # ensure_ascii=False
    assert json.loads(path.read_text(encoding="utf-8"))["has_positions"] is True


def test_open_index_closes_on_exception(index_file: Path) -> None:
    holder: list[Index] = []
    with pytest.raises(RuntimeError), open_index(index_file) as idx:
        holder.append(idx)
        raise RuntimeError("boom")
    assert holder[0].closed
    assert len(holder[0]) == 0


def test_close_runs_callbacks_and_clears_data(toy_index: Index) -> None:
    calls: list[str] = []
    toy_index.on_close(lambda: calls.append("cleanup"))
    toy_index.close()
    toy_index.close()  # повторний close нічого не ламає
    assert calls == ["cleanup"]
    assert toy_index.closed
    assert toy_index.num_docs == 0


def test_close_clears_even_if_callback_fails(toy_index: Index) -> None:
    def boom() -> None:
        raise RuntimeError("callback failed")

    toy_index.on_close(boom)
    with pytest.raises(RuntimeError):
        toy_index.close()
    assert len(toy_index) == 0  # ресурси звільнені попри виняток


def test_load_corrupt_file_raises_index_load_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"not a pickle")
    with pytest.raises(IndexLoadError):
        load_index(bad)


def test_load_wrong_structure_raises_index_load_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"x": 1}', encoding="utf-8")
    with pytest.raises(IndexLoadError):
        load_index(bad)


def test_load_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_index(tmp_path / "немає.bin")


def test_build_small_corpus_counts(corpus_index: Index) -> None:
    assert corpus_index.num_docs == 6
    assert corpus_index.avg_doc_length == pytest.approx(16 / 6)
    assert corpus_index.df("ніч") == 3
    assert corpus_index.df("дощ") == 2
    assert corpus_index.doc_length("a.bz2_line_3") == 0  # порожній документ


def test_build_positions_values(corpus_index: Index) -> None:
    python = corpus_index["python"][0]
    assert python == Posting("a.bz2_line_2", 2, (0, 4))
    assert corpus_index["hello"][0].positions == (0, 2)


def test_build_without_positions(plain_corpus_index: Index) -> None:
    assert plain_corpus_index.has_positions is False
    assert plain_corpus_index["python"][0] == Posting("a.bz2_line_2", 2)


def test_postings_sorted_by_doc_id(corpus_index: Index) -> None:
    for postings in corpus_index.values():
        ids = [p.doc_id for p in postings]
        assert ids == sorted(ids)


def test_build_skips_duplicate_doc_ids(caplog: pytest.LogCaptureFixture) -> None:
    docs = [("d1", "перший текст"), ("d1", "інший зовсім"), ("d2", "текст")]
    with caplog.at_level("WARNING", logger="findex"):
        index = build_index(docs)
    assert index.num_docs == 2
    assert index.df("текст") == 2
    assert index.df("інший") == 0
    assert "d1" in caplog.text


def test_build_inverted_index_reports_progress(corpus_dir: Path) -> None:
    steps: list[int] = []
    index = build_inverted_index(corpus_dir, on_bytes=steps.append)
    assert index.num_docs == 6
    assert sum(steps) > 0


def test_docmeta_is_frozen() -> None:
    meta = DocMeta("d1", 3)
    with pytest.raises(AttributeError):
        meta.length = 4  # type: ignore[misc]  # frozen dataclass: присвоєння заборонене


def test_save_unknown_format_is_rejected(toy_index: Index, tmp_path: Path) -> None:
    with pytest.raises(FindexError, match="Невідомий формат"):
        toy_index.save(tmp_path / "i.xml", "xml")  # type: ignore[arg-type]  # хибний формат


def test_load_unknown_format_is_rejected(toy_index: Index, tmp_path: Path) -> None:
    path = tmp_path / "i.bin"
    toy_index.save(path)
    with pytest.raises(FindexError, match="Невідомий формат"):
        load_index(path, "xml")  # type: ignore[arg-type]  # навмисно хибний формат
