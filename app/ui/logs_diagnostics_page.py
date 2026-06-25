from __future__ import annotations

import json
import os
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
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

from app.services.diagnostics import DIAGNOSTICS_DIR
from app.services.run_manager import RUNS_DIR


REPO_ROOT = Path(__file__).resolve().parent.parent.parent

COLUMNS = [
    "run_id",
    "开始时间",
    "可用性",
    "qc",
    "vision",
    "零件",
    "硬失败",
    "run_dir",
]
COL_RUN_ID = 0
COL_STARTED = 1
COL_USABLE = 2
COL_QC = 3
COL_VISION = 4
COL_PART = 5
COL_HARD_FAIL = 6
COL_RUN_DIR = 7

USABLE_COLORS = {
    "pass": QColor("#2E7D32"),
    "fail": QColor("#C62828"),
    "unknown": QColor("#757575"),
}


@dataclass
class RunSummary:
    run_id: str
    run_dir: Path
    manifest_path: Path
    manifest: dict[str, Any]
    modified_at: float

    @property
    def part_name(self) -> str:
        value = str(self.manifest.get("input_part_path_abs") or "")
        return Path(value).name if value else ""

    @property
    def drawing_usable_label(self) -> str:
        drawing_usable = self.manifest.get("drawing_usable")
        if isinstance(drawing_usable, dict):
            value = drawing_usable.get("pass")
        else:
            value = drawing_usable
        if value is True:
            return "pass"
        if value is False:
            return "fail"
        return "unknown"


