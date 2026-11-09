"""CAPTCHA 偵測測試。

測試涵蓋：
  (a) url 含 captcha → True
  (b) DOM 有 id 含 captcha 的元素 → True
  (c) DOM 有 class 含 captcha 的元素 → True
  (d) 元素文字含「驗證碼」→ True
  (e) 大小寫混合 url（如 'Captcha'）→ True
  (f) 正常頁面 + 正常 url → False
"""

from pathlib import Path

import pytest

from ndltd_spider.scraper.captcha import is_captcha_page

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestIsCaptchaPageUrlDetection:
    """透過 url 偵測 CAPTCHA 頁。"""

    def test_returns_true_when_url_contains_captcha_lowercase(self):
        # Arrange
        html = "<html><body><p>normal</p></body></html>"
        url = "https://example.com/captcha/verify"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True

    def test_returns_true_when_url_contains_captcha_uppercase(self):
        # Arrange
        html = "<html><body><p>normal</p></body></html>"
        url = "https://example.com/Captcha/verify"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True

    def test_returns_true_when_url_contains_captcha_mixed_case(self):
        # Arrange
        html = "<html><body><p>normal</p></body></html>"
        url = "https://example.com/page?type=CAPTCHA"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True

    def test_returns_false_when_url_does_not_contain_captcha(self):
        # Arrange
        html = "<html><body><p>normal</p></body></html>"
        url = "https://example.com/thesis/detail?id=123"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is False


class TestIsCaptchaPageDomIdDetection:
    """透過 DOM 元素 id 屬性偵測 CAPTCHA 頁。"""

    def test_returns_true_when_element_id_contains_captcha_lowercase(self):
        # Arrange
        html = '<html><body><img id="captchaImage" src="/img.png"/></body></html>'
        url = "https://example.com/verify"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True

    def test_returns_true_when_element_id_contains_captcha_uppercase(self):
        # Arrange
        html = '<html><body><input id="CaptchaCode" type="text"/></body></html>'
        url = "https://example.com/verify"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True

    def test_returns_true_when_using_captcha_sample_fixture(self):
        # Arrange
        html = _load_fixture("captcha_sample.html")
        url = "https://example.com/verify"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True


class TestIsCaptchaPageDomClassDetection:
    """透過 DOM 元素 class 屬性偵測 CAPTCHA 頁。"""

    def test_returns_true_when_element_class_contains_captcha(self):
        # Arrange
        html = '<html><body><div class="captcha-box">...</div></body></html>'
        url = "https://example.com/verify"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True

    def test_returns_true_when_element_class_contains_captcha_among_multiple_classes(self):
        # Arrange
        html = '<html><body><div class="form-group captcha-container active">...</div></body></html>'
        url = "https://example.com/verify"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True

    def test_returns_true_when_element_class_contains_captcha_uppercase(self):
        # Arrange
        html = '<html><body><div class="CAPTCHA-area">...</div></body></html>'
        url = "https://example.com/verify"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True


class TestIsCaptchaPageTextDetection:
    """透過元素文字內容偵測 CAPTCHA 頁。"""

    def test_returns_true_when_text_contains_verification_code_chinese(self):
        # Arrange
        html = "<html><body><p>請輸入驗證碼後繼續。</p></body></html>"
        url = "https://example.com/verify"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True

    def test_returns_true_when_label_text_contains_verification_code_chinese(self):
        # Arrange
        html = '<html><body><label for="code">驗證碼</label><input id="code"/></body></html>'
        url = "https://example.com/verify"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is True


class TestIsCaptchaPageNegativeCases:
    """正常頁面不應被誤判為 CAPTCHA 頁。"""

    def test_returns_false_for_normal_page_with_normal_url(self):
        # Arrange
        html = _load_fixture("normal_sample.html")
        url = "https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi/ccd=xyz/record?r1=1"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is False

    def test_returns_false_for_empty_html_with_normal_url(self):
        # Arrange
        html = ""
        url = "https://ndltd.ncl.edu.tw/thesis/123"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is False

    def test_returns_false_when_captcha_word_only_in_comment(self):
        # Arrange
        # HTML 注釋中有 captcha，但不在任何元素屬性或文字節點中
        html = "<!-- captcha related old code --><html><body><p>正常頁面</p></body></html>"
        url = "https://example.com/normal"
        # Act
        result = is_captcha_page(html, url)
        # Assert
        assert result is False


class TestRealValidationPage:
    """以真實擷取的 NDLTD「驗證碼檢查機制」頁驗證（Task 3.6）。"""

    def test_detects_real_validation_page(self):
        html = _load_fixture("captcha_login_sample.html")
        url = "https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi/login?ssoauth=1"
        assert is_captcha_page(html, url) is True

    def test_detects_via_validinput_id_marker(self):
        # 即使未來站方拿掉「驗證碼」字樣，validinput 結構標記仍可偵測
        html = '<html><body><input type="text" name="validinput" id="validinput"></body></html>'
        assert is_captcha_page(html, "https://ndltd.ncl.edu.tw/x") is True

    def test_detects_via_validation_image_marker(self):
        html = '<html><body><img src="/gs32/images/random_validationimgs/AB12.jpg"></body></html>'
        assert is_captcha_page(html, "https://ndltd.ncl.edu.tw/x") is True


class TestLeafOnlyTextDetection:
    """「驗證碼」文字僅檢查葉節點，避免祖先彙總全頁文字造成誤判（xreview finding 4）。"""

    def test_text_split_across_children_not_flagged(self):
        # 「驗證碼」被拆散在不同子元素，無單一葉節點含完整字串 → 不誤判
        html = (
            "<html><body><div>"
            "<span>驗</span><span>證</span><span>碼</span>"
            "</div><p>正常內容</p></body></html>"
        )
        assert is_captcha_page(html, "https://example.com/normal") is False

    def test_leaf_text_still_detected(self):
        # 葉節點直接含「驗證碼」仍應偵測
        html = "<html><body><p>請輸入驗證碼</p></body></html>"
        assert is_captcha_page(html, "https://example.com/x") is True
