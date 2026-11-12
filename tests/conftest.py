import bz2
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from findex.index import Index, build_inverted_index
from tests.helpers import make_index

# Маленький корпус: 6 документів (один порожній), українська + латиниця.
CORPUS_A = ["Дощ і ніч", "Python async code і python", "", "Темна ніч дощ"]
CORPUS_B = ["Hello world hello", "Темна ніч"]


def write_bz2(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with bz2.open(path, "wt", encoding="utf-8") as f:
        f.write("\n".join(lines))


@pytest.fixture(autouse=True)
def _reset_findex_logger() -> Iterator[None]:
    """CLI-тести змінюють логер findex; повертаємо його в початковий стан."""
    yield
    logger = logging.getLogger("findex")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)


@pytest.fixture
def corpus_dir(tmp_path: Path) -> Path:
    write_bz2(tmp_path / "corpus" / "a.bz2", CORPUS_A)
    write_bz2(tmp_path / "corpus" / "sub" / "b.bz2", CORPUS_B)
    return tmp_path / "corpus"


@pytest.fixture
def corpus_index(corpus_dir: Path) -> Index:
    return build_inverted_index(corpus_dir, positions=True)


@pytest.fixture
def plain_corpus_index(corpus_dir: Path) -> Index:
    return build_inverted_index(corpus_dir, positions=False)


@pytest.fixture
def toy_index() -> Index:
    return make_index()


@pytest.fixture
def index_file(tmp_path: Path, corpus_index: Index) -> Path:
    path = tmp_path / "index.bin"
    corpus_index.save(path)
    return path
