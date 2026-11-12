class FindexError(Exception):
    """Очікувана помилка: CLI показує її одним рядком, без стека викликів."""


class QuerySyntaxError(FindexError):
    """Запит не відповідає граматиці мови запитів."""


class MissingPositionsError(FindexError):
    """Для фразового пошуку потрібні позиції, а індекс збудовано без них."""


class IndexLoadError(FindexError):
    """Файл індексу пошкоджений або має невідомий формат."""


class DocumentError(FindexError):
    """Документ за doc_id не вдалося прочитати з корпусу."""
