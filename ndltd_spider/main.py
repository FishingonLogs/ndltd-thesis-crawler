"""程式進入點：啟動 PyQt6 桌面應用程式。"""

import sys

from PyQt6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1000, 640)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
