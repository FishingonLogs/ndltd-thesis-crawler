# Works: NDLTD 爬蟲 v2 開發日誌

## Milestone 1: 進階搜尋 + 匯出管理 ✅

完成日期：2026-06-04
測試結果：152 passed（全套件）

### 執行模式：平行（coordinator 派發 2 worker，檔案互斥非隔離）

- [A] 進階搜尋（search.py，30 tests）、[B] 匯出管理（models.py ScraperConfig + exporter.py，12 tests）並行。
- 派發時修正：ScraperConfig 實際在 `models.py` 而非 `config.py`，已在 worker prompt 導正，與 [A] 完全不重疊。

### 前置 recon（live，互動式）

- 進階查詢表單頁不在原範例，透過互動式 headful recon（使用者解驗證碼）擷取 `範例/advanced_search.html`，結構記於 `research.md`。
- recon 確認的真實欄位：10 組 `qf0..qf9`/`qs0..qs9`/`qo1..qo9`；學位 checkbox `mtty`(碩士/博士)；學年度 select `ltyr`/`eltyr`。

### 介面產出

- `scraper/search.py`
  - `AdvancedFormPlan`（dataclass：rows/degrees/year_from/year_to）
  - `build_advanced_form_plan(config) -> AdvancedFormPlan`（純函式）：row0 必為關鍵字；university→asc、department→sdp 各佔一組；degrees 依 master/doctor；year 轉字串。
  - `submit_search` 改寫：套用 plan（select_option qf/ltyr/eltyr、fill qs、check mtty）後送出；找不到欄位即報錯附可見欄位（不卡逾時）。
- `models.py` `ScraperConfig`：新增 `output_dir="output"`、`auto_export=True`。
- `storage/exporter.py` `export_run(db, output_dir, log_text, timestamp) -> (csv_path, log_path)`：建目錄、重用 export_csv 寫 `thesis_<ts>.csv`、寫 `run_<ts>.log`。timestamp 由呼叫端傳入（不在此呼叫 datetime.now，便於測試）。

### 設計重點

- 核心易變邏輯抽成純函式（`build_advanced_form_plan`）完整單元測試；Playwright 操作縮到 `submit_search` 整合層（M2 e2e 驗證）。
- `export_run` 重用既有 `export_csv`，timestamp 參數化以利測試。

### 給 M2 的注意事項

- worker 自動匯出需組 log_text（`build_run_log`）並以 filename-safe timestamp 呼叫 export_run。
- submit_search 的進階填寫需在進站驗證碼處理後（worker 已有 `_ensure_not_captcha`）。
- GUI 手動匯出改走 output_dir。

---

## Milestone 2: worker 自動匯出整合 + GUI ✅（live e2e 併入 M3）

完成日期：2026-06-04
測試結果：157 passed（全套件）

### 介面產出
- `worker.build_run_log(...)` 純函式組裝執行紀錄；`_condition_summary`/`_mode_label`/`_auto_export`；`_run_lines` 累積 [OK]/[SKIP]/[FAIL]。
- `run()` 正常完成（非 stop）且 `auto_export` 為真時自動匯出，emit CSV/log 路徑。
- `exporter`：`make_timestamp`/`TS_FORMAT`/`_timestamped_csv_path`（命名+建目錄單一來源）、`export_db_snapshot`（手動匯出）。
- GUI `_on_export` 改用 `export_db_snapshot`（不再自組時間戳/建目錄）。

### Simplify
- 兩 reviewer 共識：時間戳格式 + 建目錄 + `thesis_{ts}.csv` 命名原散在 export_run/worker/GUI 三處 → 集中到 exporter（`TS_FORMAT`/`_timestamped_csv_path`/`export_db_snapshot`），worker 用單一 `now` + `TS_FORMAT`，GUI 不再碰 Path/strftime。

