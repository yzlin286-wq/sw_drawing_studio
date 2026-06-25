from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class QcPage(QWidget):
    request_vision = Signal(str, str)
    request_tech_text = Signal()
    request_rerun = Signal(str)
    request_render_png = Signal(str, str)
    request_rerun_vqc2 = Signal(str, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._slddrw_path: str = ""
        self._qc_json_path: str = ""
        self._pixmap: QPixmap | None = None
        self._last_vision: dict | None = None
        self._vision_min_score: int = 80

        self.btn_select = QPushButton("选择 SLDDRW")
        self.btn_vision = QPushButton("AI 视觉质检")
        self.btn_tech = QPushButton("AI 生成技术要求")
        self.btn_rerun_vqc2 = QPushButton("重新跑视觉 QC v2")

        self.btn_select.clicked.connect(self._on_select)
        self.btn_vision.clicked.connect(self._on_vision)
        self.btn_tech.clicked.connect(self._on_tech)
        self.btn_rerun_vqc2.clicked.connect(self._on_rerun_vqc2)

        bar = QHBoxLayout()
        bar.addWidget(self.btn_select)
        bar.addWidget(self.btn_vision)
        bar.addWidget(self.btn_tech)
        bar.addWidget(self.btn_rerun_vqc2)
        bar.addStretch(1)

        self._status_strip = QHBoxLayout()
        self._lbl_gen = QLabel("出图: -")
        self._lbl_qc = QLabel("质量: -")
        self._lbl_vision = QLabel("视觉: -")
        self._lbl_usable = QLabel("可交付: -")
        self._lbl_warn = QLabel("警告: 0")
        for lbl in [self._lbl_gen, self._lbl_qc, self._lbl_vision, self._lbl_usable, self._lbl_warn]:
            lbl.setStyleSheet("padding:4px 10px; border:1px solid #ccc; border-radius:4px;")
            self._status_strip.addWidget(lbl)
        self._status_strip.addStretch()

        self.preview = QLabel("（无预览）")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background:#fafafa;border:1px solid #ddd;color:#999;")
        self.preview.setMinimumSize(400, 400)

        self.report = QTextEdit()
        self.report.setReadOnly(True)
        self.report.setPlaceholderText("视觉质检结果与 QC 摘要将显示在这里…")

        # v1.8 Task 6: issue 列表
        self.issue_list = QListWidget()
        self.issue_list.setMaximumWidth(300)
        self.issue_list.itemClicked.connect(self._on_issue_clicked)
        self._issues_data: list = []

        # 右侧：report + issue_list
        right_panel = QSplitter(Qt.Orientation.Vertical)
        right_panel.addWidget(self.report)
        right_panel.addWidget(self.issue_list)
        right_panel.setSizes([300, 200])

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.preview)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([700, 400])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(bar)
        layout.addLayout(self._status_strip)
        layout.addWidget(splitter, 1)

    def update_status_strip(self, summary: dict) -> None:
        """summary: {gen: bool, qc_pass: int, vision: int, usable: bool, warn_count: int}"""
        self._lbl_gen.setText(f"出图: {'✓' if summary.get('gen') else '✗'}")
        self._lbl_qc.setText(f"质量: {summary.get('qc_pass', 0)}/12")
        self._lbl_vision.setText(f"视觉: {summary.get('vision', 0)}/100")
        self._lbl_usable.setText(f"可交付: {'✓' if summary.get('usable') else '✗'}")
        wc = int(summary.get('warn_count', 0) or 0)
        self._lbl_warn.setText(f"警告: {wc}")
        if wc > 0:
            self._lbl_warn.setStyleSheet(
                "padding:4px 10px; background:#ffe5b3; color:#e07b00; border:1px solid #e07b00; border-radius:4px;"
            )
        else:
            self._lbl_warn.setStyleSheet(
                "padding:4px 10px; background:#e7f8e7; color:#2a6f2a; border:1px solid #6abe6a; border-radius:4px;"
            )

    def set_vision_min_score(self, score: int) -> None:
        try:
            self._vision_min_score = int(score)
        except Exception:
            self._vision_min_score = 80

    def slddrw_path(self) -> str:
        return self._slddrw_path

    def qc_json_path(self) -> str:
        return self._qc_json_path

    def set_slddrw(self, slddrw_path: str, qc_json_path: str = "") -> None:
        self._slddrw_path = slddrw_path or ""
        if not qc_json_path and self._slddrw_path:
            cand = Path(self._slddrw_path).with_name(Path(self._slddrw_path).stem + "_qc.json")
            qc_json_path = str(cand) if cand.exists() else ""
        self._qc_json_path = qc_json_path or ""
        self._auto_load_preview()

    def _auto_load_preview(self) -> None:
        if not self._slddrw_path:
            return
        path = Path(self._slddrw_path)
        png_candidates = [
            path.with_name(path.stem + "_vision.png"),
            path.with_suffix(".PNG"),
            path.with_suffix(".png"),
        ]
        for c in png_candidates:
            if c.exists():
                self.set_preview_image(str(c))
                return
        target = path.with_name(path.stem + "_vision.png")
        self.preview.setText(f"已选择: {path.name}\n（正在生成 PNG 预览…）")
        self.request_render_png.emit(str(path), str(target))

    def set_preview_image(self, png_path: str) -> None:
        if not png_path or not Path(png_path).exists():
            self.preview.setText("（无预览）")
            self._pixmap = None
            return
        pix = QPixmap(png_path)
        if pix.isNull():
            self.preview.setText("（图片加载失败）")
            self._pixmap = None
            return
        self._pixmap = pix
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._pixmap is None:
            return
        # v1.8 Task 6: 在 pixmap 上绘制 issue bbox 高亮
        pix = self._pixmap.copy()
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制选中的 issue bbox
        if self._issues_data:
            for i, issue in enumerate(self._issues_data):
                bbox = issue.get("bbox")
                if not bbox or len(bbox) < 4:
                    continue
                x, y, w, h = bbox
                # 归一化坐标转像素
                px = int(x * pix.width())
                py = int(y * pix.height())
                pw = int(w * pix.width())
                ph = int(h * pix.height())

                severity = issue.get("severity", "info")
                color_map = {
                    "critical": QColor(220, 30, 30, 200),
                    "major": QColor(230, 120, 30, 200),
                    "minor": QColor(230, 180, 30, 200),
                    "info": QColor(80, 150, 220, 200),
                }
                color = color_map.get(severity, QColor(100, 100, 100, 150))
                pen = QPen(color, 3)
                painter.setPen(pen)
                painter.drawRect(QRectF(px, py, pw, ph))

                # 标注 issue 编号
                font = QFont()
                font.setBold(True)
                font.setPointSize(10)
                painter.setFont(font)
                painter.drawText(QPointF(px + 4, py + 16), f"#{i+1}")

        painter.end()

        scaled = pix.scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_pixmap()

    # v1.8 Task 6: issue 列表交互
    def set_vision_qc_v2(self, vqc2_data: dict) -> None:
        """设置 vision_qc_v2 结果，更新 issue 列表"""
        self._issues_data = vqc2_data.get("issues", [])
        self.issue_list.clear()
        for i, issue in enumerate(self._issues_data):
            key = issue.get("key", "?")
            severity = issue.get("severity", "info")
            desc = issue.get("description", "")
            item_text = f"#{i+1} [{severity}] {key}: {desc[:40]}"
            item = QListWidgetItem(item_text)
            # 颜色标记
            color_map = {
                "critical": "#dc1e1e",
                "major": "#e6781e",
                "minor": "#e6b41e",
                "info": "#5096dc",
            }
            color = color_map.get(severity, "#666")
            item.setForeground(QColor(color))
            self.issue_list.addItem(item)
        self._refresh_pixmap()

    def _on_issue_clicked(self, item: "QListWidgetItem") -> None:
        """点击 issue 显示详情"""
        idx = self.issue_list.row(item)
        if 0 <= idx < len(self._issues_data):
            issue = self._issues_data[idx]
            detail = (
                f"<b>Issue #{idx+1}</b><br>"
                f"<b>Key:</b> {issue.get('key','')}<br>"
                f"<b>Severity:</b> {issue.get('severity','')}<br>"
                f"<b>Description:</b> {issue.get('description','')}<br>"
                f"<b>BBox:</b> {issue.get('bbox','')}<br>"
                f"<b>Fix Suggestion:</b> {issue.get('fix_suggestion','')}<br>"
                f"<b>Auto Fix:</b> {issue.get('auto_fix_available','')}"
            )
            self.report.setHtml(detail)
            self._refresh_pixmap()

    def _on_rerun_vqc2(self) -> None:
        """重新跑视觉 QC v2"""
        if not self._qc_json_path:
            self.report.setPlainText("请先选择 SLDDRW 或 qc.json")
            return
        qc_path = Path(self._qc_json_path)
        png_path = ""
        for c in [
            qc_path.with_name(qc_path.stem.replace("_qc", "") + ".PNG"),
            qc_path.with_name(qc_path.stem.replace("_qc", "") + ".png"),
            qc_path.parent / "drawing" / "preview.PNG",
            qc_path.parent.parent / "drawing" / f"{qc_path.stem.replace('_qc', '')}.PNG",
            qc_path.parent.parent / "drawing" / f"{qc_path.stem.replace('_qc', '')}.png",
        ]:
            if c.exists():
                png_path = str(c)
                break
        run_dir = str(qc_path.parent.parent)
        self.report.setPlainText("视觉 QC v2 已提交到 worker，等待结果…")
        self.request_rerun_vqc2.emit(str(qc_path), png_path, run_dir)

    def set_report(self, text: str) -> None:
        self.report.setPlainText(text or "")

    def append_report(self, text: str) -> None:
        if not text:
            return
        cur = self.report.toPlainText()
        if cur:
            self.report.setPlainText(cur + "\n" + text)
        else:
            self.report.setPlainText(text)

    def set_vision_result(self, result: dict | None) -> None:
        if not isinstance(result, dict):
            self.set_report("（视觉质检无结果）")
            self._last_vision = None
            return
        self._last_vision = result
        score = result.get("score", 0)
        summary = result.get("summary", "")
        issues = result.get("issues") or []
        png = result.get("png") or ""
        err = result.get("error") or ""

        lines: list[str] = []
        lines.append(f"视觉评分: {score}")
        lines.append(f"概述: {summary}")
        if err:
            lines.append(f"错误/警告: {err}")
        lines.append("")
        lines.append(f"问题清单 ({len(issues)} 条):")
        for i, it in enumerate(issues, 1):
            if isinstance(it, dict):
                key = it.get("key", "")
                desc = it.get("desc", "")
                fix = it.get("fix", "")
                lines.append(f"  {i}. [{key}] {desc}")
                if fix:
                    lines.append(f"     -> 修复: {fix}")
            else:
                lines.append(f"  {i}. {it}")

        self.set_report("\n".join(lines))

        if png and Path(png).exists():
            self.set_preview_image(png)

        try:
            score_int = int(score)
        except Exception:
            score_int = 0

        if score_int < self._vision_min_score and self._slddrw_path:
            try:
                drw = Path(self._slddrw_path)
                fix_path = drw.with_name("issues_to_fix.json")
                payload = {
                    "slddrw": str(drw),
                    "score": score_int,
                    "min_score": self._vision_min_score,
                    "issues": issues,
                    "summary": summary,
                }
                with fix_path.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                self.append_report(f"\n已写出 issues_to_fix.json: {fix_path}")
                self.append_report(
                    f"评分 {score_int} < 阈值 {self._vision_min_score}，已请求重出图。"
                )
                self.request_rerun.emit(self._slddrw_path)
            except Exception as exc:
                self.append_report(f"\n写 issues_to_fix.json 失败: {exc}")

    def set_tech_text(self, items: list[str] | str | None) -> None:
        if items is None:
            return
        if isinstance(items, str):
            text = items
        else:
            try:
                lines = []
                for i, t in enumerate(items, 1):
                    lines.append(f"{i}. {t}")
                text = "技术要求:\n" + "\n".join(lines)
            except Exception:
                text = str(items)
        self.append_report("\n" + text)

    def _on_select(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 SLDDRW 文件",
            "",
            "SolidWorks Drawing (*.SLDDRW *.slddrw);;All Files (*)",
        )
        if not path:
            return
        self.set_slddrw(path)
        info = [f"SLDDRW: {self._slddrw_path}"]
        info.append(f"QC JSON: {self._qc_json_path or '(未找到)'}")
        self.set_report("\n".join(info))

    def _on_vision(self) -> None:
        print(f"[qc] 视觉质检请求: {self._slddrw_path}")
        self.request_vision.emit(self._slddrw_path, self._qc_json_path)

    def _on_tech(self) -> None:
        print("[qc] 生成技术要求请求")
        self.request_tech_text.emit()
