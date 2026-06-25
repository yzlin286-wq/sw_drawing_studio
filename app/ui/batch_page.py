from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)


COLUMNS = [
    "File",
    "Category",
    "Front View",
    "Scale",
    "Status",
    "QC Pass",
    "Vision Score",
    "Output Path",
    "Error",
    "Summary",
    "Grade",
    "PartClass",
    "FinalStatus",
    "UsableFor",
    "AddinDim",
    "DocMgr",
    "VisionV3",
]
COL_NAME = 0
COL_CATEGORY = 1
COL_FRONT_VIEW = 2
COL_SCALE = 3
COL_STATUS = 4
COL_QC = 5
COL_VISION = 6
COL_OUT = 7
COL_ERROR = 8
COL_RESULT = 9
COL_GRADE = 10
COL_PARTCLASS = 11
COL_FINALSTATUS = 12
COL_USABLEFOR = 13
COL_ADDINDIM = 14
COL_DOCMGR = 15
COL_VISIONV3 = 16

SUPPORTED_EXTS = {".sldprt", ".sldasm"}


_STATUS_COLORS = {
    "pending": QColor("#757575"),
    "queued": QColor("#757575"),
    "pre_analyzing": QColor("#1976D2"),
    "pre_analysis_failed": QColor("#C62828"),
    "ready": QColor("#1976D2"),
    "running": QColor("#1976D2"),
    "completed": QColor("#2E7D32"),
    "failed": QColor("#C62828"),
    "timeout": QColor("#E67E22"),
    "retry": QColor("#F57C00"),
    "recovered": QColor("#1565C0"),
    "restarting": QColor("#6A1B9A"),
    "排队中": QColor("#757575"),
    "运行中": QColor("#1976D2"),
    "完成": QColor("#2E7D32"),
    "失败": QColor("#C62828"),
}


