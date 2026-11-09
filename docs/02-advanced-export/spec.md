# Spec: NDLTD 爬蟲 v2 — 進階搜尋 + 自動匯出 + 匯出管理

## 目標

讓搜尋模式能以學位類別、畢業學年度範圍、校院、系所等條件做進階查詢；爬取完成後自動把結果匯出到專用資料夾，並為每次執行產生一份純文字紀錄檔（記錄成功/跳過/失敗）。

## 非目標

- 學門、論文種類、語文別、檢索模式等**限縮**條件的 GUI 控制項（保留 `SearchConfig.extra_fields`，本期不做 UI）。
- 自動解 CAPTCHA、全文 PDF 下載（v3+）。

> 註 1：原列為非目標的「欄位選擇」與「and/or/not」已於使用者回饋後納入範圍，見 US-4（M3）。
> 註 2：US-5（M4）變更了 ThesisRecord 欄位（references→citation_stats、新增 abstract/bibliography），屬 schema 變更；`ThesisDB._migrate()` 以 ALTER TABLE 對既有 DB 補欄並搬移 references→citation_stats，向後相容。

---

## User Stories

### US-1：進階搜尋條件送出

作為研究者，我想在搜尋模式填入學位/學年度/校院/系所等條件，讓系統用 NDLTD 進階查詢精準篩選，而非只用關鍵字。

**驗收條件**
- [ ] `submit_search` 依 `SearchConfig` 填寫進階查詢表單並送出，回傳結果總筆數：
  - 關鍵字 → 第 0 組 `qf0=""`（不限欄位）、`qs0=keywords`
  - 校院（university 非空）→ 取一組 `qf{n}=asc`、`qs{n}=university`、`qo{n}=and`
  - 系所（department 非空）→ 取一組 `qf{n}=sdp`、`qs{n}=department`、`qo{n}=and`
  - 學位：`degree_master` 為真 → 勾 `mtty=碩士`；`degree_doctor` 為真 → 勾 `mtty=博士`；兩者皆假 → 不限制
  - 學年度：`year_from>0` → `ltyr=year_from`；`year_to>0` → `eltyr=year_to`（民國學年度字串）
- [ ] `build_advanced_form_plan(config)` 為純函式，將 `SearchConfig` 映射為表單操作計畫（可單元測試）
- [ ] plan 中引用的欄位選擇器（qf/qs/mtty/ltyr/eltyr）皆存在於 `advanced_search.html` fixture（結構測試）
- [ ] 送出後沿用 v1 `parse_total_count` 取總數、`record?r1=N` 逐筆爬取流程不變

### US-2：爬取完成後自動匯出

作為使用者，我希望爬完後系統自動匯出 CSV，不必每次手動按「匯出 CSV」。

**驗收條件**
- [ ] 搜尋模式與 ID 清單模式，爬取**正常結束**（非中途按停止）後，自動匯出 CSV
- [ ] `ScraperConfig.auto_export`（預設 `True`）控制是否自動匯出；為 `False` 時不自動匯出
- [ ] 中途按「停止」而結束時**不**自動匯出（避免半套資料覆寫；使用者仍可手動匯出）
- [ ] GUI 手動「匯出 CSV」按鈕保留，行為不變（改為輸出到 `output/`，見 US-3）
- [ ] 自動匯出完成後，日誌顯示「已自動匯出至 <csv 路徑>」與「紀錄檔：<log 路徑>」

### US-3：匯出集中管理與執行紀錄

作為使用者，我希望匯出檔集中在專用資料夾、檔名不互相覆蓋，且每次執行有成功/失敗紀錄可追溯。

