"""BrowserSession 純函式測試：ccd 解析。

啟動瀏覽器、導航等整合行為屬手動驗證（Task 3.6），不在此單元測試。
"""

from ndltd_spider.scraper.session import BrowserSession


def test_extract_ccd_from_search_url():
    url = "https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi/ccd=N7Hrxr/search?q=id=%22110NKUS0320041%22."
    assert BrowserSession._extract_ccd(url) == "N7Hrxr"


def test_extract_ccd_from_record_url():
    url = "https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi/ccd=AbC123/record"
    assert BrowserSession._extract_ccd(url) == "AbC123"


def test_extract_ccd_returns_none_when_absent():
    assert BrowserSession._extract_ccd("https://ndltd.ncl.edu.tw/") is None
    assert BrowserSession._extract_ccd("https://example.com/page") is None
