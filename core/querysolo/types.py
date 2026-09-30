# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""DuckDB types to Iceberg types (brief D24, §3.7). Import inspects what DuckDB's reader
inferred, casts what Iceberg cannot hold to the nearest thing it can, and tells the user
where that lost something. Nested types are handled element by element."""

from __future__ import annotations

from dataclasses import dataclass, field

# DuckDB type -> (cast to this DuckDB type or None, Iceberg type, note or None)
SCALARS: dict[str, tuple[str | None, str, str | None]] = {
    "BOOLEAN": (None, "boolean", None),
    "TINYINT": ("INTEGER", "int", None),
    "SMALLINT": ("INTEGER", "int", None),
    "INTEGER": (None, "int", None),
    "UTINYINT": ("INTEGER", "int", "unsigned widened"),
    "USMALLINT": ("INTEGER", "int", "unsigned widened"),
    "BIGINT": (None, "long", None),
    "UINTEGER": ("BIGINT", "long", "unsigned widened"),
    "UBIGINT": ("DECIMAL(20,0)", "decimal(20, 0)", "unsigned 64-bit becomes decimal(20, 0)"),
    "HUGEINT": ("DECIMAL(38,0)", "decimal(38, 0)", "128-bit integer becomes decimal(38, 0)"),
    "UHUGEINT": ("DECIMAL(38,0)", "decimal(38, 0)", "128-bit integer becomes decimal(38, 0)"),
    "FLOAT": (None, "float", None),
    "DOUBLE": (None, "double", None),
    "VARCHAR": (None, "string", None),
    "BLOB": (None, "binary", None),
    "DATE": (None, "date", None),
    "TIME": (None, "time", None),
    "TIMESTAMP": (None, "timestamp", None),
    "TIMESTAMP_S": ("TIMESTAMP", "timestamp", "seconds become microseconds"),
    "TIMESTAMP_MS": ("TIMESTAMP", "timestamp", "milliseconds become microseconds"),
    "TIMESTAMP_NS": ("TIMESTAMP", "timestamp", "nanoseconds truncated to microseconds; lossy"),
    "TIMESTAMP WITH TIME ZONE": (None, "timestamptz", None),
    "UUID": (None, "uuid", None),
}
LOSSY_TO_STRING = ("ENUM", "JSON", "BIT", "UNION", "INTERVAL", "TIME WITH TIME ZONE")


@dataclass
class Coercion:
    cast_to: str | None
    """A DuckDB type to cast the column to, or None when the reader's type is already fine."""
    iceberg_type: str
    notes: list[str] = field(default_factory=list)

    @property
    def note(self) -> str:
        return "; ".join(self.notes)


# -- a small parser for DuckDB's type strings -----------------------------------------


