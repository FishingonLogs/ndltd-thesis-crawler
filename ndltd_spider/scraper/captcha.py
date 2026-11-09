"""CAPTCHA 頁面偵測。

NDLTD 在請求量大時會以「驗證碼檢查機制」頁面攔截（input#validinput +
random_validationimgs 圖片），需人工輸入圖形驗證碼。此模組同時涵蓋通用
captcha 命名與該站實際的結構性標記（已對真實驗證頁驗證，見 works.md M3）。
"""

from bs4 import BeautifulSoup

# 出現在 id/name 即視為驗證頁的標記（不分大小寫）。
_ID_MARKERS = ("captcha", "validinput")
# 出現在 HTML 任意處即視為驗證頁的標記（站方圖形驗證碼資源路徑）。
_HTML_MARKERS = ("random_validationimgs",)


class CaptchaUnsolvedError(Exception):
    """驗證碼多次嘗試仍未通過（用於與「詳細頁不存在」區隔錯誤類型）。"""


def is_captcha_page(html: str, url: str) -> bool:
    """判斷頁面是否為 CAPTCHA 驗證頁。

    回傳 True 的條件（任一成立）：
      1. url 含 'captcha'（不分大小寫）
      2. HTML 含站方驗證碼資源標記（random_validationimgs）
      3. DOM 中任一元素的 id/name 含 captcha 或 validinput（不分大小寫）、
         class 含 'captcha'、或元素文字含 '驗證碼'
    否則回傳 False。
    """
    if "captcha" in url.lower():
        return True

    if not html:
        return False

    lower_html = html.lower()
    if any(marker in lower_html for marker in _HTML_MARKERS):
        return True

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        identifier = f"{tag.get('id', '') or ''} {tag.get('name', '') or ''}".lower()
        if any(marker in identifier for marker in _ID_MARKERS):
            return True

        tag_classes = tag.get("class") or []
        if any("captcha" in css_class.lower() for css_class in tag_classes):
            return True

        # 「驗證碼」文字只檢查葉節點自身內容，避免祖先元素彙總全頁文字造成誤判
        # （正常頁面偶有提及「驗證碼」時不應整頁被判為驗證頁）。
        if tag.find(True) is None and "驗證碼" in tag.get_text():
            return True

    return False
