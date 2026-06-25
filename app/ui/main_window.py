from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.config.defaults import get_app_config, get_llm_config
from app.services.job_runtime_facade import get_job_runtime_facade
from app.services.llm_client import build_default_client
from app.ui.batch_page import BatchPage
from app.ui.bom_pricing_page import BomPricingPage
from app.ui.drawing_review_workbench import DrawingReviewWorkbench
from app.ui.home_page import HomePage
from app.ui.job_queue_page import JobQueuePage
from app.ui.log_panel import LogPanel
from app.ui.logs_diagnostics_page import LogsDiagnosticsPage
from app.ui.qc_page import QcPage
from app.ui.settings_dialog import SettingsDialog
from app.ui.single_part_page import SinglePartPage
from app.ui.system_health_page import SystemHealthPage
from app.ui.visual_audit_page import VisualAuditPage


NAV_ITEMS = [
    "仪表盘",
    "单件制图",
    "作业队列",
    "视觉审计",
    "图纸复核",
    "批量验证",
    "系统健康",
    "日志诊断",
    "设置",
]
PAGE_HOME = 0
PAGE_SINGLE = 1
PAGE_JOBS = 2
PAGE_VISUAL_AUDIT = 3
PAGE_DRAWING_REVIEW = 4
PAGE_BATCH = 5
PAGE_HEALTH = 6
PAGE_LOG = 7
PAGE_SETTINGS = 8
PAGE_LEGACY_QC = 9
PAGE_LEGACY_BOM = 10

# Compatibility aliases for older toolbar/test code. These pages are no longer
# part of the v3 acceptance navigation, but they remain reachable.
PAGE_QC = PAGE_LEGACY_QC
PAGE_BOM = PAGE_LEGACY_BOM


GB_TECH_BRIEF = (
    "GB 制图规范摘要（用于生成技术要求时参考）：\n"
    "1) 一般公差 GB/T 1804-m: 未注线性尺寸 ±0.1~±0.5；\n"
    "2) 尺寸标注 GB/T 4458.4: 尺寸线 0.25mm，箭头清晰，同向尺寸优先共线；\n"
    "3) 表面粗糙度 GB/T 131-2006: 默认 Ra 标注于轮廓线，统一时在标题栏右上角；\n"
    "4) 形位公差 GB/T 1182-2008: 公差框格 + 基准三角；\n"
    "5) 视图 GB/T 17452 / 4458.4: 第一角投影，主视图 + 必要剖视；\n"
    "6) 字体 GB/T 14691: 长仿宋体 3.5/5/7/10mm。\n"
)


