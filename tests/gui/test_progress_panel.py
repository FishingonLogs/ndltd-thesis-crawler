"""Tests for ProgressPanel widget (Task 4.3 - Red phase)."""

import pytest
from pytestqt.qtbot import QtBot

from ndltd_spider.gui.progress_panel import ProgressPanel


class TestProgressPanelUpdateProgress:
    def test_update_progress_sets_progress_bar_maximum_to_total(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act
        panel.update_progress(done=3, total=10, skipped=1, failed=2)

        # Assert
        assert panel.progress_bar.maximum() == 10

    def test_update_progress_sets_progress_bar_value_to_done_plus_skipped_plus_failed(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act
        panel.update_progress(done=3, total=10, skipped=1, failed=2)

        # Assert: value = done + skipped + failed = 3 + 1 + 2 = 6
        assert panel.progress_bar.value() == 6

    def test_update_progress_with_all_zeros_does_not_crash(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act (should not raise)
        panel.update_progress(done=0, total=0, skipped=0, failed=0)

        # Assert
        assert panel.progress_bar.value() == 0
        assert panel.progress_bar.maximum() == 0

    def test_update_progress_when_progress_bar_total_is_zero_value_is_zero(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act
        panel.update_progress(done=0, total=0, skipped=0, failed=0)

        # Assert: no division by zero, value stays 0
        assert panel.progress_bar.value() == 0

    def test_update_progress_shows_done_count_in_label(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act
        panel.update_progress(done=3, total=10, skipped=1, failed=2)

        # Assert: label text contains the done number
        assert "3" in panel.label_done.text()

    def test_update_progress_shows_skipped_count_in_label(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act
        panel.update_progress(done=3, total=10, skipped=1, failed=2)

        # Assert
        assert "1" in panel.label_skipped.text()

    def test_update_progress_shows_failed_count_in_label(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act
        panel.update_progress(done=3, total=10, skipped=1, failed=2)

        # Assert
        assert "2" in panel.label_failed.text()

    def test_update_progress_shows_total_count_in_label(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act
        panel.update_progress(done=3, total=10, skipped=1, failed=2)

        # Assert
        assert "10" in panel.label_total.text()

    def test_update_progress_when_fully_complete_value_equals_maximum(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act: done+skipped+failed == total
        panel.update_progress(done=7, total=10, skipped=2, failed=1)

        # Assert: 7+2+1 = 10 = total
        assert panel.progress_bar.value() == panel.progress_bar.maximum()
        assert panel.progress_bar.value() == 10


class TestProgressPanelAppendLog:
    def test_append_log_adds_message_to_text_edit(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act
        panel.append_log("hello")

        # Assert
        assert "hello" in panel.log_view.toPlainText()

    def test_append_log_adds_multiple_messages_as_separate_lines(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act
        panel.append_log("hello")
        panel.append_log("world")

        # Assert: both messages appear in text
        text = panel.log_view.toPlainText()
        assert "hello" in text
        assert "world" in text

    def test_append_log_preserves_message_order(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act
        panel.append_log("first")
        panel.append_log("second")

        # Assert: "first" appears before "second"
        text = panel.log_view.toPlainText()
        assert text.index("first") < text.index("second")

    def test_log_view_is_read_only(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Assert
        assert panel.log_view.isReadOnly()

    def test_append_log_empty_string_does_not_crash(self, qtbot: QtBot):
        # Arrange
        panel = ProgressPanel()
        qtbot.addWidget(panel)

        # Act (should not raise)
        panel.append_log("")

        # Assert: no crash, text edit is accessible
        _ = panel.log_view.toPlainText()
