import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from findex.index import Index


@runtime_checkable
class Scorer(Protocol):
    """Протокол (duck typing): будь-який об'єкт із методом score() є Scorer.

    tf      — скільки разів термін трапляється в документі
    df      — у скількох документах корпусу трапляється термін
    doc_len — довжина документа в токенах
    index   — індекс (звідси беруться num_docs та avg_doc_length)
    """

    def score(self, tf: int, df: int, doc_len: int, index: "Index") -> float: ...


@dataclass(frozen=True)
class TfIdf:
    """TF-IDF: (1 + ln tf) * idf / sqrt(довжина документа).

    ln tf — «стеля» для повторень; ділення на sqrt(довжини) — нормалізація,
    щоб короткі документи не програвали довгим.
    """

    def score(self, tf: int, df: int, doc_len: int, index: "Index") -> float:
        if tf <= 0 or df <= 0:
            return 0.0
        idf = math.log(1 + index.num_docs / df)
        return (1 + math.log(tf)) * idf / math.sqrt(max(doc_len, 1))


@dataclass(frozen=True)
class BM25:
    """BM25 із параметрами k1 (насичення tf) та b (нормалізація довжини)."""

    k1: float = 1.5
    b: float = 0.75

    def score(self, tf: int, df: int, doc_len: int, index: "Index") -> float:
        if tf <= 0 or df <= 0:
            return 0.0
        n = index.num_docs
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        avg_len = index.avg_doc_length or 1.0
        length_norm = 1 - self.b + self.b * doc_len / avg_len
        return idf * tf * (self.k1 + 1) / (tf + self.k1 * length_norm)
