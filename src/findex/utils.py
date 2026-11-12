import functools
import logging
import time
from collections.abc import Callable

log = logging.getLogger("findex")


def timed[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Декоратор: логує (рівень INFO), скільки мілісекунд виконувалась функція.

    functools.wraps зберігає ім'я та docstring оригіналу. Час логується і тоді,
    коли функція кинула виняток.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.info("[timed] %s: %.2f ms", func.__qualname__, elapsed_ms)

    return wrapper
