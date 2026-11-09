"""SQLite 儲存層：論文紀錄的 upsert、去重、狀態查詢、續爬清單。

以 thesis_id 為主鍵；表格欄位由 ThesisRecord 的 dataclass 欄位自動推導，
新增欄位時不需手動改 schema（單一事實來源）。
"""

import sqlite3

from ..models import ThesisRecord, record_columns

_COLUMNS = record_columns()
# 欄位名以雙引號包裹，避免撞到 SQL 保留字（如 references）。SQL 字串在模組載入時
# 預先組好，逐筆 upsert 不需重複拼接。
_COL_LIST = ", ".join(f'"{c}"' for c in _COLUMNS)
_PLACEHOLDERS = ", ".join("?" for _ in _COLUMNS)
_INSERT_SQL = f"INSERT OR REPLACE INTO thesis ({_COL_LIST}) VALUES ({_PLACEHOLDERS})"
_CREATE_SQL = (
    "CREATE TABLE IF NOT EXISTS thesis ("
    + ", ".join(
        '"thesis_id" TEXT PRIMARY KEY' if c == "thesis_id"
        else f'"{c}" TEXT NOT NULL DEFAULT \'\''
        for c in _COLUMNS
    )
    + ")"
)


class ThesisDB:
    """論文 metadata 的 SQLite 存取。"""

    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_SQL)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """輕量 schema 遷移：對既有舊 DB 補上缺少的欄位。

        欄位由 ThesisRecord 推導，CREATE TABLE IF NOT EXISTS 對舊表是 no-op，
        故新增/改名欄位需在此以 ALTER TABLE 補齊，避免舊 ndltd.db 升級後 upsert 全炸。
        """
        existing = {row["name"] for row in self._conn.execute("PRAGMA table_info(thesis)")}
        for col in _COLUMNS:
            if col not in existing:
                self._conn.execute(
                    f'ALTER TABLE thesis ADD COLUMN "{col}" TEXT NOT NULL DEFAULT \'\''
                )
        # v1→v2：舊 references 欄（相關次數）資料搬到改名後的 citation_stats
        if "references" in existing and "citation_stats" not in existing:
            self._conn.execute(
                'UPDATE thesis SET citation_stats = "references" '
                'WHERE citation_stats = \'\' AND "references" != \'\''
            )

    def upsert(self, record: ThesisRecord) -> None:
        """以 thesis_id 為鍵插入或覆寫整筆紀錄。"""
        values = [getattr(record, name) for name in _COLUMNS]
        self._conn.execute(_INSERT_SQL, values)
        self._conn.commit()

    def get(self, thesis_id: str) -> ThesisRecord | None:
        """取得單筆完整紀錄，不存在時回傳 None。"""
        row = self._conn.execute(
            "SELECT * FROM thesis WHERE thesis_id = ?", (thesis_id,)
        ).fetchone()
        return self._row_to_record(row) if row else None

    def get_status(self, thesis_id: str) -> str | None:
        """取得單筆的爬取狀態，不存在時回傳 None。"""
        row = self._conn.execute(
            "SELECT status FROM thesis WHERE thesis_id = ?", (thesis_id,)
        ).fetchone()
        return row["status"] if row else None

    def list_completed(self) -> list[str]:
        """回傳所有已完成（completed）的 thesis_id。"""
        return self._query_ids("status = ?", ("completed",))

    def list_pending(self) -> list[str]:
        """回傳所有未完成（非 completed，含 pending/failed）的 thesis_id，供續爬重試。"""
        return self._query_ids("status != ?", ("completed",))

    def get_completed_records(self) -> list[ThesisRecord]:
        """回傳所有已完成的完整紀錄（供 CSV 匯出）。"""
        rows = self._conn.execute(
            "SELECT * FROM thesis WHERE status = 'completed'"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def count_by_status(self) -> dict[str, int]:
        """回傳各狀態的筆數統計，如 {'completed': 3, 'failed': 1}。"""
        rows = self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM thesis GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    def close(self) -> None:
        self._conn.close()

    def _query_ids(self, where: str, params: tuple = ()) -> list[str]:
        """以 WHERE 條件取出 thesis_id 清單（where 為內部常數，非使用者輸入）。"""
        rows = self._conn.execute(
            f"SELECT thesis_id FROM thesis WHERE {where}", params
        ).fetchall()
        return [r["thesis_id"] for r in rows]

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ThesisRecord:
        return ThesisRecord(**{name: row[name] for name in _COLUMNS})
