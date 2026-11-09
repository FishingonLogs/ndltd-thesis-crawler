# Tasks: NDLTD 爬蟲 v2 — 進階搜尋 + 自動匯出 + 匯出管理

> 對應 spec：`docs/02-advanced-export/spec.md`、research：`research.md`
> 測試：`QT_QPA_PLATFORM=offscreen .venv/Scripts/python -m pytest`（GUI 用 pytest-qt）
> 分支：`feat/02-advanced-export`

---

## Milestone 1: 進階搜尋 + 匯出管理（可平行）

> 預期結果：`build_advanced_form_plan` 能把 SearchConfig 正確映射為進階表單操作計畫且選擇器存在於真實 fixture；`submit_search` 改填進階表單；`export_run` 能在 output_dir 產生時間戳 CSV 與純文字 log；ScraperConfig 具備 output_dir/auto_export。
> 驗證方式：`pytest tests/scraper/test_search.py tests/storage/test_exporter.py -v` 全過
> 對應 US：US-1（進階搜尋）、US-3（匯出管理）部分、US-2 的 config 開關

### 🔀 可平行工作線

**[A] 進階搜尋**
> 範圍：`ndltd_spider/scraper/search.py`、`tests/scraper/test_search.py`、`tests/fixtures/advanced_search.html`（從 `範例/` 複製）
> 依賴：既有 `SearchConfig`（models.py）、research.md 的表單欄位對應
> 介面契約：
>   - `AdvancedFormPlan`（dataclass：rows: list[(index:int, qf_value:str, qs_value:str)]、degrees: list[str]、year_from: str、year_to: str）
>   - `build_advanced_form_plan(config: SearchConfig) -> AdvancedFormPlan`（純函式）：row 0 必為關鍵字(qf=""、qs=keywords)；university→qf=asc、department→qf=sdp 僅非空時各佔一組(index 遞增)；degrees 依 degree_master/doctor；year_from/to>0 才填，轉字串
>   - `submit_search(session, config) -> int`：套用 plan 到頁面(select_option qf/ltyr/eltyr、fill qs、check mtty)後 submit，回傳 parse_total_count
> 驗證方式：`pytest tests/scraper/test_search.py -v` 全過——映射正確、plan 引用的選擇器(qf{i}/qs{i}/mtty/ltyr/eltyr)存在於 advanced_search.html fixture
- [x] Task A1: 複製 advanced_search.html 至 fixtures，撰寫 `build_advanced_form_plan` 映射測試 + 「plan 選擇器存在於 fixture」結構測試 (Red)
- [x] Task A2: 實作 `build_advanced_form_plan` (Green)
- [x] Task A3: 改寫 `submit_search` 套用 plan 填進階表單（整合，無單元測試；M2 手動 e2e 驗證）

**[B] 匯出管理（config + export_run）**
> 範圍：`ndltd_spider/config.py`、`ndltd_spider/storage/exporter.py`、`tests/storage/test_exporter.py`
> 依賴：既有 `export_csv`（exporter.py）、`ThesisDB`
> 介面契約：
>   - `ScraperConfig` 新增 `output_dir: str = "output"`、`auto_export: bool = True`
>   - `export_run(db: ThesisDB, output_dir: str, log_text: str, timestamp: str) -> tuple[str, str]`：確保 output_dir 存在；寫 `thesis_<timestamp>.csv`（沿用 export_csv）與 `run_<timestamp>.log`（UTF-8）；回傳 (csv_path, log_path)
> 驗證方式：`pytest tests/storage/test_exporter.py -v` 全過——目錄自動建立、檔名含時間戳、CSV 為 completed 記錄、log 內容正確
- [x] Task B1: ScraperConfig 加 output_dir/auto_export（介面變更，無測試）
- [x] Task B2: 撰寫 `export_run` 測試 (Red) —— 建目錄、時間戳雙檔、CSV completed、log 寫入
- [x] Task B3: 實作 `export_run` (Green)

---

## Milestone 2: worker 自動匯出整合 + GUI（序列）

> 預期結果：搜尋/ID 兩模式正常完成後自動產生 output/ 的 CSV+log（auto_export 控制）；中途停止不匯出；GUI 手動匯出也輸出到 output/；日誌顯示匯出路徑。進階搜尋端到端可用。
> 驗證方式：`pytest tests/ -v` 全過 + 手動 e2e（搜尋進階條件→自動匯出→檢查 output/ 的 CSV 與 log）
> 依賴：M1 [A] submit_search、[B] export_run + ScraperConfig