class _Parser:
    def __init__(self, text: str) -> None:
        self.s = text.strip()
        self.i = 0

    def parse(self) -> tuple:
        node = self._type()
        self._ws()
        if self.i != len(self.s):
            raise ValueError(f"unparsed type text: {self.s[self.i :]!r} in {self.s!r}")
        return node

    def _ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def _peek(self) -> str:
        self._ws()
        return self.s[self.i] if self.i < len(self.s) else ""

    def _expect(self, ch: str) -> None:
        if self._peek() != ch:
            raise ValueError(f"expected {ch!r} at {self.i} in {self.s!r}")
        self.i += 1

    def _word(self) -> str:
        self._ws()
        start = self.i
        while self.i < len(self.s) and self.s[self.i] not in "([]),":
            self.i += 1
        return self.s[start : self.i].strip()

    def _number(self) -> int:
        self._ws()
        start = self.i
        while self.i < len(self.s) and self.s[self.i].isdigit():
            self.i += 1
        return int(self.s[start : self.i])

    def _name(self) -> str:
        self._ws()
        if self.s[self.i] == '"':
            end = self.s.index('"', self.i + 1)
            name, self.i = self.s[self.i + 1 : end], end + 1
            return name
        start = self.i
        while self.i < len(self.s) and not self.s[self.i].isspace():
            self.i += 1
        return self.s[start : self.i]

    def _skip_parens(self) -> None:
        self._expect("(")
        depth = 1
        while depth:
            ch = self.s[self.i]
            if ch == "'":
                self.i = self.s.index("'", self.i + 1) + 1
                continue
            depth += ch == "("
            depth -= ch == ")"
            self.i += 1

    def _fields(self) -> list[tuple[str, tuple]]:
        self._expect("(")
        fields = []
        while True:
            name = self._name()
            fields.append((name, self._type()))
            if self._peek() == ",":
                self.i += 1
                continue
            self._expect(")")
            return fields

    def _type(self) -> tuple:
        word = self._word().upper()
        if word == "STRUCT":
            node: tuple = ("struct", self._fields())
        elif word == "MAP":
            self._expect("(")
            key = self._type()
            self._expect(",")
            value = self._type()
            self._expect(")")
            node = ("map", key, value)
        elif word == "UNION":
            self._fields()
            node = ("scalar", "UNION")
        elif word == "ENUM":
            self._skip_parens()
            node = ("scalar", "ENUM")
        elif word == "DECIMAL":
            self._expect("(")
            precision = self._number()
            self._expect(",")
            scale = self._number()
            self._expect(")")
            node = ("decimal", precision, scale)
        else:
            node = ("scalar", word)
        while self._peek() == "[":
            self.i += 1
            fixed = self._peek().isdigit()
            if fixed:
                self._number()
            self._expect("]")
            node = ("list", node, fixed)
        return node


def parse(duckdb_type: str) -> tuple:
    return _Parser(duckdb_type).parse()


def render(node: tuple) -> str:
    kind = node[0]
    if kind == "scalar":
        return node[1]
    if kind == "decimal":
        return f"DECIMAL({node[1]},{node[2]})"
    if kind == "list":
        return f"{render(node[1])}[]"
    if kind == "struct":
        return "STRUCT(" + ", ".join(f'"{name}" {render(t)}' for name, t in node[1]) + ")"
    if kind == "map":
        return f"MAP({render(node[1])}, {render(node[2])})"
    raise ValueError(kind)


def _coerce(node: tuple, notes: list[str]) -> tuple[tuple, str, bool]:
    """Returns (node after coercion, Iceberg type, whether anything changed)."""
    kind = node[0]
    if kind == "scalar":
        name = node[1]
        if name in SCALARS:
            cast_to, iceberg, note = SCALARS[name]
            if note:
                notes.append(note)
            return (("scalar", cast_to) if cast_to else node), iceberg, cast_to is not None
        if name in LOSSY_TO_STRING or name.startswith(LOSSY_TO_STRING):
            notes.append(f"{name.lower()} becomes string; lossy")
            return ("scalar", "VARCHAR"), "string", True
        notes.append(f"{name.lower()} has no Iceberg type; becomes string")
        return ("scalar", "VARCHAR"), "string", True
    if kind == "decimal":
        return node, f"decimal({node[1]}, {node[2]})", False
    if kind == "list":
        inner, iceberg, changed = _coerce(node[1], notes)
        if node[2]:
            notes.append("fixed-size array becomes list")
        return ("list", inner, False), f"list<{iceberg}>", changed or node[2]
    if kind == "struct":
        fields, parts, changed = [], [], False
        for name, t in node[1]:
            inner, iceberg, c = _coerce(t, notes)
            fields.append((name, inner))
            parts.append(f"{name}: {iceberg}")
            changed = changed or c
        return ("struct", fields), "struct<" + ", ".join(parts) + ">", changed
    if kind == "map":
        key, key_ib, kc = _coerce(node[1], notes)
        value, value_ib, vc = _coerce(node[2], notes)
        return ("map", key, value), f"map<{key_ib}, {value_ib}>", kc or vc
    raise ValueError(kind)


def coerce(duckdb_type: str) -> Coercion:
    notes: list[str] = []
    node, iceberg, changed = _coerce(parse(duckdb_type), notes)
    return Coercion(cast_to=render(node) if changed else None, iceberg_type=iceberg, notes=notes)
