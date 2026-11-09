# Spec: NDLTD 博碩士論文爬蟲工具 v1

## 目標

提供一個 PyQt6 桌面應用程式，讓研究者能以搜尋條件或論文 ID 清單兩種方式，批次爬取臺灣博碩士論文知識加值系統（ndltd.ncl.edu.tw）的論文 metadata，並儲存為 SQLite 資料庫，支援斷點續爬與 CSV 匯出。

## 非目標

- 全文 PDF 下載
- 自動 CAPTCHA 解題（第三方服務）
- 代理 IP 池 / 分散式爬取
- 雲端部署 / 排程爬取
- 登入會員帳號功能

---

## User Stories

### US-1：搜尋模式爬取

作為研究者，我想要在 GUI 輸入搜尋條件（關鍵字、學位、年份、學校等），以便自動收集符合條件的論文 ID 清單並批次爬取 metadata。

**驗收條件**
- [ ] GUI 提供以下搜尋欄位（皆為選填）：
  - 關鍵字（論文名稱／摘要）
  - 學位類別：碩士 / 博士（可複選）
  - 畢業學年度範圍（起始～結束，民國學年度）
  - 學校名稱
  - 系所名稱
  - 其他進階欄位（依網站表單支援）
- [ ] 按下「開始爬」後，系統導航至搜尋頁、填入條件、提交，取得搜尋結果總筆數
- [ ] 逐筆以結果序號導航（`record?r1=N`）載入詳細頁，從詳細頁解析論文 ID（`dbid`）後進入爬取流程（US-3）
- [ ] 搜尋結果總筆數顯示在進度面板

> **機制說明**：搜尋結果清單頁的標題連結只帶結果序號 `r1=N`（不含論文 ID），論文 ID 僅可靠地出現在詳細頁（`dbid=...`）。因此搜尋模式以「總筆數 + 逐序號 `record?r1=N` 導航」取代「先收集所有 ID」。詳見 ADR-6。

### US-2：ID 清單模式爬取

作為研究者，我想要匯入一份含論文 ID 的 CSV 檔，以便直接爬取指定論文的 metadata，不需要透過搜尋。

**驗收條件**
- [ ] GUI 提供「匯入 ID 清單」按鈕，開啟檔案選擇器（過濾 `.csv`）
- [ ] CSV 格式：至少有一欄名為 `thesis_id`，每列一筆 ID（如 `110NKUS0320041`）
- [ ] 匯入後 ID 數量顯示在 GUI
- [ ] 按下「開始爬」後直接進入詳細頁爬取流程（US-3），略過搜尋步驟

### US-3：詳細頁 Metadata 爬取

作為系統，我需要對每筆論文 ID 爬取詳細頁的完整 metadata，並儲存至 SQLite。

**驗收條件**
- [ ] 對每筆 ID 組出詳細頁 URL 並以 Playwright 導航：
  `https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi/ccd={ccd}/search?q=id=%22{id}%22.&searchmode=basic`
  （`ccd` 值由 Playwright 進入首頁後從當前 URL 解析取得；`%22` 為雙引號的 URL 編碼）
- [ ] 解析以下 23 個欄位（th id → td.std2 配對）：

  | 欄位名稱       | th id                    |
  |----------------|--------------------------|
  | 本論文永久網址 | `format_0_table`         |
  | 研究生         | `format_0_table_th_1`    |
  | 研究生(外文)   | `format_0_table_th_2`    |
  | 論文名稱       | `format_0_table_th_3`    |
  | 論文名稱(外文) | `format_0_table_th_4`    |
  | 指導教授       | `format_0_table_th_5`    |
  | 指導教授(外文) | `format_0_table_th_6`    |
  | 口試委員       | `format_0_table_th_7`    |
  | 口試委員(外文) | `format_0_table_th_8`    |
  | 口試日期       | `format_0_table_th_9`    |
  | 學位類別       | `format_0_table_th_10`   |
  | 校院名稱       | `format_0_table_th_11`   |
  | 系所名稱       | `format_0_table_th_12`   |
  | 學門           | `format_0_table_th_13`   |
  | 學類           | `format_0_table_th_14`   |
  | 論文種類       | `format_0_table_th_15`   |
  | 論文出版年     | `format_0_table_th_16`   |
  | 畢業學年度     | `format_0_table_th_17`   |
  | 語文別         | `format_0_table_th_18`   |
  | 論文頁數       | `format_0_table_th_19`   |
  | 中文關鍵詞     | `format_0_table_th_20`   |
  | 外文關鍵詞     | `format_0_table_th_21`   |
  | 相關次數(書目) | `format_0_table_th_22`   |

