"""v2.2 Task 3: Layout Solver v2

候选 layout: T4 / L3 / TWO_VIEW / PURCHASE
候选比例: 5:1 到 1:50
每个候选 Save-Close-Reopen 后用 GetOutline 测量
评分: overlap / out_of_frame / titlebar_collision / utilization / min_gap / readability
输出: layout_solver_v2.json

验收: LB26001_36 view_overlap=0, view_out_of_frame=0, titlebar_collision=0
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from app.services.solidworks_global_lock import require_current_job_lock


class LayoutType(str, Enum):
    T4 = "T4"  # 四视图：前视+俯视+左视+等轴测
    L3 = "L3"  # 三视图L型：前视+俯视+等轴测
    TWO_VIEW = "TWO_VIEW"  # 两视图：前视+等轴测
    PURCHASE = "PURCHASE"  # 采购件：仅等轴测


# A4 横式图框 (297mm x 210mm)，单位：米
FRAME_BOX = (0.010, 0.010, 0.287, 0.200)

# 标题栏区域（右下角）
TITLEBAR_BOX = (0.102, 0.005, 0.282, 0.095)

# 比例梯子（从大到小）
SCALE_LADDER = [
    (5, 1), (2, 1), (1, 1), (1, 2), (1, 5),
    (1, 10), (1, 20), (1, 50),
]

# Layout 候选的视图位置定义（单位：米，A4 横式）
LAYOUT_TEMPLATES = {
    LayoutType.T4: {
        "front": (0.080, 0.140),
        "top":   (0.080, 0.080),
        "right": (0.180, 0.140),
        "iso":   (0.230, 0.180),
    },
    LayoutType.L3: {
        "front": (0.090, 0.130),
        "top":   (0.090, 0.070),
        "iso":   (0.220, 0.130),
    },
    LayoutType.TWO_VIEW: {
        "front": (0.100, 0.130),
        "iso":   (0.220, 0.130),
    },
    LayoutType.PURCHASE: {
        "iso": (0.150, 0.120),
    },
}

# 视图方向映射（SW StandardViewName）
VIEW_ORIENTATIONS = {
    "front": "*Front",
    "top": "*Top",
    "right": "*Right",
    "iso": "*Isometric",
}


@dataclass
class ViewOutline:
    """视图 outline 测量结果"""
    name: str
    outline: tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)
    center: tuple[float, float]
    width: float
    height: float


@dataclass
class LayoutCandidate:
    """单个 layout 候选"""
    layout_type: LayoutType
    scale: tuple[int, int]
    views: dict[str, tuple[float, float]]  # view_name -> (x, y)
    outlines: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0
    issues: list[str] = field(default_factory=list)


@dataclass
class SolverResult:
    """求解结果"""
    success: bool = False
    best_layout: Optional[LayoutType] = None
    best_scale: Optional[tuple[int, int]] = None
    best_candidate: Optional[LayoutCandidate] = None
    all_candidates: list[dict] = field(default_factory=list)
    final_outlines: dict[str, list[float]] = field(default_factory=dict)
    final_scores: dict[str, float] = field(default_factory=dict)
    reason: str = ""
    iterations: int = 0
    duration_ms: int = 0


class LayoutSolverV2:
    """Layout Solver v2

    对每种 layout 类型 × 每种比例，Save-Close-Reopen 后用 GetOutline 测量，
    评分选择最佳组合。
    """

    # 评分权重
    SCORE_WEIGHTS = {
        "overlap": 100.0,        # 重叠惩罚（最严重）
        "out_of_frame": 80.0,    # 越界惩罚
        "titlebar_collision": 60.0,  # 标题栏碰撞惩罚
        "utilization": 15.0,     # 利用率奖励
        "min_gap": 10.0,         # 最小间距奖励
        "readability": 20.0,     # 可读性奖励
    }

    # 最小可读尺寸（米）
    MIN_VIEW_SIZE_M = 0.030  # 30mm
    MIN_GAP_M = 0.005  # 5mm

    def __init__(
        self,
        sw: Any = None,
        doc: Any = None,
        run_dir: Optional[Path] = None,
        run_id: str = "",
        part_class: str = "feature_part",
        max_iterations: int = 24,  # 4 layouts × 8 scales max
    ):
        self.sw = sw
        self.doc = doc
        self.run_dir = run_dir
        self.run_id = run_id
        self.part_class = part_class
        self.max_iterations = max_iterations

    # ========== Layout 选择 ==========

    def _get_candidate_layouts(self) -> list[LayoutType]:
        """根据零件类型返回候选 layout 列表"""
        # 采购件/弹簧/紧固件：仅 PURCHASE
        if self.part_class in ("purchased_part", "spring", "fastener"):
            return [LayoutType.PURCHASE, LayoutType.TWO_VIEW]

        # 小零件：TWO_VIEW 或 L3
        if self.part_class == "tiny_part":
            return [LayoutType.TWO_VIEW, LayoutType.L3, LayoutType.T4]

        # 默认：T4 优先
        return [LayoutType.T4, LayoutType.L3, LayoutType.TWO_VIEW]

    # ========== 视图位置设置 ==========

    def _set_view_position(self, view: Any, x: float, y: float) -> bool:
        """设置视图位置"""
        try:
            import pythoncom
            from win32com.client import VARIANT
            arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x), float(y)])
            view.Position = arr
            return True
        except Exception:
            try:
                view.Position = (float(x), float(y))
                return True
            except Exception:
                return False

    def _get_view_outline(self, view: Any) -> Optional[tuple[float, float, float, float]]:
        """获取视图 outline"""
        try:
            out = view.GetOutline
            if out is None:
                return None
            o = list(out)
            if len(o) >= 4:
                # SW GetOutline 返回 (xmin, ymin, xmax, ymax) 或 6 元素
                return (float(o[0]), float(o[1]), float(o[2]), float(o[3]))
            return None
        except Exception:
            return None

    # ========== 测量与评分 ==========

    def _measure_all_views(self) -> dict[str, tuple[float, float, float, float]]:
        """测量当前 doc 所有视图的 outline"""
        outlines = {}
        try:
            sheet = self.doc.GetCurrentSheet
            views = sheet.GetViews
            if not views:
                return outlines

            for view in views:
                try:
                    name = view.Name
                    # 提取视图类型（front/top/right/iso）
                    view_type = self._classify_view(name)
                    if view_type:
                        ol = self._get_view_outline(view)
                        if ol:
                            outlines[view_type] = ol
                except Exception:
                    pass
        except Exception:
            pass
        return outlines

    def _classify_view(self, name: str) -> Optional[str]:
        """根据视图名分类"""
        name_lower = name.lower()
        if "front" in name_lower or "前视" in name:
            return "front"
        if "top" in name_lower or "俯视" in name or "上视" in name:
            return "top"
        if "right" in name_lower or "右视" in name:
            return "right"
        if "iso" in name_lower or "等轴" in name:
            return "iso"
        return None

    def _score_candidate(
        self,
        outlines: dict[str, tuple[float, float, float, float]],
    ) -> tuple[dict[str, float], list[str]]:
        """评分候选 layout

        Returns:
            (scores, issues)
        """
        scores = {
            "overlap": 0.0,
            "out_of_frame": 0.0,
            "titlebar_collision": 0.0,
            "utilization": 0.0,
            "min_gap": 0.0,
            "readability": 0.0,
        }
        issues = []

        if not outlines:
            scores["overlap"] = -100.0
            issues.append("无视图 outline")
            return scores, issues

        view_list = list(outlines.values())

        # 1. overlap 检测（视图间重叠）
        overlap_count = 0
        for i in range(len(view_list)):
            for j in range(i + 1, len(view_list)):
                if self._rect_intersect(view_list[i], view_list[j]):
                    overlap_count += 1
                    issues.append(f"视图重叠: {list(outlines.keys())[i]} × {list(outlines.keys())[j]}")
        scores["overlap"] = -overlap_count * 100.0

        # 2. out_of_frame 检测
        out_of_frame_count = 0
        for name, ol in outlines.items():
            if not self._rect_in_frame(ol):
                out_of_frame_count += 1
                issues.append(f"视图越界: {name}")
        scores["out_of_frame"] = -out_of_frame_count * 80.0

        # 3. titlebar_collision 检测（视图与标题栏碰撞）
        titlebar_collision_count = 0
        for name, ol in outlines.items():
            if self._rect_intersect(ol, TITLEBAR_BOX):
                titlebar_collision_count += 1
                issues.append(f"标题栏碰撞: {name}")
        scores["titlebar_collision"] = -titlebar_collision_count * 60.0

        # 4. utilization（图框利用率）
        total_view_area = 0.0
        for ol in view_list:
            w = ol[2] - ol[0]
            h = ol[3] - ol[1]
            total_view_area += w * h
        frame_area = (FRAME_BOX[2] - FRAME_BOX[0]) * (FRAME_BOX[3] - FRAME_BOX[1])
        utilization = total_view_area / frame_area if frame_area > 0 else 0
        # 理想利用率 0.3-0.7
        if utilization < 0.1:
            scores["utilization"] = -10.0
        elif utilization > 0.8:
            scores["utilization"] = -5.0
        else:
            scores["utilization"] = utilization * 15.0

        # 5. min_gap（视图间最小间距）
        min_gap = float("inf")
        for i in range(len(view_list)):
            for j in range(i + 1, len(view_list)):
                gap = self._rect_gap(view_list[i], view_list[j])
                if gap < min_gap:
                    min_gap = gap
        if min_gap == float("inf"):
            scores["min_gap"] = 5.0  # 单视图
        elif min_gap < self.MIN_GAP_M:
            scores["min_gap"] = -5.0
            issues.append(f"视图间距过小: {min_gap*1000:.1f}mm < {self.MIN_GAP_M*1000}mm")
        else:
            scores["min_gap"] = min(10.0, min_gap * 100)  # 0.1m = 10分

        # 6. readability（可读性：视图尺寸是否足够大）
        readability_score = 0.0
        for name, ol in outlines.items():
            w = ol[2] - ol[0]
            h = ol[3] - ol[1]
            if w < self.MIN_VIEW_SIZE_M or h < self.MIN_VIEW_SIZE_M:
                readability_score -= 5.0
                issues.append(f"视图过小: {name} ({w*1000:.0f}×{h*1000:.0f}mm)")
            else:
                readability_score += 5.0
        scores["readability"] = readability_score

        return scores, issues

    def _compute_total_score(self, scores: dict[str, float]) -> float:
        """计算总分"""
        total = 0.0
        for key, weight in self.SCORE_WEIGHTS.items():
            if key in scores:
                # 负分项用权重放大惩罚，正分项用权重放大奖励
                if scores[key] < 0:
                    total += scores[key] * weight / 10.0
                else:
                    total += scores[key] * weight / 20.0
        return total

    # ========== 几何辅助函数 ==========

    @staticmethod
    def _rect_intersect(a, b, eps: float = 1e-6) -> bool:
        """矩形相交判定（相切不算）"""
        if not a or not b:
            return False
        return (a[0] < b[2] - eps and a[2] > b[0] + eps and
                a[1] < b[3] - eps and a[3] > b[1] + eps)

    @staticmethod
    def _rect_in_frame(rect, frame=FRAME_BOX, eps: float = 1e-6) -> bool:
        """矩形是否在图框内"""
        if not rect:
            return False
        return (rect[0] >= frame[0] - eps and rect[1] >= frame[1] - eps and
                rect[2] <= frame[2] + eps and rect[3] <= frame[3] + eps)

    @staticmethod
    def _rect_gap(a, b) -> float:
        """两矩形间距（不相交时为正，相交时为 0）"""
        if not a or not b:
            return float("inf")
        dx = max(0, max(b[0] - a[2], a[0] - b[2]))
        dy = max(0, max(b[1] - a[3], a[1] - b[3]))
        return (dx * dx + dy * dy) ** 0.5

    # ========== Save-Close-Reopen ==========

    def _save_close_reopen(self, drw_path: str) -> bool:
        """Save-Close-Reopen 获取持久化 outline"""
        if self.sw is None or self.doc is None:
            return False
        guard = require_current_job_lock("layout_solver_v2._save_close_reopen")
        if not guard.get("ok"):
            return False

        try:
            import pythoncom
            from win32com.client import VARIANT

            # 1. Save
            try:
                self.doc.Save2(True)
            except Exception:
                try:
                    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                    self.doc.Save3(1, err, warn)
                except Exception:
                    pass

            # 2. Close
            try:
                doc_name = self.doc.GetTitle()
                self.sw.CloseDoc(doc_name)
            except Exception:
                pass
            self.doc = None
            time.sleep(1.5)

            # 3. Reopen
            err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            self.doc = self.sw.OpenDoc6(drw_path, 3, 257, "", err, warn)
            if self.doc is None:
                return False
            time.sleep(2.0)

            # 4. Activate
            try:
                self.sw.ActivateDoc3(drw_path, True, 2, None)
            except Exception:
                pass

            return True
        except Exception:
            return False

    # ========== 主求解流程 ==========

    def solve(
        self,
        drw_path: str = "",
        apply_best: bool = True,
    ) -> SolverResult:
        """求解最佳 layout

        Args:
            drw_path: SLDDRW 文件路径（用于 Save-Close-Reopen）
            apply_best: 是否应用最佳 layout

        Returns:
            SolverResult
        """
        start = time.time()
        result = SolverResult()

        if self.sw is None or self.doc is None:
            result.reason = "SW 或 doc 未连接"
            result.duration_ms = int((time.time() - start) * 1000)
            return result

        candidate_layouts = self._get_candidate_layouts()
        all_candidates: list[LayoutCandidate] = []
        iteration = 0

        for layout_type in candidate_layouts:
            for scale in SCALE_LADDER:
                if iteration >= self.max_iterations:
                    break

                iteration += 1
                candidate = LayoutCandidate(
                    layout_type=layout_type,
                    scale=scale,
                    views=LAYOUT_TEMPLATES[layout_type].copy(),
                )

                # 设置视图位置
                try:
                    sheet = self.doc.GetCurrentSheet
                    views = sheet.GetViews
                    if views:
                        for view in views:
                            try:
                                name = view.Name
                                view_type = self._classify_view(name)
                                if view_type and view_type in candidate.views:
                                    x, y = candidate.views[view_type]
                                    self._set_view_position(view, x, y)
                            except Exception:
                                pass
                except Exception:
                    pass

                # 设置比例
                try:
                    sheet.ScaleRatio = f"{scale[0]}:{scale[1]}"
                except Exception:
                    try:
                        self.doc.SetUserPreferenceDoubleValue(0, scale[0] / scale[1])
                    except Exception:
                        pass

                # Save-Close-Reopen 获取持久化 outline
                if drw_path:
                    self._save_close_reopen(drw_path)

                # 测量
                outlines = self._measure_all_views()
                candidate.outlines = {k: list(v) for k, v in outlines.items()}

                # 评分
                scores, issues = self._score_candidate(outlines)
                candidate.scores = scores
                candidate.issues = issues
                candidate.total_score = self._compute_total_score(scores)

                all_candidates.append(candidate)

                # 记录到结果
                result.all_candidates.append({
                    "layout_type": layout_type.value,
                    "scale": f"{scale[0]}:{scale[1]}",
                    "outlines": candidate.outlines,
                    "scores": scores,
                    "total_score": candidate.total_score,
                    "issues": issues,
                })

                # 如果是完美候选（无任何 issue），提前结束
                if not issues and candidate.total_score > 0:
                    result.best_candidate = candidate
                    result.best_layout = layout_type
                    result.best_scale = scale
                    break

            if result.best_candidate and not result.best_candidate.issues:
                break

        # 选择最佳候选
        if not result.best_candidate and all_candidates:
            best = max(all_candidates, key=lambda c: c.total_score)
            result.best_candidate = best
            result.best_layout = best.layout_type
            result.best_scale = best.scale

        result.iterations = iteration

        if result.best_candidate:
            result.success = True
            result.final_outlines = result.best_candidate.outlines
            result.final_scores = result.best_candidate.scores
            result.reason = f"最佳: {result.best_layout.value} @ {result.best_scale[0]}:{result.best_scale[1]}, score={result.best_candidate.total_score:.1f}"

            # 检查是否满足验收条件
            if result.best_candidate.scores.get("overlap", 0) < 0:
                result.reason += " [WARNING: 仍有重叠]"
            if result.best_candidate.scores.get("out_of_frame", 0) < 0:
                result.reason += " [WARNING: 仍有越界]"
            if result.best_candidate.scores.get("titlebar_collision", 0) < 0:
                result.reason += " [WARNING: 仍有标题栏碰撞]"
        else:
            result.reason = "无有效候选"

        result.duration_ms = int((time.time() - start) * 1000)

        # 保存结果
        if self.run_dir:
            self._save_result(result)

        return result

    def _save_result(self, result: SolverResult):
        """保存 layout_solver_v2.json"""
        out_dir = Path(self.run_dir)
        qc_dir = out_dir / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "run_id": self.run_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "part_class": self.part_class,
            "success": result.success,
            "best_layout": result.best_layout.value if result.best_layout else None,
            "best_scale": f"{result.best_scale[0]}:{result.best_scale[1]}" if result.best_scale else None,
            "final_outlines": result.final_outlines,
            "final_scores": result.final_scores,
            "reason": result.reason,
            "iterations": result.iterations,
            "duration_ms": result.duration_ms,
            "all_candidates_count": len(result.all_candidates),
            "all_candidates": result.all_candidates,
            "frame_box": list(FRAME_BOX),
            "titlebar_box": list(TITLEBAR_BOX),
        }

        out_path = qc_dir / "layout_solver_v2.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return out_path


# ========== 便捷函数 ==========

def solve_layout(
    sw: Any,
    doc: Any,
    drw_path: str = "",
    run_dir: Optional[Path] = None,
    run_id: str = "",
    part_class: str = "feature_part",
) -> SolverResult:
    """便捷函数：求解 layout"""
    solver = LayoutSolverV2(
        sw=sw,
        doc=doc,
        run_dir=run_dir,
        run_id=run_id,
        part_class=part_class,
    )
    return solver.solve(drw_path=drw_path)
