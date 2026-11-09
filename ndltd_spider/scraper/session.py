"""Playwright 瀏覽器 session 管理。

封裝 Chromium 的啟動、ccd session 參數解析、headless/headful 切換與關閉。
採用 Playwright 同步 API：整個 session 在單一 worker thread 中同步驅動，
不需 asyncio（見 spec ADR-2）。
"""

import re

from playwright.sync_api import sync_playwright

# 網站進入點；首次造訪後伺服器會在 URL 路徑指派 ccd session 參數。
ENTRY_URL = "https://ndltd.ncl.edu.tw/"

# 從 URL 取出 ccd 值，例如 .../gsweb.cgi/ccd=N7Hrxr/search -> N7Hrxr
_CCD_RE = re.compile(r"ccd=([A-Za-z0-9]+)")


class BrowserSession:
    """管理單一 Playwright 瀏覽器 session 的生命週期。"""

    def __init__(self, headless: bool = True, timeout_ms: int = 30000):
        self._headless = headless
        self._timeout = timeout_ms
        self._pw = None
        self._browser = None
        self._context = None
        self.page = None
        self.ccd: str | None = None

    def start(self) -> "BrowserSession":
        """啟動瀏覽器、造訪進入點並解析 ccd。"""
        self._pw = sync_playwright().start()
        self._launch(self._headless)
        self.page.goto(ENTRY_URL, timeout=self._timeout)
        self.ccd = self._extract_ccd(self.page.url)
        return self

    def goto(self, url: str) -> None:
        """導航至指定 URL，待頁面穩定後更新 ccd。"""
        self.page.goto(url, timeout=self._timeout)
        # 等待可能的 JS 轉址/載入完成，避免隨後 content() 撞到「頁面導航中」
        try:
            self.page.wait_for_load_state("networkidle", timeout=self._timeout)
        except Exception:
            pass
        self.refresh_ccd()

    def content(self) -> str:
        """回傳當前頁面的 HTML。"""
        return self.page.content()

    def set_headless(self, headless: bool) -> None:
        """切換 headless/headful 模式。

        Playwright 無法對執行中的瀏覽器切換顯示模式，故匯出 storage_state
        後關閉舊瀏覽器、以新模式重啟，再導回原頁面；cookie/session 由
        storage_state 保留，ccd 仍有效。
        """
        if headless == self._headless:
            return
        state = self._context.storage_state()
        current_url = self.page.url
        self._close_browser()
        self._headless = headless
        self._launch(headless, storage_state=state)
        if current_url and current_url != "about:blank":
            self.page.goto(current_url, timeout=self._timeout)
            self.refresh_ccd()

    def close(self) -> None:
        """關閉瀏覽器與 Playwright。"""
        self._close_browser()
        if self._pw:
            self._pw.stop()
            self._pw = None

    def _launch(self, headless: bool, storage_state=None) -> None:
        self._browser = self._pw.chromium.launch(headless=headless)
        self._context = self._browser.new_context(storage_state=storage_state)
        self.page = self._context.new_page()
        self.page.set_default_timeout(self._timeout)

    def _close_browser(self) -> None:
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        self.page = None

    def refresh_ccd(self) -> None:
        """導航/提交後重新同步 ccd。

        優先從當前 URL 解析；若 URL 不含 ccd（例如經 /login 驗證頁轉址後），
        則退而從頁面內容的連結中解析（結果頁連結含 ccd=...）。
        """
        found = self._extract_ccd(self.page.url)
        if not found:
            try:
                found = self._extract_ccd(self.page.content())
            except Exception:
                found = None
        if found:
            self.ccd = found

    @staticmethod
    def _extract_ccd(url: str) -> str | None:
        """從 URL 解析 ccd session 參數，找不到時回傳 None。"""
        match = _CCD_RE.search(url)
        return match.group(1) if match else None
