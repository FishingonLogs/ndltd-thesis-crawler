# -*- coding: utf-8 -*-
"""PyInstaller 凍結用進入點。

打包成 exe 時，將 PLAYWRIGHT_BROWSERS_PATH 指向內建的 ms-playwright，
讓程式不需另外下載瀏覽器即可執行。
"""
import os
import sys

if getattr(sys, "frozen", False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(sys._MEIPASS, "ms-playwright")

from ndltd_spider.main import main

if __name__ == "__main__":
    sys.exit(main())