**驗收條件**
- [ ] 匯出目錄為 `ScraperConfig.output_dir`（預設 `output`），不存在時自動建立
- [ ] CSV 檔名帶時間戳：`thesis_<YYYYMMDD_HHMMSS>.csv`
- [ ] 每次執行產生一份純文字紀錄檔：`run_<YYYYMMDD_HHMMSS>.log`（與該次 CSV 共用同一時間戳）
- [ ] log 內容包含：執行時間、模式與條件摘要、總數/成功/跳過/失敗計數，及逐筆 `[OK]/[SKIP]/[FAIL]` 行
- [ ] CSV 內容為 DB 中所有 `status=completed` 的紀錄（累積快照，沿用 v1 export_csv 語意）

---

### US-4：動態進階查詢列（M3，取代 US-1 的固定欄位）

作為研究者，我想用多列「查詢欄位 + 關鍵字 + and/or/not」自由組合查詢（例如：研究生=王小明 AND 校院=臺灣大學 NOT 關鍵詞=區塊鏈），欄位可選論文名稱/研究生(作者)/指導教授/校院/系所/關鍵詞等。

**驗收條件**
- [ ] `SearchConfig` 改為以 `rows: list[QueryRow]` 表達查詢列（取代 keywords/university/department 三個固定欄位）；`QueryRow(field, keyword, operator)`，`operator` 為 and/or/not（第 0 列忽略 operator）
- [ ] 查詢欄位下拉提供全部 qf 代碼（`QF_FIELDS`）：不限欄位/論文名稱(ti)/研究生(au)/校院名稱(asc)/系所(sdp)/論文出版年(pyr)/指導教授(ad)/口試委員(say)/關鍵詞(kw)/論文目次(tc)/摘要(ab)/論文參考文獻(rf)/畢業學年度(yr)/學門(sglv1)/學類(sglv2)
- [ ] `build_advanced_form_plan` 改由 `rows` 產生 `qf{i}/qs{i}/qo{i}`（i≥1 才設 qo），degree/year 限縮不變
- [ ] `submit_search` 額外設定 `qo{i}` 運算子（i≥1）
- [ ] GUI `SearchPanel` 提供**動態多列**：每列為「欄位下拉 + 關鍵字輸入」，第 2 列起前面有 and/or/not 下拉；可「+ 新增列」/「移除列」；學位、學年度限縮維持
- [ ] `SearchPanel.get_search_config()` 回傳含 `rows` 的 SearchConfig
- [ ] 空查詢列（keyword 空）在送出前過濾；至少保留一列

### US-5：詳細頁解析修正 + 分頁內容（M4）

作為使用者，我要詳細頁資料正確不錯位，並且能抓到摘要與參考文獻等分頁內容。

**驗收條件**
- [ ] `parse_detail` 改以 **th 標籤文字**（研究生:/口試委員:/校院名稱:…）對應欄位，取代固定 `th_N` id（修正某些論文缺列時整列位移的 bug）
- [ ] 新增欄位：`abstract_zh`（中文摘要）、`abstract_en`（外文摘要）、`bibliography`（參考文獻書目）
- [ ] 既有 `references` 欄位（實為「相關次數」被引用/點閱/下載）**改名 `citation_stats`**
- [ ] 分頁內容以**內容特徵分類**抽取（非脆弱的位置假設）：參考文獻=年份引用最多者；英文摘要=拉丁字母比例高者；中文摘要=中文為主且非目次非書目者；目次（含目錄/第N章）排除
- [ ] 純函式 `parse_tab_contents(html) -> dict` 可單元測試（用 detail_sample fixture）

## 相關檔案

```
ndltd_spider/
├── config.py                # ScraperConfig 新增 output_dir / auto_export
├── scraper/
│   ├── search.py            # build_advanced_form_plan（新）、submit_search（改填進階表單）
│   └── worker.py            # 完成時自動匯出 + 累積 run log；新增 _run_lines
└── storage/
    └── exporter.py          # export_run（新）：時間戳 CSV + log，建立 output_dir
tests/
├── fixtures/advanced_search.html   # 由 範例/ 複製
├── scraper/test_search.py          # build_advanced_form_plan + fixture 選擇器存在
└── storage/test_exporter.py        # export_run 檔名/目錄/log 內容
```

