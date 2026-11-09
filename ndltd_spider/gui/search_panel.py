"""搜尋條件面板（SearchPanel）。

支援動態多列進階查詢（欄位 + 關鍵字 + and/or/not）與學位/學年度限縮，
以及 ID 清單模式匯入。
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QRadioButton,
    QPushButton,
    QGroupBox,
    QFileDialog,
)
from PyQt6.QtCore import pyqtSignal

from ndltd_spider.models import QF_FIELDS, QUERY_OPERATORS, QueryRow, SearchConfig
from ndltd_spider.storage.importer import load_thesis_ids

# 進階表單只有 qf0..qf9 / qs0..qs9，故查詢列上限 10。
MAX_QUERY_ROWS = 10


class QueryRowWidget:
    """單一查詢列所持有的元件：運算子下拉 / 欄位下拉 / 關鍵字輸入 / 移除鈕。

    本身不含 layout——元件由 SearchPanel 置入共用 QGridLayout 以對齊各欄。
    第 0 列的運算子下拉隱藏（與前一列無布林關係）。
    """

    def __init__(self, on_remove) -> None:
        self.operator_combo = QComboBox()
        self.operator_combo.addItems(list(QUERY_OPERATORS))
        self.operator_combo.setFixedWidth(52)

        self.field_combo = QComboBox()
        for code, label in QF_FIELDS.items():
            self.field_combo.addItem(label, code)
        self.field_combo.setFixedWidth(104)

        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText("關鍵字")

        self.remove_btn = QPushButton("移除")
        self.remove_btn.setFixedWidth(56)
        self.remove_btn.clicked.connect(lambda: on_remove(self))

    def cells(self) -> list:
        """依欄順序回傳元件：運算子、欄位、關鍵字、移除。"""
        return [self.operator_combo, self.field_combo, self.keyword_edit, self.remove_btn]

    def to_query_row(self) -> QueryRow:
        return QueryRow(
            field=self.field_combo.currentData(),
            keyword=self.keyword_edit.text(),
            operator=self.operator_combo.currentText(),
        )

    def set_operator_visible(self, visible: bool) -> None:
        self.operator_combo.setVisible(visible)


class SearchPanel(QWidget):
    """搜尋條件面板：動態查詢列 + 學位/學年度限縮 + ID 清單匯入。"""

    start_requested = pyqtSignal(str)   # mode："search" / "ids"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._id_list: list[str] = []
        self.query_rows: list[QueryRowWidget] = []
        self._build_ui()
        self.add_query_row()   # 預設一列

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._build_mode_group())
        main_layout.addWidget(self._build_query_group())
        main_layout.addWidget(self._build_limit_group())
        main_layout.addWidget(self._build_ids_group())

        self._start_btn = QPushButton("開始爬取")
        self._start_btn.clicked.connect(self._on_start_clicked)
        main_layout.addWidget(self._start_btn)
        main_layout.addStretch()

    def _build_mode_group(self) -> QGroupBox:
        group = QGroupBox("模式")
        layout = QHBoxLayout(group)
        self._search_radio = QRadioButton("搜尋模式")
        self._ids_radio = QRadioButton("ID 清單模式")
        self._search_radio.setChecked(True)
        layout.addWidget(self._search_radio)
        layout.addWidget(self._ids_radio)
        return group

    def _build_query_group(self) -> QGroupBox:
        group = QGroupBox("進階查詢條件")
        outer = QVBoxLayout(group)
        # 共用格線：四欄（運算子/欄位/關鍵字/移除）對齊；關鍵字欄伸展
        self._rows_grid = QGridLayout()
        self._rows_grid.setColumnStretch(2, 1)
        self._rows_grid.setHorizontalSpacing(6)
        self._rows_grid.setVerticalSpacing(4)
        outer.addLayout(self._rows_grid)

        self._add_row_btn = QPushButton("+ 新增查詢列")
        self._add_row_btn.clicked.connect(self.add_query_row)
        outer.addWidget(self._add_row_btn)
        return group

    def _build_limit_group(self) -> QGroupBox:
        group = QGroupBox("限縮條件")
        layout = QVBoxLayout(group)

        self._master_cb = QCheckBox("碩士")
        self._master_cb.setChecked(True)
        self._doctor_cb = QCheckBox("博士")
        self._doctor_cb.setChecked(True)
        degree_row = QHBoxLayout()
        degree_row.addWidget(QLabel("學位類別："))
        degree_row.addWidget(self._master_cb)
        degree_row.addWidget(self._doctor_cb)
        degree_row.addStretch()
        layout.addLayout(degree_row)

        self._year_from_input = self._make_year_spinbox()
        self._year_to_input = self._make_year_spinbox()
        year_row = QHBoxLayout()
        year_row.addWidget(QLabel("畢業學年度："))
        year_row.addWidget(self._year_from_input)
        year_row.addWidget(QLabel("～"))
        year_row.addWidget(self._year_to_input)
        year_row.addStretch()
        layout.addLayout(year_row)
        return group

    def _build_ids_group(self) -> QGroupBox:
        group = QGroupBox("ID 清單")
        layout = QHBoxLayout(group)
        self._import_btn = QPushButton("匯入 ID 清單")
        self._import_btn.clicked.connect(self._on_import_clicked)
        layout.addWidget(self._import_btn)
        layout.addStretch()
        return group

    @staticmethod
    def _make_year_spinbox() -> QSpinBox:
        spinbox = QSpinBox()
        spinbox.setRange(0, 9999)
        spinbox.setValue(0)
        spinbox.setSpecialValueText("不限")
        return spinbox

    # -------------------------------------------------------- 動態查詢列

    def add_query_row(self) -> QueryRowWidget | None:
        """新增一列查詢條件（上限 MAX_QUERY_ROWS）；達上限回傳 None。"""
        if len(self.query_rows) >= MAX_QUERY_ROWS:
            return None
        row = QueryRowWidget(self.remove_query_row)
        self.query_rows.append(row)
        self._regrid()
        return row

    def remove_query_row(self, row: QueryRowWidget) -> None:
        """移除指定查詢列；至少保留一列。"""
        if len(self.query_rows) <= 1:
            return
        self.query_rows.remove(row)
        for widget in row.cells():
            self._rows_grid.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._regrid()

    def _regrid(self) -> None:
        """重新將各列元件放入格線（欄位對齊），並更新運算子顯示與鈕狀態。"""
        for row in self.query_rows:                       # 先全部移出，避免重複加入
            for widget in row.cells():
                self._rows_grid.removeWidget(widget)
        multi = len(self.query_rows) > 1
        for r, row in enumerate(self.query_rows):
            for col, widget in enumerate(row.cells()):
                self._rows_grid.addWidget(widget, r, col)
            row.set_operator_visible(r > 0)
            row.remove_btn.setEnabled(multi)              # 單列時停用移除
        self._add_row_btn.setEnabled(len(self.query_rows) < MAX_QUERY_ROWS)

    # ------------------------------------------------------------ 事件

    def _on_import_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 ID 清單 CSV", "", "CSV 檔案 (*.csv);;所有檔案 (*)"
        )
        if path:
            self.load_id_csv(path)

    def _on_start_clicked(self) -> None:
        self.start_requested.emit(self.get_mode())

    # ------------------------------------------------------------ 公開介面

    def get_search_config(self) -> SearchConfig:
        """從查詢列與限縮條件組出 SearchConfig。"""
        rows = [row.to_query_row() for row in self.query_rows]
        return SearchConfig(
            rows=rows,
            degree_master=self._master_cb.isChecked(),
            degree_doctor=self._doctor_cb.isChecked(),
            year_from=self._year_from_input.value(),
            year_to=self._year_to_input.value(),
        )

    def load_id_csv(self, path: str) -> None:
        """讀取 CSV 的 thesis_id 欄（解析委派儲存層），每次呼叫完整取代先前清單。"""
        self._id_list = load_thesis_ids(path)

    def get_id_list(self) -> list[str]:
        return list(self._id_list)

    def get_mode(self) -> str:
        return "ids" if self._ids_radio.isChecked() else "search"
