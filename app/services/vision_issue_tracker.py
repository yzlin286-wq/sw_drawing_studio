"""v2.3 Task 5: Vision Issue 追踪器

跨运行追踪人工审核决策:
  - mark_false_positive: 标记为已确认的误报
  - mark_confirmed: 标记为已确认的真实问题
  - get_review_status: 获取审核状态
  - apply_decisions: 将存储的决策应用到 issues 列表

持久化: vision_issue_tracker.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


class VisionIssueTracker:
    """Vision Issue 追踪器"""

    def __init__(self, run_dir: Optional[Path] = None):
        """初始化追踪器

        Args:
            run_dir: 运行目录, 用于自动保存/加载
        """
        self.run_dir = Path(run_dir) if run_dir else None
        self._decisions: dict[str, dict] = {}  # key: "{issue_key}::{base_name}" -> decision

    def _make_key(self, issue_key: str, base_name: str) -> str:
        """构造内部存储 key"""
        return f"{issue_key}::{base_name}"

    def mark_false_positive(self, issue_key: str, base_name: str, reason: str = ""):
        """标记为已确认的误报

        Args:
            issue_key: issue 标识
            base_name: 零件名称
            reason: 原因说明
        """
        key = self._make_key(issue_key, base_name)
        self._decisions[key] = {
            "issue_key": issue_key,
            "base_name": base_name,
            "human_review": "confirmed_false_positive",
            "reason": reason,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def mark_confirmed(self, issue_key: str, base_name: str, reason: str = ""):
        """标记为已确认的真实问题

        Args:
            issue_key: issue 标识
            base_name: 零件名称
            reason: 原因说明
        """
        key = self._make_key(issue_key, base_name)
        self._decisions[key] = {
            "issue_key": issue_key,
            "base_name": base_name,
            "human_review": "confirmed_issue",
            "reason": reason,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_review_status(self, issue_key: str, base_name: str) -> str:
        """获取审核状态

        Args:
            issue_key: issue 标识
            base_name: 零件名称

        Returns:
            "pending" / "confirmed_false_positive" / "confirmed_issue"
        """
        key = self._make_key(issue_key, base_name)
        decision = self._decisions.get(key)
        if decision:
            return decision.get("human_review", "pending")
        return "pending"

    def get_all_decisions(self) -> list[dict]:
        """获取所有审核决策

        Returns:
            决策列表
        """
        return list(self._decisions.values())

    def save(self, path: Optional[Path] = None):
        """保存到 vision_issue_tracker.json

        Args:
            path: 保存路径, 默认使用 run_dir 下的路径
        """
        if path is None:
            if self.run_dir:
                path = self.run_dir / "qc" / "vision_issue_tracker.json"
            else:
                return

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "decisions": self._decisions,
        }

        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self, path: Optional[Path] = None):
        """从 vision_issue_tracker.json 加载

        Args:
            path: 加载路径, 默认使用 run_dir 下的路径
        """
        if path is None:
            if self.run_dir:
                path = self.run_dir / "qc" / "vision_issue_tracker.json"
            else:
                return

        path = Path(path)
        if not path.exists():
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._decisions = data.get("decisions", {})
        except Exception:
            pass

    def apply_decisions(self, issues: list[dict], base_name: str) -> list[dict]:
        """将存储的审核决策应用到 issues 列表

        Args:
            issues: issue 列表
            base_name: 零件名称

        Returns:
            应用决策后的 issues 列表(修改了 human_review 字段)
        """
        result: list[dict] = []
        for issue in issues:
            issue_copy = dict(issue)
            issue_key = issue_copy.get("key", "")
            status = self.get_review_status(issue_key, base_name)
            if status != "pending":
                issue_copy["human_review"] = status
            result.append(issue_copy)
        return result
