"""核心資料結構：論文紀錄與搜尋/爬蟲設定。

ThesisRecord 的欄位定義順序即為 CSV 匯出的欄位順序（單一事實來源）。
"""

from dataclasses import dataclass, field, fields


# 詳細頁 metadata 表：th 標籤文字 → ThesisRecord 屬性名。
# 以「標籤文字」對應而非 th 的數字 id，因為網站的 format_0_table_th_N 是按該頁
# 實際出現的列順序編號，缺列時會整列位移；標籤文字才是穩定的語意鍵。
LABEL_MAP: dict[str, str] = {
    "本論文永久網址": "permanent_url",
    "研究生": "student_zh",
    "研究生(外文)": "student_en",
    "論文名稱": "title_zh",
    "論文名稱(外文)": "title_en",
    "指導教授": "advisor_zh",
    "指導教授(外文)": "advisor_en",
    "口試委員": "committee_zh",
    "口試委員(外文)": "committee_en",
    "口試日期": "exam_date",
    "學位類別": "degree",
    "校院名稱": "university",
    "系所名稱": "department",
    "學門": "field",
    "學類": "subfield",
    "論文種類": "thesis_type",
    "論文出版年": "pub_year",
    "畢業學年度": "graduation_year",
    "語文別": "language",
    "論文頁數": "pages",
    "中文關鍵詞": "keywords_zh",
    "外文關鍵詞": "keywords_en",
    "相關次數": "citation_stats",
}


@dataclass
class ThesisRecord:
    """單筆論文的完整 metadata 與爬取狀態。thesis_id 為去重主鍵。"""

    thesis_id: str
    permanent_url: str = ""
    student_zh: str = ""
    student_en: str = ""
    title_zh: str = ""
    title_en: str = ""
    advisor_zh: str = ""
    advisor_en: str = ""
    committee_zh: str = ""
    committee_en: str = ""
    exam_date: str = ""
    degree: str = ""           # "碩士" / "博士"
    university: str = ""
    department: str = ""
    field: str = ""            # 學門
    subfield: str = ""         # 學類
    thesis_type: str = ""
    pub_year: str = ""
    graduation_year: str = ""
    language: str = ""
    pages: str = ""
    keywords_zh: str = ""
    keywords_en: str = ""
    citation_stats: str = ""   # 相關次數（被引用/點閱/評分/下載/收藏）
    abstract_zh: str = ""      # 中文摘要（分頁）
    abstract_en: str = ""      # 外文摘要（分頁）
    bibliography: str = ""     # 參考文獻書目（分頁）
    scraped_at: str = ""       # ISO 8601
    status: str = "pending"    # "pending" / "completed" / "failed"
    error_msg: str = ""


def record_columns() -> list[str]:
    """回傳 ThesisRecord 的欄位名稱（依定義順序），作為 CSV 欄位順序的單一來源。"""
    return [f.name for f in fields(ThesisRecord)]


# 進階查詢可選欄位（qf 代碼 → 顯示名），供 GUI 下拉與條件摘要共用。順序即下拉順序。
QF_FIELDS: dict[str, str] = {
    "": "不限欄位",
    "ti": "論文名稱",
    "au": "研究生",
    "asc": "校院名稱",
    "sdp": "系所",
    "pyr": "論文出版年",
    "ad": "指導教授",
    "say": "口試委員",
    "kw": "關鍵詞",
    "tc": "論文目次",
    "ab": "摘要",
    "rf": "論文參考文獻",
    "yr": "畢業學年度",
    "sglv1": "學門",
    "sglv2": "學類",
}

# 查詢列之間的布林運算子（qo 值）。
QUERY_OPERATORS = ("and", "or", "not")


@dataclass
class QueryRow:
    """一條進階查詢列：在某欄位查某關鍵字，operator 為與前一列的布林關係。"""

    field: str = ""            # qf 代碼，"" 表不限欄位
    keyword: str = ""
    operator: str = "and"      # 第 0 列忽略此值


@dataclass
class SearchConfig:
    """搜尋模式的查詢條件，皆為選填。

    rows：多列「欄位+關鍵字+運算子」的進階查詢；degree/year 為獨立限縮條件。
    """

    rows: list[QueryRow] = field(default_factory=lambda: [QueryRow()])
    degree_master: bool = True
    degree_doctor: bool = True
    year_from: int = 0         # 0 表示不限（民國學年度）
    year_to: int = 0
    extra_fields: dict = field(default_factory=dict)  # 學門/論文種類等限縮，預留

    def active_rows(self) -> list["QueryRow"]:
        """回傳有填關鍵字的查詢列（過濾空白列）。"""
        return [r for r in self.rows if r.keyword.strip()]


@dataclass
class ScraperConfig:
    """爬蟲執行參數，可由 config.json 持久化。"""

    delay_min: float = 2.0     # 請求間最小延遲（秒）
    delay_max: float = 5.0     # 請求間最大延遲（秒）
    max_retries: int = 3
    db_path: str = "ndltd.db"
    headless: bool = True
    output_dir: str = "output"  # 匯出集中目錄
    auto_export: bool = True    # 執行結束後是否自動匯出
