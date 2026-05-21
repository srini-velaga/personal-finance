"""End-to-end ingest: scan a folder, match profiles, dedupe, insert into DuckDB.

The pipeline is intentionally synchronous and single-pass: there's no
threading or async here. DuckDB is fast enough on a single connection that
we'd be optimizing the wrong thing.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from personal_finance.ingest.csv_parser import parse_csv
from personal_finance.ingest.fingerprint import file_hash
from personal_finance.ingest.profile import Profile, load_profiles, match_profile
from personal_finance.models import Transaction


@dataclass
class IngestResult:
    """Summary of an ``ingest_folder`` run, suitable for returning as JSON."""

    files_scanned: int = 0
    files_ingested: int = 0
    files_skipped_already_processed: int = 0
    files_skipped_no_profile: int = 0
    transactions_inserted: int = 0
    transactions_duplicate: int = 0
    files: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "files_scanned": self.files_scanned,
            "files_ingested": self.files_ingested,
            "files_skipped_already_processed": self.files_skipped_already_processed,
            "files_skipped_no_profile": self.files_skipped_no_profile,
            "transactions_inserted": self.transactions_inserted,
            "transactions_duplicate": self.transactions_duplicate,
            "files": self.files,
        }


def _read_headers(path: Path) -> list[str] | None:
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            return next(reader, None)
    except (OSError, csv.Error):
        return None


def _already_processed(conn: duckdb.DuckDBPyConnection, fhash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM processing_log WHERE file_hash = ?", [fhash]
    ).fetchone()
    return row is not None


def _insert_transactions(
    conn: duckdb.DuckDBPyConnection, txns: list[Transaction]
) -> tuple[int, int]:
    """Insert with dedup on the PK. Returns (inserted, duplicate)."""
    inserted = 0
    duplicate = 0
    for t in txns:
        existed = conn.execute(
            "SELECT 1 FROM transactions WHERE txn_fingerprint = ?",
            [t.txn_fingerprint],
        ).fetchone()
        if existed:
            duplicate += 1
            continue
        conn.execute(
            """
            INSERT INTO transactions (
                txn_fingerprint, institution, account_type,
                transaction_date, post_date,
                description, description_clean, amount,
                original_category, unified_category,
                source_file, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                t.txn_fingerprint,
                t.institution,
                t.account_type,
                t.transaction_date,
                t.post_date,
                t.description,
                t.description_clean,
                t.amount,
                t.original_category,
                t.unified_category,
                t.source_file,
                t.ingested_at,
            ],
        )
        inserted += 1
    return inserted, duplicate


def _log_file(
    conn: duckdb.DuckDBPyConnection,
    fhash: str,
    path: Path,
    profile: Profile,
    record_count: int,
) -> None:
    conn.execute(
        """
        INSERT INTO processing_log (
            file_hash, file_path, institution, account_type,
            record_count, processed_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            fhash,
            str(path),
            profile.institution,
            profile.account_type,
            record_count,
            datetime.now(UTC),
        ],
    )


def ingest_folder(
    folder: str | Path,
    conn: duckdb.DuckDBPyConnection,
    profiles: list[Profile] | None = None,
) -> IngestResult:
    """Scan ``folder`` recursively for CSVs and ingest matching files.

    ``profiles`` defaults to the union of shipped + user profiles. Pass an
    explicit list in tests to avoid touching the user's data directory.
    """
    folder = Path(folder).expanduser().resolve()
    if profiles is None:
        profiles = load_profiles()

    result = IngestResult()

    for path in sorted(folder.rglob("*.csv")):
        result.files_scanned += 1
        file_entry: dict = {"path": str(path)}

        headers = _read_headers(path)
        if headers is None:
            file_entry["status"] = "skipped_unreadable"
            result.files.append(file_entry)
            continue

        profile = match_profile(headers, profiles)
        if profile is None:
            file_entry["status"] = "skipped_no_profile"
            result.files_skipped_no_profile += 1
            result.files.append(file_entry)
            continue
        file_entry["profile"] = profile.name

        fhash = file_hash(path)
        if _already_processed(conn, fhash):
            file_entry["status"] = "skipped_already_processed"
            result.files_skipped_already_processed += 1
            result.files.append(file_entry)
            continue

        txns = parse_csv(path, profile)
        inserted, duplicate = _insert_transactions(conn, txns)
        _log_file(conn, fhash, path, profile, len(txns))

        file_entry["status"] = "ingested"
        file_entry["transactions_inserted"] = inserted
        file_entry["transactions_duplicate"] = duplicate
        result.files_ingested += 1
        result.transactions_inserted += inserted
        result.transactions_duplicate += duplicate
        result.files.append(file_entry)

    return result
