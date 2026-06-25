from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


_LEVEL_COLORS = {
    "DEBUG": QColor("#808080"),
    "INFO": QColor("#202020"),
    "WARN": QColor("#E67E22"),
    "WARNING": QColor("#E67E22"),
    "ERROR": QColor("#C0392B"),
}


class LogPanel(QWidget):
    request_diagnostics = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._paused = False

        self.editor = QPlainTextEdit(self)
        self.editor.setReadOnly(True)
        self.editor.setMaximumBlockCount(5000)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.btn_clear = QPushButton("清空", self)
        self.btn_export = QPushButton("导出", self)
        self.btn_pause = QPushButton("暂停滚动", self)
        self.btn_pause.setCheckable(True)
        self.btn_diag = QPushButton("生成诊断包", self)
        self.btn_diag.setToolTip("基于最近一次 run 生成 diagnostics zip（含 manifest/qc/vision/logs/screenshots/version.txt）")

        self.btn_clear.clicked.connect(self.clear)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_pause.toggled.connect(self._on_pause_toggled)
        self.btn_diag.clicked.connect(self._on_build_diag)

        bar = QHBoxLayout()
        bar.addWidget(self.btn_clear)
        bar.addWidget(self.btn_export)
        bar.addWidget(self.btn_pause)
        bar.addWidget(self.btn_diag)
        bar.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(bar)
        layout.addWidget(self.editor, 1)

    def clear(self) -> None:
        self.editor.clear()

    def _on_pause_toggled(self, checked: bool) -> None:
        self._paused = bool(checked)
        self.btn_pause.setText("继续滚动" if checked else "暂停滚动")

    def _on_export(self) -> None:
        default_name = f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", default_name, "Text (*.txt);;All Files (*)"
        )
        if not path:
            return
        try:
            Path(path).write_text(self.editor.toPlainText(), encoding="utf-8")
            self.append(f"日志已导出到 {path}", level="INFO")
        except Exception as exc:
            self.append(f"导出日志失败: {exc}", level="ERROR")

    def append(self, text: str, level: str = "INFO") -> None:
        if text is None:
            return
        lvl = (level or "INFO").upper()
        color = _LEVEL_COLORS.get(lvl, _LEVEL_COLORS["INFO"])
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{lvl}] {text}"

        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.insertText(line + "\n", fmt)

        if not self._paused:
            sb = self.editor.verticalScrollBar()
            sb.setValue(sb.maximum())

    def append_raw(self, text: str) -> None:
        if not text:
            return
        lvl = "INFO"
        low = text.lower()
        if "error" in low or "traceback" in low:
            lvl = "ERROR"
        elif "warn" in low:
            lvl = "WARN"
        elif "debug" in low:
            lvl = "DEBUG"
        self.append(text, level=lvl)

    def _on_build_diag(self) -> None:
        self.request_diagnostics.emit()