---

## 介面 / 資料結構

### `SearchConfig`（沿用 v1，不改）

```python
keywords, degree_master(=True), degree_doctor(=True),
year_from(=0), year_to(=0), university, department, extra_fields
```

### `ScraperConfig`（新增兩欄）

```python
@dataclass
class ScraperConfig:
    delay_min: float = 2.0
    delay_max: float = 5.0
    max_retries: int = 3
    db_path: str = "ndltd.db"
    headless: bool = True
    output_dir: str = "output"      # 新增
    auto_export: bool = True         # 新增
```

### `build_advanced_form_plan(config: SearchConfig) -> AdvancedFormPlan`（純函式）

```python
@dataclass
class AdvancedFormPlan:
    # 每組 (index, qf_value, qs_value)；index 0 起，依填了哪些條件依序佔用
    rows: list[tuple[int, str, str]]
    degrees: list[str]        # mtty 要勾的值，子集 of {"碩士","博士"}
    year_from: str            # ltyr 值；"" 表不限
    year_to: str              # eltyr 值；"" 表不限
```

映射規則：row 0 一定是關鍵字（`qf=""`, `qs=keywords`，keywords 可為空字串）；university→`("asc")`、department→`("sdp")` 僅在非空時各佔一組（index 遞增）。

### `submit_search(session, config) -> int`（改寫，整合行為）

行為：套用 `build_advanced_form_plan` 到頁面——`select_option` 設定 `qf{i}`/`ltyr`/`eltyr`、`fill` 設定 `qs{i}`、`check` 設定對應 `mtty`，submit 表單，回傳 `parse_total_count(session.content())`。找不到表單元件時 raise 明確錯誤（沿用 v1 列出可見欄位的作法）。

### `export_run(db, output_dir, log_text, timestamp) -> tuple[str, str]`（新）

```python
def export_run(db: ThesisDB, output_dir: str, log_text: str,
               timestamp: str) -> tuple[str, str]:
    """確保 output_dir 存在；寫 thesis_<ts>.csv 與 run_<ts>.log，回傳 (csv_path, log_path)。"""
```

- `timestamp` 由呼叫端（worker）以 filename-safe 格式（`YYYYMMDD_HHMMSS`）傳入，便於測試。
- CSV 沿用 `export_csv` 邏輯（UTF-8 BOM、completed 記錄）。
- log 以 UTF-8 寫入 `log_text`。

### worker 流程變更

- 新增 `self._run_lines: list[str]`，於 `_scrape_one`/跳過處附加 `[OK]/[SKIP]/[FAIL] ...` 行。
- `run()` 在**正常結束**（未 stop）且 `config.auto_export` 為真時，組裝 log_text（標頭+條件摘要+計數+逐筆行）並呼叫 `export_run`，emit 路徑到日誌。
- 中途 stop 結束則跳過自動匯出。

### log 格式範例

```
NDLTD 爬取紀錄  2026-06-04 15:30:00
模式: 搜尋  條件: 關鍵字=機器學習; 學位=碩士,博士; 學年度=110~113; 校院=臺灣大學
總數: 50  成功: 47  跳過: 1  失敗: 2
--------
[OK]   110NKUS0320041  公司治理對股價異常報酬影響之研究
[SKIP] 109XXXX0000001  （已完成）
[FAIL] r1=33  detail_page_not_found
```

---

## 邊界案例

