from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.services.job_runtime_facade import get_job_runtime_facade
from app.services.system_health_service import (
    HealthRow,
    build_summary_text,
    count_status,
    find_row,
    health_rows_from_dicts,
)

STATUS_COLORS = {
    "pass": QColor("#2E7D32"),
    "warning": QColor("#E67E22"),
    "fail": QColor("#C62828"),
}


class SystemHealthPage(QWidget):
    """v2.3 grouped system health page.

    The page must stay useful when SolidWorks is not running. In that case the
    drawing workflow is marked unavailable, while history/audit views remain
    usable.
    """

    COLUMNS = ["分组", "检查项", "状态", "信息", "修复建议"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[HealthRow] = []
        self._last_result: dict[str, Any] = {}
        self._active_job_id = ""
        self.facade = get_job_runtime_facade()

        self.summary_label = QLabel("系统健康")
        self.summary_label.setObjectName("systemHealthSummary")
        self.summary_label.setWordWrap(True)

        self.btn_refresh = QPushButton("刷新")
        self.btn_copy = QPushButton("复制摘要")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_copy.clicked.connect(self.copy_summary)

        top = QHBoxLayout()
        top.addWidget(self.summary_label, 1)
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_copy)

        self.model = QStandardItemModel(0, len(self.COLUMNS), self)
        self.model.setHorizontalHeaderLabels(self.COLUMNS)

        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 420)

        self.detail_view = QPlainTextEdit(self)
        self.detail_view.setReadOnly(True)
        self.detail_view.setMaximumBlockCount(2000)
        self.detail_view.setPlaceholderText("系统健康检查详情")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(top)
        layout.addWidget(self.table, 2)
        layout.addWidget(QLabel("详情"))
        layout.addWidget(self.detail_view, 1)

        self.facade.job_progress.connect(self._on_job_progress)
        self.facade.job_finished.connect(self._on_job_finished)
        self.facade.job_failed.connect(self._on_job_failed)
        self.facade.event_logged.connect(self._on_event_logged)

        QTimer.singleShot(0, self.refresh)

    def refresh(self) -> None:
        if self._active_job_id:
            self.detail_view.appendPlainText(f"系统健康检查已在运行: {self._active_job_id}")
            return
        self.btn_refresh.setEnabled(False)
        try:
            self._active_job_id = self.facade.start_system_health_check(timeout_s=30)
            self.summary_label.setText(f"系统健康检查运行中 | job_id={self._active_job_id}")
            self.detail_view.setPlainText(f"系统健康 worker 已启动: {self._active_job_id}")
        except Exception as exc:
            row = HealthRow(
                "UI-Worker",
                "health_page",
                "fail",
                f"系统健康页刷新失败: {exc}",
                "检查 app/ui/system_health_page.py 和相关服务导入错误",
            )
            self._rows = [row]
            self._last_result = {"error": str(exc)}
            self._render(self._rows, self._last_result)
            self.btn_refresh.setEnabled(True)

    def copy_summary(self) -> None:
        text = build_summary_text(self._rows, self._last_result)
        try:
            from PySide6.QtWidgets import QApplication

            clipboard = QApplication.clipboard()
            clipboard.setText(text)
        except Exception:
            pass
        self.detail_view.setPlainText(text)

    def _render(self, rows: list[HealthRow], result: dict[str, Any]) -> None:
        self.model.setRowCount(0)
        for row in rows:
            values = [row.group, row.key, row.status, row.message, row.fix_suggestion]
            items = [QStandardItem(str(v)) for v in values]
            for item in items:
                item.setToolTip(json.dumps(row.details or {}, ensure_ascii=False, indent=2))
            color = STATUS_COLORS.get(row.status)
            if color is not None:
                items[2].setForeground(color)
            self.model.appendRow(items)

        counts = count_status(rows)
        sw_running = find_row(rows, "sw_running")
        sw_ok = sw_running is not None and sw_running.status == "pass"
        if sw_ok:
            availability = "制图功能可用"
        else:
            availability = "制图功能不可用，历史查看可用"
        self.summary_label.setText(
            f"{availability} | pass={counts['pass']} warning={counts['warning']} "
            f"fail={counts['fail']} | {result.get('ts', '')}"
        )
        self.detail_view.setPlainText(build_summary_text(rows, result))

    def _on_job_progress(self, job_id: str, data: dict) -> None:
        if job_id != self._active_job_id:
            return
        stage = str(data.get("stage") or "")
        progress = data.get("progress", "")
        self.summary_label.setText(f"系统健康检查运行中 | {stage} {progress}")

    def _on_job_finished(self, job_id: str, data: dict) -> None:
        if job_id != self._active_job_id:
            return
        self._active_job_id = ""
        self.btn_refresh.setEnabled(True)
        result = (data or {}).get("result", data or {})
        if not isinstance(result, dict):
            self._render_failure(f"系统健康 worker 返回格式异常: {type(result).__name__}")
            return
        rows = health_rows_from_dicts(result.get("rows") or [])
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        self._rows = rows
        self._last_result = summary
        self._render(rows, summary)

    def _on_job_failed(self, job_id: str, data: dict) -> None:
        if job_id != self._active_job_id:
            return
        self._active_job_id = ""
        self.btn_refresh.setEnabled(True)
        self._render_failure(str((data or {}).get("error") or data))

    def _on_event_logged(self, job_id: str, event_type: str, data: dict) -> None:
        if job_id != self._active_job_id:
            return
        if event_type in {"warning", "job_failed"}:
            self.detail_view.appendPlainText(json.dumps({
                "job_id": job_id,
                "event_type": event_type,
                "data": data,
            }, ensure_ascii=False))

    def _render_failure(self, message: str) -> None:
        row = HealthRow(
            "UI-Worker",
            "health_worker",
            "fail",
            f"系统健康 worker 失败: {message}",
            "检查 app/workers/health_check_worker.py 和 worker 调度",
        )
        self._rows = [row]
        self._last_result = {"error": message}
        self._render(self._rows, self._last_result)