- [ ] 欄位不存在時填入空字串，不中斷爬取
- [ ] 每筆爬完後立即寫入 SQLite（論文 ID 為去重主鍵）
- [ ] 每筆請求之間等待 `[delay_min, delay_max]` 秒（預設 2～5 秒，可在 config 調整）

### US-4：CAPTCHA 人工介入

作為使用者，我希望系統偵測到 CAPTCHA 時能暫停並提示我，讓我手動解題後繼續，而不是直接失敗。

**驗收條件**
- [ ] 偵測條件：頁面 URL 含 `captcha`；或 HTML 含站方驗證碼資源標記 `random_validationimgs`；或 DOM 元素 id/name 含 `captcha`/`validinput`、class 含 `captcha`、文字含 `驗證碼`
  （已對真實「驗證碼檢查機制」頁實證，見 works.md M3 Task 3.6）
- [ ] 偵測到 CAPTCHA 時：
  1. Playwright 切換為 headful（顯示瀏覽器視窗）
  2. GUI 彈出 Dialog 提示：「偵測到驗證碼，請在瀏覽器視窗中完成驗證後，按下「繼續」」
  3. 爬蟲 worker 暫停等待 Dialog 確認
- [ ] 使用者按「繼續」後，worker 繼續、瀏覽器切回 headless
- [ ] CAPTCHA 事件記錄在日誌面板

### US-5：斷點續爬

作為使用者，我希望中斷後重新開始時，已爬完的論文不會被重複爬取。

**驗收條件**
- [ ] 每次爬取前查 SQLite，若 `thesis_id` 已存在且 `status = 'completed'`，跳過
- [ ] 進度面板顯示：已完成 / 總數 / 跳過（已存在）/ 失敗
- [ ] 失敗的論文（`status = 'failed'`）在下次執行時重試

### US-6：CSV 匯出

作為研究者，我想要將 SQLite 中的 metadata 匯出為 CSV，方便用 Excel 或 pandas 分析。

**驗收條件**
- [ ] GUI 提供「匯出 CSV」按鈕
- [ ] 開啟儲存路徑選擇器，使用者指定輸出路徑
- [ ] 匯出所有 `status = 'completed'` 的記錄
- [ ] CSV 欄位順序與資料結構一致，編碼為 UTF-8 with BOM（支援 Excel 直接開啟）
- [ ] 匯出完成後日誌顯示成功筆數

---

## 相關檔案

```
ndltd_spider/
├── main.py                  # 程式進入點，初始化 QApplication
├── config.py                # ScraperConfig dataclass，讀寫 config.json
├── gui/
│   ├── main_window.py       # QMainWindow，整合 SearchPanel + ProgressPanel
│   ├── search_panel.py      # 搜尋條件 + 模式切換 UI
│   └── progress_panel.py    # QProgressBar + 日誌 QTextEdit
├── scraper/
│   ├── worker.py            # ScraperWorker(QThread)，內部 asyncio.run()
│   ├── session.py           # BrowserSession：Playwright browser/context 生命週期
│   ├── search.py            # collect_ids()：搜尋頁導航、分頁、ID 收集
│   ├── detail.py            # parse_detail()：詳細頁解析（23 欄），回傳 ThesisRecord
│   └── captcha.py           # is_captcha_page()、handle_captcha()
└── storage/
    ├── database.py          # ThesisDB：SQLite CRUD、斷點續爬
    └── exporter.py          # export_csv()：pandas to_csv
```

---

## 介面 / 資料結構

### ThesisRecord（SQLite schema & Python dataclass）

