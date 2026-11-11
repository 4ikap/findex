import re
from bisect import bisect_left, bisect_right
from typing import Iterable, Tuple


def best_snippet(
    text: str,
    terms: Iterable[str],
    window: int = 80,
    mark: Tuple[str, str] = ("**", "**"),
) -> str:
    """Вікно ±window символів навколо найкращого входження термів із підсвіткою.

    «Найкраще» входження — те, поруч із яким (в межах вікна) зустрічається
    найбільше РІЗНИХ термів запиту.
    """
    unique_terms = sorted({t for t in terms if t}, key=len, reverse=True)
    if not unique_terms:
        return text[: 2 * window]

    pattern = re.compile(
        r"(?<!\w)(" + "|".join(re.escape(t) for t in unique_terms) + r")(?!\w)",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return text[: 2 * window] + ("…" if len(text) > 2 * window else "")

    starts = [m.start() for m in matches]

    def distinct_nearby(i: int) -> int:
        lo = bisect_left(starts, starts[i] - window)
        hi = bisect_right(starts, starts[i] + window)
        return len({matches[j].group().lower() for j in range(lo, hi)})

    best = max(range(len(matches)), key=lambda i: (distinct_nearby(i), -i))
    left = max(0, matches[best].start() - window)
    right = min(len(text), matches[best].end() + window)

    fragment = text[left:right]
    highlighted = pattern.sub(lambda m: mark[0] + m.group() + mark[1], fragment)
    return ("…" if left > 0 else "") + highlighted + ("…" if right < len(text) else "")
