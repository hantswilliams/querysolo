# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Every row of the brief's §3.7, plus nested types, through the coercion (D24)."""

import pytest

from querysolo.types import coerce

ROWS = [
    ("BOOLEAN", None, "boolean"),
    ("TINYINT", "INTEGER", "int"),
    ("SMALLINT", "INTEGER", "int"),
    ("INTEGER", None, "int"),
    ("UTINYINT", "INTEGER", "int"),
    ("USMALLINT", "INTEGER", "int"),
    ("BIGINT", None, "long"),
    ("UINTEGER", "BIGINT", "long"),
    ("UBIGINT", "DECIMAL(20,0)", "decimal(20, 0)"),
    ("HUGEINT", "DECIMAL(38,0)", "decimal(38, 0)"),
    ("UHUGEINT", "DECIMAL(38,0)", "decimal(38, 0)"),
    ("FLOAT", None, "float"),
    ("DOUBLE", None, "double"),
    ("DECIMAL(18,3)", None, "decimal(18, 3)"),
    ("VARCHAR", None, "string"),
    ("ENUM('a', 'b')", "VARCHAR", "string"),
    ("JSON", "VARCHAR", "string"),
    ("BIT", "VARCHAR", "string"),
    ("UNION(a INTEGER, b VARCHAR)", "VARCHAR", "string"),
    ("INTERVAL", "VARCHAR", "string"),
    ("TIME WITH TIME ZONE", "VARCHAR", "string"),
    ("BLOB", None, "binary"),
    ("DATE", None, "date"),
    ("TIME", None, "time"),
    ("TIMESTAMP", None, "timestamp"),
    ("TIMESTAMP_S", "TIMESTAMP", "timestamp"),
    ("TIMESTAMP_MS", "TIMESTAMP", "timestamp"),
    ("TIMESTAMP_NS", "TIMESTAMP", "timestamp"),
    ("TIMESTAMP WITH TIME ZONE", None, "timestamptz"),
    ("UUID", None, "uuid"),
    ("INTEGER[]", None, "list<int>"),
    ("UTINYINT[]", "INTEGER[]", "list<int>"),
    ("INTEGER[3]", "INTEGER[]", "list<int>"),
    (
        'STRUCT(a UTINYINT, "b c" VARCHAR[])',
        'STRUCT("a" INTEGER, "b c" VARCHAR[])',
        "struct<a: int, b c: list<string>>",
    ),
    ("MAP(VARCHAR, HUGEINT)", "MAP(VARCHAR, DECIMAL(38,0))", "map<string, decimal(38, 0)>"),
    (
        "STRUCT(x INTEGER, y STRUCT(z TIMESTAMP_NS))",
        'STRUCT("x" INTEGER, "y" STRUCT("z" TIMESTAMP))',
        "struct<x: int, y: struct<z: timestamp>>",
    ),
    ("STRUCT(x INTEGER, y VARCHAR)", None, "struct<x: int, y: string>"),
]


@pytest.mark.parametrize(("duckdb_type", "cast_to", "iceberg"), ROWS)
def test_coercion(duckdb_type, cast_to, iceberg) -> None:
    c = coerce(duckdb_type)
    assert c.cast_to == cast_to
    assert c.iceberg_type == iceberg


def test_lossy_casts_carry_a_note() -> None:
    assert "lossy" in coerce("TIMESTAMP_NS").note
    assert "lossy" in coerce("ENUM('a')").note
    assert "widened" in coerce("UTINYINT").note
    assert coerce("INTEGER").note == ""
    assert coerce("STRUCT(x INTEGER, y VARCHAR)").note == ""
