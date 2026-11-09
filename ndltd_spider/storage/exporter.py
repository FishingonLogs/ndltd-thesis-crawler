"""CSV 匯出：將 SQLite 中已完成的論文紀錄輸出為 UTF-8 BOM 的 CSV。

使用標準庫 csv 模組；欄位順序取自 ThesisRecord 定義（record_columns）。
"""

import csv
from datetime import datetime
from pathlib import Path

from ..models import record_columns
from .database import ThesisDB

# 匯出檔名的時間戳格式（單一事實來源，CSV 與 log 共用）。
TS_FORMAT = "%Y%m%d_%H%M%S"


def make_timestamp() -> str:
    """產生檔名用的時間戳字串。"""
    return datetime.now().strftime(TS_FORMAT)


def _timestamped_csv_path(output_dir: str, timestamp: str) -> str:
    """確保 output_dir 存在，回傳該次的 CSV 路徑（命名規則單一來源）。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return str(out / f"thesis_{timestamp}.csv")


def export_csv(db: ThesisDB, path: str) -> int:
    """匯出所有 status='completed' 的紀錄至 CSV，回傳匯出筆數。

    - 欄位順序固定為 record_columns()
    - 編碼為 UTF-8 with BOM（utf-8-sig），供 Excel 直接開啟中文
    - 逗號/換行/引號等特殊字元由 csv 模組自動以引號跳脫
    - 無資料時仍寫出表頭
    """
    columns = record_columns()
    records = db.get_completed_records()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for rec in records:
            writer.writerow(vars(rec))
    return len(records)


def export_db_to_csv(db_path: str, out_path: str) -> int:
    """從 db_path 開啟資料庫並匯出至 out_path，回傳匯出筆數。

    封裝 DB 連線的開關，讓呼叫端（如 GUI）不需認識 ThesisDB 生命週期。
    """
    db = ThesisDB(db_path)
    try:
        return export_csv(db, out_path)
    finally:
        db.close()


def export_run(db: ThesisDB, output_dir: str, log_text: str, timestamp: str) -> tuple[str, str]:
    """確保 output_dir 存在（含多層）；寫兩檔並回傳 (csv_path, log_path)。

    - csv: <output_dir>/thesis_<timestamp>.csv（沿用 export_csv：completed 記錄、UTF-8 BOM）
    - log: <output_dir>/run_<timestamp>.log（UTF-8 寫入 log_text）
    """
    csv_path = _timestamped_csv_path(output_dir, timestamp)
    log_path = str(Path(output_dir) / f"run_{timestamp}.log")

    export_csv(db, csv_path)
    Path(log_path).write_text(log_text, encoding="utf-8")

    return csv_path, log_path


def export_db_snapshot(db_path: str, output_dir: str) -> tuple[str, int]:
    """手動匯出：開 db_path、輸出時間戳 CSV 至 output_dir，回傳 (csv_path, 筆數)。

    與自動匯出共用命名/建目錄規則；GUI 不需認識檔名 pattern 或 DB 生命週期。
    """
    csv_path = _timestamped_csv_path(output_dir, make_timestamp())
    count = export_db_to_csv(db_path, csv_path)
    return csv_path, count
