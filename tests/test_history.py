"""Tests for E5 selection history store (DuckDB backend)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from skillr.history import SelectionHistoryStore
from skillr.models import SelectionRecord


class TestSelectionHistoryStore:
    """Test SelectionHistoryStore with DuckDB backend using temp directories."""

    def test_add_record_inserts_into_duckdb(self, tmp_path, mocker):
        """Adding a record persists it in DuckDB."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        record = SelectionRecord(
            intent_hash="abc123",
            selected_skill="drawio",
            rejected_skills=["miro", "figma"],
            timestamp="2026-04-21T10:00:00+00:00",
        )
        store.add_record(record)

        # Verify via get_all_records
        records = store.get_all_records()
        assert len(records) == 1
        assert records[0].selected_skill == "drawio"
        assert records[0].rejected_skills == ["miro", "figma"]

    def test_add_multiple_records(self, tmp_path, mocker):
        """Multiple records are persisted separately."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        for i in range(3):
            record = SelectionRecord(
                intent_hash=f"hash{i}",
                selected_skill=f"skill{i}",
                timestamp=f"2026-04-21T{i:02d}:00:00+00:00",
            )
            store.add_record(record)

        records = store.get_all_records()
        assert len(records) == 3
        assert [r.selected_skill for r in records] == ["skill0", "skill1", "skill2"]

    def test_get_all_records_returns_all(self, tmp_path, mocker):
        """get_all_records returns all records ordered by id."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        for i in range(3):
            record = SelectionRecord(
                intent_hash=f"hash{i}",
                selected_skill=f"skill{i}",
                timestamp=f"2026-04-21T{i:02d}:00:00+00:00",
            )
            store.add_record(record)

        records = store.get_all_records()
        assert len(records) == 3
        assert [r.selected_skill for r in records] == ["skill0", "skill1", "skill2"]

    def test_get_all_records_empty_when_no_file(self, tmp_path, mocker):
        """Returns empty list when no records exist."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        records = store.get_all_records()
        assert records == []

    def test_clear_deletes_all_records(self, tmp_path, mocker):
        """clear() removes all records but keeps the table schema."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        for i in range(3):
            record = SelectionRecord(
                intent_hash=f"hash{i}",
                selected_skill=f"skill{i}",
                timestamp=f"2026-04-21T{i:02d}:00:00+00:00",
            )
            store.add_record(record)

        store.clear()

        records = store.get_all_records()
        assert records == []
        # Table schema should still exist (get_all returns [] not error)
        assert store.get_all_records() == []

    def test_clear_nonexistent_succeeds(self, tmp_path, mocker):
        """clear() succeeds even when table is empty."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        store.clear()  # Should not raise

    def test_record_selection_convenience_method(self, tmp_path, mocker):
        """record_selection() creates and inserts a record."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        store.record_selection("intent-hash-xyz", "drawio", ["miro", "figma"])

        records = store.get_all_records()
        assert len(records) == 1
        assert records[0].intent_hash == "intent-hash-xyz"
        assert records[0].selected_skill == "drawio"
        assert records[0].rejected_skills == ["miro", "figma"]

    def test_migrate_from_jsonl_preserves_data(self, tmp_path, mocker):
        """migrate_from_jsonl correctly imports JSONL records into DuckDB."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        # Create a JSONL file with test data
        jsonl_path = tmp_path / "selection_history.jsonl"
        lines = []
        for i in range(3):
            rec = SelectionRecord(
                intent_hash=f"h{i}",
                selected_skill=f"s{i}",
                rejected_skills=["rejected-skill"] if i > 0 else [],
                timestamp=f"2026-01-01T{i:02d}:00:00+00:00",
            )
            lines.append(rec.model_dump_json())
        jsonl_path.write_text("\n".join(lines))

        # Manually migrate using the store's migration function
        store = SelectionHistoryStore()
        # _migrate_if_needed already ran during __init__ — it migrated and renamed the file
        # So we call migrate_from_jsonl with the same path (it will find .bak gone, returns 0)
        # Instead: test that auto-migration worked by checking records
        records = store.get_all_records()
        assert len(records) == 3
        assert records[0].selected_skill == "s0"
        assert records[1].rejected_skills == ["rejected-skill"]
        # And .bak file should exist
        assert jsonl_path.with_suffix(".bak").exists()


class TestGetSkillSelectionCount:
    """Test get_skill_selection_count with DuckDB backend."""

    def test_returns_count_within_window(self, tmp_path, mocker):
        """Returns correct count for skill selected within window."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        now = datetime.now(UTC)

        # Insert 3 records for drawio in the last 10 days
        for i in range(3):
            record = SelectionRecord(
                intent_hash=f"hash{i}",
                selected_skill="drawio",
                rejected_skills=[],
                timestamp=(now - timedelta(days=i)).isoformat(),
            )
            store.add_record(record)

        count = store.get_skill_selection_count("drawio", days=30)
        assert count == 3

    def test_returns_none_when_zero(self, tmp_path, mocker):
        """Returns None when skill has no selections in window."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        count = store.get_skill_selection_count("nonexistent-skill", days=30)
        assert count is None

    def test_excludes_outside_window(self, tmp_path, mocker):
        """Excludes selections older than the window."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        now = datetime.now(UTC)

        # 1 recent selection
        store.add_record(
            SelectionRecord(
                intent_hash="recent",
                selected_skill="drawio",
                rejected_skills=[],
                timestamp=now.isoformat(),
            )
        )
        # 1 old selection (45 days ago)
        store.add_record(
            SelectionRecord(
                intent_hash="old",
                selected_skill="drawio",
                rejected_skills=[],
                timestamp=(now - timedelta(days=45)).isoformat(),
            )
        )

        # Within 30 days: only the recent one
        count = store.get_skill_selection_count("drawio", days=30)
        assert count == 1

        # Within 60 days: both
        count_60 = store.get_skill_selection_count("drawio", days=60)
        assert count_60 == 2

    def test_different_windows_return_different_counts(self, tmp_path, mocker):
        """Different window sizes return different counts."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        now = datetime.now(UTC)

        # 1 selection 10 days ago, 1 selection 50 days ago
        for days in [10, 50]:
            store.add_record(
                SelectionRecord(
                    intent_hash=f"h{days}",
                    selected_skill="miro",
                    rejected_skills=[],
                    timestamp=(now - timedelta(days=days)).isoformat(),
                )
            )

        count_30 = store.get_skill_selection_count("miro", days=30)
        count_90 = store.get_skill_selection_count("miro", days=90)

        assert count_30 == 1
        assert count_90 == 2


class TestRouterIntegration:
    """Test record_selection_history integration in router module."""

    def setup_method(self):
        """Reset router history store singleton."""
        import skillr.router as router_module

        router_module._history_store = None

    def teardown_method(self):
        """Reset router history store singleton."""
        import skillr.router as router_module

        router_module._history_store = None

    def test_record_selection_history_via_router(self, tmp_path, mocker):
        """record_selection_history calls the store correctly."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        from skillr.router import record_selection_history

        record_selection_history("我想画架构图", "drawio", ["miro"])

        # Verify via DuckDB
        import skillr.router as router_module

        store = router_module._get_history_store()
        records = store.get_all_records()

        assert len(records) == 1
        assert records[0].selected_skill == "drawio"

    def test_get_skill_selection_count_via_router(self, tmp_path, mocker):
        """get_skill_selection_count is accessible via router."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        from skillr.router import get_skill_selection_count, record_selection_history

        record_selection_history("test task", "drawio", [])
        count = get_skill_selection_count("drawio", days=30)

        assert count == 1
