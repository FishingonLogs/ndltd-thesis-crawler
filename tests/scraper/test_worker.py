"""ScraperWorker 冒煙測試：信號存在、控制旗標、時間戳。

完整爬取流程（Playwright 導航）屬整合行為，手動驗證（Task 3.6）。
這裡只驗證不需啟動執行緒/不連網的部分。
"""

from ndltd_spider.scraper.worker import ScraperWorker, _now_iso


def test_now_iso_is_iso8601():
    s = _now_iso()
    assert "T" in s and len(s) >= 19


def test_worker_has_expected_signals(qapp):
    worker = ScraperWorker()
    for name in (
        "progress_updated",
        "log_message",
        "captcha_detected",
        "scrape_finished",
        "error_occurred",
    ):
        assert hasattr(worker, name), f"missing signal: {name}"


def test_stop_sets_events(qapp):
    worker = ScraperWorker()
    assert not worker._stop_event.is_set()
    worker.stop()
    assert worker._stop_event.is_set()
    # 停止時也解除 CAPTCHA 等待，避免卡死
    assert worker._resume_event.is_set()


def test_reset_clears_counters(qapp):
    worker = ScraperWorker()
    worker._done = worker._failed = worker._skipped = worker._total = 5
    worker._reset()
    assert (worker._done, worker._failed, worker._skipped, worker._total) == (0, 0, 0, 0)


def test_aborted_on_failures_threshold(qapp):
    from ndltd_spider.scraper.worker import MAX_CONSECUTIVE_FAILURES
    worker = ScraperWorker()
    assert worker._aborted_on_failures(MAX_CONSECUTIVE_FAILURES - 1) is False
    assert worker._aborted_on_failures(MAX_CONSECUTIVE_FAILURES) is True


def test_captcha_unsolved_error_is_exception():
    from ndltd_spider.scraper.captcha import CaptchaUnsolvedError
    assert issubclass(CaptchaUnsolvedError, Exception)


def test_build_run_log_format():
    from ndltd_spider.scraper.worker import build_run_log
    text = build_run_log(
        timestamp_text="2026-06-04 15:30:00",
        mode_label="搜尋",
        condition_summary="關鍵字=機器學習; 學位=碩士,博士",
        done=2, total=3, skipped=0, failed=1,
        lines=["[OK]   110A  標題A", "[FAIL] r1=3  detail_page_not_found"],
    )
    assert "NDLTD 爬取紀錄  2026-06-04 15:30:00" in text
    assert "模式: 搜尋" in text
    assert "條件: 關鍵字=機器學習; 學位=碩士,博士" in text
    assert "總數: 3  成功: 2  跳過: 0  失敗: 1" in text
    assert "[OK]   110A  標題A" in text
    assert "[FAIL] r1=3  detail_page_not_found" in text
    # 逐筆行在計數摘要之後
    assert text.index("總數:") < text.index("[OK]")


def test_build_run_log_empty_lines():
    from ndltd_spider.scraper.worker import build_run_log
    text = build_run_log(
        timestamp_text="t", mode_label="ID 清單", condition_summary="0 筆 ID",
        done=0, total=0, skipped=0, failed=0, lines=[],
    )
    assert "總數: 0  成功: 0  跳過: 0  失敗: 0" in text


def test_condition_summary_search(qapp):
    from ndltd_spider.models import SearchConfig, QueryRow
    from ndltd_spider.scraper.worker import MODE_SEARCH
    worker = ScraperWorker()
    worker._mode = MODE_SEARCH
    worker._search_config = SearchConfig(
        rows=[
            QueryRow(field="", keyword="機器學習"),
            QueryRow(field="asc", keyword="臺灣大學", operator="or"),
        ],
        degree_master=True, degree_doctor=False, year_from=110, year_to=113,
    )
    s = worker._condition_summary()
    assert "不限欄位=機器學習" in s
    assert "or 校院名稱=臺灣大學" in s
    assert "學位=碩士" in s
    assert "學年度=110~113" in s


def test_condition_summary_ids(qapp):
    from ndltd_spider.scraper.worker import MODE_IDS
    worker = ScraperWorker()
    worker._mode = MODE_IDS
    worker._id_list = ["A", "B", "C"]
    assert "3 筆 ID" in worker._condition_summary()
