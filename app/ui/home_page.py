from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.job_runtime_facade import get_job_runtime_facade
from app.services.run_manager import RUNS_DIR, list_recent_runs
from app.services.system_health_service import health_rows_from_dicts
from app.ui.open_path_helper import open_local_path


_STATUS_BADGE = {
    "pass": ("✅", "#2E7D32"),
    "warning": ("⚠", "#E67E22"),
    "fail": ("❌", "#C62828"),
}

_KEY_LABEL = {
    "solidworks": "SolidWorks 连接",
    "sw_revision": "SW Revision",
    "sw_revision_supported": "SW 版本支持",
    "template": "GB 图框模板",
    "macro_bas": "宏 .bas",
    "macro_swp": "宏 .swp",
    "output_dir": "输出目录",
    "chinese_path_support": "中文路径支持",
    "v6_generator": "v6 出图脚本",
    "v5_fallback": "v5 回退脚本",
    "db_readable": "数据库可读",
    "llm": "LLM 配置",
}


class HomePage(QWidget):
    request_goto_batch = Signal()
    request_goto_single = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.facade = get_job_runtime_facade()
        self._active_health_job_id = ""

        title = QLabel("欢迎使用 SW Drawing Studio  v1.8")
        f = QFont()
        f.setPointSize(20)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        subtitle = QLabel("3D 自动转 2D · GB 制图规范 · AI 视觉质检 · BOM/工艺/报价 · 分类型生产可用")
        subtitle.setStyleSheet("color: #555;")

        # ===== v1.8 仪表盘卡 =====
        self.dashboard_card = QFrame()
        self.dashboard_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.dashboard_card.setObjectName("dashboardCard")
        dc_layout = QVBoxLayout(self.dashboard_card)

        dc_title = QLabel("<b>仪表盘 (v1.8)</b>")
        dc_layout.addWidget(dc_title)

        # 统计行
        stats_row = QHBoxLayout()
        self.lbl_today_runs = QLabel("今日运行: 0")
        self.lbl_grade_dist = QLabel("A/B/C/D: 0/0/0/0")
        self.lbl_need_review = QLabel("待复核: 0")
        self.lbl_fail_count = QLabel("失败: 0")
        for lbl in (self.lbl_today_runs, self.lbl_grade_dist, self.lbl_need_review, self.lbl_fail_count):
            lbl.setStyleSheet("font-size: 13px; padding: 4px 8px;")
            stats_row.addWidget(lbl)
        stats_row.addStretch(1)
        dc_layout.addLayout(stats_row)

        # 失败原因 Top5
        self.lbl_fail_top5 = QLabel("失败原因 Top5: -")
        self.lbl_fail_top5.setStyleSheet("font-size: 12px; color: #666;")
        dc_layout.addWidget(self.lbl_fail_top5)

        self.btn_refresh_dashboard = QPushButton("刷新仪表盘")
        self.btn_refresh_dashboard.clicked.connect(self._refresh_dashboard)
        dc_layout.addWidget(self.btn_refresh_dashboard)

        # ===== v2.2 SolidWorks 会话状态面板 =====
        self.sw_session_card = QFrame()
        self.sw_session_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.sw_session_card.setObjectName("swSessionCard")
        sws_layout = QVBoxLayout(self.sw_session_card)

        sws_title = QLabel("<b>SolidWorks 会话状态 (v2.2)</b>")
        sws_layout.addWidget(sws_title)

        # SW 状态行
        sws_row1 = QHBoxLayout()
        self.lbl_sw_state = QLabel("状态: -")
        self.lbl_sw_pid = QLabel("PID: -")
        self.lbl_sw_restarts = QLabel("重启: 0")
        for lbl in (self.lbl_sw_state, self.lbl_sw_pid, self.lbl_sw_restarts):
            lbl.setStyleSheet("font-size: 13px; padding: 4px 8px;")
            sws_row1.addWidget(lbl)
        sws_row1.addStretch(1)
        sws_layout.addLayout(sws_row1)

        # 事务统计行
        sws_row2 = QHBoxLayout()
        self.lbl_sw_transactions = QLabel("事务: 0/0")
        self.lbl_sw_retries = QLabel("重试: 0")
        self.lbl_sw_timeouts = QLabel("超时: 0")
        self.lbl_sw_recoveries = QLabel("恢复: 0")
        for lbl in (self.lbl_sw_transactions, self.lbl_sw_retries, self.lbl_sw_timeouts, self.lbl_sw_recoveries):
            lbl.setStyleSheet("font-size: 12px; padding: 2px 6px; color: #555;")
            sws_row2.addWidget(lbl)
        sws_row2.addStretch(1)
        sws_layout.addLayout(sws_row2)

        # 弹窗守护状态
        self.lbl_dialog_guard = QLabel("弹窗守护: -")
        self.lbl_dialog_guard.setStyleSheet("font-size: 12px; padding: 2px 6px; color: #555;")
        sws_layout.addWidget(self.lbl_dialog_guard)

        # 布局求解状态
        self.lbl_layout_solver = QLabel("布局求解: -")
        self.lbl_layout_solver.setStyleSheet("font-size: 12px; padding: 2px 6px; color: #555;")
        sws_layout.addWidget(self.lbl_layout_solver)

        # 视觉质检状态
        self.lbl_vision_qc = QLabel("视觉质检: -")
        self.lbl_vision_qc.setStyleSheet("font-size: 12px; padding: 2px 6px; color: #555;")
        sws_layout.addWidget(self.lbl_vision_qc)

        self.btn_refresh_sw_session = QPushButton("刷新 SolidWorks 会话")
        self.btn_refresh_sw_session.clicked.connect(self._refresh_sw_session)
        sws_layout.addWidget(self.btn_refresh_sw_session)

        # ===== 12 项环境自检卡 =====
        self.health_card = QFrame()
        self.health_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.health_card.setObjectName("healthCard")
        hc_layout = QVBoxLayout(self.health_card)

        hc_title_row = QHBoxLayout()
        hc_title = QLabel("<b>环境自检（12 项）</b>")
        self.lbl_health_summary = QLabel("检测中…")
        self.btn_refresh_health = QPushButton("重新自检")
        hc_title_row.addWidget(hc_title)
        hc_title_row.addSpacing(12)
        hc_title_row.addWidget(self.lbl_health_summary, 1)
        hc_title_row.addWidget(self.btn_refresh_health)
        hc_layout.addLayout(hc_title_row)

        self._health_grid = QGridLayout()
        self._health_grid.setColumnStretch(0, 0)
        self._health_grid.setColumnStretch(1, 0)
        self._health_grid.setColumnStretch(2, 1)
        self._health_grid.setColumnStretch(3, 2)
        hc_layout.addLayout(self._health_grid)

        self.btn_refresh_health.clicked.connect(self._refresh_health)

        # ===== 最近 5 次 run =====
        self.runs_card = QFrame()
        self.runs_card.setFrameShape(QFrame.Shape.StyledPanel)
        rc_layout = QVBoxLayout(self.runs_card)

        rc_title_row = QHBoxLayout()
        rc_title = QLabel("<b>最近 5 次出图</b>")
        self.btn_refresh_runs = QPushButton("刷新")
        self.btn_open_runs_dir = QPushButton("打开输出目录")
        rc_title_row.addWidget(rc_title)
        rc_title_row.addStretch(1)
        rc_title_row.addWidget(self.btn_refresh_runs)
        rc_title_row.addWidget(self.btn_open_runs_dir)
        rc_layout.addLayout(rc_title_row)

        self._runs_grid = QGridLayout()
        rc_layout.addLayout(self._runs_grid)

        self.btn_refresh_runs.clicked.connect(self._refresh_runs)
        self.btn_open_runs_dir.clicked.connect(self._on_open_runs_dir)

        self.facade.job_finished.connect(self._on_health_job_finished)
        self.facade.job_failed.connect(self._on_health_job_failed)

        # ===== 快速开始 =====
        self.btn_single = QPushButton("单件制图（推荐起步）")
        self.btn_single.setMinimumHeight(40)
        self.btn_single.clicked.connect(self.request_goto_single.emit)

        self.btn_quick = QPushButton("批量出图")
        self.btn_quick.setMinimumHeight(40)
        self.btn_quick.clicked.connect(self.request_goto_batch.emit)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch(1)
        bottom_row.addWidget(self.btn_single)
        bottom_row.addSpacing(12)
        bottom_row.addWidget(self.btn_quick)
        bottom_row.addStretch(1)

        # 滚动容器避免小屏溢出
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(24, 24, 24, 24)
        inner_layout.setSpacing(16)
        inner_layout.addWidget(title)
        inner_layout.addWidget(subtitle)
        inner_layout.addSpacing(8)
        inner_layout.addWidget(self.dashboard_card)
        inner_layout.addWidget(self.sw_session_card)
        inner_layout.addWidget(self.health_card)
        inner_layout.addWidget(self.runs_card)
        inner_layout.addStretch(1)
        inner_layout.addLayout(bottom_row)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._refresh_health()
        self._refresh_runs()
        self._refresh_dashboard()

    # --------------- v2.2 SolidWorks 会话状态 ---------------
    def _refresh_sw_session(self) -> None:
        """刷新 SolidWorks 会话状态面板"""
        import json
        from pathlib import Path

        # 读取最近的 sw_session.json
        sw_session_path = None
        if RUNS_DIR.exists():
            for run_dir in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                session_file = run_dir / "qc" / "sw_session.json"
                if session_file.exists():
                    sw_session_path = session_file
                    break

        if sw_session_path is None:
            self.lbl_sw_state.setText("状态: 无 session 记录")
            self.lbl_sw_pid.setText("PID: -")
            self.lbl_sw_restarts.setText("重启: 0")
            self.lbl_sw_transactions.setText("事务: 0/0")
            self.lbl_sw_retries.setText("重试: 0")
            self.lbl_sw_timeouts.setText("超时: 0")
            self.lbl_sw_recoveries.setText("恢复: 0")
            self.lbl_dialog_guard.setText("弹窗守护: 无记录")
            self.lbl_layout_solver.setText("布局求解: 无记录")
            self.lbl_vision_qc.setText("视觉质检: 无记录")
            return

        try:
            data = json.loads(sw_session_path.read_text(encoding="utf-8"))
            stats = data.get("stats", {})

            self.lbl_sw_state.setText(f"状态: {data.get('final_state', '-')}")
            self.lbl_sw_pid.setText(f"PID: {data.get('sw_pid', '-')}")
            self.lbl_sw_restarts.setText(f"重启: {data.get('restart_count', 0)}")
            self.lbl_sw_transactions.setText(
                f"事务: {stats.get('successful_transactions', 0)}/{stats.get('total_transactions', 0)}"
            )
            self.lbl_sw_retries.setText(f"重试: {stats.get('total_retries', 0)}")
            self.lbl_sw_timeouts.setText(f"超时: {stats.get('total_timeouts', 0)}")
            self.lbl_sw_recoveries.setText(f"恢复: {stats.get('total_recoveries', 0)}")

            # DialogGuard 状态
            dg_path = sw_session_path.parent / "dialog_guard.json"
            if dg_path.exists():
                dg_data = json.loads(dg_path.read_text(encoding="utf-8"))
                dg_summary = dg_data.get("summary", {})
                self.lbl_dialog_guard.setText(
                    f"弹窗守护: 已处理={dg_summary.get('dialogs_dismissed', 0)}, 已跳过={dg_summary.get('dialogs_skipped', 0)}"
                )
            else:
                self.lbl_dialog_guard.setText("弹窗守护: 无记录")

            # Layout Solver 状态
            ls_path = sw_session_path.parent / "layout_solver_v2.json"
            if ls_path.exists():
                ls_data = json.loads(ls_path.read_text(encoding="utf-8"))
                self.lbl_layout_solver.setText(
                    f"布局求解: {ls_data.get('best_layout', '-')} @ {ls_data.get('best_scale', '-')}"
                )
            else:
                self.lbl_layout_solver.setText("布局求解: 无记录")

            # Vision QC 状态
            vqc_path = sw_session_path.parent / "vision_qc_v4.json"
            if vqc_path.exists():
                vqc_data = json.loads(vqc_path.read_text(encoding="utf-8"))
                mode = vqc_data.get("mode", "-")
                fallback = vqc_data.get("fallback_used", False)
                issues = vqc_data.get("summary", {}).get("total_issues", 0)
                self.lbl_vision_qc.setText(
                    f"视觉质检: 模式={mode}, 问题={issues}, fallback={fallback}"
                )
            else:
                # 检查 v3
                vqc3_path = sw_session_path.parent / "vision_qc_v3.json"
                if vqc3_path.exists():
                    self.lbl_vision_qc.setText("视觉质检: v3 (需升级到 v4)")
                else:
                    self.lbl_vision_qc.setText("视觉质检: 无记录")

        except Exception as e:
            self.lbl_sw_state.setText(f"状态: 读取失败 ({e})")

    # --------------- v1.8 仪表盘 ---------------
    def _refresh_dashboard(self) -> None:
        """刷新仪表盘统计"""
        import json
        import time
        from collections import Counter

        try:
            today = time.strftime("%Y-%m-%d")
            today_count = 0
            grade_counter = Counter()
            need_review_count = 0
            fail_count = 0
            fail_reasons = Counter()

            if RUNS_DIR.exists():
                for run_dir in RUNS_DIR.iterdir():
                    if not run_dir.is_dir():
                        continue
                    manifest = run_dir / "manifest.json"
                    if not manifest.exists():
                        continue
                    try:
                        data = json.loads(manifest.read_text(encoding="utf-8"))
                        started = data.get("started_at", "")
                        if started.startswith(today):
                            today_count += 1
                        grade = data.get("dimension_grade", "")
                        if grade:
                            grade_counter[grade] += 1
                        fq = data.get("final_quality", {})
                        if isinstance(fq, dict):
                            status = fq.get("status", "")
                            if status == "need_review":
                                need_review_count += 1
                            elif status == "fail":
                                fail_count += 1
                        hard_fail = data.get("hard_fail", [])
                        for hf in hard_fail:
                            fail_reasons[hf] += 1
                    except Exception:
                        continue

            self.lbl_today_runs.setText(f"今日运行: {today_count}")
            self.lbl_grade_dist.setText(
                f"A/B/C/D: {grade_counter.get('A',0)}/{grade_counter.get('B',0)}/{grade_counter.get('C',0)}/{grade_counter.get('D',0)}"
            )
            self.lbl_need_review.setText(f"待复核: {need_review_count}")
            self.lbl_fail_count.setText(f"失败: {fail_count}")

            top5 = fail_reasons.most_common(5)
            if top5:
                top5_text = "失败原因 Top5: " + ", ".join(f"{k}({v})" for k, v in top5)
            else:
                top5_text = "失败原因 Top5: 无"
            self.lbl_fail_top5.setText(top5_text)
        except Exception as e:
            self.lbl_today_runs.setText(f"仪表盘异常: {e}")

    # --------------- 12 项自检 ---------------
    def _refresh_health(self) -> None:
        while self._health_grid.count():
            item = self._health_grid.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()
        if self._active_health_job_id:
            self.lbl_health_summary.setText(f"自检运行中: {self._active_health_job_id}")
            return
        self.btn_refresh_health.setEnabled(False)
        self.lbl_health_summary.setText("检测中…")
        try:
            self._active_health_job_id = self.facade.start_system_health_check(timeout_s=30)
        except Exception as exc:
            self._active_health_job_id = ""
            self.btn_refresh_health.setEnabled(True)
            self._health_grid.addWidget(QLabel(f"自检失败: {exc}"), 0, 0, 1, 4)
            self.lbl_health_summary.setText("自检异常")

    def _on_health_job_finished(self, job_id: str, data: dict) -> None:
        if job_id != self._active_health_job_id:
            return
        self._active_health_job_id = ""
        self.btn_refresh_health.setEnabled(True)
        result = (data or {}).get("result", data or {})
        rows = health_rows_from_dicts(result.get("rows") or []) if isinstance(result, dict) else []
        summary = result.get("summary", {}) if isinstance(result, dict) else {}
        self._render_health_rows(rows, summary)

    def _on_health_job_failed(self, job_id: str, data: dict) -> None:
        if job_id != self._active_health_job_id:
            return
        self._active_health_job_id = ""
        self.btn_refresh_health.setEnabled(True)
        reason = str((data or {}).get("reason") or (data or {}).get("error") or data)
        self._health_grid.addWidget(QLabel(f"自检失败: {reason}"), 0, 0, 1, 4)
        self.lbl_health_summary.setText("自检异常")

    def _render_health_rows(self, rows: list, summary: dict) -> None:
        while self._health_grid.count():
            item = self._health_grid.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()
        for i, row in enumerate(rows):
            key = getattr(row, "key", "?")
            group = getattr(row, "group", "")
            status = getattr(row, "status", "fail")
            msg = getattr(row, "msg", "")
            fix = getattr(row, "fix_suggestion", "")
            badge_text, color = _STATUS_BADGE.get(status, ("?", "#888"))
            badge = QLabel(badge_text)
            badge.setStyleSheet(f"color: {color}; font-weight: bold;")
            label = _KEY_LABEL.get(key, key)
            name = QLabel(f"{group} · {label}" if group else label)
            msg_lbl = QLabel(msg)
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet(f"color: {color};")
            fix_lbl = QLabel(fix)
            fix_lbl.setWordWrap(True)
            fix_lbl.setStyleSheet("color: #777; font-size: 11px;")
            self._health_grid.addWidget(badge, i, 0)
            self._health_grid.addWidget(name, i, 1)
            self._health_grid.addWidget(msg_lbl, i, 2)
            self._health_grid.addWidget(fix_lbl, i, 3)

        passed = int(summary.get("pass", 0) or 0)
        warn = int(summary.get("warning", 0) or 0)
        fail = int(summary.get("fail", 0) or 0)
        total = int(summary.get("total", passed + warn + fail) or 0)
        ts = summary.get("generated_at", "")
        self.lbl_health_summary.setText(
            f"<span style='color:#2E7D32;'>pass {passed}</span> · "
            f"<span style='color:#E67E22;'>warn {warn}</span> · "
            f"<span style='color:#C62828;'>fail {fail}</span> "
            f"(总 {total}) · {ts}"
        )
    # --------------- 最近 5 次 run ---------------
    def _refresh_runs(self) -> None:
        while self._runs_grid.count():
            item = self._runs_grid.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()

        headers = ["run_id", "started_at", "drawing_usable", "qc_pass", "vision", "操作"]
        for col, h in enumerate(headers):
            lbl = QLabel(f"<b>{h}</b>")
            self._runs_grid.addWidget(lbl, 0, col)

        try:
            runs = list_recent_runs(5)
        except Exception as exc:
            self._runs_grid.addWidget(QLabel(f"读取失败: {exc}"), 1, 0, 1, len(headers))
            return

        if not runs:
            self._runs_grid.addWidget(QLabel("（暂无历史 run，运行单件制图后会出现在这里）"),
                                      1, 0, 1, len(headers))
            return

        for r, info in enumerate(runs, 1):
            usable = info.get("drawing_usable")
            usable_label = QLabel("✓" if usable else "—")
            usable_label.setStyleSheet("color: #2E7D32;" if usable else "color: #888;")

            self._runs_grid.addWidget(QLabel(str(info.get("run_id", "")[:10])), r, 0)
            self._runs_grid.addWidget(QLabel(str(info.get("started_at", ""))), r, 1)
            self._runs_grid.addWidget(usable_label, r, 2)
            self._runs_grid.addWidget(
                QLabel(f"{info.get('qc_pass_count', 0)}/12"), r, 3
            )
            vs = info.get("vision_score")
            self._runs_grid.addWidget(
                QLabel(f"{vs}/100" if vs is not None else "—"), r, 4
            )
            btn = QPushButton("打开交付包")
            run_id = info.get("run_id", "")
            btn.clicked.connect(lambda _=False, rid=run_id: self._open_run_dir(rid))
            self._runs_grid.addWidget(btn, r, 5)

    def _open_run_dir(self, run_id: str) -> None:
        if not run_id:
            return
        d = RUNS_DIR / run_id
        if not d.exists():
            return
        open_local_path(d)

    def _on_open_runs_dir(self) -> None:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        open_local_path(RUNS_DIR)
