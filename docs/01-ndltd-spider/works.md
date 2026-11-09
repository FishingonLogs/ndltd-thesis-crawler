# Works: NDLTD 爬蟲開發日誌

## Milestone 1: 資料結構與儲存層 ✅

完成日期：2026-06-04
測試結果：12 passed（tests/storage/）

### 技術決策

- **專案環境**：Python 3.13，建立 `.venv` 隔離（後續要裝 PyQt6 / playwright，避免污染全域）。`pyproject.toml` 管理依賴與 pytest 設定。
- **單一事實來源**：`ThesisRecord` dataclass 的欄位定義順序同時決定
  - SQLite 表格 schema（`database.py` 由 `record_columns()` 自動推導建表，新增欄位免改 schema）
  - CSV 匯出的欄位順序
  避免欄位清單在多處重複定義。
- **metadata 欄位數修正**：spec 原寫「22 欄」，實際為 **23 欄**（`format_0_table` + `th_1`～`th_22`）。已修正 spec.md / tasks.md 的計數標籤（欄位清單本身原本就完整正確）。
- **SQL 保留字**：`references`（相關次數欄）是 SQL 保留字，所有欄位名一律用雙引號包裹（通用處理，非只對 references 打特例）。

### 介面產出

- `ndltd_spider/models.py`：`ThesisRecord`(23 metadata + thesis_id/scraped_at/status/error_msg = 27 欄)、`SearchConfig`、`ScraperConfig`、`record_columns()`、`METADATA_TH_IDS`(供 M2 detail 解析)
- `ndltd_spider/config.py`：`load_config()` / `save_config()`（config.json，忽略未知鍵）
- `ndltd_spider/storage/database.py`：`ThesisDB`（upsert 去重、get/get_status、list_completed/list_pending、get_completed_records、count_by_status）
- `ndltd_spider/storage/exporter.py`：`export_csv(db, path) -> int`

### Simplify 階段修正（4 agent 並行審查）

採納：
1. `_row_to_record` 改用模組級 `_COLUMNS`，不每筆 `fields()` 內省
2. 三條 ID 查詢合併為 `_query_ids(where)` helper（DRY）
3. upsert 的 SQL 字串改模組載入時預算常數，逐筆寫入不重組
4. `config.py` 移除多餘的 set comprehension
5. **exporter 改用標準庫 `csv.DictWriter`**（原規劃用 pandas）：三個 agent 指出為單一匯出引入 pandas 太重；stdlib csv 同樣支援 utf-8-sig BOM 與引號跳脫。連帶更新 ADR-3、移除 pandas 執行期依賴 → **M1 零第三方執行期依賴**。

跳過：
- WAL / `synchronous=NORMAL`：屬效能 vs 續爬可靠性取捨，併發讀需求在 M3/M4 才出現，YAGNI。

### 給後續 milestone 的注意事項

- M2 detail 解析可直接用 `METADATA_TH_IDS`（attr name → th id 映射）組 ThesisRecord
- 續爬邏輯：worker 對每個 id 呼叫 `db.get_status(id)`，== "completed" 則跳過；failed 會被 `list_pending()` 收入重試

---

## Milestone 2: 頁面解析層 ✅

完成日期：2026-06-04
測試結果：58 passed（全套件，含 M1 12 + detail 31 + captcha 15）

### 執行模式：平行（coordinator 派發 2 worker）

- 原規劃用 `isolation: worktree`，但 session 啟動時此資料夾尚非 git repo（事後才 `git init`），harness 的 git 偵測已快取為 false，**worktree 隔離不可用**。
- 改用「非隔離但檔案範圍完全互斥」的並行：coordinator 先建立兩條線共用的 `__init__.py` 與 `tests/fixtures/`，再派發 2 個背景 ddd-developer，各自只動互斥檔案、各跑自己的測試檔（`-p no:cacheprovider` 避免 cache 競爭）。零衝突。

### 介面契約（M3 worker 會用到）

- `scraper/detail.py`
  - `build_detail_url(ccd, thesis_id) -> str`
  - `parse_detail(html, thesis_id) -> ThesisRecord`（**簽名比 spec 多帶 thesis_id**：呼叫端本來就握有 id，避免從頁面脆弱地反推）
  - `DetailNotFoundError`：缺 `format_0_table` 元素時 raise
  - parse_detail 不設 status/scraped_at（保持純函式，那是 worker/DB 層職責）
- `scraper/captcha.py`
  - `is_captcha_page(html, url) -> bool`（url 含 captcha / DOM id|class 含 captcha / 文字含「驗證碼」）

### 技術決策與發現

