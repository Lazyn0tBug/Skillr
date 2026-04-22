"""Tests for E5 selection history store."""

from __future__ import annotations

import json

from skillr.history import SelectionHistoryStore
from skillr.models import SelectionRecord


class TestSelectionHistoryStore:
    """Test SelectionHistoryStore with real temp filesystem."""

    def test_add_record_creates_file(self, tmp_path, mocker):
        """Adding a record creates the JSONL file."""
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

        path = tmp_path / "selection_history.jsonl"
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["selected_skill"] == "drawio"
        assert data["rejected_skills"] == ["miro", "figma"]

    def test_add_multiple_records(self, tmp_path, mocker):
        """Multiple records are appended as separate lines."""
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

        path = tmp_path / "selection_history.jsonl"
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_get_all_records_returns_all(self, tmp_path, mocker):
        """get_all_records returns all appended records."""
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
        """Returns empty list if history file doesn't exist."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        records = store.get_all_records()
        assert records == []

    def test_clear_deletes_file(self, tmp_path, mocker):
        """clear() removes the history file."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        record = SelectionRecord(
            intent_hash="abc",
            selected_skill="drawio",
            timestamp="2026-04-21T10:00:00+00:00",
        )
        store.add_record(record)
        store.clear()

        path = tmp_path / "selection_history.jsonl"
        assert not path.exists()

    def test_clear_nonexistent_file_succeeds(self, tmp_path, mocker):
        """clear() succeeds even if file doesn't exist."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        store.clear()  # Should not raise

    def test_skips_malformed_lines(self, tmp_path, mocker):
        """Skips lines that are not valid JSON."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        path = tmp_path / "selection_history.jsonl"
        # Valid: two SelectionRecord lines separated by a plain-text (non-JSON) line
        valid1 = json.dumps(
            {
                "intent_hash": "h1",
                "selected_skill": "s1",
                "rejected_skills": [],
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
        )
        valid2 = json.dumps(
            {
                "intent_hash": "h2",
                "selected_skill": "s2",
                "rejected_skills": [],
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
        )
        path.write_text(f"{valid1}\nnot json\n{valid2}\n")

        # Override _path directly on the store instance to use our temp path
        store = SelectionHistoryStore()
        store._path = lambda: path
        records = store.get_all_records()

        assert len(records) == 2
        assert records[0].intent_hash == "h1"
        assert records[1].intent_hash == "h2"

    def test_record_selection_convenience_method(self, tmp_path, mocker):
        """record_selection() creates and appends a record."""
        mocker.patch("skillr.history.ensure_plugin_data_dir", return_value=tmp_path)
        mocker.patch("skillr.config.ensure_plugin_data_dir", return_value=tmp_path)

        store = SelectionHistoryStore()
        store.record_selection("intent-hash-xyz", "drawio", ["miro", "figma"])

        records = store.get_all_records()
        assert len(records) == 1
        assert records[0].intent_hash == "intent-hash-xyz"
        assert records[0].selected_skill == "drawio"
        assert records[0].rejected_skills == ["miro", "figma"]


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

        path = tmp_path / "selection_history.jsonl"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["selected_skill"] == "drawio"
