"""Мова запитів: python AND (async OR await) NOT java "event loop"

Граматика (рекурсивний спуск, пріоритет: NOT/унарний > AND > OR):

    or_expr  := and_expr ( "OR" and_expr )*
    and_expr := unary ( ("AND" | "NOT" | <неявний AND>) unary )*
    unary    := "NOT" unary | atom
    atom     := "(" or_expr ")" | WORD | "фраза в лапках"

Оператори пишуться ВЕЛИКИМИ літерами (щоб слова and/or/not лишалися звичайними термінами).
"A NOT B" означає "A AND (NOT B)".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from findex.errors import MissingPositionsError, QuerySyntaxError
from findex.index import Index
from findex.tokenize import tokenize

# --- Вузли дерева запиту ---


class Node:
    """Базовий вузол. Оператори &, |, ~ будують дерево."""

    def __and__(self, other: Node) -> And:
        return And(self, other)

    def __or__(self, other: Node) -> Or:
        return Or(self, other)

    def __invert__(self) -> Not:
        return Not(self)

    def evaluate(self, index: Index) -> set[str]:
        """Повертає множину doc_id, що задовольняють вузол."""
        raise NotImplementedError

    def terms(self) -> list[str]:
        """Терміни, що додатно впливають на рейтинг (без тих, що під NOT)."""
        raise NotImplementedError


@dataclass(frozen=True)
class Term(Node):
    text: str

    def evaluate(self, index: Index) -> set[str]:
        return {p.doc_id for p in index.get(self.text, ())}

    def terms(self) -> list[str]:
        return [self.text]


@dataclass(frozen=True)
class Phrase(Node):
    words: tuple[str, ...]

    def evaluate(self, index: Index) -> set[str]:
        if not index.has_positions:
            raise MissingPositionsError(
                "Індекс збудовано без позицій. Перебудуйте його: findex index --positions"
            )
        # для кожного слова: doc_id -> позиції
        per_word = [{p.doc_id: p.positions for p in index.get(word, ())} for word in self.words]
        candidates = set(per_word[0]).intersection(*per_word[1:])
        result: set[str] = set()
        for doc_id in candidates:
            # можливі початки фрази: позиції першого слова, узгоджені з наступними
            starts = set(per_word[0][doc_id])
            for offset, word_positions in enumerate(per_word[1:], start=1):
                starts &= {pos - offset for pos in word_positions[doc_id]}
                if not starts:
                    break
            if starts:
                result.add(doc_id)
        return result

    def terms(self) -> list[str]:
        return list(self.words)


@dataclass(frozen=True)
class And(Node):
    left: Node
    right: Node

    def evaluate(self, index: Index) -> set[str]:
        return self.left.evaluate(index) & self.right.evaluate(index)

    def terms(self) -> list[str]:
        return self.left.terms() + self.right.terms()


@dataclass(frozen=True)
class Or(Node):
    left: Node
    right: Node

    def evaluate(self, index: Index) -> set[str]:
        return self.left.evaluate(index) | self.right.evaluate(index)

    def terms(self) -> list[str]:
        return self.left.terms() + self.right.terms()


@dataclass(frozen=True)
class Not(Node):
    child: Node

    def evaluate(self, index: Index) -> set[str]:
        return set(index.meta.keys() - self.child.evaluate(index))

    def terms(self) -> list[str]:
        return []


# --- Лексер ---

_TOKEN_RE = re.compile(r'"([^"]*)"|(\()|(\))|([^\s()"]+)')


def _lex(query: str) -> list[tuple[str, str]]:
    if query.count('"') % 2:
        raise QuerySyntaxError("Незакриті лапки у запиті")
    tokens: list[tuple[str, str]] = []
    for match in _TOKEN_RE.finditer(query):
        phrase, lparen, rparen, word = match.groups()
        if phrase is not None:
            tokens.append(("PHRASE", phrase))
        elif lparen:
            tokens.append(("LP", "("))
        elif rparen:
            tokens.append(("RP", ")"))
        elif word in ("AND", "OR", "NOT"):
            tokens.append((word, word))
        else:
            tokens.append(("WORD", word))
    return tokens


def _make_leaf(text: str) -> Node:
    """Нормалізує слово/фразу тим самим токенізатором, що й індекс."""
    tokens = list(tokenize(text))
    if not tokens:
        raise QuerySyntaxError(f"Немає придатних для пошуку слів у {text!r}")
    if len(tokens) == 1:
        return Term(tokens[0])
    return Phrase(tuple(tokens))


# --- Парсер (рекурсивний спуск) ---


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> str | None:
        return self.tokens[self.pos][0] if self.pos < len(self.tokens) else None

    def _next(self) -> tuple[str, str]:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def parse(self) -> Node:
        if not self.tokens:
            raise QuerySyntaxError("Порожній запит")
        node = self._or()
        if self.pos < len(self.tokens):
            raise QuerySyntaxError(f"Неочікуваний токен {self.tokens[self.pos][1]!r}")
        return node

    def _or(self) -> Node:
        node = self._and()
        while self._peek() == "OR":
            self._next()
            node = Or(node, self._and())
        return node

    def _and(self) -> Node:
        node = self._unary()
        while True:
            kind = self._peek()
            if kind == "AND":
                self._next()
                node = And(node, self._unary())
            elif kind == "NOT":
                self._next()
                node = And(node, Not(self._unary()))
            elif kind in ("WORD", "PHRASE", "LP"):  # неявний AND
                node = And(node, self._unary())
            else:
                return node

    def _unary(self) -> Node:
        if self._peek() == "NOT":
            self._next()
            return Not(self._unary())
        return self._atom()

    def _atom(self) -> Node:
        kind = self._peek()
        if kind is None:
            raise QuerySyntaxError("Несподіваний кінець запиту")
        if kind == "LP":
            self._next()
            node = self._or()
            if self._peek() != "RP":
                raise QuerySyntaxError("Відсутня закриваюча дужка )")
            self._next()
            return node
        if kind in ("WORD", "PHRASE"):
            return _make_leaf(self._next()[1])
        raise QuerySyntaxError(f"Неочікуваний токен {self.tokens[self.pos][1]!r}")


def parse_query(query: str) -> Node:
    """Перетворює рядок запиту на дерево вузлів."""
    return _Parser(_lex(query)).parse()
