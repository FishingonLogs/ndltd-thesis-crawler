"""詳細頁解析：parse_detail、build_detail_url、extract_thesis_id。"""

import re

from bs4 import BeautifulSoup

from ..models import LABEL_MAP, ThesisRecord

# gsweb CGI 的共用前綴（detail / record 兩種 URL 共用，避免兩處不同步）。
GSWEB_BASE = "https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi"

# 詳細頁社群/書目連結帶有 dbid=<論文ID>，為頁面中最穩定的論文 ID 來源。
_DBID_RE = re.compile(r"[?&]dbid=([0-9A-Za-z]+)")
# 壓縮空白用，預編譯避免每欄位重複查 re cache。
_WS_RE = re.compile(r"\s+")


class DetailNotFoundError(Exception):
    """詳細頁不存在或非預期格式（找不到 format_0_table 元素）。"""


def build_detail_url(ccd: str, thesis_id: str) -> str:
    """組出詳細頁 URL（ID 清單模式用，以論文 ID 查詢）。

    格式：{GSWEB_BASE}/ccd={ccd}/search?q=id=%22{thesis_id}%22.&searchmode=basic
    其中 %22 是雙引號的 URL 編碼，固定字面寫入。
    """
    return (
        f"{GSWEB_BASE}/ccd={ccd}/search"
        f"?q=id=%22{thesis_id}%22.&searchmode=basic"
    )


def extract_thesis_id(html: str) -> str | None:
    """從詳細頁 HTML 解析論文 ID（取自 dbid 參數），找不到時回傳 None。

    搜尋模式以結果序號導航詳細頁時，論文 ID 不在事先已知，需從頁面取得（見 ADR-6）。
    """
    match = _DBID_RE.search(html)
    return match.group(1) if match else None


def _clean_text(text: str) -> str:
    """壓縮多餘空白並 strip。"""
    return _WS_RE.sub(" ", text).strip()


def _extract_td_value(td) -> str:
    """從 td 元素取出顯示文字；若 td 含 input[value]，回傳其 value 屬性。"""
    if td is None:
        return ""

    input_tag = td.find("input")
    if input_tag and input_tag.get("value"):
        return _clean_text(input_tag["value"])

    return _clean_text(td.get_text())


def parse_detail(html: str, thesis_id: str) -> ThesisRecord:
    """解析詳細頁 HTML，回傳 ThesisRecord。

    - thesis_id 直接設為傳入值
    - metadata 依 th 「標籤文字」對應欄位（LABEL_MAP），避免缺列時整列位移
    - 摘要/參考文獻等分頁內容由 parse_tab_contents 取得
    - status 與 scraped_at 保持預設值（不在這裡設定）
    - 找不到 metadata 表的 th（id 以 format_0_table 開頭）時 raise DetailNotFoundError
    """
    soup = BeautifulSoup(html, "html.parser")

    metadata_ths = soup.find_all("th", id=re.compile(r"^format_0_table"))
    if not metadata_ths:
        raise DetailNotFoundError(
            f"找不到詳細頁 metadata 表，thesis_id={thesis_id!r}"
        )

    record = ThesisRecord(thesis_id=thesis_id)

    for th in metadata_ths:
        label = _clean_text(th.get_text()).rstrip(":：")
        attr = LABEL_MAP.get(label)
        if attr is None:
            continue  # 非已知欄位，略過
        td = th.find_next_sibling("td") or th.find_next("td")
        setattr(record, attr, _extract_td_value(td))

    tabs = parse_tab_contents(html, soup=soup)
    record.abstract_zh = tabs["abstract_zh"]
    record.abstract_en = tabs["abstract_en"]
    record.bibliography = tabs["bibliography"]
    return record


# 分頁內容分類用的特徵與閾值（集中為可調策略）。
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")          # 書目特徵：年份引用
_TOC_RE = re.compile(r"目錄|第[一二三四五六七八九十]+[章節]")  # 目次特徵
# 參考文獻通常含數十個年份引用；門檻設 5 以避免含少量年份的摘要被誤判為書目。
_BIB_MIN_YEARS = 5        # 年份引用數達此值才視為參考文獻
_EN_LATIN_RATIO = 0.5     # 拉丁字母比例超過此值視為英文摘要


def _latin_ratio(text: str) -> float:
    """非空白字元中拉丁字母所佔比例（判斷中/英文摘要）。"""
    letters = sum(1 for c in text if c.isascii() and c.isalpha())
    total = sum(1 for c in text if not c.isspace())
    return letters / total if total else 0.0


def parse_tab_contents(html: str, soup: BeautifulSoup | None = None) -> dict:
    """從詳細頁的分頁區塊（td.stdncl2）以內容特徵抽取摘要與參考文獻。

    分頁無可靠 DOM 錨點（同 id/href），故以內容分類取代脆弱的位置假設：
    - 參考文獻＝年份引用最多（≥3）的區塊
    - 英文摘要＝拉丁字母比例 > 0.5 的區塊
    - 中文摘要＝中文為主、非目次、非書目的區塊
    - 目次（含「目錄/第N章」）排除
    回傳 {"abstract_zh", "abstract_en", "bibliography"}。
    """
    soup = soup or BeautifulSoup(html, "html.parser")
    blocks = [_clean_text(td.get_text()) for td in soup.select("td.stdncl2")]
    blocks = [b for b in blocks if b]
    result = {"abstract_zh": "", "abstract_en": "", "bibliography": ""}
    if not blocks:
        return result

    year_counts = [len(_YEAR_RE.findall(b)) for b in blocks]
    bib_idx = max(range(len(blocks)), key=year_counts.__getitem__)
    if year_counts[bib_idx] >= _BIB_MIN_YEARS:
        result["bibliography"] = blocks[bib_idx]
    else:
        bib_idx = -1

    for i, block in enumerate(blocks):
        if i == bib_idx or _TOC_RE.search(block):
            continue
        if _latin_ratio(block) > _EN_LATIN_RATIO:
            if not result["abstract_en"]:
                result["abstract_en"] = block
        elif not result["abstract_zh"]:
            result["abstract_zh"] = block

    return result
