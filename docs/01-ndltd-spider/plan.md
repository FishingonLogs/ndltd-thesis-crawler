# Plan: NDLTD 博碩士論文爬蟲工具 v1

## 背景 (Background)

舊版 `ndltdspider.py` 無完整規劃：只能爬單一 URL、覆蓋式寫入 CSV、無 session 管理、無速率控制，無法擴展。

本次從頭重新設計，目標是一個可長期使用的 PyQt6 桌面工具，對臺灣博碩士論文知識加值系統（ndltd.ncl.edu.tw）進行批次論文 metadata 爬取，同時尊重網站負擔。

## 粗略目標 (High-level Goals)

1. **雙模式輸入**：搜尋模式（GUI 設定條件 → 自動取 ID 清單）＋ ID 清單模式（匯入 CSV）
2. **Session 管理**：由 Playwright browser context 自動維持 cookie/session，含 `ccd=XXXX` 參數
3. **速率控制**：請求間可調延遲，預設保守值，避免觸發封鎖與 CAPTCHA
4. **CAPTCHA 人工介入**：偵測到 CAPTCHA 時切換為可見瀏覽器視窗，等使用者手動解題後繼續
5. **PyQt6 桌面 GUI**：搜尋條件面板 + 進度顯示 + 即時日誌
6. **雙格式輸出**：SQLite（主儲存，支援斷點續爬、去重）+ CSV 匯出
7. **第一版不含全文下載**

## 可能的方向 (Potential Directions)

### 方案 A：`requests` + `QThread`（未採用）
輕量，但 CAPTCHA 人工介入體驗差（需自行截圖顯示），且 session 管理需手工維護 cookie。

### 方案 B：`Playwright` + `QThread`（採用）
用 Playwright 控制 Chromium 瀏覽器，CAPTCHA 時直接顯示瀏覽器視窗讓使用者操作。Session 由 browser context 自動管理。

### 方案 C：`requests` + `asyncio` + `qasync`（未採用）
整合複雜，速率限制後並行優勢消失，過度設計。

## 架構設計

```
┌─────────────────────────────────────────┐
│           PyQt6 主視窗                   │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐  │
│  │ 搜尋面板  │ │ 進度面板  │ │ 日誌面板 │  │
│  │(條件設定) │ │(進度條)  │ │(即時輸出)│  │
│  └──────────┘ └──────────┘ └─────────┘  │
│  [開始爬] [停止] [匯入ID清單] [匯出CSV]  │
└────────────────────┬────────────────────┘
                     │ signal / slot
                     ▼
┌─────────────────────────────────────────┐
│          QThread (ScraperWorker)         │
│  asyncio.run() → Playwright async API    │
│                                         │
│  ┌──────────┐   ┌──────────┐            │
│  │ 搜尋導航  │→→│ 詳細頁   │            │
│  │(取得ID)  │   │ 解析     │            │
│  └──────────┘   └──────────┘            │
│          ↓           ↓                  │
│     CAPTCHA 偵測 → 切換 headful 模式     │
└──────────────────────┬──────────────────┘
                       ▼
            ┌──────────────────┐
            │  SQLite + CSV    │
            │ (斷點續爬/去重)   │
            └──────────────────┘
```

## 模組結構

```
ndltd_spider/
├── main.py              # 程式進入點
├── config.py            # 速率、路徑、預設值設定
├── gui/
│   ├── main_window.py   # 主視窗，整合各面板
│   ├── search_panel.py  # 搜尋條件面板（全部欄位，皆非必填）
│   └── progress_panel.py# 進度條 + 即時日誌
├── scraper/
│   ├── worker.py        # QThread，內部 asyncio.run() 跑 Playwright
│   ├── session.py       # Playwright browser/context 生命週期
│   ├── search.py        # 搜尋頁導航、分頁、論文 ID 收集
│   ├── detail.py        # 詳細頁解析（th[id]/td.std2 結構，21+ 欄位）
│   └── captcha.py       # CAPTCHA 偵測 + headless/headful 切換
└── storage/
    ├── database.py      # SQLite CRUD、去重、斷點續爬狀態
    └── exporter.py      # CSV 匯出
```

## 關鍵技術決策

| 項目 | 決策 |
|------|------|
| HTTP 層 | Playwright (Chromium) |
| GUI 框架 | PyQt6 |
| 並行模型 | QThread + asyncio.run() |
| 瀏覽器模式 | 預設 headless，CAPTCHA 時切 headful |
| 搜尋欄位 | 關鍵字、學位類別、畢業學年度範圍、學校/系所（全選填）|
| 主儲存 | SQLite（去重鍵：論文 ID）|
| 匯出 | CSV（pandas）|
| CAPTCHA 策略 | 速率控制降低觸發率；觸發時人工介入，第二版再評估自動解題 |

## 待釐清事項 (Open Questions)

- **搜尋頁 HTML 結構**：目前只有論文詳細頁範例，搜尋結果頁（listing page）的分頁結構與 ID 取得方式需在實作前確認（從分析 HTML 或實際測試取得）
- **CAPTCHA 觸發條件**：確切在哪個操作（搜尋次數過多？下載？特定頁面？）觸發，需實測確認

## 範圍外 (Out of Scope for v1)

- 全文 PDF 下載
- 自動 CAPTCHA 解題（第三方服務）
- 代理 IP 池
- 雲端部署 / 排程爬取

## 下一步建議 (Next Step)

執行 `/ddd.spec` 撰寫規格書，涵蓋：
- User Story（搜尋模式 / ID 清單模式 / 斷點續爬）
- 各模組 API 契約
- GUI 互動流程
- 驗收條件
