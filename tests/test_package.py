import importlib
import importlib.metadata
from importlib.metadata import PackageNotFoundError

import pytest

import findex


def test_version_is_a_non_empty_string() -> None:
    assert isinstance(findex.__version__, str)
    assert findex.__version__


def test_version_falls_back_when_package_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(name: str) -> str:
        raise PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    try:
        assert importlib.reload(findex).__version__ == "0+unknown"
    finally:
        monkeypatch.undo()
        importlib.reload(findex)  # повертаємо справжню версію для решти тестів
