"""MainWindow 冒煙測試：建構、signal 接線。

完整爬取流程（Playwright）屬手動端到端驗證。這裡只驗證視窗能建構，
且 worker 的 signal 確實接到面板（以主執行緒直接 emit 模擬）。
"""

from ndltd_spider.gui.main_window import MainWindow


def test_mainwindow_builds(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.search_panel is not None
    assert win.progress_panel is not None
    assert win.worker is not None
    assert win.stop_btn.isEnabled() is False  # 未開始前停止鈕停用


def test_progress_signal_wired_to_panel(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.worker.progress_updated.emit(2, 5, 1, 0)
    assert "2" in win.progress_panel.label_done.text()
    assert "5" in win.progress_panel.label_total.text()
    assert win.progress_panel.progress_bar.maximum() == 5
    assert win.progress_panel.progress_bar.value() == 3  # 2+1+0


def test_log_signal_wired_to_panel(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.worker.log_message.emit("hello-log")
    assert "hello-log" in win.progress_panel.log_view.toPlainText()


def test_error_signal_logs_and_disables_stop(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.stop_btn.setEnabled(True)
    win.worker.error_occurred.emit("boom")
    assert "boom" in win.progress_panel.log_view.toPlainText()
    assert win.stop_btn.isEnabled() is False
