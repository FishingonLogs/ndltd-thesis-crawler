"""Tests for ndltd_spider.scraper.detail — parse_detail and build_detail_url."""

import pathlib
import pytest

from ndltd_spider.scraper.detail import (
    DetailNotFoundError,
    build_detail_url,
    extract_thesis_id,
    parse_detail,
)
from ndltd_spider.models import LABEL_MAP, ThesisRecord

FIXTURE_PATH = pathlib.Path(__file__).parent.parent / "fixtures" / "detail_sample.html"
SAMPLE_THESIS_ID = "110NKUS0320041"


@pytest.fixture(scope="module")
def sample_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed_record(sample_html: str) -> ThesisRecord:
    return parse_detail(sample_html, SAMPLE_THESIS_ID)


class TestBuildDetailUrl:
    def test_returns_correct_url_format(self):
        url = build_detail_url("N7Hrxr", "110NKUS0320041")
        expected = (
            'https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi/ccd=N7Hrxr/search'
            '?q=id=%22110NKUS0320041%22.&searchmode=basic'
        )
        assert url == expected

    def test_interpolates_ccd_and_thesis_id(self):
        url = build_detail_url("ABCDE", "999TESTID")
        assert "ccd=ABCDE" in url
        assert '999TESTID' in url

    def test_contains_literal_percent22_encoded_quotes(self):
        url = build_detail_url("X", "Y")
        assert "%22Y%22" in url


class TestParseDetailKeyFields:
    def test_thesis_id_is_set_from_argument(self, parsed_record: ThesisRecord):
        assert parsed_record.thesis_id == SAMPLE_THESIS_ID

    def test_title_zh_contains_expected_text(self, parsed_record: ThesisRecord):
        assert "公司治理對股價異常報酬影響之研究" in parsed_record.title_zh

    def test_student_zh_is_chen_ying_xiang(self, parsed_record: ThesisRecord):
        assert parsed_record.student_zh == "陳英祥"

    def test_degree_is_doctor(self, parsed_record: ThesisRecord):
        assert parsed_record.degree == "博士"

    def test_university_is_nkust(self, parsed_record: ThesisRecord):
        assert parsed_record.university == "國立高雄科技大學"

    def test_exam_date_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.exam_date == "2022-07-18"

    def test_pages_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.pages == "100"

    def test_permanent_url_is_hdl_handle(self, parsed_record: ThesisRecord):
        assert parsed_record.permanent_url == "https://hdl.handle.net/11296/7rcrj5"

    def test_student_en_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.student_en == "Ying-Hsiang Chen"

    def test_pub_year_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.pub_year == "2022"

    def test_graduation_year_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.graduation_year == "110"

    def test_language_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.language == "中文"

    def test_field_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.field == "商業及管理學門"

    def test_subfield_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.subfield == "企業管理學類"

    def test_department_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.department == "國際企業系"

    def test_thesis_type_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.thesis_type == "學術論文"

    def test_keywords_zh_contains_expected(self, parsed_record: ThesisRecord):
        assert "公司治理" in parsed_record.keywords_zh

    def test_keywords_en_contains_expected(self, parsed_record: ThesisRecord):
        assert "corporate governance" in parsed_record.keywords_en

    def test_advisor_zh_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.advisor_zh == "姚名鴻"

    def test_advisor_en_parsed(self, parsed_record: ThesisRecord):
        assert parsed_record.advisor_en == "YAO,MING-HUNG"


