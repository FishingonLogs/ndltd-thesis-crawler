# Plan: NDLTD 爬蟲 v2 — 進階搜尋 + 自動匯出 + 匯出管理

## 背景 (Background)

v1 搜尋模式只送關鍵字（`qs0`），無法用學位/學年度/校院/系所篩選；匯出需手動按鈕、且輸出散落在專案根目錄、沒有執行紀錄。v2 補上真正的進階查詢、爬完自動匯出，並把輸出與紀錄集中管理。

進階查詢表單結構已透過 live recon 取得（見 `research.md`），無待解未知。

## 粗略目標 (High-level Goals)

1. **進階搜尋**：`submit_search` 依 SearchConfig 填寫進階表單——關鍵字、校院(`asc`)、系所(`sdp`) 用 `qf/qs` 配對；學位用 `mtty` checkbox；學年度範圍用 `ltyr/eltyr`。
2. **自動匯出**：搜尋模式與 ID 清單模式爬完後，自動匯出 CSV（不需手動按鈕；手動按鈕保留）。
3. **匯出管理**：輸出集中到 `output/` 資料夾，CSV 與紀錄檔皆帶時間戳；每次執行產生一個純文字 log（成功/失敗逐行記錄）。

## 可能的方向 (Potential Directions)

### 進階表單填寫
- **方案 A（採用）**：`submit_search` 用 Playwright 直接操作表單元件——`select_option` 設 qf/ltyr/eltyr、`fill` 設 qs、`check` 設 mtty，再 submit。貼近真實互動、可被進站驗證碼流程涵蓋。
- 方案 B：自行組 POST body 直接送。較快但要逆推所有 hidden 欄位，脆弱、難維護。→ 不採用。

### 自動匯出觸發點
- **方案 A（採用）**：worker 在爬取迴圈正常結束後（非中途停止）發出帶「本次輸出路徑」的完成信號，由 worker 直接呼叫匯出 + 寫 log（worker 已持有 db 與計數）。GUI 仍可手動匯出。
- 方案 B：GUI 收到 finished 再觸發匯出。但 GUI 不知道本次 run 的範圍，且兩模式要各接一次。→ 不採用。

## 設計概要

- **`SearchConfig`**：沿用既有欄位即可（keywords/degree_master/degree_doctor/year_from/year_to/university/department），無需改結構。
- **`scraper/search.py` `submit_search`**：改為填進階表單。以 `範例/advanced_search.html`（複製到 `tests/fixtures/`）驗證「欄位定位選擇器存在」；實際送出與筆數為整合驗證。
- **`storage/exporter.py`**：新增 `export_run(db, output_dir) -> (csv_path, log_path)`，內部用時間戳組檔名、確保 `output/` 存在、寫 CSV + 純文字 log。
- **`scraper/worker.py`**：完成（非 stop）時呼叫 `export_run`，emit 一個帶路徑的訊息到日誌；新增 `auto_export` 開關（預設開）。
- **`config.py` / `ScraperConfig`**：新增 `output_dir="output"`、`auto_export=True`。
- **GUI**：日誌顯示「已自動匯出至 output/...」；手動匯出鈕沿用。

## 純文字 log 內容（草案）

```
NDLTD 爬取紀錄  2026-06-04 15:30:00
模式: 搜尋 / 關鍵字=機器學習 學位=碩士,博士 學年度=110~113
總數: 50  成功: 47  跳過: 1  失敗: 2
----
[OK]   110NKUS0320041  公司治理對股價...
[SKIP] 109XXXX...（已完成）
[FAIL] r1=33  detail_page_not_found
...
```

## 待釐清事項 (Open Questions)

- 無阻塞性未知。進階表單結構已確認（research.md）。
- 次要（實作時決定，非阻塞）：log 失敗筆是否含完整 URL；學門/論文種類等進階條件 v2 是否納入 GUI（傾向先不加，留 extra_fields）。

## 範圍外 (Out of Scope for v2)

- 學門/論文種類/語文/檢索模式等進階條件的 GUI 控制項（保留 extra_fields，先不做 UI）。
- 布林 and/or/not 的 UI（v2 多條件一律 and）。
- 自動解 CAPTCHA、全文下載（仍在 v3+）。

## 下一步建議 (Next Step)

執行 `/ddd.spec` 撰寫規格：`submit_search` 進階填寫的介面契約與欄位對應、`export_run` 契約與 log 格式、worker 自動匯出流程、驗收條件與邊界案例。
