import functools
import json
import logging
import sys
from collections.abc import Callable
from dataclasses import asdict
from enum import StrEnum
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from findex import __version__
from findex.core import corpus_size
from findex.errors import FindexError
from findex.index import IndexFormat, build_inverted_index, open_index
from findex.index_stats import compute_stats
from findex.query import parse_query
from findex.scoring import ScorerName, make_scorer
from findex.search import Hit, SearchEngine, run_query

app = typer.Typer(
    name="findex",
    help="Findex: інвертований індекс і ранжований пошук (TF-IDF / BM25).",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)

# Службові маркери підсвітки: сніпет будується без залежності від rich,
# а CLI потім замінює їх на розмітку rich (таблиця) або на нічого (JSON).
_MARK_START = "\x02"
_MARK_END = "\x03"


class ScorerChoice(StrEnum):
    bm25 = "bm25"
    tfidf = "tfidf"


class FormatChoice(StrEnum):
    pickle = "pickle"
    json = "json"


_SCORER_NAMES: dict[ScorerChoice, ScorerName] = {
    ScorerChoice.bm25: "bm25",
    ScorerChoice.tfidf: "tfidf",
}
_FORMAT_NAMES: dict[FormatChoice, IndexFormat] = {
    FormatChoice.pickle: "pickle",
    FormatChoice.json: "json",
}

VerboseOpt = Annotated[
    int,
    typer.Option("--verbose", "-v", count=True, help="-v: INFO, -vv: DEBUG (логи йдуть у stderr)"),
]


def configure_logging(verbosity: int) -> None:
    """Єдине місце налаштування логів: handler у stderr, рівень за кількістю -v."""
    if verbosity <= 0:
        level = logging.WARNING
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG
    logger = logging.getLogger("findex")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)


def _fail(message: str) -> NoReturn:
    typer.echo(f"Помилка: {message}", err=True)
    raise typer.Exit(code=1)


