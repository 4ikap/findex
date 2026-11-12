import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from findex import __version__
from findex.cli import app
from findex.index import load_index


def make_runner() -> CliRunner:
    try:
        return CliRunner(mix_stderr=False)  # click < 8.2: stderr окремо лише з цим прапорцем
    except TypeError:
        return CliRunner()  # click >= 8.2 завжди розділяє stdout і stderr


runner = make_runner()


def test_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("index", "search", "stats"):
        assert command in result.stdout


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.stdout + result.stderr


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"findex {__version__}"


def test_index_command_builds_loadable_file(corpus_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "built.bin"
    result = runner.invoke(app, ["index", str(corpus_dir), "--out", str(out), "--positions"])
    assert result.exit_code == 0, result.stderr
    assert "Збережено" in result.stdout
    index = load_index(out)
    assert index.num_docs == 6
    assert index.has_positions


def test_index_command_json_format(corpus_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "built.json"
    result = runner.invoke(app, ["index", str(corpus_dir), "-o", str(out), "-f", "json"])
    assert result.exit_code == 0, result.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["has_positions"] is False


def test_index_missing_data_dir(tmp_path: Path) -> None:
    result = runner.invoke(app, ["index", str(tmp_path / "немає")])
    assert result.exit_code == 1
    assert "Помилка:" in result.stderr


def test_index_dir_without_bz2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["index", str(tmp_path)])
    assert result.exit_code == 1
    assert ".bz2" in result.stderr


def test_search_prints_table(index_file: Path) -> None:
    result = runner.invoke(app, ["search", str(index_file), "ніч"])
    assert result.exit_code == 0, result.stderr
    assert "a.bz2_line_1" in result.stdout
    assert "Бал" in result.stdout


def test_search_table_with_snippets(index_file: Path, corpus_dir: Path) -> None:
    result = runner.invoke(
        app, ["search", str(index_file), '"темна ніч"', "--data", str(corpus_dir)]
    )
    assert result.exit_code == 0, result.stderr
    assert "Сніпет" in result.stdout
    assert "Темна" in result.stdout


def test_search_json_goes_to_stdout_and_is_valid(index_file: Path, corpus_dir: Path) -> None:
    result = runner.invoke(
        app, ["search", str(index_file), "ніч AND дощ", "--json", "--data", str(corpus_dir)]
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)  # у stdout нічого, крім JSON
    assert payload["query"] == "ніч AND дощ"
    assert payload["scorer"] == "bm25"
    ids = {hit["doc_id"] for hit in payload["results"]}
    assert ids == {"a.bz2_line_1", "a.bz2_line_4"}
    assert all("\x02" not in hit["snippet"] for hit in payload["results"])


def test_search_json_respects_top_and_scorer(index_file: Path) -> None:
    result = runner.invoke(
        app, ["search", str(index_file), "ніч", "--json", "-k", "1", "--scorer", "tfidf"]
    )
    payload = json.loads(result.stdout)
    assert payload["scorer"] == "tfidf"
    assert len(payload["results"]) == 1
    assert "snippet" not in payload["results"][0]


def test_search_nothing_found(index_file: Path) -> None:
    result = runner.invoke(app, ["search", str(index_file), "ruby"])
    assert result.exit_code == 0
    assert "Нічого не знайдено" in result.stdout


def test_search_missing_index_is_one_line_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["search", str(tmp_path / "немає.bin"), "дощ"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1
    assert "Traceback" not in result.stderr


def test_search_bad_query_is_one_line_error(index_file: Path) -> None:
    result = runner.invoke(app, ["search", str(index_file), "(дощ"])
    assert result.exit_code == 1
    assert len(result.stderr.strip().splitlines()) == 1
    assert "закриваюча дужка" in result.stderr
    assert "Traceback" not in result.stderr


def test_search_phrase_without_positions(corpus_dir: Path, tmp_path: Path) -> None:
    plain = tmp_path / "plain.bin"
    runner.invoke(app, ["index", str(corpus_dir), "--out", str(plain)])
    result = runner.invoke(app, ["search", str(plain), '"темна ніч"'])
    assert result.exit_code == 1
    assert "--positions" in result.stderr


def test_search_corrupt_index_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"garbage")
    result = runner.invoke(app, ["search", str(bad), "дощ"])
    assert result.exit_code == 1
    assert "пошкоджений" in result.stderr


def test_search_unknown_scorer_is_rejected_by_cli(index_file: Path) -> None:
    result = runner.invoke(app, ["search", str(index_file), "ніч", "--scorer", "pagerank"])
    assert result.exit_code != 0


@pytest.mark.parametrize(("flag", "expect_debug"), [("-v", False), ("-vv", True)])
def test_verbose_flags_write_logs_to_stderr(
    index_file: Path, flag: str, expect_debug: bool
) -> None:
    result = runner.invoke(app, ["search", str(index_file), "ніч", "--json", flag])
    assert result.exit_code == 0
    json.loads(result.stdout)  # логи не псують stdout
    assert "[timed] load_index" in result.stderr
    assert "[cache] MISS" in result.stderr
    assert ("DEBUG" in result.stderr) is expect_debug


def test_default_verbosity_keeps_stderr_quiet(index_file: Path) -> None:
    result = runner.invoke(app, ["search", str(index_file), "ніч", "--json"])
    assert result.stderr == ""


def test_stats_table(index_file: Path) -> None:
    result = runner.invoke(app, ["stats", str(index_file)])
    assert result.exit_code == 0, result.stderr
    assert "Документи" in result.stdout
    assert "ніч" in result.stdout


def test_stats_json(index_file: Path) -> None:
    result = runner.invoke(app, ["stats", str(index_file), "--json", "--top", "2"])
    data = json.loads(result.stdout)
    assert data["docs"] == 6
    assert data["has_positions"] is True
    assert data["top_terms"][0] == ["ніч", 3]
    assert len(data["top_terms"]) == 2


def test_stats_missing_index(tmp_path: Path) -> None:
    result = runner.invoke(app, ["stats", str(tmp_path / "немає.bin")])
    assert result.exit_code == 1
    assert "Помилка:" in result.stderr


def test_index_unwritable_output_is_one_line_error(corpus_dir: Path, tmp_path: Path) -> None:
    """OSError (немає каталогу для виходу) теж дає один рядок і код 1, без стека."""
    out = tmp_path / "немає-такої-папки" / "index.bin"
    result = runner.invoke(app, ["index", str(corpus_dir), "--out", str(out)])
    assert result.exit_code == 1
    error_lines = [ln for ln in result.stderr.splitlines() if ln.startswith("Помилка:")]
    assert len(error_lines) == 1  # прогрес-бар у stderr — не помилка
    assert "Traceback" not in result.stderr


def test_search_data_dir_must_exist(index_file: Path, tmp_path: Path) -> None:
    result = runner.invoke(app, ["search", str(index_file), "ніч", "--data", str(tmp_path / "x")])
    assert result.exit_code == 1
    assert "Папку з корпусом не знайдено" in result.stderr
