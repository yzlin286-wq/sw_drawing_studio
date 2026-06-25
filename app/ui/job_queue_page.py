from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.services.job_runtime_facade import get_job_runtime_facade


COLUMNS = [
    "job_id",
    "part",
    "stage",
    "progress",
    "status",
    "retry_count",
    "duration",
    "sw_pid",
    "last_event",
    "action",
]
COL_JOB_ID = 0
COL_PART = 1
COL_STAGE = 2
COL_PROGRESS = 3
COL_STATUS = 4
COL_RETRY = 5
COL_DURATION = 6
COL_PID = 7
COL_LAST_EVENT = 8
COL_ACTION = 9


STATUS_COLORS = {
    "pending": QColor("#757575"),
    "queued": QColor("#616161"),
    "running": QColor("#1976D2"),
    "paused": QColor("#7B1FA2"),
    "completed": QColor("#2E7D32"),
    "failed": QColor("#C62828"),
    "cancelled": QColor("#6D4C41"),
    "timeout": QColor("#E67E22"),
    "recovering": QColor("#1565C0"),
}


class JobQueuePage(QWidget):
    """v2.3 Job Queue UI backed by JobRuntimeFacade/QProcess workers."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.facade = get_job_runtime_facade()
        self._rows_by_job_id: dict[str, int] = {}
        self._last_events: list[dict[str, Any]] = []

        self.btn_mock = QPushButton("启动 Mock")
        self.btn_add_cad = QPushButton("添加 CAD 文件")
        self.btn_start_cad = QPushButton("启动 CAD")
        self.btn_pause = QPushButton("暂停队列")
        self.btn_resume = QPushButton("恢复队列")
        self.btn_cancel = QPushButton("取消当前")
        self.btn_retry = QPushButton("重试选中")
        self.btn_skip = QPushButton("跳过选中")
        self.btn_open = QPushButton("打开目录")
        self.btn_refresh = QPushButton("刷新")

        self.scenario = QComboBox()
        self.scenario.addItems([
            "normal_pass",
            "pass_with_warning",
            "recovered",
            "stuck_then_recovered",
            "failed",
            "timeout",
        ])
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.1, 7200.0)
        self.duration.setDecimals(1)
        self.duration.setSingleStep(1.0)
        self.duration.setValue(5.0)
        self.duration.setSuffix(" s")
        self._pending_cad_paths: list[str] = []
        self.pending_label = QLabel("待启动 CAD: 0")

        top = QHBoxLayout()
        top.addWidget(self.btn_add_cad)
        top.addWidget(self.btn_start_cad)
        top.addWidget(self.pending_label)
        top.addSpacing(12)
        top.addWidget(QLabel("场景"))
        top.addWidget(self.scenario)
        top.addWidget(QLabel("时长"))
        top.addWidget(self.duration)
        top.addWidget(self.btn_mock)
        top.addSpacing(12)
        top.addWidget(self.btn_pause)
        top.addWidget(self.btn_resume)
        top.addWidget(self.btn_cancel)
        top.addWidget(self.btn_retry)
        top.addWidget(self.btn_skip)
        top.addWidget(self.btn_open)
        top.addStretch(1)
        top.addWidget(self.btn_refresh)

        self.model = QStandardItemModel(0, len(COLUMNS), self)
        self.model.setHorizontalHeaderLabels(COLUMNS)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(COL_JOB_ID, 90)
        self.table.setColumnWidth(COL_PART, 180)
        self.table.setColumnWidth(COL_STAGE, 220)
        self.table.setColumnWidth(COL_PROGRESS, 80)
        self.table.setColumnWidth(COL_STATUS, 90)
        self.table.setColumnWidth(COL_LAST_EVENT, 120)

        self.event_view = QPlainTextEdit(self)
        self.event_view.setReadOnly(True)
        self.event_view.setMaximumBlockCount(2000)
        self.event_view.setPlaceholderText("worker stdout JSONL events")

        self.timeline_view = QPlainTextEdit(self)
        self.timeline_view.setReadOnly(True)
        self.timeline_view.setMaximumBlockCount(1000)
        self.timeline_view.setPlaceholderText("sw_session / job timeline")

        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("事件 JSONL"))
        right_layout.addWidget(self.event_view, 2)
        right_layout.addWidget(QLabel("时间线"))
        right_layout.addWidget(self.timeline_view, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.table)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([820, 420])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)

        self.btn_mock.clicked.connect(self._start_mock)
        self.btn_add_cad.clicked.connect(self._add_cad_files)
        self.btn_start_cad.clicked.connect(self._start_cad_jobs)
        self.btn_pause.clicked.connect(self._pause_queue)
        self.btn_resume.clicked.connect(self._resume_queue)
        self.btn_cancel.clicked.connect(self._cancel_current)
        self.btn_retry.clicked.connect(self._retry_selected)
        self.btn_skip.clicked.connect(self._skip_selected)
        self.btn_open.clicked.connect(self._open_selected_dir)
        self.btn_refresh.clicked.connect(self.refresh)

        self.facade.job_started.connect(self._on_job_started)
        self.facade.job_progress.connect(self._on_job_progress)
        self.facade.job_finished.connect(self._on_job_finished)
        self.facade.job_failed.connect(self._on_job_failed)
        self.facade.job_heartbeat.connect(self._on_job_heartbeat)
        self.facade.event_logged.connect(self._on_event_logged)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start()
        self.refresh()

    def refresh(self) -> None:
        try:
            jobs = self.facade.list_jobs()
        except Exception as exc:
            self._append_timeline(f"refresh failed: {exc}")
            return
        seen = set()
        for job in jobs:
            job_id = str(job.get("job_id", ""))
            if not job_id:
                continue
            seen.add(job_id)
            self._upsert_job(job)

        for job_id in list(self._rows_by_job_id):
            if job_id not in seen:
                row = self._rows_by_job_id.pop(job_id)
                self.model.removeRow(row)
                self._reindex_rows()

    def _start_mock(self) -> None:
        try:
            job_id = self.facade.start_mock_job(
                scenario=self.scenario.currentText(),
                duration_s=float(self.duration.value()),
            )
            self._append_timeline(f"mock started: {job_id}")
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "作业队列", f"启动失败: {exc}")

    def _add_cad_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择 SolidWorks 文件",
            "",
            "SolidWorks (*.SLDPRT *.sldprt *.SLDASM *.sldasm);;All Files (*)",
        )
        if not paths:
            return
        existing = set(self._pending_cad_paths)
        for path in paths:
            if path not in existing:
                self._pending_cad_paths.append(path)
                existing.add(path)
        self.pending_label.setText(f"待启动 CAD: {len(self._pending_cad_paths)}")
        self._append_timeline(f"cad files queued: {len(paths)}")

    def add_cad_paths_for_test(self, paths: list[str]) -> None:
        """Add CAD paths without opening a file dialog; used by smoke tests."""
        existing = set(self._pending_cad_paths)
        for path in paths:
            if path and path not in existing:
                self._pending_cad_paths.append(path)
                existing.add(path)
        self.pending_label.setText(f"待启动 CAD: {len(self._pending_cad_paths)}")

    def _start_cad_jobs(self) -> None:
        if not self._pending_cad_paths:
            self._append_timeline("cad start skipped: no file selected")
            return
        started = 0
        failed: list[str] = []
        for path in list(self._pending_cad_paths):
            try:
                job_id = self.facade.start_cad_job(part_path=path, timeout_s=600)
                self._append_timeline(f"cad started: {job_id} {Path(path).name}")
                started += 1
            except Exception as exc:
                failed.append(f"{Path(path).name}: {exc}")
        self._pending_cad_paths.clear()
        self.pending_label.setText("待启动 CAD: 0")
        if failed:
            self._append_timeline("cad start failures: " + "; ".join(failed))
        self._append_timeline(f"cad jobs started: {started}")
        self.refresh()

    def _pause_queue(self) -> None:
        self.facade.pause_queue()
        self._append_timeline("queue paused")

    def _resume_queue(self) -> None:
        self.facade.resume_queue()
        self._append_timeline("queue resumed")

    def _cancel_current(self) -> None:
        active = self.facade.get_active_job()
        job_id = active.get("job_id") if active else self._selected_job_id()
        if not job_id:
            self._append_timeline("cancel skipped: no active job")
            return
        ok = self.facade.cancel_job(str(job_id))
        self._append_timeline(f"cancel {job_id}: {ok}")
        self.refresh()

    def _retry_selected(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            self._append_timeline("retry skipped: no selected job")
            return
        new_id = self.facade.retry_job(job_id)
        self._append_timeline(f"retry {job_id}: {new_id or 'failed'}")
        self.refresh()

    def _skip_selected(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            self._append_timeline("skip skipped: no selected job")
            return
        ok = self.facade.skip_job(job_id)
        self._append_timeline(f"skip {job_id}: {ok}")
        self.refresh()

    def _open_selected_dir(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            return
        job = self.facade.get_job_status(job_id) or {}
        run_dir = str(job.get("run_dir") or "")
        if not run_dir:
            result = job.get("result") or {}
            if isinstance(result, dict):
                run_dir = str(result.get("run_dir") or result.get("output_dir") or "")
        if not run_dir:
            self._append_timeline(f"跳过打开目录：{job_id} 没有 run_dir")
            return
        path = Path(run_dir)
        if not path.exists():
            self._append_timeline(f"运行目录缺失: {path}")
            return
        try:
            os.startfile(str(path))
        except Exception:
            subprocess.Popen(["explorer", str(path)])

    def _selected_job_id(self) -> str:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return ""
        item = self.model.item(idx.row(), COL_JOB_ID)
        if item is None:
            return ""
        job_id = item.data(Qt.ItemDataRole.UserRole)
        return str(job_id or item.text())

    def _on_job_started(self, job_id: str, data: dict) -> None:
        self._append_timeline(f"{job_id} started")
        self.refresh()

    def _on_job_progress(self, job_id: str, data: dict) -> None:
        self._append_timeline(f"{job_id} progress {data.get('progress', '-')}: {data.get('stage', '')}")
        self.refresh()

    def _on_job_finished(self, job_id: str, data: dict) -> None:
        self._append_timeline(f"{job_id} finished")
        self.refresh()

    def _on_job_failed(self, job_id: str, data: dict) -> None:
        self._append_timeline(f"{job_id} failed: {data.get('error', '')}")
        self.refresh()

    def _on_job_heartbeat(self, job_id: str, data: dict) -> None:
        self._append_timeline(f"{job_id} heartbeat")

    def _on_event_logged(self, job_id: str, event_type: str, data: dict) -> None:
        event = {"job_id": job_id, "event_type": event_type, "data": data}
        self._last_events.append(event)
        if len(self._last_events) > 2000:
            self._last_events = self._last_events[-2000:]
        self.event_view.appendPlainText(json.dumps(event, ensure_ascii=False))

    def _upsert_job(self, job: dict) -> None:
        job_id = str(job.get("job_id", ""))
        row = self._rows_by_job_id.get(job_id)
        if row is None:
            row_items = [QStandardItem("") for _ in COLUMNS]
            self.model.appendRow(row_items)
            row = self.model.rowCount() - 1
            self._rows_by_job_id[job_id] = row

        values = {
            COL_JOB_ID: job_id,
            COL_PART: str(job.get("part_name") or Path(str(job.get("part_path") or "")).name),
            COL_STAGE: str(job.get("stage") or ""),
            COL_PROGRESS: self._format_progress(job.get("progress")),
            COL_STATUS: str(job.get("status") or ""),
            COL_RETRY: str(job.get("retry_count", 0)),
            COL_DURATION: str(job.get("duration_s", 0)),
            COL_PID: str(job.get("sw_pid") or ""),
            COL_LAST_EVENT: str(job.get("last_event") or ""),
            COL_ACTION: "选择行后操作",
        }
        for col, text in values.items():
            item = self.model.item(row, col)
            if item is None:
                item = QStandardItem()
                self.model.setItem(row, col, item)
            item.setText(text)
            if col == COL_JOB_ID:
                item.setData(job_id, Qt.ItemDataRole.UserRole)
                item.setToolTip(json.dumps(job, ensure_ascii=False, indent=2))
        status = str(job.get("status") or "")
        color = STATUS_COLORS.get(status)
        if color is not None:
            self.model.item(row, COL_STATUS).setForeground(QBrush(color))

    def _reindex_rows(self) -> None:
        self._rows_by_job_id.clear()
        for row in range(self.model.rowCount()):
            item = self.model.item(row, COL_JOB_ID)
            if item is not None:
                self._rows_by_job_id[item.text()] = row

    @staticmethod
    def _format_progress(value: Any) -> str:
        try:
            return f"{float(value) * 100:.0f}%"
        except Exception:
            return "0%"

    def _append_timeline(self, text: str) -> None:
        self.timeline_view.appendPlainText(text)