class LogsDiagnosticsPage(QWidget):
    """Operational run log and diagnostics workbench."""

    request_build_diagnostics = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._runs: list[RunSummary] = []
        self._current_run: RunSummary | None = None
        self._diagnostics: list[Path] = []
        self._pending_diagnostics_job_id = ""

        self.summary_label = QLabel("日志诊断")
        self.summary_label.setWordWrap(True)

        self.btn_refresh = QPushButton("刷新")
        self.btn_build_zip = QPushButton("生成诊断包")
        self.btn_copy = QPushButton("复制摘要")
        self.btn_open_run = QPushButton("打开运行目录")
        self.btn_open_diag = QPushButton("打开诊断目录")

        top = QHBoxLayout()
        top.addWidget(self.summary_label, 1)
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_build_zip)
        top.addWidget(self.btn_copy)
        top.addWidget(self.btn_open_run)
        top.addWidget(self.btn_open_diag)

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
        self.table.setColumnWidth(COL_RUN_ID, 120)
        self.table.setColumnWidth(COL_STARTED, 145)
        self.table.setColumnWidth(COL_USABLE, 70)
        self.table.setColumnWidth(COL_QC, 60)
        self.table.setColumnWidth(COL_VISION, 70)
        self.table.setColumnWidth(COL_PART, 250)
        self.table.setColumnWidth(COL_HARD_FAIL, 180)

        self.file_combo = QComboBox(self)
        self.file_combo.setMinimumWidth(260)
        self.btn_reload_file = QPushButton("重读文件")
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("文件"))
        file_row.addWidget(self.file_combo, 1)
        file_row.addWidget(self.btn_reload_file)

        self.detail_view = QPlainTextEdit(self)
        self.detail_view.setReadOnly(True)
        self.detail_view.setMaximumBlockCount(12000)
        self.detail_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addLayout(file_row)
        right_layout.addWidget(self.detail_view, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.table)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([560, 760])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_build_zip.clicked.connect(self.build_selected_diagnostics)
        self.btn_copy.clicked.connect(self.copy_summary)
        self.btn_open_run.clicked.connect(self.open_selected_run_dir)
        self.btn_open_diag.clicked.connect(self.open_diagnostics_dir)
        self.btn_reload_file.clicked.connect(self._load_selected_file)
        self.file_combo.currentIndexChanged.connect(lambda _: self._load_selected_file())
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._on_selection_changed())

        QTimer.singleShot(0, self.refresh)

    def refresh(self) -> None:
        self._runs = discover_runs()
        self._diagnostics = list_diagnostics()
        self._render_runs()
        self.summary_label.setText(self._build_overall_summary())
        if self._runs and self.table.currentIndex().row() < 0:
            self.table.selectRow(0)
        elif not self._runs:
            self._current_run = None
            self.file_combo.clear()
            self.detail_view.setPlainText("no runs found")

    def build_selected_diagnostics(self) -> Path | None:
        run = self._selected_run()
        if run is None:
            self.detail_view.setPlainText("select a run first")
            return None
        self.request_build_diagnostics.emit(run.run_id)
        self.summary_label.setText(f"诊断包生成中: {run.run_id}")
        self.detail_view.setPlainText(f"diagnostics job requested for run_id={run.run_id}")
        return None

    def set_diagnostics_running(self, run_id: str, job_id: str) -> None:
        self._pending_diagnostics_job_id = job_id
        self.btn_build_zip.setEnabled(False)
        self.summary_label.setText(f"诊断包生成中: run_id={run_id} job_id={job_id}")

    def show_diagnostics_result(self, zip_path: str | Path) -> None:
        self._pending_diagnostics_job_id = ""
        self.btn_build_zip.setEnabled(True)
        path = Path(zip_path)
        self._diagnostics = list_diagnostics()
        self.detail_view.setPlainText(describe_zip(path))
        self.summary_label.setText(f"诊断包已生成: {path}")

    def show_diagnostics_failed(self, reason: str) -> None:
        self._pending_diagnostics_job_id = ""
        self.btn_build_zip.setEnabled(True)
        self.detail_view.setPlainText(f"diagnostics failed: {reason}")
        self.summary_label.setText(f"诊断包生成失败: {reason}")
        QMessageBox.warning(self, "Diagnostics", f"诊断包生成失败: {reason}")

    def copy_summary(self) -> str:
        run = self._selected_run()
        text = self._build_run_summary(run) if run else self._build_overall_summary()
        QApplication.clipboard().setText(text)
        self.detail_view.setPlainText(text)
        return text

    def open_selected_run_dir(self) -> None:
        run = self._selected_run()
        if run is None:
            return
        open_directory(run.run_dir)

    def open_diagnostics_dir(self) -> None:
        DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
        open_directory(DIAGNOSTICS_DIR)

    def select_run_for_test(self, run_id: str) -> bool:
        for row in range(self.model.rowCount()):
            item = self.model.item(row, COL_RUN_ID)
            if item and item.text() == run_id:
                self.table.selectRow(row)
                self._on_selection_changed()
                return True
        return False

    def _render_runs(self) -> None:
        self.model.setRowCount(0)
        for run in self._runs:
            hard_fail = run.manifest.get("hard_fail") or []
            if isinstance(hard_fail, list):
                hard_fail_text = ", ".join(str(x) for x in hard_fail[:4])
                if len(hard_fail) > 4:
                    hard_fail_text += " ..."
            else:
                hard_fail_text = str(hard_fail)
            values = [
                run.run_id,
                str(run.manifest.get("started_at") or ""),
                run.drawing_usable_label,
                str(run.manifest.get("qc_pass_count") or ""),
                "" if run.manifest.get("vision_score") is None else str(run.manifest.get("vision_score")),
                run.part_name,
                hard_fail_text,
                str(run.run_dir),
            ]
            items = [QStandardItem(v) for v in values]
            items[COL_RUN_ID].setData(run.run_id, Qt.ItemDataRole.UserRole)
            tooltip = json.dumps(run.manifest, ensure_ascii=False, indent=2)
            for item in items:
                item.setToolTip(tooltip)
            color = USABLE_COLORS.get(run.drawing_usable_label)
            if color is not None:
                items[COL_USABLE].setForeground(color)
            self.model.appendRow(items)

    def _on_selection_changed(self) -> None:
        run = self._selected_run()
        self._current_run = run
        if run is None:
            self.file_combo.clear()
            self.detail_view.setPlainText("select a run")
            return
        self._populate_file_combo(run)
        self.summary_label.setText(self._build_run_summary(run))
        self._load_selected_file()

    def _populate_file_combo(self, run: RunSummary) -> None:
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for label, path in collect_run_files(run):
            self.file_combo.addItem(label, str(path))
        self.file_combo.blockSignals(False)

    def _load_selected_file(self) -> None:
        run = self._current_run
        if run is None:
            return
        path_text = self.file_combo.currentData()
        if not path_text:
            self.detail_view.setPlainText(self._build_run_summary(run))
            return
        path = Path(str(path_text))
        if not path.exists():
            self.detail_view.setPlainText(f"文件缺失: {path}")
            return
        self.detail_view.setPlainText(read_display_text(path))

    def _selected_run(self) -> RunSummary | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        item = self.model.item(idx.row(), COL_RUN_ID)
        if item is None:
            return None
        run_id = str(item.data(Qt.ItemDataRole.UserRole) or item.text())
        for run in self._runs:
            if run.run_id == run_id:
                return run
        return None

    def _build_overall_summary(self) -> str:
        total = len(self._runs)
        usable = sum(1 for r in self._runs if r.drawing_usable_label == "pass")
        failed = sum(1 for r in self._runs if r.drawing_usable_label == "fail")
        diag_count = len(self._diagnostics)
        return f"runs={total} usable={usable} failed={failed} diagnostics={diag_count}"

    def _build_run_summary(self, run: RunSummary) -> str:
        manifest = run.manifest
        hard_fail = manifest.get("hard_fail") or []
        warnings = manifest.get("warnings") or []
        exceptions = manifest.get("exception_summary") or []
        files = collect_run_files(run)
        lines = [
            f"run_id: {run.run_id}",
            f"run_dir: {run.run_dir}",
            f"part: {run.part_name}",
            f"started_at: {manifest.get('started_at', '')}",
            f"finished_at: {manifest.get('finished_at', '')}",
            f"drawing_usable: {run.drawing_usable_label}",
            f"qc_pass_count: {manifest.get('qc_pass_count', '')}",
            f"vision_score: {manifest.get('vision_score', '')}",
            f"hard_fail: {json.dumps(hard_fail, ensure_ascii=False)}",
            f"warnings_count: {len(warnings) if isinstance(warnings, list) else 0}",
            f"exception_count: {len(exceptions) if isinstance(exceptions, list) else 0}",
            f"diagnostic_files_found: {len(files)}",
        ]
        return "\n".join(lines)


