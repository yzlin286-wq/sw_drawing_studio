"""v2.3 Task 2: SW Recovery Policy 恢复策略

定义统一的恢复动作决策逻辑：
1. retry: 重试当前操作
2. recover_session: 恢复 session（关闭文档 + 等待 + 验证）
3. restart_sw: 重启 SolidWorks 进程
4. skip_job: 跳过当前任务
5. abort: 终止整个流程

决策逻辑（优先级从高到低）:
1. 如果 retry_count < max_retries → retry
2. 如果 recovery_count < max_recoveries → recover_session
3. 如果 restart_count < max_restarts → restart_sw
4. 否则 → skip_job 或 abort（根据 failure_type 决定）

使用方式:
    from app.services.sw_recovery_policy import SwRecoveryPolicy, RecoveryPolicy
    policy = SwRecoveryPolicy(RecoveryPolicy(max_retries=3))
    action = policy.decide("open_doc_timeout", {"file": "part.sldprt"})
    if action == RecoveryAction.retry:
        # 重试
    policy.record_action(action, success=True)
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class RecoveryAction(str, Enum):
    """恢复动作类型"""
    RETRY = "retry"
    RECOVER_SESSION = "recover_session"
    RESTART_SW = "restart_sw"
    SKIP_JOB = "skip_job"
    ABORT = "abort"


@dataclass
class RecoveryPolicy:
    """恢复策略配置"""
    max_retries: int = 3
    max_recoveries: int = 2
    max_restarts: int = 1
    retry_delay_s: float = 5.0
    recover_delay_s: float = 10.0
    restart_delay_s: float = 15.0
    timeout_per_action_s: float = 120.0


@dataclass
class RecoveryStats:
    """恢复统计"""
    total_decisions: int = 0
    retry_count: int = 0
    recover_count: int = 0
    restart_count: int = 0
    skip_count: int = 0
    abort_count: int = 0
    successful_retries: int = 0
    successful_recoveries: int = 0
    successful_restarts: int = 0
    last_action: str = ""
    last_failure_type: str = ""
    last_decision_time: str = ""


class SwRecoveryPolicy:
    """SolidWorks 恢复策略管理器

    根据失败类型和当前计数，决定下一步恢复动作。
    支持多种 failure_type：
    - open_doc_timeout: 打开文档超时
    - save_as_timeout: 保存超时
    - add_dimension_timeout: 添加尺寸超时
    - export_timeout: 导出超时
    - sw_hung: SW 进程挂起
    - com_error: COM 调用错误
    """

    def __init__(self, policy: Optional[RecoveryPolicy] = None):
        """
        Args:
            policy: 恢复策略配置。None 时使用默认配置
        """
        self._policy = policy or RecoveryPolicy()
        self._stats = RecoveryStats()
        self._lock = threading.RLock()

        # 当前计数（可通过 reset() 重置）
        self._retry_count = 0
        self._recover_count = 0
        self._restart_count = 0

    # ========== 决策 ==========

    def decide(self, failure_type: str, context: Optional[dict] = None) -> RecoveryAction:
        """根据失败类型和当前状态决定恢复动作

        Args:
            failure_type: 失败类型（见类文档）
            context: 额外上下文信息（如文件路径、操作名等）

        Returns:
            RecoveryAction: 建议的恢复动作
        """
        context = context or {}

        with self._lock:
            self._stats.total_decisions += 1
            self._stats.last_failure_type = failure_type
            self._stats.last_decision_time = time.strftime("%Y-%m-%d %H:%M:%S")

            # 决策优先级：retry > recover > restart > skip/abort
            if self._retry_count < self._policy.max_retries:
                action = RecoveryAction.RETRY
                self._retry_count += 1
                self._stats.retry_count += 1
            elif self._recover_count < self._policy.max_recoveries:
                action = RecoveryAction.RECOVER_SESSION
                self._recover_count += 1
                self._stats.recover_count += 1
            elif self._restart_count < self._policy.max_restarts:
                action = RecoveryAction.RESTART_SW
                self._restart_count += 1
                self._stats.restart_count += 1
            else:
                # 所有恢复手段用尽，根据 failure_type 决定 skip 或 abort
                # sw_hung 和 com_error 倾向于 abort（严重错误）
                # 其他错误可以 skip_job
                if failure_type in ("sw_hung", "com_error"):
                    action = RecoveryAction.ABORT
                    self._stats.abort_count += 1
                else:
                    action = RecoveryAction.SKIP_JOB
                    self._stats.skip_count += 1

            self._stats.last_action = action.value
            return action

    def record_action(self, action: RecoveryAction, success: bool):
        """记录恢复动作的执行结果

        Args:
            action: 执行的恢复动作
            success: 是否成功
        """
        with self._lock:
            if success:
                if action == RecoveryAction.RETRY:
                    self._stats.successful_retries += 1
                elif action == RecoveryAction.RECOVER_SESSION:
                    self._stats.successful_recoveries += 1
                elif action == RecoveryAction.RESTART_SW:
                    self._stats.successful_restarts += 1

    def reset(self):
        """重置所有计数（保留策略配置）"""
        with self._lock:
            self._retry_count = 0
            self._recover_count = 0
            self._restart_count = 0

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            return {
                "policy": asdict(self._policy),
                "current_counts": {
                    "retry_count": self._retry_count,
                    "recover_count": self._recover_count,
                    "restart_count": self._restart_count,
                },
                "stats": asdict(self._stats),
            }

    @property
    def policy(self) -> RecoveryPolicy:
        """获取策略配置"""
        return self._policy

    @property
    def retry_count(self) -> int:
        with self._lock:
            return self._retry_count

    @property
    def recover_count(self) -> int:
        with self._lock:
            return self._recover_count

    @property
    def restart_count(self) -> int:
        with self._lock:
            return self._restart_count

    # ========== 便捷方法 ==========

    def get_delay_for_action(self, action: RecoveryAction) -> float:
        """获取动作执行前的等待时间

        Args:
            action: 恢复动作

        Returns:
            等待秒数
        """
        if action == RecoveryAction.RETRY:
            return self._policy.retry_delay_s
        elif action == RecoveryAction.RECOVER_SESSION:
            return self._policy.recover_delay_s
        elif action == RecoveryAction.RESTART_SW:
            return self._policy.restart_delay_s
        return 0.0

    def can_retry(self) -> bool:
        """是否还可以重试"""
        with self._lock:
            return self._retry_count < self._policy.max_retries

    def can_recover(self) -> bool:
        """是否还可以恢复 session"""
        with self._lock:
            return self._recover_count < self._policy.max_recoveries

    def can_restart(self) -> bool:
        """是否还可以重启 SW"""
        with self._lock:
            return self._restart_count < self._policy.max_restarts

    # ========== 输出 ==========

    def save(self, path: Path):
        """保存策略和统计到 JSON 文件

        Args:
            path: 输出文件路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            **self.get_stats(),
        }

        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
