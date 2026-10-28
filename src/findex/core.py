import bz2
from pathlib import Path
from typing import Generator, Tuple


def iter_documents(data_dir: str | Path) -> Generator[Tuple[str, str], None, None]:
    """Генератор, який обходить папку з даними, знаходить стиснуті .bz2 файли

    та повертає документи (рядки) по одному у форматі кортежу:
    (ідентифікатор_документа, вміст_тексту).
    """
    data_path = Path(data_dir)

    # Шукаємо всі .bz2 файли у папці data
    for file_path in data_path.rglob("*.bz2"):
        try:
            # Відкриваємо bz2 архів у текстовому режимі без повного розпакування на диск
            with bz2.open(
                file_path, "rt", encoding="utf-8", errors="ignore"
            ) as f:
                for line_num, line in enumerate(f, 1):
                    doc_id = f"{file_path.name}_line_{line_num}"
                    yield doc_id, line.strip()
        except Exception as e:
            print(f"Помилка читання файлу {file_path.name}: {e}")


if __name__ == "__main__":
  # Оскільки core.py лежить у src/findex/, а папка data — в корені проєкту (findex/data),
  # піднімемося на два рівня вгору, щоб знайти папку data:
  data_path = Path(__file__).resolve().parent.parent.parent / "data"

  print(f"Шукаємо дані в: {data_path}")

  # Перевіряємо роботу генератора
  count = 0
  for doc_id, text in iter_documents(data_path):
    print(f"ID: {doc_id}")
    print(f"Текст: {text[:100]}...")  # Виведе перші 100 символів рядка
    count += 1
    if count >= 3:  # Виведемо лише перші 3 документи для перевірки
      break