"""exporter 測試 (Red)：CSV 欄位順序、UTF-8 BOM、特殊字元跳脫、僅匯出 completed。
export_run：自動建目錄、回傳路徑、CSV 只含 completed、log 內容正確。
"""

import csv

import pytest

from ndltd_spider.models import ScraperConfig, ThesisRecord, record_columns
from ndltd_spider.storage.database import ThesisDB
from ndltd_spider.storage.exporter import export_csv, export_run


@pytest.fixture
def db(tmp_path):
    database = ThesisDB(str(tmp_path / "test.db"))
    yield database
    database.close()


def test_export_only_completed(db, tmp_path):
    db.upsert(ThesisRecord(thesis_id="C1", title_zh="完成一", status="completed"))
    db.upsert(ThesisRecord(thesis_id="C2", title_zh="完成二", status="completed"))
    db.upsert(ThesisRecord(thesis_id="F1", status="failed"))
    db.upsert(ThesisRecord(thesis_id="P1", status="pending"))

    out = tmp_path / "out.csv"
    count = export_csv(db, str(out))

    assert count == 2
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    ids = sorted(r["thesis_id"] for r in rows)
    assert ids == ["C1", "C2"]


def test_column_order_matches_record_columns(db, tmp_path):
    db.upsert(ThesisRecord(thesis_id="C1", status="completed"))
    out = tmp_path / "out.csv"
    export_csv(db, str(out))

    with open(out, encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f))
    assert header == record_columns()


def test_file_has_utf8_bom(db, tmp_path):
    db.upsert(ThesisRecord(thesis_id="C1", title_zh="中文標題", status="completed"))
    out = tmp_path / "out.csv"
    export_csv(db, str(out))

    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM，供 Excel 正確辨識中文


def test_special_chars_are_escaped(db, tmp_path):
    tricky = 'keyword1, keyword2\nline2 "quoted"'
    db.upsert(
        ThesisRecord(thesis_id="C1", keywords_zh=tricky, status="completed")
    )
    out = tmp_path / "out.csv"
    export_csv(db, str(out))

    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["keywords_zh"] == tricky  # 逗號/換行/引號往返後完全一致


def test_export_empty_db_writes_header_only(db, tmp_path):
    out = tmp_path / "out.csv"
    count = export_csv(db, str(out))

    assert count == 0
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert rows == [record_columns()]  # 只有表頭


# ── ScraperConfig 預設值驗證 ───────────────────────────────────────────────────

def test_scraper_config_defaults():
    """ScraperConfig 預設值含 output_dir 與 auto_export。"""
    cfg = ScraperConfig()
    assert cfg.output_dir == "output"
    assert cfg.auto_export is True


# ── export_run 測試 ──────────────────────────────────────────────────────────

TS = "20260604_153000"


@pytest.fixture
def db_with_records(tmp_path):
    """建立含 2 筆 completed、1 筆 failed 的 ThesisDB。"""
    database = ThesisDB(str(tmp_path / "run_test.db"))
    database.upsert(ThesisRecord(thesis_id="C1", title_zh="完成一", status="completed"))
    database.upsert(ThesisRecord(thesis_id="C2", title_zh="完成二", status="completed"))
    database.upsert(ThesisRecord(thesis_id="F1", title_zh="失敗一", status="failed"))
    yield database
    database.close()


def test_export_run_creates_output_dir(db_with_records, tmp_path):
    """export_run 應自動建立不存在的 output_dir（含多層）。"""
    out_dir = str(tmp_path / "nested" / "output")
    export_run(db_with_records, out_dir, "some log", TS)
    assert (tmp_path / "nested" / "output").is_dir()


def test_export_run_returns_correct_paths(db_with_records, tmp_path):
    """回傳的路徑結尾應符合 thesis_<ts>.csv 與 run_<ts>.log 格式。"""
    out_dir = str(tmp_path / "out")
    csv_path, log_path = export_run(db_with_records, out_dir, "log text", TS)
    assert csv_path.endswith(f"thesis_{TS}.csv")
    assert log_path.endswith(f"run_{TS}.log")


def test_export_run_files_exist_on_disk(db_with_records, tmp_path):
    """export_run 回傳的兩個路徑，對應檔案必須實際存在。"""
    out_dir = str(tmp_path / "out")
    csv_path, log_path = export_run(db_with_records, out_dir, "log text", TS)
    from pathlib import Path
    assert Path(csv_path).is_file()
    assert Path(log_path).is_file()


def test_export_run_csv_contains_only_completed(db_with_records, tmp_path):
    """CSV 只含 status=completed 的紀錄，failed 不應出現。"""
    out_dir = str(tmp_path / "out")
    csv_path, _ = export_run(db_with_records, out_dir, "log", TS)
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    ids = sorted(r["thesis_id"] for r in rows)
    assert ids == ["C1", "C2"]
    assert all(r["status"] == "completed" for r in rows)


def test_export_run_csv_has_utf8_bom(db_with_records, tmp_path):
    """CSV 檔案開頭必須有 UTF-8 BOM（供 Excel 正確辨識）。"""
    out_dir = str(tmp_path / "out")
    csv_path, _ = export_run(db_with_records, out_dir, "log", TS)
    from pathlib import Path
    raw = Path(csv_path).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")


def test_export_run_log_content_matches_input(db_with_records, tmp_path):
    """log 檔內容應與傳入的 log_text 完全一致（UTF-8 讀回）。"""
    log_text = "爬蟲執行完畢\n共 2 筆\nerrors: 1"
    out_dir = str(tmp_path / "out")
    _, log_path = export_run(db_with_records, out_dir, log_text, TS)
    from pathlib import Path
    content = Path(log_path).read_text(encoding="utf-8")
    assert content == log_text


def test_export_db_snapshot(tmp_path):
    from ndltd_spider.storage.exporter import export_db_snapshot
    dbp = str(tmp_path / "snap.db")
    d = ThesisDB(dbp)
    d.upsert(ThesisRecord(thesis_id="C1", title_zh="完成", status="completed"))
    d.close()
    out_dir = str(tmp_path / "out")
    path, count = export_db_snapshot(dbp, out_dir)
    assert count == 1
    assert path.endswith(".csv") and "thesis_" in path
    from pathlib import Path
    assert Path(path).exists()
    assert Path(out_dir).is_dir()
