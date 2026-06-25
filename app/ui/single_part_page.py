"""单件制图页（Spec enhance-v1-1 Task 7.2）

功能：
- 选择 SLDPRT
- 选择出图策略 (v6 推荐 / v5 兼容 / v6 调试)
- 调 run_manager.full_pipeline()，串联：出图 → QC → vision → BOM → 工艺 → 报价 → manifest
- 进度条 + 当前步骤显示
- 完成后「打开交付包」按钮打开 drw_output/runs/<run_id>/
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class SinglePartPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_run_dir: Path | None = None
        self._active_job_id: str = ""
        self._job_part_path: str = ""
        from app.services.job_runtime_facade import get_job_runtime_facade

        self.facade = get_job_runtime_facade()
        self.facade.job_started.connect(self._on_job_started)
        self.facade.job_progress.connect(self._on_job_progress)
        self.facade.job_finished.connect(self._on_job_finished)
        self.facade.job_failed.connect(self._on_job_failed)
        self.facade.event_logged.connect(self._on_job_event)

        title = QLabel("单件制图")
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        title.setFont(f)

        subtitle = QLabel(
            "选择一个 SLDPRT，自动完成：出图 → QC → 视觉评分 → BOM → 工艺 → 报价，\n"
            "作业通过独立 QProcess 运行，全部产物归集到 drw_output/runs/<run_id>/"
        )
        subtitle.setStyleSheet("color: #666;")

        # 1) 文件选择
        file_row = QHBoxLayout()
        self.le_path = QLineEdit()
        self.le_path.setPlaceholderText("选择一个 SLDPRT 文件…")
        self.btn_browse = QPushButton("浏览…")
        self.btn_browse.clicked.connect(self._on_browse)
        file_row.addWidget(QLabel("零件文件:"))
        file_row.addWidget(self.le_path, 1)
        file_row.addWidget(self.btn_browse)

        # 2) 策略
        strat_row = QHBoxLayout()
        self.cb_strategy = QComboBox()
        self.cb_strategy.addItem("v6 推荐 (v6_recommended)", "v6_recommended")
        self.cb_strategy.addItem("v5 兼容 (v5_compat)", "v5_compat")
        self.cb_strategy.addItem("v6 调试 (v6_debug)", "v6_debug")
        strat_row.addWidget(QLabel("出图策略:"))
        strat_row.addWidget(self.cb_strategy)
        strat_row.addStretch(1)

        # 3) 运行 / 打开
        run_row = QHBoxLayout()
        self.btn_run = QPushButton("开始单件制图")
        self.btn_run.setMinimumHeight(36)
        self.btn_run.clicked.connect(self._on_run)
        self.btn_open_pkg = QPushButton("打开交付包")
        self.btn_open_pkg.setEnabled(False)
        self.btn_open_pkg.clicked.connect(self._on_open_pkg)
        run_row.addWidget(self.btn_run)
        run_row.addWidget(self.btn_open_pkg)
        run_row.addStretch(1)

        # 4) 进度
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)

        self.lbl_step = QLabel("等待开始…")
        self.lbl_step.setStyleSheet("color: #555;")

        # 5) 状态条 5 项
        self._status_strip = QHBoxLayout()
        self._lbl_gen = QLabel("出图: -")
        self._lbl_qc = QLabel("QC: -")
        self._lbl_vision = QLabel("视觉: -")
        self._lbl_usable = QLabel("可交付: -")
        self._lbl_warn = QLabel("警告: -")
        for lbl in [self._lbl_gen, self._lbl_qc, self._lbl_vision, self._lbl_usable, self._lbl_warn]:
            lbl.setStyleSheet("padding:4px 10px; border:1px solid #ccc; border-radius:4px;")
            self._status_strip.addWidget(lbl)
        self._status_strip.addStretch(1)

        # 6) 报告区
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setPlaceholderText("运行结束后此处会显示 run_id、产物路径与摘要…")
        self.report.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(4)
        layout.addLayout(file_row)
        layout.addLayout(strat_row)
        layout.addLayout(run_row)
        layout.addWidget(self.progress)
        layout.addWidget(self.lbl_step)
        layout.addLayout(self._status_strip)
        layout.addWidget(self.report, 1)

    # ---------- 事件 ----------
    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 SLDPRT",
            "",
            "SolidWorks Part (*.SLDPRT *.sldprt);;All Files (*)",
        )
        if path:
            self.le_path.setText(path)

    def _on_run(self) -> None:
        path = self.le_path.text().strip()
        if not path or not Path(path).exists():
            self.report.setPlainText(f"[ERR] 输入文件不存在: {path}")
            return
        strategy = self.cb_strategy.currentData() or "v6_recommended"
        # 设置 USE_V5 环境变量 (供旧链路兼容)
        if strategy == "v5_compat":
            os.environ["USE_V5"] = "1"
        else:
            os.environ.pop("USE_V5", None)

        titlebar_overrides = self._collect_titlebar_overrides(path)

        self.btn_run.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.btn_open_pkg.setEnabled(False)
        self.progress.setVisible(True)
        self.lbl_step.setText("启动 pipeline…")
        self.report.setPlainText("")
        self._reset_status_strip()

        try:
            self._job_part_path = path
            self._active_job_id = self.facade.start_cad_job(
                part_path=path,
                output_dir="",
                max_rounds=3,
                timeout_s=900,
                titlebar_overrides=titlebar_overrides,
                strategy=strategy,
            )
            self.lbl_step.setText(f"已提交作业: {self._active_job_id}")
            self.report.setPlainText(f"job_id: {self._active_job_id}\npart: {path}\nstrategy: {strategy}")
        except Exception as exc:
            self.btn_run.setEnabled(True)
            self.btn_browse.setEnabled(True)
            self.progress.setVisible(False)
            self.lbl_step.setText("提交失败")
            self.report.setPlainText(f"[ERROR]\n{type(exc).__name__}: {exc}")

    def _on_started(self, part_path: str) -> None:
        self.lbl_step.setText(f"已启动: {Path(part_path).name}")

    def _on_step(self, msg: str) -> None:
        self.lbl_step.setText(msg)

    def _collect_titlebar_overrides(self, path: str) -> dict:
        from app.ui.titlebar_dialog import TitleBarDialog

        dlg = TitleBarDialog(path, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.get_overrides()
        return {}

    def _on_job_started(self, job_id: str, data: dict) -> None:
        if job_id != self._active_job_id:
            return
        self._on_started(str(data.get("part_path") or self._job_part_path))

    def _on_job_progress(self, job_id: str, data: dict) -> None:
        if job_id != self._active_job_id:
            return
        progress = data.get("progress", 0)
        try:
            self.progress.setValue(max(0, min(100, int(float(progress) * 100))))
        except Exception:
            pass
        stage = str(data.get("stage") or "")
        if stage:
            self._on_step(stage)

    def _on_job_finished(self, job_id: str, data: dict) -> None:
        if job_id != self._active_job_id:
            return
        result = (data or {}).get("result", data or {})
        if not isinstance(result, dict):
            result = {}
        self._active_job_id = ""
        self._on_finished(result, None)

    def _on_job_failed(self, job_id: str, data: dict) -> None:
        if job_id != self._active_job_id:
            return
        self._active_job_id = ""
        self._on_finished(None, str((data or {}).get("error") or data))

    def _on_job_event(self, job_id: str, event_type: str, data: dict) -> None:
        if job_id != self._active_job_id:
            return
        if event_type == "warning":
            line = str((data or {}).get("line") or (data or {}).get("raw_line") or "")
            if line:
                current = self.report.toPlainText()
                self.report.setPlainText((current + "\n" + line)[-12000:])

    def _on_finished(self, data, err) -> None:
        self.btn_run.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.progress.setVisible(False)
        self.progress.setValue(0)

        if err is not None:
            self.lbl_step.setText("失败")
            self.report.setPlainText(f"[ERROR]\n{err}")
            return

        if not isinstance(data, dict):
            self.report.setPlainText("[WARN] pipeline 无返回值")
            return

        run_dir = Path(data.get("run_dir", ""))
        self._current_run_dir = run_dir if run_dir.exists() else None
        self.btn_open_pkg.setEnabled(self._current_run_dir is not None)

        usable = (data.get("drawing_usable") or {}).get("pass", False)
        hard_fail = data.get("hard_fail") or []
        warns = data.get("warnings") or []
        qc_pass = data.get("qc_pass_count", 0)
        vs = data.get("vision_score")
        gen_ok = bool(data.get("output_files", {}).get("drawing"))

        self._lbl_gen.setText(f"出图: {'✓' if gen_ok else '✗'}")
        self._lbl_qc.setText(f"QC: {qc_pass}/12")
        self._lbl_vision.setText(f"视觉: {vs if vs is not None else '-'}/100")
        self._lbl_usable.setText(f"可交付: {'✓' if usable else '✗'}")
        self._lbl_warn.setText(f"警告: {len(warns)}")
        self._color_status(self._lbl_usable, usable)
        self._color_status(self._lbl_warn, len(warns) == 0)

        if not hard_fail and usable:
            verdict = "✓ 生成成功，可交付"
        elif not hard_fail and warns:
            verdict = "⚠ 生成成功，有警告"
        else:
            verdict = "✗ 生成失败"
        self.lbl_step.setText(verdict)

        lines = [
            f"=== {verdict} ===",
            f"run_id      : {data.get('run_id')}",
            f"run_dir     : {run_dir}",
            f"qc_pass     : {qc_pass}/12",
            f"vision      : {vs}/100",
            f"hard_fail   : {hard_fail}",
            f"warnings    : {warns}",
            f"fallback    : {data.get('fallback_used')}",
            f"bom_status  : {data.get('bom_status')}",
            f"process     : {data.get('process_status')}",
            f"quote       : {data.get('quote_status')}",
            "",
            "[output_files]",
        ]
        for cat, files in (data.get("output_files") or {}).items():
            lines.append(f"  {cat}:")
            for f in files:
                lines.append(f"    - {f}")
        if data.get("exception_summary"):
            lines.append("")
            lines.append("[exceptions]")
            for e in data["exception_summary"]:
                lines.append(f"  - {e}")
        self.report.setPlainText("\n".join(lines))

    def _on_open_pkg(self) -> None:
        if not self._current_run_dir:
            return
        try:
            os.startfile(str(self._current_run_dir))
        except Exception:
            try:
                subprocess.Popen(["explorer", str(self._current_run_dir)])
            except Exception:
                pass

    # ---------- 工具 ----------
    def _reset_status_strip(self) -> None:
        self._lbl_gen.setText("出图: -")
        self._lbl_qc.setText("QC: -")
        self._lbl_vision.setText("视觉: -")
        self._lbl_usable.setText("可交付: -")
        self._lbl_warn.setText("警告: -")
        for lbl in [self._lbl_gen, self._lbl_qc, self._lbl_vision, self._lbl_usable, self._lbl_warn]:
            lbl.setStyleSheet("padding:4px 10px; border:1px solid #ccc; border-radius:4px;")

    @staticmethod
    def _color_status(lbl: QLabel, ok: bool) -> None:
        if ok:
            lbl.setStyleSheet(
                "padding:4px 10px; background:#e7f8e7; color:#2a6f2a; border:1px solid #6abe6a; border-radius:4px;"
            )
        else:
            lbl.setStyleSheet(
                "padding:4px 10px; background:#ffe5b3; color:#e07b00; border:1px solid #e07b00; border-radius:4px;"
            )
