"""ThesisDB 測試 (Red)：建表、upsert、去重、狀態查詢、續爬清單。"""

import pytest

from ndltd_spider.models import ThesisRecord
from ndltd_spider.storage.database import ThesisDB


@pytest.fixture
def db(tmp_path):
    database = ThesisDB(str(tmp_path / "test.db"))
    yield database
    database.close()


def make_record(thesis_id: str, status: str = "completed", **kw) -> ThesisRecord:
    return ThesisRecord(thesis_id=thesis_id, status=status, **kw)


def test_new_db_is_empty(db):
    assert db.get_status("110NKUS0320041") is None
    assert db.get("110NKUS0320041") is None
    assert db.list_completed() == []
    assert db.list_pending() == []


def test_upsert_then_get_roundtrip(db):
    rec = make_record(
        "110NKUS0320041",
        title_zh="公司治理對股價異常報酬影響之研究",
        student_zh="陳英祥",
        degree="博士",
        citation_stats="被引用:0點閱:100下載:5",
        bibliography="很長的書目資料……",
    )
    db.upsert(rec)

    got = db.get("110NKUS0320041")
    assert got == rec


def test_upsert_dedupes_by_thesis_id(db):
    db.upsert(make_record("110NKUS0320041", title_zh="舊標題", status="pending"))
    db.upsert(make_record("110NKUS0320041", title_zh="新標題", status="completed"))

    # 同一個 thesis_id 只保留一筆，且為最後寫入的版本
    assert db.count_by_status() == {"completed": 1}
    got = db.get("110NKUS0320041")
    assert got.title_zh == "新標題"
    assert got.status == "completed"


def test_get_status(db):
    db.upsert(make_record("A001", status="completed"))
    db.upsert(make_record("A002", status="failed", error_msg="timeout"))

    assert db.get_status("A001") == "completed"
    assert db.get_status("A002") == "failed"
    assert db.get_status("A999") is None


def test_list_completed_and_pending_partition(db):
    db.upsert(make_record("C1", status="completed"))
    db.upsert(make_record("C2", status="completed"))
    db.upsert(make_record("P1", status="pending"))
    db.upsert(make_record("F1", status="failed"))

    assert sorted(db.list_completed()) == ["C1", "C2"]
    # 續爬清單包含未完成者（pending + failed）
    assert sorted(db.list_pending()) == ["F1", "P1"]


def test_get_completed_records_returns_only_completed(db):
    db.upsert(make_record("C1", status="completed", title_zh="標題1"))
    db.upsert(make_record("F1", status="failed"))

    records = db.get_completed_records()
    assert len(records) == 1
    assert records[0].thesis_id == "C1"
    assert records[0].title_zh == "標題1"
    assert isinstance(records[0], ThesisRecord)


def test_data_persists_across_reopen(tmp_path):
    path = str(tmp_path / "persist.db")
    db1 = ThesisDB(path)
    db1.upsert(make_record("110NKUS0320041", title_zh="持久化測試"))
    db1.close()

    db2 = ThesisDB(path)
    got = db2.get("110NKUS0320041")
    db2.close()
    assert got is not None
    assert got.title_zh == "持久化測試"


def test_migrates_v1_schema(tmp_path):
    """舊 v1 schema（references 欄、缺新欄位）開啟後應自動補欄並搬移 references→citation_stats。"""
    import sqlite3
    path = str(tmp_path / "v1.db")
    conn = sqlite3.connect(path)
    conn.execute(
        'CREATE TABLE thesis ("thesis_id" TEXT PRIMARY KEY, '
        '"title_zh" TEXT, "references" TEXT, "status" TEXT)'
    )
    conn.execute(
        'INSERT INTO thesis VALUES (?, ?, ?, ?)',
        ("OLD001", "舊論文", "被引用:5", "completed"),
    )
    conn.commit()
    conn.close()

    db = ThesisDB(path)               # 觸發 migration
    # 新欄位可正常 upsert（不再 OperationalError）
    db.upsert(make_record("NEW001", title_zh="新論文", abstract_zh="摘要", bibliography="書目"))
    got_old = db.get("OLD001")
    db.close()

    assert got_old is not None
    assert got_old.citation_stats == "被引用:5"   # references 搬移到 citation_stats
    assert got_old.abstract_zh == ""              # 新欄位預設空字串
