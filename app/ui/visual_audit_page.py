from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
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

from app.services.generated_output_scanner import GeneratedFile, GeneratedOutputScanner
from app.services.visual_audit_reporter import VisualAuditReporter
from app.services.visual_audit_service import AuditResult, VisualAuditService
from app.services.job_runtime_facade import get_job_runtime_facade


REPO_ROOT = Path(__file__).resolve().parent.parent.parent

COLUMNS = [
    "名称",
    "类型",
    "状态",
    "qc",
    "大小KB",
    "修改时间",
    "问题桶",
    "路径",
]
COL_BASE = 0
COL_TYPE = 1
COL_STATUS = 2
COL_QC = 3
COL_SIZE = 4
COL_MODIFIED = 5
COL_BUCKET = 6
COL_PATH = 7

STATUS_COLORS = {
    "audited": QColor("#2E7D32"),
    "missing_qc": QColor("#E67E22"),
    "queued": QColor("#1565C0"),
    "pass": QColor("#2E7D32"),
    "fail": QColor("#C62828"),
    "need_review": QColor("#E67E22"),
    "skipped": QColor("#757575"),
}


class VisualAuditPage(QWidget):
    """v2.3 Visual Audit UI.

    Scanning is lightweight and happens in-process; actual visual audit work is
    launched through JobRuntimeFacade/QProcess workers.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.scanner = GeneratedOutputScanner()
        self.service = VisualAuditService(self.scanner)
        self.facade = get_job_runtime_facade()
        self._files: list[GeneratedFile] = []
        self._audit_results: dict[str, AuditResult] = {}
        self._row_by_path: dict[str, int] = {}

        self.summary_label = QLabel("视觉审计")
        self.summary_label.setWordWrap(True)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["all", "missing_qc", "audited", "failed_or_review"])
        self.bucket_filter = QComboBox()
        self.bucket_filter.addItems(["all", "critical", "major", "minor", "info", "none"])
        self.only_pdf_png = QCheckBox("PDF/PNG")
        self.only_pdf_png.setChecked(True)

        self.btn_scan = QPushButton("扫描")
        self.btn_audit_selected = QPushButton("审计选中")
        self.btn_audit_missing = QPushButton("审计未审计")
        self.btn_rerun_failed = QPushButton("重审 failed/need_review")
        self.btn_export = QPushButton("导出报告")
        self.btn_open = QPushButton("打开目录")
        self.btn_refresh_jobs = QPushButton("刷新作业")

        top = QHBoxLayout()
        top.addWidget(self.summary_label, 1)
        top.addWidget(QLabel("状态"))
        top.addWidget(self.status_filter)
        top.addWidget(QLabel("Issue"))
        top.addWidget(self.bucket_filter)
        top.addWidget(self.only_pdf_png)
        top.addWidget(self.btn_scan)
        top.addWidget(self.btn_audit_selected)
        top.addWidget(self.btn_audit_missing)
        top.addWidget(self.btn_rerun_failed)
        top.addWidget(self.btn_export)
        top.addWidget(self.btn_open)
        top.addWidget(self.btn_refresh_jobs)

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
        self.table.setColumnWidth(COL_BASE, 220)
        self.table.setColumnWidth(COL_TYPE, 70)
        self.table.setColumnWidth(COL_STATUS, 100)
        self.table.setColumnWidth(COL_QC, 80)
        self.table.setColumnWidth(COL_BUCKET, 120)
        self.table.setColumnWidth(COL_PATH, 420)

        self.detail_view = QPlainTextEdit(self)
        self.detail_view.setReadOnly(True)
        self.detail_view.setMaximumBlockCount(5000)
        self.detail_view.setPlaceholderText("选中审计详情 / worker 事件")

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail_view)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)

        self.btn_scan.clicked.connect(self.scan)
        self.btn_audit_selected.clicked.connect(self.audit_selected)
        self.btn_audit_missing.clicked.connect(self.audit_missing)
        self.btn_rerun_failed.clicked.connect(self.rerun_failed_or_review)
        self.btn_export.clicked.connect(self.export_report)
        self.btn_open.clicked.connect(self.open_selected_dir)
        self.btn_refresh_jobs.clicked.connect(self.refresh_jobs)
        self.status_filter.currentTextChanged.connect(lambda _: self._render())
        self.bucket_filter.currentTextChanged.connect(lambda _: self._render())
        self.only_pdf_png.toggled.connect(lambda _: self._render())
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._show_selected_detail())

        self.facade.job_finished.connect(self._on_job_finished)
        self.facade.job_failed.connect(self._on_job_failed)
        self.facade.event_logged.connect(self._on_event_logged)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1500)
        self.refresh_timer.timeout.connect(self.refresh_jobs)
        self.refresh_timer.start()

        QTimer.singleShot(0, self.scan)

    def scan(self) -> None:
        try:
            self._files = self.scanner.scan()
            self.service.save_index(REPO_ROOT / "drw_output" / "visual_audit_index.json")
            self._render()
            self.detail_view.appendPlainText(f"扫描完成: {len(self._files)} 个文件")
        except Exception as exc:
            QMessageBox.warning(self, "视觉审计", f"扫描失败: {exc}")

    def audit_selected(self) -> None:
        targets = self._selected_files()
        if not targets:
            self.detail_view.appendPlainText("已跳过审计选中项：未选择行")
            return
        self._start_audit_jobs(targets)

    def audit_missing(self) -> None:
        targets = [f for f in self._filtered_files() if not f.has_vision_qc and f.file_type in ("pdf", "png")]
        self._start_audit_jobs(targets)

    def rerun_failed_or_review(self) -> None:
        paths = {
            result.file_path
            for result in self._audit_results.values()
            if result.audit_status in {"fail", "need_review"}
        }
        targets = [f for f in self._files if f.path in paths and f.file_type in ("pdf", "png")]
        if not targets:
            targets = [f for f in self._filtered_files() if f.file_type in ("pdf", "png")]
        self._start_audit_jobs(targets)

    def export_report(self) -> None:
        results = list(self._audit_results.values())
        if not results:
            results = [self._result_from_file(f) for f in self._filtered_files()]
        default = str(REPO_ROOT / "drw_output" / "visual_audit_report.xlsx")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出视觉审计报告",
            default,
            "Excel (*.xlsx);;JSON (*.json)",
        )
        if not path:
            return
        try:
            reporter = VisualAuditReporter(results)
            out = Path(path)
            if out.suffix.lower() == ".json":
                reporter.export_json(out)
            else:
                reporter.export_xlsx(out)
            self.detail_view.appendPlainText(f"报告已导出: {out}")
        except Exception as exc:
            QMessageBox.warning(self, "视觉审计", f"导出失败: {exc}")

    def refresh_jobs(self) -> None:
        try:
            for job in self.facade.list_jobs():
                if job.get("job_type") != "vision_audit":
                    continue
                pdf_path = str(job.get("part_path") or "")
                status = str(job.get("status") or "")
                row = self._row_by_path.get(pdf_path)
                if row is not None and row < self.model.rowCount():
                    item = self.model.item(row, COL_STATUS)
                    if item is not None:
                        item.setText(status)
                        color = STATUS_COLORS.get(status)
                        if color is not None:
                            item.setForeground(color)
        except Exception as exc:
            self.detail_view.appendPlainText(f"refresh jobs failed: {exc}")

    def open_selected_dir(self) -> None:
        selected = self._selected_files()
        if not selected:
            return
        path = Path(selected[0].path)
        directory = path.parent if path.is_file() else path
        try:
            import os

            os.startfile(str(directory))
        except Exception:
            self.detail_view.appendPlainText(f"directory: {directory}")

    def _start_audit_jobs(self, targets: list[GeneratedFile]) -> None:
        if not targets:
            self.detail_view.appendPlainText("audit skipped: no eligible PDF/PNG target")
            return
        started = 0
        for gf in targets:
            if gf.file_type not in ("pdf", "png"):
                continue
            pdf_path, png_path = _pair_pdf_png(gf)
            if not pdf_path:
                self.detail_view.appendPlainText(f"skip no pdf/png: {gf.path}")
                continue
            try:
                job_id = self.facade.start_visual_audit(
                    pdf_path=pdf_path,
                    png_path=png_path,
                    run_dir=gf.run_dir,
                )
                started += 1
                self._mark_status(gf.path, "queued")
                self.detail_view.appendPlainText(f"audit queued: {job_id} {Path(pdf_path).name}")
            except Exception as exc:
                self.detail_view.appendPlainText(f"audit failed to start {gf.path}: {exc}")
        self.summary_label.setText(f"已提交视觉审计作业: {started}")

    def _render(self) -> None:
        files = self._filtered_files()
        self.model.setRowCount(0)
        self._row_by_path.clear()
        for gf in files:
            result = self._audit_results.get(gf.path)
            status = result.audit_status if result else ("audited" if gf.has_vision_qc else "missing_qc")
            bucket = _issue_bucket(result.issues if result else _load_issues(gf.vision_qc_path))
            values = [
                gf.base_name,
                gf.file_type,
                status,
                gf.vision_qc_version or ("yes" if gf.has_vision_qc else "no"),
                f"{gf.size_bytes / 1024:.1f}",
                gf.modified_at,
                bucket,
                gf.path,
            ]
            items = [QStandardItem(v) for v in values]
            items[COL_PATH].setData(gf.path, Qt.ItemDataRole.UserRole)
            tooltip = json.dumps(asdict(gf), ensure_ascii=False, indent=2)
            if result:
                tooltip += "\n\n" + json.dumps(_audit_result_dict(result), ensure_ascii=False, indent=2)
            for item in items:
                item.setToolTip(tooltip)
            color = STATUS_COLORS.get(status)
            if color is not None:
                items[COL_STATUS].setForeground(color)
            self.model.appendRow(items)
            self._row_by_path[gf.path] = self.model.rowCount() - 1
        summary = self._summary(files)
        self.summary_label.setText(summary)

    def _filtered_files(self) -> list[GeneratedFile]:
        files = list(self._files)
        if self.only_pdf_png.isChecked():
            files = [f for f in files if f.file_type in ("pdf", "png")]
        status = self.status_filter.currentText()
        if status == "missing_qc":
            files = [f for f in files if not f.has_vision_qc]
        elif status == "audited":
            files = [f for f in files if f.has_vision_qc or f.path in self._audit_results]
        elif status == "failed_or_review":
            paths = {
                p for p, r in self._audit_results.items() if r.audit_status in {"fail", "need_review"}
            }
            files = [f for f in files if f.path in paths]
        bucket = self.bucket_filter.currentText()
        if bucket != "all":
            files = [
                f for f in files
                if _issue_bucket(
                    self._audit_results[f.path].issues if f.path in self._audit_results else _load_issues(f.vision_qc_path)
                ) == bucket
            ]
        return files

    def _selected_files(self) -> list[GeneratedFile]:
        selected_paths: set[str] = set()
        for idx in self.table.selectionModel().selectedRows():
            item = self.model.item(idx.row(), COL_PATH)
            if item is not None:
                selected_paths.add(str(item.data(Qt.ItemDataRole.UserRole) or item.text()))
        return [f for f in self._files if f.path in selected_paths]

    def _show_selected_detail(self) -> None:
        selected = self._selected_files()
        if not selected:
            return
        gf = selected[0]
        payload: dict[str, Any] = {"file": asdict(gf)}
        if gf.path in self._audit_results:
            payload["audit_result"] = _audit_result_dict(self._audit_results[gf.path])
        elif gf.vision_qc_path:
            payload["vision_qc_path"] = gf.vision_qc_path
            payload["issues"] = _load_issues(gf.vision_qc_path)
        self.detail_view.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))

    def _result_from_file(self, gf: GeneratedFile) -> AuditResult:
        issues = _load_issues(gf.vision_qc_path)
        bucket = _issue_bucket(issues)
        if not gf.has_vision_qc:
            status = "skipped"
        elif bucket in {"critical"}:
            status = "fail"
        elif bucket in {"major"}:
            status = "need_review"
        else:
            status = "pass"
        return AuditResult(
            file_path=gf.path,
            base_name=gf.base_name,
            audit_status=status,
            vision_qc_version=gf.vision_qc_version,
            issues=issues,
            duration_ms=0,
            timestamp=gf.modified_at,
        )

    def _mark_status(self, path: str, status: str) -> None:
        row = self._row_by_path.get(path)
        if row is None:
            return
        item = self.model.item(row, COL_STATUS)
        if item is not None:
            item.setText(status)
            color = STATUS_COLORS.get(status)
            if color is not None:
                item.setForeground(color)

    def _on_job_finished(self, job_id: str, data: dict) -> None:
        result = (data or {}).get("result", {})
        details = result.get("details", {}) if isinstance(result, dict) else {}
        job = self.facade.get_job_status(job_id) or {}
        pdf_path = str(job.get("part_path") or details.get("pdf_path") or "")
        if not pdf_path:
            return
        issues = details.get("issues", []) if isinstance(details, dict) else []
        audit_status = _status_from_issues(issues, bool(details.get("success", result.get("pass", False))))
        audit = AuditResult(
            file_path=pdf_path,
            base_name=Path(pdf_path).stem,
            audit_status=audit_status,
            vision_qc_version=str(result.get("version") or details.get("version") or "v5"),
            issues=issues,
            duration_ms=int(details.get("duration_ms", 0) or 0),
            timestamp=str(details.get("timestamp") or ""),
        )
        self._audit_results[pdf_path] = audit
        self._mark_status(pdf_path, audit_status)
        self.detail_view.appendPlainText(f"audit finished: {job_id} {Path(pdf_path).name} {audit_status}")

    def _on_job_failed(self, job_id: str, data: dict) -> None:
        job = self.facade.get_job_status(job_id) or {}
        pdf_path = str(job.get("part_path") or "")
        if pdf_path:
            self._mark_status(pdf_path, "fail")
        self.detail_view.appendPlainText(f"audit failed: {job_id} {data.get('error', '')}")

    def _on_event_logged(self, job_id: str, event_type: str, data: dict) -> None:
        if event_type in {"progress", "job_failed", "job_finished"}:
            self.detail_view.appendPlainText(json.dumps({
                "job_id": job_id,
                "event_type": event_type,
                "data": data,
            }, ensure_ascii=False))

    @staticmethod
    def _summary(files: list[GeneratedFile]) -> str:
        total = len(files)
        audited = sum(1 for f in files if f.has_vision_qc)
        missing = total - audited
        by_type: dict[str, int] = {}
        for f in files:
            by_type[f.file_type] = by_type.get(f.file_type, 0) + 1
        return f"files={total} audited={audited} missing_qc={missing} types={by_type}"


def _pair_pdf_png(gf: GeneratedFile) -> tuple[str, str]:
    path = Path(gf.path)
    if gf.file_type == "pdf":
        png = path.with_suffix(".PNG")
        if not png.exists():
            png = path.with_suffix(".png")
        return str(path), str(png) if png.exists() else ""
    if gf.file_type == "png":
        pdf = path.with_suffix(".PDF")
        if not pdf.exists():
            pdf = path.with_suffix(".pdf")
        return (str(pdf) if pdf.exists() else str(path), str(path))
    return "", ""


def _load_issues(qc_path: str) -> list[dict]:
    if not qc_path:
        return []
    try:
        data = json.loads(Path(qc_path).read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data.get("issues"), list):
        return data["issues"]
    if isinstance(data.get("results"), list):
        issues: list[dict] = []
        for item in data["results"]:
            if isinstance(item, dict) and isinstance(item.get("issues"), list):
                issues.extend(item["issues"])
        return issues
    return []


def _issue_bucket(issues: list[dict]) -> str:
    severities = {str(i.get("severity", "")).lower() for i in issues if isinstance(i, dict)}
    if "critical" in severities:
        return "critical"
    if "major" in severities:
        return "major"
    if "minor" in severities:
        return "minor"
    if "info" in severities:
        return "info"
    return "none"


def _status_from_issues(issues: list[dict], success: bool) -> str:
    bucket = _issue_bucket(issues)
    if bucket == "critical":
        return "fail"
    if bucket == "major":
        return "need_review"
    return "pass" if success else "need_review"


def _audit_result_dict(result: AuditResult) -> dict[str, Any]:
    return {
        "file_path": result.file_path,
        "base_name": result.base_name,
        "audit_status": result.audit_status,
        "vision_qc_version": result.vision_qc_version,
        "issues": result.issues,
        "duration_ms": result.duration_ms,
        "timestamp": result.timestamp,
    }
