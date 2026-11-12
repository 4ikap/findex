from pathlib import Path

import pytest

from findex.core import corpus_size, iter_documents, read_document
from findex.errors import DocumentError
from tests.conftest import CORPUS_A, CORPUS_B, write_bz2


def test_iter_documents_ids_and_text(corpus_dir: Path) -> None:
    docs = list(iter_documents(corpus_dir))
    assert docs[0] == ("a.bz2_line_1", "Дощ і ніч")
    assert docs[1] == ("a.bz2_line_2", "Python async code і python")
    assert len(docs) == len(CORPUS_A) + len(CORPUS_B)


def test_iter_documents_sorted_and_recursive(corpus_dir: Path) -> None:
    ids = [doc_id for doc_id, _ in iter_documents(corpus_dir)]
    assert ids[:4] == [f"a.bz2_line_{n}" for n in range(1, 5)]
    assert ids[4:] == ["b.bz2_line_1", "b.bz2_line_2"]  # файл із підпапки sub/


def test_iter_documents_keeps_empty_lines(corpus_dir: Path) -> None:
    texts = dict(iter_documents(corpus_dir))
    assert texts["a.bz2_line_3"] == ""


def test_iter_documents_skips_corrupt_file(
    corpus_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (corpus_dir / "bad.bz2").write_bytes("це точно не bz2".encode())
    with caplog.at_level("WARNING", logger="findex"):
        docs = list(iter_documents(corpus_dir))
    assert len(docs) == len(CORPUS_A) + len(CORPUS_B)  # решта файлів прочитана
    assert "bad.bz2" in caplog.text


def test_iter_documents_progress_sums_to_corpus_size(tmp_path: Path) -> None:
    write_bz2(tmp_path / "big.bz2", [f"рядок номер {n}" for n in range(5000)])
    steps: list[int] = []
    docs = list(iter_documents(tmp_path, on_bytes=steps.append))
    assert len(docs) == 5000
    assert sum(steps) == corpus_size(tmp_path)
    assert all(step >= 0 for step in steps)


def test_corpus_size(corpus_dir: Path) -> None:
    expected = sum(p.stat().st_size for p in corpus_dir.rglob("*.bz2"))
    assert corpus_size(corpus_dir) == expected > 0


def test_corpus_size_empty_dir(tmp_path: Path) -> None:
    assert corpus_size(tmp_path) == 0


def test_read_document_roundtrip(corpus_dir: Path) -> None:
    for doc_id, text in iter_documents(corpus_dir):
        assert read_document(corpus_dir, doc_id) == text


@pytest.mark.parametrize(
    "doc_id",
    ["без-номера", "a.bz2_line_abc", "немає.bz2_line_1", "a.bz2_line_999"],
)
def test_read_document_errors(corpus_dir: Path, doc_id: str) -> None:
    with pytest.raises(DocumentError):
        read_document(corpus_dir, doc_id)