### 使用者回饋 → 觸發 M3
- e2e 時使用者指出搜尋面板「跟上一版一樣」：v2 的進階搜尋是**後端**把既有欄位接到進階表單，GUI 未新增控制項。使用者要的是**完整進階查詢 UI**：可選欄位（作者等）+ and/or/not 布林。此為 US-1 實質擴充（原列範圍外），開 M3 處理（更新 spec：動態多列查詢 + 全部 qf 代碼 + qo 運算子）。
- M2 的自動匯出 live e2e 順延到 M3 完成後一起驗。

---

## Milestone 3: 動態進階查詢列 UI ✅

完成日期：2026-06-04　測試：141→142 passed

- `models`：`QueryRow`/`QF_FIELDS`/`QUERY_OPERATORS`；`SearchConfig` 改 `rows` 模型 + `active_rows()`。
- `search`：`build_advanced_form_plan` 改 rows→(index,qf,qs,qo)；`submit_search` 設 qo；新增 `build_advanced_url`（進階查詢頁 `?mode=advance`）。
- `gui`：`QueryRowWidget` + 動態多列（欄位下拉/關鍵字/and-or-not，可增減；第0列無運算子）；學位/學年度限縮保留。
- `worker._condition_summary` 改述 rows。
- Simplify：刪死碼 `_find_keyword_field`、`active_rows()` 收斂過濾語意、閾值/QF_FIELDS 集中。
- e2e 發現並修：(1) submit_search 需先導到 `?mode=advance`（簡易頁無 qf 欄位）；(2) 送出要點查詢鈕 `#gs32search`（gs32_quicksearch），非按 Enter。

## Milestone 4: 詳細頁解析修正 + 分頁內容 ✅

完成日期：2026-06-05　測試：148 passed；live e2e 92 筆全成功、欄位對齊正確

### 修正的資料品質 bug
- **錯位**：`th` 的 `format_0_table_th_N` 是按該頁實際列順序編號，缺列（如無口試委員）會整列位移。改用 **th 標籤文字**（LABEL_MAP）對應欄位，徹底解決。
- **references 誤導**：原 `references` 其實是「相關次數」→ 改名 `citation_stats`。

### 新增分頁內容（內容特徵分類，非脆弱位置）
- `abstract_zh`/`abstract_en`/`bibliography`，由 `parse_tab_contents` 從 `td.stdncl2` 區塊分類：參考文獻=年份引用≥3 最多者；英文摘要=拉丁比例>0.5；中文摘要=其餘非目次非書目；目次排除。
- live e2e 驗證：缺口試委員的論文 degree/university 正確不位移；三個新欄位皆有值。

### 註記
- 站方對少數字（沈/李 等）使用造字區(PUA)字元，CSV 會原樣保留（網站原始資料特性）。
- ThesisRecord 欄位變更 → 舊 `ndltd.db` schema 不相容；**xreview 後已加 `ThesisDB._migrate()`** 自動 ALTER 補欄並搬移 references→citation_stats，無需手動刪庫。
- **Excel 顯示限制（非 bug）**：`bibliography` 可能很長（實測某筆 43,875 字），超過 Excel 單格上限 32,767 字，用 Excel 開會被拆行/溢位。CSV 本身正確（Python/pandas/LibreOffice 可完整讀回）。經使用者決定維持現狀，改用非 Excel 工具開啟。

---

## Cross Review（/ddd.xreview）與修正 ✅

日期：2026-06-05　Reviewer：Claude ddd-reviewer（外部 CLI 未裝，單方）
結果：1 critical + 2 important，coordinator 讀碼確認，使用者選擇全修。150 passed。

1. **[critical] v1→v2 DB 無 migration** → `ThesisDB._migrate()`：`PRAGMA table_info` 比對，缺欄以 `ALTER TABLE ADD COLUMN` 補上；舊 `references` 搬到 `citation_stats`。加 `test_migrates_v1_schema`。
2. **[important] GUI 查詢列無上限** → `MAX_QUERY_ROWS=10`，`add_query_row` 達上限回 None 並停用新增鈕。加 `test_query_rows_capped_at_max`。
3. **[important] 摘要誤判書目** → `_BIB_MIN_YEARS` 3→5，降低含少量年份的中文摘要被誤classify為書目的機率。
- 同步修正 spec 非目標的 schema 說明。
