"""v2.2 Task 4: Dimension Arrange Service

对 DisplayDimension 按 view 分组，自动偏移到轨道。
检查尺寸文本重叠、尺寸压线、标题栏碰撞。
输出 dimension_arrange.json。

验收: 002/003/007/009 dimension_text_overlap=0
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


DEFAULT_SHEET_SIZE_M = (0.297, 0.210)


def _com_value(obj: Any, name: str, *args: Any, default: Any = None) -> Any:
    """Read a COM property or call a COM method with the same helper path."""
    if obj is None:
        return default
    try:
        value = getattr(obj, name)
    except Exception:
        return default
    try:
        if callable(value):
            return value(*args)
        if args:
            return default
        return value
    except Exception:
        return default


def _as_list(value: Any) -> list[Any]:
    if value is None or isinstance(value, int):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    try:
        return list(value)
    except Exception:
        return [value]


def _norm_box_to_sheet_box(box: Any, sheet_size: tuple[float, float]) -> Optional[tuple[float, float, float, float]]:
    if not isinstance(box, (list, tuple)) or len(box) < 4:
        return None
    try:
        x0, y0, x1, y1 = [float(v) for v in box[:4]]
    except Exception:
        return None
    x0 = max(0.0, min(1.0, x0))
    y0 = max(0.0, min(1.0, y0))
    x1 = max(0.0, min(1.0, x1))
    y1 = max(0.0, min(1.0, y1))
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    width, height = sheet_size
    return (x0 * width, y0 * height, x1 * width, y1 * height)


def _sheet_size_from_layout(layout_plan: Optional[dict[str, Any]]) -> tuple[float, float]:
    if not isinstance(layout_plan, dict):
        return DEFAULT_SHEET_SIZE_M
    size = layout_plan.get("sheet_size") or {}
    try:
        width = float(size.get("width") or DEFAULT_SHEET_SIZE_M[0])
        height = float(size.get("height") or DEFAULT_SHEET_SIZE_M[1])
    except Exception:
        return DEFAULT_SHEET_SIZE_M
    if width <= 0 or height <= 0:
        return DEFAULT_SHEET_SIZE_M
    return (width, height)


@dataclass
class DimensionInfo:
    """单个尺寸信息"""
    index: int
    view_name: str
    text: str = ""
    text_position: tuple[float, float] = (0.0, 0.0)
    arrow_position: tuple[float, float] = (0.0, 0.0)
    track: int = 0  # 轨道编号
    original_position: tuple[float, float] = (0.0, 0.0)
    new_position: tuple[float, float] = (0.0, 0.0)
    adjusted: bool = False
    overlap_detected: bool = False
    slot: str = ""
    lane_role: str = "standard"


@dataclass
class ArrangeResult:
    """排列结果"""
    success: bool = False
    total_dimensions: int = 0
    adjusted_dimensions: int = 0
    overlap_before: int = 0
    overlap_after: int = 0
    titlebar_collision_before: int = 0
    titlebar_collision_after: int = 0
    avoid_collision_before: int = 0
    avoid_collision_after: int = 0
    line_crossing_before: int = 0
    line_crossing_after: int = 0
    callout_lane_applied: bool = False
    callout_lane_count: int = 0
    dimensions: list[dict] = field(default_factory=list)
    reason: str = ""
    duration_ms: int = 0


TITLEBAR_BOX = (0.202, 0.000, 0.297, 0.038)
TRACK_GAP_M = 0.012
TEXT_MIN_GAP_M = 0.008
SHEET_MARGIN_M = 0.006


# 标题栏区域（A4 横式）
TITLEBAR_BOX = (0.102, 0.005, 0.282, 0.095)

# 轨道间距（米）
TRACK_GAP_M = 0.015  # 15mm

# 尺寸文本最小间距
TEXT_MIN_GAP_M = 0.008  # 8mm


class DimensionArrangeService:
    """尺寸排列服务

    对 drawing 中的 DisplayDimension 按 view 分组，
    自动偏移到轨道，避免文本重叠和标题栏碰撞。
    """

    def __init__(
        self,
        sw: Any = None,
        doc: Any = None,
        run_dir: Optional[Path] = None,
        run_id: str = "",
        layout_plan: Optional[dict[str, Any]] = None,
    ):
        self.sw = sw
        self.doc = doc
        self.run_dir = run_dir
        self.run_id = run_id
        self.layout_plan = layout_plan or {}
        self.sheet_size = _sheet_size_from_layout(self.layout_plan)
        self.part_class = str(self.layout_plan.get("part_class") or "").strip().lower()
        self.titlebar_box = (
            _norm_box_to_sheet_box(self.layout_plan.get("titlebar_box_norm"), self.sheet_size)
            or TITLEBAR_BOX
        )
        self.notes_box = _norm_box_to_sheet_box(self.layout_plan.get("notes_box_norm"), self.sheet_size)
        self.avoid_boxes = [self.titlebar_box]
        if self.notes_box:
            self.avoid_boxes.append(self.notes_box)

    def arrange(self) -> ArrangeResult:
        """执行尺寸排列

        Returns:
            ArrangeResult
        """
        start = time.time()
        result = ArrangeResult()

        if self.sw is None or self.doc is None:
            result.reason = "SW 或 doc 未连接"
            result.duration_ms = int((time.time() - start) * 1000)
            return result

        try:
            # 1. 收集所有尺寸信息
            dims_by_view = self._collect_dimensions()
            if not dims_by_view:
                result.reason = "无尺寸可排列"
                result.duration_ms = int((time.time() - start) * 1000)
                return result

            all_dims: list[DimensionInfo] = []
            for view_name, dims in dims_by_view.items():
                all_dims.extend(dims)

            result.total_dimensions = len(all_dims)

            # 2. 检测排列前的问题
            result.overlap_before = self._detect_text_overlaps(all_dims)
            result.titlebar_collision_before = self._detect_titlebar_collisions(all_dims)
            result.avoid_collision_before = self._detect_avoid_box_collisions(all_dims)
            result.line_crossing_before = self._detect_line_crossings(all_dims)

            # 3. 按 view 分组排列
            for view_name, dims in dims_by_view.items():
                self._arrange_view_dimensions(view_name, dims)

            # 4. 检测排列后的问题
            result.overlap_after = self._detect_text_overlaps(all_dims)
            result.titlebar_collision_after = self._detect_titlebar_collisions(all_dims)
            result.avoid_collision_after = self._detect_avoid_box_collisions(all_dims)
            result.line_crossing_after = self._detect_line_crossings(all_dims)

            result.adjusted_dimensions = sum(1 for d in all_dims if d.adjusted)
            result.callout_lane_count = sum(1 for d in all_dims if d.lane_role == "right_callout")
            result.callout_lane_applied = result.callout_lane_count > 0
            result.dimensions = [asdict(d) for d in all_dims]
            result.success = True
            result.reason = f"排列完成: {result.adjusted_dimensions}/{result.total_dimensions} 尺寸已调整"

        except Exception as e:
            result.reason = f"排列异常: {e}"

        result.duration_ms = int((time.time() - start) * 1000)

        # 保存结果
        if self.run_dir:
            self._save_result(result)

        return result

    def _views(self) -> list[Any]:
        views: list[Any] = []
        seen: set[int] = set()

        def _append(view: Any) -> None:
            if view is None:
                return
            key = id(view)
            if key in seen:
                return
            seen.add(key)
            views.append(view)

        sheet = _com_value(self.doc, "GetCurrentSheet")
        for view in _as_list(_com_value(sheet, "GetViews")):
            _append(view)

        cur = _com_value(self.doc, "GetFirstView")
        guard = 0
        while cur is not None and guard < 100:
            guard += 1
            _append(cur)
            cur = _com_value(cur, "GetNextView")

        return views

    def _view_name(self, view: Any, index: int = 0) -> str:
        return str(
            _com_value(view, "Name")
            or _com_value(view, "GetName2")
            or _com_value(view, "GetName")
            or f"view_{index}"
        )

    def _display_dimensions(self, view: Any) -> list[Any]:
        dims = _as_list(_com_value(view, "GetDisplayDimensions"))
        if dims:
            return dims
        first = _com_value(view, "GetFirstDisplayDimension")
        cur = first
        out: list[Any] = []
        guard = 0
        while cur is not None and guard < 2000:
            guard += 1
            out.append(cur)
            nxt = _com_value(view, "GetNextDisplayDimension", cur)
            if nxt is cur:
                break
            cur = nxt
        ann = _com_value(view, "GetFirstAnnotation3")
        guard = 0
        while ann is not None and guard < 2000:
            guard += 1
            ann_type = _com_value(ann, "GetType")
            try:
                ann_type_int = int(ann_type)
            except Exception:
                ann_type_int = -1
            if ann_type_int == 1:
                out.append(ann)
            nxt = _com_value(ann, "GetNext3")
            if nxt is ann:
                break
            ann = nxt
        return out

    def _dimension_position(self, dimension_like: Any) -> tuple[float, float]:
        for name in ("TextPosition", "GetTextPosition", "GetPosition"):
            value = _com_value(dimension_like, name)
            if value and len(value) >= 2:
                try:
                    return (float(value[0]), float(value[1]))
                except Exception:
                    continue
        return (0.0, 0.0)

    def _collect_dimensions(self) -> dict[str, list[DimensionInfo]]:
        """收集所有视图的尺寸信息"""
        dims_by_view: dict[str, list[DimensionInfo]] = {}

        try:
            views = self._views()
            if not views:
                return dims_by_view

            for view_index, view in enumerate(views):
                try:
                    view_name = self._view_name(view, view_index)
                    disp_dims = self._display_dimensions(view)
                    if not disp_dims:
                        continue

                    dims: list[DimensionInfo] = []
                    for idx, dd in enumerate(disp_dims):
                        try:
                            dim_info = DimensionInfo(
                                index=idx,
                                view_name=view_name,
                            )

                            # 获取尺寸文本位置
                            try:
                                dim_info.text_position = self._dimension_position(dd)
                                dim_info.original_position = dim_info.text_position
                            except Exception:
                                pass

                            # 获取尺寸值
                            try:
                                dim = _com_value(dd, "GetDimension2", 0)
                                if dim:
                                    dim_info.text = str(
                                        _com_value(dim, "FullName")
                                        or _com_value(dim, "Name")
                                        or ""
                                    )
                            except Exception:
                                pass

                            # 获取箭头位置
                            try:
                                arrow_pos = _com_value(dd, "ArrowHeadPosition")
                                if arrow_pos and len(arrow_pos) >= 2:
                                    dim_info.arrow_position = (float(arrow_pos[0]), float(arrow_pos[1]))
                            except Exception:
                                pass

                            dims.append(dim_info)
                        except Exception:
                            pass

                    if dims:
                        dims_by_view[view_name] = dims
                except Exception:
                    pass
        except Exception:
            pass

        return dims_by_view

    def _arrange_view_dimensions(
        self,
        view_name: str,
        dims: list[DimensionInfo],
    ):
        """排列单个视图的尺寸到轨道"""
        if not dims:
            return

        # 获取视图 outline 作为参考
        view_outline = self._get_view_outline(view_name)
        if not view_outline:
            return

        xmin, ymin, xmax, ymax = view_outline
        view_height = ymax - ymin

        # 按文本 Y 坐标排序（从上到下）
        dims_sorted = sorted(dims, key=lambda d: d.text_position[1], reverse=True)

        # 分配轨道（每条轨道间距 TRACK_GAP_M）
        # 轨道 0: 视图上方
        # 轨道 1: 视图上方第二层
        # 轨道 -1: 视图下方
        # 轨道 -2: 视图下方第二层
        track_y_base = ymax + TRACK_GAP_M  # 第一条轨道在视图上方

        current_track = 0
        last_y = float("inf")

        for dim in dims_sorted:
            # 如果与上一个尺寸太近，移到下一轨道
            if abs(dim.text_position[1] - last_y) < TEXT_MIN_GAP_M:
                current_track += 1

            track_y = track_y_base + current_track * TRACK_GAP_M

            # 检查是否与标题栏碰撞
            if self._point_in_titlebar(dim.text_position[0], track_y):
                # 移到视图下方
                track_y = ymin - TRACK_GAP_M - current_track * TRACK_GAP_M

            # 如果需要调整位置
            if abs(dim.text_position[1] - track_y) > 0.001:  # 1mm
                dim.new_position = (dim.text_position[0], track_y)
                dim.track = current_track
                dim.adjusted = self._set_text_position(dim, dim.new_position)
            else:
                dim.new_position = dim.text_position
                dim.track = current_track

            last_y = track_y

    def _arrange_view_dimensions(
        self,
        view_name: str,
        dims: list[DimensionInfo],
    ):
        if not dims:
            return
        view_outline = self._get_view_outline(view_name)
        if not view_outline:
            return

        xmin, ymin, xmax, ymax = view_outline
        dims_sorted = sorted(dims, key=lambda d: (d.text_position[0], -d.text_position[1]))
        slot = self._slot_for_outline((xmin, ymin, xmax, ymax), view_name)
        use_long_thin_lanes = self._is_long_thin_view((xmin, ymin, xmax, ymax), slot)
        used_positions: list[tuple[float, float]] = []
        side_orders: dict[str, int] = {}

        for index, dim in enumerate(dims_sorted):
            chosen: Optional[tuple[float, float]] = None
            chosen_track = 0
            side = self._dimension_side(dim.text_position, (xmin, ymin, xmax, ymax))
            side_order = side_orders.get(side, 0)
            side_orders[side] = side_order + 1
            dim.slot = slot
            dim.lane_role = (
                self._long_thin_lane_role(slot, side, side_order, len(dims_sorted))
                if use_long_thin_lanes
                else "standard"
            )
            if use_long_thin_lanes:
                candidates = self._long_thin_candidate_positions(
                    dim,
                    (xmin, ymin, xmax, ymax),
                    index,
                    len(dims_sorted),
                    slot,
                    side_order,
                )
            else:
                candidates = self._candidate_positions(dim, (xmin, ymin, xmax, ymax), index)
            for track, candidate in candidates:
                if not self._point_in_sheet(candidate[0], candidate[1]):
                    continue
                if self._point_in_avoid_box(candidate[0], candidate[1]):
                    continue
                if any(self._distance(candidate, prior) < TEXT_MIN_GAP_M for prior in used_positions):
                    continue
                chosen_track = track
                chosen = candidate
                break

            if chosen is None:
                chosen_track = 0
                chosen = self._clamp_to_sheet((dim.text_position[0], ymax + TRACK_GAP_M))

            dim.new_position = chosen
            dim.track = chosen_track
            if self._distance(dim.text_position, chosen) > 0.001:
                dim.adjusted = self._set_text_position(dim, chosen)
            else:
                dim.adjusted = False
            used_positions.append(dim.new_position if dim.adjusted else dim.text_position)

    def _candidate_positions(
        self,
        dim: DimensionInfo,
        outline: tuple[float, float, float, float],
        index: int,
    ) -> list[tuple[int, tuple[float, float]]]:
        xmin, ymin, xmax, ymax = outline
        x = dim.text_position[0]
        y = dim.text_position[1]
        candidates: list[tuple[int, tuple[float, float]]] = []
        for level in range(0, 8):
            step = (level + 1) * TRACK_GAP_M
            candidates.extend([
                (level + 1, self._clamp_to_sheet((x, ymax + step))),
                (-(level + 1), self._clamp_to_sheet((x, ymin - step))),
                (100 + level, self._clamp_to_sheet((xmax + step, y))),
                (-(100 + level), self._clamp_to_sheet((xmin - step, y))),
            ])
        # Try to keep an already good position when it does not collide.
        candidates.append((0, self._clamp_to_sheet(dim.text_position)))
        return candidates

    def _long_thin_candidate_positions(
        self,
        dim: DimensionInfo,
        outline: tuple[float, float, float, float],
        index: int,
        total: int,
        slot: str,
        side_order: int = 0,
    ) -> list[tuple[int, tuple[float, float]]]:
        xmin, ymin, xmax, ymax = outline
        width = max(xmax - xmin, 0.001)
        height = max(ymax - ymin, 0.001)
        total = max(1, int(total or 1))
        rank = index + 1
        frac = rank / float(total + 1)
        x_on_view = xmin + width * frac
        y_on_view = ymin + height * frac
        gap = 0.018 if slot == "top" else 0.010
        small_gap = 0.009 if slot == "top" else 0.007

        side = self._dimension_side(dim.text_position, outline)
        if slot == "top":
            if dim.lane_role == "right_callout":
                preferred = ["right", "top", "bottom", "left"]
            elif side == "bottom":
                preferred = ["bottom", "top", "right", "left"]
            else:
                preferred = ["top", "bottom", "right", "left"]
            preserve_current_side = False
        elif slot == "right":
            preferred = ["right", "top", "bottom", "left"]
            preserve_current_side = True
        elif slot == "iso":
            preferred = ["right", "top", "bottom", "left"]
            preserve_current_side = True
        else:
            preferred = ["top", "bottom", "left", "right"]
            preserve_current_side = True
        if preserve_current_side and side in preferred:
            preferred = [side] + [item for item in preferred if item != side]

        candidates: list[tuple[int, tuple[float, float]]] = []
        if dim.lane_role == "right_callout":
            callout_order = max(0, int(side_order) - 1)
            for level in range(0, 4):
                col = callout_order // 4
                row = callout_order % 4
                x = xmax + 0.020 + col * 0.018 + level * 0.006
                y = ymax + 0.004 - row * 0.011
                candidates.append((300 + level, self._clamp_to_sheet((x, y))))
        for level in range(0, 5):
            offset = gap + level * small_gap
            for side_name in preferred:
                if side_name == "top":
                    point = (x_on_view, ymax + offset)
                    track = 10 + level
                elif side_name == "bottom":
                    point = (x_on_view, ymin - offset)
                    track = -(10 + level)
                elif side_name == "left":
                    point = (xmin - offset, y_on_view)
                    track = -(100 + level)
                else:
                    point = (xmax + offset, y_on_view)
                    track = 100 + level
                candidates.append((track, self._clamp_to_sheet(point)))
        candidates.append((0, self._clamp_to_sheet(dim.text_position)))
        return candidates

    @staticmethod
    def _long_thin_lane_role(slot: str, side: str, side_order: int, total: int) -> str:
        slot_key = str(slot or "").strip().lower()
        side_key = str(side or "").strip().lower()
        if slot_key == "top" and int(total or 0) >= 5:
            # Reference-style long-thin drawings keep top-view dimensions in
            # local top/bottom lanes. Sending these to a far right callout lane
            # creates cross-view leader lines like the 006 visual review fail.
            return "standard"
        return "standard"

    def _dimension_side(
        self,
        point: tuple[float, float],
        outline: tuple[float, float, float, float],
    ) -> str:
        xmin, ymin, xmax, ymax = outline
        x, y = point
        distances = {
            "top": abs(y - ymax),
            "bottom": abs(y - ymin),
            "left": abs(x - xmin),
            "right": abs(x - xmax),
        }
        if y > ymax:
            return "top"
        if y < ymin:
            return "bottom"
        if x < xmin:
            return "left"
        if x > xmax:
            return "right"
        return min(distances, key=distances.get)

    def _slot_for_outline(self, outline: tuple[float, float, float, float], fallback: str = "") -> str:
        views = self.layout_plan.get("views") if isinstance(self.layout_plan, dict) else None
        if not isinstance(views, list):
            return str(fallback or "")
        cx = (outline[0] + outline[2]) / 2.0
        cy = (outline[1] + outline[3]) / 2.0
        best_slot = str(fallback or "")
        best_dist = float("inf")
        for item in views:
            if not isinstance(item, dict):
                continue
            box = _norm_box_to_sheet_box(item.get("box_norm"), self.sheet_size)
            if not box:
                center_norm = item.get("center_norm")
                if isinstance(center_norm, list) and len(center_norm) >= 2:
                    try:
                        box = (
                            float(center_norm[0]) * self.sheet_size[0],
                            float(center_norm[1]) * self.sheet_size[1],
                            float(center_norm[0]) * self.sheet_size[0],
                            float(center_norm[1]) * self.sheet_size[1],
                        )
                    except Exception:
                        box = None
            if not box:
                continue
            bx = (box[0] + box[2]) / 2.0
            by = (box[1] + box[3]) / 2.0
            dist = self._distance((cx, cy), (bx, by))
            if dist < best_dist:
                best_dist = dist
                best_slot = str(item.get("slot") or best_slot)
        return best_slot

    def _is_long_thin_view(self, outline: tuple[float, float, float, float], slot: str) -> bool:
        width = max(outline[2] - outline[0], 0.0)
        height = max(outline[3] - outline[1], 0.001)
        if self.part_class == "long_thin":
            return str(slot or "").lower() in {"front", "top", "right", "iso", ""}
        return width / height >= 4.0

    def _get_view_outline(self, view_name: str) -> Optional[tuple[float, float, float, float]]:
        """获取视图 outline"""
        try:
            sheet = _com_value(self.doc, "GetCurrentSheet")
            views = _as_list(_com_value(sheet, "GetViews"))
            if not views:
                return None

            for view in views:
                if view.Name == view_name:
                    out = view.GetOutline
                    if out and len(out) >= 4:
                        return (float(out[0]), float(out[1]), float(out[2]), float(out[3]))
            return None
        except Exception:
            return None

    def _get_view_outline(self, view_name: str) -> Optional[tuple[float, float, float, float]]:
        try:
            for index, view in enumerate(self._views()):
                name = self._view_name(view, index)
                if name != view_name:
                    continue
                out = _com_value(view, "GetOutline")
                if out and len(out) >= 4:
                    return (float(out[0]), float(out[1]), float(out[2]), float(out[3]))
            return None
        except Exception:
            return None

    def _set_text_position(self, dim_info: DimensionInfo, pos: tuple[float, float]) -> bool:
        """设置尺寸文本位置"""
        try:
            import pythoncom
            from win32com.client import VARIANT

            views = self._views()
            if not views:
                return False

            for view in views:
                if view.Name != dim_info.view_name:
                    continue
                disp_dims = view.GetDisplayDimensions
                if not disp_dims or isinstance(disp_dims, int):
                    continue

                if dim_info.index < len(disp_dims):
                    dd = disp_dims[dim_info.index]
                    arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(pos[0]), float(pos[1])])
                    dd.TextPosition = arr
                    return True
            return False
        except Exception:
            return False

    # ========== 检测函数 ==========

    def _set_text_position(self, dim_info: DimensionInfo, pos: tuple[float, float]) -> bool:
        try:
            for index, view in enumerate(self._views()):
                name = self._view_name(view, index)
                if name != dim_info.view_name:
                    continue
                disp_dims = self._display_dimensions(view)
                if dim_info.index >= len(disp_dims):
                    return False
                dd = disp_dims[dim_info.index]
                values = [float(pos[0]), float(pos[1])]
                try:
                    import pythoncom
                    from win32com.client import VARIANT

                    dd.TextPosition = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)
                    return True
                except Exception:
                    pass
                for candidate in (tuple(values), values):
                    try:
                        setattr(dd, "TextPosition", candidate)
                        return True
                    except Exception:
                        continue
                for method_name in ("SetPosition2", "SetPosition"):
                    method = getattr(dd, method_name, None)
                    if not callable(method):
                        continue
                    try:
                        method(float(pos[0]), float(pos[1]), 0.0)
                        return True
                    except TypeError:
                        try:
                            method(float(pos[0]), float(pos[1]))
                            return True
                        except Exception:
                            continue
                    except Exception:
                        continue
                return False
            return False
        except Exception:
            return False

    def _point_in_sheet(self, x: float, y: float) -> bool:
        width, height = self.sheet_size
        return SHEET_MARGIN_M <= x <= width - SHEET_MARGIN_M and SHEET_MARGIN_M <= y <= height - SHEET_MARGIN_M

    def _clamp_to_sheet(self, pos: tuple[float, float]) -> tuple[float, float]:
        width, height = self.sheet_size
        x = max(SHEET_MARGIN_M, min(width - SHEET_MARGIN_M, float(pos[0])))
        y = max(SHEET_MARGIN_M, min(height - SHEET_MARGIN_M, float(pos[1])))
        return (x, y)

    @staticmethod
    def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        return ((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2) ** 0.5

    def _point_in_avoid_box(self, x: float, y: float) -> bool:
        for box in self.avoid_boxes:
            if box and box[0] <= x <= box[2] and box[1] <= y <= box[3]:
                return True
        return False

    def _detect_avoid_box_collisions(self, dims: list[DimensionInfo]) -> int:
        count = 0
        for dim in dims:
            pos = dim.new_position if dim.adjusted else dim.text_position
            if self._point_in_avoid_box(pos[0], pos[1]):
                count += 1
        return count

    def _detect_text_overlaps(self, dims: list[DimensionInfo]) -> int:
        """检测尺寸文本重叠"""
        overlap_count = 0
        for i in range(len(dims)):
            for j in range(i + 1, len(dims)):
                pos_i = dims[i].new_position if dims[i].adjusted else dims[i].text_position
                pos_j = dims[j].new_position if dims[j].adjusted else dims[j].text_position
                dist = ((pos_i[0] - pos_j[0]) ** 2 + (pos_i[1] - pos_j[1]) ** 2) ** 0.5
                if dist < TEXT_MIN_GAP_M:
                    overlap_count += 1
                    dims[i].overlap_detected = True
                    dims[j].overlap_detected = True
        return overlap_count

    def _detect_titlebar_collisions(self, dims: list[DimensionInfo]) -> int:
        """检测尺寸与标题栏碰撞"""
        count = 0
        for dim in dims:
            pos = dim.new_position if dim.adjusted else dim.text_position
            if self._point_in_titlebar(pos[0], pos[1]):
                count += 1
        return count

    def _detect_line_crossings(self, dims: list[DimensionInfo]) -> int:
        """检测尺寸压线（尺寸文本穿过视图轮廓线）

        简化检测：检查尺寸文本是否在视图 outline 内
        """
        count = 0
        try:
            sheet = self.doc.GetCurrentSheet
            views = sheet.GetViews
            if not views:
                return 0

            view_outlines = {}
            for index, view in enumerate(views):
                try:
                    name = self._view_name(view, index)
                    out = _com_value(view, "GetOutline")
                    if out and len(out) >= 4:
                        view_outlines[name] = (float(out[0]), float(out[1]), float(out[2]), float(out[3]))
                except Exception:
                    pass

            for dim in dims:
                pos = dim.new_position if dim.adjusted else dim.text_position
                # 检查是否在其他视图 outline 内（非所属视图）
                for vname, vol in view_outlines.items():
                    if vname == dim.view_name:
                        continue
                    if (vol[0] < pos[0] < vol[2] and vol[1] < pos[1] < vol[3]):
                        count += 1
                        break
        except Exception:
            pass
        return count

    def _point_in_titlebar(self, x: float, y: float) -> bool:
        """点是否在标题栏区域内"""
        box = self.titlebar_box
        return box[0] <= x <= box[2] and box[1] <= y <= box[3]

    def _save_result(self, result: ArrangeResult):
        """保存 dimension_arrange.json"""
        out_dir = Path(self.run_dir)
        qc_dir = out_dir / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "run_id": self.run_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "success": result.success,
            "total_dimensions": result.total_dimensions,
            "adjusted_dimensions": result.adjusted_dimensions,
            "overlap_before": result.overlap_before,
            "overlap_after": result.overlap_after,
            "titlebar_collision_before": result.titlebar_collision_before,
            "titlebar_collision_after": result.titlebar_collision_after,
            "avoid_collision_before": result.avoid_collision_before,
            "avoid_collision_after": result.avoid_collision_after,
            "line_crossing_before": result.line_crossing_before,
            "line_crossing_after": result.line_crossing_after,
            "callout_lane_applied": result.callout_lane_applied,
            "callout_lane_count": result.callout_lane_count,
            "reason": result.reason,
            "duration_ms": result.duration_ms,
            "dimensions": result.dimensions,
            "sheet_size": list(self.sheet_size),
            "titlebar_box": list(self.titlebar_box),
            "notes_box": list(self.notes_box) if self.notes_box else [],
            "avoid_boxes": [list(box) for box in self.avoid_boxes],
        }

        out_path = qc_dir / "dimension_arrange.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return out_path


# ========== 便捷函数 ==========

def arrange_dimensions(
    sw: Any,
    doc: Any,
    run_dir: Optional[Path] = None,
    run_id: str = "",
    layout_plan: Optional[dict[str, Any]] = None,
) -> ArrangeResult:
    """便捷函数：排列尺寸"""
    service = DimensionArrangeService(
        sw=sw,
        doc=doc,
        run_dir=run_dir,
        run_id=run_id,
        layout_plan=layout_plan,
    )
    return service.arrange()
