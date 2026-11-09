"""論文 ID 清單匯入：從 CSV 讀取 thesis_id。"""

import csv


def load_thesis_ids(path: str) -> list[str]:
    """讀取 CSV 的 thesis_id 欄，去重保序後回傳。

    CSV 需有名為 thesis_id 的欄位；空值與重複值會被略過。
    """
    seen: set[str] = set()
    result: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tid = (row.get("thesis_id") or "").strip()
            if tid and tid not in seen:
                seen.add(tid)
                result.append(tid)
    return result
