"""v2.3 Task 5: 误报过滤器

通过规则引擎将已知误报降级或标记为过滤:
  - 标题栏边缘碰撞 <= 2.0mm 降级为 info
  - 标准件(fastener/spring/purchased_part)不需要 datum/ra
  - 支持自定义规则

规则匹配:
  - pattern: 精确匹配或正则匹配 issue key
  - condition: 可选条件表达式 (如 "overlap_x_mm <= 2.0")
  - new_severity: 降级目标严重级别
  - category_filter: 可选, 仅对特定零件类别生效
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FalsePositiveRule:
    """误报过滤规则"""
    pattern: str  # 正则或精确匹配 issue key
    condition: str  # 可选条件, 如 "overlap_x_mm <= 2.0"
    new_severity: str  # 降级到此严重级别, 如 "info"
    reason: str
    category_filter: Optional[str] = None  # 仅对此零件类别生效


# 内置默认规则
DEFAULT_RULES: list[FalsePositiveRule] = [
    FalsePositiveRule(
        pattern="titlebar_collision",
        condition="overlap_x_mm <= 2.0",
        new_severity="info",
        reason="标题栏边缘碰撞 <= 2.0mm 属于可接受范围",
    ),
    FalsePositiveRule(
        pattern="missing_datum",
        condition="",
        new_severity="info",
        reason="标准件不需要基准标注",
        category_filter="fastener|spring|purchased_part",
    ),
    FalsePositiveRule(
        pattern="missing_ra",
        condition="",
        new_severity="info",
        reason="标准件不需要粗糙度标注",
        category_filter="fastener|spring|purchased_part",
    ),
]


class VisionFalsePositiveFilter:
    """误报过滤器"""

    def __init__(self, custom_rules: Optional[list[FalsePositiveRule]] = None):
        """初始化过滤器

        Args:
            custom_rules: 自定义规则列表, 会与 DEFAULT_RULES 合并
        """
        self.rules: list[FalsePositiveRule] = list(DEFAULT_RULES)
        if custom_rules:
            self.rules.extend(custom_rules)

    def filter_issues(self, issues: list[dict], part_category: str = "") -> list[dict]:
        """过滤 issues 列表

        Args:
            issues: 原始 issues 列表
            part_category: 零件类别

        Returns:
            过滤后的 issues 列表(已降级的 issue 仍保留, 但 severity 已调整)
        """
        filtered: list[dict] = []

        for issue in issues:
            issue_key = issue.get("key", "")
            matched = False

            for rule in self.rules:
                if not self._match_pattern(rule.pattern, issue_key):
                    continue

                # 检查类别过滤
                if rule.category_filter:
                    if not part_category or not re.search(rule.category_filter, part_category, re.IGNORECASE):
                        continue

                # 检查条件
                if rule.condition and not self._eval_condition(rule.condition, issue):
                    continue

                # 匹配成功, 降级 severity
                old_severity = issue.get("severity", "info")
                issue_copy = dict(issue)
                issue_copy["severity"] = rule.new_severity
                issue_copy["filter_reason"] = rule.reason
                issue_copy["original_severity"] = old_severity
                filtered.append(issue_copy)
                matched = True
                break

            if not matched:
                filtered.append(issue)

        return filtered

    def add_rule(self, rule: FalsePositiveRule):
        """添加规则

        Args:
            rule: 要添加的规则
        """
        self.rules.append(rule)

    def remove_rule(self, pattern: str):
        """移除匹配 pattern 的规则

        Args:
            pattern: 规则的 pattern 字段
        """
        self.rules = [r for r in self.rules if r.pattern != pattern]

    def save_custom_rules(self, path: Path):
        """保存自定义规则到 JSON

        Args:
            path: 输出文件路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # 只保存非默认规则
        default_patterns = {r.pattern for r in DEFAULT_RULES}
        custom = [
            {
                "pattern": r.pattern,
                "condition": r.condition,
                "new_severity": r.new_severity,
                "reason": r.reason,
                "category_filter": r.category_filter,
            }
            for r in self.rules
            if r.pattern not in default_patterns
        ]

        path.write_text(
            json.dumps(custom, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_custom_rules(self, path: Path):
        """从 JSON 加载自定义规则

        Args:
            path: 规则文件路径
        """
        path = Path(path)
        if not path.exists():
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data:
                rule = FalsePositiveRule(
                    pattern=item.get("pattern", ""),
                    condition=item.get("condition", ""),
                    new_severity=item.get("new_severity", "info"),
                    reason=item.get("reason", ""),
                    category_filter=item.get("category_filter"),
                )
                self.add_rule(rule)
        except Exception:
            pass

    def _match_pattern(self, pattern: str, issue_key: str) -> bool:
        """匹配 pattern 与 issue_key

        支持精确匹配和正则匹配
        """
        # 先尝试精确匹配
        if pattern == issue_key:
            return True
        # 再尝试正则
        try:
            return bool(re.match(pattern, issue_key))
        except re.error:
            return False

    def _eval_condition(self, condition: str, issue: dict) -> bool:
        """评估条件表达式

        支持简单的比较表达式, 如 "overlap_x_mm <= 2.0"

        Args:
            condition: 条件字符串
            issue: issue 字典

        Returns:
            条件是否满足
        """
        if not condition:
            return True

        # 解析 "field op value" 格式
        match = re.match(r'(\w+)\s*(<=|>=|<|>|==|!=)\s*([\d.]+)', condition)
        if not match:
            return True  # 无法解析则默认通过

        field_name = match.group(1)
        op = match.group(2)
        threshold = float(match.group(3))

        # 从 issue 中获取字段值
        actual_value = issue.get(field_name)
        if actual_value is None:
            # 尝试从 evidence 中获取
            for ev in issue.get("evidence", []):
                if field_name in ev:
                    actual_value = ev[field_name]
                    break

        if actual_value is None:
            return True  # 字段不存在则默认通过

        try:
            actual = float(actual_value)
        except (ValueError, TypeError):
            return True

        # 评估
        if op == "<=":
            return actual <= threshold
        elif op == ">=":
            return actual >= threshold
        elif op == "<":
            return actual < threshold
        elif op == ">":
            return actual > threshold
        elif op == "==":
            return actual == threshold
        elif op == "!=":
            return actual != threshold

        return True