- [x] Task C1: 撰寫 `build_run_log(summary, lines)` 純函式測試 (Red) —— 標頭/條件摘要/計數/逐筆行格式
- [x] Task C2: 實作 `build_run_log` 並在 worker 累積 `_run_lines`（[OK]/[SKIP]/[FAIL]）、正常完成且 auto_export 時呼叫 export_run、emit 路徑 (Green)
- [x] Task C3: GUI `_on_export` 改輸出到 `output_dir`（共用 storage 層 export_db_snapshot），手動驗證按鈕
- [~] Task C4: 手動 e2e —— 自動匯出鏈已單元測試（build_run_log/export_run/snapshot/condition_summary）；live e2e 併入 M3（進階查詢 UI）完成後一起跑（屆時自然涵蓋自動匯出）

---

## Milestone 3: 動態進階查詢列 UI（序列）

> 預期結果：搜尋面板可動態增減「欄位下拉+關鍵字+and/or/not」查詢列；SearchConfig 以 rows 表達並能送進進階表單（含 qo 運算子）；條件摘要正確。
> 驗證方式：`pytest tests/ -v` 全過 + 手動 e2e（多列布林查詢→篩選生效→自動匯出）
> 依賴：M1（submit_search/plan）、M2（自動匯出）
> 對應 US：US-4
> 序列原因：SearchConfig 改形狀（rows 取代 keywords/university/department）同時牽動 search/gui/worker 與三處測試，屬共享型別變更，不宜平行。

- [x] Task D1: models.py 定義 `QueryRow`、`QF_FIELDS`、`QUERY_OPERATORS`；`SearchConfig` 改 `rows` 模型 + `active_rows()`；同步修正受影響測試
- [x] Task D2: 改寫 `build_advanced_form_plan` 測試 (Red)
- [x] Task D3: 實作 `build_advanced_form_plan`（rows→(index,qf,qs,qo)）+ `submit_search` 設 `qo{i}` (Green)
- [x] Task D4: 改寫 `SearchPanel` 測試 (Red)
- [x] Task D5: 實作 `SearchPanel` 動態多列 UI（QueryRowWidget：欄位下拉+關鍵字+運算子；+新增/移除；保留學位/學年度）(Green)
- [x] Task D6: 更新 `worker._condition_summary` 改述 rows + 測試
- [x] Task D7: 手動 e2e —— ✅ 多列布林進階查詢（論文名稱=書目 and 系所=資訊）92 筆全成功、output/ 產生 CSV+log、自動匯出正常（一併驗 M2 自動匯出 C4）。e2e 修：導到 ?mode=advance、送出點 #gs32search

## Milestone 4: 詳細頁解析修正 + 分頁內容（序列）

> 預期結果：詳細頁欄位不再錯位（標籤對應）；新增中文/英文摘要與參考文獻；references 改名 citation_stats。
> 驗證：`pytest tests/` 全過 + e2e 比對欄位對齊與新欄位有值
- [x] Task E1: models LABEL_MAP 取代 METADATA_TH_IDS；ThesisRecord 改 citation_stats + 新增 abstract_zh/abstract_en/bibliography
- [x] Task E2: 改寫 detail 測試 (Red) —— 標籤對應、缺列不位移、分頁內容分類
- [x] Task E3: 實作 parse_detail 標籤對應 + parse_tab_contents 內容分類 (Green)
- [x] Task E4: 修正受影響測試（test_database citation_stats）；simplify
- [x] Task E5: 手動 e2e —— 92 筆驗證欄位對齊、abstract/bibliography 有值

## 平行評估摘要

| Milestone | 平行性 | 理由 |
|-----------|--------|------|
| M1 | 🔀 2 線 | [A]search.py / [B]exporter.py+config.py 檔案不重疊、各自 TDD（fixture / 暫存目錄），無共用狀態 |
| M2 | 序列 | worker 整合依賴 M1 兩線產出；GUI 與 e2e 接在其後 |

> 註：worktree 隔離在本機環境不可用（git 偵測於 session 啟動時為 false），平行線改以「檔案範圍互斥的非隔離並行」派發（同 v1 M2/M4 作法）。
