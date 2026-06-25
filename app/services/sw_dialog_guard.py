"""v2.3 Task 3: DialogGuard V2 生产化增强版

在 v2.2 DialogGuard 基础上增加：
1. dry_run 模式：只记录不实际关闭对话框
2. 白名单机制：只关闭指定标题的对话框（默认：["修改", "Modify"]）
3. 事务阶段追踪：记录 guard 在哪些 transaction 阶段活跃
4. 更详细的统计和日志输出

使用方式:
    from app.services.sw_dialog_guard import DialogGuardV2
    guard = DialogGuardV2(sw_pid=12345, dry_run=False, whitelist=["修改", "Modify"])
    guard.start(stage="AddDimension")
    # ... AddDimension2 调用 ...
    guard.stop()
    print(guard.get_summary())
    guard.save_log(run_dir)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from app.services.dialog_guard import DialogGuard, DialogAction
from app.services.solidworks_global_lock import require_current_job_lock


class DialogGuardV2:
    """DialogGuard V2 增强版

    在原有 DialogGuard 基础上增加：
    - dry_run 模式：记录但不实际关闭
    - 白名单：只处理指定标题的对话框
    - 阶段追踪：记录在哪些 transaction 阶段活跃
    """

    # 默认白名单（SW 尺寸输入对话框）
    DEFAULT_WHITELIST = ["修改", "Modify"]

    def __init__(
        self,
        sw_pid: Optional[int] = None,
        run_dir=None,
        run_id: str = "",
        dry_run: bool = False,
        whitelist: Optional[list[str]] = None,
    ):
        """
        Args:
            sw_pid: SolidWorks 进程 PID
            run_dir: 运行目录（用于保存日志）
            run_id: 运行 ID
            dry_run: True=只记录不关闭，False=实际关闭对话框
            whitelist: 允许关闭的对话框标题列表。None 时使用默认白名单
        """
        self.sw_pid = sw_pid
        self.run_dir = run_dir
        self.run_id = run_id
        self._dry_run = dry_run
        self._whitelist = list(whitelist) if whitelist is not None else list(self.DEFAULT_WHITELIST)

        # 内部 DialogGuard 实例
        # 使用 dismiss_hook 实现 dry_run 模式
        self._inner_guard = DialogGuard(
            sw_pid=sw_pid,
            run_dir=run_dir,
            run_id=run_id,
            dialog_keywords=self._whitelist,
            dismiss_hook=self._dismiss_hook_impl,
        )

        # 阶段追踪
        self._current_stage: str = "unknown"
        self._stages_active: set[str] = set()
        self._stages_completed: set[str] = set()

        # 统计
        self._dialogs_dismissed: int = 0
        self._dialogs_skipped: int = 0
        self._errors: list[str] = []

    def _dismiss_hook_impl(self, hwnd: int, title: str) -> bool:
        """dismiss_hook 实现：dry_run 模式下返回 False 阻止关闭

        Args:
            hwnd: 窗口句柄
            title: 窗口标题

        Returns:
            True: 允许关闭（非 dry_run 模式）
            False: 阻止关闭（dry_run 模式）
        """
        if self._dry_run:
            return False  # dry_run 模式：不实际关闭
        return True  # 正常模式：允许关闭

    # ========== 生命周期 ==========

    def start(self, stage: str = "unknown"):
        """开始监控（进入 transaction 阶段）

        Args:
            stage: 当前 transaction 阶段名称（如 "AddDimension", "SaveAs", "OpenDoc"）
        """
        guard = require_current_job_lock(f"sw_dialog_guard.start:{stage}")
        if not guard.get("ok"):
            raise RuntimeError(
                "blocked_by_solidworks_lock: "
                + json.dumps({
                    "reason": guard.get("reason", ""),
                    "owner": guard.get("owner", {}),
                    "fix_suggestion": guard.get("fix_suggestion", ""),
                }, ensure_ascii=False)
            )
        self._current_stage = stage
        self._stages_active.add(stage)

        # 启动内部 guard
        self._inner_guard.start()

    def stop(self):
        """停止监控（退出 transaction 阶段）"""
        # 停止内部 guard
        self._inner_guard.stop()

        # 记录阶段完成
        if self._current_stage != "unknown":
            self._stages_completed.add(self._current_stage)

        # 更新统计
        summary = self._inner_guard.get_summary()
        self._dialogs_dismissed = summary.get("dialogs_dismissed", 0)
        self._dialogs_skipped = summary.get("dialogs_skipped", 0)

        # 收集错误
        actions = self._inner_guard.get_log()
        self._errors = [a["reason"] for a in actions if a["action"] == "error"]

    # ========== 白名单管理 ==========

    def add_whitelist(self, title: str):
        """添加白名单标题

        Args:
            title: 允许关闭的对话框标题关键字
        """
        if title not in self._whitelist:
            self._whitelist.append(title)
            # 同步到内部 guard
            self._inner_guard._dialog_keywords = self._whitelist

    def remove_whitelist(self, title: str):
        """移除白名单标题

        Args:
            title: 要移除的对话框标题关键字
        """
        if title in self._whitelist:
            self._whitelist.remove(title)
            # 同步到内部 guard
            self._inner_guard._dialog_keywords = self._whitelist

    def set_dry_run(self, enabled: bool):
        """设置 dry_run 模式

        Args:
            enabled: True=只记录不关闭，False=实际关闭
        """
        self._dry_run = enabled
        # dismiss_hook 会自动根据 _dry_run 状态决定是否关闭

    # ========== 查询 ==========

    def get_summary(self) -> dict:
        """获取汇总信息"""
        inner_summary = self._inner_guard.get_summary()

        return {
            "sw_pid": self.sw_pid,
            "run_id": self.run_id,
            "dry_run": self._dry_run,
            "whitelist": self._whitelist,
            "current_stage": self._current_stage,
            "stages_active": list(self._stages_active),
            "stages_completed": list(self._stages_completed),
            "dialogs_dismissed": self._dialogs_dismissed,
            "dialogs_skipped": self._dialogs_skipped,
            "errors": self._errors,
            "inner_summary": inner_summary,
        }

    def save_log(self, out_dir: Optional[Path] = None) -> Path:
        """保存日志到 JSON 文件

        Args:
            out_dir: 输出目录。None 时使用 self.run_dir

        Returns:
            输出文件路径
        """
        out_dir = Path(out_dir) if out_dir else self.run_dir
        if out_dir is None:
            raise ValueError("out_dir 或 run_dir 必须提供其一")

        qc_dir = out_dir / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "run_id": self.run_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sw_pid": self.sw_pid,
            "summary": self.get_summary(),
            "actions": self._inner_guard.get_log(),
        }

        out_path = qc_dir / "dialog_guard_v2.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out_path

    # ========== 属性 ==========

    @property
    def dry_run(self) -> bool:
        """是否 dry_run 模式"""
        return self._dry_run

    @property
    def whitelist(self) -> list[str]:
        """当前白名单"""
        return list(self._whitelist)

    @property
    def is_active(self) -> bool:
        """是否正在监控"""
        return self._inner_guard.is_active

    @property
    def current_stage(self) -> str:
        """当前 transaction 阶段"""
        return self._current_stage
