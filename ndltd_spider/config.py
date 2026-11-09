"""ScraperConfig 的 config.json 讀寫。"""

import json
from dataclasses import asdict
from pathlib import Path

from .models import ScraperConfig


def load_config(path: str = "config.json") -> ScraperConfig:
    """從 config.json 載入設定；檔案不存在時回傳預設值。

    只取用 ScraperConfig 已知的鍵，忽略多餘鍵，缺少的鍵用預設值補上。
    """
    p = Path(path)
    if not p.exists():
        return ScraperConfig()
    data = json.loads(p.read_text(encoding="utf-8"))
    known = ScraperConfig.__dataclass_fields__
    filtered = {k: v for k, v in data.items() if k in known}
    return ScraperConfig(**filtered)


def save_config(config: ScraperConfig, path: str = "config.json") -> None:
    """將設定寫入 config.json（UTF-8，縮排 2）。"""
    Path(path).write_text(
        json.dumps(asdict(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