```python
@dataclass
class ThesisRecord:
    thesis_id: str           # 主鍵，如 "110NKUS0320041"
    permanent_url: str
    student_zh: str
    student_en: str
    title_zh: str
    title_en: str
    advisor_zh: str
    advisor_en: str
    committee_zh: str
    committee_en: str
    exam_date: str
    degree: str              # "碩士" / "博士"
    university: str
    department: str
    field: str
    subfield: str
    thesis_type: str
    pub_year: str
    graduation_year: str
    language: str
    pages: str
    keywords_zh: str
    keywords_en: str
    references: str          # 相關次數（完整書目，可能很長）
    scraped_at: str          # ISO 8601
    status: str              # "pending" / "completed" / "failed"
    error_msg: str           # 失敗原因，成功時為空字串
```

### SearchConfig

```python
@dataclass
class SearchConfig:
    keywords: str = ""
    degree_master: bool = True
    degree_doctor: bool = True
    year_from: int = 0       # 0 表示不限
    year_to: int = 0
    university: str = ""
    department: str = ""
    extra_fields: dict = field(default_factory=dict)  # 進階欄位
```

### ScraperConfig

```python
@dataclass
class ScraperConfig:
    delay_min: float = 2.0   # 請求間最小延遲（秒）
    delay_max: float = 5.0   # 請求間最大延遲（秒）
    max_retries: int = 3
    db_path: str = "ndltd.db"
    headless: bool = True
```

### ScraperWorker QThread Signals

```python
class ScraperWorker(QThread):
    # 進度更新：(已完成數, 總數, 跳過數, 失敗數)
    progress_updated = Signal(int, int, int, int)
    # 即時日誌訊息
    log_message = Signal(str)
    # CAPTCHA 偵測：worker 暫停，等 GUI 呼叫 resume_after_captcha()
    captcha_detected = Signal()
    # 全部完成
    finished = Signal()
    # 無法恢復的錯誤
    error_occurred = Signal(str)
```

### GUI → Worker 控制介面

```python
worker.start_search(search_config: SearchConfig, scraper_config: ScraperConfig)
worker.start_from_ids(id_list: List[str], scraper_config: ScraperConfig)
worker.stop()                  # 請求停止（graceful）
worker.resume_after_captcha()  # CAPTCHA 解完後繼續
```

---

## 邊界案例

- **Case 1：搜尋結果 0 筆**
  系統在進度面板顯示「搜尋結果為 0 筆，請確認搜尋條件」，不進入爬取流程。

- **Case 2：論文詳細頁不存在（ID 無效）**
  Playwright 導航後若頁面無 `format_0_table` 元素，標記 `status = 'failed'`，`error_msg = 'detail_page_not_found'`，繼續下一筆。

- **Case 3：部分欄位缺失**
  某些較舊論文可能缺少外文欄位，對應欄位填入空字串，其餘欄位正常儲存。

- **Case 4：爬取中途按停止**
  Worker 在當前詳細頁爬完後才停止（不中斷單筆爬取），下次可從 `status = 'pending'` 的 ID 繼續。

- **Case 5：網路逾時**
  Playwright 設定 `timeout=30000ms`，逾時後重試最多 `max_retries` 次；仍失敗則標記 `status = 'failed'`。

- **Case 6：CSV 欄位含逗號或換行**
  pandas `to_csv` 自動加引號包覆，不需額外處理。

- **Case 7：相同 thesis_id 重複出現在 ID 清單 CSV**
  匯入時去重，進度面板顯示去重後的實際數量。

---

## ADR（Architecture Decision Record）

### ADR-1：選用 Playwright 而非 requests

**決策**：使用 Playwright（Chromium）作為 HTTP 層。

**原因**：網站 session 維護依賴 `ccd=XXXX` 參數與 browser cookie，Playwright browser context 自動處理 cookie 持久化，無需手工管理；CAPTCHA 出現時可直接切換 headful 讓使用者在同一個瀏覽器視窗操作，體驗最直接。

**替代方案**：`requests.Session`——session 手工維護可行，但 CAPTCHA 人工介入需另行截圖彈窗，體驗差。

### ADR-2：QThread 內以 Playwright 同步 API 驅動（無 asyncio）

**決策**：ScraperWorker 繼承 QThread，在 `run()` 中以 Playwright **同步 API**（`sync_playwright()`）逐步驅動爬蟲；主線程保持 GUI 響應，透過 signal/slot 通訊。CAPTCHA 暫停用 `threading.Event` 在 worker thread 阻塞等待 GUI 解除。

