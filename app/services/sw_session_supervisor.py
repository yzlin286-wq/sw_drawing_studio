"""v2.3 Task 2+3: SW Session Supervisor (增强版)

统一所有 SolidWorks COM 获取、OpenDoc6、ActivateDoc3、SaveAs、CloseDoc。
提供 transaction 状态机、timeout、retry、recover、restart 策略。
集成 v2.3 组件：SwWatchdog（进程健康监控）、SwRecoveryPolicy（恢复策略决策）、
DialogGuardV2（对话框守卫增强版）。
输出 sw_session.json 记录所有事件。

状态机:
    IDLE → CONNECTING → ACTIVE → IN_TRANSACTION → RECOVERING → ACTIVE
                                            ↓
                                      RESTARTING → CONNECTING → ACTIVE
                                            ↓
                                          FAILED

使用方式:
    from app.services.sw_session_supervisor import SwSessionSupervisor
    sup = SwSessionSupervisor(run_dir=run_dir, run_id=run_id)
    sup.setup_watchdog(hang_threshold_s=60.0)
    sup.setup_recovery()
    sw = sup.connect()
    sup.begin_transaction("OpenDoc", dialog_guard_titles=["修改"])
    doc = sup.open_doc(part_path, doc_type=1)
    sup.end_transaction("OpenDoc")
    sup.save_as(doc, out_path)
    sup.close_doc(doc)
    sup.disconnect()
    print(sup.get_full_status())
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from app.services.sw_watchdog import SwWatchdog, WatchdogState
from app.services.sw_recovery_policy import SwRecoveryPolicy, RecoveryPolicy, RecoveryAction
from app.services.sw_dialog_guard import DialogGuardV2
from app.services.solidworks_global_lock import require_current_job_lock


class SessionState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    ACTIVE = "active"
    IN_TRANSACTION = "in_transaction"
    RECOVERING = "recovering"
    RESTARTING = "restarting"
    FAILED = "failed"
    DISCONNECTED = "disconnected"


@dataclass
class TransactionEvent:
    """单个 transaction 事件记录"""
    timestamp: str
    action: str  # connect / open_doc / activate_doc / save_as / close_doc / recover / restart / timeout
    target: str = ""  # 文件路径或对象名
    attempt: int = 1
    success: bool = False
    duration_ms: int = 0
    reason: str = ""
    state_before: str = ""
    state_after: str = ""


@dataclass
class SessionStats:
    """session 统计"""
    total_transactions: int = 0
    successful_transactions: int = 0
    failed_transactions: int = 0
    total_retries: int = 0
    total_recoveries: int = 0
    total_restarts: int = 0
    total_timeouts: int = 0
    connect_count: int = 0
    restart_count: int = 0


class SwSessionSupervisor:
    """SolidWorks Session 统一管理器

    所有 SW COM 操作应通过本类进行，确保：
    1. 统一 SW 对象获取（GetActiveObject 优先 + Dispatch fallback）
    2. OpenDoc6 / ActivateDoc3 / SaveAs / CloseDoc 带 retry
    3. transaction 状态机跟踪
    4. timeout 防止永久挂起
    5. recover / restart 策略
    6. sw_session.json 记录所有事件
    """

    # 默认配置
    DEFAULT_TIMEOUT_S = 60  # 单次 COM 调用 timeout
    DEFAULT_OPEN_DOC_RETRIES = 3
    DEFAULT_SAVE_RETRIES = 2
    DEFAULT_ACTIVATE_RETRIES = 2
    DEFAULT_RECOVER_WAIT_S = 3.0
    DEFAULT_RESTART_WAIT_S = 8.0
    DEFAULT_DISPATCH_WAIT_S = 2.0

    def __init__(
        self,
        run_dir: Optional[Path] = None,
        run_id: str = "",
        visible: bool = False,
        auto_restart: bool = True,
        max_restarts: int = 3,
    ):
        self.run_dir = Path(run_dir) if run_dir else None
        self.run_id = run_id
        self.visible = visible
        self.auto_restart = auto_restart
        self.max_restarts = max_restarts

        self._sw = None
        self._state = SessionState.IDLE
        self._lock = threading.RLock()
        self._events: list[TransactionEvent] = []
        self._stats = SessionStats()
        self._restart_count = 0
        self._sw_pid: Optional[int] = None
        self._opened_docs: set[str] = set()

        # v2.3 组件（延迟初始化）
        self._watchdog: Optional[SwWatchdog] = None
        self._recovery_policy: Optional[SwRecoveryPolicy] = None
        self._dialog_guard: Optional[DialogGuardV2] = None
        self._transactions: dict[str, dict] = {}  # 事务记录 {name: {start, end, ...}}

    # ========== v2.3 组件配置 ==========

    def setup_watchdog(self, hang_threshold_s: float = 60.0):
        """配置并启用 SW 进程健康监控

        Args:
            hang_threshold_s: 判定 SW 挂起的阈值（秒）
        """
        self._watchdog = SwWatchdog(
            sw_pid=self._sw_pid,
            hang_threshold_s=hang_threshold_s,
        )
        # 设置回调
        self._watchdog.set_hung_callback(self._on_sw_hung)
        self._watchdog.set_recovery_callback(self._on_sw_needs_recovery)
        # 设置 COM 检查函数
        self._watchdog.set_com_check_func(self._check_sw_com_responsive)

    def setup_recovery(self, policy: Optional[RecoveryPolicy] = None):
        """配置恢复策略

        Args:
            policy: 恢复策略配置。None 时使用默认配置
        """
        self._recovery_policy = SwRecoveryPolicy(policy=policy)

    def begin_transaction(self, name: str, dialog_guard_titles: Optional[list] = None):
        """开始事务（启用 DialogGuard）

        Args:
            name: 事务名称（如 "OpenDoc", "SaveAs", "AddDimension"）
            dialog_guard_titles: 对话框标题白名单。None 时使用默认值
        """
        # 停止旧的 dialog_guard（如果存在且活跃）
        if self._dialog_guard is not None and self._dialog_guard.is_active:
            self._dialog_guard.stop()

        # 记录事务开始
        self._transactions[name] = {
            "start_time": time.time(),
            "stage": name,
            "completed": False,
        }

        # 创建并启动 DialogGuard
        if self._sw_pid is not None:
            self._dialog_guard = DialogGuardV2(
                sw_pid=self._sw_pid,
                run_dir=self.run_dir,
                run_id=self.run_id,
                whitelist=dialog_guard_titles,
            )
            self._dialog_guard.start(stage=name)

    def end_transaction(self, name: str):
        """结束事务（停止 DialogGuard）

        Args:
            name: 事务名称
        """
        # 停止 DialogGuard
        if self._dialog_guard is not None and self._dialog_guard.is_active:
            self._dialog_guard.stop()
            # 保存日志
            if self.run_dir is not None:
                self._dialog_guard.save_log(self.run_dir)

        # 记录事务结束
        if name in self._transactions:
            self._transactions[name]["end_time"] = time.time()
            self._transactions[name]["completed"] = True

    def get_full_status(self) -> dict:
        """获取完整状态（supervisor + watchdog + recovery + dialog_guard）

        Returns:
            包含所有组件状态的字典
        """
        status = {
            "supervisor": {
                "state": self._state.value,
                "sw_pid": self._sw_pid,
                "is_alive": self.is_alive(),
                "stats": asdict(self._stats),
                "restart_count": self._restart_count,
                "opened_docs": list(self._opened_docs),
                "transactions": self._transactions,
            },
        }

        # 添加 watchdog 状态
        if self._watchdog is not None:
            status["watchdog"] = self._watchdog.get_status()

        # 添加 recovery 统计
        if self._recovery_policy is not None:
            status["recovery"] = self._recovery_policy.get_stats()

        # 添加 dialog_guard 摘要
        if self._dialog_guard is not None:
            status["dialog_guard"] = self._dialog_guard.get_summary()

        return status

    def _on_sw_hung(self, status: dict):
        """SW 挂起回调"""
        self._record_event(
            "sw_hung",
            reason=f"hang_duration={status.get('hang_duration', 0):.2f}s",
        )

    def _on_sw_needs_recovery(self):
        """SW 需要恢复回调"""
        # 触发恢复流程
        self._recover("watchdog_triggered")

    def _check_sw_com_responsive(self) -> bool:
        """检查 SW COM 是否可响应（供 watchdog 调用）"""
        return self.is_alive()

    # ========== 状态机 ==========

    @property
    def state(self) -> SessionState:
        with self._lock:
            return self._state

    def _set_state(self, new_state: SessionState):
        """切换状态（线程安全）"""
        with self._lock:
            old = self._state
            self._state = new_state
        return old

    def _record_event(
        self,
        action: str,
        target: str = "",
        attempt: int = 1,
        success: bool = False,
        duration_ms: int = 0,
        reason: str = "",
        state_before: str = "",
        state_after: str = "",
    ):
        """记录 transaction 事件"""
        event = TransactionEvent(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            action=action,
            target=target,
            attempt=attempt,
            success=success,
            duration_ms=duration_ms,
            reason=reason,
            state_before=state_before or self._state.value,
            state_after=state_after or self._state.value,
        )
        with self._lock:
            self._events.append(event)
            self._stats.total_transactions += 1
            if success:
                self._stats.successful_transactions += 1
            else:
                self._stats.failed_transactions += 1

    def _require_global_lock(self, operation: str) -> None:
        guard = require_current_job_lock(f"sw_session_supervisor.{operation}")
        if guard.get("ok"):
            return
        raise RuntimeError(
            "blocked_by_solidworks_lock: "
            + json.dumps({
                "operation": operation,
                "reason": guard.get("reason", ""),
                "owner": guard.get("owner", {}),
                "fix_suggestion": guard.get("fix_suggestion", ""),
            }, ensure_ascii=False)
        )

    # ========== 连接管理 ==========

    def connect(self) -> Any:
        """连接到 SolidWorks（GetActiveObject 优先，Dispatch fallback）

        Returns:
            sw: SolidWorks Application COM 对象
        Raises:
            RuntimeError: 连接失败
        """
        self._require_global_lock("connect")
        state_before = self._set_state(SessionState.CONNECTING)
        start = time.time()

        try:
            sw = self._try_get_active_object()
            if sw is None:
                sw = self._try_dispatch()

            if sw is None:
                self._set_state(SessionState.FAILED)
                self._record_event(
                    "connect", attempt=1, success=False,
                    duration_ms=int((time.time() - start) * 1000),
                    reason="GetActiveObject 和 Dispatch 均失败",
                    state_before=state_before.value,
                    state_after=SessionState.FAILED.value,
                )
                raise RuntimeError("无法连接 SolidWorks: GetActiveObject 和 Dispatch 均失败")

            # 配置 SW
            try:
                sw.Visible = self.visible
            except Exception:
                pass  # Visible 设置失败不阻断

            # 获取 PID
            self._sw_pid = self._get_sw_pid(sw)

            self._sw = sw
            self._set_state(SessionState.ACTIVE)
            with self._lock:
                self._stats.connect_count += 1

            # v2.3: 启动 watchdog（如果已配置）
            if self._watchdog is not None:
                self._watchdog.sw_pid = self._sw_pid
                self._watchdog.start()

            self._record_event(
                "connect", attempt=1, success=True,
                duration_ms=int((time.time() - start) * 1000),
                reason=f"pid={self._sw_pid}, visible={self.visible}",
                state_before=state_before.value,
                state_after=SessionState.ACTIVE.value,
            )
            return sw

        except RuntimeError:
            raise
        except Exception as e:
            self._set_state(SessionState.FAILED)
            self._record_event(
                "connect", attempt=1, success=False,
                duration_ms=int((time.time() - start) * 1000),
                reason=f"异常: {e}",
                state_before=state_before.value,
                state_after=SessionState.FAILED.value,
            )
            raise RuntimeError(f"连接 SolidWorks 异常: {e}")

    def _try_get_active_object(self) -> Optional[Any]:
        """尝试 GetActiveObject"""
        try:
            import win32com.client as wc
            return wc.GetActiveObject("SldWorks.Application")
        except Exception:
            return None

    def _try_dispatch(self) -> Optional[Any]:
        """尝试 Dispatch 创建新实例"""
        try:
            import win32com.client as wc
            sw = wc.Dispatch("SldWorks.Application")
            time.sleep(self.DEFAULT_DISPATCH_WAIT_S)
            return sw
        except Exception:
            return None

    def _get_sw_pid(self, sw) -> Optional[int]:
        """获取 SW 进程 PID"""
        try:
            # 通过窗口标题查找 PID（fallback）
            import win32gui
            import win32process

            def find_sw_hwnd():
                result = [None]
                def callback(hwnd, _):
                    title = win32gui.GetWindowText(hwnd)
                    if "SOLIDWORKS" in title:
                        result[0] = hwnd
                        return False
                    return True
                win32gui.EnumWindows(callback, None)
                return result[0]

            hwnd = find_sw_hwnd()
            if hwnd:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                return pid
        except Exception:
            pass
        return None

    def disconnect(self):
        """断开连接（不杀进程，仅释放 COM 引用）"""
        state_before = self._set_state(SessionState.DISCONNECTED)
        start = time.time()

        # v2.3: 停止 watchdog
        if self._watchdog is not None:
            self._watchdog.stop()

        # 停止 dialog_guard
        if self._dialog_guard is not None and self._dialog_guard.is_active:
            self._dialog_guard.stop()

        # 关闭所有已打开的文档
        for doc_path in list(self._opened_docs):
            try:
                self.close_doc(doc_path, suppress_error=True)
            except Exception:
                pass

        self._sw = None
        self._sw_pid = None
        self._record_event(
            "disconnect", success=True,
            duration_ms=int((time.time() - start) * 1000),
            state_before=state_before.value,
            state_after=SessionState.DISCONNECTED.value,
        )

    # ========== 文档操作 ==========

    def open_doc(
        self,
        path: str,
        doc_type: int = 1,  # 1=part, 2=assembly, 3=drawing
        options: int = 273,  # 1|16|256 silent+override+readonly
        retries: Optional[int] = None,
        timeout_s: Optional[float] = None,
    ) -> Any:
        """打开文档（带 retry 和 timeout）

        Args:
            path: 文档绝对路径
            doc_type: 1=part, 2=assembly, 3=drawing
            options: OpenDoc6 options bitmask
            retries: 重试次数（默认 DEFAULT_OPEN_DOC_RETRIES）
            timeout_s: 单次调用 timeout（默认 DEFAULT_TIMEOUT_S）

        Returns:
            doc: 文档 COM 对象
        Raises:
            RuntimeError: 打开失败
        """
        if self._sw is None:
            raise RuntimeError("SW 未连接，请先调用 connect()")
        self._require_global_lock("open_doc")

        retries = retries if retries is not None else self.DEFAULT_OPEN_DOC_RETRIES
        timeout_s = timeout_s or self.DEFAULT_TIMEOUT_S

        state_before = self._set_state(SessionState.IN_TRANSACTION)
        start = time.time()
        abs_path = str(Path(path).resolve())

        last_error = ""
        for attempt in range(1, retries + 1):
            try:
                doc = self._open_doc_with_timeout(
                    abs_path, doc_type, options, timeout_s
                )
                if doc is not None:
                    self._opened_docs.add(abs_path)
                    self._set_state(SessionState.ACTIVE)
                    self._record_event(
                        "open_doc", target=abs_path, attempt=attempt, success=True,
                        duration_ms=int((time.time() - start) * 1000),
                        state_before=state_before.value,
                        state_after=SessionState.ACTIVE.value,
                    )
                    # v2.3: 记录恢复策略成功
                    if self._recovery_policy is not None:
                        self._recovery_policy.record_action(RecoveryAction.RETRY, success=True)
                    return doc

                last_error = "OpenDoc6 返回 None"
            except _TimeoutError as e:
                last_error = f"timeout: {e}"
                with self._lock:
                    self._stats.total_timeouts += 1
            except Exception as e:
                last_error = f"异常: {e}"

            # v2.3: 使用 recovery policy 决策
            if self._recovery_policy is not None:
                failure_type = "open_doc_timeout" if "timeout" in last_error else "com_error"
                action = self._recovery_policy.decide(failure_type, {"file": abs_path})
                self._recovery_policy.record_action(action, success=False)

                if action == RecoveryAction.SKIP_JOB:
                    self._set_state(SessionState.ACTIVE)
                    self._record_event(
                        "open_doc", target=abs_path, attempt=attempt, success=False,
                        duration_ms=int((time.time() - start) * 1000),
                        reason=f"recovery policy 决定跳过: {last_error}",
                        state_before=state_before.value,
                        state_after=SessionState.ACTIVE.value,
                    )
                    raise RuntimeError(f"打开文档跳过 ({abs_path}): {last_error}")
                elif action == RecoveryAction.ABORT:
                    self._set_state(SessionState.FAILED)
                    self._record_event(
                        "open_doc", target=abs_path, attempt=attempt, success=False,
                        duration_ms=int((time.time() - start) * 1000),
                        reason=f"recovery policy 决定终止: {last_error}",
                        state_before=state_before.value,
                        state_after=SessionState.FAILED.value,
                    )
                    raise RuntimeError(f"打开文档终止 ({abs_path}): {last_error}")
                elif action == RecoveryAction.RECOVER_SESSION:
                    self._recover(f"open_doc recovery: {last_error}")
                    continue
                elif action == RecoveryAction.RESTART_SW:
                    if not self._restart_sw(abs_path):
                        # restart 失败，无法继续
                        self._set_state(SessionState.FAILED)
                        self._record_event(
                            "open_doc", target=abs_path, attempt=attempt, success=False,
                            duration_ms=int((time.time() - start) * 1000),
                            reason=f"restart_sw 失败: {last_error}",
                            state_before=state_before.value,
                            state_after=SessionState.FAILED.value,
                        )
                        raise RuntimeError(f"重启 SW 失败 ({abs_path}): {last_error}")
                    continue
                # RETRY: 继续原有逻辑
                delay = self._recovery_policy.get_delay_for_action(action)
                if delay > 0:
                    time.sleep(delay)

            # retry 前的 recover（原有逻辑，仅在无 recovery policy 时执行）
            if attempt < retries and self._recovery_policy is None:
                with self._lock:
                    self._stats.total_retries += 1
                self._recover(f"open_doc retry attempt {attempt + 1}")

        # 所有 retry 失败，尝试 restart
        self._set_state(SessionState.FAILED)
        self._record_event(
            "open_doc", target=abs_path, attempt=retries, success=False,
            duration_ms=int((time.time() - start) * 1000),
            reason=f"重试 {retries} 次后失败: {last_error}",
            state_before=state_before.value,
            state_after=SessionState.FAILED.value,
        )

        # 尝试 restart 后再 open 一次
        if self.auto_restart and self._restart_count < self.max_restarts:
            recovered = self._restart_sw(abs_path)
            if recovered:
                # restart 后再试一次
                try:
                    doc = self._open_doc_with_timeout(
                        abs_path, doc_type, options, timeout_s
                    )
                    if doc is not None:
                        self._opened_docs.add(abs_path)
                        self._set_state(SessionState.ACTIVE)
                        self._record_event(
                            "open_doc", target=abs_path,
                            attempt=retries + 1, success=True,
                            duration_ms=int((time.time() - start) * 1000),
                            reason="restart 后恢复",
                            state_before=SessionState.ACTIVE.value,
                            state_after=SessionState.ACTIVE.value,
                        )
                        return doc
                except Exception as e:
                    last_error = f"restart 后仍失败: {e}"

        raise RuntimeError(f"打开文档失败 ({abs_path}): {last_error}")

    def _open_doc_with_timeout(
        self, path: str, doc_type: int, options: int, timeout_s: float
    ) -> Any:
        """带 timeout 的 OpenDoc6 调用

        主线程执行 COM 调用，后台 Timer 标记 timeout。
        注意：COM 对象不能跨线程，所以 self._sw 必须在主线程调用。
        如果 timeout 触发，主线程抛出 _TimeoutError。
        """
        import pythoncom
        from win32com.client import VARIANT

        timeout_holder: dict[str, bool] = {"timed_out": False}
        watchdog = threading.Timer(timeout_s, lambda: timeout_holder.__setitem__("timed_out", True))
        watchdog.daemon = True
        watchdog.start()

        try:
            err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            try:
                self._sw.SetUserPreferenceIntegerValue(9, 1)
            except Exception:
                pass
            doc = self._sw.OpenDoc6(path, doc_type, options, "", err, warn)

            watchdog.cancel()

            if timeout_holder["timed_out"]:
                raise _TimeoutError(f"OpenDoc6 超时 ({timeout_s}s)")
            return doc
        except _TimeoutError:
            raise
        except Exception as e:
            watchdog.cancel()
            if timeout_holder["timed_out"]:
                raise _TimeoutError(f"OpenDoc6 超时 ({timeout_s}s): {e}")
            raise

    def activate_doc(
        self,
        name: str,
        retries: Optional[int] = None,
        timeout_s: Optional[float] = None,
    ) -> Any:
        """激活文档（带 retry）"""
        if self._sw is None:
            raise RuntimeError("SW 未连接")
        self._require_global_lock("activate_doc")

        retries = retries if retries is not None else self.DEFAULT_ACTIVATE_RETRIES
        timeout_s = timeout_s or self.DEFAULT_TIMEOUT_S

        state_before = self._set_state(SessionState.IN_TRANSACTION)
        start = time.time()

        last_error = ""
        for attempt in range(1, retries + 1):
            try:
                # ActivateDoc3 优先，ActivateDoc2 fallback
                doc = None
                try:
                    doc = self._sw.ActivateDoc3(name, True, 2, None)  # 2=swRebuildOnActivation
                except Exception:
                    try:
                        doc = self._sw.ActivateDoc2(name, True, 2)
                    except Exception:
                        doc = self._sw.ActivateDoc(name)

                if doc is not None:
                    self._set_state(SessionState.ACTIVE)
                    self._record_event(
                        "activate_doc", target=name, attempt=attempt, success=True,
                        duration_ms=int((time.time() - start) * 1000),
                        state_before=state_before.value,
                        state_after=SessionState.ACTIVE.value,
                    )
                    return doc

                last_error = "ActivateDoc 返回 None"
            except Exception as e:
                last_error = str(e)

            if attempt < retries:
                with self._lock:
                    self._stats.total_retries += 1
                time.sleep(1.0)

        self._set_state(SessionState.ACTIVE)
        self._record_event(
            "activate_doc", target=name, attempt=retries, success=False,
            duration_ms=int((time.time() - start) * 1000),
            reason=last_error,
            state_before=state_before.value,
            state_after=SessionState.ACTIVE.value,
        )
        # activate 失败不抛异常，返回 None（非致命）
        return None

    def save_as(
        self,
        doc: Any,
        out_path: str,
        file_type: int = 0,  # 0=SLDDRW, 1=PDF, 2=DXF, 3=STEP
        retries: Optional[int] = None,
        timeout_s: Optional[float] = None,
        export_data: Any = None,
    ) -> bool:
        """保存文档（带 retry）

        Args:
            doc: 文档 COM 对象
            out_path: 输出路径
            file_type: SW file type
            retries: 重试次数
            timeout_s: timeout
            export_data: swExportFileData 对象（PDF/DXF 导出用）

        Returns:
            True 如果成功
        """
        if self._sw is None:
            raise RuntimeError("SW 未连接")
        self._require_global_lock("save_as")

        retries = retries if retries is not None else self.DEFAULT_SAVE_RETRIES
        timeout_s = timeout_s or self.DEFAULT_TIMEOUT_S

        state_before = self._set_state(SessionState.IN_TRANSACTION)
        start = time.time()
        abs_path = str(Path(out_path).resolve())

        last_error = ""
        for attempt in range(1, retries + 1):
            try:
                # 确保输出目录存在
                Path(abs_path).parent.mkdir(parents=True, exist_ok=True)

                # 激活文档
                try:
                    doc_name = doc.GetTitle()
                    self._sw.ActivateDoc3(doc_name, True, 2, None)
                except Exception:
                    pass

                ext = self._sw
                err = 0
                warn = 0
                import pythoncom
                from win32com.client import VARIANT
                err_var = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                warn_var = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)

                ok = False
                if export_data is not None:
                    ok = doc.Extension.SaveAs(
                        abs_path, file_type, 1, export_data, err_var, warn_var
                    )
                else:
                    ok = doc.Extension.SaveAs(
                        abs_path, file_type, 1, None, err_var, warn_var
                    )

                if ok:
                    self._set_state(SessionState.ACTIVE)
                    self._record_event(
                        "save_as", target=abs_path, attempt=attempt, success=True,
                        duration_ms=int((time.time() - start) * 1000),
                        state_before=state_before.value,
                        state_after=SessionState.ACTIVE.value,
                    )
                    # v2.3: 记录恢复策略成功
                    if self._recovery_policy is not None:
                        self._recovery_policy.record_action(RecoveryAction.RETRY, success=True)
                    return True

                last_error = f"SaveAs 返回 False, err={err_var.value}, warn={warn_var.value}"
            except Exception as e:
                last_error = str(e)

            # v2.3: 使用 recovery policy 决策
            if self._recovery_policy is not None:
                failure_type = "save_as_timeout" if "timeout" in last_error else "com_error"
                action = self._recovery_policy.decide(failure_type, {"file": abs_path})
                self._recovery_policy.record_action(action, success=False)

                if action == RecoveryAction.SKIP_JOB:
                    self._set_state(SessionState.ACTIVE)
                    self._record_event(
                        "save_as", target=abs_path, attempt=attempt, success=False,
                        duration_ms=int((time.time() - start) * 1000),
                        reason=f"recovery policy 决定跳过: {last_error}",
                        state_before=state_before.value,
                        state_after=SessionState.ACTIVE.value,
                    )
                    return False
                elif action == RecoveryAction.ABORT:
                    self._set_state(SessionState.FAILED)
                    self._record_event(
                        "save_as", target=abs_path, attempt=attempt, success=False,
                        duration_ms=int((time.time() - start) * 1000),
                        reason=f"recovery policy 决定终止: {last_error}",
                        state_before=state_before.value,
                        state_after=SessionState.FAILED.value,
                    )
                    return False
                elif action == RecoveryAction.RECOVER_SESSION:
                    self._recover(f"save_as recovery: {last_error}")
                    continue
                elif action == RecoveryAction.RESTART_SW:
                    if not self._restart_sw(abs_path):
                        # restart 失败，无法继续
                        self._set_state(SessionState.FAILED)
                        self._record_event(
                            "save_as", target=abs_path, attempt=attempt, success=False,
                            duration_ms=int((time.time() - start) * 1000),
                            reason=f"restart_sw 失败: {last_error}",
                            state_before=state_before.value,
                            state_after=SessionState.FAILED.value,
                        )
                        return False
                    continue
                # RETRY: 继续原有逻辑
                delay = self._recovery_policy.get_delay_for_action(action)
                if delay > 0:
                    time.sleep(delay)

            # 原有逻辑：retry 前等待
            if attempt < retries and self._recovery_policy is None:
                with self._lock:
                    self._stats.total_retries += 1
                time.sleep(1.5)

        self._set_state(SessionState.ACTIVE)
        self._record_event(
            "save_as", target=abs_path, attempt=retries, success=False,
            duration_ms=int((time.time() - start) * 1000),
            reason=last_error,
            state_before=state_before.value,
            state_after=SessionState.ACTIVE.value,
        )
        return False

    def close_doc(self, doc_or_path: Any, suppress_error: bool = False) -> bool:
        """关闭文档"""
        if self._sw is None:
            if suppress_error:
                return False
            raise RuntimeError("SW 未连接")
        self._require_global_lock("close_doc")

        state_before = self._set_state(SessionState.IN_TRANSACTION)
        start = time.time()

        target = ""
        try:
            if isinstance(doc_or_path, str):
                target = doc_or_path
                self._sw.CloseDoc(doc_or_path)
            else:
                try:
                    target = doc_or_path.GetTitle()
                except Exception:
                    target = "<unknown>"
                self._sw.CloseDoc(target)

            # 从已打开集合移除
            try:
                abs_path = str(Path(target).resolve())
                self._opened_docs.discard(abs_path)
            except Exception:
                pass

            self._set_state(SessionState.ACTIVE)
            self._record_event(
                "close_doc", target=target, attempt=1, success=True,
                duration_ms=int((time.time() - start) * 1000),
                state_before=state_before.value,
                state_after=SessionState.ACTIVE.value,
            )
            return True
        except Exception as e:
            self._set_state(SessionState.ACTIVE)
            self._record_event(
                "close_doc", target=target, attempt=1, success=False,
                duration_ms=int((time.time() - start) * 1000),
                reason=str(e),
                state_before=state_before.value,
                state_after=SessionState.ACTIVE.value,
            )
            if not suppress_error:
                raise
            return False

    # ========== 恢复策略 ==========

    def _recover(self, reason: str = ""):
        """恢复策略：关闭所有文档 + 等待 + 重新连接"""
        state_before = self._set_state(SessionState.RECOVERING)
        start = time.time()
        with self._lock:
            self._stats.total_recoveries += 1

        try:
            # 关闭所有已打开文档
            for doc_path in list(self._opened_docs):
                try:
                    self._sw.CloseDoc(doc_path)
                except Exception:
                    pass
            self._opened_docs.clear()

            # 等待 SW 恢复
            time.sleep(self.DEFAULT_RECOVER_WAIT_S)

            # 验证 SW 仍可响应
            try:
                _ = self._sw.RevisionNumber()
                self._set_state(SessionState.ACTIVE)
                self._record_event(
                    "recover", attempt=1, success=True,
                    duration_ms=int((time.time() - start) * 1000),
                    reason=reason,
                    state_before=state_before.value,
                    state_after=SessionState.ACTIVE.value,
                )
                return True
            except Exception as e:
                self._record_event(
                    "recover", attempt=1, success=False,
                    duration_ms=int((time.time() - start) * 1000),
                    reason=f"SW 无响应: {e}",
                    state_before=state_before.value,
                    state_after=SessionState.FAILED.value,
                )
                return False
        except Exception as e:
            self._record_event(
                "recover", attempt=1, success=False,
                duration_ms=int((time.time() - start) * 1000),
                reason=f"recover 异常: {e}",
                state_before=state_before.value,
                state_after=SessionState.FAILED.value,
            )
            return False

    def _restart_sw(self, context: str = "") -> bool:
        """重启 SW 进程"""
        self._require_global_lock("restart_sw")
        current_lock = require_current_job_lock("sw_session_supervisor.restart_sw")
        lock = current_lock.get("lock") if isinstance(current_lock.get("lock"), dict) else {}
        if not lock.get("allow_restart_sw"):
            self._record_event(
                "restart",
                target=context,
                attempt=1,
                success=False,
                reason="blocked_restart_without_allow_restart_sw",
            )
            return False
        state_before = self._set_state(SessionState.RESTARTING)
        start = time.time()
        with self._lock:
            self._stats.total_restarts += 1
            self._restart_count += 1

        try:
            # 1. 杀掉现有 SW 进程
            self._kill_sw_processes()

            # 2. 等待进程完全退出
            time.sleep(self.DEFAULT_RESTART_WAIT_S)

            # 3. 重新连接
            self._sw = None
            self._opened_docs.clear()

            # 4. Dispatch 创建新实例
            try:
                import win32com.client as wc
                sw = wc.Dispatch("SldWorks.Application")
                time.sleep(self.DEFAULT_DISPATCH_WAIT_S)
                sw.Visible = self.visible
                self._sw = sw
                self._sw_pid = self._get_sw_pid(sw)

                self._set_state(SessionState.ACTIVE)
                # v2.3: 同步 watchdog PID
                if self._watchdog is not None:
                    self._watchdog.sw_pid = self._sw_pid
                    self._watchdog.reset()
                self._record_event(
                    "restart", target=context, attempt=1, success=True,
                    duration_ms=int((time.time() - start) * 1000),
                    reason=f"pid={self._sw_pid}, restart_count={self._restart_count}",
                    state_before=state_before.value,
                    state_after=SessionState.ACTIVE.value,
                )
                return True
            except Exception as e:
                self._set_state(SessionState.FAILED)
                self._record_event(
                    "restart", target=context, attempt=1, success=False,
                    duration_ms=int((time.time() - start) * 1000),
                    reason=f"Dispatch 失败: {e}",
                    state_before=state_before.value,
                    state_after=SessionState.FAILED.value,
                )
                return False
        except Exception as e:
            self._set_state(SessionState.FAILED)
            self._record_event(
                "restart", target=context, attempt=1, success=False,
                duration_ms=int((time.time() - start) * 1000),
                reason=f"restart 异常: {e}",
                state_before=state_before.value,
                state_after=SessionState.FAILED.value,
            )
            return False

    def _kill_sw_processes(self):
        """杀掉所有 SW 进程"""
        for proc_name in ["SLDWORKS.exe", "SLDEXITAPP.exe"]:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc_name, "/T"],
                    capture_output=True,
                    timeout=30,
                )
            except Exception:
                pass

    # ========== 便捷方法 ==========

    @property
    def sw(self) -> Any:
        """获取当前 SW 对象"""
        return self._sw

    @property
    def pid(self) -> Optional[int]:
        """获取 SW 进程 PID"""
        return self._sw_pid

    def is_alive(self) -> bool:
        """检查 SW 是否仍可响应"""
        if self._sw is None:
            return False
        try:
            _ = self._sw.RevisionNumber()
            return True
        except Exception:
            return False

    def get_stats(self) -> SessionStats:
        """获取统计"""
        with self._lock:
            return self._stats

    def get_events(self) -> list[TransactionEvent]:
        """获取所有事件"""
        with self._lock:
            return list(self._events)

    # ========== 输出 ==========

    def save_session_json(self, out_dir: Optional[Path] = None):
        """保存 sw_session.json（包含 v2.3 组件数据）"""
        out_dir = out_dir or self.run_dir
        if out_dir is None:
            return

        out_dir = Path(out_dir)
        qc_dir = out_dir / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)

        # 基础数据
        data = {
            "run_id": self.run_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sw_pid": self._sw_pid,
            "final_state": self._state.value,
            "visible": self.visible,
            "auto_restart": self.auto_restart,
            "max_restarts": self.max_restarts,
            "restart_count": self._restart_count,
            "stats": asdict(self._stats),
            "events": [asdict(e) for e in self._events],
        }

        # v2.3: 添加组件数据
        full_status = self.get_full_status()
        data["v2.3_components"] = {
            "watchdog": full_status.get("watchdog"),
            "recovery": full_status.get("recovery"),
            "dialog_guard": full_status.get("dialog_guard"),
        }

        out_path = qc_dir / "sw_session.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return out_path


class _TimeoutError(Exception):
    """COM 调用超时"""
    pass


# ========== 模块级便捷函数 ==========

def create_supervisor(
    run_dir: Optional[Path] = None,
    run_id: str = "",
    visible: bool = False,
) -> SwSessionSupervisor:
    """创建 Session Supervisor"""
    return SwSessionSupervisor(
        run_dir=run_dir,
        run_id=run_id,
        visible=visible,
    )


def kill_sw_processes():
    """杀掉所有 SW 进程（模块级便捷函数）"""
    for proc_name in ["SLDWORKS.exe", "SLDEXITAPP.exe"]:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc_name, "/T"],
                capture_output=True,
                timeout=30,
            )
        except Exception:
            pass