class TestParseDetailAllFields:
    def test_all_label_map_fields_are_set(self, parsed_record: ThesisRecord):
        """LABEL_MAP 的每個目標屬性都應存在於 record。"""
        assert len(LABEL_MAP) == 23
        for attr in LABEL_MAP.values():
            assert hasattr(parsed_record, attr), f"Missing attribute: {attr}"

    def test_all_metadata_fields_are_strings(self, parsed_record: ThesisRecord):
        for attr in LABEL_MAP.values():
            value = getattr(parsed_record, attr)
            assert isinstance(value, str), f"Field {attr!r} should be str, got {type(value)}"

    def test_status_is_default_pending(self, parsed_record: ThesisRecord):
        assert parsed_record.status == "pending"

    def test_scraped_at_is_default_empty(self, parsed_record: ThesisRecord):
        assert parsed_record.scraped_at == ""

    def test_missing_field_returns_empty_string_not_error(self, sample_html: str):
        """Parsing a record whose HTML is missing some th ids should not raise."""
        minimal_html = (
            '<table id="format0_disparea">'
            '<tbody>'
            '<tr>'
            '<th id="format_0_table" class="std1">本論文永久網址:</th>'
            '<td class="std2"><input value="https://example.com"></td>'
            '</tr>'
            '</tbody>'
            '</table>'
        )
        record = parse_detail(minimal_html, "TEST001")
        assert record.thesis_id == "TEST001"
        assert record.permanent_url == "https://example.com"
        # Fields without matching th should be empty strings
        assert record.title_zh == ""
        assert record.degree == ""


class TestParseDetailErrorHandling:
    def test_raises_detail_not_found_when_format_0_table_missing(self):
        html = "<html><body><p>No data here</p></body></html>"
        with pytest.raises(DetailNotFoundError):
            parse_detail(html, "ANY_ID")

    def test_detail_not_found_error_is_exception_subclass(self):
        assert issubclass(DetailNotFoundError, Exception)

    def test_raises_detail_not_found_on_empty_html(self):
        with pytest.raises(DetailNotFoundError):
            parse_detail("", "ANY_ID")


class TestExtractThesisId:
    def test_extracts_from_dbid(self, sample_html):
        # 詳細頁的社群/書目連結含 dbid=<論文ID>，為穩定來源
        assert extract_thesis_id(sample_html) == SAMPLE_THESIS_ID

    def test_returns_none_when_absent(self):
        assert extract_thesis_id("<html><body>no id here</body></html>") is None


class TestLabelBasedParsing:
    def test_citation_stats_field(self, parsed_record):
        assert "被引用" in parsed_record.citation_stats

    def test_missing_committee_does_not_shift_fields(self):
        # th id 為位置編號；缺「口試委員」時以標籤對應仍正確（不位移）
        html = (
            "<table>"
            '<tr><th id="format_0_table_th_1">研究生:</th><td class="std2">王小明</td></tr>'
            '<tr><th id="format_0_table_th_2">論文名稱:</th><td class="std2">測試論文</td></tr>'
            '<tr><th id="format_0_table_th_3">學位類別:</th><td class="std2">碩士</td></tr>'
            '<tr><th id="format_0_table_th_4">校院名稱:</th><td class="std2">國立測試大學</td></tr>'
            "</table>"
        )
        r = parse_detail(html, "X")
        assert r.student_zh == "王小明"
        assert r.title_zh == "測試論文"
        assert r.degree == "碩士"            # 不因缺口試委員而位移
        assert r.university == "國立測試大學"
        assert r.committee_zh == ""          # 確實沒有 → 空


class TestTabContents:
    def test_abstract_zh(self, parsed_record):
        assert "本研究旨在" in parsed_record.abstract_zh

    def test_abstract_en(self, parsed_record):
        assert "From the perspective" in parsed_record.abstract_en

    def test_bibliography(self, parsed_record):
        # 注意：站方對「沈/李」等字用造字區(PUA)字元，故以穩定字串斷言
        assert "中文文獻" in parsed_record.bibliography
        assert "事件研究法" in parsed_record.bibliography

    def test_parse_tab_contents_classifies(self):
        from ndltd_spider.scraper.detail import parse_tab_contents
        html = (
            '<table><tr><td class="stdncl2">本研究探討中文摘要內容。</td></tr></table>'
            '<table><tr><td class="stdncl2">This English abstract describes the study.</td></tr></table>'
            '<table><tr><td class="stdncl2">第一章 緒論 1 目錄</td></tr></table>'
            '<table><tr><td class="stdncl2">王某 2001。李某 2010。陳某 2015。林某 2018。黃某 2020。吳某 2021。</td></tr></table>'
        )
        r = parse_tab_contents(html)
        assert "中文摘要" in r["abstract_zh"]
        assert "English abstract" in r["abstract_en"]
        assert "王某" in r["bibliography"]
        assert r["bibliography"].count("某") == 6
