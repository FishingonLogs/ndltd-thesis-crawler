# Research: NDLTD 進階查詢表單結構（live recon 2026-06-04）

來源：互動式 recon 擷取的 `範例/advanced_search.html`（解驗證碼後的進階查詢頁）。

## 表單

- `<form name="main" method="post" action="/cgi-bin/gs32/gsweb.cgi/ccd={ccd}/search">`
- 送出後導向結果頁（與 v1 簡易查詢相同的結果清單結構，沿用 `parse_total_count` / `record?r1=N`）。

## 10 組查詢列（index 0–9）

| 欄位 | 元件 | 說明 |
|------|------|------|
| `qf0`..`qf9` | select | 查詢欄位代碼 |
| `qs0`..`qs9` | text（id=ysearchinput0..9）| 該列關鍵字 |
| `qo1`..`qo9` | select | 與前一列的布林運算（and/or/not）|

`qf` 欄位代碼 options：
`''`不限欄位、`ti`論文名稱、`au`研究生、`asc`校院名稱、`sdp`系所、`pyr`論文出版年、`ad`指導教授、`say`口試委員、`kw`關鍵詞、`tc`論文目次、`ab`摘要、`rf`論文參考文獻、`yr`畢業學年度、`sglv1`學門、`sglv2`學類。

## 限縮篩選（limit filters）

| 條件 | 元件 | value |
|------|------|-------|
| 學位類別 | checkbox `mtty` | `碩士` / `博士`（可複選）|
| 畢業學年度（起）| select `ltyr` | `''` 或 77–115（民國）|
| 畢業學年度（迄）| select `eltyr` | `''` 或 77–115 |
| 學門 | select `ltsglv1` | 教育學門/商業及管理學門/…（顯示文字即 value）|
| 論文種類 | select `ltthesistype` | `''`全部 / `1`學術論文 / `2`..`5` 代替論文 |
| 語文別 | checkbox `mtlg` | 中文/英文/日文/其他語文 |
| 檢索模式 | radio `extrasearch` | es0 精準 / es1 模糊 / es2 同音 / es3 同義詞 / es4 漢語拼音 / es5 通用拼音 |
| 簡轉繁 | checkbox `cn2tw=1` | |

## SearchConfig → 進階表單 對應

| SearchConfig 欄位 | 表單填法 |
|-------------------|---------|
| `keywords` | `qf0=''`（不限欄位）或 `kw`，`qs0=關鍵字` |
| `university` | 取一組 `qf{n}=asc` + `qs{n}=學校名`，`qo{n}=and` |
| `department` | 取一組 `qf{n}=sdp` + `qs{n}=系所名`，`qo{n}=and` |
| `degree_master` | 勾 `mtty=碩士` |
| `degree_doctor` | 勾 `mtty=博士` |
| `year_from` | `ltyr=<民國學年度>`（0 表不限→空）|
| `year_to` | `eltyr=<民國學年度>`（0 表不限→空）|
| `extra_fields` | 預留：學門/論文種類/語文等進階條件 |

## 實作注意

- 進站仍有圖形驗證碼閘門（沿用 v1 的人工介入機制）。
- 多組查詢列：依使用者實際填了幾個條件，依序佔用 index 0,1,2…；qo（運算子）預設 and。
- 填表單後以 form submit（或點查詢鈕）送出，再 `parse_total_count` 取總數、`record?r1=N` 逐筆。
- `範例/advanced_search.html` 可作為「填表單欄位定位」的測試 fixture。