class BatchPage(QWidget):
    request_run = Signal(list)
    request_pre_analyze = Signal(list)
    request_stop = Signal()
    request_rerun_one = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.btn_add_files = QPushButton("Add Files")
        self.btn_add_dir = QPushButton("Add Folder")
        self.btn_clear = QPushButton("Clear")
        self.btn_pre_analyze = QPushButton("AI Pre-Analyze")
        self.btn_run = QPushButton("Start")
        self.btn_stop = QPushButton("Stop")
        self.btn_rerun = QPushButton("Rerun Selected")
        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setToolTip("Cancel the current batch job. Esc also works.")
        self.btn_rerun.setToolTip("Rerun the currently selected row.")

        self.btn_add_files.clicked.connect(self._on_add_files)
        self.btn_add_dir.clicked.connect(self._on_add_dir)
        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_pre_analyze.clicked.connect(self._on_pre_analyze)
        self.btn_run.clicked.connect(self._on_run)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_rerun.clicked.connect(self._on_rerun_one)
        self.btn_export_csv.clicked.connect(self._on_export_csv)

        bar = QHBoxLayout()
        bar.addWidget(self.btn_add_files)
        bar.addWidget(self.btn_add_dir)
        bar.addWidget(self.btn_clear)
        bar.addStretch(1)
        bar.addWidget(self.btn_pre_analyze)
        bar.addWidget(self.btn_run)
        bar.addWidget(self.btn_rerun)
        bar.addWidget(self.btn_export_csv)
        bar.addWidget(self.btn_stop)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.filter_grade = QComboBox()
        self.filter_grade.addItems(["All Grade", "A", "B", "C", "D"])
        self.filter_partclass = QComboBox()
        self.filter_partclass.addItems(
            ["All Class", "feature_part", "long_thin", "tiny_part", "fastener", "spring", "purchased_part"]
        )
        self.filter_finalstatus = QComboBox()
        self.filter_finalstatus.addItems(["All Status", "pass", "pass_with_warning", "need_review", "fail"])
        self.filter_usablefor = QComboBox()
        self.filter_usablefor.addItems(["All Usable", "manufacturing", "assembly", "procurement"])
        self.filter_addin = QComboBox()
        self.filter_addin.addItems(["All Addin", "addin_pass", "addin_fail", "addin_none"])
        self.filter_docmgr = QComboBox()
        self.filter_docmgr.addItems(["All DocMgr", "docmgr_pass", "docmgr_warning", "docmgr_fail"])
        self.filter_vision = QComboBox()
        self.filter_vision.addItems(["All Vision", "vision_pass", "vision_warning", "vision_fail"])

        for widget in [
            self.filter_grade,
            self.filter_partclass,
            self.filter_finalstatus,
            self.filter_usablefor,
            self.filter_addin,
            self.filter_docmgr,
            self.filter_vision,
        ]:
            filter_row.addWidget(widget)
            widget.currentIndexChanged.connect(self._apply_filters)
        filter_row.addStretch(1)

        self.model = QStandardItemModel(0, len(COLUMNS), self)
        self.model.setHorizontalHeaderLabels(COLUMNS)

        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(COL_NAME, 260)
        self.table.setColumnWidth(COL_CATEGORY, 110)
        self.table.setColumnWidth(COL_FRONT_VIEW, 90)
        self.table.setColumnWidth(COL_SCALE, 70)
        self.table.setColumnWidth(COL_STATUS, 90)
        self.table.setColumnWidth(COL_QC, 90)
        self.table.setColumnWidth(COL_VISION, 100)
        self.table.setColumnWidth(COL_OUT, 320)

        self.empty_label = QLabel("No CAD files added yet. Use Add Files or Add Folder to start a batch validation run.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            "QLabel {"
            "background:#E3F2FD;"
            "color:#0D47A1;"
            "border:1px solid #90CAF9;"
            "border-radius:4px;"
            "padding:10px;"
            "font-weight:600;"
            "}"
        )

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(bar)
        layout.addLayout(filter_row)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.progress)
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        empty = self.model.rowCount() == 0
        self.empty_label.setVisible(empty)
        self.table.setToolTip("No files yet. Use Add Files or Add Folder to start." if empty else "")

    def set_running(self, running: bool) -> None:
        for button in (
            self.btn_add_files,
            self.btn_add_dir,
            self.btn_clear,
            self.btn_pre_analyze,
            self.btn_run,
        ):
            button.setEnabled(not running)
        self.btn_stop.setEnabled(bool(running))

    def items(self) -> list[str]:
        out: list[str] = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row, COL_NAME)
            if item is None:
                continue
            path = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(path, str) and path:
                out.append(path)
        return out

    def add_paths(self, paths: list[str]) -> None:
        existing = set(self.items())
        for path in paths:
            if not path or path in existing:
                continue
            existing.add(path)
            row = [QStandardItem("") for _ in COLUMNS]
            row[COL_NAME].setText(Path(path).name)
            row[COL_NAME].setData(path, Qt.ItemDataRole.UserRole)
            row[COL_NAME].setToolTip(path)
            row[COL_STATUS].setText("pending")
            row[COL_STATUS].setForeground(QBrush(_STATUS_COLORS["pending"]))
            self.model.appendRow(row)
        self._update_empty_state()

    def _row_index_of(self, path: str) -> int:
        for row in range(self.model.rowCount()):
            item = self.model.item(row, COL_NAME)
            if item and item.data(Qt.ItemDataRole.UserRole) == path:
                return row
        return -1

    def update_row(
        self,
        path: str,
        status: str | None = None,
        qc_pass: str | None = None,
        vision_score: str | None = None,
        output_path: str | None = None,
        error: str | None = None,
        grade: str | None = None,
        part_class: str | None = None,
        final_status: str | None = None,
        usable_for: str | None = None,
        addin_dim: str | None = None,
        docmgr: str | None = None,
        vision_v3: str | None = None,
    ) -> None:
        row = self._row_index_of(path)
        if row < 0:
            return
        updates = {
            COL_STATUS: status,
            COL_QC: qc_pass,
            COL_VISION: vision_score,
            COL_OUT: output_path,
            COL_ERROR: error,
            COL_GRADE: grade,
            COL_PARTCLASS: part_class,
            COL_FINALSTATUS: final_status,
            COL_USABLEFOR: usable_for,
            COL_ADDINDIM: addin_dim,
            COL_DOCMGR: docmgr,
            COL_VISIONV3: vision_v3,
        }
        for col, value in updates.items():
            if value is None:
                continue
            item = self.model.item(row, col)
            if item is None:
                item = QStandardItem()
                self.model.setItem(row, col, item)
            item.setText(str(value))
            if col == COL_STATUS:
                color = _STATUS_COLORS.get(str(value))
                if color is not None:
                    item.setForeground(QBrush(color))
        self._apply_filters()

    def _apply_filters(self) -> None:
        checks = [
            (self.filter_grade.currentText(), "All Grade", COL_GRADE),
            (self.filter_partclass.currentText(), "All Class", COL_PARTCLASS),
            (self.filter_finalstatus.currentText(), "All Status", COL_FINALSTATUS),
            (self.filter_usablefor.currentText(), "All Usable", COL_USABLEFOR),
        ]
        for row in range(self.model.rowCount()):
            hide = False
            for selected, all_label, col in checks:
                value = self.model.item(row, col).text() if self.model.item(row, col) else ""
                if selected != all_label and selected not in value:
                    hide = True
            self.table.setRowHidden(row, hide)

    def set_pre_analysis(self, row: int, result: dict | None) -> None:
        if row < 0 or row >= self.model.rowCount():
            return
        if not isinstance(result, dict) or not result:
            self.model.item(row, COL_CATEGORY).setText("fail")
            self.model.item(row, COL_FRONT_VIEW).setText("fail")
            self.model.item(row, COL_SCALE).setText("fail")
            return
        self.model.item(row, COL_CATEGORY).setText(str(result.get("category") or "fail"))
        self.model.item(row, COL_FRONT_VIEW).setText(str(result.get("front_view") or "fail"))
        self.model.item(row, COL_SCALE).setText(str(result.get("scale") or "fail"))

    def set_pre_analysis_by_path(self, path: str, result: dict | None) -> None:
        row = self._row_index_of(path)
        if row >= 0:
            self.set_pre_analysis(row, result)

    def update_row_status(self, row: int, status: str, warning_text: str = "") -> None:
        col = self.model.columnCount() - 1
        item = self.model.item(row, col) or QStandardItem()
        text = {"success": "OK", "warning": "WARNING", "fail": "FAIL"}.get(status, status)
        item.setText(text)
        if warning_text:
            item.setToolTip(warning_text)
        self.model.setItem(row, col, item)

    def set_progress(self, current: int, total: int) -> None:
        if total <= 0:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            return
        self.progress.setRange(0, total)
        self.progress.setValue(min(current, total))
        self.progress.setFormat(f"{current}/{total}")

    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select SolidWorks Files",
            "",
            "SolidWorks (*.SLDPRT *.sldprt *.SLDASM *.sldasm);;All Files (*)",
        )
        if paths:
            self.add_paths(paths)

    def _on_add_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not directory:
            return
        found = [
            str(path)
            for path in Path(directory).rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
        ]
        if found:
            self.add_paths(found)

    def _on_clear(self) -> None:
        self.model.removeRows(0, self.model.rowCount())
        self.progress.setValue(0)
        self.progress.setFormat("")
        self._update_empty_state()

    def _on_pre_analyze(self) -> None:
        items = self.items()
        if items:
            self.request_pre_analyze.emit(items)

    def _on_run(self) -> None:
        items = self.items()
        if items:
            self.request_run.emit(items)

    def _on_stop(self) -> None:
        self.request_stop.emit()

    def _on_rerun_one(self) -> None:
        index = self.table.currentIndex()
        if not index.isValid():
            QMessageBox.information(self, "Rerun Selected", "Select one row first.")
            return
        item = self.model.item(index.row(), COL_NAME)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path, str) or not path:
            return
        self.update_row(path, status="queued", error="")
        self.request_rerun_one.emit(path)

    def _on_export_csv(self) -> None:
        if self.model.rowCount() <= 0:
            QMessageBox.information(self, "Export CSV", "No rows to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Batch CSV", "batch_summary.csv", "CSV (*.csv);;All Files (*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(COLUMNS)
                for row in range(self.model.rowCount()):
                    writer.writerow(
                        [
                            self.model.item(row, col).text() if self.model.item(row, col) else ""
                            for col in range(len(COLUMNS))
                        ]
                    )
            QMessageBox.information(self, "Export CSV", f"Exported {self.model.rowCount()} rows:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Export CSV", f"Export failed: {exc}")