**原因**：Playwright 同時提供 sync 與 async API。爬蟲受速率限制本質為序列、單一 worker thread，用 sync API 可完全免去 asyncio event loop 的整合與除錯成本，程式更直觀。sync API 的限制（不可在含 asyncio loop 的線程使用、不可跨線程共用）在「單一專屬 QThread」架構下都不成問題。

**替代方案**：
- async API + `asyncio.run()`（原 v1 規劃）——可行但為序列爬蟲多引入一層 event loop，無實質效益，實作時改用 sync。
- qasync——讓 Qt 與 asyncio 共用 event loop，整合複雜、除錯困難。

### ADR-5：headless/headful 切換以 storage_state 重啟達成

**決策**：`BrowserSession.set_headless()` 在切換模式時匯出 `storage_state`、關閉舊瀏覽器、以新模式重啟並導回原頁面。

**原因**：Playwright 無法對「執行中」的瀏覽器切換 headless/headful。透過 storage_state 攜帶 cookie/session，重啟後導回 ccd URL 即可延續 session，讓 CAPTCHA 人工介入（切 headful）後能無縫接回 headless 爬取。

**替代方案**：全程 headful——簡單但佔桌面、速度略慢，且違背「預設 headless」需求。

### ADR-6：搜尋模式以結果序號（r1）導航，論文 ID 取自詳細頁

**決策**：搜尋模式不在結果清單頁收集論文 ID，而是讀取「總筆數」後，對每個結果序號導航 `record?r1=N&h1=0` 載入詳細頁，再從詳細頁以 `dbid=` 解析出論文 ID。`build_detail_url(id)`（`search?q=id=%22ID%22`）僅用於 ID 清單模式（US-2）。

**原因**：實測 recon fixture 發現——結果清單頁的標題連結 href 僅為 `record?r1=N`（N 為結果序號），**不含論文 ID**；每列也無 checkbox/hidden 帶完整 ID。20 筆中僅約 14 筆在次要連結（電子全文等）出現 ID，無法穩定收集。反觀詳細頁的社群/書目連結含 `dbid=<論文ID>`（出現多次，穩定）。故由詳細頁取 ID 最可靠。

**待 3.6 實測確認**：`record?r1=N` 的 N 是否為跨頁全域序號（1..總筆數），若是則可直接迭代 r1 而免解析分頁；若為單頁序號則需配合翻頁。實作預設採全域序號，3.6 驗證後若不符再調整為翻頁模式。

**影響續爬**：搜尋模式在載入詳細頁前無法得知論文 ID，故「跳過已完成」需在取得 ID 後判斷（仍會發出該筆的詳細頁請求）。ID 清單模式則可在請求前就跳過。

**替代方案**：硬從清單頁拼湊 ID——不完整（漏約 3 成），不可行。

### ADR-3：SQLite 為主儲存，標準庫 csv 做 CSV 匯出

**決策**：SQLite 存所有爬取狀態與結果，需要時再用標準庫 `csv` 模組匯出 CSV。

**原因**：SQLite 天然支援 `thesis_id` 主鍵去重、斷點續爬（查 status）、複雜查詢；CSV 直接覆蓋式寫入無法去重也無法追蹤狀態。匯出僅需「固定欄位順序 + UTF-8 BOM + 特殊字元跳脫」，標準庫 `csv.DictWriter`（`encoding='utf-8-sig'`）即完全滿足，無須為單一匯出動作引入 pandas 這個重量級依賴。

**替代方案**：
- 純 CSV 當主儲存——結構簡單但無法支援斷點續爬，批次失敗後需從頭重跑。
- pandas 匯出——功能足夠但為一次性寫檔引入大型依賴，不符比例（原 v1 規劃曾選此，simplify 階段改用標準庫）。

### ADR-4：相關次數（書目）欄位納入儲存

**決策**：爬取並儲存 `format_0_table_th_22`（相關次數，完整參考書目文字）。

**原因**：完整保留原始資料，避免日後需要重爬；SQLite TEXT 欄位可容納長文字。CSV 匯出時若書目過長，使用者可自行決定是否排除該欄。

**替代方案**：跳過此欄——簡化但損失資料完整性。
