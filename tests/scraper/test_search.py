"""search.py 純解析函式測試 (Red)：總筆數、分頁資訊。

實際的搜尋導航/表單提交（submit_search）屬整合行為，手動驗證（Task 3.6）。
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from ndltd_spider.scraper.search import parse_total_count, parse_page_info, build_advanced_form_plan
from ndltd_spider.models import SearchConfig, QueryRow

FIXTURE = Path(__file__).parent.parent / "fixtures" / "search_result.html"
ADVANCED_FIXTURE = Path(__file__).parent.parent / "fixtures" / "advanced_search.html"


@pytest.fixture
def results_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def advanced_html() -> str:
    return ADVANCED_FIXTURE.read_text(encoding="utf-8")


def test_parse_total_count(results_html):
    # fixture 的搜尋結果頁顯示「檢索結果共 541 筆資料」
    assert parse_total_count(results_html) == 541


def test_parse_total_count_handles_thousands_separator():
    html = '<div>檢索結果共<span>&nbsp;1,234&nbsp;</span>筆資料</div>'
    assert parse_total_count(html) == 1234


def test_parse_total_count_returns_zero_when_absent():
    assert parse_total_count("<html><body>查無資料</body></html>") == 0


def test_parse_page_info(results_html):
    # fixture 為第 1 頁、共 28 頁
    current, total_pages = parse_page_info(results_html)
    assert current == 1
    assert total_pages == 28


# --- build_advanced_form_plan 單元測試（rows 模型）---

def _cfg(rows=None, **kw):
    return SearchConfig(rows=rows if rows is not None else [QueryRow()], **kw)


class TestBuildAdvancedFormPlanRows:
    def test_single_keyword_row_at_index_0_no_operator(self):
        plan = build_advanced_form_plan(_cfg([QueryRow(field="", keyword="機器學習")]))
        assert plan.rows[0] == (0, "", "機器學習", "")

    def test_multi_rows_carry_field_and_operator(self):
        plan = build_advanced_form_plan(_cfg([
            QueryRow(field="au", keyword="王小明"),
            QueryRow(field="asc", keyword="臺灣大學", operator="or"),
        ]))
        assert plan.rows == [
            (0, "au", "王小明", ""),
            (1, "asc", "臺灣大學", "or"),
        ]

    def test_empty_keyword_rows_filtered(self):
        plan = build_advanced_form_plan(_cfg([
            QueryRow(field="", keyword="機器學習"),
            QueryRow(field="au", keyword="   "),   # 空白 → 過濾
            QueryRow(field="asc", keyword="臺大", operator="not"),
        ]))
        assert plan.rows == [
            (0, "", "機器學習", ""),
            (1, "asc", "臺大", "not"),
        ]

    def test_all_empty_keeps_one_empty_row(self):
        plan = build_advanced_form_plan(_cfg([QueryRow(field="au", keyword="")]))
        assert plan.rows == [(0, "", "", "")]

    def test_default_config_one_empty_row(self):
        plan = build_advanced_form_plan(SearchConfig())
        assert plan.rows == [(0, "", "", "")]


class TestBuildAdvancedFormPlanDegrees:
    def test_only_doctor_when_master_false(self):
        plan = build_advanced_form_plan(_cfg(degree_master=False, degree_doctor=True))
        assert plan.degrees == ["博士"]

    def test_only_master_when_doctor_false(self):
        plan = build_advanced_form_plan(_cfg(degree_master=True, degree_doctor=False))
        assert plan.degrees == ["碩士"]

    def test_empty_degrees_when_both_false(self):
        plan = build_advanced_form_plan(_cfg(degree_master=False, degree_doctor=False))
        assert plan.degrees == []

    def test_both_degrees_when_both_true(self):
        plan = build_advanced_form_plan(_cfg())
        assert plan.degrees == ["碩士", "博士"]


class TestBuildAdvancedFormPlanYears:
    def test_year_from_string_when_nonzero(self):
        assert build_advanced_form_plan(_cfg(year_from=110)).year_from == "110"

    def test_year_from_empty_when_zero(self):
        assert build_advanced_form_plan(_cfg(year_from=0)).year_from == ""

    def test_year_to_string_when_nonzero(self):
        assert build_advanced_form_plan(_cfg(year_to=113)).year_to == "113"

    def test_year_from_set_but_year_to_empty(self):
        plan = build_advanced_form_plan(_cfg(year_from=110, year_to=0))
        assert plan.year_from == "110"
        assert plan.year_to == ""


# --- Fixture 結構測試（plan 選擇器存在於 advanced_search.html）---

class TestAdvancedSearchFixtureStructure:
    """驗證 advanced_search.html fixture 包含所需的表單元素。"""

    def test_qf0_select_exists(self, advanced_html):
        soup = BeautifulSoup(advanced_html, "html.parser")
        assert soup.find("select", attrs={"name": "qf0"}) is not None

    def test_qs0_input_exists(self, advanced_html):
        soup = BeautifulSoup(advanced_html, "html.parser")
        assert soup.find("input", attrs={"name": "qs0"}) is not None

    def test_ltyr_select_exists(self, advanced_html):
        soup = BeautifulSoup(advanced_html, "html.parser")
        assert soup.find("select", attrs={"name": "ltyr"}) is not None

    def test_eltyr_select_exists(self, advanced_html):
        soup = BeautifulSoup(advanced_html, "html.parser")
        assert soup.find("select", attrs={"name": "eltyr"}) is not None

    def test_mtty_master_checkbox_exists(self, advanced_html):
        soup = BeautifulSoup(advanced_html, "html.parser")
        assert soup.find("input", attrs={"name": "mtty", "value": "碩士"}) is not None

    def test_mtty_doctor_checkbox_exists(self, advanced_html):
        soup = BeautifulSoup(advanced_html, "html.parser")
        assert soup.find("input", attrs={"name": "mtty", "value": "博士"}) is not None


def test_build_advanced_url():
    from ndltd_spider.scraper.search import build_advanced_url
    url = build_advanced_url("N7Hrxr")
    assert url == "https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi/ccd=N7Hrxr/search?mode=advance"
