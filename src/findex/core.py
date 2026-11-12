import bz2
import logging
from collections.abc import Callable, Iterator
from functools import cache
from pathlib import Path

from findex.errors import DocumentError

log = logging.getLogger("findex.core")

_PROGRESS_EVERY = 2000  # як часто (у рядках) повідомляти про прогрес читання


def corpus_size(data_dir: str | Path) -> int:
    """Сумарний розмір усіх .bz2 файлів корпусу в байтах (для смуги прогресу)."""
    return sum(path.stat().st_size for path in Path(data_dir).rglob("*.bz2"))


def iter_documents(
    data_dir: str | Path,
    on_bytes: Callable[[int], None] | None = None,
) -> Iterator[tuple[str, str]]:
    """Лінивий генератор документів корпусу: (doc_id, текст рядка).

    Обходить папку, знаходить стиснуті .bz2 файли (у стабільному, відсортованому
    порядку) та читає їх потоково, без розпакування на диск.

    on_bytes — необов'язковий колбек: скільки нових стиснутих байтів прочитано.
    Сума викликів дорівнює розміру прочитаних файлів (див. corpus_size).
    Пошкоджений файл не зупиняє обхід: попередження йде в лог.
    """
    for file_path in sorted(Path(data_dir).rglob("*.bz2")):
        try:
            file_size = file_path.stat().st_size
            with (
                file_path.open("rb") as raw,
                bz2.open(raw, "rt", encoding="utf-8", errors="ignore") as stream,
            ):
                reported = 0
                for line_num, line in enumerate(stream, 1):
                    yield f"{file_path.name}_line_{line_num}", line.strip()
                    if on_bytes is not None and line_num % _PROGRESS_EVERY == 0:
                        position = raw.tell()
                        on_bytes(position - reported)
                        reported = position
                if on_bytes is not None:
                    on_bytes(file_size - reported)
        except (OSError, EOFError, ValueError) as exc:
            log.warning("Помилка читання файлу %s: %s", file_path.name, exc)


@cache
def _find_file(data_dir: str, name: str) -> Path | None:
    """Шукає .bz2 файл за іменем у папці з даними (результат кешується)."""
    for file_path in Path(data_dir).rglob("*.bz2"):
        if file_path.name == name:
            return file_path
    return None


def read_document(data_dir: str | Path, doc_id: str) -> str:
    """Повертає текст документа за doc_id виду '<файл>.bz2_line_<N>'."""
    name, sep, number = doc_id.rpartition("_line_")
    if not sep or not number.isdigit():
        raise DocumentError(f"Невірний doc_id: {doc_id!r}")

    file_path = _find_file(str(data_dir), name)
    if file_path is None:
        raise DocumentError(f"Файл {name} не знайдено в {data_dir}")

    target = int(number)
    with bz2.open(file_path, "rt", encoding="utf-8", errors="ignore") as stream:
        for line_num, line in enumerate(stream, 1):
            if line_num == target:
                return line.strip()
    raise DocumentError(f"У файлі {name} немає рядка {target}")