class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel("设置")
        font = self.title.font()
        font.setPointSize(16)
        font.setBold(True)
        self.title.setFont(font)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.lbl_provider = QLabel("-")
        self.lbl_model = QLabel("-")
        self.lbl_vision_model = QLabel("-")
        self.lbl_api = QLabel("-")
        self.lbl_output = QLabel("-")
        self.lbl_solidworks = QLabel("-")

        self.btn_refresh = QPushButton("刷新")
        self.btn_test = QPushButton("测试连接")
        self.btn_open_dialog = QPushButton("打开完整设置")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_test.clicked.connect(self.test_connection)

        form = QFormLayout()
        form.addRow("供应商", self.lbl_provider)
        form.addRow("模型", self.lbl_model)
        form.addRow("视觉模型", self.lbl_vision_model)
        form.addRow("API Key", self.lbl_api)
        form.addRow("输出目录", self.lbl_output)
        form.addRow("SolidWorks", self.lbl_solidworks)

        actions = QHBoxLayout()
        actions.addWidget(self.btn_refresh)
        actions.addWidget(self.btn_test)
        actions.addWidget(self.btn_open_dialog)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(self.title)
        layout.addWidget(self.status)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        app_cfg = get_app_config() or {}
        llm_cfg = get_llm_config() or {}
        provider = str(llm_cfg.get("active_provider") or "")
        providers = llm_cfg.get("providers") or {}
        provider_cfg = providers.get(provider) if isinstance(providers, dict) else {}
        if not isinstance(provider_cfg, dict):
            provider_cfg = {}
        api_key = str(provider_cfg.get("api_key") or "")
        model = str(provider_cfg.get("model") or "")
        vision_model = str(provider_cfg.get("vision_model") or "")
        sw_path = str(app_cfg.get("solidworks_path") or "")

        self.lbl_provider.setText(provider or "未配置")
        self.lbl_model.setText(model or "未配置")
        self.lbl_vision_model.setText(vision_model or "未配置")
        self.lbl_api.setText("已配置" if api_key else "缺失")
        self.lbl_output.setText(str(app_cfg.get("output_dir") or "drw_output"))
        self.lbl_solidworks.setText(sw_path or "未配置")
        if api_key and model:
            self.status.setStyleSheet("color:#2E7D32;")
            self.status.setText("设置已加载。可在本页或完整设置对话框中执行连接测试。")
        else:
            self.status.setStyleSheet("color:#E67E22;")
            self.status.setText("警告：API Key 或模型缺失，依赖网络的 AI 操作已禁用。")

    def test_connection(self) -> None:
        llm_cfg = get_llm_config() or {}
        provider = str(llm_cfg.get("active_provider") or "")
        providers = llm_cfg.get("providers") or {}
        provider_cfg = providers.get(provider) if isinstance(providers, dict) else {}
        if not isinstance(provider_cfg, dict):
            provider_cfg = {}
        if not provider_cfg.get("api_key") or not provider_cfg.get("model"):
            self.status.setStyleSheet("color:#E67E22;")
            self.status.setText("警告：因 API Key 或模型缺失，已跳过连接测试。")
            return
        self.status.setStyleSheet("color:#E67E22;")
        self.status.setText("警告：源码级 UI 验收不执行网络调用；请在 EXE 验收中运行完整连接测试。")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SW Drawing Studio")
        self.resize(1280, 800)

        self.job_facade = get_job_runtime_facade()
        self._active_batch_job_id = ""
        self._active_batch_items: list[str] = []
        self._qc_action_jobs: dict[str, dict[str, str]] = {}
        self._diagnostics_jobs: dict[str, dict[str, str]] = {}
        self._cad_rerun_jobs: dict[str, dict[str, str]] = {}
        self._llm_action_jobs: dict[str, dict[str, str]] = {}

        self.llm = None
        self._llm_err = ""
        try:
            client = build_default_client()
            if not getattr(client, "model", ""):
                raise RuntimeError("LLM model 未配置")
            self.llm = client
        except Exception as exc:
            self._llm_err = f"{type(exc).__name__}: {exc}"

        self.app_cfg: dict[str, Any] = {}
        try:
            self.app_cfg = get_app_config() or {}
        except Exception:
            self.app_cfg = {}
        try:
            self._vision_min_score = int(self.app_cfg.get("vision_min_score", 80))
        except Exception:
            self._vision_min_score = 80
        self._output_dir = str(self.app_cfg.get("output_dir") or
                               (Path(__file__).resolve().parent.parent.parent / "drw_output"))
        try:
            self._max_qc_rounds = int(self.app_cfg.get("max_qc_rounds", 3))
        except Exception:
            self._max_qc_rounds = 3

        self.log_panel = LogPanel(self)

        self.home_page = HomePage(self)
        self.single_page = SinglePartPage(self)
        self.batch_page = BatchPage(self)
        self.job_queue_page = JobQueuePage(self)
        self.system_health_page = SystemHealthPage(self)
        self.visual_audit_page = VisualAuditPage(self)
        self.drawing_review_page = DrawingReviewWorkbench(self)
        self.qc_page = QcPage(self)
        self.qc_page.set_vision_min_score(self._vision_min_score)
        self.bom_page = BomPricingPage(self)
        self.logs_diagnostics_page = LogsDiagnosticsPage(self)
        self.settings_page = SettingsPage(self)
        self.settings_page.btn_open_dialog.clicked.connect(self._open_settings)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.single_page)
        self.stack.addWidget(self.job_queue_page)
        self.stack.addWidget(self.visual_audit_page)
        self.stack.addWidget(self.drawing_review_page)
        self.stack.addWidget(self.batch_page)
        self.stack.addWidget(self.system_health_page)
        self.stack.addWidget(self.logs_diagnostics_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.qc_page)
        self.stack.addWidget(self.bom_page)

        self.nav = QListWidget(self)
        self.nav.setFixedWidth(180)
        for name in NAV_ITEMS:
            QListWidgetItem(name, self.nav)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav_changed)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.nav)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([180, 1100])
        self.setCentralWidget(splitter)

        self.log_dock = QDockWidget("日志", self)
        self.log_dock.setObjectName("logDock")
        self.log_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.log_dock.setWidget(self.log_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)

        self._build_menus()
        self._build_toolbar()

        if self.llm is None:
            self.statusBar().showMessage(f"模型未配置: {self._llm_err}")
            self.log_panel.append(f"模型未配置: {self._llm_err}", "WARN")
        else:
            self.statusBar().showMessage("就绪")

        self.home_page.request_goto_batch.connect(lambda: self._goto_page(PAGE_BATCH))
        self.home_page.request_goto_single.connect(lambda: self._goto_page(PAGE_SINGLE))
        self.batch_page.request_run.connect(self._on_request_run)
        self.batch_page.request_pre_analyze.connect(self._on_request_pre_analyze)
        self.batch_page.request_stop.connect(self._on_request_stop)
        self.batch_page.request_rerun_one.connect(self._on_request_rerun_one)
        self.qc_page.request_vision.connect(self._on_request_vision)
        self.qc_page.request_tech_text.connect(self._on_request_tech_text)
        self.qc_page.request_rerun.connect(self._on_request_rerun)
        self.qc_page.request_render_png.connect(self._on_request_render_png)
        self.qc_page.request_rerun_vqc2.connect(self._on_request_rerun_vqc2)
        self.log_panel.request_diagnostics.connect(self._on_request_latest_diagnostics)
        self.logs_diagnostics_page.request_build_diagnostics.connect(self._on_request_diagnostics_for_run)

        self.job_facade.job_progress.connect(self._on_batch_job_progress)
        self.job_facade.job_finished.connect(self._on_batch_job_finished)
        self.job_facade.job_failed.connect(self._on_batch_job_failed)
        self.job_facade.event_logged.connect(self._on_batch_job_event)
        self.job_facade.job_progress.connect(self._on_qc_action_progress)
        self.job_facade.job_finished.connect(self._on_qc_action_finished)
        self.job_facade.job_failed.connect(self._on_qc_action_failed)
        self.job_facade.job_progress.connect(self._on_diagnostics_action_progress)
        self.job_facade.job_finished.connect(self._on_diagnostics_action_finished)
        self.job_facade.job_failed.connect(self._on_diagnostics_action_failed)
        self.job_facade.job_progress.connect(self._on_cad_rerun_progress)
        self.job_facade.job_finished.connect(self._on_cad_rerun_finished)
        self.job_facade.job_failed.connect(self._on_cad_rerun_failed)
        self.job_facade.job_progress.connect(self._on_llm_action_progress)
        self.job_facade.job_finished.connect(self._on_llm_action_finished)
        self.job_facade.job_failed.connect(self._on_llm_action_failed)

        self._sc_stop = QShortcut(QKeySequence("Esc"), self)
        self._sc_stop.activated.connect(self._on_request_stop)
        self._sc_clear_log = QShortcut(QKeySequence("Ctrl+L"), self)
        self._sc_clear_log.activated.connect(self.log_panel.clear)

        self.log_panel.append("应用已启动", "INFO")

    def _build_menus(self) -> None:
        mb = self.menuBar()

        m_file = mb.addMenu("文件(&F)")
        act_settings = QAction("设置…", self)
        act_settings.triggered.connect(self._open_settings)
        m_file.addAction(act_settings)

        m_file.addSeparator()
        act_exit = QAction("退出(&X)", self)
        act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        m_view = mb.addMenu("视图(&V)")
        act_ai_qc = QAction("AI 质检（旧入口）", self)
        act_ai_qc.triggered.connect(lambda: self._goto_page(PAGE_QC))
        m_view.addAction(act_ai_qc)
        act_bom = QAction("BOM 与核价（旧入口）", self)
        act_bom.triggered.connect(lambda: self._goto_page(PAGE_BOM))
        m_view.addAction(act_bom)

        m_help = mb.addMenu("帮助(&H)")
        act_rules = QAction("打开 GB 制图规范…", self)
        act_rules.triggered.connect(self._open_gb_rules)
        m_help.addAction(act_rules)
        m_help.addSeparator()
        act_about = QAction("关于…", self)
        act_about.triggered.connect(self._show_about)
        m_help.addAction(act_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("主工具栏", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        self.act_pre_analyze = QAction("AI 预分析", self)
        self.act_run = QAction("开始出图", self)
        self.act_vision = QAction("AI 质检", self)

        self.act_pre_analyze.triggered.connect(self._tb_pre_analyze)
        self.act_run.triggered.connect(self._tb_run)
        self.act_vision.triggered.connect(self._tb_vision)

        tb.addAction(self.act_pre_analyze)
        tb.addAction(self.act_run)
        tb.addSeparator()
        tb.addAction(self.act_vision)

        tb.addSeparator()
        tb.addWidget(QLabel("出图策略:"))
        self._strategy_combo = QComboBox()
        self._strategy_combo.addItems(["v6 推荐", "v5 兼容", "v6 调试"])
        self._strategy_combo.setCurrentIndex(0)
        self._strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        tb.addWidget(self._strategy_combo)

    def _on_strategy_changed(self, idx: int) -> None:
        import os
        if idx == 1:
            os.environ["USE_V5"] = "1"
            print("[runner] strategy: v5 fallback (USE_V5=1)")
        else:
            os.environ.pop("USE_V5", None)
            print("[runner] strategy: v6 (USE_V5 cleared)")

    def _goto_page(self, idx: int) -> None:
        if 0 <= idx < self.stack.count():
            self.stack.setCurrentIndex(idx)
            self.nav.blockSignals(True)
            if idx < self.nav.count():
                self.nav.setCurrentRow(idx)
            else:
                self.nav.clearSelection()
            self.nav.blockSignals(False)

    def _on_nav_changed(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            self.log_panel.append("设置已保存", "INFO")
            try:
                self.app_cfg = get_app_config() or {}
                self._vision_min_score = int(self.app_cfg.get("vision_min_score", 80))
                self.qc_page.set_vision_min_score(self._vision_min_score)
                self._output_dir = str(self.app_cfg.get("output_dir") or self._output_dir)
                self._max_qc_rounds = int(self.app_cfg.get("max_qc_rounds", 3))
            except Exception as exc:
                self.log_panel.append(f"重新加载配置失败: {exc}", "WARN")
            try:
                self.llm = build_default_client()
                if not getattr(self.llm, "model", ""):
                    self.llm = None
                    self.statusBar().showMessage("模型未配置")
            except Exception as exc:
                self.llm = None
                self.statusBar().showMessage(f"模型未配置: {exc}")
            self.settings_page.refresh()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 SW Drawing Studio",
            "SW Drawing Studio\n\n"
            "3D 自动转 2D · GB 制图规范 · AI 视觉质检\n"
            "基于 PySide6 + qt-material",
        )

    def _open_gb_rules(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        rules_path = repo_root / ".trae" / "specs" / "enforce-drawing-quality" / "gb_drawing_rules.md"
        if not rules_path.exists():
            QMessageBox.warning(
                self,
                "GB 制图规范",
                f"未找到规范文档：\n{rules_path}",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(rules_path)))
        self.log_panel.append(f"已打开 GB 制图规范: {rules_path}", "INFO")

    def _on_request_stop(self) -> None:
        if not self.batch_page.btn_stop.isEnabled():
            return
        self.log_panel.append("用户取消（Esc / 停止按钮）", "WARN")
        self.statusBar().showMessage("正在停止…")
        if self._active_batch_job_id:
            try:
                cancelled = self.job_facade.cancel_job(self._active_batch_job_id)
                self.log_panel.append(f"已请求取消批量作业: {self._active_batch_job_id}", "WARN")
                if cancelled:
                    self.batch_page.set_running(False)
                    self.statusBar().showMessage("批量作业已取消")
                    self._active_batch_job_id = ""
                    self._active_batch_items = []
            except Exception as exc:
                self.log_panel.append(f"取消批量作业异常: {exc}", "ERROR")
        for job_id in list(self._cad_rerun_jobs):
            try:
                self.job_facade.cancel_job(job_id)
                self.log_panel.append(f"Requested cancel for CAD rerun job {job_id}", "WARN")
            except Exception as exc:
                self.log_panel.append(f"CAD rerun cancel failed: {exc}", "ERROR")
        if self._cad_rerun_jobs:
            self._cad_rerun_jobs.clear()
            self.batch_page.set_running(False)
        for job_id in list(self._llm_action_jobs):
            try:
                self.job_facade.cancel_job(job_id)
                self.log_panel.append(f"Requested cancel for LLM action job {job_id}", "WARN")
            except Exception as exc:
                self.log_panel.append(f"LLM action cancel failed: {exc}", "ERROR")
        if self._llm_action_jobs:
            self._llm_action_jobs.clear()

    # ---------------- diagnostics facade jobs ----------------
    def _on_request_latest_diagnostics(self) -> None:
        try:
            from app.services.run_manager import list_recent_runs
        except Exception as exc:
            self.log_panel.append(f"诊断包模块加载失败: {exc}", "ERROR")
            return
        runs = list_recent_runs(1)
        if not runs:
            QMessageBox.information(
                self,
                "诊断包",
                "尚无可用 run。请先在「单件制图」页运行至少一次。",
            )
            return
        run_id = str(runs[0].get("run_id") or "").strip()
        if not run_id:
            self.log_panel.append("最近 run 无 run_id", "WARN")
            return
        self._on_request_diagnostics_for_run(run_id, source="log_panel")

    def _on_request_diagnostics_for_run(self, run_id: str, source: str = "logs_page") -> None:
        normalized = str(run_id or "").strip()
        if not normalized:
            self.log_panel.append("诊断包生成失败: run_id 为空", "ERROR")
            return
        try:
            job_id = self.job_facade.start_diagnostics_action(
                action="build_zip",
                run_id=normalized,
                timeout_s=180,
            )
        except Exception as exc:
            self.log_panel.append(f"诊断包提交失败: {exc}", "ERROR")
            if source == "logs_page":
                self.logs_diagnostics_page.show_diagnostics_failed(str(exc))
            return
        self._diagnostics_jobs[job_id] = {"action": "build_zip", "run_id": normalized, "source": source}
        self.log_panel.append(f"诊断包 worker 已提交: {job_id} run_id={normalized}", "INFO")
        self.statusBar().showMessage(f"诊断包生成中: {normalized}")
        if source == "logs_page":
            self.logs_diagnostics_page.set_diagnostics_running(normalized, job_id)

    def _on_diagnostics_action_progress(self, job_id: str, data: dict) -> None:
        meta = self._diagnostics_jobs.get(job_id)
        if not meta:
            return
        stage = str((data or {}).get("stage") or "")
        if stage:
            self.statusBar().showMessage(f"诊断包: {stage}")

    def _on_diagnostics_action_finished(self, job_id: str, data: dict) -> None:
        meta = self._diagnostics_jobs.pop(job_id, None)
        if not meta:
            return
        result = (data or {}).get("result", data or {})
        if not isinstance(result, dict):
            result = {}
        zip_path = str(result.get("zip_path") or "")
        if not zip_path:
            reason = "diagnostics worker returned no zip_path"
            self.log_panel.append(f"诊断包生成失败: {reason}", "ERROR")
            if meta.get("source") == "logs_page":
                self.logs_diagnostics_page.show_diagnostics_failed(reason)
            elif meta.get("source") == "log_panel":
                QMessageBox.warning(self, "诊断包", f"失败: {reason}")
            return
        self.log_panel.append(f"诊断包已生成: {zip_path}", "INFO")
        self.statusBar().showMessage("诊断包已生成")
        if meta.get("source") == "logs_page":
            self.logs_diagnostics_page.show_diagnostics_result(zip_path)
        elif meta.get("source") == "log_panel":
            QMessageBox.information(self, "诊断包", f"已生成:\n{zip_path}")

    def _on_diagnostics_action_failed(self, job_id: str, data: dict) -> None:
        meta = self._diagnostics_jobs.pop(job_id, None)
        if not meta:
            return
        reason = str((data or {}).get("reason") or (data or {}).get("error") or data or "diagnostics failed")
        self.log_panel.append(f"诊断包生成失败: {reason}", "ERROR")
        self.statusBar().showMessage("诊断包生成失败")
        if meta.get("source") == "logs_page":
            self.logs_diagnostics_page.show_diagnostics_failed(reason)
        elif meta.get("source") == "log_panel":
            QMessageBox.warning(self, "诊断包", f"失败: {reason}")

    def _tb_pre_analyze(self) -> None:
        self._goto_page(PAGE_BATCH)
        self.batch_page._on_pre_analyze()

    def _tb_run(self) -> None:
        self._goto_page(PAGE_BATCH)
        self.batch_page._on_run()

    def _tb_vision(self) -> None:
        self._goto_page(PAGE_QC)
        self.qc_page._on_vision()

    # ---------------- LLM action facade jobs ----------------
    def _on_llm_action_progress(self, job_id: str, data: dict) -> None:
        meta = self._llm_action_jobs.get(job_id)
        if not meta:
            return
        stage = str((data or {}).get("stage") or "")
        if stage:
            self.statusBar().showMessage(stage)

    def _on_llm_action_finished(self, job_id: str, data: dict) -> None:
        meta = self._llm_action_jobs.pop(job_id, None)
        if not meta:
            return
        result = (data or {}).get("result", data or {})
        if not isinstance(result, dict):
            result = {}
        action = str(result.get("action") or meta.get("action") or "")
        if action == "pre_analyze":
            part_path = str(result.get("part_path") or meta.get("part_path") or "")
            pre_analysis = result.get("pre_analysis") if isinstance(result.get("pre_analysis"), dict) else {}
            self._on_pre_analyze_done(part_path, pre_analysis, None)
            return
        if action == "tech_text":
            self._on_tech_text_done(result.get("items"), None)
            return
        self.log_panel.append(f"Unknown LLM action finished: {action}", "WARN")

    def _on_llm_action_failed(self, job_id: str, data: dict) -> None:
        meta = self._llm_action_jobs.pop(job_id, None)
        if not meta:
            return
        reason = str((data or {}).get("reason") or (data or {}).get("error") or data or "LLM action failed")
        action = str(meta.get("action") or "")
        if action == "pre_analyze":
            part_path = str(meta.get("part_path") or "")
            self._on_pre_analyze_done(part_path, {}, reason)
            return
        if action == "tech_text":
            self._on_tech_text_done(None, reason)
            return
        self.log_panel.append(f"LLM 作业失败 {job_id}: {reason}", "ERROR")

    # ---------------- batch: pre analyze ----------------
    def _on_request_pre_analyze(self, items: list) -> None:
        n = len(items or [])
        self.log_panel.append(f"已请求 AI 预分析：{n} 个文件", "INFO")
        if self.llm is None:
            self.log_panel.append("LLM 未配置，已跳过预分析", "WARN")
            for p in items or []:
                self.batch_page.set_pre_analysis_by_path(p, None)
            return
        for p in items or []:
            self.batch_page.update_row(p, status="pre_analyzing")
            try:
                job_id = self.job_facade.start_llm_action(
                    action="pre_analyze",
                    part_path=str(p),
                    timeout_s=120,
                )
                self._llm_action_jobs[job_id] = {"action": "pre_analyze", "part_path": str(p)}
                self.log_panel.append(f"LLM pre-analysis worker submitted {job_id}: {p}", "INFO")
            except Exception as exc:
                self._on_pre_analyze_done(str(p), {}, str(exc))

    def _on_pre_analyze_done(self, path: str, result, err) -> None:
        if err is not None or not isinstance(result, dict) or not result:
            self.log_panel.append(
                f"Pre-analysis failed {Path(path).name}: {err if err else 'parse_failed'}", "ERROR"
            )
            self.batch_page.set_pre_analysis_by_path(path, None)
            self.batch_page.update_row(path, status="pre_analysis_failed")
            return
        self.batch_page.set_pre_analysis_by_path(path, result)
        self.batch_page.update_row(path, status="ready")
        self.log_panel.append(f"Pre-analysis completed {Path(path).name}: {result}", "INFO")
    # ---------------- batch: run ----------------
    def _on_request_run(self, items: list) -> None:
        n = len(items or [])
        if n <= 0:
            self.log_panel.append("列表为空，请先添加文件再开始出图。", "WARN")
            self.statusBar().showMessage("列表为空")
            return
        self.log_panel.append(f"开始批量出图，共 {n} 个文件", "INFO")
        self.statusBar().showMessage(f"出图中: {n} 个文件")
        for p in items or []:
            self.batch_page.update_row(p, status="排队中")
        self.batch_page.set_running(True)
        self.batch_page.set_progress(0, n)
        self._active_batch_items = list(items)
        try:
            self._active_batch_job_id = self.job_facade.start_batch_job(
                part_paths=list(items),
                output_dir=self._output_dir,
                max_rounds=self._max_qc_rounds,
                timeout_s=900,
            )
            self.log_panel.append(f"批量作业已提交: {self._active_batch_job_id}", "INFO")
        except Exception as exc:
            self._active_batch_job_id = ""
            self._active_batch_items = []
            self.batch_page.set_running(False)
            self.log_panel.append(f"批量作业提交失败: {exc}", "ERROR")
            self.statusBar().showMessage("批量出图提交失败")

    def _on_batch_job_progress(self, job_id: str, data: dict) -> None:
        if job_id != self._active_batch_job_id:
            return
        total = max(1, len(self._active_batch_items))
        progress = data.get("progress", 0)
        try:
            current = max(0, min(total, int(round(float(progress) * total))))
            self.batch_page.set_progress(current, total)
        except Exception:
            pass
        stage = str(data.get("stage") or "")
        if stage:
            self.statusBar().showMessage(stage)
        current_part = str(data.get("current_part") or "")
        if current_part:
            self.batch_page.update_row(current_part, status="运行中")

    def _on_batch_job_finished(self, job_id: str, data: dict) -> None:
        if job_id != self._active_batch_job_id:
            return
        result = (data or {}).get("result", data or {})
        self._finish_batch_job(result, None)

    def _on_batch_job_failed(self, job_id: str, data: dict) -> None:
        if job_id != self._active_batch_job_id:
            return
        result = (data or {}).get("result")
        err = str((data or {}).get("error") or data)
        self._finish_batch_job(result, err)

    def _on_batch_job_event(self, job_id: str, event_type: str, data: dict) -> None:
        if job_id != self._active_batch_job_id:
            return
        if event_type == "warning":
            line = str((data or {}).get("line") or (data or {}).get("raw_line") or "")
            if line:
                self.log_panel.append_raw(line)

    def _finish_batch_job(self, result, err) -> None:
        self.batch_page.set_running(False)
        self.batch_page.set_progress(len(self._active_batch_items), max(1, len(self._active_batch_items)))
        self._active_batch_job_id = ""
        self._active_batch_items = []
        if err is not None:
            self.log_panel.append(f"批量出图异常: {err}", "ERROR")
            self.statusBar().showMessage("批量出图异常")
        if isinstance(result, dict):
            rows = result.get("results") or []
            for row in rows:
                if isinstance(row, dict):
                    self._update_batch_row_from_facade_result(row)
            ok = result.get("ok", 0)
            failed = result.get("failed", 0)
            total = result.get("total", len(rows))
            if err is None:
                self.statusBar().showMessage(f"批量出图完成: {ok}/{total} 成功")
                self.log_panel.append(f"批量出图完成: {ok}/{total} 成功, {failed} 失败", "INFO")
            else:
                self.statusBar().showMessage(f"批量出图失败: {ok}/{total} 成功")
                self.log_panel.append(f"批量出图失败: {ok}/{total} 成功, {failed} 失败", "ERROR")
        elif err is None:
            self.statusBar().showMessage("批量出图完成")
            self.log_panel.append("批量出图完成", "INFO")

    def _update_batch_row_from_facade_result(self, result: dict) -> None:
        part_path = str(result.get("part") or result.get("sldprt") or "")
        if not part_path:
            return
        ok = bool(result.get("ok"))
        slddrw = str(result.get("slddrw") or "")
        err = str(result.get("error") or "")
        qc_pass_text = self._qc_pass_text_for_part(part_path)
        self.batch_page.update_row(
            part_path,
            status="完成" if ok else "失败",
            qc_pass=qc_pass_text or None,
            output_path=slddrw or None,
            error="" if ok else err,
        )
        if ok:
            self.log_panel.append(f"完成: {part_path} -> {slddrw}", "INFO")
        else:
            self.log_panel.append(f"失败: {part_path} · {err}", "ERROR")

    def _qc_pass_text_for_part(self, part_path: str) -> str:
        qc_json = Path(self._output_dir) / f"{Path(part_path).stem}_v5_qc.json"
        if not qc_json.exists():
            qc_json = Path("drw_output") / "v5" / f"{Path(part_path).stem}_v5_qc.json"
        return self._qc_pass_text(qc_json)

    @staticmethod
    def _qc_pass_text(qc_json: Path) -> str:
        if not qc_json.exists():
            return ""
        try:
            with qc_json.open("r", encoding="utf-8") as f:
                qc_data = json.load(f)
            count = qc_data.get("score_pass_count")
            passed = qc_data.get("pass")
            if count is not None:
                return f"{count} ({'pass' if passed else 'fail'})"
            return "pass" if passed else "fail"
        except Exception:
            return ""

    # ---------------- CAD rerun facade jobs ----------------
    def _on_cad_rerun_progress(self, job_id: str, data: dict) -> None:
        meta = self._cad_rerun_jobs.get(job_id)
        if not meta:
            return
        stage = str((data or {}).get("stage") or "")
        if stage:
            self.statusBar().showMessage(stage)
        part_path = str(meta.get("part_path") or "")
        if part_path and meta.get("mode") == "batch_one":
            self.batch_page.update_row(part_path, status="running")

    def _on_cad_rerun_finished(self, job_id: str, data: dict) -> None:
        meta = self._cad_rerun_jobs.pop(job_id, None)
        if not meta:
            return
        raw = (data or {}).get("result", data or {})
        mapped = self._map_cad_rerun_result(meta, raw if isinstance(raw, dict) else {})
        if meta.get("mode") == "batch_one":
            self.batch_page.set_running(False)
            self._update_batch_row_from_facade_result(mapped)
            return
        self._finish_qc_cad_rerun(mapped)

    def _on_cad_rerun_failed(self, job_id: str, data: dict) -> None:
        meta = self._cad_rerun_jobs.pop(job_id, None)
        if not meta:
            return
        reason = str((data or {}).get("reason") or (data or {}).get("error") or data or "CAD rerun failed")
        part_path = str(meta.get("part_path") or "")
        mapped = {"ok": False, "part": part_path, "sldprt": part_path, "error": reason}
        if meta.get("mode") == "batch_one":
            self.batch_page.set_running(False)
            self._update_batch_row_from_facade_result(mapped)
        else:
            self.qc_page.set_report(f"CAD rerun failed: {reason}")
        self.log_panel.append(f"CAD rerun job failed {job_id}: {reason}", "ERROR")

    def _submit_cad_rerun(self, part_path: str, mode: str, source_slddrw: str = "") -> str:
        job_id = self.job_facade.start_cad_job(
            part_path=str(part_path),
            output_dir="",
            max_rounds=self._max_qc_rounds,
            timeout_s=900,
        )
        self._cad_rerun_jobs[job_id] = {
            "mode": mode,
            "part_path": str(part_path),
            "source_slddrw": str(source_slddrw or ""),
        }
        self.log_panel.append(f"Submitted CAD rerun job {job_id}: {part_path}", "INFO")
        return job_id

    def _map_cad_rerun_result(self, meta: dict, result: dict) -> dict:
        part_path = str(meta.get("part_path") or result.get("part") or result.get("sldprt") or "")
        run_dir = str(result.get("run_dir") or "")
        output_files = result.get("output_files") or {}
        slddrw = str(result.get("slddrw") or self._first_artifact_path(output_files, (".slddrw",)) or "")
        qc_json = str(result.get("qc_json") or self._first_artifact_path(output_files, ("_qc.json", "vision_qc_v5.json", ".json")) or "")
        if not slddrw and run_dir:
            slddrw = self._first_existing_under(run_dir, ("*.SLDDRW", "*.slddrw"))
        if not qc_json and run_dir:
            qc_json = self._first_existing_under(run_dir, ("*_qc.json", "*vision_qc_v5.json"))
        drawing_usable = result.get("drawing_usable") if isinstance(result.get("drawing_usable"), dict) else {}
        if "ok" in result:
            ok = bool(result.get("ok"))
        elif "pass" in drawing_usable:
            ok = bool(drawing_usable.get("pass"))
        elif result.get("qc_pass") is not None:
            ok = bool(result.get("qc_pass"))
        else:
            ok = bool(slddrw) and not bool(result.get("error"))
        error = str(result.get("error") or result.get("reason") or "")
        if not error:
            hard_fail = result.get("hard_fail") or result.get("exception_summary") or []
            if isinstance(hard_fail, list) and hard_fail:
                error = "; ".join(str(x) for x in hard_fail)
            elif hard_fail:
                error = str(hard_fail)
        return {
            "ok": ok,
            "part": part_path,
            "sldprt": part_path,
            "slddrw": slddrw,
            "qc_json": qc_json,
            "error": "" if ok else (error or "CAD worker did not report a usable drawing"),
        }

    @classmethod
    def _first_artifact_path(cls, value, suffixes: tuple[str, ...]) -> str:
        for path in cls._iter_artifact_paths(value):
            low = path.lower()
            if any(low.endswith(suffix.lower()) for suffix in suffixes):
                return path
        return ""

    @classmethod
    def _iter_artifact_paths(cls, value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from cls._iter_artifact_paths(child)
        elif isinstance(value, (list, tuple, set)):
            for child in value:
                yield from cls._iter_artifact_paths(child)

    @staticmethod
    def _first_existing_under(root: str, patterns: tuple[str, ...]) -> str:
        base = Path(root)
        if not base.exists():
            return ""
        for pattern in patterns:
            for path in sorted(base.rglob(pattern)):
                if path.is_file():
                    return str(path)
        return ""

    def _finish_qc_cad_rerun(self, result: dict) -> None:
        ok = bool(result.get("ok"))
        slddrw = str(result.get("slddrw") or "")
        err = str(result.get("error") or "")
        self.log_panel.append(f"CAD rerun complete ok={ok} slddrw={slddrw}", "INFO" if ok else "ERROR")
        if ok and slddrw:
            self.qc_page.set_slddrw(slddrw)
        elif err:
            self.qc_page.set_report(f"CAD rerun failed: {err}")

    # ---------------- qc: vision ----------------
    def _on_request_vision(self, slddrw: str, qc_json: str) -> None:
        if not slddrw:
            self.log_panel.append("视觉质检：未选择 SLDDRW", "WARN")
            return
        if self.llm is None:
            self.log_panel.append("视觉质检：模型未配置", "ERROR")
            self.qc_page.set_report("模型未配置，无法执行视觉质检。")
            return
        self.log_panel.append(f"视觉质检中: {slddrw}", "INFO")
        self.qc_page.set_report("视觉质检已提交到 worker，请稍候…")
        try:
            job_id = self.job_facade.start_qc_action(
                action="legacy_vision_score",
                slddrw_path=slddrw,
                qc_json_path=qc_json,
                run_dir=str(Path(slddrw).parent),
                timeout_s=240,
            )
            self._qc_action_jobs[job_id] = {
                "action": "legacy_vision_score",
                "slddrw": slddrw,
                "qc_json": qc_json,
            }
            self.log_panel.append(f"视觉质检 worker 已提交: {job_id}", "INFO")
        except Exception as exc:
            self.log_panel.append(f"视觉质检提交失败: {exc}", "ERROR")
            self.qc_page.set_report(f"视觉质检提交失败: {exc}")

    def _on_vision_done(self, result, err) -> None:
        if err is not None or not isinstance(result, dict):
            self.log_panel.append(f"视觉质检异常: {err}", "ERROR")
            self.qc_page.set_report(f"视觉质检异常: {err}")
            return
        score = result.get("score", 0)
        self.log_panel.append(
            f"视觉质检完成 score={score} issues={len(result.get('issues') or [])}",
            "INFO",
        )
        slddrw = self.qc_page.slddrw_path()
        if slddrw:
            self.batch_page.update_row(slddrw, vision_score=str(score))
            for r in range(self.batch_page.model.rowCount()):
                it = self.batch_page.model.item(r, 0)
                if it is None:
                    continue
                p = it.data(Qt.ItemDataRole.UserRole)
                if isinstance(p, str) and p:
                    base = Path(p).stem
                    drw_stem = Path(slddrw).stem
                    if base in drw_stem or drw_stem.startswith(base):
                        self.batch_page.update_row(p, vision_score=str(score))
                        break
        self.qc_page.set_vision_result(result)

    # ---------------- qc: tech text ----------------
    def _on_request_tech_text(self) -> None:
        if self.llm is None:
            self.log_panel.append("技术要求生成失败：LLM 未配置", "ERROR")
            self.qc_page.append_report("\nLLM 未配置，无法生成技术要求。")
            return
        self.log_panel.append("正在提交技术要求生成到 LLM worker", "INFO")
        try:
            job_id = self.job_facade.start_llm_action(
                action="tech_text",
                context=GB_TECH_BRIEF,
                timeout_s=120,
            )
            self._llm_action_jobs[job_id] = {"action": "tech_text"}
            self.qc_page.append_report("\nTech text generation submitted to worker.")
        except Exception as exc:
            self._on_tech_text_done(None, str(exc))

    def _on_tech_text_done(self, result, err) -> None:
        if err is not None:
            self.log_panel.append(f"技术要求生成失败: {err}", "ERROR")
            self.qc_page.append_report(f"\n技术要求生成失败: {err}")
            return
        if not isinstance(result, list) or not result:
            self.log_panel.append("Tech text generation returned empty result", "WARN")
            self.qc_page.append_report("\n(Tech text generation returned an empty result.)")
            return
        self.qc_page.set_tech_text(result)
        self.log_panel.append(f"Tech text generation completed: {len(result)} item(s)", "INFO")
    # ---------------- qc: render png ----------------
    def _on_request_render_png(self, slddrw: str, png_out: str) -> None:
        if not slddrw or not png_out:
            self.log_panel.append("PNG 渲染：缺少输入路径", "WARN")
            return
        try:
            job_id = self.job_facade.start_qc_action(
                action="render_png",
                slddrw_path=slddrw,
                png_path=png_out,
                run_dir=str(Path(png_out).parent),
                timeout_s=120,
            )
            self._qc_action_jobs[job_id] = {
                "action": "render_png",
                "slddrw": slddrw,
                "png_out": png_out,
            }
            self.log_panel.append(f"PNG 渲染 worker 已提交: {job_id}", "INFO")
        except Exception as exc:
            self.log_panel.append(f"PNG 渲染提交失败: {exc}", "ERROR")
            self.qc_page.preview.setText(f"PNG 渲染提交失败: {exc}")

    def _on_render_png_done(self, png_out: str, result, err) -> None:
        if err is not None:
            self.log_panel.append(f"PNG 渲染异常: {err}", "ERROR")
            return
        if bool(result) and Path(png_out).exists():
            self.qc_page.set_preview_image(png_out)
            self.log_panel.append(f"PNG 预览已加载: {png_out}", "INFO")
        else:
            self.qc_page.preview.setText("（无可用 PNG 预览）")
            self.log_panel.append("PNG 渲染失败", "WARN")

    def _on_request_rerun_vqc2(self, qc_json: str, png_path: str, run_dir: str) -> None:
        if not qc_json:
            self.log_panel.append("Vision QC v2：未选择 qc.json", "WARN")
            return
        try:
            job_id = self.job_facade.start_qc_action(
                action="vision_qc_v2",
                qc_json_path=qc_json,
                png_path=png_path,
                run_dir=run_dir,
                timeout_s=180,
            )
            self._qc_action_jobs[job_id] = {
                "action": "vision_qc_v2",
                "qc_json": qc_json,
                "png_path": png_path,
                "run_dir": run_dir,
            }
            self.log_panel.append(f"Vision QC v2 worker 已提交: {job_id}", "INFO")
        except Exception as exc:
            self.log_panel.append(f"Vision QC v2 提交失败: {exc}", "ERROR")
            self.qc_page.set_report(f"Vision QC v2 提交失败: {exc}")

    def _on_qc_action_progress(self, job_id: str, data: dict) -> None:
        meta = self._qc_action_jobs.get(job_id)
        if not meta:
            return
        stage = str((data or {}).get("stage") or "")
        if stage:
            self.log_panel.append(f"QC worker {job_id}: {stage}", "INFO")

    def _on_qc_action_finished(self, job_id: str, data: dict) -> None:
        meta = self._qc_action_jobs.pop(job_id, None)
        if not meta:
            return
        action = str((data or {}).get("action") or meta.get("action") or "")
        result = (data or {}).get("result")
        if not isinstance(result, dict):
            result = data or {}

        if action == "render_png":
            png_out = str(result.get("png_path") or meta.get("png_out") or "")
            self._on_render_png_done(png_out, bool(result.get("success", True)), None)
            return
        if action == "vision_qc_v2":
            self.qc_page.set_vision_qc_v2(result)
            self.qc_page.set_report(f"视觉 QC v2 完成，共 {len(result.get('issues', []))} 个 issue")
            self.log_panel.append(f"Vision QC v2 完成: {job_id}", "INFO")
            return
        if action == "legacy_vision_score":
            self._on_vision_done(result, None)
            return

        self.log_panel.append(f"未知 QC worker action 完成: {action}", "WARN")

    def _on_qc_action_failed(self, job_id: str, data: dict) -> None:
        meta = self._qc_action_jobs.pop(job_id, None)
        if not meta:
            return
        action = str((data or {}).get("action") or meta.get("action") or "qc_action")
        reason = str((data or {}).get("reason") or (data or {}).get("error") or data)
        self.log_panel.append(f"QC worker 失败 {action}: {reason}", "ERROR")
        if action == "render_png":
            self.qc_page.preview.setText(f"PNG 渲染失败: {reason}")
        elif action == "vision_qc_v2":
            self.qc_page.set_report(f"重新跑视觉 QC v2 失败: {reason}")
        elif action == "legacy_vision_score":
            self.qc_page.set_report(f"视觉质检失败: {reason}")

    # ---------------- batch: rerun one ----------------
    def _on_request_rerun_one(self, sldprt_path: str) -> None:
        if not sldprt_path:
            return
        if not Path(sldprt_path).exists():
            self.log_panel.append(f"CAD rerun failed: file does not exist {sldprt_path}", "ERROR")
            return
        self.log_panel.append(f"Batch row CAD rerun requested: {sldprt_path}", "INFO")
        self.batch_page.set_running(True)
        self.batch_page.set_progress(0, 1)
        try:
            self._submit_cad_rerun(str(sldprt_path), "batch_one")
            self.batch_page.update_row(str(sldprt_path), status="queued")
        except Exception as exc:
            self.batch_page.set_running(False)
            self.log_panel.append(f"CAD rerun submit failed: {exc}", "ERROR")

    # ---------------- qc: rerun ----------------
    def _on_request_rerun(self, slddrw_path: str) -> None:
        if not slddrw_path:
            return
        drw = Path(slddrw_path)
        base = drw.stem
        if base.endswith("_v5"):
            base = base[:-3]
        sldprt_candidates = []
        repo_root = Path(__file__).resolve().parent.parent.parent
        sldprt_candidates.append(repo_root / "3D转2D测试图纸" / f"{base}.SLDPRT")
        sldprt_candidates.append(drw.with_name(f"{base}.SLDPRT"))
        sldprt: Path | None = None
        for candidate in sldprt_candidates:
            if candidate.exists():
                sldprt = candidate
                break
        if sldprt is None:
            self.log_panel.append(f"CAD rerun failed: matching SLDPRT not found for base={base}", "ERROR")
            self.qc_page.set_report(f"CAD rerun failed: matching SLDPRT not found for base={base}")
            return
        self.log_panel.append(f"QC CAD rerun requested: {sldprt}", "INFO")
        self.qc_page.set_report("CAD rerun submitted to worker; waiting for result.")
        try:
            self._submit_cad_rerun(str(sldprt), "qc_rerun", str(slddrw_path))
        except Exception as exc:
            self.log_panel.append(f"CAD rerun submit failed: {exc}", "ERROR")
            self.qc_page.set_report(f"CAD rerun submit failed: {exc}")
