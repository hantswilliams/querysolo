# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""DuckDB's pushed-down scan filters, as EXPLAIN renders them, into pyiceberg expressions
for manifest pruning (brief D20). What the parser does not understand is dropped, which can
only make the estimate larger: the safe direction. ``pruning`` records how much was kept.

Renderings seen on DuckDB 1.5.5: ``id>500 AND id<900``; ``customer='c1'``;
``(o_comment !~~ '%special%requests%')``; ``(NOT prefix(p_type, 'MEDIUM POLISHED'))``;
``("substring"(c_phone, 1, 2) IN ('13', '31'))``;
``d>='2026-03-01'::DATE``; ``optional: customer IN ('c1', 'c2')``; ``optional: id=5 OR id=7``;
``(customer IS NOT NULL)``; ``flag``; ``customer>='c' AND customer<'d'`` for ``LIKE 'c%'``;
``suffix(customer, '1')`` for ``LIKE '%1'``; and a list of strings when filters touch more
than one column."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pyiceberg.expressions import (
    AlwaysTrue,
    And,
    BooleanExpression,
    EqualTo,
    GreaterThan,
    GreaterThanOrEqual,
    In,
    IsNull,
    LessThan,
    LessThanOrEqual,
    Not,
    NotEqualTo,
    NotIn,
    NotNull,
    Or,
    StartsWith,
)

_COMPARISON = re.compile(r'^("?[\w ]+"?)\s*(>=|<=|!=|<>|=|>|<)\s*(.+)$')
_NULL_CHECK = re.compile(r'^("?[\w ]+"?)\s+IS\s+(NOT\s+)?NULL$', re.IGNORECASE)
_IN_LIST = re.compile(r'^("?[\w ]+"?)\s+(NOT\s+)?IN\s*\((.*)\)$', re.IGNORECASE)
_FUNCTION = re.compile(r'^(prefix|suffix|contains)\(("?[\w ]+"?),\s*(\'.*\')\)$', re.IGNORECASE)
_IDENTIFIER = re.compile(r'^"?[\w ]+"?$')
_LIKE = re.compile(r'^("?[\w ]+"?)\s*(!?~~\*?)\s*(\'.*\')$')
_FUNCTION_LHS = re.compile(r'^"?\w+"?\(.*\)\s*(NOT\s+IN|IN|>=|<=|!=|<>|=|>|<)\s', re.IGNORECASE)


@dataclass
class Translation:
    expression: BooleanExpression = field(default_factory=AlwaysTrue)
    understood: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)

    @property
    def pruning(self) -> str:
        if not self.dropped:
            return "full"
        return "partial" if self.understood else "none"


def _split_top_level(text: str, keyword: str) -> list[str]:
    parts, depth, quote, start, i = [], 0, False, 0, 0
    token = f" {keyword} "
    while i < len(text):
        ch = text[i]
        if ch == "'":
            quote = not quote
        elif not quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0 and text[i : i + len(token)].upper() == token:
                parts.append(text[start:i])
                i += len(token)
                start = i
                continue
        i += 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def _strip_parens(text: str) -> str:
    text = text.strip()
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        for i, ch in enumerate(text):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and i < len(text) - 1:
                return text
        text = text[1:-1].strip()
    return text


def _column(text: str) -> str:
    return text.strip().strip('"')


def _literal(text: str):
    text = text.strip()
    text = re.sub(r"::[\w ]+(\([^)]*\))?$", "", text).strip()  # '2026-03-01'::DATE
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1].replace("''", "'")
    if text.upper() in ("TRUE", "FALSE"):
        return text.upper() == "TRUE"
    if text.upper() == "NULL":
        raise ValueError("null literal")
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d*(e-?\d+)?|-?\d*\.\d+(e-?\d+)?", text, re.IGNORECASE):
        return float(text)
    raise ValueError(f"unrecognised literal {text!r}")


def _simple(text: str) -> BooleanExpression:
    """One comparison, null check, IN list, bare boolean or string function."""
    text = _strip_parens(text)
    if text.upper().startswith("NOT ") and not _IDENTIFIER.match(text[4:].strip()):
        inner = _simple(text[4:])
        return AlwaysTrue() if isinstance(inner, AlwaysTrue) else Not(inner)
    if _LIKE.match(text) or _FUNCTION_LHS.match(text):
        return AlwaysTrue()  # LIKE, and functions of a column: understood, prune nothing
    if match := _NULL_CHECK.match(text):
        return NotNull(_column(match[1])) if match[2] else IsNull(_column(match[1]))
    if match := _IN_LIST.match(text):
        values = [_literal(v) for v in _split_top_level(match[3].replace(",", " , "), ",")]
        return NotIn(_column(match[1]), values) if match[2] else In(_column(match[1]), values)
    if match := _FUNCTION.match(text):
        function, column, value = match[1].lower(), _column(match[2]), _literal(match[3])
        if function == "prefix":
            return StartsWith(column, value)
        return AlwaysTrue()  # suffix and contains prune nothing, but they are understood
    if match := _COMPARISON.match(text):
        column, op, value = _column(match[1]), match[2], _literal(match[3])
        return {
            ">=": GreaterThanOrEqual,
            "<=": LessThanOrEqual,
            "!=": NotEqualTo,
            "<>": NotEqualTo,
            "=": EqualTo,
            ">": GreaterThan,
            "<": LessThan,
        }[op](column, value)
    if _IDENTIFIER.match(text):
        return EqualTo(_column(text), True)
    if text.upper().startswith("NOT ") and _IDENTIFIER.match(text[4:].strip()):
        return EqualTo(_column(text[4:]), False)
    raise ValueError(f"unrecognised filter {text!r}")


def _conjunct(text: str) -> BooleanExpression:
    text = _strip_parens(text.strip())
    if text.lower().startswith("optional:"):
        text = text[len("optional:") :].strip()
    disjuncts = _split_top_level(text, "OR")
    if len(disjuncts) > 1:
        return Or(*[_simple(d) for d in disjuncts])
    return _simple(text)


def translate(filters: str | list[str] | None) -> Translation:
    result = Translation()
    if not filters:
        return result
    raw = filters if isinstance(filters, list) else [filters]
    conjuncts = [c for item in raw for c in _split_top_level(item, "AND")]
    expressions: list[BooleanExpression] = []
    for conjunct in conjuncts:
        try:
            expressions.append(_conjunct(conjunct))
            result.understood.append(conjunct)
        except (ValueError, KeyError):
            result.dropped.append(conjunct)
    expressions = [e for e in expressions if not isinstance(e, AlwaysTrue)]
    if expressions:
        result.expression = expressions[0] if len(expressions) == 1 else And(*expressions)
    return result
