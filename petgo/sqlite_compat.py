"""Compatibilidade SQLite para o deploy AWS.

As models usam BigInteger como PK com autoincrement. No SQLite, o
autoincrement de chave primaria so funciona com a coluna declarada como
INTEGER (nao BIGINT). Aqui registramos a compilacao de BigInteger como
INTEGER no dialeto SQLite, sem alterar o codigo das models (em MySQL
continua BIGINT normalmente).

Importar este modulo ANTES de criar as tabelas / a app.
"""
from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles


@compiles(BigInteger, "sqlite")
def _compile_biginteger_sqlite(type_, compiler, **kw):  # noqa: ANN001
    return "INTEGER"