def discover_runs(limit: int = 300) -> list[RunSummary]:
    if not RUNS_DIR.exists():
        return []
    runs: list[RunSummary] = []
    for run_dir in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {"run_id": run_dir.name, "_manifest_error": "parse failed"}
        run_id = str(manifest.get("run_id") or run_dir.name)
        runs.append(
            RunSummary(
                run_id=run_id,
                run_dir=run_dir,
                manifest_path=manifest_path,
                manifest=manifest,
                modified_at=manifest_path.stat().st_mtime,
            )
        )
        if len(runs) >= limit:
            break
    return runs


def list_diagnostics() -> list[Path]:
    if not DIAGNOSTICS_DIR.exists():
        return []
    return sorted(DIAGNOSTICS_DIR.glob("diagnostics_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)


def collect_run_files(run: RunSummary) -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = [("manifest.json", run.manifest_path)]
    wanted = [
        ("logs/run.log", run.run_dir / "logs" / "run.log"),
        ("logs/sw.log", run.run_dir / "logs" / "sw.log"),
        ("logs/exceptions.log", run.run_dir / "logs" / "exceptions.log"),
        ("logs/ui.log", run.run_dir / "logs" / "ui.log"),
        ("sw_session.json", run.run_dir / "sw_session.json"),
        ("logs/sw_session.json", run.run_dir / "logs" / "sw_session.json"),
        ("qc/vision_qc_v5.json", run.run_dir / "qc" / "vision_qc_v5.json"),
        ("qc/vision_qc_v4.json", run.run_dir / "qc" / "vision_qc_v4.json"),
        ("qc/vision_qc_v3.json", run.run_dir / "qc" / "vision_qc_v3.json"),
        ("qc/final_quality.json", run.run_dir / "qc" / "final_quality.json"),
        ("worker_stdout.log", run.run_dir / "logs" / "worker_stdout.log"),
        ("worker_stderr.log", run.run_dir / "logs" / "worker_stderr.log"),
    ]
    entries.extend((label, path) for label, path in wanted if path.exists())

    qc_dir = run.run_dir / "qc"
    if qc_dir.exists():
        seen = {path.resolve() for _, path in entries if path.exists()}
        for path in sorted(qc_dir.glob("*.json"), key=lambda p: p.name.lower()):
            try:
                key = path.resolve()
            except Exception:
                key = path
            if key not in seen:
                entries.append((f"qc/{path.name}", path))
                seen.add(key)

    log_dir = run.run_dir / "logs"
    if log_dir.exists():
        seen = {path.resolve() for _, path in entries if path.exists()}
        for path in sorted(log_dir.glob("*"), key=lambda p: p.name.lower()):
            if not path.is_file() or path.suffix.lower() not in {".log", ".json", ".txt"}:
                continue
            try:
                key = path.resolve()
            except Exception:
                key = path
            if key not in seen:
                entries.append((f"logs/{path.name}", path))
                seen.add(key)
    return [(label, path) for label, path in entries if path.exists()]


def read_display_text(path: Path, max_chars: int = 250_000) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            text = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"read failed: {path}\n{type(exc).__name__}: {exc}"
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n... truncated at {max_chars} chars ..."
    return text


def describe_zip(zip_path: Path) -> str:
    lines = [f"zip: {zip_path}", f"size_bytes: {zip_path.stat().st_size}"]
    try:
        with zipfile.ZipFile(zip_path) as zf:
            lines.append("contents:")
            for name in zf.namelist():
                lines.append(f"  - {name}")
    except Exception as exc:
        lines.append(f"zip read failed: {exc}")
    return "\n".join(lines)


def open_directory(path: Path) -> None:
    try:
        os.startfile(str(path))
    except Exception:
        subprocess.Popen(["explorer", str(path)])
