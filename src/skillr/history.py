"""Selection history store using DuckDB for efficient time-windowed queries."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from .config import ensure_plugin_data_dir
from .models import SelectionRecord

logger = logging.getLogger(__name__)


class SelectionHistoryStore:
    """DuckDB-backed selection history store.

    Database: ${CLAUDE_PLUGIN_DATA}/selection_history.duckdb
    Table schema:
        intent_hash    — SHA256 of the original intent text
        selected_skill — skill name the user selected
        rejected_skills — DuckDB VARCHAR[] of rejected skill names
        created_at     — TIMESTAMP of when selection was recorded
    Ordering:       — by DuckDB implicit rowid (insertion order)
    """

    DB_NAME = "selection_history.duckdb"

    def __init__(self) -> None:
        self._db_path = ensure_plugin_data_dir() / self.DB_NAME
        self._con: duckdb.DuckDBPyConnection | None = None
        self._ensure_table()
        self._migrate_if_needed()

    def _conn(self) -> duckdb.DuckDBPyConnection:
        """Get or create a DuckDB connection."""
        if self._con is None:
            self._con = duckdb.connect(str(self._db_path))
        return self._con

    def _ensure_table(self) -> None:
        """Create the selection_history table and indexes if they don't exist."""
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS selection_history (
                intent_hash    VARCHAR,
                selected_skill VARCHAR,
                rejected_skills VARCHAR[],
                created_at     TIMESTAMP
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sel_skill ON selection_history(selected_skill)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sel_created ON selection_history(created_at)")

    def _migrate_if_needed(self) -> None:
        """Migrate data from JSONL to DuckDB if the JSONL file exists and is non-empty."""
        jsonl_path = ensure_plugin_data_dir() / "selection_history.jsonl"
        if not jsonl_path.exists() or jsonl_path.stat().st_size == 0:
            return

        # Check if DuckDB table already has data (avoid re-migration)
        count = self._conn().execute("SELECT COUNT(*) FROM selection_history").fetchone()[0]
        if count > 0:
            # Already migrated — rename JSONL as backup
            bak_path = jsonl_path.with_suffix(".bak")
            jsonl_path.rename(bak_path)
            return

        migrated = self.migrate_from_jsonl(jsonl_path)
        if migrated > 0:
            bak_path = jsonl_path.with_suffix(".bak")
            jsonl_path.rename(bak_path)

    def migrate_from_jsonl(self, jsonl_path: Path) -> int:
        """Migrate records from a JSONL file into DuckDB.

        Args:
            jsonl_path: Path to the JSONL file to migrate.

        Returns:
            Number of records successfully migrated.
        """
        conn = self._conn()
        migrated = 0

        try:
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        record = SelectionRecord.model_validate(data)
                        conn.execute(
                            """
                            INSERT INTO selection_history
                                (intent_hash, selected_skill, rejected_skills, created_at)
                            VALUES (?, ?, ?, ?)
                            """,
                            [
                                record.intent_hash,
                                record.selected_skill,
                                record.rejected_skills,
                                datetime.fromisoformat(record.timestamp),
                            ],
                        )
                        migrated += 1
                    except Exception:
                        continue
        except Exception:
            pass

        return migrated

    def add_record(self, record: SelectionRecord) -> None:
        """Insert a selection record into DuckDB.

        Silently passes on write errors (non-blocking).
        """
        try:
            conn = self._conn()
            conn.execute(
                """
                INSERT INTO selection_history
                    (intent_hash, selected_skill, rejected_skills, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    record.intent_hash,
                    record.selected_skill,
                    record.rejected_skills,
                    datetime.fromisoformat(record.timestamp),
                ],
            )
        except Exception as exc:
            # Non-blocking — log for operator diagnostics (ADV-002)
            logger.warning(
                "SelectionHistoryStore: failed to record selection '%s' for skill '%s': %s",
                record.intent_hash[:8],
                record.selected_skill,
                exc,
            )

    def get_all_records(self) -> list[SelectionRecord]:
        """Load and return all selection records, ordered by insertion order."""
        try:
            conn = self._conn()
            rows = conn.execute(
                """
                SELECT intent_hash, selected_skill, rejected_skills, created_at
                FROM selection_history
                ORDER BY rowid ASC
                """
            ).fetchall()
            return [
                SelectionRecord(
                    intent_hash=row[0],
                    selected_skill=row[1],
                    rejected_skills=list(row[2]) if row[2] else [],
                    timestamp=row[3].isoformat(),
                )
                for row in rows
            ]
        except Exception:
            # Non-blocking — return empty list rather than propagate
            return []

    def clear(self) -> None:
        """Delete all records from the table (table schema remains)."""
        try:
            self._conn().execute("DELETE FROM selection_history")
        except Exception:
            # Non-blocking — clear failure should not disrupt anything
            pass

    def record_selection(
        self,
        intent_hash: str,
        selected_skill: str,
        rejected_skills: list[str] | None = None,
    ) -> None:
        """Convenience method to create and insert a selection record."""
        record = SelectionRecord(
            intent_hash=intent_hash,
            selected_skill=selected_skill,
            rejected_skills=rejected_skills or [],
            timestamp=datetime.now(UTC).isoformat(),
        )
        self.add_record(record)

    def get_skill_selection_count(self, skill_name: str, days: int = 30) -> int | None:
        """Return the number of times a skill was selected within the time window.

        Args:
            skill_name: Name of the skill to query.
            days: Number of days to look back (default 30).

        Returns:
            Number of selections within the window, or None if 0 or error.
        """
        try:
            conn = self._conn()
            result = conn.execute(
                """
                SELECT COUNT(*)
                FROM selection_history
                WHERE selected_skill = ?
                  AND created_at > CURRENT_TIMESTAMP - INTERVAL '1 day' * ?
                """,
                [skill_name, days],
            ).fetchone()
            if result is None:
                return None
            count = result[0]
            return count if count > 0 else None
        except Exception as exc:
            # Non-blocking — return None; log for diagnostics (ADV-002)
            logger.warning(
                "SelectionHistoryStore.get_skill_selection_count(%r, %r) failed: %s",
                skill_name,
                days,
                exc,
            )
            return None

    def get_skill_stats(self, skill_names: list[str], days: int = 30) -> dict[str, int]:
        """Return selection counts for multiple skills within the time window.

        Args:
            skill_names: List of skill names to query.
            days: Number of days to look back (default 30).

        Returns:
            Dict mapping skill_name -> selection count (0 if not found or error).
        """
        if not skill_names:
            return {}
        # Initialize all skills to 0 (handles unselected skills not in query result)
        result: dict[str, int] = {name: 0 for name in skill_names}
        try:
            conn = self._conn()
            rows = conn.execute(
                """
                SELECT selected_skill, COUNT(*)
                FROM selection_history
                WHERE selected_skill IN ({placeholders})
                  AND created_at > CURRENT_TIMESTAMP - INTERVAL '1 day' * ?
                GROUP BY selected_skill
                """.format(placeholders=", ".join("?" for _ in skill_names)),
                [*skill_names, days],
            ).fetchall()
            for row in rows:
                result[row[0]] = row[1]
            return result
        except Exception as exc:
            logger.warning(
                "SelectionHistoryStore.get_skill_stats(%d skills, %r) failed: %s",
                len(skill_names),
                days,
                exc,
            )
            return {name: 0 for name in skill_names}

    def close(self) -> None:
        """Close the DuckDB connection."""
        if self._con is not None:
            self._con.close()
            self._con = None


# Module-level singleton
_history_store: SelectionHistoryStore | None = None


def _get_history_store() -> SelectionHistoryStore:
    """Lazily initialize the history store singleton."""
    global _history_store
    if _history_store is None:
        _history_store = SelectionHistoryStore()
    return _history_store
