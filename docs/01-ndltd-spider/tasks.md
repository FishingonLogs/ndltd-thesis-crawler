# Tasks: NDLTD 博碩士論文爬蟲工具 v1

> 對應 spec：`docs/01-ndltd-spider/spec.md`
> 測試框架：`pytest`（GUI signal 測試用 `pytest-qt`，瀏覽器互動為手動整合驗證）
> 開發順序建議：M1 → M2 →（M3 依賴 M2 的 detail/captcha）→ M4

---

## Milestone 1: 資料結構與儲存層（序列）

> 預期結果：ThesisRecord/SearchConfig/ScraperConfig 定義完成；SQLite 可建表、寫入、去重、查詢續爬狀態；可匯出 UTF-8 BOM 的 CSV；config.json 可讀寫。
> 驗證方式：`pytest tests/storage/ -v` 全過
> 對應 US：US-5（斷點續爬）、US-6（CSV 匯出）；為全專案的型別契約基礎

- [x] Task 1.1: 定義 `ThesisRecord` / `SearchConfig` / `ScraperConfig` dataclasses 與 `config.py` 的 config.json 讀寫函式（介面契約，無測試）
- [x] Task 1.2: 撰寫 `ThesisDB` 測試 (Red) — 建表、`upsert(record)`、以 `thesis_id` 去重、`get_status(id)`、`list_pending()` / `list_completed()`
- [x] Task 1.3: 實作 `storage/database.py` `ThesisDB` (Green)
- [x] Task 1.4: 撰寫 `exporter` 測試 (Red) — 匯出 completed 記錄、欄位順序固定、編碼 UTF-8 with BOM、特殊字元（逗號/換行）正確跳脫
- [x] Task 1.5: 實作 `storage/exporter.py` `export_csv(db, path)` (Green)

---

## Milestone 2: 頁面解析層（可平行）

> 預期結果：能從詳細頁 HTML 解析出 23 欄 metadata 組成 ThesisRecord；能判斷任一頁面是否為 CAPTCHA 頁；能由 ccd + thesis_id 組出詳細頁 URL。
> 驗證方式：`pytest tests/scraper/test_detail.py tests/scraper/test_captcha.py -v` 全過
> 依賴：Task 1.1 的 `ThesisRecord` 型別
> 對應 US：US-3（詳細頁爬取）、US-4（CAPTCHA 偵測）
> Fixture：詳細頁用 `範例/公司治理...html`；CAPTCHA 用自製 HTML 片段

### 🔀 可平行工作線

**[A] 詳細頁解析** — `isolation: worktree`
> 範圍：`scraper/detail.py`、`tests/scraper/test_detail.py`、`tests/fixtures/`（複製範例 HTML）
> 依賴：Task 1.1 的 `ThesisRecord`
> 介面契約：
>   - `build_detail_url(ccd: str, thesis_id: str) -> str`
>   - `parse_detail(html: str) -> ThesisRecord`（缺欄填空字串；無 `format_0_table` 元素時 raise `DetailNotFoundError`）
> 驗證方式：`pytest tests/scraper/test_detail.py -v` 全過——對範例 HTML 解析出 22 欄且值正確、缺欄案例填空、URL 組裝正確
- [x] Task 2.1: 複製範例 HTML 至 `tests/fixtures/detail_sample.html`，撰寫 `parse_detail` + `build_detail_url` 測試 (Red)
- [x] Task 2.2: 實作 `scraper/detail.py`（th id → td.std2 配對解析、URL 組裝、缺頁例外）(Green)

**[B] CAPTCHA 偵測** — `isolation: worktree`
> 範圍：`scraper/captcha.py`、`tests/scraper/test_captcha.py`、`tests/fixtures/captcha_sample.html`
> 依賴：無（純函式）
> 介面契約：`is_captcha_page(html: str, url: str) -> bool`（URL 含 `captcha` 或 DOM 含 `captcha`/`驗證碼` 元素時回傳 True）
> 驗證方式：`pytest tests/scraper/test_captcha.py -v` 全過——正常詳細頁回傳 False、CAPTCHA 片段回傳 True、URL 觸發條件正確
- [x] Task 2.3: 製作 `captcha_sample.html`，撰寫 `is_captcha_page` 測試 (Red)
- [x] Task 2.4: 實作 `scraper/captcha.py` `is_captcha_page` (Green)

---

## Milestone 3: 爬蟲引擎（序列，含 recon）

> 預期結果：Playwright 可啟動 session 並解析 ccd；可送出搜尋條件、翻頁收集所有論文 ID；ScraperWorker 可逐筆爬詳細頁、套用速率延遲、偵測 CAPTCHA 暫停、跳過已完成、寫入 DB 並 emit 進度 signal。
> 驗證方式：對真實網站手動執行小批量（3 筆 ID）端到端，確認寫入 DB；search 對 recon fixture 收集 ID 數量正確（`pytest tests/scraper/test_search.py -v`）
> 依賴：M1（DB）、M2（detail、captcha）
> 對應 US：US-1（搜尋模式）、US-2（ID 清單）、US-3、US-4、US-5
> ⚠️ 注意：Task 3.2 recon 會對真實網站發請求，需套用速率限制

