"""DuckDB schema. Idempotent — ``init_schema`` is safe to call on every connect."""

from __future__ import annotations

import duckdb

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS transactions (
    txn_fingerprint    VARCHAR PRIMARY KEY,
    institution        VARCHAR NOT NULL,
    account_type       VARCHAR NOT NULL,
    transaction_date   DATE    NOT NULL,
    post_date          DATE,
    description        VARCHAR NOT NULL,
    description_clean  VARCHAR NOT NULL,
    amount             DECIMAL(12, 2) NOT NULL,
    original_category  VARCHAR,
    unified_category   VARCHAR,
    source_file        VARCHAR NOT NULL,
    ingested_at        TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_txn_date     ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(unified_category);
CREATE INDEX IF NOT EXISTS idx_txn_inst     ON transactions(institution);

CREATE TABLE IF NOT EXISTS processing_log (
    file_hash      VARCHAR PRIMARY KEY,
    file_path      VARCHAR NOT NULL,
    institution    VARCHAR NOT NULL,
    account_type   VARCHAR NOT NULL,
    record_count   INTEGER NOT NULL,
    processed_at   TIMESTAMP NOT NULL
);
"""


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create tables and indexes if they don't already exist."""
    conn.execute(SCHEMA_DDL)