- **permanent_url 特殊格式**：`format_0_table` 那格的值在 `<input value="...">` 而非純文字，detail 的 `_extract_td_value` 偵測到 td 內有 input[value] 時取 value 屬性（通用機制，非只針對該欄）。
- **td 取法**：優先 `find_next_sibling("td")`（限定同一 `<tr>`），fallback `find_next("td")`。
- Coordinator 驗收清理：detail.py 改相對 import（與 M1 一致）、移除缺欄分支多餘的 setattr。

### 環境註記

- 解析用 BeautifulSoup4（已加入 pyproject 依賴並裝入 .venv）。
- worker 一律用主 .venv 的絕對路徑直譯器執行測試（cwd 帶入 worktree/主目錄程式碼）。

---

## Milestone 3: 爬蟲引擎 ✅（含 live 驗證）

完成日期：2026-06-04
測試結果：74 passed（全套件）

### 介面產出

- `scraper/session.py` `BrowserSession`：Playwright **同步** API（ADR-2 由 async 改 sync）。start/goto/content/`refresh_ccd`(公開)/`set_headless`(storage_state 重啟，ADR-5)/close；`_extract_ccd` 純函式有測試。
- `scraper/search.py`：`parse_total_count`(→541)、`parse_page_info`(→(1,28))、`build_record_url`、`submit_search`（整合）。
- `scraper/detail.py` 新增 `extract_thesis_id`（`dbid=`）；`GSWEB_BASE` 常數；`parse_detail` 改單趟 O(n) 解析。
- `scraper/worker.py` `ScraperWorker(QThread)`：信號 `progress_updated`/`log_message`/`captcha_detected`/`scrape_finished`(避開 QThread 內建 finished)/`error_occurred`；`start_search`/`start_from_ids`/`stop`/`resume_after_captcha`；CAPTCHA 用 `threading.Event` 阻塞、速率延遲、續爬跳過。

### 關鍵架構發現（實測 recon fixture）

- **搜尋模式以 r1 序號導航**（ADR-6）：結果清單頁標題連結只帶 `r1=N`（不含論文 ID），ID 僅可靠出現在詳細頁 `dbid=`。故搜尋模式＝讀總筆數 → 逐 `record?r1=N` → 詳細頁取 ID。`build_detail_url(id)` 僅供 ID 清單模式。
- 搜尋結果頁 fixture 為 UTF-8（中文在 console 顯示會亂碼，但檔案正確）；總筆數在全頁文字「檢索結果共 N 筆」。

### Task 3.6 Live 驗證結果（最小化、限速）

對真實 ndltd.ncl.edu.tw 做了少量請求：

- ✅ `BrowserSession.start()` 取得 ccd（如 gRNAED）
- ✅ **ID 清單模式端到端可用**：`build_detail_url` + `parse_detail` 對真實站台解析出正確 title/university/degree；`extract_thesis_id` 正確
- ✅ **CAPTCHA 偵測對真實驗證頁驗證成功**：站方在數次請求後即跳「驗證碼檢查機制」頁（`/login` URL、`input#validinput`、`random_validationimgs` 圖片、文字「請輸入圖形驗證碼」）。已擷取為 `tests/fixtures/captcha_login_sample.html`，並**強化 `is_captcha_page`**（新增 `validinput`/`random_validationimgs` 結構標記）+ 3 個真實頁測試。這證實了「人工介入解 CAPTCHA」架構的必要性。
- ⚠️ **`submit_search` 表單選擇器（`qs0`）未驗證**：因當時 session 已被驗證碼閘門攔截，無法到達搜尋表單。延後到 M4（GUI 可互動解 CAPTCHA 後）驗證並視實況調整選擇器。
- ❓ **`record?r1=N` 是否為全域序號未驗證**（同樣被閘門擋）：延後到 M4。

### 給 M4 的注意事項

- CAPTCHA 會頻繁出現，人工介入流程是核心；GUI 必須把 `captcha_detected` 接到對話框、解完呼叫 `resume_after_captcha()`。
- M4 整合測試時需在能互動解 CAPTCHA 的情況下，補驗 `submit_search` 選擇器與 r1 全域序號假設（tasks 3.6 殘留項）。

---

## Milestone 4: GUI 與整合 ✅（程式碼 + 冒煙測試；真實站台 e2e 待使用者執行）

完成日期：2026-06-04
測試結果：115 passed（全套件）

### 執行模式：平行（coordinator 派發 2 worker）+ 匯合

- 與 M2 同因（worktree 不可用）改用「檔案互斥非隔離並行」。
- [A] `gui/search_panel.py`（23 tests）、[B] `gui/progress_panel.py`（14 tests）並行；匯合由 coordinator 寫 `gui/main_window.py` + `main.py`（4 冒煙測試）。
- GUI 測試用 pytest-qt，環境變數 `QT_QPA_PLATFORM=offscreen` 執行。

### 介面產出