- [x] Task 3.1: 實作 `scraper/session.py` `BrowserSession`（Playwright browser/context 啟動、進首頁解析 `ccd`、headless↔headful 切換、`close()`）—— sync API；ccd 解析有單元測試，啟動/導航手動驗證
- [x] Task 3.2: Recon —— 使用者手動存搜尋結果頁 HTML 至 `tests/fixtures/search_result.html`（共 541 筆、28 頁範例）
- [ ] Task 3.3: 撰寫解析測試 (Red) —— `search.parse_total_count`（→541）、`search.parse_page_info`（→(1,28)）、`detail.extract_thesis_id`（→110NKUS0320041）
- [ ] Task 3.4: 實作 (Green) —— `scraper/search.py`：`parse_total_count`、`parse_page_info`（純函式）、`submit_search(session, search_config) -> int`（整合：填表單、提交、回傳總筆數）；`detail.extract_thesis_id(html)`（純函式，`dbid=`）
- [ ] Task 3.5: 實作 `scraper/worker.py` `ScraperWorker(QThread)`：`start_search` / `start_from_ids` / `stop` / `resume_after_captcha`，整合 session+search+detail+captcha+db，emit `progress_updated`/`log_message`/`captcha_detected`/`finished`/`error_occurred`，套用 `[delay_min, delay_max]` 隨機延遲、跳過已 completed、重試 failed。搜尋模式逐 `record?r1=N` 導航取 ID
- [x] Task 3.6: live 驗證 —— ✅ session/ccd、✅ ID 清單模式端到端解析、✅ CAPTCHA 偵測對真實驗證頁成功（已強化偵測+測試）。✅ 殘留已於 M4 互動驗證解決：`submit_search` 的 `qs0` 選擇器**確認正確**、`record?r1=N` 導航**確認可用**

---

## Milestone 4: GUI 與整合（部分平行）

> 預期結果：使用者可在 GUI 設定搜尋條件或匯入 ID 清單、開始/停止爬取、即時看進度與日誌、遇 CAPTCHA 時依 Dialog 提示完成驗證後繼續、匯出 CSV。
> 驗證方式：手動操作 GUI 完成「搜尋模式」與「ID 清單模式」各一次完整流程，並成功匯出 CSV
> 依賴：M3（ScraperWorker 及其 signals）
> 對應 US：US-1、US-2、US-4、US-6

### 🔀 可平行工作線

**[A] 搜尋條件面板** — `isolation: worktree`
> 範圍：`gui/search_panel.py`、`tests/gui/test_search_panel.py`
> 依賴：Task 1.1 的 `SearchConfig` 型別
> 介面契約：
>   - `SearchPanel.get_search_config() -> SearchConfig`
>   - `SearchPanel.get_id_list() -> List[str]`（讀取匯入的 CSV，去重）
>   - emit signal `start_requested(mode: str)`（mode = "search" | "ids"）
> 驗證方式：`pytest tests/gui/test_search_panel.py -v`——填欄位後 `get_search_config()` 回傳值正確、匯入 CSV 後 `get_id_list()` 去重正確
- [x] Task 4.1: 撰寫 `SearchPanel` 測試 (Red) —— 欄位 → SearchConfig 映射、CSV 匯入去重、模式切換
- [x] Task 4.2: 實作 `gui/search_panel.py`（關鍵字/學位複選/學年度範圍/學校/系所 + 匯入 ID 按鈕）(Green)

**[B] 進度與日誌面板** — `isolation: worktree`
> 範圍：`gui/progress_panel.py`、`tests/gui/test_progress_panel.py`
> 依賴：無（接收 worker signal 的純顯示元件）
> 介面契約：
>   - `ProgressPanel.update_progress(done, total, skipped, failed)`
>   - `ProgressPanel.append_log(msg: str)`
> 驗證方式：`pytest tests/gui/test_progress_panel.py -v`——呼叫 update_progress 後進度條與標籤文字正確、append_log 後日誌內容正確
- [x] Task 4.3: 撰寫 `ProgressPanel` 測試 (Red) —— 進度更新與日誌顯示
- [x] Task 4.4: 實作 `gui/progress_panel.py`（QProgressBar + 統計標籤 + 日誌 QTextEdit）(Green)

### 🔗 匯合點

> 驗證方式：手動端到端（搜尋模式 + ID 模式 + CSV 匯出各一次）
- [x] Task 4.5: 實作 `gui/main_window.py`（整合兩面板、按鈕列、連接 ScraperWorker signals、CAPTCHA QMessageBox 提示與 `resume_after_captcha`、匯出 CSV 流程）+ 冒煙測試
- [x] Task 4.6: 實作 `ndltd_spider/main.py` 進入點（QApplication）。✅ 真實站台手動端到端**確認成功**：搜尋模式（關鍵字→驗證碼人工解→「搜尋結果共 N 筆」→逐筆「完成」）端到端打通；CAPTCHA 人工介入流程順暢；CSV 匯出可用

---

## 平行評估摘要

| Milestone | 平行性 | 理由 |
|-----------|--------|------|
| M1 儲存層 | 序列 | 型別契約 → DB → exporter 為線性依賴 |
| M2 解析層 | 🔀 2 線 | detail.py / captcha.py 檔案不重疊，唯讀依賴 ThesisRecord |
| M3 引擎層 | 序列 | session → search → worker 生命週期依賴；含 recon 前置 |
| M4 GUI | 🔀 2 線 + 匯合 | 兩面板獨立，main_window 整合為匯合點 |
