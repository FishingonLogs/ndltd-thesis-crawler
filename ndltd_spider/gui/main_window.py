"""主視窗：整合搜尋面板、進度面板與爬蟲 worker。"""

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import load_config
from ..storage.exporter import export_db_snapshot
from ..scraper.worker import ScraperWorker
from .progress_panel import ProgressPanel
from .search_panel import SearchPanel


class MainWindow(QMainWindow):
    """應用程式主視窗。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("NDLTD 博碩士論文爬蟲工具")
        self._config = load_config()

        self.search_panel = SearchPanel()
        self.progress_panel = ProgressPanel()
        self.worker = ScraperWorker(self)

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)

        panels = QHBoxLayout()
        self.search_panel.setMinimumWidth(400)   # 確保查詢列關鍵字框有足夠寬度
        panels.addWidget(self.search_panel, 2)
        panels.addWidget(self.progress_panel, 3)
        outer.addLayout(panels)

        buttons = QHBoxLayout()
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.export_btn = QPushButton("匯出 CSV")
        buttons.addStretch()
        buttons.addWidget(self.stop_btn)
        buttons.addWidget(self.export_btn)
        outer.addLayout(buttons)

        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.search_panel.start_requested.connect(self._on_start)
        self.stop_btn.clicked.connect(self.worker.stop)
        self.export_btn.clicked.connect(self._on_export)

        self.worker.progress_updated.connect(self.progress_panel.update_progress)
        self.worker.log_message.connect(self.progress_panel.append_log)
        self.worker.captcha_detected.connect(self._on_captcha)
        self.worker.scrape_finished.connect(self._on_finished)
        self.worker.error_occurred.connect(self._on_error)

    # ---- slots ----

    def _on_start(self, mode: str) -> None:
        if self.worker.isRunning():
            QMessageBox.warning(self, "爬取中", "目前已有爬取任務在執行。")
            return

        if mode == "ids":
            ids = self.search_panel.get_id_list()
            if not ids:
                QMessageBox.warning(self, "無 ID", "請先匯入論文 ID 清單 CSV。")
                return
            self.progress_panel.append_log(f"開始 ID 清單模式，共 {len(ids)} 筆")
            self.worker.start_from_ids(ids, self._config)
        else:
            self.progress_panel.append_log("開始搜尋模式")
            self.worker.start_search(self.search_panel.get_search_config(), self._config)

        self.stop_btn.setEnabled(True)

    def _on_captcha(self) -> None:
        QMessageBox.information(
            self,
            "偵測到驗證碼",
            "偵測到驗證碼，請在瀏覽器視窗中完成驗證後，按下「確定」繼續。",
        )
        self.worker.resume_after_captcha()

    def _on_export(self) -> None:
        """手動匯出：輸出到 output_dir 的時間戳 CSV（命名/建目錄由 storage 層處理）。"""
        path, count = export_db_snapshot(self._config.db_path, self._config.output_dir)
        self.progress_panel.append_log(f"已匯出 {count} 筆至 {path}")

    def _on_finished(self) -> None:
        self._finish("爬取完成")

    def _on_error(self, message: str) -> None:
        self._finish(f"錯誤：{message}")

    def _finish(self, message: str) -> None:
        """爬取結束（完成或錯誤）的共用收尾：記錄訊息並停用停止鈕。"""
        self.progress_panel.append_log(message)
        self.stop_btn.setEnabled(False)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt 介面命名)
        """關閉視窗時若仍在爬取，請求停止並等待 worker 結束。

        stop() 會解除 CAPTCHA 阻塞且 worker 在停止時略過瀏覽器重啟，通常能很快結束；
        若仍卡住（例如正卡在一次 goto 逾時）才強制 terminate，避免帶著 running 的
        QThread 解構導致閃退/殘留程序。
        """
        if self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(8000):
                self.worker.terminate()
                self.worker.wait(2000)
        super().closeEvent(event)
