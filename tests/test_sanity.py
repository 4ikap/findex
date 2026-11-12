from findex.index import Index
from findex.sanity import run_checks


def test_run_checks_builds_markdown_table(corpus_index: Index) -> None:
    report = run_checks(corpus_index)
    assert "| Перевірка | TF-IDF | BM25 |" in report
    assert report.count("✅") + report.count("❌") == 6  # 3 перевірки x 2 рейтинги
    assert "Корпус: 6 документів" in report


def test_run_checks_all_pass_on_toy_corpus(toy_index: Index) -> None:
    report = run_checks(toy_index)
    assert "❌" not in report
