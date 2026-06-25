"""v2.0 Task 7 / v2.1 Task 6: Drawing Review Workbench

三栏 UI 组件:
  左栏: Issue List
  中栏: PNG/PDF Preview + bbox overlay
  右栏: Evidence + Fix Suggestions

v3.0 改进:
  - Add-in / DocMgr / Vision QC 操作通过 JobRuntimeFacade/QProcess worker 执行
  - 新增 human_review.json 写入
  - 支持 pass_with_manual_review 状态
  - 操作结果实时刷新到 Issue List 和 Evidence 面板

支持操作:
  - 重新跑 Add-in Dimension (QProcess worker)
  - 重新跑 DocMgr Relink (QProcess worker)
  - 重新跑 Vision QC v3 (QProcess worker)
  - 标记人工确认 (写入 human_review.json)
  - 生成诊断包 (zip run_dir 下所有 JSON/PNG)
"""
from __future__ import annotations
import json
import time
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRectF, QPointF, Signal as QSignal
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.job_runtime_facade import get_job_runtime_facade


class DrawingReviewWorkbench(QWidget):
    """v2.0 Task 7 / v2.1 Task 6: 三栏 Drawing Review Workbench"""

    # 信号（保留，用于父组件追踪；v2.1 按钮已直接调用服务）
    request_addin_dimension = Signal(str, str)  # drawing_path, part_path
    request_docmgr_relink = Signal(str, str)    # drawing_path, part_path
    request_vision_qc_v3 = Signal(str)          # pdf_path
    request_manual_confirm = Signal(str, str)   # run_id, status
    # v2.1: 服务调用完成信号
    service_completed = QSignal(str, dict)      # (action_name, result)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._slddrw_path: str = ""
        self._sldprt_path: str = ""
        self._pdf_path: str = ""
        self._png_path: str = ""
        self._run_dir: str = ""
        self._run_id: str = ""
        self._pixmap: QPixmap | None = None
        self._issues_data: list = []
        self._filtered_issue_indices: list[int] = []
        self._bbox_overlays: list = []
        self._current_issue_index: int | None = None
        self._zoom_factor: float = 1.0
        self._layer_visibility: dict[str, bool] = {
            "ocr": True,
            "yolo": True,
            "template": True,
            "geometry": True,
        }
        self._job_facade = get_job_runtime_facade()
        self._active_action_job_id: str = ""
        self._active_action_name: str = ""
        self._human_review_path: Path | None = None

        self._build_ui()
        self._connect_job_runtime()

    def _build_ui(self) -> None:
        # === 顶部操作栏 ===
        self.btn_addin_dim = QPushButton("重新跑 Add-in Dimension")
        self.btn_docmgr_relink = QPushButton("重新跑 DocMgr Relink")
        self.btn_vision_qc_v3 = QPushButton("重新跑 Vision QC v3")
        self.btn_manual_confirm = QPushButton("标记人工确认")
        self.btn_confirm_issue = QPushButton("确认真实问题")
        self.btn_false_positive = QPushButton("标记误报")
        self.btn_diag_pack = QPushButton("生成诊断包")

        self.btn_addin_dim.clicked.connect(self._on_addin_dimension)
        self.btn_docmgr_relink.clicked.connect(self._on_docmgr_relink)
        self.btn_vision_qc_v3.clicked.connect(self._on_vision_qc_v3)
        self.btn_manual_confirm.clicked.connect(self._on_manual_confirm)
        self.btn_confirm_issue.clicked.connect(self._on_mark_confirmed_issue)
        self.btn_false_positive.clicked.connect(self._on_mark_false_positive)
        self.btn_diag_pack.clicked.connect(self._on_diag_pack)

        toolbar = QHBoxLayout()
        for btn in [self.btn_addin_dim, self.btn_docmgr_relink,
                    self.btn_vision_qc_v3, self.btn_manual_confirm,
                    self.btn_confirm_issue, self.btn_false_positive,
                    self.btn_diag_pack]:
            toolbar.addWidget(btn)
        toolbar.addStretch(1)

        # v2.1: 状态栏 + 进度条
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color:#666;padding:2px 4px;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)  # 默认不显示进度
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)

        status_bar = QHBoxLayout()
        status_bar.setContentsMargins(0, 0, 0, 0)
        status_bar.addWidget(self.status_label, 1)
        status_bar.addWidget(self.progress_bar, 2)

        # === 左栏: Issue List + Error Timeline ===
        self.filter_source = QComboBox()
        self.filter_source.addItem("全部 Source", "")
        self.filter_severity = QComboBox()
        self.filter_severity.addItems(["全部 Severity", "critical", "major", "minor", "info"])
        self.filter_review = QComboBox()
        self.filter_review.addItems([
            "全部 Review",
            "pending",
            "confirmed_issue",
            "confirmed_false_positive",
            "manual_confirmed",
        ])
        self.filter_source.currentIndexChanged.connect(lambda *_: self._refresh_issue_list())
        self.filter_severity.currentIndexChanged.connect(lambda *_: self._refresh_issue_list())
        self.filter_review.currentIndexChanged.connect(lambda *_: self._refresh_issue_list())

        self.issue_list = QListWidget()
        self.issue_list.itemClicked.connect(self._on_issue_clicked)

        # v2.2: 错误时间线
        self.timeline_list = QListWidget()
        self.timeline_list.setMaximumHeight(120)
        self.timeline_list.setStyleSheet("font-size: 11px; color: #555;")

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Issue List"))
        filter_row = QHBoxLayout()
        filter_row.addWidget(self.filter_source)
        filter_row.addWidget(self.filter_severity)
        filter_row.addWidget(self.filter_review)
        left_layout.addLayout(filter_row)
        left_layout.addWidget(self.issue_list, 1)
        left_layout.addWidget(QLabel("Error Timeline (v2.2)"))
        left_layout.addWidget(self.timeline_list)

        # === 中栏: PNG/PDF Preview + bbox overlay ===
        self.preview = QLabel("（无预览）")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background:#fafafa;border:1px solid #ddd;color:#999;")
        self.preview.setMinimumSize(500, 500)
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(False)
        self.preview_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_scroll.setWidget(self.preview)

        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_reset = QPushButton("100%")
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_out.clicked.connect(lambda: self.set_zoom(self._zoom_factor / 1.25))
        self.btn_zoom_reset.clicked.connect(lambda: self.set_zoom(1.0))
        self.btn_zoom_in.clicked.connect(lambda: self.set_zoom(self._zoom_factor * 1.25))
        self.layer_ocr = QCheckBox("OCR")
        self.layer_yolo = QCheckBox("YOLO")
        self.layer_template = QCheckBox("Template")
        self.layer_geometry = QCheckBox("Geometry")
        for cb in [self.layer_ocr, self.layer_yolo, self.layer_template, self.layer_geometry]:
            cb.setChecked(True)
            cb.toggled.connect(lambda *_: self._on_layer_toggled())

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(QLabel("Preview + BBox Overlay"))
        view_tools = QHBoxLayout()
        view_tools.addWidget(self.btn_zoom_out)
        view_tools.addWidget(self.btn_zoom_reset)
        view_tools.addWidget(self.btn_zoom_in)
        view_tools.addSpacing(12)
        for cb in [self.layer_ocr, self.layer_yolo, self.layer_template, self.layer_geometry]:
            view_tools.addWidget(cb)
        view_tools.addStretch(1)
        center_layout.addLayout(view_tools)
        center_layout.addWidget(self.preview_scroll, 1)

        # === 右栏: Evidence + Fix Suggestions ===
        self.evidence_text = QTextEdit()
        self.evidence_text.setReadOnly(True)
        self.evidence_text.setPlaceholderText("Evidence 和 Fix Suggestions 将显示在这里…")

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Evidence + Fix Suggestions"))
        right_layout.addWidget(self.evidence_text, 1)

        # === 三栏 Splitter ===
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([250, 700, 400])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(toolbar)
        layout.addWidget(splitter, 1)
        # v2.1: 底部状态栏
        layout.addLayout(status_bar)

    def set_context(
        self,
        slddrw_path: str = "",
        sldprt_path: str = "",
        pdf_path: str = "",
        png_path: str = "",
        run_dir: str = "",
        run_id: str = "",
    ) -> None:
        """设置当前上下文"""
        self._slddrw_path = slddrw_path
        self._sldprt_path = sldprt_path
        self._pdf_path = pdf_path
        self._png_path = png_path
        self._run_dir = run_dir
        self._run_id = run_id

        # 加载预览
        if png_path and Path(png_path).exists():
            self.set_preview_image(png_path)
        self._load_issue_tracker_decisions()

    def set_preview_image(self, png_path: str) -> None:
        """设置预览图"""
        if not png_path or not Path(png_path).exists():
            self.preview.setText("（无预览）")
            self._pixmap = None
            return
        pix = QPixmap(png_path)
        if pix.isNull():
            self.preview.setText("（预览加载失败）")
            return
        self._pixmap = pix
        self._zoom_factor = 1.0
        self.btn_zoom_reset.setText("100%")
        self._update_preview()

    def set_issues(self, issues: list) -> None:
        """设置 issue 列表

        Args:
            issues: [{key, severity, bbox, description, fix_suggestion, source}]
        """
        self._issues_data = issues or []
        self._current_issue_index = None
        self._load_issue_tracker_decisions()
        self._sync_source_filter_options()
        self._refresh_issue_list()
        self._update_preview()

    def _update_preview(self) -> None:
        """更新预览图（带 bbox overlay）"""
        if self._pixmap is None:
            return

        base = self._pixmap
        target_w = max(1, int(base.width() * self._zoom_factor))
        target_h = max(1, int(base.height() * self._zoom_factor))
        pix = base.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = pix.width()
        h = pix.height()

        self._bbox_overlays = self._visible_overlays()
        for overlay in self._bbox_overlays:
            bbox = overlay["bbox"]
            color = QColor(overlay["color"])
            # bbox 是归一化坐标 [x, y, w, h]
            x = int(bbox[0] * w)
            y = int(bbox[1] * h)
            bw = int(bbox[2] * w)
            bh = int(bbox[3] * h)

            pen = QPen(color, 5 if overlay.get("selected") else 3)
            painter.setPen(pen)
            painter.drawRect(x, y, bw, bh)

        painter.end()

        self.preview.setPixmap(pix)
        self.preview.resize(pix.size())

    def _on_issue_clicked(self, item: QListWidgetItem) -> None:
        """点击 issue 显示详情"""
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx < 0 or idx >= len(self._issues_data):
            return

        self._current_issue_index = int(idx)
        issue = self._issues_data[idx]
        evidence_parts = []
        evidence_parts.append(f"<h3>{issue.get('key', '')}</h3>")
        evidence_parts.append(f"<p><b>Severity:</b> {issue.get('severity', '')}</p>")
        evidence_parts.append(f"<p><b>Source:</b> {issue.get('source', 'unknown')}</p>")
        evidence_parts.append(f"<p><b>Human Review:</b> {issue.get('human_review', 'pending')}</p>")
        evidence_parts.append(f"<p><b>Confidence:</b> {issue.get('confidence', '')}</p>")
        evidence_parts.append(f"<p><b>Description:</b> {issue.get('description', '')}</p>")

        bbox = issue.get("bbox")
        if bbox:
            evidence_parts.append(f"<p><b>BBox:</b> [{', '.join(f'{v:.3f}' for v in bbox)}]</p>")

        fix = issue.get("fix_suggestion", "")
        if fix:
            evidence_parts.append(f"<p><b>Fix Suggestion:</b> {fix}</p>")

        auto_fix = issue.get("auto_fix_available")
        if auto_fix is not None:
            evidence_parts.append(f"<p><b>Auto Fix:</b> {'是' if auto_fix else '否'}</p>")
        evidence = issue.get("evidence")
        if evidence:
            evidence_parts.append("<p><b>Evidence:</b></p><pre>")
            evidence_parts.append(json.dumps(evidence, ensure_ascii=False, indent=2))
            evidence_parts.append("</pre>")

        self.evidence_text.setHtml("\n".join(evidence_parts))
        self._center_on_issue(issue)
        self._update_preview()

    def _sync_source_filter_options(self) -> None:
        current = self.filter_source.currentData() or ""
        sources = sorted({
            str(issue.get("source") or "unknown")
            for issue in self._issues_data
            if isinstance(issue, dict)
        })
        self.filter_source.blockSignals(True)
        self.filter_source.clear()
        self.filter_source.addItem("全部 Source", "")
        for source in sources:
            self.filter_source.addItem(source, source)
        idx = self.filter_source.findData(current)
        self.filter_source.setCurrentIndex(idx if idx >= 0 else 0)
        self.filter_source.blockSignals(False)

    def _refresh_issue_list(self) -> None:
        self.issue_list.clear()
        self._filtered_issue_indices = []
        severity_colors = {
            "critical": "#d32f2f",
            "major": "#f57c00",
            "minor": "#fbc02d",
            "info": "#1976d2",
        }
        for i, issue in enumerate(self._issues_data):
            if not self._issue_matches_filters(issue):
                continue
            severity = str(issue.get("severity") or "info")
            key = str(issue.get("key") or "")
            source = str(issue.get("source") or "unknown")
            review = str(issue.get("human_review") or "pending")
            desc = str(issue.get("description") or "")
            color = severity_colors.get(severity, "#666")
            item_text = f"[{severity.upper()}] {key}\n{source} · {review} · {desc[:80]}"
            item = QListWidgetItem(item_text)
            item.setForeground(QColor(color))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.issue_list.addItem(item)
            self._filtered_issue_indices.append(i)
        self._update_preview()

    def _issue_matches_filters(self, issue: dict) -> bool:
        source_filter = str(self.filter_source.currentData() or "")
        severity_filter = self.filter_severity.currentText()
        review_filter = self.filter_review.currentText()
        source = str(issue.get("source") or "unknown")
        severity = str(issue.get("severity") or "info")
        review = str(issue.get("human_review") or "pending")
        if source_filter and source != source_filter:
            return False
        if severity_filter != "全部 Severity" and severity != severity_filter:
            return False
        if review_filter != "全部 Review" and review != review_filter:
            return False
        return True

    def _on_layer_toggled(self) -> None:
        self._layer_visibility = {
            "ocr": self.layer_ocr.isChecked(),
            "yolo": self.layer_yolo.isChecked(),
            "template": self.layer_template.isChecked(),
            "geometry": self.layer_geometry.isChecked(),
        }
        self._update_preview()

    def _visible_overlays(self) -> list[dict]:
        severity_colors = {
            "critical": "#d32f2f",
            "major": "#f57c00",
            "minor": "#fbc02d",
            "info": "#1976d2",
        }
        overlays: list[dict] = []
        allowed_indices = set(self._filtered_issue_indices)
        for i, issue in enumerate(self._issues_data):
            if i not in allowed_indices:
                continue
            bbox = issue.get("bbox")
            if not bbox or len(bbox) < 4:
                continue
            if not self._source_layer_visible(str(issue.get("source") or "")):
                continue
            severity = str(issue.get("severity") or "info")
            overlays.append({
                "bbox": bbox,
                "color": severity_colors.get(severity, "#666"),
                "source": issue.get("source", ""),
                "selected": i == self._current_issue_index,
            })
        return overlays

    def _source_layer_visible(self, source: str) -> bool:
        low = source.lower()
        if any(key in low for key in ["ocr", "pdf_text"]):
            return self._layer_visibility.get("ocr", True)
        if any(key in low for key in ["yolo", "obb"]):
            return self._layer_visibility.get("yolo", True)
        if any(key in low for key in ["template", "symbol"]):
            return self._layer_visibility.get("template", True)
        if any(key in low for key in ["geometry", "layout", "qc"]):
            return self._layer_visibility.get("geometry", True)
        return True

    def set_zoom(self, factor: float) -> None:
        self._zoom_factor = max(0.2, min(6.0, float(factor)))
        self.btn_zoom_reset.setText(f"{int(self._zoom_factor * 100)}%")
        self._update_preview()

    def _center_on_issue(self, issue: dict) -> None:
        bbox = issue.get("bbox")
        if not bbox or len(bbox) < 4 or self.preview.pixmap() is None:
            return
        pix = self.preview.pixmap()
        center_x = int((bbox[0] + bbox[2] / 2) * pix.width())
        center_y = int((bbox[1] + bbox[3] / 2) * pix.height())
        hbar = self.preview_scroll.horizontalScrollBar()
        vbar = self.preview_scroll.verticalScrollBar()
        hbar.setValue(max(0, center_x - self.preview_scroll.viewport().width() // 2))
        vbar.setValue(max(0, center_y - self.preview_scroll.viewport().height() // 2))

    def _load_issue_tracker_decisions(self) -> None:
        if not self._run_dir or not self._issues_data:
            return
        try:
            from app.services.vision_issue_tracker import VisionIssueTracker

            tracker = VisionIssueTracker(Path(self._run_dir))
            tracker.load()
            base_name = self._base_name_for_tracker()
            self._issues_data = tracker.apply_decisions(self._issues_data, base_name)
        except Exception:
            pass

    def _base_name_for_tracker(self) -> str:
        for value in [self._png_path, self._pdf_path, self._slddrw_path, self._sldprt_path]:
            if value:
                return Path(value).stem
        return self._run_id or "unknown"

    def _selected_issue(self) -> tuple[int, dict] | tuple[None, None]:
        if self._current_issue_index is not None and 0 <= self._current_issue_index < len(self._issues_data):
            return self._current_issue_index, self._issues_data[self._current_issue_index]
        item = self.issue_list.currentItem()
        if item is None:
            return None, None
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx < 0 or idx >= len(self._issues_data):
            return None, None
        return int(idx), self._issues_data[int(idx)]

    def _on_mark_false_positive(self) -> None:
        self._write_issue_review("confirmed_false_positive")

    def _on_mark_confirmed_issue(self) -> None:
        self._write_issue_review("confirmed_issue")

    def _write_issue_review(self, decision: str) -> None:
        idx, issue = self._selected_issue()
        if idx is None or issue is None:
            QMessageBox.information(self, "Issue Review", "请先选中一个 issue。")
            return
        issue_key = str(issue.get("key") or f"issue_{idx}")
        base_name = self._base_name_for_tracker()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self._issues_data[idx]["human_review"] = decision
        self._issues_data[idx]["reviewed_at"] = timestamp

        if self._run_dir:
            try:
                from app.services.vision_issue_tracker import VisionIssueTracker

                tracker = VisionIssueTracker(Path(self._run_dir))
                tracker.load()
                if decision == "confirmed_false_positive":
                    tracker.mark_false_positive(issue_key, base_name, "marked in DrawingReviewWorkbench")
                else:
                    tracker.mark_confirmed(issue_key, base_name, "marked in DrawingReviewWorkbench")
                tracker.save()
            except Exception as exc:
                self.timeline_list.addItem(f"[{timestamp}] issue_tracker save FAIL - {exc}")
            self._append_human_review_event(issue_key, decision, timestamp)

        self._refresh_issue_list()
        self.status_label.setText(f"{issue_key}: {decision}")
        self.evidence_text.setHtml(
            f"<h3>Issue Review</h3>"
            f"<p><b>Issue:</b> {issue_key}</p>"
            f"<p><b>Decision:</b> {decision}</p>"
            f"<p><b>Timestamp:</b> {timestamp}</p>"
        )

    def _append_human_review_event(self, issue_key: str, decision: str, timestamp: str) -> None:
        if not self._run_dir:
            return
        qc_dir = Path(self._run_dir) / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)
        review_path = qc_dir / "human_review.json"
        entry = {
            "run_id": self._run_id,
            "status": "manual_confirmed",
            "issue_key": issue_key,
            "decision": decision,
            "timestamp": timestamp,
            "base_name": self._base_name_for_tracker(),
        }
        history: list = []
        if review_path.exists():
            try:
                old = json.loads(review_path.read_text(encoding="utf-8"))
                if isinstance(old, dict):
                    history = list(old.get("history") or [])
                    if old.get("issue_key") and old not in history:
                        history.insert(0, old)
            except Exception:
                history = []
        history.append(entry)
        payload = dict(entry)
        payload["history"] = history
        review_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._human_review_path = review_path
        self._update_manifest_with_human_review(review_path)

    # ============================================================
    # v2.1 Task 6: 5 个按钮真实调用服务
    # ============================================================

    def _set_busy(self, busy: bool, status_text: str = ""):
        """设置 UI 忙碌状态"""
        self.btn_addin_dim.setEnabled(not busy)
        self.btn_docmgr_relink.setEnabled(not busy)
        self.btn_vision_qc_v3.setEnabled(not busy)
        self.btn_manual_confirm.setEnabled(not busy)
        self.btn_confirm_issue.setEnabled(not busy)
        self.btn_false_positive.setEnabled(not busy)
        self.btn_diag_pack.setEnabled(not busy)
        if busy:
            self.progress_bar.setRange(0, 0)  # 不确定进度
            self.status_label.setText(status_text or "处理中…")
        else:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)
            self.status_label.setText(status_text or "就绪")

    def _connect_job_runtime(self) -> None:
        self._job_facade.job_progress.connect(self._on_review_job_progress)
        self._job_facade.job_finished.connect(self._on_review_job_finished)
        self._job_facade.job_failed.connect(self._on_review_job_failed)
        self._job_facade.event_logged.connect(self._on_review_job_event)

    def _start_review_action(self, action: str, action_name: str) -> None:
        """启动 Drawing Review QProcess worker 操作。"""
        if self._active_action_job_id:
            QMessageBox.warning(self, "忙碌", "上一个操作尚未完成，请稍候")
            return
        try:
            job_id = self._job_facade.start_drawing_review_action(
                action=action,
                slddrw_path=self._slddrw_path,
                sldprt_path=self._sldprt_path,
                pdf_path=self._pdf_path,
                png_path=self._png_path,
                run_dir=self._run_dir,
                run_id=self._run_id,
            )
        except Exception as exc:
            QMessageBox.warning(self, "图纸复核", f"启动失败: {exc}")
            return
        self._active_action_job_id = job_id
        self._active_action_name = action_name
        self._set_busy(True, f"正在执行: {action_name}…")
        self.timeline_list.addItem(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {action_name}: worker 作业 {job_id} 已启动")

    def _on_review_job_progress(self, job_id: str, data: dict) -> None:
        if job_id != self._active_action_job_id:
            return
        stage = str((data or {}).get("stage") or "")
        progress = (data or {}).get("progress")
        if progress is not None:
            self.status_label.setText(f"{self._active_action_name}: {stage} ({progress})")
        elif stage:
            self.status_label.setText(f"{self._active_action_name}: {stage}")

    def _on_review_job_event(self, job_id: str, event_type: str, data: dict) -> None:
        if job_id != self._active_action_job_id:
            return
        if event_type in {"warning", "recovered"}:
            msg = str((data or {}).get("reason") or (data or {}).get("error") or (data or {}).get("raw_line") or event_type)
            self.timeline_list.addItem(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {self._active_action_name}: {event_type} - {msg[:80]}")

    def _on_review_job_finished(self, job_id: str, data: dict) -> None:
        if job_id != self._active_action_job_id:
            return
        action_name = self._active_action_name or str((data or {}).get("action_name") or "图纸复核")
        result = (data or {}).get("result", data or {})
        if isinstance(result, dict):
            result.setdefault("success", True)
        else:
            result = {"success": False, "reason": f"worker 返回格式异常: {type(result).__name__}"}
        self._active_action_job_id = ""
        self._active_action_name = ""
        self._set_busy(False)
        self._handle_service_result(action_name, result)

    def _on_review_job_failed(self, job_id: str, data: dict) -> None:
        if job_id != self._active_action_job_id:
            return
        action_name = self._active_action_name or str((data or {}).get("action_name") or "图纸复核")
        result = dict(data or {})
        result.setdefault("success", False)
        result.setdefault("reason", result.get("error", "worker 失败"))
        result.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
        self._active_action_job_id = ""
        self._active_action_name = ""
        self._set_busy(False)
        self._handle_service_result(action_name, result)

    def _handle_service_result(self, action_name: str, result: dict):
        """处理服务调用结果"""
        # 发射信号给父组件
        self.service_completed.emit(action_name, result)

        success = bool(result.get("success", False))
        reason = result.get("reason", "")
        ts = result.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))

        # v2.2: 更新错误时间线
        timeline_entry = f"[{ts}] {action_name}: {'OK' if success else 'FAIL'} - {reason[:80]}"
        self.timeline_list.addItem(timeline_entry)
        # 保留最近 50 条
        while self.timeline_list.count() > 50:
            self.timeline_list.takeItem(0)
        self.timeline_list.scrollToBottom()

        # 更新 Evidence 面板
        html_parts = [
            f"<h3>{action_name} 结果</h3>",
            f"<p><b>Success:</b> {'是' if success else '否'}</p>",
            f"<p><b>Reason:</b> {reason}</p>",
            f"<p><b>Timestamp:</b> {ts}</p>",
        ]

        # 关键字段
        for key in ["display_dim_count", "addin_created_dim_count",
                    "existing_display_dim_count", "model_associative_dim_count",
                    "note_dim_count", "standard_annotation_count",
                    "replaced_count", "reference_count", "mode",
                    "overall_status", "strategy_log"]:
            if key in result:
                val = result[key]
                if isinstance(val, list):
                    html_parts.append(f"<p><b>{key}:</b> [{', '.join(str(v) for v in val[:5])}{'...' if len(val) > 5 else ''}]</p>")
                else:
                    html_parts.append(f"<p><b>{key}:</b> {val}</p>")

        # fallback_used
        if "fallback_used" in result:
            fu = result["fallback_used"]
            if fu:
                html_parts.append(f"<p><b>Fallback Used:</b> {', '.join(fu)}</p>")

        # issues
        issues = result.get("issues", [])
        if issues:
            html_parts.append(f"<p><b>Issues ({len(issues)}):</b></p><ul>")
            for iss in issues[:10]:
                html_parts.append(
                    f"<li>[{iss.get('severity', '')}] {iss.get('key', '')}: "
                    f"{iss.get('description', '')} (source={iss.get('source', '')})</li>"
                )
            html_parts.append("</ul>")

        self.evidence_text.setHtml("\n".join(html_parts))

        # 状态栏
        status_msg = f"{action_name}: {'✓' if success else '✗'} {reason[:60]}"
        self.status_label.setText(status_msg)

        # 如果是 Vision QC v3，刷新 Issue List
        if action_name == "Vision QC v3" and issues:
            self.set_issues(issues)

        # 如果是 Add-in Dimension，刷新 manifest 信息
        if action_name == "Add-in Dimension V3":
            self._refresh_issues_from_vision_qc()

    def _refresh_issues_from_vision_qc(self):
        """从 run_dir/qc/vision_qc_v3.json 重新加载 issues"""
        if not self._run_dir:
            return
        vqc_path = Path(self._run_dir) / "qc" / "vision_qc_v3.json"
        if not vqc_path.exists():
            return
        try:
            vqc_data = json.loads(vqc_path.read_text(encoding="utf-8"))
            issues = vqc_data.get("issues", [])
            if issues:
                self.set_issues(issues)
        except Exception:
            pass

    def _on_addin_dimension(self) -> None:
        """重新跑 Add-in Dimension V3 (QProcess worker)."""
        if not self._slddrw_path or not self._sldprt_path:
            QMessageBox.warning(self, "警告", "需要 SLDDRW 和 SLDPRT 路径")
            return
        self.request_addin_dimension.emit(self._slddrw_path, self._sldprt_path)
        self._start_review_action("addin_dimension", "Add-in Dimension V3")

    def _on_docmgr_relink(self) -> None:
        """重新跑 DocMgr Relink (QProcess worker)."""
        if not self._slddrw_path or not self._sldprt_path:
            QMessageBox.warning(self, "警告", "需要 SLDDRW 和 SLDPRT 路径")
            return
        self.request_docmgr_relink.emit(self._slddrw_path, self._sldprt_path)
        self._start_review_action("docmgr_relink", "DocMgr Relink")

    def _on_vision_qc_v3(self) -> None:
        """重新跑 Vision QC v3 (QProcess worker)."""
        if not self._pdf_path:
            QMessageBox.warning(self, "警告", "需要 PDF 路径")
            return
        self.request_vision_qc_v3.emit(self._pdf_path)
        self._start_review_action("vision_qc_v3", "Vision QC v3")

    def _on_manual_confirm(self) -> None:
        """标记人工确认 (写入 human_review.json)"""
        if not self._run_id:
            QMessageBox.warning(self, "警告", "需要 run_id")
            return
        self.request_manual_confirm.emit(self._run_id, "manual_confirmed")

        # v2.1: 写入 human_review.json
        review_data = {
            "run_id": self._run_id,
            "status": "manual_confirmed",
            "reviewer": "operator",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "slddrw_path": self._slddrw_path,
            "sldprt_path": self._sldprt_path,
            "pdf_path": self._pdf_path,
            "png_path": self._png_path,
            "notes": "",
            "decision": "pass_with_manual_review",
        }

        try:
            if self._run_dir:
                qc_dir = Path(self._run_dir) / "qc"
                qc_dir.mkdir(parents=True, exist_ok=True)
                review_path = qc_dir / "human_review.json"

                # 如果已存在，合并历史
                history = []
                if review_path.exists():
                    try:
                        old = json.loads(review_path.read_text(encoding="utf-8"))
                        if isinstance(old, dict) and "history" in old:
                            history = old.get("history", [])
                        elif isinstance(old, dict):
                            history = [old]
                    except Exception:
                        pass
                    history.append(review_data)

                review_data["history"] = history
                review_path.write_text(
                    json.dumps(review_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._human_review_path = review_path

                # 更新 manifest
                self._update_manifest_with_human_review(review_path)

                self.status_label.setText(
                    f"人工确认已写入: {review_path.name}"
                )
                self.evidence_text.setHtml(
                    f"<h3>人工确认已记录</h3>"
                    f"<p><b>Run ID:</b> {self._run_id}</p>"
                    f"<p><b>Status:</b> manual_confirmed</p>"
                    f"<p><b>Decision:</b> pass_with_manual_review</p>"
                    f"<p><b>Timestamp:</b> {review_data['timestamp']}</p>"
                    f"<p><b>File:</b> {review_path}</p>"
                )
            else:
                self.status_label.setText("无 run_dir，仅发射信号")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"写入 human_review.json 失败: {e}")

        QMessageBox.information(self, "已确认", f"Run {self._run_id} 已标记人工确认")

    def _update_manifest_with_human_review(self, review_path: Path):
        """更新 manifest.json 记录 human_review"""
        if not self._run_dir:
            return
        manifest_path = Path(self._run_dir) / "manifest.json"
        if not manifest_path.exists():
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            qc_files = manifest.setdefault("qc_files", {})
            qc_files["human_review"] = str(review_path)
            manifest["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            manifest["has_manual_review"] = True
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _load_dimension_policy(self) -> dict:
        """从 blueprint_decision.json 加载 dimension policy"""
        if not self._run_dir:
            return {}
        bp_path = Path(self._run_dir) / "qc" / "blueprint_decision.json"
        if not bp_path.exists():
            return {}
        try:
            bp = json.loads(bp_path.read_text(encoding="utf-8"))
            return {
                "dimension_policy": bp.get("dimension_policy", {}),
                "part_class": bp.get("part_class", ""),
                "required_dims": bp.get("dimension_policy", {}).get("required", []),
                "optional_dims": bp.get("dimension_policy", {}).get("optional", []),
            }
        except Exception:
            return {}

    def _on_diag_pack(self) -> None:
        """生成诊断包 (zip run_dir 下所有 JSON/PNG/log)"""
        if not self._run_dir:
            QMessageBox.warning(self, "警告", "需要 run_dir")
            return

        run_dir = Path(self._run_dir)
        if not run_dir.exists():
            QMessageBox.warning(self, "警告", f"run_dir 不存在: {run_dir}")
            return

        # 选择保存路径
        default_name = f"diag_pack_{self._run_id or 'unknown'}.zip"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存诊断包", default_name, "ZIP files (*.zip)"
        )
        if not save_path:
            return

        try:
            file_count = 0
            with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # 添加 run_dir 下所有 JSON 文件
                for json_file in run_dir.rglob("*.json"):
                    arcname = json_file.relative_to(run_dir)
                    zf.write(json_file, arcname)
                    file_count += 1

                # 添加 PNG 文件
                for png_file in run_dir.rglob("*.png"):
                    arcname = png_file.relative_to(run_dir)
                    zf.write(png_file, arcname)
                    file_count += 1

                # 添加 log 文件
                for log_file in run_dir.rglob("*.log"):
                    arcname = log_file.relative_to(run_dir)
                    zf.write(log_file, arcname)
                    file_count += 1

                # 添加 manifest.json
                manifest = run_dir / "manifest.json"
                if manifest.exists():
                    zf.write(manifest, "manifest.json")
                    file_count += 1

                # 添加 human_review.json（如果存在）
                if self._human_review_path and self._human_review_path.exists():
                    zf.write(self._human_review_path, "qc/human_review.json")
                    file_count += 1

                # 添加诊断元信息
                diag_info = {
                    "run_id": self._run_id,
                    "run_dir": str(run_dir),
                    "slddrw_path": self._slddrw_path,
                    "sldprt_path": self._sldprt_path,
                    "pdf_path": self._pdf_path,
                    "png_path": self._png_path,
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "file_count": file_count,
                    "version": "v2.1",
                }
                zf.writestr("diag_info.json", json.dumps(diag_info, ensure_ascii=False, indent=2))

            self.status_label.setText(f"诊断包已生成: {Path(save_path).name} ({file_count} 文件)")
            QMessageBox.information(
                self, "诊断包已生成",
                f"诊断包已保存到:\n{save_path}\n\n包含 {file_count} 个文件。"
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成诊断包失败: {e}")

    def resizeEvent(self, event) -> None:
        """窗口大小变化时重新渲染预览"""
        super().resizeEvent(event)
        if self._pixmap:
            self._update_preview()
