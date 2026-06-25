"""v1.6 Task 3: 持久化布局求解器

生成 drawing 后必须 SaveAs → Close → Reopen → GetOutline，
同时检测 overlap 和 out_of_frame。
若任一失败，降比例并重新保存/重开测量。
不要只在内存态检查 outline。
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any

# pywin32
try:
    import pythoncom
    from pywintypes import com_error
    _HAS_PYWIN32 = True
except Exception:
    _HAS_PYWIN32 = False
    pythoncom = None  # type: ignore

# FRAME_BOX 与 drw_generate_v6.py L1003 一致
FRAME_BOX = (0.010, 0.010, 0.287, 0.200)
EPS = 1e-6


def _require_solidworks_lock(operation: str, path: str = "") -> dict[str, Any]:
    try:
        from app.services.solidworks_global_lock import require_current_job_lock

        guard = require_current_job_lock(operation)
    except Exception as exc:
        return {
            "ok": False,
            "status": "blocked_by_solidworks_lock",
            "reason": f"lock_guard_unavailable: {exc}",
            "path": path,
        }
    if guard.get("ok"):
        return {"ok": True}
    return {
        "ok": False,
        "status": "blocked_by_solidworks_lock",
        "reason": guard.get("reason", ""),
        "owner": guard.get("owner", {}),
        "fix_suggestion": guard.get("fix_suggestion", "等待当前 CAD job 完成，或手动确认后释放 stale lock"),
        "path": path,
    }


def _variant_i4_ref(value: int = 0):
    """构造 VARIANT(VT_BYREF | VT_I4, value)"""
    if not _HAS_PYWIN32:
        return value
    from win32com.client import VARIANT
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, value)


def _vt_dispatch_none():
    """构造 VARIANT(VT_DISPATCH, None) - SaveAs 第 4 参数需要此类型"""
    if not _HAS_PYWIN32:
        return None
    from win32com.client import VARIANT
    return VARIANT(pythoncom.VT_DISPATCH, None)


def _rect_intersect(a, b) -> bool:
    """严格相交（相切不算），eps=1e-6"""
    if not a or not b or len(a) < 4 or len(b) < 4:
        return False
    ax0, ay0, ax1, ay1 = a[0], a[1], a[2], a[3]
    bx0, by0, bx1, by1 = b[0], b[1], b[2], b[3]
    if ax1 <= bx0 + EPS or bx1 <= ax0 + EPS:
        return False
    if ay1 <= by0 + EPS or by1 <= ay0 + EPS:
        return False
    return True


def _rect_in_frame(rect) -> bool:
    """检查 AABB 是否完全在 FRAME_BOX 内"""
    if not rect or len(rect) < 4:
        return False
    x0, y0, x1, y1 = rect[0], rect[1], rect[2], rect[3]
    return (x0 >= FRAME_BOX[0] - EPS and
            y0 >= FRAME_BOX[1] - EPS and
            x1 <= FRAME_BOX[2] + EPS and
            y1 <= FRAME_BOX[3] + EPS)


def _get_view_outline(view) -> list:
    """获取视图 outline [x0, y0, x1, y1]"""
    # 兼容 property/method 两种访问方式
    ol = _call_or_get(view, "GetOutline")
    if ol is None:
        return []
    try:
        if isinstance(ol, (list, tuple)):
            return [float(v) for v in ol]
        return [float(v) for v in list(ol)]
    except Exception:
        return []


def _call_or_get(obj, name, *args):
    """兼容 COM 成员的 property/method 访问

    对齐 drw_quality_check.py 的 call() 函数逻辑：
      - 先 getattr 获取成员
      - 若 callable 且有参数：调用 m(*args)
      - 若 callable 无参数：尝试 m()，TypeError 时返回 m 本身
      - 若非 callable：直接返回 m
    """
    if obj is None:
        return None
    try:
        m = getattr(obj, name)
    except Exception:
        return None
    try:
        if args:
            return m(*args) if callable(m) else m
        if callable(m):
            try:
                return m()
            except TypeError:
                return m
        return m
    except Exception:
        try:
            return m
        except Exception:
            return None


def _get_all_views(drw, log_fn=None) -> list:
    """获取工程图所有视图（排除 sheet 视图 type=1）

    多策略遍历（兼容 property/method 两种 COM 访问方式）：
      策略 A: GetFirstView() -> GetNextView() 链（IDrawingDoc 方法）
      策略 B: GetViews property 返回 sheet views，每个 sheet view -> GetNextView 链
      策略 C: 遍历所有 sheet（GetSheetNames），激活后 GetFirstView -> GetNextView
    """
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    views = []

    # 策略 A: 标准 GetFirstView -> GetNextView 链（method 调用）
    try:
        sheet_view = _call_or_get(drw, "GetFirstView")
        _log(f"    [get_views] 策略A: GetFirstView = {None if sheet_view is None else 'OK'}")
        if sheet_view is not None:
            v = _call_or_get(sheet_view, "GetNextView")
            while v is not None:
                views.append(v)
                try:
                    v = _call_or_get(v, "GetNextView")
                except Exception:
                    break
        _log(f"    [get_views] 策略A 收集 {len(views)} 个视图")
    except Exception as e:
        _log(f"    [get_views] 策略A 异常: {e}")

    if views:
        return views

    # 策略 B: GetViews property 返回 sheet views（IModelDoc2.GetViews）
    # 每个 sheet view 通过 GetNextView 链获取实际视图
    try:
        all_sheet_views = _call_or_get(drw, "GetViews")
        if all_sheet_views is not None:
            # all_sheet_views 可能是 tuple/list
            if not isinstance(all_sheet_views, (list, tuple)):
                all_sheet_views = [all_sheet_views]
            _log(f"    [get_views] 策略B: GetViews 返回 {len(all_sheet_views)} 个 sheet view")
            for sv in all_sheet_views:
                try:
                    v = _call_or_get(sv, "GetNextView")
                    while v is not None:
                        views.append(v)
                        try:
                            v = _call_or_get(v, "GetNextView")
                        except Exception:
                            break
                except Exception:
                    continue
            _log(f"    [get_views] 策略B 收集 {len(views)} 个视图")
    except Exception as e:
        _log(f"    [get_views] 策略B 异常: {e}")

    if views:
        return views

    # 策略 C: 遍历所有 sheet，激活后 GetFirstView -> GetNextView
    try:
        sheet_names = _call_or_get(drw, "GetSheetNames")
        if sheet_names is not None:
            if not isinstance(sheet_names, (list, tuple)):
                sheet_names = [sheet_names]
            _log(f"    [get_views] 策略C: {len(sheet_names)} 个 sheet")
            for sname in sheet_names:
                try:
                    _call_or_get(drw, "ActivateSheet", sname)
                    time.sleep(0.2)
                    sheet_view = _call_or_get(drw, "GetFirstView")
                    if sheet_view is None:
                        continue
                    v = _call_or_get(sheet_view, "GetNextView")
                    while v is not None:
                        views.append(v)
                        try:
                            v = _call_or_get(v, "GetNextView")
                        except Exception:
                            break
                except Exception:
                    continue
            _log(f"    [get_views] 策略C 收集 {len(views)} 个视图")
    except Exception as e:
        _log(f"    [get_views] 策略C 异常: {e}")

    return views


def _measure_persisted_outlines(drw, log_fn=None) -> dict:
    """测量工程图所有视图的 outline

    返回 {view_name: [x0, y0, x1, y1]}

    包含重试机制：reopen 后视图可能需要多次尝试才能加载
    """
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    outlines = {}

    # 重试 3 次，每次间隔 1 秒
    for attempt in range(3):
        views = _get_all_views(drw, log_fn=log_fn)
        _log(f"    [measure] 尝试 {attempt+1}/3: _get_all_views 返回 {len(views)} 个视图")
        if views:
            for idx, v in enumerate(views):
                try:
                    name = str(v.Name)
                except Exception:
                    name = f"view_{idx}"
                ol = _get_view_outline(v)
                if ol:
                    outlines[name] = ol
                    _log(f"    [measure] {name}: outline={ol}")
                else:
                    _log(f"    [measure] {name}: outline 为空")
            if outlines:
                break

        # 如果没有视图，等待后重试
        if attempt < 2:
            _log(f"    [measure] 等待 1.5s 后重试...")
            time.sleep(1.5)
            # 强制重建
            try:
                drw.ForceRebuild3(False)
            except Exception:
                pass

    return outlines


def _detect_overlap(outlines: dict) -> list:
    """检测视图重叠，返回重叠对列表"""
    names = list(outlines.keys())
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = outlines[names[i]]
            b = outlines[names[j]]
            if _rect_intersect(a, b):
                pairs.append({
                    "a": names[i],
                    "b": names[j],
                    "a_outline": a,
                    "b_outline": b,
                })
    return pairs


def _detect_out_of_frame(outlines: dict) -> list:
    """检测视图越界，返回越界视图列表"""
    out_of_frame = []
    for name, ol in outlines.items():
        if not _rect_in_frame(ol):
            out_of_frame.append({"name": name, "outline": ol})
    return out_of_frame


def _outline_center(outline) -> tuple[float, float] | None:
    if not outline or len(outline) < 4:
        return None
    try:
        return (
            (float(outline[0]) + float(outline[2])) / 2.0,
            (float(outline[1]) + float(outline[3])) / 2.0,
        )
    except Exception:
        return None


def _outline_size(outline) -> tuple[float, float] | None:
    if not outline or len(outline) < 4:
        return None
    try:
        return (
            abs(float(outline[2]) - float(outline[0])),
            abs(float(outline[3]) - float(outline[1])),
        )
    except Exception:
        return None


def _slot_outlines_by_center(outlines: dict, centers: dict) -> dict:
    mapped = {}
    used = set()
    for slot, center in (centers or {}).items():
        try:
            cx, cy = float(center[0]), float(center[1])
        except Exception:
            continue
        ranked = []
        for name, outline in (outlines or {}).items():
            if name in used:
                continue
            actual_center = _outline_center(outline)
            if actual_center is None:
                continue
            dist = ((actual_center[0] - cx) ** 2 + (actual_center[1] - cy) ** 2) ** 0.5
            ranked.append((dist, name, outline))
        ranked.sort(key=lambda item: item[0])
        if ranked:
            _, name, outline = ranked[0]
            mapped[slot] = {"name": name, "outline": outline}
            used.add(name)
    return mapped


def _target_outline_size_issues(outlines: dict, centers: dict, target_outlines: dict | None, tolerance: float) -> list:
    if not target_outlines:
        return []
    slot_map = _slot_outlines_by_center(outlines, centers)
    issues = []
    for slot, target_outline in target_outlines.items():
        target_size = _outline_size(target_outline)
        if target_size is None:
            continue
        item = slot_map.get(slot)
        if not item:
            issues.append({
                "slot": slot,
                "reason": "slot_outline_missing",
                "blocking": str(slot).lower() != "iso",
            })
            continue
        actual_size = _outline_size(item.get("outline"))
        if actual_size is None:
            issues.append({
                "slot": slot,
                "view": item.get("name"),
                "reason": "actual_outline_invalid",
                "blocking": str(slot).lower() != "iso",
            })
            continue
        aw, ah = actual_size
        tw, th = target_size
        width_delta = abs(aw - tw) / tw if tw > EPS else 0.0
        height_delta = abs(ah - th) / th if th > EPS else 0.0
        if width_delta > tolerance or height_delta > tolerance:
            width_direction = "too_large" if aw > tw else "too_small"
            height_direction = "too_large" if ah > th else "too_small"
            dominant_axis = "width" if width_delta >= height_delta else "height"
            dominant_direction = width_direction if dominant_axis == "width" else height_direction
            issues.append({
                "slot": slot,
                "view": item.get("name"),
                "reason": "outline_size_mismatch",
                "actual_size": [round(aw, 6), round(ah, 6)],
                "target_size": [round(tw, 6), round(th, 6)],
                "width_delta": round(width_delta, 4),
                "height_delta": round(height_delta, 4),
                "width_direction": width_direction,
                "height_direction": height_direction,
                "dominant_axis": dominant_axis,
                "dominant_direction": dominant_direction,
                "tolerance": tolerance,
                "blocking": str(slot).lower() != "iso",
            })
    return issues


def _blocking_target_outline_issues(issues: list) -> list:
    return [item for item in issues if item.get("blocking", True)]


def _target_outline_scale_direction(issues: list) -> str:
    directions = [
        str(item.get("dominant_direction") or "")
        for item in _blocking_target_outline_issues(issues)
    ]
    directions = [item for item in directions if item in {"too_small", "too_large"}]
    if not directions:
        return ""
    unique = set(directions)
    if len(unique) == 1:
        return directions[0]
    if "too_large" in unique:
        return "too_large"
    return "too_small"


def _set_view_scale(view, num: int, den: int) -> bool:
    """设置视图比例（使用 VARIANT SafeArray，对齐 drw_generate_v6.py）"""
    try:
        from win32com.client import VARIANT
        arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(num), float(den)])
        view.ScaleRatio = arr
        return True
    except Exception:
        try:
            view.ScaleRatio = (float(num), float(den))
            return True
        except Exception:
            try:
                view.SetScale2(num, den, False, False, "", 0)
                return True
            except Exception:
                return False


def _set_view_position(view, x: float, y: float) -> bool:
    """设置视图位置（使用 VARIANT SafeArray，对齐 drw_generate_v6.py）"""
    try:
        from win32com.client import VARIANT
        arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x), float(y)])
        view.Position = arr
        return True
    except Exception:
        try:
            view.Position = (float(x), float(y))
            return True
        except Exception:
            try:
                view.SetPosition2(float(x), float(y), 0.0)
                return True
            except Exception:
                return False


def _save_close_reopen(sw, drw_path: str, log_fn=None, doc=None):
    """SaveAs → Close → Reopen，返回新的 drw 对象

    对齐 drw_quality_check.py 的 _open_doc_with_retry 方式：
      - OpenDoc6 options=257 (silent + override default)
      - SetUserPreferenceIntegerValue(9, 1) 更新外部引用
      - 不调用 ActivateDoc3/ForceRebuild3（QC check 不用这些）
    """
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    try:
        # 优先保存调用方传入的工程图对象；ActiveDoc 可能已经被零件文档抢占。
        drw = doc
        if drw is None:
            drw = sw.ActiveDoc
        if drw is None:
            _log("    [save_close_reopen] ActiveDoc 为 None，直接 OpenDoc6")
            try:
                sw.SetUserPreferenceIntegerValue(9, 1)
            except Exception:
                pass
            err = _variant_i4_ref(0)
            warn = _variant_i4_ref(0)
            drw = sw.OpenDoc6(drw_path, 3, 257, "", err, warn)
            if drw is None:
                _log("    [save_close_reopen] OpenDoc6 返回 None")
                return None
            time.sleep(2.0)
            return drw

        try:
            title_hint = str(_call_or_get(drw, "GetTitle") or "")
        except Exception:
            title_hint = ""
        try:
            path_hint = str(_call_or_get(drw, "GetPathName") or "")
        except Exception:
            path_hint = ""
        _log(f"    [save_close_reopen] 保存对象 title={title_hint!r} path={path_hint!r}")

        # SaveAs（确保最新状态落盘）
        err = _variant_i4_ref(0)
        warn = _variant_i4_ref(0)
        try:
            ok = drw.Extension.SaveAs(drw_path, 0, 1, _vt_dispatch_none(), err, warn)
            _log(f"    [save_close_reopen] SaveAs {'OK' if ok is not False else 'FAIL'}")
        except Exception as e:
            _log(f"    [save_close_reopen] SaveAs 异常: {e}")

        # Close
        try:
            title = _call_or_get(drw, "GetTitle")
            if title:
                sw.CloseDoc(title)
                _log(f"    [save_close_reopen] CloseDoc: {title}")
        except Exception as e:
            _log(f"    [save_close_reopen] CloseDoc 异常: {e}")
        time.sleep(1.5)  # 等待 SW 完成关闭

        # Reopen（对齐 QC check: options=257, SetUserPreferenceIntegerValue(9,1)）
        try:
            sw.SetUserPreferenceIntegerValue(9, 1)
        except Exception:
            pass
        err = _variant_i4_ref(0)
        warn = _variant_i4_ref(0)
        drw = sw.OpenDoc6(drw_path, 3, 257, "", err, warn)
        if drw is None:
            _log("    [save_close_reopen] Reopen OpenDoc6 返回 None")
            return None

        try:
            reopened_path = str(_call_or_get(drw, "GetPathName") or "")
            if reopened_path:
                _log(f"    [save_close_reopen] Reopen path={reopened_path!r}")
        except Exception:
            pass

        _log(f"    [save_close_reopen] Reopen OK, 等待 2s 加载")
        time.sleep(2.0)  # 等待 SW 完成视图加载

        return drw
    except Exception as e:
        _log(f"    [save_close_reopen] 整体异常: {e}")
        return None


def _adjust_positions_for_frame(views: list, outlines: dict, log_fn=None) -> dict:
    """调整越界视图的位置使其落入 FRAME_BOX 内

    Args:
        views: IView 对象列表
        outlines: {view_name: [x0, y0, x1, y1]} 测量结果
        log_fn: 日志函数

    Returns:
        {view_name: (new_x, new_y)} 调整后的位置
    """
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    adjustments = {}
    for idx, view_obj in enumerate(views):
        try:
            name = str(view_obj.Name)
        except Exception:
            name = f"view_{idx}"
        ol = outlines.get(name)
        if not ol or len(ol) < 4:
            continue

        x0, y0, x1, y1 = ol[0], ol[1], ol[2], ol[3]
        # 获取当前位置
        try:
            pos = view_obj.Position
            px, py = float(pos[0]), float(pos[1])
        except Exception:
            _log(f"    [adjust] {name}: 无法获取 Position")
            continue

        dx, dy = 0.0, 0.0
        # 检查 y 方向越界
        if y1 > FRAME_BOX[3] + EPS:
            dy = -(y1 - FRAME_BOX[3])  # 下移
            _log(f"    [adjust] {name}: y1={y1:.4f} > {FRAME_BOX[3]}, 下移 {dy:.4f}")
        elif y0 < FRAME_BOX[1] - EPS:
            dy = (FRAME_BOX[1] - y0)  # 上移
            _log(f"    [adjust] {name}: y0={y0:.4f} < {FRAME_BOX[1]}, 上移 {dy:.4f}")

        # 检查 x 方向越界
        if x1 > FRAME_BOX[2] + EPS:
            dx = -(x1 - FRAME_BOX[2])  # 左移
            _log(f"    [adjust] {name}: x1={x1:.4f} > {FRAME_BOX[2]}, 左移 {dx:.4f}")
        elif x0 < FRAME_BOX[0] - EPS:
            dx = (FRAME_BOX[0] - x0)  # 右移
            _log(f"    [adjust] {name}: x0={x0:.4f} < {FRAME_BOX[0]}, 右移 {dx:.4f}")

        if abs(dx) > EPS or abs(dy) > EPS:
            new_px, new_py = px + dx, py + dy
            # 先移除视图对齐，防止位置被对齐覆盖
            try:
                view_obj.RemoveAlignment()
            except Exception:
                pass
            ok = _set_view_position(view_obj, new_px, new_py)
            if not ok:
                # 尝试 SetPosition3（解锁视图位置）
                try:
                    view_obj.SetPosition3(new_px, new_py, 0.0, 0)
                    ok = True
                except Exception:
                    pass
            if ok:
                # 验证位置是否实际更新
                try:
                    pos2 = view_obj.Position
                    actual_px, actual_py = float(pos2[0]), float(pos2[1])
                    if abs(actual_px - new_px) < 0.001 and abs(actual_py - new_py) < 0.001:
                        adjustments[name] = (new_px, new_py)
                        _log(f"    [adjust] {name}: Position ({px:.4f},{py:.4f}) -> ({new_px:.4f},{new_py:.4f}) OK")
                    else:
                        # 位置验证失败，但仍记录调整（可能 ForceRebuild 后才生效）
                        adjustments[name] = (new_px, new_py)
                        _log(f"    [adjust] {name}: Position 设置后验证偏差, actual=({actual_px:.4f},{actual_py:.4f}), 期望=({new_px:.4f},{new_py:.4f})")
                except Exception:
                    adjustments[name] = (new_px, new_py)
                    _log(f"    [adjust] {name}: Position ({px:.4f},{py:.4f}) -> ({new_px:.4f},{new_py:.4f}) (无验证)")
            else:
                _log(f"    [adjust] {name}: SetPosition 返回 False")

    return adjustments


def _apply_target_centers_to_views(views: list, centers: dict, log_fn=None) -> dict:
    """重开后按 front/top/right/iso 目标中心重新定位视图。

    SolidWorks 保存/重开后，视图可能仍在图框内但偏离参考布局中心。
    这里按创建顺序重新应用目标中心，让后续 overlap/frame 检查基于真实目标布局。
    """
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    applied: dict[str, tuple[float, float]] = {}
    if not views or not centers:
        return applied

    center_items = list(centers.items())
    for idx, view_obj in enumerate(views):
        if idx >= len(center_items):
            break
        key, point = center_items[idx]
        try:
            nx, ny = float(point[0]), float(point[1])
        except Exception:
            continue
        try:
            view_obj.RemoveAlignment()
        except Exception:
            pass
        ok = _set_view_position(view_obj, nx, ny)
        if not ok:
            try:
                view_obj.SetPosition3(nx, ny, 0.0, 0)
                ok = True
            except Exception:
                ok = False
        try:
            name = str(view_obj.Name)
        except Exception:
            name = f"view_{idx}"
        if ok:
            applied[str(key)] = (nx, ny)
            _log(f"    [target_centers] {name}/{key} -> ({nx:.4f},{ny:.4f})")
        else:
            _log(f"    [target_centers] {name}/{key} Position 失败")
    return applied


def solve_persisted_layout(sw, drw_path: str, created_views: dict,
                           centers: dict, scale_ladder: list,
                           max_iterations: int = 5,
                           log_fn=None,
                           drawing_doc=None,
                           target_outlines: dict | None = None,
                           target_outline_tolerance: float = 0.28,
                           start_scale: tuple[int, int] | None = None) -> dict:
    """持久化布局求解器主函数

    Args:
        sw: SolidWorks Application 对象
        drw_path: 工程图绝对路径
        created_views: {view_key: IView} 视图对象字典（内存态，用于设置比例/位置）
        centers: {view_key: (x, y)} 视图目标位置
        scale_ladder: [(num, den), ...] 比例梯（如 [(5,1),(2,1),(1,1),(1,2),(1,5),(1,10),(1,20),(1,50)]）
        max_iterations: 最大迭代次数
        log_fn: 日志函数

    Returns:
        {
            "success": bool,
            "iterations": int,
            "final_scale": str,
            "final_outlines": {view_name: [x0,y0,x1,y1]},
            "target_outline_size_issues": [],
            "overlap_pairs": [],
            "out_of_frame": [],
            "error": str,
        }
    """
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    result = {
        "success": False,
        "iterations": 0,
        "final_scale": "",
        "final_outlines": {},
        "target_outline_size_issues": [],
        "target_outline_size_blocking_issues": [],
        "target_outline_size_warning_issues": [],
        "target_outline_size_pass": not bool(target_outlines),
        "target_outline_scale_direction": "",
        "overlap_pairs": [],
        "out_of_frame": [],
        "error": "",
    }

    if not _HAS_PYWIN32:
        result["error"] = "pywin32 不可用"
        return result

    try:
        drw_path = str(Path(drw_path).resolve())
    except Exception as e:
        result["error"] = f"路径解析失败: {e}"
        return result

    guard = _require_solidworks_lock("persisted_layout_solver.solve_persisted_layout", drw_path)
    if not guard.get("ok"):
        result.update({
            "status": "blocked_by_solidworks_lock",
            "failure_bucket": "solidworks_lock_conflict",
            "error": "blocked_by_solidworks_lock",
            "lock": guard,
        })
        _write_layout_json(drw_path, result)
        return result

    # 初始比例。参考图给出比例提示时，从该档开始，不再从 5:1 盲目试起。
    current_scale_idx = 0
    current_scale = scale_ladder[0] if scale_ladder else (1, 1)
    if start_scale and scale_ladder:
        try:
            normalized_start = (int(start_scale[0]), int(start_scale[1]))
            if normalized_start in scale_ladder:
                current_scale_idx = scale_ladder.index(normalized_start)
                current_scale = scale_ladder[current_scale_idx]
        except Exception:
            pass
    result["start_scale"] = f"{current_scale[0]}:{current_scale[1]}"
    drw = drawing_doc

    for iteration in range(1, max_iterations + 1):
        result["iterations"] = iteration
        _log(f"  [v1.6 layout] 迭代 {iteration}/{max_iterations}, scale={current_scale[0]}:{current_scale[1]}")

        # SaveAs → Close → Reopen
        drw = _save_close_reopen(sw, drw_path, log_fn=_log, doc=drw)
        if drw is None:
            result["error"] = f"迭代 {iteration}: SaveAs/Close/Reopen 失败"
            _log(f"  [v1.6 layout] {result['error']}")
            return result

        # 测量持久化后的 outline
        outlines = _measure_persisted_outlines(drw, log_fn=_log)
        _log(f"  [v1.6 layout] 持久化后测量 {len(outlines)} 个视图")

        # 安全检查：0 个视图视为失败（不能误判为成功）
        if not outlines:
            _log(f"  [v1.6 layout] ! 迭代 {iteration} 失败: 测量到 0 个视图，无法验证布局")
            result["error"] = f"迭代 {iteration}: 测量到 0 个视图"
            # 尝试降比例继续
            if current_scale_idx + 1 >= len(scale_ladder):
                _write_layout_json(drw_path, result)
                return result
            current_scale_idx += 1
            current_scale = scale_ladder[current_scale_idx]
            new_n, new_d = current_scale
            _log(f"  [v1.6 layout] 降比例至 {new_n}:{new_d}")
            _current_views = _get_all_views(drw, log_fn=_log)
            for idx, view_obj in enumerate(_current_views):
                try:
                    _set_view_scale(view_obj, new_n, new_d)
                except Exception as e:
                    _log(f"    view[{idx}] ScaleRatio 失败: {e}")
            try:
                drw.ForceRebuild3(False)
            except Exception:
                pass
            time.sleep(0.5)
            continue

        # 保存/重开后先按目标中心重新定位，避免“在框内但偏离参考布局”被误判成功。
        _current_views = _get_all_views(drw, log_fn=_log)
        applied_centers = _apply_target_centers_to_views(_current_views, centers, log_fn=_log)
        if applied_centers:
            result["target_centers_applied"] = {
                key: [round(value[0], 6), round(value[1], 6)]
                for key, value in applied_centers.items()
            }
            try:
                drw.ForceRebuild3(False)
            except Exception:
                pass
            time.sleep(0.5)
            outlines = _measure_persisted_outlines(drw, log_fn=_log)
            _log(f"  [v1.6 layout] 目标中心重定位后测量 {len(outlines)} 个视图")
            if not outlines:
                result["error"] = f"迭代 {iteration}: 目标中心重定位后测量到 0 个视图"
                _write_layout_json(drw_path, result)
                return result

            # 目标中心必须再次落盘并重开验证；否则后续 sidecar/QC 可能读取到旧布局。
            drw = _save_close_reopen(sw, drw_path, log_fn=_log, doc=drw)
            if drw is None:
                result["error"] = f"迭代 {iteration}: 目标中心落盘后 SaveAs/Close/Reopen 失败"
                _write_layout_json(drw_path, result)
                return result
            result["target_centers_persisted"] = True
            outlines = _measure_persisted_outlines(drw, log_fn=_log)
            _log(f"  [v1.6 layout] 目标中心落盘重开后测量 {len(outlines)} 个视图")
            if not outlines:
                result["error"] = f"迭代 {iteration}: 目标中心落盘重开后测量到 0 个视图"
                _write_layout_json(drw_path, result)
                return result

        # 检测 overlap 和 out_of_frame
        overlap_pairs = _detect_overlap(outlines)
        out_of_frame = _detect_out_of_frame(outlines)
        target_outline_size_issues = _target_outline_size_issues(
            outlines,
            centers,
            target_outlines,
            target_outline_tolerance,
        )
        blocking_target_outline_issues = _blocking_target_outline_issues(target_outline_size_issues)
        warning_target_outline_issues = [
            item for item in target_outline_size_issues if not item.get("blocking", True)
        ]
        target_outline_scale_direction = _target_outline_scale_direction(blocking_target_outline_issues)

        result["final_outlines"] = outlines
        result["overlap_pairs"] = overlap_pairs
        result["out_of_frame"] = out_of_frame
        result["target_outline_size_issues"] = target_outline_size_issues
        result["target_outline_size_blocking_issues"] = blocking_target_outline_issues
        result["target_outline_size_warning_issues"] = warning_target_outline_issues
        result["target_outline_size_pass"] = not bool(blocking_target_outline_issues)
        result["target_outline_scale_direction"] = target_outline_scale_direction
        result["final_scale"] = f"{current_scale[0]}:{current_scale[1]}"

        if not overlap_pairs and not out_of_frame and not blocking_target_outline_issues:
            result["success"] = True
            _log(f"  [v1.6 layout] ✓ 迭代 {iteration} 成功: 无 overlap, 无 out_of_frame")
            # 写 persisted_layout.json
            _write_layout_json(drw_path, result)
            return result

        if target_outline_size_issues:
            _log(f"  [v1.6 layout] ! target outline mismatch: {target_outline_size_issues[:4]}")
        _log(
            f"  [v1.6 layout] ! 迭代 {iteration} 失败: "
            f"overlap={len(overlap_pairs)}, out_of_frame={len(out_of_frame)}, "
            f"target_outline_blocking={len(blocking_target_outline_issues)}, "
            f"target_outline_warning={len(warning_target_outline_issues)}, "
            f"target_outline_direction={target_outline_scale_direction or 'n/a'}"
        )

        # v1.6: 位置调整在 save/reopen 后不持久化，直接降比例解决 overlap/out_of_frame
        _current_views = _get_all_views(drw, log_fn=_log)
        _log(f"  [v1.6 layout] 从 Reopen 后的 drw 获取 {len(_current_views)} 个视图")

        next_scale_idx = current_scale_idx + 1
        scale_action = "smaller"
        if (
            blocking_target_outline_issues
            and not overlap_pairs
            and not out_of_frame
            and target_outline_scale_direction == "too_small"
        ):
            next_scale_idx = current_scale_idx - 1
            scale_action = "larger"

        if next_scale_idx < 0 or next_scale_idx >= len(scale_ladder):
            result["error"] = f"迭代 {iteration}: 比例梯已耗尽，仍无法满足布局要求"
            _log(f"  [v1.6 layout] {result['error']}")
            _write_layout_json(drw_path, result)
            return result

        current_scale_idx = next_scale_idx
        current_scale = scale_ladder[current_scale_idx]
        new_n, new_d = current_scale

        _log(f"  [v1.6 layout] 调整比例({scale_action})至 {new_n}:{new_d}")

        # 设置所有视图比例
        for idx, view_obj in enumerate(_current_views):
            try:
                ok_sc = _set_view_scale(view_obj, new_n, new_d)
                _log(f"    view[{idx}] ScaleRatio -> {new_n}:{new_d}  ok={ok_sc}")
            except Exception as e:
                _log(f"    view[{idx}] ScaleRatio 失败: {e}")

        try:
            drw.ForceRebuild3(False)
        except Exception:
            pass

        # 重新设置视图位置到 centers（按顺序匹配）
        _center_values = list(centers.values())
        for idx, view_obj in enumerate(_current_views):
            if idx < len(_center_values):
                nx, ny = _center_values[idx]
                try:
                    _set_view_position(view_obj, nx, ny)
                except Exception as e:
                    _log(f"    view[{idx}] Position 失败: {e}")

        try:
            drw.ForceRebuild3(False)
        except Exception:
            pass

        time.sleep(0.5)  # 等待 SW 重建

    # 达到最大迭代次数
    result["error"] = f"达到最大迭代次数 {max_iterations}，仍无法满足布局要求"
    _write_layout_json(drw_path, result)
    return result


def _write_layout_json(drw_path: str, result: dict) -> None:
    """写 persisted_layout.json 到 drw_path 同级目录"""
    try:
        drw_dir = Path(drw_path).parent
        layout_json_path = drw_dir / "persisted_layout.json"
        # 序列化（outline 中的 float 需转为可序列化）
        serializable = {
            "success": result.get("success", False),
            "iterations": result.get("iterations", 0),
            "start_scale": result.get("start_scale", ""),
            "final_scale": result.get("final_scale", ""),
            "final_outlines": {k: list(v) for k, v in result.get("final_outlines", {}).items()},
            "target_outline_size_pass": result.get("target_outline_size_pass", True),
            "target_outline_size_issues": result.get("target_outline_size_issues", []),
            "target_outline_size_blocking_issues": result.get("target_outline_size_blocking_issues", []),
            "target_outline_size_warning_issues": result.get("target_outline_size_warning_issues", []),
            "target_outline_scale_direction": result.get("target_outline_scale_direction", ""),
            "overlap_pairs": result.get("overlap_pairs", []),
            "out_of_frame": result.get("out_of_frame", []),
            "error": result.get("error", ""),
            "target_centers_applied": result.get("target_centers_applied", {}),
            "target_centers_persisted": result.get("target_centers_persisted", False),
        }
        with open(layout_json_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass
