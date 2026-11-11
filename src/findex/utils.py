import functools
import logging
import time

log = logging.getLogger("findex")


def timed(func):
    """Декоратор: логує, скільки мілісекунд виконувалась функція.

    functools.wraps зберігає ім'я та docstring оригінальної функції.
    Час логується навіть якщо функція кинула виняток.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.info("[timed] %s: %.2f ms", func.__qualname__, elapsed_ms)

    return wrapper