def _handle_errors[**P](func: Callable[P, None]) -> Callable[P, None]:
    """Очікувані помилки → один зрозумілий рядок у stderr і код виходу 1 (без стека)."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            func(*args, **kwargs)
        except FindexError as exc:
            _fail(str(exc))
        except OSError as exc:
            has_detail = exc.strerror and exc.filename
            _fail(f"{exc.strerror}: {exc.filename}" if has_detail else str(exc))

    return wrapper


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"findex {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Показати версію й вийти"
        ),
    ] = False,
) -> None:
    """Findex: індексація, ранжований пошук і статистика."""


@app.command("index")
@_handle_errors
def index_cmd(
    data_dir: Annotated[Path, typer.Argument(help="Папка з корпусом (.bz2 файли)")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Куди зберегти індекс")] = Path(
        "index.bin"
    ),
    fmt: Annotated[FormatChoice, typer.Option("--format", "-f", help="Формат файлу")] = (
        FormatChoice.pickle
    ),
    positions: Annotated[
        bool,
        typer.Option("--positions/--no-positions", help="Зберігати позиції (потрібні для фраз)"),
    ] = False,
    verbose: VerboseOpt = 0,
) -> None:
    """Будує інвертований індекс із корпусу й зберігає його у файл."""
    configure_logging(verbose)
    if not data_dir.is_dir():
        raise FindexError(f"Папку з корпусом не знайдено: {data_dir}")
    total = corpus_size(data_dir)
    if total == 0:
        raise FindexError(f"У {data_dir} немає .bz2 файлів")

    progress_console = Console(stderr=True)  # прогрес у stderr, щоб stdout лишався чистим
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]Індексація"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=progress_console,
    ) as progress:
        task = progress.add_task("index", total=total)
        index = build_inverted_index(
            data_dir,
            positions=positions,
            on_bytes=lambda step: progress.advance(task, step),
        )

    index.save(out, _FORMAT_NAMES[fmt])
    typer.echo(f"Збережено {out}: {index}")


def _to_markup(snippet: str) -> str:
    """Сніпет із службовими маркерами -> розмітка rich (решту тексту екрануємо)."""
    return (
        escape(snippet)
        .replace(_MARK_START, "[bold yellow]")
        .replace(_MARK_END, "[/bold yellow]")
    )


def _to_plain(snippet: str) -> str:
    return snippet.replace(_MARK_START, "").replace(_MARK_END, "")


def _hit_to_dict(hit: Hit) -> dict[str, object]:
    item: dict[str, object] = {"rank": hit.rank, "score": hit.score, "doc_id": hit.doc_id}
    if hit.snippet is not None:
        item["snippet"] = _to_plain(hit.snippet)
    return item


def _render_table(hits: list[Hit], query: str, scorer: str, with_snippets: bool) -> None:
    console = Console()
    if not hits:
        console.print("[dim]Нічого не знайдено.[/dim]")
        return
    table = Table(title=f"Результати: {escape(query)} ({scorer})")
    table.add_column("#", justify="right")
    table.add_column("Бал", justify="right")
    table.add_column("Документ", no_wrap=True)
    if with_snippets:
        table.add_column("Сніпет", overflow="fold")
    for hit in hits:
        row = [str(hit.rank), f"{hit.score:.4f}", hit.doc_id]
        if with_snippets:
            row.append(_to_markup(hit.snippet or ""))
        table.add_row(*row)
    console.print(table)


@app.command("search")
@_handle_errors
def search_cmd(
    index_file: Annotated[Path, typer.Argument(help="Файл індексу (.bin або .json)")],
    query: Annotated[str, typer.Argument(help='Запит, напр.: дощ AND (ніч OR вечір) "темна ніч"')],
    scorer: Annotated[ScorerChoice, typer.Option("--scorer", "-s", help="Рейтинг")] = (
        ScorerChoice.bm25
    ),
    top: Annotated[int, typer.Option("--top", "-k", min=1, help="Скільки результатів")] = 10,
    data: Annotated[
        Path | None, typer.Option("--data", "-d", help="Папка з корпусом (для сніпетів)")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Вивести JSON у stdout")] = False,
    verbose: VerboseOpt = 0,
) -> None:
    """Ранжований пошук: таблиця результатів (або JSON зі --json)."""
    configure_logging(verbose)
    if not index_file.is_file():
        raise FindexError(f"Файл індексу не знайдено: {index_file}")
    if data is not None and not data.is_dir():
        raise FindexError(f"Папку з корпусом не знайдено: {data}")
    parse_query(query)  # швидка перевірка синтаксису ще до завантаження індексу

    scorer_name = _SCORER_NAMES[scorer]
    with open_index(index_file) as index:
        engine = SearchEngine(index, make_scorer(scorer_name))
        hits = run_query(engine, query, top, data, mark=(_MARK_START, _MARK_END))

    if as_json:
        payload: dict[str, object] = {
            "query": query,
            "scorer": scorer_name,
            "results": [_hit_to_dict(hit) for hit in hits],
        }
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _render_table(hits, query, scorer_name, with_snippets=data is not None)


@app.command("stats")
@_handle_errors
def stats_cmd(
    index_file: Annotated[Path, typer.Argument(help="Файл індексу (.bin або .json)")],
    top: Annotated[int, typer.Option("--top", "-n", min=1, help="Скільки топ-термінів")] = 10,
    as_json: Annotated[bool, typer.Option("--json", help="Вивести JSON у stdout")] = False,
    verbose: VerboseOpt = 0,
) -> None:
    """Статистика індексу: розміри, довжина документів, найчастіші терміни."""
    configure_logging(verbose)
    if not index_file.is_file():
        raise FindexError(f"Файл індексу не знайдено: {index_file}")
    with open_index(index_file) as index:
        stats = compute_stats(index, top)

    if as_json:
        typer.echo(json.dumps(asdict(stats), ensure_ascii=False, indent=2))
        return

    console = Console()
    summary = Table(title=f"Індекс {escape(str(index_file))}", show_header=False)
    summary.add_column("Показник")
    summary.add_column("Значення", justify="right")
    summary.add_row("Терміни", f"{stats.terms:,}")
    summary.add_row("Документи", f"{stats.docs:,}")
    summary.add_row("Середня довжина документа", f"{stats.avg_doc_length:.2f}")
    summary.add_row("Усього постінгів", f"{stats.total_postings:,}")
    summary.add_row("Позиції збережено", "так" if stats.has_positions else "ні")
    console.print(summary)

    top_table = Table(title=f"Топ-{len(stats.top_terms)} термінів за df")
    top_table.add_column("Термін")
    top_table.add_column("df", justify="right")
    for term, df in stats.top_terms:
        top_table.add_row(escape(term), f"{df:,}")
    console.print(top_table)
