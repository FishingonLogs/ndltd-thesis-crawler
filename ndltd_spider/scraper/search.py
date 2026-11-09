"""搜尋頁解析與導航。

純解析函式（parse_total_count / parse_page_info）以 recon fixture 單元測試；
submit_search 為整合行為（驅動瀏覽器填表單、提交），於 Task 3.6 手動驗證。
"""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .detail import GSWEB_BASE
from .session import BrowserSession
from ..models import SearchConfig, QueryRow


@dataclass
class AdvancedFormPlan:
    """表單操作計畫：純資料，不含 Playwright 依賴。"""

    rows: list[tuple[int, str, str, str]]  # 每組 (index, qf_value, qs_value, qo_value)
    degrees: list[str]                     # mtty 要勾的值，子集 of {"碩士","博士"}
    year_from: str                         # ltyr 值；"" 表不限
    year_to: str                           # eltyr 值；"" 表不限


def build_advanced_form_plan(config: SearchConfig) -> AdvancedFormPlan:
    """純函式。將 SearchConfig.rows 映射為進階表單操作計畫。

    映射規則：
    - 過濾 keyword 為空白的查詢列；若全空則保留一列空查詢（送出＝不限）
    - 依序重新編號 0..，每列 → (index, row.field, row.keyword, qo)
      qo：index 0 為 ""（忽略）；index≥1 取 row.operator（and/or/not）
    - degrees：degree_master→加 "碩士"；degree_doctor→加 "博士"
    - year_from>0 → str(year_from) 否則 ""；year_to 同理
    """
    active = config.active_rows() or [QueryRow()]

    rows: list[tuple[int, str, str, str]] = []
    for idx, row in enumerate(active):
        qo = "" if idx == 0 else row.operator
        rows.append((idx, row.field, row.keyword, qo))

    degrees: list[str] = []
    if config.degree_master:
        degrees.append("碩士")
    if config.degree_doctor:
        degrees.append("博士")

    year_from = str(config.year_from) if config.year_from > 0 else ""
    year_to = str(config.year_to) if config.year_to > 0 else ""

    return AdvancedFormPlan(rows=rows, degrees=degrees, year_from=year_from, year_to=year_to)


# 「檢索結果共 N 筆」——N 可能含千分位逗號，標籤間以 nbsp 分隔（\s 可涵蓋）。
_TOTAL_RE = re.compile(r"檢索結果共\s*([0-9,]+)\s*筆")
# 跳頁輸入框後緊接「/<總頁數>」，例如 <input id="jmpage" ...>/28<font>頁
_TOTAL_PAGES_RE = re.compile(r'id="jmpage".*?/\s*(\d+)\s*<', re.S)


def parse_total_count(html: str) -> int:
    """解析搜尋結果總筆數；找不到時回傳 0。"""
    text = BeautifulSoup(html, "html.parser").get_text()
    match = _TOTAL_RE.search(text)
    return int(match.group(1).replace(",", "")) if match else 0


def parse_page_info(html: str) -> tuple[int, int]:
    """解析 (目前頁碼, 總頁數)；解析不到時各自預設為 1。"""
    soup = BeautifulSoup(html, "html.parser")
    jmpage = soup.find("input", id="jmpage")
    current = int(jmpage["value"]) if jmpage and jmpage.get("value", "").isdigit() else 1

    match = _TOTAL_PAGES_RE.search(html)
    total_pages = int(match.group(1)) if match else 1
    return current, total_pages


def build_record_url(ccd: str, r1: int) -> str:
    """組出「第 r1 筆結果」的詳細頁 URL（搜尋模式以結果序號導航，見 ADR-6）。"""
    return f"{GSWEB_BASE}/ccd={ccd}/record?r1={r1}&h1=0"


def build_advanced_url(ccd: str) -> str:
    """組出進階查詢頁 URL（含 qf0..qf9 多欄位表單）。"""
    return f"{GSWEB_BASE}/ccd={ccd}/search?mode=advance"


def submit_search(session: BrowserSession, config: SearchConfig) -> int:
    """導到進階查詢頁、套用查詢計畫填表單後送出，回傳搜尋結果總筆數。

    整合行為，依賴真實網站的表單結構。呼叫前 worker 應已處理進站驗證碼。
    找不到表單元件時立即報錯（附當前可見輸入框）。
    """
    page = session.page
    plan = build_advanced_form_plan(config)

    # 進階查詢表單在 mode=advance 頁（簡易頁無 qf 欄位）。導過去並等表單載入穩定。
    session.goto(build_advanced_url(session.ccd))
    try:
        page.wait_for_selector("select[name='qf0']", timeout=15000)
    except Exception as exc:
        raise RuntimeError(
            "找不到進階查詢表單 qf0；當前 URL=" + page.url
            + "；可見輸入框=" + _visible_inputs(page)
        ) from exc

    # 填入各查詢列
    for idx, qf_value, qs_value, qo_value in plan.rows:
        try:
            page.select_option(f"select[name='qf{idx}']", value=qf_value)
        except Exception as exc:
            raise RuntimeError(
                f"無法設定 qf{idx}={qf_value!r}；可見輸入框=" + _visible_inputs(page)
            ) from exc
        page.fill(f"input[name='qs{idx}']", qs_value)
        # 第 2 列起設定與前一列的布林運算子
        if idx >= 1 and qo_value:
            page.select_option(f"select[name='qo{idx}']", value=qo_value)

    # 勾選學位
    for degree in plan.degrees:
        page.check(f"input[name='mtty'][value='{degree}']")

    # 設定學年度
    if plan.year_from:
        page.select_option("select[name='ltyr']", value=plan.year_from)
    if plan.year_to:
        page.select_option("select[name='eltyr']", value=plan.year_to)

    # 送出：點進階頁的查詢鈕（#gs32search，其 onclick 觸發 gs32_quicksearch 送出）
    page.click("#gs32search")
    page.wait_for_load_state("networkidle")
    session.refresh_ccd()
    return parse_total_count(session.content())


def _visible_inputs(page) -> str:
    """列出當前頁可見的 input/select 之 name/id/type，供除錯定位表單欄位。"""
    try:
        items = page.eval_on_selector_all(
            "input,select,textarea",
            "els => els.map(e => `${e.tagName}[name=${e.name}|id=${e.id}|type=${e.type}]`)"
            ".filter((v,i,a)=>a.indexOf(v)===i)",
        )
        return ", ".join(items)
    except Exception:
        return "(無法取得)"
