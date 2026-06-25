"""v2.3 Task 5: 证据融合

将来自多个源(geometry_qc/ocr/yolo_obb/template/llm_review)的 issues 进行融合:
  - 相同 key 的 issues 合并
  - 取最高 confidence
  - 选择最精确(面积最小)的 bbox
  - 聚合所有证据
  - 从最佳来源获取 fix_suggestion
"""
from __future__ import annotations

from typing import Optional


class EvidenceFusion:
    """证据融合器"""

    def __init__(self):
        pass

    def fuse_issues(self, issues_from_sources: dict[str, list[dict]]) -> list[dict]:
        """融合来自多个来源的 issues

        Args:
            issues_from_sources: {source_name: [issue_dict, ...]}
                例如: {"geometry_qc": [...], "ocr": [...], "yolo_obb": [...]}

        Returns:
            融合后的 issues 列表
        """
        # 按 key 分组
        key_groups: dict[str, list[dict]] = {}
        for source_name, issues in issues_from_sources.items():
            for issue in issues:
                key = issue.get("key", "unknown")
                if key not in key_groups:
                    key_groups[key] = []
                # 确保 issue 有 source 字段
                issue_copy = dict(issue)
                if "source" not in issue_copy:
                    issue_copy["source"] = source_name
                key_groups[key].append(issue_copy)

        # 对每个 key 进行融合
        fused: list[dict] = []
        for key, group in key_groups.items():
            merged = self._merge_key(group)
            fused.append(merged)

        return fused

    def _merge_key(self, issues: list[dict]) -> dict:
        """融合具有相同 key 的多个 issues

        Args:
            issues: 相同 key 的 issue 列表

        Returns:
            融合后的单个 issue
        """
        if len(issues) == 1:
            result = dict(issues[0])
            # 确保有 evidence 字段
            if "evidence" not in result:
                result["evidence"] = []
            return result

        # 取最高 confidence
        best_confidence = max(i.get("confidence", 0.0) for i in issues)

        # 收集所有 bboxes
        bboxes = [i.get("bbox", [0, 0, 0, 0]) for i in issues]
        best_bbox = self._select_best_bbox(bboxes)

        # 聚合证据
        all_evidence: list[dict] = []
        for issue in issues:
            # 已有的 evidence
            for ev in issue.get("evidence", []):
                all_evidence.append(ev)
            # 将 issue 本身也作为证据
            all_evidence.append({
                "source": issue.get("source", "unknown"),
                "severity": issue.get("severity", "info"),
                "confidence": issue.get("confidence", 0.0),
                "description": issue.get("description", ""),
            })

        # 取最高 severity
        severity_order = {"critical": 4, "major": 3, "minor": 2, "info": 1}
        best_severity = "info"
        best_sev_rank = 0
        for issue in issues:
            sev = issue.get("severity", "info")
            rank = severity_order.get(sev, 0)
            if rank > best_sev_rank:
                best_sev_rank = rank
                best_severity = sev

        # 取最佳来源的 fix_suggestion (最高 confidence 的)
        best_issue = max(issues, key=lambda i: i.get("confidence", 0.0))
        fix_suggestion = best_issue.get("fix_suggestion", "")

        # 取最佳来源的 description
        description = best_issue.get("description", "")

        # 合并所有来源
        sources = list(set(i.get("source", "unknown") for i in issues))

        return {
            "key": issues[0].get("key", "unknown"),
            "severity": best_severity,
            "bbox": best_bbox,
            "source": "/".join(sources),
            "confidence": best_confidence,
            "fix_suggestion": fix_suggestion,
            "evidence": all_evidence,
            "human_review": issues[0].get("human_review", "pending"),
            "description": description,
        }

    def _select_best_bbox(self, bboxes: list[list[float]]) -> list[float]:
        """选择最精确(面积最小)的 bbox

        Args:
            bboxes: bbox 列表, 每个 bbox 为 [x, y, w, h]

        Returns:
            面积最小的 bbox
        """
        if not bboxes:
            return [0.0, 0.0, 0.0, 0.0]

        def _area(bbox: list[float]) -> float:
            if len(bbox) < 4:
                return 0.0
            w = bbox[2] if bbox[2] > 0 else 0.0
            h = bbox[3] if bbox[3] > 0 else 0.0
            return w * h

        # 过滤掉全零 bbox
        non_zero = [b for b in bboxes if _area(b) > 0]
        if not non_zero:
            return bboxes[0] if bboxes else [0.0, 0.0, 0.0, 0.0]

        # 返回面积最小的
        return min(non_zero, key=_area)
