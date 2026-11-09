"""進度與日誌面板元件。"""

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ProgressPanel(QWidget):
    """顯示爬取進度與即時日誌的面板。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Progress bar（QProgressBar 預設 minimum=0、value=0）
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Statistics labels row
        stats_layout = QHBoxLayout()

        self.label_done = QLabel("已完成: 0")
        self.label_skipped = QLabel("跳過: 0")
        self.label_failed = QLabel("失敗: 0")
        self.label_total = QLabel("總數: 0")

        stats_layout.addWidget(self.label_done)
        stats_layout.addWidget(self.label_skipped)
        stats_layout.addWidget(self.label_failed)
        stats_layout.addWidget(self.label_total)

        layout.addLayout(stats_layout)

        # Log area
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

    def update_progress(self, done: int, total: int, skipped: int, failed: int) -> None:
        """更新進度條與統計標籤。

        進度值 = done + skipped + failed（已處理數）。
        total 為 0 時進度條顯示 0，不除以零。
        """
        processed = done + skipped + failed

        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(processed)

        self.label_done.setText(f"已完成: {done}")
        self.label_skipped.setText(f"跳過: {skipped}")
        self.label_failed.setText(f"失敗: {failed}")
        self.label_total.setText(f"總數: {total}")

    def append_log(self, message: str) -> None:
        """將訊息附加為日誌區的新一行。"""
        self.log_view.append(message)