- `SearchPanel`：`get_search_config()`/`load_id_csv()`/`get_id_list()`/`get_mode()` + `start_requested(mode)` signal；模式切換、學位複選、學年度範圍、CSV 匯入。
- `ProgressPanel`：`update_progress(done,total,skipped,failed)`（進度值=已處理數，total=0 不除零）/`append_log(msg)`。
- `MainWindow`：整合兩面板、停止/匯出按鈕、接 worker 五信號；`captcha_detected` → QMessageBox → `resume_after_captcha()`；`_on_export` 匯出 CSV。
- `main.py`：`python -m ndltd_spider.main` 進入點。

### Simplify 採納（4 agent 審查）

- CSV 解析下沉到 `storage/importer.py` `load_thesis_ids()`（原本在 GUI widget 內，altitude 修正）。
- 新增 `exporter.export_db_to_csv(db_path, out_path)`，GUI 不再認識 ThesisDB 生命週期。
- 移除冗餘 `QButtonGroup`（radio 同 parent 已互斥）、progress bar 預設 setter。
- `MainWindow._on_finished/_on_error` 抽共用 `_finish()`。
- 跳過：export 移背景執行緒（v1 資料量小，YAGNI）、degree/year row 與 _labeled_row 合併（差異大）、CAPTCHA 隱性耦合（即架構設計）。

### 真實站台端到端驗證 ✅（與使用者互動完成）

`python -m ndltd_spider.main` 實測搜尋模式，端到端打通。過程中發現並修正三個整合 bug：

1. **進站驗證碼未處理**：網站使用量大時，進站即被「驗證碼檢查機制」閘門攔截（`/login`、`validinput`），但 worker 原本只在逐筆爬取時處理 CAPTCHA。
   修正：worker 在 `session.start()` 後先 `_pause_if_captcha(session)`（兩種模式皆適用），把 CAPTCHA 處理抽成 `_pause_for_captcha` 共用。
2. **`submit_search` 硬卡 `qs0` 逾時**：撞到閘門時頁面無搜尋框，`page.fill` 卡 30s 逾時。
   修正：改用 `query_selector` 逐一試候選選擇器（不等待），找不到立即報錯並列出可見輸入框。實測確認 **`input[name='qs0']` 為正確選擇器**。
3. **`ccd=None`**：進站走 `/login`（網址不含 ccd），解完驗證碼後結果頁的**網址列也不含 ccd**（ccd 在頁面連結裡）。導致 `record?r1=N` URL 變 `ccd=None` 而失敗。
   修正：`refresh_ccd()` 在網址找不到 ccd 時，**退而從頁面內容解析**；worker 於進站解碼後補呼叫 `refresh_ccd()`；`goto()` 後加 `wait_for_load_state("networkidle")` 避免 content() 撞到導航中。

驗證結果：搜尋「機器學習」→ 人工解驗證碼 → 「搜尋結果共 N 筆」→ 逐筆「完成：<ID> <標題>」→ CSV 匯出皆正常。`record?r1=N` 導航確認可用。

備註：`config.json` 為使用者本機執行設定（已 gitignore）；程式預設 `headless=True`（CAPTCHA 時自動切 headful），除錯期間可設 `false` 全程顯示瀏覽器。

---

## Cross Review（/ddd.xreview）與修正 ✅

日期：2026-06-04
Reviewer：Claude ddd-reviewer（外部 CLI 未安裝，退化為單方審查）
結果：0 critical、4 important，coordinator 讀碼驗證後全部確認，使用者選擇全修。119 passed。

修正內容：
1. **CAPTCHA 解題後未複驗** → `_ensure_not_captcha` 改為迴圈重試：解完重新偵測，最多 `MAX_CAPTCHA_RETRIES=3` 次，仍未過拋 `CaptchaUnsolvedError`（與「詳細頁不存在」區隔，避免錯誤歸因與搜尋模式靜默漏抓）。
2. **關窗卡死/閃退** → `_pause_for_captcha` 在 stop 時略過 `set_headless` 重啟；`closeEvent` 改 `wait(8000)` 逾時則 `terminate()`，避免帶 running 的 QThread 解構。
3. **r1 全域序號假設無防呆** → `_run_search`/`_run_ids` 加連續失敗中止：連續 `MAX_CONSECUTIVE_FAILURES=5` 筆失敗即停並報明確訊息（防 r1 超範圍/結構改變時悶頭跑完全錯）。
4. **`is_captcha_page` 文字誤判** → 「驗證碼」文字只檢查**葉節點**自身內容，不再因祖先元素彙總全頁文字而誤判；結構標記（validinput/random_validationimgs/url）維持為主訊號。

新增測試：leaf-only 偵測 2、連續失敗門檻 1、CaptchaUnsolvedError 1。
