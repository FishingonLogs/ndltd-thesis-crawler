"""SearchPanel 測試（v2 M3：動態進階查詢列）。

涵蓋：預設一列、增列/移除列、欄位下拉值、get_search_config 回傳 rows、
第 0 列無 operator、學位/學年度限縮、模式切換、CSV 匯入去重。
"""

import csv

import pytest

from ndltd_spider.models import QF_FIELDS
from ndltd_spider.gui.search_panel import SearchPanel


@pytest.fixture
def panel(qtbot):
    p = SearchPanel()
    qtbot.addWidget(p)
    return p


class TestQueryRows:
    def test_default_has_one_row(self, panel):
        assert len(panel.query_rows) == 1
        cfg = panel.get_search_config()
        assert len(cfg.rows) == 1

    def test_add_query_row(self, panel):
        panel.add_query_row()
        assert len(panel.query_rows) == 2

    def test_remove_query_row(self, panel):
        panel.add_query_row()
        panel.add_query_row()
        assert len(panel.query_rows) == 3
        panel.remove_query_row(panel.query_rows[1])
        assert len(panel.query_rows) == 2

    def test_cannot_remove_last_row(self, panel):
        panel.remove_query_row(panel.query_rows[0])
        assert len(panel.query_rows) == 1

    def test_field_combo_has_all_qf_fields(self, panel):
        combo = panel.query_rows[0].field_combo
        codes = [combo.itemData(i) for i in range(combo.count())]
        assert codes == list(QF_FIELDS.keys())

    def test_get_search_config_reads_rows(self, panel):
        keys = list(QF_FIELDS.keys())
        r0 = panel.query_rows[0]
        r0.field_combo.setCurrentIndex(keys.index("au"))
        r0.keyword_edit.setText("王小明")
        panel.add_query_row()
        r1 = panel.query_rows[1]
        r1.field_combo.setCurrentIndex(keys.index("asc"))
        r1.keyword_edit.setText("臺灣大學")
        r1.operator_combo.setCurrentText("or")

        cfg = panel.get_search_config()
        assert (cfg.rows[0].field, cfg.rows[0].keyword) == ("au", "王小明")
        assert (cfg.rows[1].field, cfg.rows[1].keyword) == ("asc", "臺灣大學")
        assert cfg.rows[1].operator == "or"

    def test_first_row_operator_hidden(self, panel):
        assert panel.query_rows[0].operator_combo.isVisibleTo(panel) is False


class TestLimitFilters:
    def test_degree_defaults_checked(self, panel):
        cfg = panel.get_search_config()
        assert cfg.degree_master is True
        assert cfg.degree_doctor is True

    def test_uncheck_master(self, panel):
        panel._master_cb.setChecked(False)
        cfg = panel.get_search_config()
        assert cfg.degree_master is False
        assert cfg.degree_doctor is True

    def test_year_range(self, panel):
        panel._year_from_input.setValue(110)
        panel._year_to_input.setValue(113)
        cfg = panel.get_search_config()
        assert cfg.year_from == 110
        assert cfg.year_to == 113


class TestModeAndIds:
    def test_default_mode_search(self, panel):
        assert panel.get_mode() == "search"

    def test_switch_to_ids(self, panel):
        panel._ids_radio.setChecked(True)
        assert panel.get_mode() == "ids"

    def test_load_id_csv_dedups(self, panel, tmp_path):
        p = tmp_path / "ids.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["thesis_id"])
            for t in ["A1", "A2", "A1", "A3"]:
                w.writerow([t])
        panel.load_id_csv(str(p))
        assert panel.get_id_list() == ["A1", "A2", "A3"]


class TestStartSignal:
    def test_start_requested_emits_mode(self, panel, qtbot):
        with qtbot.waitSignal(panel.start_requested, timeout=1000) as blocker:
            panel._start_btn.click()
        assert blocker.args == ["search"]


def test_query_rows_capped_at_max(panel):
    from ndltd_spider.gui.search_panel import MAX_QUERY_ROWS
    for _ in range(MAX_QUERY_ROWS + 5):
        panel.add_query_row()
    assert len(panel.query_rows) == MAX_QUERY_ROWS
