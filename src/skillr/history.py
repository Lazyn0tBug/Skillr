"""Selection history store for tracking user skill selections over time."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .config import ensure_plugin_data_dir
from .models import SelectionRecord


class SelectionHistoryStore:
    """Append-only JSONL store for user skill selection history.

    File format: one JSON line per record at `${CLAUDE_PLUGIN_DATA}/selection_history.jsonl`.
    """

    FILENAME = "selection_history.jsonl"

    def _path(self) -> Path:
        """Return the path to the selection history file."""
        return ensure_plugin_data_dir() / self.FILENAME

    def add_record(self, record: SelectionRecord) -> None:
        """Append a selection record to the history file.

        Creates the file and parent directory if they don't exist.
        Silently passes on write errors (non-blocking).
        """
        path = self._path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(record.model_dump_json() + "\n")
        except Exception:
            # Non-blocking — history write failures don't affect user-facing functionality
            pass

    def get_all_records(self) -> list[SelectionRecord]:
        """Load and return all selection records from the history file.

        Returns an empty list if the file doesn't exist or is empty.
        Skips malformed lines.
        """
        path = self._path()
        if not path.exists():
            return []

        records: list[SelectionRecord] = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        records.append(SelectionRecord.model_validate(data))
                    except Exception:
                        # Skip malformed lines
                        continue
        except Exception:
            return []

        return records

    def clear(self) -> None:
        """Delete the selection history file."""
        path = self._path()
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

    def record_selection(
        self,
        intent_hash: str,
        selected_skill: str,
        rejected_skills: list[str] | None = None,
    ) -> None:
        """Convenience method to create and append a selection record.

        Args:
            intent_hash: SHA256 hash of the original intent text
            selected_skill: Name of the skill the user selected
            rejected_skills: Names of skills offered but not selected
        """
        record = SelectionRecord(
            intent_hash=intent_hash,
            selected_skill=selected_skill,
            rejected_skills=rejected_skills or [],
            timestamp=datetime.now(UTC).isoformat(),
        )
        self.add_record(record)


# Module-level singleton
_history_store: SelectionHistoryStore | None = None


def _get_history_store() -> SelectionHistoryStore:
    """Lazily initialize the history store singleton."""
    global _history_store
    if _history_store is None:
        _history_store = SelectionHistoryStore()
    return _history_store
