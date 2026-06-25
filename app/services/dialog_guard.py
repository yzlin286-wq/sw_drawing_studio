"""v2.2 Task 2: DialogGuard 生产化

替换 sheet_sketch_dimension_service.py 中的无边界 _dismiss_dialog_thread。

改进点:
1. 只监控 sw_pid 下的窗口（通过 GetWindowThreadProcessId 过滤）
2. 只在 AddDimension transaction 期间工作（start/stop 显式控制）
3. 记录每个关闭动作的 hwnd/title/class/action
4. 精确匹配 SW 尺寸输入对话框（标题"修改" + class "#32770"）
5. 避免误关其他窗口

使用方式:
    from app.services.dialog_guard import DialogGuard
    guard = DialogGuard(sw_pid=12345)
    guard.start()
    # ... AddDimension2 调用 ...
    guard.stop()
    print(guard.get_log())
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, asdict
from typing import Optional

from app.services.solidworks_global_lock import require_current_job_lock


@dataclass
class DialogAction:
    """单个对话框关闭动作记录"""
    timestamp: str
    hwnd: int
    title: str
    window_class: str
    pid: int
    action: str  # dismissed / skipped / error
    reason: str = ""


class DialogGuard:
    """生产级对话框守卫

    只在 transaction 期间监控并关闭 SW 的尺寸输入对话框。
    通过 PID 过滤确保只处理目标 SW 实例的窗口。
    """

    # SW 尺寸输入对话框的精确特征
    # 标题: "修改" (中文 SW) / "Modify" (英文 SW)
    # 窗口类: "#32770" (标准对话框类)
    DIALOG_TITLE_KEYWORDS = ["修改", "Modify"]
    DIALOG_CLASS = "#32770"

    # 轮询间隔
    POLL_INTERVAL_S = 0.15

    # 关闭后等待确认时间
    DISMISS_CONFIRM_S = 0.1

    def __init__(
        self,
        sw_pid: Optional[int] = None,
        run_dir=None,
        run_id: str = "",
        dialog_keywords: Optional[list[str]] = None,
        dismiss_hook=None,
    ):
        """
        Args:
            sw_pid: SolidWorks 进程 PID。如果为 None，会监控所有窗口（不推荐）
            run_dir: 运行目录（用于保存日志）
            run_id: 运行 ID
            dialog_keywords: 对话框标题关键字列表（实例级），None 时使用类默认值
            dismiss_hook: 关闭前回调 hook(hwnd, title) -> bool，返回 False 则跳过关闭
        """
        self.sw_pid = sw_pid
        self.run_dir = run_dir
        self.run_id = run_id
        # 实例级对话框关键字（优先于类属性）
        self._dialog_keywords = dialog_keywords
        # 关闭前回调（用于 dry_run 等场景）
        self._dismiss_hook = dismiss_hook

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._actions: list[DialogAction] = []
        self._lock = threading.Lock()
        self._active = False

    @property
    def dialog_keywords(self) -> list[str]:
        """获取当前生效的对话框关键字列表"""
        return self._dialog_keywords if self._dialog_keywords is not None else self.DIALOG_TITLE_KEYWORDS

    # ========== 生命周期 ==========

    def start(self):
        """开始监控（进入 transaction）"""
        guard = require_current_job_lock("dialog_guard.start")
        if not guard.get("ok"):
            raise RuntimeError(
                "blocked_by_solidworks_lock: "
                + str({
                    "reason": guard.get("reason", ""),
                    "owner": guard.get("owner", {}),
                    "fix_suggestion": guard.get("fix_suggestion", ""),
                })
            )
        if self._thread is not None and self._thread.is_alive():
            return  # 已在运行

        self._stop_event.clear()
        self._active = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="DialogGuard",
        )
        self._thread.start()

    def stop(self, timeout_s: float = 3.0):
        """停止监控（退出 transaction）"""
        self._active = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout_s)
            self._thread = None

    @property
    def is_active(self) -> bool:
        """是否正在监控"""
        return self._active

    # ========== 监控逻辑 ==========

    def _monitor_loop(self):
        """监控循环（后台线程）"""
        try:
            import win32gui
            import win32con
            import win32process
        except ImportError:
            self._record_action(
                0, "", "", 0, "error", "win32gui not available"
            )
            return

        while not self._stop_event.is_set():
            try:
                dismissed_this_round = []

                def enum_callback(hwnd, _):
                    if not win32gui.IsWindowVisible(hwnd):
                        return True

                    try:
                        # PID 过滤
                        if self.sw_pid is not None:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            if pid != self.sw_pid:
                                return True

                        title = win32gui.GetWindowText(hwnd)
                        if not title:
                            return True

                        # 获取窗口类
                        try:
                            wnd_class = win32gui.GetClassName(hwnd)
                        except Exception:
                            wnd_class = ""

                        # 精确匹配：标题包含关键字 + 类为标准对话框
                        is_target = False
                        for kw in self.dialog_keywords:  # 使用实例属性
                            if kw in title:
                                # 如果有类名，检查是否为对话框类
                                if wnd_class and wnd_class != self.DIALOG_CLASS:
                                    # 标题匹配但类不匹配，记录但跳过
                                    self._record_action(
                                        hwnd, title, wnd_class, self.sw_pid or 0,
                                        "skipped",
                                        f"标题匹配'{kw}'但类={wnd_class}≠{self.DIALOG_CLASS}"
                                    )
                                    return True
                                is_target = True
                                break

                        if is_target:
                            # 关闭前回调（用于 dry_run 等场景）
                            if self._dismiss_hook is not None:
                                try:
                                    should_dismiss = self._dismiss_hook(hwnd, title)
                                    if not should_dismiss:
                                        self._record_action(
                                            hwnd, title, wnd_class, self.sw_pid or 0,
                                            "skipped", "dismiss_hook 返回 False"
                                        )
                                        return True
                                except Exception as e:
                                    self._record_action(
                                        hwnd, title, wnd_class, self.sw_pid or 0,
                                        "error", f"dismiss_hook 异常: {e}"
                                    )
                                    return True

                            # 发送 Enter 键关闭对话框
                            win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                            win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
                            dismissed_this_round.append(hwnd)
                            self._record_action(
                                hwnd, title, wnd_class, self.sw_pid or 0,
                                "dismissed", "PostMessage VK_RETURN"
                            )
                    except Exception as e:
                        self._record_action(
                            0, "", "", 0, "error", f"enum_callback 异常: {e}"
                        )
                    return True

                win32gui.EnumWindows(enum_callback, None)

            except Exception:
                pass

            time.sleep(self.POLL_INTERVAL_S)

    def _record_action(
        self,
        hwnd: int,
        title: str,
        window_class: str,
        pid: int,
        action: str,
        reason: str = "",
    ):
        """记录动作"""
        event = DialogAction(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}",
            hwnd=hwnd,
            title=title,
            window_class=window_class,
            pid=pid,
            action=action,
            reason=reason,
        )
        with self._lock:
            self._actions.append(event)

    # ========== 查询 ==========

    def get_log(self) -> list[dict]:
        """获取所有动作记录"""
        with self._lock:
            return [asdict(a) for a in self._actions]

    def get_summary(self) -> dict:
        """获取汇总"""
        with self._lock:
            actions = list(self._actions)

        dismissed = [a for a in actions if a.action == "dismissed"]
        skipped = [a for a in actions if a.action == "skipped"]
        errors = [a for a in actions if a.action == "error"]

        return {
            "total_actions": len(actions),
            "dialogs_dismissed": len(dismissed),
            "dialogs_skipped": len(skipped),
            "errors": len(errors),
            "dismissed_titles": list(set(a.title for a in dismissed)),
            "skipped_titles": list(set(a.title for a in skipped)),
            "sw_pid": self.sw_pid,
            "run_id": self.run_id,
        }

    def save_log(self, out_dir):
        """保存日志到 run_dir/qc/dialog_guard.json"""
        from pathlib import Path
        import json

        out_dir = Path(out_dir)
        qc_dir = out_dir / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "run_id": self.run_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sw_pid": self.sw_pid,
            "summary": self.get_summary(),
            "actions": self.get_log(),
        }

        out_path = qc_dir / "dialog_guard.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out_path


# ========== Context Manager 支持 ==========

class DialogGuardContext:
    """DialogGuard 上下文管理器

    使用方式:
        with DialogGuardContext(sw_pid=12345) as guard:
            doc.AddDimension2(x, y, 0)
        print(guard.get_summary())
    """

    def __init__(self, sw_pid: Optional[int] = None, run_dir=None, run_id: str = ""):
        self.guard = DialogGuard(sw_pid=sw_pid, run_dir=run_dir, run_id=run_id)

    def __enter__(self) -> DialogGuard:
        self.guard.start()
        return self.guard

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.guard.stop()
        if self.guard.run_dir:
            self.guard.save_log(self.guard.run_dir)
        return False