- **Case 1：所有條件皆空**（搜尋模式未填任何欄位）— `submit_search` 仍送出，回傳全站總數；worker 照常進行（不視為錯誤）。但若 `total==0` 走 v1 既有「0 筆」處理。
- **Case 2：學位兩者皆未勾** — 不勾任何 `mtty`（= 不限學位），非錯誤。
- **Case 3：只填 year_from 或只填 year_to** — 只設有值的那個（`ltyr` 或 `eltyr`），另一個留空。
- **Case 4：中途按停止** — 不自動匯出；已寫入 DB 的資料保留，可下次續爬或手動匯出。
- **Case 5：output_dir 不存在** — 自動建立（含多層）。
- **Case 6：auto_export=False** — 爬完不自動匯出，僅可手動匯出。
- **Case 7：本次 0 筆成功**（全失敗或搜尋 0 筆）— 仍產生 log（記錄失敗/0 筆）；CSV 為僅表頭（沿用 export_csv 對空資料的行為）。
- **Case 8：進階表單欄位選擇器在實站與 fixture 不一致** — `submit_search` raise 明確錯誤並列出可見欄位（沿用 v1），由日誌呈現。

---

## ADR

### ADR-1：以 Playwright 操作表單元件填寫進階查詢（非自組 POST）

**決策**：`submit_search` 用 `select_option`/`fill`/`check` 操作真實表單元件後 submit。

**原因**：貼近真實互動、自動帶上所有 hidden 欄位與 session 狀態，且能被既有進站驗證碼流程涵蓋；自組 POST 需逆推大量 hidden 欄位，脆弱難維護。

**替代方案**：直接組 POST body 送出——快但脆弱，站方表單一改即壞。

### ADR-2：純函式 `build_advanced_form_plan` 分離「條件→表單計畫」與「實際操作」

**決策**：把 `SearchConfig` → 表單欄位的映射抽成純函式，`submit_search` 只負責把計畫套到頁面。

**原因**：映射邏輯（哪個條件填哪個 qf/qs、學位/學年度怎麼對應）是 v2 的核心且易變，純函式可完整單元測試；實際 Playwright 操作屬整合，難測部分縮到最小。

**替代方案**：全部寫在 `submit_search` 內——無法在不開瀏覽器下測試映射正確性。

### ADR-3：自動匯出只在「正常完成」觸發，CSV 為累積快照、log 為單次執行

**決策**：worker 正常結束（非 stop）才自動匯出；CSV 匯出 DB 全部 completed（累積），log 只記本次執行。

**原因**：中途停止資料不完整，自動匯出易誤導；CSV 作為「目前累積資料集快照」符合 `export_csv` 既有語意與續爬模型；log 作為「本次執行稽核」需逐筆 OK/SKIP/FAIL，故由 worker 累積本次行項。

**替代方案**：CSV 只匯出本次 run 的記錄——需額外追蹤本次 id 集合，且與「累積資料集」的直覺不符。

### ADR-4：時間戳檔名集中於 output_dir

**決策**：CSV 與 log 皆寫入 `output_dir`，檔名帶共用時間戳。

**原因**：避免每次覆寫、可追溯歷次執行；CSV 與其 log 以同一時間戳配對，方便對照。

**替代方案**：固定檔名覆寫——只留最新一份，喪失歷史與稽核能力。

### ADR-5：SearchConfig 以查詢列清單取代固定欄位（M3）

**決策**：`SearchConfig.rows: list[QueryRow]`（field/keyword/operator）取代原 keywords/university/department；degree/year 維持為獨立限縮欄位。`QF_FIELDS`（code→顯示名）定義在 models.py 供 GUI 下拉與條件摘要共用。

**原因**：使用者要的進階查詢是「任意欄位 + 布林組合」，固定三欄位無法表達；查詢列清單直接對應網站 qf/qs/qo 結構，且可動態增減。degree/year 屬「限縮」性質（mtty/ltyr/eltyr），與查詢列機制不同，分開表達較清楚。

**替代方案**：保留固定欄位再外掛 rows——兩套並存易混淆、condition 來源不一致。

**影響**：build_advanced_form_plan、submit_search、worker._condition_summary、SearchPanel、相關測試都需配合改為 rows 模型。
